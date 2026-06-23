from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.site_hunter.models import SearchAnchorStatus, SearchAnchorType, SiteHunterStructuredCriteria, SiteSearchAnchor, utc_now


class SearchAnchorResolver:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._cache: dict[str, SiteSearchAnchor] = {}

    async def resolve(self, criteria: SiteHunterStructuredCriteria) -> SiteHunterStructuredCriteria:
        if not criteria.search_anchor:
            return criteria
        anchor = criteria.search_anchor.model_copy(deep=True)
        if not anchor.radius_miles:
            anchor.radius_miles = criteria.regions.radius_miles
        cache_key = self._cache_key(anchor)
        if cache_key in self._cache:
            criteria.search_anchor = self._cache[cache_key].model_copy(deep=True)
            self._merge_anchor_region(criteria)
            return criteria

        if anchor.latitude is not None and anchor.longitude is not None:
            latitude, longitude = self._normalize_us_coordinate_pair(anchor.latitude, anchor.longitude)
            anchor.latitude = latitude
            anchor.longitude = longitude
            anchor = await self._reverse_coordinates(anchor)
        elif anchor.input_type == SearchAnchorType.ZIP_CODE and anchor.zip_code:
            anchor = await self._resolve_zip(anchor)
        else:
            anchor.status = SearchAnchorStatus.FAILED
            anchor.error_message = "Search anchor did not include usable ZIP or coordinates."

        self._cache[cache_key] = anchor.model_copy(deep=True)
        criteria.search_anchor = anchor
        self._merge_anchor_region(criteria)
        return criteria

    def _normalize_us_coordinate_pair(self, first: float, second: float) -> tuple[float, float]:
        if 24 <= first <= 50 and -125 <= second <= -66:
            return first, second
        if 24 <= second <= 50 and -125 <= first <= -66:
            return second, first
        return first, second

    def _cache_key(self, anchor: SiteSearchAnchor) -> str:
        return "|".join(
            [
                anchor.input_type,
                anchor.raw_input or "",
                str(anchor.latitude or ""),
                str(anchor.longitude or ""),
                anchor.zip_code or "",
            ]
        ).lower()

    def _merge_anchor_region(self, criteria: SiteHunterStructuredCriteria) -> None:
        anchor = criteria.search_anchor
        if not anchor:
            return
        if anchor.state and anchor.state not in criteria.regions.states:
            criteria.regions.states.append(anchor.state)
        if anchor.county and anchor.county not in criteria.regions.counties:
            criteria.regions.counties.append(anchor.county)
        if anchor.city and anchor.city not in criteria.regions.cities:
            criteria.regions.cities.append(anchor.city)
        if anchor.zip_code and anchor.zip_code not in criteria.regions.zip_codes:
            criteria.regions.zip_codes.append(anchor.zip_code)
        if anchor.radius_miles and not criteria.regions.radius_miles:
            criteria.regions.radius_miles = anchor.radius_miles

    async def _resolve_zip(self, anchor: SiteSearchAnchor) -> SiteSearchAnchor:
        zippopotam_result = await self._zippopotam_zip(anchor)
        if zippopotam_result.status == SearchAnchorStatus.RESOLVED:
            return zippopotam_result
        nominatim_result = await self._nominatim_zip(anchor)
        if nominatim_result.status == SearchAnchorStatus.RESOLVED:
            return nominatim_result
        return zippopotam_result

    async def _zippopotam_zip(self, anchor: SiteSearchAnchor) -> SiteSearchAnchor:
        zip_code = (anchor.zip_code or "").split("-")[0]
        url = f"https://api.zippopotam.us/us/{zip_code}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            data = response.json()
            place = (data.get("places") or [{}])[0]
            lat = float(place["latitude"])
            lon = float(place["longitude"])
            resolved = anchor.model_copy(update={
                "label": f"{zip_code} {place.get('place name') or ''}, {place.get('state') or ''}".strip(),
                "latitude": lat,
                "longitude": lon,
                "city": place.get("place name"),
                "state": place.get("state"),
                "zip_code": zip_code,
                "source_name": "Zippopotam ZIP centroid",
                "source_url": url,
                "confidence": 0.75,
                "status": SearchAnchorStatus.RESOLVED,
                "resolved_at": utc_now(),
                "error_message": None,
            })
            return await self._reverse_coordinates(resolved)
        except Exception as exc:
            return anchor.model_copy(update={
                "source_name": "Zippopotam ZIP centroid",
                "source_url": url,
                "status": SearchAnchorStatus.FAILED,
                "error_message": str(exc)[:500],
            })

    async def _nominatim_zip(self, anchor: SiteSearchAnchor) -> SiteSearchAnchor:
        zip_code = (anchor.zip_code or "").split("-")[0]
        params = {"postalcode": zip_code, "country": "United States", "format": "jsonv2", "limit": "1", "addressdetails": "1"}
        url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"
        headers = {"User-Agent": self.settings.nominatim_user_agent}
        if self.settings.nominatim_email:
            headers["From"] = self.settings.nominatim_email
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
            matches = response.json()
            if not matches:
                raise ValueError("No ZIP match returned.")
            match = matches[0]
            address = match.get("address") or {}
            return anchor.model_copy(update={
                "label": match.get("display_name") or zip_code,
                "latitude": float(match["lat"]),
                "longitude": float(match["lon"]),
                "city": address.get("city") or address.get("town") or address.get("village"),
                "county": address.get("county"),
                "state": address.get("state"),
                "zip_code": zip_code,
                "source_name": "OpenStreetMap Nominatim ZIP",
                "source_url": url,
                "confidence": 0.7,
                "status": SearchAnchorStatus.RESOLVED,
                "resolved_at": utc_now(),
                "error_message": None,
            })
        except Exception as exc:
            return anchor.model_copy(update={
                "source_name": "OpenStreetMap Nominatim ZIP",
                "source_url": url,
                "status": SearchAnchorStatus.FAILED,
                "error_message": str(exc)[:500],
            })

    async def _reverse_coordinates(self, anchor: SiteSearchAnchor) -> SiteSearchAnchor:
        census_result = await self._census_reverse(anchor)
        if census_result.status == SearchAnchorStatus.RESOLVED:
            return census_result
        nominatim_result = await self._nominatim_reverse(anchor)
        if nominatim_result.status == SearchAnchorStatus.RESOLVED:
            return nominatim_result
        return census_result

    async def _census_reverse(self, anchor: SiteSearchAnchor) -> SiteSearchAnchor:
        params = {
            "x": anchor.longitude,
            "y": anchor.latitude,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        }
        url = f"https://geocoding.geo.census.gov/geocoder/geographies/coordinates?{urlencode(params)}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            geographies = response.json().get("result", {}).get("geographies", {})
            states = geographies.get("States") or []
            counties = geographies.get("Counties") or []
            places = geographies.get("Incorporated Places") or geographies.get("Census Designated Places") or []
            state = states[0].get("NAME") if states else anchor.state
            county = self._clean_county(counties[0].get("NAME")) if counties else anchor.county
            city = self._clean_place(places[0].get("NAME")) if places else anchor.city
            label_parts = [city, county, state]
            source_name = "US Census Geocoder reverse coordinates"
            if anchor.input_type == SearchAnchorType.ZIP_CODE and anchor.source_name:
                source_name = f"{anchor.source_name} + US Census reverse coordinates"
            return anchor.model_copy(update={
                "label": anchor.label or ", ".join(part for part in label_parts if part),
                "city": city,
                "county": county,
                "state": state,
                "source_name": source_name,
                "source_url": url,
                "confidence": max(anchor.confidence, 0.85),
                "status": SearchAnchorStatus.RESOLVED,
                "resolved_at": utc_now(),
                "error_message": None,
            })
        except Exception as exc:
            return anchor.model_copy(update={
                "source_name": "US Census Geocoder reverse coordinates",
                "source_url": url,
                "status": SearchAnchorStatus.FAILED,
                "error_message": str(exc)[:500],
            })

    def _clean_county(self, value: str | None) -> str | None:
        if not value:
            return None
        return value.removesuffix(" County").strip()

    def _clean_place(self, value: str | None) -> str | None:
        if not value:
            return None
        for suffix in [" city", " town", " village"]:
            if value.lower().endswith(suffix):
                return value[: -len(suffix)].strip()
        return value.strip()

    async def _nominatim_reverse(self, anchor: SiteSearchAnchor) -> SiteSearchAnchor:
        params = {"lat": anchor.latitude, "lon": anchor.longitude, "format": "jsonv2", "addressdetails": "1"}
        url = f"https://nominatim.openstreetmap.org/reverse?{urlencode(params)}"
        headers = {"User-Agent": self.settings.nominatim_user_agent}
        if self.settings.nominatim_email:
            headers["From"] = self.settings.nominatim_email
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
            data = response.json()
            address = data.get("address") or {}
            return anchor.model_copy(update={
                "label": anchor.label or data.get("display_name"),
                "city": address.get("city") or address.get("town") or address.get("village"),
                "county": address.get("county"),
                "state": address.get("state"),
                "zip_code": address.get("postcode") or anchor.zip_code,
                "source_name": "OpenStreetMap Nominatim reverse coordinates",
                "source_url": url,
                "confidence": max(anchor.confidence, 0.7),
                "status": SearchAnchorStatus.RESOLVED,
                "resolved_at": utc_now(),
                "error_message": None,
            })
        except Exception as exc:
            return anchor.model_copy(update={
                "source_name": "OpenStreetMap Nominatim reverse coordinates",
                "source_url": url,
                "status": SearchAnchorStatus.FAILED,
                "error_message": str(exc)[:500],
            })
