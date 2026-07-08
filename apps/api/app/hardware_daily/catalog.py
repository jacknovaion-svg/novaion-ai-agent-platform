from __future__ import annotations

import re
from urllib.parse import quote_plus

from app.core.config import get_settings
from app.hardware_daily.models import HardwareCategory, HardwareGeneratedQuery, HardwareScanDepth, HardwareScanLane, HardwareScanScope


ACTIVE_SOURCE_DOMAINS = {
    "GovDeals": "govdeals.com",
    "Public Surplus": "publicsurplus.com",
    "Municibid": "municibid.com",
    "GSA Auctions": "gsaauctions.gov",
    "GovAuctions.app": "govauctions.app",
}

RESERVED_SOURCE_DOMAINS = {
    "eBay": "ebay.com",
    "HGP Industrial Auctions": "hgpauction.com",
    "GSA Auctions": "gsaauctions.gov",
    "AllSurplus": "allsurplus.com",
    "BidSpotter": "bidspotter.com",
    "Proxibid": "proxibid.com",
    "R2 Directory": "sustainableelectronics.org",
    "e-Stewards Directory": "e-stewards.org",
    "NAID AAA Directory": "isigmaonline.org",
}

DEEP_PLANNED_SOURCE_DOMAINS = {
    "eBay": "ebay.com",
    "HGP Industrial Auctions": "hgpauction.com",
    "AllSurplus": "allsurplus.com",
    "BidSpotter": "bidspotter.com",
    "Proxibid": "proxibid.com",
}

SOURCE_CONFIGS = {
    "GovDeals": {
        "enabled": True,
        "scan_lane": HardwareScanLane.FAST,
        "default_timeout_seconds": 12,
        "max_retries": 0,
        "max_concurrency": 1,
        "cache_ttl_minutes": 30,
        "categories_supported": [category.value for category in HardwareCategory],
        "health_status": "healthy",
    },
    "Public Surplus": {
        "enabled": True,
        "scan_lane": HardwareScanLane.FAST,
        "default_timeout_seconds": 12,
        "max_retries": 0,
        "max_concurrency": 1,
        "cache_ttl_minutes": 30,
        "categories_supported": [category.value for category in HardwareCategory],
        "health_status": "healthy",
    },
    "Municibid": {
        "enabled": True,
        "scan_lane": HardwareScanLane.FAST,
        "default_timeout_seconds": 12,
        "max_retries": 0,
        "max_concurrency": 1,
        "cache_ttl_minutes": 30,
        "categories_supported": [category.value for category in HardwareCategory],
        "health_status": "healthy",
    },
    "GSA Auctions": {
        "enabled": True,
        "scan_lane": HardwareScanLane.FAST,
        "default_timeout_seconds": 12,
        "max_retries": 0,
        "max_concurrency": 1,
        "cache_ttl_minutes": 30,
        "categories_supported": [category.value for category in HardwareCategory],
        "health_status": "healthy",
        "source_type": "auction_public_json_or_search",
    },
    "GovAuctions.app": {
        "enabled": True,
        "scan_lane": HardwareScanLane.FAST,
        "default_timeout_seconds": 12,
        "max_retries": 0,
        "max_concurrency": 1,
        "cache_ttl_minutes": 30,
        "categories_supported": [category.value for category in HardwareCategory],
        "health_status": "healthy",
        "source_type": "aggregator_meta_source",
    },
    **{
        name: {
            "enabled": False,
            "scan_lane": HardwareScanLane.DEEP,
            "default_timeout_seconds": 20,
            "max_retries": 0,
            "max_concurrency": 1,
            "cache_ttl_minutes": 120,
            "categories_supported": [category.value for category in HardwareCategory],
            "health_status": "planned",
        }
        for name in ["eBay", "HGP Industrial Auctions", "AllSurplus", "BidSpotter", "Proxibid"]
    },
}


