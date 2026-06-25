create table if not exists hardware_scan_jobs (
  id uuid primary key default gen_random_uuid(),
  mode text not null default 'both',
  status text not null default 'created',
  categories jsonb not null default '[]'::jsonb,
  states jsonb not null default '[]'::jsonb,
  quality_stats jsonb not null default '{}'::jsonb,
  report jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists hardware_sources (
  id uuid primary key default gen_random_uuid(),
  source_name text not null,
  source_type text not null,
  domain text,
  adapter_type text not null,
  status text not null default 'enabled',
  trust_level text not null default 'public_search_discovery',
  last_success_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists hardware_source_runs (
  id uuid primary key default gen_random_uuid(),
  scan_job_id uuid references hardware_scan_jobs(id) on delete cascade,
  source_name text not null,
  adapter_type text not null,
  query text,
  category text,
  status text not null default 'pending',
  result_count integer not null default 0,
  error_message text,
  started_at timestamptz,
  completed_at timestamptz
);

create table if not exists hardware_opportunities (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  subcategory text,
  title text not null,
  manufacturer text,
  model text,
  part_number text,
  generation text,
  configuration text,
  quantity integer,
  quantity_status text not null default 'unknown',
  unit_price numeric,
  total_price numeric,
  condition text not null default 'unknown',
  working_status text not null default 'unknown',
  testing_status text not null default 'unknown',
  warranty_status text not null default 'unknown',
  location_city text,
  location_state text,
  zip_code text,
  pickup_only boolean,
  shipping_available boolean,
  auction_end_time timestamptz,
  seller_name text,
  seller_type text not null default 'unknown',
  source text not null,
  source_url text not null,
  source_listing_id text,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_changed_at timestamptz,
  status text not null default 'needs_verification',
  confidence_level text not null default 'needs_verification',
  risk_flags jsonb not null default '[]'::jsonb,
  change_types jsonb not null default '[]'::jsonb,
  opportunity_score numeric not null default 0,
  risk_score numeric not null default 0,
  score_reasons jsonb not null default '[]'::jsonb,
  raw_title text not null,
  raw_description text,
  raw_data_json jsonb not null default '{}'::jsonb,
  unique_key text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists hardware_opportunities_unique_key_idx
  on hardware_opportunities(unique_key)
  where unique_key is not null;

create table if not exists hardware_listings (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  scan_job_id uuid references hardware_scan_jobs(id) on delete set null,
  source text not null,
  source_url text not null,
  source_listing_id text,
  original_title text not null,
  original_description text,
  raw_data_json jsonb not null default '{}'::jsonb,
  fetched_at timestamptz not null default now()
);

create table if not exists hardware_lots (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  lot_number text,
  lot_title text,
  quantity integer,
  unit_price numeric,
  total_price numeric,
  auction_end_time timestamptz,
  raw_data_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists hardware_price_history (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  opportunity_key text,
  source_url text not null,
  unit_price numeric,
  total_price numeric,
  quantity integer,
  status text,
  observed_at timestamptz not null default now()
);

create table if not exists hardware_alerts (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  alert_type text not null,
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists telegram_delivery_logs (
  id uuid primary key default gen_random_uuid(),
  scan_job_id uuid references hardware_scan_jobs(id) on delete cascade,
  report_type text not null default 'daily_hardware_report',
  message_hash text not null,
  status text not null,
  chat_id text,
  error_message text,
  sent_at timestamptz,
  created_at timestamptz not null default now(),
  unique(scan_job_id, report_type, message_hash)
);
