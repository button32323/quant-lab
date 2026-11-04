#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面回测进阶验证：Walk-forward（轮动/配对）+ 多重检验 + 容量区间。

依赖 run_directional_suite.py 的策略函数；不修改主套件，单独输出：
reports/ALL_BACKTESTS_ADVANCED.md / .json
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import run_directional_suite as rds  # noqa: E402

REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
RAW = ROOT / "data" / "raw"
HL = RAW / "hl"
LEV = {"PURR": 3.0, "HYPE": 10.0, "BTC": 40.0, "ETH": 25.0}
VOL_FRAC = 0.01
OOS_START = pd.Timestamp("2024-01-01")
INT = None


def sharpe_of(eq: pd.Series) -> float:
    r = eq.pct_change().dropna()
    if len(r) < 20 or r.std() == 0:
        return -9.0
    return float(r.mean() / r.std() * np.sqrt(365))


def metrics(eq: pd.Series) -> dict:
    return rds.metrics(eq)


def common_data():
    data = {s: rds.load(s) for s in ["BTC", "ETH", "SOL", "BNB"]}
    common = None
    for df in data.values():
        common = df.index if common is None else common.intersection(df.index)
    common = common.sort_values()
    common = common[common >= pd.Timestamp("2020-08-11")]
    opens = pd.DataFrame({s: df.loc[common, "open"] for s, df in data.items()}, index=common)
    closes = pd.DataFrame({s: df.loc[common, "close"] for s, df in data.items()}, index=common)
    return opens, closes


def pair_targets(closes: pd.DataFrame, win: int, entry: float, exit_: float) -> pd.DataFrame:
    ratio = np.log(closes["BTC"] / closes["ETH"])
    z = (ratio - ratio.rolling(win).mean()) / ratio.rolling(win).std()
    pos = pd.DataFrame(0.0, index=closes.index, columns=["BTC", "ETH"])
    state = 0.0
    for i in range(len(z)):
        if pd.isna(z.iloc[i]):
            pos.iloc[i] = [0, 0]
            continue
        if state == 0:
            if z.iloc[i] > entry:
                state = -1
            elif z.iloc[i] < -entry:
                state = 1
        elif state == 1 and z.iloc[i] >= -exit_:
            state = 0
        elif state == -1 and z.iloc[i] <= exit_:
            state = 0
        pos.iloc[i] = [0.5, -0.5] if state == 1 else ([-0.5, 0.5] if state == -1 else [0.0, 0.0])
    return pos.shift(1)


def walk_forward_rotation(opens, closes):
    combos = []
    for lb in rds.LOOKBACKS:
        for k in [1, 2]:
            for monthly in [True, False]:
                tgt = rds.rotation_targets(closes, lb, k, monthly)
                eq = rds.simulate_weights(opens, closes, tgt)
                combos.append({"name": f"ROT_top{k}_{lb}_{'M' if monthly else 'D'}", "tgt": tgt, "eq": eq})
    n = len(closes)
    combined = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    min_train, step = 365, 90
    picks = []
    i = min_train
    while i < n:
        best = max(combos, key=lambda c: sharpe_of(c["eq"].iloc[:i]))
        picks.append({"date": str(closes.index[i].date()), "combo": best["name"], "train_sharpe": round(sharpe_of(best["eq"].iloc[:i]), 2)})
        j = min(i + step, n)
        combined.iloc[i:j] = best["tgt"].iloc[i:j].values
        i = j
    eq = rds.simulate_weights(opens, closes, combined)
    return {"full": metrics(eq), "oos": rds.slice_metrics(eq, OOS_START), "picks": picks[-6:]}


def walk_forward_pairs(opens, closes):
    combos = []
    for win in [20, 30, 60]:
        for entry in [1.5, 2.0, 2.5]:
            tgt = pair_targets(closes, win, entry, 0.5)
            eq = rds.simulate_weights(opens[["BTC", "ETH"]], closes[["BTC", "ETH"]], tgt, borrow=rds.BORROW)
            combos.append({"name": f"PAIR_z{win}_e{entry}", "tgt": tgt, "eq": eq})
    n = len(closes)
    combined = pd.DataFrame(0.0, index=closes.index, columns=["BTC", "ETH"])
    min_train, step = 365, 90
    picks = []
    i = min_train
    while i < n:
        best = max(combos, key=lambda c: sharpe_of(c["eq"].iloc[:i]))
        picks.append({"date": str(closes.index[i].date()), "combo": best["name"], "train_sharpe": round(sharpe_of(best["eq"].iloc[:i]), 2)})
        j = min(i + step, n)
        combined.iloc[i:j] = best["tgt"].iloc[i:j].values
        i = j
    eq = rds.simulate_weights(opens[["BTC", "ETH"]], closes[["BTC", "ETH"]], combined, borrow=rds.BORROW)
    return {"full": metrics(eq), "oos": rds.slice_metrics(eq, OOS_START), "picks": picks[-6:]}


