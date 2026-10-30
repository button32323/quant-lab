#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告数字一致性检查：关键结论与生成的 JSON 是否一致（回归保护）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def load(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def find_by_capital(results: list, cap: float) -> dict:
    for r in results:
        if int(r.get("capital", -1)) == int(cap):
            return r
    raise KeyError(cap)


def main() -> int:
    checks = []

    tiers = load("carry_capital_tiers.json")
    a0 = find_by_capital(tiers["results"], 1000)
    checks += [
        ("A0 CAGR ≈ 18.08%", abs(a0["cagr"] - 0.180776) < 1e-4),
        ("A0 MDD ≈ 0.74%", abs(a0["max_drawdown"] - 0.007396) < 1e-5),
        ("A0 Sharpe ≈ 4.95", abs(a0["sharpe"] - 4.9544) < 1e-3),
    ]

    majors = load("carry_majors.json")
    m = find_by_capital(majors["results"], 1000)
    checks += [
        ("Majors CAGR ≈ 11.56%", abs(m["cagr"] - 0.115565) < 5e-4),
        ("Majors MDD ≈ 0.68%", abs(m["max_drawdown"] - 0.006759) < 5e-5),
    ]

    combined = load("carry_combined.json")["results"]
    checks += [
        ("组合 A0 年化 ≈ 18.08%", abs(combined["A0_small_only"]["annualized"] - 0.180776) < 1e-4),
        ("组合 E 年化 ≈ 15.54%", abs(combined["E_75_25_small"]["annualized"] - 0.155411) < 1e-4),
    ]

    timing = load("funding_timing.json")
    checks += [("滚动30d资金费 ≈ 9.66%", abs(timing["current"]["ann_funding_30d"] - 0.0966) < 5e-4)]

    paper_state = json.loads((ROOT / "paper" / "state.json").read_text(encoding="utf-8"))
    checks += [("paper 本金 = $1,000", abs(paper_state["capital_usd"] - 1000.0) < 1e-9)]

    bad = 0
    for name, ok in checks:
        print(("OK   " if ok else "FAIL ") + name)
        if not ok:
            bad += 1
    print(f"\n{len(checks) - bad}/{len(checks)} checks passed")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
