# Hardware Hunter V1.5 Supplier Discovery

目标：在现有 Hardware Hunter 内增加 Supplier Discovery，不修改 Site Hunter，不新建独立项目。

## 本地页面

```text
http://localhost:3000/
```

Hardware Hunter 页面新增三种模式：

- Retail Products
- Used Enterprise Hardware
- Supplier Discovery

## 新增 API

```text
POST /api/v1/supplier-hunter/search-jobs
GET  /api/v1/supplier-hunter/search-jobs/{job_id}
GET  /api/v1/supplier-hunter/suppliers/{supplier_id}
POST /api/v1/supplier-hunter/suppliers/{supplier_id}/review
```

## Texas 第一版区域

- Dallas-Fort Worth
- Houston
- Austin
- San Antonio
- El Paso
- Midland-Odessa
- Waco
- Lubbock
- Amarillo
- Corpus Christi
- Beaumont-Port Arthur
- Rio Grande Valley

## 供应商类型

- ITAD company
- Data center decommissioning company
- Enterprise IT asset disposition
- Electronics recycler
- R2 certified recycler
- e-Stewards processor
- Server refurbisher
- Used server wholesaler
- Corporate laptop liquidation
- Asset remarketing company
- Direct asset purchasing company
- Data center equipment buyer

## 分类

- A类：可能直接接触数据中心、企业、银行、医院、学校等退役资产，并有直接采购/再营销能力。
- B类：ITAD、数据中心退役、资产再营销、电子回收公司。
- C类：二手服务器、电脑、内存、硬盘批发和翻新公司。
- D类：普通维修店、消费电子回收点或低价值来源，默认过滤。

## 认证状态

R2、e-Stewards、NAID AAA 不自动标记官方验证。

状态：

- `verified`
- `claimed_on_website`
- `directory_discovered`
- `needs_verification`
- `unknown`

V1.5 只做公开搜索发现和目录发现，目录或官网无法稳定抓取时标记 `needs_verification`。

## 已接入真实来源

- Public Web Search：DuckDuckGo HTML / 配置的公开搜索服务
- Certification Directory Discovery：针对 R2、e-Stewards、NAID AAA 目录的公开搜索发现
- Manual Import

## 测试输入

```text
TX，寻找做数据中心退役、企业ITAD、二手服务器、内存、硬盘、笔记本和台式机批量销售的一手供应商。
```

期望：

- Texas 识别正确
- 自动拆分 Texas 多个城市/区域
- 生成英文供应商搜索词
- 返回真实公司和原始链接
- 显示认证状态、业务能力、A/B/C/D 分类
- D 类低价值来源被过滤
- 支持保留、拒绝、联系、进一步调查

## 限制

- 不自动发送邮件。
- 不自动打电话。
- 不自动签约。
- 不自动采购。
- 不把目录发现结果假装成官方认证。
- 不把普通维修店和消费电子回收点当作一手供应商。

