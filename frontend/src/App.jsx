import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import AnalyticsPanel from "./components/AnalyticsPanel";
import AuditPanel from "./components/AuditPanel";
import SearchToolbar from "./components/SearchToolbar";
import StatsBar from "./components/StatsBar";
import TicketBoard from "./components/TicketBoard";
import WorkerStatus from "./components/WorkerStatus";
import { useSSE } from "./hooks/useSSE";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const ADMIN_TOKEN = import.meta.env.VITE_API_ADMIN_TOKEN || "change_me_in_production";

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
  const [runInProgress, setRunInProgress] = useState(false);
  const [runError, setRunError] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [darkMode, setDarkMode] = useState(false);
  const uploadRef = useRef(null);

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

  useEffect(() => {
    const mediaQuery = window.matchMedia?.("(prefers-color-scheme: dark)");
    setDarkMode(mediaQuery?.matches ?? false);
    const listener = (event) => setDarkMode(event.matches);
    mediaQuery?.addEventListener?.("change", listener);
    return () => mediaQuery?.removeEventListener?.("change", listener);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);

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
      if (event.type === "run_started") {
        setRunInProgress(true);
      }
      if (event.type === "run_complete") {
        setRunInProgress(false);
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

  const runAgent = async () => {
    setRunError(null);
    try {
      setRunInProgress(true);
      const response = await fetch(`${API_URL}/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-token": ADMIN_TOKEN,
        },
      });
      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(`Run failed: ${response.status} ${errorBody}`);
      }
      await response.json();
    } catch (error) {
      console.error("Failed to start run", error);
      setRunError(error instanceof Error ? error.message : "Unable to start run");
      setRunInProgress(false);
    }
  };

  const uploadTickets = async (file) => {
    setUploadStatus("Uploading ticket batch...");
    setRunError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${API_URL}/tickets/upload`, {
        method: "POST",
        headers: {
          "x-admin-token": ADMIN_TOKEN,
        },
        body: formData,
      });
      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(`Upload failed: ${response.status} ${errorBody}`);
      }
      const data = await response.json();
      setUploadStatus(`Uploaded ${data.count} tickets. Reloading snapshot...`);
      const snapshotData = await fetchJson(`${API_URL}/tickets`);
      startTransition(() => setSnapshot(snapshotData));
    } catch (error) {
      console.error("Ticket upload failed", error);
      setUploadStatus(error instanceof Error ? error.message : "Unable to upload tickets");
    }
  };

  const handleUploadChange = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      uploadTickets(file);
    }
  };

  return (
    <main className="app-shell">
      <section className="hero">
        <div className="hero-top">
          <button className="theme-toggle" type="button" onClick={() => setDarkMode((value) => !value)}>
            {darkMode ? "Switch to light" : "Switch to dark"}
          </button>
        </div>
        <div className="hero-copy-block">
          <p>Support operations, complaint analysis, and live audit flow in one workspace.</p>
          <h1 className="eyebrow">ShopWave Auto-Agent</h1>
          <h6 className="hero-copy">
            Search tickets, inspect complaint patterns, watch worker activity, and open any ticket’s reasoning trace
            without the UI breaking when audit data is still pending.
          </h6>
        </div>
      </section>

      <section className="run-control">
        <div className="run-control-left">
          <h2>Launch support automation</h2>
          <p>Start the agent from the UI and watch the live backend stream update ticket progress in real time.</p>
          <div className="upload-row">
            <label className="upload-button" htmlFor="ticket-file-input">
              Upload tickets JSON
              <input
                id="ticket-file-input"
                type="file"
                accept="application/json"
                ref={uploadRef}
                onChange={handleUploadChange}
              />
            </label>
            {uploadStatus && <span className="upload-copy">{uploadStatus}</span>}
          </div>
        </div>
        <div className="run-control-right">
          <button className={`run-button ${runInProgress ? "running" : ""}`} onClick={runAgent} disabled={runInProgress || !connected}>
            {runInProgress ? "Run in progress…" : "Start workflow"}
          </button>
          <span className={`run-pill ${runInProgress ? "active" : "idle"}`}>
            {runInProgress ? "Processing tickets" : connected ? "Ready to run" : "Waiting for stream"}
          </span>
          {runError && <p className="error-copy">{runError}</p>}
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
