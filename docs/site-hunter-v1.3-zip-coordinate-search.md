# Site Hunter V1.3 ZIP / Coordinate Land Search

目标：支持用户直接输入 ZIP Code 或变电站坐标，搜索指定半径内的工业土地、旧工厂、仓库和制造设施挂牌。

## 支持的输入

示例：

```text
91766
78624
29.762731, -98.720308
搜索 29.762731, -98.720308 周边20英里内，20英亩以上，1000万美元以内的工业土地或旧工厂
```

## 实现范围

- 新增 `SiteSearchAnchor`，记录搜索中心点。
- 支持 `zip_code` 和 `coordinates` 两种 anchor。
- 自动解析 `周边20英里`、`within 20 miles`、`30 km` 为 `radius_miles`。
- ZIP 通过公开 ZIP centroid / Nominatim 解析为经纬度。
- 坐标通过 US Census reverse geocoder / Nominatim 反查 city、county、state。
- 英文搜索词自动加入 `near [city/state/ZIP/coordinates]` 和 `within X miles`。
- 结果经 Geocoding 后计算到搜索中心点距离。
- 已知超出半径的具体挂牌会被过滤。
- 无法计算距离的挂牌保留，但标记 `needs_verification: distance_to_search_anchor unknown`。

## 距离口径

当前距离是：

```text
address_point_to_search_anchor
```

也就是“地产地址点到搜索中心点”的球面距离，不是 Parcel 边界距离。后续如果接入 Land id 或县 Parcel GIS，可以升级为：

```text
parcel_boundary_to_search_anchor
```

## 不做的事

- 不判断变电站是否有可用容量。
- 不判断是否可以直接T接。
- 不预测接入成本、接入时间或可用MW。
- 不把 nearby 线路或变电站当成 Utility confirmed。

## 本地测试建议

后端：

```bash
cd apps/api
API_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 SITE_HUNTER_SEARCH_PROVIDER=duckduckgo_html .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run dev
```

页面：

```text
http://localhost:3000/site-hunter
```

测试输入：

```text
搜索 29.762731, -98.720308 周边20英里内，20英亩以上，1000万美元以内的工业土地或旧工厂，用于未来建设50MW AI数据中心。
```

验收要点：

- Results 页面显示 Search center、radius、resolved coordinates。
- 每条具体挂牌显示 Anchor distance。
- `radius_mismatch_removed` 有统计字段。
- 详情页显示 Anchor distance 和 Distance basis。

