create table if not exists site_truth_verifications (
  id uuid primary key default gen_random_uuid(),
  site_id uuid not null,
  automatic_result_summary text,
  land_id_result_summary text,
  official_source_summary text,
  conflict_summary text,
  final_verification_status text not null default 'unverified'
    check (final_verification_status in (
      'official_verified',
      'manual_map_confirmed',
      'source_confirmed',
      'estimated',
      'conflicting',
      'unverified'
    )),
  verified_at timestamptz,
  verified_by text,
  notes text,
  field_sources jsonb not null default '{}'::jsonb,
  conflicting_fields jsonb not null default '[]'::jsonb,
  capacity_status text not null default 'unknown',
  verification_warning text not null default '真实性验证不代表Utility容量、接入许可、接入成本或送电时间已经确认。',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_site_truth_verifications_site_id
  on site_truth_verifications(site_id);

