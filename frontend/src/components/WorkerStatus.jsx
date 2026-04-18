export default function WorkerStatus({ workers = {} }) {
  const entries = Object.entries(workers);

  return (
    <section className="worker-strip">
      {entries.map(([workerId, worker]) => (
        <article key={workerId} className="worker-card">
          <span>Worker {workerId}</span>
          <strong>{worker.ticket_id || "Idle"}</strong>
          <small>{worker.status}</small>
        </article>
      ))}
    </section>
  );
}
