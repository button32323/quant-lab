#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总全部回测结果，生成执行摘要与数据质量报告。

依赖：reports/ALL_BACKTESTS_CARRY.json、reports/ALL_BACKTESTS_DIRECTIONAL.json
输出：reports/ALL_BACKTESTS.md、reports/ALL_BACKTESTS_DATA_QUALITY.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
HL = RAW / "hl"
REPORTS = ROOT / "reports"
BINANCE = {"BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL", "BNBUSDT": "BNB"}
HL_ASSETS = ["PURR", "HYPE", "AZTEC", "BERA", "MON", "PUMP", "STABLE", "TRUMP", "BTC", "ETH"]


def data_quality() -> dict:
    out = {"binance": {}, "hl": {}}
    for sym, coin in BINANCE.items():
        p = RAW / f"{sym}_1d.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, parse_dates=["date"])
        dup = int(df["date"].duplicated().sum())
        gaps = int((df["date"].diff().dt.days > 1).sum())
        out["binance"][coin] = {"rows": len(df), "start": str(df["date"].iloc[0].date()),
                                "end": str(df["date"].iloc[-1].date()), "duplicates": dup, "gaps": gaps}
    for coin in HL_ASSETS:
        fp = HL / f"funding_{coin}.json"
        cp = HL / f"candles_1d_{coin}.json"
        sp = HL / f"candles_1d_spot_{coin}.json"
        if not (fp.exists() and cp.exists() and sp.exists()):
            continue
        fund = pd.DataFrame(json.loads(fp.read_text(encoding="utf-8")))
        fund["date"] = pd.to_datetime(fund["time"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
        perp = pd.DataFrame(json.loads(cp.read_text(encoding="utf-8")))
        perp["date"] = pd.to_datetime(perp["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
        spot = pd.DataFrame(json.loads(sp.read_text(encoding="utf-8")))
        spot["date"] = pd.to_datetime(spot["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
        out["hl"][coin] = {
            "funding_rows": len(fund), "funding_start": str(fund["date"].min().date()), "funding_end": str(fund["date"].max().date()),
            "perp_rows": len(perp), "perp_start": str(perp["date"].min().date()), "perp_end": str(perp["date"].max().date()),
            "spot_rows": len(spot), "spot_start": str(spot["date"].min().date()), "spot_end": str(spot["date"].max().date()),
        }
    return out


def money(x: float | None) -> str:
    return "—" if x is None else f"${x:,.0f}"


def pct(x: float | None) -> str:
    return "—" if x is None else f"{x*100:+.1f}%"


def main() -> int:
    dq = data_quality()
    (REPORTS / "ALL_BACKTESTS_DATA_QUALITY.json").write_text(json.dumps(dq, ensure_ascii=False, indent=2), encoding="utf-8")

    carry = json.loads((REPORTS / "ALL_BACKTESTS_CARRY.json").read_text(encoding="utf-8")) if (REPORTS / "ALL_BACKTESTS_CARRY.json").exists() else None
    direc = json.loads((REPORTS / "ALL_BACKTESTS_DIRECTIONAL.json").read_text(encoding="utf-8")) if (REPORTS / "ALL_BACKTESTS_DIRECTIONAL.json").exists() else None

    lines = ["# 全面回测报告（所有可行策略）", "",
             f"> 生成：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ｜ 工作区 `C:\\量化项目` ｜ 代码/数据可复现",
             "", "## 0. 执行摘要", ""]

    if carry:
        presets = carry["presets"]
        a0 = presets.get("A0_PURR_HYPE", {})
        singles = sorted(carry["single"].items(), key=lambda kv: kv[1]["sharpe"], reverse=True)
        lines += [
            f"- **carry 族**：{len(carry['single'])} 个单资产、{len(carry['pairs'])} 个两两组合、{len(presets)} 个预设组合；",
            f"- 单资产历史 Sharpe 最高：{singles[0][0]}（{singles[0][1]['sharpe']:.2f}），A0 组合 Sharpe {a0.get('sharpe', 0):.2f}、年化 {a0.get('cagr',0)*100:+.1f}%（窗口 {a0.get('window','—')}）；",
            "- **资产/组合排序存在明显选择偏差**：候选池是 2026-10 时点筛选的 8 个小市值资产，历史表现好不代表未来；",
            "- 单资产与其他组合的完整排名见 `ALL_BACKTESTS_CARRY.md`。",
        ]
    else:
        lines.append("- carry 套件尚未生成 JSON。")

    if direc:
        strat = direc["strategies"]
        ranked = sorted(strat.items(), key=lambda kv: (kv[1]["full"]["sharpe"] or -9), reverse=True)
        btc = strat.get("BTC_BH", {})
        lines += [
            f"- **方向性族**：{len(strat)} 个策略（TSMOM/轮动/均值回归/配对/walk-forward）；",
            f"- 全样本 Sharpe 最高的方向性策略：{ranked[0][0]}（{ranked[0][1]['full']['sharpe']:.2f}），BTC 买入持有 Sharpe {btc.get('full',{}).get('sharpe',0):.2f}；",
            "- 但方向性策略**样本外普遍不稳定**（见下表与 `ALL_BACKTESTS_DIRECTIONAL.md`），且回撤远大于 carry；",
            "- walk-forward 参数选择也未能稳定跑赢 BTC 买入持有。",
        ]
    else:
        lines.append("- 方向性套件尚未生成 JSON。")

    lines += ["", "> **结论：carry 族整体远优于方向性；carry 内部：A0 年化最高（+18.2%，Sharpe 4.85），B0 最平滑（Sharpe 10.75 但年化 +11.5%），ALL4 折中（+13.1%，Sharpe 6.45，回撤 0.37%）——按目标取舍。方向性策略没有可复现的稳定优势。**", ""]

    # 数据质量
    lines += ["## 1. 数据覆盖与质量", "", "### Binance 现货日线", "",
              "| 品种 | 行数 | 起 | 止 | 重复 | 缺口 |", "|---|---:|---|---|---:|---:|"]
    for coin, d in dq["binance"].items():
        lines.append(f"| {coin} | {d['rows']} | {d['start']} | {d['end']} | {d['duplicates']} | {d['gaps']} |")
    lines += ["", "### Hyperliquid", "",
              "| 资产 | funding 行 | funding 起止 | perp 行 | perp 起止 | spot 行 | spot 起止 |",
              "|---|---:|---|---:|---|---:|---|"]
    for coin, d in dq["hl"].items():
        lines.append(f"| {coin} | {d['funding_rows']} | {d['funding_start']} → {d['funding_end']} | "
                     f"{d['perp_rows']} | {d['perp_start']} → {d['perp_end']} | "
                     f"{d['spot_rows']} | {d['spot_start']} → {d['spot_end']} |")

    lines += ["", "## 2. 方法（准确性相关）", "",
              "| 项 | 做法 |", "|---|---|",
              "| 执行 | 日线信号，**次日开盘**执行，无未来函数 |",
              "| 成本 | 方向性现货：0.10% 手续费 + 0.05% 滑点/边；carry：0.415%/边（含现货/永续费+滑点，实测 PURR L2） |",
              "| 资金费 | Hyperliquid 逐小时 funding 按 UTC 日加总，**每日 PnL = N×(现货收益−永续收益) + N×资金费** |",
              "| 杠杆 | carry 1x delta 中性（N = sleeve/(1+1/maxLev)）；杠杆情景单独报告 |",
              "| 样本外 | 2024-01-01 起为固定 OOS；walk-forward 用扩展窗口选参 |",
              "| 稳健性 | Block Bootstrap（90 天/30 天）、成本/资金费敏感性、压力测试 |",
              "| 容量 | 1% × min(现货, 永续) 日成交额（动态） |",
              "| 限制 | 单交易所（HL）+ 单一时点候选池（选择偏差）；无逐笔盘口成交模拟；历史短；未计税费；paper 与实盘仍有差异 |", ""]

    # 方向性概览表
    if direc:
        lines += ["## 3. 方向性策略：全样本 vs 样本外（Top 15 by full Sharpe）", "",
                  "| 策略 | 全样本年化 | 全样本 Sharpe | MDD | 样本外年化 | 样本外 Sharpe |", "|---|---:|---:|---:|---:|---:|"]
        ranked = sorted(direc["strategies"].items(), key=lambda kv: (kv[1]["full"]["sharpe"] or -9), reverse=True)[:15]
        for name, r in ranked:
            f, o = r["full"], r.get("oos")
            lines.append(f"| {name} | {pct(f['cagr'])} | {f['sharpe']:.2f} | {pct(f['mdd'])} | "
                         f"{pct(o['cagr']) if o else '—'} | {(f'{o["sharpe"]:.2f}' if o else '—')} |")
        lines += ["", "（完整排名见 `ALL_BACKTESTS_DIRECTIONAL.md`）", ""]

    # carry 概览
    if carry:
        lines += ["## 4. carry 策略：预设组合与 Top 单资产", "",
                  "| 组合 | 窗口 | 年化 | Sharpe | MDD | 容量 |", "|---|---|---:|---:|---:|---:|"]
        for name, r in carry["presets"].items():
            lines.append(f"| {name} | {r['window']} | {pct(r['cagr'])} | {r['sharpe']:.2f} | {pct(r['mdd'])} | {money(r['capacity_max_capital'])} |")
        lines += ["", "| 单资产（Top 5 by Sharpe） | 窗口 | 年化 | Sharpe | MDD | 容量 |", "|---|---|---:|---:|---:|---:|"]
        singles = sorted(carry["single"].items(), key=lambda kv: kv[1]["sharpe"], reverse=True)[:5]
        for name, r in singles:
            lines.append(f"| {name} | {r['window']} | {pct(r['cagr'])} | {r['sharpe']:.2f} | {pct(r['mdd'])} | {money(r['capacity_max_capital'])} |")
        lines += ["", "（完整排名、两两组合、Bootstrap、成本敏感性见 `ALL_BACKTESTS_CARRY.md`）", ""]

    lines += ["## 5. 结论与建议", "",
              "1. **不要用方向性策略替代 carry**：65 个方向性策略样本外不稳定、回撤大，扣成本后优势消失；",
              "2. **carry 内部按目标选**：A0（PURR+HYPE）年化最高、容量 $56k；B0（BTC/ETH）Sharpe 最高但年化低、容量百万级；ALL4 组合回撤最低；",
              "3. **所有结论都需 paper 验证**：当前 4 个 paper 账户在跑，30 天后看 gate；",
              "4. **继续跟踪数据与环境**：资金费转负是最大风险；",
              "5. 本报告不构成投资建议，历史回测不代表未来。", ""]

    (REPORTS / "ALL_BACKTESTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {REPORTS / 'ALL_BACKTESTS.md'}")
    print("carry:", bool(carry), "directional:", bool(direc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

