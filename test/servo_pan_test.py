"""A.W.A.K.E. 2.0 — Pan Servo Continuous Rotation Test (360° MG90S)

Hardware pin assignment (BCM mode):
  Pan → GPIO 12  (Pin 32)  — Software PWM via RPi.GPIO

The pan servo is a 360° continuous rotation servo. PWM pulse width
controls speed and direction, NOT angle:

  500 µs  → full speed one way
  1500 µs → stop (centre / neutral)
  2500 µs → full speed other way

Usage:
  python test/servo_pan_test.py                  # sweep forward & reverse
  python test/servo_pan_test.py --speed 7        # faster sweep
  python test/servo_pan_test.py --duration 3     # 3 seconds each direction
  python test/servo_pan_test.py --forward         # forward only
  python test/servo_pan_test.py --reverse         # reverse only
  python test/servo_pan_test.py --stop            # stop immediately
  python test/servo_pan_test.py --pin 18          # use a different GPIO pin
  python test/servo_pan_test.py --diagnostic      # verbose PWM output check
"""
from __future__ import annotations

import argparse
import sys
import time

# ── Pin assignment (BCM) — must match src/awake/config.py ───
PAN_GPIO = 12   # CFG.servo_pan_gpio

# ── PWM spec — must match src/awake/config.py ──────────────
PWM_FREQ_HZ  = 50       # 50 Hz standard servo
PULSE_MIN_US = 500      # full speed one way
PULSE_MAX_US = 2500     # full speed other way
NEUTRAL_US   = 1500     # stop / neutral
PWM_PERIOD_US = 1_000_000 // PWM_FREQ_HZ   # 20 000 µs at 50 Hz

# ── RPi.GPIO fallback ──────────────────────────────────────
_pwm = None
try:
    import RPi.GPIO as gpio
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False


# ── Helpers ─────────────────────────────────────────────────

def _pulse_to_duty(pulse_us: float) -> float:
    """Convert pulse width in µs → PWM duty cycle (%)."""
    return pulse_us / PWM_PERIOD_US * 100.0


def _speed_to_pulse(speed: float) -> float:
    """Convert speed (0–10) to pulse width in µs.

    speed  0      = neutral (stop)     → 1500 µs
    speed  1–5    = forward (one way)  → 1300 down to 500
    speed  6–10   = reverse (other way)→ 1700 up to 2500
    """
    if speed == 0:
        return float(NEUTRAL_US)
    if 1 <= speed <= 5:
        norm = (speed - 1) / 4.0
        return 1300.0 - norm * 800.0
    else:
        norm = (speed - 6) / 4.0
        return 1700.0 + norm * 800.0


def setup(pin: int) -> None:
    """Initialise RPi.GPIO and start software PWM on pan servo pin."""
    global _pwm
    if not _HAS_GPIO:
        print("[WARN] RPi.GPIO not available — running in simulation mode")
        return
    gpio.setmode(gpio.BCM)
    gpio.setup(pin, gpio.OUT, initial=gpio.LOW)
    _pwm = gpio.PWM(pin, PWM_FREQ_HZ)
    _pwm.start(_pulse_to_duty(NEUTRAL_US))
    print(f"[OK] Software PWM {PWM_FREQ_HZ} Hz on GPIO {pin} (pan — continuous rotation)")


def drive_speed(speed: float, pin: int) -> None:
    """Drive the pan servo at the given speed (0=stop, 1–5=forward, 6–10=reverse)."""
    global _pwm
    pulse = _speed_to_pulse(speed)
    duty = _pulse_to_duty(pulse)
    if _HAS_GPIO and _pwm is not None:
        _pwm.ChangeDutyCycle(duty)

    if speed == 0:
        label = "STOP"
    elif speed <= 5:
        label = "FWD"
    else:
        label = "REV"
    print(f"  [PAN] GPIO {pin}  {label}  speed={speed:.1f}  pulse={pulse:.0f}µs  duty={duty:.2f}%", end="\r")


def stop(pin: int) -> None:
    """Stop the pan servo (neutral pulse)."""
    drive_speed(0, pin)
    print()


