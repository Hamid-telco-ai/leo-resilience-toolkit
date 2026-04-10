from __future__ import annotations
from math import atan2, cos, pi, radians, sin, sqrt, log10
from typing import Any

def free_space_path_loss_db(range_km: float, frequency_hz: float) -> float:
    """
    Compute free-space path loss (FSPL) in dB.
    """
    frequency_ghz = frequency_hz / 1e9
    return 92.45 + 20.0 * log10(max(frequency_ghz, 1e-12)) + 20.0 * log10(max(range_km, 1e-12))


def noise_power_dbw(bandwidth_hz: float, noise_figure_db: float) -> float:
    """
    Thermal noise power in dBW.
    """
    return -228.6 + 10.0 * log10(max(bandwidth_hz, 1e-12)) + noise_figure_db

def beam_gain_relative_db(off_axis_ratio: float) -> float:
    """
    sinc² antenna pattern approximation.
    off_axis_ratio = distance_from_beam_center / beam_radius
    """

    off_axis_ratio = max(0.0, off_axis_ratio)

    # Beam edge cutoff
    if off_axis_ratio >= 1.0:
        return -25.0

    # Convert ratio to angular argument
    x = 3.14159 * off_axis_ratio

    # sinc function
    if abs(x) < 1e-6:
        gain_linear = 1.0
    else:
        gain_linear = (sin(x) / x) ** 2

    # Convert to dB
    gain_db = 10.0 * log10(max(gain_linear, 1e-6))

    return gain_db

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def km_to_latlon_offset(lat_deg: float, dx_km: float, dy_km: float) -> tuple[float, float]:
    earth_radius_km = 6371.0
    dlat = (dy_km / earth_radius_km) * (180.0 / pi)
    dlon = (dx_km / earth_radius_km) * (180.0 / pi) / max(cos(radians(lat_deg)), 1e-6)
    return dlat, dlon


def interpolate_latlon(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    fraction: float,
) -> tuple[float, float]:
    """
    Linear lat/lon interpolation for a short regional distance.
    fraction=0 -> point1, fraction=1 -> point2
    """
    return (
        lat1 + fraction * (lat2 - lat1),
        lon1 + fraction * (lon2 - lon1),
    )


def project_service_region_center(
    sat_lat: float,
    sat_lon: float,
    terminal_lat: float,
    terminal_lon: float,
    sat_elevation_deg: float,
) -> tuple[float, float]:
    """
    Create a beam steering reference point between the satellite subpoint and the terminal.
    Lower elevation -> service region pulled closer to the terminal.
    Higher elevation -> service region can stay closer to the subpoint.
    """
    elev = max(0.0, min(90.0, sat_elevation_deg))

    # At low elevation, steer more toward the terminal
    # At high elevation, the center can remain closer to subpoint
    # fraction_terminal_pull ranges roughly from 0.75 down to 0.25
    fraction_terminal_pull = 0.75 - 0.50 * (elev / 90.0)

    service_lat, service_lon = interpolate_latlon(
        sat_lat,
        sat_lon,
        terminal_lat,
        terminal_lon,
        fraction_terminal_pull,
    )
    return service_lat, service_lon

def generate_beam_codebook(
    sat_lat: float,
    sat_lon: float,
    terminal_lat: float,
    terminal_lon: float,
    sat_elevation_deg: float,
    beam_family: str = "steered_multiring",
) -> list[dict[str, Any]]:
    beams: list[dict[str, Any]] = []

    service_center_lat, service_center_lon = project_service_region_center(
        sat_lat=sat_lat,
        sat_lon=sat_lon,
        terminal_lat=terminal_lat,
        terminal_lon=terminal_lon,
        sat_elevation_deg=sat_elevation_deg,
    )

    elev = max(0.0, min(90.0, sat_elevation_deg))

    # Base beam size varies a bit with elevation
    # lower elevation -> broader service region
    base_radius_km = max(120.0, min(260.0, 240.0 - 0.8 * elev))

    # Tier-dependent radii
    r_s0 = 0.75 * base_radius_km
    r_s1 = 1.00 * base_radius_km
    r_s2 = 1.30 * base_radius_km
    r_f0 = 1.50 * base_radius_km

    # Elevation-dependent scaling:
    elev_rad = radians(max(5.0, sat_elevation_deg))
    elevation_scale = 1.0 / sin(elev_rad)

    elevation_scale = min(elevation_scale, 2.5)

    r_s0 *= elevation_scale
    r_s1 *= elevation_scale
    r_s2 *= elevation_scale
    r_f0 *= elevation_scale

    # Main steered center beam
    beams.append(
        {
            "beam_id": "S0",
            "beam_group": "steered",
            "beam_tier": "center",
            "beam_lat": service_center_lat,
            "beam_lon": service_center_lon,
            "beam_radius_km": r_s0,
            "beam_priority": 1.00,
        }
    )

    # Inner ring around steered center
    inner_ring_offset_km = 0.85 * r_s1
    for i in range(6):
        angle = 2 * pi * i / 6
        dx = inner_ring_offset_km * cos(angle)
        dy = inner_ring_offset_km * sin(angle)
        dlat, dlon = km_to_latlon_offset(service_center_lat, dx, dy)

        beams.append(
            {
                "beam_id": f"S1_{i}",
                "beam_group": "steered",
                "beam_tier": "inner",
                "beam_lat": service_center_lat + dlat,
                "beam_lon": service_center_lon + dlon,
                "beam_radius_km": r_s1,
                "beam_priority": 0.90,
            }
        )

    # Outer ring around steered center
    outer_ring_offset_km = 1.55 * r_s2
    for i in range(12):
        angle = 2 * pi * i / 12
        dx = outer_ring_offset_km * cos(angle)
        dy = outer_ring_offset_km * sin(angle)
        dlat, dlon = km_to_latlon_offset(service_center_lat, dx, dy)

        beams.append(
            {
                "beam_id": f"S2_{i}",
                "beam_group": "steered",
                "beam_tier": "outer",
                "beam_lat": service_center_lat + dlat,
                "beam_lon": service_center_lon + dlon,
                "beam_radius_km": r_s2,
                "beam_priority": 0.78,
            }
        )

    # Fallback beam near raw subpoint
    beams.append(
        {
            "beam_id": "F0",
            "beam_group": "fallback",
            "beam_tier": "subpoint",
            "beam_lat": sat_lat,
            "beam_lon": sat_lon,
            "beam_radius_km": r_f0,
            "beam_priority": 0.55,
        }
    )

    return beams

