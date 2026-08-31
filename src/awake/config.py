"""A.W.A.K.E. 2.0 — Configuration & Thresholds"""
from dataclasses import dataclass


@dataclass
class Config:
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    camera_index: int = 0
    camera_source: str | None = None  # video file path overrides camera_index
    camera_rotate_180: bool = True   # rotate frame 180° (upside-down mount)

    servo_pan_gpio: int = 12
    servo_tilt_gpio: int = 13
    buzzer_gpio: int = 17
    ir_led_gpio: int = 6
    vibration_gpio: int = 26

    pan_min_angle: float = -60.0
    pan_max_angle: float = 60.0
    tilt_min_angle: float = 135.0   # minimum working angle (°)
    tilt_max_angle: float = 175.0   # maximum working angle (°)
    tilt_centre_angle: float = 165.0  # front-facing / home angle (°)
    servo_min_pulse_us: int = 500
    servo_max_pulse_us: int = 2500

    pan_kp: float = 0.008
    tilt_kp: float = 0.008
    pan_tilt_deadband: int = 30
    tilt_angle_deadband: float = 2.0   # min angle change (°) to trigger tilt servo
    tilt_cooldown_seconds: float = 5.0 # pause after each servo movement (s)
    tilt_move_time: float = 0.3        # time to let servo reach position before stopping PWM (s)

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
