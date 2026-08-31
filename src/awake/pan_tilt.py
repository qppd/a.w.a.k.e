"""A.W.A.K.E. 2.0 — Pan/Tilt Servo Control Module

GPIO pins (BCM):
  Pan  → GPIO 12  — 360° continuous rotation servo (rpi-hardware-pwm)
  Tilt → GPIO 13  — Standard positional servo (RPi.GPIO software PWM)

Improvements:
  - Face position prediction (compensates ~100ms detection latency)
  - Error smoothing (EMA filter prevents jerky movements)
  - Adaptive deadband (tight when moving, wide when still)
"""
from __future__ import annotations

import logging
import math
import time

from .config import CFG

logger = logging.getLogger(__name__)

# ── PWM spec ───────────────────────────────────────────────
PWM_FREQ_HZ   = 50       # 50 Hz standard servo PWM
PULSE_MIN_US  = 500
PULSE_MAX_US  = 2500
NEUTRAL_US    = 1500     # stop / centre for both servos
PWM_PERIOD_US = 1_000_000 // PWM_FREQ_HZ   # 20 000 µs

# ── Tilt positional range ──────────────────────────────────
TILT_MIN_DEG = 0.0
TILT_MAX_DEG = 180.0
TILT_STEP_MAX = 3.0      # max degrees per frame for smooth movement

# ── Prediction & smoothing ─────────────────────────────────
PREDICTION_LOOKAHEAD = 0.12   # predict 120ms ahead (detection latency)
SMOOTHING_ALPHA = 0.4         # EMA filter: 0=instant, 1=never moves
ADAPTIVE_DEADZONE_MOVING = 5  # px deadband when face is moving fast
ADAPTIVE_DEADZONE_STILL = 15  # px deadband when face is still


