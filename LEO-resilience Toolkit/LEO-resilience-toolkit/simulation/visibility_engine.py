from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from skyfield.api import Topos, load


def run_visibility_engine(config: dict[str, Any]) -> list[dict[str, Any]]:
    region = config["region"]
    sim = config["simulation"]
    constellation = config["constellation"]

    ts = load.timescale()
    observer = Topos(
        latitude_degrees=region["latitude_deg"],
        longitude_degrees=region["longitude_deg"],
        elevation_m=region.get("altitude_m", 0),
    )

    #start_dt = datetime.fromisoformat(sim["start_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
    start_value = sim["start_utc"]

    if isinstance(start_value, str) and start_value.strip().lower() == "now":
        start_dt = datetime.now(timezone.utc)
    else:
        start_dt = datetime.fromisoformat(start_value.replace("Z", "+00:00")).astimezone(timezone.utc)
    duration_s = int(sim["duration_s"])
    step_s = int(sim["step_s"])

    tle_file = constellation.get("tle_file", "simulation/sample_scenarios/sample.tle")
    satellites = load.tle_file(str(Path(tle_file)))

    rows: list[dict[str, Any]] = []
    num_steps = duration_s // step_s

    for i in range(num_steps + 1):
        current_dt = start_dt + timedelta(seconds=i * step_s)
        t = ts.from_datetime(current_dt)

        for sat in satellites:
            difference = sat - observer
            topocentric = difference.at(t)
            alt, az, distance = topocentric.altaz()

            if alt.degrees > 0:
                rows.append(
                    {
                        "timestamp_utc": current_dt,
                        "satellite_name": sat.name,
                        "elevation_deg": round(alt.degrees, 3),
                        "azimuth_deg": round(az.degrees, 3),
                        "range_km": round(distance.km, 3),
                    }
                )

    return rows
