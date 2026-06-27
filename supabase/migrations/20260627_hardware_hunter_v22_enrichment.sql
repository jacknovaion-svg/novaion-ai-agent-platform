create table if not exists hardware_scan_jobs (
  id uuid primary key,
  mode text not null,
  status text not null,
  categories jsonb not null default '[]'::jsonb,
  states jsonb not null default '[]'::jsonb,
  generated_queries jsonb not null default '[]'::jsonb,
  quality_stats jsonb not null default '{}'::jsonb,
  report jsonb,
  error_message text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  completed_at timestamptz
);

create table if not exists hardware_source_runs (
  id uuid primary key,
  scan_job_id uuid references hardware_scan_jobs(id) on delete cascade,
  source_name text not null,
  adapter_type text not null,
  query text,
  category text,
  status text not null,
  result_count integer not null default 0,
  started_at timestamptz,
  completed_at timestamptz,
  error_message text
);

create table if not exists hardware_opportunities (
  id uuid primary key,
  scan_job_id uuid references hardware_scan_jobs(id) on delete set null,
  source text not null,
  source_url text not null,
  canonical_url text,
  source_listing_id text,
  lot_number text,
  category text not null,
  title text not null,
  manufacturer text,
  model text,
  part_number text,
  quantity integer,
  unit_price numeric,
  total_price numeric,
  current_price numeric,
  current_total_cost numeric,
  cost_per_unit numeric,
  cost_per_gb numeric,
  cost_confidence text not null default 'unknown',
  bid_count integer,
  condition text,
  listing_status text not null default 'unknown',
  component_completeness text not null default 'unknown',
  recommendation text not null default 'information_incomplete',
  recommendation_reasons jsonb not null default '[]'::jsonb,
  location_city text,
  location_state text,
  zip_code text,
  pickup_only boolean,
  shipping_available boolean,
  seller_name text,
  opportunity_score numeric not null default 0,
  risk_score numeric not null default 0,
  risk_flags jsonb not null default '[]'::jsonb,
  needs_manual_review boolean not null default false,
  last_checked_at timestamptz,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists hardware_listing_snapshots (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  listing_status text,
  quantity integer,
  unit_price numeric,
  total_price numeric,
  current_price numeric,
  bid_count integer,
  raw_data jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now()
);

create table if not exists hardware_price_history (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  source_url text not null,
  unit_price numeric,
  total_price numeric,
  quantity integer,
  listing_status text,
  observed_at timestamptz not null default now()
);

create table if not exists supplier_leads (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  company_type text,
  website text,
  city text,
  state text,
  phone text,
  email text,
  certifications jsonb not null default '[]'::jsonb,
  data_center_decommissioning boolean,
  enterprise_itad boolean,
  asset_remarketing boolean,
  bulk_sales boolean,
  equipment_types jsonb not null default '[]'::jsonb,
  source_url text,
  confidence text not null default 'needs_verification',
  recommended_contact_reason text,
  review_status text not null default 'needs_review',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists telegram_delivery_logs (
  id uuid primary key,
  scan_job_id uuid references hardware_scan_jobs(id) on delete set null,
  report_type text not null,
  message_hash text not null,
  status text not null,
  chat_id text,
  telegram_message_id text,
  error_message text,
  sent_at timestamptz,
  created_at timestamptz not null
);

create table if not exists scheduler_state (
  id text primary key,
  payload jsonb not null,
  updated_at timestamptz not null default now()
);

create index if not exists hardware_opportunities_listing_status_idx on hardware_opportunities(listing_status);
create index if not exists hardware_opportunities_category_idx on hardware_opportunities(category);
create index if not exists hardware_opportunities_canonical_url_idx on hardware_opportunities(canonical_url);
