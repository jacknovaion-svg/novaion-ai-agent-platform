alter table search_jobs
  add column if not exists job_mode text default 'standard_search',
  add column if not exists state_job jsonb,
  add column if not exists region_subjobs jsonb;

alter table search_results
  add column if not exists state_region_name text,
  add column if not exists state_region_type text;

create index if not exists idx_search_results_state_region_name
  on search_results(state_region_name);

