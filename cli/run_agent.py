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
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:  # pragma: no cover - optional dependency
    Console = None  # type: ignore
    Panel = None  # type: ignore
    Table = None  # type: ignore
    Text = None  # type: ignore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=_print_header("ShopWave Auto-Agent CLI"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Process all available tickets")
    run_parser.add_argument("--workers", type=int, default=None, help="Override worker count")

    subparsers.add_parser("status", help="Show queue and worker state")

    audit_parser = subparsers.add_parser("audit", help="Print audit log")
    audit_parser.add_argument("ticket_id", nargs="?", default=None)

    subparsers.add_parser("stats", help="Show summary stats")
    subparsers.add_parser("export", help="Show audit_log.json path")
    return parser


def _console() -> Console | None:
    return Console() if Console else None


def _print_header(title: str, subtitle: str | None = None) -> None:
    console = _console()
    banner_lines = [
        " '######::'##::::'##::'#######::'########::'##:::::'##::::'###::::'##::::'##:'########:",
        "'##... ##: ##:::: ##:'##.... ##: ##.... ##: ##:'##: ##:::'## ##::: ##:::: ##: ##.....::",
        " ##:::..:: ##:::: ##: ##:::: ##: ##:::: ##: ##: ##: ##::'##:. ##:: ##:::: ##: ##:::::::",
        ". ######:: #########: ##:::: ##: ########:: ##: ##: ##:'##:::. ##: ##:::: ##: ######:::",
        ":..... ##: ##.... ##: ##:::: ##: ##.....::: ##: ##: ##: #########:. ##:: ##:: ##...::::",
        "'##::: ##: ##:::: ##: ##:::: ##: ##:::::::: ##: ##: ##: ##.... ##::. ## ##::: ##:::::::",
        ". ######:: ##:::: ##:. #######:: ##::::::::. ###. ###:: ##:::: ##:::. ###:::: ########:",
        ":......:::..:::::..:::.......:::..::::::::::...::...:::..:::::..:::::...:::::........::",
        ":::'###::::'##::::'##:'########::'#######::::::::::::::'###:::::'######:::'########:'##::: ##:'########:",
        "::'## ##::: ##:::: ##:... ##..::'##.... ##::::::::::::'## ##:::'##... ##:: ##.....:: ###:: ##:... ##..::",
        ":'##:. ##:: ##:::: ##:::: ##:::: ##:::: ##:::::::::::'##:. ##:: ##:::..::: ##::::::: ####: ##:::: ##::::",
        "'##:::. ##: ##:::: ##:::: ##:::: ##:::: ##:'#######:'##:::. ##: ##::'####: ######::: ## ## ##:::: ##::::",
        " #########: ##:::: ##:::: ##:::: ##:::: ##:........: #########: ##::: ##:: ##...:::: ##. ####:::: ##::::",
        " ##.... ##: ##:::: ##:::: ##:::: ##:::: ##:::::::::: ##.... ##: ##::: ##:: ##::::::: ##:. ###:::: ##::::",
        " ##:::: ##:. #######::::: ##::::. #######::::::::::: ##:::: ##:. ######::: ########: ##::. ##:::: ##::::",
        "..:::::..:::.......::::::..::::::.......::::::::::::..:::::..:::......::::........::..::::..:::::..:::::",
    ]
    banner_text = "\n".join(banner_lines)
    if console and Panel and Text:
        heading = Text(banner_text, style="bold cyan")
        heading.append("\n\nSupport automation for live triage, escalation, and audit", style="italic dim")
        heading.append(f"\n{title}", style="bold magenta")
        if subtitle:
            heading.append(f"\n{subtitle}", style="bold green")
        max_width = max(len(line) for line in banner_lines)
        if console.width and console.width < max_width + 8:
            compact = Text()
            compact.append("ShopWave Auto-Agent\n", style="bold cyan")
            compact.append(f"{title}\n", style="bold magenta")
            if subtitle:
                compact.append(f"{subtitle}\n", style="bold green")
            compact.append("Support automation for live triage, escalation, and audit", style="italic dim")
            console.print(Panel.fit(compact, border_style="bright_blue", padding=(1, 1)))
        else:
            panel = Panel.fit(
                heading,
                border_style="bright_blue",
                padding=(1, 2),
                title="ShopWave",
                subtitle_align="right",
            )
            console.print(panel)
    else:
        banner = "= SHOPWAVE AUTO-AGENT ="
        border = "=" * len(banner)
        print(border)
        print(banner)
        print(f"[{title}]")
        if subtitle:
            print(f"[{subtitle}]")
        print(border)


