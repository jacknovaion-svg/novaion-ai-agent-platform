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
type OpportunityFilter = "current" | "active" | "ending_soon" | "needs_review" | "expired" | "missing_components" | "pickup_only";
type RegionStrategy = "all_us" | "priority_states" | "rotating_states" | "custom_states";
type ScanPreset =
  | "full_hardware_scan"
  | "servers_only"
  | "gpu_memory"
  | "government_auctions"
  | "data_center_decommissioning"
  | "supplier_discovery"
  | "custom";
type DashboardScanMode = "asset_listing_search" | "supplier_lead_search" | "both";

const sourceCount = 5;
const defaultStates = ["TX", "CA", "GA"];
const categoryLabels: Record<HardwareCategory, string> = {
  servers: "Servers",
  gpu: "GPU",
  memory: "Memory",
  storage: "HDD / SSD / NVMe",
  cpu: "CPU",
};
const scanModeLabels: Record<DashboardScanMode, string> = {
  asset_listing_search: "Asset Listings / 设备销售信息",
  supplier_lead_search: "Supplier Leads / 供应商线索",
  both: "Both / 两者都扫描",
};
const regionStrategies: Record<RegionStrategy, string> = {
  all_us: "All US",
  priority_states: "Priority States",
  rotating_states: "Rotating States",
  custom_states: "Custom States",
};

const usStates = [
  ["AL", "Alabama", "阿拉巴马州"],
  ["AK", "Alaska", "阿拉斯加州"],
  ["AZ", "Arizona", "亚利桑那州"],
  ["AR", "Arkansas", "阿肯色州"],
  ["CA", "California", "加州"],
  ["CO", "Colorado", "科罗拉多州"],
  ["CT", "Connecticut", "康涅狄格州"],
  ["DE", "Delaware", "特拉华州"],
  ["FL", "Florida", "佛州"],
  ["GA", "Georgia", "乔治亚州"],
  ["HI", "Hawaii", "夏威夷州"],
  ["ID", "Idaho", "爱达荷州"],
  ["IL", "Illinois", "伊利诺伊州"],
  ["IN", "Indiana", "印第安纳州"],
  ["IA", "Iowa", "爱荷华州"],
  ["KS", "Kansas", "堪萨斯州"],
  ["KY", "Kentucky", "肯塔基州"],
  ["LA", "Louisiana", "路易斯安那州"],
  ["ME", "Maine", "缅因州"],
  ["MD", "Maryland", "马里兰州"],
  ["MA", "Massachusetts", "马萨诸塞州"],
  ["MI", "Michigan", "密歇根州"],
  ["MN", "Minnesota", "明尼苏达州"],
  ["MS", "Mississippi", "密西西比州"],
  ["MO", "Missouri", "密苏里州"],
  ["MT", "Montana", "蒙大拿州"],
  ["NE", "Nebraska", "内布拉斯加州"],
  ["NV", "Nevada", "内华达州"],
  ["NH", "New Hampshire", "新罕布什尔州"],
  ["NJ", "New Jersey", "新泽西州"],
  ["NM", "New Mexico", "新墨西哥州"],
  ["NY", "New York", "纽约州"],
  ["NC", "North Carolina", "北卡罗来纳州"],
  ["ND", "North Dakota", "北达科他州"],
  ["OH", "Ohio", "俄亥俄州"],
  ["OK", "Oklahoma", "俄克拉荷马州"],
  ["OR", "Oregon", "俄勒冈州"],
  ["PA", "Pennsylvania", "宾夕法尼亚州"],
  ["RI", "Rhode Island", "罗德岛州"],
  ["SC", "South Carolina", "南卡罗来纳州"],
  ["SD", "South Dakota", "南达科他州"],
  ["TN", "Tennessee", "田纳西州"],
  ["TX", "Texas", "德州"],
  ["UT", "Utah", "犹他州"],
  ["VT", "Vermont", "佛蒙特州"],
  ["VA", "Virginia", "弗吉尼亚州"],
  ["WA", "Washington", "华盛顿州"],
  ["DC", "Washington, D.C.", "华盛顿特区"],
  ["WV", "West Virginia", "西弗吉尼亚州"],
  ["WI", "Wisconsin", "威斯康星州"],
  ["WY", "Wyoming", "怀俄明州"],
] as const;
const allStateCodes = usStates.map(([code]) => code);
const stateLookup = new Map<string, string>(
  usStates.flatMap(([code, name, zh]) => [
    [code.toLowerCase(), code],
    [name.toLowerCase(), code],
    [zh.toLowerCase(), code],
  ]),
);

