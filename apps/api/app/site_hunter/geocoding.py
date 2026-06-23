from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.site_hunter.models import GeocodingResult, NormalizedSiteListing, PowerAddressStatus, TrustLevel


class GeocodingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._cache: dict[str, GeocodingResult] = {}

    async def geocode_site(self, site: NormalizedSiteListing) -> GeocodingResult:
        raw_address = self._raw_address(site)
        if site.latitude and site.longitude:
            return GeocodingResult(
                raw_address=raw_address,
                standardized_address=raw_address,
                latitude=site.latitude,
                longitude=site.longitude,
                county=site.county,
                state=site.state,
                zip_code=site.zip_code,
                source_name="existing_site_coordinates",
                confidence=0.95,
                status=PowerAddressStatus.VERIFIED_ADDRESS,
            )
        if not self._has_complete_address(site):
            return GeocodingResult(
                raw_address=raw_address,
                standardized_address=raw_address,
                state=site.state,
                zip_code=site.zip_code,
                source_name="site_listing",
                confidence=0.2,
                status=PowerAddressStatus.PARTIAL_ADDRESS if raw_address else PowerAddressStatus.ADDRESS_NEEDS_VERIFICATION,
                error_message="Full address is required before calculating precise power distances.",
            )

        cache_key = raw_address.lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = await self._census_geocode(raw_address)
        for candidate in self._address_variants(raw_address):
            if result.status != PowerAddressStatus.GEOCODING_FAILED:
                break
            result = await self._census_geocode(candidate)
        if result.status == PowerAddressStatus.GEOCODING_FAILED:
            result = await self._nominatim_geocode(raw_address)
            for candidate in self._address_variants(raw_address):
                if result.status != PowerAddressStatus.GEOCODING_FAILED:
                    break
                result = await self._nominatim_geocode(candidate)
        self._cache[cache_key] = result
        return result

    def _raw_address(self, site: NormalizedSiteListing) -> str:
        parts = [site.address_line_1, site.city, site.state, site.zip_code]
        return ", ".join(part for part in parts if part)

    def _has_complete_address(self, site: NormalizedSiteListing) -> bool:
        return bool(site.address_line_1 and site.city and site.state and site.zip_code)

    def _address_variants(self, address: str) -> list[str]:
        variants: list[str] = []
        replacements = [
            ("W Ih-10", "IH 10 W"),
            ("W IH-10", "IH 10 W"),
            ("W Ih 10", "IH 10 W"),
            ("IH-10", "IH 10"),
            ("Ih-10", "I-10"),
            ("Ih 10", "I-10"),
            ("E US Hwy 290", "US Highway 290 E"),
            ("E US Hwy", "US Highway"),
        ]
        for old, new in replacements:
            if old in address:
                variants.append(address.replace(old, new))
        return list(dict.fromkeys(variants))

    async def _census_geocode(self, address: str) -> GeocodingResult:
        params = {
            "address": address,
            "benchmark": "Public_AR_Current",
            "format": "json",
        }
        url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{urlencode(params)}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            matches = response.json().get("result", {}).get("addressMatches", [])
            if not matches:
                return self._failed(address, "US Census Geocoder", url, "No address match returned.")
            match = matches[0]
            coordinates = match.get("coordinates") or {}
            lat = coordinates.get("y")
            lon = coordinates.get("x")
            if lat is None or lon is None:
                return self._failed(address, "US Census Geocoder", url, "Address match did not include coordinates.")
            components = match.get("addressComponents") or {}
            return GeocodingResult(
                raw_address=address,
                standardized_address=match.get("matchedAddress") or address,
                latitude=float(lat),
                longitude=float(lon),
                state=components.get("state"),
                zip_code=components.get("zip"),
                source_name="US Census Geocoder",
                source_url=url,
                confidence=0.9,
                status=PowerAddressStatus.GEOCODED_ADDRESS,
            )
        except Exception as exc:
            return self._failed(address, "US Census Geocoder", url, str(exc))

    async def _nominatim_geocode(self, address: str) -> GeocodingResult:
        params = {"q": address, "format": "jsonv2", "limit": "1", "addressdetails": "1"}
        url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"
        headers = {"User-Agent": self.settings.nominatim_user_agent}
        if self.settings.nominatim_email:
            headers["From"] = self.settings.nominatim_email
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
            data = response.json()
            if not data:
                return self._failed(address, "OpenStreetMap Nominatim", url, "No address match returned.")
            match = data[0]
            address_data = match.get("address") or {}
            return GeocodingResult(
                raw_address=address,
                standardized_address=match.get("display_name") or address,
                latitude=float(match["lat"]),
                longitude=float(match["lon"]),
                county=address_data.get("county"),
                state=address_data.get("state"),
                zip_code=address_data.get("postcode"),
                source_name="OpenStreetMap Nominatim",
                source_url=url,
                confidence=0.75,
                status=PowerAddressStatus.GEOCODED_ADDRESS,
            )
        except Exception as exc:
            return self._failed(address, "OpenStreetMap Nominatim", url, str(exc))

    def _failed(self, address: str, source_name: str, source_url: str, message: str) -> GeocodingResult:
        return GeocodingResult(
            raw_address=address,
            standardized_address=address,
            source_name=source_name,
            source_url=source_url,
            confidence=0,
            status=PowerAddressStatus.GEOCODING_FAILED,
            error_message=message[:500],
        )
