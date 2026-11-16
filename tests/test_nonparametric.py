"""Unit tests of the helpers of scripts/nonparametric_tests.py (no database: synthetic series)."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import nonparametric_tests as npt  # noqa: E402


class HelperTests(unittest.TestCase):
    def test_bh_adjusts_and_keeps_nan(self):
        adjusted = npt.bh([0.01, 0.02, 0.03, np.nan])
        np.testing.assert_allclose(adjusted[:3], [0.03, 0.03, 0.03])
        self.assertTrue(np.isnan(adjusted[3]))

    def test_block_indices_are_whole_days(self):
        starts, counts = np.array([0, 3, 7]), np.array([3, 4, 2])
        for seed in range(20):
            idx = npt.block_indices(starts, counts, np.random.default_rng(seed))
            picked = np.random.default_rng(seed).integers(0, len(starts), len(starts))       # the same draw of days as inside the function
            expected = np.concatenate([np.arange(starts[d], starts[d] + counts[d]) for d in picked])
            np.testing.assert_array_equal(idx, expected)                                      # the drawn days, whole, in the order drawn

    def test_spearman_detects_a_relation_and_not_noise(self):
        rng = np.random.default_rng(2)
        x = rng.normal(size=480)
        days = np.arange(480) // 24
        rho, low, high, shift_p, formula_p = npt.spearman_block(x, x + 0.5 * rng.normal(size=480), days, rng, 100, 200)
        self.assertGreater(rho, 0.7)
        self.assertGreater(low, 0.5)
        self.assertLess(shift_p, 0.05)
        rho, low, high, shift_p, formula_p = npt.spearman_block(x, rng.normal(size=480), days, rng, 100, 200)
        self.assertLess(abs(rho), 0.2)
        self.assertLessEqual(low, 0.0 + 1e-9 if rho > 0 else high)                       # the interval of pure noise reaches zero or is near it

    def test_group_tests_need_enough_hours(self):
        status = np.array(["positive"] * 40 + ["negative"] * 40 + ["neutral"] * 10, dtype=object)
        y = np.concatenate([np.linspace(0, 1, 40), np.linspace(0, 1, 40), np.zeros(10)])
        row = npt.group_tests(y, status)
        self.assertAlmostEqual(row["mw_prob_superiority"], 0.5, places=3)
        self.assertTrue(np.isnan(npt.group_tests(y[:20], status[:20])["mw_p"]))


if __name__ == "__main__":
    unittest.main()
