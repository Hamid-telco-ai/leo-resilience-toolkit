from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation.visibility_engine import run_visibility_engine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Visualize satellite passes for a scenario")
    parser.add_argument(
        "--scenario",
        default="simulation/sample_scenarios/northern_quebec_starlink_like.yaml",
        help="Path to scenario YAML",
    )
    parser.add_argument(
        "--output",
        default="artifacts/visibility_passes.html",
        help="HTML output path",
    )
    args = parser.parse_args()

    scenario_path = ROOT / args.scenario
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    config = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    rows = run_visibility_engine(config)
    if not rows:
        print("No visible satellites found for this scenario.")
        return 0

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])

    fig = px.line(
        df,
        x="timestamp_utc",
        y="elevation_deg",
        color="satellite_name",
        title=f"Visible satellite passes — {config['region']['name']}",
        labels={"timestamp_utc": "UTC time", "elevation_deg": "Elevation (deg)"},
    )
    fig.update_layout(legend_title_text="Satellite", template="plotly_white")
    fig.write_html(output_path, include_plotlyjs="cdn")
    print(f"Saved pass visualization to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
