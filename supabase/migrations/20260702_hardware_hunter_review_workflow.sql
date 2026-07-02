alter table manual_verification_records
  add column if not exists previous_status text,
  add column if not exists review_action text,
  add column if not exists manual_fields_json jsonb not null default '{}'::jsonb,
  add column if not exists notes text,
  add column if not exists reviewed_by text,
  add column if not exists reviewed_at timestamptz;

create index if not exists manual_verification_records_reviewed_at_idx
  on manual_verification_records(reviewed_at);

insert into schema_migrations(version)
values ('20260702_hardware_hunter_review_workflow')
on conflict (version) do nothing;
