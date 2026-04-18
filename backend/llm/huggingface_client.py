from __future__ import annotations

from typing import Iterable


class HuggingFaceClient:
    async def classify_zero_shot(self, text: str, labels: Iterable[str]) -> dict[str, object]:
        normalized = text.lower()
        label = "GENERAL_FAQ"
        confidence = 0.74

        if any(term in normalized for term in ("cancel", "stop my order", "before it ships")):
            label = "ORDER_CANCEL"
            confidence = 0.9
        elif any(term in normalized for term in ("where is", "tracking", "in transit", "shipped")):
            label = "ORDER_STATUS"
            confidence = 0.87
        elif any(term in normalized for term in ("warranty", "stopped working", "broken after")):
            label = "WARRANTY_CLAIM"
            confidence = 0.91
        elif any(term in normalized for term in ("refund", "money back", "damaged", "defective", "wrong size")):
            label = "REFUND_REQUEST"
            confidence = 0.89
        elif any(term in normalized for term in ("return", "send it back", "wrong colour", "wrong color", "exchange")):
            label = "RETURN_REQUEST"
            confidence = 0.85

        if label not in labels:
            label = "GENERAL_FAQ"

        return {
            "label": label,
            "confidence": confidence,
            "provider": "huggingface-bart-mock",
        }

