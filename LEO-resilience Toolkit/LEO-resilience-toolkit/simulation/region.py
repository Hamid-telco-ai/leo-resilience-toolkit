from dataclasses import dataclass


@dataclass
class Region:
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0
