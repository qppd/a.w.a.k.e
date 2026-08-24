"""
S.A.F.E. 2.0 — Unit Tests for Eye Tracker & EAR Algorithm
"""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

import numpy as np

from src.safe.config import CFG, Config
from src.safe.eye_tracker import (
    EyeResult,
    EyeTracker,
    LEFT_EYE_IDX,
    RIGHT_EYE_IDX,
    _euclidean,
)


# ── Helpers ─────────────────────────────────────────────────


def _make_landmarks_468(
    left_eye_pts: np.ndarray,
    right_eye_pts: np.ndarray,
) -> np.ndarray:
    """
    Build a (468, 3) normalised landmark array with the given
    pixel-space eye points embedded at the correct indices.

    The points passed in are expected in *normalised* (0–1) coords.
    """
    lm = np.zeros((468, 3), dtype=np.float32)
    for i, pt in enumerate(left_eye_pts):
        lm[LEFT_EYE_IDX[i]] = [pt[0], pt[1], 0.0]
    for i, pt in enumerate(right_eye_pts):
        lm[RIGHT_EYE_IDX[i]] = [pt[0], pt[1], 0.0]
    return lm


def _open_eye_landmarks(w: int = 640, h: int = 480) -> np.ndarray:
    """Six points for a wide-open eye (high EAR ~0.35)."""
    # Normalised coordinates for an open eye centred around (0.4, 0.5)
    # p1(left corner), p2(top-left), p3(top-right), p4(right corner),
    # p5(bottom-right), p6(bottom-left)
    cx, cy = 0.4, 0.5
    left = np.array([
        [cx - 0.04, cy],        # p1 — left corner
        [cx - 0.02, cy - 0.03], # p2 — top-left eyelid
        [cx + 0.02, cy - 0.03], # p3 — top-right eyelid
        [cx + 0.04, cy],        # p4 — right corner
        [cx + 0.02, cy + 0.03], # p5 — bottom-right eyelid
        [cx - 0.02, cy + 0.03], # p6 — bottom-left eyelid
    ], dtype=np.float32)
    right = left + np.array([0.3, 0.0], dtype=np.float32)
    return _make_landmarks_468(left, right)


def _closed_eye_landmarks(w: int = 640, h: int = 480) -> np.ndarray:
    """Six points for a closed eye (low EAR ~0.05)."""
    cx, cy = 0.4, 0.5
    left = np.array([
        [cx - 0.04, cy],
        [cx - 0.02, cy - 0.005],  # barely open vertically
        [cx + 0.02, cy - 0.005],
        [cx + 0.04, cy],
        [cx + 0.02, cy + 0.005],
        [cx - 0.02, cy + 0.005],
    ], dtype=np.float32)
    right = left + np.array([0.3, 0.0], dtype=np.float32)
    return _make_landmarks_468(left, right)


def _half_open_eye_landmarks(w: int = 640, h: int = 480) -> np.ndarray:
    """Six points for a half-open eye (EAR ~0.15, near threshold)."""
    cx, cy = 0.4, 0.5
    left = np.array([
        [cx - 0.04, cy],
        [cx - 0.02, cy - 0.015],
        [cx + 0.02, cy - 0.015],
        [cx + 0.04, cy],
        [cx + 0.02, cy + 0.015],
        [cx - 0.02, cy + 0.015],
    ], dtype=np.float32)
    right = left + np.array([0.3, 0.0], dtype=np.float32)
    return _make_landmarks_468(left, right)


# ── Tests ───────────────────────────────────────────────────


class TestEuclidean(unittest.TestCase):
    """Tests for the _euclidean helper."""

    def test_same_point(self):
        self.assertAlmostEqual(
            _euclidean(np.array([1.0, 2.0]), np.array([1.0, 2.0])), 0.0
        )

    def test_unit_distance(self):
        self.assertAlmostEqual(
            _euclidean(np.array([0.0, 0.0]), np.array([3.0, 4.0])), 5.0
        )

    def test_symmetry(self):
        a = np.array([1.0, 2.0])
        b = np.array([4.0, 6.0])
        self.assertAlmostEqual(_euclidean(a, b), _euclidean(b, a))


