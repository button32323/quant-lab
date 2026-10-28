"""metrics 模块单元测试（离线）。"""
import unittest

import numpy as np

from quantlab import metrics


class TestMetrics(unittest.TestCase):
    def test_total_return(self):
        self.assertAlmostEqual(metrics.total_return([100, 110]), 0.10)
        self.assertAlmostEqual(metrics.total_return([100, 90]), -0.10)
        self.assertEqual(metrics.total_return([100]), 0.0)

    def test_max_drawdown(self):
        eq = [100, 120, 90, 110]
        self.assertAlmostEqual(metrics.max_drawdown(eq), 0.25)
        self.assertAlmostEqual(metrics.max_drawdown([100, 110, 120]), 0.0)

    def test_cagr_one_year(self):
        # 365 个日收益周期 = 1 年
        eq = [100.0] + [100.0 * (1.0005 ** i) for i in range(1, 366)]
        got = metrics.cagr(eq, 365)
        self.assertAlmostEqual(got, eq[-1] / 100.0 - 1.0, places=6)

    def test_volatility_and_sharpe_zero(self):
        flat = [100.0] * 50
        self.assertAlmostEqual(metrics.volatility(flat, 365), 0.0)
        self.assertAlmostEqual(metrics.sharpe(flat, 365), 0.0)

    def test_summary_keys(self):
        s = metrics.summary([100, 101, 99, 102], 365)
        for k in ("total_return", "cagr", "volatility", "sharpe", "max_drawdown"):
            self.assertIn(k, s)
        self.assertAlmostEqual(s["max_drawdown"], 0.01980198, places=6)


if __name__ == "__main__":
    unittest.main()
