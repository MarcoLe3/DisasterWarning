from fastapi import APIRouter, HTTPException

from app.models import Disaster
from app.services.apify import fetch_disasters

router = APIRouter(prefix="/api/disasters", tags=["disasters"])


@router.get("", response_model=list[Disaster])
async def list_disasters():
    return await fetch_disasters()


@router.get("/{disaster_id}", response_model=Disaster)
async def get_disaster(disaster_id: str):
    for disaster in await fetch_disasters():
        if disaster.id == disaster_id:
            return disaster
    raise HTTPException(status_code=404, detail="Disaster not found")
