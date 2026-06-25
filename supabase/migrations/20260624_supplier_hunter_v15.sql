create table if not exists supplier_search_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  natural_language_query_zh text,
  parsed_criteria jsonb,
  state_job jsonb,
  region_subjobs jsonb not null default '[]'::jsonb,
  status text not null default 'created',
  quality_stats jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists suppliers (
  supplier_id uuid primary key default gen_random_uuid(),
  search_job_id uuid references supplier_search_jobs(id) on delete cascade,
  company_name text not null,
  company_type text,
  supplier_category text not null default 'D',
  website text,
  address text,
  city text,
  county text,
  state text,
  zip_code text,
  latitude numeric,
  longitude numeric,
  phone text,
  email text,
  contact_name text,
  service_area text,
  r2_certified text not null default 'unknown',
  e_stewards_certified text not null default 'unknown',
  naid_aaa_certified text not null default 'unknown',
  data_center_decommissioning boolean not null default false,
  enterprise_itad boolean not null default false,
  asset_remarketing boolean not null default false,
  direct_asset_purchasing boolean not null default false,
  server_recycling boolean not null default false,
  computer_refurbishing boolean not null default false,
  bulk_sales boolean not null default false,
  wholesale boolean not null default false,
  equipment_types jsonb not null default '[]'::jsonb,
  minimum_order text,
  pickup_available boolean,
  shipping_available boolean,
  source_name text not null,
  source_url text not null,
  last_checked_at timestamptz not null default now(),
  confidence_level text not null default 'needs_verification',
  review_status text not null default 'new',
  notes text,
  supplier_score numeric not null default 0,
  score_reasons jsonb not null default '[]'::jsonb,
  quality_flags jsonb not null default '[]'::jsonb,
  raw_data_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_suppliers_state_city on suppliers(state, city);
create index if not exists idx_suppliers_category_score on suppliers(supplier_category, supplier_score desc);
create index if not exists idx_suppliers_review_status on suppliers(review_status);

