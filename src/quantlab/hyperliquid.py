"""Hyperliquid 公开 API 封装（无需 API key）。

只读公开数据：资金费历史、K 线、市场上下文（mark price / OI / 成交量）。
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone

BASE_URL = "https://api.hyperliquid.xyz/info"

# 清理可能存在的失效代理环境变量（不影响系统设置）
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)


class HyperliquidError(RuntimeError):
    pass


def post(body: dict, timeout: float = 15.0, retries: int = 6) -> object:
    """POST /info，带重试；429 时指数退避。"""
    import urllib.error
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                BASE_URL,
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            last = exc
            wait = 8.0 * (i + 1) if exc.code == 429 else 1.5 * (i + 1)
            time.sleep(wait)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (i + 1))
    raise HyperliquidError(f"API 请求失败: {last}")


def funding_history(coin: str, start_ms: int = 0) -> list[dict]:
    """逐小时资金费历史（分页拉全）。返回 [{coin, fundingRate, time}, ...]。"""
    rows: list[dict] = []
    start = int(start_ms)
    for _ in range(1000):
        batch = post({"type": "fundingHistory", "coin": coin, "startTime": start})
        if not batch:
            break
        rows.extend(batch)
        time.sleep(0.12)  # 分页节流，避免 429
        last = int(batch[-1]["time"])
        if last <= start:
            break
        start = last + 1
        if len(batch) < 500:
            break
    return rows


def candles(coin: str, interval: str = "1d", start_ms: int = 0) -> list[dict]:
    """K 线（1m/5m/15m/1h/4h/1d 等）。返回 [{t,o,h,l,c,v}, ...]。"""
    return post({
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": interval, "startTime": int(start_ms)},
    })


def ctxs() -> dict:
    """市场上下文：coin -> {funding, openInterest, dayNtlVlm, markPx, oraclePx, premium...}"""
    data = post({"type": "metaAndAssetCtxs"})
    universe = data[0]["universe"]
    rows = data[1]
    return {m["name"]: c for m, c in zip(universe, rows)}


def to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)

