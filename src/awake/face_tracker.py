"""A.W.A.K.E. 2.0 — Face Tracker Module"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

logger = logging.getLogger(__name__)

_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "models", "face_landmarker.task")


@dataclass
class FaceResult:
    bbox: tuple[int, int, int, int]
    landmarks: np.ndarray
    bbox_center: tuple[int, int]
    frame_size: tuple[int, int]


def model_exists() -> bool:
    """Check if the face landmarker model file exists locally."""
    return os.path.exists(_MODEL_PATH)


def _download_model() -> str:
    if os.path.exists(_MODEL_PATH):
        return _MODEL_PATH
    os.makedirs(os.path.dirname(_MODEL_PATH), exist_ok=True)
    logger.info("Downloading face landmarker model to %s …", _MODEL_PATH)
    try:
        import urllib.request
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        logger.info("Model downloaded.")
    except Exception as exc:
        logger.error(
            "Failed to download model (no internet?): %s\n"
            "  Download manually and place at: %s\n"
            "  URL: %s",
            exc, _MODEL_PATH, _MODEL_URL,
        )
        raise SystemExit(1) from exc
    return _MODEL_PATH


class FaceTracker:

    def __init__(self) -> None:
        self._landmarker = None

    def init(self) -> None:
        if not model_exists():
            logger.warning(
                "Face model not found at %s — attempting download…", _MODEL_PATH
            )
        model_path = _download_model()
        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarker = mp.tasks.vision.FaceLandmarker
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)
        logger.info("FaceTracker initialised (MediaPipe FaceLandmarker)")

    def detect(self, frame: np.ndarray) -> FaceResult | None:
        if self._landmarker is None:
            return None
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None
        face_lm = result.face_landmarks[0]
        landmarks = np.array(
            [[lm.x, lm.y, lm.z] for lm in face_lm],
            dtype=np.float32,
        )
        xs = (landmarks[:, 0] * w).astype(int)
        ys = (landmarks[:, 1] * h).astype(int)
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        bbox = (x_min, y_min, x_max - x_min, y_max - y_min)
        cx = (x_min + x_max) // 2
        cy = (y_min + y_max) // 2
        return FaceResult(
            bbox=bbox,
            landmarks=landmarks,
            bbox_center=(cx, cy),
            frame_size=(w, h),
        )

    def draw(self, frame: np.ndarray, face: FaceResult) -> None:
        x, y, w, h = face.bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    def release(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
        logger.info("FaceTracker released")
