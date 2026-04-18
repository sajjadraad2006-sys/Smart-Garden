# AgriMaster Pro — Setup Guide

## Prerequisites
- Linux PC or Raspberry Pi (Ubuntu/Debian)
- Python 3.11+
- ESP32-WROOM-32 board + sensors (see WIRING_DIAGRAM.md)
- Local WiFi network

## Quick Start (Simulation Mode)

```bash
cd /home/sajjad/Desktop/garden_project

# Install dependencies
./scripts/install.sh

# Start everything (simulator + backend)
./scripts/run_all.sh

# Open dashboard
xdg-open agrimaster-pro.html
```

The system starts in **simulation mode** by default — no hardware needed.

## Hardware Setup

### 1. Flash ESP32 Firmware
1. Install Arduino IDE or PlatformIO
2. Install libraries: `DHT`, `BH1750`, `DallasTemperature`, `PubSubClient`, `ArduinoJson`, `Adafruit_INA219`
3. Edit `firmware/config.h` — set your WiFi SSID/password and MQTT broker IP
4. Flash `firmware/main.ino` to ESP32
5. Open Serial Monitor at 115200 baud to verify

### 2. Configure MQTT
```bash
./scripts/setup_mqtt.sh
```

### 3. Switch to Hardware Mode
Edit `config/system.yaml`:
```yaml
system:
  simulation_mode: false
```

### 4. Start Backend
```bash
./scripts/run_all.sh
```

## API Documentation
Once running, visit: http://localhost:8000/docs

## Configuration
All tunable parameters are in `config/system.yaml`. Key settings:
- `algorithm.cycle_interval_seconds`: Decision engine frequency (default 30s)
- `algorithm.irrigation.*`: Irrigation timing and thresholds
- `alerts.thresholds.*`: Alert trigger levels

## Assumptions
- Pump delivers 2.0 L/min (configurable in system.yaml)
- Rain tip = 0.2794mm per bucket tip
- pH calibration uses two-point method (pH 4.0 and 7.0 buffer solutions)
- Soil moisture sensor calibrated with MOISTURE_DRY=3800 and MOISTURE_WET=1200 ADC values
- Max 3 relays active simultaneously (15A power budget)

## Known Issues Resolved in v1.0.1

### Critical Hardware Fixes
- **A-01**: GPIO 21 conflict — RGB LED Blue moved from GPIO 21 (I2C SDA) to GPIO 4. DHT22 moved from GPIO 4 to GPIO 36.
- **A-02**: GPIO 0 (BOOT pin) — pH-Up relay moved from GPIO 0 to GPIO 16. MH-Z19B RX moved to GPIO 39 (input-only).

### Critical Firmware Fixes
- **A-03**: NTP time synchronization added — timestamps now use real Unix time instead of `millis()`.
- **A-04**: Arduino library versions pinned in `firmware/libraries.txt` and `firmware/install_libs.sh`.
- **A-05**: OTA update implementation added as `firmware/ota_update.cpp`.
- **C-09**: MQTT QoS levels set: QoS 0 for sensor data, QoS 1 for commands.
- **C-10**: Rain gauge ISR debounced (20ms) to reject switch bounce.

### Critical Backend Fixes
- **A-06**: All `__init__.py` package files verified.
- **A-07**: paho-mqtt thread safety — queue bridge prevents asyncio RuntimeError.
- **A-08**: Actuator controller service created (`backend/services/actuator_controller.py`).
- **A-09**: WebSocket message schema defined (`backend/models/websocket_message.py`).
- **A-10**: API key authentication added to all write endpoints (X-API-Key header).

### Critical Algorithm Fixes
- **A-11**: Linear regression normalized to minutes (was using raw ms — slope off by 60,000×).
- **A-12**: Lighting algorithm corrected — uses lux deficit proportional to 50,000 lux scale.
- **A-13**: `_is_daytime()`, `_is_night()`, `_is_morning()` implemented with Basra timezone.
- **A-14**: `_calc_irrigation_duration()` properly accesses pump_flow_lpm from config.
- **B-05**: pH weighted average now weights by plant zone area.
- **B-06**: Fan speed hysteresis (±0.5°C dead band) and rate limiting (max 30%/cycle).
- **B-07**: Misting startup suppression — waits one cooldown before first activation.
- **B-08**: Stress function divide-by-zero guard and NaN handling.

### New Files Created
- `config/mosquitto.conf` — MQTT broker configuration (B-01)
- `backend/algorithm/state_manager.py` — Persistent algorithm memory (B-02)
- `backend/algorithm/scheduler.py` — Enhanced with daily/one-shot scheduling (B-04)
- `backend/services/actuator_controller.py` — MQTT command publisher (A-08)
- `backend/services/auth.py` — API key authentication (A-10)
- `backend/models/websocket_message.py` — WS message schema (A-09)
- `firmware/ota_update.cpp` — OTA implementation (A-05)
- `firmware/libraries.txt` / `install_libs.sh` — Library versions (A-04)
- `.env.example` / `.gitignore` / `requirements-dev.txt`

### Configuration Changes
- `config/system.yaml`: Added `location` block (Basra, Iraq), version bumped to 1.0.1
- `backend/requirements.txt`: Added `pytz`, `astral`, `python-multipart`
- `database`: Added `algorithm_state` table (C-04)

### API Changes
- All POST/PUT/DELETE endpoints now require `X-API-Key` header
- GET `/api/sensors/history` returns structured response with stats (C-12)