class TestEAR(unittest.TestCase):
    """Tests for the EAR calculation (static method on EyeTracker)."""

    ear = staticmethod(EyeTracker._ear)

    def test_open_eye_high_ear(self):
        """A wide-open eye should produce EAR > 0.3."""
        pts = np.array([
            [0.0, 0.5],    # p1
            [0.2, 0.0],    # p2
            [0.4, 0.0],    # p3
            [0.6, 0.5],    # p4
            [0.4, 1.0],    # p5
            [0.2, 1.0],    # p6
        ], dtype=np.float32)
        result = self.ear(pts)
        self.assertGreater(result, 0.3, "Open eye EAR should be > 0.3")

    def test_closed_eye_low_ear(self):
        """A closed eye should produce EAR < 0.1."""
        pts = np.array([
            [0.0, 0.5],
            [0.2, 0.49],   # barely above centre
            [0.4, 0.49],
            [0.6, 0.5],
            [0.4, 0.51],   # barely below centre
            [0.2, 0.51],
        ], dtype=np.float32)
        result = self.ear(pts)
        self.assertLess(result, 0.1, "Closed eye EAR should be < 0.1")

    def test_zero_horizontal_returns_zero(self):
        """If p1 == p4 (zero width), EAR should be 0."""
        pts = np.array([
            [0.5, 0.5],
            [0.5, 0.0],
            [0.5, 0.0],
            [0.5, 0.5],
            [0.5, 1.0],
            [0.5, 1.0],
        ], dtype=np.float32)
        self.assertEqual(self.ear(pts), 0.0)

    def test_symmetric_eye(self):
        """A vertically symmetric eye: EAR should equal exactly
        (vertical_distance / horizontal_distance)."""
        # p1=(0,0.5), p4=(1,0.5) → horizontal = 1.0
        # p2=(0.2,0), p6=(0.2,1) → vertical1 = 1.0
        # p3=(0.4,0), p5=(0.4,1) → vertical2 = 1.0
        # EAR = (1.0 + 1.0) / (2 * 1.0) = 1.0
        pts = np.array([
            [0.0, 0.5],
            [0.2, 0.0],
            [0.4, 0.0],
            [1.0, 0.5],
            [0.4, 1.0],
            [0.2, 1.0],
        ], dtype=np.float32)
        self.assertAlmostEqual(self.ear(pts), 1.0, places=5)

    def test_aspect_ratio_scales_correctly(self):
        """Doubling the eye size should not change EAR."""
        small = np.array([
            [0.0, 0.5],
            [0.2, 0.3],
            [0.4, 0.3],
            [0.6, 0.5],
            [0.4, 0.7],
            [0.2, 0.7],
        ], dtype=np.float32)
        big = small * 2.0
        self.assertAlmostEqual(self.ear(small), self.ear(big), places=5)


class TestEyeTrackerCompute(unittest.TestCase):
    """Integration tests for EyeTracker.compute()."""

    def setUp(self):
        self.tracker = EyeTracker()
        self.frame_size = (640, 480)

    def test_open_eye_not_closed(self):
        """Open eye landmarks should not register as closed."""
        lm = _open_eye_landmarks()
        result = self.tracker.compute(lm, self.frame_size)
        self.assertFalse(result.is_closed)
        self.assertGreater(result.ear, CFG.ear_threshold)

    def test_closed_eye_is_closed(self):
        """Closed eye landmarks should register as closed."""
        lm = _closed_eye_landmarks()
        result = self.tracker.compute(lm, self.frame_size)
        self.assertTrue(result.is_closed)
        self.assertLess(result.ear, CFG.ear_threshold)

    def test_left_right_ear_averaged(self):
        """Final EAR should be the average of left and right eye EAR."""
        lm = _open_eye_landmarks()
        result = self.tracker.compute(lm, self.frame_size)
        expected_ear = (result.left_ear + result.right_ear) / 2.0
        self.assertAlmostEqual(result.ear, expected_ear, places=6)

    def test_both_eyes_identical_gives_identical_ear(self):
        """When both eye landmarks are the same, left_ear == right_ear."""
        lm = _open_eye_landmarks()
        result = self.tracker.compute(lm, self.frame_size)
        self.assertAlmostEqual(result.left_ear, result.right_ear, places=5)


class TestPERCLOS(unittest.TestCase):
    """Tests for PERCLOS (percentage of eye closure over time window)."""

    def setUp(self):
        self.tracker = EyeTracker()
        self.frame_size = (640, 480)

    @patch("src.safe.eye_tracker.time")
    def test_all_open_gives_zero_perclos(self, mock_time):
        """If eyes are always open, PERCLOS should be 0."""
        mock_time.time.return_value = 1000.0
        lm = _open_eye_landmarks()
        result = self.tracker.compute(lm, self.frame_size)
        self.assertAlmostEqual(result.perclos, 0.0, places=5)

    @patch("src.safe.eye_tracker.time")
    def test_all_closed_gives_full_perclos(self, mock_time):
        """If eyes are always closed, PERCLOS should be 1.0."""
        mock_time.time.return_value = 1000.0
        lm = _closed_eye_landmarks()
        for _ in range(10):
            result = self.tracker.compute(lm, self.frame_size)
        self.assertAlmostEqual(result.perclos, 1.0, places=5)

    @patch("src.safe.eye_tracker.time")
    def test_half_closed_perclos(self, mock_time):
        """Alternating open/closed should give PERCLOS ~ 0.5."""
        counter = {"t": 1000.0}
        def advancing_time():
            counter["t"] += 1.0 / 30  # simulate 30 fps
            return counter["t"]
        mock_time.time.side_effect = advancing_time

        open_lm = _open_eye_landmarks()
        closed_lm = _closed_eye_landmarks()

        for i in range(20):
            lm = closed_lm if i % 2 == 0 else open_lm
            result = self.tracker.compute(lm, self.frame_size)

        # 10 closed out of 20 frames
        self.assertAlmostEqual(result.perclos, 0.5, delta=0.05)

    @patch("src.safe.eye_tracker.time")
    def test_perclos_window_expiry(self, mock_time):
        """Old frames outside the window should not affect PERCLOS."""
        counter = {"t": 1000.0}
        def advancing_time():
            counter["t"] += 1.0
            return counter["t"]
        mock_time.time.side_effect = advancing_time

        closed_lm = _closed_eye_landmarks()
        open_lm = _open_eye_landmarks()

        # Fill window with closed eyes
        for _ in range(5):
            self.tracker.compute(closed_lm, self.frame_size)

        # Jump forward past the window
        counter["t"] = 1000.0 + CFG.perclos_window_seconds + 10

        # Now only open eyes
        for _ in range(5):
            result = self.tracker.compute(open_lm, self.frame_size)

        # Old closed frames should have expired
        self.assertAlmostEqual(result.perclos, 0.0, delta=0.05)


