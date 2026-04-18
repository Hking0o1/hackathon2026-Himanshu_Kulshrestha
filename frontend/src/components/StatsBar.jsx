export default function StatsBar({ stats = {}, connected = false }) {
  const items = [
    { label: "Total", value: stats.total ?? 0 },
    { label: "Resolved", value: stats.resolved ?? 0 },
    { label: "Escalated", value: stats.escalated ?? 0 },
    { label: "Dead", value: stats.dead ?? 0 },
    { label: "Avg Confidence", value: stats.avg_confidence ?? 0 },
  ];

  return (
    <section className="stats-bar">
      <div>
        <p className="eyebrow">Operations</p>
        <h2>Live resolution board</h2>
      </div>
      <div className={`connection-pill ${connected ? "online" : "offline"}`}>
        {connected ? "SSE Online" : "SSE Offline"}
      </div>
      <div className="stats-grid">
        {items.map((item) => (
          <article className="stat-card" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

