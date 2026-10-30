"""Binance 公共历史 K 线数据（data.binance.vision，无需密钥）。

用于离线回测：monthly + daily zip 文件，CSV 格式。
"""
from __future__ import annotations

import io
import json
import os
import time
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = "https://data.binance.vision/data/spot"

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)


def _get(url: str, retries: int = 4, timeout: float = 20.0) -> bytes:
    import urllib.error
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quantlab/0.1"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            # 404/403：文件不存在，直接失败，不重试
            if exc.code in (403, 404):
                raise RuntimeError(f"文件不存在 {url}") from exc
            last = exc
            time.sleep(1.5 * (i + 1))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"下载失败 {url}: {last}")


def _parse_zip_csv(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not names:
            return []
        raw = zf.read(names[0]).decode("utf-8").strip().splitlines()
    rows = []
    for line in raw:
        parts = [p.strip() for p in line.split(",")]
        if not parts or not parts[0] or parts[0].lower().startswith("open"):
            continue
        rows.append(parts)
    return rows


def _to_bars(rows: list[list[str]]) -> list[dict]:
    out = []
    for p in rows:
        if len(p) < 6:
            continue
        ts = int(float(p[0]))
        if ts > 100_000_000_000_000:  # 2025 起部分文件使用微秒时间戳
            ts //= 1000
        if not (100_000_000_000 < ts < 2_500_000_000_000):  # 合理性校验（2010~2049）
            continue
        out.append({
            "open_time": ts,
            "open": float(p[1]),
            "high": float(p[2]),
            "low": float(p[3]),
            "close": float(p[4]),
            "volume": float(p[5]),
        })
    return out


def month_zip_url(symbol: str, interval: str, year: int, month: int) -> str:
    return f"{BASE}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{year:04d}-{month:02d}.zip"


def day_zip_url(symbol: str, interval: str, day: date) -> str:
    return f"{BASE}/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{day.isoformat()}.zip"


def fetch_daily_bars(
    symbol: str = "BTCUSDT",
    interval: str = "1d",
    start: date = date(2017, 8, 1),
    end: date | None = None,
    cache_dir: Path | None = None,
    sleep: float = 0.05,
) -> list[dict]:
    """拉取 [start, end] 的日线 K 线（monthly 文件 + 当月 daily 文件）。"""
    end = end or date.today()
    cache_dir = cache_dir or Path("data/cache/binance")
    cache_dir.mkdir(parents=True, exist_ok=True)
    bars: dict[int, dict] = {}

    # 完整月份
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        if date(y, m, 1) > end:
            break
        month_start = date(y, m, 1)
        # 仅下载已结束的月份
        if (month_start.year, month_start.month) >= (end.year, end.month):
            break
        cache = cache_dir / f"{symbol}-{interval}-{y:04d}-{m:02d}.zip"
        if not cache.exists():
            url = month_zip_url(symbol, interval, y, m)
            try:
                cache.write_bytes(_get(url))
            except RuntimeError:
                # 缺失月份跳过（例如该月无数据）
                pass
            time.sleep(sleep)
        if cache.exists():
            for b in _to_bars(_parse_zip_csv(cache.read_bytes())):
                bars[b["open_time"]] = b
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1

    # 当月：逐日文件
    d = date(end.year, end.month, 1)
    while d <= end:
        cache = cache_dir / f"{symbol}-{interval}-{d.isoformat()}.zip"
        if not cache.exists():
            url = day_zip_url(symbol, interval, d)
            try:
                cache.write_bytes(_get(url))
            except RuntimeError:
                pass
            time.sleep(sleep)
        if cache.exists():
            for b in _to_bars(_parse_zip_csv(cache.read_bytes())):
                bars[b["open_time"]] = b
        d += timedelta(days=1)

    return [bars[k] for k in sorted(bars)]



