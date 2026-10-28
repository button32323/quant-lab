"""收益与风险指标（纯函数，便于测试）。"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def total_return(equity: Sequence[float]) -> float:
    """累计收益率（小数）。equity 为净值序列。"""
    eq = np.asarray(equity, dtype=float)
    if len(eq) < 2 or eq[0] <= 0:
        return 0.0
    return float(eq[-1] / eq[0] - 1.0)


def cagr(equity: Sequence[float], periods_per_year: float) -> float:
    """年化收益率。periods_per_year 为每年的周期数（日线=365）。"""
    eq = np.asarray(equity, dtype=float)
    if len(eq) < 2 or eq[0] <= 0 or eq[-1] <= 0:
        return 0.0
    years = (len(eq) - 1) / float(periods_per_year)
    if years <= 0:
        return 0.0
    return float((eq[-1] / eq[0]) ** (1.0 / years) - 1.0)


def returns_from_equity(equity: Sequence[float]) -> np.ndarray:
    eq = np.asarray(equity, dtype=float)
    return eq[1:] / eq[:-1] - 1.0


def volatility(equity: Sequence[float], periods_per_year: float) -> float:
    """年化波动率。"""
    r = returns_from_equity(equity)
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=1) * math.sqrt(periods_per_year))


def sharpe(equity: Sequence[float], periods_per_year: float, rf: float = 0.0) -> float:
    """年化 Sharpe（rf 为年化无风险利率）。"""
    r = returns_from_equity(equity)
    if len(r) < 2:
        return 0.0
    excess = r - rf / periods_per_year
    sd = excess.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(excess.mean() / sd * math.sqrt(periods_per_year))


def max_drawdown(equity: Sequence[float]) -> float:
    """最大回撤（正小数，0.05 = 5%）。"""
    eq = np.asarray(equity, dtype=float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    return float(dd.max())


def summary(equity: Sequence[float], periods_per_year: float = 365.0) -> dict:
    return {
        "total_return": round(total_return(equity), 6),
        "cagr": round(cagr(equity, periods_per_year), 6),
        "volatility": round(volatility(equity, periods_per_year), 6),
        "sharpe": round(sharpe(equity, periods_per_year), 4),
        "max_drawdown": round(max_drawdown(equity), 6),
    }
