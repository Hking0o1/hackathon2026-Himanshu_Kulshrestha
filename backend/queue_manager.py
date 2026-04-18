from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from backend.agent.react_loop import ShopWaveAgent
from backend.agent.triage import TriageEngine
from backend.config import settings
from backend.db.audit_writer import AuditWriter
from backend.db.models import DeadLetterEntry, PrioritisedTicket, RuntimeStore, utc_now
from backend.llm.router import LLMRouter
from backend.tools.read_tools import ReadTools
from backend.tools.write_tools import WriteTools


def tier_to_priority(tier: int) -> int:
    return -tier


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            await queue.put(event)


class QueueManager:
    def __init__(self) -> None:
        self.settings = settings
        self.store = RuntimeStore()
        self.events = EventBroker()
        self.audit_writer = AuditWriter(self.settings, self.store)
        self.read_tools = ReadTools(self.store)
        self.write_tools = WriteTools(self.store, self.settings)
        self.triage = TriageEngine()
        self.llm_router = LLMRouter(self.settings, self.store)
        self.agent = ShopWaveAgent(self.settings, self.store, self.llm_router, self.read_tools, self.write_tools)
        self.queue: asyncio.PriorityQueue[PrioritisedTicket] = asyncio.PriorityQueue()

    async def bootstrap(self) -> None:
        self._reset_runtime()
        await self.llm_router.bootstrap()

    async def run_all(self, workers: int | None = None) -> dict[str, Any]:
        worker_count = workers or self.settings.worker_count
        self._reset_runtime()
        await self.llm_router.bootstrap()
        await self._load_tickets()
        self.store.last_run_started = utc_now()
        await self.events.publish({"type": "run_started", "started_at": self.store.last_run_started})
        tasks = [asyncio.create_task(self.worker(worker_id + 1)) for worker_id in range(worker_count)]
        await self.queue.join()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.store.last_run_finished = utc_now()
        await self.audit_writer.export_json()
        stats = self.stats()
        await self.events.publish({"type": "run_complete"} | stats)
        return stats

    async def worker(self, worker_id: int) -> None:
        while True:
            item = await self.queue.get()
            ticket = item.ticket
            self.store.worker_status[worker_id] = {"ticket_id": ticket["ticket_id"], "status": "PROCESSING"}
            ticket["assigned_worker"] = worker_id
            ticket["status"] = "PROCESSING"
            await self.events.publish(self._ticket_event(ticket, worker_id))
            try:
                triage_result = await self.triage.classify(ticket)
                ticket["category"] = triage_result.category
                audit_entry = await self.agent.process_ticket(ticket, worker_id, triage_result)
                await self.audit_writer.write_entry(audit_entry)
                for tool_call in audit_entry.react_loop["tool_calls"]:
                    await self.events.publish(
                        {
                            "type": "tool_call",
                            "ticket_id": ticket["ticket_id"],
                            "worker_id": worker_id,
                            "tool": tool_call["tool"],
                            "latency_ms": tool_call["latency_ms"],
                        }
                    )
                await self.events.publish(self._ticket_event(ticket, worker_id))
            except Exception as exc:
                ticket["status"] = "DEAD"
                ticket["resolution_type"] = "DEAD_LETTER"
                ticket["resolved_at"] = utc_now()
                entry = DeadLetterEntry(
                    ticket_id=ticket["ticket_id"],
                    failure_reason="unrecoverable_tool_failure",
                    last_error=str(exc),
                    retry_count=ticket.get("retry_count", 0),
                    ticket_snapshot=ticket,
                )
                await self.audit_writer.write_dead_letter(entry)
                await self.events.publish(self._ticket_event(ticket, worker_id))
            finally:
                self.store.worker_status[worker_id] = {"ticket_id": None, "status": "IDLE"}
                self.queue.task_done()

    def snapshot(self) -> dict[str, Any]:
        return {
            "tickets": self.store.tickets,
            "workers": self.store.worker_status,
            "stats": self.stats(),
            "started_at": self.store.last_run_started,
            "finished_at": self.store.last_run_finished,
        }

    def stats(self) -> dict[str, Any]:
        stats = self.audit_writer.stats()
        stats["queued"] = sum(1 for ticket in self.store.tickets if ticket["status"] == "QUEUED")
        stats["processing"] = sum(1 for ticket in self.store.tickets if ticket["status"] == "PROCESSING")
        return stats

    def get_audit(self, ticket_id: str | None = None) -> list[dict[str, Any]] | dict[str, Any] | None:
        payload = [entry.to_dict() for entry in self.store.audit_entries]
        if ticket_id is None:
            return payload
        for entry in payload:
            if entry["ticket_id"] == ticket_id:
                return entry
        return None

    async def _load_tickets(self) -> None:
        self.queue = asyncio.PriorityQueue()
        for ticket in self.store.tickets:
            item = PrioritisedTicket(
                priority=tier_to_priority(ticket["tier"]),
                created_at=ticket["created_at"],
                ticket=ticket,
            )
            await self.queue.put(item)

    def _reset_runtime(self) -> None:
        self.store.tickets = self._load_json(self.settings.data_dir / "tickets.json")
        customer_list = self._load_json(self.settings.data_dir / "customers.json")
        order_list = self._load_json(self.settings.data_dir / "orders.json")
        product_list = self._load_json(self.settings.data_dir / "products.json")
        self.store.customers = {customer["email"].lower(): customer for customer in customer_list}
        self.store.orders = {order["order_id"]: order for order in order_list}
        self.store.products = {product["product_id"]: product for product in product_list}
        self.store.knowledge_base = (self.settings.data_dir / "knowledge_base.md").read_text(encoding="utf-8")
        self.store.knowledge_sections = self._parse_kb_sections(self.store.knowledge_base)
        self.store.audit_entries = []
        self.store.dead_letters = []
        self.store.replies = []
        self.store.escalations = []
        self.store.worker_status = {worker_id: {"ticket_id": None, "status": "IDLE"} for worker_id in range(1, self.settings.worker_count + 1)}
        self.store.last_run_started = None
        self.store.last_run_finished = None

    def _load_json(self, path: Path) -> list[dict[str, Any]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _parse_kb_sections(self, markdown_text: str) -> list[dict[str, str]]:
        sections: list[dict[str, str]] = []
        current_title = "Overview"
        current_lines: list[str] = []
        for line in markdown_text.splitlines():
            if line.startswith("## "):
                if current_lines:
                    sections.append({"section": current_title, "content": " ".join(current_lines).strip()})
                current_title = line.replace("## ", "", 1).strip()
                current_lines = []
            elif line.startswith("# "):
                continue
            elif line.strip():
                current_lines.append(line.strip())
        if current_lines:
            sections.append({"section": current_title, "content": " ".join(current_lines).strip()})
        return sections

    def _ticket_event(self, ticket: dict[str, Any], worker_id: int | None) -> dict[str, Any]:
        return {
            "type": "ticket_update",
            "ticket_id": ticket["ticket_id"],
            "status": ticket["status"],
            "confidence": ticket["confidence"],
            "decision": ticket["resolution_type"],
            "worker_id": worker_id,
            "category": ticket.get("category"),
            "tier": ticket.get("tier"),
            "flags": ticket.get("flags", []),
        }


manager = QueueManager()
