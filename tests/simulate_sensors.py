"""Sensor Simulator — publishes realistic fake data to MQTT for testing without hardware.
Responds to actuator commands by adjusting simulated state."""
import json
import time
import math
import random
import paho.mqtt.client as mqtt
import yaml
import os
import sys

# Load config
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "system.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)

BROKER = config["mqtt"]["broker"]
PORT = config["mqtt"]["port"]
TOPIC_SENSORS = config["mqtt"]["topics"]["sensors"]
TOPIC_CMD = config["mqtt"]["topics"]["commands"]
TOPIC_STATUS = config["mqtt"]["topics"]["status"]
DEVICE_ID = config["mqtt"]["device_id"]
INTERVAL = config["algorithm"]["sensor_read_interval_ms"] / 1000

# ═══ Simulated State ═══
class SimState:
    def __init__(self):
        self.time_offset = 0
        self.soil_moisture = 55.0
        self.ph = 6.5
        self.co2 = 600.0
        self.rainfall_accum = 0.0
        self.rain_event = False
        self.rain_remaining = 0
        # Actuator effects
        self.pump_on = False
        self.fan_speed = 0
        self.misting = False
        self.ph_down_on = False
        self.ph_up_on = False
        self.light_pwm = 0

    def temperature(self, t: float) -> float:
        """Sine wave 18-34°C with 24h period + noise."""
        hour = (t / 3600) % 24
        base = 26 + 8 * math.sin((hour - 6) * math.pi / 12)
        # Fan cooling effect
        if self.fan_speed > 0:
            base -= self.fan_speed / 255 * 3
        return base + random.gauss(0, 0.5)

    def humidity(self, temp: float) -> float:
        """Inverse relationship with temperature."""
        base = 90 - (temp - 18) * 1.8
        if self.misting:
            base += 8
        if self.rain_event:
            base += 10
        return max(20, min(98, base + random.gauss(0, 2)))

    def update_soil(self, dt: float):
        """Soil dries slowly, jumps up when pump fires."""
        # Natural drying: ~0.5%/min
        self.soil_moisture -= 0.008 * dt
        if self.pump_on:
            self.soil_moisture += 0.4 * dt  # Rapid increase when irrigating
        if self.rain_event:
            self.soil_moisture += 0.1 * dt
        self.soil_moisture = max(5, min(98, self.soil_moisture))

    def update_ph(self, dt: float):
        """Slow drift, corrects when dosing pumps fire."""
        self.ph += random.gauss(0, 0.002)
        if self.ph_down_on:
            self.ph -= 0.05 * dt
        if self.ph_up_on:
            self.ph += 0.05 * dt
        self.ph = max(3, min(10, self.ph))

    def light(self, t: float) -> float:
        """0 at night, gaussian peak at noon, cloudy days randomly."""
        hour = (t / 3600) % 24
        if hour < 6 or hour > 20:
            lux = 0
        else:
            peak = 55000
            lux = peak * math.exp(-0.5 * ((hour - 12) / 3) ** 2)
            # Random cloud factor
            if random.random() < 0.15:
                lux *= random.uniform(0.2, 0.6)
        if self.light_pwm > 0:
            lux += self.light_pwm / 255 * 15000
        return max(0, lux + random.gauss(0, 500))

    def update_co2(self, dt: float):
        """400 base, higher when fan off."""
        target = 400 if self.fan_speed > 100 else 700
        self.co2 += (target - self.co2) * 0.01 * dt + random.gauss(0, 10)
        self.co2 = max(350, min(3000, self.co2))

    def wind(self) -> float:
        """Weibull distribution with gusts."""
        base = random.weibullvariate(8, 2)
        if random.random() < 0.05:
            base += random.uniform(10, 30)  # Gust
        return max(0, min(80, base))

    def update_rain(self, dt: float):
        """Poisson rain events."""
        if not self.rain_event and random.random() < 0.0005:
            self.rain_event = True
            self.rain_remaining = random.uniform(5, 50)
        if self.rain_event:
            rate = self.rain_remaining / 30  # mm per minute
            self.rainfall_accum += rate * dt / 60
            self.rain_remaining -= rate * dt / 60
            if self.rain_remaining <= 0:
                self.rain_event = False

    def soil_temp(self, air_temp: float) -> float:
        """Soil temp lags air temp."""
        return air_temp * 0.7 + 6 + random.gauss(0, 0.3)

    def power(self) -> float:
        """Power based on active actuators."""
        w = 2.0  # Base ESP32
        if self.pump_on: w += 45
        if self.misting: w += 15
        w += self.fan_speed / 255 * 25
        w += self.light_pwm / 255 * 40
        return w + random.gauss(0, 0.5)


