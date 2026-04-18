<p align="center">
  <img src="https://img.shields.io/badge/AgriMaster-Pro-2ecc71?style=for-the-badge&logo=seedling&logoColor=white" alt="AgriMaster Pro"/>
  <br/>
  <strong>🌿 Smart Garden IoT System</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/ESP32-Firmware-blue?style=flat-square&logo=espressif"/>
  <img src="https://img.shields.io/badge/Python-FastAPI-009688?style=flat-square&logo=fastapi"/>
  <img src="https://img.shields.io/badge/MQTT-Mosquitto-660066?style=flat-square&logo=eclipse-mosquitto"/>
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?style=flat-square&logo=sqlite"/>
  <img src="https://img.shields.io/badge/Version-1.0.1-2ecc71?style=flat-square"/>
</p>

---

# AgriMaster Pro

A production-grade smart garden management system combining ESP32 hardware, a 10-layer decision engine, and a real-time web dashboard. Designed for precision agriculture — monitors 10 sensor channels, controls 9 actuators, and makes intelligent irrigation, pH, ventilation, lighting, and fertilizer decisions every 30 seconds.

## 🏗️ Architecture

```
┌─────────────────┐     MQTT (JSON)     ┌─────────────────┐     WebSocket     ┌─────────────────┐
│   ESP32 Firmware │ ◄────────────────► │  FastAPI Backend │ ◄──────────────► │   HTML Dashboard │
│                  │   agrimaster/*      │                  │    /ws/live       │                  │
│  • 10 Sensors    │                    │  • Decision Engine│                  │  • Live Gauges   │
│  • 9 Actuators   │                    │  • SQLite DB      │                  │  • Plant Health  │
│  • NTP Sync      │                    │  • Alert Service  │                  │  • 42 Plant DB   │
│  • OTA Updates   │                    │  • REST API       │                  │  • History Charts│
└─────────────────┘                    └─────────────────┘                  └─────────────────┘
```

## ✨ Features

### 🌡️ Sensors (10 channels)
| Sensor | Hardware | Pin | Protocol |
|--------|----------|-----|----------|
| Temperature & Humidity | DHT22 | GPIO 36 | OneWire |
| Soil Moisture | Capacitive v1.2 | GPIO 34 | ADC |
| Soil Temperature | DS18B20 | GPIO 5 | OneWire |
| pH Level | SEN0161 | GPIO 35 | ADC |
| Light Intensity | BH1750 | I2C (21/22) | I2C |
| CO₂ Concentration | MH-Z19B | GPIO 17/39 | UART |
| Wind Speed | Anemometer | GPIO 27 | Pulse |
| Rainfall | Tipping Bucket | GPIO 26 | ISR |
| Power Consumption | INA219 | I2C (21/22) | I2C |

### 🔌 Actuators (9 channels)
| Actuator | Type | Pin | Control |
|----------|------|-----|---------|
| Main Pump | Relay (Active LOW) | GPIO 32 | ON/OFF + duration |
| Drip Zone 1 | Relay | GPIO 33 | ON/OFF + duration |
| Drip Zone 2 | Relay | GPIO 25 | ON/OFF + duration |
| Misting System | Relay | GPIO 14 | ON/OFF + duration |
| Ventilation Fan | MOSFET PWM | GPIO 12 | 0-255 PWM |
| Grow Light | MOSFET PWM | GPIO 13 | 0-255 PWM |
| Fertilizer Pump | Relay | GPIO 15 | ON/OFF + duration |
| pH-Down Pump | Relay | GPIO 2 | ON/OFF + duration |
| pH-Up Pump | Relay | GPIO 16 | ON/OFF + duration |

### 🧠 10-Layer Decision Engine
| Layer | Function | Priority |
|-------|----------|----------|
| L0 | Input Validation & Sensor Fusion | Always |
| L1 | Plant Stress Scoring | Always |
| L2 | Predictive Trend Analysis | Always |
| L3 | Irrigation Decision | Critical |
| L4 | pH Correction | High |
| L5 | Ventilation Control (with hysteresis) | Medium |
| L6 | Supplemental Lighting | Low |
| L7 | Fertilizer Scheduling | Low |
| L8 | Misting & Humidity | Low |
| L9 | Conflict Resolution | Always |
| L10 | Anomaly Detection & Alerts | Always |

