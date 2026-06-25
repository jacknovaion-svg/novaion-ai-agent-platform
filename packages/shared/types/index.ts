export type Language = "en" | "zh" | "es";

export type SearchMode = "local" | "online" | "all";

export type SearchSource =
  | "best_buy"
  | "micro_center"
  | "newegg"
  | "cdw"
  | "provantage";

export type HardwareSearchMode = "retail_products" | "used_enterprise_hardware" | "supplier_discovery";

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

export type SupplierJobStatus =
  | "created"
  | "parsing_requirements"
  | "generating_queries"
  | "searching_suppliers"
  | "normalizing_results"
  | "scoring"
  | "completed"
  | "partially_completed"
  | "failed";

export type SupplierCategory = "A" | "B" | "C" | "D";
export type SupplierVerificationStatus =
  | "verified"
  | "claimed_on_website"
  | "directory_discovered"
  | "needs_verification"
  | "unknown";
export type SupplierReviewStatus = "new" | "kept" | "rejected" | "contact" | "investigate";
export type SupplierSourceRunStatus = "pending" | "searching" | "success" | "failed" | "timeout" | "blocked";

export interface SupplierSearchRegions {
  states: string[];
  state_codes: string[];
  cities: string[];
  zip_codes: string[];
  radius_miles?: number | null;
}

export interface SupplierSearchCriteria {
  regions: SupplierSearchRegions;
  supplier_types: string[];
  equipment_types: string[];
  certifications: string[];
  data_center_decommissioning?: boolean | null;
  bulk_sales?: boolean | null;
  wholesale?: boolean | null;
  direct_asset_purchasing?: boolean | null;
  raw_user_query_zh?: string | null;
  parsed_summary_zh?: string | null;
}

export interface SupplierGeneratedQuery {
  id: string;
  generated_query_en: string;
  source_group: string;
  state?: string | null;
  state_code?: string | null;
  city?: string | null;
  region_name?: string | null;
  supplier_type?: string | null;
  result_count: number;
  status: SupplierSourceRunStatus;
}

export interface SupplierRegionSubJob {
  id: string;
  state_code: string;
  state_name: string;
  region_name: string;
  cities: string[];
  generated_query_count: number;
  executed_query_count: number;
  raw_result_count: number;
  supplier_count: number;
  high_value_count: number;
  status: SupplierSourceRunStatus;
}

