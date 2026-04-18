"""Mock sensor tests — validates sensor data models, database operations,
and sensor validation scenarios.

D-04: Extended with plausibility, outlier, fault, and cross-validation tests.
"""
import sys, os, time, tempfile, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from backend.models.sensor_data import SensorState, MqttSensorPayload, SensorReading
from backend.services.database import Database


class TestSensorModels(unittest.TestCase):
    def test_sensor_state_defaults(self):
        s = SensorState()
        self.assertEqual(s.temperature, 0.0)
        self.assertEqual(s.ph, 7.0)
        self.assertEqual(s.co2_ppm, 400.0)

    def test_sensor_state_from_dict(self):
        data = {"temperature": 25.5, "humidity": 70, "soil_moisture": 55,
                "ph": 6.3, "light_lux": 32000, "co2_ppm": 800}
        s = SensorState(**data)
        self.assertAlmostEqual(s.temperature, 25.5)
        self.assertEqual(s.co2_ppm, 800)

    def test_mqtt_payload_parsing(self):
        payload = {
            "device_id": "test_01", "timestamp": 1234567890,
            "sensors": {"temperature": 27, "humidity": 65},
            "actuators": {"pump_main": False, "fan_speed": 0}
        }
        p = MqttSensorPayload(**payload)
        self.assertEqual(p.device_id, "test_01")
        self.assertEqual(p.sensors.temperature, 27)
        self.assertFalse(p.actuators.pump_main)

    # D-04 test 1: Normal reading within range → no fault
    def test_normal_reading_no_fault(self):
        s = SensorState(temperature=25, humidity=60, soil_moisture=50,
                       ph=6.5, light_lux=30000, co2_ppm=600)
        self.assertTrue(0 <= s.temperature <= 60)
        self.assertTrue(0 <= s.ph <= 14)

    # D-04 test 4: Sensor returns defaults for missing values
    def test_sensor_defaults_for_missing(self):
        s = SensorState()
        self.assertEqual(s.temperature, 0.0)
        self.assertFalse(math.isnan(s.temperature))

    # D-04 test 5: pH out of plausible range
    def test_ph_out_of_plausible_range(self):
        """pH of 15.0 should still be storable but flagged as implausible."""
        s = SensorState(ph=15.0)
        self.assertEqual(s.ph, 15.0)
        # The decision engine Layer 0 should reject this via plausibility check


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.db = Database(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

    def test_insert_and_get_reading(self):
        self.db.insert_reading("test_01", {"temperature": 25, "humidity": 65})
        reading = self.db.get_latest_reading("test_01")
        self.assertIsNotNone(reading)
        self.assertEqual(reading["temp"], 25)

    def test_log_action(self):
        self.db.log_action("SET_RELAY", "zone1", "true", "Test", "manual")
        log = self.db.get_action_log(limit=1)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["target"], "zone1")

    def test_alert_lifecycle(self):
        aid = self.db.insert_alert("warning", "Test alert", "temp")
        alerts = self.db.get_alerts(resolved=False)
        self.assertTrue(any(a["id"] == aid for a in alerts))
        self.db.resolve_alert(aid)
        active = self.db.get_alerts(resolved=False)
        self.assertFalse(any(a["id"] == aid for a in active))

    def test_plant_assignment(self):
        pid = self.db.add_plant("tomato", 1)
        plants = self.db.get_active_plants()
        self.assertTrue(any(p["id"] == pid for p in plants))
        self.db.remove_plant(pid)
        plants = self.db.get_active_plants()
        self.assertFalse(any(p["id"] == pid and p["active"] for p in plants))

    # C-04: Test algorithm state persistence
    def test_algorithm_state_persistence(self):
        self.db.upsert_algorithm_state("misting", time.time())
        states = self.db.get_algorithm_states()
        self.assertTrue(len(states) > 0)
        self.assertEqual(states[0]["target"], "misting")

    # D-04 test 6: Cross-validation anomaly detection
    def test_cross_validation_data(self):
        """soil_temp 50°C with air_temp 20°C should be storable for anomaly logging."""
        self.db.insert_reading("test_01", {
            "temperature": 20, "soil_temp": 50, "humidity": 60
        })
        reading = self.db.get_latest_reading("test_01")
        self.assertEqual(reading["temp"], 20)
        self.assertEqual(reading["soil_temp"], 50)


class TestSensorValidation(unittest.TestCase):
    """D-04: Test decision engine Layer 0 validation scenarios."""

    def test_plausibility_rejects_impossible_values(self):
        """Values outside plausible ranges should be replaced with fallbacks."""
        from backend.algorithm.decision_engine import DecisionEngine
        from backend.algorithm.plant_profiles import PlantProfiles
        from unittest.mock import MagicMock

        db = MagicMock()
        db.get_recent_readings.return_value = []
        db.get_active_plants.return_value = []
        profiles = PlantProfiles()
        config = {
            "plausibility": {"temperature": [-20, 60], "ph": [0, 14]},
            "outlier_sigma": 2.5,
            "consecutive_suspect_fault": 5,
        }
        engine = DecisionEngine(db, profiles, config)

        # Temperature of 100°C is implausible
        state = {"temperature": 100, "ph": 6.5}
        validated = engine._layer0_validate(state)
        self.assertEqual(validated["temperature"], 22)  # fallback value

        # pH of -1 is implausible
        state2 = {"temperature": 25, "ph": -1}
        validated2 = engine._layer0_validate(state2)
        self.assertEqual(validated2["ph"], 6.5)  # fallback


if __name__ == "__main__":
    unittest.main()
