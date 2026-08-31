"""A.W.A.K.E. 2.0 — Passive Piezo Buzzer GPIO Test

Hardware pin assignment (BCM mode):
  Buzzer → GPIO 17  (Pin 11)  — Software PWM

A passive piezo buzzer requires a square-wave signal to produce
sound. This test uses RPi.GPIO software PWM to generate tones at
different frequencies.

Usage:
  python test/buzzer_test.py                   # beep at 1000 Hz (default)
  python test/buzzer_test.py --freq 2000       # beep at 2000 Hz
  python test/buzzer_test.py --freq 500 --duration 2   # low tone, 2s
  python test/buzzer_test.py --sweep           # frequency sweep 200–3000 Hz
  python test/buzzer_test.py --alarm           # alarm pattern (pulsing)
  python test/buzzer_test.py --pattern         # multi-tone alert pattern
  python test/buzzer_test.py --off             # silence immediately
"""
from __future__ import annotations

import argparse
import sys
import time

# ── Pin assignment (BCM) — must match src/awake/config.py ───
BUZZER_GPIO = 17   # CFG.buzzer_gpio

# ── Default frequency — must match src/awake/config.py ──────
DEFAULT_FREQ = 1000   # CFG.alarm_buzzer_freq (Hz)
DEFAULT_DUTY = 50     # 50% duty cycle (square wave)

# ── RPi.GPIO fallback ───────────────────────────────────────
try:
    import RPi.GPIO as gpio
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False


# ── Helpers ─────────────────────────────────────────────────

def setup() -> None:
    """Prepare the GPIO pin for PWM output."""
    if not _HAS_GPIO:
        print("[WARN] RPi.GPIO not available — running in simulation mode")
        return
    gpio.setmode(gpio.BCM)
    gpio.setup(BUZZER_GPIO, gpio.OUT, initial=gpio.LOW)
    print(f"[OK] GPIO {BUZZER_GPIO} configured as OUTPUT (BCM mode)")


def tone_on(freq: int = DEFAULT_FREQ, duty: int = DEFAULT_DUTY) -> None:
    """Start PWM at the given frequency — buzzer sounds."""
    if _HAS_GPIO:
        _pwm = gpio.PWM(BUZZER_GPIO, freq)
        _pwm.start(duty)
        return _pwm
    print(f"  [TONE] GPIO {BUZZER_GPIO}  {freq} Hz  duty={duty}%")
    return None


def tone_off(pwm) -> None:
    """Stop PWM — buzzer silent."""
    if pwm is not None:
        pwm.stop()
    if _HAS_GPIO:
        gpio.output(BUZZER_GPIO, gpio.LOW)


def cleanup() -> None:
    """Release the GPIO pin."""
    if _HAS_GPIO:
        gpio.output(BUZZER_GPIO, gpio.LOW)
        gpio.cleanup(BUZZER_GPIO)
    print(f"\n[OK] GPIO {BUZZER_GPIO} released")


# ── Tests ───────────────────────────────────────────────────

def single_beep(freq: int, duration: float) -> None:
    """Single beep at a given frequency for a given duration."""
    print(f"\n=== Single Beep: {freq} Hz, {duration}s ===")
    pwm = tone_on(freq)
    time.sleep(duration)
    tone_off(pwm)
    print("  done")


def frequency_sweep() -> None:
    """Sweep from 200 Hz to 3000 Hz in steps."""
    print("\n=== Frequency Sweep (200 — 3000 Hz) ===")
    for freq in range(200, 3001, 100):
        pwm = tone_on(freq)
        print(f"  {freq} Hz", end="\r")
        time.sleep(0.08)
        tone_off(pwm)
        time.sleep(0.02)
    print("\n  sweep complete")


def alarm_pattern() -> None:
    """Pulsing alarm — fast on/off at 1000 Hz (matches CFG.alarm_buzzer_freq)."""
    print(f"\n=== Alarm Pattern ({DEFAULT_FREQ} Hz, 5 pulses) ===")
    print("    Press Ctrl+C to stop early\n")

    try:
        for i in range(1, 6):
            print(f"  pulse {i}/5", end="")
            pwm = tone_on(DEFAULT_FREQ)
            time.sleep(0.3)
            tone_off(pwm)
            time.sleep(0.15)
            print("  ✓")
    except KeyboardInterrupt:
        print("\n  [INTERRUPTED]")

    print("  alarm pattern complete")


def multi_tone_pattern() -> None:
    """Three-tone ascending alert pattern."""
    tones = [
        (600,  0.25, "low"),
        (1000, 0.25, "mid"),
        (1500, 0.40, "high"),
    ]
    print("\n=== Multi-Tone Alert Pattern ===")
    print("    Press Ctrl+C to stop early\n")

    try:
        for cycle in range(1, 4):
            print(f"  cycle {cycle}/3")
            for freq, dur, label in tones:
                print(f"    {label}  {freq} Hz  {dur}s")
                pwm = tone_on(freq)
                time.sleep(dur)
                tone_off(pwm)
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n  [INTERRUPTED]")

    print("  pattern complete")


def silence() -> None:
    """Immediately silence the buzzer."""
    print(f"\n=== Silence GPIO {BUZZER_GPIO} ===")
    if _HAS_GPIO:
        gpio.output(BUZZER_GPIO, gpio.LOW)
    print("  buzzer off")


# ── CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="A.W.A.K.E. Passive Piezo Buzzer GPIO test"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--freq",     type=int, metavar="HZ",
                       help=f"Beep at this frequency (default: {DEFAULT_FREQ})")
    group.add_argument("--sweep",    action="store_true",
                       help="Frequency sweep 200–3000 Hz")
    group.add_argument("--alarm",    action="store_true",
                       help="Pulsing alarm pattern")
    group.add_argument("--pattern",  action="store_true",
                       help="Multi-tone ascending alert")
    group.add_argument("--off",      action="store_true",
                       help="Silence immediately")
    parser.add_argument("--duration", type=float, default=0.5,
                        help="Duration for single beep in seconds (default: 0.5)")

    args = parser.parse_args()

    setup()

    try:
        if args.off:
            silence()

        elif args.sweep:
            frequency_sweep()

        elif args.alarm:
            alarm_pattern()

        elif args.pattern:
            multi_tone_pattern()

        elif args.freq is not None:
            single_beep(args.freq, args.duration)

        else:
            # Default: single beep at default frequency
            single_beep(DEFAULT_FREQ, args.duration)

    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")
    finally:
        silence()
        cleanup()


if __name__ == "__main__":
    main()
