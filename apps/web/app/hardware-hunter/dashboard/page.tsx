"use client";

import { Bell, ExternalLink, Loader2, Play, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  createHardwareTelegramReport,
  getHardwareDailyScanJob,
  getHardwareDashboard,
  runHardwareDailyScan,
} from "@/lib/api";
import type { HardwareCategory, HardwareDashboard, HardwareScanJob } from "@novaion/shared/types";

const categories: HardwareCategory[] = ["servers", "gpu", "memory", "storage", "cpu"];

export default function HardwareDashboardPage() {
  const [dashboard, setDashboard] = useState<HardwareDashboard | null>(null);
  const [job, setJob] = useState<HardwareScanJob | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<HardwareCategory[]>(["servers", "gpu", "memory", "storage", "cpu"]);
  const [states, setStates] = useState("TX, CA, GA");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeJobId = job?.id ?? dashboard?.latest_job?.id;
  const opportunities = job?.opportunities ?? dashboard?.top_opportunities ?? [];
  const sourceRuns = job?.source_runs ?? dashboard?.latest_job?.source_runs ?? [];
  const report = job?.report ?? dashboard?.latest_job?.report;
  const stats = job?.quality_stats ?? dashboard?.latest_job?.quality_stats;

  useEffect(() => {
    void refreshDashboard();
  }, []);

  useEffect(() => {
    if (!activeJobId || job?.status === "completed" || job?.status === "partially_completed" || job?.status === "failed") return;
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

  const categoryLabel = useMemo(() => selectedCategories.join(", "), [selectedCategories]);

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

  async function generateReport() {
    if (!activeJobId) return;
    setBusy(true);
    try {
      const generated = await createHardwareTelegramReport(activeJobId, false);
      const latest = await getHardwareDailyScanJob(activeJobId);
      setJob({ ...latest, report: generated });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report failed");
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
    <div className="grid" style={{ gap: 18 }}>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1.2fr) minmax(320px, 0.8fr)", alignItems: "start" }}>
        <section className="panel">
          <div className="section-label">Hardware Hunter V2</div>
          <h1 className="page-title" style={{ marginTop: 8 }}>退役IT资产每日扫描</h1>
          <p className="muted">
            本地模式：公开搜索 GovDeals、Public Surplus、eBay、HGP 和工业拍卖发现结果，保留真实原始链接；不会自动购买、出价或联系卖家。
          </p>
          <div className="form-grid" style={{ marginTop: 18 }}>
            <label className="field">
              <span>States</span>
              <input className="input" value={states} onChange={(event) => setStates(event.target.value)} />
            </label>
            <label className="field">
              <span>Scan Mode</span>
              <select className="select" defaultValue="both">
                <option value="both">Asset Listing + Supplier Lead</option>
              </select>
            </label>
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="section-label">Categories: {categoryLabel}</div>
            <div className="source-grid">
              {categories.map((category) => (
                <label className="check" key={category}>
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
          {error ? <p style={{ color: "var(--danger)" }}>{error}</p> : null}
          <div style={{ display: "flex", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
            <button className="button" onClick={startScan} disabled={busy || selectedCategories.length === 0}>
              {busy ? <Loader2 size={17} className="spin" /> : <Play size={17} />}
              Start 24h Test Scan
            </button>
            <button className="button secondary" onClick={refreshDashboard} disabled={busy}>
              <RefreshCw size={17} />
              Refresh
            </button>
            <button className="button secondary" onClick={generateReport} disabled={busy || !activeJobId}>
              <Bell size={17} />
              Generate Telegram Preview
            </button>
          </div>
        </section>

        <aside className="panel">
          <div className="section-label">Scheduler</div>
          <h2 style={{ marginTop: 8 }}>Daily Report</h2>
          <div className="agent-list">
            <div className="agent-row"><span>Telegram</span><span className="pill">{dashboard?.telegram_enabled ? "enabled" : "disabled"}</span></div>
            <div className="agent-row"><span>Report hour</span><span className="pill">{dashboard?.daily_report_hour ?? 8}:00</span></div>
            <div className="agent-row"><span>Timezone</span><span className="pill">{dashboard?.timezone ?? "America/Los_Angeles"}</span></div>
            <div className="agent-row"><span>Immediate alerts</span><span className="pill">{dashboard?.immediate_alerts ? "enabled" : "disabled"}</span></div>
          </div>
          <p className="muted" style={{ marginTop: 14 }}>
            Telegram 默认关闭。配置 Bot Token 和 Chat ID 后，后端可以把同一份中文日报发送到 Telegram。
          </p>
        </aside>
      </div>

      <section className="metric-grid">
        <div className="metric"><span>Job Status</span><strong>{job?.status ?? dashboard?.latest_job?.status ?? "no job"}</strong></div>
        <div className="metric"><span>Raw Results</span><strong>{stats?.raw_results ?? 0}</strong></div>
        <div className="metric"><span>Final Opportunities</span><strong>{stats?.final_opportunities ?? dashboard?.active_opportunities ?? 0}</strong></div>
        <div className="metric"><span>Duplicates Removed</span><strong>{stats?.duplicates_removed ?? 0}</strong></div>
        <div className="metric"><span>New</span><strong>{stats?.new_opportunities ?? 0}</strong></div>
        <div className="metric"><span>Price Changes</span><strong>{stats?.price_changes ?? 0}</strong></div>
      </section>

      <section className="panel">
        <div className="section-label">Source Runs</div>
        <div className="table-wrap">
          <table>
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
              {sourceRuns.slice(0, 30).map((run) => (
                <tr key={run.id}>
                  <td>{run.source_name}</td>
                  <td>{run.category ?? "-"}</td>
                  <td><span className="pill">{run.status}</span></td>
                  <td>{run.result_count}</td>
                  <td className="muted">{run.query}</td>
                </tr>
              ))}
              {!sourceRuns.length ? <tr><td colSpan={5} className="muted">No source runs yet.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(340px, 0.8fr)", alignItems: "start" }}>
        <div className="grid">
          {opportunities.map((item) => (
            <article className="panel" key={item.opportunity_id}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
                <div>
                  <div className="section-label">{item.category} · {item.source}</div>
                  <h3 style={{ margin: "8px 0" }}>{item.title}</h3>
                  <p className="muted">{item.raw_description || "No public snippet available."}</p>
                </div>
                <div style={{ textAlign: "right", minWidth: 120 }}>
                  <strong>{item.opportunity_score.toFixed(0)}/100</strong>
                  <div className="muted">risk {item.risk_score.toFixed(0)}</div>
                </div>
              </div>
              <div className="agent-list" style={{ marginTop: 12 }}>
                <div className="agent-row"><span>Model</span><span>{item.model ?? "unknown"}</span></div>
                <div className="agent-row"><span>Quantity</span><span>{item.quantity ?? "unknown"}</span></div>
                <div className="agent-row"><span>Total Price</span><span>{item.total_price ? `$${item.total_price.toLocaleString()}` : "unknown"}</span></div>
                <div className="agent-row"><span>Condition</span><span>{item.condition}</span></div>
                <div className="agent-row"><span>Confidence</span><span>{item.confidence_level}</span></div>
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
                {item.change_types.map((change) => <span className="pill" key={change}>{change}</span>)}
                {item.risk_flags.map((flag) => <span className="pill" key={flag}>{flag}</span>)}
              </div>
              <a className="button secondary" style={{ marginTop: 14, display: "inline-flex" }} href={item.source_url} target="_blank">
                <ExternalLink size={16} />
                Open Original Link
              </a>
            </article>
          ))}
          {!opportunities.length ? <div className="panel muted">还没有扫描结果。点击 Start 24h Test Scan 开始本地测试。</div> : null}
        </div>
        <aside className="panel">
          <div className="section-label">Telegram Preview</div>
          <h2 style={{ marginTop: 8 }}>中文日报</h2>
          <pre style={{ whiteSpace: "pre-wrap", color: "var(--muted)", fontSize: 12, lineHeight: 1.6 }}>
            {report?.message_zh ?? "生成日报后会显示在这里。"}
          </pre>
          {report?.delivery_log ? (
            <div className="agent-row">
              <span>Delivery</span>
              <span className="pill">{report.delivery_log.status}</span>
            </div>
          ) : null}
        </aside>
      </section>
    </div>
  );
}
