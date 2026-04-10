from __future__ import annotations

import argparse
from pathlib import Path
import sys

import requests

DEFAULT_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle"
FALLBACK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
DEFAULT_OUTPUT = Path("simulation/sample_scenarios/starlink_live.tle")


def fetch_tle(url: str, timeout: int = 20) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    text = response.text.strip()
    if not text or "No GP data found" in text:
        raise ValueError(f"No usable TLE data returned from {url}")
    return text + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download public TLEs for LEO Resilience Studio")
    parser.add_argument("--url", default=DEFAULT_URL, help="TLE source URL")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output path for downloaded TLE file")
    parser.add_argument("--fallback", action="store_true", help="Use stations fallback URL if primary fails")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    urls_to_try = [args.url]
    if args.fallback and args.url != FALLBACK_URL:
        urls_to_try.append(FALLBACK_URL)

    for url in urls_to_try:
        try:
            tle_text = fetch_tle(url)
            output_path.write_text(tle_text, encoding="utf-8")
            print(f"Saved TLEs to {output_path}")
            print(f"Source: {url}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to download from {url}: {exc}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
