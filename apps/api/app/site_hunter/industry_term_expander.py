from __future__ import annotations


INDUSTRY_TERM_MAP: dict[str, list[str]] = {
    "former manufacturing facility": [
        "former manufacturing facility",
        "former factory",
        "closed manufacturing plant",
        "decommissioned industrial facility",
    ],
    "manufacturing facility": [
        "manufacturing facility",
        "manufacturing plant",
        "industrial facility",
        "industrial building",
    ],
    "industrial land": [
        "industrial land",
        "industrial site",
        "industrial acreage",
        "industrial development site",
    ],
    "heavy industrial property": [
        "heavy industrial property",
        "heavy industrial land",
        "heavy industrial site",
    ],
    "warehouse": ["warehouse", "industrial warehouse", "logistics warehouse"],
    "distribution center": ["distribution center", "logistics facility"],
    "brownfield industrial site": ["brownfield industrial site", "redevelopment industrial site"],
    "shovel-ready industrial site": ["shovel-ready industrial site", "development-ready industrial site"],
    "powered land": ["powered land", "power-ready site", "utility-served industrial site"],
}


class IndustryTermExpander:
    def expand_property_types(self, property_types: list[str]) -> list[str]:
        terms: list[str] = []
        for property_type in property_types:
            mapped = INDUSTRY_TERM_MAP.get(property_type, [property_type])
            for term in mapped:
                if term not in terms:
                    terms.append(term)
        return terms or ["industrial property", "industrial land"]

    def power_context_terms(self) -> list[str]:
        return [
            "near substation",
            "near transmission line",
            "utility-served site",
            "large-load industrial site",
            "powered land for data center",
        ]