class PanTilt:

    def __init__(self) -> None:
        self._gpio = None
        self._pan_pwm = None
        self._tilt_pwm = None
        self._tilt_angle: float = 180.0
        self._has_gpio = False
        self._has_hw_pwm = False

        # ── Prediction state ────────────────────────────────
        self._prev_face_center: tuple[int, int] | None = None
        self._prev_time: float = 0.0
        self._face_vel_x: float = 0.0   # px/sec
        self._face_vel_y: float = 0.0

        # ── Smoothing state ─────────────────────────────────
        self._smooth_error_x: float = 0.0
        self._smooth_error_y: float = 0.0
        self._has_previous: bool = False

    # ── Init ────────────────────────────────────────────────

    def init(self) -> None:
        # ── Pan servo: rpi-hardware-pwm on GPIO 12 ──────────
        try:
            from rpi_hardware_pwm import HardwarePWM
            self._pan_pwm = HardwarePWM(pwm_channel=0, hz=PWM_FREQ_HZ, chip=2)
            self._pan_pwm.start(_pulse_to_duty(NEUTRAL_US))
            self._has_hw_pwm = True
            logger.info("Pan servo initialised via rpi-hardware-pwm (GPIO %d)", CFG.servo_pan_gpio)
        except (ImportError, Exception) as exc:
            logger.warning("rpi-hardware-pwm unavailable (%s) — pan servo disabled", exc)

        # ── Tilt servo: RPi.GPIO on GPIO 13 ─────────────────
        try:
            import RPi.GPIO as gpio
            gpio.setmode(gpio.BCM)
            gpio.setup(CFG.servo_tilt_gpio, gpio.OUT, initial=gpio.LOW)
            self._tilt_pwm = gpio.PWM(CFG.servo_tilt_gpio, PWM_FREQ_HZ)
            self._tilt_pwm.start(_pulse_to_duty(_angle_to_pulse(180.0)))
            self._gpio = gpio
            self._has_gpio = True
            logger.info("Tilt servo initialised via RPi.GPIO (GPIO %d)", CFG.servo_tilt_gpio)
        except (ImportError, RuntimeError) as exc:
            logger.warning("RPi.GPIO unavailable (%s) — tilt servo disabled", exc)
            self._has_gpio = False

    # ── Public API ──────────────────────────────────────────

    def update(self, face_center: tuple[int, int], frame_size: tuple[int, int]) -> None:
        """Track face centre with prediction and smoothing.

        1. Compute raw error from face position
        2. Predict future position (compensate detection latency)
        3. Smooth the error (EMA filter)
        4. Apply proportional control with adaptive deadband
        """
        now = time.time()
        fw, fh = frame_size
        fcx, fcy = face_center

        # ── Step 1: Compute velocity ────────────────────────
        if self._prev_face_center is not None and self._prev_time > 0:
            dt = now - self._prev_time
            if dt > 0:
                # Exponential smoothing on velocity (prevents spikes)
                alpha_v = 0.3
                raw_vx = (fcx - self._prev_face_center[0]) / dt
                raw_vy = (fcy - self._prev_face_center[1]) / dt
                self._face_vel_x = alpha_v * raw_vx + (1 - alpha_v) * self._face_vel_x
                self._face_vel_y = alpha_v * raw_vy + (1 - alpha_v) * self._face_vel_y

        self._prev_face_center = face_center
        self._prev_time = now

        # ── Step 2: Predict future face position ────────────
        pred_cx = fcx + self._face_vel_x * PREDICTION_LOOKAHEAD
        pred_cy = fcy + self._face_vel_y * PREDICTION_LOOKAHEAD

        # Raw error = predicted position − frame centre
        raw_error_x = pred_cx - fw // 2
        raw_error_y = pred_cy - fh // 2

        # ── Step 3: Smooth error (EMA filter) ───────────────
        if not self._has_previous:
            self._smooth_error_x = raw_error_x
            self._smooth_error_y = raw_error_y
            self._has_previous = True
        else:
            self._smooth_error_x = SMOOTHING_ALPHA * raw_error_x + (1 - SMOOTHING_ALPHA) * self._smooth_error_x
            self._smooth_error_y = SMOOTHING_ALPHA * raw_error_y + (1 - SMOOTHING_ALPHA) * self._smooth_error_y

        error_x = self._smooth_error_x
        error_y = self._smooth_error_y

        # ── Step 4: Adaptive deadband ───────────────────────
        speed = math.hypot(self._face_vel_x, self._face_vel_y)
        # Interpolate deadband: fast face → small deadband, still face → large deadband
        speed_clamped = min(speed / 200.0, 1.0)  # normalize: 200px/s = full speed
        deadband = ADAPTIVE_DEADZONE_STILL - speed_clamped * (ADAPTIVE_DEADZONE_STILL - ADAPTIVE_DEADZONE_MOVING)

        # ── Pan: continuous rotation ─────────────────────────
        if abs(error_x) > deadband:
            pan_pulse = _error_to_pan_pulse(error_x, fw)
            self._set_pan_pulse(pan_pulse)
        else:
            self._set_pan_pulse(NEUTRAL_US)

        # ── Tilt: positional servo ──────────────────────────
        half_frame = fh / 2.0
        desired_angle = _clamp(
            180.0 - (error_y / half_frame) * 30.0,  # ±30° around home
            0.0,
            180.0,
        )

        # Smooth movement toward target
        diff = desired_angle - self._tilt_angle
        if abs(diff) > TILT_STEP_MAX:
            step = TILT_STEP_MAX if diff > 0 else -TILT_STEP_MAX
            self._tilt_angle += step
        else:
            self._tilt_angle = desired_angle

        # Always hold position (keeps servo locked)
        self._apply_tilt()

    def reset_tracking(self) -> None:
        """Reset prediction state (call when face is lost)."""
        self._prev_face_center = None
        self._prev_time = 0.0
        self._face_vel_x = 0.0
        self._face_vel_y = 0.0
        self._smooth_error_x = 0.0
        self._smooth_error_y = 0.0
        self._has_previous = False

    def search(self) -> None:
        """Sweep pan and tilt servos back and forth when no face detected."""
        now = time.time()

        # Pan: continuous rotation sweep
        pan_sweep = 30 * math.sin(now * 0.5)
        pan_pulse = NEUTRAL_US + (pan_sweep / 60.0) * (PULSE_MAX_US - NEUTRAL_US)
        self._set_pan_pulse(pan_pulse)

        # Tilt: sweep 120° ↔ 180° back and forth
        tilt_sweep = 30 * math.sin(now * 0.3)
        target_tilt = _clamp(150.0 + tilt_sweep, 120.0, 180.0)
        self._tilt_angle = target_tilt
        self._apply_tilt()

    def centre(self) -> None:
        """Centre both servos."""
        self._set_pan_pulse(NEUTRAL_US)
        self._tilt_angle = 180.0
        self._apply_tilt()

    def release(self) -> None:
        """Stop PWM and release GPIO."""
        if self._has_hw_pwm and self._pan_pwm is not None:
            self._pan_pwm.stop()
            self._pan_pwm = None
            self._has_hw_pwm = False

        if self._has_gpio and self._gpio is not None:
            if self._tilt_pwm is not None:
                self._tilt_pwm.ChangeDutyCycle(0)
                time.sleep(0.1)
                self._tilt_pwm.stop()
                self._tilt_pwm = None
            self._gpio.output(CFG.servo_tilt_gpio, False)
            self._gpio.cleanup([CFG.servo_tilt_gpio])
        logger.info("PanTilt released")

    # ── Private helpers ─────────────────────────────────────

    def _set_pan_pulse(self, pulse_us: float) -> None:
        clamped = _clamp(pulse_us, PULSE_MIN_US, PULSE_MAX_US)
        if self._has_hw_pwm and self._pan_pwm is not None:
            self._pan_pwm.change_duty_cycle(_pulse_to_duty(clamped))

    def _apply_tilt(self) -> None:
        pulse = _angle_to_pulse(self._tilt_angle)
        duty = _pulse_to_duty(pulse)
        if self._has_gpio and self._tilt_pwm is not None:
            self._tilt_pwm.ChangeDutyCycle(duty)

    @property
    def angles(self) -> tuple[float, float]:
        return 0.0, self._tilt_angle


# ── Module-level helpers ────────────────────────────────────

def _pulse_to_duty(pulse_us: float) -> float:
    return pulse_us / PWM_PERIOD_US * 100.0


def _angle_to_pulse(angle: float) -> int:
    norm = (angle - TILT_MIN_DEG) / (TILT_MAX_DEG - TILT_MIN_DEG)
    return int(PULSE_MIN_US + norm * (PULSE_MAX_US - PULSE_MIN_US))


def _error_to_pan_pulse(error_x: float, frame_width: int) -> float:
    """Convert horizontal pixel error to pan servo pulse width.

    error_x > 0 → face right → pan right → pulse < 1500
    error_x < 0 → face left  → pan left  → pulse > 1500
    """
    max_error = frame_width / 2
    norm = max(-1.0, min(1.0, error_x / max_error))

    if norm >= 0:
        return 1300.0 - norm * 800.0
    else:
        return 1800.0 + abs(norm) * 700.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
