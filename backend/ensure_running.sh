#!/bin/bash
# Ensure backend and scheduler are running
# Run this from cron every 5 minutes

LOG_DIR="/home/umichleg/ai-domain-discovery/logs"
BACKEND_DIR="/home/umichleg/ai-domain-discovery/backend"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Check if backend is running
if ! pgrep -f "uvicorn main:app.*8000" > /dev/null; then
    echo "$(date): Backend not running, starting..." >> "$LOG_DIR/watchdog.log"
    cd "$BACKEND_DIR"
    source venv/bin/activate
    unset OPENAI_API_KEY
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 >> "$LOG_DIR/backend.log" 2>&1 &
    echo "$(date): Backend started with PID $!" >> "$LOG_DIR/watchdog.log"
fi

# Check if scheduler is running
if ! pgrep -f "daily_discovery.py --schedule" > /dev/null; then
    echo "$(date): Scheduler not running, starting..." >> "$LOG_DIR/watchdog.log"
    cd "$BACKEND_DIR"
    source venv/bin/activate
    unset OPENAI_API_KEY
    nohup python3 daily_discovery.py --schedule >> "$LOG_DIR/scheduler.log" 2>&1 &
    echo "$(date): Scheduler started with PID $!" >> "$LOG_DIR/watchdog.log"
fi
