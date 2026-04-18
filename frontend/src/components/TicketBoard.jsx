function ticketName(ticket) {
  return ticket.customer_email?.split("@")[0]?.replace(".", " ") || "unknown";
}

function tierLabel(tier) {
  if (tier === 3) return "VIP";
  if (tier === 2) return "Premium";
  return "Standard";
}

function tierClass(tier) {
  if (tier === 3) return "vip";
  if (tier === 2) return "premium";
  return "standard";
}

function confidenceClass(confidence) {
  if ((confidence || 0) >= 0.8) return "high";
  if ((confidence || 0) >= 0.6) return "medium";
  return "low";
}

function TicketCard({ ticket, onSelect, selected }) {
  return (
    <button className={`ticket-card ${selected ? "selected" : ""}`} onClick={() => onSelect(ticket.ticket_id)}>
      <div className="ticket-card-top">
        <strong>{ticket.ticket_id}</strong>
        <span className={`tier-badge ${tierClass(ticket.tier)}`}>{tierLabel(ticket.tier)}</span>
      </div>
      <p className="ticket-name">{ticketName(ticket)}</p>
      <p className="ticket-subject">{ticket.subject}</p>
      <div className="ticket-meta">
        <span>{ticket.category || "Pending triage"}</span>
        <span>{ticket.flags?.join(", ") || "no flags"}</span>
      </div>
      <div className={`confidence-bar ${confidenceClass(ticket.confidence)}`}>
        <div style={{ width: `${(ticket.confidence || 0) * 100}%` }} />
      </div>
    </button>
  );
}

export default function TicketBoard({ tickets = [], selectedId, onSelect }) {
  const columns = ["QUEUED", "PROCESSING", "RESOLVED", "ESCALATED"];

  return (
    <section className="board-grid">
      {columns.map((column) => (
        <article key={column} className="board-column">
          <header>
            <h3>{column}</h3>
            <span>{tickets.filter((ticket) => ticket.status === column).length}</span>
          </header>
          <div className="ticket-stack">
            {tickets
              .filter((ticket) => ticket.status === column)
              .map((ticket) => (
                <TicketCard
                  key={ticket.ticket_id}
                  ticket={ticket}
                  onSelect={onSelect}
                  selected={selectedId === ticket.ticket_id}
                />
              ))}
          </div>
        </article>
      ))}
    </section>
  );
}

