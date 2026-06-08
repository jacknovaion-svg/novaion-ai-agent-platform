# Deployment Guide

NOVAION is deployed as decoupled services:

- Frontend: Next.js on Vercel
- Backend: FastAPI + Playwright on Render, Railway, or Fly.io
- Database: Supabase PostgreSQL

The frontend never imports or hosts the backend. It calls the API through `NEXT_PUBLIC_API_BASE_URL`.

## 1. Local Development

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

Open:

- API health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

If using `http://127.0.0.1:3000`, keep backend CORS configured for both local origins:

```env
API_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

## 2. Supabase Setup

1. Create a Supabase project.
2. Open SQL Editor.
3. Run `supabase/schema.sql`.
4. Run `supabase/seed.sql`.
5. Go to Project Settings -> Database.
6. Copy the connection string.
7. Use the SQLAlchemy/psycopg format for the backend:

```env
DATABASE_URL=postgresql+psycopg://postgres:[PASSWORD]@[HOST]:5432/postgres
```

Demo user:

```text
Email: demo@novaion.ai
Password: not required in V1
```

V1 does not implement authentication yet. The demo email is used as an application-level user preference and saved-search owner seed.

## 3. Backend Deployment On Render

Recommended: deploy the backend with Docker because Playwright needs browser dependencies.

### Option A: Render Blueprint

1. Push the repository to GitHub.
2. In Render, choose New -> Blueprint.
3. Select the repo.
4. Render reads `render.yaml`.
5. Set these environment variables:

```env
APP_ENV=production
APP_NAME=NOVAION AI Agent Platform
API_CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
DATABASE_URL=postgresql+psycopg://postgres:[PASSWORD]@[HOST]:5432/postgres
ENABLE_LIVE_SCRAPING=false
PLAYWRIGHT_HEADLESS=true
DEFAULT_USER_EMAIL=demo@novaion.ai
```

6. Deploy.
7. Verify:

```text
https://YOUR-RENDER-SERVICE.onrender.com/health
https://YOUR-RENDER-SERVICE.onrender.com/docs
```

### Option B: Manual Render Web Service

Use:

```text
Runtime: Docker
Dockerfile Path: apps/api/Dockerfile
Docker Context: apps/api
Health Check Path: /health
```

Set the same environment variables as Option A.

## 4. Backend Deployment On Railway

1. Create a Railway project from the GitHub repo.
2. Select the backend service root:

```text
apps/api
```

3. Railway will use `apps/api/Dockerfile` and `apps/api/railway.json`.
4. Set environment variables:

```env
APP_ENV=production
APP_NAME=NOVAION AI Agent Platform
API_CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
DATABASE_URL=postgresql+psycopg://postgres:[PASSWORD]@[HOST]:5432/postgres
ENABLE_LIVE_SCRAPING=false
PLAYWRIGHT_HEADLESS=true
DEFAULT_USER_EMAIL=demo@novaion.ai
```

5. Deploy.
6. Verify:

```text
https://YOUR-RAILWAY-DOMAIN.up.railway.app/health
```

## 5. Frontend Deployment On Vercel

The web app is independent from the API. Configure the API URL through an environment variable.

### Recommended Monorepo Settings

1. Import the GitHub repo into Vercel.
2. Set Project Root / Root Directory to:

```text
.
```

3. Set Install Command:

```bash
npm install
```

4. Set Build Command:

```bash
npm --workspace apps/web run build
```

5. Set Output Directory:

```text
apps/web/.next
```

6. Set environment variables:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR-BACKEND-DOMAIN/api/v1
NEXT_PUBLIC_DEFAULT_USER_EMAIL=demo@novaion.ai
```

7. Deploy.

After Vercel gives you a public domain, update backend CORS:

```env
API_CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
```

For multiple frontend domains:

```env
API_CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app,https://www.yourdomain.com
```

## 6. Optional Backend Deployment On Fly.io

Render or Railway is recommended for V1 because setup is simpler. Fly.io is also supported through the backend Dockerfile.

1. Install and log in to `flyctl`.
2. Copy the example config:

```bash
cd apps/api
cp fly.toml.example fly.toml
```

3. Edit `fly.toml` and change:

```text
app = "novaion-api"
```

4. Set secrets:

```bash
fly secrets set APP_ENV=production
fly secrets set "APP_NAME=NOVAION AI Agent Platform"
fly secrets set API_CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
fly secrets set DATABASE_URL=postgresql+psycopg://postgres:[PASSWORD]@[HOST]:5432/postgres
fly secrets set ENABLE_LIVE_SCRAPING=false
fly secrets set PLAYWRIGHT_HEADLESS=true
fly secrets set DEFAULT_USER_EMAIL=demo@novaion.ai
```

5. Deploy:

```bash
fly deploy
```

6. Verify:

```text
https://novaion-api.fly.dev/health
```

## 7. Customer Test Flow

After deployment, share the Vercel URL with customers.

Test steps:

1. Open the Vercel URL.
2. Switch language between English and Chinese.
3. Search `RTX 5090`.
4. Search `64GB DDR5 ECC RDIMM`.
5. Confirm ranked results appear.
6. Save a search.
7. Open Saved Searches.
8. Open Alert Center placeholder.

## 8. Live Scraping Mode

For reliable demos, keep:

```env
ENABLE_LIVE_SCRAPING=false
```

This returns normalized demo-backed source results while preserving the real adapter contract.

To try live source scraping:

```env
ENABLE_LIVE_SCRAPING=true
```

The Docker image already includes Playwright browsers and system dependencies. Live scraping can still be blocked by source sites, rate limits, bot protection, or region-based behavior. The adapter layer is designed so official APIs can replace Playwright later without changing frontend or agent architecture.

## 9. Production Checklist

- Supabase schema initialized
- Supabase seed loaded
- Backend deployed and `/health` returns `ok`
- Backend `DATABASE_URL` configured
- Backend `API_CORS_ORIGINS` includes Vercel domain
- Frontend deployed to Vercel
- Frontend `NEXT_PUBLIC_API_BASE_URL` points to backend `/api/v1`
- Customer can search from the public Vercel URL
