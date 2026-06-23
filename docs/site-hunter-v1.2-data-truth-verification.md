# Site Hunter V1.2 数据真实性验证报告

验证日期：2026-06-23  
运行环境：本地 FastAPI + Next.js  
测试 Job：`513d3d43-ab20-451e-9f1f-2152cbaf8c6e`  
核查范围：只验证当前系统返回的坐标、电力设施、距离、电压和Utility候选可信度；不判断可用MW、接入许可、接入成本或送电时间。

## 验证状态口径

- `official_verified`：Utility或政府正式GIS/正式公开文件确认。
- `manual_map_confirmed`：Land id或人工地图目视确认，但未达到官方确认。
- `source_confirmed`：两个独立公开来源一致，或一个正式公开GIS数据源给出可追溯字段。
- `estimated`：公开地图或规则推断，缺少独立交叉验证。
- `conflicting`：位置、电压、所有者、Utility或资产解释存在冲突。
- `unverified`：尚未核查或证据不足。

## 使用来源

- 自动来源：OpenStreetMap Overpass、HIFLD / ArcGIS Electric Power Transmission Lines、US Census Geocoder、OpenStreetMap Nominatim。
- Land id：本次没有可用的已登录 Land id 人工核查结果；所有 Land id 字段保持 `not_reviewed`，不得标记 `manual_map_confirmed`。
- 官方/政府公开资料：US Census Geocoder、HIFLD ArcGIS FeatureServer、Texas PUC electric maps入口、Georgia Power economic development入口。Utility服务区仍需按Parcel或官方服务区图继续核查。

关键来源链接：

- US Census Geocoder: https://geocoding.geo.census.gov/geocoder/
- HIFLD Electric Power Transmission Lines: https://hifld-geoplatform.opendata.arcgis.com/datasets/geoplatform::electric-power-transmission-lines/about
- ArcGIS FeatureServer Query: https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/US_Electric_Power_Transmission_Lines/FeatureServer/0/query
- Texas PUC electric maps: https://www.puc.texas.gov/industry/electric/maps/
- Georgia Power economic development: https://www.georgiapower.com/business/economic-development.html

## 总体结论

当前 V1.2 可以把地址点成功转为坐标，并能通过 OSM/HIFLD 找到附近线路或变电站；但目前距离全部基于“地址点到设施几何”的距离，不是 Parcel 边界距离。地块边界、线路是否穿过地块、线路与变电站是否存在实际连接关系、Utility服务区和容量都没有完成官方确认。

| 项目 | 地址坐标 | 最近变电站 | 最近线路 | 电压 | Utility候选 | 最终状态 |
|---|---:|---|---|---|---|---|
| Gainesville GA | geocoded_address | unknown | OSM 0.009 mi + HIFLD 0.010 mi | OSM 46kV / HIFLD 115kV冲突 | estimated | `conflicting` |
| Jackson GA | geocoded_address | unknown | OSM 0.283 mi minor_line；HIFLD/OSM 0.970 mi 500kV | 500kV来源一致，最近minor_line unknown | estimated | `source_confirmed` |
| Fredericksburg TX | geocoded_address | unknown | HIFLD 8.475 mi | 138kV | estimated | `source_confirmed` |
| Boerne TX | geocoded_address | OSM Menger Creek 0.556 mi | OSM/HIFLD约0.54 mi 138kV；HIFLD 2.721 mi 345kV | 138kV和345kV均在附近但关系未证实 | estimated | `conflicting` |

## 1. 3263 Tanners Mill Road, Gainesville, GA 30507

自动结果：

- 坐标：`34.1868601673, -83.783076145055`
- Geocoding：US Census Geocoder，confidence `0.9`，状态 `geocoded_address`
- 最近OSM线路：OpenStreetMap way `1035015645`，距离 `0.009 mi`，电压 `46 kV`
- 最近HIFLD线路：ID `142272`，距离 `0.010 mi`，电压 `115 kV`，owner `GEORGIA POWER CO`，status `IN SERVICE`
- 另有HIFLD/OSM约 `0.024 mi` 的 `230 kV` 线路，和约 `1.846 mi` 的 `500 kV` HIFLD线路
- 最近变电站：当前系统未返回
- Utility候选：`Georgia Power or local EMC service territory`，规则估算

Land id结果：

