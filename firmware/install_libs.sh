#!/bin/bash
# AgriMaster Pro — Install Arduino Libraries (exact versions)
set -e
echo "[LIBS] Installing Arduino libraries..."

arduino-cli lib install \
  "DHTesp@1.19.0" \
  "OneWire@2.3.7" \
  "DallasTemperature@3.11.0" \
  "BH1750@1.3.0" \
  "PubSubClient@2.8.0" \
  "ArduinoJson@7.1.0" \
  "MHZ19@1.5.3" \
  "Adafruit INA219@1.2.2"

echo "[LIBS] Installing ESP32 board support..."
arduino-cli core install esp32:esp32@2.0.16

echo "[LIBS] All libraries installed successfully"
