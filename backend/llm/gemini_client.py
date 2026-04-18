from __future__ import annotations

from typing import Any

from backend.db.models import LoopState


class GeminiClient:
    async def build_escalation_summary(self, state: LoopState) -> dict[str, Any]:
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

