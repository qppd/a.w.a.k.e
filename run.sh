#!/usr/bin/env bash
# A.W.A.K.E. 2.0 — Run script
# Displays camera feed with face/eye tracking overlay via imshow

cd "$(dirname "$0")"

# Ensure picamera2 is importable from system packages (Raspberry Pi)
export PYTHONPATH="src"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

exec venv/bin/python3 -m src.awake.main "$@"
