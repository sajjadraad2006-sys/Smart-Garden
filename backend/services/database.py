"""SQLite database service with async-friendly operations."""
import sqlite3
import time
import threading
import logging
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger("agrimaster.db")


class Database:
    """Thread-safe SQLite wrapper for AgriMaster sensor/actuator data."""

    def __init__(self, db_path: str = "database/agrimaster.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS sensor_readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        device_id TEXT NOT NULL,
                        temp REAL, humidity REAL, soil_moist REAL,
                        soil_temp REAL, ph REAL, light_lux REAL,
                        co2_ppm REAL, wind_kmh REAL, rainfall_mm REAL,
                        power_w REAL
                    );
                    CREATE TABLE IF NOT EXISTS actuator_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        target TEXT NOT NULL,
                        value TEXT,
                        reason TEXT,
                        triggered_by TEXT
                    );
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        severity TEXT NOT NULL,
                        sensor TEXT,
                        message TEXT NOT NULL,
                        resolved INTEGER DEFAULT 0
                    );
                    CREATE TABLE IF NOT EXISTS plant_assignments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plant_id TEXT NOT NULL,
                        zone INTEGER NOT NULL,
                        planted_at INTEGER NOT NULL,
                        active INTEGER DEFAULT 1
                    );
                    CREATE INDEX IF NOT EXISTS idx_readings_time ON sensor_readings(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_readings_device ON sensor_readings(device_id);

                    -- C-04: Algorithm state persistence
                    CREATE TABLE IF NOT EXISTS algorithm_state (
                        target TEXT PRIMARY KEY,
                        last_fired_at REAL NOT NULL,
                        updated_at INTEGER NOT NULL
                    );
                """)
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
            finally:
                conn.close()

    # ─── Sensor Readings ───
    def insert_reading(self, device_id: str, sensors: dict):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO sensor_readings
                       (timestamp, device_id, temp, humidity, soil_moist,
                        soil_temp, ph, light_lux, co2_ppm, wind_kmh,
                        rainfall_mm, power_w)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (int(time.time() * 1000), device_id,
                     sensors.get("temperature"), sensors.get("humidity"),
                     sensors.get("soil_moisture"), sensors.get("soil_temp"),
                     sensors.get("ph"), sensors.get("light_lux"),
                     sensors.get("co2_ppm"), sensors.get("wind_kmh"),
                     sensors.get("rainfall_mm"), sensors.get("power_w"))
                )
                conn.commit()
            finally:
                conn.close()

    def get_latest_reading(self, device_id: str = "agrimaster_01") -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT * FROM sensor_readings WHERE device_id=? ORDER BY timestamp DESC LIMIT 1",
                    (device_id,)
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def get_readings_history(self, hours: int = 24, sensor: Optional[str] = None,
                             device_id: str = "agrimaster_01") -> List[dict]:
        since = int((time.time() - hours * 3600) * 1000)
        with self._lock:
            conn = self._get_conn()
            try:
                if sensor:
                    col = self._safe_column(sensor)
                    if not col:
                        return []
                    rows = conn.execute(
                        f"SELECT timestamp, {col} as value FROM sensor_readings "
                        f"WHERE device_id=? AND timestamp>=? ORDER BY timestamp",
                        (device_id, since)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM sensor_readings WHERE device_id=? AND timestamp>=? ORDER BY timestamp",
                        (device_id, since)
                    ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_readings_stats(self, hours: int = 168, device_id: str = "agrimaster_01") -> List[dict]:
        since = int((time.time() - hours * 3600) * 1000)
        cols = ["temp", "humidity", "soil_moist", "soil_temp", "ph",
                "light_lux", "co2_ppm", "wind_kmh", "rainfall_mm", "power_w"]
        stats = []
        with self._lock:
            conn = self._get_conn()
            try:
                for col in cols:
                    row = conn.execute(
                        f"SELECT MIN({col}) as mn, MAX({col}) as mx, AVG({col}) as av, COUNT({col}) as cnt "
                        f"FROM sensor_readings WHERE device_id=? AND timestamp>=?",
                        (device_id, since)
                    ).fetchone()
                    if row and row["cnt"] > 0:
                        stats.append({"sensor": col, "min_val": row["mn"],
                                      "max_val": row["mx"], "avg_val": round(row["av"], 2),
                                      "count": row["cnt"], "period_hours": hours})
                return stats
            finally:
                conn.close()

    def get_recent_readings(self, n: int = 60, device_id: str = "agrimaster_01") -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM sensor_readings WHERE device_id=? ORDER BY timestamp DESC LIMIT ?",
                    (device_id, n)
                ).fetchall()
                return [dict(r) for r in reversed(rows)]
            finally:
                conn.close()

    # ─── Actuator Log ───
    def log_action(self, action: str, target: str, value: str = "",
                   reason: str = "", triggered_by: str = "algorithm"):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO actuator_log (timestamp, action, target, value, reason, triggered_by) VALUES (?,?,?,?,?,?)",
                    (int(time.time() * 1000), action, target, value, reason, triggered_by)
                )
                conn.commit()
            finally:
                conn.close()

    def get_last_action(self, target: str, action: Optional[str] = None) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                if action:
                    row = conn.execute(
                        "SELECT * FROM actuator_log WHERE target=? AND action=? ORDER BY timestamp DESC LIMIT 1",
                        (target, action)
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT * FROM actuator_log WHERE target=? ORDER BY timestamp DESC LIMIT 1",
                        (target,)
                    ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def get_action_log(self, limit: int = 100) -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM actuator_log ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    # ─── Alerts ───
    def insert_alert(self, severity: str, message: str, sensor: Optional[str] = None) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "INSERT INTO alerts (timestamp, severity, sensor, message) VALUES (?,?,?,?)",
                    (int(time.time() * 1000), severity, sensor, message)
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def get_alerts(self, resolved: Optional[bool] = None, limit: int = 50) -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                if resolved is not None:
                    rows = conn.execute(
                        "SELECT * FROM alerts WHERE resolved=? ORDER BY timestamp DESC LIMIT ?",
                        (int(resolved), limit)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
                    ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def resolve_alert(self, alert_id: int):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("UPDATE alerts SET resolved=1 WHERE id=?", (alert_id,))
                conn.commit()
            finally:
                conn.close()

    def get_recent_alert(self, sensor: str, minutes: int = 30) -> Optional[dict]:
        since = int((time.time() - minutes * 60) * 1000)
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT * FROM alerts WHERE sensor=? AND timestamp>=? ORDER BY timestamp DESC LIMIT 1",
                    (sensor, since)
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    # ─── Plant Assignments ───
    def add_plant(self, plant_id: str, zone: int) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "INSERT INTO plant_assignments (plant_id, zone, planted_at, active) VALUES (?,?,?,1)",
                    (plant_id, zone, int(time.time() * 1000))
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def get_active_plants(self) -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM plant_assignments WHERE active=1"
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def remove_plant(self, plant_id: int):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("UPDATE plant_assignments SET active=0 WHERE id=?", (plant_id,))
                conn.commit()
            finally:
                conn.close()

    def prune_old_readings(self, max_age_days: int = 90):
        cutoff = int((time.time() - max_age_days * 86400) * 1000)
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM sensor_readings WHERE timestamp<?", (cutoff,))
                conn.commit()
                logger.info(f"Pruned readings older than {max_age_days} days")
            finally:
                conn.close()

    @staticmethod
    def _safe_column(name: str) -> Optional[str]:
        allowed = {"temp", "humidity", "soil_moist", "soil_temp", "ph",
                    "light_lux", "co2_ppm", "wind_kmh", "rainfall_mm", "power_w"}
        return name if name in allowed else None

    # C-04: Algorithm state persistence
    def upsert_algorithm_state(self, target: str, last_fired_at: float):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO algorithm_state (target, last_fired_at, updated_at) VALUES (?,?,?)",
                    (target, last_fired_at, int(time.time() * 1000))
                )
                conn.commit()
            finally:
                conn.close()

    def get_algorithm_states(self) -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute("SELECT * FROM algorithm_state").fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_last_actuator_states(self) -> dict:
        """Get last known state of each actuator from action log."""
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT target, value FROM actuator_log GROUP BY target ORDER BY timestamp DESC"
                ).fetchall()
                return {r["target"]: r["value"] for r in rows}
            finally:
                conn.close()


def init_db(path: str = "database/agrimaster.db") -> Database:
    return Database(path)
