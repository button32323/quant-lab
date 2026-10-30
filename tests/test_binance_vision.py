"""binance_vision 数据解析测试（内存 zip，无网络）。"""
import io
import unittest
import zipfile

from quantlab import binance_vision as bv


def make_zip(csv_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("BTCUSDT-1d-2024-01.csv", csv_text)
    return buf.getvalue()


class TestBinanceVision(unittest.TestCase):
    def test_parse_zip_with_header(self):
        csv_text = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,"
                    "taker_buy_volume,taker_buy_quote_volume,ignore\n"
                    "1700000000000,100,110,90,105,1000,1700086399999,0,0,0,0,0\n")
        rows = bv._parse_zip_csv(make_zip(csv_text))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "1700000000000")

    def test_to_bars_millisecond(self):
        bars = bv._to_bars([["1700000000000", "100", "110", "90", "105", "1000"]])
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["open_time"], 1700000000000)

    def test_to_bars_microsecond_normalized(self):
        # 2025 起部分文件使用微秒时间戳，应归一化为毫秒
        us = 1735689600000000
        bars = bv._to_bars([[str(us), "100", "110", "90", "105", "1000"]])
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["open_time"], us // 1000)

    def test_to_bars_invalid_timestamp_skipped(self):
        bars = bv._to_bars([["0", "1", "2", "0.5", "1.5", "10"]])
        self.assertEqual(bars, [])


if __name__ == "__main__":
    unittest.main()
