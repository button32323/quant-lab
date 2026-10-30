#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多资产（小市值）资金费 carry 组合回测：分散化是否改善风险调整收益。

数据：R174A 原始 funding（逐小时）+ 现货/永续 1d K 线（8 个小市值资产）。
口径：等权 sleeve，每资产 1x delta 中性；建仓成本 0.415% × 名义。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import hyperliquid as hl  # noqa: E402

DATA = ROOT / "data" / "raw" / "R174A" / "data"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
ENTRY_COST = 0.00045 + 0.00070 + 2 * 0.0015
CAPITAL = 1000.0
ASSETS = ["PURR", "HYPE", "AZTEC", "STABLE"]


def max_leverage() -> dict[str, float]:
    meta = hl.post({"type": "meta"})["universe"]
    return {m["name"]: float(m.get("maxLeverage", 10)) for m in meta}


def load_asset(asset: str) -> pd.DataFrame:
    fund = pd.DataFrame(json.loads((DATA / "funding" / f"{asset}.json").read_text()))
    fund["date"] = pd.to_datetime(fund["time"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    fund["rate"] = fund["fundingRate"].astype(float)
    fund_day = fund.groupby("date")["rate"].sum().rename(f"{asset}_fund_day")
    spot = pd.DataFrame(json.loads((DATA / "candles" / f"1d_spot_{asset}.json").read_text()))
    spot["date"] = pd.to_datetime(spot["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    spot = spot.sort_values("date").drop_duplicates("date")
    spot[f"{asset}_spot_ret"] = spot["c"].astype(float).pct_change()
    perp = pd.DataFrame(json.loads((DATA / "candles" / f"1d_perp_{asset}.json").read_text()))
    perp["date"] = pd.to_datetime(perp["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    perp = perp.sort_values("date").drop_duplicates("date")
    perp[f"{asset}_perp_ret"] = perp["c"].astype(float).pct_change()
    df = spot[["date", f"{asset}_spot_ret"]].merge(perp[["date", f"{asset}_perp_ret"]], on="date")
    df = df.merge(fund_day, on="date").dropna().reset_index(drop=True)
    return df


def simulate(merged: pd.DataFrame, assets: list[str], lev: dict, capital: float) -> dict:
    w = 1.0 / len(assets)
    notionals = {a: w * capital / (1 + 1 / lev.get(a, 10)) for a in assets}
    total = sum(notionals.values())
    funding = np.zeros(len(merged))
    basis = np.zeros(len(merged))
    for a, n in notionals.items():
        funding += n * merged[f"{a}_fund_day"].to_numpy()
        basis += n * (merged[f"{a}_spot_ret"].to_numpy() - merged[f"{a}_perp_ret"].to_numpy())
    pnl = funding + basis
    pnl[0] -= total * ENTRY_COST
    eq = capital + np.cumsum(pnl)
    dates = merged["date"]
    days = max((dates.iloc[-1] - dates.iloc[0]).days, 1)
    rets = np.diff(eq) / eq[:-1]
    vol = float(np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 else 0.0
    sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 and np.std(rets, ddof=1) > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    mdd = float(np.max((peak - eq) / peak))
    return {"assets": assets, "window": f"{dates.iloc[0].date()} → {dates.iloc[-1].date()}", "days": len(merged),
            "cagr": round(float((eq[-1] / capital) ** (365 / days) - 1), 6),
            "mdd": round(mdd, 6), "sharpe": round(sharpe, 4),
            "funding_usd": round(float(funding.sum()), 2), "basis_usd": round(float(basis.sum()), 2),
            "min_notional": round(min(notionals.values()), 2)}


def main() -> int:
    lev = max_leverage()
    frames = {a: load_asset(a) for a in ASSETS}
    results = {}
    for n in [2, 3, 4]:
        subset = ASSETS[:n]
        merged = frames[subset[0]]
        for a in subset[1:]:
            merged = merged.merge(frames[a], on="date", how="inner")
        merged = merged.sort_values("date").reset_index(drop=True)
        if len(merged) < 60:
            results[f"{n}资产"] = {"error": f"共同窗口不足: {len(merged)} 天"}
            continue
        results[f"{n}资产"] = simulate(merged, subset, lev, CAPITAL)
        # 同期 A0 基准（PURR+HYPE，限制在同一窗口）
        a0 = merged[[c for c in merged.columns if c.startswith(("PURR_", "HYPE_"))]]
        base = simulate(pd.concat([merged[["date"]], a0], axis=1), ["PURR", "HYPE"], lev, CAPITAL)
        results[f"{n}资产_A0基准"] = base

    out = {"capital": CAPITAL, "leverage": {a: lev.get(a) for a in ASSETS}, "results": results}
    (REPORTS / "carry_multiasset.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 多资产小市值 carry 组合", "", f"本金 ${CAPITAL:.0f}｜等权 sleeve｜1x delta 中性｜成本 0.415%/边", "",
             "| 组合 | 窗口 | 年化 | 最大回撤 | Sharpe | 最小名义$ |", "|---|---|---:|---:|---:|---:|"]
    for name, r in results.items():
        if "error" in r:
            lines.append(f"| {name} | — | — | — | — | {r['error']} |")
        else:
            lines.append(f"| {name} | {r['window']}（{r['days']}天） | {r['cagr']*100:+.2f}% | {r['mdd']*100:.2f}% | "
                         f"{r['sharpe']:.2f} | ${r['min_notional']:.1f} |")
    lines += ["", "> 资产越多，共同窗口越短；AZTEC 2026-02 上线、STABLE 2025-12 上线。分散化效果需结合窗口长度解读。"]
    (REPORTS / "CARRY_MULTIASSET.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
