"""A.W.A.K.E. 2.0 — Eye Tracker Module"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

from .config import CFG

logger = logging.getLogger(__name__)

LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]


def _euclidean(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


@dataclass
class EyeResult:
    ear: float
    left_ear: float
    right_ear: float
    perclos: float
    is_closed: bool


class EyeTracker:

    def __init__(self) -> None:
        self._closed_frames: int = 0
        self._total_frames: int = 0
        self._ear_history: deque[tuple[float, bool]] = deque()
        self._window_start: float = time.time()

    def init(self) -> None:
        logger.info(
            "EyeTracker initialised (EAR thresh=%.3f, frame thresh=%d)",
            CFG.ear_threshold,
            CFG.closed_frame_threshold,
        )

    def compute(
        self,
        landmarks: np.ndarray,
        frame_size: tuple[int, int],
    ) -> EyeResult:
        w, h = frame_size
        left_pts = landmarks[LEFT_EYE_IDX, :2] * np.array([w, h])
        right_pts = landmarks[RIGHT_EYE_IDX, :2] * np.array([w, h])
        left_ear = self._ear(left_pts)
        right_ear = self._ear(right_pts)
        ear = (left_ear + right_ear) / 2.0
        is_closed = ear < CFG.ear_threshold
        self._update_perclos(is_closed)
        perclos = self._compute_perclos()
        return EyeResult(
            ear=ear,
            left_ear=left_ear,
            right_ear=right_ear,
            perclos=perclos,
            is_closed=is_closed,
        )

    def reset(self) -> None:
        self._closed_frames = 0
        self._total_frames = 0
        self._ear_history.clear()
        self._window_start = time.time()

    @staticmethod
    def _ear(pts: np.ndarray) -> float:
        p1, p2, p3, p4, p5, p6 = pts
        vertical = _euclidean(p2, p6) + _euclidean(p3, p5)
        horizontal = _euclidean(p1, p4)
        if horizontal < 1e-6:
            return 0.0
        return float(vertical / (2.0 * horizontal))

    def _update_perclos(self, is_closed: bool) -> None:
        now = time.time()
        self._total_frames += 1
        if is_closed:
            self._closed_frames += 1
        self._ear_history.append((now, is_closed))
        window_end = now - CFG.perclos_window_seconds
        while self._ear_history and self._ear_history[0][0] < window_end:
            old_ts, old_closed = self._ear_history.popleft()
            self._total_frames -= 1
            if old_closed:
                self._closed_frames -= 1
        self._closed_frames = max(0, self._closed_frames)
        self._total_frames = max(1, self._total_frames)

    def _compute_perclos(self) -> float:
        if self._total_frames == 0:
            return 0.0
        return self._closed_frames / self._total_frames

    def consecutive_closed_count(self) -> int:
        return self._closed_frames

    def perclos_value(self) -> float:
        return self._compute_perclos()