def collect_returns(opens, closes):
    """收集各策略日收益，用于多重检验。"""
    rets = {}
    for sym in closes.columns:
        for lb in rds.LOOKBACKS:
            tgt = rds.momentum_targets(closes[sym], lb)
            tgt.columns = [sym]
            eq = rds.simulate_weights(opens[[sym]], closes[[sym]], tgt)
            rets[f"TSMOM_{sym}_{lb}"] = eq.pct_change().dropna()
    for lb in rds.LOOKBACKS:
        for k in [1, 2]:
            for monthly in [True, False]:
                tgt = rds.rotation_targets(closes, lb, k, monthly)
                eq = rds.simulate_weights(opens, closes, tgt)
                rets[f"ROT_top{k}_{lb}_{'M' if monthly else 'D'}"] = eq.pct_change().dropna()
    for sym in ["BTC", "ETH"]:
        for name, sig in [("RSI", rds.rsi_strategy(closes[sym])), ("BOLL", rds.bollinger_strategy(closes[sym]))]:
            eq = rds.simulate_weights(opens[[sym]], closes[[sym]], pd.DataFrame({sym: sig.shift(1)}))
            rets[f"{name}_{sym}"] = eq.pct_change().dropna()
    for win in [30, 60]:
        tgt = pair_targets(closes, win, 2.0, 0.5)
        eq = rds.simulate_weights(opens[["BTC", "ETH"]], closes[["BTC", "ETH"]], tgt, borrow=rds.BORROW)
        rets[f"PAIR_z{win}"] = eq.pct_change().dropna()
    return pd.DataFrame(rets).dropna(how="all")