CATEGORY_TERMS: dict[HardwareCategory, list[str]] = {
    HardwareCategory.SERVERS: [
        "server",
        "servers",
        "supermicro",
        "poweredge",
        "Dell PowerEdge",
        "rack server",
        "rack servers",
        "gpu server",
        "gpu servers",
        "ai server",
        "ai servers",
        "blade server",
        "storage server",
        "compute server",
        "enterprise server",
        "dell server",
        "hpe server",
        "hp proliant",
        "lenovo thinksystem",
        "cisco ucs",
        "HPE ProLiant",
        "Supermicro server",
        "Lenovo ThinkSystem",
        "Cisco UCS",
        "rack server",
        "blade server",
        "server lot",
        "compute node",
        "data center equipment",
    ],
    HardwareCategory.GPU: [
        "gpu",
        "gpus",
        "nvidia",
        "rtx",
        "a6000",
        "a5000",
        "a100",
        "h100",
        "h200",
        "b200",
        "b300",
        "NVIDIA GPU",
        "Tesla GPU",
        "NVIDIA A100",
        "NVIDIA V100",
        "NVIDIA P100",
        "NVIDIA T4",
        "NVIDIA A40",
        "NVIDIA A6000",
        "GPU server",
        "graphics card lot",
        "accelerator card",
    ],
    HardwareCategory.MEMORY: [
        "memory",
        "ddr4",
        "ddr5",
        "ecc memory",
        "DDR4 ECC",
        "DDR5 ECC",
        "RDIMM",
        "LRDIMM",
        "server memory",
        "memory modules lot",
        "ECC RAM",
        "32GB server memory",
        "64GB server memory",
    ],
    HardwareCategory.STORAGE: [
        "ssd",
        "nvme",
        "hard drive",
        "enterprise SSD",
        "NVMe SSD",
        "U.2 NVMe",
        "SAS SSD",
        "SAS drives",
        "server hard drives",
        "storage array",
        "Dell storage",
        "NetApp",
        "EMC storage",
    ],
    HardwareCategory.CPU: [
        "Intel Xeon",
        "Xeon Gold",
        "Xeon Platinum",
        "AMD EPYC",
        "server processors",
        "CPU lot",
        "matched CPU pairs",
        "processor lot",
    ],
    HardwareCategory.NETWORKING: [
        "Cisco switch",
        "Juniper switch",
        "network switch",
        "router",
        "firewall",
        "networking equipment",
        "Cisco lot",
        "Juniper router",
    ],
    HardwareCategory.COMPUTERS_IT: [
        "computer equipment",
        "workstation",
        "desktop computer",
        "laptop lot",
        "electronics lot",
        "IT equipment",
        "computer lot",
        "office computers",
    ],
}


STATE_HINTS = {
    "TX": "Texas",
    "CA": "California",
    "GA": "Georgia",
    "OR": "Oregon",
    "NC": "North Carolina",
    "OK": "Oklahoma",
    "AZ": "Arizona",
    "NV": "Nevada",
    "VA": "Virginia",
    "IL": "Illinois",
    "OH": "Ohio",
    "NY": "New York",
    "FL": "Florida",
}

STATE_METROS = {
    "OR": ["Portland, OR", "Salem, OR", "Eugene, OR"],
    "NC": ["Charlotte, NC", "Raleigh, NC", "Durham, NC", "Greensboro, NC"],
    "CA": ["Los Angeles, CA", "San Jose, CA", "San Diego, CA", "Sacramento, CA"],
    "GA": ["Atlanta, GA", "Savannah, GA", "Augusta, GA"],
    "OK": ["Oklahoma City, OK", "Tulsa, OK"],
    "TX": ["Dallas, TX", "Houston, TX", "Austin, TX", "San Antonio, TX"],
}

SCAN_DEPTH_LIMITS = {
    HardwareScanDepth.QUICK: 2,
    HardwareScanDepth.STANDARD: 5,
    HardwareScanDepth.DEEP: 10,
}

SOURCE_QUERY_LIMITS = {
    "GovDeals": 5,
    "Public Surplus": 5,
    "Municibid": 5,
    "GSA Auctions": 3,
    "AllSurplus": 3,
    "BidSpotter": 3,
    "Proxibid": 3,
    "eBay": 3,
    "HGP Industrial Auctions": 3,
}


