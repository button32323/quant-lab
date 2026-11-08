#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apple 风格量化监控面板：本地 HTTP 服务 + /api/summary。

只读项目内 paper 数据，不涉及交易/密钥。
"""
from __future__ import annotations

import csv
import json
import math
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = Path(__file__).resolve().parent
PAPER = ROOT / "paper"

ACCOUNTS = [
    {"id": "a0_100", "name": "A0 · PURR+HYPE", "sub": "$100 小市值 carry", "capital": 100.0,
     "state": PAPER / "accounts" / "a0_100" / "state.json",
     "hourly": PAPER / "accounts" / "a0_100" / "hourly.csv",
     "reconcile": PAPER / "accounts" / "a0_100" / "reconcile.json",
     "alerts": PAPER / "accounts" / "a0_100" / "ALERTS.md"},
    {"id": "e_100", "name": "E · 75/25 分散", "sub": "$100 小市值+主流", "capital": 100.0,
     "state": PAPER / "accounts" / "e_100" / "state.json",
     "hourly": PAPER / "accounts" / "e_100" / "hourly.csv",
     "reconcile": PAPER / "accounts" / "e_100" / "reconcile.json",
     "alerts": PAPER / "accounts" / "e_100" / "ALERTS.md"},
    {"id": "b0_100", "name": "B0 · BTC+ETH", "sub": "$100 主流 carry", "capital": 100.0,
     "state": PAPER / "accounts" / "b0_100" / "state.json",
     "hourly": PAPER / "accounts" / "b0_100" / "hourly.csv",
     "reconcile": PAPER / "accounts" / "b0_100" / "reconcile.json",
     "alerts": PAPER / "accounts" / "b0_100" / "ALERTS.md"},
]
MAIN = {"id": "main", "name": "A0 · 主账户", "sub": "$1,000 PURR+HYPE carry", "capital": 1000.0,
        "state": PAPER / "state.json", "hourly": PAPER / "hourly.csv",
        "reconcile": PAPER / "reconcile.json", "alerts": PAPER / "ALERTS.md"}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _hourly(path: Path, limit: int = 120) -> list[float]:
    if not path.exists():
        return []
    vals: list[float] = []
    try:
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    vals.append(float(row["nav_usd"]))
                except (TypeError, ValueError, KeyError):
                    continue
    except Exception:  # noqa: BLE001
        return []
    return vals[-limit:]


def _mdd(vals: list[float]) -> float:
    peak, mdd = -math.inf, 0.0
    for v in vals:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd


def _age_min(path: Path) -> float | None:
    if not path.exists():
        return None
    return (time.time() - path.stat().st_mtime) / 60.0


def account_payload(cfg: dict) -> dict:
    st = _read_json(cfg["state"])
    if not st:
        return {"id": cfg["id"], "name": cfg["name"], "sub": cfg["sub"], "capital": cfg["capital"],
                "ok": False, "error": "state 缺失"}
    capital = float(st.get("capital_usd", cfg["capital"]))
    entry = float(st.get("entry_cost_usd", 0.0))
    funding = float(st.get("funding_accrued_usd", 0.0))
    navs = _hourly(cfg["hourly"])
    nav = navs[-1] if navs else capital - entry
    created = datetime.fromisoformat(st["created_at"])
    days = max((datetime.now(timezone.utc) - created).total_seconds() / 86400.0, 0.0)
    stats = st.get("funding_stats", {})
    total_sett = sum(int(v.get("settlements", 0)) for v in stats.values())
    total_pos = sum(int(v.get("positive", 0)) for v in stats.values())
    rec = _read_json(cfg["reconcile"]).get("overall", "n/a")
    alerts = ""
    if cfg["alerts"].exists():
        lines = [x.strip() for x in cfg["alerts"].read_text(encoding="utf-8").splitlines() if x.strip()]
        alerts = lines[-1] if lines else ""
    ret = nav / capital - 1.0
    fund_ann = (funding / capital) * (365.0 / days) if days > 0 else 0.0
    gate_date = (created.timestamp() + 30 * 86400)
    return {
        "id": cfg["id"], "name": cfg["name"], "sub": cfg["sub"], "capital": capital,
        "ok": True, "nav": round(nav, 2), "ret": round(ret * 100, 3),
        "funding": round(funding, 4), "mtm": round(float(st.get("mtm_usd", 0.0)), 4) if "mtm_usd" in st else None,
        "entry": round(entry, 4), "coverage": round(funding / entry * 100, 0) if entry else 0,
        "fund_ann": round(fund_ann * 100, 2), "mdd": round(_mdd(navs) * 100, 3) if navs else 0.0,
        "days": round(days, 2), "settlements": total_sett,
        "pos_share": round((total_pos / total_sett * 100) if total_sett else 0.0, 1),
        "reconcile": rec, "alerts": alerts,
        "series": [round(v, 2) for v in navs[-72:]],
        "gate_days": round(days, 1), "gate_pct": min(100.0, days / 30.0 * 100),
        "gate_date": datetime.fromtimestamp(gate_date, tz=timezone.utc).strftime("%m-%d"),
        "min_order": bool(st.get("min_order_ok", True)),
    }


def summary() -> dict:
    main = account_payload(MAIN)
    accounts = [account_payload(a) for a in ACCOUNTS]
    # mtm 从 state 里没有直接字段；用 nav 反推（nav = cap - entry + funding + mtm）
    for p in [main] + accounts:
        if p.get("ok"):
            p["mtm"] = round(p["nav"] - p["capital"] + p["entry"] - p["funding"], 4)
    total_cap = sum(p["capital"] for p in [main] + accounts if p.get("ok"))
    total_nav = sum(p["nav"] for p in [main] + accounts if p.get("ok"))
    total_fund = sum(p["funding"] for p in [main] + accounts if p.get("ok"))
    main_age = _age_min(PAPER / "heartbeat.txt")
    acct_age = _age_min(PAPER / "accounts" / "heartbeat.txt")
    return {
        "now": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "totals": {"capital": round(total_cap, 2), "nav": round(total_nav, 2),
                   "ret": round((total_nav / total_cap - 1) * 100, 3),
                   "funding": round(total_fund, 4)},
        "main": main, "accounts": accounts,
        "system": {
            "main_runner": None if main_age is None else round(main_age, 1),
            "acct_runner": None if acct_age is None else round(acct_age, 1),
            "online": (main_age is not None and main_age < 90) and (acct_age is not None and acct_age < 90),
        },
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASH), **kwargs)

    def log_message(self, fmt, *args):  # 静默
        pass

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] == "/api/summary":
            data = json.dumps(summary(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()


def main() -> int:
    port = 8765
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"dashboard: http://127.0.0.1:{port}")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
