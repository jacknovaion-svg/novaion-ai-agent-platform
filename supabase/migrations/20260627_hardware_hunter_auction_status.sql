alter table hardware_opportunities
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
  add column if not exists verified_at timestamptz;

create index if not exists hardware_opportunities_end_time_idx on hardware_opportunities(end_time_utc);
create index if not exists hardware_opportunities_final_status_idx on hardware_opportunities(final_status);
create index if not exists hardware_opportunities_next_status_check_idx on hardware_opportunities(next_status_check_at);
