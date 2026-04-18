export default function SearchToolbar({
  query,
  setQuery,
  statusFilter,
  setStatusFilter,
  categoryFilter,
  setCategoryFilter,
  categories,
}) {
  return (
    <section className="search-toolbar">
      <label className="search-box">
        <span>Search tickets</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ticket ID, subject, email, order ID"
        />
      </label>

      <label className="filter-box">
        <span>Status</span>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="ALL">All statuses</option>
          <option value="QUEUED">Queued</option>
          <option value="PROCESSING">Processing</option>
          <option value="RESOLVED">Resolved</option>
          <option value="ESCALATED">Escalated</option>
          <option value="DEAD">Dead</option>
        </select>
      </label>

      <label className="filter-box">
        <span>Category</span>
        <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
          <option value="ALL">All categories</option>
          {categories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}

