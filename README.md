# S.A.F.E. 2.0

> **S**ystem for **A**lerting **F**atigued **E**yes — A Raspberry Pi–based drowsiness detection system with real-time eye tracking, pan/tilt servo control, and audible alarm.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-33%20passing-brightgreen)]()

---

## Overview

S.A.F.E. 2.0 uses a camera, two servo motors, and computer vision to continuously track a driver's face and eyes. It computes the **Eye Aspect Ratio (EAR)** and **PERCLOS** metrics in real time. When these exceed calibrated thresholds for a sustained duration, an audible alarm is triggered — alerting the driver before drowsiness leads to an accident.

### Key Features

- **Real-time eye tracking** via MediaPipe FaceLandmarker (478 landmarks)
- **EAR + PERCLOS** drowsiness detection with configurable thresholds
- **Pan/tilt servo control** to keep the driver's face centred in frame
- **Interactive calibration mode** to tune thresholds per user
- **Headless mode** for running on Pi without a monitor (SSH)
- **Cross-platform** — works on Raspberry Pi (CSI camera) and Windows/macOS (USB webcam)
- **33 unit tests** covering EAR algorithm, PERCLOS, calibration, and more

---

## Hardware

| Component | Spec | Qty |
|---|---|---|
| Raspberry Pi 5 (or 4) | 8 GB RAM recommended | 1 |
| Raspberry Pi Camera v2 | 8 MP, IMX219, CSI-2 | 1 |
| Servo motor (MG90S) | 1.8 kg·cm, metal gears | 2 |
| Pan-tilt bracket | 2-axis mount | 1 |
| Buzzer (5V active) | 400–1500 Hz | 1 |
| 5V DC power supply | 4–5 A output | 1 |
| IR LED ring (optional) | 850 nm, for low-light | 1 |
| Jumper wires | M-F / M-M assorted | 1 |

### 3D-Printed Parts

