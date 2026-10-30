#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据新鲜度/质量概览：本地各数据源的最后日期与行数。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"


def main() -> int:
    print(f"生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")
    print(f"{'文件':<42} {'行数':>8}  {'起':<12} {'止':<12}")
    print("-" * 80)
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
        p = RAW / f"{sym}_1d.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, parse_dates=["date"])
        print(f"{p.name:<42} {len(df):>8}  {str(df['date'].iloc[0].date()):<12} {str(df['date'].iloc[-1].date()):<12}")
    for coin in ["BTC", "ETH", "PURR", "HYPE"]:
        p = RAW / "hl" / f"funding_{coin}.json"
        if not p.exists():
            continue
        rows = json.loads(p.read_text(encoding="utf-8"))
        last = datetime.fromtimestamp(int(rows[-1]["time"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        print(f"{'hl/funding_' + coin + '.json':<42} {len(rows):>8}  {'—':<12} {last:<12}")
    for asset in ["PURR", "HYPE", "AZTEC", "STABLE"]:
        p = RAW / "R174A" / "data" / "panels" / f"daily_{asset}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, parse_dates=["day"])
        tr = df[df["tradable"] == 1]
        print(f"{'R174A daily_' + asset + '.csv':<42} {len(df):>8}  {str(df['day'].iloc[0].date()):<12} {str(tr['day'].iloc[-1].date()):<12}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
