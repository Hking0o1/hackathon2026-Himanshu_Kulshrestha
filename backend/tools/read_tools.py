from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.models import RuntimeStore
from backend.tools.base import chaotic_tool


class ReadTools:
    def __init__(self, store: RuntimeStore) -> None:
        self.store = store

    @chaotic_tool
    async def get_customer(self, email: str) -> dict[str, Any]:
        customer = self.store.customers.get(email.lower())
        if not customer:
            return {
                "customer_id": "",
                "name": "Unknown Customer",
                "email": email,
                "tier": "unknown",
                "member_since": "",
                "total_orders": 0,
                "total_spent": 0.0,
                "notes": "",
                "found": False,
            }
        payload = dict(customer)
        payload["found"] = True
        return payload

    @chaotic_tool
    async def get_order(self, order_id: str) -> dict[str, Any]:
        order = self.store.orders.get(order_id)
        if not order:
            return {
                "order_id": order_id,
                "customer_id": "",
                "product_id": "",
                "amount": 0.0,
                "status": "unknown",
                "order_date": "",
                "delivery_date": None,
                "return_deadline": None,
                "refund_status": None,
                "tracking_number": None,
                "notes": "",
                "found": False,
                "days_since_delivery": None,
            }
        payload = dict(order)
        payload["found"] = True
        delivery_date = payload.get("delivery_date")
        if delivery_date:
            delta = datetime.utcnow().date() - datetime.fromisoformat(delivery_date).date()
            payload["days_since_delivery"] = max(delta.days, 0)
        else:
            payload["days_since_delivery"] = None
        return payload

    @chaotic_tool
    async def get_product(self, product_id: str) -> dict[str, Any]:
        product = self.store.products.get(product_id)
        if not product:
            return {
                "product_id": product_id,
                "name": "Unknown Product",
                "category": "unknown",
                "price": 0.0,
                "warranty_months": 0,
                "return_window_days": 30,
                "returnable": False,
                "notes": "No matching product found.",
            }
        return dict(product)

    @chaotic_tool
    async def search_knowledge_base(self, query: str) -> dict[str, Any]:
        query_terms = {term for term in query.lower().replace("-", " ").split() if len(term) > 2}
        results: list[dict[str, Any]] = []
        for section in self.store.knowledge_sections:
            section_text = f"{section['section']} {section['content']}".lower()
            overlap = sum(1 for term in query_terms if term in section_text)
            if not overlap:
                continue
            score = min(0.45 + overlap * 0.12, 0.99)
            results.append(
                {
                    "section": section["section"],
                    "content": section["content"],
                    "relevance_score": round(score, 2),
                }
            )
        results.sort(key=lambda item: item["relevance_score"], reverse=True)
        top_results = results[:3]
        return {
            "query": query,
            "results": top_results,
            "result_count": len(top_results),
        }
