from __future__ import annotations

from urllib.parse import quote_plus

from app.site_hunter.models import NormalizedSiteListing, PowerSourceRecord, TrustLevel, UtilityCandidate


class UtilityTerritoryResolver:
    def resolve(self, site: NormalizedSiteListing) -> UtilityCandidate:
        state = (site.state or "").lower()
        city = (site.city or "").lower()
        if state == "georgia":
            if city in {"gainesville", "jackson", "acworth", "cordele"}:
                return UtilityCandidate(
                    likely_utility="Georgia Power or local EMC service territory",
                    utility_type="investor_owned_or_cooperative",
                    evidence=f"Estimated from city/state: {site.city}, {site.state}. Must verify with parcel and utility territory map.",
                    source_url="https://www.georgiapower.com/business/economic-development.html",
                    confidence_level=TrustLevel.ESTIMATED,
                    status=TrustLevel.ESTIMATED,
                )
        if state == "texas":
            return UtilityCandidate(
                likely_utility="Texas deregulated market / local TDU to verify",
                utility_type="tdsp_or_cooperative_unknown",
                evidence=f"Estimated from city/state: {site.city}, {site.state}. Texas service territory must be verified by address.",
                source_url="https://www.puc.texas.gov/industry/electric/maps/",
                confidence_level=TrustLevel.ESTIMATED,
                status=TrustLevel.ESTIMATED,
            )
        return UtilityCandidate(
            likely_utility=None,
            utility_type="unknown",
            evidence="No utility territory was confirmed from the available listing fields.",
            confidence_level=TrustLevel.UNKNOWN,
            status=TrustLevel.UNKNOWN,
        )


class GovernmentGISDiscoveryService:
    def build_source_records(self, site: NormalizedSiteListing, utility: UtilityCandidate) -> list[PowerSourceRecord]:
        location_parts = [site.city, site.county, site.state]
        location = " ".join(part for part in location_parts if part) or "United States"
        utility_name = utility.likely_utility or "electric utility"
        queries = [
            f"{site.state or location} electric substation GIS",
            f"{site.county or site.city or location} substation ArcGIS",
            f"{site.city or location} electric utility infrastructure map",
            f"{utility_name} transmission map",
            f"{utility_name} substation map",
            f"{utility_name} service territory map",
            f"{utility_name} economic development power map",
        ]
        records: list[PowerSourceRecord] = []
        for query in dict.fromkeys(queries):
            records.append(
                PowerSourceRecord(
                    source_name="Generated GIS Discovery Task",
                    source_type="gis_discovery_query",
                    generated_query=query,
                    source_url=f"https://duckduckgo.com/?q={quote_plus(query)}",
                    confidence_level=TrustLevel.UNKNOWN,
                )
            )
        return records
