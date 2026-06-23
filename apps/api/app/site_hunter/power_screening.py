from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.site_hunter.geocoding import GeocodingService
from app.site_hunter.models import (
    GeocodingResult,
    LandIdReview,
    NearbyPowerAsset,
    NormalizedSiteListing,
    PowerAddressStatus,
    PowerAssetType,
    SitePowerAssessment,
    TrustLevel,
)
from app.site_hunter.power_adapters import OpenStreetMapPowerAdapter
from app.site_hunter.transmission import NearbyTransmissionLineService
from app.site_hunter.utility import GovernmentGISDiscoveryService, UtilityTerritoryResolver


class PowerScreeningService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.geocoding = GeocodingService()
        self.osm = OpenStreetMapPowerAdapter()
        self.nearby_transmission = NearbyTransmissionLineService()
        self.utility = UtilityTerritoryResolver()
        self.gis_discovery = GovernmentGISDiscoveryService()

    async def assess_site(self, site: NormalizedSiteListing) -> NormalizedSiteListing:
        geocoding = await self.geocoding.geocode_site(site)
        site.standardized_address = geocoding.standardized_address
        site.latitude = geocoding.latitude
        site.longitude = geocoding.longitude
        site.geocoding_source = geocoding.source_name
        site.geocoding_confidence = geocoding.confidence
        if geocoding.county and not site.county:
            site.county = geocoding.county
        if geocoding.state and not site.state:
            site.state = geocoding.state
        if geocoding.zip_code and not site.zip_code:
            site.zip_code = geocoding.zip_code

        utility_candidate = self.utility.resolve(site)
        assessment = SitePowerAssessment(
            site_id=site.id,
            address_status=geocoding.status,
            raw_address=geocoding.raw_address,
            standardized_address=geocoding.standardized_address,
            latitude=geocoding.latitude,
            longitude=geocoding.longitude,
            geocoding_source=geocoding.source_name,
            geocoding_confidence=geocoding.confidence,
            likely_utility=utility_candidate,
            power_source_records=self.gis_discovery.build_source_records(site, utility_candidate),
            confidence_level=TrustLevel.UNKNOWN,
            error_message=geocoding.error_message,
        )

        site.land_id_review.land_id_map_url = site.land_id_review.land_id_map_url or self._land_id_url(site, geocoding)

        if not self._can_calculate_distances(geocoding):
            assessment.address_status = geocoding.status
            assessment.error_message = geocoding.error_message or "Address or coordinates need manual verification before precise power distance screening."
            site.power_assessment = assessment
            site.warnings.append("Power screening skipped until address or coordinates are verified.")
            return site

        nearby_assets = await self._nearby_assets(geocoding.latitude, geocoding.longitude)
        for asset in nearby_assets:
            asset.site_id = site.id
        assessment.nearby_assets = nearby_assets
        assessment.nearest_substation = self._nearest(nearby_assets, PowerAssetType.SUBSTATION)
        assessment.nearest_transmission_line = self._nearest(nearby_assets, PowerAssetType.TRANSMISSION_LINE)
        assessment.known_voltage_kv = self._highest_voltage(nearby_assets)
        assessment.search_radius_counts = self._radius_counts(nearby_assets)
        assessment.confidence_level = TrustLevel.ESTIMATED if nearby_assets else TrustLevel.UNKNOWN
        site.power_assessment = assessment
        site.warnings.append(assessment.assessment_warning)
        return site

    async def assess_sites(self, sites: list[NormalizedSiteListing]) -> list[NormalizedSiteListing]:
        assessed: list[NormalizedSiteListing] = []
        for site in sites:
            try:
                assessed.append(await asyncio.wait_for(self.assess_site(site), timeout=70))
            except Exception as exc:
                site.power_assessment = SitePowerAssessment(
                    site_id=site.id,
                    address_status=PowerAddressStatus.GEOCODING_FAILED,
                    raw_address=self.geocoding._raw_address(site),
                    error_message=str(exc)[:500],
                )
                assessed.append(site)
        return assessed

    def update_land_id_review(self, site: NormalizedSiteListing, review: LandIdReview) -> NormalizedSiteListing:
        site.land_id_review = review
        return site

    async def _nearby_assets(self, latitude: float | None, longitude: float | None) -> list[NearbyPowerAsset]:
        if latitude is None or longitude is None:
            return []
        assets: list[NearbyPowerAsset] = []
        assets.extend(await self.nearby_transmission.find_nearby(latitude, longitude, max(self.settings.power_search_radii)))
        try:
            assets.extend(await self.osm.search_nearby(latitude, longitude, self.settings.power_search_radii))
        except Exception as exc:
            assets.append(
                NearbyPowerAsset(
                    asset_type=PowerAssetType.TRANSMISSION_LINE,
                    source_name="OpenStreetMap Overpass",
                    confidence_level=TrustLevel.UNKNOWN,
                    verification_status=TrustLevel.UNKNOWN,
                    raw_data_json={"error": str(exc)[:500]},
                )
            )
        return sorted(
            [asset for asset in assets if asset.distance_miles is not None],
            key=lambda item: item.distance_miles if item.distance_miles is not None else 999,
        )

    def _can_calculate_distances(self, geocoding: GeocodingResult) -> bool:
        return (
            geocoding.status in {PowerAddressStatus.VERIFIED_ADDRESS, PowerAddressStatus.GEOCODED_ADDRESS}
            and geocoding.latitude is not None
            and geocoding.longitude is not None
            and geocoding.confidence >= 0.7
        )

    def _nearest(self, assets: list[NearbyPowerAsset], asset_type: PowerAssetType) -> NearbyPowerAsset | None:
        matches = [asset for asset in assets if asset.asset_type == asset_type and asset.distance_miles is not None]
        return min(matches, key=lambda item: item.distance_miles or 999) if matches else None

    def _highest_voltage(self, assets: list[NearbyPowerAsset]) -> float | None:
        voltages = [asset.voltage_kv for asset in assets if asset.voltage_kv]
        return max(voltages) if voltages else None

    def _radius_counts(self, assets: list[NearbyPowerAsset]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for radius in self.settings.power_search_radii:
            counts[f"{radius:g}_mile"] = sum(1 for asset in assets if asset.distance_miles is not None and asset.distance_miles <= radius)
        return counts

    def _land_id_url(self, site: NormalizedSiteListing, geocoding: GeocodingResult) -> str:
        if geocoding.latitude and geocoding.longitude:
            return f"https://id.land/?lat={geocoding.latitude:.6f}&lng={geocoding.longitude:.6f}&z=16"
        return "https://id.land/"
