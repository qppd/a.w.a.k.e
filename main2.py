#!/usr/bin/env python3
"""Test script — Camera feed + Pan/Tilt servo control via lgpio.

GPIO pins (BCM):
  Pan  → GPIO 12  — 360° continuous rotation servo (speed/direction via pulse)
  Tilt → GPIO 13  — Standard positional servo (angle via pulse)

Usage:
    python main2.py              # default camera 0
    python main2.py --camera 1   # specific camera index

Controls (when window focused):
    a / LEFT   → pan left       w / UP     → tilt up
    d / RIGHT  → pan right      x / DOWN   → tilt down
    s / SPACE  → stop pan       e          → tilt to 90° (centre)
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

# ── Servo constants ─────────────────────────────────────────
PAN_GPIO = 12
TILT_GPIO = 13

PULSE_MIN_US = 500
PULSE_MAX_US = 2500
NEUTRAL_US = 1500  # stop (360°) / centre (180°)

# Tilt positional range (standard 180° servo)
TILT_MIN_DEG = 0.0
TILT_MAX_DEG = 180.0
TILT_DEFAULT_DEG = 180.0  # front-facing home position


def _angle_to_pulse(angle_deg: float) -> int:
    """Convert physical servo angle (0-180°) to pulse width in µs."""
    norm = (angle_deg - TILT_MIN_DEG) / (TILT_MAX_DEG - TILT_MIN_DEG)
    return int(PULSE_MIN_US + norm * (PULSE_MAX_US - PULSE_MIN_US))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Camera + Pan/Tilt Servo test")
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

    # ── Claim and initialise both servo GPIOs ────────────────
    for gpio_pin in (PAN_GPIO, TILT_GPIO):
        ret = lgpio.gpio_claim_output(chip, gpio_pin)
        print(f"gpio_claim_output(GPIO {gpio_pin}): ret={ret}")

    # Pan servo: 360° continuous — start at neutral (stopped)
    ret = lgpio.tx_servo(chip, PAN_GPIO, NEUTRAL_US)
    print(f"Pan  servo GPIO {PAN_GPIO}: pulse={NEUTRAL_US}µs (ret={ret})")

    # Tilt servo: 180° positional — start at home (180° = front-facing)
    tilt_angle = TILT_DEFAULT_DEG
    tilt_pulse = _angle_to_pulse(tilt_angle)
    ret = lgpio.tx_servo(chip, TILT_GPIO, tilt_pulse)
    print(f"Tilt servo GPIO {TILT_GPIO}: {tilt_angle:.0f}° = {tilt_pulse}µs (ret={ret})")

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
            lgpio.tx_servo(chip, TILT_GPIO, 0)
            lgpio.gpio_free(chip, PAN_GPIO)
            lgpio.gpio_free(chip, TILT_GPIO)
            lgpio.gpiochip_close(chip)
            sys.exit(1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        print(f"Camera {args.camera} opened via OpenCV ({args.width}x{args.height})")

    # ── Control state ────────────────────────────────────────
    pan_pulse = NEUTRAL_US          # current pan pulse (360° servo: speed/direction)
    pan_step = 100                  # µs per keypress

    # tilt_angle already set above; tilt_step in degrees
    tilt_step = 5.0                 # degrees per keypress

    print("\nControls:")
    print("  Pan:  a/LEFT=left  d/RIGHT=right  s/SPACE=stop")
    print("  Tilt: w/UP=up(180°)  x/DOWN=down(0°)  e=centre(90°)")
    print("  Quit: q/ESC\n")

    try:
        while True:
            # ── Read frame ───────────────────────────────────
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
            # Pan status
            if pan_pulse < NEUTRAL_US:
                pan_dir = "RIGHT"
            elif pan_pulse > NEUTRAL_US:
                pan_dir = "LEFT"
            else:
                pan_dir = "STOP"

            hud_pan = f"Pan  GPIO{PAN_GPIO}  {pan_pulse:.0f}us [{pan_dir}]"
            cv2.putText(
                frame, hud_pan, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
            )

            # Tilt status
            hud_tilt = f"Tilt GPIO{TILT_GPIO}  {tilt_angle:.0f}deg ({tilt_pulse}us)"
            cv2.putText(
                frame, hud_tilt, (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2,
            )

            cv2.putText(
                frame, "a/d=pan s=stop | w/x=tilt e=centre | q=quit", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1,
            )

            cv2.imshow("Pan/Tilt Servo Test", frame)

            key = cv2.waitKey(1) & 0xFF

            # ── Quit ─────────────────────────────────────────
            if key in (ord("q"), 27):
                break

            # ── Pan controls (360° continuous servo) ─────────
            elif key in (ord("a"), 81):  # LEFT
                pan_pulse = min(PULSE_MAX_US, pan_pulse + pan_step)
                ret = lgpio.tx_servo(chip, PAN_GPIO, int(pan_pulse))
                print(f"  Pan LEFT  -> {pan_pulse:.0f} us  (ret={ret})")

            elif key in (ord("d"), 83):  # RIGHT
                pan_pulse = max(PULSE_MIN_US, pan_pulse - pan_step)
                ret = lgpio.tx_servo(chip, PAN_GPIO, int(pan_pulse))
                print(f"  Pan RIGHT -> {pan_pulse:.0f} us  (ret={ret})")

            elif key in (ord("s"), 32):  # STOP
                pan_pulse = NEUTRAL_US
                ret = lgpio.tx_servo(chip, PAN_GPIO, int(pan_pulse))
                print(f"  Pan STOP  -> {pan_pulse:.0f} us  (ret={ret})")

            # ── Tilt controls (180° positional servo) ────────
            elif key in (ord("w"), 82):  # UP — tilt up (towards 180°)
                tilt_angle = _clamp(tilt_angle + tilt_step, TILT_MIN_DEG, TILT_MAX_DEG)
                tilt_pulse = _angle_to_pulse(tilt_angle)
                ret = lgpio.tx_servo(chip, TILT_GPIO, tilt_pulse)
                print(f"  Tilt UP   -> {tilt_angle:.0f} deg ({tilt_pulse} us)  (ret={ret})")

            elif key in (ord("x"), 84):  # DOWN — tilt down (towards 0°)
                tilt_angle = _clamp(tilt_angle - tilt_step, TILT_MIN_DEG, TILT_MAX_DEG)
                tilt_pulse = _angle_to_pulse(tilt_angle)
                ret = lgpio.tx_servo(chip, TILT_GPIO, tilt_pulse)
                print(f"  Tilt DOWN -> {tilt_angle:.0f} deg ({tilt_pulse} us)  (ret={ret})")

            elif key == ord("e"):  # CENTRE — tilt to 90°
                tilt_angle = 90.0
                tilt_pulse = _angle_to_pulse(tilt_angle)
                ret = lgpio.tx_servo(chip, TILT_GPIO, tilt_pulse)
                print(f"  Tilt CENTRE -> {tilt_angle:.0f} deg ({tilt_pulse} us)  (ret={ret})")

    except KeyboardInterrupt:
        print("\nInterrupted")

    finally:
        # ── Cleanup ──────────────────────────────────────────
        lgpio.tx_servo(chip, PAN_GPIO, 0)   # stop pan pulse
        lgpio.tx_servo(chip, TILT_GPIO, 0)  # stop tilt pulse
        lgpio.gpio_free(chip, PAN_GPIO)
        lgpio.gpio_free(chip, TILT_GPIO)
        lgpio.gpiochip_close(chip)
        if picamera is not None:
            picamera.stop()
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        print("Cleaned up. Bye!")


if __name__ == "__main__":
    main()
