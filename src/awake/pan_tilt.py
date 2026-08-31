"""A.W.A.K.E. 2.0 — Pan/Tilt Servo Control Module

GPIO pins (BCM):
  Pan  → GPIO 12  — 360° continuous rotation servo (speed/direction via PWM)
  Tilt → GPIO 13  — Standard positional servo (angle via PWM)

Both use RPi.GPIO software PWM at 50 Hz.
"""
from __future__ import annotations

import logging
import math
import time

from .config import CFG

logger = logging.getLogger(__name__)

# ── PWM spec ───────────────────────────────────────────────
PWM_FREQ_HZ   = 50       # 50 Hz standard servo PWM
PULSE_MIN_US  = 500      # CFG.servo_min_pulse_us
PULSE_MAX_US  = 2500     # CFG.servo_max_pulse_us
NEUTRAL_US    = 1500     # stop / centre for both servos
PWM_PERIOD_US = 1_000_000 // PWM_FREQ_HZ   # 20 000 µs

# ── Tilt positional range (standard servo) ─────────────────
TILT_MIN_DEG = 0.0       # physical 0°
TILT_MAX_DEG = 180.0     # physical 180°

# ── Pan speed mapping (continuous rotation) ────────────────
# Negative error → forward, positive error → reverse
# Speed proportional to error, clamped to valid pulse range


