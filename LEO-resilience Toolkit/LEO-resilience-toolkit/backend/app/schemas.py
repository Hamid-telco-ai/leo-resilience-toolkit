from datetime import datetime

from pydantic import BaseModel


class ScenarioCreate(BaseModel):
    name: str
    scenario_yaml: str


class ScenarioRead(BaseModel):
    id: int
    name: str
    scenario_yaml: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VisibilityResult(BaseModel):
    timestamp_utc: datetime
    satellite_name: str
    elevation_deg: float
    azimuth_deg: float
    range_km: float
