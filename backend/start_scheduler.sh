#!/bin/bash
# Start the discovery scheduler (runs all agents automatically)
cd /home/umichleg/ai-domain-discovery/backend
source venv/bin/activate

# Ensure no OpenAI key interferes
unset OPENAI_API_KEY

# Start scheduler - runs discovery 3x daily + hourly rechecks
exec python3 daily_discovery.py --schedule
