export default function AuditPanel({ audit }) {
  if (!audit) {
    return (
      <aside className="audit-panel empty">
        <p className="eyebrow">Audit Detail</p>
        <h3>Select a ticket</h3>
        <p>Choose any card to inspect the reasoning chain, tool trail, and policy explanation.</p>
      </aside>
    );
  }

  return (
    <aside className="audit-panel">
      <p className="eyebrow">Audit Detail</p>
      <h3>{audit.ticket_id}</h3>
      <p className="panel-copy">{audit.policy_explanation}</p>

      <section>
        <h4>Thoughts</h4>
        <div className="pill-list">
          {audit.react_loop.thoughts.map((thought) => (
            <span key={thought} className="pill">
              {thought}
            </span>
          ))}
        </div>
      </section>

      <section>
        <h4>Tool Calls</h4>
        <div className="tool-list">
          {audit.react_loop.tool_calls.map((tool) => (
            <article key={`${audit.ticket_id}-${tool.tool}-${tool.latency_ms}`} className="tool-card">
              <strong>{tool.tool}</strong>
              <span>{tool.latency_ms}ms</span>
              <pre>{JSON.stringify(tool.output ?? tool.error, null, 2)}</pre>
            </article>
          ))}
        </div>
      </section>
    </aside>
  );
}

