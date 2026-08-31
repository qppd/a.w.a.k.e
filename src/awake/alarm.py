"""A.W.A.K.E. 2.0 — Alarm Module

GPIO pins (BCM):
  Buzzer    → GPIO 17  — Software PWM (passive piezo)
  Vibration → GPIO 26  — Digital HIGH/LOW
  IR LED    → GPIO 6   — Digital HIGH/LOW (via MOSFET)

When drowsy:  buzzer sounds + vibration on + IR LED on
When alert:   all off
"""
from __future__ import annotations

import logging
import sys
import time
import threading

from .config import CFG

logger = logging.getLogger(__name__)


class Alarm:

    def __init__(self) -> None:
        self._gpio = None
        self._buzzer_pwm = None
        self._last_trigger: float = 0.0
        self._active: bool = False
        self._beep_thread: threading.Thread | None = None
        self._beep_stop = threading.Event()

    # ── Init ────────────────────────────────────────────────

    def init(self) -> None:
        try:
            import RPi.GPIO as gpio
            gpio.setmode(gpio.BCM)

            # Buzzer — software PWM at alarm frequency, start silent (0% duty)
            gpio.setup(CFG.buzzer_gpio, gpio.OUT, initial=gpio.LOW)
            self._buzzer_pwm = gpio.PWM(CFG.buzzer_gpio, CFG.alarm_buzzer_freq)
            self._buzzer_pwm.start(0)

            # Vibration motor — digital on/off
            gpio.setup(CFG.vibration_gpio, gpio.OUT, initial=gpio.LOW)

            # IR LED — digital on/off (via MOSFET gate)
            gpio.setup(CFG.ir_led_gpio, gpio.OUT, initial=gpio.LOW)

            self._gpio = gpio
            logger.info(
                "Alarm GPIO initialised (buzzer=%d %dHz, vibration=%d, ir_led=%d)",
                CFG.buzzer_gpio, CFG.alarm_buzzer_freq,
                CFG.vibration_gpio, CFG.ir_led_gpio,
            )
        except (ImportError, RuntimeError):
            logger.warning("RPi.GPIO unavailable — alarm will use system beep")
            self._gpio = None

    # ── Trigger / Clear ─────────────────────────────────────

    def trigger(self) -> None:
        """Activate alarm: buzzer + vibration + IR LED."""
        now = time.time()
        if now - self._last_trigger < CFG.alarm_cooldown_seconds:
            return
        self._last_trigger = now
        self._active = True
        logger.warning("ALARM TRIGGERED")

        if self._gpio is not None:
            # Passive buzzer: 50% duty at CFG.alarm_buzzer_freq → audible tone
            self._buzzer_pwm.ChangeDutyCycle(50)
            # Vibration motor ON
            self._gpio.output(CFG.vibration_gpio, True)
            # IR LED ON
            self._gpio.output(CFG.ir_led_gpio, True)
        else:
            self._start_beep()

    def clear(self) -> None:
        """Deactivate alarm: silence buzzer + vibration off + LED off."""
        if not self._active:
            return
        self._active = False
        logger.info("Alarm cleared")

        if self._gpio is not None:
            # Buzzer silent (0% duty)
            self._buzzer_pwm.ChangeDutyCycle(0)
            # Vibration motor OFF
            self._gpio.output(CFG.vibration_gpio, False)
            # IR LED OFF
            self._gpio.output(CFG.ir_led_gpio, False)
        else:
            self._stop_beep()

    def release(self) -> None:
        """Stop all outputs and release GPIO."""
        self.clear()
        if self._gpio is not None:
            if self._buzzer_pwm is not None:
                self._buzzer_pwm.stop()
                self._buzzer_pwm = None
            self._gpio.output(CFG.buzzer_gpio, False)
            self._gpio.output(CFG.vibration_gpio, False)
            self._gpio.output(CFG.ir_led_gpio, False)
            self._gpio.cleanup([
                CFG.buzzer_gpio,
                CFG.vibration_gpio,
                CFG.ir_led_gpio,
            ])
        logger.info("Alarm released")

    @property
    def is_active(self) -> bool:
        return self._active

    # ── System beep fallback (no GPIO on dev machine) ──────

    def _start_beep(self) -> None:
        self._beep_stop.clear()
        if self._beep_thread is not None and self._beep_thread.is_alive():
            return
        self._beep_thread = threading.Thread(target=self._beep_loop, daemon=True)
        self._beep_thread.start()

    def _stop_beep(self) -> None:
        self._beep_stop.set()

    def _beep_loop(self) -> None:
        while not self._beep_stop.is_set():
            self._system_beep()
            self._beep_stop.wait(timeout=0.5)

    @staticmethod
    def _system_beep() -> None:
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(1000, 300)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(
                    ["afplay", "/System/Library/Sounds/Glass.aiff"],
                    timeout=1, capture_output=True,
                )
            else:
                print("\a", end="", flush=True)
        except Exception:
            print("\a", end="", flush=True)
