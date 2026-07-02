alter table hardware_source_runs
  add column if not exists expanded_query text,
  add column if not exists query_template_id text,
  add column if not exists query_template text,
  add column if not exists state_code text,
  add column if not exists state_name text,
  add column if not exists scan_depth text not null default 'standard',
  add column if not exists specific_listing_count integer not null default 0,
  add column if not exists zero_result_reason text;

create index if not exists idx_hardware_source_runs_template
  on hardware_source_runs(query_template_id, state_code, scan_depth);

insert into schema_migrations(version)
values ('20260702_hardware_hunter_v25a_query_engine')
on conflict (version) do nothing;
