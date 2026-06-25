from __future__ import annotations

from app.supplier_hunter.models import SupplierGeneratedQuery, SupplierRegionSubJob, SupplierSearchCriteria
from app.supplier_hunter.state_profiles import get_supplier_state_profile


DEFAULT_SUPPLIER_TYPES = [
    "R2 certified ITAD company",
    "data center decommissioning",
    "enterprise IT asset disposition",
    "used server wholesaler",
    "server refurbishment company",
    "data center equipment buyer",
    "asset remarketing company",
    "bulk used laptops wholesale",
    "used enterprise server supplier",
]


class SupplierSearchQueryBuilder:
    def build(self, criteria: SupplierSearchCriteria) -> tuple[dict | None, list[SupplierRegionSubJob], list[SupplierGeneratedQuery]]:
        state_code = criteria.regions.state_codes[0] if criteria.regions.state_codes else None
        profile = get_supplier_state_profile(state_code)
        if not profile:
            return None, [], self._fallback_queries(criteria)

        subjobs = [
            SupplierRegionSubJob(
                state_code=profile["state_code"],
                state_name=profile["state_name"],
                region_name=region.name,
                cities=list(region.cities),
            )
            for region in profile["regions"]
        ]
        supplier_terms = self._supplier_terms(criteria)
        queries: list[SupplierGeneratedQuery] = []
        for region in profile["regions"]:
            for phrase in region.search_phrases[:2]:
                for supplier_type in supplier_terms[:5]:
                    queries.append(
                        SupplierGeneratedQuery(
                            generated_query_en=f"{supplier_type} {phrase}",
                            source_group="regional_supplier_search",
                            state=profile["state_name"],
                            state_code=profile["state_code"],
                            city=region.cities[0] if region.cities else None,
                            region_name=region.name,
                            supplier_type=supplier_type,
                        )
                    )
        for query in profile["statewide_queries"]:
            queries.append(
                SupplierGeneratedQuery(
                    generated_query_en=query,
                    source_group="statewide_supplier_search",
                    state=profile["state_name"],
                    state_code=profile["state_code"],
                    region_name="Statewide",
                )
            )
        queries = self._dedupe(queries)
        for subjob in subjobs:
            subjob.generated_query_count = len([query for query in queries if query.region_name == subjob.region_name])
        return profile, subjobs, queries

    def _supplier_terms(self, criteria: SupplierSearchCriteria) -> list[str]:
        output = list(criteria.supplier_types)
        for item in DEFAULT_SUPPLIER_TYPES:
            if item not in output:
                output.append(item)
        return output

    def _fallback_queries(self, criteria: SupplierSearchCriteria) -> list[SupplierGeneratedQuery]:
        states = criteria.regions.states or ["United States"]
        terms = self._supplier_terms(criteria)
        queries = [
            SupplierGeneratedQuery(
                generated_query_en=f"{term} {state}",
                source_group="supplier_search",
                state=state,
                supplier_type=term,
            )
            for state in states
            for term in terms[:8]
        ]
        return self._dedupe(queries)

    def _dedupe(self, queries: list[SupplierGeneratedQuery]) -> list[SupplierGeneratedQuery]:
        seen: set[str] = set()
        output: list[SupplierGeneratedQuery] = []
        for query in queries:
            key = query.generated_query_en.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(query)
        return output