class HardwareSearchQueryBuilder:
    def build(
        self,
        categories: list[HardwareCategory] | None = None,
        states: list[str] | None = None,
        max_queries_per_category: int = 8,
        scan_depth: HardwareScanDepth = HardwareScanDepth.STANDARD,
        scan_lane: HardwareScanLane = HardwareScanLane.FAST,
        scan_scope: HardwareScanScope = HardwareScanScope.NATIONWIDE,
    ) -> list[HardwareGeneratedQuery]:
        selected_categories = categories or list(HardwareCategory)
        state_targets = self._state_targets(states or []) if scan_scope == HardwareScanScope.LEGACY_STATE else self._state_targets([])
        query_limit = min(max_queries_per_category, SCAN_DEPTH_LIMITS.get(scan_depth, 5))
        queries: list[HardwareGeneratedQuery] = []
        seen: set[str] = set()
        for category in selected_categories:
            category_terms = CATEGORY_TERMS[category]
            source_domains = ACTIVE_SOURCE_DOMAINS if scan_lane == HardwareScanLane.FAST else DEEP_PLANNED_SOURCE_DOMAINS
            settings = get_settings()
            enabled_sources = {
                source_name: domain
                for source_name, domain in source_domains.items()
                if (
                    (source_name != "GovAuctions.app" or settings.enable_govauctions_app_source)
                    and (SOURCE_CONFIGS.get(source_name, {}).get("enabled", False) or scan_lane == HardwareScanLane.FAST)
                )
            }
            for source_name, domain in enabled_sources.items():
                source_query_limit = min(query_limit, SOURCE_QUERY_LIMITS.get(source_name, query_limit))
                for target in state_targets:
                    for index, term in enumerate(category_terms[:source_query_limit], start=1):
                        query = self._build_source_query(source_name, domain, term, target["location_phrase"])
                        dedupe_key = self._dedupe_key(source_name, category.value, term, target["state_code"] if scan_scope == HardwareScanScope.LEGACY_STATE else None, query)
                        if dedupe_key in seen:
                            continue
                        seen.add(dedupe_key)
                        queries.append(
                            HardwareGeneratedQuery(
                                category=category,
                                source_group=source_name,
                                generated_query_en=query,
                                query_template_id=f"{source_name.lower().replace(' ', '_')}:{category.value}:{index}",
                                query_template=term,
                                state_code=target["state_code"] if scan_scope == HardwareScanScope.LEGACY_STATE else None,
                                state_name=target["state_name"] if scan_scope == HardwareScanScope.LEGACY_STATE else None,
                                location_phrase=target["location_phrase"] if scan_scope == HardwareScanScope.LEGACY_STATE else None,
                                scan_depth=scan_depth,
                                scan_lane=scan_lane,
                            )
                        )
        return queries

    def planned_deep_queries(
        self,
        categories: list[HardwareCategory] | None = None,
        states: list[str] | None = None,
        scan_depth: HardwareScanDepth = HardwareScanDepth.STANDARD,
        scan_scope: HardwareScanScope = HardwareScanScope.NATIONWIDE,
    ) -> list[HardwareGeneratedQuery]:
        selected_categories = categories or list(HardwareCategory)
        state_targets = self._state_targets(states or []) if scan_scope == HardwareScanScope.LEGACY_STATE else self._state_targets([])
        queries: list[HardwareGeneratedQuery] = []
        for category in selected_categories:
            term = CATEGORY_TERMS[category][0]
            for source_name, domain in DEEP_PLANNED_SOURCE_DOMAINS.items():
                target = state_targets[0]
                query = self._build_source_query(source_name, domain, term, target["location_phrase"])
                queries.append(
                    HardwareGeneratedQuery(
                        category=category,
                        source_group=source_name,
                        generated_query_en=query,
                        query_template_id=f"{source_name.lower().replace(' ', '_')}:planned:{category.value}",
                        query_template=term,
                        state_code=target["state_code"] if scan_scope == HardwareScanScope.LEGACY_STATE else None,
                        state_name=target["state_name"] if scan_scope == HardwareScanScope.LEGACY_STATE else None,
                        location_phrase=target["location_phrase"] if scan_scope == HardwareScanScope.LEGACY_STATE else None,
                        scan_depth=scan_depth,
                        scan_lane=HardwareScanLane.DEEP,
                        status="planned",
                    )
                )
        return queries

    def _state_targets(self, states: list[str]) -> list[dict[str, str | None]]:
        normalized: list[dict[str, str | None]] = []
        for state in states:
            token = state.strip().upper()
            if not token:
                continue
            state_name = STATE_HINTS.get(token, state.strip())
            metros = STATE_METROS.get(token, [])
            if metros:
                quoted = [self._quote(state_name), *[self._quote(city) for city in metros]]
                location_phrase = f"({' OR '.join(quoted)})"
            else:
                location_phrase = self._quote(state_name)
            normalized.append({"state_code": token, "state_name": state_name, "location_phrase": location_phrase})
        return normalized or [{"state_code": None, "state_name": None, "location_phrase": ""}]

    def _build_source_query(self, source_name: str, domain: str, term: str, location_phrase: str) -> str:
        quoted_term = self._quote(term) if self._should_quote(term) else term
        if source_name == "GovDeals":
            parts = [f"site:{domain}/en/asset", quoted_term, "auction lot", location_phrase]
        elif source_name == "Public Surplus":
            parts = [f"site:{domain}/sms/auction/view", quoted_term, "surplus auction", location_phrase]
        elif source_name == "Municibid":
            parts = [f"site:{domain}", quoted_term, '"Computers & IT"', "government auction", location_phrase]
        elif source_name == "GSA Auctions":
            parts = [f"site:{domain}", quoted_term, "government auction", location_phrase]
        elif source_name == "GovAuctions.app":
            parts = [f"https://{domain}/feed?q={quote_plus(term)}&sort=relevance"]
        elif source_name == "AllSurplus":
            parts = [f"site:{domain}", quoted_term, "auction lot", "surplus", location_phrase]
        elif source_name in {"BidSpotter", "Proxibid"}:
            parts = [f"site:{domain}", quoted_term, "auction lot", location_phrase]
        elif source_name == "eBay":
            parts = [f"site:{domain}/itm", quoted_term, "lot", location_phrase]
        elif source_name == "HGP Industrial Auctions":
            parts = [f"site:{domain}", quoted_term, "industrial auction", location_phrase]
        else:
            parts = [f"site:{domain}", quoted_term, "auction surplus", location_phrase]
        return self._normalize_query(" ".join(part for part in parts if part))

    def _quote(self, value: str) -> str:
        cleaned = value.strip().strip('"')
        return f'"{cleaned}"'

    def _should_quote(self, value: str) -> bool:
        return " " in value.strip() or any(char.isdigit() for char in value)

    def _normalize_query(self, query: str) -> str:
        return re.sub(r"\s+", " ", query.replace('""', '"')).strip()

    def _dedupe_key(self, source_name: str, category: str, term: str, state_code: str | None, query: str) -> str:
        normalized_query = self._normalize_query(query).lower()
        return f"{source_name.lower()}|{category}|{term.lower()}|{state_code or 'all'}|{normalized_query}"
