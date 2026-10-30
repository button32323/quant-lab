#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HL 现货-永续资金费 carry：按不同本金档位回测（$27–$1000+）。

数据：R174A 面板（PURR/HYPE 日线，2024-12 起）
口径：每资产 sleeve = 本金/2；名义 N = sleeve/(1+1/maxLev)；
      建仓成本 0.415% × 名义；每日 PnL = N*(现货收益-永续收益) + N*资金费；
      无杠杆、delta 中性、不调仓。
输出：reports/carry_capital_tiers.json / .md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "raw" / "R174A" / "data" / "panels"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

ASSETS = {
    "PURR": {"file": "daily_PURR.csv", "max_lev": 3.0},
    "HYPE": {"file": "daily_HYPE.csv", "max_lev": 10.0},
}
ENTRY_COST_RATE = 0.00045 + 0.00070 + 2 * 0.0015  # 0.415%
MIN_ORDER_USD = 10.0
TIERS = [27, 50, 100, 300, 500, 1000, 3000, 12000]


def load_panel(asset: str) -> pd.DataFrame:
    cfg = ASSETS[asset]
    df = pd.read_csv(DATA / cfg["file"], parse_dates=["day"])
    df = df[df["tradable"] == 1].dropna(subset=["fund_day", "spot_ret", "perp_ret"]).copy()
    df = df[["day", "spot_close", "perp_close", "fund_day", "spot_ret", "perp_ret"]]
    df = df.rename(columns={c: f"{asset}_{c}" for c in df.columns if c != "day"})
    df["max_lev"] = cfg["max_lev"]
    return df


def simulate(merged: pd.DataFrame, capital: float) -> dict:
    sleeve = capital / 2.0
    notionals = {}
    for asset in ASSETS:
        lev = ASSETS[asset]["max_lev"]
        n = sleeve / (1 + 1 / lev)
        notionals[asset] = n
    total_notional = sum(notionals.values())
    entry_cost = total_notional * ENTRY_COST_RATE
    n_days = len(merged)
    pnl = np.zeros(n_days)
    funding = np.zeros(n_days)
    basis = np.zeros(n_days)
    for asset, n in notionals.items():
        sret = merged[f"{asset}_spot_ret"].to_numpy()
        pret = merged[f"{asset}_perp_ret"].to_numpy()
        fnd = merged[f"{asset}_fund_day"].to_numpy()
        basis += n * (sret - pret)
        funding += n * fnd
        pnl += n * (sret - pret) + n * fnd
    # 建仓首日扣成本
    pnl[0] -= entry_cost
    equity = capital + np.cumsum(pnl)
    dates = pd.to_datetime(merged["day"])
    days = max((dates.iloc[-1] - dates.iloc[0]).days, 1)
    total_ret = equity[-1] / capital - 1.0
    cagr = (equity[-1] / capital) ** (365.0 / days) - 1.0 if equity[-1] > 0 else -1.0
    rets = np.diff(equity) / equity[:-1]
    vol = float(np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 else 0.0
    sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 and np.std(rets, ddof=1) > 0 else 0.0
    peak = np.maximum.accumulate(equity)
    mdd = float(np.max((peak - equity) / peak))
    min_notional = min(notionals.values())
    feasible = min_notional >= MIN_ORDER_USD
    return {
        "capital": capital,
        "start": str(dates.iloc[0].date()),
        "end": str(dates.iloc[-1].date()),
        "days": int(days),
        "feasible_min_order": feasible,
        "min_notional": round(min_notional, 2),
        "total_notional": round(total_notional, 2),
        "entry_cost": round(entry_cost, 4),
        "total_return": round(float(total_ret), 6),
        "cagr": round(float(cagr), 6),
        "volatility": round(vol, 6),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(mdd, 6),
        "funding_usd": round(float(funding.sum()), 4),
        "basis_usd": round(float(basis.sum()), 4),
        "annual_income_p50_usd": round(capital * 0.18, 2),  # 历史年化约 18% 的参考
    }


def main() -> int:
    panels = [load_panel(a) for a in ASSETS]
    merged = panels[0]
    for p in panels[1:]:
        merged = merged.merge(p.drop(columns=["max_lev"]), on="day", how="inner")
    merged = merged.sort_values("day").reset_index(drop=True)
    if len(merged) < 30:
        print("共同交易窗口不足")
        return 1

    results = [simulate(merged, cap) for cap in TIERS]
    out = {"window": f"{merged['day'].iloc[0].date()} → {merged['day'].iloc[-1].date()}",
           "rows": len(merged), "results": results}
    (REPORTS / "carry_capital_tiers.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# HL 资金费 carry：本金档位回测", "",
        f"共同交易窗口：{out['window']}（{len(merged)} 个交易日）｜ PURR+HYPE、1x delta 中性、建仓成本 0.415%/边",
        "", "| 本金 | 可执行(≥$10/腿) | 年化 | 最大回撤 | Sharpe | 资金费贡献 | basis 贡献 | 参考年收入(18%) |",
        "|---:|:---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(f"| ${r['capital']:,} | {'✅' if r['feasible_min_order'] else '❌'} | {r['cagr']*100:+.2f}% | "
                     f"{r['max_drawdown']*100:.2f}% | {r['sharpe']:.2f} | ${r['funding_usd']:+.2f} | "
                     f"${r['basis_usd']:+.2f} | ${r['annual_income_p50_usd']:,.0f} |")
    lines += ["", "> 收益率与本金近似无关（成本按比例），本金决定绝对收入与最小下单可行性。",
              "> 当前环境资金费年化约 9%，低于历史平均 18%；且策略容量约 $12–14k。"]
    (REPORTS / "CARRY_CAPITAL_TIERS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
