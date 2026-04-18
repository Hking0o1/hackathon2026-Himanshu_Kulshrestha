from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings
from backend.db.models import LoopState
from backend.llm.utils import parse_json_object


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.timeout = settings.llm_request_timeout

    async def build_escalation_summary(self, state: LoopState) -> dict[str, Any]:
        if self.api_key:
            live = await self._build_live(state)
            if live is not None:
                return live

        ticket = state.ticket
        customer = state.customer or {"name": "Unknown Customer", "customer_id": "N/A", "tier": "unknown"}
        verified_bits = []
        if state.customer:
            verified_bits.append(f"Customer tier is {customer['tier']}")
        if state.order:
            verified_bits.append(f"Order status is {state.order['status']}")
        if state.product:
            verified_bits.append(f"Product policy notes: {state.product['notes']}")
        if state.eligibility:
            verified_bits.append(f"Eligibility result: {state.eligibility['reason']}")

        attempted = [f"Called {call.tool}" for call in state.tool_calls]
        return {
            "issue_summary": (
                f"Customer {customer['name']} ({customer['tier']}, {customer['customer_id']}) "
                f"needs manual support for ticket {ticket['ticket_id']}."
            ),
            "what_was_verified": verified_bits or ["Insufficient customer data was available."],
            "what_was_attempted": attempted,
            "recommended_path": state.policy_explanation or "Review the ticket manually and contact the customer.",
            "priority": state.pending_priority,
            "confidence_at_escalation": state.confidence,
        }

    async def _build_live(self, state: LoopState) -> dict[str, Any] | None:
        prompt = {
            "ticket": state.ticket,
            "customer": state.customer,
            "order": state.order,
            "product": state.product,
            "eligibility": state.eligibility,
            "tool_calls": [call.to_dict() for call in state.tool_calls],
            "confidence": state.confidence,
            "priority": state.pending_priority,
            "policy_explanation": state.policy_explanation,
        }
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Return only JSON with keys issue_summary, what_was_verified, "
                                "what_was_attempted, recommended_path, priority, confidence_at_escalation. "
                                f"Use this case context: {prompt}"
                            )
                        }
                    ]
                }
            ]
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        params = {"key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, params=params, json=body)
                response.raise_for_status()
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = parse_json_object(text)
                return {
                    "issue_summary": parsed.get("issue_summary", "Manual review required."),
                    "what_was_verified": parsed.get("what_was_verified", []),
                    "what_was_attempted": parsed.get("what_was_attempted", []),
                    "recommended_path": parsed.get("recommended_path", "Manual review required."),
                    "priority": parsed.get("priority", state.pending_priority),
                    "confidence_at_escalation": float(parsed.get("confidence_at_escalation", state.confidence)),
                    "_provider": f"gemini:{self.model}",
                }
        except Exception:
            return None
