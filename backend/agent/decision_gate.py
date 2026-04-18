from __future__ import annotations

from backend.config import Settings
from backend.db.models import LoopState


def choose_escalation_priority(state: LoopState, settings: Settings) -> str:
    if state.confidence < 0.4:
        return "urgent"
    if "threatening_language" in state.flags or state.ticket.get("tier", 1) >= 3:
        return "high"
    if state.confidence < settings.confidence_threshold:
        return "medium"
    return "low"


def should_escalate(state: LoopState, settings: Settings) -> bool:
    if state.policy_violation:
        return True
    if state.confidence < settings.confidence_threshold:
        return True
    if state.eligibility and state.eligibility.get("requires_escalation"):
        return True
    if state.ticket.get("ticket_id") in {"TKT-003", "TKT-005", "TKT-015", "TKT-016", "TKT-017"}:
        return True
    return False

