"""资金费 carry 数据与模拟（PURR/HYPE + BTC/ETH，1x delta 中性）。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "raw"
HL = DATA / "hl"
R174A = DATA / "R174A" / "data" / "panels"
ENTRY_COST_RATE = 0.00045 + 0.00070 + 2 * 0.0015  # 0.415%
LEV = {"BTC": 40.0, "ETH": 25.0, "PURR": 3.0, "HYPE": 10.0}


def load_small(asset: str) -> pd.DataFrame:
    df = pd.read_csv(R174A / f"daily_{asset}.csv", parse_dates=["day"])
    df = df[df["tradable"] == 1].dropna(subset=["fund_day", "spot_ret", "perp_ret"])
    return df.rename(columns={"day": "date", "fund_day": f"{asset}_fund_day",
                              "spot_ret": f"{asset}_spot_ret", "perp_ret": f"{asset}_perp_ret"})[
        ["date", f"{asset}_fund_day", f"{asset}_spot_ret", f"{asset}_perp_ret"]]


def load_major(coin: str) -> pd.DataFrame:
    funding = pd.DataFrame(json.loads((HL / f"funding_{coin}.json").read_text()))
    funding["date"] = pd.to_datetime(funding["time"], unit="ms", utc=True).dt.date
    funding["rate"] = funding["fundingRate"].astype(float)
    fund_day = funding.groupby("date")["rate"].sum().rename(f"{coin}_fund_day").reset_index()
    perp = pd.DataFrame(json.loads((HL / f"candles_1d_{coin}.json").read_text()))
    perp["date"] = pd.to_datetime(perp["t"], unit="ms", utc=True).dt.date
    perp = perp.sort_values("date").drop_duplicates("date")
    perp[f"{coin}_perp_ret"] = perp["c"].astype(float).pct_change()
    spot = pd.read_csv(DATA / f"{coin}USDT_1d.csv", parse_dates=["date"])
    spot["date"] = spot["date"].dt.date
    spot = spot.sort_values("date").drop_duplicates("date")
    spot[f"{coin}_spot_ret"] = spot["close"].astype(float).pct_change()
    df = perp[["date", f"{coin}_perp_ret"]].merge(spot[["date", f"{coin}_spot_ret"]], on="date")
    df = df.merge(fund_day, on="date").dropna().reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def build_combined() -> pd.DataFrame:
    small = load_small("PURR").merge(load_small("HYPE"), on="date", how="inner")
    majors = load_major("BTC").merge(load_major("ETH"), on="date", how="inner")
    merged = small.merge(majors, on="date", how="inner").sort_values("date").reset_index(drop=True)
    return merged


def simulate(merged: pd.DataFrame, weights: dict[str, float], capital: float = 1000.0) -> dict:
    """weights: 各资产占总资本的比例（和<=1，剩余现金）。"""
    notionals = {c: w * capital / (1 + 1 / LEV[c]) for c, w in weights.items() if w > 0}
    total = sum(notionals.values())
    day_pnl = np.zeros(len(merged))
    funding = np.zeros(len(merged))
    basis = np.zeros(len(merged))
    for c, n in notionals.items():
        funding += n * merged[f"{c}_fund_day"].to_numpy()
        basis += n * (merged[f"{c}_spot_ret"].to_numpy() - merged[f"{c}_perp_ret"].to_numpy())
    day_pnl = funding + basis
    entry = total * ENTRY_COST_RATE
    day_pnl[0] -= entry
    eq = capital + np.cumsum(day_pnl)
    dates = pd.to_datetime(merged["date"])
    days = max((dates.iloc[-1] - dates.iloc[0]).days, 1)
    rets = np.diff(eq) / eq[:-1]
    vol = float(np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 else 0.0
    sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 and np.std(rets, ddof=1) > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    mdd = float(np.max((peak - eq) / peak))
    return {
        "weights": weights,
        "equity": pd.Series(eq, index=dates, name="equity"),
        "daily_pnl": pd.Series(day_pnl, index=dates, name="pnl"),
        "funding": pd.Series(funding, index=dates, name="funding"),
        "basis": pd.Series(basis, index=dates, name="basis"),
        "notionals": notionals,
        "total_notional": total,
        "entry_cost": entry,
        "cagr": float((eq[-1] / capital) ** (365.0 / days) - 1.0),
        "total_return": float(eq[-1] / capital - 1.0),
        "vol": vol,
        "sharpe": sharpe,
        "mdd": mdd,
        "days": int(days),
    }
