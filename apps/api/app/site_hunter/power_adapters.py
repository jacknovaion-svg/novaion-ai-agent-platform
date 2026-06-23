from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.site_hunter.models import NearbyPowerAsset, PowerAssetType, TrustLevel
from app.site_hunter.power_geometry import geometry_center, haversine_miles, point_to_polyline_miles

MILES_TO_METERS = 1609.344


class OpenStreetMapPowerAdapter:
    source_name = "OpenStreetMap Overpass"
    source_url = "https://www.openstreetmap.org"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search_nearby(self, latitude: float, longitude: float, radii_miles: list[float]) -> list[NearbyPowerAsset]:
        last_assets: list[NearbyPowerAsset] = []
        for radius in radii_miles:
            assets = await self._query_radius(latitude, longitude, radius)
            if assets:
                return assets
            last_assets = assets
        return last_assets

    async def _query_radius(self, latitude: float, longitude: float, radius_miles: float) -> list[NearbyPowerAsset]:
        radius_meters = int(radius_miles * MILES_TO_METERS)
        query = f"""
        [out:json][timeout:25];
        (
          node(around:{radius_meters},{latitude},{longitude})["power"~"substation|tower|plant|pole"];
          way(around:{radius_meters},{latitude},{longitude})["power"~"line|minor_line|substation|plant"];
          relation(around:{radius_meters},{latitude},{longitude})["power"~"line|minor_line|substation|plant"];
        );
        out tags center geom;
        """
        headers = {"User-Agent": self.settings.nominatim_user_agent}
        async with httpx.AsyncClient(timeout=35, follow_redirects=True, headers=headers) as client:
            response = await client.post(self.settings.overpass_api_url, data={"data": query})
            response.raise_for_status()
        elements = response.json().get("elements", [])
        assets: list[NearbyPowerAsset] = []
        for element in elements:
            asset = self._element_to_asset(element, latitude, longitude)
            if asset and asset.distance_miles is not None and asset.distance_miles <= radius_miles:
                assets.append(asset)
        return sorted(assets, key=lambda item: item.distance_miles if item.distance_miles is not None else 999)

    def _element_to_asset(self, element: dict[str, Any], latitude: float, longitude: float) -> NearbyPowerAsset | None:
        tags = element.get("tags") or {}
        power = tags.get("power")
        if power in {"line", "minor_line"}:
            asset_type = PowerAssetType.TRANSMISSION_LINE
        elif power in {"tower", "pole"}:
            asset_type = PowerAssetType.TOWER
        elif power == "plant":
            asset_type = PowerAssetType.PLANT
        elif power == "substation":
            asset_type = PowerAssetType.SUBSTATION
        else:
            return None

        geometry = element.get("geometry") or []
        coords = [(float(point["lat"]), float(point["lon"])) for point in geometry if "lat" in point and "lon" in point]
        asset_lat: float | None = None
        asset_lon: float | None = None
        distance: float | None = None
        if coords:
            asset_lat, asset_lon = geometry_center(coords)
            if asset_type == PowerAssetType.TRANSMISSION_LINE:
                distance = point_to_polyline_miles(latitude, longitude, coords)
            elif asset_lat is not None and asset_lon is not None:
                distance = haversine_miles(latitude, longitude, asset_lat, asset_lon)
        elif "lat" in element and "lon" in element:
            asset_lat = float(element["lat"])
            asset_lon = float(element["lon"])
            distance = haversine_miles(latitude, longitude, asset_lat, asset_lon)
        elif "center" in element:
            asset_lat = float(element["center"]["lat"])
            asset_lon = float(element["center"]["lon"])
            distance = haversine_miles(latitude, longitude, asset_lat, asset_lon)

        return NearbyPowerAsset(
            asset_type=asset_type,
            asset_name=tags.get("name"),
            latitude=asset_lat,
            longitude=asset_lon,
            geometry={"type": "LineString", "coordinates": [[lon, lat] for lat, lon in coords]} if coords else None,
            distance_miles=round(distance, 3) if distance is not None else None,
            voltage_kv=self._voltage(tags.get("voltage")),
            owner=tags.get("owner"),
            operator=tags.get("operator"),
            status=tags.get("status"),
            source_name=self.source_name,
            source_url=f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}",
            confidence_level=TrustLevel.ESTIMATED,
            verification_status=TrustLevel.ESTIMATED,
            dataset_version=f"Overpass live {datetime.utcnow().date().isoformat()}",
            source_timestamp=datetime.utcnow(),
            raw_data_json={"osm_id": element.get("id"), "osm_type": element.get("type"), "tags": tags},
        )

    def _voltage(self, value: str | None) -> float | None:
        if not value:
            return None
        first = str(value).replace(";", ",").split(",")[0].strip()
        try:
            number = float(first)
        except ValueError:
            return None
        return round(number / 1000, 3) if number > 1000 else number
