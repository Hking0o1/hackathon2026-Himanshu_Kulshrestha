from __future__ import annotations

from typing import Any

from backend.config import Settings
from backend.db.models import LoopState, RuntimeStore
from backend.llm.gemini_client import GeminiClient
from backend.llm.groq_client import GroqClient
from backend.llm.ollama_fallback import check_ollama_available


class LLMRouter:
    def __init__(self, settings: Settings, store: RuntimeStore) -> None:
        self.settings = settings
        self.store = store
        self.groq = GroqClient()
        self.gemini = GeminiClient()
        self.ollama_available = False

    async def bootstrap(self) -> None:
        self.ollama_available = await check_ollama_available()

    async def think(self, state: LoopState) -> dict[str, Any]:
        response = await self.groq.reason(state)
        if "groq-mock" not in state.providers_used:
            state.providers_used.append("groq-mock")
        return response

    async def escalation_summary(self, state: LoopState) -> dict[str, Any]:
        if "gemini-mock" not in state.providers_used:
            state.providers_used.append("gemini-mock")
        return await self.gemini.build_escalation_summary(state)
