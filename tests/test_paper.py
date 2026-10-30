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

class TestGate(unittest.TestCase):
    def _state(self, days: float) -> dict:
        from datetime import datetime, timedelta, timezone
        created = datetime.now(timezone.utc) - timedelta(days=days)
        return {"created_at": created.isoformat(timespec="seconds"), "capital_usd": 1000.0,
                "entry_cost_usd": 3.44, "funding_stats": {"PURR": {"settlements": 100, "positive": 70}}}

    def _hourly(self, tmp_path, navs):
        import csv
        p = tmp_path / "hourly.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(paper.HOURLY_COLS)
            for i, nav in enumerate(navs):
                w.writerow([f"2026-01-{i+1:02d}T00:00:00+00:00", nav, 5.0, 0.0, 3.44, 0.7, 0, 0, 0, 0])
        return p

    def test_pending_before_30d(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            hourly = self._hourly(tmp, [1000, 1010, 1005, 1020])
            rec = tmp / "reconcile.json"
            rec.write_text('{"overall": "PASS"}', encoding="utf-8")
            with mock.patch.object(paper, "HOURLY", hourly), mock.patch.object(paper, "RECONCILE", rec):
                g = paper.evaluate_gate(self._state(days=5))
        self.assertEqual(g["status"], "PENDING")
        self.assertFalse(g["checks"]["elapsed_30d"])

    def test_pass_after_30d(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            hourly = self._hourly(tmp, [1000, 1020, 1015, 1030])
            rec = tmp / "reconcile.json"
            rec.write_text('{"overall": "PASS"}', encoding="utf-8")
            with mock.patch.object(paper, "HOURLY", hourly), mock.patch.object(paper, "RECONCILE", rec):
                g = paper.evaluate_gate(self._state(days=31))
        self.assertEqual(g["status"], "PASS")
        self.assertTrue(all(g["checks"].values()), g)

    def test_fail_negative_return(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            hourly = self._hourly(tmp, [1000, 990, 970, 960])
            rec = tmp / "reconcile.json"
            rec.write_text('{"overall": "PASS"}', encoding="utf-8")
            with mock.patch.object(paper, "HOURLY", hourly), mock.patch.object(paper, "RECONCILE", rec):
                g = paper.evaluate_gate(self._state(days=31))
        self.assertEqual(g["status"], "FAIL")
        self.assertFalse(g["checks"]["return_positive"])
