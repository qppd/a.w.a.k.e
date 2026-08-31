#!/usr/bin/env python3
"""Test script — Camera feed + Pan servo (GPIO 12) via lgpio.

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

# Ensure picamera2 is importable from system packages (Raspberry Pi)
if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

import cv2

# ── Pan servo constants ─────────────────────────────────────
PAN_GPIO = 12
PULSE_MIN_US = 500
PULSE_MAX_US = 2500
NEUTRAL_US = 1500  # stop / centre for 360° continuous servo


def main() -> None:
    parser = argparse.ArgumentParser(description="Camera + Pan Servo test")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--width", type=int, default=640, help="Frame width")
    parser.add_argument("--height", type=int, default=480, help="Frame height")
    args = parser.parse_args()

    # ── Init lgpio ──────────────────────────────────────────
    try:
        import lgpio
    except ImportError:
        print("ERROR: lgpio not installed. Install with:")
        print("  pip install lgpio")
        sys.exit(1)

    try:
        chip = lgpio.gpiochip_open(0)
    except lgpio.error as exc:
        print(f"ERROR: Cannot open GPIO chip: {exc}")
        print("  Make sure you have permission (run with sudo if needed).")
        sys.exit(1)

    lgpio.gpio_claim_output(chip, PAN_GPIO)
    lgpio.tx_servo(chip, PAN_GPIO, NEUTRAL_US)
    print(f"Pan servo initialised on GPIO {PAN_GPIO} (pulse: {NEUTRAL_US}µs)")

    # ── Init camera (picamera2 on Pi, OpenCV fallback) ────────
    picamera = None
    cap = None

    def _is_raspberry_pi() -> bool:
        try:
            with open("/proc/cpuinfo", "r") as f:
                return "Raspberry Pi" in f.read()
        except FileNotFoundError:
            return False

    if _is_raspberry_pi():
        try:
            from picamera2 import Picamera2
            picamera = Picamera2()
            config = picamera.create_preview_configuration(
                main={"size": (args.width, args.height), "format": "RGB888"},
            )
            picamera.configure(config)
            picamera.start()
            print(f"picamera2 initialised ({args.width}x{args.height})")
        except (ImportError, Exception) as exc:
            print(f"picamera2 failed ({exc}) — falling back to OpenCV")
            picamera = None

    if picamera is None:
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            print(f"ERROR: Cannot open camera {args.camera}")
            lgpio.tx_servo(chip, PAN_GPIO, 0)
            lgpio.gpio_free(chip, PAN_GPIO)
            lgpio.gpiochip_close(chip)
            sys.exit(1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        print(f"Camera {args.camera} opened via OpenCV ({args.width}x{args.height})")

    # ── Pan control state ────────────────────────────────────
    current_pulse = NEUTRAL_US
    step = 100  # µs per keypress

    print("\nControls:  a/LEFT=pan left  d/RIGHT=pan right  s/SPACE=stop  q/ESC=quit\n")

    try:
        while True:
            if picamera is not None:
                frame = picamera.capture_array("main")
            else:
                ok, frame = cap.read()
                if not ok:
                    frame = None
            if frame is None:
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
                lgpio.tx_servo(chip, PAN_GPIO, int(current_pulse))
                print(f"  Pan LEFT  → {current_pulse:.0f} µs")
            elif key in (ord("d"), 83):  # d or RIGHT arrow
                current_pulse = max(PULSE_MIN_US, current_pulse - step)
                lgpio.tx_servo(chip, PAN_GPIO, int(current_pulse))
                print(f"  Pan RIGHT → {current_pulse:.0f} µs")
            elif key in (ord("s"), 32):  # s or SPACE
                current_pulse = NEUTRAL_US
                lgpio.tx_servo(chip, PAN_GPIO, int(current_pulse))
                print(f"  Pan STOP  → {current_pulse:.0f} µs")

    except KeyboardInterrupt:
        print("\nInterrupted")

    finally:
        # ── Cleanup ──────────────────────────────────────────
        lgpio.tx_servo(chip, PAN_GPIO, 0)  # stop pulse
        lgpio.gpio_free(chip, PAN_GPIO)
        lgpio.gpiochip_close(chip)
        if picamera is not None:
            picamera.stop()
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        print("Cleaned up. Bye!")


if __name__ == "__main__":
    main()
