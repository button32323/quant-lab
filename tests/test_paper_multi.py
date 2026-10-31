"""paper_multi 配置/取整纯函数测试（离线）。"""
import unittest

from quantlab import paper_multi as pm


class TestPaperMulti(unittest.TestCase):
    def test_floor_to_decimals(self):
        self.assertAlmostEqual(pm.floor_to(0.4962, 2), 0.49)
        self.assertAlmostEqual(pm.floor_to(312.99, 0), 312.0)
        self.assertAlmostEqual(pm.floor_to(0.0004437, 5), 0.00044)

    def test_account_weights_sum_to_one(self):
        for name, cfg in pm.ACCOUNTS.items():
            total = sum(cfg["weights"].values())
            self.assertAlmostEqual(total, 1.0, places=9, msg=name)

    def test_all_account_assets_configured(self):
        for name, cfg in pm.ACCOUNTS.items():
            for asset in cfg["weights"]:
                self.assertIn(asset, pm.ASSETS, f"{name}: {asset}")

    def test_min_order_math_at_100_usd(self):
        # $100 本金、A0 配置下每腿名义应 >= $10
        capital = 100.0
        w = pm.ACCOUNTS["a0_100"]["weights"]
        for asset, weight in w.items():
            target = capital * weight / (1 + 1 / pm.ASSETS[asset]["max_lev"])
            self.assertGreaterEqual(target, 10.0, asset)


if __name__ == "__main__":
    unittest.main()
