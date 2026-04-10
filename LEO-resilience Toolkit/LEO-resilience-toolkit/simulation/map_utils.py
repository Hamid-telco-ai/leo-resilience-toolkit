from __future__ import annotations

from math import cos, radians, sin, pi


def circle_polygon(lat: float, lon: float, radius_km: float, num_points: int = 36):
    """Approximate a circle on Earth as a polygon in lat/lon."""

    points = []
    earth_radius_km = 6371.0

    for i in range(num_points + 1):
        angle = 2 * pi * i / num_points

        dlat = (radius_km / earth_radius_km) * (180 / pi) * sin(angle)

        dlon = (
            (radius_km / earth_radius_km)
            * (180 / pi)
            * cos(angle)
            / max(cos(radians(lat)), 1e-6)
        )

        points.append([lon + dlon, lat + dlat])

    return points

from math import cos, radians, sin, pi


def hex_polygon(lat: float, lon: float, radius_km: float):
    """
    Approximate a hexagon footprint on Earth in lat/lon.
    radius_km = distance from center to each vertex.
    """
    points = []
    earth_radius_km = 6371.0

    for i in range(6):
        angle = 2 * pi * i / 6
        dlat = (radius_km / earth_radius_km) * (180 / pi) * sin(angle)
        dlon = (
            (radius_km / earth_radius_km)
            * (180 / pi)
            * cos(angle)
            / max(cos(radians(lat)), 1e-6)
        )
        points.append([lon + dlon, lat + dlat])

    # close polygon
    points.append(points[0])
    return points