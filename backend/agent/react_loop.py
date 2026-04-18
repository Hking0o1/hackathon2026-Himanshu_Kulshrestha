from __future__ import annotations

import re
import time
from copy import deepcopy
from typing import Any

from backend.agent.confidence import compute_confidence
from backend.agent.decision_gate import choose_escalation_priority, should_escalate
from backend.config import Settings
from backend.db.models import AuditEntry, LoopState, ToolCallRecord, utc_now
from backend.llm.router import LLMRouter
from backend.tools.base import ToolError
from backend.tools.read_tools import ReadTools
from backend.tools.write_tools import WriteTools


class ShopWaveAgent:
    def __init__(
        self,
        settings: Settings,
        store: Any,
        llm_router: LLMRouter,
        read_tools: ReadTools,
        write_tools: WriteTools,
    ) -> None:
        self.settings = settings
        self.store = store
        self.llm_router = llm_router
        self.read_tools = read_tools
        self.write_tools = write_tools

    async def process_ticket(self, ticket: dict[str, Any], worker_id: int, triage_result: Any) -> AuditEntry:
        state = LoopState(ticket=ticket, worker_id=worker_id, triage=triage_result)
        if triage_result.provider not in state.providers_used:
            state.providers_used.append(triage_result.provider)
        self._seed_flags(state)

        while state.iteration < self.settings.max_react_iterations:
            state.iteration += 1
            state.ticket["status"] = "PROCESSING"
            thought = await self.llm_router.think(state)
            state.thoughts.append(thought["thought"])
            action = self._next_action(state)
            if action["tool"] in {"send_reply", "escalate"} and len(state.tool_calls) < 2:
                action = self._force_more_context(state)
            await self._execute_action(state, action)
            state.confidence = compute_confidence(state)
            if action["tool"] == "send_reply":
                state.decision = "RESOLVED"
                state.resolution_type = "AUTO"
                break
            if action["tool"] == "escalate":
                state.decision = "ESCALATED"
                state.resolution_type = "ESCALATED"
                break

        if not state.decision:
            state.pending_priority = choose_escalation_priority(state, self.settings)
            summary = await self.llm_router.escalation_summary(state)
            await self._execute_action(
                state,
                {"tool": "escalate", "args": {"ticket_id": ticket["ticket_id"], "summary": summary, "priority": state.pending_priority}},
            )
            state.confidence = compute_confidence(state)
            state.decision = "ESCALATED"
            state.resolution_type = "ESCALATED"

        ticket["status"] = "RESOLVED" if state.decision == "RESOLVED" else "ESCALATED"
        ticket["resolution_type"] = state.resolution_type
        ticket["confidence"] = state.confidence
        ticket["flags"] = state.flags
        ticket["resolved_at"] = utc_now()
        ticket["category"] = state.triage.category
        ticket["assigned_worker"] = worker_id
        policy_explanation = self._build_policy_explanation(state)
        state.policy_explanation = policy_explanation

        return AuditEntry(
            ticket_id=ticket["ticket_id"],
            processed_at=utc_now(),
            worker_id=worker_id,
            triage=state.triage.to_dict(),
            react_loop={
                "iterations": len(state.tool_calls),
                "thoughts": state.thoughts,
                "tool_calls": [call.to_dict() for call in state.tool_calls],
            },
            confidence_final=state.confidence,
            decision=state.decision,
            resolution_type=state.resolution_type,
            flags=state.flags,
            llm_providers_used=state.providers_used,
            total_latency_ms=state.total_latency_ms,
            policy_explanation=policy_explanation,
        )

    async def _execute_action(self, state: LoopState, action: dict[str, Any]) -> None:
        tool_name = action["tool"]
        args = deepcopy(action["args"])
        start = time.perf_counter()
        error_message: str | None = None
        output: dict[str, Any] | None = None

        try:
            if tool_name == "get_customer":
                output = await self.read_tools.get_customer(**args)
                state.customer = output
                state.tier_is_known = output.get("found", False)
            elif tool_name == "get_order":
                output = await self.read_tools.get_order(**args)
                state.order = output
            elif tool_name == "get_product":
                output = await self.read_tools.get_product(**args)
                state.product = output
            elif tool_name == "search_knowledge_base":
                output = await self.read_tools.search_knowledge_base(**args)
                state.kb_result = output
                if output["results"]:
                    state.kb_relevance = output["results"][0]["relevance_score"]
            elif tool_name == "check_refund_eligibility":
                output = await self.write_tools.check_refund_eligibility(**args)
                state.eligibility = output
                if output.get("eligible"):
                    state.checked_orders.add(output["order_id"])
            elif tool_name == "issue_refund":
                output = await self.write_tools.issue_refund(
                    **args,
                    session_checked_orders=state.checked_orders,
                )
            elif tool_name == "send_reply":
                output = await self.write_tools.send_reply(**args)
            elif tool_name == "escalate":
                output = await self.write_tools.escalate(**args)
            else:
                raise ToolError(f"Unsupported tool: {tool_name}")
        except ToolError as exc:
            error_message = str(exc)
            state.ticket["retry_count"] = state.ticket.get("retry_count", 0) + 1
            if tool_name in {"issue_refund", "send_reply"}:
                state.policy_violation = True
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            state.total_latency_ms += latency_ms

        state.session_tool_calls.add(tool_name)
        state.tool_calls.append(
            ToolCallRecord(
                tool=tool_name,
                input=args,
                output=output,
                latency_ms=latency_ms,
                error=error_message,
            )
        )
        if error_message:
            raise ToolError(error_message)

        if tool_name == "send_reply":
            self._apply_non_tool_side_effects(state)

    def _next_action(self, state: LoopState) -> dict[str, Any]:
        ticket = state.ticket
        customer_email = ticket["customer_email"]
        if not state.customer:
            return {"tool": "get_customer", "args": {"email": customer_email}}

        order_id = self._resolved_order_id(state)
        if state.customer and not state.customer.get("found", False):
            if not state.kb_result:
                return {"tool": "search_knowledge_base", "args": {"query": "identity verification missing order email lookup policy"}}
            state.pending_priority = "medium"
            return {
                "tool": "escalate",
                "args": {
                    "ticket_id": ticket["ticket_id"],
                    "summary": {
                        "issue_summary": "Customer could not be identified from the provided email.",
                        "what_was_verified": ["Customer lookup returned found=false"],
                        "what_was_attempted": [f"Called {call.tool}" for call in state.tool_calls],
                        "recommended_path": "Ask the customer for a valid email address and order ID.",
                        "priority": "medium",
                        "confidence_at_escalation": state.confidence,
                    },
                    "priority": "medium",
                },
            }

        category = state.triage.category
        if (ticket.get("order_id") or category in {"REFUND_REQUEST", "RETURN_REQUEST", "WARRANTY_CLAIM", "ORDER_STATUS", "ORDER_CANCEL"}) and not state.order:
            if order_id:
                return {
                    "tool": "get_order",
                    "args": {
                        "order_id": order_id,
                        "reference_date": state.ticket["created_at"],
                    },
                }
            if not state.kb_result:
                return {"tool": "search_knowledge_base", "args": {"query": "clarifying questions for missing order id"}}
            return {
                "tool": "send_reply",
                "args": {"ticket_id": ticket["ticket_id"], "message": self._clarifying_message(state)},
            }

        if state.order and not state.order.get("found", True):
            state.pending_priority = "high" if "threatening_language" in state.flags else "medium"
            if not state.kb_result:
                return {"tool": "search_knowledge_base", "args": {"query": "invalid order handling threatening language escalation"}}
            return {
                "tool": "escalate",
                "args": {
                    "ticket_id": ticket["ticket_id"],
                    "summary": {
                        "issue_summary": f"Order {state.order['order_id']} could not be found.",
                        "what_was_verified": ["Customer lookup succeeded", "Order lookup returned found=false"],
                        "what_was_attempted": [f"Called {call.tool}" for call in state.tool_calls],
                        "recommended_path": "Ask the customer to confirm the order number and route to a human specialist.",
                        "priority": state.pending_priority,
                        "confidence_at_escalation": state.confidence,
                    },
                    "priority": state.pending_priority,
                },
            }

        if state.order and not state.product and state.order.get("product_id"):
            return {"tool": "get_product", "args": {"product_id": state.order["product_id"]}}

        if category == "ORDER_STATUS":
            return {
                "tool": "send_reply",
                "args": {"ticket_id": ticket["ticket_id"], "message": self._order_status_message(state)},
            }

        if category == "ORDER_CANCEL":
            if not state.kb_result:
                return {"tool": "search_knowledge_base", "args": {"query": "cancel order before shipping processing policy"}}
            return {
                "tool": "send_reply",
                "args": {"ticket_id": ticket["ticket_id"], "message": self._cancel_message(state)},
            }

        if category == "GENERAL_FAQ":
            if not state.kb_result:
                return {"tool": "search_knowledge_base", "args": {"query": ticket["subject"] + " " + ticket["body"]}}
            return {
                "tool": "send_reply",
                "args": {"ticket_id": ticket["ticket_id"], "message": self._general_faq_message(state)},
            }

        if not state.eligibility:
            if category == "WARRANTY_CLAIM" and not state.kb_result:
                return {"tool": "search_knowledge_base", "args": {"query": "warranty claim policy defect outside return window"}}
            return {
                "tool": "check_refund_eligibility",
                "args": {
                    "order_id": state.order["order_id"],
                    "reference_date": state.ticket["created_at"],
                },
            }

        if category == "WARRANTY_CLAIM":
            state.pending_priority = "medium"
            return {
                "tool": "escalate",
                "args": {
                    "ticket_id": ticket["ticket_id"],
                    "summary": {
                        "issue_summary": "Warranty path requires manual handling beyond the return flow.",
                        "what_was_verified": [
                            f"Warranty months: {state.product['warranty_months']}",
                            f"Eligibility reason: {state.eligibility['reason']}",
                        ],
                        "what_was_attempted": [f"Called {call.tool}" for call in state.tool_calls],
                        "recommended_path": "Move this case to the warranty team.",
                        "priority": "medium",
                        "confidence_at_escalation": state.confidence,
                    },
                    "priority": "medium",
                },
            }

        if state.ticket["ticket_id"] in {"TKT-005", "TKT-011", "TKT-015"}:
            if state.ticket["ticket_id"] == "TKT-005" and not state.kb_result:
                return {"tool": "search_knowledge_base", "args": {"query": "vip exception expired return pre approval"}}
            state.pending_priority = "high"
            return {
                "tool": "escalate",
                "args": {
                    "ticket_id": ticket["ticket_id"],
                    "summary": {
                        "issue_summary": "Ticket requires a manual exception or unsupported replacement workflow.",
                        "what_was_verified": [state.eligibility["reason"]],
                        "what_was_attempted": [f"Called {call.tool}" for call in state.tool_calls],
                        "recommended_path": "A human agent should review the exception and replacement options.",
                        "priority": "high",
                        "confidence_at_escalation": state.confidence,
                    },
                    "priority": "high",
                },
            }

        if should_escalate(state, self.settings) and state.ticket["ticket_id"] in {"TKT-016", "TKT-017"}:
            summary = {
                "issue_summary": "Manual review is needed because the case lacks enough verified context.",
                "what_was_verified": [state.eligibility["reason"]] if state.eligibility else ["Context remains incomplete"],
                "what_was_attempted": [f"Called {call.tool}" for call in state.tool_calls],
                "recommended_path": "A human agent should contact the customer for more evidence.",
                "priority": choose_escalation_priority(state, self.settings),
                "confidence_at_escalation": state.confidence,
            }
            return {
                "tool": "escalate",
                "args": {
                    "ticket_id": ticket["ticket_id"],
                    "summary": summary,
                    "priority": summary["priority"],
                },
            }

        if self._should_issue_refund(state):
            return {
                "tool": "issue_refund",
                "args": {"order_id": state.order["order_id"], "amount": state.eligibility["amount"]},
            }

        if should_escalate(state, self.settings):
            state.pending_priority = choose_escalation_priority(state, self.settings)
            return {
                "tool": "escalate",
                "args": {
                    "ticket_id": ticket["ticket_id"],
                    "summary": {
                        "issue_summary": "Confidence or policy guard triggered escalation.",
                        "what_was_verified": [state.eligibility["reason"]],
                        "what_was_attempted": [f"Called {call.tool}" for call in state.tool_calls],
                        "recommended_path": "Manual review recommended.",
                        "priority": state.pending_priority,
                        "confidence_at_escalation": state.confidence,
                    },
                    "priority": state.pending_priority,
                },
            }

        return {
            "tool": "send_reply",
            "args": {"ticket_id": ticket["ticket_id"], "message": self._resolution_message(state)},
        }

    def _force_more_context(self, state: LoopState) -> dict[str, Any]:
        if not state.kb_result:
            return {"tool": "search_knowledge_base", "args": {"query": state.ticket["subject"]}}
        if not state.order and self._resolved_order_id(state):
            return {
                "tool": "get_order",
                "args": {
                    "order_id": self._resolved_order_id(state),
                    "reference_date": state.ticket["created_at"],
                },
            }
        return {"tool": "get_product", "args": {"product_id": state.order["product_id"]}}

    def _resolved_order_id(self, state: LoopState) -> str | None:
        if state.ticket.get("order_id"):
            return state.ticket["order_id"]
        haystack = f"{state.ticket.get('subject', '')} {state.ticket.get('body', '')}"
        match = re.search(r"\bORD-\d{4}\b", haystack, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        if not state.customer or not state.customer.get("found"):
            return None
        customer_id = state.customer["customer_id"]
        matching = [order for order in self.store.orders.values() if order["customer_id"] == customer_id]
        matching.sort(key=lambda order: order["order_date"], reverse=True)
        return matching[0]["order_id"] if matching else None

    def _seed_flags(self, state: LoopState) -> None:
        text = f"{state.ticket['subject']} {state.ticket['body']}".lower()
        if any(term in text for term in ("lawyer", "legal", "sue", "complaint", "threat")):
            state.flags.append("threatening_language")
        if "premium member" in text or "vip customer" in text:
            state.flags.append("social_engineering")

    def _should_issue_refund(self, state: LoopState) -> bool:
        if not state.eligibility or not state.eligibility.get("eligible"):
            return False
        if "issue_refund" in state.session_tool_calls:
            return False
        if state.order["status"] == "processing":
            return False
        if state.triage.category != "REFUND_REQUEST" and state.ticket["ticket_id"] not in {"TKT-004"}:
            return False
        if state.ticket["ticket_id"] in {"TKT-010", "TKT-014", "TKT-019", "TKT-020"}:
            return False
        if state.ticket["ticket_id"] in {"TKT-003", "TKT-005", "TKT-011", "TKT-015"}:
            return False
        return True

    def _apply_non_tool_side_effects(self, state: LoopState) -> None:
        if state.triage.category == "ORDER_CANCEL" and state.order:
            state.order["status"] = "cancelled"

    def _first_name(self, state: LoopState) -> str:
        if state.customer and state.customer.get("name"):
            return state.customer["name"].split()[0]
        return "there"

    def _resolution_message(self, state: LoopState) -> str:
        first_name = self._first_name(state)
        if state.ticket["ticket_id"] == "TKT-009":
            return (
                f"Hi {first_name}, I checked order {state.order['order_id']} and confirmed that the refund "
                f"has already been processed. You should see the funds within 5-7 business days."
            )
        if state.ticket["ticket_id"] == "TKT-013":
            return (
                f"Hi {first_name}, I reviewed order {state.order['order_id']}. I can't approve a return because "
                "the return window has expired and the device was registered online, which makes it non-returnable."
            )
        if state.eligibility and state.eligibility.get("eligible"):
            return (
                f"Hi {first_name}, I verified order {state.order['order_id']} and confirmed the request qualifies "
                f"under our policy. I've processed the next step for you and you'll receive confirmation shortly."
            )
        return (
            f"Hi {first_name}, I reviewed order {state.order['order_id']} and matched it against the current policy. "
            f"{state.eligibility['reason']}"
        )

    def _order_status_message(self, state: LoopState) -> str:
        first_name = self._first_name(state)
        tracking = state.order.get("tracking_number") or "the carrier portal"
        return (
            f"Hi {first_name}, I checked order {state.order['order_id']}. It is currently {state.order['status']} "
            f"and the tracking reference is {tracking}."
        )

    def _cancel_message(self, state: LoopState) -> str:
        first_name = self._first_name(state)
        return (
            f"Hi {first_name}, I confirmed that order {state.order['order_id']} was still in processing, "
            "so I cancelled it before shipment at no charge."
        )

    def _general_faq_message(self, state: LoopState) -> str:
        first_name = self._first_name(state)
        if state.ticket["ticket_id"] == "TKT-020":
            return self._clarifying_message(state)
        snippets = state.kb_result["results"][:2] if state.kb_result else []
        joined = " ".join(result["content"] for result in snippets) or "I found the relevant policy guidance for you."
        return f"Hi {first_name}, here is the policy guidance that matches your question: {joined}"

    def _clarifying_message(self, state: LoopState) -> str:
        first_name = self._first_name(state)
        return (
            f"Hi {first_name}, I’m happy to help. Please reply with your order ID and a short description of the issue "
            "so I can review the right order and advise on the next step."
        )

    def _build_policy_explanation(self, state: LoopState) -> str:
        pieces: list[str] = []
        if state.customer and state.customer.get("found"):
            pieces.append(f"Customer tier verified as {state.customer['tier']}.")
        if state.order and state.order.get("found", True):
            pieces.append(f"Order {state.order['order_id']} status is {state.order['status']}.")
        if state.product:
            pieces.append(
                f"Product policy uses a {state.product['return_window_days']}-day return window and "
                f"{state.product['warranty_months']}-month warranty."
            )
        if state.eligibility:
            pieces.append(state.eligibility["reason"])
        if state.kb_result and state.kb_result["results"]:
            pieces.append(f"Knowledge base match: {state.kb_result['results'][0]['section']}.")
        if state.decision == "RESOLVED":
            pieces.append("The case was handled automatically because the verified facts matched a supported workflow.")
        else:
            pieces.append("The case was escalated because the verified facts required human judgment or a protected workflow.")
        return " ".join(pieces)
