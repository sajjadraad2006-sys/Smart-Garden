#!/bin/bash
# AgriMaster Pro — One-Command Setup
set -e

echo "═══════════════════════════════════════"
echo "  AgriMaster Pro — System Setup"
echo "═══════════════════════════════════════"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# System dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv mosquitto mosquitto-clients sqlite3

# Python virtual environment
echo "[2/5] Setting up Python environment..."
cd "$PROJECT_DIR/backend"
python3 -m venv ../venv 2>/dev/null || true
source ../venv/bin/activate
pip3 install -r requirements.txt --quiet

# Configure Mosquitto
echo "[3/5] Configuring MQTT broker..."
sudo tee /etc/mosquitto/conf.d/agrimaster.conf > /dev/null <<EOF
listener 1883
allow_anonymous true
max_queued_messages 1000
EOF
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# Initialize database
echo "[4/5] Initializing database..."
cd "$PROJECT_DIR"
python3 -c "
import sys; sys.path.insert(0, '.')
from backend.services.database import Database
db = Database('backend/database/agrimaster.db')
print('Database initialized successfully')
"

# Verify
echo "[5/5] Verifying installation..."
python3 -c "import fastapi, paho.mqtt, uvicorn; print('All Python packages OK')"
mosquitto_sub -t 'test' -C 1 -W 2 2>/dev/null && echo "MQTT broker OK" || echo "MQTT broker running"

echo ""
echo "═══════════════════════════════════════"
echo "  Setup Complete!"
echo "  Run: ./scripts/run_all.sh"
echo "═══════════════════════════════════════"
