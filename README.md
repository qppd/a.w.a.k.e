# A.W.A.K.E. 2.0

System for Alerting Fatigued Eyes

A Raspberry Pi-based drowsiness detection system that uses real-time eye tracking, a motorised pan/tilt camera mount, and an audible alarm to alert drivers showing signs of fatigue.

**Python 3.11+** | **License: MIT** | **Tests: 33 passing**

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
- [GPIO Pin Assignments](#gpio-pin-assignments)
- [Installation](#installation)
- [Usage](#usage)
- [CLI Options](#cli-options)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Testing](#testing)
- [Wiring Diagram](#wiring-diagram)
- [Author](#author)
- [License](#license)
- [Third-Party Licenses](#third-party-licenses)
- [Acknowledgements](#acknowledgements)

---

## Overview

A.W.A.K.E. 2.0 continuously monitors a driver's face and eyes using a camera mounted on a motorised pan/tilt bracket. The system computes two key metrics in real time:

- **Eye Aspect Ratio (EAR)** -- a geometric measure of eye openness derived from facial landmarks.
- **PERCLOS** -- the percentage of time the eyes are mostly closed over a sliding window.

When either metric exceeds its calibrated threshold for a sustained duration, the system triggers an audible alarm to alert the driver. The pan/tilt servos automatically track the driver's head to keep the face centred in the camera frame.

The system is designed for the Raspberry Pi 5 (or 4) with a Pi Camera v2, but also runs on Windows and macOS using a standard USB webcam for development and testing.

---

## Features

- Real-time face and eye tracking using MediaPipe FaceLandmarker (478 facial landmarks).
- EAR and PERCLOS computation with configurable thresholds.
- Motorised pan/tilt control using hardware PWM (pigpio) to track the driver's head.
- Interactive calibration mode for per-user EAR threshold tuning.
- Headless mode for running on a Raspberry Pi without a monitor (SSH).
- Cross-platform: Raspberry Pi (CSI camera) and Windows/macOS (USB webcam).
- Audio alarm with platform-native fallback (GPIO buzzer on Pi, system beep on desktop).
- Timestamped CSV logging of all detection data.
- 33 unit tests covering the EAR algorithm, PERCLOS computation, and calibration logic.

---

## Hardware Requirements

| Component | Specification | Quantity |
|---|---|---|
| Raspberry Pi 4 (4 GB) | 4 GB RAM | 1 |
| Raspberry Pi Camera v2 | 8 MP, IMX219 sensor, CSI-2 connector | 1 |
| Servo motor (MG90S) | 1.8 kg-cm stall torque, metal gears, 4.8V | 2 |
| Pan-tilt bracket | 2-axis mount for SG90/MG90 servos | 1 |
| Active buzzer | 5V, 400-1500 Hz | 1 |
| 5V DC power supply | 4-5A output, regulated | 1 |
| IR LED ring (optional) | 850 nm wavelength, for low-light operation | 1 |
| Jumper wires | Male-to-female and male-to-male, assorted | 1 pack |

### 3D-Printed Parts

STL files for the pan/tilt bracket are included in the `model/` directory. The design is sourced from the [Super Ultra Compact Pan-Tilt Camera Mount v1](https://cults3d.com/en/3d-model/gadget/super-ultra-compact-pan-tilt-camera-mount-v1) by ZalophusDokdo. Print settings: PLA or PETG, 0.2mm layer height, 20-30% infill.

---

## GPIO Pin Assignments

| Board Pin | BCM GPIO | Function |
|:---:|:---:|---|
| 32 | GPIO12 (PWM0) | Pan servo signal |
| 33 | GPIO13 (PWM1) | Tilt servo signal |
| 11 | GPIO17 | Buzzer control |
| 31 | GPIO6 | IR LED control |
| 37 | GPIO26 | Vibration motor |
| 2, 4 | 5V | External power input |
| 6 | GND | Common ground |

**Important:** Use a separate 5V power supply for the servos. Connect all grounds together (common ground). Do not draw servo current from the Raspberry Pi's 5V pins, as this can damage the board.

---

## Installation

### Raspberry Pi

```bash
git clone https://github.com/qppd/a.w.a.k.e.git
cd a.w.a.k.e
pip install -r requirements.txt
sudo apt update && sudo apt install pigpio
sudo pigpiod
```

### Windows / macOS (Development)

```bash
git clone https://github.com/qppd/a.w.a.k.e.git
cd a.w.a.k.e
pip install -r requirements.txt
```

### Dependencies

The following Python packages are required (listed in `requirements.txt`):

- `opencv-python` (4.8+) -- image capture and processing
- `mediapipe` (1.0+) -- face landmark detection
- `numpy` (1.24+) -- numerical computation

On Raspberry Pi, the following system packages are also needed:

- `pigpio` -- hardware PWM servo control (install via apt)
- `picamera2` -- CSI camera support (pre-installed on Raspberry Pi OS)

---

## Usage

### Detection Mode

```bash
# Raspberry Pi (auto-detects CSI camera)
python -m src.awake.main

# Windows/macOS (specify webcam index)
python -m src.awake.main --camera 0

# Headless mode (terminal output, no display window)
python -m src.awake.main --headless
```

### Calibration Mode

Run calibration first to determine optimal EAR thresholds for your face. The system will record samples of your open and closed eyes, then suggest threshold values.

```bash
python -m src.awake.main --calibrate --camera 0
```

During calibration, use the following keys:

| Key | Action |
|---|---|
| O | Mark the current frame as "eyes open" |
| C | Mark the current frame as "eyes closed" |
| S | Save samples and compute thresholds |
| Q | Abort calibration without saving |
| L | Toggle the EAR bar graph display |

---

## CLI Options

| Flag | Description | Default |
|---|---|---|
| `--camera N` | Webcam device index | `0` |
| `--calibrate` | Run calibration instead of detection | `False` |
| `--headless` | Disable display window; output to terminal only | `False` |
| `--samples N` | Number of samples per class during calibration | `30` |
| `--width N` | Camera capture width in pixels | `640` |
| `--height N` | Camera capture height in pixels | `480` |

---

## Configuration

All thresholds and system parameters are defined in `src/awake/config.py`:

| Parameter | Default | Description |
|---|---|---|
| `ear_threshold` | `0.20` | EAR value below which eyes are considered closed |
| `closed_frame_threshold` | `45` | Consecutive closed frames required to trigger drowsiness (approximately 1.5 seconds at 30 FPS) |
| `perclos_threshold` | `0.20` | PERCLOS percentage above which the driver is considered drowsy |
| `perclos_window_seconds` | `60.0` | Duration of the PERCLOS sliding window in seconds |
| `alarm_cooldown_seconds` | `5.0` | Minimum interval between successive alarms |
| `pan_kp` / `tilt_kp` | `0.008` | Proportional gain for pan and tilt servo control |
| `pan_tilt_deadband` | `30` | Pixel offset from frame centre before servo correction is applied |
| `camera_width` / `camera_height` | `640` / `480` | Camera capture resolution |
| `camera_fps` | `30` | Target frame rate |

---

## Project Structure

```
a.w.a.k.e/
├── src/awake/
│   ├── __init__.py
│   ├── main.py              # Entry point and main detection loop
│   ├── config.py            # System configuration and thresholds
│   ├── camera.py            # Camera capture (Pi Camera v2 / USB webcam)
│   ├── face_tracker.py      # Face detection via MediaPipe FaceLandmarker
│   ├── eye_tracker.py       # EAR and PERCLOS computation
│   ├── pan_tilt.py          # Servo control via pigpio hardware PWM
│   ├── drowsiness.py        # Drowsiness decision logic
│   ├── alarm.py             # Buzzer and system beep control
│   └── calibration.py       # Interactive threshold calibration
├── tests/
│   ├── test_eye_tracker.py  # 23 tests for EAR algorithm and PERCLOS
│   └── test_calibration.py  # 10 tests for calibration threshold computation
├── model/                   # 3D-printable STL files for pan/tilt bracket
├── models/                  # MediaPipe model (auto-downloaded on first run)
├── logs/                    # Runtime logs (auto-created)
├── requirements.txt         # Python dependencies
├── initial-plan.txt         # Full project design document
└── README.md
```

---

## How It Works

1. The camera captures frames at 30 FPS.
2. MediaPipe FaceLandmarker detects the face and extracts 478 facial landmarks.
3. Six key landmarks per eye are used to compute the Eye Aspect Ratio (EAR).
4. EAR is averaged across both eyes. A PERCLOS score is maintained over a 60-second sliding window.
5. If PERCLOS exceeds the configured threshold, the system flags the driver as drowsy.
6. The pan/tilt servos adjust automatically to keep the face centred in the frame.
7. An audible alarm is triggered when drowsiness is detected.

### Eye Aspect Ratio Formula

```
EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)
```

Where p1 through p6 are the six landmark points defining the eye boundary. When the eye is open, EAR is typically between 0.25 and 0.40. When the eye closes, EAR drops below 0.20.

### PERCLOS

PERCLOS is the percentage of frames within the sliding window where the EAR falls below the configured threshold. A PERCLOS value above 0.20 (20%) indicates sustained eye closure and triggers the alarm.

---

## Testing

```bash
python -m pytest tests/ -v
```

The test suite includes 33 tests covering:

- Euclidean distance computation
- EAR calculation with synthetic eye landmarks (open, closed, symmetric, edge cases)
- PERCLOS sliding window computation and expiry
- Calibration threshold computation (cluster separation, clamping, variance handling)
- Frame size scaling behaviour
- State reset and consecutive frame counting

---

## Wiring Diagram

```
              Raspberry Pi
            +--------------+
 Camera ----| CSI Port     |
            |              |
 Servo 1 ---| GPIO12 (Pin32)|---- Pan servo (signal)
 Servo 2 ---| GPIO13 (Pin33)|---- Tilt servo (signal)
            |              |
 Buzzer ----| GPIO17 (Pin11)|---- Buzzer (+)
 IR LED ----| GPIO6  (Pin31)|---- MOSFET gate
            |              |
 GND -------| GND (Pin6)  |---- Common ground
 5V --------| 5V (Pin2)   |---- External PSU (+)
            +--------------+
                   |
          +--------+--------+
          |  External 5V/4A  |
          |  Power Supply    |
          +-----------------+
```

---

## Author

**qppd**
GitHub: https://github.com/qppd

---

## License

This project is licensed under the MIT License.

```
MIT License

Copyright (c) 2026 qppd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Third-Party Licenses

This project uses the following third-party libraries and assets:

### MediaPipe (Apache License 2.0)

Face landmark detection is performed using Google's MediaPipe FaceLandmarker model. MediaPipe is licensed under the Apache License, Version 2.0.

    Copyright 2023 Google LLC.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

### OpenCV (Apache License 2.0)

Image capture and processing uses OpenCV. OpenCV is licensed under the Apache License, Version 2.0.

    Copyright (C) 2000-2024, Intel Corporation, all rights reserved.
    Copyright (C) 2009-2011, Willow Garage Inc., all rights reserved.
    Copyright (C) 2009-2016, NVIDIA Corporation, all rights reserved.
    Copyright (C) 2010-2013, Advanced Micro Devices, Inc., all rights reserved.
    Copyright (C) 2015-2016, OpenCV Foundation, all rights reserved.
    Copyright (C) 2015-2016, Itseez Inc., all rights reserved.

    Licensed under the Apache License, Version 2.0.

### NumPy (BSD License)

Numerical computation uses NumPy. NumPy is licensed under the BSD License.

    Copyright (c) 2005-2024, NumPy Developers.
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
       this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright notice,
       this list of conditions and the following disclaimer in the documentation
       and/or other materials provided with the distribution.

    3. Neither the name of the copyright holder nor the names of its
       contributors may be used to endorse or promote products derived from
       this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
    LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
    CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.

### pigpio (Unlicense / zlib License)

Servo PWM control uses pigpio. pigpio is released under a combination of the Unlicense and the zlib License.

    Copyright (c) 2013-2024, gpio Admin (gpio@admin.com)
    All rights reserved.

    This software is released under the terms of the Unlicense
    (http://unlicense.org) and the zlib License
    (https://www.zlib.net/zlib_license.html).

### 3D Model: Super Ultra Compact Pan-Tilt Camera Mount v1

STL files in the `model/` directory are sourced from Cults3D user ZalophusDokdo.
Designer: ZalophusDokdo
Source: https://cults3d.com/en/3d-model/gadget/super-ultra-compact-pan-tilt-camera-mount-v1

---

## Acknowledgements

- Google MediaPipe team for the FaceLandmarker model and Tasks API.
- ZalophusDokdo for the pan/tilt bracket 3D model.
- Raspberry Pi Foundation for camera and GPIO documentation.
- Terek Soukupova and Jiri Cech for the Eye Aspect Ratio formula, as described in "Real-Time Detection of Driver Drowsiness using Machine Learning" (2016).
