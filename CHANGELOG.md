# Changelog

All notable changes to S.A.F.E. 2.0 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.0] - 2026-08-24

Initial release of S.A.F.E. 2.0.

### Added

**Core Detection System**
- Camera module supporting Raspberry Pi Camera v2 (picamera2/CSI) and USB webcam (OpenCV).
- Face tracking using MediaPipe FaceLandmarker (Tasks API v1.0+) with 478 facial landmarks.
- Eye Aspect Ratio (EAR) computation from six landmark points per eye.
- PERCLOS computation over a configurable 60-second sliding window.
- Drowsiness decision logic combining EAR temporal filtering and PERCLOS thresholds.

**Hardware Control**
- Pan/tilt servo control via pigpio hardware PWM on GPIO 12 and GPIO 13.
- Proportional control with configurable gain and deadband.
- Search mode with oscillating sweep when no face is detected.
- Alarm module with GPIO buzzer support (RPi.GPIO) and system beep fallback (winsound on Windows, terminal bell on Linux).

**Calibration**
- Interactive calibration mode for per-user EAR threshold tuning.
- Real-time EAR display with scrolling bar graph and threshold line.
- Keyboard-driven sample collection (open/closed eye marking).
- Automatic threshold suggestion using cluster midpoint with 2-sigma safety margin.
- CSV export of calibration samples for offline analysis.

**Interface**
- Headless mode for operation without a display (SSH, Pi without monitor).
- Terminal-based live status output in headless mode (EAR, PERCLOS, FPS, status).
- CLI with arguments for camera index, resolution, calibration, and headless mode.
- Timestamped CSV logging of all detection data (EAR, PERCLOS, drowsiness state).

**Configuration**
- Centralised configuration in `config.py` using Python dataclass.
- Configurable GPIO pin assignments, servo limits, EAR/PERCLOS thresholds, and alarm parameters.

**Hardware Design**
- GPIO pin assignment table for Raspberry Pi 4/5.
- 3D-printable pan/tilt bracket STL files (Super Ultra Compact Pan-Tilt Mount v1 by ZalophusDokdo).
- External 5V power supply wiring scheme with common ground.

**Testing**
- 33 unit tests covering:
  - Euclidean distance computation.
  - EAR algorithm with synthetic eye landmarks (open, closed, symmetric, zero-width, scale-invariant).
  - PERCLOS sliding window computation and time-based expiry.
  - Calibration threshold computation (cluster separation, edge detection, clamping, variance handling).
  - Frame size scaling and aspect ratio behaviour.
  - State reset and consecutive frame counting.

**Documentation**
- README with project overview, hardware BOM, GPIO pinout, installation, usage, configuration, project structure, algorithm explanation, wiring diagram, and license information.
- MIT License (standalone file).
- Third-party license notices (MediaPipe Apache 2.0, OpenCV Apache 2.0, NumPy BSD, pigpio Unlicense/zlib).
- Contributing guidelines (CONTRIBUTING.md).
- Project design document (initial-plan.txt).

### Known Limitations

- Camera v2 is a standard visible-light sensor; IR LED ring has limited effectiveness in total darkness.
- No yawning detection.
- Single-face tracking only.
- Pan/tilt uses proportional control without derivative or integral terms (no PID).
- No network or remote alert capability.
