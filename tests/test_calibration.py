"""
S.A.F.E. 2.0 — Unit Tests for Calibration Module
"""
from __future__ import annotations

import unittest

from src.safe.calibration import Calibration, CalibrationResult


class TestComputeThresholds(unittest.TestCase):
    """Tests for Calibration._compute_thresholds (static, no hardware needed)."""

    compute = staticmethod(Calibration._compute_thresholds)

    def test_well_separated_clusters(self):
        """Open ~0.35 and closed ~0.10 should give a threshold in between."""
        open_ears = [0.34, 0.36, 0.35, 0.33, 0.37]
        closed_ears = [0.08, 0.10, 0.12, 0.09, 0.11]
        result = self.compute(open_ears, closed_ears)

        self.assertIsInstance(result, CalibrationResult)
        self.assertGreater(result.suggested_ear_threshold, 0.10)
        self.assertLess(result.suggested_ear_threshold, 0.33)
        self.assertGreater(result.separation, 0.0)

    def test_threshold_between_clusters(self):
        """Threshold should be between open_mean and closed_mean."""
        open_ears = [0.30, 0.32, 0.34]
        closed_ears = [0.12, 0.14, 0.16]
        result = self.compute(open_ears, closed_ears)

        self.assertGreater(result.suggested_ear_threshold, result.closed_mean)
        self.assertLess(result.suggested_ear_threshold, result.open_mean)

    def test_sample_counts_preserved(self):
        open_ears = [0.30, 0.32, 0.34, 0.31]
        closed_ears = [0.10, 0.12, 0.11]
        result = self.compute(open_ears, closed_ears)

        self.assertEqual(result.num_open, 4)
        self.assertEqual(result.num_closed, 3)

    def test_means_are_correct(self):
        open_ears = [0.40, 0.40]
        closed_ears = [0.10, 0.10]
        result = self.compute(open_ears, closed_ears)

        self.assertAlmostEqual(result.open_mean, 0.40, places=4)
        self.assertAlmostEqual(result.closed_mean, 0.10, places=4)
        self.assertAlmostEqual(result.open_std, 0.0, places=4)
        self.assertAlmostEqual(result.closed_std, 0.0, places=4)

    def test_threshold_clamped_low(self):
        """Threshold should not go below 0.05."""
        open_ears = [0.10, 0.11, 0.12]
        closed_ears = [0.08, 0.09, 0.10]
        result = self.compute(open_ears, closed_ears)

        self.assertGreaterEqual(result.suggested_ear_threshold, 0.05)

    def test_threshold_clamped_high(self):
        """Threshold should not go above 0.40."""
        open_ears = [0.50, 0.51, 0.52]
        closed_ears = [0.45, 0.46, 0.47]
        result = self.compute(open_ears, closed_ears)

        self.assertLessEqual(result.suggested_ear_threshold, 0.40)

    def test_identical_values(self):
        """All same EAR → threshold should be clamped (no separation)."""
        open_ears = [0.25, 0.25, 0.25]
        closed_ears = [0.25, 0.25, 0.25]
        result = self.compute(open_ears, closed_ears)

        self.assertAlmostEqual(result.separation, 0.0, places=4)
        self.assertEqual(result.suggested_ear_threshold, 0.25)

    def test_single_high_variance(self):
        """High variance in open eyes should still produce a valid threshold."""
        open_ears = [0.20, 0.40, 0.30, 0.35, 0.25]
        closed_ears = [0.05, 0.10, 0.08, 0.12, 0.07]
        result = self.compute(open_ears, closed_ears)

        self.assertGreater(result.suggested_ear_threshold, 0.05)
        self.assertLess(result.suggested_ear_threshold, 0.40)

    def test_realistic_values(self):
        """Simulate realistic EAR values from actual eye tracking."""
        import random
        random.seed(42)

        # Simulate open eyes with some noise around 0.33
        open_ears = [0.33 + random.gauss(0, 0.03) for _ in range(50)]
        # Simulate closed eyes with some noise around 0.08
        closed_ears = [0.08 + random.gauss(0, 0.02) for _ in range(50)]

        result = self.compute(open_ears, closed_ears)

        # Threshold should be well between the two clusters
        self.assertGreater(result.suggested_ear_threshold, 0.10)
        self.assertLess(result.suggested_ear_threshold, 0.30)
        self.assertGreater(result.separation, 0.15)

    def test_frame_threshold_is_positive(self):
        open_ears = [0.30]
        closed_ears = [0.10]
        result = self.compute(open_ears, closed_ears)

        self.assertGreater(result.suggested_frame_threshold, 0)



if __name__ == "__main__":
    unittest.main()