def evaluate_terminal_against_beams(
    terminal_lat: float,
    terminal_lon: float,
    sat_name: str,
    sat_elevation_deg: float,
    sat_range_km: float,
    beams: list[dict[str, Any]],
    rf_params: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    - Computes RF-aware quantities:
      beam gain, path loss, received power, noise power, SINR
    """
    if rf_params is None:
        rf_params = {
            "carrier_frequency_hz": 12e9,
            "channel_bandwidth_hz": 100e6,
            "sat_eirp_dbw": 40.0,
            "terminal_gain_dbi": 35.0,
            "noise_figure_db": 3.0,
            "sinr_service_threshold_db": 3.0,
            "interference_margin_db": 15.0,
        }

    frequency_hz = float(rf_params["carrier_frequency_hz"])
    bandwidth_hz = float(rf_params["channel_bandwidth_hz"])
    sat_eirp_dbw = float(rf_params["sat_eirp_dbw"])
    terminal_gain_dbi = float(rf_params["terminal_gain_dbi"])
    noise_figure_db = float(rf_params["noise_figure_db"])
    interference_margin_db = float(rf_params["interference_margin_db"])

    results: list[dict[str, Any]] = []

    for beam in beams:
        distance_to_center_km = haversine_km(
            terminal_lat,
            terminal_lon,
            beam["beam_lat"],
            beam["beam_lon"],
        )

        beam_radius_km = max(float(beam["beam_radius_km"]), 1e-6)
        inside_beam = distance_to_center_km <= beam_radius_km

        off_axis_ratio = distance_to_center_km / beam_radius_km

        # Existing Week-2 geometric gain-like score
        gain_like = max(0.0, 1.0 - off_axis_ratio**2)

        elevation_score = max(0.0, min(1.0, sat_elevation_deg / 90.0))
        range_score = max(0.0, min(1.0, 1.0 - sat_range_km / 3000.0))
        priority_score = float(beam["beam_priority"])

        beam_score = 0.0
        if inside_beam:
            beam_score = (
                0.50 * gain_like
                + 0.20 * elevation_score
                + 0.15 * range_score
                + 0.15 * priority_score
            )

        # New Week-4 RF-aware quantities
        beam_gain_rel_db = beam_gain_relative_db(off_axis_ratio)
        fspl_db = free_space_path_loss_db(sat_range_km, frequency_hz)
        noise_dbw = noise_power_dbw(bandwidth_hz, noise_figure_db)

        # Simple received power model
        rx_power_dbw = sat_eirp_dbw + terminal_gain_dbi + beam_gain_rel_db - fspl_db

        # Simple SINR proxy
        sinr_db = rx_power_dbw - (noise_dbw + interference_margin_db)

        results.append(
            {
                "satellite_name": sat_name,
                "beam_id": beam["beam_id"],
                "beam_group": beam["beam_group"],
                "beam_tier": beam["beam_tier"],
                "beam_lat": beam["beam_lat"],
                "beam_lon": beam["beam_lon"],
                "beam_radius_km": beam_radius_km,
                "beam_priority": beam["beam_priority"],
                "distance_to_beam_center_km": round(distance_to_center_km, 3),
                "off_axis_ratio": round(off_axis_ratio, 6),
                "gain_like": round(gain_like, 6),
                "inside_beam": inside_beam,
                "beam_score": round(beam_score, 6),
                "sat_elevation_deg": sat_elevation_deg,
                "sat_range_km": sat_range_km,
                "beam_gain_rel_db": round(beam_gain_rel_db, 3),
                "fspl_db": round(fspl_db, 3),
                "rx_power_dbw": round(rx_power_dbw, 3),
                "noise_power_dbw": round(noise_dbw, 3),
                "sinr_db": round(sinr_db, 3),
            }
        )

    return results