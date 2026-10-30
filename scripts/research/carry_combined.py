#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组合 carry：小市值（PURR/HYPE）+ 主流（BTC/ETH）资金费 carry 的配置回测。

共同窗口：2024-12-07 起（PURR/HYPE 数据起点之后）。
配置：资金按权重分给 4 个 sleeve，每个 1x delta 中性；建仓成本 0.415% × 名义。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data" / "raw"
HL = DATA / "hl"
R174A = DATA / "R174A" / "data" / "panels"
REPORTS = ROOT / "reports"
ENTRY_COST = 0.00045 + 0.00070 + 2 * 0.0015
LEV = {"BTC": 40.0, "ETH": 25.0, "PURR": 3.0, "HYPE": 10.0}
CAPITAL = 1000.0


def load_small(asset: str, max_lev: float) -> pd.DataFrame:
    df = pd.read_csv(R174A / f"daily_{asset}.csv", parse_dates=["day"])
    df = df[df["tradable"] == 1].dropna(subset=["fund_day", "spot_ret", "perp_ret"])
    return df.rename(columns={"day": "date", "fund_day": f"{asset}_fund_day",
                              "spot_ret": f"{asset}_spot_ret", "perp_ret": f"{asset}_perp_ret"})[
        ["date", f"{asset}_fund_day", f"{asset}_spot_ret", f"{asset}_perp_ret"]]


def load_major(coin: str) -> pd.DataFrame:
    funding = pd.DataFrame(json.loads((HL / f"funding_{coin}.json").read_text()))
    funding["date"] = pd.to_datetime(funding["time"], unit="ms", utc=True).dt.date
    funding["rate"] = funding["fundingRate"].astype(float)
    fund_day = funding.groupby("date")["rate"].sum().rename(f"{coin}_fund_day").reset_index()
    perp = pd.DataFrame(json.loads((HL / f"candles_1d_{coin}.json").read_text()))
    perp["date"] = pd.to_datetime(perp["t"], unit="ms", utc=True).dt.date
    perp = perp.sort_values("date").drop_duplicates("date")
    perp[f"{coin}_perp_ret"] = perp["c"].astype(float).pct_change()
    spot = pd.read_csv(DATA / f"{coin}USDT_1d.csv", parse_dates=["date"])
    spot["date"] = spot["date"].dt.date
    spot = spot.sort_values("date").drop_duplicates("date")
    spot[f"{coin}_spot_ret"] = spot["close"].astype(float).pct_change()
    df = perp[["date", f"{coin}_perp_ret"]].merge(spot[["date", f"{coin}_spot_ret"]], on="date")
    df = df.merge(fund_day, on="date").dropna().reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def simulate(merged: pd.DataFrame, weights: dict[str, float], capital: float) -> dict:
    notionals = {c: weights[c] * capital / (1 + 1 / LEV[c]) for c in weights if weights[c] > 0}
    total_notional = sum(notionals.values())
    entry_cost = total_notional * ENTRY_COST
    n = len(merged)
    pnl = np.zeros(n)
    funding = np.zeros(n)
    basis = np.zeros(n)
    for c, N in notionals.items():
        basis += N * (merged[f"{c}_spot_ret"].to_numpy() - merged[f"{c}_perp_ret"].to_numpy())
        funding += N * merged[f"{c}_fund_day"].to_numpy()
    pnl = basis + funding
    pnl[0] -= entry_cost
    eq = capital + np.cumsum(pnl)
    dates = pd.to_datetime(merged["date"])
    days = max((dates.iloc[-1] - dates.iloc[0]).days, 1)
    rets = np.diff(eq) / eq[:-1]
    vol = float(np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 else 0.0
    sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 and np.std(rets, ddof=1) > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    mdd = float(np.max((peak - eq) / peak))
    return {"weights": weights, "annualized": round(float((eq[-1] / capital) ** (365 / days) - 1), 6),
            "max_drawdown": round(mdd, 6), "sharpe": round(sharpe, 4),
            "funding_usd": round(float(funding.sum()), 4),
            "basis_usd": round(float(basis.sum()), 4),
            "total_notional": round(total_notional, 2),
            "entry_cost": round(entry_cost, 4),
            "min_notional": round(min(notionals.values()), 2) if notionals else 0}


def main() -> int:
    small = load_small("PURR", 3.0).merge(load_small("HYPE", 10.0), on="date", how="inner")
    majors = load_major("BTC").merge(load_major("ETH"), on="date", how="inner")
    merged = small.merge(majors, on="date", how="inner").sort_values("date").reset_index(drop=True)
    print("common window:", merged["date"].iloc[0], "→", merged["date"].iloc[-1], "rows:", len(merged))

    allocs = {
        "A0_small_only": {"PURR": 0.5, "HYPE": 0.5},
        "B0_majors_only": {"BTC": 0.5, "ETH": 0.5},
        "C_50_50": {"PURR": 0.25, "HYPE": 0.25, "BTC": 0.25, "ETH": 0.25},
        "D_25_75_majors": {"PURR": 0.125, "HYPE": 0.125, "BTC": 0.375, "ETH": 0.375},
        "E_75_25_small": {"PURR": 0.375, "HYPE": 0.375, "BTC": 0.125, "ETH": 0.125},
    }
    results = {name: simulate(merged, w, CAPITAL) for name, w in allocs.items()}
    out = {"window": f"{merged['date'].iloc[0]} → {merged['date'].iloc[-1]}", "rows": len(merged),
           "capital": CAPITAL, "results": results}
    (REPORTS / "carry_combined.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 组合 carry 配置回测（PURR/HYPE + BTC/ETH）", "",
             f"共同窗口：{out['window']}（{len(merged)} 天）｜ 1x delta 中性｜成本 0.415%/边｜本金 ${CAPITAL:.0f}",
             "", "| 配置 | 小市值权重 | 主流权重 | 年化 | 最大回撤 | Sharpe | 资金费$ | basis$ | 最小名义$ |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, r in results.items():
        small_w = r["weights"].get("PURR", 0) + r["weights"].get("HYPE", 0)
        lines.append(f"| {name} | {small_w*100:.0f}% | {(1-small_w)*100:.0f}% | {r['annualized']*100:+.2f}% | "
                     f"{r['max_drawdown']*100:.2f}% | {r['sharpe']:.1f} | ${r['funding_usd']:+.0f} | "
                     f"${r['basis_usd']:+.0f} | ${r['min_notional']:.1f} |")
    (REPORTS / "CARRY_COMBINED.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


