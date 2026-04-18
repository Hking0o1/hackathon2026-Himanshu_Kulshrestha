# Failure Modes

## 1. Tool retries exhausted
If a tool still fails after the retry budget, the ticket is moved to the dead-letter path instead of crashing the run.
Implementation: `backend/tools/base.py` raises `MaxRetriesExceededError`, and `backend/queue_manager.py` records a dead-letter entry.

## 2. Confidence drops below `0.6`
Any path that cannot reach a reliable policy match or verified context is escalated automatically.
Implementation: `backend/agent/confidence.py` computes the score deterministically and `backend/agent/decision_gate.py` applies the threshold.

## 3. Confidence drops below `0.4`
This is treated as urgent because both the policy certainty and the verified context are weak.
Implementation: `choose_escalation_priority()` upgrades the escalation priority to `urgent`.

## 4. Irreversible refund guard is violated
`issue_refund` must never run before `check_refund_eligibility` in the same session.
Implementation: `backend/tools/write_tools.py` validates `session_checked_orders` and raises `IrreversibleActionGuardError`.

## 5. Customer identity cannot be verified
If `get_customer` returns `found=false`, the agent cannot safely take account-level action.
Implementation: `backend/agent/react_loop.py` forces a policy lookup and then escalates with a structured summary.

## 6. Order lookup fails
An invalid order ID combined with threatening language should escalate instead of trying to resolve inline.
Implementation: `backend/agent/react_loop.py` detects `found=false`, adds the threat flag, and routes the ticket to human review.

## 7. Duplicate refund risk
If `refund_status=refunded`, the agent must not issue another refund.
Implementation: `check_refund_eligibility()` returns `ALREADY_REFUNDED`, and the resolution path switches to a confirmation reply.

## 8. Unsupported workflow requested
Replacement and exchange-only cases are not automated in this build.
Implementation: the ReAct loop escalates `TKT-011` and `TKT-015` style requests instead of inventing a tool that does not exist.

