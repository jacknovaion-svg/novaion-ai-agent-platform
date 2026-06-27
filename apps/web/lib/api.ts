import type {
  SearchJob,
  SearchMode,
  SearchResult,
  SearchSource,
  SiteHunterJob,
  SiteListing,
  SiteSearchAnchor,
  SupplierSearchJob,
  HardwareDashboard,
  HardwareDailyReport,
  HardwareListingRecheckSummary,
  HardwareOpportunity,
  HardwareSchedulerState,
  HardwareScanJob,
} from "@novaion/shared/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export type SearchPayload = {
  query: string;
  quantity: number;
  zip_code: string;
  radius: number;
  mode: SearchMode;
  sources: SearchSource[];
};

export async function runSearch(payload: SearchPayload): Promise<SearchJob> {
  const response = await fetch(`${API_BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, agent_type: "hardware_hunter" }),
  });
  if (!response.ok) throw new Error("Search failed");
  return response.json();
}

export async function saveSearch(payload: SearchPayload) {
  const response = await fetch(`${API_BASE}/saved-searches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Save failed");
  return response.json();
}

export async function listSavedSearches() {
  const response = await fetch(`${API_BASE}/saved-searches`, { cache: "no-store" });
  if (!response.ok) return [];
  return response.json();
}

export function storeResults(job: SearchJob) {
  window.sessionStorage.setItem("novaion-last-job", JSON.stringify(job));
}

export function loadResults(): SearchJob | null {
  const raw = window.sessionStorage.getItem("novaion-last-job");
  return raw ? (JSON.parse(raw) as SearchJob) : null;
}

export function storeDetail(result: SearchResult) {
  window.sessionStorage.setItem("novaion-selected-result", JSON.stringify(result));
}

export function loadDetail(): SearchResult | null {
  const raw = window.sessionStorage.getItem("novaion-selected-result");
  return raw ? (JSON.parse(raw) as SearchResult) : null;
}

export type SiteHunterPayload = {
  natural_language_query_zh?: string;
  structured_criteria?: {
    regions: {
      states: string[];
      state_codes?: string[];
      counties: string[];
      cities: string[];
      zip_codes: string[];
      custom_area?: string | null;
      radius_miles?: number | null;
    };
    search_anchor?: Partial<SiteSearchAnchor> | null;
    property_types: string[];
    transaction_types: string[];
    min_land_acres?: number | null;
    max_price_usd?: number | null;
    target_load_mw?: number | null;
    preferred_substation_distance_miles?: number | null;
    preferred_transmission_voltage_kv?: number | null;
    project_use?: string | null;
  };
  manual_urls?: string[];
  manual_text?: string | null;
  max_results_per_source?: number;
};

export async function createSiteHunterJob(payload: SiteHunterPayload): Promise<SiteHunterJob> {
  const response = await fetch(`${API_BASE}/site-hunter/search-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Site Hunter search failed");
  return response.json();
}

export async function getSiteHunterJob(jobId: string): Promise<SiteHunterJob> {
  const response = await fetch(`${API_BASE}/site-hunter/search-jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Site Hunter job not found");
  return response.json();
}

export async function getSiteHunterResults(jobId: string): Promise<SiteListing[]> {
  const response = await fetch(`${API_BASE}/site-hunter/search-jobs/${jobId}/results`, { cache: "no-store" });
  if (!response.ok) throw new Error("Site Hunter results not found");
  return response.json();
}

export async function getSiteHunterSite(siteId: string): Promise<SiteListing> {
  const response = await fetch(`${API_BASE}/site-hunter/sites/${siteId}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Site not found");
  return response.json();
}

export async function reviewSiteHunterSite(siteId: string, status: string) {
  const response = await fetch(`${API_BASE}/site-hunter/sites/${siteId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!response.ok) throw new Error("Site review failed");
  return response.json();
}

export async function updateLandIdReview(siteId: string, payload: {
  land_id_review_status: string;
  land_id_map_url?: string | null;
  parcel_id?: string | null;
  owner_name?: string | null;
  owner_mailing_address?: string | null;
  parcel_acres?: number | null;
  nearest_substation_name?: string | null;
  nearest_substation_distance?: number | null;
  nearest_transmission_voltage?: number | null;
  manual_notes?: string | null;
}) {
  const response = await fetch(`${API_BASE}/site-hunter/sites/${siteId}/land-id-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Land id review save failed");
  return response.json();
}

export async function updateDataTruthVerification(siteId: string, payload: {
  automatic_result_summary?: string | null;
  land_id_result_summary?: string | null;
  official_source_summary?: string | null;
  conflict_summary?: string | null;
  final_verification_status: string;
  verified_by?: string | null;
  notes?: string | null;
  field_sources?: Record<string, string>;
  conflicting_fields?: string[];
}) {
  const response = await fetch(`${API_BASE}/site-hunter/sites/${siteId}/data-truth-verification`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Data truth verification save failed");
  return response.json();
}

export type SupplierHunterPayload = {
  natural_language_query_zh?: string;
  structured_criteria?: {
    regions: {
      states: string[];
      state_codes: string[];
      cities: string[];
      zip_codes: string[];
      radius_miles?: number | null;
    };
    supplier_types: string[];
    equipment_types: string[];
    certifications: string[];
    data_center_decommissioning?: boolean | null;
    bulk_sales?: boolean | null;
    wholesale?: boolean | null;
    direct_asset_purchasing?: boolean | null;
  };
  manual_urls?: string[];
  manual_text?: string | null;
  max_results_per_source?: number;
};

export async function createSupplierHunterJob(payload: SupplierHunterPayload): Promise<SupplierSearchJob> {
  const response = await fetch(`${API_BASE}/supplier-hunter/search-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Supplier Hunter search failed");
  return response.json();
}

export async function getSupplierHunterJob(jobId: string): Promise<SupplierSearchJob> {
  const response = await fetch(`${API_BASE}/supplier-hunter/search-jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Supplier Hunter job not found");
  return response.json();
}

export async function reviewSupplier(supplierId: string, status: string, notes?: string | null) {
  const response = await fetch(`${API_BASE}/supplier-hunter/suppliers/${supplierId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes }),
  });
  if (!response.ok) throw new Error("Supplier review failed");
  return response.json();
}

export type HardwareDailyScanPayload = {
  mode: "asset_listing_search" | "supplier_lead_search" | "both";
  categories: Array<"servers" | "gpu" | "memory" | "storage" | "cpu">;
  states: string[];
  test_run: boolean;
  max_results_per_query: number;
  max_queries_per_category: number;
  send_telegram: boolean;
  manual_urls?: string[];
  manual_text?: string | null;
};

export async function runHardwareDailyScan(payload: HardwareDailyScanPayload): Promise<HardwareScanJob> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Hardware daily scan failed");
  return response.json();
}

export async function getHardwareDailyScanJob(jobId: string): Promise<HardwareScanJob> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Hardware daily scan job not found");
  return response.json();
}

