# Site Hunter V1.4 State-Level Search Mode

目标：用户不知道 ZIP、城市或变电站坐标时，可以直接输入州名、州缩写或中文州名，系统自动执行州级工业地产发现。

## 支持输入

```text
TX
Texas
德州
TX，搜索20英亩以上，1000万美元以内，适合50MW AI数据中心的工业土地或旧工厂。
```

## 州标准化

V1.4 新增美国 50 州及 Washington, D.C. 标准化：

```text
TX / Texas / 德州 / 德克萨斯 -> state_code=TX, state_name=Texas
CA / California / 加州 -> state_code=CA, state_name=California
GA / Georgia / 乔治亚 / 佐治亚 -> state_code=GA, state_name=Georgia
```

注意：`IN`、`OR` 等容易和英文普通词冲突的缩写，仅在独立输入或大写独立词时识别。

## Texas 第一版区域覆盖

Texas profile 已覆盖：

- Dallas-Fort Worth
- Houston
- San Antonio
- Austin
- Midland-Odessa
- Abilene
- Waco
- Temple-Killeen
- Amarillo
- Lubbock
- Corpus Christi
- Beaumont-Port Arthur
- El Paso

每个区域配置：

- region_name
- region_type
- cities
- counties
- search_phrases
- max_specific_listings

## 查询生成策略

州级搜索不会只生成 `land for sale Texas` 这类宽泛查询。系统会生成分区查询：

```text
industrial land for sale Dallas Fort Worth Texas 20+ acres under $10,000,000
former manufacturing facility for sale Houston Texas 20+ acres under $10,000,000
heavy industrial property for sale San Antonio Texas
industrial acreage Midland County Texas
Texas economic development available sites
utility-served industrial land Texas
powered land for data center Texas
```

## Job 结构

新增：

```text
job_mode = state_search
state_job
region_subjobs
source_runs
```

`region_subjobs` 记录：

- generated_query_count
- executed_query_count
- raw_result_count
- specific_listing_count
- final_candidate_count
- power_screened_count
- status

## 规模控制

默认策略：

- 每次州级任务选择最多 36 条执行查询。
- 所有 Texas 主要区域至少覆盖 2 条物业查询。
- 州经济发展与 Utility 查询强制加入。
- 全州正式候选最多 80 条。
- 只对 Top 20 执行电力设施初筛。
- 其他候选保留地产信息，但不自动查变电站和线路。

## 结果页

Results 页面显示：

- 搜索州
- state_code
- 已执行区域数量
- 每个区域 raw / candidate / power count
- total specific listings
- 去重后 final candidates
- 已完成电力初筛数量

支持继续筛选：

- 州
- 城市/县
- 土地面积
- 价格
- 地产类型
- 线路电压
- 最近变电站距离

## 验收输入

```text
TX，搜索20英亩以上，1000万美元以内，适合50MW AI数据中心的工业土地或旧工厂。
```

期望：

- `TX` 标准化为 `Texas / TX`
- 自动生成多个 Texas 区域任务
- 英文查询包含具体城市、县或工业走廊
- 结果保持 `specific_listing` 分类、去重、州过滤、面积过滤、预算过滤
- 如果公开来源没有合格具体挂牌，不用分类页冒充
- Top 20 候选执行电力设施初筛

