"""A.W.A.K.E. 2.0 — IR LED GPIO Test

Hardware pin assignment (BCM mode):
  IR LED  → GPIO 6  (Pin 31) via MOSFET

This script toggles the IR LED on/off in a loop so you can verify
the MOSFET gate, wiring, and LED are working correctly.

Usage:
  python test/led_test.py              # blink 5 times, ~1s on / 1s off
  python test/led_test.py --on         # turn on and stay on
  python test/led_test.py --off        # turn off immediately
  python test/led_test.py --count 10   # blink 10 times
"""
from __future__ import annotations

import argparse
import sys
import time

# ── Pin assignment (BCM) ────────────────────────────────────
IR_LED_GPIO = 6        # matches CFG.ir_led_gpio in src/awake/config.py

# ── Graceful fallback when RPi.GPIO is unavailable ───────────
try:
    import RPi.GPIO as gpio
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False


def setup() -> None:
    """Prepare the GPIO pin for output."""
    if not _HAS_GPIO:
        print("[WARN] RPi.GPIO not available — running in simulation mode")
        return
    gpio.setmode(gpio.BCM)
    gpio.setup(IR_LED_GPIO, gpio.OUT, initial=gpio.LOW)
    print(f"[OK] GPIO {IR_LED_GPIO} configured as OUTPUT (LOW)")


def led_on() -> None:
    """Turn the IR LED on."""
    if _HAS_GPIO:
        gpio.output(IR_LED_GPIO, True)
    print(f"[LED] GPIO {IR_LED_GPIO} → HIGH  (LED ON)")


def led_off() -> None:
    """Turn the IR LED off."""
    if _HAS_GPIO:
        gpio.output(IR_LED_GPIO, False)
    print(f"[LED] GPIO {IR_LED_GPIO} → LOW   (LED OFF)")


def cleanup() -> None:
    """Release the GPIO pin."""
    if _HAS_GPIO:
        led_off()
        gpio.cleanup(IR_LED_GPIO)
    print(f"[OK] GPIO {IR_LED_GPIO} cleaned up")


def blink(count: int = 5, interval: float = 1.0) -> None:
    """Blink the IR LED `count` times with `interval` seconds on/off."""
    print(f"\n=== IR LED Blink Test (GPIO {IR_LED_GPIO}) ===")
    print(f"    Blinking {count} times, {interval}s on / {interval}s off\n")

    for i in range(1, count + 1):
        led_on()
        time.sleep(interval)
        led_off()
        if i < count:
            time.sleep(interval)
        print(f"    [{i}/{count}] cycle complete")

    print(f"\n=== Test finished ({count} cycles) ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="A.W.A.K.E. IR LED GPIO test")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--on", action="store_true",
        help="Turn LED on and keep it on",
    )
    group.add_argument(
        "--off", action="store_true",
        help="Turn LED off immediately",
    )
    parser.add_argument(
        "--count", type=int, default=5,
        help="Number of blink cycles (default: 5)",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="Seconds on / off per cycle (default: 1.0)",
    )
    args = parser.parse_args()

    setup()

    try:
        if args.on:
            print("\n=== IR LED ON (holding) ===")
            led_on()
            print("Press Ctrl+C to turn off and exit")
            while True:
                time.sleep(1)
        elif args.off:
            led_off()
        else:
            blink(count=args.count, interval=args.interval)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
