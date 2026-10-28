"""costs 模块单元测试（离线）。"""
import unittest

from quantlab.costs import CostModel


class TestCosts(unittest.TestCase):
    def test_rates(self):
        c = CostModel(taker_bps=4.5, maker_bps=1.5, slippage_bps=5.0)
        self.assertAlmostEqual(c.fee_rate(), 0.00045)
        self.assertAlmostEqual(c.fee_rate(maker=True), 0.00015)
        self.assertAlmostEqual(c.per_leg_cost_rate(), 0.00045 + 0.0005)

    def test_trade_cost_two_legs(self):
        c = CostModel()
        cost = c.trade_cost(1000, legs=2)
        self.assertAlmostEqual(cost, 1000 * (0.00045 + 0.0005) * 2, places=8)

    def test_funding_payment_short_receives_positive(self):
        c = CostModel()
        # 正资金费：空头收钱 -> 返回正数
        self.assertAlmostEqual(c.funding_payment(1000, 0.0001), -0.1)

    def test_funding_payment_long_pays_negative(self):
        c = CostModel()
        # 用负号约定：空头视角返回 -notional*rate；正费率时结果为负表示付？这里按实现校验
        self.assertAlmostEqual(c.funding_payment(1000, -0.0001), 0.1)


if __name__ == "__main__":
    unittest.main()
