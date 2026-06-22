# NOVAION Site Hunter V1 Local Testing

This stage is local-only. Do not deploy Render or Vercel for this verification pass.

## Local URLs

- Frontend: http://localhost:3000/site-hunter
- Backend: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

## Environment

Backend local defaults:

```bash
API_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SITE_HUNTER_SEARCH_PROVIDER=duckduckgo_html
SEARCH_ENGINE_API_KEY=
```

Frontend local defaults:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_DEFAULT_USER_EMAIL=demo@novaion.ai
```

No search API key is required for the default V1 local search path. Site Hunter uses public DuckDuckGo HTML discovery plus source adapters. `SEARCH_ENGINE_API_KEY` is reserved for a future official/paid search provider. Crexi is clearly marked as search-engine-backed discovery only; it is not an official Crexi API.

## One Command Start

```bash
bash scripts/dev-local.sh
```

The script starts:

- FastAPI on `127.0.0.1:8000`
- Next.js on `localhost:3000`
- Frontend API base set to `http://127.0.0.1:8000/api/v1`

## Manual Start

Terminal 1:

```bash
cd apps/api
API_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm --workspace apps/web run dev
```

If this Mac does not have system Node/npm, use the bundled Codex runtime path or run `bash scripts/dev-local.sh`.

## Test Input

```text
帮我搜索德州和乔治亚州20英亩以上的旧制造工厂或工业土地，预算1000万美元以内，用于未来建设50MW AI数据中心。
```

Expected parsed fields:

- States: `Texas`, `Georgia`
- Minimum land: `20 acres`
- Maximum budget: `$10,000,000`
- Target load: `50 MW`
- Property types: `former manufacturing facility`, `manufacturing facility`, `industrial land`

Expected result behavior:

- Generated English queries are shown on the progress page.
- Source run status is shown per adapter.
- `Public Web Search`, `Manual Import`, and `Century 21 Commercial` run independently.
- `Crexi` may return zero results and is labeled as search-engine-backed discovery.
- At least one real candidate should include an original English title, original link, source name, Chinese summary, and unknown markers for missing fields.
- Missing address, acreage, building size, price, or zoning fields must display as `unknown`.

## API Smoke Test

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/site-hunter/search-jobs \
  -H 'Content-Type: application/json' \
  -d '{"natural_language_query_zh":"帮我搜索德州和乔治亚州20英亩以上的旧制造工厂或工业土地，预算1000万美元以内，用于未来建设50MW AI数据中心。","max_results_per_source":5}'
```

Use the returned `id`:

```bash
curl -s http://127.0.0.1:8000/api/v1/site-hunter/search-jobs/JOB_ID
curl -s http://127.0.0.1:8000/api/v1/site-hunter/search-jobs/JOB_ID/results
```

Review endpoint:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/site-hunter/sites/SITE_ID/review \
  -H 'Content-Type: application/json' \
  -d '{"status":"investigate"}'
```

## Known Local Limits

- Job data is stored in memory for V1 local testing. Restarting FastAPI clears jobs and results.
- PostgreSQL/Supabase persistence is prepared in migrations but intentionally not required in this phase.
- Utility capacity, GIS, substations, and transmission lines are reserved for the next stage.
- Public search engines and websites can rate-limit, timeout, or change HTML. A single source failure is isolated and shown in source status.