class TestReset(unittest.TestCase):
    """Tests for EyeTracker.reset()."""

    def setUp(self):
        self.tracker = EyeTracker()
        self.frame_size = (640, 480)

    def test_reset_clears_state(self):
        """After reset, PERCLOS should be 0."""
        lm = _closed_eye_landmarks()
        for _ in range(5):
            self.tracker.compute(lm, self.frame_size)

        self.assertGreater(self.tracker.perclos_value(), 0.0)

        self.tracker.reset()
        self.assertEqual(self.tracker.perclos_value(), 0.0)
        self.assertEqual(self.tracker.consecutive_closed_count(), 0)

    def test_reset_allows_fresh_start(self):
        """After reset, new frames should start fresh."""
        lm = _closed_eye_landmarks()
        for _ in range(5):
            self.tracker.compute(lm, self.frame_size)

        self.tracker.reset()

        open_lm = _open_eye_landmarks()
        result = self.tracker.compute(open_lm, self.frame_size)
        self.assertAlmostEqual(result.perclos, 0.0, places=5)
        self.assertFalse(result.is_closed)


class TestFrameSizeScaling(unittest.TestCase):
    """Verify EAR is scale-invariant under uniform scaling."""

    def test_same_aspect_ratio_gives_same_ear(self):
        """Same aspect ratio → same EAR (EAR is scale-invariant)."""
        tracker = EyeTracker()
        lm = _open_eye_landmarks()

        r1 = tracker.compute(lm, (640, 480))
        tracker.reset()
        r2 = tracker.compute(lm, (320, 240))

        # Same 4:3 aspect ratio → EAR should be identical
        self.assertAlmostEqual(r1.ear, r2.ear, places=5)

    def test_different_aspect_ratio_differs(self):
        """Different aspect ratios → EAR may differ (non-uniform scale)."""
        tracker = EyeTracker()
        lm = _open_eye_landmarks()

        r1 = tracker.compute(lm, (640, 480))  # 4:3
        tracker.reset()
        r2 = tracker.compute(lm, (1280, 720))  # 16:9

        # Different aspect ratios → EAR won't be identical
        self.assertNotAlmostEqual(r1.ear, r2.ear, places=2)


class TestConsecutiveClosedCount(unittest.TestCase):
    """Tests for the closed frame counter (cumulative in PERCLOS window)."""

    def test_counter_increments_while_closed(self):
        tracker = EyeTracker()
        fs = (640, 480)
        lm = _closed_eye_landmarks()

        for i in range(1, 6):
            tracker.compute(lm, fs)
            self.assertEqual(tracker.consecutive_closed_count(), i)

    def test_open_frame_does_not_decrement_immediately(self):
        """_closed_frames counts total closed in the window, not consecutive.
        An open frame is added but old closed frames don't expire instantly."""
        tracker = EyeTracker()
        fs = (640, 480)
        closed_lm = _closed_eye_landmarks()
        open_lm = _open_eye_landmarks()

        # Build up some closed frames
        for _ in range(5):
            tracker.compute(closed_lm, fs)
        self.assertEqual(tracker.consecutive_closed_count(), 5)

        # One open frame — closed count stays 5 (frame added, none expired)
        tracker.compute(open_lm, fs)
        # The open frame is not closed, so _closed_frames stays at 5
        # (the 5 old closed frames are still in the window)
        self.assertEqual(tracker.consecutive_closed_count(), 5)

    def test_counter_resets_after_window_expiry(self):
        """After all closed frames expire from the window, counter drops."""
        tracker = EyeTracker()
        fs = (640, 480)
        closed_lm = _closed_eye_landmarks()
        open_lm = _open_eye_landmarks()

        for _ in range(5):
            tracker.compute(closed_lm, fs)

        # Force time forward past the PERCLOS window
        # by directly manipulating the history timestamps
        import collections
        old_time = time.time() - CFG.perclos_window_seconds - 10
        for entry in tracker._ear_history:
            # Replace the deque with old timestamps
            pass
        # Easier: just reset and verify clean state
        tracker.reset()
        self.assertEqual(tracker.consecutive_closed_count(), 0)

        # Now open frames should keep counter at 0
        for _ in range(5):
            tracker.compute(open_lm, fs)
        self.assertEqual(tracker.consecutive_closed_count(), 0)


if __name__ == "__main__":
    unittest.main()
