"""Unit tests for the Decision Engine."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock
from backend.algorithm.decision_engine import DecisionEngine
from backend.algorithm.plant_profiles import PlantProfiles
from backend.models.sensor_data import SensorState


class MockDB:
    def __init__(self):
        self.actions = []
        self.alerts = []

    def get_recent_readings(self, n=60, device_id="agrimaster_01"):
        # Return 60 mock readings with declining moisture
        return [{"timestamp": int(time.time()*1000) - (60-i)*5000,
                 "soil_moist": 60 - i * 0.3, "temp": 25, "ph": 6.5,
                 "humidity": 65, "light_lux": 30000, "co2_ppm": 600}
                for i in range(n)]

    def get_active_plants(self):
        return [{"id": 1, "plant_id": "tomato", "zone": 1,
                 "planted_at": int((time.time() - 30*86400) * 1000), "active": 1}]

    def get_last_action(self, target, action=None):
        return None

    def log_action(self, *args, **kwargs):
        self.actions.append(args)

    def get_recent_alert(self, sensor, minutes=30):
        return None

    def insert_alert(self, severity, message, sensor=None):
        self.alerts.append((severity, message, sensor))
        return len(self.alerts)


class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.db = MockDB()
        self.profiles = PlantProfiles()
        self.config = {
            "history_window_readings": 60,
            "outlier_sigma": 2.5,
            "consecutive_suspect_fault": 5,
            "plausibility": {
                "temperature": [-20, 60], "humidity": [0, 100],
                "soil_moisture": [0, 100], "ph": [0, 14],
                "light_lux": [0, 200000], "co2_ppm": [0, 10000],
            },
            "irrigation": {
                "pump_flow_lpm": 2.0, "min_duration_sec": 30,
                "max_duration_sec": 600, "midday_suppress_start": 11,
                "midday_suppress_end": 14, "predictive_minutes_threshold": 45,
                "critical_moisture_factor": 0.85,
            },
            "ph": {"hysteresis_band": 0.3, "min_dose_seconds": 5,
                   "max_dose_seconds": 30, "equilibration_hours": 2,
                   "safety_window_hours": 4},
            "ventilation": {"night_max_speed_pct": 30, "humidity_force_min_pct": 40, "critical_temp": 42},
            "misting": {"high_deficit_threshold": 15, "medium_deficit_threshold": 8,
                        "high_duration_sec": 30, "medium_duration_sec": 15,
                        "high_cooldown_min": 15, "medium_cooldown_min": 20,
                        "wind_suppress_kmh": 20, "rain_suppress_mm": 2},
            "fertilizer": {"vegetative_interval_days": 14, "flowering_interval_days": 10,
                           "dose_duration_sec": 10},
            "lighting": {"optimal_dli_klux_hours": 30},
            "conflicts": {"max_simultaneous_relays": 3},
            "thresholds": {},
        }
        self.engine = DecisionEngine(self.db, self.profiles, self.config)

    def test_normal_conditions(self):
        state = SensorState(temperature=24, humidity=65, soil_moisture=60,
                            ph=6.5, light_lux=35000, co2_ppm=600)
        result = self.engine.run_cycle(state)
        self.assertIn("actions", result)
        self.assertIn("plant_scores", result)
        self.assertIsInstance(result["actions"], list)

    def test_critical_soil_triggers_irrigation(self):
        state = SensorState(temperature=24, humidity=65, soil_moisture=15,
                            ph=6.5, light_lux=35000, co2_ppm=600)
        result = self.engine.run_cycle(state)
        irrigation_actions = [a for a in result["actions"] if a["target"] in ("zone1", "zone2")]
        self.assertTrue(len(irrigation_actions) > 0, "Should trigger irrigation for critically dry soil")

    def test_high_temp_triggers_fan(self):
        state = SensorState(temperature=38, humidity=50, soil_moisture=60,
                            ph=6.5, light_lux=35000, co2_ppm=600)
        result = self.engine.run_cycle(state)
        fan_actions = [a for a in result["actions"] if a["target"] == "fan"]
        self.assertTrue(len(fan_actions) > 0, "Should activate fan for high temp")
        self.assertTrue(fan_actions[0]["value"] > 0, "Fan should be running")

    def test_ph_correction(self):
        # High soil moisture prevents irrigation, which would block pH via L9 conflicts
        state = SensorState(temperature=24, humidity=65, soil_moisture=85,
                            ph=8.0, light_lux=35000, co2_ppm=600)
        result = self.engine.run_cycle(state)
        ph_actions = [a for a in result["actions"] if a["target"] in ("ph_down", "ph_up")]
        # pH 8.0 vs typical target ~6.4 → should trigger ph_down
        self.assertTrue(len(ph_actions) > 0, "Should trigger pH correction")

    def test_stress_scoring(self):
        state = SensorState(temperature=40, humidity=30, soil_moisture=20,
                            ph=4.0, light_lux=5000, co2_ppm=2500)
        result = self.engine.run_cycle(state)
        scores = result.get("plant_scores", [])
        if scores:
            self.assertIn(scores[0]["status"], ("critical", "dying"))

    def test_anomaly_alerts(self):
        state = SensorState(temperature=45, humidity=65, soil_moisture=10,
                            ph=3.5, co2_ppm=2500, power_w=250)
        result = self.engine.run_cycle(state)
        alerts = result.get("alerts", [])
        self.assertTrue(len(alerts) > 0, "Should generate alerts for extreme conditions")

    def test_conflict_resolution(self):
        """pH-up and pH-down should never both appear."""
        state = SensorState(temperature=24, humidity=65, soil_moisture=60,
                            ph=6.5, light_lux=35000, co2_ppm=600)
        result = self.engine.run_cycle(state)
        targets = [a["target"] for a in result["actions"]]
        has_both = "ph_up" in targets and "ph_down" in targets
        self.assertFalse(has_both, "Should never have both pH-up and pH-down")


if __name__ == "__main__":
    unittest.main()