### 🌱 Plant Database
42 plant profiles across 6 categories with per-plant optimal ranges for temperature, humidity, soil moisture, pH, light, and CO₂. Categories include:
- **Grains & Cereals**: Wheat, Rice, Corn, Barley, Sorghum
- **Vegetables**: Tomato, Potato, Cucumber, Pepper, Spinach, and more
- **Fruits**: Apple, Strawberry, Mango, Watermelon, Banana, and more
- **Trees**: Olive, Date Palm, Avocado, Coconut, Fig, Pomegranate
- **Herbs & Spices**: Mint, Basil, Saffron, Turmeric, Ginger
- **Industrial**: Sunflower, Cotton, Sugar Cane

## 📁 Project Structure

```
garden_project/
├── firmware/                    # ESP32 Arduino firmware
│   ├── main.ino                 # Main firmware entry point
│   ├── config.h                 # Pin assignments, WiFi, MQTT config
│   ├── sensors.h/cpp            # Sensor reading with circular buffers
│   ├── wifi_manager.h/cpp       # WiFi, MQTT, NTP synchronization
│   ├── ota_update.h/cpp         # Over-The-Air firmware updates
│   ├── libraries.txt            # Pinned Arduino library versions
│   └── install_libs.sh          # Library installer script
│
├── backend/                     # Python FastAPI backend
│   ├── main.py                  # FastAPI app, startup, scheduler
│   ├── requirements.txt         # Production dependencies
│   ├── requirements-dev.txt     # Test dependencies
│   ├── services/
│   │   ├── database.py          # SQLite with WAL mode, thread-safe
│   │   ├── mqtt_broker.py       # paho-mqtt with async queue bridge
│   │   ├── websocket_manager.py # WebSocket broadcast manager
│   │   ├── alert_service.py     # Alert deduplication & lifecycle
│   │   ├── actuator_controller.py # MQTT command publisher
│   │   └── auth.py              # API key authentication
│   ├── algorithm/
│   │   ├── decision_engine.py   # 10-layer decision engine
│   │   ├── predictor.py         # Linear regression trend analysis
│   │   ├── plant_profiles.py    # Plant DB loader & threshold lookups
│   │   ├── state_manager.py     # Persistent algorithm state
│   │   └── scheduler.py         # APScheduler wrapper
│   ├── models/
│   │   ├── sensor_data.py       # Pydantic models for sensors/commands
│   │   ├── decision.py          # Action, Alert, PlantScore models
│   │   └── websocket_message.py # Canonical WS message schema
│   └── api/
│       ├── routes_sensors.py    # GET /api/sensors/*
│       ├── routes_control.py    # POST /api/control/* (auth required)
│       ├── routes_history.py    # GET /api/algorithm/*, alerts, health
│       └── routes_plants.py     # Plant library & management
│
├── config/
│   ├── system.yaml              # Master configuration (all thresholds)
│   ├── plants_db.json           # 42 plant profiles
│   └── mosquitto.conf           # MQTT broker configuration
│
├── tests/
│   ├── test_algorithm.py        # Decision engine unit tests
│   ├── test_sensors_mock.py     # Sensor model & DB tests
│   └── simulate_sensors.py      # MQTT sensor simulator
│
├── scripts/
│   ├── install.sh               # One-command system setup
│   ├── run_all.sh               # Start all services
│   └── setup_mqtt.sh            # Mosquitto broker setup
│
├── docs/
│   ├── SETUP_GUIDE.md           # Installation & hardware guide
│   ├── WIRING_DIAGRAM.md        # ESP32 pin diagram
│   └── ALGORITHM_SPEC.md        # Decision engine specification
│
├── agrimaster-pro.html          # Single-file dashboard (no build step)
├── .env.example                 # Environment variable template
└── .gitignore
```

## 🚀 Quick Start

### Simulation Mode (No Hardware Required)

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/garden_project.git
cd garden_project

# 2. Install everything
./scripts/install.sh

# 3. Start all services (simulator + backend)
./scripts/run_all.sh

