from __future__ import annotations

import math

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return EARTH_RADIUS_MILES * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def point_to_polyline_miles(lat: float, lon: float, coordinates: list[tuple[float, float]]) -> float | None:
    if not coordinates:
        return None
    if len(coordinates) == 1:
        node_lat, node_lon = coordinates[0]
        return haversine_miles(lat, lon, node_lat, node_lon)

    lat0 = math.radians(lat)
    miles_per_degree_lat = 69.0
    miles_per_degree_lon = math.cos(lat0) * 69.172

    px = lon * miles_per_degree_lon
    py = lat * miles_per_degree_lat
    best: float | None = None
    for (lat1, lon1), (lat2, lon2) in zip(coordinates, coordinates[1:]):
        x1 = lon1 * miles_per_degree_lon
        y1 = lat1 * miles_per_degree_lat
        x2 = lon2 * miles_per_degree_lon
        y2 = lat2 * miles_per_degree_lat
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            distance = math.hypot(px - x1, py - y1)
        else:
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
            nearest_x = x1 + t * dx
            nearest_y = y1 + t * dy
            distance = math.hypot(px - nearest_x, py - nearest_y)
        best = distance if best is None else min(best, distance)
    return best


def geometry_center(coordinates: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    if not coordinates:
        return None, None
    return sum(lat for lat, _ in coordinates) / len(coordinates), sum(lon for _, lon in coordinates) / len(coordinates)