sim = SimState()
start_time = time.time()

# ═══ MQTT Command Handler ═══
def on_message(client, userdata, msg):
    try:
        cmd = json.loads(msg.payload.decode())
        target = cmd.get("target", "")
        action = cmd.get("action", "")
        value = cmd.get("value", False)

        if action == "SET_RELAY":
            if target == "pump_main" or target == "zone1" or target == "zone2":
                sim.pump_on = value
            elif target == "misting":
                sim.misting = value
            elif target == "ph_down":
                sim.ph_down_on = value
            elif target == "ph_up":
                sim.ph_up_on = value
            print(f"[SIM] {target} → {'ON' if value else 'OFF'}")
        elif action == "SET_PWM":
            val = cmd.get("value", 0)
            if target == "fan":
                sim.fan_speed = val
            elif target == "grow_light":
                sim.light_pwm = val
            print(f"[SIM] PWM {target} → {val}")

        # Auto-off after duration
        duration = cmd.get("duration_sec", 0)
        if duration > 0 and value:
            import threading
            def auto_off():
                if target in ("pump_main", "zone1", "zone2"):
                    sim.pump_on = False
                elif target == "misting":
                    sim.misting = False
                elif target == "ph_down":
                    sim.ph_down_on = False
                elif target == "ph_up":
                    sim.ph_up_on = False
                print(f"[SIM] Auto-off {target}")
            threading.Timer(duration, auto_off).start()

    except Exception as e:
        print(f"[SIM] Command error: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(TOPIC_CMD)
        print(f"[SIM] Connected to MQTT, subscribed to {TOPIC_CMD}")

# ═══ Main Loop ═══
def main():
    client = mqtt.Client(client_id="agrimaster_simulator")
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[SIM] Connecting to MQTT broker at {BROKER}:{PORT}...")
    try:
        client.connect(BROKER, PORT, 60)
    except Exception as e:
        print(f"[SIM] Cannot connect to MQTT: {e}")
        print("[SIM] Make sure Mosquitto is running: sudo systemctl start mosquitto")
        sys.exit(1)

    client.loop_start()
    print("[SIM] Sensor simulator running. Ctrl+C to stop.")

    last_time = time.time()
    try:
        while True:
            now = time.time()
            dt = now - last_time
            last_time = now
            t = now - start_time

            # Update stateful sensors
            sim.update_soil(dt)
            sim.update_ph(dt)
            sim.update_co2(dt)
            sim.update_rain(dt)

            temp = sim.temperature(t)
            payload = {
                "device_id": DEVICE_ID,
                "timestamp": int(now * 1000),
                "sensors": {
                    "temperature": round(temp, 1),
                    "humidity": round(sim.humidity(temp), 1),
                    "soil_moisture": round(sim.soil_moisture, 1),
                    "soil_temp": round(sim.soil_temp(temp), 1),
                    "ph": round(sim.ph, 2),
                    "light_lux": round(sim.light(t), 0),
                    "co2_ppm": round(sim.co2, 0),
                    "wind_kmh": round(sim.wind(), 1),
                    "rainfall_mm": round(sim.rainfall_accum, 1),
                    "power_w": round(sim.power(), 1),
                },
                "actuators": {
                    "pump_main": sim.pump_on,
                    "zone1": sim.pump_on,
                    "zone2": False,
                    "misting": sim.misting,
                    "fan_speed": sim.fan_speed,
                    "light_pwm": sim.light_pwm,
                    "fertilizer": False,
                    "ph_down": sim.ph_down_on,
                    "ph_up": sim.ph_up_on,
                }
            }

            client.publish(TOPIC_SENSORS, json.dumps(payload))
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\n[SIM] Stopped")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
