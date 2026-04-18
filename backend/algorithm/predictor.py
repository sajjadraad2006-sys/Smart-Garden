"""Statistical prediction — trend analysis using linear regression on sensor time-series.

A-11 FIX: Linear regression now normalizes timestamps to minutes-from-first
instead of using raw Unix milliseconds. Previously slope was in units/ms
(~60,000x too small) so threshold comparisons never triggered.

D-03: Uses numpy.polyfit instead of scipy.stats.linregress to remove
scipy dependency for this simple calculation.
"""
import numpy as np
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("agrimaster.predictor")


def calc_slope_per_minute(timestamps_ms: List[int],
                          values: List[float]) -> float:
    """Returns slope in units/minute. A-11 FIX: normalizes timestamps."""
    if len(timestamps_ms) < 3:
        return 0.0
    t = np.array(timestamps_ms, dtype=float)
    t_norm = (t - t[0]) / 60000.0  # Convert ms → minutes from first reading
    v = np.array(values, dtype=float)
    # Remove NaN pairs
    mask = ~(np.isnan(t_norm) | np.isnan(v))
    if mask.sum() < 3:
        return 0.0
    try:
        # D-03: numpy.polyfit instead of scipy.stats.linregress
        coeffs = np.polyfit(t_norm[mask], v[mask], 1)
        return float(coeffs[0])  # slope in units per minute
    except Exception:
        return 0.0


def minutes_to_threshold(current: float, threshold: float,
                         slope_per_min: float) -> float:
    """Returns minutes until value crosses threshold. inf if not crossing."""
    if slope_per_min >= 0:
        return float('inf')  # Not decreasing
    return (current - threshold) / abs(slope_per_min)


class Predictor:
    """Calculates trends, slopes, and time-to-critical predictions from sensor history."""

    def __init__(self, config: dict):
        self.window = config.get("history_window_readings", 60)

    def linear_slope(self, values: List[float], interval_sec: float = 5.0) -> float:
        """Calculate linear regression slope (units per minute).
        A-11 FIX: uses proper time normalization."""
        if len(values) < 3:
            return 0.0
        n = len(values)
        # Create time axis in minutes
        t = np.arange(n) * (interval_sec / 60.0)
        try:
            # D-03: numpy instead of scipy
            coeffs = np.polyfit(t, values, 1)
            return float(coeffs[0])
        except Exception:
            return 0.0

    def predict_time_to_threshold(self, current: float, threshold: float,
                                   slope: float) -> Optional[float]:
        """Predict minutes until value reaches threshold given current slope.
        Returns None if slope direction won't reach threshold."""
        if slope == 0:
            return None
        # If current is already past threshold in slope direction, return 0
        if slope < 0 and current <= threshold:
            return 0.0
        if slope > 0 and current >= threshold:
            return 0.0
        # If slope moves away from threshold, return None
        if slope > 0 and current < threshold:
            # Value increasing toward threshold (e.g., temp rising to max)
            return (threshold - current) / slope
        if slope < 0 and current > threshold:
            # Value decreasing toward threshold (e.g., moisture dropping to min)
            return (current - threshold) / abs(slope)
        return None

    def analyze_moisture(self, readings: List[dict], current: float,
                         critical_threshold: float) -> dict:
        """Analyze soil moisture trend and predict time to critical."""
        values = [r.get("soil_moist", 0) for r in readings if r.get("soil_moist") is not None]
        if len(values) < 5:
            return {"slope": 0, "minutes_to_critical": None, "trend": "stable"}

        slope = self.linear_slope(values[-self.window:])
        minutes_to_critical = self.predict_time_to_threshold(
            current, critical_threshold, slope
        )

        if slope < -0.3:
            trend = "drying_fast"
        elif slope < -0.1:
            trend = "drying_slowly"
        elif slope > 0.1:
            trend = "wetting"
        else:
            trend = "stable"

        return {
            "slope": round(slope, 4),
            "minutes_to_critical": round(minutes_to_critical, 1) if minutes_to_critical else None,
            "trend": trend
        }

    def analyze_temperature(self, readings: List[dict], current: float) -> dict:
        """Analyze temperature trend."""
        values = [r.get("temp", 0) for r in readings if r.get("temp") is not None]
        # Use last 20 readings for faster response
        recent = values[-20:] if len(values) >= 20 else values
        slope = self.linear_slope(recent) if len(recent) >= 3 else 0

        return {
            "slope": round(slope, 4),
            "rising_fast": slope > 0.5 and current > 28,
            "trend": "rising" if slope > 0.1 else "falling" if slope < -0.1 else "stable"
        }

    def analyze_ph(self, readings: List[dict], current: float) -> dict:
        """Analyze pH drift direction and rate."""
        values = [r.get("ph", 0) for r in readings if r.get("ph") is not None]
        slope = self.linear_slope(values[-self.window:]) if len(values) >= 5 else 0
        # Convert per-minute slope to per-hour
        slope_per_hour = slope * 60

        return {
            "slope_per_hour": round(slope_per_hour, 4),
            "drifting_acidic": slope_per_hour < -0.05,
            "drifting_alkaline": slope_per_hour > 0.05,
            "trend": "acidifying" if slope_per_hour < -0.05 else "alkalifying" if slope_per_hour > 0.05 else "stable"
        }

    def estimate_rainfall_moisture_contribution(self, rainfall_mm: float) -> float:
        """Estimate soil moisture increase from rainfall (approximate)."""
        return rainfall_mm * 2.5

    def should_skip_irrigation_due_to_rain(self, readings: List[dict],
                                            current_rainfall: float) -> Tuple[bool, str]:
        """Check if active rainfall means we should skip irrigation."""
        if current_rainfall <= 0:
            return False, ""

        # Check moisture trend — if increasing, rain is helping
        values = [r.get("soil_moist", 0) for r in readings if r.get("soil_moist") is not None]
        if len(values) >= 5:
            slope = self.linear_slope(values[-20:])
            if slope > 0:
                return True, f"Rainfall detected ({current_rainfall}mm), moisture increasing"

        return False, ""
