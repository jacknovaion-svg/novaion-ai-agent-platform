alter table hardware_scan_jobs
  add column if not exists scan_lane text not null default 'fast';

alter table hardware_source_runs
  add column if not exists scan_lane text not null default 'fast',
  add column if not exists raw_results integer not null default 0,
  add column if not exists matched_state_results integer not null default 0,
  add column if not exists state_mismatch_results integer not null default 0,
  add column if not exists location_unknown_results integer not null default 0,
  add column if not exists filtered_out_results integer not null default 0,
  add column if not exists detected_states jsonb not null default '[]'::jsonb,
  add column if not exists state_match_status text,
  add column if not exists filter_reason text,
  add column if not exists duration_ms integer,
  add column if not exists timeout_seconds integer,
  add column if not exists retry_count integer not null default 0,
  add column if not exists cache_hit boolean not null default false,
  add column if not exists current_opportunities integer not null default 0,
  add column if not exists needs_review integer not null default 0,
  add column if not exists history integer not null default 0;

create table if not exists hardware_worker_runs (
  id uuid primary key default gen_random_uuid(),
  scan_job_id uuid references hardware_scan_jobs(id) on delete cascade,
  source_name text not null,
  category text,
  state_code text,
  query text,
  scan_lane text not null default 'fast',
  started_at timestamptz,
  finished_at timestamptz,
  duration_ms integer,
  status text not null default 'pending',
  raw_results integer not null default 0,
  matched_state_results integer not null default 0,
  state_mismatch_results integer not null default 0,
  location_unknown_results integer not null default 0,
  specific_listings integer not null default 0,
  current_opportunities integer not null default 0,
  needs_review integer not null default 0,
  history integer not null default 0,
  error_message text,
  timeout_seconds integer,
  retry_count integer not null default 0,
  cache_hit boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_hardware_worker_runs_job
  on hardware_worker_runs(scan_job_id, scan_lane, status);

create index if not exists idx_hardware_worker_runs_source
  on hardware_worker_runs(source_name, status, created_at desc);

create table if not exists hardware_query_cache (
  cache_key text primary key,
  source_name text not null,
  category text,
  state_code text,
  query_normalized text not null,
  scan_depth text not null default 'standard',
  scan_lane text not null default 'fast',
  raw_results jsonb not null default '[]'::jsonb,
  result_count integer not null default 0,
  cached_at timestamptz not null default now(),
  expires_at timestamptz not null,
  hit_count integer not null default 0,
  last_hit_at timestamptz
);

create index if not exists idx_hardware_query_cache_expiry
  on hardware_query_cache(expires_at);

create table if not exists hardware_source_health (
  source_name text primary key,
  enabled boolean not null default true,
  scan_lane text not null default 'fast',
  total_runs integer not null default 0,
  success_runs integer not null default 0,
  zero_result_runs integer not null default 0,
  failed_runs integer not null default 0,
  timeout_runs integer not null default 0,
  raw_results integer not null default 0,
  matched_state_results integer not null default 0,
  state_mismatch_results integer not null default 0,
  location_unknown_results integer not null default 0,
  specific_listings integer not null default 0,
  current_opportunities integer not null default 0,
  needs_review integer not null default 0,
  history integer not null default 0,
  avg_duration_ms numeric not null default 0,
  result_rate numeric not null default 0,
  specific_listing_rate numeric not null default 0,
  state_match_rate numeric not null default 0,
  needs_review_rate numeric not null default 0,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  health_status text not null default 'low_yield',
  updated_at timestamptz not null default now()
);

create table if not exists hardware_query_performance (
  query_key text primary key,
  source_name text not null,
  category text,
  state_code text,
  query_template text,
  scan_lane text not null default 'fast',
  total_runs integer not null default 0,
  consecutive_zero_results integer not null default 0,
  consecutive_failures integer not null default 0,
  raw_results integer not null default 0,
  specific_listings integer not null default 0,
  priority_status text not null default 'normal',
  last_run_at timestamptz,
  updated_at timestamptz not null default now()
);
