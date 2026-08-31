#!/usr/bin/env python3
"""Test script — Camera feed + Pan servo (GPIO 12) via pigpio.

Usage:
    python main2.py              # default camera 0
    python main2.py --camera 1   # specific camera index

Controls (when window focused):
    a / LEFT   → pan left
    d / RIGHT  → pan right
    s / SPACE  → stop pan (neutral)
    q / ESC    → quit
"""
from __future__ import annotations

import argparse
import sys
import time

import cv2

# ── Pan servo constants ─────────────────────────────────────
PAN_GPIO = 12
PWM_FREQ_HZ = 50
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
NEUTRAL_US = 1500


def main() -> None:
    parser = argparse.ArgumentParser(description="Camera + Pan Servo test")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--width", type=int, default=640, help="Frame width")
    parser.add_argument("--height", type=int, default=480, help="Frame height")
    args = parser.parse_args()

    # ── Init pigpio ──────────────────────────────────────────
    try:
        import pigpio
    except ImportError:
        print("ERROR: pigpio not installed. Install with:")
        print("  pip install pigpio")
        sys.exit(1)

    pi = pigpio.pi()
    if not pi.connected:
        print("ERROR: pigpio daemon not running. Start it with:")
        print("  sudo pigpiod")
        print("  # or: sudo systemctl start pigpiod")
        sys.exit(1)

    pi.set_mode(PAN_GPIO, pigpio.OUTPUT)
    pi.set_servo_pulsewidth(PAN_GPIO, NEUTRAL_US)
    print(f"Pan servo initialised on GPIO {PAN_GPIO} (pulse: {NEUTRAL_US}µs)")

    # ── Init camera ──────────────────────────────────────────
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"ERROR: Cannot open camera {args.camera}")
        pi.set_servo_pulsewidth(PAN_GPIO, 0)
        pi.stop()
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    print(f"Camera {args.camera} opened ({args.width}x{args.height})")

    # ── Pan control state ────────────────────────────────────
    current_pulse = NEUTRAL_US
    step = 100  # µs per keypress

    print("\nControls:  a/LEFT=pan left  d/RIGHT=pan right  s/SPACE=stop  q/ESC=quit\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("No frame, retrying...")
                time.sleep(0.1)
                continue

            # ── HUD overlay ──────────────────────────────────
            hud = f"Pan GPIO{PAN_GPIO}  Pulse: {current_pulse:.0f} us"
            if current_pulse < NEUTRAL_US:
                hud += "  [RIGHT]"
            elif current_pulse > NEUTRAL_US:
                hud += "  [LEFT]"
            else:
                hud += "  [STOP]"

            cv2.putText(
                frame, hud, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
            )
            cv2.putText(
                frame, "a/d=pan  s=stop  q=quit", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
            )

            cv2.imshow("Pan Servo Test", frame)

            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):  # q or ESC
                break
            elif key in (ord("a"), 81):  # a or LEFT arrow
                current_pulse = min(PULSE_MAX_US, current_pulse + step)
                pi.set_servo_pulsewidth(PAN_GPIO, current_pulse)
                print(f"  Pan LEFT  → {current_pulse:.0f} µs")
            elif key in (ord("d"), 83):  # d or RIGHT arrow
                current_pulse = max(PULSE_MIN_US, current_pulse - step)
                pi.set_servo_pulsewidth(PAN_GPIO, current_pulse)
                print(f"  Pan RIGHT → {current_pulse:.0f} µs")
            elif key in (ord("s"), 32):  # s or SPACE
                current_pulse = NEUTRAL_US
                pi.set_servo_pulsewidth(PAN_GPIO, current_pulse)
                print(f"  Pan STOP  → {current_pulse:.0f} µs")

    except KeyboardInterrupt:
        print("\nInterrupted")

    finally:
        # ── Cleanup ──────────────────────────────────────────
        pi.set_servo_pulsewidth(PAN_GPIO, 0)  # release pulse
        pi.stop()
        cap.release()
        cv2.destroyAllWindows()
        print("Cleaned up. Bye!")


if __name__ == "__main__":
    main()