def _print_table(title: str, mapping: dict[str, object]) -> None:
    console = _console()
    if console and Table:
        table = Table(title=title)
        table.add_column("Metric")
        table.add_column("Value")
        for key, value in mapping.items():
            table.add_row(str(key), str(value))
        console.print(table)
    else:
        print(title)
        pprint(mapping)


def _print_line(message: str) -> None:
    console = _console()
    if console:
        console.print(message)
    else:
        print(message)


def _format_ticket_event(event: dict[str, object]) -> str:
    ticket_id = event.get("ticket_id", "unknown")
    status = event.get("status", "unknown")
    worker_id = event.get("worker_id", "-")
    category = event.get("category") or "pending"
    return f"[worker {worker_id}] {ticket_id} -> {status} ({category})"


async def _stream_run_events(stop_event: asyncio.Event) -> None:
    queue = manager.events.subscribe()
    try:
        while not stop_event.is_set():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            event_type = event.get("type")
            if event_type == "run_started":
                _print_line(f"[cyan]Run started[/cyan] at {event.get('started_at')}")
            elif event_type == "ticket_update":
                _print_line(_format_ticket_event(event))
            elif event_type == "tool_call":
                _print_line(
                    f"  tool: {event.get('ticket_id')} -> {event.get('tool')} ({event.get('latency_ms')}ms)"
                )
            elif event_type == "run_complete":
                _print_line(
                    f"[green]Run complete[/green] resolved={event.get('resolved')} escalated={event.get('escalated')} dead={event.get('dead')}"
                )
    except asyncio.CancelledError:
        return
    finally:
        manager.events.unsubscribe(queue)


async def _heartbeat(stop_event: asyncio.Event) -> None:
    try:
        while not stop_event.is_set():
            await asyncio.sleep(5)
            if stop_event.is_set():
                break
            snapshot = manager.snapshot()
            stats = snapshot["stats"]
            _print_line(
                f"[dim]heartbeat[/dim] queued={stats.get('queued')} processing={stats.get('processing')} "
                f"resolved={stats.get('resolved')} escalated={stats.get('escalated')}"
            )
    except asyncio.CancelledError:
        return


async def cmd_run(workers: int | None) -> None:
    await manager.bootstrap()
    _print_header(
        "ShopWave Auto-Agent Run",
        f"workers={workers or settings.worker_count} | audit={settings.audit_log_path.name}",
    )
    stop_event = asyncio.Event()
    event_task = asyncio.create_task(_stream_run_events(stop_event))
    heartbeat_task = asyncio.create_task(_heartbeat(stop_event))

    try:
        stats = await manager.run_all(workers)
    except asyncio.CancelledError:
        _print_line("[yellow]Run cancelled gracefully.[/yellow]")
        partial = manager.stats()
        _print_table("Partial Run Summary", partial)
        return
    except Exception as exc:
        _print_line(f"[red]Run failed:[/red] {exc}")
        partial = manager.stats()
        _print_table("Partial Run Summary", partial)
        return
    finally:
        stop_event.set()
        event_task.cancel()
        heartbeat_task.cancel()
        await asyncio.gather(event_task, heartbeat_task, return_exceptions=True)

    _print_table("ShopWave Auto-Agent Run Summary", stats)
    _print_line(f"Audit log exported to {settings.audit_log_path}")


async def cmd_status() -> None:
    await manager.bootstrap()
    snapshot = manager.snapshot()
    console = _console()
    if console and Table:
        _print_header("ShopWave Auto-Agent Status", "Current queue-ready view of tickets and workers")
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
    _print_header(
        "ShopWave Auto-Agent Audit",
        f"Ticket audit details{f' for {ticket_id}' if ticket_id else ''}",
    )
    if settings.audit_log_path.exists():
        payload = json.loads(settings.audit_log_path.read_text(encoding="utf-8"))
    else:
        payload = manager.get_audit()
    if ticket_id:
        payload = next((entry for entry in payload if entry["ticket_id"] == ticket_id), None)
    print(json.dumps(payload, indent=2))


async def cmd_stats() -> None:
    await manager.bootstrap()
    _print_header("ShopWave Auto-Agent Stats", "Current aggregate view")
    print(json.dumps(manager.stats(), indent=2))


async def cmd_export() -> None:
    await manager.bootstrap()
    _print_header("ShopWave Auto-Agent Export", "Audit log location")
    print(settings.audit_log_path)


def main() -> None:
    args = build_parser().parse_args()
    try:
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
    except KeyboardInterrupt:
        _print_line("[yellow]Command interrupted by user.[/yellow]")


if __name__ == "__main__":
    main()
