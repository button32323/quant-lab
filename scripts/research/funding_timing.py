#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资金费环境择时（风控用）：滚动 30 天资金费水平与后续资金费/收益的关系。

输出：reports/FUNDING_TIMING.md / .json
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
CAPITAL = 1000.0
WEIGHTS = {"PURR": 0.5, "HYPE": 0.5}
THRESHOLD = 0.05  # 年化 5% 以下视为环境差


def main() -> int:
    merged = carry.build_combined()
    res = carry.simulate(merged, WEIGHTS, CAPITAL)
    funding_daily = res["funding"]  # 日资金费金额
    ann = funding_daily * 365 / CAPITAL  # 年化（对资本）
    roll30 = ann.rolling(30).mean()
    roll90 = ann.rolling(90).mean()

    # 后续 30 天资金费
    fwd = ann[::-1].rolling(30).mean()[::-1].shift(-30)
    cond = pd.DataFrame({"roll30": roll30, "fwd30": fwd}).dropna()

    buckets = {}
    for name, lo, hi in [("滚动30d <5%", -1, THRESHOLD), ("5–10%", THRESHOLD, 0.10), ("10–20%", 0.10, 0.20), (">20%", 0.20, 9)]:
        sub = cond[(cond["roll30"] > lo) & (cond["roll30"] <= hi)]
        buckets[name] = {"days": int(len(sub)), "share": round(float(len(sub) / len(cond)), 4),
                         "fwd30_mean": round(float(sub["fwd30"].mean()), 4) if len(sub) else None}

    out = {
        "window": f"{merged['date'].iloc[0].date()} → {merged['date'].iloc[-1].date()}",
        "days": len(merged),
        "current": {"ann_funding_30d": round(float(roll30.iloc[-1]), 4),
                    "ann_funding_90d": round(float(roll90.iloc[-1]), 4),
                    "ann_funding_now": round(float(ann.iloc[-1]), 4)},
        "share_below_5pct": round(float((roll30 < THRESHOLD).mean()), 4),
        "share_below_0": round(float((roll30 < 0).mean()), 4),
        "share_above_10pct": round(float((roll30 > 0.10).mean()), 4),
        "buckets": buckets,
        "rule_suggestion": "若滚动30天资金费连续 14 天 < 5%/年（或任意 30 天 < 0），暂停/退出并重新评估环境；不用于预测，只用于风控。",
    }
    (REPORTS / "funding_timing.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 资金费环境与风控阈值", "",
             f"窗口：{out['window']}（{len(merged)} 天）｜ A0 口径（PURR/HYPE 各 50%）", "",
             "## 当前", "",
             f"- 即时年化资金费：{out['current']['ann_funding_now']*100:+.2f}%",
             f"- 滚动 30 天年化：{out['current']['ann_funding_30d']*100:+.2f}%",
             f"- 滚动 90 天年化：{out['current']['ann_funding_90d']*100:+.2f}%", "",
             "## 历史分布", "",
             f"- 滚动 30 天 < 5%/年的天数占比：**{out['share_below_5pct']*100:.1f}%**",
             f"- 滚动 30 天 < 0 的天数占比：{out['share_below_0']*100:.1f}%",
             f"- 滚动 30 天 > 10%/年的天数占比：{out['share_above_10pct']*100:.1f}%", "",
             "## 条件分桶：当前环境 → 后续 30 天平均资金费", "",
             "| 滚动30d 区间 | 天数 | 占比 | 后续30d平均年化 |", "|---|---:|---:|---:|"]
    for name, b in buckets.items():
        lines.append(f"| {name} | {b['days']} | {b['share']*100:.1f}% | "
                     f"{b['fwd30_mean']*100:+.2f}% |" if b["fwd30_mean"] is not None else f"| {name} | {b['days']} | {b['share']*100:.1f}% | n/a |")
    lines += ["", f"**风控规则建议**：{out['rule_suggestion']}",
              "> 这不是收益择时，而是环境恶化时降风险的防守规则；不修改策略参数。"]
    (REPORTS / "FUNDING_TIMING.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
