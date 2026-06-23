alter table search_jobs
  add column if not exists search_anchor jsonb,
  add column if not exists search_radius_miles numeric;

alter table search_results
  add column if not exists distance_to_search_anchor_miles numeric,
  add column if not exists search_anchor_distance_basis text;

create index if not exists idx_search_results_anchor_distance
  on search_results(distance_to_search_anchor_miles);

