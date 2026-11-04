#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷新全部数据到最新：

- Binance 现货日线：BTC/ETH/SOL/BNB
- Hyperliquid 永续+现货日线 + 资金费：8 个小市值资产（R174A 候选）+ BTC/ETH

输出到 data/raw/ 与 data/raw/hl/。只读公开数据。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import binance_vision as bv  # noqa: E402
from quantlab import hyperliquid as hl  # noqa: E402

RAW = ROOT / "data" / "raw"
HL = RAW / "hl"
HL.mkdir(parents=True, exist_ok=True)

BINANCE = {"BTCUSDT": date(2017, 8, 17), "ETHUSDT": date(2017, 8, 17),
           "SOLUSDT": date(2020, 8, 11), "BNBUSDT": date(2017, 11, 6)}

# 来自 R174A candidates：perp 名称 -> 现货对
HL_ASSETS = {
    "AZTEC": "@285", "BERA": "@117", "HYPE": "@107", "MON": "@129",
    "PUMP": "@20", "PURR": "PURR/USDC", "STABLE": "@258", "TRUMP": "@9",
    "BTC": "@142", "ETH": "@151",
}


def refresh_binance() -> list[str]:
    out = []
    for sym, start in BINANCE.items():
        bars = bv.fetch_daily_bars(symbol=sym, interval="1d", start=start, sleep=0.01)
        df = pd.DataFrame([{
            "date": pd.to_datetime(int(b["open_time"]), unit="ms", utc=True).date().isoformat(),
            "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"], "volume": b["volume"],
        } for b in bars])
        df.to_csv(RAW / f"{sym}_1d.csv", index=False)
        out.append(f"binance {sym}: {len(df)} rows → {df['date'].iloc[-1]}")
    return out


def refresh_hl() -> list[str]:
    out = []
    for coin, spot_pair in HL_ASSETS.items():
        funding = hl.funding_history(coin)
        (HL / f"funding_{coin}.json").write_text(json.dumps(funding), encoding="utf-8")
        perp = hl.candles(coin, "1d")
        (HL / f"candles_1d_{coin}.json").write_text(json.dumps(perp), encoding="utf-8")
        spot = hl.candles(spot_pair, "1d")
        (HL / f"candles_1d_spot_{coin}.json").write_text(json.dumps(spot), encoding="utf-8")
        out.append(f"hl {coin}: funding={len(funding)} perp={len(perp)} spot={len(spot)}")
        time.sleep(0.15)
    return out


def main() -> int:
    print("start:", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    for line in refresh_binance():
        print(line, flush=True)
    for line in refresh_hl():
        print(line, flush=True)
    print("done:", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
