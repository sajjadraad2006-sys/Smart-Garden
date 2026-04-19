<p align="center">
  <img src="https://img.shields.io/badge/AgriMaster-Pro-2ecc71?style=for-the-badge&logo=seedling&logoColor=white" alt="AgriMaster Pro"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/ESP32-Firmware-blue?style=flat-square&logo=espressif"/>
  <img src="https://img.shields.io/badge/Python-FastAPI-009688?style=flat-square&logo=fastapi"/>
  <img src="https://img.shields.io/badge/MQTT-Mosquitto-660066?style=flat-square&logo=eclipse-mosquitto"/>
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?style=flat-square&logo=sqlite"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square"/>
  <img src="https://img.shields.io/badge/Plants-42_Profiles-2ecc71?style=flat-square"/>
  <img src="https://img.shields.io/badge/Tests-20_passed-brightgreen?style=flat-square"/>
  <img src="https://img.shields.io/badge/Lang-EN_|_AR-blue?style=flat-square"/>
</p>

<p align="center">
  <strong>Production-grade smart garden system that monitors 10 sensors, controls 9 actuators, and makes autonomous farming decisions every 30 seconds.</strong>
</p>

---

> **📖 [اقرأ الشرح بالعربي](docs/README_AR.md)** — شرح كامل بالعربي مع خطوات التنصيب والاستخدام

<!-- TODO: Replace with actual screenshot or demo GIF -->
<!-- ![AgriMaster Pro Dashboard](docs/assets/dashboard-demo.gif) -->

## What It Does

- **Automates irrigation, pH correction, ventilation, lighting, and fertilization** using a 10-layer decision engine — no cloud dependency, no API costs.
- **Runs a real-time dashboard** with live sensor gauges, plant health scores, and smart recommendations — fully bilingual (English + Arabic).
- **Supports 42 crop profiles** with per-plant optimal ranges, including Basra-region staples like Date Palm, Olive, and Pomegranate.
- **Works without hardware.** Open the dashboard in simulation mode, test scenarios (desert, frost, storm), and watch plants respond in real time.

## Architecture

The system has three layers: ESP32 hardware reads sensors and controls actuators via MQTT. A Python FastAPI backend runs the decision engine and persists data. A single-file HTML dashboard connects via WebSocket for live updates.

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

## Sensors (10 Channels)

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

## Actuators (9 Channels)

| Actuator | Type | Pin | Control |
|----------|------|-----|---------|
| Main Pump | Relay (Active LOW) | GPIO 32 | ON/OFF + duration |
| Drip Zone 1 | Relay | GPIO 33 | ON/OFF + duration |
| Drip Zone 2 | Relay | GPIO 25 | ON/OFF + duration |
| Misting System | Relay | GPIO 14 | ON/OFF + duration |
| Ventilation Fan | MOSFET PWM | GPIO 12 | 0–255 PWM |
| Grow Light | MOSFET PWM | GPIO 13 | 0–255 PWM |
| Fertilizer Pump | Relay | GPIO 15 | ON/OFF + duration |
| pH-Down Pump | Relay | GPIO 2 | ON/OFF + duration |
| pH-Up Pump | Relay | GPIO 16 | ON/OFF + duration |

## 10-Layer Decision Engine

Every 30 seconds, the engine evaluates all sensor data and produces actuator commands:

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

> Full specification: [docs/ALGORITHM_SPEC.md](docs/ALGORITHM_SPEC.md)

## Quick Start

### Try It Now (No Hardware)

The dashboard works standalone as a simulation. No backend, no ESP32 — just open the file:

```bash
git clone https://github.com/sajjadraad2006-sys/Smart-Garden.git
cd Smart-Garden
xdg-open agrimaster-pro.html    # Linux
# or: open agrimaster-pro.html  # macOS
# or: just double-click the file on Windows
```

The dashboard includes 6 environment scenarios (Desert, Storm, Frost, Tropical, Drought, Perfect) and a full-day simulation that cycles dawn → noon → sunset → night in 28 seconds.

### Full Stack (Backend + Simulator)

```bash
# 1. Install everything (Python venv, dependencies, Mosquitto)
./scripts/install.sh

# 2. Start all services
./scripts/run_all.sh

# 3. Open the dashboard
xdg-open agrimaster-pro.html
# API docs: http://localhost:8000/docs
```

### Hardware Mode

Flash the ESP32, connect your sensors, and switch to real data:

```bash
# 1. Flash ESP32 firmware (see docs/SETUP_GUIDE.md for wiring)
# 2. Edit firmware/config.h with your WiFi and MQTT settings
# 3. Disable simulation
sed -i 's/simulation_mode: true/simulation_mode: false/' config/system.yaml

# 4. Start backend
./scripts/run_all.sh
```

