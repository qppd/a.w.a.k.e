"""A.W.A.K.E. 2.0 — Tilt Servo Back-and-Forth Test (±45°)

Hardware pin assignment (BCM mode):
  Tilt → GPIO 13  (Pin 33)  — Software PWM via RPi.GPIO

Servo initialise at 90° (midpoint of 0–180° range), then sweep
±45° from that position (45° → 135° → 45°), repeating until
Ctrl+C is pressed.

Usage:
  python test/servo_tilt_test.py                # default: 90° start, 5° step, 0.05s delay
  python test/servo_tilt_test.py --start 0      # start at 0°
  python test/servo_tilt_test.py --step 1       # 1° steps (smoother)
  python test/servo_tilt_test.py --delay 0.1    # slower sweep
  python test/servo_tilt_test.py --cycles 3     # stop after 3 back-and-forths
"""
from __future__ import annotations

import argparse
import sys
import time

# ── Pin assignment (BCM) — must match src/awake/config.py ───
TILT_GPIO = 13   # CFG.servo_tilt_gpio

# ── PWM spec — must match src/awake/config.py ──────────────
PWM_FREQ_HZ  = 50       # 50 Hz standard servo
PULSE_MIN_US = 500      # CFG.servo_min_pulse_us  (0°)
PULSE_MAX_US = 2500     # CFG.servo_max_pulse_us  (180°)
PWM_PERIOD_US = 1_000_000 // PWM_FREQ_HZ   # 20 000 µs at 50 Hz

# ── Physical servo range ────────────────────────────────────
SERVO_MIN_DEG = 0.0     # physical 0°
SERVO_MAX_DEG = 180.0   # physical 180°

# ── Test sweep ──────────────────────────────────────────────
SWEEP_DEG = 45.0        # sweep ±45° from start position
DEFAULT_START = 90.0    # centre / initial position

# ── RPi.GPIO fallback ──────────────────────────────────────
_pwm = None

try:
    import RPi.GPIO as gpio
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False


# ── Helpers ─────────────────────────────────────────────────

def _angle_to_duty(angle: float) -> float:
    """Convert physical servo angle (0–180°) → PWM duty cycle (%)."""
    clamped = _clamp(angle, SERVO_MIN_DEG, SERVO_MAX_DEG)
    norm = (clamped - SERVO_MIN_DEG) / (SERVO_MAX_DEG - SERVO_MIN_DEG)
    pulse_us = PULSE_MIN_US + norm * (PULSE_MAX_US - PULSE_MIN_US)
    return pulse_us / PWM_PERIOD_US * 100.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def setup() -> None:
    """Initialise RPi.GPIO and start software PWM on tilt servo pin."""
    global _pwm
    if not _HAS_GPIO:
        print("[WARN] RPi.GPIO not available — running in simulation mode")
        return
    gpio.setmode(gpio.BCM)
    gpio.setup(TILT_GPIO, gpio.OUT, initial=gpio.LOW)
    _pwm = gpio.PWM(TILT_GPIO, PWM_FREQ_HZ)
    _pwm.start(0.0)
    print(f"[OK] Software PWM {PWM_FREQ_HZ} Hz on GPIO {TILT_GPIO} (tilt)")


def drive(angle: float) -> None:
    """Drive the tilt servo to the given physical angle."""
    global _pwm
    clamped = _clamp(angle, SERVO_MIN_DEG, SERVO_MAX_DEG)
    duty = _angle_to_duty(clamped)
    pulse = int(clamped / SERVO_MAX_DEG * (PULSE_MAX_US - PULSE_MIN_US) + PULSE_MIN_US)
    if _HAS_GPIO and _pwm is not None:
        _pwm.ChangeDutyCycle(duty)
    print(f"  [TILT] GPIO {TILT_GPIO}  {clamped:.1f}°  {pulse}µs", end="\r")
    return clamped, pulse


def cleanup() -> None:
    """Stop PWM and release GPIO."""
    global _pwm
    if _pwm is not None:
        _pwm.stop()
        _pwm = None
    if _HAS_GPIO:
        gpio.output(TILT_GPIO, gpio.LOW)
        gpio.cleanup(TILT_GPIO)
    print(f"\n[OK] GPIO {TILT_GPIO} released")


# ── Main sweep ──────────────────────────────────────────────

def sweep_back_forth(step: float, delay: float, cycles: int | None, start_angle: float) -> None:
    """
    Sweep ±45° back and forth from start_angle.

    Sequence:  start → start+45 → start-45 → start → start+45 → …
    """
    lo = _clamp(start_angle - SWEEP_DEG, SERVO_MIN_DEG, SERVO_MAX_DEG)
    hi = _clamp(start_angle + SWEEP_DEG, SERVO_MIN_DEG, SERVO_MAX_DEG)

    print(f"\n=== Tilt Sweep (±{SWEEP_DEG}° from {start_angle}°) ===")
    print(f"    range: {lo}° — {hi}°")
    print(f"    step={step}°  delay={delay}s  cycles={'∞' if cycles is None else cycles}")
    print(f"    Press Ctrl+C to stop\n")

    up   = list(_frange(start_angle, hi, step))
    down = list(_frange(hi, lo, -step))
    back = list(_frange(lo, start_angle, step))

    if not up or abs(up[-1] - hi) > 1e-9:
        up.append(round(hi, 1))
    if not down or abs(down[-1] - lo) > 1e-9:
        down.append(round(lo, 1))
    if not back or abs(back[-1] - start_angle) > 1e-9:
        back.append(round(start_angle, 1))

    cycle_count = 0
    try:
        while True:
            for angle in up:
                drive(angle)
                time.sleep(delay)
            for angle in down:
                drive(angle)
                time.sleep(delay)
            for angle in back:
                drive(angle)
                time.sleep(delay)

            cycle_count += 1
            print(f"  cycle {cycle_count} complete")

            if cycles is not None and cycle_count >= cycles:
                break

    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")

    drive(start_angle)
    time.sleep(0.3)
    print(f"\n=== Done — {cycle_count} cycle(s) — stopped at {start_angle}° ===")


def _frange(start: float, stop: float, step: float):
    """Float range — yields from start toward stop."""
    val = start
    if step > 0:
        while val < stop + 1e-9:
            yield round(val, 1)
            val += step
    else:
        while val > stop - 1e-9:
            yield round(val, 1)
            val += step


# ── CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="A.W.A.K.E. Tilt Servo ±45° test")
    parser.add_argument("--start",  type=float, default=DEFAULT_START,
                        help=f"Initial position in degrees (default: {DEFAULT_START})")
    parser.add_argument("--step",   type=float, default=5.0,
                        help="Step size in degrees (default: 5)")
    parser.add_argument("--delay",  type=float, default=0.05,
                        help="Delay between steps in seconds (default: 0.05)")
    parser.add_argument("--cycles", type=int, default=None,
                        help="Number of back-and-forth cycles (∞ if omitted)")

    args = parser.parse_args()
    setup()

    try:
        drive(args.start)
        time.sleep(0.5)
        print(f"\n  Initialised to {args.start}° — starting sweep …")
        sweep_back_forth(args.step, args.delay, args.cycles, args.start)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
