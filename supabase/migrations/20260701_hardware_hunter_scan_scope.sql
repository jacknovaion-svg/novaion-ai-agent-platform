alter table hardware_opportunities
  add column if not exists first_seen_job_id uuid,
  add column if not exists last_seen_job_id uuid,
  add column if not exists last_updated_job_id uuid;

update hardware_opportunities
set
  first_seen_job_id = coalesce(first_seen_job_id, scan_job_id),
  last_seen_job_id = coalesce(last_seen_job_id, scan_job_id),
  last_updated_job_id = coalesce(last_updated_job_id, scan_job_id)
where scan_job_id is not null
  and (first_seen_job_id is null or last_seen_job_id is null or last_updated_job_id is null);

create index if not exists hardware_opportunities_last_seen_job_idx
  on hardware_opportunities(last_seen_job_id);

create index if not exists hardware_opportunities_last_updated_job_idx
  on hardware_opportunities(last_updated_job_id);

insert into schema_migrations(version)
values ('20260701_hardware_hunter_scan_scope')
on conflict (version) do nothing;
