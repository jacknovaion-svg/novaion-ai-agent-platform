from __future__ import annotations

import re

from app.site_hunter.us_states import all_state_aliases, normalize_state
from app.supplier_hunter.models import SupplierSearchCriteria, SupplierSearchRegions


SUPPLIER_TYPE_KEYWORDS = [
    ("data center decommissioning", ["数据中心退役", "data center decommissioning", "decommissioning"]),
    ("enterprise ITAD", ["企业itad", "itad", "it asset disposition", "资产处置"]),
    ("electronics recycler", ["电子回收", "electronics recycler", "recycler"]),
    ("server refurbisher", ["服务器翻新", "server refurbisher", "server refurbishment"]),
    ("used server wholesaler", ["二手服务器", "used server", "server wholesale"]),
    ("corporate laptop liquidation", ["笔记本", "laptop liquidation", "corporate laptop"]),
    ("asset remarketing company", ["资产再营销", "asset remarketing", "remarketing"]),
    ("direct asset purchasing company", ["一手供应商", "直接采购", "direct asset purchasing", "equipment buyer"]),
]

EQUIPMENT_KEYWORDS = [
    ("servers", ["服务器", "server", "servers"]),
    ("memory", ["内存", "memory", "ram"]),
    ("hard drives", ["硬盘", "hard drive", "hdd", "ssd"]),
    ("laptops", ["笔记本", "laptop", "laptops"]),
    ("desktops", ["台式机", "desktop", "desktops"]),
    ("network equipment", ["网络设备", "network equipment", "switches"]),
]


class SupplierRequirementParser:
    def parse(self, raw_query: str, structured: SupplierSearchCriteria | None = None) -> SupplierSearchCriteria:
        criteria = structured.model_copy(deep=True) if structured else SupplierSearchCriteria()
        criteria.raw_user_query_zh = raw_query or criteria.raw_user_query_zh
        text = raw_query or ""
        lowered = text.lower()
        criteria.regions = self._merge_regions(criteria.regions, text, lowered)
        criteria.supplier_types = self._merge_keyword_list(criteria.supplier_types, lowered, SUPPLIER_TYPE_KEYWORDS)
        criteria.equipment_types = self._merge_keyword_list(criteria.equipment_types, lowered, EQUIPMENT_KEYWORDS)
        if "r2" in lowered and "R2" not in criteria.certifications:
            criteria.certifications.append("R2")
        if "e-stewards" in lowered and "e-Stewards" not in criteria.certifications:
            criteria.certifications.append("e-Stewards")
        if "naid" in lowered and "NAID AAA" not in criteria.certifications:
            criteria.certifications.append("NAID AAA")
        criteria.data_center_decommissioning = criteria.data_center_decommissioning or ("数据中心退役" in text or "data center" in lowered)
        criteria.bulk_sales = criteria.bulk_sales or any(token in lowered for token in ["bulk", "批量", "wholesale"])
        criteria.wholesale = criteria.wholesale or any(token in lowered for token in ["wholesale", "批发"])
        criteria.direct_asset_purchasing = criteria.direct_asset_purchasing or any(token in lowered for token in ["一手", "direct", "buyer", "采购"])
        criteria.parsed_summary_zh = self._summary(criteria)
        return criteria

    def _merge_regions(self, existing: SupplierSearchRegions, text: str, lowered: str) -> SupplierSearchRegions:
        regions = existing.model_copy(deep=True)
        for state_code in list(regions.state_codes):
            state = normalize_state(state_code)
            if state:
                if state.name not in regions.states:
                    regions.states.append(state.name)
                regions.state_codes[regions.state_codes.index(state_code)] = state.code
        for alias, state in all_state_aliases().items():
            if self._contains_state_alias(text, lowered, alias):
                if state.name not in regions.states:
                    regions.states.append(state.name)
                if state.code not in regions.state_codes:
                    regions.state_codes.append(state.code)
        for zip_code in re.findall(r"\b\d{5}(?:-\d{4})?\b", text):
            if zip_code not in regions.zip_codes:
                regions.zip_codes.append(zip_code)
        return regions

    def _contains_state_alias(self, text: str, lowered: str, alias: str) -> bool:
        if len(alias) == 2 and alias.isascii():
            stripped = text.strip().strip(",.;:，。；：")
            if stripped.lower() == alias.lower():
                return True
            return bool(re.search(rf"\b{re.escape(alias.upper())}\b", text))
        return alias in lowered

    def _merge_keyword_list(self, existing: list[str], lowered: str, mapping: list[tuple[str, list[str]]]) -> list[str]:
        output = list(existing)
        for value, tokens in mapping:
            if any(token.lower() in lowered for token in tokens) and value not in output:
                output.append(value)
        return output

    def _summary(self, criteria: SupplierSearchCriteria) -> str:
        states = "、".join(criteria.regions.states) or "未指定州"
        supplier_types = "、".join(criteria.supplier_types) or "ITAD / enterprise hardware suppliers"
        equipment = "、".join(criteria.equipment_types) or "servers, laptops, storage"
        return f"区域：{states}；供应商类型：{supplier_types}；设备：{equipment}"