class PanTilt:

    def __init__(self) -> None:
        self._gpio = None
        self._pan_pwm = None
        self._tilt_pwm = None
        self._tilt_angle: float = 180.0  # tilt starts at 180° (front-facing)
        self._has_gpio = False
        self._pigpio_pi = None  # pigpio instance for GPIO12 (HW PWM workaround)
        # Tilt servo stability: stop PWM after movement, cooldown, angle deadband
        self._tilt_cooldown_until: float = 0.0
        self._tilt_moving_since: float | None = None

    # ── Init ────────────────────────────────────────────────

    def init(self) -> None:
        # ── Try pigpio first for the pan servo (GPIO 12) ──────────
        # GPIO 12 is a hardware-PWM pin; RPi.GPIO HW-PWM can produce
        # inaccurate pulse widths that prevent continuous-rotation
        # servos from responding.  pigpio gives cycle-accurate output.
        try:
            import pigpio
            pi = pigpio.pi()
            if pi.connected:
                self._pigpio_pi = pi
                pi.set_mode(CFG.servo_pan_gpio, pigpio.OUTPUT)
                pi.set_servo_pulsewidth(CFG.servo_pan_gpio, NEUTRAL_US)
                logger.info(
                    "Pan servo initialised via pigpio (GPIO %d)",
                    CFG.servo_pan_gpio,
                )
            else:
                logger.warning("pigpio daemon not running — will fall back to RPi.GPIO")
        except (ImportError, OSError):
            logger.debug("pigpio not available — will use RPi.GPIO for pan")

        try:
            import RPi.GPIO as gpio
            gpio.setmode(gpio.BCM)

            # Pan — continuous rotation servo (only if pigpio not used)
            if self._pigpio_pi is None:
                gpio.setup(CFG.servo_pan_gpio, gpio.OUT, initial=gpio.LOW)
                self._pan_pwm = gpio.PWM(CFG.servo_pan_gpio, PWM_FREQ_HZ)
                self._pan_pwm.start(_pulse_to_duty(NEUTRAL_US))

            # Tilt — standard positional servo
            gpio.setup(CFG.servo_tilt_gpio, gpio.OUT, initial=gpio.LOW)
            self._tilt_pwm = gpio.PWM(CFG.servo_tilt_gpio, PWM_FREQ_HZ)
            self._tilt_pwm.start(_pulse_to_duty(_angle_to_pulse(180.0)))

            self._gpio = gpio
            self._has_gpio = True
            logger.info(
                "PanTilt initialised (pan=%d via %s, tilt=%d via RPi.GPIO)",
                CFG.servo_pan_gpio,
                "pigpio" if self._pigpio_pi else "RPi.GPIO",
                CFG.servo_tilt_gpio,
            )
        except (ImportError, RuntimeError) as exc:
            if self._pigpio_pi is None:
                logger.warning("RPi.GPIO unavailable (%s) — using simulation mode", exc)
            self._has_gpio = False

    # ── Public API ──────────────────────────────────────────

    def update(self, face_center: tuple[int, int], frame_size: tuple[int, int]) -> None:
        """Move servos to track the face centre.

        Pan (continuous rotation): speed proportional to horizontal error.
        Tilt (positional): angle proportional to vertical error.
        """
        fw, fh = frame_size
        fcx, fcy = face_center
        error_x = fcx - fw // 2
        error_y = fcy - fh // 2

        # ── Pan: continuous rotation — speed from error_x ──
        # Face right of centre (error > 0) → pan right → pulse < 1500
        # Face left of centre  (error < 0) → pan left  → pulse > 1500
        if abs(error_x) > CFG.pan_tilt_deadband:
            pan_pulse = _error_to_pan_pulse(error_x, fw)
            self._set_pan_pulse(pan_pulse)
        else:
            self._set_pan_pulse(NEUTRAL_US)

        # ── Tilt: positional servo — centre face vertically ────
        # Directly compute the target angle that puts the face at frame centre,
        # then move the servo there in one step.
        now = time.time()

        # If servo is still physically moving to the last target, wait
        if self._tilt_moving_since is not None:
            if now - self._tilt_moving_since >= CFG.tilt_move_time:
                # Servo has had time to reach position — stop PWM signal
                self._stop_tilt_pwm()
                self._tilt_moving_since = None
                self._tilt_cooldown_until = now + CFG.tilt_cooldown_seconds
            return  # either still moving or just finished — skip this frame

        # During cooldown, do not move or update the servo
        if now < self._tilt_cooldown_until:
            return

        # Always compute the exact target angle from face position.
        # No pixel deadband here — even a centred face must correct
        # the tilt if search() left it at a different angle.
        half_frame = fh / 2.0
        desired_angle = _clamp(
            180.0 - (error_y / half_frame) * 30.0,  # ±30° around home
            0.0,
            180.0,
        )

        # Angle deadband — ignore tiny corrections to prevent oscillation
        if abs(desired_angle - self._tilt_angle) < CFG.tilt_angle_deadband:
            return

        # Commit: command the servo to the new angle
        self._tilt_angle = desired_angle
        self._apply_tilt()
        self._tilt_moving_since = now

    def search(self) -> None:
        """Sweep pan and tilt servos back and forth when no face detected.

        Both servos sweep slowly to find a face. Pan sweeps ±30° around neutral;
        tilt sweeps 150°–180° (downward from front-facing home).
        """
        now = time.time()

        # Pan: continuous rotation sweep
        pan_sweep = 30 * math.sin(now * 0.5)
        pan_pulse = NEUTRAL_US + (pan_sweep / 60.0) * (PULSE_MAX_US - NEUTRAL_US)
        self._set_pan_pulse(pan_pulse)

        # Tilt: sweep 90° ↔ 180° back and forth to find a face
        tilt_sweep = 45 * math.sin(now * 0.3)          # −45 .. +45
        target_tilt = _clamp(135.0 + tilt_sweep, 90.0, 180.0)
        if abs(self._tilt_angle - target_tilt) > 0.5:
            self._tilt_angle = target_tilt
            self._apply_tilt()

    def centre(self) -> None:
        """Centre both servos — stop pan, tilt to 180° (front-facing)."""
        self._set_pan_pulse(NEUTRAL_US)
        self._tilt_angle = 180.0
        self._apply_tilt()

    def release(self) -> None:
        """Stop PWM and release GPIO."""
        # Stop pan servo
        if self._pigpio_pi is not None:
            self._pigpio_pi.set_servo_pulsewidth(CFG.servo_pan_gpio, 0)  # release pulse
            self._pigpio_pi.stop()
            self._pigpio_pi = None
        elif self._has_gpio and self._pan_pwm is not None:
            self._pan_pwm.ChangeDutyCycle(_pulse_to_duty(NEUTRAL_US))

        if self._has_gpio and self._gpio is not None:
            # Centre tilt
            if self._tilt_pwm is not None:
                self._tilt_pwm.ChangeDutyCycle(_pulse_to_duty(NEUTRAL_US))

            import time
            time.sleep(0.1)

            if self._pan_pwm is not None:
                self._pan_pwm.stop()
                self._pan_pwm = None
            if self._tilt_pwm is not None:
                self._tilt_pwm.stop()
                self._tilt_pwm = None

            self._gpio.output(CFG.servo_pan_gpio, False)
            self._gpio.output(CFG.servo_tilt_gpio, False)
            self._gpio.cleanup([CFG.servo_pan_gpio, CFG.servo_tilt_gpio])
        logger.info("PanTilt released")

    # ── Private helpers ─────────────────────────────────────

    def _set_pan_pulse(self, pulse_us: float) -> None:
        """Set pan servo pulse width (continuous rotation: speed/direction)."""
        clamped = _clamp(pulse_us, PULSE_MIN_US, PULSE_MAX_US)
        if self._pigpio_pi is not None:
            self._pigpio_pi.set_servo_pulsewidth(CFG.servo_pan_gpio, clamped)
        elif self._has_gpio and self._pan_pwm is not None:
            duty = _pulse_to_duty(clamped)
            self._pan_pwm.ChangeDutyCycle(duty)

    def _apply_tilt(self) -> None:
        """Apply current tilt angle to the servo."""
        pulse = _angle_to_pulse(self._tilt_angle)
        duty = _pulse_to_duty(pulse)
        if self._has_gpio and self._tilt_pwm is not None:
            self._tilt_pwm.ChangeDutyCycle(duty)

    def _stop_tilt_pwm(self) -> None:
        """Stop tilt PWM signal to eliminate servo jitter.

        Setting duty cycle to 0 keeps the GPIO pin LOW (no pulses).
        The MG90S holds its position mechanically via gear friction.
        """
        if self._has_gpio and self._tilt_pwm is not None:
            self._tilt_pwm.ChangeDutyCycle(0)

    @property
    def angles(self) -> tuple[float, float]:
        """Return (pan_pulse_us, tilt_angle_deg)."""
        return 0.0, self._tilt_angle


