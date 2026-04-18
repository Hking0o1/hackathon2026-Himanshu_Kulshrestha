from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import urlopen

from backend.config import settings


async def check_ollama_available() -> bool:
    try:
        with urlopen(f"{settings.ollama_base_url}/api/tags", timeout=2) as response:
            return response.status == 200 and bool(json.loads(response.read().decode("utf-8")))
    except (URLError, TimeoutError, OSError, ValueError):
        return False