export default function HardwareDashboardPage() {
  const [dashboard, setDashboard] = useState<HardwareDashboard | null>(null);
  const [job, setJob] = useState<HardwareScanJob | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<HardwareCategory[]>(categories);
  const [selectedStates, setSelectedStates] = useState<string[]>(defaultStates);
  const [stateDraft, setStateDraft] = useState("");
  const [regionStrategy, setRegionStrategy] = useState<RegionStrategy>("priority_states");
  const [scanPreset, setScanPreset] = useState<ScanPreset>("full_hardware_scan");
  const [scanMode, setScanMode] = useState<DashboardScanMode>("both");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [showQuality, setShowQuality] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("score");
  const [opportunityFilter, setOpportunityFilter] = useState<OpportunityFilter>("current");
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

  const filteredOpportunities = useMemo(() => filterOpportunities(opportunities, opportunityFilter), [opportunities, opportunityFilter]);
  const sortedOpportunities = useMemo(() => sortOpportunities(filteredOpportunities, sortBy), [filteredOpportunities, sortBy]);
  const sourceSummary = useMemo(() => summarizeSources(sourceRuns), [sourceRuns]);
  const scanProgress = useMemo(() => buildScanProgress(job), [job]);
  const coverageLabel = useMemo(
    () => regionStrategy === "all_us" ? "All 50 States + Washington, D.C." : selectedStates.join(", "),
    [regionStrategy, selectedStates],
  );
  const estimatedTasks = useMemo(
    () => estimateTasks(regionStrategy, selectedStates.length, selectedCategories.length),
    [regionStrategy, selectedStates.length, selectedCategories.length],
  );
  const runButtonLabel = useMemo(() => {
    if (busy || scanProgress.isScanning) return "Scanning...";
    if (job?.status === "completed" || job?.status === "partially_completed") return "Completed";
    if (job?.status === "failed") return "Failed";
    return "Run Scan Now";
  }, [busy, job?.status, scanProgress.isScanning]);
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
        mode: scanMode,
        categories: selectedCategories,
        states: regionStrategy === "all_us" ? [] : selectedStates,
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

  function addState() {
    const normalized = normalizeState(stateDraft);
    if (!normalized) {
      setStateDraft("");
      return;
    }
    setSelectedStates((current) => current.includes(normalized) ? current : [...current, normalized]);
    setRegionStrategy((current) => current === "all_us" ? "custom_states" : current);
    setScanPreset("custom");
    setStateDraft("");
  }

  function removeState(code: string) {
    setSelectedStates((current) => current.filter((item) => item !== code));
    setRegionStrategy((current) => current === "all_us" ? "custom_states" : current);
    setScanPreset("custom");
  }

  function applyPreset(preset: ScanPreset) {
    setScanPreset(preset);
    if (preset === "full_hardware_scan") {
      setRegionStrategy("priority_states");
      setSelectedStates(defaultStates);
      setScanMode("both");
      setSelectedCategories(categories);
    } else if (preset === "servers_only") {
      setRegionStrategy("priority_states");
      setSelectedStates(defaultStates);
      setScanMode("asset_listing_search");
      setSelectedCategories(["servers"]);
    } else if (preset === "gpu_memory") {
      setRegionStrategy("priority_states");
      setSelectedStates(defaultStates);
      setScanMode("asset_listing_search");
      setSelectedCategories(["gpu", "memory"]);
    } else if (preset === "government_auctions") {
      setRegionStrategy("all_us");
      setScanMode("asset_listing_search");
      setSelectedCategories(categories);
    } else if (preset === "data_center_decommissioning") {
      setRegionStrategy("priority_states");
      setSelectedStates(["TX", "CA", "GA", "VA", "AZ"]);
      setScanMode("both");
      setSelectedCategories(["servers", "gpu", "memory", "storage"]);
    } else if (preset === "supplier_discovery") {
      setRegionStrategy("priority_states");
      setSelectedStates(defaultStates);
      setScanMode("supplier_lead_search");
      setSelectedCategories(["servers", "gpu", "memory", "storage"]);
    }
  }

  return (
    <div className="hardware-dashboard">
      <section className="panel dashboard-control">
        <div className="scan-control-header">
          <div>
            <div className="section-label">Hardware Hunter V2</div>
            <h1 className="dashboard-title">退役IT资产扫描</h1>
          </div>
          <label className="field compact-field preset-field">
            <span>Scan Preset</span>
            <select className="select" value={scanPreset} onChange={(event) => applyPreset(event.target.value as ScanPreset)}>
              <option value="full_hardware_scan">Full Hardware Scan</option>
              <option value="servers_only">Servers Only</option>
              <option value="gpu_memory">GPU + Memory</option>
              <option value="government_auctions">Government Auctions</option>
              <option value="data_center_decommissioning">Data Center Decommissioning</option>
              <option value="supplier_discovery">Supplier Discovery</option>
              <option value="custom">Custom</option>
            </select>
          </label>
        </div>

        <div className="scan-config-row">
          <label className="field compact-field">
            <span>Region Strategy</span>
            <select className="select" value={regionStrategy} onChange={(event) => { setRegionStrategy(event.target.value as RegionStrategy); setScanPreset("custom"); }}>
              {Object.entries(regionStrategies).map(([value, label]) => (
                <option value={value} key={value}>{label}</option>
              ))}
            </select>
            <small className="strategy-help">{regionStrategyDescription(regionStrategy)}</small>
          </label>

          <div className="field compact-field state-picker">
            <span>States</span>
            {regionStrategy === "all_us" ? (
              <div className="coverage-banner">Coverage: All 50 States + Washington, D.C.</div>
            ) : (
              <>
                <div className="state-chip-row">
                  {selectedStates.map((code) => (
                    <button className="state-chip" key={code} onClick={() => removeState(code)}>
                      {code} <X size={12} />
                    </button>
                  ))}
                  <input
                    className="state-add-input"
                    value={stateDraft}
                    onChange={(event) => setStateDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        addState();
                      }
                    }}
                    placeholder="+ Add State"
                  />
                  <button className="button secondary compact-button" onClick={addState}>Add</button>
                </div>
                <div className="mini-actions">
                  <button onClick={() => { setSelectedStates(allStateCodes); setScanPreset("custom"); }}>Select All</button>
                  <button onClick={() => { setSelectedStates([]); setScanPreset("custom"); }}>Clear All</button>
                </div>
              </>
            )}
          </div>

          <label className="field compact-field">
            <span>Scan Mode</span>
            <select className="select" value={scanMode} onChange={(event) => { setScanMode(event.target.value as DashboardScanMode); setScanPreset("custom"); }}>
              {Object.entries(scanModeLabels).map(([value, label]) => (
                <option value={value} key={value}>{label}</option>
              ))}
            </select>
          </label>

          <div className="field compact-field categories-field">
            <span>Categories</span>
            <div className="compact-category-row single-line">
              {categories.map((category) => (
                <label className="compact-check" key={category}>
                  <input
                    type="checkbox"
                    checked={selectedCategories.includes(category)}
                    onChange={() => { toggleCategory(category); setScanPreset("custom"); }}
                  />
                  {categoryLabels[category]}
                </label>
              ))}
            </div>
            <div className="mini-actions">
              <button onClick={() => { setSelectedCategories(categories); setScanPreset("custom"); }}>Select All</button>
              <button onClick={() => { setSelectedCategories([]); setScanPreset("custom"); }}>Clear</button>
            </div>
          </div>
        </div>

        <div className="scan-action-row">
          <div className="scan-action-main">
            <button className="button gold run-scan-button" onClick={startScan} disabled={busy || scanProgress.isScanning || selectedCategories.length === 0}>
              {busy || scanProgress.isScanning ? <Loader2 size={17} className="spin" /> : <Play size={17} />}
              {runButtonLabel}
            </button>
            <button className="button secondary" onClick={refreshDashboard} disabled={busy}>
              <RefreshCw size={17} />
              Refresh
            </button>
            <div className="scan-summary">
              {coverageLabel || "No states"} · {selectedCategories.length} categories · {sourceCount} sources · {estimatedTasks} estimated tasks
            </div>
            {scanProgress.isScanning ? (
              <div className="scan-progress">
                <span>{scanProgress.completed}/{scanProgress.total} tasks</span>
                <span>{scanProgress.currentCategory} · {scanProgress.currentSource}</span>
                <span>{scanProgress.elapsed}</span>
              </div>
            ) : null}
          </div>

          <div className="status-card-row">
            <div className="mini-status-card">
              <div className="section-label">Scheduler</div>
              <strong>{scheduler?.status ?? "paused"}</strong>
              <span>Last: {scheduler?.last_run_at ? new Date(scheduler.last_run_at).toLocaleString() : "none"}</span>
              <span>Next: {scheduler?.next_run_at ? new Date(scheduler.next_run_at).toLocaleString() : "paused"}</span>
              <div>
                <button className="button secondary compact-button" onClick={() => setScheduler("pause")} disabled={busy}><Pause size={14} /> Pause</button>
                <button className="button secondary compact-button" onClick={() => setScheduler("resume")} disabled={busy}><Play size={14} /> Resume</button>
              </div>
            </div>
            <div className="mini-status-card">
              <div className="section-label">Telegram</div>
              <strong>{telegramStatus(dashboard)}</strong>
              <span>Last delivery: {report?.delivery_log?.status ?? "none"}</span>
              <div>
                <button className="button secondary compact-button" onClick={() => setActiveTab("telegram reports")}>Configure</button>
                <button className="button secondary compact-button" onClick={() => generateReport("test")} disabled={busy || !activeJobId}><Send size={14} /> Test</button>
              </div>
            </div>
          </div>
        </div>
        {error ? <p className="danger-text">{error}</p> : null}
        {dashboard?.persistence_warning ? <p className="warning-text">{dashboard.persistence_warning}</p> : null}
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
            <label className="field compact-field sort-field">
              <span>Filter</span>
              <select className="select" value={opportunityFilter} onChange={(event) => setOpportunityFilter(event.target.value as OpportunityFilter)}>
                <option value="current">Current</option>
                <option value="active">Active</option>
                <option value="ending_soon">Ending Soon</option>
                <option value="needs_review">Needs Review</option>
                <option value="expired">Expired</option>
                <option value="missing_components">Missing Components</option>
                <option value="pickup_only">Pickup Only</option>
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
            <th>End Time</th>
            <th>Time Left</th>
            <th>Quantity</th>
            <th>Current Price</th>
            <th>Unit Cost</th>
            <th>Location</th>
            <th>Completeness</th>
            <th>Status</th>
            <th>Verification</th>
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
              <td>{formatShortDate(item.auction_end_time)}</td>
              <td>{item.time_remaining ?? <span className="muted">verify</span>}</td>
              <td>{item.quantity ?? <span className="muted">verify</span>}</td>
              <td>{formatMoney(item.current_total_cost ?? item.total_price)}</td>
              <td>{formatMoney(item.cost_per_unit ?? item.unit_price)}</td>
              <td>{[item.location_city, item.location_state].filter(Boolean).join(", ") || <span className="muted">verify</span>}</td>
              <td><span className="pill">{item.component_completeness}</span></td>
              <td><span className="pill">{item.listing_status}</span></td>
              <td>{item.needs_manual_review ? <span className="badge changed-badge">needs review</span> : <span className="badge new-badge">checked</span>}</td>
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
    ["Active", stats?.active_opportunities ?? 0],
    ["Ending Soon", stats?.ending_soon ?? 0],
    ["Expired", stats?.expired_removed ?? 0],
    ["Unavailable", stats?.unavailable_links ?? 0],
    ["Needs Review", stats?.needs_manual_review ?? 0],
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
            <StatusPill label="Listing" value={opportunity.listing_status} />
            <StatusPill label="Recommendation" value={opportunity.recommendation} />
          </div>
          <div className="detail-compact-grid">
            <Detail label="Lot Number" value={opportunity.lot_number} />
            <Detail label="Model" value={opportunity.model} />
            <Detail label="Quantity" value={opportunity.quantity} />
            <Detail label="Current Price" value={formatMoney(opportunity.current_total_cost ?? opportunity.total_price)} />
            <Detail label="Unit Cost" value={formatMoney(opportunity.cost_per_unit ?? opportunity.unit_price)} />
            <Detail label="Cost / GB" value={formatMoney(opportunity.cost_per_gb)} />
            <Detail label="Cost Confidence" value={opportunity.cost_confidence} />
            <Detail label="Bid Count" value={opportunity.bid_count} />
            <Detail label="Buyer Premium" value={opportunity.buyer_premium} />
            <Detail label="Condition" value={opportunity.condition} />
            <Detail label="Completeness" value={opportunity.component_completeness} />
            <Detail label="Location" value={[opportunity.location_city, opportunity.location_state].filter(Boolean).join(", ")} />
            <Detail label="Auction End" value={formatDate(opportunity.auction_end_time)} />
            <Detail label="Time Left" value={opportunity.time_remaining} />
            <Detail label="Pickup / Shipping" value={pickupShipping(opportunity)} />
            <Detail label="Last Checked" value={formatDate(opportunity.last_checked_at)} />
          </div>
          <p className="muted">
            Fields needing verification: {missingFields.length ? missingFields.join(", ") : "none"}
          </p>
          <div className="badge-row">
            {opportunity.recommendation_reasons.map((reason) => <span className="badge changed-badge" key={reason}>{reason}</span>)}
            {opportunity.risk_flags.map((flag) => <span className="badge" key={flag}>{flag}</span>)}
            {opportunity.change_types.map((change) => <span className="badge new-badge" key={change}>{change}</span>)}
          </div>
          {opportunity.unavailable_reason ? <p className="danger-text">Unavailable reason: {opportunity.unavailable_reason}</p> : null}
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
    if (sortBy === "price") return (b.current_total_cost ?? b.total_price ?? -1) - (a.current_total_cost ?? a.total_price ?? -1);
    if (sortBy === "auction") return Date.parse(a.auction_end_time ?? "9999-12-31") - Date.parse(b.auction_end_time ?? "9999-12-31");
    if (sortBy === "risk") return b.risk_score - a.risk_score;
    return b.opportunity_score - a.opportunity_score;
  });
}

