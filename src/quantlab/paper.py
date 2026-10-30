"""Paper 交易引擎：Hyperliquid 现货-永续资金费 carry（PURR + HYPE）。

只读公开 API、虚拟资金、无账户/密钥。逐小时增量更新资金费与 NAV。
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

CAPITAL = 1000.0
ENTRY_COST_RATE = 0.00045 + 0.00070 + 2 * 0.0015  # 0.415%
PAPER_DIR = HERE / "paper"
STATE = PAPER_DIR / "state.json"
HOURLY = PAPER_DIR / "hourly.csv"
REPORT = PAPER_DIR / "REPORT.md"
RECONCILE = PAPER_DIR / "reconcile.json"

ASSETS = {
    "PURR": {"spot_pair": "PURR/USDC", "perp": "PURR", "max_lev": 3.0},
    "HYPE": {"spot_pair": "@107", "perp": "HYPE", "max_lev": 10.0},
}

HOURLY_COLS = ["ts", "nav_usd", "funding_accrued_usd", "mtm_usd", "entry_cost_usd",
               "funding_positive_share", "PURR_spot", "PURR_perp", "HYPE_spot", "HYPE_perp"]


# ---------------- 纯函数（可测试） ----------------
def dedupe_funding(rows: list[dict]) -> list[dict]:
    """按时间戳去重并排序。"""
    uniq: dict[int, dict] = {}
    for r in rows:
        uniq[int(r["time"])] = r
    return [uniq[t] for t in sorted(uniq)]


def funding_amount(rows: list[dict], notional: float) -> float:
    """资金费金额 = Σ rate × notional（正费率、空头收取为正）。"""
    return sum(float(r["fundingRate"]) for r in rows) * notional


def position_mtm(qty_spot: float, entry_spot: float, spot: float,
                 qty_perp: float, entry_perp: float, perp: float) -> float:
    """现货多头 + 永续空头的市值盈亏（basis 盈亏）。"""
    return qty_spot * (spot - entry_spot) - qty_perp * (perp - entry_perp)


def compute_nav(capital: float, entry_cost: float, funding: float, mtm: float) -> float:
    return capital - entry_cost + funding + mtm


def max_drawdown(values: list[float]) -> float:
    peak = float("-inf")
    mdd = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd


def latest_negative_streak(rates: list[float]) -> int:
    """按时间顺序的费率列表中，末尾连续负值的数量。"""
    streak = 0
    for r in reversed(rates):
        if r < 0:
            streak += 1
        else:
            break
    return streak


# ---------------- 网络与状态 ----------------
def fetch_prices(asset: str) -> tuple[float, float]:
    cfg = ASSETS[asset]
    now_ms = int(time.time() * 1000)
    spot = hl.candles(cfg["spot_pair"], "1h", now_ms - 3 * 3600 * 1000)
    perp = hl.candles(cfg["perp"], "1h", now_ms - 3 * 3600 * 1000)
    if not spot or not perp:
        raise RuntimeError(f"{asset} 价格获取失败")
    return float(spot[-1]["c"]), float(perp[-1]["c"])


def load_state() -> dict:
    if not STATE.exists():
        raise FileNotFoundError("paper 未初始化，先运行 init")
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def init(capital: float = CAPITAL) -> dict:
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    state = {
        "created_at": now.isoformat(timespec="seconds"),
        "capital_usd": capital,
        "entry_cost_usd": 0.0,
        "funding_accrued_usd": 0.0,
        "positions": {},
        "funding_last_ts": {},
        "funding_stats": {},
        "funding_by_asset": {},
        "settlements_log": {},
        "hourly_rows": 0,
    }
    total_cost = 0.0
    for asset, cfg in ASSETS.items():
        spot, perp = fetch_prices(asset)
        sleeve = capital / 2.0
        notional = sleeve / (1 + 1 / cfg["max_lev"])
        qty_spot = notional / spot
        qty_perp = notional / perp
        fee = notional * ENTRY_COST_RATE
        total_cost += fee
        state["positions"][asset] = {
            "spot_pair": cfg["spot_pair"], "perp": cfg["perp"], "max_lev": cfg["max_lev"],
            "sleeve_usd": round(sleeve, 2), "notional_usd": round(notional, 2),
            "qty_spot": qty_spot, "qty_perp": qty_perp,
            "entry_spot": round(spot, 8), "entry_perp": round(perp, 8), "entry_fee_usd": round(fee, 4),
        }
        state["funding_last_ts"][asset] = int(now.timestamp() * 1000)
        state["funding_by_asset"][asset] = 0.0
        state["funding_stats"][asset] = {"settlements": 0, "positive": 0}
        state["settlements_log"][asset] = []
    state["entry_cost_usd"] = round(total_cost, 4)
    save_state(state)
    _ensure_hourly()
    write_report(state)
    return state


def _ensure_hourly() -> None:
    if not HOURLY.exists():
        with HOURLY.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HOURLY_COLS)


def run_once() -> dict:
    state = load_state()
    now = datetime.now(timezone.utc)
    funding_added = 0.0
    for asset, pos in state["positions"].items():
        last = int(state["funding_last_ts"].get(asset, 0))
        rows = dedupe_funding(hl.funding_history(pos["perp"], start_ms=last + 1))
        rows = [r for r in rows if int(r["time"]) > last]
        if rows:
            added = funding_amount(rows, pos["notional_usd"])
            funding_added += added
            state["funding_accrued_usd"] = state.get("funding_accrued_usd", 0.0) + added
            fba = state.setdefault("funding_by_asset", {})
            fba[asset] = fba.get(asset, 0.0) + added
            stats = state["funding_stats"].setdefault(asset, {"settlements": 0, "positive": 0})
            stats["settlements"] += len(rows)
            stats["positive"] += sum(1 for r in rows if float(r["fundingRate"]) > 0)
            log = state["settlements_log"].setdefault(asset, [])
            for r in rows:
                log.append({"time": int(r["time"]), "rate": float(r["fundingRate"]),
                            "usd": round(float(r["fundingRate"]) * pos["notional_usd"], 6)})
            state["settlements_log"][asset] = log[-200:]
            state["funding_last_ts"][asset] = int(rows[-1]["time"])

    prices = {}
    mtm = 0.0
    for asset, pos in state["positions"].items():
        spot, perp = fetch_prices(asset)
        prices[asset] = {"spot": spot, "perp": perp}
        mtm += position_mtm(pos["qty_spot"], pos["entry_spot"], spot, pos["qty_perp"], pos["entry_perp"], perp)
    nav = compute_nav(state["capital_usd"], state["entry_cost_usd"],
                      state.get("funding_accrued_usd", 0.0), mtm)
    total_sett = sum(s["settlements"] for s in state["funding_stats"].values())
    total_pos = sum(s["positive"] for s in state["funding_stats"].values())
    pos_share = (total_pos / total_sett) if total_sett else 0.0

    row = [now.isoformat(timespec="seconds"), round(nav, 4), round(state.get("funding_accrued_usd", 0.0), 6),
           round(mtm, 6), state.get("entry_cost_usd", 0.0), round(pos_share, 4),
           prices.get("PURR", {}).get("spot"), prices.get("PURR", {}).get("perp"),
           prices.get("HYPE", {}).get("spot"), prices.get("HYPE", {}).get("perp")]
    _ensure_hourly()
    with HOURLY.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)
    state["hourly_rows"] = int(state.get("hourly_rows", 0)) + 1
    save_state(state)
    write_report(state)
    return {"nav": nav, "funding_accrued": state.get("funding_accrued_usd", 0.0),
            "mtm": mtm, "funding_added": funding_added, "funding_positive_share": pos_share}


def reconcile() -> dict:
    state = load_state()
    created_ms = int(datetime.fromisoformat(state["created_at"]).timestamp() * 1000)
    out = {"created_at": state["created_at"], "assets": {}}
    total_diff = 0.0
    for asset, pos in state["positions"].items():
        rows = dedupe_funding(hl.funding_history(pos["perp"], start_ms=created_ms))
        rows = [r for r in rows if int(r["time"]) >= created_ms]
        expected = funding_amount(rows, pos["notional_usd"])
        actual = float(state.get("funding_by_asset", {}).get(asset, 0.0))
        diff = actual - expected
        total_diff += abs(diff)
        out["assets"][asset] = {"expected_usd": round(expected, 6), "actual_usd": round(actual, 6),
                                "diff_usd": round(diff, 6)}
    out["overall"] = "PASS" if total_diff < 0.01 else "FAIL"
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    RECONCILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


GATE = {"days": 30, "return_gt": 0.0, "cagr_gt": 0.10, "mdd_lt": 0.05,
        "funding_positive_share_gt": 0.60, "reconcile_pass": True}


def evaluate_gate(state: dict, now: datetime | None = None) -> dict:
    """30 天验证门禁评估（基于 hourly.csv 与 reconcile.json）。"""
    now = now or datetime.now(timezone.utc)
    created = datetime.fromisoformat(state["created_at"])
    days = (now - created).total_seconds() / 86400.0
    navs = []
    if HOURLY.exists():
        with HOURLY.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    navs.append(float(r["nav_usd"]))
                except (TypeError, ValueError):
                    continue
    nav = navs[-1] if navs else state["capital_usd"] - state["entry_cost_usd"]
    ret = nav / state["capital_usd"] - 1.0
    cagr = (nav / state["capital_usd"]) ** (365.0 / days) - 1.0 if days >= 1 and nav > 0 else None
    mdd = max_drawdown(navs) if navs else 0.0
    total_sett = sum(s["settlements"] for s in state.get("funding_stats", {}).values())
    total_pos = sum(s["positive"] for s in state.get("funding_stats", {}).values())
    pos_share = (total_pos / total_sett) if total_sett else 0.0
    rec_pass = False
    if RECONCILE.exists():
        try:
            rec_pass = json.loads(RECONCILE.read_text(encoding="utf-8")).get("overall") == "PASS"
        except Exception:  # noqa: BLE001
            rec_pass = False
    checks = {
        "elapsed_30d": days >= GATE["days"],
        "return_positive": ret > GATE["return_gt"],
        "cagr_gt_10pct": (cagr is not None and cagr > GATE["cagr_gt"]),
        "mdd_lt_5pct": mdd < GATE["mdd_lt"],
        "funding_positive_share_gt_60pct": pos_share > GATE["funding_positive_share_gt"],
        "funding_reconcile_pass": rec_pass,
    }
    status = "PENDING" if days < GATE["days"] else ("PASS" if all(checks.values()) else "FAIL")
    funding_only_ann = (state.get("funding_accrued_usd", 0.0) / state["capital_usd"]) * (365.0 / days) if days > 0 else 0.0
    return {"status": status, "days_elapsed": round(days, 4), "nav_usd": round(nav, 4),
            "funding_only_annualized_pct": round(funding_only_ann * 100, 4),
            "return_pct": round(ret * 100, 4),
            "annualized_pct": round(cagr * 100, 4) if cagr is not None else None,
            "max_drawdown_pct": round(mdd * 100, 4),
            "funding_settlements": total_sett,
            "funding_positive_share": round(pos_share, 4),
            "checks": checks}


def write_report(state: dict) -> None:
    navs = []
    if HOURLY.exists():
        with HOURLY.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    navs.append(float(r["nav_usd"]))
                except (TypeError, ValueError):
                    continue
    mdd = max_drawdown(navs) if navs else 0.0
    total_sett = sum(s["settlements"] for s in state.get("funding_stats", {}).values())
    total_pos = sum(s["positive"] for s in state.get("funding_stats", {}).values())
    pos_share = (total_pos / total_sett) if total_sett else 0.0
    nav_last = navs[-1] if navs else state["capital_usd"] - state["entry_cost_usd"]
    lines = [
        "# Paper 交易报告（HL PURR+HYPE carry）", "",
        f"- 启动时间：{state['created_at']}",
        f"- 初始资金：${state['capital_usd']:.2f} ｜ 建仓成本：${state['entry_cost_usd']:.2f}",
        f"- 当前 NAV：**${nav_last:.2f}** ｜ 累计收益：{(nav_last/state['capital_usd']-1)*100:+.3f}%",
        f"- 累计资金费：${state.get('funding_accrued_usd', 0):+.4f} ｜ 结算次数：{total_sett} ｜ 正费率占比：{pos_share*100:.1f}%",
        f"- 最大回撤（小时级）：{mdd*100:.3f}%",
        "",
        "## 持仓",
        "",
        "| 资产 | 名义$ | 现货数量 | 永续数量 | 入场现货 | 入场永续 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for asset, p in state["positions"].items():
        lines.append(f"| {asset} | ${p['notional_usd']:.2f} | {p['qty_spot']:.6f} | {p['qty_perp']:.6f} | "
                     f"{p['entry_spot']} | {p['entry_perp']} |")
    lines += [
        "", "## 最近结算（最多 5 笔/资产）", "",
        "| 资产 | 时间(UTC) | 费率 | 金额$ |", "|---|---|---:|---:|",
    ]
    for asset, log in state.get("settlements_log", {}).items():
        for r in log[-5:]:
            ts = datetime.fromtimestamp(r["time"] / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")
            lines.append(f"| {asset} | {ts} | {r['rate']:.8f} | {r['usd']:+.6f} |")
    lines += ["", "> paper 模拟盘：公开数据、虚拟资金，不涉及真实订单。"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "init":
        init()
        print("initialized")
    elif cmd == "run":
        print(json.dumps(run_once(), ensure_ascii=False))
    elif cmd == "reconcile":
        print(json.dumps(reconcile(), ensure_ascii=False, indent=2))
    elif cmd == "gate":
        print(json.dumps(evaluate_gate(load_state()), ensure_ascii=False, indent=2))
    elif cmd == "status":
        st = load_state()
        print(json.dumps({k: st[k] for k in ("created_at", "capital_usd", "entry_cost_usd",
                                            "funding_accrued_usd", "funding_by_asset", "hourly_rows", "funding_stats")},
                         ensure_ascii=False, indent=2))
    else:
        print(f"unknown command: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))





