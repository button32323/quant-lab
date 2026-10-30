#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Hyperliquid 实时 L2 盘口估算 $10–$1,000 单腿订单的滑点（对照回测假设 15bps）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import hyperliquid as hl  # noqa: E402

REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
SIZES = [10, 25, 50, 100, 200, 333, 375, 500, 1000]
INSTRUMENTS = {
    "PURR_spot": "PURR/USDC",
    "PURR_perp": "PURR",
    "HYPE_spot": "@107",
    "HYPE_perp": "HYPE",
}


def book(coin: str) -> dict:
    return hl.post({"type": "l2Book", "coin": coin})


def side_levels(b: dict, side: str) -> list[tuple[float, float]]:
    levels = b["levels"][0] if side == "bid" else b["levels"][1]
    return [(float(x["px"]), float(x["sz"])) for x in levels]


def walk(levels: list[tuple[float, float]], notional: float) -> dict | None:
    remaining = notional
    spent = 0.0
    filled = 0.0
    for px, sz in levels:
        val = px * sz
        take = min(remaining, val)
        filled += take / px
        spent += take
        remaining -= take
        if remaining <= 1e-9:
            break
    if remaining > 1e-9:
        return None
    return {"vwap": spent / filled, "filled": filled, "spent": spent}


def main() -> int:
    out = {"instruments": {}}
    for label, coin in INSTRUMENTS.items():
        try:
            b = book(coin)
        except Exception as exc:  # noqa: BLE001
            out["instruments"][label] = {"error": str(exc)}
            continue
        bids = side_levels(b, "bid")
        asks = side_levels(b, "ask")
        best_bid, best_ask = bids[0][0], asks[0][0]
        mid = (best_bid + best_ask) / 2
        rows = []
        for size in SIZES:
            buy = walk(asks, size)
            sell = walk(bids, size)
            rows.append({
                "notional_usd": size,
                "buy_slip_bps": round((buy["vwap"] / mid - 1) * 1e4, 2) if buy else None,
                "sell_slip_bps": round((1 - sell["vwap"] / mid) * 1e4, 2) if sell else None,
                "buy_fillable": buy is not None,
                "sell_fillable": sell is not None,
            })
        # 20bps/50bps 内深度
        depth20 = sum(px * sz for px, sz in asks if px <= mid * 1.002)
        depth20b = sum(px * sz for px, sz in bids if px >= mid * 0.998)
        out["instruments"][label] = {
            "coin": coin, "mid": mid, "best_bid": best_bid, "best_ask": best_ask,
            "spread_bps": round((best_ask - best_bid) / mid * 1e4, 2),
            "ask_depth_within_20bps_usd": round(depth20, 0),
            "bid_depth_within_20bps_usd": round(depth20b, 0),
            "rows": rows,
        }

    (REPORTS / "slippage_depth.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 盘口滑点实测（Hyperliquid L2）", "",
             f"对照回测假设：单边滑点 15 bps。数据抓取：{pd_now()} UTC", ""]
    for label, d in out["instruments"].items():
        if "error" in d:
            lines += [f"## {label}", "", f"- 抓取失败：{d['error']}", ""]
            continue
        lines += [f"## {label}", "",
                  f"- 中间价 {d['mid']:.6g} ｜ 盘口价差 {d['spread_bps']:.2f} bps ｜ 20bps 内深度：买 ${d['ask_depth_within_20bps_usd']:,.0f} / 卖 ${d['bid_depth_within_20bps_usd']:,.0f}",
                  "", "| 单腿金额 | 买入滑点(bps) | 卖出滑点(bps) | 可成交 |", "|---:|---:|---:|:---:|"]
        for r in d["rows"]:
            lines.append(f"| ${r['notional_usd']:,} | {r['buy_slip_bps'] if r['buy_slip_bps'] is not None else 'n/a'} | "
                         f"{r['sell_slip_bps'] if r['sell_slip_bps'] is not None else 'n/a'} | "
                         f"{'✅' if (r['buy_fillable'] and r['sell_fillable']) else '❌'} |")
        lines.append("")
    (REPORTS / "SLIPPAGE_DEPTH.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def pd_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


if __name__ == "__main__":
    raise SystemExit(main())
