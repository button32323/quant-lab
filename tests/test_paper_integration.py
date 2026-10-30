"""paper 引擎集成测试（离线，mock 网络）：验证 init → run → reconcile 全链路。"""
import csv
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from quantlab import paper


class TestPaperIntegration(unittest.TestCase):
    def test_full_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            patches = {
                "PAPER_DIR": tmp,
                "STATE": tmp / "state.json",
                "HOURLY": tmp / "hourly.csv",
                "REPORT": tmp / "REPORT.md",
                "RECONCILE": tmp / "reconcile.json",
            }
            with mock.patch.multiple(paper, **patches):
                entry = {"PURR": (0.12, 0.121), "HYPE": (92.0, 92.3)}
                with mock.patch.object(paper, "fetch_prices", side_effect=lambda a: entry[a]):
                    state = paper.init(capital=1000.0)

                # 建仓规模检查
                self.assertAlmostEqual(state["entry_cost_usd"], 375 * 0.00415 + 454.545 * 0.00415, places=2)
                purr = state["positions"]["PURR"]
                hype = state["positions"]["HYPE"]
                self.assertAlmostEqual(purr["notional_usd"], 375.0, places=2)
                self.assertAlmostEqual(purr["qty_spot"], 375.0 / 0.12, places=6)
                self.assertAlmostEqual(hype["notional_usd"], 454.545, places=2)

                # 模拟两笔资金费结算 + 价格变动
                t0 = int(time.time() * 1000) + 3600
                rows = [{"time": t0, "fundingRate": "0.0001"},
                        {"time": t0 + 3600, "fundingRate": "-0.00002"}]
                new_prices = {"PURR": (0.121, 0.1215), "HYPE": (92.5, 92.8)}

                def fake_funding(coin, start_ms=0):
                    return [r for r in rows if int(r["time"]) > start_ms]

                with mock.patch.object(paper.hl, "funding_history", side_effect=fake_funding), \
                     mock.patch.object(paper, "fetch_prices", side_effect=lambda a: new_prices[a]):
                    res = paper.run_once()

                # 资金费 = 0.0001*375 + 0.0001*454.545 + (-0.00002)*(375+454.545)
                exp_funding = 0.0001 * 375 + 0.0001 * 454.545 - 0.00002 * (375 + 454.545)
                self.assertAlmostEqual(res["funding_accrued"], exp_funding, places=6)

                # MTM：现货多头 - 永续空头
                exp_mtm = (purr["qty_spot"] * (0.121 - 0.12) - purr["qty_perp"] * (0.1215 - 0.121)
                           + hype["qty_spot"] * (92.5 - 92.0) - hype["qty_perp"] * (92.8 - 92.3))
                exp_nav = 1000.0 - state["entry_cost_usd"] + exp_funding + exp_mtm
                self.assertAlmostEqual(res["mtm"], exp_mtm, places=4)
                self.assertAlmostEqual(res["nav"], exp_nav, places=4)

                # hourly 写入
                with patches["HOURLY"].open(encoding="utf-8") as f:
                    lines = list(csv.DictReader(f))
                self.assertEqual(len(lines), 1)
                self.assertAlmostEqual(float(lines[0]["nav_usd"]), exp_nav, places=4)

                # 对账：全量资金费独立重算应一致
                st = paper.load_state()
                created_ms = int(__import__("datetime").datetime.fromisoformat(st["created_at"]).timestamp() * 1000)
                with mock.patch.object(paper.hl, "funding_history", side_effect=lambda coin, start_ms=0: rows):
                    rec = paper.reconcile()
                self.assertEqual(rec["overall"], "PASS")
                self.assertAlmostEqual(rec["assets"]["PURR"]["expected_usd"],
                                       0.0001 * 375 - 0.00002 * 375, places=6)


if __name__ == "__main__":
    unittest.main()
