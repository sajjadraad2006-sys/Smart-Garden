"""Plant management endpoints.

A-10: Write endpoints (POST, DELETE) require API key authentication.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from backend.services.auth import require_api_key

router = APIRouter(prefix="/api/plants", tags=["plants"])
_db = None
_profiles = None
_engine = None

def init(db, profiles, engine):
    global _db, _profiles, _engine
    _db = db
    _profiles = profiles
    _engine = engine

class AddPlantRequest(BaseModel):
    plant_id: str
    zone: int = 1

@router.get("/library")
def get_library():
    return _profiles.get_all()

@router.get("/active")
def get_active():
    plants = _db.get_active_plants()
    result = []
    for p in plants:
        profile = _profiles.get(p["plant_id"])
        if profile:
            result.append({**p, "profile": profile})
    return result

@router.post("/add")
def add_plant(req: AddPlantRequest, _key: str = Depends(require_api_key)):
    profile = _profiles.get(req.plant_id)
    if not profile:
        return {"error": f"Unknown plant: {req.plant_id}"}
    plant_db_id = _db.add_plant(req.plant_id, req.zone)
    return {"success": True, "id": plant_db_id, "plant": profile["name"]}

@router.delete("/{plant_db_id}")
def remove_plant(plant_db_id: int, _key: str = Depends(require_api_key)):
    _db.remove_plant(plant_db_id)
    return {"success": True}

@router.get("/{plant_id}/health")
def plant_health(plant_id: str):
    last = _engine.get_last_decision() if _engine else None
    if last:
        for s in last.get("plant_scores", []):
            if s["plant_id"] == plant_id:
                return s
    return {"error": "No health data available"}
