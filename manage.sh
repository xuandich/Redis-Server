#!/bin/bash

SERVICE="redis-crawler"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_status() {
    local active
    active=$(systemctl is-active "$SERVICE" 2>/dev/null)
    local enabled
    enabled=$(systemctl is-enabled "$SERVICE" 2>/dev/null)

    if [ "$active" = "active" ]; then
        echo "  Status  : ✅ running"
    else
        echo "  Status  : ❌ stopped ($active)"
    fi
    echo "  Boot    : $enabled"
    echo "  Dashboard: http://localhost:5000"
    echo "  Redis   : localhost:6379"
}

show_menu() {
    clear
    echo "================================================"
    echo "   Redis Crawler Stack — Service Manager"
    echo "================================================"
    print_status
    echo ""
    echo "  1) Start service"
    echo "  2) Stop service"
    echo "  3) Stop + flush all Redis jobs"
    echo "  4) Restart service"
    echo "  5) View status"
    echo "  6) Follow logs (live)"
    echo "  7) Enable auto-start on boot"
    echo "  8) Disable auto-start on boot"
    echo "  9) Full reset (flush + rebuild)"
    echo "  0) Exit"
    echo "================================================"
    echo -n "  Choose [0-9]: "
}

require_root() {
    if [ "$EUID" -ne 0 ]; then
        echo ""
        echo "❌ This action requires sudo. Run: sudo ./manage.sh"
        echo ""
        read -rp "Press Enter to continue..."
        return 1
    fi
    return 0
}

while true; do
    show_menu
    read -r choice
    echo ""

    case "$choice" in
        1)
            require_root || continue
            echo "Starting $SERVICE..."
            systemctl start "$SERVICE"
            echo "✅ Done"
            ;;
        2)
            require_root || continue
            echo "Stopping $SERVICE..."
            systemctl stop "$SERVICE"
            echo "✅ Done"
            ;;
        3)
            require_root || continue
            echo "Stopping $SERVICE and flushing Redis..."
            systemctl stop "$SERVICE"
            "$PROJECT_ROOT/stop.sh" -clear
            echo "✅ Done"
            ;;
        4)
            require_root || continue
            echo "Restarting $SERVICE..."
            systemctl restart "$SERVICE"
            echo "✅ Done"
            ;;
        5)
            systemctl status "$SERVICE"
            ;;
        6)
            echo "Following logs — press Ctrl+C to exit"
            echo ""
            journalctl -u "$SERVICE" -f
            ;;
        7)
            require_root || continue
            systemctl enable "$SERVICE"
            echo "✅ Auto-start enabled"
            ;;
        8)
            require_root || continue
            systemctl disable "$SERVICE"
            echo "✅ Auto-start disabled"
            ;;
        9)
            require_root || continue
            echo "⚠️  This will stop all services, flush Redis data, and rebuild Docker volumes."
            read -rp "   Are you sure? (yes/N): " confirm
            if [ "$confirm" = "yes" ]; then
                systemctl stop "$SERVICE"
                "$PROJECT_ROOT/stop.sh" -clear
                docker compose -f "$PROJECT_ROOT/docker-compose.yml" down --volumes
                systemctl start "$SERVICE"
                echo "✅ Full reset complete"
            else
                echo "   Cancelled"
            fi
            ;;
        0)
            echo "Bye."
            exit 0
            ;;
        *)
            echo "Invalid option."
            ;;
    esac

    echo ""
    read -rp "Press Enter to continue..."
done
