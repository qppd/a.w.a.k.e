#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  A.W.A.K.E. 2.0 — Boot Service Installer
#  Run this on your Raspberry Pi to set up auto-start on boot.
#
#  Usage:
#    chmod +x install_service.sh
#    sudo ./install_service.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="awake"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
MODEL_DIR="${PROJECT_DIR}/models"
MODEL_FILE="${MODEL_DIR}/face_landmarker.task"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

# Detect venv — prefer project-local venv over system Python
VENV_DIR=""
PYTHON_BIN=""
for candidate in "${PROJECT_DIR}/venv" "${PROJECT_DIR}/.venv"; do
    if [[ -f "${candidate}/bin/python3" ]]; then
        VENV_DIR="${candidate}"
        PYTHON_BIN="${candidate}/bin/python3"
        break
    fi
done

# Fallback to system Python if no venv found
if [[ -z "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="$(which python3)"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── Pre-flight checks ───────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    error "Please run with sudo: sudo ./install_service.sh"
fi

if [[ ! -f "${PYTHON_BIN}" ]]; then
    error "Python3 not found at ${PYTHON_BIN}"
fi

if [[ ! -f "${PROJECT_DIR}/src/awake/main.py" ]]; then
    error "main.py not found — run this script from the project root"
fi

log "Project directory: ${PROJECT_DIR}"
log "Python binary:     ${PYTHON_BIN}"
if [[ -n "${VENV_DIR}" ]]; then
    log "Virtual env:       ${VENV_DIR}"
else
    warn "No venv found — using system Python (may fail on newer Debian)"
    warn "Create one with: python3 -m venv ${PROJECT_DIR}/venv"
fi

# ── Step 1: Install Python dependencies ──────────────────────
log "Installing Python dependencies..."
if [[ -f "${PROJECT_DIR}/requirements.txt" ]]; then
    ${PYTHON_BIN} -m pip install -r "${PROJECT_DIR}/requirements.txt" --quiet
    log "Dependencies installed from requirements.txt"
else
    warn "No requirements.txt found — skipping dependency install"
fi

# Update service file to use venv Python if found
if [[ -n "${VENV_DIR}" ]]; then
    VENV_PYTHON="${VENV_DIR}/bin/python3"
    log "Service will use venv Python: ${VENV_PYTHON}"
else
    VENV_PYTHON="${PYTHON_BIN}"
fi

# ── Step 2: Pre-download face model ──────────────────────────
log "Checking face model..."
if [[ -f "${MODEL_FILE}" ]]; then
    log "Face model already exists: ${MODEL_FILE}"
else
    log "Downloading face landmarker model..."
    mkdir -p "${MODEL_DIR}"
    if wget -q -O "${MODEL_FILE}" "${MODEL_URL}"; then
        log "Face model downloaded successfully"
    else
        warn "Failed to download model — will retry on first launch"
        warn "To download manually later:"
        warn "  wget -O ${MODEL_FILE} \"${MODEL_URL}\""
    fi
fi

# ── Step 3: Generate the service file ────────────────────────
log "Generating service file..."

# Auto-detect VNC display
DISPLAY_NUM=":1"
if command -v vncserver &>/dev/null; then
    # Try to find VNC display from running processes
    VNC_PID=$(pgrep -f "Xvnc" 2>/dev/null | head -1) || true
    if [[ -n "${VNC_PID}" ]]; then
        VNC_CMD=$(ps -p "${VNC_PID}" -o args= 2>/dev/null) || true
        VNC_DISPLAY=$(echo "${VNC_CMD}" | grep -oP ':\d+' | head -1) || true
        if [[ -n "${VNC_DISPLAY}" ]]; then
            DISPLAY_NUM="${VNC_DISPLAY}"
            log "Detected VNC display: ${DISPLAY_NUM}"
        fi
    fi
fi

# Detect running user (who invoked sudo)
REAL_USER="${SUDO_USER:-pi}"

cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=A.W.A.K.E. 2.0 — Drowsiness Detection
After=graphical.target

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} -m awake.main
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Display environment (VNC) — update DISPLAY if needed
Environment=DISPLAY=${DISPLAY_NUM}
Environment=XAUTHORITY=/home/${REAL_USER}/.Xauthority
Environment=HOME=/home/${REAL_USER}
Environment=PYTHONPATH=${PROJECT_DIR}/src

[Install]
WantedBy=graphical.target
EOF

log "Service file written to ${SERVICE_FILE}"

# ── Step 4: Enable and start the service ─────────────────────
log "Enabling service..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service" 2>/dev/null
log "Service enabled (auto-start on boot)"

# ── Step 5: Start the service ────────────────────────────────
read -p "Start the service now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl start "${SERVICE_NAME}.service"
    sleep 2

    if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
        log "Service is running!"
        echo ""
        systemctl status "${SERVICE_NAME}.service" --no-pager
    else
        warn "Service started but may have issues. Check logs with:"
        warn "  sudo journalctl -u ${SERVICE_NAME} -f"
    fi
else
    log "Service installed but not started. Start with:"
    log "  sudo systemctl start ${SERVICE_NAME}"
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  A.W.A.K.E. 2.0 — Service installed successfully!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Quick commands:"
echo "    sudo systemctl status ${SERVICE_NAME}     # Check status"
echo "    sudo systemctl restart ${SERVICE_NAME}    # Restart"
echo "    sudo systemctl stop ${SERVICE_NAME}       # Stop"
echo "    sudo journalctl -u ${SERVICE_NAME} -f     # View logs"
echo "    sudo systemctl disable ${SERVICE_NAME}    # Remove auto-start"
echo ""
