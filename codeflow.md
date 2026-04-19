# Code Flow

## Runtime path
1. FastAPI startup or CLI bootstrap calls `backend.queue_manager.manager.bootstrap()`.
2. JSON data from `backend/data/` is loaded into the in-memory `RuntimeStore`.
3. Tickets are pushed into `asyncio.PriorityQueue` using inverted tier priority so VIP tickets are handled first.
4. Five workers pull tickets concurrently and run triage, the ReAct loop, decisioning, and audit export.
5. Results are written to `audit_log.json`, optional Postgres inserts are attempted, and SSE events are emitted for the dashboard.

## ReAct path
1. `backend/agent/triage.py` classifies each ticket into one of the six canonical categories.
2. `backend/agent/react_loop.py` drives tool sequencing and enforces guardrails.
3. `backend/tools/read_tools.py` verifies customer, order, product, and policy context.
4. `backend/tools/write_tools.py` performs eligibility checks, refunds, replies, and escalations.
5. `backend/agent/confidence.py` computes the deterministic final confidence score.
6. `backend/agent/decision_gate.py` decides whether the case should resolve automatically or escalate.

## What was implemented in this pass
- Full backend skeleton from the TRD, including queue manager, tool layer, mock LLM wrappers, SSE API, and CLI.
- Mock datasets for all 20 tickets and the supporting customers, orders, products, and policy knowledge base.
- Outcome alignment so the run resolves and escalates the same ticket set described in the TRD.
- React dashboard shell for ticket board, live stats, worker lanes, and audit inspection.
- Frontend theme toggle, dark mode styling, and file upload support for ticket JSON batches.
- Rich CLI header with a colored ASCII banner and consistent command headers for every `cli/run_agent.py` command.
- Delivery docs: `README.md`, `failure_modes.md`, `codeflow.md`, and `agent.md`.

## Key assumptions
- The current build uses deterministic local heuristics for triage and reasoning, while preserving the provider wrapper boundaries for future API-backed upgrades.
- Postgres writes are optional at runtime and are skipped gracefully if `asyncpg` is unavailable.
- The dashboard is designed against the backend SSE contract that exists in this repository today.

