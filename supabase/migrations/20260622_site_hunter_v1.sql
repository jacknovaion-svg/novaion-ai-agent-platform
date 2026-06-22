create extension if not exists "pgcrypto";

create table if not exists site_hunter_search_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete set null,
  natural_language_query_zh text,
  parsed_criteria_json jsonb,
  status text not null default 'created',
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists site_hunter_generated_queries (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references site_hunter_search_jobs(id) on delete cascade,
  generated_query_en text not null,
  source_group text,
  state text,
  county text,
  city text,
  property_type text,
  status text not null default 'pending',
  result_count integer not null default 0,
  error_message text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists discovered_sources (
  id uuid primary key default gen_random_uuid(),
  source_name text not null,
  domain text not null,
  source_type text not null,
  state text,
  county text,
  city text,
  discovery_method text,
  trust_level text not null default 'unknown',
  adapter_type text not null default 'generic_web_search',
  status text not null default 'pending',
  last_success_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists source_domains (
  id uuid primary key default gen_random_uuid(),
  domain text not null unique,
  root_domain text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists source_regions (
  id uuid primary key default gen_random_uuid(),
  discovered_source_id uuid references discovered_sources(id) on delete cascade,
  state text,
  county text,
  city text,
  zip_code text,
  created_at timestamptz not null default now()
);

create table if not exists source_categories (
  id uuid primary key default gen_random_uuid(),
  discovered_source_id uuid references discovered_sources(id) on delete cascade,
  source_type text not null,
  category_label text,
  trust_level text not null default 'unknown',
  created_at timestamptz not null default now()
);

create table if not exists source_health (
  id uuid primary key default gen_random_uuid(),
  discovered_source_id uuid references discovered_sources(id) on delete cascade,
  status text not null default 'pending',
  last_success_at timestamptz,
  last_error text,
  last_checked_at timestamptz not null default now(),
  consecutive_failures integer not null default 0
);

create table if not exists search_source_runs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references site_hunter_search_jobs(id) on delete cascade,
  source_name text not null,
  source_type text,
  adapter_type text,
  query text,
  status text not null default 'pending',
  result_count integer not null default 0,
  started_at timestamptz,
  completed_at timestamptz,
  error_message text
);

create table if not exists sites (
  id uuid primary key default gen_random_uuid(),
  site_name text not null,
  address_line_1 text,
  city text,
  county text,
  state text,
  zip_code text,
  country text not null default 'US',
  latitude numeric,
  longitude numeric,
  property_type text,
  original_use text,
  current_status text,
  zoning text,
  land_acres numeric,
  building_sqft numeric,
  year_built integer,
  asking_price_usd numeric,
  lease_rate text,
  transaction_type text,
  source_confidence text not null default 'unverified',
  preliminary_score numeric not null default 0,
  preliminary_grade text,
  review_status text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists property_listings (
  id uuid primary key default gen_random_uuid(),
  site_id uuid not null references sites(id) on delete cascade,
  source_name text not null,
  source_url text not null,
  source_listing_id text,
  original_title text not null,
  translated_title_zh text,
  original_description text,
  translated_summary_zh text,
  broker_name text,
  broker_company text,
  broker_phone text,
  broker_email text,
  listing_status text,
  listed_at timestamptz,
  last_checked_at timestamptz not null default now(),
  raw_data_json jsonb not null default '{}'::jsonb
);

create table if not exists source_documents (
  id uuid primary key default gen_random_uuid(),
  site_id uuid references sites(id) on delete cascade,
  document_type text,
  file_name text,
  source_url text,
  language text,
  raw_text text,
  parsed_data_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists site_coordinates (
  id uuid primary key default gen_random_uuid(),
  site_id uuid not null references sites(id) on delete cascade,
  formatted_address text,
  latitude numeric,
  longitude numeric,
  geocoding_source text,
  confidence numeric,
  created_at timestamptz not null default now()
);

create table if not exists utilities (
  id uuid primary key default gen_random_uuid(),
  utility_name text not null,
  utility_type text not null default 'unknown',
  service_area text,
  website text,
  large_load_contact_name text,
  large_load_contact_email text,
  large_load_contact_phone text,
  economic_development_url text,
  source_url text,
  verification_status text not null default 'unknown'
);

create table if not exists substations (
  id uuid primary key default gen_random_uuid(),
  name text,
  latitude numeric,
  longitude numeric,
  owner text,
  voltage_kv numeric,
  substation_type text,
  status text,
  capacity_mva numeric,
  capacity_status text not null default 'unknown',
  source_url text,
  confidence_level text not null default 'unknown'
);

create table if not exists transmission_lines (
  id uuid primary key default gen_random_uuid(),
  name text,
  owner text,
  voltage_kv numeric,
  geometry jsonb,
  status text,
  source_url text,
  confidence_level text not null default 'unknown'
);

create table if not exists nearby_power_assets (
  id uuid primary key default gen_random_uuid(),
  site_id uuid not null references sites(id) on delete cascade,
  asset_type text not null,
  asset_id uuid,
  asset_name text,
  distance_miles numeric,
  voltage_kv numeric,
  owner text,
  relationship text,
  source_url text,
  confidence_level text not null default 'unknown',
  verification_status text not null default 'unknown',
  created_at timestamptz not null default now()
);

create table if not exists site_power_assessments (
  id uuid primary key default gen_random_uuid(),
  site_id uuid not null references sites(id) on delete cascade,
  nearest_substation_name text,
  nearest_substation_distance_miles numeric,
  nearest_transmission_line_name text,
  nearest_transmission_line_distance_miles numeric,
  highest_known_voltage_kv numeric,
  utility_name text,
  score numeric,
  grade text,
  reasons jsonb not null default '[]'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  verification_status text not null default 'unknown',
  created_at timestamptz not null default now()
);

create index if not exists idx_site_hunter_jobs_status on site_hunter_search_jobs(status);
create index if not exists idx_site_hunter_queries_job_id on site_hunter_generated_queries(job_id);
create index if not exists idx_discovered_sources_region on discovered_sources(state, county, city);
create index if not exists idx_source_regions_region on source_regions(state, county, city, zip_code);
create index if not exists idx_source_health_source_id on source_health(discovered_source_id);
create index if not exists idx_source_runs_job_id on search_source_runs(job_id);
create index if not exists idx_sites_region on sites(state, county, city, zip_code);
create index if not exists idx_property_listings_site_id on property_listings(site_id);
create index if not exists idx_nearby_power_assets_site_id on nearby_power_assets(site_id);
