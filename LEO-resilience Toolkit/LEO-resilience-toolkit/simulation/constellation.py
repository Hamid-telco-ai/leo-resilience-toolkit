from pathlib import Path

from skyfield.api import load


def load_tle_objects(tle_file: str):
    tle_path = Path(tle_file)
    if not tle_path.exists():
        raise FileNotFoundError(f"TLE file not found: {tle_file}")
    return load.tle_file(str(tle_path))
