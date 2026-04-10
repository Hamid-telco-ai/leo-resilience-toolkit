from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import yaml

from app.db import get_db
from app.models import Scenario
from app.schemas import VisibilityResult
from app.services.visibility_service import run_visibility_simulation

router = APIRouter(prefix="/simulate", tags=["simulation"])


@router.post("/visibility/{scenario_id}", response_model=list[VisibilityResult])
def simulate_visibility(scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    config = yaml.safe_load(scenario.scenario_yaml)
    return run_visibility_simulation(config, db=db, scenario_id=scenario_id)
