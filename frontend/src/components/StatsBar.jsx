export default function StatsBar({ stats = {}, connected = false }) {
  const items = [
    { label: "Total Tickets", value: stats.total ?? 0 },
    { label: "Resolved", value: stats.resolved ?? 0 },
    { label: "Escalated", value: stats.escalated ?? 0 },
    { label: "Queued", value: stats.queued ?? 0 },
    { label: "Avg Confidence", value: stats.avg_confidence ?? 0 },
  ];

  return (
    <section className="stats-bar">
      <div className="stats-bar-top">
        <div>
          <p className="eyebrow">Operations</p>
          <h2>Support command center</h2>
        </div>
        <div className={`connection-pill ${connected ? "online" : "offline"}`}>
          {connected ? "Stream connected" : "Stream reconnecting"}
        </div>
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
