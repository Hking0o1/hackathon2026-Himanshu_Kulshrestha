from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from pprint import pprint

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.queue_manager import manager

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:  # pragma: no cover - optional dependency
    Console = None  # type: ignore
    Table = None  # type: ignore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ShopWave Auto-Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Process all 20 tickets")
    run_parser.add_argument("--workers", type=int, default=None, help="Override worker count")

    subparsers.add_parser("status", help="Show queue and worker state")

    audit_parser = subparsers.add_parser("audit", help="Print audit log")
    audit_parser.add_argument("ticket_id", nargs="?", default=None)

    subparsers.add_parser("stats", help="Show summary stats")
    subparsers.add_parser("export", help="Show audit_log.json path")
    return parser


async def cmd_run(workers: int | None) -> None:
    await manager.bootstrap()
    stats = await manager.run_all(workers)
    if Console:
        console = Console()
        table = Table(title="ShopWave Auto-Agent Run Summary")
        table.add_column("Metric")
        table.add_column("Value")
        for key, value in stats.items():
            table.add_row(key, str(value))
        console.print(table)
        console.print(f"Audit log exported to {settings.audit_log_path}")
    else:
        pprint(stats)
        print(f"Audit log exported to {settings.audit_log_path}")


async def cmd_status() -> None:
    await manager.bootstrap()
    snapshot = manager.snapshot()
    if Console:
        console = Console()
        table = Table(title="Current Ticket Snapshot")
        table.add_column("Ticket")
        table.add_column("Status")
        table.add_column("Tier")
        table.add_column("Category")
        for ticket in snapshot["tickets"]:
            table.add_row(ticket["ticket_id"], ticket["status"], str(ticket["tier"]), str(ticket.get("category")))
        console.print(table)
    else:
        pprint(snapshot)


async def cmd_audit(ticket_id: str | None) -> None:
    await manager.bootstrap()
    if settings.audit_log_path.exists():
        payload = json.loads(settings.audit_log_path.read_text(encoding="utf-8"))
    else:
        payload = manager.get_audit()
    if ticket_id:
        payload = next((entry for entry in payload if entry["ticket_id"] == ticket_id), None)
    print(json.dumps(payload, indent=2))


async def cmd_stats() -> None:
    await manager.bootstrap()
    print(json.dumps(manager.stats(), indent=2))


async def cmd_export() -> None:
    await manager.bootstrap()
    print(settings.audit_log_path)


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        asyncio.run(cmd_run(args.workers))
    elif args.command == "status":
        asyncio.run(cmd_status())
    elif args.command == "audit":
        asyncio.run(cmd_audit(args.ticket_id))
    elif args.command == "stats":
        asyncio.run(cmd_stats())
    elif args.command == "export":
        asyncio.run(cmd_export())


if __name__ == "__main__":
    main()
