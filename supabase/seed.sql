insert into agents (name, type, enabled) values
  ('Hardware Hunter', 'hardware_hunter', true),
  ('Site Hunter', 'site_hunter', true),
  ('Power Hunter', 'power_hunter', false),
  ('Land Hunter', 'land_hunter', false),
  ('Supplier Hunter', 'supplier_hunter', false),
  ('Data Center Hunter', 'data_center_hunter', false)
on conflict (type) do update set
  name = excluded.name,
  enabled = excluded.enabled;

insert into users (email, language) values
  ('demo@novaion.ai', 'en')
on conflict (email) do nothing;

with demo_user as (
  select id from users where email = 'demo@novaion.ai' limit 1
)
insert into saved_searches (user_id, query, quantity, zip_code, radius, sources)
select id, 'RTX 5090', 1, '94085', 25, array['best_buy', 'newegg']
from demo_user
where not exists (
  select 1 from saved_searches
  where query = 'RTX 5090'
    and user_id = (select id from demo_user)
);

with demo_user as (
  select id from users where email = 'demo@novaion.ai' limit 1
),
demo_search as (
  select id from saved_searches
  where user_id = (select id from demo_user)
    and query = 'RTX 5090'
  limit 1
)
insert into alerts (user_id, saved_search_id, alert_type, enabled)
select (select id from demo_user), id, 'price_drop', true
from demo_search
where not exists (
  select 1 from alerts
  where saved_search_id = (select id from demo_search)
    and alert_type = 'price_drop'
);
