create extension if not exists "pgcrypto";

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text unique,
  language text not null default 'en' check (language in ('en', 'zh', 'es')),
  created_at timestamptz not null default now()
);

create table if not exists agents (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text not null unique,
  enabled boolean not null default false
);

create table if not exists search_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete set null,
  agent_type text not null,
  query text not null,
  quantity integer not null default 1,
  zip_code text,
  radius integer,
  mode text not null default 'all' check (mode in ('local', 'online', 'all')),
  status text not null default 'pending' check (status in ('pending', 'running', 'completed', 'failed')),
  created_at timestamptz not null default now()
);

create table if not exists search_results (
  id uuid primary key default gen_random_uuid(),
  search_job_id uuid not null references search_jobs(id) on delete cascade,
  source text not null,
  product_name text not null,
  brand text,
  model text,
  store_name text,
  address text,
  distance numeric,
  price numeric,
  promotion text,
  inventory_status text,
  pickup_available boolean not null default false,
  shipping_available boolean not null default false,
  product_url text,
  recommendation_score numeric not null default 0,
  updated_at timestamptz not null default now()
);

create table if not exists saved_searches (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  query text not null,
  quantity integer not null default 1,
  zip_code text,
  radius integer,
  sources text[] not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  saved_search_id uuid references saved_searches(id) on delete cascade,
  alert_type text not null check (alert_type in ('email', 'telegram', 'price_drop', 'back_in_stock')),
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_search_jobs_user_id on search_jobs(user_id);
create index if not exists idx_search_results_job_id on search_results(search_job_id);
create index if not exists idx_saved_searches_user_id on saved_searches(user_id);
create index if not exists idx_alerts_user_id on alerts(user_id);
