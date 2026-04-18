from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import httpx

from backend.config import settings
from backend.llm.utils import parse_json_object


async def check_ollama_available() -> bool:
    try:
        with urlopen(f"{settings.ollama_base_url}/api/tags", timeout=2) as response:
            return response.status == 200 and bool(json.loads(response.read().decode("utf-8")))
    except (URLError, TimeoutError, OSError, ValueError):
        return False


async def generate_json(prompt: str, system: str) -> dict[str, Any] | None:
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "format": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.llm_request_timeout) as client:
            response = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return parse_json_object(data.get("response", ""))
    except Exception:
        return None
