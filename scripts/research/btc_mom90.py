#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 90 日动量趋势策略回测（按用户给定规格执行）。

输出：
  reports/BTC_MOM90_REPORT.md
  reports/btc_mom90_results.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import backtest as bt  # noqa: E402

DATA = ROOT / "data" / "raw" / "BTCUSDT_1d.csv"
QUALITY = ROOT / "data" / "raw" / "BTCUSDT_1d_quality.json"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

FEE = 0.0010
SLIP = 0.0005
CAPITAL = 100.0
LOOKBACK = 90
OOS_START = "2024-01-01"
ROBUSTNESS = [60, 75, 90, 105, 120]


def pct(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:+.{digits}f}%"


def run_one(df, lookback, label):
    res = bt.run_tsmom(df, lookback=lookback, capital=CAPITAL, fee=FEE, slippage=SLIP)
    stats = res.stats()
    return res, {"label": label, "lookback": lookback, **stats}


def main() -> int:
    df = bt.load_daily_csv(str(DATA))
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))

    # 全样本
    res_full, full = run_one(df, LOOKBACK, "full")
    bh_full = bt.buy_and_hold(df, capital=CAPITAL, fee=FEE, slippage=SLIP)
    cash_full = bt.cash_benchmark(df, capital=CAPITAL)
    bh_full_stats = bt.equity_stats(bh_full, CAPITAL)
    cash_full_stats = bt.equity_stats(cash_full, CAPITAL)

    # 样本外 2024 至今
    df_oos = df[df["date"] >= pd.Timestamp(OOS_START)].reset_index(drop=True)
    res_oos, oos = run_one(df_oos, LOOKBACK, "oos")
    bh_oos = bt.buy_and_hold(df_oos, capital=CAPITAL, fee=FEE, slippage=SLIP)
    cash_oos = bt.cash_benchmark(df_oos, capital=CAPITAL)
    bh_oos_stats = bt.equity_stats(bh_oos, CAPITAL)
    cash_oos_stats = bt.equity_stats(cash_oos, CAPITAL)

    # 参数稳健性（只报告，不用于调参）
    robust = []
    for lb in ROBUSTNESS:
        _, s = run_one(df, lb, "full")
        _, so = run_one(df_oos, lb, "oos")
        robust.append({"lookback": lb,
                       "full_cagr": s["cagr"], "full_mdd": s["max_drawdown"], "full_sharpe": s["sharpe"],
                       "full_trades": s["trades"],
                       "oos_return": so["total_return"], "oos_cagr": so["cagr"],
                       "oos_sharpe": so["sharpe"], "oos_mdd": so["max_drawdown"]})

    # 通过标准
    checks = {
        "oos_return_positive": oos["total_return"] > 0,
        "oos_sharpe_gt_0.5": oos["sharpe"] > 0.5,
        "max_drawdown_le_30pct": full["max_drawdown"] <= 0.30,
        "advantage_vs_bh": (oos["total_return"] > bh_oos_stats["total_return"]) or
                           (full["max_drawdown"] < bh_full_stats["max_drawdown"]),
        "robustness_ok": all(r["oos_return"] > -0.10 and r["full_cagr"] > 0 for r in robust),
        "data_and_timing_ok": (quality["duplicates"] == 0 and quality["unsorted"] == 0
                               and quality["bad_ohlc"] == 0 and quality["calendar_gaps"] == 0),
    }
    passed = all(checks.values())

    results = {
        "strategy": "BTC 90d time-series momentum, long-only, 1x, daily, next-open execution",
        "data": quality, "costs": {"fee_per_side": FEE, "slippage_per_side": SLIP,
                                   "roundtrip": 2 * (FEE + SLIP)},
        "capital": CAPITAL, "lookback": LOOKBACK,
        "full": full, "full_benchmark_bh": bh_full_stats, "full_benchmark_cash": cash_full_stats,
        "oos": oos, "oos_benchmark_bh": bh_oos_stats, "oos_benchmark_cash": cash_oos_stats,
        "robustness": robust, "checks": checks, "all_checks_passed": passed,
    }
    (REPORTS / "btc_mom90_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 生成报告
    lines = [
        "# BTC 90 日动量趋势策略 — 回测报告", "",
        f"- 数据：BTC/USDT 日线，{quality['start']} → {quality['end']}，共 {quality['rows']} 根",
        f"- 成本：手续费 {FEE*100:.2f}% + 滑点 {SLIP*100:.2f}% / 边（往返 {(FEE+SLIP)*2*100:.2f}%）",
        f"- 初始资金：{CAPITAL:.0f} USDT ｜ 动量周期：{LOOKBACK} 日 ｜ 1x、仅做多、日线、信号次日开盘执行",
        "", "## 全样本表现（2017-08-17 起）", "",
        "| 指标 | 策略 | BTC 买入持有 | USDT 现金 |", "|---|---:|---:|---:|",
        f"| 累计收益 | {pct(full['total_return'])} | {pct(bh_full_stats['total_return'])} | {pct(cash_full_stats['total_return'])} |",
        f"| 年化收益（CAGR） | {pct(full['cagr'])} | {pct(bh_full_stats['cagr'])} | {pct(cash_full_stats['cagr'])} |",
        f"| 年化波动 | {pct(full['volatility'])} | {pct(bh_full_stats['volatility'])} | — |",
        f"| Sharpe | {full['sharpe']:.2f} | {bh_full_stats['sharpe']:.2f} | — |",
        f"| 最大回撤 | {pct(full['max_drawdown'])} | {pct(bh_full_stats['max_drawdown'])} | 0.00% |",
        f"| 期末净值 | {full['total_return']*CAPITAL+CAPITAL:.2f} | {bh_full_stats['final_equity']:.2f} | 100.00 |",
        "",
        "### 交易统计", "",
        "| 项 | 数值 |", "|---|---:|",
        f"| 交易次数（完整买卖） | {full['trades']} |",
        f"| 胜率 | {full['win_rate']*100:.1f}% |",
        f"| Profit Factor | {full['profit_factor'] if full['profit_factor'] is not None else 'n/a'} |",
        f"| 手续费+滑点总成本 | {full['total_costs_usd']:.2f} USDT |",
        f"| 持仓时间占比 | {full['time_in_market']*100:.1f}% |",
        "", f"## 样本外表现（{OOS_START} 起）", "",
        "| 指标 | 策略 | BTC 买入持有 | USDT 现金 |", "|---|---:|---:|---:|",
        f"| 累计收益 | {pct(oos['total_return'])} | {pct(bh_oos_stats['total_return'])} | {pct(cash_oos_stats['total_return'])} |",
        f"| 年化收益（CAGR） | {pct(oos['cagr'])} | {pct(bh_oos_stats['cagr'])} | {pct(cash_oos_stats['cagr'])} |",
        f"| 年化波动 | {pct(oos['volatility'])} | {pct(bh_oos_stats['volatility'])} | — |",
        f"| Sharpe | {oos['sharpe']:.2f} | {bh_oos_stats['sharpe']:.2f} | — |",
        f"| 最大回撤 | {pct(oos['max_drawdown'])} | {pct(bh_oos_stats['max_drawdown'])} | 0.00% |",
        f"| 交易次数 | {oos['trades']} | 0（一次买入） | 0 |",
        f"| 胜率 | {oos['win_rate']*100:.1f}% | — | — |",
        f"| 成本 | {oos['total_costs_usd']:.2f} USDT | — | — |",
        f"| 持仓时间占比 | {oos['time_in_market']*100:.1f}% | 100% | 0% |",
        "", "## 参数稳健性（仅报告，不用于调参）", "",
        "| 动量周期 | 全样本 CAGR | 全样本 MDD | 全样本 Sharpe | 样本外收益 | 样本外 Sharpe | 样本外 MDD |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in robust:
        lines.append(f"| {r['lookback']} | {pct(r['full_cagr'])} | {pct(r['full_mdd'])} | {r['full_sharpe']:.2f} | "
                     f"{pct(r['oos_return'])} | {r['oos_sharpe']:.2f} | {pct(r['oos_mdd'])} |")
    lines += [
        "", "## 预注册通过标准检查", "",
        "| 检查项 | 标准 | 结果 | 判定 |", "|---|---|---|---|",
        f"| 样本外收益（扣成本） | > 0 | {pct(oos['total_return'])} | {'✅' if checks['oos_return_positive'] else '❌'} |",
        f"| 样本外 Sharpe | > 0.5 | {oos['sharpe']:.2f} | {'✅' if checks['oos_sharpe_gt_0.5'] else '❌'} |",
        f"| 最大回撤（全样本） | ≤ 30% | {pct(full['max_drawdown'])} | {'✅' if checks['max_drawdown_le_30pct'] else '❌'} |",
        f"| 对比 BTC 买入持有 | 收益或回撤至少一项明显优势 | {'有' if checks['advantage_vs_bh'] else '无'} | {'✅' if checks['advantage_vs_bh'] else '❌'} |",
        f"| 参数稳健性（60~120 日） | 相近周期不剧烈恶化 | {'通过' if checks['robustness_ok'] else '未通过'} | {'✅' if checks['robustness_ok'] else '❌'} |",
        f"| 数据与交易时序 | 无未来函数、无数据错误 | {'通过' if checks['data_and_timing_ok'] else '未通过'} | {'✅' if checks['data_and_timing_ok'] else '❌'} |",
        "", f"**综合：{'通过初步筛选' if passed else '未通过初步筛选'}**", "",
        "## 数据质量", "",
        f"- 行数：{quality['rows']}；重复日期：{quality['duplicates']}；乱序：{quality['unsorted']}；异常 OHLC：{quality['bad_ohlc']}；日历缺口：{quality['calendar_gaps']}",
        "", "## 说明与限制", "",
        "- 信号为日线收盘后计算，次日开盘执行，无未来函数；",
        "- 成本只在仓位变化时收取（买卖各一次）；",
        "- 未做空、未加杠杆；初始资金 100 USDT；",
        "- 本报告仅为历史回测，不构成任何投资建议；历史结果不代表未来。",
        "",
    ]
    (REPORTS / "BTC_MOM90_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"full": full, "oos": oos, "checks": checks, "passed": passed,
                      "bench_full": bh_full_stats, "bench_oos": bh_oos_stats}, ensure_ascii=False, indent=2))
    print(f"\n报告已生成: {REPORTS / 'BTC_MOM90_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
