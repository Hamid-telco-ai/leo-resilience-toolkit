from sqlalchemy.orm import Session

from app.models import SimulationRun, VisibilitySample
from simulation.visibility_engine import run_visibility_engine


def run_visibility_simulation(config: dict, db: Session, scenario_id: int):
    rows = run_visibility_engine(config)

    run = SimulationRun(scenario_id=scenario_id, run_type="visibility", status="completed")
    db.add(run)
    db.commit()
    db.refresh(run)

    for row in rows:
        sample = VisibilitySample(run_id=run.id, **row)
        db.add(sample)

    db.commit()
    return rows
