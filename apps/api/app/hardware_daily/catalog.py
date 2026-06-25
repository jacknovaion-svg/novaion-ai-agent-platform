from __future__ import annotations

from app.hardware_daily.models import HardwareCategory, HardwareGeneratedQuery


SOURCE_DOMAINS = {
    "GovDeals": "govdeals.com",
    "Public Surplus": "publicsurplus.com",
    "eBay": "ebay.com",
    "HGP Industrial Auctions": "hgpauction.com",
    "Industrial Auction Discovery": "",
}


CATEGORY_TERMS: dict[HardwareCategory, list[str]] = {
    HardwareCategory.SERVERS: [
        "Dell PowerEdge server lot",
        "HPE ProLiant server lot",
        "Supermicro server lot",
        "data center server liquidation",
    ],
    HardwareCategory.GPU: [
        "NVIDIA A100 GPU lot",
        "NVIDIA H100 GPU lot",
        "RTX 4090 bulk lot",
        "data center GPU liquidation",
    ],
    HardwareCategory.MEMORY: [
        "DDR4 ECC RDIMM bulk",
        "DDR5 ECC RDIMM bulk",
        "server memory lot",
        "enterprise memory liquidation",
    ],
    HardwareCategory.STORAGE: [
        "enterprise SSD lot",
        "NVMe SSD bulk",
        "server hard drive lot",
        "data center storage liquidation",
    ],
    HardwareCategory.CPU: [
        "Intel Xeon CPU lot",
        "AMD EPYC CPU lot",
        "server processor bulk",
        "enterprise CPU liquidation",
    ],
}


STATE_HINTS = {
    "TX": "Texas",
    "CA": "California",
    "GA": "Georgia",
    "AZ": "Arizona",
    "NV": "Nevada",
    "VA": "Virginia",
    "IL": "Illinois",
    "OH": "Ohio",
    "NY": "New York",
    "FL": "Florida",
}


class HardwareSearchQueryBuilder:
    def build(
        self,
        categories: list[HardwareCategory] | None = None,
        states: list[str] | None = None,
        max_queries_per_category: int = 8,
    ) -> list[HardwareGeneratedQuery]:
        selected_categories = categories or list(HardwareCategory)
        state_suffixes = self._state_suffixes(states or [])
        queries: list[HardwareGeneratedQuery] = []
        for category in selected_categories:
            category_terms = CATEGORY_TERMS[category]
            category_queries: list[HardwareGeneratedQuery] = []
            for source_name, domain in SOURCE_DOMAINS.items():
                for term in category_terms[:2]:
                    for suffix in state_suffixes:
                        if domain:
                            query = f"site:{domain} {term} {suffix}".strip()
                        else:
                            query = f"{term} auction surplus liquidation {suffix}".strip()
                        category_queries.append(
                            HardwareGeneratedQuery(
                                category=category,
                                source_group=source_name,
                                generated_query_en=query,
                            )
                        )
            queries.extend(self._round_robin_by_source(category_queries, max_queries_per_category))
        return queries

    def _state_suffixes(self, states: list[str]) -> list[str]:
        normalized = []
        for state in states:
            token = state.strip()
            if not token:
                continue
            normalized.append(STATE_HINTS.get(token.upper(), token))
        return normalized or [""]

    def _round_robin_by_source(self, candidates: list[HardwareGeneratedQuery], limit: int) -> list[HardwareGeneratedQuery]:
        by_source: dict[str, list[HardwareGeneratedQuery]] = {}
        for query in candidates:
            by_source.setdefault(query.source_group, []).append(query)
        output: list[HardwareGeneratedQuery] = []
        while len(output) < limit and any(by_source.values()):
            for source in SOURCE_DOMAINS:
                bucket = by_source.get(source) or []
                if bucket:
                    output.append(bucket.pop(0))
                    if len(output) >= limit:
                        break
        return output
