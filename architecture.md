# Architecture Overview

This document describes the overall architecture of the ShopWave Auto-Agent repository, including backend, CLI, and frontend components.

## High-level architecture

```bash
┌─────────────────────────────────────────────────────────────────────┐
│                        ShopWave Auto-Agent                          │
│                                                                     │
│  tickets.json ──► FastAPI Startup ──► asyncio.PriorityQueue         │
│                          │              (tier-ordered, heapq)       │
│                          │                                          │
│                    Worker Pool (N=5 concurrent workers)             │
│                    asyncio.gather(*[worker() for _ in range(5)])    │
│                          │                                          │
│           ┌──────────────┼──────────────┐                           │
│           │              │              │                           │
│      [Worker 1]    [Worker 2]    [Worker N]                         │
│           │                                                         │
│    STAGE 1: Triage                                                  │
│    HuggingFace BART ──► category label + confidence                 │
│           │                                                         │
│    STAGE 2: ReAct Loop (Groq / Ollama fallback)                     │
│    THOUGHT ──► TOOL CALL ──► OBSERVATION ──► THOUGHT ──► ...        │
│    [min 3 tool calls enforced, max 8 iterations, irreversibility]   │
│           │                                                         │
│    STAGE 3: Decision Gate                                           │
│    confidence < 0.6 OR policy_violated ──► Gemini escalate          │
│    confidence ≥ 0.6 AND policy_ok ──► send_reply + resolve          │
│           │                                                         │
│    STAGE 4: Audit Writer                                            │
│    Groq structured output ──► Postgres + audit_log.json             │
│                                                                     │
│  REST API (FastAPI) ──► React Dashboard (SSE live updates)          │
│  CLI Tool (argparse + rich) ──► Colour-coded parallel streams       │
└─────────────────────────────────────────────────────────────────────┘
```

## Backend architecture

### Runtime store and data loading

- Ticket and fixture data are stored under `backend/data/`.
- At startup, the runtime loads tickets, customers, orders, products, and policy knowledge fixtures into memory.
- `backend/queue_manager.py` builds an `asyncio.PriorityQueue` and enqueues tickets using an inverted tier priority rule so higher-priority tickets execute first.

### Worker pool and execution

- A pool of concurrent asyncio workers processes tickets from the queue.
- Each worker executes the agent flow and emits runtime events through an internal pub/sub event broker.
- Events include run status, ticket updates, tool calls, and completion summaries.

### Agent / ReAct workflow

- `backend/agent/triage.py` assigns a ticket category.
- `backend/agent/react_loop.py` orchestrates the reasoning loop and tool execution.
- `backend/agent/confidence.py` computes a deterministic confidence score based on tool outcomes and context.
- `backend/agent/decision_gate.py` decides whether a ticket resolves automatically or escalates.

### Tool layer

- `backend/tools/read_tools.py` provides read-only access to customers, orders, products, and policy data.
- `backend/tools/write_tools.py` performs actions such as refunds, reply generation, and escalation decisions.
- Guardrails are enforced so irreversible actions are only executed when upstream validation passes.

### API and streaming

- The backend exposes FastAPI endpoints for ticket snapshots, analytics, audit data, and SSE streaming.
- `backend/main.py` serves the dashboard data and allows the frontend to subscribe to live updates.
- The backend also exposes a ticket upload endpoint for JSON batch submission.

## CLI architecture

- `cli/run_agent.py` provides terminal commands for:
  - `run`: process the full ticket set
  - `status`: show current queue/worker state
  - `audit`: inspect stored audit logs or a specific ticket
  - `stats`: print current aggregate statistics
  - `export`: show audit log export location
- The CLI uses `rich` when available to render a colored ASCII banner, tables, and styled output.
- CLI and backend commands remain aligned to a shared runtime and can be used independently of the frontend.

## Frontend architecture

- Built with React and Vite under `frontend/`.
- Components include:
  - `StatsBar`: dashboard summary metrics
  - `SearchToolbar`: filters and query input
  - `AnalyticsPanel`: line/pie/cluster visuals
  - `TicketBoard`: ticket list and selection
  - `AuditPanel`: audit reasoning and escalation summary
  - `WorkerStatus`: worker runtime state
- The frontend connects to backend SSE using `frontend/src/hooks/useSSE.js` to receive live events during agent execution.
- Theme handling is implemented with CSS variables and a dark mode toggle.
- The dashboard supports uploading a ticket JSON file to the backend via `POST /tickets/upload`.

## Data contracts

### SSE events

- `snapshot`: full ticket and analytics state payload.
- `ticket_update`: incremental ticket status updates.
- `run_started`: signal that the workflow has started.
- `run_complete`: final summary and statistics.

### API contracts

- `GET /tickets`: ticket snapshot
- `POST /tickets/upload`: upload ticket JSON batch
- `GET /audit`: audit log list
- `GET /audit/{ticket_id}`: audit entry for one ticket
- `GET /analytics`: analytics payload
- `GET /stats`: aggregate stats
- `GET /stream`: SSE stream
- `POST /run`: start workflow; requires `x-admin-token`

## Deployment and local development

### Backend

- Start the backend with `uvicorn backend.main:app --reload`.
- The frontend defaults to API host `http://localhost:8000`.

### Frontend

- Install dependencies and run the dashboard from `frontend/` with `npm install` and `npm run dev`.

### Docker

- Build and launch the full stack using `docker compose up --build`.

## Notes

- The architecture is intentionally modular: the agent, tool layer, and dashboard communicate through clear contracts.
- The CLI, API, and frontend all share the same runtime semantics for ticket lifecycle, audit output, and analytics.
- Future upgrades should keep the SSE and audit contracts stable while replacing provider implementations behind `backend/llm/`.
