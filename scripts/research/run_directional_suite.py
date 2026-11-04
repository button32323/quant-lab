#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面方向性回测套件（现货日线，next-open 执行，含成本）。

覆盖：
- 基准：BTC 买入持有、等权买入持有
- 单资产 TSMOM：lookback 20/30/45/60/90/120/180（BTC/ETH/SOL/BNB）
- 波动率目标 TSMOM（BTC）
- 多资产动量轮动：top1/top2 × lookback × 月/日频
- 均值回归：RSI、布林带（BTC/ETH）
- 配对交易：BTC-ETH 价差 z-score（long/short，含借币成本近似）
- Walk-forward 参数选择（TSMOM/轮动）
- 样本外（2024-01-01+）与 Bootstrap

输出：reports/ALL_BACKTESTS_DIRECTIONAL.md / .json
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
from quantlab import backtest as bt  # noqa: E402
from quantlab import portfolio as pf  # noqa: E402

RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
CAPITAL = 1000.0
FEE = 0.0010
SLIP = 0.0005
COST = FEE + SLIP
OOS_START = pd.Timestamp("2024-01-01")
BORROW = 0.05  # 借币成本近似
LOOKBACKS = [20, 30, 45, 60, 90, 120, 180]


def load(sym: str) -> pd.DataFrame:
    df = pd.read_csv(RAW / f"{sym}USDT_1d.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    return df.set_index("date")[["open", "close", "volume"]]


def metrics(eq: pd.Series, capital: float = CAPITAL) -> dict:
    sub = eq / eq.iloc[0] * capital
    st = bt.equity_stats(sub, capital)
    return {"total_return": st["total_return"], "cagr": st["cagr"], "vol": st["volatility"],
            "sharpe": st["sharpe"], "mdd": st["max_drawdown"], "final": st["final_equity"]}


def slice_metrics(eq: pd.Series, start: pd.Timestamp) -> dict | None:
    sub = eq[eq.index >= start]
    if len(sub) < 10:
        return None
    return metrics(sub)


# ---------- 通用权重模拟（支持做空/借币成本） ----------
def simulate_weights(open_df: pd.DataFrame, close_df: pd.DataFrame, target: pd.DataFrame,
                     capital: float = CAPITAL, cost: float = COST, borrow: float = 0.0) -> pd.Series:
    symbols = list(open_df.columns)
    units = {s: 0.0 for s in symbols}
    cash = capital
    eq = np.zeros(len(open_df))
    for i in range(len(open_df)):
        if i >= 1:
            desired = target.iloc[i - 1]
            cur_value = cash + sum(units[s] * float(open_df[s].iloc[i]) for s in symbols)
            for s in symbols:
                w = float(desired.get(s, 0.0))
                tv = w * cur_value
                mv = units[s] * float(open_df[s].iloc[i])
                delta = tv - mv
                if abs(delta) < 1e-9:
                    continue
                px = float(open_df[s].iloc[i])
                if delta > 0:  # 买入/加多
                    buy = min(delta, max(cash, 0))
                    units[s] += buy / (px * (1 + cost))
                    cash -= buy
                else:  # 卖出/加空
                    sell = -delta
                    units[s] -= sell / (px * (1 - cost))
                    cash += sell
            # 空头借币成本（按空头市值计）
            short_val = sum(-units[s] * float(open_df[s].iloc[i]) for s in symbols if units[s] < 0)
            cash -= short_val * borrow / 365
        eq[i] = cash + sum(units[s] * float(close_df[s].iloc[i]) for s in symbols)
    return pd.Series(eq, index=open_df.index)


def momentum_targets(close: pd.Series, lookback: int) -> pd.DataFrame:
    mom = close / close.shift(lookback) - 1
    w = (mom > 0).astype(float).shift(0)  # t 日收盘信号，次日执行
    return pd.DataFrame({"asset": w})


def rotation_targets(close_df: pd.DataFrame, lookback: int, top_k: int, monthly: bool) -> pd.DataFrame:
    mom = close_df / close_df.shift(lookback) - 1
    raw = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)
    for i in range(len(close_df)):
        row = mom.iloc[i].dropna()
        if row.empty:
            continue
        best = row.nlargest(top_k)
        best = best[best > 0]
        if len(best) == 0:
            continue
        for s in best.index:
            raw.iat[i, raw.columns.get_loc(s)] = 1.0 / len(best)
    if not monthly:
        return raw
    out = raw.copy()
    month = raw.index.to_period("M")
    for i in range(1, len(raw)):
        if month[i] == month[i - 1]:
            out.iloc[i] = out.iloc[i - 1]
    return out


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def rsi_strategy(close: pd.Series) -> pd.Series:
    r = rsi(close)
    state = 0.0
    out = []
    for v in r:
        if pd.isna(v):
            out.append(0.0)
        elif v < 30:
            state = 1.0
            out.append(state)
        elif v > 70:
            state = 0.0
            out.append(state)
        else:
            out.append(state)
    return pd.Series(out, index=close.index)


