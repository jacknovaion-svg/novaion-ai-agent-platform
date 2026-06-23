from __future__ import annotations

import re

from app.site_hunter.models import SearchAnchorStatus, SearchAnchorType, SiteHunterRegions, SiteHunterStructuredCriteria, SiteSearchAnchor
from app.site_hunter.us_states import all_state_aliases, normalize_state

PROJECT_USE_ALIASES = {
    "ai数据中心": "ai_data_center",
    "ai data center": "ai_data_center",
    "数据中心": "data_center",
    "算力中心": "ai_data_center",
    "矿场": "btc_mining",
    "btc": "btc_mining",
    "储能": "battery_storage",
    "工业负荷": "industrial_load",
}


class ChineseRequirementParser:
    def parse(self, raw_query: str, structured: SiteHunterStructuredCriteria | None = None) -> SiteHunterStructuredCriteria:
        criteria = structured.model_copy(deep=True) if structured else SiteHunterStructuredCriteria()
        criteria.raw_user_query_zh = raw_query or criteria.raw_user_query_zh
        text = raw_query or ""
        lowered = text.lower()

        criteria.regions = self._merge_regions(criteria.regions, text, lowered)
        criteria.regions.radius_miles = criteria.regions.radius_miles or self._search_radius(text)
        criteria.search_anchor = criteria.search_anchor or self._search_anchor(text, criteria.regions)
        criteria.property_types = self._property_types(text, lowered, criteria.property_types)
        criteria.transaction_types = self._transaction_types(text, lowered, criteria.transaction_types)
        criteria.min_land_acres = criteria.min_land_acres or self._land_acres(text)
        criteria.min_building_sqft = criteria.min_building_sqft or self._building_sqft(text)
        criteria.max_price_usd = criteria.max_price_usd or self._max_price(text)
        criteria.target_load_mw = criteria.target_load_mw or self._target_load(text)
        criteria.preferred_substation_distance_miles = (
            criteria.preferred_substation_distance_miles or self._preferred_substation_distance(text)
        )
        criteria.preferred_transmission_voltage_kv = (
            criteria.preferred_transmission_voltage_kv or self._preferred_transmission_voltage(text)
        )
        criteria.project_use = criteria.project_use or self._project_use(lowered)
        criteria.parsed_summary_zh = self._summary(criteria)
        return criteria

    def _merge_regions(self, existing: SiteHunterRegions, text: str, lowered: str) -> SiteHunterRegions:
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
        for state_value in list(regions.states):
            state = normalize_state(state_value)
            if state:
                regions.states[regions.states.index(state_value)] = state.name
                if state.code not in regions.state_codes:
                    regions.state_codes.append(state.code)

        for zip_code in re.findall(r"\b\d{5}(?:-\d{4})?\b", text):
            if zip_code not in regions.zip_codes:
                regions.zip_codes.append(zip_code)

        county_matches = re.findall(r"([A-Za-z][A-Za-z\s.'-]+)\s+County", text)
        county_matches += re.findall(r"([\u4e00-\u9fffA-Za-z\s.'-]+)县", text)
        for county in county_matches:
            cleaned = county.strip()
            if cleaned and cleaned not in regions.counties:
                regions.counties.append(cleaned)
        return regions

    def _contains_state_alias(self, text: str, lowered: str, alias: str) -> bool:
        if len(alias) == 2 and alias.isascii():
            stripped = text.strip().strip(",.;:，。；：")
            if stripped.lower() == alias.lower():
                return True
            return bool(re.search(rf"\b{re.escape(alias.upper())}\b", text))
        return alias in lowered

    def _search_anchor(self, text: str, regions: SiteHunterRegions) -> SiteSearchAnchor | None:
        coordinate_match = re.search(r"(-?\d{1,3}(?:\.\d+)?)\s*[,，]\s*(-?\d{1,3}(?:\.\d+)?)", text)
        if coordinate_match:
            first = float(coordinate_match.group(1))
            second = float(coordinate_match.group(2))
            lat, lon = self._normalize_us_coordinate_pair(first, second)
            return SiteSearchAnchor(
                input_type=SearchAnchorType.COORDINATES,
                raw_input=coordinate_match.group(0),
                label=f"{lat:.6f}, {lon:.6f}",
                latitude=lat,
                longitude=lon,
                radius_miles=regions.radius_miles,
                source_name="user_input",
                confidence=0.95,
                status=SearchAnchorStatus.UNRESOLVED,
            )
        if len(regions.zip_codes) == 1:
            return SiteSearchAnchor(
                input_type=SearchAnchorType.ZIP_CODE,
                raw_input=regions.zip_codes[0],
                label=regions.zip_codes[0],
                zip_code=regions.zip_codes[0][:5],
                radius_miles=regions.radius_miles,
                source_name="user_input",
                confidence=0.6,
                status=SearchAnchorStatus.UNRESOLVED,
            )
        return None

    def _normalize_us_coordinate_pair(self, first: float, second: float) -> tuple[float, float]:
        if 24 <= first <= 50 and -125 <= second <= -66:
            return first, second
        if 24 <= second <= 50 and -125 <= first <= -66:
            return second, first
        return first, second

    def _property_types(self, text: str, lowered: str, existing: list[str]) -> list[str]:
        types = list(existing)
        mapping = [
            (["旧工厂", "旧制造", "former factory", "closed manufacturing"], "former manufacturing facility"),
            (["制造工厂", "制造设施", "manufacturing"], "manufacturing facility"),
            (["工业土地", "industrial land"], "industrial land"),
            (["重工业", "heavy industrial"], "heavy industrial property"),
            (["仓库", "warehouse"], "warehouse"),
            (["配送中心", "distribution"], "distribution center"),
            (["棕地", "brownfield"], "brownfield industrial site"),
            (["可立即建设", "shovel"], "shovel-ready industrial site"),
        ]
        for tokens, value in mapping:
            if any(token in text or token in lowered for token in tokens) and value not in types:
                types.append(value)
        return types or ["industrial property", "industrial land"]

    def _transaction_types(self, text: str, lowered: str, existing: list[str]) -> list[str]:
        types = list(existing or [])
        if ("租" in text or "lease" in lowered) and "for lease" not in types:
            types.append("for lease")
        if ("买" in text or "售" in text or "sale" in lowered) and "for sale" not in types:
            types.append("for sale")
        return types or ["for sale"]

    def _land_acres(self, text: str) -> float | None:
        acre_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+|以上|至少|英亩|acres?)", text, flags=re.IGNORECASE)
        if acre_match:
            return float(acre_match.group(1))
        mu_match = re.search(r"(\d+(?:\.\d+)?)\s*亩", text)
        if mu_match:
            return round(float(mu_match.group(1)) * 0.1647, 2)
        return None

    def _building_sqft(self, text: str) -> float | None:
        sqft_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:sqft|square feet|平方英尺)", text, flags=re.IGNORECASE)
        if sqft_match:
            return float(sqft_match.group(1).replace(",", ""))
        sqm_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:平方米|平米)", text)
        if sqm_match:
            return round(float(sqm_match.group(1).replace(",", "")) * 10.7639, 2)
        return None

    def _max_price(self, text: str) -> float | None:
        usd_million = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:million\b|m\b)\s*(?:usd|dollars?)?",
            text,
            flags=re.IGNORECASE,
        )
        if usd_million:
            return float(usd_million.group(1)) * 1_000_000
        chinese_usd = re.search(r"(\d+(?:\.\d+)?)\s*万\s*美元", text)
        if chinese_usd:
            return float(chinese_usd.group(1)) * 10_000
        dollar = re.search(r"\$?\s*(\d+(?:,\d{3})+(?:\.\d+)?)", text)
        if dollar:
            return float(dollar.group(1).replace(",", ""))
        return None

    def _target_load(self, text: str) -> float | None:
        mw = re.search(r"(\d+(?:\.\d+)?)\s*(?:mw|兆瓦)", text, flags=re.IGNORECASE)
        return float(mw.group(1)) if mw else None

    def _preferred_substation_distance(self, text: str) -> float | None:
        if "变电站" not in text and "substation" not in text.lower():
            return None
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:英里|mile|miles)", text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
        km_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:公里|km)", text, flags=re.IGNORECASE)
        if km_match:
            return round(float(km_match.group(1)) * 0.6214, 2)
        return None

    def _search_radius(self, text: str) -> float | None:
        match = re.search(r"(?:周边|半径|附近|within|radius)?\s*(\d+(?:\.\d+)?)\s*(?:英里|mile|miles|mi)", text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
        km_match = re.search(r"(?:周边|半径|附近|within|radius)?\s*(\d+(?:\.\d+)?)\s*(?:公里|km)", text, flags=re.IGNORECASE)
        if km_match:
            return round(float(km_match.group(1)) * 0.6214, 2)
        return None

    def _preferred_transmission_voltage(self, text: str) -> float | None:
        kv = re.search(r"(\d+(?:\.\d+)?)\s*(?:kv|kV|千伏)", text)
        return float(kv.group(1)) if kv else None

    def _project_use(self, lowered: str) -> str | None:
        for alias, value in PROJECT_USE_ALIASES.items():
            if alias in lowered:
                return value
        return None

    def _summary(self, criteria: SiteHunterStructuredCriteria) -> str:
        states = "、".join(criteria.regions.states) or "未指定州"
        property_types = "、".join(criteria.property_types) or "工业地产"
        details = [f"区域：{states}", f"类型：{property_types}"]
        if criteria.min_land_acres:
            details.append(f"最低土地面积：{criteria.min_land_acres} acres")
        if criteria.max_price_usd:
            details.append(f"最高预算：${criteria.max_price_usd:,.0f}")
        if criteria.target_load_mw:
            details.append(f"目标负荷：{criteria.target_load_mw}MW")
        if criteria.search_anchor:
            details.append(f"搜索中心：{criteria.search_anchor.label or criteria.search_anchor.raw_input or 'unknown'}")
            if criteria.search_anchor.radius_miles:
                details.append(f"搜索半径：{criteria.search_anchor.radius_miles} miles")
        return "；".join(details)
