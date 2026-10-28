#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例：拉取 Hyperliquid 公开数据并做基础统计（无需密钥）。

用法：
    python scripts/demo/hl_fetch.py --coin HYPE --interval 1d
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import hyperliquid as hl  # noqa: E402
from quantlab import metrics  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="HYPE")
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--bars", type=int, default=200)
    args = ap.parse_args()

    rows = hl.candles(args.coin, args.interval)
    closes = [float(r["c"]) for r in rows][-args.bars:]
    if len(closes) < 2:
        print("数据不足")
        return 1
    ppy = {"1h": 24 * 365, "4h": 6 * 365, "1d": 365}.get(args.interval, 365)
    stats = metrics.summary(closes, periods_per_year=ppy)
    print(json.dumps({
        "coin": args.coin,
        "interval": args.interval,
        "bars": len(closes),
        "first_close": closes[0],
        "last_close": closes[-1],
        "price_only_stats": stats,
        "note": "仅价格序列统计，用于数据管道自检；不是策略回测",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
