from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.site_hunter.models import NearbyPowerAsset, PowerAssetType, TrustLevel, utc_now
from app.site_hunter.power_geometry import geometry_center, point_to_polyline_miles


class TransmissionLineDataImporter:
    def import_geojson(self, path: str | None) -> list[NearbyPowerAsset]:
        if not path:
            return []
        file_path = Path(path)
        if not file_path.exists():
            return []
        data = json.loads(file_path.read_text())
        features = data.get("features", [])
        lines: list[NearbyPowerAsset] = []
        for feature in features:
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            line_coords = self._extract_lines(geometry)
            for coords in line_coords:
                center_lat, center_lon = geometry_center(coords)
                lines.append(
                    NearbyPowerAsset(
                        id=uuid4(),
                        asset_type=PowerAssetType.TRANSMISSION_LINE,
                        asset_name=props.get("name") or props.get("LINE_NAME"),
                        latitude=center_lat,
                        longitude=center_lon,
                        geometry={"type": "LineString", "coordinates": [[lon, lat] for lat, lon in coords]},
                        voltage_kv=self._number(props.get("voltage_kv") or props.get("VOLTAGE") or props.get("KV")),
                        owner=props.get("owner") or props.get("OWNER"),
                        status=props.get("status") or props.get("STATUS"),
                        source_name=props.get("source_name") or "Local GeoJSON transmission dataset",
                        source_url=props.get("source_url"),
                        confidence_level=TrustLevel.SOURCE_CONFIRMED,
                        verification_status=TrustLevel.SOURCE_CONFIRMED,
                        dataset_version=props.get("dataset_version") or file_path.name,
                        checked_at=utc_now(),
                        raw_data_json=props,
                    )
                )
        return lines

    def _extract_lines(self, geometry: dict[str, Any]) -> list[list[tuple[float, float]]]:
        if geometry.get("type") == "LineString":
            return [[(float(lat), float(lon)) for lon, lat, *_ in geometry.get("coordinates", [])]]
        if geometry.get("type") == "MultiLineString":
            return [[(float(lat), float(lon)) for lon, lat, *_ in line] for line in geometry.get("coordinates", [])]
        return []

    def _number(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class TransmissionLineRepository:
    def __init__(self) -> None:
        settings = get_settings()
        self.lines = TransmissionLineDataImporter().import_geojson(settings.transmission_line_geojson_path)

    def all(self) -> list[NearbyPowerAsset]:
        return self.lines


class NearbyTransmissionLineService:
    arcgis_layer_url = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/US_Electric_Power_Transmission_Lines/FeatureServer/0/query"
    arcgis_source_url = "https://www.arcgis.com/home/item.html?id=260b4513acdb4a3a8e4d64e69fc84fee"

    def __init__(self) -> None:
        self.repository = TransmissionLineRepository()

    async def find_nearby(self, latitude: float, longitude: float, max_radius_miles: float = 10) -> list[NearbyPowerAsset]:
        matches: list[NearbyPowerAsset] = []
        for line in self.repository.all():
            geometry = line.geometry or {}
            coords = [(float(lat), float(lon)) for lon, lat in geometry.get("coordinates", [])]
            distance = point_to_polyline_miles(latitude, longitude, coords)
            if distance is None or distance > max_radius_miles:
                continue
            copied = line.model_copy(deep=True)
            copied.distance_miles = round(distance, 3)
            matches.append(copied)
        matches.extend(await self._query_arcgis(latitude, longitude, max_radius_miles))
        return sorted(matches, key=lambda item: item.distance_miles if item.distance_miles is not None else 999)

    async def _query_arcgis(self, latitude: float, longitude: float, radius_miles: float) -> list[NearbyPowerAsset]:
        delta_lat = radius_miles / 69.0
        delta_lon = radius_miles / max(1.0, math.cos(math.radians(latitude)) * 69.172)
        geometry = {
            "xmin": longitude - delta_lon,
            "ymin": latitude - delta_lat,
            "xmax": longitude + delta_lon,
            "ymax": latitude + delta_lat,
            "spatialReference": {"wkid": 4326},
        }
        params = {
            "f": "geojson",
            "where": "1=1",
            "outFields": "ID,TYPE,STATUS,SOURCE,SOURCEDATE,OWNER,VOLTAGE,VOLT_CLASS,INFERRED",
            "geometry": json.dumps(geometry),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "returnGeometry": "true",
            "resultRecordCount": "200",
        }
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                response = await client.get(self.arcgis_layer_url, params=params)
                response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        assets: list[NearbyPowerAsset] = []
        for feature in data.get("features", []):
            props = feature.get("properties") or {}
            for coords in self._geojson_lines(feature.get("geometry") or {}):
                distance = point_to_polyline_miles(latitude, longitude, coords)
                if distance is None or distance > radius_miles:
                    continue
                center_lat, center_lon = geometry_center(coords)
                assets.append(
                    NearbyPowerAsset(
                        asset_type=PowerAssetType.TRANSMISSION_LINE,
                        asset_name=props.get("ID"),
                        latitude=center_lat,
                        longitude=center_lon,
                        geometry={"type": "LineString", "coordinates": [[lon, lat] for lat, lon in coords]},
                        distance_miles=round(distance, 3),
                        voltage_kv=self._number(props.get("VOLTAGE")),
                        owner=props.get("OWNER"),
                        status=props.get("STATUS"),
                        source_name="HIFLD U.S. Electric Power Transmission Lines (ArcGIS)",
                        source_url=self.arcgis_source_url,
                        confidence_level=TrustLevel.SOURCE_CONFIRMED,
                        verification_status=TrustLevel.SOURCE_CONFIRMED,
                        dataset_version=str(props.get("SOURCEDATE") or "ArcGIS FeatureServer live query"),
                        checked_at=utc_now(),
                        raw_data_json=props,
                    )
                )
        return assets

    def _geojson_lines(self, geometry: dict[str, Any]) -> list[list[tuple[float, float]]]:
        if geometry.get("type") == "LineString":
            return [[(float(lat), float(lon)) for lon, lat, *_ in geometry.get("coordinates", [])]]
        if geometry.get("type") == "MultiLineString":
            return [[(float(lat), float(lon)) for lon, lat, *_ in line] for line in geometry.get("coordinates", [])]
        return []

    def _number(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
