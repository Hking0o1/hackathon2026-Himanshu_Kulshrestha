function maxValue(items) {
  return Math.max(...items.map((item) => item.value), 1);
}

function MiniBarChart({ title, items }) {
  const ceiling = maxValue(items);

  return (
    <article className="chart-card">
      <div className="chart-header">
        <h4>{title}</h4>
      </div>
      <div className="chart-list">
        {items.map((item) => (
          <div key={item.label} className="chart-row">
            <span>{item.label}</span>
            <div className="chart-track">
              <div className="chart-fill" style={{ width: `${(item.value / ceiling) * 100}%` }} />
            </div>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
    </article>
  );
}

function mapObject(obj = {}) {
  return Object.entries(obj).map(([label, value]) => ({ label, value }));
}

export default function AnalyticsPanel({ analytics = {} }) {
  const complaintItems = mapObject(analytics.complaint_breakdown);
  const categoryItems = mapObject(analytics.category_breakdown);
  const statusItems = mapObject(analytics.status_breakdown);
  const timelineItems = (analytics.timeline || []).map((item) => ({ label: item.date, value: item.count }));

  return (
    <section className="analytics-grid">
      <MiniBarChart title="Complaint Mix" items={complaintItems} />
      <MiniBarChart title="Category Load" items={categoryItems} />
      <MiniBarChart title="Status Split" items={statusItems} />
      <MiniBarChart title="Ticket Timeline" items={timelineItems} />

      <article className="chart-card highlights-card">
        <div className="chart-header">
          <h4>Policy Highlights</h4>
        </div>
        <div className="highlight-list">
          {(analytics.policy_highlights || []).map((item) => (
            <article key={item.ticket_id} className="highlight-item">
              <div>
                <strong>{item.ticket_id}</strong>
                <span>{item.decision}</span>
              </div>
              <p>{item.policy_explanation}</p>
            </article>
          ))}
        </div>
      </article>
    </section>
  );
}
