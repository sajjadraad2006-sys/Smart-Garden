"""Plant profile loader — reads plants_db.json and provides threshold lookups."""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("agrimaster.plants")

DEFAULT_PLANTS_PATH = Path(__file__).parent.parent.parent / "config" / "plants_db.json"


class PlantProfiles:
    """Loads and queries plant profiles with optimal growing thresholds."""

    def __init__(self, json_path: Optional[str] = None):
        path = Path(json_path) if json_path else DEFAULT_PLANTS_PATH
        self.profiles: dict = {}
        self._load(path)

    def _load(self, path: Path):
        try:
            with open(path, "r") as f:
                raw = json.load(f)

            # Handle format: {"plants": [...]} with nested environment objects
            plants_list = None
            if isinstance(raw, dict) and "plants" in raw:
                plants_list = raw["plants"]
            elif isinstance(raw, list):
                plants_list = raw
            elif isinstance(raw, dict):
                # Try category-keyed format: {"Vegetables": [...], ...}
                for key, val in raw.items():
                    if isinstance(val, list):
                        for p in val:
                            if isinstance(p, dict) and "id" in p:
                                pid = p["id"]
                                self.profiles[pid] = self._normalize(p)
                logger.info(f"Loaded {len(self.profiles)} plant profiles from {path}")
                return

            if plants_list:
                for p in plants_list:
                    if not isinstance(p, dict):
                        continue
                    pid = p.get("id", p.get("name", "unknown").lower().replace(" ", "_"))
                    self.profiles[pid] = self._normalize(p)

            logger.info(f"Loaded {len(self.profiles)} plant profiles from {path}")
        except FileNotFoundError:
            logger.warning(f"Plants DB not found at {path}, using empty profiles")
        except Exception as e:
            logger.error(f"Failed to load plants DB: {e}")

    def _normalize(self, p: dict) -> dict:
        """Normalize any JSON format into flat threshold dict."""
        env = p.get("environment", {})
        growth = p.get("growth", {})

        def _env_val(key: str, field: str, default: float) -> float:
            """Extract from nested env: environment.temperature.min"""
            obj = env.get(key, {})
            if isinstance(obj, dict):
                return float(obj.get(field, default))
            # Fallback: flat keys like temp_min
            return float(p.get(f"{key}_{field}", default))

        def _range_val(key: str, idx: int, default: float) -> float:
            """Extract from array format: 'temp': [15, 30]"""
            val = p.get(key)
            if isinstance(val, (list, tuple)) and len(val) > idx:
                return float(val[idx])
            return default

        # Try nested environment format first, then flat array format
        if env:
            temp_min = _env_val("temperature", "min", 15)
            temp_max = _env_val("temperature", "max", 30)
            temp_opt = _env_val("temperature", "opt", (temp_min + temp_max) / 2)
            hum_min = _env_val("humidity", "min", 50)
            hum_max = _env_val("humidity", "max", 80)
            hum_opt = _env_val("humidity", "opt", (hum_min + hum_max) / 2)
            ph_min = _env_val("ph", "min", 6.0)
            ph_max = _env_val("ph", "max", 7.0)
            ph_opt = _env_val("ph", "opt", (ph_min + ph_max) / 2)
            soil_min = _env_val("soil_moisture", "min", 40)
            soil_max = _env_val("soil_moisture", "max", 70)
            soil_opt = _env_val("soil_moisture", "opt", (soil_min + soil_max) / 2)
            light_min = _env_val("light_lux", "min", 20000)
            light_max = _env_val("light_lux", "max", 60000)
            light_opt = _env_val("light_lux", "opt", (light_min + light_max) / 2)
            co2_min = _env_val("co2_ppm", "min", 400)
            co2_max = _env_val("co2_ppm", "max", 1200)
        else:
            # Flat array format from HTML PLANT_DB: 'temp': [15, 30], 'pH': [6.0, 7.0]
            temp_min = _range_val("temp", 0, 15)
            temp_max = _range_val("temp", 1, 30)
            temp_opt = (temp_min + temp_max) / 2
            hum_min = _range_val("humidity", 0, 50)
            hum_max = _range_val("humidity", 1, 80)
            hum_opt = (hum_min + hum_max) / 2
            ph_min = _range_val("pH", 0, 6.0)
            ph_max = _range_val("pH", 1, 7.0)
            ph_opt = (ph_min + ph_max) / 2
            soil_min = _range_val("soilMoisture", 0, 40)
            soil_max = _range_val("soilMoisture", 1, 70)
            soil_opt = (soil_min + soil_max) / 2
            light_min = _range_val("light", 0, 20) * 1000
            light_max = _range_val("light", 1, 60) * 1000
            light_opt = (light_min + light_max) / 2
            co2_min = p.get("co2_min", 400)
            co2_max = p.get("co2_max", 1200)

        return {
            "id": p.get("id", "unknown"),
            "name": p.get("name", "Unknown"),
            "category": p.get("category", ""),
            "emoji": p.get("emoji", "🌱"),
            "sci": p.get("scientific_name", p.get("sci", "")),
            "desc": p.get("description", p.get("desc", "")),
            "temp_min": temp_min, "temp_max": temp_max, "temp_opt": temp_opt,
            "humidity_min": hum_min, "humidity_max": hum_max, "humidity_opt": hum_opt,
            "ph_min": ph_min, "ph_max": ph_max, "ph_opt": ph_opt,
            "soil_min": soil_min, "soil_max": soil_max, "soil_opt": soil_opt,
            "light_min": light_min, "light_max": light_max, "light_opt": light_opt,
            "co2_min": co2_min, "co2_max": co2_max,
            "harvest_days": growth.get("harvest_days", p.get("harvest", 90)),
            "germination_days": growth.get("germination_days", p.get("germination_days", 10)),
            "vegetative_end_day": growth.get("vegetative_end_day", None),
            "irrigation_interval_hours": growth.get("irrigation_interval_hours", 12),
            "daily_light_target": growth.get("daily_light_target_klux_hours", 30),
            "area_m2": growth.get("area_m2", 1.0),
            "requires_short_day": growth.get("requires_short_day", False),
            "critical_photoperiod": growth.get("critical_photoperiod", 14),
        }

    def get(self, plant_id: str) -> Optional[dict]:
        return self.profiles.get(plant_id)

    def get_all(self) -> dict:
        return self.profiles

    def search(self, query: str) -> list:
        q = query.lower()
        return [p for p in self.profiles.values()
                if q in p["name"].lower() or q in p.get("sci", "").lower()]
