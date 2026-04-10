from pathlib import Path
import yaml

from simulation.visibility_engine import run_visibility_engine


def test_visibility_engine_runs() -> None:
    config_path = Path("simulation/sample_scenarios/northern_quebec_starlink_like.yaml")
    config = yaml.safe_load(config_path.read_text())
    rows = run_visibility_engine(config)
    assert isinstance(rows, list)