export async function getHardwareDashboard(): Promise<HardwareDashboard> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/dashboard`, { cache: "no-store" });
  if (!response.ok) throw new Error("Hardware dashboard failed");
  return response.json();
}

export async function recheckHardwareOpportunities(limit = 80): Promise<HardwareListingRecheckSummary> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/recheck?limit=${limit}`, { method: "POST" });
  if (!response.ok) throw new Error("Hardware recheck failed");
  return response.json();
}

export async function recheckHardwareOpportunity(opportunityId: string): Promise<HardwareOpportunity> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/opportunities/${opportunityId}/recheck`, { method: "POST" });
  if (!response.ok) throw new Error("Opportunity recheck failed");
  return response.json();
}

export async function updateHardwareOpportunityManualStatus(
  opportunityId: string,
  payload: {
    manual_status: string;
    manual_end_time?: string | null;
    manual_timezone?: string | null;
    manual_notes?: string | null;
    verified_by?: string | null;
  },
): Promise<HardwareOpportunity> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/opportunities/${opportunityId}/manual-status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Manual status update failed");
  return response.json();
}

export async function createHardwareTelegramReport(
  jobId: string,
  action: "preview" | "test" | "approve_and_send" = "preview",
  message?: string,
): Promise<HardwareDailyReport> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/jobs/${jobId}/telegram-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, message }),
  });
  if (!response.ok) throw new Error("Telegram report generation failed");
  return response.json();
}

export async function getHardwareScheduler(): Promise<HardwareSchedulerState> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/scheduler`, { cache: "no-store" });
  if (!response.ok) throw new Error("Scheduler status failed");
  return response.json();
}

export async function updateHardwareScheduler(action: "pause" | "resume"): Promise<HardwareSchedulerState> {
  const response = await fetch(`${API_BASE}/hardware-hunter/daily-scan/scheduler/${action}`, { method: "POST" });
  if (!response.ok) throw new Error("Scheduler update failed");
  return response.json();
}