# 4. Open the dashboard
xdg-open agrimaster-pro.html
# Or visit: http://localhost:8000/docs for API docs
```

### Hardware Mode

```bash
# 1. Flash ESP32 firmware (see docs/SETUP_GUIDE.md)
# 2. Edit firmware/config.h with your WiFi and MQTT settings
# 3. Disable simulation mode
sed -i 's/simulation_mode: true/simulation_mode: false/' config/system.yaml

# 4. Start backend
./scripts/run_all.sh
```

## 🔧 Configuration

All tunable parameters are in `config/system.yaml`:

```yaml
algorithm:
  cycle_interval_seconds: 30      # Decision engine frequency
  irrigation:
    pump_flow_lpm: 2.0            # Pump flow rate
    midday_suppress_start: 11     # Skip irrigation 11:00-14:00
    midday_suppress_end: 14
  ph:
    hysteresis_band: 0.3          # pH dead band
    equilibration_hours: 2        # Cooldown between doses
  ventilation:
    night_max_speed_pct: 30       # Max fan at night
  conflicts:
    max_simultaneous_relays: 3    # Power budget (15A)

location:
  city: "Basra"
  timezone: "Asia/Baghdad"
```

## 🔐 API Authentication

Write endpoints (POST, DELETE) require an API key:

```bash
# Set your API key
export AGRIMASTER_API_KEY="your-secret-key"

# Use it in requests
curl -X POST http://localhost:8000/api/control/relay \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"target": "zone1", "value": true, "duration": 120}'
```

Read endpoints (GET) are open for the dashboard.

## 📡 API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/sensors/latest` | No | Latest sensor readings |
| GET | `/api/sensors/history?hours=24` | No | Historical data |
| GET | `/api/sensors/stats` | No | Aggregated statistics |
| GET | `/api/sensors/export?format=csv` | No | CSV data export |
| POST | `/api/control/relay` | **Yes** | Control relay actuator |
| POST | `/api/control/pwm` | **Yes** | Set PWM value |
| GET | `/api/control/state` | No | Current actuator states |
| GET | `/api/plants/library` | No | 42 plant profiles |
| GET | `/api/plants/active` | No | Currently planted |
| POST | `/api/plants/add` | **Yes** | Add plant to zone |
| GET | `/api/algorithm/status` | No | Engine status |
| GET | `/api/algorithm/last_decision` | No | Last decision result |
| POST | `/api/algorithm/override` | **Yes** | Manual override |
| GET | `/api/alerts` | No | Active alerts |
| GET | `/api/system/health` | No | System health check |
| WS | `/ws/live` | No | Real-time updates |

## 🧪 Testing

```bash
# Run all tests
cd garden_project
source venv/bin/activate
PYTHONPATH=. python -m pytest tests/ -v

# Expected output:
# tests/test_algorithm.py    — 7 passed
# tests/test_sensors_mock.py — 13 passed
# Total: 20 passed, 0 failed
```

## 📋 Prerequisites

- **Backend**: Python 3.11+, Mosquitto MQTT broker
- **Firmware**: Arduino IDE or PlatformIO, ESP32-WROOM-32
- **OS**: Linux (Ubuntu/Debian) or Raspberry Pi

## 🔬 Technical Details

### Safety Mechanisms
- **pH dosing**: Max 30 seconds per dose, 2-hour equilibration cooldown
- **Irrigation**: 30s-600s duration bounds, midday suppression (11-14h)
- **Misting**: Night suppression (fungal risk), wind/rain suppression
- **Fan**: Hysteresis band (±0.5°C), rate limiting (30%/cycle max)
- **Conflict resolution**: Max 3 simultaneous relays (15A power budget)
- **Startup guards**: No misting on first cycle after reboot

### Thread Safety
- SQLite uses WAL mode with threading locks
- paho-mqtt uses a thread-safe queue bridge to the asyncio event loop
- Algorithm state manager uses atomic dict operations

## 📄 License

This project is open source. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built for Iraqi agricultural conditions (Basra region, UTC+3)
- Plant profiles optimized for Middle Eastern climate
- Date Palm and Olive tree profiles included for regional relevance
