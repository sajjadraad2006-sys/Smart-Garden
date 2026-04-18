"""THE MAIN SMART ALGORITHM — 10-layer decision engine for AgriMaster Pro."""
import math
import time
import logging
from datetime import datetime
from typing import List, Optional
from backend.models.decision import Action, ActionPriority, PlantScore, Alert, AlertSeverity
from backend.models.sensor_data import SensorState
from backend.algorithm.predictor import Predictor

try:
    import pytz
except ImportError:
    pytz = None

logger = logging.getLogger("agrimaster.engine")


class DecisionEngine:
    def __init__(self, db, plant_profiles, config: dict):
        self.db = db
        self.profiles = plant_profiles
        self.cfg = config
        self.predictor = Predictor(config)
        self._suspect_counts: dict = {}
        self._last_ph_dose_time: float = 0
        self._last_ph_dose_type: str = ""
        self._last_misting_time: float = 0
        self._overrides: dict = {}
        self._last_decision = None

    def run_cycle(self, current_state: SensorState) -> dict:
        """Main entry point — returns actions, scores, alerts."""
        start = time.time()
        actions: List[Action] = []
        alerts: List[Alert] = []
        layers_triggered: List[str] = []
        suppressed: List[str] = []

        state = current_state.model_dump()
        history = self.db.get_recent_readings(n=self.cfg.get("history_window_readings", 60))
        active_plants = self.db.get_active_plants()
        plant_data = []
        for ap in active_plants:
            profile = self.profiles.get(ap["plant_id"])
            if profile:
                plant_data.append({**profile, "planted_at": ap["planted_at"], "zone": ap["zone"], "db_id": ap["id"]})

        # LAYER 0: Input validation
        validated = self._layer0_validate(state)

        # LAYER 1: Plant stress scoring
        scores = self._layer1_stress(plant_data, validated)

        # LAYER 2: Predictive trends
        trends = self._layer2_trends(history, validated, plant_data)

        # LAYER 3: Irrigation
        irr_actions, irr_suppressed = self._layer3_irrigation(validated, plant_data, trends, history)
        actions.extend(irr_actions)
        suppressed.extend(irr_suppressed)
        if irr_actions:
            layers_triggered.append("L3_irrigation")

        # LAYER 4: pH correction
        ph_actions = self._layer4_ph(validated, plant_data)
        actions.extend(ph_actions)
        if ph_actions:
            layers_triggered.append("L4_ph")

        # LAYER 5: Ventilation
        vent_actions = self._layer5_ventilation(validated, plant_data)
        actions.extend(vent_actions)
        if vent_actions:
            layers_triggered.append("L5_ventilation")

        # LAYER 6: Lighting
        light_actions = self._layer6_lighting(validated, plant_data, history)
        actions.extend(light_actions)
        if light_actions:
            layers_triggered.append("L6_lighting")

        # LAYER 7: Fertilizer
        fert_actions = self._layer7_fertilizer(plant_data, actions)
        actions.extend(fert_actions)
        if fert_actions:
            layers_triggered.append("L7_fertilizer")

        # LAYER 8: Misting
        mist_actions, mist_suppressed = self._layer8_misting(validated, plant_data)
        actions.extend(mist_actions)
        suppressed.extend(mist_suppressed)
        if mist_actions:
            layers_triggered.append("L8_misting")

        # LAYER 9: Conflict resolution
        actions = self._layer9_resolve(actions)

        # LAYER 10: Anomaly detection
        new_alerts = self._layer10_anomaly(validated, history)
        alerts.extend(new_alerts)

        # Log actions to DB
        for a in actions:
            self.db.log_action(a.action_type, a.target, str(a.value), a.reason, "algorithm")
        for al in alerts:
            existing = self.db.get_recent_alert(al.sensor or "system", minutes=30)
            if not existing:
                self.db.insert_alert(al.severity.value, al.message, al.sensor)

        elapsed = (time.time() - start) * 1000
        result = {
            "timestamp": int(time.time() * 1000),
            "cycle_ms": round(elapsed, 2),
            "actions": [a.model_dump() for a in actions],
            "plant_scores": [s.model_dump() for s in scores],
            "alerts": [a.model_dump() for a in alerts],
            "layers_triggered": layers_triggered,
            "suppressed": suppressed,
        }
        self._last_decision = result
        return result

    # ═══ LAYER 0: Input Validation ═══
    def _layer0_validate(self, state: dict) -> dict:
        plaus = self.cfg.get("plausibility", {})
        sigma = self.cfg.get("outlier_sigma", 2.5)
        fault_threshold = self.cfg.get("consecutive_suspect_fault", 5)
        validated = dict(state)

        for key, (lo, hi) in plaus.items():
            val = state.get(key)
            if val is None:
                continue
            # Hard plausibility check
            if val < lo or val > hi:
                validated[key] = self._get_fallback(key)
                self._increment_suspect(key)
                continue
            self._suspect_counts[key] = 0

        # Cross-validate soil_temp vs air_temp
        if abs(validated.get("soil_temp", 0) - validated.get("temperature", 0)) > 15:
            logger.warning("Anomaly: soil_temp and air_temp differ by >15°C")

        return validated

    def _get_fallback(self, key: str) -> float:
        fallbacks = {"temperature": 22, "humidity": 60, "soil_moisture": 50,
                     "soil_temp": 20, "ph": 6.5, "light_lux": 20000,
                     "co2_ppm": 600, "wind_kmh": 5, "rainfall_mm": 0, "power_w": 10}
        return fallbacks.get(key, 0)

    def _increment_suspect(self, key: str):
        self._suspect_counts[key] = self._suspect_counts.get(key, 0) + 1

    # ═══ LAYER 1: Plant Stress Scoring ═══
    def _layer1_stress(self, plants: list, state: dict) -> List[PlantScore]:
        scores = []
        for p in plants:
            s = self._calc_stress_score(p, state)
            scores.append(s)
        return scores

    # A-13: Daytime helpers using Basra timezone
    def _is_daytime(self) -> bool:
        if pytz:
            tz_name = self.cfg.get("location", {}).get("timezone", "Asia/Baghdad")
            try:
                tz = pytz.timezone(tz_name)
                hour = datetime.now(tz).hour
            except Exception:
                hour = time.localtime().tm_hour
        else:
            hour = time.localtime().tm_hour
        return 6 <= hour < 20

    def _is_morning(self) -> bool:
        hour = time.localtime().tm_hour
        return hour in [5, 6, 7]

    def _is_night(self) -> bool:
        return not self._is_daytime()

    # B-05: Weighted average by plant zone area
    def _weighted_avg_parameter(self, plants: list, param: str, default: float = 6.5) -> float:
        total_weight = 0.0
        weighted_sum = 0.0
        for p in plants:
            value = p.get(param)
            area = p.get("area_m2", 1.0)
            if value is not None:
                weighted_sum += value * area
                total_weight += area
        return weighted_sum / total_weight if total_weight > 0 else default

    def _calc_stress_score(self, plant: dict, state: dict) -> PlantScore:
        # B-08: Stress with divide-by-zero guard
        def stress(current, mn, mx, opt):
            if current is None or (isinstance(current, float) and math.isnan(current)):
                return 0.5  # Unknown sensor -> medium stress
            range_size = mx - mn
            if range_size <= 0:
                return 0.0
            if mn <= current <= mx:
                return abs(current - opt) / range_size * 0.3
            elif current < mn:
                under = (mn - current) / max(mn, 0.001)
                return min(1.0, 0.3 + under * 0.7)
            else:
                over = (current - mx) / max(mx, 0.001)
                return min(1.0, 0.3 + over * 0.7)

        s_temp = stress(state.get("temperature", 22), plant["temp_min"], plant["temp_max"], plant["temp_opt"])
        s_hum = stress(state.get("humidity", 60), plant["humidity_min"], plant["humidity_max"], plant["humidity_opt"])
        s_soil = stress(state.get("soil_moisture", 50), plant["soil_min"], plant["soil_max"], plant["soil_opt"])
        s_ph = stress(state.get("ph", 6.5), plant["ph_min"], plant["ph_max"], plant["ph_opt"])
        s_light = stress(state.get("light_lux", 30000), plant["light_min"], plant["light_max"], plant["light_opt"])
        co2 = state.get("co2_ppm", 600)
        s_co2 = 0.0 if plant["co2_min"] <= co2 <= plant["co2_max"] else 0.3

        total = s_temp*0.25 + s_hum*0.20 + s_soil*0.20 + s_ph*0.20 + s_light*0.10 + s_co2*0.05

        if total <= 0.15: status = "thriving"
        elif total <= 0.35: status = "good"
        elif total <= 0.55: status = "stressed"
        elif total <= 0.75: status = "critical"
        else: status = "dying"

        recs = []
        if s_temp > 0.3: recs.append(f"Temperature stress ({state.get('temperature', 0):.1f}°C vs {plant['temp_min']}-{plant['temp_max']}°C)")
        if s_soil > 0.3: recs.append(f"Soil moisture stress ({state.get('soil_moisture', 0):.0f}% vs {plant['soil_min']}-{plant['soil_max']}%)")
        if s_ph > 0.3: recs.append(f"pH stress ({state.get('ph', 0):.1f} vs {plant['ph_min']}-{plant['ph_max']})")

        return PlantScore(
            plant_id=plant["id"], plant_name=plant["name"], zone=plant.get("zone", 1),
            total_stress=round(total, 3), status=status,
            scores={"temp": round(s_temp, 3), "humidity": round(s_hum, 3), "soil": round(s_soil, 3),
                    "ph": round(s_ph, 3), "light": round(s_light, 3), "co2": round(s_co2, 3)},
            recommendations=recs
        )

    # ═══ LAYER 2: Predictive Trends ═══
    def _layer2_trends(self, history: list, state: dict, plants: list) -> dict:
        critical_soil = min((p["soil_min"] for p in plants), default=30)
        moisture = self.predictor.analyze_moisture(history, state.get("soil_moisture", 50), critical_soil)
        temp = self.predictor.analyze_temperature(history, state.get("temperature", 22))
        ph = self.predictor.analyze_ph(history, state.get("ph", 6.5))
        return {"moisture": moisture, "temperature": temp, "ph": ph}

    # ═══ LAYER 3: Irrigation ═══
    def _layer3_irrigation(self, state: dict, plants: list, trends: dict, history: list):
        if not plants:
            return [], []
        actions = []
        suppressed = []
        irr_cfg = self.cfg.get("irrigation", {})

        soil = state.get("soil_moisture", 50)
        avg_soil_min = sum(p["soil_min"] for p in plants) / len(plants)
        avg_soil_opt = sum(p["soil_opt"] for p in plants) / len(plants)

        need = False
        duration = 0
        reason = ""
        priority = ActionPriority.SCHEDULED

        # Step 1: Hard trigger
        crit_factor = irr_cfg.get("critical_moisture_factor", 0.85)
        if soil < avg_soil_min * crit_factor:
            need = True
            duration = self._calc_irrigation_duration(avg_soil_opt, soil, plants, irr_cfg)
            reason = f"CRITICAL: Soil {soil:.0f}% below minimum {avg_soil_min*crit_factor:.0f}%"
            priority = ActionPriority.CRITICAL

        # Step 2: Predictive trigger
        mtc = trends["moisture"].get("minutes_to_critical")
        pred_thresh = irr_cfg.get("predictive_minutes_threshold", 45)
        if not need and mtc is not None and mtc < pred_thresh:
            need = True
            duration = self._calc_irrigation_duration(avg_soil_opt, soil, plants, irr_cfg)
            reason = f"PREDICTIVE: Will reach critical in {mtc:.0f} min"
            priority = ActionPriority.PREVENTIVE

        # Step 3: Scheduled check
        if not need:
            last = self.db.get_last_action("zone1", "SET_RELAY")
            if last:
                hours_since = (time.time() * 1000 - last["timestamp"]) / 3600000
            else:
                hours_since = 999
            base_interval = sum(p.get("irrigation_interval_hours", 12) for p in plants) / len(plants)
            adj = base_interval
            if state.get("temperature", 22) > 30: adj *= 0.7
            if state.get("humidity", 60) > 80: adj *= 1.3
            if state.get("rainfall_mm", 0) > 5: adj *= 1.5

            if hours_since >= adj and soil < avg_soil_opt:
                need = True
                duration = self._calc_irrigation_duration(avg_soil_opt, soil, plants, irr_cfg)
                reason = f"SCHEDULE: {hours_since:.1f}h since last irrigation"

        # Step 4: Suppression
        if need:
            now_hour = time.localtime().tm_hour
            suppress_start = irr_cfg.get("midday_suppress_start", 11)
            suppress_end = irr_cfg.get("midday_suppress_end", 14)
            if suppress_start <= now_hour < suppress_end and priority != ActionPriority.CRITICAL:
                suppressed.append("Midday suppression - evaporation too high")
                need = False
            if state.get("rainfall_mm", 0) > 10:
                suppressed.append("Active rainfall detected")
                need = False
            if soil > sum(p["soil_max"] for p in plants) / len(plants):
                suppressed.append("Soil already saturated")
                need = False

        if need:
            actions.append(Action(target="zone1", action_type="SET_RELAY", value=True,
                                  duration=duration, priority=priority, reason=reason, layer="L3"))
        return actions, suppressed

    # A-14: Fixed to properly use config values
    def _calc_irrigation_duration(self, target: float, current: float, plants: list, cfg: dict) -> int:
        deficit = target - current
        if deficit <= 0:
            return cfg.get("min_duration_sec", 30)
        area = sum(p.get("area_m2", 1.0) for p in plants) / max(len(plants), 1)
        liters = deficit * 0.3 * area
        flow = cfg.get("pump_flow_lpm", 2.0)
        dur = int((liters / flow) * 60)
        min_dur = cfg.get("min_duration_sec", 30)
        max_dur = cfg.get("max_duration_sec", 600)
        return max(min_dur, min(max_dur, dur))

    # ═══ LAYER 4: pH Correction ═══
    def _layer4_ph(self, state: dict, plants: list):
        if not plants:
            return []
        ph_cfg = self.cfg.get("ph", {})
        target = sum(p["ph_opt"] for p in plants) / len(plants)
        current = state.get("ph", 7.0)
        error = current - target
        band = ph_cfg.get("hysteresis_band", 0.3)

        if abs(error) < band:
            return []

        # Check equilibration cooldown
        eq_hours = ph_cfg.get("equilibration_hours", 2)
        if time.time() - self._last_ph_dose_time < eq_hours * 3600:
            return []

        # Safety: never dose both in same window
        safety_hours = ph_cfg.get("safety_window_hours", 4)
        min_dose = ph_cfg.get("min_dose_seconds", 5)
        max_dose = ph_cfg.get("max_dose_seconds", 30)

        if error > band:  # Too alkaline
            if self._last_ph_dose_type == "ph_up" and time.time() - self._last_ph_dose_time < safety_hours * 3600:
                return []
            dose = min(min_dose + (error - band) * 8, max_dose)
            self._last_ph_dose_time = time.time()
            self._last_ph_dose_type = "ph_down"
            return [Action(target="ph_down", duration=int(dose), priority=ActionPriority.PH_CORRECTION,
                          reason=f"pH {current:.1f} too alkaline (target {target:.1f}), dosing {dose:.0f}s", layer="L4")]

        if error < -band:  # Too acidic
            if self._last_ph_dose_type == "ph_down" and time.time() - self._last_ph_dose_time < safety_hours * 3600:
                return []
            dose = min(min_dose + (abs(error) - band) * 8, max_dose)
            self._last_ph_dose_time = time.time()
            self._last_ph_dose_type = "ph_up"
            return [Action(target="ph_up", duration=int(dose), priority=ActionPriority.PH_CORRECTION,
                          reason=f"pH {current:.1f} too acidic (target {target:.1f}), dosing {dose:.0f}s", layer="L4")]
        return []

    # ═══ LAYER 5: Ventilation (B-06: hysteresis) ═══
    def _layer5_ventilation(self, state: dict, plants: list):
        vent_cfg = self.cfg.get("ventilation", {})
        if not plants:
            opt_temp = 25
        else:
            opt_temp = self._weighted_avg_parameter(plants, "temp_opt", 25)

        temp = state.get("temperature", 22)
        humidity = state.get("humidity", 60)
        error = temp - opt_temp
        HYSTERESIS = 0.5  # B-06: dead band to prevent oscillation

        # Get previous fan speed from last action
        prev_speed = getattr(self, '_prev_fan_speed', 0)

        if error <= 0:
            speed = 0
        elif error < (2 - HYSTERESIS):
            speed = 0 if prev_speed < 20 else 20
        elif error < 2:
            speed = 20
        elif error < 5:
            speed = 50
        elif error < 8:
            speed = 80
        else:
            speed = 100

        if humidity > 85:
            force_min = vent_cfg.get("humidity_force_min_pct", 40)
            speed = max(speed, force_min)

        if self._is_night():
            night_max = vent_cfg.get("night_max_speed_pct", 30)
            speed = min(speed, night_max)

        # B-06: Never jump more than 30% in one cycle (motor protection)
        max_change = 30
        if speed > prev_speed + max_change:
            speed = prev_speed + max_change
        elif speed < prev_speed - max_change:
            speed = prev_speed - max_change
        speed = max(0, min(100, speed))

        self._prev_fan_speed = speed
        pwm = int(speed * 255 / 100)
        reason = f"Fan {speed}%: temp_err={error:.1f}°C, humidity={humidity:.0f}%"

        return [Action(target="fan", action_type="SET_PWM", value=pwm,
                      priority=ActionPriority.VENTILATION, reason=reason, layer="L5")]

    # ═══ LAYER 6: Lighting (A-12: corrected algorithm) ═══
    def _layer6_lighting(self, state: dict, plants: list, history: list):
        lux = state.get("light_lux", 0)
        is_day = self._is_daytime()  # A-13: uses proper daytime check

        if not plants:
            return []

        avg_light_min = self._weighted_avg_parameter(plants, "light_min", 20000)
        avg_light_opt = self._weighted_avg_parameter(plants, "light_opt", 40000)

        # A-12: Corrected lighting algorithm
        if is_day and lux < avg_light_min:
            deficit_lux = avg_light_opt - lux
            # PWM proportional to deficit: 50,000 lux deficit → 255 PWM
            pwm = int(min(255, (deficit_lux / 50000.0) * 255))
            if pwm > 10:  # ignore tiny corrections
                return [Action(target="grow_light", action_type="SET_PWM", value=pwm,
                              priority=ActionPriority.LIGHTING,
                              reason=f"Low light: {lux:.0f} lux < min {avg_light_min:.0f}", layer="L6")]

        if not is_day or lux >= avg_light_opt * 0.95:
            return [Action(target="grow_light", action_type="SET_PWM", value=0,
                          priority=ActionPriority.LIGHTING,
                          reason="Sufficient natural light or nighttime", layer="L6")]
        return []

    # ═══ LAYER 7: Fertilizer ═══
    def _layer7_fertilizer(self, plants: list, existing_actions: list):
        if not plants:
            return []
        fert_cfg = self.cfg.get("fertilizer", {})
        hour = time.localtime().tm_hour
        if not (6 <= hour <= 9):  # Morning only
            return []

        # Don't fertilize if irrigation is already running
        if any(a.target in ("zone1", "zone2", "pump_main") for a in existing_actions):
            return []

        actions = []
        for p in plants:
            planted_ms = p.get("planted_at", 0)
            days = (time.time() * 1000 - planted_ms) / 86400000 if planted_ms else 0
            germ = p.get("germination_days", 10)
            veg_end = p.get("vegetative_end_day", germ + 40)
            harvest = p.get("harvest_days", 90)

            if days < germ:
                continue  # No fertilizer for seedlings
            elif days < veg_end:
                interval = fert_cfg.get("vegetative_interval_days", 14)
            elif days < harvest:
                interval = fert_cfg.get("flowering_interval_days", 10)
            else:
                continue

            last = self.db.get_last_action("fertilizer", "SET_RELAY")
            if last:
                days_since = (time.time() * 1000 - last["timestamp"]) / 86400000
            else:
                days_since = 999

            if days_since >= interval:
                dose_dur = fert_cfg.get("dose_duration_sec", 10)
                actions.append(Action(target="fertilizer", duration=dose_dur,
                                     priority=ActionPriority.FERTILIZER,
                                     reason=f"Fertigation for {p['name']} ({days_since:.0f}d since last)", layer="L7"))
                break  # Only one fertigation per cycle
        return actions

    # ═══ LAYER 8: Misting (B-07: startup guard) ═══
    def _layer8_misting(self, state: dict, plants: list):
        if not plants:
            return [], []
        mist_cfg = self.cfg.get("misting", {})
        target_hum = self._weighted_avg_parameter(plants, "humidity_opt", 65)
        current = state.get("humidity", 60)
        deficit = target_hum - current
        suppressed = []

        # B-07: Startup suppression — don't mist on first boot
        if self._last_misting_time == 0:
            self._last_misting_time = time.time()  # Set baseline, skip this cycle
            logger.info("[LAYER8] Misting: startup suppression active")
            return [], ["Startup misting suppression"]

        if self._is_night():
            suppressed.append("Night misting suppressed (fungal risk)")
            return [], suppressed
        if state.get("wind_kmh", 0) > mist_cfg.get("wind_suppress_kmh", 20):
            suppressed.append(f"Wind too high ({state.get('wind_kmh', 0):.0f} km/h)")
            return [], suppressed
        if state.get("rainfall_mm", 0) > mist_cfg.get("rain_suppress_mm", 2):
            suppressed.append("Rainfall detected, misting unnecessary")
            return [], suppressed

        # Cooldown check
        high_thresh = mist_cfg.get("high_deficit_threshold", 15)
        med_thresh = mist_cfg.get("medium_deficit_threshold", 8)

        if deficit > high_thresh:
            cooldown = mist_cfg.get("high_cooldown_min", 15) * 60
            dur = mist_cfg.get("high_duration_sec", 30)
        elif deficit > med_thresh:
            cooldown = mist_cfg.get("medium_cooldown_min", 20) * 60
            dur = mist_cfg.get("medium_duration_sec", 15)
        else:
            return [], []

        if time.time() - self._last_misting_time < cooldown:
            return [], []

        self._last_misting_time = time.time()
        return [Action(target="misting", duration=dur, priority=ActionPriority.MISTING,
                      reason=f"Humidity deficit {deficit:.0f}% (target {target_hum:.0f}%)", layer="L8")], []

    # ═══ LAYER 9: Conflict Resolution ═══
    def _layer9_resolve(self, actions: List[Action]) -> List[Action]:
        priority_order = list(ActionPriority)
        actions.sort(key=lambda a: priority_order.index(a.priority))

        resolved = []
        active_targets = set()
        max_relays = self.cfg.get("conflicts", {}).get("max_simultaneous_relays", 3)
        relay_count = 0

        has_ph_up = any(a.target == "ph_up" for a in actions)
        has_ph_down = any(a.target == "ph_down" for a in actions)
        has_irrigation = any(a.target in ("zone1", "zone2", "pump_main") for a in actions)
        has_fertilizer = any(a.target == "fertilizer" for a in actions)

        for a in actions:
            # Never pH-up and pH-down together
            if a.target == "ph_up" and has_ph_down:
                continue
            # Never pH and irrigation simultaneously
            if a.target in ("ph_up", "ph_down") and has_irrigation:
                continue
            # Never fertilizer and pH simultaneously
            if a.target == "fertilizer" and (has_ph_up or has_ph_down):
                continue

            if a.target in active_targets:
                continue

            if a.action_type == "SET_RELAY" and a.value:
                if relay_count >= max_relays:
                    continue
                relay_count += 1

            active_targets.add(a.target)
            resolved.append(a)

        return resolved

    # ═══ LAYER 10: Anomaly Detection ═══
    def _layer10_anomaly(self, state: dict, history: list) -> List[Alert]:
        alerts = []
        thresholds = self.cfg.get("thresholds", {}) if "thresholds" not in self.cfg else {}
        # Use alert thresholds from top-level config
        t = state.get("temperature", 22)
        if t > 42:
            alerts.append(Alert(severity=AlertSeverity.CRITICAL, sensor="temperature",
                               message=f"Temperature {t:.1f}°C lethal for all plants"))
        if t < 0:
            alerts.append(Alert(severity=AlertSeverity.CRITICAL, sensor="temperature",
                               message=f"Frost risk at {t:.1f}°C"))

        soil = state.get("soil_moisture", 50)
        if soil < 15:
            alerts.append(Alert(severity=AlertSeverity.CRITICAL, sensor="soil_moisture",
                               message=f"Soil critically dry at {soil:.0f}%"))

        ph = state.get("ph", 7)
        if ph < 4.0 or ph > 9.0:
            alerts.append(Alert(severity=AlertSeverity.CRITICAL, sensor="ph",
                               message=f"pH {ph:.1f} out of survivable range"))

        co2 = state.get("co2_ppm", 400)
        if co2 > 2000:
            alerts.append(Alert(severity=AlertSeverity.WARNING, sensor="co2_ppm",
                               message=f"CO2 dangerously high at {co2:.0f} ppm"))

        power = state.get("power_w", 0)
        if power > 200:
            alerts.append(Alert(severity=AlertSeverity.WARNING, sensor="power_w",
                               message=f"High power consumption: {power:.1f}W"))

        # Sensor fault detection
        for key, count in self._suspect_counts.items():
            if count >= self.cfg.get("consecutive_suspect_fault", 5):
                alerts.append(Alert(severity=AlertSeverity.WARNING, sensor=key,
                                   message=f"Sensor fault: {key} suspect for {count} cycles"))
        return alerts

    def get_last_decision(self) -> Optional[dict]:
        return self._last_decision

    def set_override(self, action: str, duration_minutes: int):
        self._overrides[action] = time.time() + duration_minutes * 60
