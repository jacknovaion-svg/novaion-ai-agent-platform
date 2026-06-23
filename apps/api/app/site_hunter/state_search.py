from __future__ import annotations

from app.site_hunter.industry_term_expander import IndustryTermExpander
from app.site_hunter.models import GeneratedSearchQuery, SiteHunterStructuredCriteria, SourceRunStatus, StateRegionSubJob
from app.site_hunter.state_profiles import StateSearchProfile, get_state_search_profile


class StateSearchPlanner:
    def __init__(self) -> None:
        self.expander = IndustryTermExpander()

    def plan(self, criteria: SiteHunterStructuredCriteria) -> tuple[StateSearchProfile | None, list[StateRegionSubJob], list[GeneratedSearchQuery]]:
        if criteria.search_anchor:
            return None, [], []
        if not criteria.regions.state_codes and len(criteria.regions.states) != 1:
            return None, [], []
        state_code = criteria.regions.state_codes[0] if criteria.regions.state_codes else None
        profile = get_state_search_profile(state_code)
        if not profile:
            return None, [], []

        subjobs = [
            StateRegionSubJob(
                state_code=profile.state_code,
                state_name=profile.state_name,
                region_name=region.name,
                region_type=region.region_type,
                cities=list(region.cities),
                counties=list(region.counties),
                status=SourceRunStatus.PENDING,
            )
            for region in profile.regions
        ]
        queries = self._build_queries(profile, criteria)
        for subjob in subjobs:
            subjob.generated_query_count = len([query for query in queries if query.region_name == subjob.region_name])
        return profile, subjobs, queries

    def _build_queries(self, profile: StateSearchProfile, criteria: SiteHunterStructuredCriteria) -> list[GeneratedSearchQuery]:
        terms = self._terms(criteria.property_types)
        transaction = criteria.transaction_types[0] if criteria.transaction_types else "for sale"
        area_suffix = f" {criteria.min_land_acres:g}+ acres" if criteria.min_land_acres else ""
        price_suffix = f" under ${criteria.max_price_usd:,.0f}" if criteria.max_price_usd else ""
        queries: list[GeneratedSearchQuery] = []

        for region in profile.regions:
            phrases = list(region.search_phrases)
            for city in region.cities[:2]:
                phrase = f"{city} {profile.state_name}"
                if phrase not in phrases:
                    phrases.append(phrase)
            for county in region.counties[:2]:
                phrase = f"{self._county_phrase(county)} {profile.state_name}"
                if phrase not in phrases:
                    phrases.append(phrase)

            for phrase in phrases[:4]:
                for term in terms[:4]:
                    queries.append(
                        GeneratedSearchQuery(
                            generated_query_en=f"{term} {transaction} {phrase}{area_suffix}{price_suffix}".strip(),
                            source_group="state_region_property_market",
                            state=profile.state_name,
                            county=region.counties[0] if region.counties else None,
                            city=region.cities[0] if region.cities else None,
                            property_type=term,
                            region_name=region.name,
                            region_type=region.region_type,
                        )
                    )
                queries.extend(
                    [
                        GeneratedSearchQuery(
                            generated_query_en=f"industrial acreage {phrase}",
                            source_group="state_region_property_market",
                            state=profile.state_name,
                            county=region.counties[0] if region.counties else None,
                            city=region.cities[0] if region.cities else None,
                            region_name=region.name,
                            region_type=region.region_type,
                        ),
                        GeneratedSearchQuery(
                            generated_query_en=f"commercial real estate industrial broker {phrase}",
                            source_group="state_region_local_brokerage",
                            state=profile.state_name,
                            county=region.counties[0] if region.counties else None,
                            city=region.cities[0] if region.cities else None,
                            region_name=region.name,
                            region_type=region.region_type,
                        ),
                    ]
                )

        for query in profile.statewide_queries:
            queries.append(
                GeneratedSearchQuery(
                    generated_query_en=query,
                    source_group="state_economic_development",
                    state=profile.state_name,
                    region_name="Statewide",
                    region_type="statewide",
                )
            )
        for query in profile.utility_queries:
            queries.append(
                GeneratedSearchQuery(
                    generated_query_en=query,
                    source_group="state_utility",
                    state=profile.state_name,
                    region_name="Statewide",
                    region_type="utility",
                )
            )
        return self._dedupe(queries)

    def _terms(self, property_types: list[str]) -> list[str]:
        terms: list[str] = []
        for property_type in property_types:
            if property_type not in terms:
                terms.append(property_type)
        for term in self.expander.expand_property_types(property_types):
            if term not in terms:
                terms.append(term)
        fallback = ["industrial land", "former manufacturing facility", "heavy industrial property", "industrial acreage"]
        for term in fallback:
            if term not in terms:
                terms.append(term)
        return terms

    def _county_phrase(self, county: str) -> str:
        cleaned = county.strip()
        return cleaned if cleaned.lower().endswith(" county") else f"{cleaned} County"

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

