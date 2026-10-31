"""多账户 paper 交易：$100 档的多个候选策略并行验证。

账户：
  a0_100：PURR 50% + HYPE 50%（推荐方案 A0）
  e_100 ：PURR 37.5% + HYPE 37.5% + BTC 12.5% + ETH 12.5%（分散方案 E）
  b0_100：BTC 50% + ETH 50%（主流方案 B0）

只读公开 API、虚拟资金、无需账户/密钥；每小时增量更新资金费与 NAV。
每个账户独立 state/hourly/REPORT/ALERTS/reconcile。
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
if str(HERE / "src") not in sys.path:
    sys.path.insert(0, str(HERE / "src"))

from quantlab import hyperliquid as hl  # noqa: E402
from quantlab.paper import (  # 复用纯函数，避免重复实现
    compute_nav,
    dedupe_funding,
    funding_amount,
    latest_negative_streak,
    max_drawdown,
    position_mtm,
)

PAPER_DIR = HERE / "paper"
ACCT_ROOT = PAPER_DIR / "accounts"
ENTRY_COST_RATE = 0.00045 + 0.00070 + 2 * 0.0015  # 0.415%
MIN_ORDER_USD = 10.0

ASSETS = {
    "PURR": {"spot_pair": "PURR/USDC", "perp": "PURR", "max_lev": 3.0, "spot_sz": 0, "perp_sz": 0},
    "HYPE": {"spot_pair": "@107", "perp": "HYPE", "max_lev": 10.0, "spot_sz": 2, "perp_sz": 2},
    "BTC": {"spot_pair": "@142", "perp": "BTC", "max_lev": 40.0, "spot_sz": 5, "perp_sz": 5},
    "ETH": {"spot_pair": "@151", "perp": "ETH", "max_lev": 25.0, "spot_sz": 4, "perp_sz": 4},
}

ACCOUNTS = {
    "a0_100": {"capital": 100.0, "weights": {"PURR": 0.5, "HYPE": 0.5}},
    "e_100": {"capital": 100.0, "weights": {"PURR": 0.375, "HYPE": 0.375, "BTC": 0.125, "ETH": 0.125}},
    "b0_100": {"capital": 100.0, "weights": {"BTC": 0.5, "ETH": 0.5}},
}

HOURLY_COLS = ["ts", "nav_usd", "funding_accrued_usd", "mtm_usd", "entry_cost_usd", "funding_positive_share"]


def acct_dir(name: str) -> Path:
    return ACCT_ROOT / name


def paths(name: str) -> dict[str, Path]:
    d = acct_dir(name)
    return {"dir": d, "state": d / "state.json", "hourly": d / "hourly.csv",
            "report": d / "REPORT.md", "alerts": d / "ALERTS.md", "reconcile": d / "reconcile.json",
            "final": d / "FINAL_REPORT.md"}


def floor_to(x: float, decimals: int) -> float:
    factor = 10 ** decimals
    return int(x * factor) / factor


def fetch_prices(asset: str) -> tuple[float, float]:
    cfg = ASSETS[asset]
    now_ms = int(time.time() * 1000)
    spot = hl.candles(cfg["spot_pair"], "1h", now_ms - 3 * 3600 * 1000)
    perp = hl.candles(cfg["perp"], "1h", now_ms - 3 * 3600 * 1000)
    if not spot or not perp:
        raise RuntimeError(f"{asset} 价格获取失败")
    return float(spot[-1]["c"]), float(perp[-1]["c"])


def load_state(name: str) -> dict:
    return json.loads(paths(name)["state"].read_text(encoding="utf-8"))


def save_state(name: str, state: dict) -> None:
    p = paths(name)
    p["dir"].mkdir(parents=True, exist_ok=True)
    p["state"].write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_hourly(name: str) -> None:
    p = paths(name)["hourly"]
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HOURLY_COLS)


def init_account(name: str) -> dict:
    cfg = ACCOUNTS[name]
    now = datetime.now(timezone.utc)
    state = {
        "name": name, "created_at": now.isoformat(timespec="seconds"),
        "capital_usd": cfg["capital"], "weights": cfg["weights"],
        "entry_cost_usd": 0.0, "funding_accrued_usd": 0.0,
        "positions": {}, "funding_last_ts": {}, "funding_stats": {},
        "funding_by_asset": {}, "settlements_log": {}, "hourly_rows": 0,
        "min_order_ok": True,
    }
    total_cost = 0.0
    prices = {a: fetch_prices(a) for a in cfg["weights"]}
    for asset, w in cfg["weights"].items():
        ac = ASSETS[asset]
        spot, perp = prices[asset]
        sleeve = cfg["capital"] * w
        target_notional = sleeve / (1 + 1 / ac["max_lev"])
        qty_spot = floor_to(target_notional / spot, ac["spot_sz"])
        qty_perp = floor_to(target_notional / perp, ac["perp_sz"])
        notional_spot = qty_spot * spot
        notional_perp = qty_perp * perp
        fee = max(notional_spot, notional_perp) * ENTRY_COST_RATE
        total_cost += fee
        ok = min(notional_spot, notional_perp) >= MIN_ORDER_USD
        state["positions"][asset] = {
            "spot_pair": ac["spot_pair"], "perp": ac["perp"], "max_lev": ac["max_lev"],
            "sleeve_usd": round(sleeve, 4),
            "qty_spot": qty_spot, "qty_perp": qty_perp,
            "notional_spot": round(notional_spot, 4), "notional_perp": round(notional_perp, 4),
            "entry_spot": spot, "entry_perp": perp, "entry_fee_usd": round(fee, 6),
            "min_order_ok": ok,
        }
        state["min_order_ok"] = state["min_order_ok"] and ok
        state["funding_last_ts"][asset] = int(now.timestamp() * 1000)
        state["funding_stats"][asset] = {"settlements": 0, "positive": 0}
        state["funding_by_asset"][asset] = 0.0
        state["settlements_log"][asset] = []
    state["entry_cost_usd"] = round(total_cost, 6)
    save_state(name, state)
    ensure_hourly(name)
    write_report(name, state)
    return state


def run_account(name: str, prices: dict[str, tuple[float, float]]) -> dict:
    state = load_state(name)
    cfg = ACCOUNTS[name]
    now = datetime.now(timezone.utc)
    funding_added = 0.0
    for asset in cfg["weights"]:
        pos = state["positions"][asset]
        last = int(state["funding_last_ts"].get(asset, 0))
        rows = dedupe_funding(hl.funding_history(pos["perp"], start_ms=last + 1))
        rows = [r for r in rows if int(r["time"]) > last]
        if rows:
            added = funding_amount(rows, pos["notional_perp"])
            funding_added += added
            state["funding_by_asset"][asset] = state["funding_by_asset"].get(asset, 0.0) + added
            state["funding_accrued_usd"] = state.get("funding_accrued_usd", 0.0) + added
            stats = state["funding_stats"].setdefault(asset, {"settlements": 0, "positive": 0})
            stats["settlements"] += len(rows)
            stats["positive"] += sum(1 for r in rows if float(r["fundingRate"]) > 0)
            log = state["settlements_log"].setdefault(asset, [])
            for r in rows:
                log.append({"time": int(r["time"]), "rate": float(r["fundingRate"]),
                            "usd": round(float(r["fundingRate"]) * pos["notional_perp"], 6)})
            state["settlements_log"][asset] = log[-200:]
            state["funding_last_ts"][asset] = int(rows[-1]["time"])

    mtm = 0.0
    for asset in cfg["weights"]:
        pos = state["positions"][asset]
        spot, perp = prices[asset]
        mtm += position_mtm(pos["qty_spot"], pos["entry_spot"], spot,
                            pos["qty_perp"], pos["entry_perp"], perp)
    nav = compute_nav(state["capital_usd"], state["entry_cost_usd"],
                      state.get("funding_accrued_usd", 0.0), mtm)
    total_sett = sum(s["settlements"] for s in state["funding_stats"].values())
    total_pos = sum(s["positive"] for s in state["funding_stats"].values())
    pos_share = (total_pos / total_sett) if total_sett else 0.0

    ensure_hourly(name)
    with paths(name)["hourly"].open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([now.isoformat(timespec="seconds"), round(nav, 4),
                                round(state.get("funding_accrued_usd", 0.0), 6), round(mtm, 6),
                                state.get("entry_cost_usd", 0.0), round(pos_share, 4)])
    state["hourly_rows"] = int(state.get("hourly_rows", 0)) + 1
    save_state(name, state)
    write_report(name, state)
    return {"account": name, "nav": round(nav, 4), "funding_accrued": round(state.get("funding_accrued_usd", 0.0), 6),
            "funding_added": round(funding_added, 6), "mtm": round(mtm, 6)}


def run_all() -> dict:
    prices = {a: fetch_prices(a) for a in ASSETS}
    out = {}
    for name in ACCOUNTS:
        try:
            out[name] = run_account(name, prices)
        except Exception as exc:  # noqa: BLE001
            out[name] = {"error": str(exc)}
    write_accounts_summary()
    return out


def _navs(name: str) -> list[float]:
    p = paths(name)["hourly"]
    if not p.exists():
        return []
    vals = []
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                vals.append(float(r["nav_usd"]))
            except (TypeError, ValueError):
                continue
    return vals


def reconcile(name: str) -> dict:
    state = load_state(name)
    created_ms = int(datetime.fromisoformat(state["created_at"]).timestamp() * 1000)
    out = {"account": name, "created_at": state["created_at"], "assets": {}}
    total_diff = 0.0
    for asset in ACCOUNTS[name]["weights"]:
        pos = state["positions"][asset]
        rows = dedupe_funding(hl.funding_history(pos["perp"], start_ms=created_ms))
        rows = [r for r in rows if int(r["time"]) >= created_ms]
        expected = funding_amount(rows, pos["notional_perp"])
        actual = float(state["funding_by_asset"].get(asset, 0.0))
        diff = actual - expected
        total_diff += abs(diff)
        out["assets"][asset] = {"expected_usd": round(expected, 6), "actual_usd": round(actual, 6),
                                "diff_usd": round(diff, 6)}
    out["overall"] = "PASS" if total_diff < 0.01 else "FAIL"
    out["diff_total_usd"] = round(total_diff, 6)
    paths(name)["reconcile"].parent.mkdir(parents=True, exist_ok=True)
    paths(name)["reconcile"].write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def evaluate_gate(name: str, now: datetime | None = None) -> dict:
    state = load_state(name)
    now = now or datetime.now(timezone.utc)
    days = (now - datetime.fromisoformat(state["created_at"])).total_seconds() / 86400.0
    navs = _navs(name)
    nav = navs[-1] if navs else state["capital_usd"] - state["entry_cost_usd"]
    ret = nav / state["capital_usd"] - 1.0
    cagr = (nav / state["capital_usd"]) ** (365.0 / days) - 1.0 if days >= 1 and nav > 0 else None
    mdd = max_drawdown(navs) if navs else 0.0
    total_sett = sum(s["settlements"] for s in state.get("funding_stats", {}).values())
    total_pos = sum(s["positive"] for s in state.get("funding_stats", {}).values())
    pos_share = (total_pos / total_sett) if total_sett else 0.0
    rec_pass = False
    rp = paths(name)["reconcile"]
    if rp.exists():
        try:
            rec_pass = json.loads(rp.read_text(encoding="utf-8")).get("overall") == "PASS"
        except Exception:  # noqa: BLE001
            rec_pass = False
    checks = {
        "elapsed_30d": days >= 30,
        "return_positive": ret > 0,
        "cagr_gt_10pct": (cagr is not None and cagr > 0.10),
        "mdd_lt_5pct": mdd < 0.05,
        "funding_positive_share_gt_60pct": pos_share > 0.60,
        "funding_reconcile_pass": rec_pass,
    }
    status = "PENDING" if days < 30 else ("PASS" if all(checks.values()) else "FAIL")
    funding_only = (state.get("funding_accrued_usd", 0.0) / state["capital_usd"]) * (365.0 / days) if days > 0 else 0.0
    return {"account": name, "status": status, "days_elapsed": round(days, 4),
            "nav_usd": round(nav, 4), "return_pct": round(ret * 100, 4),
            "annualized_pct": round(cagr * 100, 4) if cagr is not None else None,
            "funding_only_annualized_pct": round(funding_only * 100, 4),
            "max_drawdown_pct": round(mdd * 100, 4),
            "funding_settlements": total_sett, "funding_positive_share": round(pos_share, 4),
            "checks": checks}


def write_report(name: str, state: dict) -> None:
    navs = _navs(name)
    nav = navs[-1] if navs else state["capital_usd"] - state["entry_cost_usd"]
    mdd = max_drawdown(navs) if navs else 0.0
    total_sett = sum(s["settlements"] for s in state.get("funding_stats", {}).values())
    total_pos = sum(s["positive"] for s in state.get("funding_stats", {}).values())
    pos_share = (total_pos / total_sett) if total_sett else 0.0
    lines = [f"# Paper 账户 {name}", "",
             f"- 启动：{state['created_at']} ｜ 本金 ${state['capital_usd']:.2f} ｜ 建仓成本 ${state['entry_cost_usd']:.4f}",
             f"- 当前 NAV：**${nav:.2f}** ｜ 累计收益：{(nav/state['capital_usd']-1)*100:+.3f}%",
             f"- 累计资金费：${state.get('funding_accrued_usd', 0.0):+.4f} ｜ 结算 {total_sett} 次 ｜ 正费率 {pos_share*100:.1f}%",
             f"- 小时级最大回撤：{mdd*100:.3f}% ｜ 最小下单满足：{'✅' if state.get('min_order_ok') else '❌'}",
             "", "## 持仓", "",
             "| 资产 | 现货数量 | 永续数量 | 入场现货 | 入场永续 | 名义(永续) |",
             "|---|---:|---:|---:|---:|---:|"]
    for asset, p in state["positions"].items():
        lines.append(f"| {asset} | {p['qty_spot']} | {p['qty_perp']} | {p['entry_spot']} | {p['entry_perp']} | ${p['notional_perp']:.2f} |")
    lines += ["", "## 最近结算", "", "| 资产 | 时间(UTC) | 费率 | 金额$ |", "|---|---|---:|---:|"]
    for asset, log in state.get("settlements_log", {}).items():
        for r in log[-3:]:
            ts = datetime.fromtimestamp(r["time"] / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")
            lines.append(f"| {asset} | {ts} | {r['rate']:.8f} | {r['usd']:+.6f} |")
    paths(name)["report"].write_text("\n".join(lines), encoding="utf-8")

    # 告警
    alerts = []
    if mdd > 0.05:
        alerts.append(f"最大回撤 {mdd*100:.2f}% > 5%")
    for asset, log in state.get("settlements_log", {}).items():
        streak = latest_negative_streak([r["rate"] for r in log])
        if streak >= 12:
            alerts.append(f"{asset} 连续 {streak} 次负资金费")
    paths(name)["alerts"].write_text("\n".join(["# Paper 告警", ""] + (alerts if alerts else ["无告警（OK）"])) + "\n",
                                     encoding="utf-8")


def write_accounts_summary() -> None:
    ACCT_ROOT.mkdir(parents=True, exist_ok=True)
    lines = ["# $100 Paper 账户总览", "",
             "| 账户 | 策略 | 本金 | NAV | 收益 | 累计资金费 | 正费率 | 对账 |", "|---|---|---:|---:|---:|---:|---:|---|"]
    for name, cfg in ACCOUNTS.items():
        try:
            state = load_state(name)
            navs = _navs(name)
            nav = navs[-1] if navs else state["capital_usd"] - state["entry_cost_usd"]
            total_sett = sum(s["settlements"] for s in state.get("funding_stats", {}).values())
            total_pos = sum(s["positive"] for s in state.get("funding_stats", {}).values())
            share = total_pos / total_sett if total_sett else 0.0
            rp = paths(name)["reconcile"]
            rec = json.loads(rp.read_text(encoding="utf-8")).get("overall") if rp.exists() else "n/a"
            lines.append(f"| {name} | {'/'.join(f'{a}{int(w*100)}%' for a, w in cfg['weights'].items())} | "
                         f"${cfg['capital']:.0f} | ${nav:.2f} | {(nav/cfg['capital']-1)*100:+.3f}% | "
                         f"${state.get('funding_accrued_usd',0):+.4f} | {share*100:.1f}% | {rec} |")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"| {name} | - | - | - | - | - | - | {exc} |")
    lines += ["", "> 各账户独立虚拟资金；数字每小时更新。"]
    (PAPER_DIR / "ACCOUNTS.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "init":
        for name in ACCOUNTS:
            init_account(name)
            print("initialized", name)
        write_accounts_summary()
    elif cmd == "run":
        print(json.dumps(run_all(), ensure_ascii=False, indent=2))
    elif cmd == "status":
        for name in ACCOUNTS:
            print(f"--- {name}")
            print(json.dumps(evaluate_gate(name), ensure_ascii=False, indent=2))
    elif cmd == "gate":
        print(json.dumps({n: evaluate_gate(n) for n in ACCOUNTS}, ensure_ascii=False, indent=2))
    elif cmd == "reconcile":
        print(json.dumps({n: reconcile(n) for n in ACCOUNTS}, ensure_ascii=False, indent=2))
    else:
        print("unknown command", cmd)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
