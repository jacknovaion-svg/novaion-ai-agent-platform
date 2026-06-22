# NOVAION Architecture

## Platform Shape

NOVAION is an agent platform, not a single-purpose hardware finder. V1 ships enabled agents:

- `hardware_hunter`
- `site_hunter`

Reserved agent types:

- `power_hunter`
- `land_hunter`
- `supplier_hunter`
- `data_center_hunter`

## Backend Layers

```text
Routers
  -> Agent Center
    -> Agent implementation
      -> Search Engine Center
        -> Source adapters
          -> Playwright/API/manual source implementation
      -> Recommendation service
  -> Database repository
```

## Site Hunter Shape

Site Hunter is implemented as a task-based agent because real estate discovery can take longer than a normal request-response search.

```text
Site Hunter Search Request
  -> ChineseRequirementParser
  -> IndustryTermExpander
  -> EnglishSearchQueryBuilder
  -> SourceDiscoveryService
  -> PropertySourceAdapters
      -> WebSearchPropertyAdapter
      -> CrexiSearchAdapter
      -> Century21CommercialAdapter
      -> ManualImportAdapter
  -> PropertyNormalizer
  -> SiteOpportunityScoringService
  -> Site Hunter results/detail pages
```

The first phase supports all U.S. states and Washington, D.C. at the query and source-discovery layer. It does not claim complete coverage of every county, city, broker, or property website.

## Site Hunter Data Integrity

Site Hunter must retain:

- Original Chinese input
- Parsed structured criteria
- Generated English search terms
- Source run status and errors
- Original English title
- Original description/snippet when available
- Original source URL
- Fetch/check timestamp

Missing fields are stored as unknown. Public seller, broker, or utility claims are source-confirmed or unverified; they are not treated as utility-verified capacity.

## Adapter Contract

Every source adapter implements:

- `search(query, options)`
- `parse_results(raw_data)`
- `normalize_result(parsed_data)`

Adapters return a shared normalized result format:

```json
{
  "source": "Best Buy",
  "product_name": "RTX 5090 Graphics Card",
  "brand": "NVIDIA",
  "model": "RTX 5090",
  "store_name": "Online",
  "address": "",
  "distance": null,
  "price": 2499.99,
  "promotion": "",
  "inventory_status": "In Stock",
  "pickup_available": false,
  "shipping_available": true,
  "product_url": "https://example.com",
  "updated_at": "2026-06-07T12:00:00Z"
}
```

## Recommendation Score

Initial scoring is intentionally simple:

- Inventory: 40%
- Price: 30%
- Distance: 20%
- Promotion: 10%

Future versions can replace this with model-assisted ranking while keeping the score service interface stable.

## i18n

V1 supports:

- English
- Chinese

Reserved:

- Spanish

The frontend defaults to browser language and persists preference through the backend user preference endpoint.
