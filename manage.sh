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
    echo " 10) Remove all Docker images + cache (.gz)"
    echo "  0) Exit"
    echo "================================================"
    echo -n "  Choose [0-9, 10]: "
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
                echo "  ⚠️  (Docker images are NOT removed — use option 10 to remove them)"
                systemctl start "$SERVICE"
                echo "✅ Full reset complete"
            else
                echo "   Cancelled"
            fi
            ;;
        10)
            require_root || continue
            echo "⚠️  This will remove all related Docker images and .gz cache files."
            read -rp "   Are you sure? (yes/N): " confirm
            if [ "$confirm" = "yes" ]; then
                IMAGE_CACHE_DIR="$PROJECT_ROOT/Redis_Docker_Image"

                # Remove orchestrator + dashboard images
                for img in redis_server-orchestrator:latest redis_server-dashboard:latest; do
                    if docker image inspect "$img" > /dev/null 2>&1; then
                        docker rmi "$img" && echo "🗑  Removed image: $img"
                    fi
                done

                # Remove worker images + .gz cache
                if [ -d "$PROJECT_ROOT/workers" ]; then
                    for worker_dir in "$PROJECT_ROOT/workers"/*/; do
                        if [ -f "${worker_dir}Dockerfile" ]; then
                            domain=$(basename "$worker_dir")
                            img="worker-${domain}:latest"
                            if docker image inspect "$img" > /dev/null 2>&1; then
                                docker rmi "$img" && echo "🗑  Removed image: $img"
                            fi
                            cache="${worker_dir}worker-${domain}-latest.tar.gz"
                            if [ -f "$cache" ]; then
                                rm "$cache" && echo "🗑  Removed cache: $(basename $cache)"
                            fi
                        fi
                    done
                fi

                # Remove orchestrator + dashboard .gz cache
                for f in "$IMAGE_CACHE_DIR"/*.tar.gz; do
                    [ -f "$f" ] && rm "$f" && echo "🗑  Removed cache: $(basename $f)"
                done

                echo "✅ All images and cache files removed"
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
