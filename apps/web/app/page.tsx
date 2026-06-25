import { SearchForm } from "@/components/search-form";

export default function HomePage() {
  return (
    <div className="grid search-layout">
      <div>
        <h1 className="page-title">Hardware Hunter</h1>
        <SearchForm />
      </div>
      <aside className="panel">
        <div className="section-label">V1 Scope</div>
        <h2 style={{ marginTop: 10 }}>AI procurement search</h2>
        <p className="muted">
          Search retail hardware, used enterprise hardware, and supplier discovery sources from one Hardware
          Hunter workspace.
        </p>
        <div className="agent-list" style={{ marginTop: 16 }}>
          <div className="agent-row">
            <span>Best Buy Adapter</span>
            <span className="pill">Playwright</span>
          </div>
          <div className="agent-row">
            <span>Newegg Adapter</span>
            <span className="pill">Playwright</span>
          </div>
          <div className="agent-row">
            <span>CDW / Micro Center / Provantage</span>
            <span className="pill">Ready</span>
          </div>
          <div className="agent-row">
            <span>Supplier Discovery</span>
            <span className="pill">V1.5</span>
          </div>
        </div>
      </aside>
    </div>
  );
}