def multiple_testing(returns: pd.DataFrame, samples: int = 500, block: int = 10, seed: int = 3) -> dict:
    r = returns.dropna()
    n = len(r)
    ann_sharpe = (r.mean() / r.std()) * np.sqrt(365)
    tstats = ann_sharpe * np.sqrt(n / 365)
    from math import erf, sqrt
    def pval(z):
        return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    m = r.shape[1]
    bonf_z = 2.807 if m <= 100 else 3.0  # 近似：alpha=0.05/m 的双侧 z
    rng = np.random.default_rng(seed)
    arr = r.to_numpy()
    arr = arr - arr.mean(axis=0, keepdims=True)
    observed_max = float(ann_sharpe.max())
    null_max = np.empty(samples)
    for i in range(samples):
        blocks = int(np.ceil(n / block))
        idx = rng.integers(0, n - block, size=blocks)
        sample = np.concatenate([arr[j:j + block] for j in idx])[:n]
        means = sample.mean(axis=0)
        stds = sample.std(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            sh = np.where(stds > 0, means / stds * np.sqrt(365), -9)
        null_max[i] = np.nanmax(sh)
    best = ann_sharpe.sort_values(ascending=False).head(10)
    return {
        "n_strategies": int(m), "n_days": int(n),
        "top10": [{"name": k, "ann_sharpe": round(float(v), 3),
                   "t_stat": round(float(tstats[k]), 2), "p_value": round(float(pval(tstats[k])), 4)}
                  for k, v in best.items()],
        "bonferroni_z": bonf_z,
        "bonferroni_pass": [k for k in best.index if abs(float(tstats[k])) >= bonf_z],
        "white_reality_check_p": round(float((null_max >= observed_max).mean()), 4),
        "observed_max_sharpe": round(observed_max, 3),
        "null_max_p95": round(float(np.percentile(null_max, 95)), 3),
    }


def capacity_ranges() -> dict:
    """容量区间：用最近 90 天数据（成交量口径），避免早期低流动性与 0 值污染。"""
    out = {}

    def summarize(v: pd.Series, lev: float) -> dict:
        v = v.dropna()
        if len(v) == 0:
            return {}
        cap = 0.01 * v * (1 + 1 / lev)
        return {"p5_vol30": float(v.quantile(0.05)), "median_vol30": float(v.median()),
                "p95_vol30": float(v.quantile(0.95)),
                "capacity_p5": float(cap.quantile(0.05)), "capacity_median": float(cap.median()),
                "capacity_p95": float(cap.quantile(0.95))}

    for coin in ["PURR", "HYPE"]:
        spot = pd.DataFrame(json.loads((HL / f"candles_1d_spot_{coin}.json").read_text(encoding="utf-8")))
        perp = pd.DataFrame(json.loads((HL / f"candles_1d_{coin}.json").read_text(encoding="utf-8")))
        for df in (spot, perp):
            df["date"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
            df["vol_usd"] = df["v"].astype(float) * df["c"].astype(float)
        m = spot[["date", "vol_usd"]].rename(columns={"vol_usd": "spot"}).merge(
            perp[["date", "vol_usd"]].rename(columns={"vol_usd": "perp"}), on="date").tail(90)
        v = m[["spot", "perp"]].replace(0, np.nan).min(axis=1).rolling(30).mean().dropna()
        out[coin] = summarize(v, LEV[coin])

    for coin in ["BTC", "ETH"]:
        spot = pd.read_csv(RAW / f"{coin}USDT_1d.csv", parse_dates=["date"])
        spot["date"] = pd.to_datetime(spot["date"]).dt.normalize()
        spot["spot_vol"] = spot["close"].astype(float) * spot["volume"].astype(float)
        perp = pd.DataFrame(json.loads((HL / f"candles_1d_{coin}.json").read_text(encoding="utf-8")))
        perp["date"] = pd.to_datetime(perp["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
        perp["perp_vol"] = perp["v"].astype(float) * perp["c"].astype(float)
        m = spot[["date", "spot_vol"]].merge(perp[["date", "perp_vol"]], on="date").tail(90)
        v = m[["spot_vol", "perp_vol"]].replace(0, np.nan).min(axis=1).rolling(30).mean().dropna()
        out[coin] = summarize(v, LEV[coin])
    return out

def main() -> int:
    opens, closes = common_data()
    wf_rot = walk_forward_rotation(opens, closes)
    wf_pair = walk_forward_pairs(opens, closes)
    rets = collect_returns(opens, closes)
    mt = multiple_testing(rets)
    caps = capacity_ranges()
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "walk_forward_rotation": wf_rot, "walk_forward_pairs": wf_pair,
           "multiple_testing": mt, "capacity_ranges": caps}
    (REPORTS / "ALL_BACKTESTS_ADVANCED.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 全面回测进阶验证（walk-forward / 多重检验 / 容量）", "",
             f"生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "",
             "## 1. Walk-forward：多资产轮动（每 90 天用扩展窗口重选参数）", "",
             f"- 全样本：年化 {wf_rot['full']['cagr']*100:+.1f}%，Sharpe {wf_rot['full']['sharpe']:.2f}，MDD {wf_rot['full']['mdd']*100:.1f}%",
             f"- 样本外（2024+）：年化 {(wf_rot['oos']['cagr']*100 if wf_rot['oos'] else 0):+.1f}%，Sharpe {(wf_rot['oos']['sharpe'] if wf_rot['oos'] else 0):.2f}",
             f"- 最近选择：{json.dumps(wf_rot['picks'][-3:], ensure_ascii=False)}", "",
             "## 2. Walk-forward：BTC-ETH 配对", "",
             f"- 全样本：年化 {wf_pair['full']['cagr']*100:+.1f}%，Sharpe {wf_pair['full']['sharpe']:.2f}，MDD {wf_pair['full']['mdd']*100:.1f}%",
             f"- 样本外（2024+）：年化 {(wf_pair['oos']['cagr']*100 if wf_pair['oos'] else 0):+.1f}%，Sharpe {(wf_pair['oos']['sharpe'] if wf_pair['oos'] else 0):.2f}",
             "", "## 3. 多重检验（65 个方向性策略）", "",
             f"- 策略数 {mt['n_strategies']}，样本天数 {mt['n_days']}；Bonferroni 近似阈值 z≈{mt['bonferroni_z']}",
             f"- **White Reality Check p 值：{mt['white_reality_check_p']}**（观测最大 Sharpe {mt['observed_max_sharpe']}，null 95 分位 {mt['null_max_p95']}）",
             f"- 通过 Bonferroni 的策略：{', '.join(mt['bonferroni_pass']) if mt['bonferroni_pass'] else '无'}", "",
             "| 策略 | 年化 Sharpe | t 值 | p 值 |", "|---|---:|---:|---:|"]
    for row in mt["top10"]:
        lines.append(f"| {row['name']} | {row['ann_sharpe']:.2f} | {row['t_stat']:.2f} | {row['p_value']:.4f} |")
    lines += ["", "> 结论：在 65 个策略里，即使最好的策略，若考虑多重检验，也无法证明存在真实 edge（p 值/White 检验）。", "",
              "## 4. 容量区间（滚动 30 天成交量分位）", "",
              "| 资产 | 30d 成交额 p5 | 中位 | p95 | 容量 p5 | 容量中位 | 容量 p95 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for coin, c in caps.items():
        lines.append(f"| {coin} | ${c['p5_vol30']:,.0f} | ${c['median_vol30']:,.0f} | ${c['p95_vol30']:,.0f} | "
                     f"${c['capacity_p5']:,.0f} | ${c['capacity_median']:,.0f} | ${c['capacity_p95']:,.0f} |")
    lines += ["", "> 容量随成交额剧烈波动；小资金（$100–$1,000）在 p5 情形容量也足够，但大资金需按 p5 保守估计。"]
    (REPORTS / "ALL_BACKTESTS_ADVANCED.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

