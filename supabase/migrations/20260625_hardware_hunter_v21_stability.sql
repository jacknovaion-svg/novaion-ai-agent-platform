alter table hardware_opportunities
  add column if not exists canonical_url text,
  add column if not exists page_type text not null default 'specific_listing',
  add column if not exists classification_reason text;

alter table hardware_listings
  add column if not exists page_type text not null default 'irrelevant',
  add column if not exists classification_reason text;

alter table hardware_scan_jobs
  add column if not exists scheduler_state jsonb;

alter table telegram_delivery_logs
  add column if not exists telegram_message_id text;

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
  updated_at timestamptz not null default now()
);

insert into hardware_scheduler_state(id)
values ('daily_scheduler')
on conflict (id) do nothing;
