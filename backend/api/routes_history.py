"""Historical data and algorithm status endpoints.

A-10: Write endpoints (POST) require API key authentication.
C-12: Response format defined for sensor history.
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from backend.models.decision import AlgorithmOverride
from backend.services.auth import require_api_key

router = APIRouter(prefix="/api", tags=["history", "algorithm"])
_db = None
_engine = None
_alert_service = None

def init(db, engine, alert_service):
    global _db, _engine, _alert_service
    _db = db
    _engine = engine
    _alert_service = alert_service

@router.get("/algorithm/status")
def algorithm_status():
    last = _engine.get_last_decision() if _engine else None
    return {
        "running": _engine is not None,
        "last_cycle_ms": last.get("cycle_ms") if last else None,
        "layers_triggered": last.get("layers_triggered", []) if last else [],
    }

@router.get("/algorithm/last_decision")
def last_decision():
    return _engine.get_last_decision() if _engine else {"error": "Engine not running"}

@router.get("/algorithm/plant_scores")
def plant_scores():
    last = _engine.get_last_decision() if _engine else None
    return last.get("plant_scores", []) if last else []

@router.post("/algorithm/override")
def set_override(override: AlgorithmOverride, _key: str = Depends(require_api_key)):
    if _engine:
        _engine.set_override(override.action, override.duration_minutes)
        return {"success": True, "action": override.action, "minutes": override.duration_minutes}
    return {"success": False, "error": "Engine not running"}

@router.get("/alerts")
def get_alerts(resolved: bool = False):
    return _alert_service.get_active() if not resolved else _db.get_alerts(resolved=True)

@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, _key: str = Depends(require_api_key)):
    _alert_service.resolve(alert_id)
    return {"success": True}

# C-12: Defined response format for sensor history
SENSOR_UNITS = {
    "temp": "°C", "humidity": "%", "soil_moist": "%", "soil_temp": "°C",
    "ph": "pH", "light_lux": "lux", "co2_ppm": "ppm",
    "wind_kmh": "km/h", "rainfall_mm": "mm", "power_w": "W"
}

@router.get("/sensors/history")
def get_sensor_history(hours: int = Query(24, ge=1, le=8760),
                       sensor: Optional[str] = Query(None)):
    """C-12: Returns structured response with data array and stats."""
    data = _db.get_readings_history(hours=hours, sensor=sensor)
    if sensor:
        values = [d.get("value") for d in data if d.get("value") is not None]
        stats = {}
        if values:
            stats = {
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "avg": round(sum(values) / len(values), 2),
            }
        return {
            "sensor": sensor,
            "hours": hours,
            "count": len(data),
            "unit": SENSOR_UNITS.get(sensor, ""),
            "data": data,
            "stats": stats
        }
    return {
        "hours": hours,
        "count": len(data),
        "data": data
    }

@router.get("/system/health")
def system_health():
    return {
        "backend": "running",
        "database": "ok",
        "engine": "running" if _engine else "stopped",
    }

@router.get("/system/config")
def get_config():
    return {"message": "Config available via system.yaml"}