# ── Module-level helpers ────────────────────────────────────

def _pulse_to_duty(pulse_us: float) -> float:
    """Convert pulse width in µs → PWM duty cycle (%)."""
    return pulse_us / PWM_PERIOD_US * 100.0


def _angle_to_pulse(angle: float) -> int:
    """Convert physical servo angle (0–180°) → pulse width in µs."""
    norm = (angle - TILT_MIN_DEG) / (TILT_MAX_DEG - TILT_MIN_DEG)
    return int(PULSE_MIN_US + norm * (PULSE_MAX_US - PULSE_MIN_US))


def _error_to_pan_pulse(error_x: int, frame_width: int) -> float:
    """Convert horizontal pixel error to pan servo pulse width.

    error_x > 0 → face right → pan right → pulse < 1500 (spin right)
    error_x < 0 → face left  → pan left  → pulse > 1500 (spin left)
    """
    max_error = frame_width / 2
    norm = max(-1.0, min(1.0, error_x / max_error))

    # Asymmetric range: reverse (left) needs wider offset to overcome friction
    if norm >= 0:
        # Pan right: 1300 → 500 µs
        return 1300.0 - norm * 800.0
    else:
        # Pan left: 1800 → 2500 µs (wider range to overcome friction)
        return 1800.0 + abs(norm) * 700.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
