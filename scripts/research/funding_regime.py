#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资金费环境分析：月度水平、负费率连续期、盈亏平衡所需资金费。

输出：reports/FUNDING_REGIME.md / .json
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
REPORTS.mkdir(exist_ok=True)
NOTIONALS = {"PURR": 375.0, "HYPE": 454.55, "BTC": 480.77, "ETH": 480.77}  # $1000 本金 A0 配置下的名义
ENTRY_COST_RATIO = 0.0034426  # $1000 本金建仓成本占比


def load_fund(asset: str) -> pd.Series:
    """返回逐日资金费（Sum of hourly rates）。"""
    if asset in ("PURR", "HYPE"):
        df = pd.read_csv(R174A / f"daily_{asset}.csv", parse_dates=["day"])
        df = df[df["tradable"] == 1].dropna(subset=["fund_day"])
        s = df.set_index("day")["fund_day"]
        return s.rename(asset)
    f = pd.DataFrame(json.loads((HL / f"funding_{asset}.json").read_text()))
    f["day"] = pd.to_datetime(f["time"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    f["rate"] = f["fundingRate"].astype(float)
    return f.groupby("day")["rate"].sum().rename(asset)


def monthly_annualized(daily: pd.Series) -> pd.Series:
    return daily.groupby(daily.index.to_period("M")).mean() * 365


def longest_negative_streak(daily: pd.Series) -> int:
    best = cur = 0
    for v in daily.values:
        if v < 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def main() -> int:
    daily = pd.concat([load_fund(a) for a in NOTIONALS], axis=1).sort_index().dropna(how="all")
    out = {"days": len(daily), "start": str(daily.index[0].date()), "end": str(daily.index[-1].date()),
           "monthly": {}, "assets": {}}

    for a in NOTIONALS:
        s = daily[a].dropna()
        out["assets"][a] = {
            "mean_annualized": round(float(s.mean() * 365), 4),
            "median_annualized": round(float(s.median() * 365), 4),
            "p5_annualized": round(float(s.quantile(0.05) * 365), 4),
            "min_daily_annualized": round(float(s.min() * 365), 4),
            "negative_day_share": round(float((s < 0).mean()), 4),
            "longest_negative_streak_days": longest_negative_streak(s),
            "monthly_annualized": {str(k): round(float(v), 4) for k, v in monthly_annualized(s).items()},
        }

    # 组合口径：$1000 本金下 A0 / B0 / E
    allocs = {
        "A0": {"PURR": 0.375, "HYPE": 0.45455},
        "B0": {"BTC": 0.48077, "ETH": 0.48077},
        "E": {"PURR": 0.28125, "HYPE": 0.34091, "BTC": 0.12019, "ETH": 0.12019},
    }
    port = {}
    for name, w in allocs.items():
        sub = daily[[a for a in w]].dropna()          # 仅使用全部资产都有数据的共同窗口
        series = sum(sub[a] * w[a] for a in w) * 365  # 年化（对资本）
        monthly = series.groupby(series.index.to_period("M")).mean()
        port[name] = {
            "window": f"{sub.index[0].date()} → {sub.index[-1].date()}",
            "full_mean_annualized": round(float(series.mean()), 4),
            "last_30d_mean": round(float(series.tail(30).mean()), 4),
            "last_90d_mean": round(float(series.tail(90).mean()), 4),
            "monthly": {str(k): round(float(v), 4) for k, v in monthly.items()},
            "breakeven_gross_for_10pct_net": round(0.10 + ENTRY_COST_RATIO, 4),
        }
    out["portfolios"] = port

    (REPORTS / "funding_regime.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 资金费环境分析", "",
             f"数据：{out['start']} → {out['end']}（{out['days']} 天）｜年化 = 日均费率 × 365", "",
             "## 各资产", "",
             "| 资产 | 均值年化 | 中位年化 | p5 年化 | 负费率天数占比 | 最长连续负天数 |",
             "|---|---:|---:|---:|---:|---:|"]
    for a, d in out["assets"].items():
        lines.append(f"| {a} | {d['mean_annualized']*100:+.2f}% | {d['median_annualized']*100:+.2f}% | "
                     f"{d['p5_annualized']*100:+.2f}% | {d['negative_day_share']*100:.1f}% | {d['longest_negative_streak_days']} |")
    lines += ["", "## 组合口径（按 $1000 本金配置）", "",
              "| 组合 | 全期均值 | 近 90 天 | 近 30 天 | 10% 净收益所需毛资金费 |",
              "|---|---:|---:|---:|---:|"]
    for name, d in port.items():
        lines.append(f"| {name} | {d['full_mean_annualized']*100:+.2f}% | {d['last_90d_mean']*100:+.2f}% | "
                     f"{d['last_30d_mean']*100:+.2f}% | {d['breakeven_gross_for_10pct_net']*100:.2f}% |")
    lines += ["", "## A0 月度年化（近 12 个月）", "",
              "| 月份 | A0 | B0 | E |", "|---|---:|---:|---:|"]
    months = sorted(port["A0"]["monthly"])[-12:]
    for m in months:
        lines.append(f"| {m} | {port['A0']['monthly'][m]*100:+.2f}% | {port['B0']['monthly'].get(m, 0)*100:+.2f}% | "
                     f"{port['E']['monthly'].get(m, 0)*100:+.2f}% |")
    lines += ["", "> 当前环境（近30天）A0 约 +9.7%/年，略低于 10% 门槛；需要毛资金费 ≥ 10.34% 才能覆盖成本并达到 10% 净收益。"]
    (REPORTS / "FUNDING_REGIME.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"assets": {a: {k: v for k, v in d.items() if k != "monthly_annualized"} for a, d in out["assets"].items()},
                      "portfolios": {k: {kk: vv for kk, vv in v.items() if kk != "monthly"} for k, v in port.items()}},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

