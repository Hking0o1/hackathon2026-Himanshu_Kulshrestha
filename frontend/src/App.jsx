import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import AnalyticsPanel from "./components/AnalyticsPanel";
import AuditPanel from "./components/AuditPanel";
import SearchToolbar from "./components/SearchToolbar";
import StatsBar from "./components/StatsBar";
import TicketBoard from "./components/TicketBoard";
import WorkerStatus from "./components/WorkerStatus";
import { useSSE } from "./hooks/useSSE";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

export default function App() {
  const [snapshot, setSnapshot] = useState({ tickets: [], workers: {}, stats: {}, analytics: {} });
  const [selectedId, setSelectedId] = useState(null);
  const [selectedAudit, setSelectedAudit] = useState(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [categoryFilter, setCategoryFilter] = useState("ALL");

  useEffect(() => {
    fetchJson(`${API_URL}/tickets`)
      .then((data) => {
        startTransition(() => setSnapshot(data));
      })
      .catch((error) => console.error("Failed to load initial snapshot", error));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setSelectedAudit(null);
      return;
    }
    fetch(`${API_URL}/audit/${selectedId}`)
      .then(async (response) => {
        if (!response.ok) {
          return {
            ticket_id: selectedId,
            react_loop: { thoughts: [], tool_calls: [] },
            policy_explanation: "Audit detail is not available yet for this ticket.",
            preview: true,
          };
        }
        return response.json();
      })
      .then((data) => setSelectedAudit(data))
      .catch((error) => {
        console.error("Failed to load audit panel", error);
        setSelectedAudit({
          ticket_id: selectedId,
          react_loop: { thoughts: [], tool_calls: [] },
          policy_explanation: "Audit detail could not be loaded.",
          preview: true,
        });
      });
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
        setSnapshot((current) => ({
          ...current,
          stats: event,
          analytics: current.analytics,
        }));
        if (selectedId) {
          fetchJson(`${API_URL}/audit/${selectedId}`)
            .then((audit) => {
              startTransition(() => setSelectedAudit(audit));
            })
            .catch((error) => console.error("Failed to refresh selected audit", error));
        }
        fetchJson(`${API_URL}/analytics`)
          .then((analytics) => {
            startTransition(() => {
              setSnapshot((current) => ({ ...current, analytics }));
            });
          })
          .catch((error) => console.error("Failed to refresh analytics", error));
      }
    });
  });

  const deferredQuery = useDeferredValue(query);

  const categories = useMemo(() => {
    return [...new Set(snapshot.tickets.map((ticket) => ticket.category).filter(Boolean))].sort();
  }, [snapshot.tickets]);

  const filteredTickets = useMemo(() => {
    const normalized = deferredQuery.trim().toLowerCase();
    return snapshot.tickets.filter((ticket) => {
      const matchesQuery =
        !normalized ||
        [ticket.ticket_id, ticket.subject, ticket.customer_email, ticket.order_id, ticket.category]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalized));
      const matchesStatus = statusFilter === "ALL" || ticket.status === statusFilter;
      const matchesCategory = categoryFilter === "ALL" || ticket.category === categoryFilter;
      return matchesQuery && matchesStatus && matchesCategory;
    });
  }, [snapshot.tickets, deferredQuery, statusFilter, categoryFilter]);

  const selectedTicket = useMemo(
    () => snapshot.tickets.find((ticket) => ticket.ticket_id === selectedId) || null,
    [snapshot.tickets, selectedId],
  );

  return (
    <main className="app-shell">
      <section className="hero">
        <div className="hero-copy-block">
          <p className="eyebrow">ShopWave Auto-Agent</p>
          <h1>Support operations, complaint analysis, and live audit flow in one workspace.</h1>
          <p className="hero-copy">
            Search tickets, inspect complaint patterns, watch worker activity, and open any ticket’s reasoning trace
            without the UI breaking when audit data is still pending.
          </p>
        </div>
      </section>

      <StatsBar stats={snapshot.stats} connected={connected} />

      <SearchToolbar
        query={query}
        setQuery={setQuery}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        categoryFilter={categoryFilter}
        setCategoryFilter={setCategoryFilter}
        categories={categories}
      />

      <AnalyticsPanel analytics={snapshot.analytics} />

      <section className="workspace">
        <TicketBoard tickets={filteredTickets} selectedId={selectedId} onSelect={setSelectedId} />
        <AuditPanel audit={selectedAudit} selectedTicket={selectedTicket} />
      </section>

      <WorkerStatus workers={snapshot.workers} />
    </main>
  );
}
