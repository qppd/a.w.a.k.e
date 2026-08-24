"""S.A.F.E. 2.0 — Camera Capture Module"""
from __future__ import annotations

import logging

import cv2
import numpy as np

from .config import CFG

logger = logging.getLogger(__name__)


class Camera:

    def __init__(self) -> None:
        self._cap = None
        self._picamera = None
        self._use_picamera = False

    def init(self) -> None:
        if self._is_raspberry_pi():
            self._init_picamera2()
        else:
            self._init_opencv()

    def read(self) -> np.ndarray | None:
        if self._use_picamera and self._picamera is not None:
            return self._picamera.capture_array("main")
        if self._cap is not None:
            ok, frame = self._cap.read()
            return frame if ok else None
        return None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._picamera is not None:
            self._picamera.stop()
            self._picamera = None
        logger.info("Camera released")

    def _is_raspberry_pi(self) -> bool:
        try:
            with open("/proc/cpuinfo", "r") as f:
                return "Raspberry Pi" in f.read()
        except FileNotFoundError:
            return False

    def _init_picamera2(self) -> None:
        try:
            from picamera2 import Picamera2

            self._picamera = Picamera2()
            config = self._picamera.create_preview_configuration(
                main={
                    "size": (CFG.camera_width, CFG.camera_height),
                    "format": "RGB888",
                }
            )
            self._picamera.configure(config)
            self._picamera.start()
            self._use_picamera = True
            logger.info(
                "picamera2 initialised (%dx%d)",
                CFG.camera_width,
                CFG.camera_height,
            )
        except ImportError:
            logger.warning("picamera2 not found — falling back to OpenCV")
            self._init_opencv()

    def _init_opencv(self) -> None:
        self._cap = cv2.VideoCapture(CFG.camera_index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CFG.camera_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CFG.camera_height)
        self._cap.set(cv2.CAP_PROP_FPS, CFG.camera_fps)
        if not self._cap.isOpened():
            logger.error("Failed to open camera index %d", CFG.camera_index)
        else:
            logger.info("OpenCV camera initialised (%dx%d)", CFG.camera_width, CFG.camera_height)
