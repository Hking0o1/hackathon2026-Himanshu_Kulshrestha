from __future__ import annotations

from typing import Any

from backend.db.models import LoopState


class GroqClient:
    async def reason(self, state: LoopState) -> dict[str, Any]:
        customer_name = state.customer["name"] if state.customer else "the customer"
        return {
            "thought": (
                f"I need to gather enough verified evidence for {customer_name} "
                f"before taking any irreversible action."
            ),
            "provider": "groq-mock",
        }

