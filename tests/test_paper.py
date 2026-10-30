"""paper 引擎纯函数测试（离线，无网络）。"""
import unittest

from quantlab import paper


class TestPaperCalc(unittest.TestCase):
    def test_dedupe_funding(self):
        rows = [{"time": 2, "fundingRate": "0.1"}, {"time": 1, "fundingRate": "0.2"},
                {"time": 2, "fundingRate": "0.3"}]
        out = paper.dedupe_funding(rows)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["time"], 1)
        self.assertEqual(out[1]["fundingRate"], "0.3")

    def test_funding_amount(self):
        rows = [{"time": 1, "fundingRate": 0.0001}, {"time": 2, "fundingRate": -0.00005}]
        self.assertAlmostEqual(paper.funding_amount(rows, 1000.0), 0.05)

    def test_position_mtm_neutral(self):
        # 现货与永续同比例同幅度：mtm≈0
        mtm = paper.position_mtm(10, 100, 110, 10, 100, 110)
        self.assertAlmostEqual(mtm, 0.0)
        # 现货涨、永续不涨：basis 收益
        mtm2 = paper.position_mtm(10, 100, 110, 10, 100, 100)
        self.assertAlmostEqual(mtm2, 100.0)

    def test_compute_nav(self):
        self.assertAlmostEqual(paper.compute_nav(1000, 3, 10, -1), 1006.0)

    def test_max_drawdown(self):
        self.assertAlmostEqual(paper.max_drawdown([100, 120, 90]), 0.25)
        self.assertAlmostEqual(paper.max_drawdown([100, 110]), 0.0)
        self.assertEqual(paper.max_drawdown([]), 0.0)

    def test_negative_streak(self):
        self.assertEqual(paper.latest_negative_streak([0.1, -0.1, -0.2]), 2)
        self.assertEqual(paper.latest_negative_streak([-0.1, 0.1]), 0)
        self.assertEqual(paper.latest_negative_streak([]), 0)


if __name__ == "__main__":
    unittest.main()
