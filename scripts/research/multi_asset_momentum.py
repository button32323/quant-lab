#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多资产动量策略回测：$100–$1,000 小资金可执行的现货 long-only 方案。

候选：
  M1 BTC/ETH/SOL(+BNB) top-1 动量（90日），每日轮动
  M2 同上，月度轮动
  M3 top-1 动量（60日），每日轮动
  M4 ETH/BTC 相对动量（60日），每日轮动（始终满仓其一）
  M5 正动量资产等权（90日），月度轮动
基准：BTC 买入持有、等权买入持有
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import backtest as bt  # noqa: E402
from quantlab import portfolio as pf  # noqa: E402

RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
FEE = 0.0010
SLIP = 0.0005
CAPITAL = 100.0
OOS_START = "2024-01-01"


def load_all() -> dict[str, pd.DataFrame]:
    frames = {}
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
        p = RAW / f"{sym}_1d.csv"
        if p.exists() and p.stat().st_size > 10_000:
            frames[sym.replace("USDT", "")] = pf.load_symbol_csv(str(p))
    return frames


def slice_stats(eq: pd.Series, start: str) -> dict:
    sub = eq[eq.index >= pd.Timestamp(start)]
    if len(sub) < 10:
        return {}
    rebased = sub / sub.iloc[0] * 100.0
    return bt.equity_stats(rebased, 100.0)


def main() -> int:
    frames = load_all()
    if len(frames) < 3:
        print("数据不足:", list(frames))
        return 1
    symbols = list(frames.keys())
    opens, closes = pf.align_symbols(frames)
    print("symbols:", symbols, "| window:", closes.index[0].date(), "→", closes.index[-1].date(), "| bars:", len(closes))

    strategies: dict[str, pd.DataFrame] = {}
    # M1/M2/M3：top-1 动量
    for name, lb, monthly in [("M1_top1_90d_daily", 90, False), ("M2_top1_90d_monthly", 90, True), ("M3_top1_60d_daily", 60, False)]:
        raw = pf.momentum_weights(closes, lb, mode="top1")
        strategies[name] = pf.monthly_rebalance(raw) if monthly else raw
    # M4：ETH/BTC 相对动量
    if "ETH" in symbols and "BTC" in symbols:
        strategies["M4_eth_btc_rel_60d"] = pf.relative_momentum_weights(closes, "ETH", "BTC", 60)
    # M5：正动量等权、月度
    raw5 = pf.momentum_weights(closes, 90, mode="equal_positive")
    strategies["M5_equal_positive_90d_monthly"] = pf.monthly_rebalance(raw5)

    results = {}
    equity_full = {}
    for name, w in strategies.items():
        res = pf.simulate_weights(opens, closes, w, capital=CAPITAL, fee=FEE, slippage=SLIP)
        equity_full[name] = res.equity
        full = bt.equity_stats(res.equity, CAPITAL)
        oos = slice_stats(res.equity, OOS_START)
        exposure = float(res.weights_used.sum(axis=1).mean()) if not res.weights_used.empty else 0.0
        results[name] = {"full": full, "oos": oos, "costs_usd": round(res.costs, 4),
                         "turnover_usd": round(res.turnover, 2), "avg_exposure": round(exposure, 3)}

    # 基准
    bh_btc = pf.simulate_weights(opens, closes, pd.DataFrame(1.0, index=closes.index, columns=["BTC"]).reindex(columns=symbols).fillna(0.0),
                                 capital=CAPITAL, fee=FEE, slippage=SLIP)
    eqw = pd.DataFrame(1.0 / len(symbols), index=closes.index, columns=symbols)
    # 等权买入持有：只在第一天买入，之后不再调仓（用一次性权重 + 后续权重=0 会卖出；改为固定份额模拟）
    eqw_bh = _buy_and_hold_equal(opens, closes, symbols, CAPITAL, FEE, SLIP)

    benchmarks = {
        "BTC_buy_hold": {"full": bt.equity_stats(bh_btc.equity, CAPITAL), "oos": slice_stats(bh_btc.equity, OOS_START)},
        "equal_weight_buy_hold": {"full": bt.equity_stats(eqw_bh, CAPITAL), "oos": slice_stats(eqw_bh, OOS_START)},
    }

    out = {"symbols": symbols, "window": f"{closes.index[0].date()} → {closes.index[-1].date()}",
           "bars": len(closes), "costs": {"fee": FEE, "slippage": SLIP},
           "strategies": results, "benchmarks": benchmarks}
    (REPORTS / "multi_asset_momentum.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 多资产动量策略回测（现货 long-only）", "",
             f"标的：{'/'.join(symbols)} ｜ 窗口：{out['window']}（{len(closes)} 天）｜ 成本 0.10%+0.05%/边",
             "", "## 全样本", "",
             "| 策略 | 累计收益 | 年化 | 波动 | Sharpe | 最大回撤 | 成本$ | 平均仓位 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, r in results.items():
        f = r["full"]
        lines.append(f"| {name} | {f['total_return']*100:+.1f}% | {f['cagr']*100:+.2f}% | {f['volatility']*100:.1f}% | "
                     f"{f['sharpe']:.2f} | {f['max_drawdown']*100:.2f}% | {r['costs_usd']:.1f} | {r['avg_exposure']*100:.0f}% |")
    for name, r in benchmarks.items():
        f = r["full"]
        lines.append(f"| *{name}* | {f['total_return']*100:+.1f}% | {f['cagr']*100:+.2f}% | {f['volatility']*100:.1f}% | "
                     f"{f['sharpe']:.2f} | {f['max_drawdown']*100:.2f}% | — | — |")
    lines += ["", "## 样本外（2024-01-01 起，按全历史信号、只统计区间净值）", "",
              "| 策略 | 累计收益 | 年化 | Sharpe | 最大回撤 |", "|---|---:|---:|---:|---:|"]
    for name, r in results.items():
        o = r.get("oos") or {}
        lines.append(f"| {name} | {o.get('total_return',0)*100:+.1f}% | {o.get('cagr',0)*100:+.2f}% | "
                     f"{o.get('sharpe',0):.2f} | {o.get('max_drawdown',0)*100:.2f}% |")
    for name, r in benchmarks.items():
        o = r.get("oos") or {}
        lines.append(f"| *{name}* | {o.get('total_return',0)*100:+.1f}% | {o.get('cagr',0)*100:+.2f}% | "
                     f"{o.get('sharpe',0):.2f} | {o.get('max_drawdown',0)*100:.2f}% |")
    lines += ["", "> 小资金（$100–$1,000）下，这些策略的百分比收益与最小下单约束无关；关键看风险调整后收益与回撤。"]

    (REPORTS / "MULTI_ASSET_MOMENTUM.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n报告: {REPORTS / 'MULTI_ASSET_MOMENTUM.md'}")
    return 0


def _buy_and_hold_equal(opens: pd.DataFrame, closes: pd.DataFrame, symbols, capital, fee, slip) -> pd.Series:
    """等权买入并持有（第一天等权买入，之后不调仓）。"""
    cost = fee + slip
    px = opens.iloc[0]
    per = capital / len(symbols)
    units = {s: per / (float(px[s]) * (1 + cost)) for s in symbols}
    eq = []
    for i in range(len(closes)):
        eq.append(sum(units[s] * float(closes[s].iloc[i]) for s in symbols))
    return pd.Series(eq, index=closes.index)


if __name__ == "__main__":
    raise SystemExit(main())
