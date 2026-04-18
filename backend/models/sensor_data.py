"""Pydantic models for sensor data and MQTT payloads."""
from pydantic import BaseModel, Field
from typing import Optional
import time


class SensorState(BaseModel):
    """Current state of all sensors from ESP32."""
    temperature: float = 0.0
    humidity: float = 0.0
    soil_moisture: float = 0.0
    soil_temp: float = 0.0
    ph: float = 7.0
    light_lux: float = 0.0
    co2_ppm: float = 400.0
    wind_kmh: float = 0.0
    rainfall_mm: float = 0.0
    power_w: float = 0.0


class ActuatorState(BaseModel):
    """Current state of all actuators."""
    pump_main: bool = False
    zone1: bool = False
    zone2: bool = False
    misting: bool = False
    fan_speed: int = 0
    light_pwm: int = 0
    fertilizer: bool = False
    ph_down: bool = False
    ph_up: bool = False


class MqttSensorPayload(BaseModel):
    """Full MQTT message from ESP32."""
    device_id: str
    timestamp: int
    sensors: SensorState
    actuators: ActuatorState


class SensorReading(BaseModel):
    """Single sensor reading for DB storage."""
    id: Optional[int] = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    device_id: str = "agrimaster_01"
    temp: Optional[float] = None
    humidity: Optional[float] = None
    soil_moist: Optional[float] = None
    soil_temp: Optional[float] = None
    ph: Optional[float] = None
    light_lux: Optional[float] = None
    co2_ppm: Optional[float] = None
    wind_kmh: Optional[float] = None
    rainfall_mm: Optional[float] = None
    power_w: Optional[float] = None


class RelayCommand(BaseModel):
    """Command to control a relay."""
    target: str
    value: bool
    duration: Optional[int] = None  # seconds, 0 = permanent


class PwmCommand(BaseModel):
    """Command to set PWM value."""
    target: str
    value: int = Field(ge=0, le=255)


class SensorHistoryQuery(BaseModel):
    """Query parameters for sensor history."""
    hours: int = 24
    sensor: Optional[str] = None


class SensorStats(BaseModel):
    """Aggregated sensor statistics."""
    sensor: str
    min_val: float
    max_val: float
    avg_val: float
    count: int
    period_hours: int
