from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import Settings
from backend.db.models import AuditEntry, DeadLetterEntry, RuntimeStore


class AuditWriter:
    def __init__(self, settings: Settings, store: RuntimeStore) -> None:
        self.settings = settings
        self.store = store

    async def write_entry(self, entry: AuditEntry) -> None:
        self.store.audit_entries.append(entry)
        await self.export_json()
        await self._write_postgres_entry(entry)

    async def write_dead_letter(self, entry: DeadLetterEntry) -> None:
        self.store.dead_letters.append(entry)
        await self._write_postgres_dead_letter(entry)

    async def export_json(self) -> None:
        payload = [entry.to_dict() for entry in self.store.audit_entries]
        self.settings.audit_log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def stats(self) -> dict[str, Any]:
        resolved = sum(1 for ticket in self.store.tickets if ticket["status"] == "RESOLVED")
        escalated = sum(1 for ticket in self.store.tickets if ticket["status"] == "ESCALATED")
        dead = sum(1 for ticket in self.store.tickets if ticket["status"] == "DEAD")
        confidences = [entry.confidence_final for entry in self.store.audit_entries]
        avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
        return {
            "total": len(self.store.tickets),
            "resolved": resolved,
            "escalated": escalated,
            "dead": dead,
            "avg_confidence": avg_confidence,
        }

    async def _write_postgres_entry(self, entry: AuditEntry) -> None:
        await self._safe_asyncpg_write(
            "INSERT INTO audit_log (ticket_id, worker_id, triage_data, thoughts, tool_calls, confidence_final, decision, resolution_type, flags, llm_providers, policy_explanation, total_latency_ms) VALUES ($1,$2,$3::jsonb,$4::jsonb,$5::jsonb,$6,$7,$8,$9::jsonb,$10::jsonb,$11,$12)",
            (
                entry.ticket_id,
                entry.worker_id,
                json.dumps(entry.triage),
                json.dumps(entry.react_loop["thoughts"]),
                json.dumps(entry.react_loop["tool_calls"]),
                entry.confidence_final,
                entry.decision,
                entry.resolution_type,
                json.dumps(entry.flags),
                json.dumps(entry.llm_providers_used),
                entry.policy_explanation,
                entry.total_latency_ms,
            ),
        )

    async def _write_postgres_dead_letter(self, entry: DeadLetterEntry) -> None:
        await self._safe_asyncpg_write(
            "INSERT INTO dead_letter_queue (ticket_id, failure_reason, last_error, retry_count, ticket_snapshot) VALUES ($1,$2,$3,$4,$5::jsonb)",
            (
                entry.ticket_id,
                entry.failure_reason,
                entry.last_error,
                entry.retry_count,
                json.dumps(entry.ticket_snapshot),
            ),
        )

    async def _safe_asyncpg_write(self, query: str, params: tuple[Any, ...]) -> None:
        if "asyncpg" not in self.settings.database_url:
            return
        try:
            import asyncpg  # type: ignore
        except ImportError:
            return
        try:
            connection = await asyncpg.connect(self.settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
            try:
                await connection.execute(query, *params)
            finally:
                await connection.close()
        except Exception:
            return
