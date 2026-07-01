create extension if not exists pgcrypto;

create table if not exists schema_migrations (
  version text primary key,
  applied_at timestamptz not null default now()
);

alter table hardware_scan_jobs
  add column if not exists generated_queries jsonb not null default '[]'::jsonb,
  add column if not exists scheduler_state jsonb;

alter table hardware_opportunities
  add column if not exists scan_job_id uuid references hardware_scan_jobs(id) on delete set null,
  add column if not exists subcategory text,
  add column if not exists canonical_url text,
  add column if not exists unique_key text,
  add column if not exists source_listing_id text,
  add column if not exists lot_number text,
  add column if not exists generation text,
  add column if not exists configuration text,
  add column if not exists quantity_status text not null default 'unknown',
  add column if not exists current_price numeric,
  add column if not exists current_total_cost numeric,
  add column if not exists buyer_premium text,
  add column if not exists buyer_premium_amount numeric,
  add column if not exists estimated_tax numeric,
  add column if not exists estimated_shipping numeric,
  add column if not exists estimated_landed_cost numeric,
  add column if not exists cost_per_unit numeric,
  add column if not exists cost_per_gb numeric,
  add column if not exists cost_confidence text not null default 'unknown',
  add column if not exists bid_count integer,
  add column if not exists condition text not null default 'unknown',
  add column if not exists working_status text not null default 'unknown',
  add column if not exists testing_status text not null default 'unknown',
  add column if not exists warranty_status text not null default 'unknown',
  add column if not exists listing_status text not null default 'unknown',
  add column if not exists end_time_verification text not null default 'unknown',
  add column if not exists end_time_raw text,
  add column if not exists end_time_timezone_raw text,
  add column if not exists end_time_utc timestamptz,
  add column if not exists end_time_user_timezone text,
  add column if not exists timezone_needs_verification boolean not null default false,
  add column if not exists countdown_raw_text text,
  add column if not exists countdown_captured_at timestamptz,
  add column if not exists calculated_end_time timestamptz,
  add column if not exists calculated_timezone text,
  add column if not exists calculation_confidence text,
  add column if not exists last_status_check_at timestamptz,
  add column if not exists next_status_check_at timestamptz,
  add column if not exists status_check_attempts integer not null default 0,
  add column if not exists status_check_result text,
  add column if not exists status_check_error text,
  add column if not exists automated_result jsonb not null default '{}'::jsonb,
  add column if not exists manual_result jsonb not null default '{}'::jsonb,
  add column if not exists final_status text not null default 'unknown',
  add column if not exists manual_end_time timestamptz,
  add column if not exists manual_timezone text,
  add column if not exists manual_status text,
  add column if not exists manual_notes text,
  add column if not exists verified_by text,
  add column if not exists verified_at timestamptz,
  add column if not exists page_type text not null default 'specific_listing',
  add column if not exists classification_reason text,
  add column if not exists component_completeness text not null default 'unknown',
  add column if not exists component_details jsonb not null default '{}'::jsonb,
  add column if not exists recommendation text not null default 'information_incomplete',
  add column if not exists recommendation_reasons jsonb not null default '[]'::jsonb,
  add column if not exists last_checked_at timestamptz,
  add column if not exists unavailable_reason text,
  add column if not exists needs_manual_review boolean not null default false,
  add column if not exists confidence_level text not null default 'needs_verification',
  add column if not exists change_types jsonb not null default '[]'::jsonb,
  add column if not exists score_reasons jsonb not null default '[]'::jsonb,
  add column if not exists raw_title text,
  add column if not exists raw_description text,
  add column if not exists raw_data_json jsonb not null default '{}'::jsonb,
  add column if not exists raw_data jsonb not null default '{}'::jsonb;

create unique index if not exists hardware_opportunities_unique_key_idx
  on hardware_opportunities(unique_key)
  where unique_key is not null;

create index if not exists hardware_opportunities_listing_status_idx on hardware_opportunities(listing_status);
create index if not exists hardware_opportunities_final_status_idx on hardware_opportunities(final_status);
create index if not exists hardware_opportunities_end_time_idx on hardware_opportunities(end_time_utc);
create index if not exists hardware_opportunities_next_status_check_idx on hardware_opportunities(next_status_check_at);

create table if not exists hardware_listing_snapshots (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  scan_job_id uuid references hardware_scan_jobs(id) on delete set null,
  listing_status text,
  quantity integer,
  unit_price numeric,
  total_price numeric,
  current_price numeric,
  bid_count integer,
  raw_data jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now()
);

create table if not exists hardware_status_history (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  old_status text,
  new_status text,
  old_end_time timestamptz,
  new_end_time timestamptz,
  change_type text,
  source text,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table hardware_price_history
  add column if not exists old_unit_price numeric,
  add column if not exists new_unit_price numeric,
  add column if not exists old_total_price numeric,
  add column if not exists new_total_price numeric,
  add column if not exists listing_status text;

create table if not exists hardware_supplier_leads (
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

create table if not exists manual_verification_records (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references hardware_opportunities(id) on delete cascade,
  manual_status text,
  manual_end_time timestamptz,
  manual_timezone text,
  manual_notes text,
  verified_by text,
  verified_at timestamptz,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists hardware_scheduler_state (
  id text primary key default 'daily_scheduler',
  status text not null default 'paused',
  enabled boolean not null default false,
  is_job_running boolean not null default false,
  last_run_at timestamptz,
  next_run_at timestamptz,
  current_job_id uuid,
  last_job_id uuid,
  last_error text,
  daily_report_hour integer not null default 8,
  timezone text not null default 'America/Los_Angeles',
  restored_from_disk boolean not null default false,
  last_result text,
  failure_count integer not null default 0,
  updated_at timestamptz not null default now()
);

insert into hardware_scheduler_state(id)
values ('daily_scheduler')
on conflict (id) do nothing;

alter table telegram_delivery_logs
  add column if not exists telegram_message_id text;

create unique index if not exists telegram_delivery_unique_idx
  on telegram_delivery_logs(scan_job_id, report_type, message_hash);

insert into schema_migrations(version)
values ('20260701_hardware_hunter_v23_persistence')
on conflict (version) do nothing;
