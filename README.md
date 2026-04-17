# ShockWave Auto-Agent
ShopWave Auto-Agent is an autonomous support resolution system for the ShopWave e-commerce platform. It ingests customer support tickets, classifies them, resolves them using a multi-step ReAct (Reason + Act) agent loop, escalates intelligently when needed, and maintains an immutable audit trail of every decision.

## 1. System Architecture

### 1.1 High-Level Component Map

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

