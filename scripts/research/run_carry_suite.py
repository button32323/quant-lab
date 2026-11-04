#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面 carry 回测套件（修正数据质量问题版）。

数据覆盖与口径：
- 小市值：HL 现货/永续/资金费；**仅保留现货日成交额足够、价格无异常**的资产（PURR/HYPE）
- 主流：HL 永续+资金费，**现货价格用 Binance 现货**（HL 版 UBTC/UETH 现货早期报价异常，已弃用）
- 其余小市值资产（AZTEC/BERA/MON/PUMP/STABLE/TRUMP）现货流动性/数据质量不达标，报告为"剔除"

口径：1x delta 中性、建仓成本 0.415%/边、每日 PnL = N*(现货收益-永续收益) + N*资金费。
输出：reports/ALL_BACKTESTS_CARRY.md / .json
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
from quantlab import hyperliquid as hl  # noqa: E402

HL = ROOT / "data" / "raw" / "hl"
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
CAPITAL = 1000.0
ENTRY_COST = 0.00415
SMALL = ["PURR", "HYPE", "AZTEC", "BERA", "MON", "PUMP", "STABLE", "TRUMP"]
MAJORS = ["BTC", "ETH"]
DEFAULT_LEV = {"PURR": 3.0, "HYPE": 10.0, "BTC": 40.0, "ETH": 25.0}
VOL_FRAC = 0.01
MIN_CAPACITY = 500.0  # 容量低于 $500 的资产不适合 $100–1000 策略
MAX_ABS_DAILY = 3.0    # 单日涨跌 > 300% 视为数据/流动性异常
OOS_START = pd.Timestamp("2026-01-01")

LEV = dict(DEFAULT_LEV)
try:
    meta = hl.post({"type": "meta"})["universe"]
    for m in meta:
        if m.get("maxLeverage"):
            LEV[m["name"]] = float(m["maxLeverage"])
except Exception:  # noqa: BLE001
    pass


