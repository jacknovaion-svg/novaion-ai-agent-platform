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
  bulkReviewHardwareOpportunities,
  cancelHardwareDailyScan,
  createHardwareTelegramReport,
  getHardwareDailyScanJob,
  getHardwareDashboard,
  getHardwareScanProgress,
  recheckHardwareOpportunities,
  recheckHardwareOpportunity,
  runHardwareDailyScan,
  updateHardwareOpportunityManualStatus,
  updateHardwareScheduler,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type {
  HardwareCategory,
  HardwareDashboard,
  HardwareOpportunity,
  HardwareScanJob,
  HardwareScanProgress,
  HardwareSourceRun,
} from "@novaion/shared/types";

const categories: HardwareCategory[] = ["servers", "gpu", "memory", "storage", "cpu", "networking", "computers_it"];
const tabs = ["overview", "opportunities", "needs review", "source runs", "telegram reports"] as const;
type Tab = (typeof tabs)[number];
type SortBy = "score" | "newest" | "price" | "auction" | "risk";
type OpportunityFilter = "current" | "active" | "ending_soon" | "needs_review" | "history" | "missing_components" | "pickup_only";
type ResultScope = "current_scan" | "all_current" | "selected_states";
type RegionStrategy = "all_us" | "priority_states" | "rotating_states" | "custom_states";
type ScanDepth = "quick" | "standard" | "deep";
type ScanLane = "fast" | "deep";
type ScanScope = "nationwide" | "legacy_state";
type ScanPreset =
  | "full_hardware_scan"
  | "servers_only"
  | "gpu_memory"
  | "government_auctions"
  | "data_center_decommissioning"
  | "supplier_discovery"
  | "custom";
type DashboardScanMode = "asset_listing_search" | "supplier_lead_search" | "both";
type ReviewFormPayload = {
  manual_status: string;
  review_action: string;
  manual_quantity: string;
  manual_current_price: string;
  manual_total_price: string;
  manual_end_time: string;
  manual_timezone: string;
  manual_location: string;
  manual_condition: string;
  manual_component_completeness: string;
  review_notes: string;
};

