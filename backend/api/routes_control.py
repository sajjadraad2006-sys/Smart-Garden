"""REST endpoints for actuator control.

A-10: Write endpoints (POST) now require API key authentication.
"""
from fastapi import APIRouter, Depends
from backend.models.sensor_data import RelayCommand, PwmCommand
from backend.services.auth import require_api_key

router = APIRouter(prefix="/api/control", tags=["control"])
_db = None
_mqtt = None

def init(db, mqtt_service):
    global _db, _mqtt
    _db = db
    _mqtt = mqtt_service

@router.post("/relay")
def set_relay(cmd: RelayCommand, _key: str = Depends(require_api_key)):
    success = _mqtt.publish_command(
        target=cmd.target, action="SET_RELAY",
        value=cmd.value, duration=cmd.duration or 0
    )
    _db.log_action("SET_RELAY", cmd.target, str(cmd.value),
                   f"Manual control, duration={cmd.duration}s", "manual")
    return {"success": success, "target": cmd.target, "value": cmd.value}

@router.post("/pwm")
def set_pwm(cmd: PwmCommand, _key: str = Depends(require_api_key)):
    success = _mqtt.publish_command(
        target=cmd.target, action="SET_PWM", value=cmd.value
    )
    _db.log_action("SET_PWM", cmd.target, str(cmd.value), "Manual PWM control", "manual")
    return {"success": success, "target": cmd.target, "value": cmd.value}

@router.get("/state")
def get_state():
    state = _mqtt.get_latest_state()
    return state.get("actuators", {}) if state else {}

@router.get("/log")
def get_log(limit: int = 100):
    return _db.get_action_log(limit=limit)
