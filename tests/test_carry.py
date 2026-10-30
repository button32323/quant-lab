"""carry 模块单元测试（合成数据，离线）。"""
import unittest

import numpy as np
import pandas as pd

from quantlab import carry


class TestCarry(unittest.TestCase):
    def _merged(self, n=30):
        dates = pd.date_range("2024-12-07", periods=n, freq="D")
        return pd.DataFrame({
            "date": dates,
            "PURR_fund_day": [0.0002] * n,
            "HYPE_fund_day": [0.0001] * n,
            "PURR_spot_ret": [0.01] * n,
            "PURR_perp_ret": [0.01] * n,   # basis = 0
            "HYPE_spot_ret": [-0.005] * n,
            "HYPE_perp_ret": [-0.005] * n,  # basis = 0
        })

    def test_position_sizing(self):
        merged = self._merged()
        res = carry.simulate(merged, {"PURR": 0.5, "HYPE": 0.5}, 1000.0)
        self.assertAlmostEqual(res["notionals"]["PURR"], 375.0, places=6)
        self.assertAlmostEqual(res["notionals"]["HYPE"], 454.5454545, places=4)
        self.assertAlmostEqual(res["entry_cost"], (375 + 454.5454545) * 0.00415, places=4)

    def test_funding_and_zero_basis(self):
        merged = self._merged()
        res = carry.simulate(merged, {"PURR": 0.5, "HYPE": 0.5}, 1000.0)
        n_days_after_first = len(merged)
        exp_funding = n_days_after_first * (375 * 0.0002 + 454.5454545 * 0.0001)
        self.assertAlmostEqual(float(res["funding"].sum()), exp_funding, places=4)
        self.assertAlmostEqual(float(res["basis"].sum()), 0.0, places=8)
        exp_equity = 1000.0 - res["entry_cost"] + exp_funding
        self.assertAlmostEqual(float(res["equity"].iloc[-1]), exp_equity, places=4)

    def test_basis_pnl_when_spot_diverges(self):
        merged = self._merged()
        merged["PURR_spot_ret"] = 0.01
        merged["PURR_perp_ret"] = 0.005  # 现货腿跑赢 0.5%，basis 为正
        res = carry.simulate(merged, {"PURR": 0.5, "HYPE": 0.5}, 1000.0)
        self.assertGreater(float(res["basis"].sum()), 0.0)
        # 约 375 * 0.005 * 30 天
        self.assertAlmostEqual(float(res["basis"].sum()), 375 * 0.005 * len(merged), places=2)


if __name__ == "__main__":
    unittest.main()
