#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A0 内部权重敏感性：PURR/HYPE 不同配比（总杠杆不变，1x）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import carry  # noqa: E402

REPORTS = ROOT / "reports"
CAPITAL = 1000.0
ALLOCS = {
    "50/50（默认）": {"PURR": 0.5, "HYPE": 0.5},
    "75/25 PURR偏重": {"PURR": 0.75, "HYPE": 0.25},
    "25/75 HYPE偏重": {"PURR": 0.25, "HYPE": 0.75},
    "100% PURR": {"PURR": 1.0},
    "100% HYPE": {"HYPE": 1.0},
}


def main() -> int:
    merged = carry.build_combined()
    out = {"window": f"{merged['date'].iloc[0].date()} → {merged['date'].iloc[-1].date()}",
           "capital": CAPITAL, "results": {}}
    for name, w in ALLOCS.items():
        r = carry.simulate(merged, w, CAPITAL)
        out["results"][name] = {
            "cagr": round(r["cagr"], 6), "mdd": round(r["mdd"], 6),
            "sharpe": round(r["sharpe"], 4), "vol": round(r["vol"], 6),
            "funding_usd": round(float(r["funding"].sum()), 2),
            "basis_usd": round(float(r["basis"].sum()), 2),
            "min_notional": round(min(r["notionals"].values()), 2),
        }
    (REPORTS / "allocation_sensitivity.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# A0 内部权重敏感性（PURR/HYPE 配比）", "",
             f"窗口：{out['window']} ｜ 本金 ${CAPITAL:.0f} ｜ 总杠杆 1x", "",
             "| 配比 | 年化 | 最大回撤 | Sharpe | 最小名义$ |", "|---|---:|---:|---:|---:|"]
    for name, r in out["results"].items():
        lines.append(f"| {name} | {r['cagr']*100:+.2f}% | {r['mdd']*100:.2f}% | {r['sharpe']:.2f} | ${r['min_notional']:.1f} |")
    lines += ["", "> 结论若 50/50 与各偏重配比差异不大，说明方案对配比不敏感；若差异大，50/50 只是现状选择，需进一步验证。"]
    (REPORTS / "ALLOCATION_SENSITIVITY.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
