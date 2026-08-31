"""A.W.A.K.E. 2.0 — Main Entry Point"""
from __future__ import annotations

import csv
import logging
import os
import sys
import time
from datetime import datetime

import cv2

from .alarm import Alarm
from .camera import Camera
from .config import CFG
from .drowsiness import DrowsinessDetector
from .eye_tracker import EyeTracker
from .face_tracker import FaceTracker
from .pan_tilt import PanTilt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("awake2")


class AwakeApp:

    def __init__(self) -> None:
        self.camera = Camera()
        self.face_tracker = FaceTracker()
        self.eye_tracker = EyeTracker()
        self.pan_tilt = PanTilt()
        self.drowsiness = DrowsinessDetector()
        self.alarm = Alarm()
        self._log_file = None
        self._log_writer = None

    def run(self) -> None:
        logger.info("A.W.A.K.E. 2.0 starting …")
        self._init_all()
        self._open_log()
        try:
            self._loop()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self._cleanup()

    def _init_all(self) -> None:
        self.camera.init()
        self.face_tracker.init()
        self.eye_tracker.init()
        self.pan_tilt.init()
        self.drowsiness.init()
        self.alarm.init()
        os.makedirs(CFG.log_dir, exist_ok=True)
        if CFG.headless:
            print("\n" + "=" * 50)
            print("  A.W.A.K.E. 2.0 — Headless Mode (no display)")
            print("  Press Ctrl+C to stop")
            print("=" * 50 + "\n")

    def _loop(self) -> None:
        fps_counter = _FPSCounter()

        while True:
            frame = self.camera.read()
            if frame is None:
                logger.warning("No frame — retrying")
                time.sleep(0.1)
                continue

            fps = fps_counter.tick()
            face = self.face_tracker.detect(frame)

            if face is not None:
                self.pan_tilt.update(face.bbox_center, face.frame_size)
                eye = self.eye_tracker.compute(face.landmarks, face.frame_size)
                is_drowsy = self.drowsiness.analyze(eye)

                if is_drowsy:
                    self.alarm.trigger()
                else:
                    self.alarm.clear()

                self._log_row(fps, eye.ear, eye.perclos, eye.is_closed, is_drowsy)

                if self._debug_enabled():
                    self._draw_debug(frame, face, eye, fps, is_drowsy)
            else:
                self.pan_tilt.search()
                self.alarm.clear()
                self.eye_tracker.reset()
                self._log_row(fps, 0.0, 0.0, False, False)

            if CFG.headless and face is not None:
                status = "DROWSY!" if is_drowsy else "Alert"
                alarm_str = " [ALARM]" if self.alarm.is_active else ""
                print(
                    f"\r  EAR={eye.ear:.3f}  PERCLOS={eye.perclos:.3f}  "
                    f"FPS={fps:.0f}  [{status}]{alarm_str}    ",
                    end="", flush=True,
                )

            if self._debug_enabled():
                cv2.imshow("A.W.A.K.E. 2.0", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    def _open_log(self) -> None:
        write_header = not os.path.exists(CFG.log_file)
        self._log_file = open(CFG.log_file, "a", newline="")
        self._log_writer = csv.writer(self._log_file)
        if write_header:
            self._log_writer.writerow([
                "timestamp", "fps", "ear", "perclos",
                "eyes_closed", "is_drowsy",
            ])

    def _log_row(
        self, fps: float, ear: float, perclos: float,
        closed: bool, drowsy: bool,
    ) -> None:
        if self._log_writer is None:
            return
        self._log_writer.writerow([
            datetime.now().isoformat(),
            f"{fps:.1f}",
            f"{ear:.4f}",
            f"{perclos:.4f}",
            int(closed),
            int(drowsy),
        ])
        self._log_file.flush()

    def _cleanup(self) -> None:
        logger.info("Shutting down …")
        self.alarm.release()
        self.pan_tilt.release()
        self.face_tracker.release()
        self.camera.release()
        if self._log_file:
            self._log_file.close()
        if self._debug_enabled():
            cv2.destroyAllWindows()
        logger.info("A.W.A.K.E. 2.0 stopped")

    @staticmethod
    def _debug_enabled() -> bool:
        if CFG.headless:
            return False
        if os.environ.get("DISPLAY") is not None:
            return True
        if sys.platform in ("win32", "darwin"):
            return True
        return False

    @staticmethod
    def _draw_debug(frame, face, eye, fps, drowsy) -> None:
        from .face_tracker import FaceTracker as FT
        FT.draw(None, frame, face)
        colour = (0, 0, 255) if drowsy else (0, 255, 0)
        cv2.putText(
            frame, f"EAR: {eye.ear:.3f}", (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2,
        )
        cv2.putText(
            frame, f"PERCLOS: {eye.perclos:.3f}", (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2,
        )
        cv2.putText(
            frame, f"FPS: {fps:.1f}", (10, 75),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
        )
        status = "DROWSY!" if drowsy else "Alert"
        cv2.putText(
            frame, status, (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2,
        )


class _FPSCounter:

    def __init__(self) -> None:
        self._last = time.time()
        self._fps = 0.0

    def tick(self) -> float:
        now = time.time()
        dt = now - self._last
        self._last = now
        if dt > 0:
            self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt)
        return self._fps


def main() -> None:
    import argparse
    from .config import CFG

    parser = argparse.ArgumentParser(description="A.W.A.K.E. 2.0 — Drowsiness Detection")
    parser.add_argument(
        "--calibrate", action="store_true",
        help="Run interactive EAR threshold calibration instead of detection",
    )
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Webcam index (default: 0)",
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help="Video file path to use instead of a webcam",
    )
    parser.add_argument(
        "--samples", type=int, default=30,
        help="Number of samples per class during calibration (default: 30)",
    )
    parser.add_argument(
        "--width", type=int, default=CFG.camera_width,
        help=f"Camera width (default: {CFG.camera_width})",
    )
    parser.add_argument(
        "--height", type=int, default=CFG.camera_height,
        help=f"Camera height (default: {CFG.camera_height})",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run without display (SSH / Pi headless) — logs to terminal",
    )
    parser.add_argument(
        "--no-rotate", action="store_true",
        help="Disable 180° frame rotation",
    )
    args = parser.parse_args()

    CFG.camera_index = args.camera
    CFG.camera_width = args.width
    CFG.camera_height = args.height
    CFG.headless = args.headless
    CFG.camera_rotate_180 = not args.no_rotate
    if args.source:
        CFG.camera_source = args.source

    if args.calibrate:
        from .calibration import Calibration
        cal = Calibration()
        try:
            cal.init()
            result = cal.run(sample_target=args.samples)
            if result is not None:
                print("\nCalibration complete. Update config.py with the suggested values.")
            else:
                print("\nCalibration aborted or insufficient samples.")
        finally:
            cal.release()
    else:
        app = AwakeApp()
        app.run()


if __name__ == "__main__":
    main()
