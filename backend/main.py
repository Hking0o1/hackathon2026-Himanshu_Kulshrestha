from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.queue_manager import manager

try:
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError:  # pragma: no cover - optional runtime dependency
    FastAPI = None  # type: ignore


def _require_fastapi() -> None:
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Run `pip install -r requirements.txt` first.")


def create_app() -> Any:
    _require_fastapi()
    app = FastAPI(title="ShopWave Auto-Agent", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup() -> None:
        await manager.bootstrap()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/tickets")
    async def tickets() -> dict[str, Any]:
        return manager.snapshot()

    @app.get("/audit")
    async def audit() -> Any:
        return manager.get_audit()

    @app.get("/audit/{ticket_id}")
    async def audit_for_ticket(ticket_id: str) -> Any:
        payload = manager.get_audit(ticket_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Ticket audit not found")
        return payload

    @app.get("/stats")
    async def stats() -> dict[str, Any]:
        return manager.stats()

    @app.post("/run")
    async def run_agent(x_admin_token: str = Header(default="")) -> JSONResponse:
        if x_admin_token != manager.settings.admin_token:
            raise HTTPException(status_code=401, detail="Invalid ADMIN_TOKEN")
        stats = await manager.run_all()
        return JSONResponse(stats)

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def event_source() -> Any:
            queue = manager.events.subscribe()
            try:
                yield f"data: {json.dumps({'type': 'snapshot', **manager.snapshot()})}\n\n"
                while True:
                    event = await queue.get()
                    yield f"data: {json.dumps(event)}\n\n"
            finally:
                manager.events.unsubscribe(queue)

        return StreamingResponse(event_source(), media_type="text/event-stream")

    return app


app = create_app() if FastAPI is not None else None
