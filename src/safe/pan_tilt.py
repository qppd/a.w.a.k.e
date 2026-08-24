"""S.A.F.E. 2.0 — Pan/Tilt Servo Control Module"""
from __future__ import annotations

import logging
import math

from .config import CFG

logger = logging.getLogger(__name__)


class PanTilt:

    def __init__(self) -> None:
        self._pi = None
        self._pan_angle: float = 0.0
        self._tilt_angle: float = 0.0
        self._use_pigpio = False

    def init(self) -> None:
        try:
            import pigpio
            self._pi = pigpio.pi()
            if not self._pi.connected:
                raise RuntimeError("pigpiod not running")
            self._use_pigpio = True
            self._pi.set_PWM_frequency(CFG.servo_pan_gpio, 50)
            self._pi.set_PWM_frequency(CFG.servo_tilt_gpio, 50)
            logger.info(
                "PanTilt initialised via pigpio (pan=%d, tilt=%d)",
                CFG.servo_pan_gpio,
                CFG.servo_tilt_gpio,
            )
        except Exception as exc:
            logger.warning("pigpio unavailable (%s) — using simulation mode", exc)
            self._use_pigpio = False

    def update(self, face_center: tuple[int, int], frame_size: tuple[int, int]) -> None:
        fw, fh = frame_size
        fcx, fcy = face_center
        error_x = fcx - fw // 2
        error_y = fcy - fh // 2

        if abs(error_x) > CFG.pan_tilt_deadband:
            delta_pan = CFG.pan_kp * error_x
            self._pan_angle = self._clamp(
                self._pan_angle + delta_pan,
                CFG.pan_min_angle,
                CFG.pan_max_angle,
            )

        if abs(error_y) > CFG.pan_tilt_deadband:
            delta_tilt = CFG.tilt_kp * error_y
            self._tilt_angle = self._clamp(
                self._tilt_angle - delta_tilt,
                CFG.tilt_min_angle,
                CFG.tilt_max_angle,
            )

        self._apply()

    def search(self) -> None:
        import time
        sweep = 30 * math.sin(time.time() * 0.5)
        self._pan_angle = self._clamp(sweep, CFG.pan_min_angle, CFG.pan_max_angle)
        self._apply()

    def centre(self) -> None:
        self._pan_angle = 0.0
        self._tilt_angle = 0.0
        self._apply()

    def release(self) -> None:
        if self._pi is not None and self._use_pigpio:
            self._pi.set_PWM_dutycycle(CFG.servo_pan_gpio, 0)
            self._pi.set_PWM_dutycycle(CFG.servo_tilt_gpio, 0)
            self._pi.stop()
        logger.info("PanTilt released")

    def _apply(self) -> None:
        if self._use_pigpio and self._pi is not None:
            pan_pulse = self._angle_to_pulse(self._pan_angle)
            tilt_pulse = self._angle_to_pulse(self._tilt_angle)
            self._pi.set_servo_pulsewidth(CFG.servo_pan_gpio, pan_pulse)
            self._pi.set_servo_pulsewidth(CFG.servo_tilt_gpio, tilt_pulse)

    def _angle_to_pulse(self, angle: float) -> int:
        min_a = min(CFG.pan_min_angle, CFG.tilt_min_angle)
        max_a = max(CFG.pan_max_angle, CFG.tilt_max_angle)
        norm = (angle - min_a) / (max_a - min_a)
        pulse = CFG.servo_min_pulse_us + norm * (CFG.servo_max_pulse_us - CFG.servo_min_pulse_us)
        return int(pulse)

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    @property
    def angles(self) -> tuple[float, float]:
        return self._pan_angle, self._tilt_angle
