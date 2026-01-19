#!/bin/bash
# Start the backend API server
cd /home/umichleg/ai-domain-discovery/backend
source venv/bin/activate

# Ensure no OpenAI key interferes
unset OPENAI_API_KEY

# Start uvicorn
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
