# Agent Maintenance Notes

## Guardrails that future updates should preserve
- Do not remove the `asyncio.PriorityQueue` flow or replace it with sequential processing.
- Keep the refund irreversibility guard intact: `issue_refund` must remain blocked unless `check_refund_eligibility` was called first.
- Keep confidence deterministic. It should stay derived from verified context and tool outcomes, not from raw LLM text.
- Preserve the 20-ticket outcome expectations from the TRD unless the ticket fixtures are intentionally revised together.

## Best places to extend the system
- Add real provider integrations inside `backend/llm/` without changing the queue, tool, or audit contracts.
- Add more tool types in `backend/tools/` only if the TRD or product scope truly requires them.
- Expand the dashboard by adding new components under `frontend/src/components/` while keeping the SSE snapshot and update events backward compatible.

## Files that define the current behavior
- `backend/agent/react_loop.py`: branch logic and tool sequencing.
- `backend/tools/write_tools.py`: refund policy engine and irreversible actions.
- `backend/queue_manager.py`: worker pool, event broker, and data loading.
- `backend/data/*.json` plus `backend/data/knowledge_base.md`: source-of-truth fixtures for the mock environment.

## Safe update checklist
1. Run `python -m py_compile` on the backend files you touched.
2. Run `python cli/run_agent.py run`.
3. Verify `audit_log.json` still exports successfully.
4. Confirm the expected escalations are still `TKT-003`, `TKT-005`, `TKT-011`, `TKT-015`, `TKT-016`, and `TKT-017`.
5. If you change the API contract, update both the frontend consumer and these docs in the same pass.
