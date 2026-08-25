"""A.W.A.K.E. 2.0 — Configuration & Thresholds"""
from dataclasses import dataclass


@dataclass
class Config:
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    camera_index: int = 0

    servo_pan_gpio: int = 12
    servo_tilt_gpio: int = 13
    buzzer_gpio: int = 17
    ir_led_gpio: int = 6
    vibration_gpio: int = 26

    pan_min_angle: float = -60.0
    pan_max_angle: float = 60.0
    tilt_min_angle: float = -30.0
    tilt_max_angle: float = 30.0
    servo_min_pulse_us: int = 500
    servo_max_pulse_us: int = 2500

    pan_kp: float = 0.008
    tilt_kp: float = 0.008
    pan_tilt_deadband: int = 30

    ear_threshold: float = 0.20
    closed_frame_threshold: int = 45

    perclos_window_seconds: float = 60.0
    perclos_threshold: float = 0.20

    drowsy_score_threshold: int = 1

    alarm_cooldown_seconds: float = 5.0
    alarm_buzzer_freq: int = 1000

    headless: bool = False

    log_dir: str = "logs"
    log_file: str = "logs/drowsiness_log.csv"


CFG = Config()
