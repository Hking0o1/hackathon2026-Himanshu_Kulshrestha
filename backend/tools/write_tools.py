from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from backend.config import Settings
from backend.db.models import RuntimeStore
from backend.tools.base import IrreversibleActionGuardError, chaotic_tool


class WriteTools:
    def __init__(self, store: RuntimeStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    @chaotic_tool
    async def check_refund_eligibility(self, order_id: str, reference_date: str | None = None) -> dict[str, Any]:
        order = self.store.orders.get(order_id)
        if not order:
            return {
                "order_id": order_id,
                "eligible": False,
                "reason": "Order could not be verified.",
                "amount": 0.0,
                "policy_flags": ["ORDER_NOT_FOUND"],
                "requires_escalation": True,
            }

        product = self.store.products.get(order["product_id"], {})
        policy_flags: list[str] = []
        requires_escalation = False

        if order["refund_status"] == "refunded":
            policy_flags.append("ALREADY_REFUNDED")
        if order["status"] == "shipped":
            policy_flags.append("NOT_DELIVERED")
        if order["status"] == "processing":
            policy_flags.append("PROCESSING_ONLY")
        if not product.get("returnable", True):
            policy_flags.append("NOT_RETURNABLE")

        order_notes = order.get("notes", "").lower()
        if "registered_online" in order_notes:
            policy_flags.append("REGISTERED_ONLINE")
        if "damaged_on_arrival" in order_notes:
            return {
                "order_id": order_id,
                "eligible": True,
                "reason": "Damaged on arrival overrides the standard return process.",
                "amount": order["amount"],
                "policy_flags": [],
                "requires_escalation": order["amount"] > self.settings.escalation_amount_threshold,
            }

        if order["status"] == "delivered":
            return_deadline = datetime.fromisoformat(order["return_deadline"]).date()
            if reference_date:
                today = datetime.fromisoformat(reference_date.replace("Z", "+00:00")).date()
            else:
                today = datetime.utcnow().date()
            if today > return_deadline:
                policy_flags.append("OUT_OF_WINDOW")

        eligible = not any(
            flag in {"ALREADY_REFUNDED", "NOT_DELIVERED", "NOT_RETURNABLE", "OUT_OF_WINDOW", "REGISTERED_ONLINE"}
            for flag in policy_flags
        )
        if eligible and order["status"] == "processing":
            eligible = False

        if eligible and order["amount"] > self.settings.escalation_amount_threshold:
            requires_escalation = True

        reason = (
            "Within the allowed policy window. No duplicate refund was found."
            if eligible
            else "Refund is not eligible under the current order and product policy checks."
        )

        return {
            "order_id": order_id,
            "eligible": eligible,
            "reason": reason,
            "amount": order["amount"],
            "policy_flags": policy_flags,
            "requires_escalation": requires_escalation,
        }

    @chaotic_tool
    async def issue_refund(
        self,
        order_id: str,
        amount: float,
        *,
        session_checked_orders: set[str] | None = None,
    ) -> dict[str, Any]:
        if not session_checked_orders or order_id not in session_checked_orders:
            raise IrreversibleActionGuardError(
                f"issue_refund blocked for {order_id}: check_refund_eligibility was not called first"
            )
        order = self.store.orders[order_id]
        order["refund_status"] = "refunded"
        return {
            "order_id": order_id,
            "amount_refunded": amount,
            "transaction_id": f"TXN-{uuid.uuid4()}",
            "status": "processed",
            "processing_time": "5-7 business days",
            "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }

    @chaotic_tool
    async def send_reply(self, ticket_id: str, message: str) -> dict[str, Any]:
        payload = {
            "ticket_id": ticket_id,
            "delivered": True,
            "message_preview": message[:160],
            "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        self.store.replies.append(payload | {"message": message})
        return payload

    @chaotic_tool
    async def escalate(self, ticket_id: str, summary: dict[str, Any], priority: str) -> dict[str, Any]:
        payload = {
            "ticket_id": ticket_id,
            "escalation_id": f"ESC-{uuid.uuid4()}",
            "routed_to": "tier-2-support",
            "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "summary": summary,
            "priority": priority,
        }
        self.store.escalations.append(payload)
        return payload
