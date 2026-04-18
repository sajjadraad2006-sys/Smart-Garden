"""Pydantic models for decision engine actions and alerts."""
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class ActionPriority(str, Enum):
    EMERGENCY = "emergency"
    PH_CORRECTION = "ph_correction"
    CRITICAL = "critical"
    VENTILATION = "ventilation"
    PREVENTIVE = "preventive"
    SCHEDULED = "scheduled"
    MISTING = "misting"
    LIGHTING = "lighting"
    FERTILIZER = "fertilizer"


class Action(BaseModel):
    """Single action output from the decision engine."""
    target: str                          # e.g. "zone1", "fan", "ph_down"
    action_type: str = "SET_RELAY"       # SET_RELAY or SET_PWM
    value: bool | int = True
    duration: Optional[int] = None       # seconds
    delay: Optional[int] = None          # seconds before execution
    priority: ActionPriority = ActionPriority.SCHEDULED
    reason: str = ""
    layer: str = ""                      # which algorithm layer triggered this
    force: bool = False                  # override suppression rules


class PlantScore(BaseModel):
    """Stress/health score for a single plant."""
    plant_id: str
    plant_name: str
    zone: int = 1
    total_stress: float = 0.0
    status: str = "thriving"
    scores: dict = {}                    # per-parameter stress scores
    recommendations: List[str] = []


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert(BaseModel):
    """System alert."""
    id: Optional[int] = None
    timestamp: int = 0
    severity: AlertSeverity = AlertSeverity.INFO
    sensor: Optional[str] = None
    message: str = ""
    resolved: bool = False


class DecisionCycleResult(BaseModel):
    """Full output of one decision engine cycle."""
    timestamp: int = 0
    cycle_ms: float = 0.0               # how long the cycle took
    actions: List[Action] = []
    plant_scores: List[PlantScore] = []
    alerts: List[Alert] = []
    layers_triggered: List[str] = []
    suppressed: List[str] = []           # reasons for suppressed actions


class AlgorithmOverride(BaseModel):
    """Manual override from dashboard."""
    action: str                          # e.g. "SKIP_IRRIGATION"
    duration_minutes: int = 60


class PlantAssignment(BaseModel):
    """Plant assigned to a zone."""
    id: Optional[int] = None
    plant_id: str
    zone: int = 1
    planted_at: int = 0
    active: bool = True
