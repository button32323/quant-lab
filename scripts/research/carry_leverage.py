#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A0 加杠杆测算（近似）：把名义敞口放大 m 倍，计入借币成本，展示收益/回撤变化。

注意：不模拟强平/保证金追缴（真实风险更高），只用于量级判断。
输出：reports/CARRY_LEVERAGE.md / .json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import carry  # noqa: E402

REPORTS = ROOT / "reports"
CAPITAL = 1000.0
WEIGHTS = {"PURR": 0.5, "HYPE": 0.5}
BORROW_RATE = 0.06  # 借币/保证金资金成本 6%/年（保守假设）
MULTS = [1.0, 1.2, 1.5, 2.0, 3.0]


def main() -> int:
    merged = carry.build_combined()
    base = carry.simulate(merged, WEIGHTS, CAPITAL)
    base_pnl = base["daily_pnl"].to_numpy()  # 已含建仓成本（首日）
    e0 = base["total_notional"] / CAPITAL  # 当前名义/本金 ≈0.83
    days = base["days"]

    results = {}
    for m in MULTS:
        pnl = base_pnl * m
        # 借入资金 = (m-1) × 基础名义，按年化成本逐日计息
        borrow = (m - 1) * base["total_notional"]
        pnl = pnl - borrow * BORROW_RATE / 365.0
        eq = CAPITAL + np.cumsum(pnl)
        total_ret = eq[-1] / CAPITAL - 1
        cagr = (eq[-1] / CAPITAL) ** (365 / days) - 1 if eq[-1] > 0 else -1
        rets = np.diff(eq) / eq[:-1]
        vol = float(np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 else 0
        sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(365)) if np.std(rets, ddof=1) > 0 else 0
        peak = np.maximum.accumulate(eq)
        mdd = float(np.max((peak - eq) / peak))
        results[str(m)] = {
            "exposure_mult": m,
            "exposure_vs_capital": round(e0 * m, 3),
            "borrowed_usd": round(borrow, 2),
            "cagr": round(float(cagr), 4),
            "mdd": round(mdd, 4),
            "sharpe": round(sharpe, 2),
            "vol": round(vol, 4),
        }

    # 资金费转负压力（-0.5×）下的杠杆结果
    stress = {}
    for m in MULTS:
        pnl = (base["funding"].to_numpy() * -0.5 + base["basis"].to_numpy()) * m
        pnl[0] -= base["total_notional"] * carry.ENTRY_COST_RATE * m
        borrow = (m - 1) * base["total_notional"]
        pnl = pnl - borrow * BORROW_RATE / 365.0
        eq = CAPITAL + np.cumsum(pnl)
        peak = np.maximum.accumulate(eq)
        stress[str(m)] = {"cagr": round(float((eq[-1] / CAPITAL) ** (365 / days) - 1), 4),
                          "mdd": round(float(np.max((peak - eq) / peak)), 4)}

    out = {"window": f"{merged['date'].iloc[0].date()} → {merged['date'].iloc[-1].date()}",
           "base_exposure": round(e0, 3), "borrow_rate": BORROW_RATE,
           "results": results, "stress_funding_negative": stress}
    (REPORTS / "carry_leverage.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# A0 加杠杆测算（近似，未模拟强平）", "",
             f"窗口：{out['window']} ｜ 本金 ${CAPITAL:.0f} ｜ 借贷成本 {BORROW_RATE*100:.0f}%/年 ｜ 当前名义/本金 = {e0:.2f}x",
             "", "| 名义倍数 | 名义/本金 | 借入$ | 年化 | 最大回撤 | Sharpe |", "|---:|---:|---:|---:|---:|---:|"]
    for k, r in results.items():
        lines.append(f"| {r['exposure_mult']}x | {r['exposure_vs_capital']:.2f}x | ${r['borrowed_usd']:.0f} | "
                     f"{r['cagr']*100:+.2f}% | {r['mdd']*100:.2f}% | {r['sharpe']:.2f} |")
    lines += ["", "## 压力测试：资金费持续为负（×−0.5）", "", "| 名义倍数 | 年化 | 最大回撤 |", "|---:|---:|---:|"]
    for k, r in stress.items():
        lines.append(f"| {k}x | {r['cagr']*100:+.2f}% | {r['mdd']*100:.2f}% |")
    lines += ["", "> 重要：本测算未包含**强制平仓/保证金追缴**，真实杠杆的风险高于此表；回撤随倍数近似线性放大，资金费转负时亏损同样放大。"]
    (REPORTS / "CARRY_LEVERAGE.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
