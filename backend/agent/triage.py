from __future__ import annotations

from backend.db.models import TriageResult
from backend.llm.huggingface_client import HuggingFaceClient


class TriageEngine:
    LABELS = (
        "REFUND_REQUEST",
        "RETURN_REQUEST",
        "WARRANTY_CLAIM",
        "ORDER_STATUS",
        "ORDER_CANCEL",
        "GENERAL_FAQ",
    )

    def __init__(self) -> None:
        self.client = HuggingFaceClient()

    async def classify(self, ticket: dict[str, str]) -> TriageResult:
        text = f"{ticket['subject']} {ticket['body']}"
        response = await self.client.classify_zero_shot(text, self.LABELS)
        return TriageResult(
            category=response["label"],
            confidence=response["confidence"],
            provider=response["provider"],
        )

