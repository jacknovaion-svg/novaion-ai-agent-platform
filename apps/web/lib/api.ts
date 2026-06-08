import type { SearchJob, SearchMode, SearchResult, SearchSource } from "@novaion/shared/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

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
