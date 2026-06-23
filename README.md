# NOVAION AI Agent Platform

Unified AI search, procurement, and resource discovery platform.

V1 launches with **Hardware Hunter**, an agent for discovering computer hardware inventory and pricing across online and local sources. The architecture is intentionally generic so future agents can be added without rewriting the platform:

- Hardware Hunter
- Site Hunter
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
- Site Hunter agent
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

## Site Hunter V1 Phase 1

Site Hunter is implemented as an independent enabled agent. It does not modify Hardware Hunter core search logic.

Implemented:

- Chinese natural-language requirement intake
- Structured site-search criteria for state, county, city, ZIP, acreage, budget, target MW, and project use
- Rule-based Chinese requirement parser with audit fields
- U.S. industrial real-estate English term expansion
- Multi-query English search generation
- `SourceDiscoveryService` for national, local brokerage, economic-development, industrial-park, and utility source discovery
- Background search-job API with per-source run status
- `WebSearchPropertyAdapter`
- `ManualImportAdapter`
- `Century21CommercialAdapter`
- `CrexiSearchAdapter` as best-effort search-backed commercial source discovery
- Property normalization, basic dedupe, missing-field labeling, source confidence, and Chinese summaries
- Result quality classification: `specific_listing`, `listing_collection`, `source_page`, and `irrelevant`
- Result quality stats and filtering for state, known acreage, known budget, irrelevant pages, and duplicates
- V1.2 local power screening: address geocoding, OpenStreetMap power assets, optional local transmission GeoJSON, likely utility estimate, and Land id manual review fields
- Site Hunter frontend pages: search, progress, results, and detail/review
- Supabase schema for discovered sources, site listings, source documents, coordinates, and reserved power-assessment tables

Real data status:

- Public Web Search: real public result pages and original links
- Century 21 Commercial: real public commercial real-estate state pages
- Crexi: adapter present, search-engine-backed, may return zero results depending on search availability
- Manual Import: real user-provided URLs/text only

Not implemented in this phase:

- Utility capacity verification
- Available MW determination
- Complex grid GIS
- Automated broker or utility outreach
- Email sending or CRM workflows

## Notes

The search adapter layer is designed so Playwright scraping or public web search can be swapped for official APIs later. Hardware sources implement:

```python
search(query, options)
parse_results(raw_data)
normalize_result(parsed_data)
```

Site Hunter does not generate fake property listings. Missing price, acreage, zoning, address, or broker fields are marked as unknown instead of guessed.

For local-only Site Hunter testing, use `LOCAL_TESTING.md`. The intended local URLs are:

- Frontend: `http://localhost:3000/site-hunter`
- Backend: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
