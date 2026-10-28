#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 Binance BTCUSDT 日线（2017-08 至今）并保存 CSV + 数据质量报告。

用法：python scripts/data/fetch_btc_daily.py
输出：
  data/raw/BTCUSDT_1d.csv
  data/raw/BTCUSDT_1d_quality.json
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import binance_vision as bv  # noqa: E402

OUT = ROOT / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    bars = bv.fetch_daily_bars(symbol="BTCUSDT", interval="1d", start=date(2017, 8, 1))
    if not bars:
        print("未获取到数据")
        return 1

    # 数据质量检查
    dates = [datetime.fromtimestamp(b["open_time"] / 1000, tz=timezone.utc).date() for b in bars]
    dup = len(dates) - len(set(dates))
    unsorted = sum(1 for i in range(1, len(dates)) if dates[i] <= dates[i - 1])
    bad_ohlc = sum(1 for b in bars if not (b["high"] >= b["low"] > 0 and b["open"] > 0 and b["close"] > 0))
    gaps = [(dates[i - 1], dates[i]) for i in range(1, len(dates)) if (dates[i] - dates[i - 1]).days > 1]
    quality = {
        "rows": len(bars),
        "start": str(dates[0]),
        "end": str(dates[-1]),
        "duplicates": dup,
        "unsorted": unsorted,
        "bad_ohlc": bad_ohlc,
        "calendar_gaps": len(gaps),
        "gap_samples": [[str(a), str(b)] for a, b in gaps[:10]],
    }

    path = OUT / "BTCUSDT_1d.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "open_time", "open", "high", "low", "close", "volume"])
        for b, d in zip(bars, dates):
            w.writerow([d.isoformat(), b["open_time"], b["open"], b["high"], b["low"], b["close"], b["volume"]])
    (OUT / "BTCUSDT_1d_quality.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(quality, ensure_ascii=False, indent=2))
    print(f"已保存: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
