#!/usr/bin/env python3
"""Test script — Camera feed + Pan/Tilt servo control.

GPIO pins (BCM):
  Pan  → GPIO 12  — 360° continuous rotation servo (rpi-hardware-pwm)
  Tilt → GPIO 13  — Standard positional servo (RPi.GPIO software PWM)

Setup (one-time):
  1. Add to /boot/firmware/config.txt:
     dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
  2. Reboot
  3. pip install rpi-hardware-pwm

Usage:
    python main3.py              # default camera 0
    python main3.py --camera 1   # specific camera index

Controls:
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

PWM_FREQ_HZ = 50
PWM_PERIOD_US = 1_000_000 // PWM_FREQ_HZ  # 20 000 µs

PULSE_MIN_US = 500
PULSE_MAX_US = 2500
NEUTRAL_US = 1500  # stop (360°) / centre (180°)

TILT_MIN_DEG = 0.0
TILT_MAX_DEG = 180.0
TILT_DEFAULT_DEG = 180.0

TILT_MOVE_TIME = 0.3


def _pulse_to_duty(pulse_us: float) -> float:
    return pulse_us / PWM_PERIOD_US * 100.0


def _angle_to_pulse(angle_deg: float) -> int:
    norm = (angle_deg - TILT_MIN_DEG) / (TILT_MAX_DEG - TILT_MIN_DEG)
    return int(PULSE_MIN_US + norm * (PULSE_MAX_US - PULSE_MIN_US))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _stop_tilt_pwm(tilt_pwm) -> None:
    tilt_pwm.ChangeDutyCycle(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Camera + Pan/Tilt Servo test")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--width", type=int, default=640, help="Frame width")
    parser.add_argument("--height", type=int, default=480, help="Frame height")
    args = parser.parse_args()

    # ── Init Pan servo (rpi-hardware-pwm on GPIO 12) ─────────
    try:
        from rpi_hardware_pwm import HardwarePWM
    except ImportError:
        print("ERROR: pip install rpi-hardware-pwm")
        print("Also add to /boot/firmware/config.txt:")
        print("  dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4")
        sys.exit(1)

    pan_pwm = HardwarePWM(pwm_channel=0, hz=PWM_FREQ_HZ, chip=2)  # Pi 5: GPIO 12 is on PWM chip 2
    pan_duty = _pulse_to_duty(NEUTRAL_US)
    pan_pwm.start(pan_duty)
    print(f"Pan  GPIO {PAN_GPIO}: hardware PWM at {NEUTRAL_US}us (duty={pan_duty:.2f}%)")

    # ── Init Tilt servo (RPi.GPIO on GPIO 13) ────────────────
    try:
        import RPi.GPIO as gpio
    except ImportError:
        print("ERROR: pip install RPi.GPIO  OR  pip install rpi-lgpio")
        pan_pwm.stop()
        sys.exit(1)

    gpio.setmode(gpio.BCM)
    gpio.setup(TILT_GPIO, gpio.OUT, initial=gpio.LOW)
    tilt_pwm = gpio.PWM(TILT_GPIO, PWM_FREQ_HZ)
    tilt_angle = TILT_DEFAULT_DEG
    tilt_pulse = _angle_to_pulse(tilt_angle)
    tilt_pwm.start(_pulse_to_duty(tilt_pulse))
    time.sleep(TILT_MOVE_TIME)
    _stop_tilt_pwm(tilt_pwm)
    print(f"Tilt GPIO {TILT_GPIO}: {tilt_angle:.0f} deg = {tilt_pulse}us (stopped)")

    # ── Init camera ──────────────────────────────────────────
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
            print(f"picamera2 ({args.width}x{args.height})")
        except (ImportError, Exception) as exc:
            print(f"picamera2 failed ({exc})")
            picamera = None

    if picamera is None:
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            print(f"ERROR: Cannot open camera {args.camera}")
            pan_pwm.stop()
            tilt_pwm.stop()
            gpio.cleanup([TILT_GPIO])
            sys.exit(1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        print(f"Camera {args.camera} via OpenCV ({args.width}x{args.height})")

    # ── State ────────────────────────────────────────────────
    pan_pulse = NEUTRAL_US
    pan_step = 100
    tilt_step = 5.0
    tilt_moving_since: float | None = None

    print("\nControls:")
    print("  a/d=pan  s=stop  |  w/x=tilt  e=centre  |  q=quit\n")

    try:
        while True:
            if tilt_moving_since is not None:
                if time.time() - tilt_moving_since >= TILT_MOVE_TIME:
                    _stop_tilt_pwm(tilt_pwm)
                    tilt_moving_since = None

            if picamera is not None:
                frame = picamera.capture_array("main")
            else:
                ok, frame = cap.read()
                if not ok:
                    frame = None
            if frame is None:
                time.sleep(0.1)
                continue

            # HUD
            pan_dir = "RIGHT" if pan_pulse < NEUTRAL_US else ("LEFT" if pan_pulse > NEUTRAL_US else "STOP")
            cv2.putText(frame, f"Pan  {PAN_GPIO} {pan_pulse:.0f}us [{pan_dir}]", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            ts = f"moving" if tilt_moving_since else "hold"
            cv2.putText(frame, f"Tilt {TILT_GPIO} {tilt_angle:.0f}deg [{ts}]", (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            cv2.putText(frame, "a/d=pan s=stop | w/x=tilt e=centre | q=quit", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

            cv2.imshow("Pan/Tilt Test", frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                break
            elif key in (ord("a"), 81):
                pan_pulse = min(PULSE_MAX_US, pan_pulse + pan_step)
                pan_pwm.change_duty_cycle(_pulse_to_duty(pan_pulse))
                print(f"  Pan LEFT  -> {pan_pulse:.0f}us")
            elif key in (ord("d"), 83):
                pan_pulse = max(PULSE_MIN_US, pan_pulse - pan_step)
                pan_pwm.change_duty_cycle(_pulse_to_duty(pan_pulse))
                print(f"  Pan RIGHT -> {pan_pulse:.0f}us")
            elif key in (ord("s"), 32):
                pan_pulse = NEUTRAL_US
                pan_pwm.change_duty_cycle(_pulse_to_duty(pan_pulse))
                print(f"  Pan STOP  -> {pan_pulse:.0f}us")
            elif key in (ord("w"), 82):
                tilt_angle = _clamp(tilt_angle + tilt_step, TILT_MIN_DEG, TILT_MAX_DEG)
                tilt_pulse = _angle_to_pulse(tilt_angle)
                tilt_pwm.ChangeDutyCycle(_pulse_to_duty(tilt_pulse))
                tilt_moving_since = time.time()
                print(f"  Tilt UP   -> {tilt_angle:.0f}deg ({tilt_pulse}us)")
            elif key in (ord("x"), 84):
                tilt_angle = _clamp(tilt_angle - tilt_step, TILT_MIN_DEG, TILT_MAX_DEG)
                tilt_pulse = _angle_to_pulse(tilt_angle)
                tilt_pwm.ChangeDutyCycle(_pulse_to_duty(tilt_pulse))
                tilt_moving_since = time.time()
                print(f"  Tilt DOWN -> {tilt_angle:.0f}deg ({tilt_pulse}us)")
            elif key == ord("e"):
                tilt_angle = 90.0
                tilt_pulse = _angle_to_pulse(tilt_angle)
                tilt_pwm.ChangeDutyCycle(_pulse_to_duty(tilt_pulse))
                tilt_moving_since = time.time()
                print(f"  Tilt CENTRE -> 90deg ({tilt_pulse}us)")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        pan_pwm.stop()
        tilt_pwm.ChangeDutyCycle(0)
        time.sleep(0.1)
        tilt_pwm.stop()
        gpio.output(TILT_GPIO, False)
        gpio.cleanup([TILT_GPIO])
        if picamera:
            picamera.stop()
        if cap:
            cap.release()
        cv2.destroyAllWindows()
        print("Bye!")


if __name__ == "__main__":
    main()
