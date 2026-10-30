#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据源交叉验证与延长：用 Hyperliquid 原始数据重建 PURR/HYPE 面板，与 R174A 面板对比。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import carry  # noqa: E402

HL = ROOT / "data" / "raw" / "hl"
PANELS = ROOT / "data" / "raw" / "R174A" / "data" / "panels"
REPORTS = ROOT / "reports"
CAPITAL = 1000.0
WEIGHTS = {"PURR": 0.5, "HYPE": 0.5}


def from_hl(asset: str) -> pd.DataFrame:
    fund = pd.DataFrame(json.loads((HL / f"funding_{asset}.json").read_text()))
    fund["date"] = pd.to_datetime(fund["time"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    fund["rate"] = fund["fundingRate"].astype(float)
    fund_day = fund.groupby("date")["rate"].sum().rename(f"{asset}_fund_day")
    spot = pd.DataFrame(json.loads((HL / f"candles_1d_spot_{asset}.json").read_text()))
    spot["date"] = pd.to_datetime(spot["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    spot = spot.sort_values("date").drop_duplicates("date")
    spot[f"{asset}_spot_ret"] = spot["c"].astype(float).pct_change()
    perp = pd.DataFrame(json.loads((HL / f"candles_1d_{asset}.json").read_text()))
    perp["date"] = pd.to_datetime(perp["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    perp = perp.sort_values("date").drop_duplicates("date")
    perp[f"{asset}_perp_ret"] = perp["c"].astype(float).pct_change()
    df = spot[["date", f"{asset}_spot_ret"]].merge(perp[["date", f"{asset}_perp_ret"]], on="date")
    return df.merge(fund_day.reset_index(), on="date").dropna().reset_index(drop=True)


def from_panel(asset: str) -> pd.DataFrame:
    df = pd.read_csv(PANELS / f"daily_{asset}.csv", parse_dates=["day"])
    df = df[df["tradable"] == 1].dropna(subset=["fund_day", "spot_ret", "perp_ret"])
    return df.rename(columns={"day": "date", "fund_day": f"{asset}_fund_day",
                              "spot_ret": f"{asset}_spot_ret", "perp_ret": f"{asset}_perp_ret"})[
        ["date", f"{asset}_fund_day", f"{asset}_spot_ret", f"{asset}_perp_ret"]]


def build(loader) -> pd.DataFrame:
    a = loader("PURR")
    b = loader("HYPE")
    return a.merge(b, on="date").sort_values("date").reset_index(drop=True)


def stats(df: pd.DataFrame) -> dict:
    r = carry.simulate(df, WEIGHTS, CAPITAL)
    return {"window": f"{df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()}", "days": len(df),
            "cagr": round(r["cagr"], 6), "mdd": round(r["mdd"], 6), "sharpe": round(r["sharpe"], 4)}


def main() -> int:
    panel = build(from_panel)
    hl = build(from_hl)
    common_start = max(panel["date"].iloc[0], hl["date"].iloc[0])
    common_end = min(panel["date"].iloc[-1], hl["date"].iloc[-1])
    p_common = panel[(panel["date"] >= common_start) & (panel["date"] <= common_end)].reset_index(drop=True)
    h_common = hl[(hl["date"] >= common_start) & (hl["date"] <= common_end)].reset_index(drop=True)

    out = {"panel_full": stats(panel), "hl_full": stats(hl),
           "panel_on_common": stats(p_common), "hl_on_common": stats(h_common),
           "common_window": f"{common_start.date()} → {common_end.date()}"}
    (REPORTS / "carry_source_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# A0 数据源交叉验证（R174A 面板 vs HL 原始数据）", "",
             f"共同窗口：{out['common_window']}", "",
             "| 数据源 | 窗口 | 天数 | 年化 | 最大回撤 | Sharpe |", "|---|---|---|---:|---:|---:|"]
    for k, label in [("panel_on_common", "R174A 面板（共同窗口）"), ("hl_on_common", "HL 原始（共同窗口）"),
                     ("panel_full", "R174A 面板（全窗口）"), ("hl_full", "HL 原始（全窗口，含最新）")]:
        s = out[k]
        lines.append(f"| {label} | {s['window']} | {s['days']} | {s['cagr']*100:+.2f}% | {s['mdd']*100:.2f}% | {s['sharpe']:.2f} |")
    lines += ["", "> 若两个数据源在共同窗口内结果接近，说明结论不依赖单一面板；HL 原始数据可把回测延长到最新日期。"]
    (REPORTS / "CARRY_SOURCE_CHECK.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