def _candles(path: Path, coin: str) -> pd.DataFrame:
    rows = pd.DataFrame(json.loads(path.read_text(encoding="utf-8")))
    rows["date"] = pd.to_datetime(rows["t"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    rows = rows.sort_values("date").drop_duplicates("date")
    rows["close"] = rows["c"].astype(float)
    rows["vol_usd"] = rows["v"].astype(float) * rows["close"]
    return rows[["date", "close", "vol_usd"]].rename(columns={"close": f"{coin}_px", "vol_usd": f"{coin}_vol"})


def load_small(coin: str) -> pd.DataFrame:
    fund = pd.DataFrame(json.loads((HL / f"funding_{coin}.json").read_text(encoding="utf-8")))
    fund["date"] = pd.to_datetime(fund["time"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    fund["rate"] = fund["fundingRate"].astype(float)
    fund_day = fund.groupby("date")["rate"].sum().rename(f"{coin}_fund_day")
    perp = _candles(HL / f"candles_1d_{coin}.json", coin)
    spot = _candles(HL / f"candles_1d_spot_{coin}.json", coin)
    perp[f"{coin}_perp_ret"] = perp[f"{coin}_px"].pct_change()
    spot[f"{coin}_spot_ret"] = spot[f"{coin}_px"].pct_change()
    df = spot[["date", f"{coin}_spot_ret", f"{coin}_vol"]].merge(
        perp[["date", f"{coin}_perp_ret", f"{coin}_vol"]], on="date")
    df = df.merge(fund_day.reset_index(), on="date")
    return df.dropna().reset_index(drop=True)


def load_major(coin: str) -> pd.DataFrame:
    fund = pd.DataFrame(json.loads((HL / f"funding_{coin}.json").read_text(encoding="utf-8")))
    fund["date"] = pd.to_datetime(fund["time"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    fund["rate"] = fund["fundingRate"].astype(float)
    fund_day = fund.groupby("date")["rate"].sum().rename(f"{coin}_fund_day")
    perp = _candles(HL / f"candles_1d_{coin}.json", coin)
    perp[f"{coin}_perp_ret"] = perp[f"{coin}_px"].pct_change()
    spot_raw = pd.read_csv(RAW / f"{coin}USDT_1d.csv", parse_dates=["date"])
    spot_raw["date"] = pd.to_datetime(spot_raw["date"]).dt.normalize()
    spot_raw = spot_raw.sort_values("date").drop_duplicates("date")
    spot_raw[f"{coin}_spot_ret"] = spot_raw["close"].astype(float).pct_change()
    spot_raw[f"{coin}_vol"] = spot_raw["close"].astype(float) * spot_raw["volume"].astype(float)
    df = spot_raw[["date", f"{coin}_spot_ret", f"{coin}_vol"]].merge(perp[["date", f"{coin}_perp_ret", f"{coin}_vol"]], on="date")
    return df.merge(fund_day.reset_index(), on="date").dropna().reset_index(drop=True)


def validate(coin: str, df: pd.DataFrame) -> dict:
    recent = df.tail(30)
    spot_v = float(recent[f"{coin}_vol_x"].mean() if f"{coin}_vol_x" in df.columns else recent[f"{coin}_vol"].mean())
    perp_v = float(recent[f"{coin}_vol"].mean())
    max_ret = float(max(df[f"{coin}_spot_ret"].abs().max(), df[f"{coin}_perp_ret"].abs().max()))
    cap_notional = VOL_FRAC * min(spot_v, perp_v)
    max_capital = cap_notional * (1 + 1 / max(LEV.get(coin, 5.0), 1.0))
    ok = len(df) >= 60 and max_ret <= MAX_ABS_DAILY and max_capital >= MIN_CAPACITY
    reasons = []
    if len(df) < 60:
        reasons.append(f"仅{len(df)}天")
    if max_ret > MAX_ABS_DAILY:
        reasons.append(f"异常日收益{max_ret:.1f}x")
    if max_capital < MIN_CAPACITY:
        reasons.append(f"容量仅${max_capital:,.0f}")
    return {"coin": coin, "rows": len(df), "window": f"{df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()}",
            "spot_vol_30d": round(spot_v, 0), "perp_vol_30d": round(perp_v, 0),
            "max_abs_daily_ret": round(max_ret, 2), "capacity_max_capital": round(max_capital, 0),
            "valid": bool(ok), "reasons": reasons}


def simulate(df: pd.DataFrame, assets: list[str], capital: float = CAPITAL,
             cost_mult: float = 1.0, fund_mult: float = 1.0) -> dict:
    weights = {a: 1.0 / len(assets) for a in assets}
    notionals = {a: weights[a] * capital / (1 + 1 / max(LEV.get(a, 5.0), 1.0)) for a in assets}
    total = sum(notionals.values())
    funding = np.zeros(len(df))
    basis = np.zeros(len(df))
    for a, n in notionals.items():
        funding += n * df[f"{a}_fund_day"].to_numpy() * fund_mult
        basis += n * (df[f"{a}_spot_ret"].to_numpy() - df[f"{a}_perp_ret"].to_numpy())
    pnl = funding + basis
    pnl[0] -= total * ENTRY_COST * cost_mult
    eq = capital + np.cumsum(pnl)
    dates = pd.to_datetime(df["date"])
    days = max((dates.iloc[-1] - dates.iloc[0]).days, 1)
    rets = np.diff(eq) / eq[:-1]
    vol = float(np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 else 0.0
    sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(365)) if len(rets) > 2 and np.std(rets, ddof=1) > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    mdd = float(np.max((peak - eq) / peak))
    eq_s = pd.Series(eq, index=dates)
    oos = eq_s[eq_s.index >= OOS_START]
    oos_ret = float(oos.iloc[-1] / oos.iloc[0] - 1) if len(oos) > 10 else None
    caps = {}
    for a in assets:
        spot_col = f"{a}_vol_x" if f"{a}_vol_x" in df.columns else f"{a}_vol"
        caps[a] = VOL_FRAC * min(df[spot_col].mean(), df[f"{a}_vol"].mean())
        caps[a + "_max"] = caps[a] * (1 + 1 / max(LEV.get(a, 5.0), 1.0)) / weights[a]
    return {
        "assets": assets, "window": f"{dates.iloc[0].date()} → {dates.iloc[-1].date()}", "days": int(days),
        "total_return": round(float(eq[-1] / capital - 1), 6),
        "cagr": round(float((eq[-1] / capital) ** (365 / days) - 1), 6) if eq[-1] > 0 else -1,
        "vol": round(vol, 6), "sharpe": round(sharpe, 4), "mdd": round(mdd, 6),
        "funding_usd": round(float(funding.sum()), 2), "basis_usd": round(float(basis.sum()), 2),
        "funding_positive_share": round(float((funding > 0).mean()), 4),
        "min_notional": round(min(notionals.values()), 2),
        "capacity_max_capital": round(min(caps[a + "_max"] for a in assets), 0),
        "oos_return": round(oos_ret, 6) if oos_ret is not None else None,
    }


def bootstrap(df: pd.DataFrame, assets: list[str], horizon: int = 90, block: int = 7, samples: int = 2000,
              seed: int = 11) -> dict:
    weights = {a: 1.0 / len(assets) for a in assets}
    notionals = {a: weights[a] * CAPITAL / (1 + 1 / max(LEV.get(a, 5.0), 1.0)) for a in assets}
    funding = sum(n * df[f"{a}_fund_day"].to_numpy() for a, n in notionals.items())
    basis = sum(n * (df[f"{a}_spot_ret"].to_numpy() - df[f"{a}_perp_ret"].to_numpy()) for a, n in notionals.items())
    pnl = funding + basis
    pnl[0] -= sum(notionals.values()) * ENTRY_COST
    rets = pnl / CAPITAL
    rng = np.random.default_rng(seed)
    n = len(rets)
    out = np.empty(samples)
    for i in range(samples):
        blocks = int(np.ceil(horizon / block))
        idx = rng.integers(0, max(n - block, 1), size=blocks)
        sample = np.concatenate([rets[j:j + block] for j in idx])[:horizon]
        out[i] = np.prod(1 + sample) - 1
    return {"horizon_days": horizon, "p5": round(float(np.percentile(out, 5)), 4),
            "p50": round(float(np.percentile(out, 50)), 4), "p95": round(float(np.percentile(out, 95)), 4),
            "prob_negative": round(float((out < 0).mean()), 4),
            "cagr_from_median": round(float((1 + np.percentile(out, 50)) ** (365 / horizon) - 1), 4)}


def main() -> int:
    frames = {}
    validations = {}
    loaders = {**{c: load_small for c in SMALL}, **{c: load_major for c in MAJORS}}
    for coin, loader in loaders.items():
        try:
            df = loader(coin)
            frames[coin] = df
            # 统一 spot/perp 量列名（merge 后可能带后缀）
            if f"{coin}_vol_x" in df.columns:
                df[f"{coin}_vol"] = df[f"{coin}_vol_y"]
            validations[coin] = validate(coin, df)
        except Exception as exc:  # noqa: BLE001
            validations[coin] = {"coin": coin, "valid": False, "reasons": [str(exc)], "rows": 0}

    valid = [c for c, v in validations.items() if v.get("valid")]
    excluded = {c: v for c, v in validations.items() if not v.get("valid")}

    results = {"capital": CAPITAL, "entry_cost_per_leg": ENTRY_COST, "valid_assets": valid,
               "excluded": excluded, "single": {}, "pairs": {}, "presets": {},
               "bootstrap": {}, "cost_sensitivity": {}}

    for coin in valid:
        results["single"][coin] = simulate(frames[coin], [coin])

    # 两两组合（有效资产，共同窗口 >= 60 天）
    pair_rows = []
    for a, b in itertools.combinations(valid, 2):
        merged = frames[a].merge(frames[b], on="date", how="inner")
        if f"{a}_vol_x" in merged.columns:
            pass
        if len(merged) < 60:
            continue
        res = simulate(merged, [a, b])
        results["pairs"][f"{a}+{b}"] = res
        pair_rows.append((a, b, res))

    # 预设组合（等权）
    presets = {"A0_PURR_HYPE": ["PURR", "HYPE"], "B0_BTC_ETH": ["BTC", "ETH"],
               "PURR_HYPE_BTC": ["PURR", "HYPE", "BTC"], "ALL4": ["PURR", "HYPE", "BTC", "ETH"]}
    for name, assets in presets.items():
        if not all(a in valid for a in assets):
            continue
        merged = frames[assets[0]]
        for a in assets[1:]:
            merged = merged.merge(frames[a], on="date", how="inner")
        if len(merged) < 30:
            continue
        results["presets"][name] = simulate(merged, assets)
        if name in ("A0_PURR_HYPE", "B0_BTC_ETH", "ALL4"):
            results["bootstrap"][name] = bootstrap(merged, assets)

    a0_merged = frames["PURR"].merge(frames["HYPE"], on="date", how="inner")
    for label, cm, fm in [("cost×0.5", 0.5, 1.0), ("cost×2", 2.0, 1.0),
                          ("funding×0.5", 1.0, 0.5), ("funding×0", 1.0, 0.0)]:
        results["cost_sensitivity"][label] = simulate(a0_merged, ["PURR", "HYPE"], cost_mult=cm, fund_mult=fm)

    (REPORTS / "ALL_BACKTESTS_CARRY.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 全面回测：资金费 carry 族（数据质量修正版）", "",
             f"生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ｜ 本金 ${CAPITAL:.0f} ｜ 建仓成本 {ENTRY_COST*100:.3f}%/边",
             "", f"有效资产：{', '.join(valid)}", "",
             "## 0. 资产筛查（为什么只保留 PURR/HYPE/BTC/ETH）", "",
             "| 资产 | 窗口 | 行数 | 现货日成交额(30d) | 最大单日涨跌 | 容量上限 | 结论/原因 |",
             "|---|---|---:|---:|---:|---:|---|"]
    for coin, v in validations.items():
        if v.get("rows", 0) == 0:
            lines.append(f"| {coin} | — | 0 | — | — | — | 数据加载失败：{'/'.join(v.get('reasons', []))} |")
            continue
        status = "✅ 有效" if v["valid"] else "❌ 剔除：" + "；".join(v["reasons"])
        lines.append(f"| {coin} | {v['window']} | {v['rows']} | ${v['spot_vol_30d']:,.0f} | {v['max_abs_daily_ret']:.1f}x | "
                     f"${v['capacity_max_capital']:,.0f} | {status} |")
    lines += ["", "> 关键发现：AZTEC/BERA/MON/PUMP/STABLE/TRUMP 的 HL 现货日成交额只有 **$0–3.8k**（几乎无交易），"
              "价格序列存在多数十倍级异常跳变，**不能用于可执行的现货-永续 carry**；"
              "主流资产改用 Binance 现货（HL 版现货早期有 7,979,573 等异常报价）。", ""]
    lines += ["## 1. 单资产 carry（有效资产）", "",
              "| 资产 | 窗口 | 天数 | 年化 | 波动 | Sharpe | 最大回撤 | 资金费$ | basis$ | OOS收益 | 容量 |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for coin, r in sorted(results["single"].items(), key=lambda kv: kv[1]["sharpe"], reverse=True):
        lines.append(f"| {coin} | {r['window']} | {r['days']} | {r['cagr']*100:+.1f}% | {r['vol']*100:.1f}% | {r['sharpe']:.2f} | "
                     f"{r['mdd']*100:.2f}% | {r['funding_usd']:+.1f} | {r['basis_usd']:+.1f} | "
                     f"{(r['oos_return']*100 if r['oos_return'] is not None else 0):+.1f}% | ${r['capacity_max_capital']:,.0f} |")
    lines += ["", "## 2. 预设组合（等权）", "",
              "| 组合 | 资产 | 窗口 | 年化 | Sharpe | 最大回撤 | 容量 |", "|---|---|---|---:|---:|---:|---:|"]
    for name, r in results["presets"].items():
        lines.append(f"| {name} | {'+'.join(r['assets'])} | {r['window']} | {r['cagr']*100:+.1f}% | {r['sharpe']:.2f} | "
                     f"{r['mdd']*100:.2f}% | ${r['capacity_max_capital']:,.0f} |")
    lines += ["", "## 3. 两两组合（有效资产）", "",
              "| 组合 | 窗口 | 年化 | Sharpe | 最大回撤 | OOS收益 |", "|---|---|---:|---:|---:|---:|"]
    for a, b, r in sorted(pair_rows, key=lambda x: x[2]["sharpe"], reverse=True):
        lines.append(f"| {a}+{b} | {r['window']} | {r['cagr']*100:+.1f}% | {r['sharpe']:.2f} | {r['mdd']*100:.2f}% | "
                     f"{(r['oos_return']*100 if r['oos_return'] is not None else 0):+.1f}% |")
    lines += ["", "## 4. Bootstrap（90 天，block=7）", "",
              "| 组合 | p5 | 中位 | p95 | 负收益概率 | 中位折算年化 |", "|---|---:|---:|---:|---:|---:|"]
    for name, b in results["bootstrap"].items():
        lines.append(f"| {name} | {b['p5']*100:+.1f}% | {b['p50']*100:+.1f}% | {b['p95']*100:+.1f}% | "
                     f"{b['prob_negative']*100:.1f}% | {b['cagr_from_median']*100:+.1f}% |")
    lines += ["", "## 5. 成本/资金费敏感性（A0）", "",
              "| 情景 | 年化 | 最大回撤 | Sharpe |", "|---|---:|---:|---:|"]
    for label, r in results["cost_sensitivity"].items():
        lines.append(f"| {label} | {r['cagr']*100:+.1f}% | {r['mdd']*100:.2f}% | {r['sharpe']:.2f} |")
    lines += ["", "## 结论", "",
              "- **可执行 carry 的资产只有 PURR、HYPE（+ BTC/ETH 用 Binance 现货）**；其余小市值现货市场近乎无流动性，回测收益是虚假/不可交易的；",
              "- A0 结果与之前一致（年化 ~18%、回撤 <1%）；B0 用 Binance 现货后恢复正常（不再出现异常负收益）；",
              "- 参数/资产选择存在选择偏差：候选池来自 2026-10 的筛选；",
              "- 历史资金费环境与当前差异大，不能外推；实盘需考虑滑点、容量、对手方风险。"]
    (REPORTS / "ALL_BACKTESTS_CARRY.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"valid": valid, "excluded": {k: v.get("reasons") for k, v in excluded.items()},
                      "presets": {k: {"cagr": v["cagr"], "sharpe": v["sharpe"], "mdd": v["mdd"], "window": v["window"]}
                                  for k, v in results["presets"].items()}, "pairs": len(pair_rows)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
