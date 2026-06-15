#!/bin/bash
# Stop Redis, Orchestrator, and RQ Dashboard

echo "🛑 Stopping services..."

# Kill RQ Dashboard
pkill -f "rq_dashboard" 2>/dev/null && echo "  ✅ Dashboard stopped" || echo "  ⓘ Dashboard not running"

# Stop Docker containers
docker compose down > /dev/null 2>&1 && echo "  ✅ Containers stopped" || echo "  ⓘ Docker not running"

echo ""
echo "✅ All services stopped"
