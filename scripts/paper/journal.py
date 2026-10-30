#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 paper 日记：按 UTC 日汇总 NAV、资金费、日收益。"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOURLY = ROOT / "paper" / "hourly.csv"
JOURNAL = ROOT / "paper" / "JOURNAL.md"


def main() -> int:
    if not HOURLY.exists():
        print("没有 hourly.csv")
        return 1
    rows = list(csv.DictReader(HOURLY.open(encoding="utf-8")))
    if not rows:
        print("暂无数据")
        return 0
    days: dict[str, dict] = {}
    for r in rows:
        day = r["ts"][:10]
        days[day] = r  # 保留当天最后一条
    lines = ["# Paper 日记（UTC 日汇总）", "",
             "| 日期 | NAV($) | 累计资金费($) | 日收益 | 累计收益 |", "|---|---:|---:|---:|---:|"]
    prev_nav = None
    for day in sorted(days):
        r = days[day]
        nav = float(r["nav_usd"])
        fund = float(r["funding_accrued_usd"])
        daily = (nav / prev_nav - 1) if prev_nav else 0.0
        lines.append(f"| {day} | {nav:.2f} | {fund:+.4f} | {daily*100:+.3f}% | {(nav/1000-1)*100:+.3f}% |")
        prev_nav = nav
    JOURNAL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
