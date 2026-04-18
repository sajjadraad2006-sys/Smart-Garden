#!/bin/bash
# AgriMaster Pro — Start All Services
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "═══ AgriMaster Pro ═══"

# Activate venv if exists
[ -f venv/bin/activate ] && source venv/bin/activate

# Start MQTT broker
sudo systemctl start mosquitto 2>/dev/null || echo "[WARN] Mosquitto not installed, run install.sh first"

# Start simulator if in simulation mode
SIM_MODE=$(python3 -c "import yaml; print(yaml.safe_load(open('config/system.yaml'))['system']['simulation_mode'])" 2>/dev/null)
if [ "$SIM_MODE" = "True" ]; then
    echo "[SIM] Starting sensor simulator..."
    python3 tests/simulate_sensors.py &
    SIM_PID=$!
fi

# Start FastAPI backend
echo "[API] Starting backend on port 8000..."
cd "$PROJECT_DIR"
PYTHONPATH="$PROJECT_DIR" uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo ""
echo "═══════════════════════════════════════"
echo "  Dashboard: file://$PROJECT_DIR/agrimaster-pro.html"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Press Ctrl+C to stop"
echo "═══════════════════════════════════════"

cleanup() {
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    [ -n "$SIM_PID" ] && kill $SIM_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

wait $BACKEND_PID
