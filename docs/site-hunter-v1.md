# Site Hunter V1 Phase 1

## Goal

Site Hunter turns Chinese industrial-site requirements into English U.S. industrial-real-estate discovery searches. Phase 1 focuses on finding real public site candidates and preserving source evidence.

## Implemented

- `SiteHunterAgent`
- Chinese natural-language parser
- Industry term expansion
- English query generation
- `SourceDiscoveryService`
- Background job APIs
- Per-source run status
- Public web search adapter
- Century 21 Commercial public-page adapter
- Crexi search-backed adapter
- Manual import adapter
- Basic property normalization, dedupe, scoring, and Chinese summaries
- Frontend search, progress, results, and detail pages
- Database schema for source discovery, sites, listings, documents, coordinates, and reserved power tables

## API

```text
POST /api/v1/site-hunter/search-jobs
GET /api/v1/site-hunter/search-jobs/{job_id}
GET /api/v1/site-hunter/search-jobs/{job_id}/results
GET /api/v1/site-hunter/sites/{site_id}
POST /api/v1/site-hunter/sites/{site_id}/review
```

## Real Source Status

```text
Public Web Search: real public webpages discovered through search.
Century 21 Commercial: real public commercial real-estate state pages.
Crexi: adapter present; result availability depends on search engine visibility.
Manual Import: real user-provided URL/text only.
```

## Known Limits

- V1 supports nationwide search parameters but does not fully crawl every U.S. county or local broker.
- Search engines can return broad category pages, not always individual listings.
- Address, acreage, price, zoning, and broker fields are extracted only when visible in title/snippet/source metadata.
- Power facilities and utility capacity are reserved for phase 2.
- The system must not interpret nearby lines/substations as confirmed available MW.

## Phase 2 Recommendation

- Add geocoding.
- Add public substation/transmission datasets.
- Add distance calculation.
- Add utility service territory detection.
- Add source-specific adapters for high-value state/local economic development sites.
