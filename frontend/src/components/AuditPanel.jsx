function pretty(value) {
  return JSON.stringify(value, null, 2);
}

export default function AuditPanel({ audit, selectedTicket }) {
  const thoughts = audit?.react_loop?.thoughts ?? [];
  const toolCalls = audit?.react_loop?.tool_calls ?? [];
  const providers = audit?.llm_providers_used ?? [];

  if (!selectedTicket) {
    return (
      <aside className="audit-panel empty">
        <p className="eyebrow">Audit Detail</p>
        <h3>Choose a ticket</h3>
        <p>Search or click any ticket to inspect reasoning, tools, policy notes, and provider usage.</p>
      </aside>
    );
  }

  return (
    <aside className="audit-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Audit Detail</p>
          <h3>{selectedTicket.ticket_id}</h3>
        </div>
        <span className={`status-chip ${selectedTicket.status?.toLowerCase() || "queued"}`}>
          {selectedTicket.status || "QUEUED"}
        </span>
      </div>

      <p className="panel-copy">
        {audit?.policy_explanation ||
          "This ticket has not produced a full audit entry yet. Once the run completes, the reasoning chain will appear here."}
      </p>

      <section className="panel-grid">
        <article className="metric-tile">
          <span>Decision</span>
          <strong>{audit?.decision || selectedTicket.status || "Pending"}</strong>
        </article>
        <article className="metric-tile">
          <span>Confidence</span>
          <strong>{audit?.confidence_final ?? selectedTicket.confidence ?? "n/a"}</strong>
        </article>
        <article className="metric-tile">
          <span>Providers</span>
          <strong>{providers.length ? providers.join(", ") : "pending"}</strong>
        </article>
      </section>

      <section>
        <h4>Thought Trail</h4>
        <div className="pill-list">
          {thoughts.length ? (
            thoughts.map((thought, index) => (
              <span key={`${selectedTicket.ticket_id}-thought-${index}`} className="pill">
                {thought}
              </span>
            ))
          ) : (
            <span className="pill muted">No thought trail yet for this ticket.</span>
          )}
        </div>
      </section>

      <section>
        <h4>Tool Calls</h4>
        <div className="tool-list">
          {toolCalls.length ? (
            toolCalls.map((tool, index) => (
              <article key={`${selectedTicket.ticket_id}-${tool.tool}-${index}`} className="tool-card">
                <div className="tool-card-top">
                  <strong>{tool.tool}</strong>
                  <span>{tool.latency_ms}ms</span>
                </div>
                <small>{tool.error ? "Error" : "Success"}</small>
                <pre>{pretty(tool.output ?? tool.error ?? {})}</pre>
              </article>
            ))
          ) : (
            <article className="tool-card empty-card">
              <strong>No tool trace yet</strong>
              <pre>{pretty({ ticket_id: selectedTicket.ticket_id, preview: audit?.preview ?? true })}</pre>
            </article>
          )}
        </div>
      </section>
    </aside>
  );
}
