"""回测引擎单元测试（合成数据，离线）。"""
import unittest

import numpy as np
import pandas as pd

from quantlab import backtest as bt


def make_df(closes, opens=None, start="2020-01-01"):
    n = len(closes)
    if opens is None:
        opens = closes
    dates = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame({"date": dates, "open": opens, "close": closes})


class TestBacktest(unittest.TestCase):
    def test_no_lookahead_executes_next_open(self):
        # 前 10 天上涨，第 11 天暴跌：动量在 t=10 收盘为正，应在 t=11 开盘买入（不是 t=10）
        closes = [100.0] * 10 + [100.0, 50.0, 50.0]
        closes = [100.0, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 60, 60]
        df = make_df(closes)
        res = bt.run_tsmom(df, lookback=5, fee=0.0, slippage=0.0)
        # 第一次买入应发生在信号出现后的下一天
        buys = [t for t in res.trades if t["side"] == "buy"]
        self.assertTrue(buys)
        # 买入日期索引应 >= lookback+1
        idx = df.index[df["date"] == buys[0]["date"]][0]
        self.assertGreaterEqual(idx, 5 + 1)

    def test_cost_applied_only_on_trade(self):
        # 单调上涨：持有 BTC，仅一笔买入成本
        closes = [100.0 * (1.01 ** i) for i in range(120)]
        df = make_df(closes)
        res = bt.run_tsmom(df, lookback=10, fee=0.001, slippage=0.0005)
        self.assertEqual(len([t for t in res.trades if t["side"] == "buy"]), 1)
        self.assertAlmostEqual(res.costs, res.capital * 0.0015 / 1.0015, places=6)
        # 后续无卖出，成本不再增加
        self.assertEqual(len([t for t in res.trades if t["side"] == "sell"]), 0)

    def test_flat_market_no_trades(self):
        closes = [100.0] * 50
        df = make_df(closes)
        res = bt.run_tsmom(df, lookback=10, fee=0.001, slippage=0.0005)
        self.assertEqual(res.trades, [])
        self.assertAlmostEqual(res.equity.iloc[-1], 100.0)

    def test_cash_when_momentum_negative(self):
        closes = [200.0 * (0.99 ** i) for i in range(60)]
        df = make_df(closes)
        res = bt.run_tsmom(df, lookback=10, fee=0.0, slippage=0.0)
        self.assertTrue((res.position == 0).all())
        self.assertAlmostEqual(res.equity.iloc[-1], 100.0)

    def test_trade_pnl_and_win_rate(self):
        # 上涨后下跌，触发一次完整买卖
        closes = [100.0] * 5 + [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 90, 90, 90]
        df = make_df(closes)
        res = bt.run_tsmom(df, lookback=5, fee=0.001, slippage=0.0005)
        sells = [t for t in res.trades if t["side"] == "sell"]
        self.assertTrue(sells)
        self.assertIn("pnl", sells[0])
        st = res.stats()
        self.assertIn("win_rate", st)
        self.assertIn("profit_factor", st)


if __name__ == "__main__":
    unittest.main()
