"""A.W.A.K.E. 2.0 — Drowsiness Decision Logic"""
from __future__ import annotations

import logging

from .config import CFG
from .eye_tracker import EyeResult

logger = logging.getLogger(__name__)


class DrowsinessDetector:

    def __init__(self) -> None:
        self._is_drowsy: bool = False

    def init(self) -> None:
        logger.info("DrowsinessDetector initialised")

    def analyze(self, eye: EyeResult) -> bool:
        score = 0

        if eye.perclos >= CFG.perclos_threshold:
            score += 1
            logger.debug("PERCLOS=%.3f >= %.3f  (+1)", eye.perclos, CFG.perclos_threshold)

        self._is_drowsy = score >= CFG.drowsy_score_threshold

        if self._is_drowsy:
            logger.warning(
                "DROWSINESS DETECTED — EAR=%.3f  PERCLOS=%.3f",
                eye.ear,
                eye.perclos,
            )

        return self._is_drowsy

    def reset(self) -> None:
        self._is_drowsy = False

    @property
    def is_drowsy(self) -> bool:
        return self._is_drowsy
