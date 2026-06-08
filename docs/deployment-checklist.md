# Deployment Requirements Checklist

This checklist maps the requested deployment requirements to concrete files in the project.

| Requirement | Status | File / Setting |
| --- | --- | --- |
| Frontend Next.js deploys to Vercel | Ready | `vercel.json`, `apps/web/package.json`, `docs/deployment.md` |
| Backend FastAPI + Playwright deploys to Render / Railway / Fly.io | Ready | `apps/api/Dockerfile`, `render.yaml`, `apps/api/railway.json`, `apps/api/fly.toml.example` |
| Database uses Supabase PostgreSQL | Ready | `supabase/schema.sql`, `supabase/seed.sql`, `docs/deployment.md` |
| Frontend calls backend through `NEXT_PUBLIC_API_BASE_URL` | Ready | `apps/web/.env.example`, `apps/web/lib/api.ts` |
| Backend connects to Supabase through env var | Ready | `apps/api/.env.example`, `apps/api/app/db/repository.py` |
| Local run tutorial | Ready | `README.md`, `docs/deployment.md` |
| Vercel frontend deployment tutorial | Ready | `docs/deployment.md` |
| Render/Railway backend deployment tutorial | Ready | `docs/deployment.md` |
| Fly.io backend deployment option | Ready | `docs/deployment.md`, `apps/api/fly.toml.example` |
| Supabase database initialization tutorial | Ready | `docs/deployment.md` |
| `.env.example` files | Ready | `apps/api/.env.example`, `apps/web/.env.example` |
| Test account and demo data | Ready | `supabase/seed.sql`, `README.md`, `docs/deployment.md` |
| Customer can access and test through public webpage | Ready after deploy | Share Vercel URL; set backend CORS and frontend API env |
| Frontend/backend decoupled | Ready | Separate `apps/web` and `apps/api`; API URL configured by env |

## Demo Account

```text
Email: demo@novaion.ai
Password: not required in V1
```

V1 does not include a login flow. The demo account is seeded for language preference, saved searches, and alert examples.

## Public Test URL Rule

After deployment, send customers only the Vercel frontend URL:

```text
https://YOUR-VERCEL-DOMAIN.vercel.app
```

The backend URL is used by the frontend through:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR-BACKEND-DOMAIN/api/v1
```
