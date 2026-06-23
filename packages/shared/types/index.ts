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

export type SiteHunterJobStatus =
  | "created"
  | "parsing_requirements"
  | "generating_queries"
  | "discovering_sources"
  | "searching_properties"
  | "normalizing_results"
  | "scoring"
  | "completed"
  | "partially_completed"
  | "failed";

export type SiteSourceRunStatus = "pending" | "searching" | "success" | "failed" | "timeout" | "blocked" | "disabled";
export type SiteResultCategory = "specific_listing" | "listing_collection" | "source_page" | "irrelevant";
export type PowerAddressStatus = "verified_address" | "geocoded_address" | "partial_address" | "address_needs_verification" | "geocoding_failed";
export type LandIdReviewStatus = "not_reviewed" | "in_review" | "manually_verified" | "mismatch_found";

export interface NearbyPowerAsset {
  id: string;
  site_id?: string | null;
  asset_type: "substation" | "transmission_line" | "tower" | "plant";
  asset_name?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  geometry?: Record<string, unknown> | null;
  distance_miles?: number | null;
  voltage_kv?: number | null;
  owner?: string | null;
  operator?: string | null;
  status?: string | null;
  source_name: string;
  source_url?: string | null;
  confidence_level: string;
  verification_status: string;
  dataset_version?: string | null;
  source_timestamp?: string | null;
  checked_at: string;
  raw_data_json: Record<string, unknown>;
}

export interface UtilityCandidate {
  likely_utility?: string | null;
  utility_type: string;
  evidence?: string | null;
  source_url?: string | null;
  confidence_level: string;
  status: string;
}

export interface PowerSourceRecord {
  source_name: string;
  source_url?: string | null;
  source_type: string;
  generated_query?: string | null;
  confidence_level: string;
  discovered_at: string;
}

export interface LandIdReview {
  land_id_review_status: LandIdReviewStatus;
  land_id_map_url?: string | null;
  parcel_id?: string | null;
  owner_name?: string | null;
  owner_mailing_address?: string | null;
  parcel_acres?: number | null;
  nearest_substation_name?: string | null;
  nearest_substation_distance?: number | null;
  nearest_transmission_voltage?: number | null;
  manual_notes?: string | null;
  reviewed_at?: string | null;
}

export interface SitePowerAssessment {
  site_id?: string | null;
  address_status: PowerAddressStatus;
  raw_address?: string | null;
  standardized_address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  geocoding_source?: string | null;
  geocoding_confidence: number;
  nearest_substation?: NearbyPowerAsset | null;
  nearest_transmission_line?: NearbyPowerAsset | null;
  nearby_assets: NearbyPowerAsset[];
  likely_utility: UtilityCandidate;
  power_source_records: PowerSourceRecord[];
  search_radius_counts: Record<string, number>;
  known_voltage_kv?: number | null;
  capacity_status: string;
  assessment_warning: string;
  confidence_level: string;
  checked_at: string;
  error_message?: string | null;
}

export interface ResultQualityStats {
  raw_results: number;
  specific_listings: number;
  listing_collections: number;
  source_pages: number;
  irrelevant_results: number;
  duplicates_removed: number;
  state_mismatch_removed: number;
  size_mismatch_removed: number;
  budget_mismatch_removed: number;
  final_candidates: number;
}

export interface SiteHunterRegions {
  states: string[];
  counties: string[];
  cities: string[];
  zip_codes: string[];
  custom_area?: string | null;
  radius_miles?: number | null;
}

export interface SiteHunterStructuredCriteria {
  regions: SiteHunterRegions;
  property_types: string[];
  transaction_types: string[];
  min_land_acres?: number | null;
  max_land_acres?: number | null;
  min_building_sqft?: number | null;
  max_building_sqft?: number | null;
  max_price_usd?: number | null;
  target_load_mw?: number | null;
  preferred_substation_distance_miles?: number | null;
  preferred_transmission_voltage_kv?: number | null;
  project_use?: string | null;
  raw_user_query_zh?: string | null;
  parsed_summary_zh?: string | null;
}

export interface GeneratedSearchQuery {
  id: string;
  generated_query_en: string;
  source_group: string;
  state?: string | null;
  county?: string | null;
  city?: string | null;
  property_type?: string | null;
  status: SiteSourceRunStatus;
  result_count: number;
  created_at: string;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface DiscoveredSource {
  id: string;
  source_name: string;
  domain: string;
  source_type: string;
  state?: string | null;
  county?: string | null;
  city?: string | null;
  discovery_method: string;
  trust_level: string;
  adapter_type: string;
  status: SiteSourceRunStatus;
  last_success_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SiteSourceRun {
  id: string;
  source_name: string;
  source_type: string;
  adapter_type: string;
  query?: string | null;
  status: SiteSourceRunStatus;
  result_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface SiteListing {
  id: string;
  site_name: string;
  translated_title_zh?: string | null;
  translated_summary_zh?: string | null;
  address_line_1?: string | null;
  city?: string | null;
  county?: string | null;
  state?: string | null;
  zip_code?: string | null;
  country: string;
  latitude?: number | null;
  longitude?: number | null;
  standardized_address?: string | null;
  geocoding_source?: string | null;
  geocoding_confidence: number;
  property_type?: string | null;
  zoning?: string | null;
  land_acres?: number | null;
  building_sqft?: number | null;
  asking_price_usd?: number | null;
  transaction_type?: string | null;
  source_name: string;
  source_url: string;
  source_type: string;
  original_title: string;
  original_description?: string | null;
  broker_name?: string | null;
  broker_company?: string | null;
  result_category: SiteResultCategory;
  address_status: string;
  price_status: string;
  data_completeness_score: number;
  quality_flags: string[];
  source_confidence: string;
  field_confidence: Record<string, string>;
  missing_fields: string[];
  raw_data_json: Record<string, unknown>;
  first_seen_at: string;
  last_checked_at: string;
  preliminary_score: number;
  preliminary_grade: string;
  score_reasons: string[];
  warnings: string[];
  review_status?: string | null;
  power_assessment?: SitePowerAssessment | null;
  land_id_review: LandIdReview;
}

export interface SiteHunterJob {
  id: string;
  status: SiteHunterJobStatus;
  natural_language_query_zh?: string | null;
  parsed_criteria?: SiteHunterStructuredCriteria | null;
  generated_queries: GeneratedSearchQuery[];
  discovered_sources: DiscoveredSource[];
  source_runs: SiteSourceRun[];
  results: SiteListing[];
  discovery_candidates: SiteListing[];
  quality_stats: ResultQualityStats;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}
