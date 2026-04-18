function ticketName(ticket) {
  return ticket.customer_email?.split("@")[0]?.replaceAll(".", " ") || "unknown";
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
        <span>{ticket.order_id || "No order ID"}</span>
      </div>
      <div className="ticket-footer">
        <span className={`status-chip ${ticket.status?.toLowerCase() || "queued"}`}>{ticket.status || "QUEUED"}</span>
        <span>{ticket.flags?.length ? ticket.flags.join(", ") : "clear"}</span>
      </div>
      <div className={`confidence-bar ${confidenceClass(ticket.confidence)}`}>
        <div style={{ width: `${(ticket.confidence || 0) * 100}%` }} />
      </div>
    </button>
  );
}

export default function TicketBoard({ tickets = [], selectedId, onSelect }) {
  return (
    <section className="ticket-results">
      <div className="results-header">
        <h3>Ticket Search Results</h3>
        <span>{tickets.length} tickets</span>
      </div>

      <div className="results-grid">
        {tickets.map((ticket) => (
          <TicketCard
            key={ticket.ticket_id}
            ticket={ticket}
            onSelect={onSelect}
            selected={selectedId === ticket.ticket_id}
          />
        ))}
      </div>
    </section>
  );
}