def cleanup(pin: int) -> None:
    """Stop PWM and release GPIO."""
    global _pwm
    if _pwm is not None:
        _pwm.ChangeDutyCycle(_pulse_to_duty(NEUTRAL_US))
        time.sleep(0.1)
        _pwm.stop()
        _pwm = None
    if _HAS_GPIO:
        gpio.output(pin, gpio.LOW)
        gpio.cleanup(pin)
    print(f"\n[OK] GPIO {pin} released")


def diagnostic(pin: int) -> None:
    """Print detailed PWM info and cycle through speeds to verify output."""
    print(f"\n=== Diagnostic — GPIO {pin} ===\n")

    speeds = [0, 3, 5, 7, 10, 0]
    for s in speeds:
        pulse = _speed_to_pulse(s)
        duty = _pulse_to_duty(pulse)
        drive_speed(s, pin)
        print(f"\n  speed={s:.1f}  pulse={pulse:.0f}µs  duty={duty:.2f}%")
        if s != 0:
            print(f"  → Servo should {'rotate one way' if s <= 5 else 'rotate other way'}")
        else:
            print(f"  → Servo should STOP")
        time.sleep(2)
        stop(pin)

    print(f"\n=== Diagnostic complete ===")
    print(f"If servo didn't rotate:")
    print(f"  1. Check wiring — signal wire to GPIO {pin}")
    print(f"  2. Check power — servo needs stable 5V supply")
    print(f"  3. GPIO conflict — try --pin 23 (non-HW PWM pin)")


# ── Tests ───────────────────────────────────────────────────

def sweep_forward_reverse(speed: float, duration: float, cycles: int | None, pin: int) -> None:
    """Sweep forward then reverse, repeating for N cycles."""
    print(f"\n=== Pan Continuous Rotation — speed {speed}, {duration}s each direction ===")
    print(f"    cycles={'∞' if cycles is None else cycles}")
    print(f"    Press Ctrl+C to stop\n")

    cycle_count = 0
    try:
        while True:
            print(f"  >> Forward  (speed {speed})")
            drive_speed(speed, pin)
            time.sleep(duration)

            stop(pin)

            print(f"  >> Reverse  (speed {speed})")
            drive_speed(11 - speed, pin)
            time.sleep(duration)

            stop(pin)

            cycle_count += 1
            print(f"  cycle {cycle_count} complete\n")

            if cycles is not None and cycle_count >= cycles:
                break

    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")

    stop(pin)
    print(f"\n=== Done — {cycle_count} cycle(s) ===")


def run_forward(speed: float, duration: float, pin: int) -> None:
    """Run forward only."""
    print(f"\n=== Forward — speed {speed}, {duration}s ===")
    drive_speed(speed, pin)
    time.sleep(duration)
    stop(pin)


def run_reverse(speed: float, duration: float, pin: int) -> None:
    """Run reverse only."""
    print(f"\n=== Reverse — speed {speed}, {duration}s ===")
    drive_speed(11 - speed, pin)
    time.sleep(duration)
    stop(pin)


# ── CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="A.W.A.K.E. Pan Servo — Continuous Rotation Test (360° MG90S)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--forward", action="store_true",
                       help="Run forward only")
    group.add_argument("--reverse", action="store_true",
                       help="Run reverse only")
    group.add_argument("--stop",    action="store_true",
                       help="Stop the servo immediately")
    group.add_argument("--diagnostic", action="store_true",
                       help="Run diagnostic — cycle speeds and print PWM info")
    parser.add_argument("--speed",    type=float, default=5.0,
                        help="Speed 1–10 (default: 5)")
    parser.add_argument("--duration", type=float, default=3.0,
                        help="Duration in seconds each direction (default: 3)")
    parser.add_argument("--cycles",   type=int, default=None,
                        help="Number of back-and-forth cycles (∞ if omitted)")
    parser.add_argument("--pin",      type=int, default=PAN_GPIO,
                        help=f"GPIO pin BCM (default: {PAN_GPIO})")

    args = parser.parse_args()
    pin = args.pin

    setup(pin)

    try:
        if args.diagnostic:
            diagnostic(pin)
        elif args.stop:
            stop(pin)
        elif args.forward:
            run_forward(args.speed, args.duration, pin)
        elif args.reverse:
            run_reverse(args.speed, args.duration, pin)
        else:
            sweep_forward_reverse(args.speed, args.duration, args.cycles, pin)

    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")
    finally:
        stop(pin)
        cleanup(pin)


if __name__ == "__main__":
    main()
