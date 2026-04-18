# AgriMaster Pro — ESP32 Wiring Diagram

## Sensor Connections

```
ESP32-WROOM-32
┌──────────────────┐
│                  │
│  GPIO 36 ────────── DHT22 (DATA) ── 10kΩ pullup to 3.3V  [moved from GPIO 4]
│  GPIO 34 ────────── Soil Moisture Sensor (Analog Out)
│  GPIO 35 ────────── pH Sensor SEN0161 (Analog Out)
│  GPIO 21 ────────── I2C SDA ─┬── BH1750 SDA
│  GPIO 22 ────────── I2C SCL ─┤   INA219 SDA
│                              ├── BH1750 SCL
│                              └── INA219 SCL
│  GPIO 17 ────────── MH-Z19B RX (ESP TX → sensor RX)
│  GPIO 39 ────────── MH-Z19B TX (sensor TX → ESP RX)  [input-only, safe]
│  GPIO 27 ────────── Anemometer (Pulse output)
│  GPIO 26 ────────── Rain Gauge (Tipping bucket switch)
│  GPIO 5  ────────── DS18B20 (DATA) ── 4.7kΩ pullup to 3.3V
│                  │
│  GPIO 32 ────────── Relay: Main Pump (Active LOW)
│  GPIO 33 ────────── Relay: Drip Zone 1
│  GPIO 25 ────────── Relay: Drip Zone 2
│  GPIO 14 ────────── Relay: Misting System
│  GPIO 12 ────────── MOSFET: Ventilation Fan (PWM)
│  GPIO 13 ────────── MOSFET: Grow Light (PWM)
│  GPIO 15 ────────── Relay: Fertilizer Pump
│  GPIO 2  ────────── Relay: pH-Down Pump
│  GPIO 0  ────────── [RESERVED — BOOT pin, do NOT connect]
│  GPIO 16 ────────── Relay: pH-Up Pump  [moved from GPIO 0]
│  GPIO 23 ────────── Buzzer
│  GPIO 18 ────────── RGB LED Red
│  GPIO 19 ────────── RGB LED Green
│  GPIO 4  ────────── RGB LED Blue  [moved from GPIO 21]
│                  │
│  5V  ────────────── Sensor VCC bus, Relay VCC
│  3.3V ───────────── DHT22, DS18B20, BH1750
│  GND ────────────── Common Ground bus
└──────────────────┘
```

## Power Supply
- **ESP32**: 5V USB or regulated from 12V
- **Relays**: 12V solenoid power through relay contacts
- **Total current budget**: 15A @ 12V circuit breaker

## Notes
- All relay modules use **active LOW** logic
- I2C devices (BH1750, INA219) share the same bus — ensure different addresses
- BH1750 default address: 0x23, INA219 default: 0x40
- Use **level shifters** if connecting 5V sensors to 3.3V ESP32 ADC
- pH sensor requires **isolated power** to avoid ground loop interference
