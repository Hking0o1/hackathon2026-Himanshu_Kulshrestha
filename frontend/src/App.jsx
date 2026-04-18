import { startTransition, useEffect, useState } from "react";
import AuditPanel from "./components/AuditPanel";
import StatsBar from "./components/StatsBar";
import TicketBoard from "./components/TicketBoard";
import WorkerStatus from "./components/WorkerStatus";
import { useSSE } from "./hooks/useSSE";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [snapshot, setSnapshot] = useState({ tickets: [], workers: {}, stats: {} });
  const [selectedId, setSelectedId] = useState(null);
  const [selectedAudit, setSelectedAudit] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/tickets`)
      .then((response) => response.json())
      .then((data) => {
        startTransition(() => setSnapshot(data));
      })
      .catch((error) => console.error("Failed to load initial snapshot", error));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      return;
    }
    fetch(`${API_URL}/audit/${selectedId}`)
      .then((response) => response.json())
      .then((data) => setSelectedAudit(data))
      .catch((error) => console.error("Failed to load audit panel", error));
  }, [selectedId]);

  const connected = useSSE((event) => {
    startTransition(() => {
      if (event.type === "snapshot") {
        setSnapshot(event);
        return;
      }
      if (event.type === "ticket_update") {
        setSnapshot((current) => ({
          ...current,
          tickets: current.tickets.map((ticket) =>
            ticket.ticket_id === event.ticket_id
              ? {
                  ...ticket,
                  status: event.status,
                  confidence: event.confidence,
                  category: event.category,
                  flags: event.flags,
                }
              : ticket,
          ),
        }));
        return;
      }
      if (event.type === "run_complete") {
        setSnapshot((current) => ({ ...current, stats: event }));
      }
    });
  });

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">ShockWave Auto-Agent</p>
          <h1>Parallel ticket resolution with live audit visibility.</h1>
          <p className="hero-copy">
            The board streams queue movement, agent reasoning, and policy outcomes from the FastAPI backend so future
            updates stay grounded in the same operational flow.
          </p>
        </div>
      </section>

      <StatsBar stats={snapshot.stats} connected={connected} />

      <section className="workspace">
        <TicketBoard tickets={snapshot.tickets} selectedId={selectedId} onSelect={setSelectedId} />
        <AuditPanel audit={selectedAudit} />
      </section>

      <WorkerStatus workers={snapshot.workers} />
    </main>
  );
}

