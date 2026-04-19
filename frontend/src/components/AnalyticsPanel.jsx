function maxValue(items) {
  return Math.max(...items.map((item) => item.value), 1);
}

function LineChart({ title, items }) {
  const width = 320;
  const height = 180;
  const padding = 24;
  const values = items.map((item) => item.value);
  const max = Math.max(...values, 1);
  const points = items.map((item, index) => {
    const x = padding + (index / Math.max(items.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - (item.value / max) * (height - padding * 2);
    return `${x},${y}`;
  });
  return (
    <article className="chart-card chart-with-graph">
      <div className="chart-header">
        <h4>{title}</h4>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="line-chart">
        <polyline points={points.join(" ")} fill="none" stroke="var(--graph-line)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {items.map((item, index) => {
          const x = padding + (index / Math.max(items.length - 1, 1)) * (width - padding * 2);
          const y = height - padding - (item.value / max) * (height - padding * 2);
          return <circle key={index} cx={x} cy={y} r="4" fill="var(--graph-dot)raph-dot)" />;
        })}
      </svg>
      <div className="chart-labels">
        {items.slice(0, 5).map((item) => (
          <span key={item.label}>{item.label}</span>
        ))}
      </div>
    </article>
  );
}

function PieChart({ title, items }) {
  const total = items.reduce((sum, item) => sum + item.value, 0) || 1;
  const colors = [
    "var(--graph-1)",
    "var(--graph-2)",
    "var(--graph-3)",
    "var(--graph-4)",
    "var(--graph-5)",
    "var(--graph-6)",
  
    "var(--graph-1)",
    "var(--graph-2)",
    "var(--graph-3)",
    "var(--graph-4)",
    "var(--graph-5)",
    "var(--graph-6)",
  ];
  let angleAccumulator = 0;

  return (
    <article className="chart-card chart-with-graph">
      <div className="chart-header">
        <h4>{title}</h4>
      </div>
      <div className="pie-chart-wrapper">
        <svg viewBox="0 0 160 160" className="pie-chart">
          {items.map((item, index) => {
            const slice = item.value / total;
            const angle = slice * Math.PI * 2;
            const x1 = 80 + Math.cos(angleAccumulator) * 64;
            const y1 = 80 + Math.sin(angleAccumulator) * 64;
            angleAccumulator += angle;
            const x2 = 80 + Math.cos(angleAccumulator) * 64;
            const y2 = 80 + Math.sin(angleAccumulator) * 64;
            const largeArc = slice > 0.5 ? 1 : 0;
            const path = `M80 80 L ${x1} ${y1} A 64 64 0 ${largeArc} 1 ${x2} ${y2} Z`;
            return <path key={item.label} d={path} fill={colors[index % colors.length]} />;
          })}
        </svg>
        <div className="pie-legend">
          {items.map((item, index) => (
            <div key={item.label} className="legend-row">
              <span className="legend-dot" style={{ background: colors[index % colors.length] }} />
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}
    
 

function ClusterGraph({ title, nodes }) {
  const width = 320;
  const height = 220;
  const categories = [...new Set(nodes.map((node) => node.category))];
  const statusMap = { resolved: 0, escalated: 1, dead: 2 };
  const colors = {
    resolved: "var(--resolved)",
    escalated: "var(--escalated)",
    dead: "var(--dead)",
  };

  return (
    <article className="chart-card chart-with-graph">
      <div className="chart-header">
        <h4>{title}</h4>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="cluster-graph">
        {nodes.map((node, index) => {
          const x = 40 + (categories.indexOf(node.category) / Math.max(categories.length - 1, 1)) * (width - 80);
          const y = 40 + statusMap[node.status] * 60;
          const radius = Math.min(24, 10 + node.value * 4);
          return (
            <g key={node.id}>var(--muted)
              <circle cx={x} cy={y} r={radius} fill={colors[node.status]} fillOpacity="0.85" />
              <text x={x} y={y + 4} textAnchor="middle" fontSize="10" fill="#fff">
                {node.value}
              </text>
            </g>
          );
        })}
        {categories.map((category, index) => {
          const x = 40 + (index / Math.max(categories.length - 1, 1)) * (width - 80);
          return (
            <text key={category} x={x} y={height - 10} textAnchor="middle" fontSize="10" fill="var(--muted)">
              {category}
            </text>
          );
        })}
      </svg>
      <div className="cluster-legend">
        <span className="legend-chip resolved">Resolved</span>
        <span className="legend-chip escalated">Escalated</span>
        <span className="legend-chip dead">Dead</span>
      </div>
    </article>
  );
}

function mapObject(obj = {}) {
  return Object.entries(obj)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}

export default function AnalyticsPanel({ analytics = {} }) {
  const complaintItems = mapObject(analytics.complaint_breakdown);
  const categoryItems = mapObject(analytics.category_breakdown);
  const statusItems = mapObject(analytics.status_breakdown);
  const timelineItems = (analytics.timeline || []).map((item) => ({ label: item.date, value: item.count }));
  const clusterItems = Object.entries(analytics.resolution_by_category || {}).flatMap(([category, values]) =>
    ["resolved", "escalated", "dead"].map((status) => ({
      id: `${category}-${status}`,
      category,
      status,
      value: values[status] || 0,
    })),
  );

  return (
    <section className="analytics-grid">
      <LineChart title="Ticket Volume Trend" items={timelineItems} />
      <PieChart title="Status Distribution" items={statusItems} />
      <ClusterGraph title="Category vs Resolution Cluster" nodes={clusterItems.filter((node) => node.value > 0)} />
      <article className="chart-card highlights-card wide-card">
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
