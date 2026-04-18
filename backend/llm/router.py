from __future__ import annotations

from typing import Any

from backend.config import Settings
from backend.db.models import LoopState, RuntimeStore
from backend.llm.gemini_client import GeminiClient
from backend.llm.groq_client import GroqClient
from backend.llm.ollama_fallback import check_ollama_available, generate_json


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
        provider = response.get("provider", "groq-fallback")
        if provider.endswith("fallback") and self.ollama_available:
            ollama = await generate_json(
                prompt=str(
                    {
                        "ticket": state.ticket,
                        "category": state.triage.category,
                        "iteration": state.iteration,
                        "tool_history": [call.to_dict() for call in state.tool_calls[-4:]],
                    }
                ),
                system=(
                    "Return JSON only with a key named thought. "
                    "The thought must be one concise sentence about the next evidence gathering step."
                ),
            )
            if ollama and isinstance(ollama.get("thought"), str):
                response = {"thought": ollama["thought"].strip(), "provider": f"ollama:{self.settings.ollama_model}"}
                provider = response["provider"]
        if provider not in state.providers_used:
            state.providers_used.append(provider)
        return response

    async def escalation_summary(self, state: LoopState) -> dict[str, Any]:
        response = await self.gemini.build_escalation_summary(state)
        if response.get("_provider") not in (None, ""):
            provider = response.pop("_provider")
        elif self.settings.gemini_api_key:
            provider = f"gemini:{self.settings.gemini_model}"
        else:
            provider = "gemini-fallback"
        if provider == "gemini-fallback" and self.ollama_available:
            ollama = await generate_json(
                prompt=str(
                    {
                        "ticket": state.ticket,
                        "customer": state.customer,
                        "order": state.order,
                        "product": state.product,
                        "eligibility": state.eligibility,
                        "tool_calls": [call.to_dict() for call in state.tool_calls],
                        "confidence": state.confidence,
                        "priority": state.pending_priority,
                    }
                ),
                system=(
                    "Return JSON only with keys issue_summary, what_was_verified, what_was_attempted, "
                    "recommended_path, priority, confidence_at_escalation."
                ),
            )
            if ollama:
                response = {
                    "issue_summary": ollama.get("issue_summary", "Manual review required."),
                    "what_was_verified": ollama.get("what_was_verified", []),
                    "what_was_attempted": ollama.get("what_was_attempted", []),
                    "recommended_path": ollama.get("recommended_path", "Manual review required."),
                    "priority": ollama.get("priority", state.pending_priority),
                    "confidence_at_escalation": float(ollama.get("confidence_at_escalation", state.confidence)),
                }
                provider = f"ollama:{self.settings.ollama_model}"
        if provider not in state.providers_used:
            state.providers_used.append(provider)
        return response
