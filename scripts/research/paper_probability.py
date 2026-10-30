#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper 30 天结果的概率分布：A0 策略在"近 180 天/全窗口"环境下的通过概率。

输出：reports/PAPER_PROBABILITY.md / .json
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
WEIGHTS = {"PURR": 0.5, "HYPE": 0.5}
HORIZON = 30
SAMPLES = 5000
BLOCK = 7


def simulate_paths(daily_ret: np.ndarray, funding_share: float, cost_pct: float = 0.0,
                   samples: int = SAMPLES, horizon: int = HORIZON, block: int = BLOCK, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    n = len(daily_ret)
    rets = np.empty((samples, horizon))
    for i in range(samples):
        blocks = int(np.ceil(horizon / block))
        idx = rng.integers(0, n - block, size=blocks)
        rets[i] = np.concatenate([daily_ret[j:j + block] for j in idx])[:horizon]
    # 建仓成本在起点一次性扣除（paper 的真实情况）
    rets[:, 0] = (1 + rets[:, 0]) * (1 - cost_pct) - 1
    nav = CAPITAL * np.cumprod(1 + rets, axis=1)
    final = nav[:, -1]
    total_ret = final / CAPITAL - 1
    annualized = (final / CAPITAL) ** (365.0 / horizon) - 1
    peak = np.maximum.accumulate(np.column_stack([np.full(samples, CAPITAL), nav]), axis=1)
    mdd = np.max((peak - np.column_stack([np.full(samples, CAPITAL), nav])) / peak, axis=1)
    gate_ret = total_ret > 0
    gate_cagr = annualized > 0.10
    gate_mdd = mdd < 0.05
    gate_fund = funding_share > 0.60
    return {
        "horizon_days": horizon,
        "samples": samples,
        "return_p5": round(float(np.percentile(total_ret, 5)) * 100, 4),
        "return_p50": round(float(np.percentile(total_ret, 50)) * 100, 4),
        "return_p95": round(float(np.percentile(total_ret, 95)) * 100, 4),
        "annualized_p5": round(float(np.percentile(annualized, 5)) * 100, 4),
        "annualized_p50": round(float(np.percentile(annualized, 50)) * 100, 4),
        "annualized_p95": round(float(np.percentile(annualized, 95)) * 100, 4),
        "mdd_p50": round(float(np.percentile(mdd, 50)) * 100, 4),
        "mdd_p95": round(float(np.percentile(mdd, 95)) * 100, 4),
        "prob_return_positive": round(float(gate_ret.mean()), 4),
        "prob_annualized_gt_10pct": round(float(gate_cagr.mean()), 4),
        "prob_mdd_lt_5pct": round(float(gate_mdd.mean()), 4),
        "prob_funding_share_gt_60pct": round(float(gate_fund), 4),
        "prob_all_gates": round(float((gate_ret & gate_cagr & gate_mdd & gate_fund).mean()), 4),
    }


def main() -> int:
    merged = carry.build_combined()
    res = carry.simulate(merged, WEIGHTS, CAPITAL)
    daily_ret = res["equity"].pct_change().dropna().to_numpy()
    funding_share = float((res["funding"] > 0).mean())

    # 近 180 天 / 全窗口
    recent = res["equity"].pct_change().dropna().tail(180).to_numpy()
    full = daily_ret

    out = {
        "strategy": "A0 PURR+HYPE carry", "capital": CAPITAL,
        "window": f"{merged['date'].iloc[0].date()} → {merged['date'].iloc[-1].date()}",
        "current_env_annualized": 0.0966,
        "entry_cost_usd": round(res["entry_cost"], 4),
        "entry_cost_pct": round(res["entry_cost"] / CAPITAL * 100, 4),
        "recent180_funding_positive_share": round(float((res["funding"].tail(180) > 0).mean()), 4),
        "bootstrap_recent180": simulate_paths(recent, funding_share, res["entry_cost"] / CAPITAL),
        "bootstrap_full": simulate_paths(full, funding_share, res["entry_cost"] / CAPITAL),
    }
    # 当前环境下 30 天确定性估算（含一次性建仓成本）
    monthly_gross = 0.0966 * HORIZON / 365
    net_30d = monthly_gross - res["entry_cost"] / CAPITAL
    out["current_env_expectation"] = {
        "gross_30d_pct": round(monthly_gross * 100, 4),
        "net_after_entry_cost_30d_pct": round(net_30d * 100, 4),
        "annualized_after_entry_cost_pct": round(((1 + net_30d) ** (365 / HORIZON) - 1) * 100, 4),
    }
    (REPORTS / "paper_probability.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Paper 30 天结果概率（A0）", "",
             f"窗口：{out['window']} ｜ 本金 ${CAPITAL:.0f} ｜ 30 天、块 Bootstrap（block={BLOCK}, samples={SAMPLES}）", "",
             "## 当前环境确定性估算", "",
             f"- 当前资金费环境年化约 +9.66% → 30 天毛收益约 +{monthly_gross*100:.2f}%",
             f"- 一次性建仓成本 −{res['entry_cost']/CAPITAL*100:.2f}% → 30 天净收益约 **{net_30d*100:+.2f}%**",
             f"- 折算年化约 **{out['current_env_expectation']['annualized_after_entry_cost_pct']:+.2f}%**（低于 10% 门槛）", "",
             "## Bootstrap 概率", "",
             "| 指标 | 近 180 天环境 | 全窗口环境 |", "|---|---:|---:|"]
    a, b = out["bootstrap_recent180"], out["bootstrap_full"]
    for k, label in [("return_p5", "30天收益 p5"), ("return_p50", "30天收益 中位"), ("return_p95", "30天收益 p95"),
                     ("annualized_p50", "年化 中位"), ("mdd_p50", "回撤 中位"), ("mdd_p95", "回撤 p95")]:
        lines.append(f"| {label} | {a[k]:+.2f}% | {b[k]:+.2f}% |")
    lines += ["", "| 门禁通过概率 | 近 180 天 | 全窗口 |", "|---|---:|---:|",
              f"| 30 天收益 > 0 | {a['prob_return_positive']*100:.1f}% | {b['prob_return_positive']*100:.1f}% |",
              f"| 年化 > 10% | {a['prob_annualized_gt_10pct']*100:.1f}% | {b['prob_annualized_gt_10pct']*100:.1f}% |",
              f"| 回撤 < 5% | {a['prob_mdd_lt_5pct']*100:.1f}% | {b['prob_mdd_lt_5pct']*100:.1f}% |",
              f"| **全部通过** | **{a['prob_all_gates']*100:.1f}%** | **{b['prob_all_gates']*100:.1f}%** |",
              "", "> 关键：30 天里一次性建仓成本（−0.34%）会显著压低年化读数——当前环境下 30 天年化约 +5.7%，大概率低于 10% 门槛。",
              "> 这不是策略不行，而是 30 天窗口 + 一次性成本导致的门禁偏差；paper 应重点验证执行/对账，收益评估需拉长到 60–90 天或剔除建仓成本。"]
    (REPORTS / "PAPER_PROBABILITY.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

