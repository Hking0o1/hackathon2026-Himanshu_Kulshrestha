from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class ToolCallRecord:
    tool: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    latency_ms: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TriageResult:
    category: str
    confidence: float
    provider: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(order=True)
class PrioritisedTicket:
    priority: int
    created_at: str = field(compare=True)
    ticket: dict[str, Any] = field(compare=False)


@dataclass
class LoopState:
    ticket: dict[str, Any]
    worker_id: int
    triage: TriageResult
    thoughts: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    session_tool_calls: set[str] = field(default_factory=set)
    checked_orders: set[str] = field(default_factory=set)
    providers_used: list[str] = field(default_factory=list)
    iteration: int = 0
    confidence: float = 0.5
    flags: list[str] = field(default_factory=list)
    customer: dict[str, Any] | None = None
    order: dict[str, Any] | None = None
    product: dict[str, Any] | None = None
    kb_result: dict[str, Any] | None = None
    eligibility: dict[str, Any] | None = None
    policy_explanation: str = ""
    pending_message: str = ""
    pending_priority: str = "medium"
    decision: str | None = None
    resolution_type: str | None = None
    policy_violation: bool = False
    kb_relevance: float = 0.0
    tier_is_known: bool = False
    total_latency_ms: int = 0


@dataclass
class AuditEntry:
    ticket_id: str
    processed_at: str
    worker_id: int
    triage: dict[str, Any]
    react_loop: dict[str, Any]
    confidence_final: float
    decision: str
    resolution_type: str
    flags: list[str]
    llm_providers_used: list[str]
    total_latency_ms: int
    policy_explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeadLetterEntry:
    ticket_id: str
    failure_reason: str
    last_error: str
    retry_count: int
    ticket_snapshot: dict[str, Any]
    failed_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeStore:
    tickets: list[dict[str, Any]] = field(default_factory=list)
    customers: dict[str, dict[str, Any]] = field(default_factory=dict)
    orders: dict[str, dict[str, Any]] = field(default_factory=dict)
    products: dict[str, dict[str, Any]] = field(default_factory=dict)
    knowledge_base: str = ""
    knowledge_sections: list[dict[str, str]] = field(default_factory=list)
    audit_entries: list[AuditEntry] = field(default_factory=list)
    dead_letters: list[DeadLetterEntry] = field(default_factory=list)
    replies: list[dict[str, Any]] = field(default_factory=list)
    escalations: list[dict[str, Any]] = field(default_factory=list)
    worker_status: dict[int, dict[str, Any]] = field(default_factory=dict)
    last_run_started: str | None = None
    last_run_finished: str | None = None