Pan/tilt bracket STL files are included in [`model/`](model/) — sourced from [Super Ultra Compact Pan-Tilt Camera Mount v1](https://cults3d.com/en/3d-model/gadget/super-ultra-compact-pan-tilt-camera-mount-v1) by ZalophusDokdo.

---

## GPIO Pin Assignments

| Pin (Board) | BCM GPIO | Function |
|:---:|:---:|---|
| 32 | GPIO12 (PWM0) | Pan servo signal |
| 33 | GPIO13 (PWM1) | Tilt servo signal |
| 11 | GPIO17 | Buzzer control |
| 31 | GPIO6 | IR LED control |
| 37 | GPIO26 | Vibration motor |
| 2, 4 | 5V | External power |
| 6 | GND | Common ground |

> **Important:** Use a separate 5V supply for servos. Connect grounds together (common ground). Do not draw servo power from the Pi's 5V pins.

---

## Installation

### On Raspberry Pi

```bash
# Clone the repo
git clone https://github.com/qppd/s.a.f.e.git
cd s.a.f.e

# Install Python dependencies
pip install -r requirements.txt

# Install hardware drivers
sudo apt update
sudo apt install pigpio

# Start pigpio daemon (needed for servo PWM)
sudo pigpiod
```

### On Windows / macOS (for testing)

```bash
git clone https://github.com/qppd/s.a.f.e.git
cd s.a.f.e
pip install -r requirements.txt
```

---

## Usage

### Detection mode

```bash
# Raspberry Pi (auto-detects CSI camera)
python -m src.safe.main

# Windows/macOS (USB webcam)
python -m src.safe.main --camera 0

# Headless mode (no display, terminal output)
python -m src.safe.main --headless
```

### Calibration mode

Run calibration first to tune EAR thresholds for your face:

```bash
python -m src.safe.main --calibrate --camera 0
```

Calibration controls:
| Key | Action |
|---|---|
| `O` | Mark frame as eyes open |
| `C` | Mark frame as eyes closed |
| `S` | Save & compute thresholds |
| `Q` | Abort |
| `L` | Toggle EAR bar graph |

### CLI Options

| Flag | Description | Default |
|---|---|---|
| `--camera N` | Webcam index | `0` |
| `--calibrate` | Run calibration instead of detection | `False` |
| `--headless` | No display, terminal output only | `False` |
| `--samples N` | Samples per class in calibration | `30` |
| `--width N` | Camera width | `640` |
| `--height N` | Camera height | `480` |

---

## Configuration

All thresholds and settings are in [`src/safe/config.py`](src/safe/config.py):

| Parameter | Default | Description |
|---|---|---|
| `ear_threshold` | `0.20` | Below this EAR → eyes closed |
| `closed_frame_threshold` | `45` | Consecutive frames to flag drowsy (~1.5s at 30fps) |
| `perclos_threshold` | `0.20` | PERCLOS % above which → drowsy |
| `perclos_window_seconds` | `60.0` | Sliding window for PERCLOS |
| `alarm_cooldown_seconds` | `5.0` | Minimum time between alarms |
| `pan_kp` / `tilt_kp` | `0.008` | Servo proportional gain |
| `pan_tilt_deadband` | `30` | Pixels from centre before servo moves |

---

## Project Structure

```
s.a.f.e/
├── src/safe/
│   ├── __init__.py
│   ├── main.py              # Entry point & main loop
│   ├── config.py            # All thresholds & GPIO pins
│   ├── camera.py            # Pi Camera v2 / USB webcam
│   ├── face_tracker.py      # MediaPipe FaceLandmarker
│   ├── eye_tracker.py       # EAR + PERCLOS computation
│   ├── pan_tilt.py          # Servo control (pigpio PWM)
│   ├── drowsiness.py        # Decision logic
│   ├── alarm.py             # Buzzer / system beep
│   └── calibration.py       # Interactive threshold calibration
├── tests/
│   ├── test_eye_tracker.py  # 23 tests for EAR & PERCLOS
│   └── test_calibration.py  # 10 tests for calibration
├── model/                   # 3D-printable STL files
├── models/                  # MediaPipe model (auto-downloaded)
├── logs/                    # Runtime logs (auto-created)
├── requirements.txt
└── initial-plan.txt         # Full project plan & design doc
```

---

## How It Works

1. **Camera** captures frames at 30 FPS
2. **FaceTracker** detects the face and extracts 478 landmarks using MediaPipe
3. **EyeTracker** computes EAR from 6 eye landmarks per eye
4. **DrowsinessDetector** checks if PERCLOS exceeds threshold
5. **PanTilt** adjusts servos to keep face centred
6. **Alarm** triggers buzzer/beep when drowsiness is detected

### Algorithm

**Eye Aspect Ratio (EAR):**

```
EAR = (||p2-p6|| + ||p3-p5||) / (2 × ||p1-p4||)
```

Where p1–p6 are the 6 key eye landmark points. EAR drops toward 0 when eyes close.

**PERCLOS:** Percentage of frames in a 60-second window where EAR < threshold.

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_eye_tracker.py -v
```

---

## Wiring Diagram

```
                Raspberry Pi
              ┌──────────────┐
   Camera ────┤ CSI Port     │
              │              │
   Servo 1 ───┤ GPIO12 (Pin32)│──── Pan servo (signal)
   Servo 2 ───┤ GPIO13 (Pin33)│──── Tilt servo (signal)
              │              │
   Buzzer ────┤ GPIO17 (Pin11)│──── Buzzer (+)
   IR LED ────┤ GPIO6  (Pin31)│──── MOSFET gate
              │              │
   GND ───────┤ GND (Pin6)  │──── Common ground
   5V ────────┤ 5V (Pin2)   │──── External PSU (+)
              └──────────────┘
                     │
            ┌────────┴────────┐
            │  External 5V/4A │
            │  Power Supply   │
            └─────────────────┘
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker) for face mesh detection
- [Super Ultra Compact Pan-Tilt Mount](https://cults3d.com/en/3d-model/gadget/super-ultra-compact-pan-tilt-camera-mount-v1) by ZalophusDokdo for 3D-printed bracket
- [Raspberry Pi Camera v2](https://www.raspberrypi.com/products/camera-module-v2/) documentation
- EAR formula from [Soukupová & Čech (2016)](http://www.telecom.lille.fr/~yanovski/VM/2016/resources/report.pdf)
