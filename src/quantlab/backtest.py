"""时间序列动量（TSMOM）日线回测引擎。

规则（与用户给定策略一致）：
- 标的：BTC/USDT 日线
- 信号：M_t = Close_t / Close_{t-L} - 1；M_t > 0 → 目标 100% BTC，否则 100% USDT
- 执行：t 日收盘后算信号，t+1 日开盘执行（无未来函数）
- 成本：单边 fee + slippage（买卖各一次），只在仓位变化时收取
- 不做空、1 倍杠杆
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    lookback: int
    equity: pd.Series
    position: pd.Series
    trades: list[dict] = field(default_factory=list)
    costs: float = 0.0
    capital: float = 100.0
    fee: float = 0.001
    slippage: float = 0.0005

    @property
    def total_return(self) -> float:
        return float(self.equity.iloc[-1] / self.capital - 1.0)

    def stats(self, periods_per_year: float = 365.0) -> dict:
        eq = self.equity.to_numpy(dtype=float)
        rets = eq[1:] / eq[:-1] - 1.0
        n = len(eq)
        days = max((self.equity.index[-1] - self.equity.index[0]).days, 1)
        cagr = (eq[-1] / eq[0]) ** (365.0 / days) - 1.0 if eq[0] > 0 and eq[-1] > 0 else 0.0
        vol = float(np.std(rets, ddof=1) * np.sqrt(periods_per_year)) if n > 2 else 0.0
        sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(periods_per_year)) if n > 2 and np.std(rets, ddof=1) > 0 else 0.0
        peak = np.maximum.accumulate(eq)
        mdd = float(np.max((peak - eq) / peak)) if n else 0.0
        completed = [t for t in self.trades if t["side"] == "sell"]
        wins = [t for t in completed if t.get("pnl", 0) > 0]
        losses = [t for t in completed if t.get("pnl", 0) <= 0]
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        return {
            "days": days,
            "bars": n,
            "total_return": round(self.total_return, 6),
            "cagr": round(float(cagr), 6),
            "volatility": round(vol, 6),
            "sharpe": round(sharpe, 4),
            "max_drawdown": round(mdd, 6),
            "trades": len(completed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(completed), 4) if completed else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
            "total_costs_usd": round(self.costs, 4),
            "time_in_market": round(float(self.position.mean()), 4),
        }


def load_daily_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    if df["date"].duplicated().any():
        raise ValueError("数据存在重复日期")
    return df


def momentum(close: pd.Series, lookback: int) -> pd.Series:
    return close / close.shift(lookback) - 1.0


def run_tsmom(
    df: pd.DataFrame,
    lookback: int = 90,
    capital: float = 100.0,
    fee: float = 0.001,
    slippage: float = 0.0005,
    start: pd.Timestamp | None = None,
) -> BacktestResult:
    """执行 TSMOM 回测。

    df 需含列：date, open, close（按日期升序）。
    """
    data = df.copy()
    if start is not None:
        data = data[data["date"] >= pd.Timestamp(start)].reset_index(drop=True)
    if len(data) < lookback + 2:
        raise ValueError("数据不足以计算动量信号")

    close = data["close"].astype(float).reset_index(drop=True)
    open_ = data["open"].astype(float).reset_index(drop=True)
    dates = pd.to_datetime(data["date"]).reset_index(drop=True)
    mom = momentum(close, lookback)
    target = (mom > 0).astype(int)  # 1 = 持有 BTC，0 = 持有 USDT；t 日收盘信号

    cost_rate = fee + slippage
    cash = float(capital)
    units = 0.0
    position = np.zeros(len(data), dtype=int)
    equity = np.zeros(len(data), dtype=float)
    trades: list[dict] = []
    costs_total = 0.0
    entry_info: dict | None = None

    for i in range(len(data)):
        # 在 i 日开盘执行 i-1 日收盘产生的信号
        if i >= 1:
            desired = int(target.iloc[i - 1]) if not np.isnan(mom.iloc[i - 1]) else 0
            prev = position[i - 1]
            if desired != prev and np.isfinite(open_.iloc[i]) and open_.iloc[i] > 0:
                px = float(open_.iloc[i])
                if desired == 1 and units == 0:
                    # 买入：现金全部换 BTC，扣除成本
                    eff_px = px * (1.0 + cost_rate)
                    units = cash / eff_px
                    cost_paid = cash - units * px
                    cash = 0.0
                    costs_total += cost_paid
                    entry_info = {"date": str(dates.iloc[i].date()), "price": eff_px,
                                  "units": units, "cost": cost_paid, "equity_before": units * px}
                    trades.append({"date": dates.iloc[i], "side": "buy", "price": eff_px,
                                   "units": units, "cost": cost_paid})
                elif desired == 0 and units > 0:
                    # 卖出：BTC 全部换现金，扣除成本
                    gross = units * px
                    cost_paid = gross * cost_rate
                    cash = gross - cost_paid
                    costs_total += cost_paid
                    pnl = cash - entry_info["equity_before"] if entry_info else np.nan
                    trades.append({"date": dates.iloc[i], "side": "sell", "price": px * (1.0 - cost_rate),
                                   "units": units, "cost": cost_paid, "pnl": pnl})
                    units = 0.0
                    entry_info = None
                position[i] = desired
            else:
                position[i] = prev

        equity[i] = cash + units * float(close.iloc[i])

    eq = pd.Series(equity, index=pd.DatetimeIndex(dates), name="equity")
    pos = pd.Series(position, index=pd.DatetimeIndex(dates), name="position")
    return BacktestResult(lookback=lookback, equity=eq, position=pos, trades=trades,
                          costs=costs_total, capital=capital, fee=fee, slippage=slippage)


def equity_stats(eq: pd.Series, capital: float, periods_per_year: float = 365.0) -> dict:
    """对任意净值序列计算统计指标（用于基准对比）。"""
    arr = eq.to_numpy(dtype=float)
    rets = arr[1:] / arr[:-1] - 1.0
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    cagr = (arr[-1] / capital) ** (365.0 / days) - 1.0 if capital > 0 and arr[-1] > 0 else 0.0
    vol = float(np.std(rets, ddof=1) * np.sqrt(periods_per_year)) if len(arr) > 2 else 0.0
    sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(periods_per_year)) if len(arr) > 2 and np.std(rets, ddof=1) > 0 else 0.0
    peak = np.maximum.accumulate(arr)
    mdd = float(np.max((peak - arr) / peak)) if len(arr) else 0.0
    return {
        "days": days,
        "total_return": round(float(arr[-1] / capital - 1.0), 6),
        "cagr": round(float(cagr), 6),
        "volatility": round(vol, 6),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(mdd, 6),
        "final_equity": round(float(arr[-1]), 4),
    }


def buy_and_hold(df: pd.DataFrame, capital: float = 100.0, fee: float = 0.001,
                 slippage: float = 0.0005, start: pd.Timestamp | None = None) -> pd.Series:
    """买入并持有基准：区间第一天开盘买入，持有到结束；只在买入时收一次成本。"""
    data = df.copy()
    if start is not None:
        data = data[data["date"] >= pd.Timestamp(start)].reset_index(drop=True)
    cost_rate = fee + slippage
    px = float(data["open"].iloc[0])
    units = capital / (px * (1.0 + cost_rate))
    eq = units * data["close"].astype(float)
    return pd.Series(eq.to_numpy(), index=pd.DatetimeIndex(pd.to_datetime(data["date"])), name="bh")


def cash_benchmark(df: pd.DataFrame, capital: float = 100.0,
                   start: pd.Timestamp | None = None) -> pd.Series:
    data = df.copy()
    if start is not None:
        data = data[data["date"] >= pd.Timestamp(start)].reset_index(drop=True)
    return pd.Series(np.full(len(data), capital, dtype=float),
                     index=pd.DatetimeIndex(pd.to_datetime(data["date"])), name="cash")

