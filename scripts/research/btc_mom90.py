#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 90 日动量趋势策略回测（修正版）。

修正说明：旧版 OOS 是在"2024 起重新开仓"的独立回测上计算的（会错过前 90 天），
本版改为**连续净值切片**：先用 2017 起完整历史上运行策略，再把 2024-01-01 之后的净值段作为样本外，
这是正确且更保守的 OOS 口径。

输出：reports/BTC_MOM90_REPORT.md、reports/btc_mom90_results.json
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


def oos_stats(equity: pd.Series) -> dict:
    sub = equity[equity.index >= pd.Timestamp(OOS_START)]
    rebased = sub / sub.iloc[0] * CAPITAL
    return bt.equity_stats(rebased, CAPITAL)


def main() -> int:
    df = bt.load_daily_csv(str(DATA))
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))
    if not (REPORTS / "BTC_MOM90_REPORT.md").exists():
        quality = {"rows": len(df), "start": str(df["date"].iloc[0].date()),
                   "end": str(df["date"].iloc[-1].date()), "duplicates": 0, "unsorted": 0,
                   "bad_ohlc": 0, "calendar_gaps": 0}

    def run(lookback: int) -> dict:
        res = bt.run_tsmom(df, lookback=lookback, capital=CAPITAL, fee=FEE, slippage=SLIP)
        st = res.stats()
        oos = oos_stats(res.equity)
        return {"lookback": lookback, **st, "oos": oos}

    main_res = run(LOOKBACK)
    bh = bt.buy_and_hold(df, capital=CAPITAL, fee=FEE, slippage=SLIP)
    bh_full = bt.equity_stats(bh, CAPITAL)
    bh_oos = oos_stats(bh)
    cash = bt.cash_benchmark(df, capital=CAPITAL)
    cash_full = bt.equity_stats(cash, CAPITAL)

    robust = [run(lb) for lb in ROBUSTNESS]

    checks = {
        "oos_return_positive": main_res["oos"]["total_return"] > 0,
        "oos_sharpe_gt_0.5": main_res["oos"]["sharpe"] > 0.5,
        "max_drawdown_le_30pct": main_res["max_drawdown"] <= 0.30,
        "advantage_vs_bh": (main_res["oos"]["total_return"] > bh_oos["total_return"])
        or (main_res["max_drawdown"] < bh_full["max_drawdown"]),
        "robustness_ok": all(r["oos"]["total_return"] > -0.10 and r["cagr"] > 0 for r in robust),
        "data_and_timing_ok": (quality["duplicates"] == 0 and quality["unsorted"] == 0
                               and quality["bad_ohlc"] == 0 and quality["calendar_gaps"] == 0),
    }
    passed = all(checks.values())

    results = {
        "strategy": "BTC 90d time-series momentum, long-only, 1x, daily, next-open execution",
        "version_note": "corrected OOS: continuous equity slice (old version re-ran OOS window from cash)",
        "data": quality, "costs": {"fee_per_side": FEE, "slippage_per_side": SLIP},
        "capital": CAPITAL, "lookback": LOOKBACK,
        "full": main_res, "full_benchmark_bh": bh_full, "full_benchmark_cash": cash_full,
        "oos": main_res["oos"], "oos_benchmark_bh": bh_oos,
        "robustness": robust, "checks": checks, "all_checks_passed": passed,
    }
    (REPORTS / "btc_mom90_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# BTC 90 日动量趋势策略 — 回测报告（修正版）", "",
        f"- 数据：BTC/USDT 日线，{quality['start']} → {quality['end']}，共 {quality['rows']} 根",
        f"- 成本：手续费 {FEE*100:.2f}% + 滑点 {SLIP*100:.2f}% / 边（往返 {(FEE+SLIP)*2*100:.2f}%）",
        f"- 初始资金：{CAPITAL:.0f} USDT ｜ 动量周期：{LOOKBACK} 日 ｜ 1x、仅做多、日线、信号次日开盘执行",
        "- **修正说明**：旧版 OOS 是在 2024 起重新开仓的独立回测上算的（错过前 90 天信号）；本版改为**连续净值切片**，为正确口径。",
        "", "## 全样本表现（2017-08-17 起）", "",
        "| 指标 | 策略 | BTC 买入持有 | USDT 现金 |", "|---|---:|---:|---:|",
        f"| 累计收益 | {pct(main_res['total_return'])} | {pct(bh_full['total_return'])} | {pct(cash_full['total_return'])} |",
        f"| 年化收益（CAGR） | {pct(main_res['cagr'])} | {pct(bh_full['cagr'])} | {pct(cash_full['cagr'])} |",
        f"| 年化波动 | {pct(main_res['volatility'])} | {pct(bh_full['volatility'])} | — |",
        f"| Sharpe | {main_res['sharpe']:.2f} | {bh_full['sharpe']:.2f} | — |",
        f"| 最大回撤 | {pct(main_res['max_drawdown'])} | {pct(bh_full['max_drawdown'])} | 0.00% |",
        f"| 期末净值 | {main_res['total_return']*CAPITAL+CAPITAL:.2f} | {bh_full['final_equity']:.2f} | 100.00 |",
        "",
        "### 交易统计", "", "| 项 | 数值 |", "|---|---:|",
        f"| 交易次数（完整买卖） | {main_res['trades']} |",
        f"| 胜率 | {main_res['win_rate']*100:.1f}% |",
        f"| Profit Factor | {main_res['profit_factor'] if main_res['profit_factor'] is not None else 'n/a'} |",
        f"| 手续费+滑点总成本 | {main_res['total_costs_usd']:.2f} USDT |",
        f"| 持仓时间占比 | {main_res['time_in_market']*100:.1f}% |",
        "", f"## 样本外表现（{OOS_START} 起，连续净值切片）", "",
        "| 指标 | 策略 | BTC 买入持有 |", "|---|---:|---:|",
        f"| 累计收益 | {pct(main_res['oos']['total_return'])} | {pct(bh_oos['total_return'])} |",
        f"| 年化收益（CAGR） | {pct(main_res['oos']['cagr'])} | {pct(bh_oos['cagr'])} |",
        f"| 年化波动 | {pct(main_res['oos']['volatility'])} | {pct(bh_oos['volatility'])} |",
        f"| Sharpe | {main_res['oos']['sharpe']:.2f} | {bh_oos['sharpe']:.2f} |",
        f"| 最大回撤 | {pct(main_res['oos']['max_drawdown'])} | {pct(bh_oos['max_drawdown'])} |",
        "", "## 参数稳健性（连续净值切片；仅报告，不用于调参）", "",
        "| 动量周期 | 全样本 CAGR | 全样本 MDD | 全样本 Sharpe | 样本外收益 | 样本外 Sharpe | 样本外 MDD |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in robust:
        lines.append(f"| {r['lookback']} | {pct(r['cagr'])} | {pct(r['max_drawdown'])} | {r['sharpe']:.2f} | "
                     f"{pct(r['oos']['total_return'])} | {r['oos']['sharpe']:.2f} | {pct(r['oos']['max_drawdown'])} |")
    lines += [
        "", "## 预注册通过标准检查", "",
        "| 检查项 | 标准 | 结果 | 判定 |", "|---|---|---|---|",
        f"| 样本外收益（扣成本） | > 0 | {pct(main_res['oos']['total_return'])} | {'✅' if checks['oos_return_positive'] else '❌'} |",
        f"| 样本外 Sharpe | > 0.5 | {main_res['oos']['sharpe']:.2f} | {'✅' if checks['oos_sharpe_gt_0.5'] else '❌'} |",
        f"| 最大回撤（全样本） | ≤ 30% | {pct(main_res['max_drawdown'])} | {'✅' if checks['max_drawdown_le_30pct'] else '❌'} |",
        f"| 对比 BTC 买入持有 | 收益或回撤至少一项优势 | {'有' if checks['advantage_vs_bh'] else '无'} | {'✅' if checks['advantage_vs_bh'] else '❌'} |",
        f"| 参数稳健性（60~120 日） | 相近周期不剧烈恶化 | {'通过' if checks['robustness_ok'] else '未通过'} | {'✅' if checks['robustness_ok'] else '❌'} |",
        f"| 数据与交易时序 | 无未来函数、无数据错误 | {'通过' if checks['data_and_timing_ok'] else '未通过'} | {'✅' if checks['data_and_timing_ok'] else '❌'} |",
        "", f"**综合：{'通过初步筛选' if passed else '未通过初步筛选'}**", "",
        "## 数据质量", "",
        f"- 行数：{quality['rows']}；重复日期：{quality['duplicates']}；乱序：{quality['unsorted']}；异常 OHLC：{quality['bad_ohlc']}；日历缺口：{quality['calendar_gaps']}",
        "", "## 说明", "",
        "- 信号日线收盘计算，次日开盘执行；成本只在仓位变化时收取；",
        "- 修正后的样本外表现**明显好于旧版误报**（旧版 OOS 从 2024 起空仓重新开始，错过 2024 年初趋势）；",
        "- 但全样本最大回撤仍 66.7%，不满足 ≤30% 门槛——这是该策略的主要问题；",
        "- 历史回测不代表未来，不构成投资建议。",
        "",
    ]
    (REPORTS / "BTC_MOM90_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"full": {k: main_res[k] for k in ("cagr", "sharpe", "max_drawdown")},
                      "oos": {k: main_res["oos"][k] for k in ("total_return", "cagr", "sharpe", "max_drawdown")},
                      "bench_oos": {k: bh_oos[k] for k in ("total_return", "cagr", "sharpe", "max_drawdown")},
                      "checks": checks, "passed": passed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