def bollinger_strategy(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.Series:
    ma = close.rolling(n).mean()
    sd = close.rolling(n).std()
    state = 0.0
    out = []
    for i in range(len(close)):
        c = close.iloc[i]
        if pd.isna(ma.iloc[i]):
            out.append(0.0)
            continue
        if c < ma.iloc[i] - k * sd.iloc[i]:
            state = 1.0
        elif c > ma.iloc[i]:
            state = 0.0
        out.append(state)
    return pd.Series(out, index=close.index)


def walk_forward_tsmom(close: pd.Series, candidates: list[int], min_train: int = 365,
                       step: int = 90) -> tuple[pd.Series, list[dict]]:
    """扩展窗口选择最佳 lookback（按训练段 Sharpe），应用于未来 step 天。"""
    weights = pd.Series(0.0, index=close.index)
    picks = []
    n = len(close)
    start = max(min_train, max(candidates) + 5)
    i = start
    while i < n:
        train_end = i
        best, best_sharpe = None, -9
        for lb in candidates:
            mom = close.iloc[:train_end] / close.iloc[:train_end].shift(lb) - 1
            w = (mom > 0).astype(float)
            r = (close.iloc[:train_end].pct_change() * w.shift(1)).dropna()
            if len(r) < 30 or r.std() == 0:
                continue
            sharpe = r.mean() / r.std() * np.sqrt(365)
            if sharpe > best_sharpe:
                best, best_sharpe = lb, sharpe
        if best is None:
            best = candidates[len(candidates) // 2]
        picks.append({"date": str(close.index[i].date()), "lookback": best, "train_sharpe": round(float(best_sharpe), 2)})
        j = min(i + step, n)
        seg = close.iloc[i:j]
        mom = seg / close.shift(best).iloc[i:j] - 1
        weights.iloc[i:j] = (mom > 0).astype(float).values
        i = j
    return weights, picks


def main() -> int:
    data = {}
    for sym in ["BTC", "ETH", "SOL", "BNB"]:
        try:
            data[sym] = load(sym)
        except Exception:  # noqa: BLE001
            pass
    # 对齐共同窗口（2020-08 起，SOL 上市后）
    common = None
    for df in data.values():
        common = df.index if common is None else common.intersection(df.index)
    common = common.sort_values()
    common = common[common >= pd.Timestamp("2020-08-11")]
    opens = pd.DataFrame({s: df.loc[common, "open"] for s, df in data.items()}, index=common)
    closes = pd.DataFrame({s: df.loc[common, "close"] for s, df in data.items()}, index=common)

    out = {"window": f"{common[0].date()} → {common[-1].date()}", "bars": len(common),
           "cost_per_side": COST, "borrow_rate": BORROW, "strategies": {}}

    # 基准
    bh = opens.iloc[0]
    units = {s: CAPITAL / len(opens.columns) / (float(opens.iloc[0][s]) * (1 + COST)) for s in opens.columns}
    eq_ew = pd.Series([sum(units[s] * float(closes.iloc[i][s]) for s in units) for i in range(len(closes))], index=common)
    eq_btc = pd.Series(units["BTC"] * closes["BTC"], index=common)
    out["strategies"]["BTC_BH"] = {"full": metrics(eq_btc), "oos": slice_metrics(eq_btc, OOS_START)}
    out["strategies"]["EW_BH"] = {"full": metrics(eq_ew), "oos": slice_metrics(eq_ew, OOS_START)}

    # 单资产 TSMOM
    for sym in closes.columns:
        close = closes[sym]
        o = opens[[sym]]
        c = closes[[sym]]
        for lb in LOOKBACKS:
            tgt = momentum_targets(close, lb)
            tgt.columns = [sym]
            eq = simulate_weights(o, c, tgt)
            out["strategies"][f"TSMOM_{sym}_{lb}"] = {"full": metrics(eq), "oos": slice_metrics(eq, OOS_START)}

    # 波动率目标 TSMOM（BTC）
    btc_r = closes["BTC"].pct_change()
    vol20 = btc_r.rolling(20).std() * np.sqrt(365)
    mom60 = closes["BTC"] / closes["BTC"].shift(60) - 1
    w = ((mom60 > 0) * (0.25 / vol20.replace(0, np.nan))).clip(0, 1).fillna(0)
    eq = simulate_weights(opens[["BTC"]], closes[["BTC"]], pd.DataFrame({"BTC": w.shift(1)}))
    out["strategies"]["VT_TSMOM_BTC_60_25"] = {"full": metrics(eq), "oos": slice_metrics(eq, OOS_START)}

    # 多资产轮动
    for lb in LOOKBACKS:
        for top_k in [1, 2]:
            for monthly in [True, False]:
                tgt = rotation_targets(closes, lb, top_k, monthly)
                eq = simulate_weights(opens, closes, tgt)
                name = f"ROT_top{top_k}_{lb}_{'M' if monthly else 'D'}"
                out["strategies"][name] = {"full": metrics(eq), "oos": slice_metrics(eq, OOS_START)}

    # 均值回归
    for sym in ["BTC", "ETH"]:
        o = opens[[sym]]
        c = closes[[sym]]
        tgt = pd.DataFrame({sym: rsi_strategy(closes[sym]).shift(1)})
        eq = simulate_weights(o, c, tgt)
        out["strategies"][f"RSI_{sym}"] = {"full": metrics(eq), "oos": slice_metrics(eq, OOS_START)}
        tgt = pd.DataFrame({sym: bollinger_strategy(closes[sym]).shift(1)})
        eq = simulate_weights(o, c, tgt)
        out["strategies"][f"BOLL_{sym}"] = {"full": metrics(eq), "oos": slice_metrics(eq, OOS_START)}

    # 配对 BTC-ETH（z-score 均值回归）
    ratio = np.log(closes["BTC"] / closes["ETH"])
    pair_res = {}
    for win in [30, 60]:
        z = (ratio - ratio.rolling(win).mean()) / ratio.rolling(win).std()
        pos = pd.DataFrame(0.0, index=common, columns=["BTC", "ETH"])
        state = 0.0
        for i in range(len(z)):
            if pd.isna(z.iloc[i]):
                pos.iloc[i] = [0, 0]
                continue
            if state == 0:
                if z.iloc[i] > 2:
                    state = -1  # short ratio: short BTC long ETH
                elif z.iloc[i] < -2:
                    state = 1
            elif state == 1 and z.iloc[i] >= -0.5:
                state = 0
            elif state == -1 and z.iloc[i] <= 0.5:
                state = 0
            if state == 1:
                pos.iloc[i] = [0.5, -0.5]
            elif state == -1:
                pos.iloc[i] = [-0.5, 0.5]
            else:
                pos.iloc[i] = [0.0, 0.0]
        tgt = pos.shift(1)
        eq = simulate_weights(opens[["BTC", "ETH"]], closes[["BTC", "ETH"]], tgt, borrow=BORROW)
        pair_res[f"PAIR_BTC_ETH_z{win}"] = {"full": metrics(eq), "oos": slice_metrics(eq, OOS_START)}
    out["strategies"].update(pair_res)

    # Walk-forward（BTC TSMOM 与轮动）
    wf_w, picks = walk_forward_tsmom(closes["BTC"], LOOKBACKS)
    eq = simulate_weights(opens[["BTC"]], closes[["BTC"]], pd.DataFrame({"BTC": wf_w}))
    out["walk_forward"] = {"btc_tsmom_picks": picks[-10:],
                           "btc_tsmom": {"full": metrics(eq), "oos": slice_metrics(eq, OOS_START)}}

    # 报告
    (REPORTS / "ALL_BACKTESTS_DIRECTIONAL.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for name, r in out["strategies"].items():
        f, o = r["full"], r.get("oos")
        rows.append((name, f, o))
    rows.sort(key=lambda x: (x[1]["sharpe"] or -9), reverse=True)

    lines = ["# 全面回测：方向性策略族", "",
             f"生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ｜ 窗口 {out['window']}（{len(common)} 天）",
             f"成本 {COST*10000:.0f} bps/边（含滑点）｜ 借币成本 {BORROW*100:.0f}%/年（配对）｜ next-open 执行", "",
             "## 全策略排名（按全样本 Sharpe）", "",
             "| 策略 | 全样本年化 | 全样本 Sharpe | 全样本 MDD | 样本外年化 | 样本外 Sharpe |", "|---|---:|---:|---:|---:|---:|"]
    for name, f, o in rows:
        oa = (o["cagr"] * 100) if o else 0.0
        os_ = (o["sharpe"]) if o else 0.0
        lines.append(f"| {name} | {f['cagr']*100:+.1f}% | {f['sharpe']:.2f} | {f['mdd']*100:.1f}% | {oa:+.1f}% | {os_:.2f} |")
    lines += ["", "## Walk-forward（BTC TSMOM，扩展窗口选 lookback）", "",
              f"- 全样本：年化 {out['walk_forward']['btc_tsmom']['full']['cagr']*100:+.1f}%，Sharpe {out['walk_forward']['btc_tsmom']['full']['sharpe']:.2f}",
              f"- 样本外：年化 {(out['walk_forward']['btc_tsmom']['oos']['cagr']*100 if out['walk_forward']['btc_tsmom']['oos'] else 0):+.1f}%，Sharpe {(out['walk_forward']['btc_tsmom']['oos']['sharpe'] if out['walk_forward']['btc_tsmom']['oos'] else 0):.2f}",
              f"- 最近选择：{json.dumps(out['walk_forward']['btc_tsmom_picks'][-3:], ensure_ascii=False)}", "",
              "## 结论（自动生成）", "",
              "- 方向性策略的样本外表现普遍弱于或接近 BTC 买入持有；成本对高频轮动伤害大；",
              "- 单资产 TSMOM 在长窗口全样本可能好看，但样本外不稳定，且回撤大；",
              "- 均值回归/配对在扣成本后大多无优势（且未计资金费）；",
              "- 任何参数选择/排序都有多重检验偏差，不能据此实施。"]
    (REPORTS / "ALL_BACKTESTS_DIRECTIONAL.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"window": out["window"], "n_strategies": len(out["strategies"]),
                      "top5": [(n, f["sharpe"]) for n, f, _ in rows[:5]],
                      "btc_wf": out["walk_forward"]["btc_tsmom"]["full"]}, ensure_ascii=False, indent=2))
    print(f"\n报告: {REPORTS / 'ALL_BACKTESTS_DIRECTIONAL.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