> Full hardware guide: [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) · Wiring diagram: [docs/WIRING_DIAGRAM.md](docs/WIRING_DIAGRAM.md)

## Configuration

All tunable parameters live in `config/system.yaml`. The most commonly changed fields:

```yaml
algorithm:
  cycle_interval_seconds: 30      # How often the engine runs
  irrigation:
    pump_flow_lpm: 2.0            # Your pump's flow rate
    midday_suppress_start: 11     # Skip irrigation 11:00–14:00
    midday_suppress_end: 14
  ph:
    hysteresis_band: 0.3          # pH dead band to prevent oscillation
    equilibration_hours: 2        # Cooldown between pH doses
  ventilation:
    night_max_speed_pct: 30       # Cap fan speed at night (noise)
  conflicts:
    max_simultaneous_relays: 3    # Power budget limit (15A)

simulation_mode: true             # Set to false for real hardware

location:
  city: "Basra"                   # Used for weather context
  timezone: "Asia/Baghdad"
```

## API Reference

Write endpoints (POST, DELETE) require an API key via `X-API-Key` header. Read endpoints are open.

```bash
export AGRIMASTER_API_KEY="your-secret-key"
```

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

> Interactive API docs available at `http://localhost:8000/docs` after starting the backend.

## Plant Database

42 plant profiles across 6 categories. Each profile defines optimal ranges for temperature, humidity, soil moisture, pH, light, and CO₂. Profiles include Basra-region staples: Date Palm, Olive, and Pomegranate.

| Category | Plants |
|----------|--------|
| Grains & Cereals | Wheat, Rice, Corn, Barley, Sorghum |
| Vegetables | Tomato, Potato, Cucumber, Pepper, Spinach, Lettuce, Onion, Garlic, Eggplant, Carrot |
| Fruits | Apple, Strawberry, Mango, Watermelon, Banana, Grape, Orange, Lemon, Pineapple, Pomegranate |
| Trees | Olive, Date Palm, Avocado, Coconut, Fig, Almond |
| Herbs & Spices | Mint, Basil, Saffron, Turmeric, Ginger, Lavender |
| Industrial | Sunflower, Cotton, Sugar Cane |

## Testing

```bash
cd garden_project
source venv/bin/activate
PYTHONPATH=. python -m pytest tests/ -v

# Run a specific test file:
PYTHONPATH=. python -m pytest tests/test_algorithm.py -v

# Expected output:
# tests/test_algorithm.py    — 7 passed
# tests/test_sensors_mock.py — 13 passed
# Total: 20 passed, 0 failed
```

## Safety Mechanisms

These are hard limits enforced by the decision engine, not configurable overrides:

| System | Safety Rule |
|--------|-------------|
| pH dosing | Max 30 seconds per dose, 2-hour equilibration cooldown |
| Irrigation | 30s–600s duration bounds, midday suppression (11:00–14:00) |
| Misting | Night suppression (fungal risk), wind/rain suppression |
| Fan | Hysteresis band (±0.5°C), rate limiting (30%/cycle max change) |
| Power | Max 3 simultaneous relays (15A budget) |
| Startup | No misting on first cycle after reboot |

## Thread Safety

- SQLite uses WAL mode with threading locks.
- paho-mqtt uses a thread-safe queue bridge to the asyncio event loop.
- Algorithm state manager uses atomic dict operations.

<details>
<summary><strong>Project Structure</strong></summary>

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
│   ├── system.yaml              # Master configuration
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
│   ├── README_AR.md             # Full Arabic documentation
│   ├── SETUP_GUIDE.md           # Installation & hardware guide
│   ├── WIRING_DIAGRAM.md        # ESP32 pin diagram
│   └── ALGORITHM_SPEC.md        # Decision engine specification
│
├── agrimaster-pro.html          # Single-file dashboard (no build step)
├── LICENSE                      # MIT License
├── .env.example                 # Environment variable template
└── .gitignore
```

</details>

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| Backend | Python 3.11+, Mosquitto MQTT broker |
| Firmware | Arduino IDE or PlatformIO, ESP32-WROOM-32 |
| Dashboard | Any modern browser (Chrome, Firefox, Edge) |
| OS | Linux (Ubuntu/Debian), Raspberry Pi, or macOS |

## Contributing

Contributions are welcome. To get started:

1. **Report a bug** — Open an [issue](https://github.com/sajjadraad2006-sys/Smart-Garden/issues) with steps to reproduce.
2. **Suggest a feature** — Open an issue tagged `enhancement`.
3. **Submit code** — Fork the repo, create a branch, and open a pull request. Keep changes focused and include tests when possible.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- Built for Iraqi agricultural conditions (Basra region, UTC+3).
- Plant profiles optimized for Middle Eastern climate zones.
- Date Palm, Olive, and Pomegranate profiles included for regional relevance.
- Dashboard supports full Arabic (RTL) localization.
