#!/bin/bash
# AI Domain Discovery - Dashboard Launcher

cd "$(dirname "$0")"

echo "🤖 Starting AI Domain Discovery Dashboard..."
echo ""
echo "This dashboard shows:"
echo "  • Real-time agent activity and discovery runs"
echo "  • Domain quality metrics and scores"
echo "  • Recent startup discoveries with full details"
echo "  • System health and API status"
echo ""
echo "Press Ctrl+C to exit"
echo ""
sleep 2

python3 enhanced_dashboard.py
