from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Scenario
from app.schemas import ScenarioCreate, ScenarioRead

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("", response_model=ScenarioRead)
def create_scenario(payload: ScenarioCreate, db: Session = Depends(get_db)):
    existing = db.query(Scenario).filter(Scenario.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Scenario name already exists")

    scenario = Scenario(name=payload.name, scenario_yaml=payload.scenario_yaml)
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("", response_model=list[ScenarioRead])
def list_scenarios(db: Session = Depends(get_db)):
    return db.query(Scenario).order_by(Scenario.created_at.desc()).all()


@router.get("/{scenario_id}", response_model=ScenarioRead)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario
