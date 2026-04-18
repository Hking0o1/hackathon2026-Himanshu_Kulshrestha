from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings
from backend.db.models import LoopState
from backend.llm.utils import parse_json_object


class GroqClient:
    def __init__(self) -> None:
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.timeout = settings.llm_request_timeout

    async def reason(self, state: LoopState) -> dict[str, Any]:
        if self.api_key:
            live = await self._reason_live(state)
            if live is not None:
                return live
        customer_name = state.customer["name"] if state.customer else "the customer"
        return {
            "thought": (
                f"I need to gather enough verified evidence for {customer_name} "
                f"before taking any irreversible action."
            ),
            "provider": "groq-fallback",
        }

    async def _reason_live(self, state: LoopState) -> dict[str, Any] | None:
        system_prompt = (
            "You are ShopWave's autonomous support reasoning assistant. "
            "Return JSON only with a single key named thought. "
            "The thought must be 1-2 concise sentences about the next evidence-gathering step."
        )
        summary = {
            "ticket": {
                "ticket_id": state.ticket["ticket_id"],
                "subject": state.ticket["subject"],
                "body": state.ticket["body"],
                "order_id": state.ticket.get("order_id"),
            },
            "category": state.triage.category,
            "iteration": state.iteration,
            "tool_history": [call.to_dict() for call in state.tool_calls[-4:]],
            "customer": state.customer,
            "order": state.order,
            "product": state.product,
            "confidence": state.confidence,
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(summary)},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = parse_json_object(content)
                thought = parsed.get("thought")
                if not isinstance(thought, str) or not thought.strip():
                    return None
                return {"thought": thought.strip(), "provider": f"groq:{self.model}"}
        except Exception:
            return None
