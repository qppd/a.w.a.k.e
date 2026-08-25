# Contributing to A.W.A.K.E. 2.0

Thank you for your interest in contributing to A.W.A.K.E. 2.0. This document outlines the guidelines for contributing to this project.

---

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/a.w.a.k.e.git
   cd a.w.a.k.e
   ```
3. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   pip install pytest
   ```
4. Create a new branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

---

## Development Setup

### Running Tests

```bash
python -m pytest tests/ -v
```

All 33 existing tests must pass before submitting a pull request.

### Running the Application

```bash
# With display
python -m src.awake.main --camera 0

# Headless
python -m src.awake.main --headless --camera 0

# Calibration
python -m src.awake.main --calibrate --camera 0
```

---

## Code Style

- Follow PEP 8 for Python code formatting.
- Use type hints for all function signatures.
- Keep functions focused and short.
- Use meaningful variable and function names.
- Remove unused imports.
- Do not add comments unless the logic is non-obvious.

---

## Project Structure

When adding new functionality, follow the existing module structure:

| Module | Responsibility |
|---|---|
| `config.py` | All configurable parameters |
| `camera.py` | Camera abstraction (CSI / USB) |
| `face_tracker.py` | Face detection and landmarks |
| `eye_tracker.py` | EAR and PERCLOS computation |
| `pan_tilt.py` | Servo control |
| `drowsiness.py` | Decision logic |
| `alarm.py` | Alert output (buzzer / beep) |
| `calibration.py` | Interactive threshold calibration |
| `main.py` | Entry point and orchestration |

New modules should be placed in `src/awake/` and follow the same single-responsibility pattern.

---

## Making Changes

1. Keep changes focused. One pull request per feature or fix.
2. Write or update tests for any new functionality.
3. Ensure all tests pass before committing.
4. Update `README.md` if your change affects usage, configuration, or hardware wiring.
5. Write clear commit messages describing what changed and why.

---

## Submitting a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
2. Open a pull request against the `main` branch on the original repository.
3. Provide a clear description of:
   - What the change does
   - Why the change is needed
   - How it was tested
4. Reference any related issues if applicable.

---

## Reporting Issues

When reporting a bug, include:

- Steps to reproduce the issue
- Expected behaviour
- Actual behaviour
- Python version and operating system
- Hardware details (Raspberry Pi model, camera type)
- Relevant log output

---

## Areas for Contribution

- Additional alarm types (vibration, visual, network notifications).
- Yawning detection.
- Improved pan/tilt PID controller tuning.
- Support for multiple faces / passengers.
- Data recording and playback for offline testing.
- Performance optimisation for lower-end hardware.
- Documentation improvements.
