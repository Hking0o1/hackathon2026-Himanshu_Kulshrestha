from __future__ import annotations

from typing import Iterable

import httpx

from backend.config import settings


class HuggingFaceClient:
    def __init__(self) -> None:
        self.api_key = settings.huggingface_api_key
        self.model = settings.huggingface_model
        self.timeout = settings.llm_request_timeout

    async def classify_zero_shot(self, text: str, labels: Iterable[str]) -> dict[str, object]:
        label_list = list(labels)
        if self.api_key:
            live = await self._classify_live(text, label_list)
            if live is not None:
                return live
        return self._classify_fallback(text, label_list)

    async def _classify_live(self, text: str, labels: list[str]) -> dict[str, object] | None:
        url = f"https://router.huggingface.co/hf-inference/models/{self.model}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": text,
            "parameters": {
                "candidate_labels": labels,
                "multi_label": False,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception:
            return None

        if isinstance(data, list) and data:
            top = data[0]
            return {
                "label": top.get("label", "GENERAL_FAQ"),
                "confidence": round(float(top.get("score", 0.5)), 3),
                "provider": f"huggingface:{self.model}",
            }
        return None

    def _classify_fallback(self, text: str, labels: list[str]) -> dict[str, object]:
        normalized = text.lower()
        label = "GENERAL_FAQ"
        confidence = 0.74

        if any(term in normalized for term in ("cancel", "stop my order", "before it ships")):
            label = "ORDER_CANCEL"
            confidence = 0.9
        elif any(term in normalized for term in ("where is", "tracking", "in transit", "shipped")):
            label = "ORDER_STATUS"
            confidence = 0.87
        elif any(term in normalized for term in ("warranty", "stopped working", "broken after", "manufacturing defect")):
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
            "provider": "huggingface-fallback",
        }
