#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量分析：PURR/HYPE 资金费 carry 在不同本金档位下的可部署上限。

口径：单资产名义 ≤ 1% × min(现货日成交额, 永续日成交额)（取近 30 日均值）。
输出：reports/CAPACITY_TIERS.md / .json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
R174A = ROOT / "data" / "raw" / "R174A" / "data" / "panels"
REPORTS = ROOT / "reports"
ASSETS = {"PURR": 3.0, "HYPE": 10.0}
VOL_FRAC = 0.01
MIN_ORDER_USD = 10.0
TIERS = [27, 50, 100, 300, 500, 1000, 3000, 12000, 20000]
ALLOCATIONS = {
    "A0_small": {"PURR": 0.5, "HYPE": 0.5},
    "E_75_25": {"PURR": 0.375, "HYPE": 0.375},
}


def asset_capacity(asset: str, window: int = 30) -> dict:
    df = pd.read_csv(R174A / f"daily_{asset}.csv", parse_dates=["day"])
    df = df[df["tradable"] == 1].dropna(subset=["spot_vol_quote"])
    recent = df.tail(window)
    spot_vol = float(recent["spot_vol_quote"].mean())
    perp_vol = float(recent["perp_vol_quote"].mean()) if "perp_vol_quote" in recent else spot_vol
    cap_notional = VOL_FRAC * min(spot_vol, perp_vol)
    return {"asset": asset, "window_days": window,
            "spot_vol_usd": round(spot_vol, 0), "perp_vol_usd": round(perp_vol, 0),
            "capacity_notional_usd": round(cap_notional, 0),
            "capacity_utilization_pct": round(cap_notional / spot_vol * 100, 2) if spot_vol else 0}


def main() -> int:
    caps = {a: asset_capacity(a) for a in ASSETS}
    out = {"vol_frac": VOL_FRAC, "min_order_usd": MIN_ORDER_USD, "assets": caps, "allocations": {}}
    for name, weights in ALLOCATIONS.items():
        rows = []
        for cap in TIERS:
            row = {"capital": cap, "feasible": True, "min_notional_ok": True, "max_util": 0.0}
            for asset, lev in ASSETS.items():
                w = weights.get(asset, 0.0)
                if w <= 0:
                    continue
                notional = w * cap / (1 + 1 / lev)
                row[f"{asset}_notional"] = round(notional, 2)
                if notional < MIN_ORDER_USD:
                    row["min_notional_ok"] = False
                util = notional / caps[asset]["capacity_notional_usd"]
                row[f"{asset}_util"] = round(util, 4)
                row["max_util"] = max(row["max_util"], util)
            row["feasible"] = row["min_notional_ok"] and row["max_util"] <= 1.0
            rows.append(row)
        # 最大可部署资本
        max_cap = min(caps[asset]["capacity_notional_usd"] * (1 + 1 / lev) / weights[asset]
                      for asset, lev in ASSETS.items() if weights.get(asset, 0) > 0)
        out["allocations"][name] = {"weights": weights, "max_capital_usd": round(max_cap, 0), "rows": rows}

    (REPORTS / "capacity_tiers.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 容量分析：本金档位 vs 可部署上限", "",
             f"口径：单资产名义 ≤ {VOL_FRAC*100:.0f}% × min(现货日成交额, 永续日成交额)，取近 30 日均值。", "",
             "## 当前容量", "",
             "| 资产 | 日成交额(现货) | 日成交额(永续) | 容量上限(名义) |",
             "|---|---:|---:|---:|"]
    for a, c in caps.items():
        lines.append(f"| {a} | ${c['spot_vol_usd']:,.0f} | ${c['perp_vol_usd']:,.0f} | ${c['capacity_notional_usd']:,.0f} |")
    lines += ["", "## 各本金档位（A0：PURR/HYPE 各 50%）", "",
              "| 本金 | PURR 名义 | PURR 使用率 | HYPE 名义 | HYPE 使用率 | 可执行 |",
              "|---:|---:|---:|---:|---:|:---:|"]
    for row in out["allocations"]["A0_small"]["rows"]:
        lines.append(f"| ${row['capital']:,} | ${row.get('PURR_notional',0):,.0f} | {row.get('PURR_util',0)*100:.1f}% | "
                     f"${row.get('HYPE_notional',0):,.0f} | {row.get('HYPE_util',0)*100:.1f}% | "
                     f"{'✅' if row['feasible'] else '❌'} |")
    lines += ["", f"**A0 最大可部署资本：约 ${out['allocations']['A0_small']['max_capital_usd']:,.0f}**（受 PURR 流动性约束）",
              f"**最小可行本金：约 ${MIN_ORDER_USD*(1+1/3)/0.5:,.2f}**（PURR 单腿 ≥ $10）",
              "", "> 容量随成交额波动；下单前应重新计算。"]
    (REPORTS / "CAPACITY_TIERS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
