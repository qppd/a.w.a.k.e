"""A.W.A.K.E. 2.0 — Interactive Calibration Mode"""
from __future__ import annotations

import csv
import logging
import os
import time
from dataclasses import dataclass

import cv2
import numpy as np

from .camera import Camera
from .config import CFG
from .eye_tracker import EyeTracker
from .face_tracker import FaceTracker

logger = logging.getLogger(__name__)

KEY_OPEN = ord("o")
KEY_CLOSED = ord("c")
KEY_DONE = ord("s")
KEY_QUIT = ord("q")
KEY_TOGGLE_LIVE = ord("l")


@dataclass
class CalibrationSample:
    ear: float
    left_ear: float
    right_ear: float
    label: str
    timestamp: float


@dataclass
class CalibrationResult:
    suggested_ear_threshold: float
    suggested_frame_threshold: int
    open_mean: float
    open_std: float
    closed_mean: float
    closed_std: float
    num_open: int
    num_closed: int
    separation: float


class Calibration:

    def __init__(self) -> None:
        self.camera = Camera()
        self.face_tracker = FaceTracker()
        self.eye_tracker = EyeTracker()
        self._samples: list[CalibrationSample] = []
        self._current_ear: float = 0.0
        self._current_label: str = ""
        self._show_guide: bool = True

    def init(self) -> None:
        self.camera.init()
        self.face_tracker.init()
        self.eye_tracker.init()
        logger.info("Calibration module initialised")

    def run(self, sample_target: int = 30) -> CalibrationResult | None:
        logger.info(
            "Calibration started — collect open & closed eye samples. "
            "Keys: [O]pen  [C]losed  [S]ave  [Q]uit"
        )

        open_samples: list[float] = []
        closed_samples: list[float] = []

        while True:
            frame = self.camera.read()
            if frame is None:
                time.sleep(0.05)
                continue

            face = self.face_tracker.detect(frame)
            ear = 0.0
            if face is not None:
                eye = self.eye_tracker.compute(face.landmarks, face.frame_size)
                ear = eye.ear
                self._current_ear = ear
                self.face_tracker.draw(frame, face)

            self._draw_hud(frame, len(open_samples), len(closed_samples), sample_target)

            cv2.imshow("A.W.A.K.E. 2.0 — Calibration", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == KEY_QUIT:
                cv2.destroyAllWindows()
                logger.info("Calibration aborted")
                return None

            elif key == KEY_OPEN:
                if face is not None:
                    open_samples.append(ear)
                    self._samples.append(
                        CalibrationSample(ear, eye.left_ear, eye.right_ear, "open", time.time())
                    )
                    logger.info("Sampled OPEN  EAR=%.4f  (%d/%d)", ear, len(open_samples), sample_target)

            elif key == KEY_CLOSED:
                if face is not None:
                    closed_samples.append(ear)
                    self._samples.append(
                        CalibrationSample(ear, eye.left_ear, eye.right_ear, "closed", time.time())
                    )
                    logger.info("Sampled CLOSED EAR=%.4f  (%d/%d)", ear, len(closed_samples), sample_target)

            elif key == KEY_TOGGLE_LIVE:
                self._show_guide = not self._show_guide

            elif key == KEY_DONE:
                break

            if sample_target > 0 and len(open_samples) >= sample_target and len(closed_samples) >= sample_target:
                logger.info("Sample target reached (%d per class)", sample_target)
                break

        cv2.destroyAllWindows()

        if len(open_samples) < 2 or len(closed_samples) < 2:
            logger.warning(
                "Not enough samples (open=%d, closed=%d). Need ≥2 each.",
                len(open_samples),
                len(closed_samples),
            )
            return None

        result = self._compute_thresholds(open_samples, closed_samples)
        self._print_result(result)
        self._save_csv()
        return result

    @staticmethod
    def _compute_thresholds(
        open_ears: list[float], closed_ears: list[float]
    ) -> CalibrationResult:
        open_arr = np.array(open_ears)
        closed_arr = np.array(closed_ears)

        open_mean = float(np.mean(open_arr))
        open_std = float(np.std(open_arr))
        closed_mean = float(np.mean(closed_arr))
        closed_std = float(np.std(closed_arr))

        open_edge = open_mean - 2 * open_std
        closed_edge = closed_mean + 2 * closed_std

        threshold = (open_edge + closed_edge) / 2.0
        threshold = max(0.05, min(0.40, threshold))

        separation = open_mean - closed_mean

        suggested_frame_threshold = 45

        return CalibrationResult(
            suggested_ear_threshold=round(threshold, 4),
            suggested_frame_threshold=suggested_frame_threshold,
            open_mean=round(open_mean, 4),
            open_std=round(open_std, 4),
            closed_mean=round(closed_mean, 4),
            closed_std=round(closed_std, 4),
            num_open=len(open_ears),
            num_closed=len(closed_ears),
            separation=round(separation, 4),
        )

    def _draw_hud(
        self,
        frame: np.ndarray,
        open_count: int,
        closed_count: int,
        target: int,
    ) -> None:
        h, w = frame.shape[:2]

        cv2.rectangle(frame, (0, 0), (w, 90), (40, 40, 40), -1)
        cv2.putText(
            frame, "A.W.A.K.E. 2.0 — Calibration Mode",
            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2,
        )

        ear_colour = (0, 255, 0) if self._current_ear >= CFG.ear_threshold else (0, 0, 255)
        cv2.putText(
            frame, f"EAR: {self._current_ear:.4f}",
            (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, ear_colour, 2,
        )

        cv2.putText(
            frame,
            f"Open: {open_count}/{target}   Closed: {closed_count}/{target}",
            (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
        )

        y_start = h - 80
        cv2.rectangle(frame, (0, y_start), (w, h), (40, 40, 40), -1)
        instructions = [
            "[O] Mark as OPEN     [C] Mark as CLOSED     [S] Save & Exit     [Q] Quit",
            "[L] Toggle EAR bar",
        ]
        for i, text in enumerate(instructions):
            cv2.putText(
                frame, text,
                (10, y_start + 25 + i * 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1,
            )

        if self._show_guide and len(self._samples) > 1:
            self._draw_ear_bar(frame, open_count, closed_count)

    def _draw_ear_bar(
        self, frame: np.ndarray, open_count: int, closed_count: int
    ) -> None:
        h, w = frame.shape[:2]
        bar_x, bar_y = 10, 100
        bar_w, bar_h = w - 20, 60

        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (30, 30, 30), -1)

        max_bars = min(len(self._samples), bar_w - 4)
        recent = self._samples[-max_bars:]

        for i, sample in enumerate(recent):
            bx = bar_x + 2 + i
            bar_fill = int((sample.ear / 0.5) * bar_h)
            bar_fill = max(1, min(bar_h, bar_fill))
            colour = (0, 180, 0) if sample.label == "open" else (0, 0, 200)
            by_top = bar_y + bar_h - bar_fill
            cv2.line(frame, (bx, bar_y + bar_h), (bx, by_top), colour, 1)

        thresh_y = bar_y + bar_h - int((CFG.ear_threshold / 0.5) * bar_h)
        thresh_y = max(bar_y, min(bar_y + bar_h, thresh_y))
        cv2.line(frame, (bar_x, thresh_y), (bar_x + bar_w, thresh_y), (0, 255, 255), 1)
        cv2.putText(
            frame, f"T={CFG.ear_threshold:.3f}",
            (bar_x + bar_w + 5, thresh_y + 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1,
        )

    @staticmethod
    def _print_result(result: CalibrationResult) -> None:
        print("\n" + "=" * 55)
        print("  CALIBRATION RESULTS")
        print("=" * 55)
        print(f"  Open eye EAR  : {result.open_mean:.4f} ± {result.open_std:.4f}  ({result.num_open} samples)")
        print(f"  Closed eye EAR: {result.closed_mean:.4f} ± {result.closed_std:.4f}  ({result.num_closed} samples)")
        print(f"  Separation    : {result.separation:.4f}")
        print("-" * 55)
        print(f"  ➤ Suggested EAR threshold     : {result.suggested_ear_threshold}")
        print(f"  ➤ Suggested frame threshold   : {result.suggested_frame_threshold}")
        print("-" * 55)
        print("  Update config.py with these values:")
        print(f'    ear_threshold = {result.suggested_ear_threshold}')
        print(f'    closed_frame_threshold = {result.suggested_frame_threshold}')
        print("=" * 55 + "\n")
        logger.info(
            "Calibration complete: EAR_thresh=%.4f  frame_thresh=%d",
            result.suggested_ear_threshold,
            result.suggested_frame_threshold,
        )

    def _save_csv(self) -> None:
        os.makedirs(CFG.log_dir, exist_ok=True)
        path = os.path.join(CFG.log_dir, "calibration_samples.csv")
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "ear", "left_ear", "right_ear", "label"])
            for s in self._samples:
                writer.writerow([
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.timestamp)),
                    f"{s.ear:.4f}",
                    f"{s.left_ear:.4f}",
                    f"{s.right_ear:.4f}",
                    s.label,
                ])
        logger.info("Calibration samples saved to %s", path)

    def release(self) -> None:
        self.eye_tracker.reset()
        self.face_tracker.release()
        self.camera.release()
        cv2.destroyAllWindows()
