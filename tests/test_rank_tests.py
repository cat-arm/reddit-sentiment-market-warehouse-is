"""Unit tests of analysis/rank_tests.py (synthetic series)."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import rank_tests as rt  # noqa: E402


def slow_shift_p(x, y, min_shift):
    from scipy import stats
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    real = abs(rt.corr(rx, ry))
    values = [abs(rt.corr(np.roll(rx, s), ry)) for s in range(min_shift, len(x) - min_shift + 1)]
    return (1 + sum(v >= real - 1e-12 for v in values)) / (1 + len(values))


class CircularShiftTests(unittest.TestCase):
    def test_fourier_version_equals_the_plain_loop(self):
        rng = np.random.default_rng(3)
        x = rng.normal(size=300)
        y = 0.3 * x + rng.normal(size=300)
        self.assertAlmostEqual(rt.circular_shift_p(x, y, 24), slow_shift_p(x, y, 24), places=12)

    def test_relation_is_significant_and_noise_is_not(self):
        rng = np.random.default_rng(4)
        x = rng.normal(size=600)
        self.assertLess(rt.circular_shift_p(x, x + 0.5 * rng.normal(size=600)), 0.01)
        self.assertGreater(rt.circular_shift_p(x, rng.normal(size=600)), 0.05)

    def test_autocorrelated_series_are_judged_against_their_own_shifts(self):
        """Pairs of INDEPENDENT, strongly autocorrelated (stationary) series: the usual p of Spearman calls many of them related, the circular-shift p does not."""
        from scipy import stats

        def ar1(rng, n=1500, phi=0.95):
            e = rng.normal(size=n)
            x = np.zeros(n)
            for i in range(1, n):
                x[i] = phi * x[i - 1] + e[i]
            return x

        rng = np.random.default_rng(5)
        formula, shift = [], []
        for _ in range(40):
            x, y = ar1(rng), ar1(rng)
            formula.append(stats.spearmanr(x, y).pvalue < 0.05)
            shift.append(rt.circular_shift_p(x, y) < 0.05)
        self.assertGreater(np.mean(formula), 0.4)                                # the formula: far more false alarms than the nominal 5%
        self.assertLess(np.mean(shift), 0.2)                                     # the shift test: near the nominal 5%

    def test_too_short_is_nan(self):
        self.assertTrue(np.isnan(rt.circular_shift_p(np.arange(20.0), np.arange(20.0))))


class BlockTests(unittest.TestCase):
    def test_block_indices_are_whole_days(self):
        first, counts = np.array([0, 3, 7]), np.array([3, 4, 2])
        for seed in range(10):
            idx = rt.block_indices(first, counts, np.random.default_rng(seed))
            picked = np.random.default_rng(seed).integers(0, 3, 3)
            expected = np.concatenate([np.arange(first[d], first[d] + counts[d]) for d in picked])
            np.testing.assert_array_equal(idx, expected)

    def test_decile_table_follows_a_rising_relation(self):
        rng = np.random.default_rng(6)
        hours = np.arange(3000) * 3600
        sentiment = rng.normal(size=3000)
        returns = 0.5 * sentiment + rng.normal(size=3000)
        table = rt.decile_table(sentiment, returns, hours, boot=50)
        self.assertGreater(table["trend"], 0.8)
        self.assertGreater(table["diff"], 0.5)
        self.assertGreater(table["diff_ci"][0], 0.0)
        self.assertEqual(int(table["counts"].sum()), 3000)

    def test_decile_table_needs_enough_data(self):
        self.assertIsNone(rt.decile_table(np.arange(30.0), np.arange(30.0), np.arange(30) * 3600))

    def test_spearman_with_ci(self):
        rng = np.random.default_rng(7)
        hours = np.arange(2400) * 3600
        x = rng.normal(size=2400)
        rho, low, high, p, n = rt.spearman_with_ci(x, x + rng.normal(size=2400), hours, boot=50)
        self.assertGreater(low, 0.3)
        self.assertLess(p, 0.01)
        self.assertEqual(n, 2400)


class FastIntervalTests(unittest.TestCase):
    def test_fast_interval_matches_the_exact_one_and_covers_the_true_value(self):
        rng = np.random.default_rng(11)
        n = 6000
        hours = np.arange(n) * 3600
        x = rng.normal(size=n)
        y = 0.1 * x + rng.normal(size=n)
        low, high = rt.spearman_ci_fast(x, y, hours // 86400, boot=1000)
        rho, exact_low, exact_high, _, _ = rt.spearman_with_ci(x, y, hours, boot=300)
        self.assertLess(low, rho)
        self.assertGreater(high, rho)
        self.assertAlmostEqual(low, exact_low, delta=0.02)                         # the shortcut (ranks of the full sample) gives nearly the interval of the exact bootstrap
        self.assertAlmostEqual(high, exact_high, delta=0.02)

    def test_fast_interval_of_noise_reaches_zero_and_too_little_data_is_nan(self):
        rng = np.random.default_rng(12)
        low, high = rt.spearman_ci_fast(rng.normal(size=4000), rng.normal(size=4000), np.arange(4000) // 24)
        self.assertLess(low, 0.0)
        self.assertGreater(high, 0.0)
        self.assertTrue(np.isnan(rt.spearman_ci_fast(np.arange(10.0), np.arange(10.0), np.arange(10))[0]))


if __name__ == "__main__":
    unittest.main()