const sourceCount = 5;
const scanDepthQueryCounts: Record<ScanDepth, number> = {
  quick: 2,
  standard: 5,
  deep: 10,
};
const defaultStates = ["TX", "CA", "GA"];
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
  const { t } = useI18n();
  const [dashboard, setDashboard] = useState<HardwareDashboard | null>(null);
  const [job, setJob] = useState<HardwareScanJob | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<HardwareCategory[]>(["servers"]);
  const [selectedStates, setSelectedStates] = useState<string[]>(defaultStates);
  const [stateDraft, setStateDraft] = useState("");
  const [regionStrategy, setRegionStrategy] = useState<RegionStrategy>("priority_states");
  const [scanScope, setScanScope] = useState<ScanScope>("nationwide");
  const [scanPreset, setScanPreset] = useState<ScanPreset>("servers_only");
  const [scanMode, setScanMode] = useState<DashboardScanMode>("asset_listing_search");
  const [scanDepth, setScanDepth] = useState<ScanDepth>("standard");
  const [scanLane, setScanLane] = useState<ScanLane>("fast");
  const [progress, setProgress] = useState<HardwareScanProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [showQuality, setShowQuality] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("score");
  const [opportunityFilter, setOpportunityFilter] = useState<OpportunityFilter>("current");
  const [resultScope, setResultScope] = useState<ResultScope>("current_scan");
  const [stateFilter, setStateFilter] = useState("all");
  const [selectedOpportunity, setSelectedOpportunity] = useState<HardwareOpportunity | null>(null);
  const [reviewOpportunity, setReviewOpportunity] = useState<HardwareOpportunity | null>(null);
  const [selectedReviewIds, setSelectedReviewIds] = useState<string[]>([]);
  const [telegramOpen, setTelegramOpen] = useState(false);
  const [recheckSummary, setRecheckSummary] = useState<string | null>(null);
  const [manualImportText, setManualImportText] = useState("");

  const activeJobId = job?.id ?? dashboard?.latest_job?.id;
  const allKnownOpportunities = useMemo(
    () => uniqueOpportunities([
      ...(dashboard?.top_opportunities ?? []),
      ...(dashboard?.history_opportunities ?? []),
      ...(dashboard?.needs_review_opportunities ?? []),
      ...(dashboard?.latest_job?.opportunities ?? []),
      ...(job?.opportunities ?? []),
    ]),
    [dashboard?.history_opportunities, dashboard?.latest_job?.opportunities, dashboard?.needs_review_opportunities, dashboard?.top_opportunities, job?.opportunities],
  );
  const latestJob = job ?? dashboard?.latest_job ?? null;
  const latestJobId = latestJob?.id ?? null;
  const availableStateFilters = useMemo(
    () => buildStateFilters(allKnownOpportunities, latestJob?.states ?? selectedStates),
    [allKnownOpportunities, latestJob?.states, selectedStates],
  );
  const scopedOpportunities = useMemo(
    () => getScopedOpportunities(allKnownOpportunities, resultScope, latestJobId, stateFilter, selectedStates, latestJob?.opportunities ?? []),
    [allKnownOpportunities, latestJobId, latestJob?.opportunities, resultScope, selectedStates, stateFilter],
  );
  const currentOpportunities = useMemo(() => getCurrentOpportunities(scopedOpportunities), [scopedOpportunities]);
  const allNeedsReviewOpportunities = useMemo(() => getNeedsReviewOpportunities(allKnownOpportunities), [allKnownOpportunities]);
  const allHistoryOpportunities = useMemo(() => getHistoryOpportunities(allKnownOpportunities), [allKnownOpportunities]);
  const needsReviewOpportunities = allNeedsReviewOpportunities;
  const historyOpportunities = allHistoryOpportunities;
  const sourceRuns = progress?.worker_runs ?? job?.source_runs ?? dashboard?.latest_job?.source_runs ?? [];
  const report = job?.report ?? dashboard?.latest_job?.report;
  const stats = job?.quality_stats ?? dashboard?.latest_job?.quality_stats;
  const scheduler = dashboard?.scheduler;
  const filterExplanation = useMemo(
    () => buildFilterExplanation(latestJob, stats),
    [latestJob, stats],
  );

  useEffect(() => {
    void refreshDashboard();
  }, []);

  useEffect(() => {
    if (!activeJobId || isTerminalJobStatus(job?.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const latestProgress = await getHardwareScanProgress(activeJobId);
        setProgress(latestProgress);
      } catch {
        // Progress is best-effort; job polling below remains the source of truth.
      }
      const latest = await getHardwareDailyScanJob(activeJobId);
      setJob(latest);
      if (isTerminalJobStatus(latest.status)) {
        setProgress(null);
        setResultScope("current_scan");
        if (latest.states.length === 1) setStateFilter(latest.states[0]);
        window.clearInterval(timer);
        await refreshDashboard();
      }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [activeJobId, job?.status]);

  const filteredOpportunities = useMemo(
    () => filterOpportunities(opportunityFilter === "needs_review" || opportunityFilter === "history" ? allKnownOpportunities : scopedOpportunities, opportunityFilter, {
      current: currentOpportunities,
      needsReview: needsReviewOpportunities,
      history: historyOpportunities,
    }),
    [allKnownOpportunities, scopedOpportunities, currentOpportunities, historyOpportunities, needsReviewOpportunities, opportunityFilter],
  );
  const sortedOpportunities = useMemo(() => sortOpportunities(filteredOpportunities, sortBy), [filteredOpportunities, sortBy]);
  const sourceSummary = useMemo(() => summarizeSources(sourceRuns), [sourceRuns]);
  const scanProgress = useMemo(() => buildScanProgress(job, progress), [job, progress]);
  const latestJobHealth = useMemo(() => buildLatestJobHealth(latestJob), [latestJob]);
  const coverageLabel = useMemo(
    () => scanScope === "nationwide" ? t("nationwideKeywordScan") : regionStrategy === "all_us" ? t("coverageAllUs").replace("Coverage: ", "").replace("覆盖范围：", "") : selectedStates.join(", "),
    [regionStrategy, scanScope, selectedStates, t],
  );
  const estimatedTasks = useMemo(
    () => estimateTasks(regionStrategy, selectedStates.length, selectedCategories.length, scanDepth, scanLane, scanScope, Boolean(manualImportText.trim())),
    [regionStrategy, scanScope, selectedStates.length, selectedCategories.length, scanDepth, scanLane, manualImportText],
  );
  const automatedSourceCount = scanLane === "fast" ? sourceCount : 0;
  const manualImportTaskCount = manualImportText.trim() ? 1 : 0;
  const activeSourceCount = automatedSourceCount + manualImportTaskCount;
  const runButtonLabel = useMemo(() => {
    if (busy || scanProgress.isScanning) return t("scanning");
    if (job?.status === "cancelled") return t("cancelled");
    if (job?.status === "completed" || job?.status === "partially_completed") return t("completed");
    if (job?.status === "failed") return t("failed");
    return t("runScanNow");
  }, [busy, job?.status, scanProgress.isScanning, t]);
  const auctionEndingCount = useMemo(
    () => currentOpportunities.filter((item) => (item.change_types ?? []).includes("AUCTION_ENDING") || item.listing_status === "ending_soon").length,
    [currentOpportunities],
  );
  const reviewStats = useMemo(() => buildReviewStats(needsReviewOpportunities, historyOpportunities), [historyOpportunities, needsReviewOpportunities]);
  const scopedNewCount = useMemo(
    () => currentOpportunities.filter((item) => (item.change_types ?? []).includes("NEW")).length,
    [currentOpportunities],
  );
  const scopedChangedCount = useMemo(
    () => currentOpportunities.filter((item) => (item.change_types ?? []).some((change) => change !== "NEW")).length,
    [currentOpportunities],
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
      const requestStates = scanScope === "legacy_state" && regionStrategy !== "all_us" ? selectedStates : [];
      const created = await runHardwareDailyScan({
        mode: scanMode,
        categories: selectedCategories,
        states: requestStates,
        scan_scope: scanScope,
        test_run: true,
        max_results_per_query: 3,
        max_queries_per_category: scanDepthQueryCounts[scanDepth],
        scan_depth: scanDepth,
        scan_lane: scanLane,
        send_telegram: false,
        manual_text: manualImportText.trim() || null,
      });
      setJob(created);
      setProgress(null);
      setResultScope("current_scan");
      const requestedStates = requestStates;
      setStateFilter(requestedStates.length === 1 ? requestedStates[0] : "all");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function stopCurrentScan() {
    if (!activeJobId) return;
    setCancelBusy(true);
    setError(null);
    try {
      const cancelled = await cancelHardwareDailyScan(activeJobId);
      setJob(cancelled);
      const latestProgress = await getHardwareScanProgress(activeJobId).catch(() => null);
      setProgress(latestProgress);
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan cancel failed");
    } finally {
      setCancelBusy(false);
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

  async function bulkRecheck() {
    setBusy(true);
    setError(null);
    setRecheckSummary(null);
    try {
      const summary = await recheckHardwareOpportunities(80);
      setRecheckSummary(
        `Rechecked ${summary.checked}: active ${summary.auto_active}, ending soon ${summary.ending_soon}, ended ${summary.auto_ended}, needs review ${summary.needs_manual_review}, conflicting ${summary.conflicting}, errors ${summary.errors}`,
      );
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Listing recheck failed");
    } finally {
      setBusy(false);
    }
  }

  async function recheckSelectedOpportunity(opportunityId: string) {
    setBusy(true);
    setError(null);
    try {
      const updated = await recheckHardwareOpportunity(opportunityId);
      setSelectedOpportunity(updated);
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Opportunity recheck failed");
    } finally {
      setBusy(false);
    }
  }

  async function manualStatus(opportunityId: string, manualStatusValue: string, manualEndTime?: string | null) {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateHardwareOpportunityManualStatus(opportunityId, {
        manual_status: manualStatusValue,
        manual_end_time: manualEndTime || null,
        manual_timezone: "America/Los_Angeles",
        verified_by: "local_user",
      });
      setSelectedOpportunity(updated);
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Manual status update failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveReview(opportunityId: string, payload: ReviewFormPayload) {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateHardwareOpportunityManualStatus(opportunityId, {
        manual_status: payload.manual_status,
        manual_end_time: payload.manual_end_time || null,
        manual_timezone: payload.manual_timezone || "America/Los_Angeles",
        manual_quantity: nullableNumber(payload.manual_quantity),
        manual_current_price: nullableNumber(payload.manual_current_price),
        manual_total_price: nullableNumber(payload.manual_total_price),
        manual_location: payload.manual_location || null,
        manual_condition: payload.manual_condition || null,
        manual_component_completeness: payload.manual_component_completeness || null,
        review_action: payload.review_action,
        review_notes: payload.review_notes || null,
        manual_notes: payload.review_notes || null,
        verified_by: "local_user",
      });
      setReviewOpportunity(updated);
      setSelectedOpportunity(updated);
      setSelectedReviewIds((current) => current.filter((id) => id !== opportunityId));
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review save failed");
    } finally {
      setBusy(false);
    }
  }

  async function bulkReview(action: "ended" | "unavailable" | "ignored" | "recheck") {
    if (!selectedReviewIds.length) return;
    if (!window.confirm(`Apply ${action} to ${selectedReviewIds.length} records?`)) return;
    setBusy(true);
    setError(null);
    try {
      if (action === "recheck") {
        await bulkReviewHardwareOpportunities({ opportunity_ids: selectedReviewIds, review_action: "recheck", verified_by: "local_user" });
      } else {
        await bulkReviewHardwareOpportunities({
          opportunity_ids: selectedReviewIds,
          review_action: action,
          manual_status: action,
          verified_by: "local_user",
        });
      }
      setSelectedReviewIds([]);
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk review failed");
    } finally {
      setBusy(false);
    }
  }

  function toggleReviewSelection(id: string) {
    setSelectedReviewIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
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
            <div className="section-label">{t("hardwareV2")}</div>
            <h1 className="dashboard-title">{t("retiredItScan")}</h1>
          </div>
          <label className="field compact-field preset-field">
            <span>{t("scanPreset")}</span>
            <select className="select" value={scanPreset} onChange={(event) => applyPreset(event.target.value as ScanPreset)}>
              <option value="full_hardware_scan">{t("fullHardwareScan")}</option>
              <option value="servers_only">{t("serversOnly")}</option>
              <option value="gpu_memory">{t("gpuMemory")}</option>
              <option value="government_auctions">{t("governmentAuctions")}</option>
              <option value="data_center_decommissioning">{t("dataCenterDecommissioning")}</option>
              <option value="supplier_discovery">{t("supplierDiscovery")}</option>
              <option value="custom">{t("custom")}</option>
            </select>
          </label>
        </div>

        <div className="scan-config-row">
          <label className="field compact-field">
            <span>{t("scanScope")}</span>
            <select className="select" value={scanScope} onChange={(event) => { setScanScope(event.target.value as ScanScope); setScanPreset("custom"); }}>
              <option value="nationwide">{t("nationwideKeywordScan")}</option>
              <option value="legacy_state">{t("legacyStateScan")}</option>
            </select>
            <small className="strategy-help">
              {scanScope === "nationwide" ? t("locationFilterOnly") : regionStrategyDescription(regionStrategy, t)}
            </small>
          </label>

          {scanScope === "legacy_state" ? (
          <label className="field compact-field">
            <span>{t("regionStrategy")}</span>
            <select className="select" value={regionStrategy} onChange={(event) => { setRegionStrategy(event.target.value as RegionStrategy); setScanPreset("custom"); }}>
              {(["all_us", "priority_states", "rotating_states", "custom_states"] as RegionStrategy[]).map((value) => (
                <option value={value} key={value}>{regionStrategyLabel(value, t)}</option>
              ))}
            </select>
            <small className="strategy-help">{regionStrategyDescription(regionStrategy, t)}</small>
          </label>
          ) : null}

          {scanScope === "legacy_state" ? (
          <div className="field compact-field state-picker">
            <span>{t("states")}</span>
            {regionStrategy === "all_us" ? (
              <div className="coverage-banner">{t("coverageAllUs")}</div>
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
                    placeholder={t("addState")}
                  />
                  <button className="button secondary compact-button" onClick={addState}>{t("add")}</button>
                </div>
                <div className="mini-actions">
                  <button onClick={() => { setSelectedStates(allStateCodes); setScanPreset("custom"); }}>{t("selectAll")}</button>
                  <button onClick={() => { setSelectedStates([]); setScanPreset("custom"); }}>{t("clearAll")}</button>
                </div>
              </>
            )}
          </div>
          ) : null}

          <label className="field compact-field">
            <span>{t("scanMode")}</span>
            <select className="select" value={scanMode} onChange={(event) => { setScanMode(event.target.value as DashboardScanMode); setScanPreset("custom"); }}>
              {(["asset_listing_search", "supplier_lead_search", "both"] as DashboardScanMode[]).map((value) => (
                <option value={value} key={value}>{scanModeLabel(value, t)}</option>
              ))}
            </select>
          </label>

          <div className="field compact-field categories-field">
            <span>{t("categories")}</span>
            <div className="compact-category-row single-line">
              {categories.map((category) => (
                <label className="compact-check" key={category}>
                  <input
                    type="checkbox"
                    checked={selectedCategories.includes(category)}
                    onChange={() => { toggleCategory(category); setScanPreset("custom"); }}
                  />
                  {categoryLabel(category, t)}
                </label>
              ))}
            </div>
            <div className="mini-actions">
              <button onClick={() => { setSelectedCategories(categories); setScanPreset("custom"); }}>{t("selectAll")}</button>
              <button onClick={() => { setSelectedCategories([]); setScanPreset("custom"); }}>{t("clear")}</button>
            </div>
          </div>

          <label className="field compact-field">
            <span>{t("scanDepth")}</span>
            <select className="select" value={scanDepth} onChange={(event) => { setScanDepth(event.target.value as ScanDepth); setScanPreset("custom"); }}>
              <option value="quick">{t("quick")}</option>
              <option value="standard">{t("standard")}</option>
              <option value="deep">{t("deep")}</option>
            </select>
          </label>

          <label className="field compact-field">
            <span>Scan Lane</span>
            <select className="select" value={scanLane} onChange={(event) => setScanLane(event.target.value as ScanLane)}>
              <option value="fast">Fast Scan</option>
              <option value="deep">Deep Scan planned</option>
            </select>
            <small className="strategy-help">
              {scanLane === "fast" ? "Runs GovDeals, Public Surplus, and Municibid now." : "Shows planned deep sources without fabricating results."}
            </small>
          </label>
        </div>

        <div className="manual-import-row">
          <label className="field compact-field">
            <span>{t("manualImport")}</span>
            <textarea
              className="textarea compact-textarea"
              value={manualImportText}
              onChange={(event) => setManualImportText(event.target.value)}
              placeholder={t("manualImportPlaceholder")}
            />
            <small className="strategy-help">{t("manualImportHelp")}</small>
          </label>
        </div>

        <div className="scan-action-row">
          <div className="scan-action-main">
            <button className="button gold run-scan-button" onClick={startScan} disabled={busy || scanProgress.isScanning || selectedCategories.length === 0}>
              {busy || scanProgress.isScanning ? <Loader2 size={17} className="spin" /> : <Play size={17} />}
              {runButtonLabel}
            </button>
            {scanProgress.isScanning ? (
              <button className="button secondary" onClick={stopCurrentScan} disabled={cancelBusy}>
                {cancelBusy ? <Loader2 size={17} className="spin" /> : <Pause size={17} />}
                {cancelBusy ? t("stoppingScan") : t("stopCurrentScan")}
              </button>
            ) : null}
            <button className="button secondary" onClick={refreshDashboard} disabled={busy}>
              <RefreshCw size={17} />
              {t("refresh")}
            </button>
            <button className="button secondary" onClick={bulkRecheck} disabled={busy}>
              {t("recheckListings")}
            </button>
            <div className="scan-summary">
              {coverageLabel || t("noData")} · {selectedCategories.length} {t("categories")} · {activeSourceCount} {t("sources")} · {estimatedTasks} {t("tasks")}
            </div>
            <div className="scan-summary">
              {t("queryPreview")}: {automatedSourceCount} {t("sources")} × {selectedCategories.length} {t("categories")} × up to {scanDepthQueryCounts[scanDepth]} keywords{manualImportTaskCount ? ` + ${t("manualImport")}` : ""} = {estimatedTasks} {t("tasks")}
              {estimatedTasks >= 100 ? ` · ${t("largeScanWarning")}` : ""}
            </div>
            {scanProgress.isScanning ? (
              <div className="scan-progress">
                <span>{scanProgress.completed}/{scanProgress.total} {t("tasks")}</span>
                <span>{scanProgress.currentCategory} · {scanProgress.currentSource}</span>
                <span>Workers {scanProgress.runningWorkers} running · {scanProgress.cacheHits} cache hits</span>
                <span>{scanProgress.elapsed}</span>
              </div>
            ) : null}
          </div>

          <div className="status-card-row">
            <div className="mini-status-card">
              <div className="section-label">{t("scheduler")}</div>
              <strong>{scheduler?.enabled && scheduler?.status === "running" ? t("running") : t("paused")}</strong>
              <span>{t("schedulerEnabled")}: {scheduler?.enabled ? t("yes") : t("no")}</span>
              <span>{t("currentScanRunning")}: {scheduler?.is_job_running || scanProgress.isScanning ? t("yes") : t("idle")}</span>
              {latestJobHealth.isStale || scheduler?.last_error ? (
                <span className={latestJobHealth.isStale ? "danger-text" : "warning-text"}>
                  {t("interruptedTask")}: {latestJobHealth.isStale ? t("yes") : scheduler?.last_error}
                </span>
              ) : null}
              <span>{t("last")}: {scheduler?.last_run_at ? new Date(scheduler.last_run_at).toLocaleString() : t("none")}</span>
              <span>{t("next")}: {scheduler?.next_run_at ? new Date(scheduler.next_run_at).toLocaleString() : t("paused")}</span>
              <div>
                {scheduler?.status === "running" ? (
                  <button className="button secondary compact-button" onClick={() => setScheduler("pause")} disabled={busy}><Pause size={14} /> {t("pause")}</button>
                ) : (
                  <button className="button secondary compact-button" onClick={() => setScheduler("resume")} disabled={busy}><Play size={14} /> {t("resume")}</button>
                )}
              </div>
            </div>
            <div className="mini-status-card">
              <div className="section-label">{t("persistence")}</div>
              <strong>{dashboard?.persistence_mode ?? "memory_fallback"} · {databaseHealthLabel(dashboard)}</strong>
              <span>{t("databaseConfigured")}: {dashboard?.database_url_configured ? t("yes") : t("no")}</span>
              <span>{t("storedOpportunities")}: {dashboard?.stored_opportunities ?? 0}</span>
              <span>{t("storedHistoryFlags")}: {dashboard?.stored_history_records ?? 0}</span>
              <span>{t("storedReviewFlags")}: {dashboard?.stored_needs_review_records ?? 0}</span>
              <span>{t("lastWrite")}: {dashboard?.last_successful_database_write ? new Date(dashboard.last_successful_database_write).toLocaleString() : t("none")}</span>
              <span>{t("migration")}: {dashboard?.migration_version ?? t("unknown")}</span>
            </div>
            <div className="mini-status-card">
              <div className="section-label">{t("latestJobHealth")}</div>
              <strong>{latestJob?.status ?? t("none")}</strong>
              <span>{t("scanJob")}: {latestJobId ?? t("none")}</span>
              <span>
                {t("sourceRuns")}: {latestJobHealth.total} · {t("completedRuns")}: {latestJobHealth.completed} · {t("searchingRuns")}: {latestJobHealth.searching} · {t("failedRuns")}: {latestJobHealth.failed}
              </span>
              <span>{t("opportunitiesFound")}: {latestJobHealth.opportunitiesFound}</span>
              <span className={latestJobHealth.isStale ? "danger-text" : undefined}>{t("staleJob")}: {latestJobHealth.isStale ? t("yes") : t("no")}</span>
            </div>
            <div className="mini-status-card">
              <div className="section-label">{t("telegram")}</div>
              <strong>{telegramStatus(dashboard, t)}</strong>
              <span>{t("lastDelivery")}: {report?.delivery_log?.status ?? t("none")}</span>
              <div>
                <button className="button secondary compact-button" onClick={() => setActiveTab("telegram reports")}>{t("configure")}</button>
                <button className="button secondary compact-button" onClick={() => generateReport("test")} disabled={busy || !activeJobId}><Send size={14} /> {t("test")}</button>
              </div>
            </div>
          </div>
        </div>
        {error ? <p className="danger-text">{error}</p> : null}
        {dashboard?.persistence_warning ? <p className="warning-text">{dashboard.persistence_warning}</p> : null}
        {recheckSummary ? <p className="muted">{recheckSummary}</p> : null}
      </section>

      <section className="panel compact-panel">
        <div className="panel-head">
          <div>
            <div className="section-label">{t("resultScope")}</div>
            <h2>{resultScopeTitle(resultScope, t)}</h2>
            <p className="muted">
              {resultScope === "current_scan"
                ? `${t("scanJob")}: ${latestJobId ?? t("none")} · ${t("scanScopeLabel")}: ${latestJob?.scan_scope === "legacy_state" ? t("legacyStateScan") : t("nationwideKeywordScan")} · ${t("sourcesScanned")}: ${uniqueSourceCount(latestJob?.source_runs ?? [])} · ${t("keywordsScanned")}: ${latestJob?.generated_queries?.filter((query) => query.status !== "planned").length ?? 0} · ${t("lastScanTime")}: ${latestJob?.created_at ? new Date(latestJob.created_at).toLocaleString() : t("none")}`
                : resultScope === "all_current"
                  ? t("showingAllCurrent")
                  : t("showingSelectedStates")}
            </p>
          </div>
          <div className="dashboard-actions no-margin">
            <button
              className={`button secondary ${resultScope === "current_scan" ? "active" : ""}`}
              onClick={() => {
                setResultScope("current_scan");
              }}
            >
              {t("currentScan")}
            </button>
            <button
              className={`button secondary ${resultScope === "all_current" ? "active" : ""}`}
              onClick={() => {
                setResultScope("all_current");
                setStateFilter("all");
              }}
            >
              {t("allCurrent")}
            </button>
            <button
              className={`button secondary ${resultScope === "selected_states" ? "active" : ""}`}
              onClick={() => {
                setResultScope("selected_states");
                setStateFilter("all");
              }}
            >
              {t("selectedStates")}
            </button>
            <label className="field compact-field sort-field">
              <span>{t("stateFilter")}</span>
              <select className="select" value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
                <option value="all">{t("allStates")}</option>
                {availableStateFilters.map((state) => (
                  <option value={state} key={state}>{state}</option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </section>

      <section className="metric-grid dashboard-metrics">
        <Metric label={t("finalOpportunities")} value={currentOpportunities.length} />
        <Metric label={t("new")} value={scopedNewCount} />
        <Metric label={t("changed")} value={scopedChangedCount} />
        <Metric label={t("auctionEnding")} value={auctionEndingCount} />
        <Metric label={t("needsReview")} value={needsReviewOpportunities.length} />
        <Metric label={t("history")} value={historyOpportunities.length} />
        <Metric label={t("failedSources")} value={stats?.failed_sources ?? sourceSummary.failed} tone={sourceSummary.failed ? "danger" : "normal"} />
      </section>

      <nav className="dashboard-tabs">
        {tabs.map((tab) => (
          <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            {tabLabel(tab, t)}
          </button>
        ))}
      </nav>

      {activeTab === "overview" ? (
        <div className="dashboard-overview">
          <section className="panel compact-panel">
            <div className="panel-head">
              <div>
                <div className="section-label">{t("topOpportunities")}</div>
                <h2>{resultScopeTitle(resultScope, t)}</h2>
                <p className="muted">{Math.min(currentOpportunities.length, 12)} / {currentOpportunities.length} {t("current")}</p>
              </div>
              <button className="button secondary" onClick={() => setActiveTab("opportunities")}>
                {t("viewAll")}
              </button>
            </div>
            <OpportunityTable
              opportunities={sortOpportunities(currentOpportunities, sortBy).slice(0, 12)}
              onView={setSelectedOpportunity}
              emptyMessage={emptyOpportunityMessage(resultScope, latestJob?.states ?? [], stateFilter)}
              t={t}
              compact
            />
            {filterExplanation ? <FilterExplanationCard explanation={filterExplanation} /> : null}
          </section>

          <section className="panel compact-panel">
            <div className="panel-head">
              <div>
                <div className="section-label">{t("sourceRuns")}</div>
                <h2>
                  {sourceSummary.successful} / {sourceSummary.zero} / {sourceSummary.failed} · {t("sourceSummary")}
                </h2>
              </div>
              <button className="button secondary" onClick={() => setShowSources((value) => !value)}>
                {showSources ? t("collapseSourceRuns") : t("viewSourceRuns")}
              </button>
            </div>
          {showSources ? (
            <>
              <SourceQualitySummary sourceRuns={sourceRuns} t={t} />
              <SourceHealthTable sourceHealth={dashboard?.source_health ?? []} />
              <SourceRunsTable sourceRuns={sourceRuns} t={t} />
            </>
          ) : null}
          </section>

          <section className="panel compact-panel">
            <div className="panel-head">
              <div>
                <div className="section-label">{t("qualityDetails")}</div>
                <h2>{stats?.raw_results ?? 0} {t("raw")} / {stats?.specific_listings ?? 0} {t("specific")} / {stats?.duplicates_removed ?? 0} {t("duplicate")}</h2>
              </div>
              <button className="button secondary" onClick={() => setShowQuality((value) => !value)}>
                {showQuality ? t("hideQualityDetails") : t("qualityDetails")}
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
              <div className="section-label">{t("opportunities")}</div>
              <h2>{sortedOpportunities.length} {opportunityFilter === "history" ? t("historyRecords") : t("formalSpecificListings")}</h2>
            </div>
            <label className="field compact-field sort-field">
              <span>{t("sort")}</span>
              <select className="select" value={sortBy} onChange={(event) => setSortBy(event.target.value as SortBy)}>
                <option value="score">{t("score")}</option>
                <option value="newest">{t("newest")}</option>
                <option value="price">{t("price")}</option>
                <option value="auction">{t("endTime")}</option>
                <option value="risk">{t("risk")}</option>
              </select>
            </label>
            <label className="field compact-field sort-field">
              <span>{t("filter")}</span>
              <select className="select" value={opportunityFilter} onChange={(event) => setOpportunityFilter(event.target.value as OpportunityFilter)}>
                <option value="current">{t("current")}</option>
                <option value="active">{t("active")}</option>
                <option value="ending_soon">{t("endingSoon")}</option>
                <option value="needs_review">{t("needsReview")}</option>
                <option value="history">{t("history")}</option>
                <option value="missing_components">{t("missingComponents")}</option>
                <option value="pickup_only">{t("pickupOnly")}</option>
              </select>
            </label>
          </div>
          <OpportunityTable
            opportunities={sortedOpportunities}
            onView={setSelectedOpportunity}
            emptyMessage={emptyOpportunityMessage(resultScope, latestJob?.states ?? [], stateFilter)}
            t={t}
          />
        </section>
      ) : null}

      {activeTab === "needs review" ? (
        <section className="panel compact-panel">
          <div className="panel-head">
            <div>
              <div className="section-label">{t("needsReview")} / Needs Review</div>
              <h2>{reviewStats.total} {t("requiresReview")}</h2>
              <p className="muted">
                {t("reviewedToday")}: {reviewStats.reviewedToday} · {t("remaining")}: {reviewStats.remaining} · {t("blocked")}: {reviewStats.blocked} · {t("unknownEndTime")}: {reviewStats.unknownEndTime} · {t("ignored")}: {reviewStats.ignored}
              </p>
            </div>
            <div className="dashboard-actions no-margin">
              <button className="button secondary" disabled={busy || !selectedReviewIds.length} onClick={() => bulkReview("recheck")}>{t("recheckNow")}</button>
              <button className="button secondary" disabled={busy || !selectedReviewIds.length} onClick={() => bulkReview("ended")}>{t("markEnded")}</button>
              <button className="button secondary" disabled={busy || !selectedReviewIds.length} onClick={() => bulkReview("unavailable")}>{t("markUnavailable")}</button>
              <button className="button secondary" disabled={busy || !selectedReviewIds.length} onClick={() => bulkReview("ignored")}>{t("ignore")}</button>
            </div>
          </div>
          <NeedsReviewTable
            opportunities={needsReviewOpportunities}
            selectedIds={selectedReviewIds}
            onToggle={toggleReviewSelection}
            onReview={setReviewOpportunity}
            t={t}
          />
        </section>
      ) : null}

      {activeTab === "source runs" ? (
        <section className="panel compact-panel">
          <div className="panel-head">
            <div>
              <div className="section-label">{t("sourceRuns")}</div>
              <h2>
                {sourceSummary.successful} / {sourceSummary.zero} / {sourceSummary.failed} · {t("sourceSummary")}
              </h2>
            </div>
            <button className="button secondary" onClick={() => setShowSources((value) => !value)}>
              {showSources ? t("collapseSourceRuns") : t("viewSourceRuns")}
            </button>
          </div>
          {showSources ? (
            <>
              <SourceQualitySummary sourceRuns={sourceRuns} t={t} />
              <SourceHealthTable sourceHealth={dashboard?.source_health ?? []} />
              <SourceRunsTable sourceRuns={sourceRuns} t={t} />
            </>
          ) : <p className="muted">{t("sourceRunsCollapsed")}</p>}
        </section>
      ) : null}

      {activeTab === "telegram reports" ? (
        <section className="panel compact-panel">
          <div className="panel-head">
            <div>
              <div className="section-label">{t("telegramReports")}</div>
              <h2>{t("previewDailyReport")}</h2>
            </div>
            <div className="dashboard-actions no-margin">
              <button className="button secondary" onClick={() => generateReport("preview")} disabled={busy || !activeJobId}>
                <Bell size={17} />
                {t("previewDailyReport")}
              </button>
              <button className="button secondary" onClick={() => generateReport("test")} disabled={busy || !activeJobId}>
                <Send size={17} />
                {t("sendTestMessage")}
              </button>
              <button className="button gold" onClick={() => generateReport("approve_and_send")} disabled={busy || !activeJobId}>
                <Send size={17} />
                {t("approveAndSend")}
              </button>
            </div>
          </div>
          <div className="telegram-summary">
            <StatusPill label="Delivery" value={report?.delivery_log?.status ?? "none"} />
            <StatusPill label="Message ID" value={report?.delivery_log?.telegram_message_id ?? "none"} />
            <button className="button secondary" onClick={() => setTelegramOpen(true)} disabled={!report}>
              {t("openPreview")}
            </button>
          </div>
          {report?.delivery_log?.error_message ? <p className="danger-text">{report.delivery_log.error_message}</p> : null}
        </section>
      ) : null}

      <OpportunityDrawer
        opportunity={selectedOpportunity}
        onClose={() => setSelectedOpportunity(null)}
        onRecheck={recheckSelectedOpportunity}
        onManualStatus={manualStatus}
      />
      <ReviewDrawer
        opportunity={reviewOpportunity}
        onClose={() => setReviewOpportunity(null)}
        onRecheck={recheckSelectedOpportunity}
        onSave={saveReview}
        t={t}
      />
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
  t,
  emptyMessage = "No formal specific listings yet.",
  compact = false,
}: {
  opportunities: HardwareOpportunity[];
  onView: (opportunity: HardwareOpportunity) => void;
  t: (key: string) => string;
  emptyMessage?: string;
  compact?: boolean;
}) {
  const rows = opportunities ?? [];
  if (!rows.length) {
    return <div className="muted empty-state">{emptyMessage}</div>;
  }
  return (
    <div className="table-wrap compact-table-wrap">
      <table className="compact-table opportunity-table">
        <thead>
          <tr>
            <th>{t("score")}</th>
            <th>{t("category")}</th>
            <th>{t("title")}</th>
            <th>{t("model")}</th>
            <th>{t("endTime")}</th>
            <th>{t("timeLeft")}</th>
            <th>{t("quantity")}</th>
            <th>{t("currentPrice")}</th>
            <th>{t("unitCost")}</th>
            <th>{t("location")}</th>
            <th>{t("matchedKeywords")}</th>
            <th>{t("completeness")}</th>
            <th>{t("status")}</th>
            <th>{t("verification")}</th>
            <th>{t("action")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, compact ? 12 : rows.length).map((item, index) => (
            <tr key={stableOpportunityKey(item, index)}>
              <td>
                <span className="score-ring">{item.opportunity_score.toFixed(0)}</span>
              </td>
              <td>{categoryLabel(item.category, t)}</td>
              <td>
                <div className="title-cell">
                  <span>{item.title}</span>
                  <BadgeRow item={item} />
                </div>
              </td>
              <td>{item.model ?? <span className="muted">{t("unknown")}</span>}</td>
              <td>{formatEndTime(item, t)}</td>
              <td>{timeLeftLabel(item, t)}</td>
              <td>{item.quantity ?? <span className="muted">{t("unknown")}</span>}</td>
              <td>{formatMoney(item.current_total_cost ?? item.total_price, t)}</td>
              <td>{formatMoney(item.cost_per_unit ?? item.unit_price, t)}</td>
              <td>{opportunityLocation(item) || <span className="muted">{t("unknown")}</span>}</td>
              <td>{matchedKeywords(item).slice(0, 4).join(", ") || <span className="muted">{t("unknown")}</span>}</td>
              <td><span className="pill">{completenessLabel(item.component_completeness, t)}</span></td>
              <td><span className="pill">{statusLabel(item.listing_status, t)}</span></td>
              <td>{verificationBadge(item, t)}</td>
              <td>
                <button className="button secondary compact-button" onClick={() => onView(item)}>
                  {t("viewDetails")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NeedsReviewTable({
  opportunities,
  selectedIds,
  onToggle,
  onReview,
  t,
}: {
  opportunities: HardwareOpportunity[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  onReview: (opportunity: HardwareOpportunity) => void;
  t: (key: string) => string;
}) {
  if (!opportunities.length) return <div className="muted empty-state">{t("noRecords")}</div>;
  return (
    <div className="table-wrap compact-table-wrap">
      <table className="compact-table opportunity-table">
        <thead>
          <tr>
            <th></th>
            <th>{t("title")}</th>
            <th>{t("source")}</th>
            <th>{t("state")}</th>
            <th>{t("category")}</th>
            <th>{t("reason")}</th>
            <th>{t("endTime")}</th>
            <th>{t("price")}</th>
            <th>{t("quantity")}</th>
            <th>{t("lastChecked")}</th>
            <th>{t("reviewStatus")}</th>
            <th>{t("action")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`review-${stableOpportunityKey(item, index)}`}>
              <td>
                <input type="checkbox" checked={selectedIds.includes(item.opportunity_id)} onChange={() => onToggle(item.opportunity_id)} />
              </td>
              <td>{safeText(item.title, t)}</td>
              <td>{safeText(item.source, t)}</td>
              <td>{safeText(detectedState(item), t)}</td>
              <td>{safeText(item.category, t)}</td>
              <td>{reasonLabel(reviewReason(item), t)}</td>
              <td>{formatEndTime(item, t)}</td>
              <td>{formatMoney(item.final_price ?? item.current_total_cost ?? item.total_price, t)}</td>
              <td>{item.final_quantity ?? item.quantity ?? t("unknown")}</td>
              <td>{formatDate(item.last_checked_at)}</td>
              <td>{statusLabel(item.listing_status, t)}</td>
              <td>
                <button className="button secondary compact-button" onClick={() => onReview(item)}>
                  {t("review")}
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
  const badges = [...(item.change_types ?? []), ...(item.risk_flags ?? [])].slice(0, 4);
  if (!badges.length) return null;
  return (
    <div className="badge-row">
      {badges.map((badge, index) => (
        <span className={`badge ${badge === "NEW" ? "new-badge" : badge.includes("CHANGED") ? "changed-badge" : ""}`} key={`${badge}-${index}`}>
          {badge}
        </span>
      ))}
    </div>
  );
}

function SourceRunsTable({ sourceRuns, t }: { sourceRuns: HardwareSourceRun[]; t: (key: string) => string }) {
  const rows = sourceRuns ?? [];
  return (
    <div className="table-wrap compact-table-wrap">
      <table className="compact-table source-table">
        <thead>
          <tr>
            <th>{t("source")}</th>
            <th>{t("category")}</th>
            <th>{t("state")}</th>
            <th>{t("detectedState")}</th>
            <th>{t("stateMatch")}</th>
            <th>{t("filterReason")}</th>
            <th>{t("queryTemplate")}</th>
            <th>{t("expandedQuery")}</th>
            <th>{t("scanDepth")}</th>
            <th>{t("status")}</th>
            <th>{t("resultCount")}</th>
            <th>{t("specificListingCount")}</th>
            <th>{t("stateStats")}</th>
            <th>{t("zeroResult")}</th>
            <th>{t("duration")}</th>
            <th>{t("error")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((run) => (
            <tr key={run.id}>
              <td>{run.source_name}</td>
              <td>{run.category ? categoryLabel(run.category, t) : "-"}</td>
              <td>{run.state_code ?? run.state_name ?? "-"}</td>
              <td>{(run.detected_states ?? []).join(", ") || "-"}</td>
              <td>{run.state_match_status ?? "-"}</td>
              <td>{run.filter_reason ?? "-"}</td>
              <td className="muted truncate-query" title={run.query_template ?? ""}>{run.query_template ?? "-"}</td>
              <td className="muted truncate-query" title={run.expanded_query ?? run.query ?? ""}>{run.expanded_query ?? run.query ?? "-"}</td>
              <td>{run.scan_depth}</td>
              <td><span className="pill">{run.status}</span></td>
              <td>{run.result_count}</td>
              <td>{run.specific_listing_count ?? 0}</td>
              <td>{run.matched_state_results ?? 0} / {run.state_mismatch_results ?? 0} / {run.location_unknown_results ?? 0}</td>
              <td>{run.result_count === 0 ? run.zero_result_reason ?? "unknown" : "-"}</td>
              <td>{sourceRunDuration(run)}</td>
              <td className="muted truncate-query" title={run.error_message ?? ""}>{run.error_message ?? "-"}</td>
            </tr>
          ))}
          {!rows.length ? <tr><td colSpan={16} className="muted">{t("noRecords")}</td></tr> : null}
        </tbody>
      </table>
    </div>
  );
}

function SourceQualitySummary({ sourceRuns, t }: { sourceRuns: HardwareSourceRun[]; t: (key: string) => string }) {
  const stats = buildSourceQualityStats(sourceRuns);
  if (!stats.length) return null;
  return (
    <div className="quality-strip source-quality-strip">
      {stats.map((item) => (
        <span key={item.source}>
          {item.source}
          <strong>{item.totalQueries} q · {item.queriesWithResults} hit · {item.zeroResultQueries} zero</strong>
          <small>{item.rawResults} raw · {item.specificListings} specific · {Math.round(item.resultRate * 100)}% result · {Math.round(item.specificListingRate * 100)}% specific</small>
        </span>
      ))}
    </div>
  );
}

function SourceHealthTable({ sourceHealth }: { sourceHealth: NonNullable<HardwareDashboard["source_health"]> }) {
  if (!sourceHealth.length) return <p className="muted">Source Quality Report will appear after the next scan.</p>;
  return (
    <div className="table-wrap compact-table-wrap">
      <table className="compact-table source-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Runs</th>
            <th>Success</th>
            <th>Zero</th>
            <th>Timeout</th>
            <th>Failed</th>
            <th>Raw</th>
            <th>State Match</th>
            <th>Mismatch</th>
            <th>Unknown Location</th>
            <th>Specific</th>
            <th>Current</th>
            <th>Needs Review</th>
            <th>Avg Duration</th>
            <th>Health</th>
          </tr>
        </thead>
        <tbody>
          {sourceHealth.map((item) => (
            <tr key={item.source_name}>
              <td>{item.source_name}</td>
              <td>{item.total_runs}</td>
              <td>{item.success_runs}</td>
              <td>{item.zero_result_runs}</td>
              <td>{item.timeout_runs}</td>
              <td>{item.failed_runs}</td>
              <td>{item.raw_results}</td>
              <td>{item.matched_state_results}</td>
              <td>{item.state_mismatch_results}</td>
              <td>{item.location_unknown_results}</td>
              <td>{item.specific_listings}</td>
              <td>{item.current_opportunities}</td>
              <td>{item.needs_review}</td>
              <td>{formatMs(item.avg_duration_ms)}</td>
              <td><span className="pill">{item.health_status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type FilterExplanation = {
  rawResults: number;
  filteredOut: number;
  stateMismatches: number;
  locationUnknown: number;
  needsReview: number;
};

function FilterExplanationCard({ explanation }: { explanation: FilterExplanation }) {
  return (
    <div className="filter-explanation-card">
      <div>
        <strong>Scan completed. No current opportunities matched the selected state filters.</strong>
        <p>扫描已完成，但没有符合当前州筛选的有效机会。</p>
      </div>
      <div className="quality-strip">
        <span>Raw results / 原始结果 <strong>{explanation.rawResults}</strong></span>
        <span>Filtered out / 已过滤 <strong>{explanation.filteredOut}</strong></span>
        <span>State mismatches / 州不匹配 <strong>{explanation.stateMismatches}</strong></span>
        <span>Location unknown / 地点未知 <strong>{explanation.locationUnknown}</strong></span>
        <span>Needs review / 待核查 <strong>{explanation.needsReview}</strong></span>
      </div>
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
    ["State Match", stats?.matched_state_results ?? 0],
    ["State Mismatch", stats?.state_mismatch_results ?? 0],
    ["Location Unknown", stats?.location_unknown_results ?? 0],
    ["Filtered Out", stats?.filtered_out_results ?? 0],
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

function buildFilterExplanation(job: HardwareScanJob | null, stats: HardwareScanJob["quality_stats"] | undefined): FilterExplanation | null {
  if (!job || !stats) return null;
  if (!["completed", "partially_completed"].includes(job.status)) return null;
  if ((stats.raw_results ?? 0) <= 0) return null;
  if ((stats.final_opportunities ?? 0) > 0) return null;
  const filteredOut = stats.filtered_out_results ?? 0;
  const stateMismatches = stats.state_mismatch_results ?? 0;
  const locationUnknown = stats.location_unknown_results ?? 0;
  const needsReview = stats.needs_manual_review ?? 0;
  if (filteredOut + stateMismatches + locationUnknown + needsReview <= 0) return null;
  return {
    rawResults: stats.raw_results ?? 0,
    filteredOut,
    stateMismatches,
    locationUnknown,
    needsReview,
  };
}

function buildSourceQualityStats(sourceRuns: HardwareSourceRun[]) {
  const bySource = new Map<string, {
    source: string;
    totalQueries: number;
    queriesWithResults: number;
    zeroResultQueries: number;
    rawResults: number;
    specificListings: number;
    currentOpportunities: number;
    needsReview: number;
    history: number;
    resultRate: number;
    specificListingRate: number;
  }>();
  for (const run of sourceRuns) {
    const item = bySource.get(run.source_name) ?? {
      source: run.source_name,
      totalQueries: 0,
      queriesWithResults: 0,
      zeroResultQueries: 0,
      rawResults: 0,
      specificListings: 0,
      currentOpportunities: 0,
      needsReview: 0,
      history: 0,
      resultRate: 0,
      specificListingRate: 0,
    };
    item.totalQueries += 1;
    item.rawResults += run.result_count;
    item.specificListings += run.specific_listing_count ?? 0;
    if (run.result_count > 0) item.queriesWithResults += 1;
    else item.zeroResultQueries += 1;
    item.resultRate = item.totalQueries ? item.queriesWithResults / item.totalQueries : 0;
    item.specificListingRate = item.rawResults ? item.specificListings / item.rawResults : 0;
    bySource.set(run.source_name, item);
  }
  return [...bySource.values()].sort((a, b) => a.source.localeCompare(b.source));
}

function uniqueSourceCount(sourceRuns: HardwareSourceRun[]) {
  return new Set(sourceRuns.filter((run) => run.status !== "planned").map((run) => run.source_name)).size;
}

function OpportunityDrawer({
  opportunity,
  onClose,
  onRecheck,
  onManualStatus,
}: {
  opportunity: HardwareOpportunity | null;
  onClose: () => void;
  onRecheck: (opportunityId: string) => void;
  onManualStatus: (opportunityId: string, status: string, manualEndTime?: string | null) => void;
}) {
  if (!opportunity) return null;
  const missingFields = fieldsNeedingVerification(opportunity);
  const recommendationReasons = opportunity.recommendation_reasons ?? [];
  const riskFlags = opportunity.risk_flags ?? [];
  const changeTypes = opportunity.change_types ?? [];
  const badgeCount = recommendationReasons.length + riskFlags.length + changeTypes.length;
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
            <StatusPill label="Verification" value={opportunity.end_time_verification ?? "unknown"} />
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
            <Detail label="Location" value={opportunityLocation(opportunity)} />
            <Detail label="Discovery Source" value={rawDataString(opportunity, "discovery_source")} />
            <Detail label="Original Source" value={rawDataString(opportunity, "original_source_platform")} />
            <Detail label="Verification Status" value={rawDataString(opportunity, "verification_status")} />
            <Detail label="Last Verified At" value={formatDate(rawDataString(opportunity, "last_verified_at"))} />
            <Detail label="Matched Keywords" value={matchedKeywords(opportunity).join(", ")} />
            <Detail label="End Time" value={formatEndTime(opportunity)} />
            <Detail label="User Time" value={formatDate(opportunity.end_time_user_timezone)} />
            <Detail label="Time Left" value={opportunity.time_remaining} />
            <Detail label="End Raw" value={opportunity.end_time_raw} />
            <Detail label="Timezone" value={opportunity.timezone_needs_verification ? "needs verification" : opportunity.end_time_timezone_raw} />
            <Detail label="Next Recheck" value={formatDate(opportunity.next_status_check_at)} />
            <Detail label="Pickup / Shipping" value={pickupShipping(opportunity)} />
            <Detail label="Last Checked" value={formatDate(opportunity.last_checked_at)} />
          </div>
          <p className="muted">
            Fields needing verification: {missingFields.length ? missingFields.join(", ") : "none"}
          </p>
          {badgeCount ? (
            <div className="badge-row">
              {recommendationReasons.map((reason, index) => <span className="badge changed-badge" key={`reason-${reason}-${index}`}>{reason}</span>)}
              {riskFlags.map((flag, index) => <span className="badge" key={`risk-${flag}-${index}`}>{flag}</span>)}
              {changeTypes.map((change, index) => <span className="badge new-badge" key={`change-${change}-${index}`}>{change}</span>)}
            </div>
          ) : (
            <p className="muted">No additional flags</p>
          )}
          {opportunity.unavailable_reason ? <p className="danger-text">Unavailable reason: {opportunity.unavailable_reason}</p> : null}
          <p className="muted">
            Status reason: {opportunity.status_check_result || opportunity.unavailable_reason || "No status note"}
          </p>
          <div className="drawer-url">
            <span className="section-label">Canonical URL</span>
            <p>{opportunity.canonical_url ?? opportunity.source_url}</p>
            {rawDataString(opportunity, "govauctions_url") ? (
              <p className="muted">Discovery URL: {rawDataString(opportunity, "govauctions_url")}</p>
            ) : null}
          </div>
          <div className="actions">
            <button className="button secondary" type="button" onClick={() => onRecheck(opportunity.opportunity_id)}>
              <RefreshCw size={16} />
              Recheck Now
            </button>
            <a className="button gold" href={opportunity.source_url} target="_blank">
              <ExternalLink size={16} />
              Open Original Link
            </a>
          </div>
          <div className="actions">
            <button className="button secondary" type="button" onClick={() => onManualStatus(opportunity.opportunity_id, "active")}>Mark Still Active</button>
            <button className="button secondary" type="button" onClick={() => onManualStatus(opportunity.opportunity_id, "ended")}>Mark Ended</button>
            <button className="button secondary" type="button" onClick={() => onManualStatus(opportunity.opportunity_id, "sold")}>Mark Sold</button>
            <button className="button secondary" type="button" onClick={() => onManualStatus(opportunity.opportunity_id, "unavailable")}>Mark Unavailable</button>
          </div>
          <div className="actions">
            <button
              className="button secondary"
              type="button"
              onClick={() => {
                const value = window.prompt("Enter end time in ISO format, e.g. 2026-06-29T20:00:00-05:00");
                if (value) onManualStatus(opportunity.opportunity_id, "active", value);
              }}
            >
              Enter End Time
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function ReviewDrawer({
  opportunity,
  onClose,
  onRecheck,
  onSave,
  t,
}: {
  opportunity: HardwareOpportunity | null;
  onClose: () => void;
  onRecheck: (opportunityId: string) => void;
  onSave: (opportunityId: string, payload: ReviewFormPayload) => void;
  t: (key: string) => string;
}) {
  const [form, setForm] = useState<ReviewFormPayload>(emptyReviewForm());

  useEffect(() => {
    if (!opportunity) return;
    setForm({
      manual_status: opportunity.manual_status ?? opportunity.listing_status ?? "needs_manual_review",
      review_action: opportunity.review_action ?? "save_review",
      manual_quantity: stringValue(opportunity.manual_quantity ?? opportunity.quantity),
      manual_current_price: stringValue(opportunity.manual_current_price ?? opportunity.current_price),
      manual_total_price: stringValue(opportunity.manual_total_price ?? opportunity.total_price),
      manual_end_time: toLocalInputValue(opportunity.manual_end_time ?? opportunity.end_time_utc ?? opportunity.auction_end_time),
      manual_timezone: opportunity.manual_timezone ?? "America/Los_Angeles",
      manual_location: opportunity.manual_location ?? [opportunity.location_city, opportunity.location_state].filter(Boolean).join(", "),
      manual_condition: opportunity.manual_condition ?? opportunity.condition ?? "",
      manual_component_completeness: opportunity.manual_component_completeness ?? opportunity.component_completeness ?? "unknown",
      review_notes: opportunity.review_notes ?? opportunity.manual_notes ?? "",
    });
  }, [opportunity]);

  if (!opportunity) return null;
  const missingFields = fieldsNeedingVerification(opportunity);
  const update = (field: keyof ReviewFormPayload, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const quickSave = (status: string, action: string) => {
    onSave(opportunity.opportunity_id, { ...form, manual_status: status, review_action: action });
  };
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <DrawerHeader title={`${t("needsReview")} / Review`} onClose={onClose} />
        <div className="drawer-body">
          <h2>{safeText(opportunity.raw_title || opportunity.title, t)}</h2>
          <p className="muted">{safeText(opportunity.raw_description, t)}</p>
          <div className="drawer-score-row">
            <StatusPill label={t("source")} value={safeText(opportunity.source, t)} />
            <StatusPill label="Listing ID" value={safeText(opportunity.source_listing_id ?? opportunity.lot_number, t)} />
            <StatusPill label="Auto Status" value={statusLabel(opportunity.listing_status, t)} />
            <StatusPill label={t("reason")} value={reasonLabel(reviewReason(opportunity), t)} />
          </div>
          <div className="detail-compact-grid">
            <Detail label="Automated End Time" value={formatEndTime(opportunity)} />
            <Detail label="Automated Price" value={formatMoney(opportunity.current_total_cost ?? opportunity.total_price)} />
            <Detail label="Automated Quantity" value={opportunity.quantity} />
            <Detail label={t("lastChecked")} value={formatDate(opportunity.last_checked_at)} />
            <Detail label="Risk" value={(opportunity.risk_flags ?? []).join(", ")} />
            <Detail label="Missing" value={missingFields.join(", ")} />
          </div>

          <div className="review-form-grid">
            <label className="field compact-field">
              <span>Manual Status</span>
              <select className="select" value={form.manual_status} onChange={(event) => update("manual_status", event.target.value)}>
                <option value="needs_manual_review">{t("requiresReview")}</option>
                <option value="active">{t("markActive")}</option>
                <option value="ending_soon">{t("markEndingSoon")}</option>
                <option value="ended">{t("markEnded")}</option>
                <option value="sold">{t("markSold")}</option>
                <option value="unavailable">{t("markUnavailable")}</option>
                <option value="ignored">{t("ignore")}</option>
              </select>
            </label>
            <label className="field compact-field"><span>{t("quantity")}</span><input value={form.manual_quantity} onChange={(event) => update("manual_quantity", event.target.value)} /></label>
            <label className="field compact-field"><span>Current Price</span><input value={form.manual_current_price} onChange={(event) => update("manual_current_price", event.target.value)} /></label>
            <label className="field compact-field"><span>Total Price</span><input value={form.manual_total_price} onChange={(event) => update("manual_total_price", event.target.value)} /></label>
            <label className="field compact-field"><span>End Time</span><input type="datetime-local" value={form.manual_end_time} onChange={(event) => update("manual_end_time", event.target.value)} /></label>
            <label className="field compact-field"><span>Timezone</span><input value={form.manual_timezone} onChange={(event) => update("manual_timezone", event.target.value)} /></label>
            <label className="field compact-field"><span>Location</span><input value={form.manual_location} onChange={(event) => update("manual_location", event.target.value)} /></label>
            <label className="field compact-field"><span>Condition</span><input value={form.manual_condition} onChange={(event) => update("manual_condition", event.target.value)} /></label>
            <label className="field compact-field">
              <span>Completeness</span>
              <select className="select" value={form.manual_component_completeness} onChange={(event) => update("manual_component_completeness", event.target.value)}>
                {["complete", "mostly_complete", "missing_storage", "missing_memory", "missing_cpu", "missing_psu", "barebone", "mixed_lot", "unknown"].map((value) => (
                  <option value={value} key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="field compact-field review-notes-field">
              <span>{t("reviewNotes")}</span>
              <textarea value={form.review_notes} onChange={(event) => update("review_notes", event.target.value)} />
            </label>
          </div>

          <div className="actions">
            <a className="button gold" href={opportunity.source_url} target="_blank"><ExternalLink size={16} />{t("openOriginalLink")}</a>
            <button className="button secondary" type="button" onClick={() => onRecheck(opportunity.opportunity_id)}><RefreshCw size={16} />{t("recheckNow")}</button>
          </div>
          <div className="actions">
            <button className="button secondary" type="button" onClick={() => quickSave("active", "mark_active")}>{t("markActive")}</button>
            <button className="button secondary" type="button" onClick={() => quickSave("ending_soon", "mark_ending_soon")}>{t("markEndingSoon")}</button>
            <button className="button secondary" type="button" onClick={() => quickSave("ended", "mark_ended")}>{t("markEnded")}</button>
            <button className="button secondary" type="button" onClick={() => quickSave("sold", "mark_sold")}>{t("markSold")}</button>
            <button className="button secondary" type="button" onClick={() => quickSave("unavailable", "mark_unavailable")}>{t("markUnavailable")}</button>
            <button className="button secondary" type="button" onClick={() => quickSave("ignored", "ignore")}>{t("ignore")}</button>
            <button className="button gold" type="button" onClick={() => onSave(opportunity.opportunity_id, { ...form, review_action: "save_review" })}>{t("saveReview")}</button>
          </div>
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
      <strong>{value || <span className="muted">Unknown</span>}</strong>
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

function uniqueOpportunities(opportunities: HardwareOpportunity[]) {
  const seen = new Set<string>();
  const output: HardwareOpportunity[] = [];
  for (const item of opportunities) {
    const key = normalizeOpportunityUrl(item.canonical_url ?? item.source_url) || item.opportunity_id || item.title;
    if (seen.has(key)) continue;
    seen.add(key);
    output.push(item);
  }
  return output;
}

function getScopedOpportunities(
  opportunities: HardwareOpportunity[],
  scope: ResultScope,
  latestJobId: string | null,
  stateFilter: string,
  selectedStateCodes: string[],
  jobOpportunities: HardwareOpportunity[],
) {
  const jobOpportunityIds = new Set(jobOpportunities.map((item) => item.opportunity_id));
  let scoped = opportunities;
  if (scope === "current_scan") {
    scoped = jobOpportunities.length
      ? jobOpportunities
      : latestJobId
      ? opportunities.filter((item) => isOpportunityFromJob(item, latestJobId, jobOpportunityIds))
      : [];
  } else if (scope === "all_current") {
    scoped = getCurrentOpportunities(opportunities);
  } else if (scope === "selected_states" && stateFilter === "all") {
    const selected = new Set(selectedStateCodes.map(normalizeStateCode).filter(Boolean));
    scoped = selected.size ? scoped.filter((item) => selected.has(normalizeStateCode(detectedState(item)))) : [];
  }
  if (stateFilter !== "all") {
    scoped = scoped.filter((item) => normalizeStateCode(detectedState(item)) === stateFilter);
  }
  return scoped;
}

function isOpportunityFromJob(item: HardwareOpportunity, jobId: string, jobOpportunityIds: Set<string>) {
  return item.last_seen_job_id === jobId
    || item.last_updated_job_id === jobId
    || item.first_seen_job_id === jobId
    || jobOpportunityIds.has(item.opportunity_id);
}

function buildStateFilters(opportunities: HardwareOpportunity[], preferredStates: string[]) {
  const states = new Set<string>();
  preferredStates.forEach((state) => {
    const normalized = normalizeStateCode(state);
    if (normalized) states.add(normalized);
  });
  opportunities.forEach((item) => {
    const normalized = normalizeStateCode(detectedState(item));
    if (normalized) states.add(normalized);
  });
  return [...states].sort();
}

function detectedState(item: HardwareOpportunity) {
  const rawDetected = typeof item.raw_data_json?.detected_state === "string" ? item.raw_data_json.detected_state : null;
  return item.detected_state || rawDetected || item.location_state || null;
}

function opportunityLocation(item: HardwareOpportunity) {
  const rawLocation = typeof item.raw_data_json?.location_text === "string" ? item.raw_data_json.location_text : null;
  return item.location_text || rawLocation || [item.location_city, detectedState(item), item.zip_code].filter(Boolean).join(", ");
}

function matchedKeywords(item: HardwareOpportunity) {
  const rawKeywords = item.raw_data_json?.matched_keywords;
  const values = item.matched_keywords ?? (Array.isArray(rawKeywords) ? rawKeywords.map(String) : []);
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function rawDataString(item: HardwareOpportunity, key: string) {
  const value = item.raw_data_json?.[key];
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

function normalizeStateCode(value?: string | null) {
  if (!value) return "";
  return stateLookup.get(value.trim().toLowerCase()) ?? value.trim().toUpperCase();
}

function resultScopeTitle(scope: ResultScope, t: (key: string) => string) {
  if (scope === "current_scan") return t("currentScanOpportunities");
  if (scope === "all_current") return t("allCurrentOpportunities");
  return t("selectedStatesOpportunities");
}

function emptyOpportunityMessage(scope: ResultScope, states: string[], stateFilter: string) {
  const stateLabel = stateFilter !== "all" ? stateFilter : states.length === 1 ? states[0] : "";
  if (scope === "current_scan") {
    return stateLabel
      ? `No current opportunities found in this scan. / 本次${stateLabel}扫描未发现当前有效机会。`
      : "No current opportunities found in this scan. / 本次扫描未发现当前有效机会。";
  }
  if (scope === "all_current") return "No current opportunities found in the database.";
  return stateLabel ? `No opportunities found for ${stateLabel}.` : "No opportunities found for the selected state filter.";
}

function stableOpportunityKey(item: HardwareOpportunity, index = 0) {
  return item.opportunity_id
    || `${normalizeOpportunityUrl(item.canonical_url ?? item.source_url)}-${index}`
    || `${item.source}-${item.title}-${index}`;
}

function normalizeOpportunityUrl(url: string | null | undefined) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return url.split("?")[0].split("#")[0].replace(/\/$/, "");
  }
}

function getCurrentOpportunities(opportunities: HardwareOpportunity[]) {
  return opportunities.filter(isCurrentOpportunity);
}

function getNeedsReviewOpportunities(opportunities: HardwareOpportunity[]) {
  return opportunities.filter((item) => isNeedsReviewOpportunity(item) && !isHistoryOpportunity(item));
}

function getHistoryOpportunities(opportunities: HardwareOpportunity[]) {
  return opportunities.filter(isHistoryOpportunity);
}

function filterOpportunities(
  opportunities: HardwareOpportunity[],
  filter: OpportunityFilter,
  buckets: { current: HardwareOpportunity[]; needsReview: HardwareOpportunity[]; history: HardwareOpportunity[] },
) {
  return opportunities.filter((item) => {
    if (filter === "current") return buckets.current.some((current) => current.opportunity_id === item.opportunity_id);
    if (filter === "active") return item.listing_status === "active" && isCurrentOpportunity(item);
    if (filter === "ending_soon") return item.listing_status === "ending_soon" && isCurrentOpportunity(item);
    if (filter === "needs_review") return buckets.needsReview.some((review) => review.opportunity_id === item.opportunity_id);
    if (filter === "history") return buckets.history.some((history) => history.opportunity_id === item.opportunity_id);
    if (filter === "missing_components") return ["missing_storage", "missing_memory", "missing_cpu", "missing_psu", "barebone", "mixed_lot"].includes(item.component_completeness);
    if (filter === "pickup_only") return item.pickup_only === true;
    return true;
  });
}

function isCurrentOpportunity(item: HardwareOpportunity) {
  if ((item.requested_states ?? []).length > 0 && item.state_match_status !== "matched") return false;
  if (hasReviewBlocker(item) || hasPastEndTime(item)) return false;
  if (item.listing_status === "active" || item.listing_status === "ending_soon") {
    return !hasUnconfirmedBlockedSource(item);
  }
  if (item.listing_status !== "unknown") return false;
  if (hasUnconfirmedBlockedSource(item) || hasClosedSignal(item)) return false;
  if (!item.first_seen_at || !item.last_status_check_at) return false;
  return isWithinHours(item.first_seen_at, 24) && isWithinHours(item.last_status_check_at, 24);
}

function isNeedsReviewOpportunity(item: HardwareOpportunity) {
  if ((item.requested_states ?? []).length > 0 && item.state_match_status === "unknown") return true;
  if (item.end_time_verification === "conflicting") return true;
  if (isHistoryOpportunity(item)) return false;
  if (item.needs_manual_review || item.listing_status === "needs_manual_review") return true;
  if (item.unavailable_reason || hasUnconfirmedBlockedSource(item)) return true;
  if (item.listing_status === "unknown") return !isCurrentOpportunity(item);
  return false;
}

function isHistoryOpportunity(item: HardwareOpportunity) {
  if (item.end_time_verification === "conflicting") return false;
  return ["ended", "sold", "removed", "unavailable", "ignored"].includes(item.listing_status) || hasPastEndTime(item);
}

function hasReviewBlocker(item: HardwareOpportunity) {
  return Boolean(
    item.needs_manual_review
      || item.listing_status === "needs_manual_review"
      || item.listing_status === "unavailable"
      || item.end_time_verification === "conflicting"
      || item.unavailable_reason,
  );
}

function confirmedEndTime(item: HardwareOpportunity) {
  return item.end_time_utc ?? item.auction_end_time ?? item.calculated_end_time ?? null;
}

function hasPastEndTime(item: HardwareOpportunity) {
  const endTime = confirmedEndTime(item);
  return Boolean(endTime && Date.parse(endTime) <= Date.now());
}

function hasUnconfirmedBlockedSource(item: HardwareOpportunity) {
  if (confirmedEndTime(item)) return false;
  const source = item.source.toLowerCase();
  const statusNote = [
    item.unavailable_reason,
    item.status_check_result,
    item.status_check_error,
    String(item.raw_data_json?.detail_parse_status ?? ""),
    String(item.raw_data_json?.detail_error ?? ""),
  ].join(" ").toLowerCase();
  const blocked = ["blocked", "captcha", "403", "login", "unavailable"].some((token) => statusNote.includes(token));
  return blocked || (source.includes("govdeals") && item.end_time_verification === "unknown");
}

function hasClosedSignal(item: HardwareOpportunity) {
  const text = [item.status_check_result, item.unavailable_reason, item.raw_title, item.raw_description].join(" ").toLowerCase();
  return ["auction ended", "closed", "sold", "no longer available", "removed"].some((token) => text.includes(token));
}

function isWithinHours(value: string, hours: number) {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return false;
  return Date.now() - parsed <= hours * 60 * 60 * 1000;
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

function sourceRunDuration(run: HardwareSourceRun) {
  if (!run.started_at || !run.completed_at) return "-";
  const ms = Date.parse(run.completed_at) - Date.parse(run.started_at);
  if (!Number.isFinite(ms) || ms < 0) return "-";
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatMs(ms?: number | null) {
  if (!ms || !Number.isFinite(ms)) return "-";
  return `${(ms / 1000).toFixed(1)}s`;
}

function tabLabel(tab: Tab, t: (key: string) => string) {
  if (tab === "needs review") return t("needsReview");
  if (tab === "source runs") return t("sourceRuns");
  if (tab === "telegram reports") return t("telegramReports");
  if (tab === "opportunities") return t("opportunities");
  return t("overview");
}

function buildReviewStats(needsReview: HardwareOpportunity[], history: HardwareOpportunity[]) {
  const today = new Date().toDateString();
  return {
    total: needsReview.length,
    reviewedToday: [...needsReview, ...history].filter((item) => item.reviewed_at && new Date(item.reviewed_at).toDateString() === today).length,
    remaining: needsReview.length,
    conflicting: needsReview.filter((item) => item.end_time_verification === "conflicting").length,
    blocked: needsReview.filter((item) => reviewReason(item) === "blocked").length,
    unknownEndTime: needsReview.filter((item) => !confirmedEndTime(item)).length,
    ignored: history.filter((item) => item.listing_status === "ignored").length,
  };
}

function buildLatestJobHealth(job: HardwareScanJob | null) {
  const runs = job?.source_runs ?? [];
  const searching = runs.filter((run) => run.status === "searching" || run.status === "running").length;
  const completed = runs.filter((run) => !["searching", "pending", "running"].includes(run.status)).length;
  const failed = runs.filter((run) => run.status === "failed" || run.status === "timeout" || run.status === "blocked").length;
  const updatedAtMs = job?.updated_at ? Date.parse(job.updated_at) : 0;
  const staleAgeMs = updatedAtMs ? Date.now() - updatedAtMs : 0;
  return {
    total: runs.length,
    completed,
    searching,
    failed,
    opportunitiesFound: job?.opportunities?.length ?? 0,
    isStale: Boolean(job && (job.status === "created" || job.status === "running") && searching > 0 && staleAgeMs > 10 * 60 * 1000),
  };
}

function reviewReason(item: HardwareOpportunity) {
  if (item.end_time_verification === "conflicting") return "conflicting";
  if (hasUnconfirmedBlockedSource(item)) return "blocked";
  if (!confirmedEndTime(item)) return "end_time_unknown";
  if (item.listing_status === "unknown") return "stale_unknown";
  if (item.end_time_verification === "unknown") return "verification_unknown";
  if (item.needs_manual_review) return "needs_manual_review";
  return item.status_check_result || "needs_manual_review";
}

function statusLabel(value: string | null | undefined, t: (key: string) => string) {
  const labels: Record<string, string> = {
    needs_manual_review: t("requiresReview"),
    conflicting: t("conflicting"),
    blocked: t("blocked"),
    stale_unknown: t("staleUnknown"),
    end_time_unknown: t("endTimeUnknown"),
    verification_unknown: t("verificationUnknown"),
    ignored: t("ignored"),
    active: t("statusActive"),
    ending_soon: t("statusEndingSoon"),
    ended: t("statusEnded"),
    sold: t("statusSold"),
    unavailable: t("statusUnavailable"),
    unknown: t("unknown"),
  };
  return labels[value || "unknown"] ?? value ?? t("unknown");
}

function completenessLabel(value: string | null | undefined, t: (key: string) => string) {
  const labels: Record<string, string> = {
    complete: t("statusActive"),
    mostly_complete: t("mostlyComplete"),
    missing_storage: t("missingComponents"),
    missing_memory: t("missingComponents"),
    missing_cpu: t("missingComponents"),
    missing_psu: t("missingComponents"),
    barebone: t("barebone"),
    mixed_lot: t("mixedLot"),
    unknown: t("unknown"),
  };
  return labels[value || "unknown"] ?? value ?? t("unknown");
}

function reasonLabel(value: string | null | undefined, t: (key: string) => string) {
  if (!value) return t("requiresReview");
  if (value.includes("blocked")) return t("blocked");
  return statusLabel(value, t);
}

function safeText(value?: string | null, t?: (key: string) => string) {
  return value && value.trim() ? value : t ? t("unknown") : "Unknown";
}

function stringValue(value?: string | number | null) {
  return value === null || value === undefined ? "" : String(value);
}

function nullableNumber(value: string) {
  if (!value.trim()) return null;
  const parsed = Number(value.replaceAll(",", ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function toLocalInputValue(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function emptyReviewForm(): ReviewFormPayload {
  return {
    manual_status: "needs_manual_review",
    review_action: "save_review",
    manual_quantity: "",
    manual_current_price: "",
    manual_total_price: "",
    manual_end_time: "",
    manual_timezone: "America/Los_Angeles",
    manual_location: "",
    manual_condition: "",
    manual_component_completeness: "unknown",
    review_notes: "",
  };
}

function normalizeState(input: string) {
  const key = input.trim().toLowerCase();
  if (!key) return null;
  return stateLookup.get(key) ?? null;
}

function estimateTasks(strategy: RegionStrategy, stateCount: number, categoryCount: number, scanDepth: ScanDepth, scanLane: ScanLane, scanScope: ScanScope, hasManualImport: boolean) {
  if (scanLane === "deep") return 0;
  const regionFactor = scanScope === "nationwide" || strategy === "all_us" ? 1 : Math.max(stateCount, 1);
  const queryCount = scanDepthQueryCounts[scanDepth];
  const fastSourceQueries = queryCount * 3 + Math.min(queryCount, 3);
  return regionFactor * categoryCount * fastSourceQueries + (hasManualImport ? 1 : 0);
}

function buildScanProgress(job: HardwareScanJob | null, progress: HardwareScanProgress | null) {
  const isScanning = job?.status === "created" || job?.status === "running";
  if (progress) {
    const activeRun = progress.worker_runs.find((run) => run.status === "running" || run.status === "searching");
    const elapsedSeconds = job ? Math.max(0, Math.round((Date.now() - Date.parse(job.created_at)) / 1000)) : 0;
    return {
      isScanning,
      total: Math.max(progress.overall_total, 1),
      completed: progress.overall_completed,
      runningWorkers: progress.running_workers,
      cacheHits: progress.cache_hits,
      currentCategory: activeRun?.category ?? "waiting",
      currentSource: progress.current_source ?? activeRun?.source_name ?? "queued",
      elapsed: `${Math.floor(elapsedSeconds / 60)}m ${elapsedSeconds % 60}s`,
    };
  }
  const total = Math.max(job?.generated_queries?.length ?? 0, job?.source_runs?.length ?? 0, 1);
  const completed = job?.source_runs?.filter((run) => !["searching", "pending", "running"].includes(run.status)).length ?? 0;
  const activeRun = job?.source_runs?.find((run) => run.status === "searching" || run.status === "running");
  const lastRun = job?.source_runs?.[job.source_runs.length - 1];
  const elapsedSeconds = job ? Math.max(0, Math.round((Date.now() - Date.parse(job.created_at)) / 1000)) : 0;
  return {
    isScanning,
    total,
    completed: Math.min(completed, total),
    runningWorkers: job?.source_runs?.filter((run) => run.status === "running" || run.status === "searching").length ?? 0,
    cacheHits: job?.source_runs?.filter((run) => run.cache_hit || run.status === "skipped_cache").length ?? 0,
    currentCategory: activeRun?.category ?? lastRun?.category ?? "waiting",
    currentSource: activeRun?.source_name ?? lastRun?.source_name ?? "queued",
    elapsed: `${Math.floor(elapsedSeconds / 60)}m ${elapsedSeconds % 60}s`,
  };
}

function isTerminalJobStatus(status?: HardwareScanJob["status"] | null) {
  return Boolean(status && ["completed", "partially_completed", "failed", "cancelled"].includes(status));
}

function categoryLabel(category: HardwareCategory, t: (key: string) => string) {
  const labels: Record<HardwareCategory, string> = {
    servers: t("servers"),
    gpu: t("gpuShort"),
    memory: t("memory"),
    storage: t("storageDevices"),
    cpu: t("cpuShort"),
    networking: "Networking / 网络设备",
    computers_it: "Computers IT / 电脑IT",
  };
  return labels[category];
}

function scanModeLabel(mode: DashboardScanMode, t: (key: string) => string) {
  const labels: Record<DashboardScanMode, string> = {
    asset_listing_search: t("assetListings"),
    supplier_lead_search: t("supplierLeads"),
    both: t("bothScan"),
  };
  return labels[mode];
}

function regionStrategyLabel(strategy: RegionStrategy, t: (key: string) => string) {
  const labels: Record<RegionStrategy, string> = {
    all_us: t("allUs"),
    priority_states: t("priorityStates"),
    rotating_states: t("rotatingStates"),
    custom_states: t("customStates"),
  };
  return labels[strategy];
}

function telegramStatus(dashboard: HardwareDashboard | null, t: (key: string) => string) {
  if (!dashboard?.telegram_enabled) return t("disabled");
  return t("enabled");
}

function databaseHealthLabel(dashboard: HardwareDashboard | null) {
  if (dashboard?.database_health) return dashboard.database_health;
  if (!dashboard?.database_url_configured) return "not_configured";
  if (dashboard.persistence_mode === "postgresql") return "healthy";
  return "error";
}

function regionStrategyDescription(strategy: RegionStrategy, t: (key: string) => string) {
  if (strategy === "all_us") return t("strategyAllUs");
  if (strategy === "priority_states") return t("strategyPriority");
  if (strategy === "rotating_states") return t("strategyRotating");
  return t("strategyCustom");
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

function formatMoney(value?: number | null, t?: (key: string) => string) {
  return value ? `$${value.toLocaleString()}` : t ? t("unknown") : "Unknown";
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "Unknown";
}

function formatShortDate(value?: string | null) {
  return value ? new Date(value).toLocaleDateString() : "Unknown";
}

function formatEndTime(item: HardwareOpportunity, t?: (key: string) => string) {
  const value = item.end_time_utc ?? item.auction_end_time;
  if (!value) return t ? t("unknown") : "Unknown";
  const rawZone = item.end_time_timezone_raw ? ` ${item.end_time_timezone_raw}` : "";
  return `${new Date(value).toLocaleString()}${rawZone}`;
}

function timeLeftLabel(item: HardwareOpportunity, t?: (key: string) => string) {
  if (item.time_remaining) return item.time_remaining;
  const value = item.end_time_utc ?? item.auction_end_time;
  if (!value) return <span className="muted">{t ? t("unknown") : "Unknown"}</span>;
  const ms = Date.parse(value) - Date.now();
  if (ms <= 0) return t ? t("statusEnded") : "Ended";
  const hours = Math.floor(ms / 3600000);
  const minutes = Math.floor((ms % 3600000) / 60000);
  return `${hours}h ${minutes}m`;
}

function verificationBadge(item: HardwareOpportunity, t: (key: string) => string) {
  if (item.needs_manual_review || item.listing_status === "needs_manual_review") {
    return <span className="badge changed-badge">{t("requiresReview")}</span>;
  }
  if (item.end_time_verification === "unknown") {
    return <span className="badge">{t("unknown")}</span>;
  }
  if (item.end_time_verification === "conflicting") {
    return <span className="badge changed-badge">{t("conflicting")}</span>;
  }
  const labels: Record<string, string> = {
    source_confirmed: t("sourceConfirmed"),
    manually_verified: t("manuallyVerified"),
    countdown_estimated: t("countdownEstimated"),
    secondary_source_confirmed: t("secondarySourceConfirmed"),
  };
  return <span className="badge new-badge">{labels[item.end_time_verification] ?? item.end_time_verification}</span>;
}

function pickupShipping(item: HardwareOpportunity) {
  const pickup = item.pickup_only === true ? "pickup only" : item.pickup_only === false ? "pickup unknown" : "pickup unknown";
  const shipping = item.shipping_available === true ? "shipping yes" : item.shipping_available === false ? "shipping no" : "shipping unknown";
  return `${pickup} / ${shipping}`;
}
