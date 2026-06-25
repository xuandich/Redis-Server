#!/bin/bash
# Setup systemd service cho Redis Crawler Stack
# Chạy 1 lần trên server: sudo ./setup_systemd.sh

set -e

SERVICE_NAME="redis-crawler"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Script này cần chạy với sudo:"
    echo "   sudo ./setup_systemd.sh"
    exit 1
fi

echo "📂 Project root: $PROJECT_ROOT"
echo ""

# Kiểm tra start.sh và stop.sh tồn tại
if [ ! -f "$PROJECT_ROOT/start.sh" ]; then
    echo "❌ Không tìm thấy start.sh tại $PROJECT_ROOT"
    exit 1
fi
if [ ! -f "$PROJECT_ROOT/stop.sh" ]; then
    echo "❌ Không tìm thấy stop.sh tại $PROJECT_ROOT"
    exit 1
fi

# Đảm bảo start.sh và stop.sh có quyền execute
chmod +x "$PROJECT_ROOT/start.sh"
chmod +x "$PROJECT_ROOT/stop.sh"
echo "✅ start.sh / stop.sh đã có quyền execute"

# Nếu service đang chạy thì stop trước
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "⚠️  Service đang chạy — stop trước khi cài lại..."
    systemctl stop "$SERVICE_NAME"
    echo "   ✅ Stopped"
fi

# Tạo file systemd unit
echo "📝 Tạo $SERVICE_FILE ..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Redis Crawler Stack (start.sh)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${PROJECT_ROOT}
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=${PROJECT_ROOT}/start.sh -quiet
ExecStop=${PROJECT_ROOT}/stop.sh
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
EOF

echo "   ✅ Tạo xong: $SERVICE_FILE"
echo ""

# Reload systemd và enable các service
echo "⚙️  Cấu hình systemd..."
systemctl daemon-reload
echo "   ✅ daemon-reload"

systemctl enable docker
echo "   ✅ Docker daemon: enabled (tự lên khi boot)"

systemctl enable "$SERVICE_NAME"
echo "   ✅ ${SERVICE_NAME}: enabled (tự lên khi boot)"

echo ""
echo "🚀 Khởi động service ngay bây giờ..."
systemctl start "$SERVICE_NAME"
echo "   ✅ Started"

echo ""
echo "================================================"
echo "✅ Setup hoàn tất!"
echo ""
echo "Vận hành:"
echo "  systemctl status ${SERVICE_NAME}     # Xem trạng thái"
echo "  journalctl -u ${SERVICE_NAME} -f     # Xem log"
echo "  sudo systemctl stop ${SERVICE_NAME}  # Dừng"
echo "  sudo systemctl start ${SERVICE_NAME} # Chạy lại"
echo ""
echo "Khi update code:"
echo "  sudo systemctl stop ${SERVICE_NAME}"
echo "  git pull  (hoặc sửa file)"
echo "  sudo systemctl start ${SERVICE_NAME}"
echo "================================================"