- 未执行人工账户核查；状态 `not_reviewed`
- Parcel边界、APN、所有者、地块面积、线路是否穿越地块：`unverified`

官方或政府GIS结果：

- US Census Geocoder支持地址点坐标，但不等同于Parcel边界。
- HIFLD/ArcGIS返回Georgia Power线路属性，但HIFLD字段 `INFERRED=Y`，且其来源含Imagery/EIA/OSM，不能替代Georgia Power正式接入确认。

一致性与冲突：

- 重点复核项“0.009 miles线路是否真实”：OSM显示有46kV线路，HIFLD几乎同位置显示115kV线路，说明附近线路真实可能性高，但最近线路电压存在冲突。
- 重点复核项“46kV电压是否正确”：仅OSM支持，不能标记官方确认。
- 距离基于地址点，不是Parcel边界。

最终状态：`conflicting`

仍需确认：

- Georgia Power或县级/州级官方GIS确认线路电压和所有者。
- Land id或县Parcel GIS确认地块边界与线路关系。
- Utility正式服务区和可接入容量。

## 2. 150 Truck Stop Way, Jackson, GA 30233

自动结果：

- 坐标：`33.206884609522, -84.056161612728`
- Geocoding：US Census Geocoder，confidence `0.9`，状态 `geocoded_address`
- 最近OSM线路：OpenStreetMap way `355490345`，距离 `0.283 mi`，`power=minor_line`，电压 `unknown`
- HIFLD线路：ID `136257`，距离 `0.970 mi`，`500 kV`，owner `GEORGIA POWER CO`，status `IN SERVICE`
- OSM交叉来源：OpenStreetMap way `9460274`，`Scherer - O'Hara 500kV`，距离 `0.970 mi`，operator `Georgia Power`
- 最近变电站：当前系统未返回
- Utility候选：`Georgia Power or local EMC service territory`，规则估算

Land id结果：

- 未执行人工账户核查；状态 `not_reviewed`
- Parcel边界和线路相对关系：`unverified`

官方或政府GIS结果：

- US Census Geocoder支持地址点坐标。
- HIFLD/ArcGIS与OSM均指向约0.97英里处500kV Georgia Power线路。

一致性与冲突：

- 500kV线路存在、电压和运营方在HIFLD与OSM之间一致，可标记 `source_confirmed`。
- 最近0.283英里的OSM minor_line没有电压和官方属性，仍是 `estimated`。
- 距离基于地址点，不是Parcel边界。

最终状态：`source_confirmed`

仍需确认：

- 最近minor_line是否为配电/低压设施。
- Georgia Power或官方服务区图确认该Parcel Utility。
- Parcel边界距离和是否存在跨地块线路。

## 3. 12346 E US Hwy 290, Fredericksburg, TX 78624

自动结果：

- 坐标：`30.22120656387, -98.696363194388`
- Geocoding：US Census Geocoder，confidence `0.9`，状态 `geocoded_address`
- 最近HIFLD线路：ID `305810`，距离 `8.475 mi`，`138 kV`，owner `CENTRAL TEXAS ELEC COOP, INC`，status `IN SERVICE`
- 第二HIFLD线路：ID `307100`，距离 `9.809 mi`，`138 kV`，owner `CENTRAL TEXAS ELEC COOP, INC`
- 最近变电站：当前系统未返回
- Utility候选：`Texas deregulated market / local TDU to verify`，规则估算

Land id结果：

- 未执行人工账户核查；状态 `not_reviewed`
- Parcel边界和距离：`unverified`

官方或政府GIS结果：

- HIFLD/ArcGIS返回两条Central Texas Electric Coop 138kV线路，字段 `INFERRED=N`。
- Texas PUC服务区仍需按地址或Parcel核查。

一致性与冲突：

- 重点复核项“8.475 miles线路距离是否准确”：当前距离为地址点到HIFLD线路几何的最短距离；不是Parcel边界距离。
- 电压/owner来自HIFLD单一公开GIS数据源，可信度高于OSM估算，但仍不是Utility容量确认。

最终状态：`source_confirmed`

仍需确认：

- Central Texas Electric Coop是否为该Parcel服务Utility或仅为附近线路owner。
- Land id/县Parcel边界距离。
- 官方Utility是否确认线路、变电站和服务区。

## 4. 33975 W IH-10, Boerne, TX 78006

自动结果：

