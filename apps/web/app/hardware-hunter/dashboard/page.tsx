"use client";

import {
  Bell,
  ExternalLink,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Send,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  createHardwareTelegramReport,
  getHardwareDailyScanJob,
  getHardwareDashboard,
  runHardwareDailyScan,
  updateHardwareScheduler,
} from "@/lib/api";
import type {
  HardwareCategory,
  HardwareDashboard,
  HardwareOpportunity,
  HardwareScanJob,
  HardwareSourceRun,
} from "@novaion/shared/types";

const categories: HardwareCategory[] = ["servers", "gpu", "memory", "storage", "cpu"];
const tabs = ["overview", "opportunities", "source runs", "telegram reports"] as const;
type Tab = (typeof tabs)[number];
type SortBy = "score" | "newest" | "price" | "auction" | "risk";

export default function HardwareDashboardPage() {
  const [dashboard, setDashboard] = useState<HardwareDashboard | null>(null);
  const [job, setJob] = useState<HardwareScanJob | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<HardwareCategory[]>(categories);
  const [states, setStates] = useState("TX, CA, GA");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [showQuality, setShowQuality] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("score");
  const [selectedOpportunity, setSelectedOpportunity] = useState<HardwareOpportunity | null>(null);
  const [telegramOpen, setTelegramOpen] = useState(false);

  const activeJobId = job?.id ?? dashboard?.latest_job?.id;
  const opportunities = job?.opportunities ?? dashboard?.top_opportunities ?? [];
  const sourceRuns = job?.source_runs ?? dashboard?.latest_job?.source_runs ?? [];
  const report = job?.report ?? dashboard?.latest_job?.report;
  const stats = job?.quality_stats ?? dashboard?.latest_job?.quality_stats;
  const scheduler = dashboard?.scheduler;

  useEffect(() => {
    void refreshDashboard();
  }, []);

  useEffect(() => {
    if (!activeJobId || ["completed", "partially_completed", "failed"].includes(job?.status ?? "")) return;
    const timer = window.setInterval(async () => {
      const latest = await getHardwareDailyScanJob(activeJobId);
      setJob(latest);
      if (["completed", "partially_completed", "failed"].includes(latest.status)) {
        window.clearInterval(timer);
        await refreshDashboard();
      }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [activeJobId, job?.status]);

  const sortedOpportunities = useMemo(() => sortOpportunities(opportunities, sortBy), [opportunities, sortBy]);
  const sourceSummary = useMemo(() => summarizeSources(sourceRuns), [sourceRuns]);
  const auctionEndingCount = useMemo(
    () => opportunities.filter((item) => item.change_types.includes("AUCTION_ENDING")).length,
    [opportunities],
  );

  async function refreshDashboard() {
    try {
      const data = await getHardwareDashboard();
      setDashboard(data);
      if (!job && data.latest_job) setJob(data.latest_job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dashboard load failed");
    }
  }

  async function startScan() {
    setBusy(true);
    setError(null);
    try {
      const created = await runHardwareDailyScan({
        mode: "both",
        categories: selectedCategories,
        states: states
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        test_run: true,
        max_results_per_query: 3,
        max_queries_per_category: 6,
        send_telegram: false,
      });
      setJob(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function generateReport(action: "preview" | "test" | "approve_and_send") {
    if (!activeJobId) return;
    setBusy(true);
    setError(null);
    try {
      const generated = await createHardwareTelegramReport(
        activeJobId,
        action,
        action === "test" ? "NOVAION Hardware Hunter Telegram test message." : undefined,
      );
      const latest = await getHardwareDailyScanJob(activeJobId);
      setJob({ ...latest, report: generated });
      setTelegramOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Telegram action failed");
    } finally {
      setBusy(false);
    }
  }

  async function setScheduler(action: "pause" | "resume") {
    setBusy(true);
    setError(null);
    try {
      await updateHardwareScheduler(action);
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scheduler update failed");
    } finally {
      setBusy(false);
    }
  }

  function toggleCategory(category: HardwareCategory) {
    setSelectedCategories((current) =>
      current.includes(category) ? current.filter((item) => item !== category) : [...current, category],
    );
  }

  return (
    <div className="hardware-dashboard">
      <section className="panel dashboard-control">
        <div>
          <div className="section-label">Hardware Hunter V2</div>
          <h1 className="dashboard-title">退役IT资产扫描</h1>
        </div>

        <div className="dashboard-controls-grid">
          <label className="field compact-field">
            <span>States</span>
            <input className="input" value={states} onChange={(event) => setStates(event.target.value)} />
          </label>
          <label className="field compact-field">
            <span>Scan Mode</span>
            <select className="select" defaultValue="both">
              <option value="both">Asset + Supplier</option>
            </select>
          </label>
          <div className="compact-category-row">
            {categories.map((category) => (
              <label className="compact-check" key={category}>
                <input
                  type="checkbox"
                  checked={selectedCategories.includes(category)}
                  onChange={() => toggleCategory(category)}
                />
                {category}
              </label>
            ))}
          </div>
        </div>

        <div className="dashboard-actions">
          <button className="button gold" onClick={startScan} disabled={busy || selectedCategories.length === 0}>
            {busy ? <Loader2 size={17} className="spin" /> : <Play size={17} />}
            Run Now
          </button>
          <button className="button secondary" onClick={refreshDashboard} disabled={busy}>
            <RefreshCw size={17} />
            Refresh
          </button>
          <StatusPill label="Scheduler" value={scheduler?.status ?? "paused"} />
          <StatusPill label="Telegram" value={dashboard?.telegram_enabled ? "enabled" : "disabled"} />
          <button className="button secondary icon-button" onClick={() => setScheduler("pause")} disabled={busy} title="Pause scheduler">
            <Pause size={16} />
          </button>
          <button className="button secondary icon-button" onClick={() => setScheduler("resume")} disabled={busy} title="Resume scheduler">
            <Play size={16} />
          </button>
        </div>
        {error ? <p className="danger-text">{error}</p> : null}
      </section>

      <section className="metric-grid dashboard-metrics">
        <Metric label="Final Opportunities" value={stats?.final_opportunities ?? dashboard?.active_opportunities ?? 0} />
        <Metric label="New" value={stats?.new_opportunities ?? 0} />
        <Metric label="Changed" value={stats?.changed_opportunities ?? 0} />
        <Metric label="Auction Ending" value={auctionEndingCount} />
        <Metric label="Failed Sources" value={stats?.failed_sources ?? sourceSummary.failed} tone={sourceSummary.failed ? "danger" : "normal"} />
      </section>

      <nav className="dashboard-tabs">
        {tabs.map((tab) => (
          <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === "overview" ? (
        <div className="dashboard-overview">
          <section className="panel compact-panel">
            <div className="panel-head">
              <div>
                <div className="section-label">Top Opportunities</div>
                <h2>Best current candidates</h2>
              </div>
              <button className="button secondary" onClick={() => setActiveTab("opportunities")}>
                View All
              </button>
            </div>
            <OpportunityTable
              opportunities={sortedOpportunities.slice(0, 12)}
              onView={setSelectedOpportunity}
              compact
            />
          </section>

          <section className="panel compact-panel">
            <div className="panel-head">
              <div>
                <div className="section-label">Source Runs</div>
                <h2>
                  {sourceSummary.successful} Sources Successful / {sourceSummary.zero} Zero Results / {sourceSummary.failed} Failed
                </h2>
              </div>
              <button className="button secondary" onClick={() => setShowSources((value) => !value)}>
                {showSources ? "Collapse Source Runs" : "View Source Runs"}
              </button>
            </div>
            {showSources ? <SourceRunsTable sourceRuns={sourceRuns} /> : null}
          </section>

          <section className="panel compact-panel">
            <div className="panel-head">
              <div>
                <div className="section-label">Quality Details</div>
                <h2>{stats?.raw_results ?? 0} raw / {stats?.specific_listings ?? 0} specific / {stats?.duplicates_removed ?? 0} duplicate</h2>
              </div>
              <button className="button secondary" onClick={() => setShowQuality((value) => !value)}>
                {showQuality ? "Hide Quality Details" : "Quality Details"}
              </button>
            </div>
            {showQuality ? <QualityDetails stats={stats} /> : null}
          </section>
        </div>
      ) : null}

      {activeTab === "opportunities" ? (
        <section className="panel compact-panel">
          <div className="panel-head">
            <div>
              <div className="section-label">Opportunities</div>
              <h2>{sortedOpportunities.length} formal specific listings</h2>
            </div>
            <label className="field compact-field sort-field">
              <span>Sort</span>
              <select className="select" value={sortBy} onChange={(event) => setSortBy(event.target.value as SortBy)}>
                <option value="score">Score</option>
                <option value="newest">Newest</option>
                <option value="price">Price</option>
                <option value="auction">Auction End Time</option>
                <option value="risk">Risk</option>
              </select>
            </label>
          </div>
          <OpportunityTable opportunities={sortedOpportunities} onView={setSelectedOpportunity} />
        </section>
      ) : null}

      {activeTab === "source runs" ? (
        <section className="panel compact-panel">
          <div className="panel-head">
            <div>
              <div className="section-label">Source Runs</div>
              <h2>
                {sourceSummary.successful} successful / {sourceSummary.zero} zero / {sourceSummary.failed} failed
              </h2>
            </div>
            <button className="button secondary" onClick={() => setShowSources((value) => !value)}>
              {showSources ? "Collapse Source Runs" : "View Source Runs"}
            </button>
          </div>
          {showSources ? <SourceRunsTable sourceRuns={sourceRuns} /> : <p className="muted">Source run details are collapsed by default.</p>}
        </section>
      ) : null}

      {activeTab === "telegram reports" ? (
        <section className="panel compact-panel">
          <div className="panel-head">
            <div>
              <div className="section-label">Telegram Reports</div>
              <h2>Preview, test, approve</h2>
            </div>
            <div className="dashboard-actions no-margin">
              <button className="button secondary" onClick={() => generateReport("preview")} disabled={busy || !activeJobId}>
                <Bell size={17} />
                Preview Daily Report
              </button>
              <button className="button secondary" onClick={() => generateReport("test")} disabled={busy || !activeJobId}>
                <Send size={17} />
                Send Test Message
              </button>
              <button className="button gold" onClick={() => generateReport("approve_and_send")} disabled={busy || !activeJobId}>
                <Send size={17} />
                Approve and Send
              </button>
            </div>
          </div>
          <div className="telegram-summary">
            <StatusPill label="Delivery" value={report?.delivery_log?.status ?? "none"} />
            <StatusPill label="Message ID" value={report?.delivery_log?.telegram_message_id ?? "none"} />
            <button className="button secondary" onClick={() => setTelegramOpen(true)} disabled={!report}>
              Open Preview
            </button>
          </div>
          {report?.delivery_log?.error_message ? <p className="danger-text">{report.delivery_log.error_message}</p> : null}
        </section>
      ) : null}

      <OpportunityDrawer opportunity={selectedOpportunity} onClose={() => setSelectedOpportunity(null)} />
      <TelegramDrawer
        open={telegramOpen}
        reportText={report?.message_zh}
        deliveryStatus={report?.delivery_log?.status}
        messageId={report?.delivery_log?.telegram_message_id}
        error={report?.delivery_log?.error_message}
        onClose={() => setTelegramOpen(false)}
      />
    </div>
  );
}

function Metric({ label, value, tone = "normal" }: { label: string; value: number | string; tone?: "normal" | "danger" }) {
  return (
    <div className={`metric compact-metric ${tone === "danger" ? "danger-metric" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="status-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

function OpportunityTable({
  opportunities,
  onView,
  compact = false,
}: {
  opportunities: HardwareOpportunity[];
  onView: (opportunity: HardwareOpportunity) => void;
  compact?: boolean;
}) {
  if (!opportunities.length) {
    return <div className="muted empty-state">No formal specific listings yet.</div>;
  }
  return (
    <div className="table-wrap compact-table-wrap">
      <table className="compact-table opportunity-table">
        <thead>
          <tr>
            <th>Score</th>
            <th>Category</th>
            <th>Title</th>
            <th>Model</th>
            <th>Qty</th>
            <th>Price</th>
            <th>Status</th>
            <th>Source</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.slice(0, compact ? 12 : opportunities.length).map((item) => (
            <tr key={`${item.opportunity_id}-${item.source_url}`}>
              <td>
                <span className="score-ring">{item.opportunity_score.toFixed(0)}</span>
              </td>
              <td>{item.category}</td>
              <td>
                <div className="title-cell">
                  <span>{item.title}</span>
                  <BadgeRow item={item} />
                </div>
              </td>
              <td>{item.model ?? <span className="muted">verify</span>}</td>
              <td>{item.quantity ?? <span className="muted">verify</span>}</td>
              <td>{formatMoney(item.total_price)}</td>
              <td><span className="pill">{item.status}</span></td>
              <td>{item.source}</td>
              <td>
                <button className="button secondary compact-button" onClick={() => onView(item)}>
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BadgeRow({ item }: { item: HardwareOpportunity }) {
  const badges = [...item.change_types, ...item.risk_flags].slice(0, 4);
  if (!badges.length) return null;
  return (
    <div className="badge-row">
      {badges.map((badge) => (
        <span className={`badge ${badge === "NEW" ? "new-badge" : badge.includes("CHANGED") ? "changed-badge" : ""}`} key={badge}>
          {badge}
        </span>
      ))}
    </div>
  );
}

function SourceRunsTable({ sourceRuns }: { sourceRuns: HardwareSourceRun[] }) {
  return (
    <div className="table-wrap compact-table-wrap">
      <table className="compact-table source-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Category</th>
            <th>Status</th>
            <th>Results</th>
            <th>Query</th>
          </tr>
        </thead>
        <tbody>
          {sourceRuns.map((run) => (
            <tr key={run.id}>
              <td>{run.source_name}</td>
              <td>{run.category ?? "-"}</td>
              <td><span className="pill">{run.status}</span></td>
              <td>{run.result_count}</td>
              <td className="muted truncate-query" title={run.query ?? ""}>{run.query ?? "-"}</td>
            </tr>
          ))}
          {!sourceRuns.length ? <tr><td colSpan={5} className="muted">No source runs yet.</td></tr> : null}
        </tbody>
      </table>
    </div>
  );
}

function QualityDetails({ stats }: { stats: HardwareScanJob["quality_stats"] | undefined }) {
  const items = [
    ["Raw", stats?.raw_results ?? 0],
    ["Specific", stats?.specific_listings ?? 0],
    ["Collections", stats?.listing_collections ?? 0],
    ["Source Pages", stats?.source_pages ?? 0],
    ["News", stats?.news_or_articles ?? 0],
    ["Irrelevant", stats?.irrelevant ?? 0],
    ["Duplicates", stats?.duplicates_removed ?? 0],
  ];
  return (
    <div className="quality-strip">
      {items.map(([label, value]) => (
        <span key={label}>
          {label}
          <strong>{value}</strong>
        </span>
      ))}
    </div>
  );
}

function OpportunityDrawer({ opportunity, onClose }: { opportunity: HardwareOpportunity | null; onClose: () => void }) {
  if (!opportunity) return null;
  const missingFields = fieldsNeedingVerification(opportunity);
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <DrawerHeader title="Opportunity Details" onClose={onClose} />
        <div className="drawer-body">
          <div className="drawer-title-row">
            <h2>{opportunity.title}</h2>
            <span className="score-ring large">{opportunity.opportunity_score.toFixed(0)}</span>
          </div>
          <p className="muted">{opportunity.raw_description || "No public snippet available."}</p>
          <div className="drawer-score-row">
            <StatusPill label="Risk" value={`${opportunity.risk_score.toFixed(0)}/100`} />
            <StatusPill label="Source" value={opportunity.source} />
            <StatusPill label="Page" value={opportunity.page_type} />
          </div>
          <div className="detail-compact-grid">
            <Detail label="Model" value={opportunity.model} />
            <Detail label="Quantity" value={opportunity.quantity} />
            <Detail label="Unit Price" value={formatMoney(opportunity.unit_price)} />
            <Detail label="Total Price" value={formatMoney(opportunity.total_price)} />
            <Detail label="Condition" value={opportunity.condition} />
            <Detail label="Location" value={[opportunity.location_city, opportunity.location_state].filter(Boolean).join(", ")} />
            <Detail label="Auction End" value={formatDate(opportunity.auction_end_time)} />
            <Detail label="Pickup / Shipping" value={pickupShipping(opportunity)} />
          </div>
          <p className="muted">
            Fields needing verification: {missingFields.length ? missingFields.join(", ") : "none"}
          </p>
          <div className="badge-row">
            {opportunity.risk_flags.map((flag) => <span className="badge" key={flag}>{flag}</span>)}
            {opportunity.change_types.map((change) => <span className="badge new-badge" key={change}>{change}</span>)}
          </div>
          <div className="drawer-url">
            <span className="section-label">Canonical URL</span>
            <p>{opportunity.canonical_url ?? opportunity.source_url}</p>
          </div>
          <a className="button gold" href={opportunity.source_url} target="_blank">
            <ExternalLink size={16} />
            Open Original Link
          </a>
        </div>
      </aside>
    </div>
  );
}

function TelegramDrawer({
  open,
  reportText,
  deliveryStatus,
  messageId,
  error,
  onClose,
}: {
  open: boolean;
  reportText?: string;
  deliveryStatus?: string;
  messageId?: string | null;
  error?: string | null;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <DrawerHeader title="Telegram Report" onClose={onClose} />
        <div className="drawer-body">
          <div className="drawer-score-row">
            <StatusPill label="Delivery" value={deliveryStatus ?? "none"} />
            <StatusPill label="Message ID" value={messageId ?? "none"} />
          </div>
          {error ? <p className="danger-text">{error}</p> : null}
          <pre className="telegram-preview">{reportText ?? "No report preview yet."}</pre>
        </div>
      </aside>
    </div>
  );
}

function DrawerHeader({ title, onClose }: { title: string; onClose: () => void }) {
  return (
    <div className="drawer-header">
      <h2>{title}</h2>
      <button className="button secondary icon-button" onClick={onClose}>
        <X size={16} />
      </button>
    </div>
  );
}

function Detail({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value || <span className="muted">verify</span>}</strong>
    </div>
  );
}

function sortOpportunities(opportunities: HardwareOpportunity[], sortBy: SortBy) {
  return [...opportunities].sort((a, b) => {
    if (sortBy === "newest") return Date.parse(b.first_seen_at) - Date.parse(a.first_seen_at);
    if (sortBy === "price") return (b.total_price ?? -1) - (a.total_price ?? -1);
    if (sortBy === "auction") return Date.parse(a.auction_end_time ?? "9999-12-31") - Date.parse(b.auction_end_time ?? "9999-12-31");
    if (sortBy === "risk") return b.risk_score - a.risk_score;
    return b.opportunity_score - a.opportunity_score;
  });
}

function summarizeSources(sourceRuns: HardwareSourceRun[]) {
  return sourceRuns.reduce(
    (summary, run) => {
      if (["failed", "timeout", "blocked"].includes(run.status)) summary.failed += 1;
      else if (run.result_count === 0) summary.zero += 1;
      else summary.successful += 1;
      return summary;
    },
    { successful: 0, zero: 0, failed: 0 },
  );
}

function fieldsNeedingVerification(item: HardwareOpportunity) {
  const fields: string[] = [];
  if (!item.quantity) fields.push("quantity");
  if (!item.total_price && !item.unit_price) fields.push("price");
  if (!item.location_city && !item.location_state && !item.zip_code) fields.push("location");
  if (!item.configuration) fields.push("configuration");
  if (!item.auction_end_time) fields.push("auction end time");
  return fields;
}

function formatMoney(value?: number | null) {
  return value ? `$${value.toLocaleString()}` : "verify";
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "verify";
}

function pickupShipping(item: HardwareOpportunity) {
  const pickup = item.pickup_only === true ? "pickup only" : item.pickup_only === false ? "pickup unknown" : "pickup verify";
  const shipping = item.shipping_available === true ? "shipping yes" : item.shipping_available === false ? "shipping no" : "shipping verify";
  return `${pickup} / ${shipping}`;
}
