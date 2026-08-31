#!/usr/bin/env bash
# Quick fix: install Qt Wayland plugin and configure the service
set -euo pipefail

echo "[1/4] Installing Qt6 Wayland plugin..."
sudo apt-get install -y qt6-wayland 2>/dev/null || {
    echo "[!] qt6-wayland not in apt, trying manual install..."
    # Find system Qt plugins directory
    SYS_QT_PLUGINS=$(find /usr/lib -name "platforms" -path "*/qt6/*" 2>/dev/null | head -1)
    if [[ -z "${SYS_QT_PLUGINS}" ]]; then
        SYS_QT_PLUGINS=$(find /usr/lib -name "platforms" -path "*/qt*/*" 2>/dev/null | head -1)
    fi
    echo "    System Qt plugins: ${SYS_QT_PLUGINS:-not found}"
}

echo "[2/4] Finding system Qt Wayland plugin..."
SYS_WAYLAND=$(find /usr/lib -name "libqwayland-generic.so" 2>/dev/null | head -1)
if [[ -z "${SYS_WAYLAND}" ]]; then
    SYS_WAYLAND=$(find /usr/lib -name "libqwayland*.so" 2>/dev/null | head -1)
fi
echo "    Found: ${SYS_WAYLAND:-not found}"

echo "[3/4] Copying Wayland plugin to OpenCV's Qt plugins..."
CV2_PLUGINS="/home/admin/a.w.a.k.e/venv/lib/python3.13/site-packages/cv2/qt/plugins/platforms"
if [[ -n "${SYS_WAYLAND}" && -d "${CV2_PLUGINS}" ]]; then
    sudo cp "${SYS_WAYLAND}" "${CV2_PLUGINS}/"
    echo "    Copied to ${CV2_PLUGINS}/"
    ls -la "${CV2_PLUGINS}/"
else
    echo "    Skipping copy (plugin not found or target dir missing)"
fi

echo "[4/4] Updating service file..."
sudo tee /etc/systemd/system/awake.service > /dev/null << 'EOF'
[Unit]
Description=A.W.A.K.E. 2.0 — Drowsiness Detection
After=graphical.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/admin/a.w.a.k.e
ExecStartPre=/bin/sleep 5
ExecStart=/home/admin/a.w.a.k.e/venv/bin/python3 -m awake.main
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-0
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=XAUTHORITY=/home/admin/.Xauthority
Environment=HOME=/home/admin
Environment=PYTHONPATH=/home/admin/a.w.a.k.e/src
Environment=QT_QPA_PLATFORM=wayland

[Install]
WantedBy=graphical.target
EOF

echo ""
echo "Done! Restart with:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl restart awake"
