#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷新数据：Binance 现货日线（BTC/ETH/SOL/BNB）+ Hyperliquid 资金费/日线（BTC/ETH/PURR/HYPE）。

用法：python scripts/data/refresh_daily.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import binance_vision as bv  # noqa: E402
from quantlab import hyperliquid as hl  # noqa: E402

RAW = ROOT / "data" / "raw"
HL_DIR = RAW / "hl"
HL_DIR.mkdir(parents=True, exist_ok=True)

BINANCE = {"BTCUSDT": date(2017, 8, 17), "ETHUSDT": date(2017, 8, 17),
           "SOLUSDT": date(2020, 8, 11), "BNBUSDT": date(2017, 11, 6)}
HL_PERP = ["BTC", "ETH", "PURR", "HYPE"]
HL_SPOT = {"BTC": None, "ETH": None, "PURR": "PURR/USDC", "HYPE": "@107"}


def refresh_binance() -> list[str]:
    out = []
    for sym, start in BINANCE.items():
        bars = bv.fetch_daily_bars(symbol=sym, interval="1d", start=start, sleep=0.01)
        df = pd.DataFrame([{
            "date": pd.to_datetime(int(b["open_time"]), unit="ms", utc=True).date().isoformat(),
            "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"], "volume": b["volume"],
        } for b in bars])
        path = RAW / f"{sym}_1d.csv"
        df.to_csv(path, index=False)
        out.append(f"{sym}: {len(df)} 行，{df['date'].iloc[0]} → {df['date'].iloc[-1]}")
    return out


def refresh_hl() -> list[str]:
    out = []
    for coin in HL_PERP:
        funding = hl.funding_history(coin)
        (HL_DIR / f"funding_{coin}.json").write_text(json.dumps(funding), encoding="utf-8")
        rows = hl.candles(coin, "1d")
        (HL_DIR / f"candles_1d_{coin}.json").write_text(json.dumps(rows), encoding="utf-8")
        spot = HL_SPOT.get(coin)
        if spot:
            (HL_DIR / f"candles_1d_spot_{coin}.json").write_text(json.dumps(hl.candles(spot, "1d")), encoding="utf-8")
        out.append(f"HL {coin}: funding {len(funding)} 条，candles {len(rows)} 根")
    return out


def main() -> int:
    print("\n".join(refresh_binance()))
    print("\n".join(refresh_hl()))
    print("刷新完成:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
