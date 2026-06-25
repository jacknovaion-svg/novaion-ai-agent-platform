# NOVAION Hardware Hunter V2 Local Daily Scan

V2 extends the existing Hardware Hunter. It does not create a separate project and does not change Site Hunter.

## Local Page

- Frontend: http://localhost:3000/hardware-hunter/dashboard
- API docs: http://127.0.0.1:8000/docs
- Dashboard API: `GET /api/v1/hardware-hunter/daily-scan/dashboard`

## What Is Implemented

- `HardwareHunterDailyScheduler`
- Asset Listing Search job mode
- Public discovery for GovDeals, Public Surplus, eBay, HGP, and broad industrial auction sources
- Manual hardware listing import
- Hardware categories: servers, GPU, memory, storage, CPU
- Hardware listing normalization
- Result page classification: specific listing, listing collection, source page, news/article, irrelevant
- Only `specific_listing` enters formal opportunities and Telegram reports
- Deduplication by canonical URL
- Change detection: new, price, quantity, status
- Opportunity score and risk score
- Chinese Telegram daily report preview, test send, approve-and-send
- Telegram delivery log model
- 24-hour scheduler state: pause/resume, last run, next run, overlap prevention, local disk restore
- Local Dashboard page
- Supabase/PostgreSQL migration for the V2 tables

## Important Data Truth Notes

Current source integrations are public-search discovery unless marked otherwise. They preserve original titles, snippets, URLs, and fetch timestamps. They are not official GovDeals, Public Surplus, eBay, or HGP APIs.

The system must not auto-buy, auto-bid, auto-call, auto-email, or claim final procurement availability. Human review is required before contacting sellers or placing bids.

## Environment Variables

Add these to `apps/api/.env` when Telegram is ready:

```bash
HARDWARE_HUNTER_TELEGRAM_ENABLED=false
HARDWARE_HUNTER_TELEGRAM_BOT_TOKEN=
HARDWARE_HUNTER_TELEGRAM_CHAT_ID=
HARDWARE_HUNTER_DAILY_REPORT_HOUR=8
HARDWARE_HUNTER_TIMEZONE=America/Los_Angeles
HARDWARE_HUNTER_IMMEDIATE_ALERTS=false
```

With Telegram disabled or missing token/chat id, the API returns a local report preview and records a disabled/dry-run delivery status.

## API

- `POST /api/v1/hardware-hunter/daily-scan/run`
- `GET /api/v1/hardware-hunter/daily-scan/jobs/{job_id}`
- `GET /api/v1/hardware-hunter/daily-scan/dashboard`
- `POST /api/v1/hardware-hunter/daily-scan/jobs/{job_id}/telegram-report`
- `GET /api/v1/hardware-hunter/daily-scan/scheduler`
- `POST /api/v1/hardware-hunter/daily-scan/scheduler/pause`
- `POST /api/v1/hardware-hunter/daily-scan/scheduler/resume`

Example payload:

```json
{
  "mode": "both",
  "categories": ["servers", "gpu", "memory", "storage", "cpu"],
  "states": ["TX", "CA", "GA"],
  "test_run": true,
  "max_results_per_query": 3,
  "max_queries_per_category": 6,
  "send_telegram": false
}
```

Telegram actions:

```json
{ "action": "preview" }
```

```json
{ "action": "test", "message": "NOVAION Hardware Hunter Telegram test message." }
```

```json
{ "action": "approve_and_send" }
```

`preview` never sends. `test` and `approve_and_send` require Telegram token and chat id. Same `scan_job_id + report_type + message_hash` cannot be sent twice after a successful Telegram send.

## Planned Dedicated Adapters

- GovDeals dedicated auction adapter
- Public Surplus dedicated auction adapter
- eBay official Browse/Finding API adapter
- HGP/BidSpotter/Proxibid industrial auction adapters
- R2/e-Stewards/NAID directory direct adapters
- Price history persistence through PostgreSQL repository
