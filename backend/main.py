"""AgriMaster Pro — FastAPI application entry point."""
import sys
import os
import yaml
import logging
import asyncio
import time

# Add parent to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.services.database import Database
from backend.services.mqtt_broker import MqttService
from backend.services.websocket_manager import WebSocketManager
from backend.services.alert_service import AlertService
from backend.algorithm.plant_profiles import PlantProfiles
from backend.algorithm.decision_engine import DecisionEngine
from backend.algorithm.scheduler import TaskScheduler
from backend.models.sensor_data import SensorState

from backend.api import routes_sensors, routes_control, routes_history, routes_plants

# ─── Load Config ───
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "system.yaml")
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

# ─── Logging ───
log_cfg = config.get("logging", {})
logging.basicConfig(level=getattr(logging, log_cfg.get("level", "INFO")),
                    format=log_cfg.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger = logging.getLogger("agrimaster.main")

# ─── Initialize Services ───
db = Database(config["database"]["path"])
mqtt_service = MqttService(config["mqtt"])
ws_manager = WebSocketManager()
plant_profiles = PlantProfiles()
alert_service = AlertService(db, config.get("alerts", {}))
alert_service.set_ws_manager(ws_manager)

algo_config = config.get("algorithm", {})
# Merge alert thresholds into algo config for decision engine
algo_config["thresholds"] = config.get("alerts", {}).get("thresholds", {})
engine = DecisionEngine(db, plant_profiles, algo_config)
scheduler = TaskScheduler()

# ─── Latest State (shared) ───
latest_sensor_state = SensorState()
_main_loop: asyncio.AbstractEventLoop = None  # Set in startup

def on_sensor_data(payload: dict):
    """Called by MQTT when new sensor data arrives from ESP32."""
    global latest_sensor_state
    try:
        sensors = payload.get("sensors", {})
        latest_sensor_state = SensorState(**sensors)
        # Store in DB
        db.insert_reading(payload.get("device_id", "agrimaster_01"), sensors)
        # Check alerts
        alert_service.check_and_emit(sensors)
        # Push to WebSocket clients (thread-safe)
        if _main_loop and _main_loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast({
                "type": "sensor_update",
                "sensors": sensors,
                "actuators": payload.get("actuators", {}),
                "timestamp": payload.get("timestamp", int(time.time() * 1000))
            }), _main_loop)
    except Exception as e:
        logger.error(f"Error processing sensor data: {e}")

def run_decision_cycle():
    """Periodic decision engine execution."""
    try:
        result = engine.run_cycle(latest_sensor_state)
        # Send commands to ESP32 via MQTT
        for action in result.get("actions", []):
            mqtt_service.publish_command(
                target=action["target"],
                action=action.get("action_type", "SET_RELAY"),
                value=action.get("value", True),
                duration=action.get("duration", 0)
            )
        # Broadcast decision to dashboard (thread-safe)
        if _main_loop and _main_loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast({
                "type": "decision",
                "plant_scores": result.get("plant_scores", []),
                "actions": result.get("actions", []),
                "layers": result.get("layers_triggered", [])
            }), _main_loop)
    except Exception as e:
        logger.error(f"Decision cycle error: {e}")

# ─── FastAPI App ───
app = FastAPI(title="AgriMaster Pro API", version="1.0.0",
              description="Smart Garden IoT Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config["server"].get("cors_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Init Routes ───
routes_sensors.init(db)
routes_control.init(db, mqtt_service)
routes_history.init(db, engine, alert_service)
routes_plants.init(db, plant_profiles, engine)

app.include_router(routes_sensors.router)
app.include_router(routes_control.router)
app.include_router(routes_history.router)
app.include_router(routes_plants.router)

# ─── WebSocket Endpoint ───
@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # Keep alive
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)

# ─── Startup / Shutdown ───
@app.on_event("startup")
async def startup():
    global _main_loop
    _main_loop = asyncio.get_event_loop()
    logger.info("═══ AgriMaster Pro Backend Starting ═══")
    # Connect MQTT
    if not config["system"].get("simulation_mode", False):
        mqtt_service.set_sensor_callback(on_sensor_data)
        mqtt_service.connect()
    else:
        logger.info("SIMULATION MODE — MQTT not connecting to real broker")
        mqtt_service.set_sensor_callback(on_sensor_data)
        try:
            mqtt_service.connect()
        except Exception:
            logger.info("MQTT broker not available in simulation mode (OK)")

    # Start decision engine scheduler
    cycle_sec = algo_config.get("cycle_interval_seconds", 30)
    scheduler.start()
    scheduler.add_interval_job("decision_engine", run_decision_cycle, seconds=cycle_sec)
    scheduler.add_interval_job("db_prune", lambda: db.prune_old_readings(
        config["database"].get("max_readings_age_days", 90)
    ), seconds=config["database"].get("vacuum_interval_hours", 24) * 3600)
    logger.info("═══ AgriMaster Pro Backend Ready ═══")

@app.on_event("shutdown")
async def shutdown():
    scheduler.stop()
    mqtt_service.disconnect()
    logger.info("AgriMaster Pro Backend stopped")

@app.get("/")
def root():
    return {"name": "AgriMaster Pro", "version": "1.0.0", "status": "running",
            "ws_clients": ws_manager.client_count}
