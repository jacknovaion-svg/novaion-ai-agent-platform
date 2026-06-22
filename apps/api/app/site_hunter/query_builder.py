from __future__ import annotations

from app.site_hunter.industry_term_expander import IndustryTermExpander
from app.site_hunter.models import GeneratedSearchQuery, SiteHunterStructuredCriteria


class EnglishSearchQueryBuilder:
    def __init__(self) -> None:
        self.expander = IndustryTermExpander()

    def build(self, criteria: SiteHunterStructuredCriteria) -> list[GeneratedSearchQuery]:
        regions = self._region_phrases(criteria)
        terms = self.expander.expand_property_types(criteria.property_types)
        transaction = criteria.transaction_types[0] if criteria.transaction_types else "for sale"
        area_suffix = f" {criteria.min_land_acres:g}+ acres" if criteria.min_land_acres else ""
        price_suffix = f" under ${criteria.max_price_usd:,.0f}" if criteria.max_price_usd else ""

        queries: list[GeneratedSearchQuery] = []
        for region in regions:
            state, county, city, phrase = region
            for term in terms[:5]:
                queries.append(
                    GeneratedSearchQuery(
                        generated_query_en=f"{term} {transaction} {phrase}{area_suffix}{price_suffix}".strip(),
                        source_group="property_market",
                        state=state,
                        county=county,
                        city=city,
                        property_type=term,
                    )
                )
            queries.extend(
                [
                    GeneratedSearchQuery(
                        generated_query_en=f"economic development available sites {phrase}",
                        source_group="economic_development",
                        state=state,
                        county=county,
                        city=city,
                    ),
                    GeneratedSearchQuery(
                        generated_query_en=f"industrial park available buildings {phrase}",
                        source_group="industrial_park",
                        state=state,
                        county=county,
                        city=city,
                    ),
                    GeneratedSearchQuery(
                        generated_query_en=f"commercial real estate industrial broker {phrase}",
                        source_group="local_brokerage",
                        state=state,
                        county=county,
                        city=city,
                    ),
                    GeneratedSearchQuery(
                        generated_query_en=f"powered land for data center {state or phrase}",
                        source_group="utility",
                        state=state,
                        county=county,
                        city=city,
                    ),
                    GeneratedSearchQuery(
                        generated_query_en=f"shovel-ready industrial site {state or phrase}",
                        source_group="economic_development",
                        state=state,
                        county=county,
                        city=city,
                    ),
                ]
            )
        return self._dedupe(queries)[:40]

    def _region_phrases(self, criteria: SiteHunterStructuredCriteria) -> list[tuple[str | None, str | None, str | None, str]]:
        regions = criteria.regions
        phrases: list[tuple[str | None, str | None, str | None, str]] = []
        for state in regions.states:
            phrases.append((state, None, None, state))
            for county in regions.counties:
                phrases.append((state, county, None, f"{county} County {state}"))
            for city in regions.cities:
                phrases.append((state, None, city, f"{city} {state}"))
        if not phrases:
            for zip_code in regions.zip_codes:
                phrases.append((None, None, None, zip_code))
        if not phrases and regions.custom_area:
            phrases.append((None, None, None, regions.custom_area))
        return phrases or [(None, None, None, "United States")]

    def _dedupe(self, queries: list[GeneratedSearchQuery]) -> list[GeneratedSearchQuery]:
        seen: set[str] = set()
        output: list[GeneratedSearchQuery] = []
        for query in queries:
            key = query.generated_query_en.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(query)
        return output
