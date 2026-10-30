#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HL BTC/ETH 资金费 carry 回测（majors，容量大、波动小）。

数据：
- HL 资金费（2023-05 起，逐小时）+ HL 永续日线
- Binance BTCUSDT/ETHUSDT 现货日线（作为现货腿代理；跨所基差作为噪声，报告注明）
口径：本金分 2 份，每资产 1x delta 中性；建仓成本 0.415% × 名义；
      每日 PnL = N*(现货收益-永续收益) + N*资金费。
输出：reports/CARRY_MAJORS.md / .json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data" / "raw"
HL = DATA / "hl"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
ENTRY_COST_RATE = 0.00045 + 0.00070 + 2 * 0.0015  # 0.415%
LEV = {"BTC": 40.0, "ETH": 25.0}
TIERS = [100, 300, 500, 1000, 12000, 100000]


def load_coin(coin: str) -> pd.DataFrame:
    funding = json.loads((HL / f"funding_{coin}.json").read_text())
    fdf = pd.DataFrame(funding)
    fdf["date"] = pd.to_datetime(fdf["time"], unit="ms", utc=True).dt.date
    fdf["rate"] = fdf["fundingRate"].astype(float)
    fund_day = fdf.groupby("date")["rate"].sum().rename("fund_day")

    perp = json.loads((HL / f"candles_1d_{coin}.json").read_text())
    pdf = pd.DataFrame(perp)
    pdf["date"] = pd.to_datetime(pdf["t"], unit="ms", utc=True).dt.date
    pdf["perp_close"] = pdf["c"].astype(float)
    pdf = pdf.sort_values("date").drop_duplicates("date")
    pdf["perp_ret"] = pdf["perp_close"].pct_change()

    spot = pd.read_csv(DATA / f"{coin}USDT_1d.csv", parse_dates=["date"])
    spot["date"] = spot["date"].dt.date
    spot = spot.sort_values("date").drop_duplicates("date")
    spot["spot_ret"] = spot["close"].astype(float).pct_change()

    df = pdf[["date", "perp_close", "perp_ret"]].merge(
        spot[["date", "close", "spot_ret"]].rename(columns={"close": "spot_close"}), on="date", how="inner")
    df = df.merge(fund_day.reset_index(), on="date", how="inner")
    return df.dropna(subset=["perp_ret", "spot_ret", "fund_day"]).reset_index(drop=True)


def simulate(merged: pd.DataFrame, capital: float) -> dict:
    sleeve = capital / 2.0
    notionals = {c: sleeve / (1 + 1 / LEV[c]) for c in LEV}
    total_notional = sum(notionals.values())
    entry_cost = total_notional * ENTRY_COST_RATE
    n = len(merged)
    basis = np.zeros(n)
    funding = np.zeros(n)
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
    return {
        "capital": capital,
        "window": f"{dates.iloc[0].date()} → {dates.iloc[-1].date()}",
        "days": int(days),
        "min_notional": round(min(notionals.values()), 2),
        "total_notional": round(total_notional, 2),
        "entry_cost": round(entry_cost, 4),
        "total_return": round(float(eq[-1] / capital - 1), 6),
        "cagr": round(float((eq[-1] / capital) ** (365 / days) - 1), 6) if eq[-1] > 0 else -1.0,
        "volatility": round(vol, 6),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(mdd, 6),
        "funding_usd": round(float(funding.sum()), 4),
        "basis_usd": round(float(basis.sum()), 4),
    }


def main() -> int:
    frames = {c: load_coin(c) for c in LEV}
    merged = frames["BTC"]
    for c in ["ETH"]:
        merged = merged.merge(frames[c][["date", f"{c}_perp_ret", f"{c}_spot_ret", f"{c}_fund_day"]]
                              if f"{c}_perp_ret" in frames[c].columns else
                              frames[c][["date", "perp_ret", "spot_ret", "fund_day"]].rename(
                                  columns={"perp_ret": f"{c}_perp_ret", "spot_ret": f"{c}_spot_ret",
                                           "fund_day": f"{c}_fund_day"}),
                              on="date", how="inner")
    merged = merged.rename(columns={"perp_ret": "BTC_perp_ret", "spot_ret": "BTC_spot_ret",
                                    "fund_day": "BTC_fund_day"})
    merged = merged.sort_values("date").reset_index(drop=True)

    results = [simulate(merged, cap) for cap in TIERS]
    out = {"assets": "HL BTC + ETH perp, spot proxy=Binance", "rows": len(merged),
           "window": f"{merged['date'].iloc[0]} → {merged['date'].iloc[-1]}", "results": results}
    (REPORTS / "carry_majors.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# HL BTC/ETH 资金费 carry 回测", "",
             f"窗口：{out['window']}（{len(merged)} 天）｜ 1x delta 中性｜成本 0.415%/边｜现货腿用 Binance 价格代理（跨所基差为噪声）",
             "", "| 本金 | 年化 | 最大回撤 | Sharpe | 资金费贡献 | basis 贡献 |", "|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        lines.append(f"| ${r['capital']:,} | {r['cagr']*100:+.2f}% | {r['max_drawdown']*100:.2f}% | "
                     f"{r['sharpe']:.2f} | ${r['funding_usd']:+.2f} | ${r['basis_usd']:+.2f} |")
    lines += ["", "> 收益率与本金近似无关；majors 容量大，适合更大资金；但年化低于小市值 carry。"]
    (REPORTS / "CARRY_MAJORS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
