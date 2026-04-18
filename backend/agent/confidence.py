from __future__ import annotations

from backend.db.models import LoopState


def compute_confidence(state: LoopState) -> float:
    classification_score = state.triage.confidence
    successful_calls = sum(1 for call in state.tool_calls if call.error is None)
    total_calls = max(len(state.tool_calls), 1)
    tool_success_rate = successful_calls / total_calls
    kb_called = any(call.tool == "search_knowledge_base" for call in state.tool_calls)
    policy_match_score = state.kb_relevance if kb_called else 0.5
    tier_policy_coverage = 1.0 if state.tier_is_known else 0.4
    confidence = (
        0.40 * classification_score
        + 0.30 * tool_success_rate
        + 0.20 * policy_match_score
        + 0.10 * tier_policy_coverage
    )
    return round(min(max(confidence, 0.0), 1.0), 3)

