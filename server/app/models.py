from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DisasterType(str, Enum):
    fire = "fire"
    flood = "flood"
    earthquake = "earthquake"
    hurricane = "hurricane"
    tornado = "tornado"
    other = "other"


class LocationPrecision(str, Enum):
    address = "address"
    neighborhood = "neighborhood"
    city = "city"
    county = "county"
    state = "state"
    country = "country"


class SourcePost(BaseModel):
    platform: str
    url: str
    caption: str
    posted_at: datetime


class SpreadPoint(BaseModel):
    """Estimated extent of the disaster at a point in time."""

    timestamp: datetime
    radius_km: float


class Disaster(BaseModel):
    id: str
    type: DisasterType
    title: str
    location: str
    precision: LocationPrecision
    lat: float
    lng: float
    severity: int  # 1 (low) - 5 (extreme)
    spread: list[SpreadPoint]
    sources: list[SourcePost]
