#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预登记下一小时资金费结算的预期金额（用于 paper 对账验证）。

读取 Hyperliquid 市场上下文的当前小时资金费率，按 paper 持仓名义计算预期入账。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import hyperliquid as hl  # noqa: E402
from quantlab import paper  # noqa: E402

OUT = ROOT / "paper" / "expected_settlement.json"


def main() -> int:
    state = paper.load_state()
    ctxs = hl.ctxs()
    out = {"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "assets": {}}
    total = 0.0
    for asset, pos in state["positions"].items():
        ctx = ctxs.get(pos["perp"], {})
        rate = float(ctx.get("funding", 0.0))  # 当前小时资金费率
        usd = rate * float(pos["notional_usd"])
        total += usd
        out["assets"][asset] = {"hourly_rate": rate, "notional_usd": pos["notional_usd"],
                                "expected_usd": round(usd, 6),
                                "mark_px": ctx.get("markPx")}
    out["expected_total_usd"] = round(total, 6)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
