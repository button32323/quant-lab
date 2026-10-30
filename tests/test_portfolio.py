"""portfolio 模块单元测试（离线）。"""
import unittest

import numpy as np
import pandas as pd

from quantlab import portfolio as pf


def make_frames():
    idx = pd.date_range("2021-01-01", periods=40, freq="D")
    up = pd.Series([100.0 * (1.01 ** i) for i in range(40)], index=idx)
    flat = pd.Series([100.0] * 40, index=idx)
    frames = {
        "A": pd.DataFrame({"open": up, "close": up}, index=idx),
        "B": pd.DataFrame({"open": flat, "close": flat}, index=idx),
    }
    return pf.align_symbols(frames)


class TestPortfolio(unittest.TestCase):
    def test_momentum_weights_top1(self):
        opens, closes = make_frames()
        w = pf.momentum_weights(closes, lookback=5, mode="top1")
        # 前 5 天没有动量 -> 空仓
        self.assertAlmostEqual(w.iloc[0].sum(), 0.0)
        # 之后 A 持续上涨 -> 选 A
        self.assertAlmostEqual(w.iloc[-1]["A"], 1.0)

    def test_simulate_full_weight_matches_buy_hold(self):
        opens, closes = make_frames()
        weights = pd.DataFrame({"A": 1.0, "B": 0.0}, index=closes.index)
        res = pf.simulate_weights(opens, closes, weights, capital=100.0, fee=0.001, slippage=0.0005)
        # 第一天买入后持有：等价于 100/(open*1.0015) 份 A 的净值
        units = 100.0 / (float(opens["A"].iloc[1]) * 1.0015)
        expected = units * closes["A"]
        self.assertAlmostEqual(res.equity.iloc[-1], expected.iloc[-1], places=6)
        self.assertGreater(res.costs, 0)

    def test_zero_weights_flat(self):
        opens, closes = make_frames()
        weights = pd.DataFrame({"A": 0.0, "B": 0.0}, index=closes.index)
        res = pf.simulate_weights(opens, closes, weights, capital=100.0)
        self.assertAlmostEqual(res.equity.iloc[-1], 100.0)
        self.assertEqual(res.costs, 0.0)


if __name__ == "__main__":
    unittest.main()