- 坐标：`29.7703725, -98.7231895`
- Geocoding：OpenStreetMap Nominatim，confidence `0.75`，状态 `geocoded_address`
- 最近疑似变电站：OpenStreetMap way `289004897`，`Menger Creek Substation`，距离 `0.556 mi`，电压 `138 kV`，operator `Lower Colorado River Authority`
- 最近OSM线路：way `849647640`，距离 `0.530 mi`，电压 `unknown`
- 附近138kV线路：OSM约 `0.540-0.553 mi`；HIFLD IDs `303209`、`307596`，约 `0.545 mi`，owner `BANDERA ELECTRIC COOP, INC`
- 附近345kV线路：HIFLD ID `302826`，距离 `2.721 mi`，owner `BANDERA ELECTRIC COOP, INC`；HIFLD ID `305942`，距离 `3.069 mi`，owner `PEDERNALES ELECTRIC COOP, INC`
- Utility候选：`Texas deregulated market / local TDU to verify`，规则估算

Land id结果：

- 未执行人工账户核查；状态 `not_reviewed`
- Parcel边界、线路是否穿越地块、变电站相对边界：`unverified`

官方或政府GIS结果：

- HIFLD/ArcGIS支持附近138kV与345kV线路存在，并给出owner/status/voltage。
- Menger Creek Substation名称、电压和LCRA operator目前来自OSM；没有Utility官方页面在本轮被核实。

一致性与冲突：

- 重点复核项“Menger Creek Substation是否真实”：OSM中存在该变电站，但本轮没有LCRA或政府GIS正式确认，状态只能是 `estimated`。
- 重点复核项“Boerne附近345kV线路是否真实”：HIFLD/ArcGIS返回两条345kV线路，状态 `IN SERVICE`，可作为 `source_confirmed` 的附近线路证据。
- 重点复核项“345kV线路与Menger Creek Substation是否有关联”：当前没有证据证明345kV线路与Menger Creek Substation存在实际连接关系。
- 系统当前 `known_voltage_kv=345` 容易被误读为最近变电站电压；页面和报告中应明确“附近最高已知电压”和“最近设施电压”不是同一结论。

最终状态：`conflicting`

仍需确认：

- LCRA官方/政府GIS确认Menger Creek Substation名称、坐标、电压和运营方。
- Bandera/Pedernales/LCRA之间的线路-变电站实际连接关系。
- Parcel边界距离和服务Utility。

## 冲突数据清单

| 项目 | 字段 | 自动结果 | 交叉结果 | 处理 |
|---|---|---|---|---|
| Gainesville | 最近线路电压 | OSM 46kV at 0.009 mi | HIFLD 115kV at 0.010 mi；HIFLD/OSM 230kV at 0.024 mi | `conflicting` |
| Gainesville | Utility | Georgia Power或local EMC | HIFLD owner显示Georgia Power，但服务区未确认 | `estimated` |
| Jackson | 最近线路 | OSM minor_line 0.283 mi voltage unknown | HIFLD/OSM 500kV at 0.970 mi一致 | 最近minor_line `estimated`；500kV `source_confirmed` |
| Fredericksburg | Utility | Texas local TDU待核查 | HIFLD线路owner Central Texas Elec Coop | 线路owner不等于Parcel服务Utility |
| Boerne | 最近变电站 | OSM Menger Creek 138kV LCRA | HIFLD只确认附近线路，不确认该变电站 | 变电站 `estimated` |
| Boerne | 345kV关系 | nearby highest voltage 345kV | Menger Creek Substation为OSM 138kV；无连接关系证据 | `conflicting` / needs manual review |

## 需要人工继续确认的问题

1. 使用 Land id 或县级Parcel GIS确认四个地块的Parcel边界、APN、地块面积、所有者和线路相对位置。
2. 使用Utility正式服务区图确认每个Parcel的服务Utility。
3. Gainesville需要Georgia Power或官方GIS确认0.009-0.010mi附近线路到底是46kV、115kV，还是多条线路并行。
4. Boerne需要LCRA或官方GIS确认Menger Creek Substation真实性，以及它与附近138kV/345kV线路是否存在连接关系。
5. Fredericksburg需要确认HIFLD 8.475mi距离是否按Parcel边界计算后仍接近该数值。
6. 所有项目容量保持 `unknown`，不得因为线路或变电站靠近推断50MW可接入。

