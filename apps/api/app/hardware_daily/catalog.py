from __future__ import annotations

import re

from app.hardware_daily.models import HardwareCategory, HardwareGeneratedQuery, HardwareScanDepth


ACTIVE_SOURCE_DOMAINS = {
    "GovDeals": "govdeals.com",
    "Public Surplus": "publicsurplus.com",
}

RESERVED_SOURCE_DOMAINS = {
    "GSA Auctions": "gsaauctions.gov",
    "AllSurplus": "allsurplus.com",
    "Municibid": "municibid.com",
    "BidSpotter": "bidspotter.com",
    "Proxibid": "proxibid.com",
    "eBay": "ebay.com",
    "HGP Industrial Auctions": "hgpauction.com",
}


CATEGORY_TERMS: dict[HardwareCategory, list[str]] = {
    HardwareCategory.SERVERS: [
        "Dell PowerEdge",
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


class HardwareSearchQueryBuilder:
    def build(
        self,
        categories: list[HardwareCategory] | None = None,
        states: list[str] | None = None,
        max_queries_per_category: int = 8,
        scan_depth: HardwareScanDepth = HardwareScanDepth.STANDARD,
    ) -> list[HardwareGeneratedQuery]:
        selected_categories = categories or list(HardwareCategory)
        state_targets = self._state_targets(states or [])
        query_limit = min(max_queries_per_category, SCAN_DEPTH_LIMITS.get(scan_depth, 5))
        queries: list[HardwareGeneratedQuery] = []
        seen: set[str] = set()
        for category in selected_categories:
            category_terms = CATEGORY_TERMS[category]
            for source_name, domain in ACTIVE_SOURCE_DOMAINS.items():
                for target in state_targets:
                    for index, term in enumerate(category_terms[:query_limit], start=1):
                        query = self._build_source_query(source_name, domain, term, target["location_phrase"])
                        dedupe_key = self._dedupe_key(source_name, category.value, term, target["state_code"], query)
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
                                state_code=target["state_code"],
                                state_name=target["state_name"],
                                location_phrase=target["location_phrase"],
                                scan_depth=scan_depth,
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