export interface SupplierSourceRun {
  id: string;
  source_name: string;
  adapter_type: string;
  query?: string | null;
  status: SupplierSourceRunStatus;
  result_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface SupplierResult {
  supplier_id: string;
  company_name: string;
  company_type?: string | null;
  supplier_category: SupplierCategory;
  website?: string | null;
  address?: string | null;
  city?: string | null;
  county?: string | null;
  state?: string | null;
  zip_code?: string | null;
  phone?: string | null;
  email?: string | null;
  contact_name?: string | null;
  service_area?: string | null;
  r2_certified: SupplierVerificationStatus;
  e_stewards_certified: SupplierVerificationStatus;
  naid_aaa_certified: SupplierVerificationStatus;
  data_center_decommissioning: boolean;
  enterprise_itad: boolean;
  asset_remarketing: boolean;
  direct_asset_purchasing: boolean;
  server_recycling: boolean;
  computer_refurbishing: boolean;
  bulk_sales: boolean;
  wholesale: boolean;
  equipment_types: string[];
  minimum_order?: string | null;
  pickup_available?: boolean | null;
  shipping_available?: boolean | null;
  source_name: string;
  source_url: string;
  last_checked_at: string;
  confidence_level: SupplierVerificationStatus;
  review_status: SupplierReviewStatus;
  notes?: string | null;
  supplier_score: number;
  score_reasons: string[];
  quality_flags: string[];
  raw_data_json: Record<string, unknown>;
}

export interface SupplierQualityStats {
  raw_results: number;
  normalized_suppliers: number;
  duplicates_removed: number;
  low_value_filtered: number;
  final_suppliers: number;
  high_value_suppliers: number;
}

export interface SupplierSearchJob {
  id: string;
  status: SupplierJobStatus;
  natural_language_query_zh?: string | null;
  parsed_criteria?: SupplierSearchCriteria | null;
  state_job?: Record<string, unknown> | null;
  region_subjobs: SupplierRegionSubJob[];
  generated_queries: SupplierGeneratedQuery[];
  source_runs: SupplierSourceRun[];
  results: SupplierResult[];
  rejected_low_value_results: SupplierResult[];
  quality_stats: SupplierQualityStats;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export type HardwareScanJobStatus = "created" | "running" | "partially_completed" | "completed" | "failed";
export type HardwareSourceRunStatus = "pending" | "searching" | "success" | "failed" | "timeout" | "blocked" | "disabled";
export type HardwareScanMode = "asset_listing_search" | "supplier_lead_search" | "both";
export type HardwareCategory = "servers" | "gpu" | "memory" | "storage" | "cpu";
export type HardwareCondition =
  | "new"
  | "open_box"
  | "used_working"
  | "refurbished"
  | "tested"
  | "untested"
  | "customer_return"
  | "salvage"
  | "parts_only"
  | "broken"
  | "unknown";
export type HardwareChangeType =
  | "NEW"
  | "PRICE_CHANGED"
  | "QUANTITY_CHANGED"
  | "STATUS_CHANGED"
  | "AUCTION_ENDING"
  | "RELISTED"
  | "SUPPLIER_DISCOVERED";

export interface HardwareGeneratedQuery {
  id: string;
  category: HardwareCategory;
  source_group: string;
  generated_query_en: string;
  status: HardwareSourceRunStatus;
  result_count: number;
}

export interface HardwareSourceRun {
  id: string;
  source_name: string;
  adapter_type: string;
  query?: string | null;
  category?: HardwareCategory | null;
  status: HardwareSourceRunStatus;
  result_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface HardwareOpportunity {
  opportunity_id: string;
  category: HardwareCategory;
  subcategory?: string | null;
  title: string;
  manufacturer?: string | null;
  model?: string | null;
  part_number?: string | null;
  generation?: string | null;
  configuration?: string | null;
  quantity?: number | null;
  quantity_status: string;
  unit_price?: number | null;
  total_price?: number | null;
  condition: HardwareCondition;
  working_status: string;
  testing_status: string;
  warranty_status: string;
  location_city?: string | null;
  location_state?: string | null;
  zip_code?: string | null;
  pickup_only?: boolean | null;
  shipping_available?: boolean | null;
  auction_end_time?: string | null;
  seller_name?: string | null;
  seller_type: string;
  source: string;
  source_url: string;
  source_listing_id?: string | null;
  first_seen_at: string;
  last_seen_at: string;
  last_changed_at?: string | null;
  status: string;
  confidence_level: string;
  risk_flags: string[];
  change_types: HardwareChangeType[];
  opportunity_score: number;
  risk_score: number;
  score_reasons: string[];
  raw_title: string;
  raw_description?: string | null;
  raw_data_json: Record<string, unknown>;
}

export interface HardwareQualityStats {
  raw_results: number;
  normalized_listings: number;
  duplicates_removed: number;
  new_opportunities: number;
  price_changes: number;
  quantity_changes: number;
  status_changes: number;
  final_opportunities: number;
  high_score_opportunities: number;
  failed_sources: number;
}

export interface TelegramDeliveryLog {
  id: string;
  scan_job_id: string;
  report_type: string;
  message_hash: string;
  status: "disabled" | "dry_run" | "sent" | "failed" | "duplicate_skipped";
  chat_id?: string | null;
  error_message?: string | null;
  sent_at?: string | null;
  created_at: string;
}

export interface HardwareDailyReport {
  scan_job_id: string;
  report_type: string;
  title: string;
  message_zh: string;
  generated_at: string;
  delivery_log?: TelegramDeliveryLog | null;
}

export interface HardwareScanJob {
  id: string;
  mode: HardwareScanMode;
  status: HardwareScanJobStatus;
  categories: HardwareCategory[];
  states: string[];
  generated_queries: HardwareGeneratedQuery[];
  source_runs: HardwareSourceRun[];
  opportunities: HardwareOpportunity[];
  quality_stats: HardwareQualityStats;
  report?: HardwareDailyReport | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface HardwareDashboard {
  total_jobs: number;
  total_opportunities_seen: number;
  active_opportunities: number;
  latest_job?: HardwareScanJob | null;
  telegram_enabled: boolean;
  daily_report_hour: number;
  timezone: string;
  immediate_alerts: boolean;
  top_opportunities: HardwareOpportunity[];
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
export type SearchAnchorType = "zip_code" | "coordinates" | "address" | "unknown";
export type SearchAnchorStatus = "unresolved" | "resolved" | "failed";
export type DataTruthVerificationStatus =
  | "official_verified"
  | "manual_map_confirmed"
  | "source_confirmed"
  | "estimated"
  | "conflicting"
  | "unverified";

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

export interface DataTruthVerification {
  automatic_result_summary?: string | null;
  land_id_result_summary?: string | null;
  official_source_summary?: string | null;
  conflict_summary?: string | null;
  final_verification_status: DataTruthVerificationStatus;
  verified_at?: string | null;
  verified_by?: string | null;
  notes?: string | null;
  field_sources: Record<string, string>;
  conflicting_fields: string[];
  capacity_status: string;
  verification_warning: string;
  updated_at: string;
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
  radius_mismatch_removed: number;
  final_candidates: number;
  power_screened_candidates: number;
}

export interface SiteHunterRegions {
  states: string[];
  state_codes: string[];
  counties: string[];
  cities: string[];
  zip_codes: string[];
  custom_area?: string | null;
  radius_miles?: number | null;
}

export interface SiteSearchAnchor {
  input_type: SearchAnchorType;
  raw_input?: string | null;
  label?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  radius_miles?: number | null;
  city?: string | null;
  county?: string | null;
  state?: string | null;
  zip_code?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  confidence: number;
  status: SearchAnchorStatus;
  error_message?: string | null;
  resolved_at?: string | null;
}

export interface SiteHunterStructuredCriteria {
  regions: SiteHunterRegions;
  search_anchor?: SiteSearchAnchor | null;
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
  distance_to_search_anchor_miles?: number | null;
  search_anchor_distance_basis?: string | null;
  power_assessment?: SitePowerAssessment | null;
  land_id_review: LandIdReview;
  data_truth_verification: DataTruthVerification;
}

export interface StateRegionSubJob {
  id: string;
  state_code: string;
  state_name: string;
  region_name: string;
  region_type: string;
  cities: string[];
  counties: string[];
  generated_query_count: number;
  executed_query_count: number;
  raw_result_count: number;
  specific_listing_count: number;
  final_candidate_count: number;
  power_screened_count: number;
  status: SiteSourceRunStatus;
  error_message?: string | null;
}

export interface SiteHunterJob {
  id: string;
  status: SiteHunterJobStatus;
  natural_language_query_zh?: string | null;
  parsed_criteria?: SiteHunterStructuredCriteria | null;
  job_mode: string;
  state_job?: Record<string, unknown> | null;
  region_subjobs: StateRegionSubJob[];
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
