"""Alert service — generates, deduplicates, and dispatches alerts."""
import time
import logging
from typing import List, Optional
from backend.models.decision import Alert, AlertSeverity

logger = logging.getLogger("agrimaster.alerts")


class AlertService:
    def __init__(self, db, config: dict):
        self.db = db
        self.dedup_minutes = config.get("deduplication_minutes", 30)
        self.thresholds = config.get("thresholds", {})
        self._ws_manager = None

    def set_ws_manager(self, ws_manager):
        self._ws_manager = ws_manager

    def check_and_emit(self, state: dict) -> List[dict]:
        """Check sensor state against thresholds and emit new alerts."""
        new_alerts = []
        checks = [
            ("temperature", state.get("temperature", 22) > self.thresholds.get("temp_lethal_high", 42),
             AlertSeverity.CRITICAL, f"Temperature lethal at {state.get('temperature', 0):.1f}°C"),
            ("temperature", state.get("temperature", 22) < self.thresholds.get("temp_frost", 0),
             AlertSeverity.CRITICAL, f"Frost risk at {state.get('temperature', 0):.1f}°C"),
            ("soil_moisture", state.get("soil_moisture", 50) < self.thresholds.get("soil_critical_dry", 15),
             AlertSeverity.CRITICAL, f"Soil critically dry at {state.get('soil_moisture', 0):.0f}%"),
            ("ph", state.get("ph", 7) < self.thresholds.get("ph_survivable_low", 4) or
             state.get("ph", 7) > self.thresholds.get("ph_survivable_high", 9),
             AlertSeverity.CRITICAL, f"pH {state.get('ph', 7):.1f} out of survivable range"),
            ("co2_ppm", state.get("co2_ppm", 400) > self.thresholds.get("co2_dangerous", 2000),
             AlertSeverity.WARNING, f"CO2 high at {state.get('co2_ppm', 0):.0f} ppm"),
            ("power_w", state.get("power_w", 0) > self.thresholds.get("power_high", 200),
             AlertSeverity.WARNING, f"High power: {state.get('power_w', 0):.1f}W"),
        ]

        for sensor, condition, severity, message in checks:
            if condition:
                # Deduplication check
                recent = self.db.get_recent_alert(sensor, minutes=self.dedup_minutes)
                if not recent:
                    alert_id = self.db.insert_alert(severity.value, message, sensor)
                    alert = {"id": alert_id, "severity": severity.value,
                             "sensor": sensor, "message": message,
                             "timestamp": int(time.time() * 1000)}
                    new_alerts.append(alert)
                    logger.warning(f"Alert [{severity.value}] {message}")

        # Push to WebSocket clients
        if new_alerts and self._ws_manager:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._ws_manager.broadcast({
                        "type": "alerts", "alerts": new_alerts
                    }))
            except RuntimeError:
                pass

        return new_alerts

    def get_active(self, limit: int = 50) -> List[dict]:
        return self.db.get_alerts(resolved=False, limit=limit)

    def resolve(self, alert_id: int):
        self.db.resolve_alert(alert_id)
        logger.info(f"Alert {alert_id} resolved")
