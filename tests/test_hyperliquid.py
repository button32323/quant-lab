"""hyperliquid 模块的离线测试（mock 网络请求）。"""
import unittest
from unittest import mock

from quantlab import hyperliquid as hl


class TestHyperliquid(unittest.TestCase):
    def test_to_utc(self):
        dt = hl.to_utc(0)
        self.assertEqual(dt.year, 1970)

    def test_funding_history_pagination(self):
        calls = []

        def fake_post(body, timeout=15.0, retries=3):
            calls.append(body)
            start = int(body["startTime"])
            if start == 0:
                return [{"coin": "X", "fundingRate": "0.0001", "time": 1000 + i} for i in range(500)]
            return []

        with mock.patch.object(hl, "post", side_effect=fake_post):
            rows = hl.funding_history("X", start_ms=0)
        self.assertEqual(len(rows), 500)
        self.assertEqual(len(calls), 2)
        # 第二次请求应从最后一根时间 +1 开始
        self.assertEqual(int(calls[1]["startTime"]), 1000 + 499 + 1)

    def test_candles_request_shape(self):
        captured = {}

        def fake_post(body, timeout=15.0, retries=3):
            captured.update(body)
            return []

        with mock.patch.object(hl, "post", side_effect=fake_post):
            hl.candles("HYPE", "1d", 0)
        self.assertEqual(captured["type"], "candleSnapshot")
        self.assertEqual(captured["req"]["coin"], "HYPE")
        self.assertEqual(captured["req"]["interval"], "1d")


if __name__ == "__main__":
    unittest.main()
