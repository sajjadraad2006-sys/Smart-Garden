"""WebSocket message schema — canonical JSON structure for all WS messages.

A-09 FIX: Frontend and all consumers now have a defined contract for
WebSocket message format instead of making different assumptions.
"""
from pydantic import BaseModel
from typing import Optional, List


class SensorPayload(BaseModel):
    """Real-time sensor values from ESP32."""
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    soil_temp: Optional[float] = None
    ph: Optional[float] = None
    light_lux: Optional[float] = None
    co2_ppm: Optional[float] = None
    wind_kmh: Optional[float] = None
    rainfall_mm: Optional[float] = None
    power_w: Optional[float] = None


class ActuatorPayload(BaseModel):
    """Current actuator states."""
    pump_main: bool = False
    zone1: bool = False
    zone2: bool = False
    misting: bool = False
    fan_speed: int = 0       # 0-255 PWM
    light_pwm: int = 0       # 0-255 PWM
    fertilizer: bool = False
    ph_down: bool = False
    ph_up: bool = False


class PlantScoreWS(BaseModel):
    """Plant health score for WebSocket broadcast."""
    plant_id: str
    name: str
    zone: int = 1
    health_score: float = 100.0     # 0.0-100.0
    stress_score: float = 0.0       # 0.0-1.0
    status: str = "thriving"        # thriving/good/stressed/critical/dying
    recommendations: List[str] = []


class AlgorithmStatus(BaseModel):
    """Algorithm engine status for WebSocket broadcast."""
    last_cycle_at: int = 0          # unix ms
    active_actions: List[str] = []  # human-readable list
    last_reason: str = ""
    override_active: bool = False


class WSMessage(BaseModel):
    """Canonical WebSocket message format.

    type values:
    - "state_update": Full system state (sensors + actuators + scores)
    - "alert": New alert notification
    - "pong": Keepalive response
    - "decision": Algorithm decision cycle result
    - "sensor_update": Sensor-only update
    """
    type: str = "state_update"
    timestamp: int = 0
    sensors: Optional[SensorPayload] = None
    actuators: Optional[ActuatorPayload] = None
    plant_scores: Optional[List[PlantScoreWS]] = None
    algorithm: Optional[AlgorithmStatus] = None
    alerts_count: int = 0
    # For alert-type messages
    alerts: Optional[list] = None
    # For decision-type messages
    actions: Optional[list] = None
    layers_triggered: Optional[List[str]] = None
