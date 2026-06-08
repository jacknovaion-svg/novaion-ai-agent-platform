export type Language = "en" | "zh" | "es";

export type SearchMode = "local" | "online" | "all";

export type SearchSource =
  | "best_buy"
  | "micro_center"
  | "newegg"
  | "cdw"
  | "provantage";

export interface SearchResult {
  source: string;
  product_name: string;
  brand?: string | null;
  model?: string | null;
  store_name?: string | null;
  address?: string | null;
  distance?: number | null;
  price?: number | null;
  promotion?: string | null;
  inventory_status?: string | null;
  pickup_available: boolean;
  shipping_available: boolean;
  product_url?: string | null;
  updated_at: string;
  recommendation_score: number;
}

export interface SearchJob {
  id: string;
  agent_type: string;
  query: string;
  quantity: number;
  zip_code?: string | null;
  radius?: number | null;
  mode: SearchMode;
  status: string;
  created_at: string;
  results: SearchResult[];
}
