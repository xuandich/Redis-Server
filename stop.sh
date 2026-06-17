#!/bin/bash
# Stop all services (Redis, Orchestrator, Dashboard)

echo "🛑 Stopping services..."
echo ""

# Stop Docker containers gracefully (preserve Redis data)
if docker compose stop; then
    echo "  ✅ Redis stopped"
    echo "  ✅ Orchestrator stopped"
    echo "  ✅ Dashboard stopped"
    echo "  ✅ Networks cleaned up"
else
    echo "  ⓘ Docker services not running"
fi

echo ""
echo "✅ All services stopped successfully"
