"""Unit tests of the helpers of scripts/spearman_assumptions_check.py (synthetic series, no database)."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import spearman_assumptions_check as sac  # noqa: E402


class StationarityTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.noise = rng.normal(size=4000)
        self.walk = np.cumsum(self.noise)

    def test_adf_separates_noise_from_random_walk(self):
        self.assertLess(sac.adf(self.noise), sac.ADF_CRITICAL["1%"])
        self.assertGreater(sac.adf(self.walk), sac.ADF_CRITICAL["10%"])

    def test_kpss_separates_noise_from_random_walk(self):
        self.assertLess(sac.kpss_stat(self.noise), sac.KPSS_CRITICAL["5%"])
        self.assertGreater(sac.kpss_stat(self.walk), sac.KPSS_CRITICAL["1%"])

    def test_agree_with_statsmodels_when_installed(self):
        try:
            from statsmodels.tsa.stattools import adfuller, kpss
        except ImportError:
            self.skipTest("statsmodels is not installed")
        self.assertAlmostEqual(sac.adf(self.walk), adfuller(self.walk, maxlag=12, regression="c", autolag=None)[0], places=6)
        self.assertAlmostEqual(sac.kpss_stat(self.walk), kpss(self.walk, regression="c", nlags=int(12 * (len(self.walk) / 100) ** 0.25))[0], places=6)


class AutocorrelationTests(unittest.TestCase):
    def test_ljung_box_and_lag_corr(self):
        rng = np.random.default_rng(1)
        noise = rng.normal(size=4000)
        ar = np.zeros(4000)
        for i in range(1, 4000):
            ar[i] = 0.5 * ar[i - 1] + rng.normal()
        self.assertGreater(sac.ljung_box(pd.Series(noise))[1], 0.01)
        self.assertLess(sac.ljung_box(pd.Series(ar))[1], 1e-10)
        self.assertAlmostEqual(sac.lag_corr(pd.Series(ar), 1), 0.5, delta=0.05)

    def test_lag_corr_ignores_gaps(self):
        grid = pd.Series(np.arange(1.0, 41.0))
        grid[2] = np.nan                                                          # a gap: the pairs that touch it are dropped, the others stay exactly one step apart
        self.assertAlmostEqual(sac.lag_corr(grid, 1), 1.0, places=6)


class SmallHelperTests(unittest.TestCase):
    def test_ties_and_groups(self):
        self.assertEqual(sac.ties([1, 1, 2, 3]), 0.5)
        self.assertEqual(sac.group_of("ES=F", "futures"), sac.GROUP_ORDER[0])
        self.assertEqual(sac.group_of("CL=F", "futures"), sac.GROUP_ORDER[3])
        self.assertEqual(sac.group_of("BTC-USD", "crypto"), sac.GROUP_ORDER[1])
        self.assertEqual(sac.group_of("AAPL", "stock_etf"), sac.GROUP_ORDER[2])


if __name__ == "__main__":
    unittest.main()
