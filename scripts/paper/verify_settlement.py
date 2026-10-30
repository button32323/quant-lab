#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结算后验证：对比预登记预期与实际入账金额。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import paper  # noqa: E402

EXPECTED = ROOT / "paper" / "expected_settlement.json"
OUT = ROOT / "paper" / "settlement_verification.json"


def main() -> int:
    if not EXPECTED.exists():
        print("没有预登记文件")
        return 1
    exp = json.loads(EXPECTED.read_text(encoding="utf-8"))
    state = paper.load_state()
    recorded = datetime.fromisoformat(exp["recorded_at"])
    next_hour = recorded.replace(minute=0, second=0, microsecond=0)
    from datetime import timedelta
    next_hour = next_hour + timedelta(hours=1)
    start_ms = int(next_hour.timestamp() * 1000)
    end_ms = start_ms + 3600 * 1000

    out = {"expected_file": str(EXPECTED), "recorded_at": exp["recorded_at"],
           "settlement_hour_utc": next_hour.isoformat(timespec="seconds"), "assets": {}}
    total_actual = 0.0
    total_expected = 0.0
    for asset, pos in state["positions"].items():
        rows = [r for r in state.get("settlements_log", {}).get(asset, [])
                if start_ms <= int(r["time"]) < end_ms]
        actual = sum(float(r["usd"]) for r in rows)
        expected = float(exp.get("assets", {}).get(asset, {}).get("expected_usd", 0.0))
        diff = actual - expected
        total_actual += actual
        total_expected += expected
        out["assets"][asset] = {"expected_usd": round(expected, 6), "actual_usd": round(actual, 6),
                                "diff_usd": round(diff, 6), "settlements_found": len(rows),
                                "rows": rows}
    out["expected_total_usd"] = round(total_expected, 6)
    out["actual_total_usd"] = round(total_actual, 6)
    out["diff_total_usd"] = round(total_actual - total_expected, 6)
    tolerance = max(0.02 * abs(total_expected), 0.002)
    out["tolerance_usd"] = round(tolerance, 6)
    out["verdict"] = ("PASS" if total_expected > 0 and abs(out["diff_total_usd"]) <= tolerance
                      else ("PENDING" if total_actual == 0 else "FAIL"))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