function filterOpportunities(opportunities: HardwareOpportunity[], filter: OpportunityFilter) {
  return opportunities.filter((item) => {
    if (filter === "current") return !["ended", "sold", "removed", "unavailable"].includes(item.listing_status);
    if (filter === "active") return item.listing_status === "active";
    if (filter === "ending_soon") return item.listing_status === "ending_soon";
    if (filter === "needs_review") return item.needs_manual_review || item.listing_status === "unknown";
    if (filter === "expired") return ["ended", "sold", "removed", "unavailable"].includes(item.listing_status);
    if (filter === "missing_components") return ["missing_storage", "missing_memory", "missing_cpu", "missing_psu", "barebone", "mixed_lot"].includes(item.component_completeness);
    if (filter === "pickup_only") return item.pickup_only === true;
    return true;
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

function normalizeState(input: string) {
  const key = input.trim().toLowerCase();
  if (!key) return null;
  return stateLookup.get(key) ?? null;
}

function estimateTasks(strategy: RegionStrategy, stateCount: number, categoryCount: number) {
  const regionFactor = strategy === "all_us" ? 1 : Math.max(stateCount, 1);
  return regionFactor * categoryCount * sourceCount;
}

function buildScanProgress(job: HardwareScanJob | null) {
  const isScanning = job?.status === "created" || job?.status === "running";
  const total = Math.max(job?.generated_queries?.length ?? 0, job?.source_runs?.length ?? 0, 1);
  const completed = job?.source_runs?.filter((run) => run.status !== "searching" && run.status !== "pending").length ?? 0;
  const activeRun = job?.source_runs?.find((run) => run.status === "searching");
  const lastRun = job?.source_runs?.[job.source_runs.length - 1];
  const elapsedSeconds = job ? Math.max(0, Math.round((Date.now() - Date.parse(job.created_at)) / 1000)) : 0;
  return {
    isScanning,
    total,
    completed: Math.min(completed, total),
    currentCategory: activeRun?.category ?? lastRun?.category ?? "waiting",
    currentSource: activeRun?.source_name ?? lastRun?.source_name ?? "queued",
    elapsed: `${Math.floor(elapsedSeconds / 60)}m ${elapsedSeconds % 60}s`,
  };
}

function telegramStatus(dashboard: HardwareDashboard | null) {
  if (!dashboard?.telegram_enabled) return "Disabled";
  return "Enabled";
}

function regionStrategyDescription(strategy: RegionStrategy) {
  if (strategy === "all_us") return "National platforms scan all US; local sources follow task policy.";
  if (strategy === "priority_states") return "Scan selected priority states first.";
  if (strategy === "rotating_states") return "Rotate a subset of states each daily run.";
  return "Use only the states selected below.";
}

function fieldsNeedingVerification(item: HardwareOpportunity) {
  const fields: string[] = [];
  if (!item.quantity) fields.push("quantity");
  if (!item.total_price && !item.current_price && !item.unit_price) fields.push("price");
  if (!item.location_city && !item.location_state && !item.zip_code) fields.push("location");
  if (!item.configuration) fields.push("configuration");
  if (!item.auction_end_time) fields.push("auction end time");
  if (item.listing_status === "unknown") fields.push("listing status");
  if (item.component_completeness === "unknown") fields.push("component completeness");
  return fields;
}

function formatMoney(value?: number | null) {
  return value ? `$${value.toLocaleString()}` : "verify";
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "verify";
}

function formatShortDate(value?: string | null) {
  return value ? new Date(value).toLocaleDateString() : "verify";
}

function pickupShipping(item: HardwareOpportunity) {
  const pickup = item.pickup_only === true ? "pickup only" : item.pickup_only === false ? "pickup unknown" : "pickup verify";
  const shipping = item.shipping_available === true ? "shipping yes" : item.shipping_available === false ? "shipping no" : "shipping verify";
  return `${pickup} / ${shipping}`;
}
