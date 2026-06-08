# NOVAION AI Agent Platform

Unified AI search, procurement, and resource discovery platform.

V1 launches with **Hardware Hunter**, an agent for discovering computer hardware inventory and pricing across online and local sources. The architecture is intentionally generic so future agents can be added without rewriting the platform:

- Hardware Hunter
- Power Hunter
- Land Hunter
- Supplier Hunter
- Data Center Hunter

## Tech Stack

- Frontend: Next.js App Router, TypeScript
- Backend: FastAPI, Python
- Data: PostgreSQL or Supabase-compatible schema
- Automation: Playwright-ready adapter layer
- Deployment: Vercel frontend, Render/Railway/Fly.io backend, Supabase PostgreSQL

## Project Structure

```text
.
├── apps
│   ├── api
│   │   ├── app
│   │   │   ├── agents
│   │   │   ├── adapters
│   │   │   ├── core
│   │   │   ├── db
│   │   │   ├── models
│   │   │   ├── routers
│   │   │   ├── services
│   │   │   └── main.py
│   │   ├── requirements.txt
│   │   └── .env.example
│   └── web
│       ├── app
│       ├── components
│       ├── lib
│       ├── package.json
│       └── .env.example
├── docs
│   └── architecture.md
├── packages
│   └── shared
│       ├── i18n
│       └── types
└── supabase
    ├── schema.sql
    └── seed.sql
```

## Quick Start

### Backend

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

## Environment Variables

Backend: see [apps/api/.env.example](apps/api/.env.example)

Frontend: see [apps/web/.env.example](apps/web/.env.example)

The frontend and backend are intentionally decoupled:

- Frontend calls `NEXT_PUBLIC_API_BASE_URL`
- Backend connects to Supabase through `DATABASE_URL`
- Backend CORS is controlled with `API_CORS_ORIGINS`

## Database

Run [supabase/schema.sql](supabase/schema.sql) in Supabase SQL Editor or any PostgreSQL database.

Optional sample data:

```sql
\i supabase/seed.sql
```

Demo account:

```text
Email: demo@novaion.ai
Password: not required in V1
```

V1 has no login flow yet. The demo user seeds language preference, saved searches, and alert examples.

## Deployment

Full deployment guide: [docs/deployment.md](docs/deployment.md)

Deployment requirements checklist: [docs/deployment-checklist.md](docs/deployment-checklist.md)

Public customer testing architecture:

- Next.js frontend on Vercel
- FastAPI + Playwright backend on Render/Railway/Fly.io
- Supabase PostgreSQL database
- Frontend API URL configured by `NEXT_PUBLIC_API_BASE_URL`
- Backend database URL configured by `DATABASE_URL`

## V1 Scope

Implemented foundation:

- Generic Agent Center
- Hardware Hunter agent
- Adapter-based Search Engine Center
- Best Buy and Newegg Playwright-ready adapters
- CDW, Micro Center, and Provantage placeholder adapters
- Recommendation score: inventory 40%, price 30%, distance 20%, promotion 10%
- Search page
- Results table
- Result detail page
- Saved searches
- Alert Center placeholder
- English and Chinese i18n, with Spanish reserved
- User language preference API

## Notes

The search adapter layer is designed so Playwright scraping can be swapped for official APIs later. Each source implements:

```python
search(query, options)
parse_results(raw_data)
normalize_result(parsed_data)
```

V1 uses resilient page extraction and sample fallback data when live scraping is blocked or not configured. This keeps the product usable during early development while preserving the real adapter contract.
