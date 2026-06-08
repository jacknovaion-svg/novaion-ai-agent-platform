# NOVAION Architecture

## Platform Shape

NOVAION is an agent platform, not a single-purpose hardware finder. V1 ships one enabled agent:

- `hardware_hunter`

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
