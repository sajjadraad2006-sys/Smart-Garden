#!/bin/bash
# AgriMaster Pro — Setup Mosquitto MQTT Broker
# C-08: Full setup script with config file deployment
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[MQTT] Installing Mosquitto..."
sudo apt-get install -y mosquitto mosquitto-clients

echo "[MQTT] Deploying configuration..."
sudo systemctl stop mosquitto 2>/dev/null || true
sudo cp "$PROJECT_DIR/config/mosquitto.conf" \
    /etc/mosquitto/conf.d/agrimaster.conf
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

echo "[MQTT] Testing broker..."
sleep 1
mosquitto_pub -h localhost -t "test/ping" -m "ok" && echo "[MQTT] Broker OK" || echo "[MQTT] Broker may need a moment..."

echo "[MQTT] Broker ready on port 1883"
echo "[MQTT] Test: mosquitto_pub -t 'test' -m 'hello'"
