alter table if exists sites
  add column if not exists standardized_address text,
  add column if not exists geocoding_source text,
  add column if not exists geocoding_confidence numeric,
  add column if not exists power_address_status text,
  add column if not exists land_id_review_status text not null default 'not_reviewed',
  add column if not exists land_id_map_url text,
  add column if not exists parcel_id text,
  add column if not exists owner_name text,
  add column if not exists owner_mailing_address text,
  add column if not exists parcel_acres numeric,
  add column if not exists manual_notes text,
  add column if not exists land_id_reviewed_at timestamptz;

alter table if exists transmission_lines
  add column if not exists line_id text,
  add column if not exists source_name text,
  add column if not exists dataset_version text,
  add column if not exists updated_at timestamptz not null default now();

alter table if exists nearby_power_assets
  add column if not exists latitude numeric,
  add column if not exists longitude numeric,
  add column if not exists geometry jsonb,
  add column if not exists operator text,
  add column if not exists source_name text,
  add column if not exists dataset_version text,
  add column if not exists checked_at timestamptz not null default now();

alter table if exists site_power_assessments
  add column if not exists address_status text,
  add column if not exists raw_address text,
  add column if not exists standardized_address text,
  add column if not exists latitude numeric,
  add column if not exists longitude numeric,
  add column if not exists geocoding_source text,
  add column if not exists geocoding_confidence numeric,
  add column if not exists capacity_status text not null default 'unknown',
  add column if not exists assessment_warning text,
  add column if not exists checked_at timestamptz not null default now();

create table if not exists utility_candidates (
  id uuid primary key default gen_random_uuid(),
  site_id uuid references sites(id) on delete cascade,
  likely_utility text,
  utility_type text not null default 'unknown',
  evidence text,
  source_url text,
  confidence_level text not null default 'unknown',
  status text not null default 'unknown',
  created_at timestamptz not null default now()
);

create table if not exists power_source_records (
  id uuid primary key default gen_random_uuid(),
  site_id uuid references sites(id) on delete cascade,
  source_name text not null,
  source_url text,
  source_type text,
  generated_query text,
  confidence_level text not null default 'unknown',
  discovered_at timestamptz not null default now()
);

create index if not exists idx_power_assets_site_id_checked_at on nearby_power_assets(site_id, checked_at);
create index if not exists idx_utility_candidates_site_id on utility_candidates(site_id);
create index if not exists idx_power_source_records_site_id on power_source_records(site_id);
