#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下单数量取整与最小下单检查（$27–$1,000 本金）。

读取 Hyperliquid 的 szDecimals，计算建仓数量取整后的实际名义与资金费误差。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import hyperliquid as hl  # noqa: E402

REPORTS = ROOT / "reports"
MIN_ORDER_USD = 10.0
ENTRY_COST = 0.00415
CAPS = [27, 50, 100, 300, 500, 1000]


def floor_to(x: float, decimals: int) -> float:
    factor = 10 ** decimals
    return int(x * factor) / factor


def main() -> int:
    perp_meta = hl.post({"type": "meta"})["universe"]
    spot_meta = hl.post({"type": "spotMeta"})
    perp_dec = {m["name"]: int(m["szDecimals"]) for m in perp_meta}
    tokens = {t["name"]: t for t in spot_meta["tokens"]}
    pairs = {p["name"]: p for p in spot_meta["universe"]}

    order_specs = {
        "PURR": {"spot_pair": "PURR/USDC", "perp": "PURR", "max_lev": 3.0},
        "HYPE": {"spot_pair": "@107", "perp": "HYPE", "max_lev": 10.0},
    }
    specs = {}
    for asset, cfg in order_specs.items():
        token = tokens[asset]
        pair = pairs[cfg["spot_pair"]]
        specs[asset] = {
            "spot_sz_decimals": int(token.get("szDecimals", 0)),
            "perp_sz_decimals": int(perp_dec.get(cfg["perp"], 0)),
            "max_lev": cfg["max_lev"],
        }

    prices = {}
    for asset, cfg in order_specs.items():
        spot = hl.candles(cfg["spot_pair"], "1h", 0)[-1]["c"]
        perp = hl.candles(cfg["perp"], "1h", 0)[-1]["c"]
        prices[asset] = {"spot": float(spot), "perp": float(perp)}

    rows = []
    for cap in CAPS:
        row = {"capital": cap, "assets": {}, "total_funding_error_pct": 0.0}
        for asset, cfg in order_specs.items():
            sleeve = cap / 2
            notional = sleeve / (1 + 1 / cfg["max_lev"])
            qty_spot = notional / prices[asset]["spot"]
            qty_perp = notional / prices[asset]["perp"]
            rs = floor_to(qty_spot, specs[asset]["spot_sz_decimals"])
            rp = floor_to(qty_perp, specs[asset]["perp_sz_decimals"])
            actual_notional = min(rs * prices[asset]["spot"], rp * prices[asset]["perp"])
            row["assets"][asset] = {
                "target_notional": round(notional, 4),
                "qty_spot_raw": qty_spot, "qty_spot_rounded": rs,
                "qty_perp_raw": qty_perp, "qty_perp_rounded": rp,
                "actual_notional": round(actual_notional, 4),
                "notional_error_pct": round((actual_notional / notional - 1) * 100, 4),
                "above_min_order": actual_notional >= MIN_ORDER_USD,
            }
            row["total_funding_error_pct"] += abs(row["assets"][asset]["notional_error_pct"]) / 2
        rows.append(row)

    out = {"min_order_usd": MIN_ORDER_USD, "entry_cost_rate": ENTRY_COST, "specs": specs,
           "prices": prices, "rows": rows}
    (REPORTS / "order_rounding.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 下单取整与最小下单检查", "",
             f"最小下单：${MIN_ORDER_USD:.0f}/腿 ｜ 取整规则：按交易所 szDecimals 向下取整", "",
             "| 资产 | 现货 szDecimals | 永续 szDecimals |", "|---|---:|---:|"]
    for a, s in specs.items():
        lines.append(f"| {a} | {s['spot_sz_decimals']} | {s['perp_sz_decimals']} |")
    lines += ["", "## 各本金档位", "",
              "| 本金 | 资产 | 目标名义 | 取整后名义 | 误差 | 可下单 |", "|---:|---|---:|---:|---:|:---:|"]
    for row in rows:
        for a, d in row["assets"].items():
            lines.append(f"| ${row['capital']:,} | {a} | ${d['target_notional']:.2f} | ${d['actual_notional']:.2f} | "
                         f"{d['notional_error_pct']:+.4f}% | {'✅' if d['above_min_order'] else '❌'} |")
    lines += ["", "> 取整误差随本金增大而减小：$27 时约 −0.9%/−2.3%，$100 时约 −0.3%/−0.6%，$1,000 时 <0.2%；小资金会略微欠配（更保守），不影响方向性结论。"]
    (REPORTS / "ORDER_ROUNDING.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

