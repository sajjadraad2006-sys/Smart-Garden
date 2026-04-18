"""Actuator Controller — publishes MQTT commands to ESP32 and caches state.

A-08 FIX: This service was missing entirely. Routes_control.py receives
POST requests but had no service to actually publish MQTT commands.
"""
import json
import time
import logging
from typing import Optional

logger = logging.getLogger("agrimaster.actuator")


class ActuatorController:
    """Manages actuator state and publishes MQTT commands to ESP32."""

    def __init__(self, mqtt_service, db=None):
        self._mqtt = mqtt_service
        self._db = db
        self._state: dict = {}  # in-memory actuator state cache

    def set_relay(self, target: str, value: bool,
                  duration_sec: int = 0, reason: str = "manual",
                  triggered_by: str = "manual") -> bool:
        """Send relay command to ESP32 via MQTT."""
        success = self._mqtt.publish_command(
            target=target, action="SET_RELAY",
            value=value, duration=duration_sec
        )
        if success:
            self._state[target] = value
            logger.info(f"[ACTUATOR] {target}={'ON' if value else 'OFF'} "
                       f"({duration_sec}s) reason={reason}")
            # Log to DB
            if self._db:
                self._db.log_action("SET_RELAY", target, str(value),
                                   reason, triggered_by)
            return True
        logger.error(f"[ACTUATOR] MQTT publish failed for {target}")
        return False

    def set_pwm(self, target: str, value: int,
                reason: str = "manual", triggered_by: str = "manual") -> bool:
        """Send PWM command to ESP32 via MQTT. value: 0-255."""
        value = max(0, min(255, value))
        success = self._mqtt.publish_command(
            target=target, action="SET_PWM", value=value
        )
        if success:
            self._state[target] = value
            logger.info(f"[ACTUATOR] PWM {target}={value} reason={reason}")
            if self._db:
                self._db.log_action("SET_PWM", target, str(value),
                                   reason, triggered_by)
            return True
        logger.error(f"[ACTUATOR] MQTT PWM publish failed for {target}")
        return False

    def get_state(self) -> dict:
        """Return copy of current actuator state cache."""
        return self._state.copy()

    def update_state_from_payload(self, actuators: dict):
        """Update internal state from ESP32 telemetry."""
        self._state.update(actuators)

    def restore_state_from_db(self, db):
        """On startup, read last known actuator state from DB."""
        try:
            log = db.get_action_log(limit=20)
            seen = set()
            for entry in log:
                target = entry["target"]
                if target not in seen:
                    seen.add(target)
                    val = entry.get("value", "false")
                    if val.isdigit():
                        self._state[target] = int(val)
                    else:
                        self._state[target] = val.lower() == "true"
            logger.info(f"[ACTUATOR] State restored: {self._state}")
        except Exception as e:
            logger.warning(f"[ACTUATOR] Could not restore state: {e}")
