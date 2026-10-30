#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A0/E 资金费 carry 的稳健性验证：滚动窗口、Bootstrap、压力测试、环境情景。

输出：reports/CARRY_VALIDATION.md / .json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import carry  # noqa: E402

REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
CAPITAL = 1000.0
WEIGHTS = {
    "A0_small": {"PURR": 0.5, "HYPE": 0.5},
    "E_75_25": {"PURR": 0.375, "HYPE": 0.375, "BTC": 0.125, "ETH": 0.125},
    "B0_majors": {"BTC": 0.5, "ETH": 0.5},
}


def bootstrap_annualized(daily_returns: np.ndarray, horizon_days: int = 365, block: int = 7,
                         samples: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    n = len(daily_returns)
    out = np.empty(samples)
    for i in range(samples):
        # 循环块采样（保留自相关）
        blocks = int(np.ceil(horizon_days / block))
        idx = rng.integers(0, n - block, size=blocks)
        sample = np.concatenate([daily_returns[j:j + block] for j in idx])[:horizon_days]
        out[i] = np.prod(1 + sample) - 1
    return {
        "p5": round(float(np.percentile(out, 5)), 6),
        "p50": round(float(np.percentile(out, 50)), 6),
        "p95": round(float(np.percentile(out, 95)), 6),
        "prob_negative": round(float((out < 0).mean()), 4),
        "prob_below_10pct": round(float((out < 0.10).mean()), 4),
        "samples": samples, "block": block, "horizon_days": horizon_days,
    }


def rolling_annualized(equity: pd.Series, window: int) -> dict:
    r = equity.pct_change().dropna()
    roll = (1 + r).rolling(window).apply(np.prod, raw=True) ** (365.0 / window) - 1
    roll = roll.dropna()
    return {"window_days": window,
            "p5": round(float(roll.quantile(0.05)), 4),
            "p50": round(float(roll.median()), 4),
            "p95": round(float(roll.quantile(0.95)), 4),
            "share_negative": round(float((roll < 0).mean()), 4),
            "share_below_10": round(float((roll < 0.10).mean()), 4)}


def yearly_returns(equity: pd.Series) -> dict:
    out = {}
    for year, g in equity.groupby(equity.index.year):
        out[str(year)] = round(float(g.iloc[-1] / g.iloc[0] - 1), 6)
    return out


def main() -> int:
    merged = carry.build_combined()
    print("window:", merged["date"].iloc[0].date(), "→", merged["date"].iloc[-1].date(), "rows:", len(merged))

    results = {}
    for name, w in WEIGHTS.items():
        res = carry.simulate(merged, w, CAPITAL)
        eq = res["equity"]
        r = eq.pct_change().dropna().to_numpy()
        funding_share = float((res["funding"] > 0).mean())
        results[name] = {
            "cagr": round(res["cagr"], 6),
            "total_return": round(res["total_return"], 6),
            "vol": round(res["vol"], 6),
            "sharpe": round(res["sharpe"], 4),
            "mdd": round(res["mdd"], 6),
            "funding_positive_share": round(funding_share, 4),
            "yearly": yearly_returns(eq),
            "rolling_30d": rolling_annualized(eq, 30),
            "rolling_90d": rolling_annualized(eq, 90),
            "bootstrap_1y": bootstrap_annualized(r),
        }

        # 压力测试
        stress = {}
        for label, fund_mul, basis_mul, cost_mul in [
            ("基线", 1.0, 1.0, 1.0),
            ("资金费减半", 0.5, 1.0, 1.0),
            ("资金费归零", 0.0, 1.0, 1.0),
            ("资金费转负(×-0.5)", -0.5, 1.0, 1.0),
            ("basis 波动×2", 1.0, 2.0, 1.0),
            ("成本×2", 1.0, 1.0, 2.0),
        ]:
            notionals = {c: w[c] * CAPITAL / (1 + 1 / carry.LEV[c]) for c in w}
            fund = np.zeros(len(merged))
            basis = np.zeros(len(merged))
            for c, n in notionals.items():
                fund += n * merged[f"{c}_fund_day"].to_numpy() * fund_mul
                basis += n * (merged[f"{c}_spot_ret"].to_numpy() - merged[f"{c}_perp_ret"].to_numpy()) * basis_mul
            pnl = fund + basis
            pnl[0] -= sum(notionals.values()) * carry.ENTRY_COST_RATE * cost_mul
            eq_s = CAPITAL + np.cumsum(pnl)
            days = max((merged["date"].iloc[-1] - merged["date"].iloc[0]).days, 1)
            peak = np.maximum.accumulate(eq_s)
            stress[label] = {
                "cagr": round(float((eq_s[-1] / CAPITAL) ** (365 / days) - 1), 4),
                "mdd": round(float(np.max((peak - eq_s) / peak)), 4),
            }
        results[name]["stress"] = stress

        # 当前环境情景：用最近 30 天平均资金费、basis=0
        last30 = merged.tail(30)
        cur = {}
        for label, w in WEIGHTS.items():
            notionals = {c: w[c] * CAPITAL / (1 + 1 / carry.LEV[c]) for c in w}
            annual = sum(n * float(last30[f"{c}_fund_day"].mean()) * 365 for c, n in notionals.items())
            cur[label] = round(annual / CAPITAL, 4)
        results[name]["current_env_annualized"] = cur.get(name)

    out = {"window": f"{merged['date'].iloc[0].date()} → {merged['date'].iloc[-1].date()}",
           "rows": len(merged), "capital": CAPITAL, "results": results}
    (REPORTS / "carry_validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 资金费 carry 稳健性验证", "",
             f"共同窗口：{out['window']}（{len(merged)} 天）｜本金 ${CAPITAL:.0f}｜1x delta 中性", ""]
    for name, r in results.items():
        lines += [f"## {name}", "",
                  f"- 全期：年化 {r['cagr']*100:+.2f}%，回撤 {r['mdd']*100:.2f}%，Sharpe {r['sharpe']:.2f}，正资金费占比 {r['funding_positive_share']*100:.1f}%",
                  f"- 当前环境（近30天均值）：年化 {r['current_env_annualized']*100:+.2f}%",
                  f"- 年度收益：{json.dumps(r['yearly'], ensure_ascii=False)}",
                  f"- 滚动30日年化：p5 {r['rolling_30d']['p5']*100:+.1f}% / 中位 {r['rolling_30d']['p50']*100:+.1f}% / p95 {r['rolling_30d']['p95']*100:+.1f}%；负值占比 {r['rolling_30d']['share_negative']*100:.1f}%",
                  f"- 滚动90日年化：p5 {r['rolling_90d']['p5']*100:+.1f}% / 中位 {r['rolling_90d']['p50']*100:+.1f}% / p95 {r['rolling_90d']['p95']*100:+.1f}%",
                  f"- 一年 Bootstrap：p5 {r['bootstrap_1y']['p5']*100:+.1f}% / 中位 {r['bootstrap_1y']['p50']*100:+.1f}% / p95 {r['bootstrap_1y']['p95']*100:+.1f}%；负收益概率 {r['bootstrap_1y']['prob_negative']*100:.1f}%；<10% 概率 {r['bootstrap_1y']['prob_below_10pct']*100:.1f}%",
                  "", "| 压力情景 | 年化 | 回撤 |", "|---|---:|---:|"]
        for label, s in r["stress"].items():
            lines.append(f"| {label} | {s['cagr']*100:+.2f}% | {s['mdd']*100:.2f}% |")
        lines.append("")
    (REPORTS / "CARRY_VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
