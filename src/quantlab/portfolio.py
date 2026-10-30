"""多资产现货组合回测（long-only，权重目标，次日开盘执行）。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def load_symbol_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    return df[["date", "open", "close"]].set_index("date")


def align_symbols(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """按日期取交集，返回 (open_df, close_df)。"""
    common = None
    for df in frames.values():
        idx = df.index
        common = idx if common is None else common.intersection(idx)
    common = common.sort_values()
    opens = pd.DataFrame({s: df.loc[common, "open"] for s, df in frames.items()}, index=common)
    closes = pd.DataFrame({s: df.loc[common, "close"] for s, df in frames.items()}, index=common)
    return opens, closes


def momentum_weights(close_df: pd.DataFrame, lookback: int, mode: str = "top1") -> pd.DataFrame:
    """动量目标权重（t 日收盘信号，权重<=1，其余为现金）。

    mode:
      - top1：选动量最高的资产；若动量<=0 则空仓
      - equal_positive：所有动量>0 的资产等权；若无则空仓
    """
    mom = close_df / close_df.shift(lookback) - 1.0
    weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)
    for i in range(len(close_df)):
        row = mom.iloc[i].dropna()
        if row.empty:
            continue
        if mode == "top1":
            best = row.idxmax()
            if row[best] > 0:
                weights.iat[i, weights.columns.get_loc(best)] = 1.0
        elif mode == "equal_positive":
            pos = row[row > 0]
            if len(pos) > 0:
                w = 1.0 / len(pos)
                for s in pos.index:
                    weights.iat[i, weights.columns.get_loc(s)] = w
        else:
            raise ValueError(f"unknown mode {mode}")
    return weights


def relative_momentum_weights(close_df: pd.DataFrame, a: str, b: str, lookback: int) -> pd.DataFrame:
    """在 a、b 两个资产间做相对动量轮动（始终满仓其中一个）。"""
    ma = close_df[a] / close_df[a].shift(lookback) - 1.0
    mb = close_df[b] / close_df[b].shift(lookback) - 1.0
    weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)
    for i in range(len(close_df)):
        if pd.isna(ma.iloc[i]) or pd.isna(mb.iloc[i]):
            continue
        pick = a if ma.iloc[i] >= mb.iloc[i] else b
        weights.iat[i, weights.columns.get_loc(pick)] = 1.0
    return weights


def monthly_rebalance(raw_weights: pd.DataFrame) -> pd.DataFrame:
    """每月第一个交易日生效上一月末的目标权重，其余时间沿用。"""
    idx = raw_weights.index
    out = pd.DataFrame(np.nan, index=idx, columns=raw_weights.columns)
    month_key = idx.to_period("M")
    prev = pd.Series([np.nan] * raw_weights.shape[1], index=raw_weights.columns)
    last_raw = None
    for i in range(len(idx)):
        # 月末时记录下月要用的权重
        if i + 1 == len(idx) or month_key[i + 1] != month_key[i]:
            last_raw = raw_weights.iloc[i]
        if i == 0 or month_key[i] != month_key[i - 1]:
            out.iloc[i] = last_raw if last_raw is not None else raw_weights.iloc[0]
        else:
            out.iloc[i] = out.iloc[i - 1]
    return out.fillna(0.0)


@dataclass
class SpotBacktestResult:
    equity: pd.Series
    costs: float
    turnover: float
    weights_used: pd.DataFrame


def simulate_weights(
    open_df: pd.DataFrame,
    close_df: pd.DataFrame,
    target_weights: pd.DataFrame,
    capital: float = 100.0,
    fee: float = 0.001,
    slippage: float = 0.0005,
) -> SpotBacktestResult:
    """按目标权重模拟现货组合（long-only）。

    target_weights 为 t 日收盘后的目标权重，在 t+1 日开盘执行。
    """
    cost_rate = fee + slippage
    symbols = list(open_df.columns)
    units = {s: 0.0 for s in symbols}
    cash = float(capital)
    equity = np.zeros(len(open_df))
    costs = 0.0
    turnover = 0.0
    weights_used = pd.DataFrame(np.nan, index=open_df.index, columns=symbols)

    for i in range(len(open_df)):
        if i >= 1:
            desired = target_weights.iloc[i - 1]
            current_value = cash + sum(units[s] * float(open_df[s].iloc[i]) for s in symbols)
            # 先卖后买（现金不足时也可行）
            target_values = {s: float(desired.get(s, 0.0)) * current_value for s in symbols}
            for s in symbols:
                mv = units[s] * float(open_df[s].iloc[i])
                delta = target_values[s] - mv
                if abs(delta) < 1e-9:
                    continue
                if delta < 0:  # 卖出
                    sell_val = min(-delta, mv)
                    units[s] -= sell_val / float(open_df[s].iloc[i])
                    cash += sell_val * (1.0 - cost_rate)
                    costs += sell_val * cost_rate
                    turnover += sell_val
            for s in symbols:
                mv = units[s] * float(open_df[s].iloc[i])
                delta = target_values[s] - mv
                if delta > 0 and cash > 0:
                    buy_val = min(delta, cash)
                    if buy_val < 1e-6:
                        continue
                    units[s] += buy_val / (float(open_df[s].iloc[i]) * (1.0 + cost_rate))
                    cash -= buy_val
                    costs += buy_val * cost_rate
                    turnover += buy_val
            # 记录实际权重
            cur = cash + sum(units[s] * float(open_df[s].iloc[i]) for s in symbols)
            weights_used.iloc[i] = [units[s] * float(open_df[s].iloc[i]) / cur if cur else 0 for s in symbols]
        equity[i] = cash + sum(units[s] * float(close_df[s].iloc[i]) for s in symbols)

    return SpotBacktestResult(equity=pd.Series(equity, index=open_df.index),
                              costs=costs, turnover=turnover, weights_used=weights_used)

