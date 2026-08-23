#!/usr/bin/env python3
"""CoinGecko 시총을 이용해 BTC.D·TOTAL2·OTHERS 프록시를 만든다.

화면의 TradingView 차트와 자동 판정값은 역할을 분리한다. 이 파일의 값은
정확한 CRYPTOCAP 지수가 아니라 같은 자금 흐름을 읽기 위한 CoinGecko 프록시다.
"""
from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "global_market_data.json"
HISTORY = ROOT / "history" / "global_market_snapshots.json"


def _api_config() -> tuple[str, dict[str, str]]:
    key = os.getenv("COINGECKO_API_KEY", "").strip()
    plan = os.getenv("COINGECKO_API_PLAN", "demo").strip().lower()
    if plan == "pro":
        return "https://pro-api.coingecko.com/api/v3", ({"x-cg-pro-api-key": key} if key else {})
    return "https://api.coingecko.com/api/v3", ({"x-cg-demo-api-key": key} if key else {})


def _get(path: str, params: dict | None = None) -> dict | list:
    base, headers = _api_config()
    response = requests.get(
        f"{base}{path}", params=params or {}, headers={**headers, "Accept": "application/json"}, timeout=30
    )
    response.raise_for_status()
    return response.json()


def _previous(current: float, change_pct: float | None) -> float | None:
    if change_pct is None or change_pct <= -100:
        return None
    return current / (1 + change_pct / 100)


def _previous_cap(row: dict) -> float | None:
    """같은 /coins/markets 응답 안에서 24시간 전 시총을 복원한다."""
    current = row.get("market_cap")
    if not isinstance(current, (int, float)):
        return None
    absolute_change = row.get("market_cap_change_24h")
    if isinstance(absolute_change, (int, float)):
        return float(current) - float(absolute_change)
    percentage_change = row.get("market_cap_change_percentage_24h")
    return _previous(float(current), float(percentage_change) if isinstance(percentage_change, (int, float)) else None)


def _change(current: float, previous: float | None) -> float | None:
    if previous in (None, 0):
        return None
    return (current / previous - 1) * 100


def calculate_proxy(_global_payload: dict, coins: list[dict]) -> dict:
    """CoinGecko 응답을 오코탐 시장지표 형식으로 변환한다."""
    ranked = sorted(
        [row for row in coins if isinstance(row.get("market_cap"), (int, float)) and row.get("market_cap_rank")],
        key=lambda row: int(row["market_cap_rank"]),
    )[:125]
    btc = next((row for row in ranked if row.get("id") == "bitcoin"), None)
    if len(ranked) < 10 or not btc:
        raise ValueError("CoinGecko 상위 시총 데이터가 부족합니다")

    # TradingView TOTAL 계열은 상위 125개만 합산한다. /global 전체 시총과
    # /coins/markets 개별 변화율을 섞으면 서로 다른 모집단 때문에 거짓 급락이 생긴다.
    total = sum(float(row["market_cap"]) for row in ranked)
    btc_cap = float(btc["market_cap"])
    total2 = max(total - btc_cap, 0)
    top10 = ranked[:10]
    others_rows = ranked[10:]
    others = sum(float(row["market_cap"]) for row in others_rows)
    previous_caps = {row.get("id"): _previous_cap(row) for row in ranked}
    previous_values = [previous_caps.get(row.get("id")) for row in ranked]
    previous_total = sum(previous_values) if all(value is not None for value in previous_values) else None
    previous_btc = previous_caps.get("bitcoin")
    previous_total2 = previous_total - previous_btc if previous_total is not None and previous_btc is not None else None
    previous_others_values = [previous_caps.get(row.get("id")) for row in others_rows]
    previous_others = sum(previous_others_values) if all(value is not None for value in previous_others_values) else None
    btc_d = btc_cap / total * 100
    previous_btc_d = previous_btc / previous_total * 100 if previous_btc and previous_total else None
    alt_changes = [
        float(row["price_change_percentage_24h"])
        for row in others_rows
        if isinstance(row.get("price_change_percentage_24h"), (int, float))
    ]

    return {
        "source": "coingecko_top125_proxy",
        "method_version": "top125-v2",
        "is_exact_tradingview": False,
        "definitions": {
            "btc_d": "BTC 시총 / CoinGecko 시총 상위 125개 합계",
            "total2": "CoinGecko 시총 상위 125개 합계 - BTC 시총",
            "others": "CoinGecko 시총 11~125위 합계",
        },
        "btc": {
            "market_cap_usd": btc_cap,
            "price_change_24h_pct": btc.get("price_change_percentage_24h"),
        },
        "btc_d": {"value": btc_d, "change_24h_pct_point": btc_d - previous_btc_d if previous_btc_d is not None else None},
        "total2": {"value_usd": total2, "change_24h_pct": _change(total2, previous_total2)},
        "others": {"value_usd": others, "change_24h_pct": _change(others, previous_others)},
        "top10": [row.get("symbol", "").upper() for row in top10],
        "tracked_coin_count": len(ranked),
        "breadth": {
            "sample_count": len(alt_changes),
            "positive_ratio_24h_pct": sum(value > 0 for value in alt_changes) / len(alt_changes) * 100 if alt_changes else None,
            "median_change_24h_pct": statistics.median(alt_changes) if alt_changes else None,
        },
    }


def _slot_key(now: datetime) -> str:
    now = now.astimezone(KST)
    boundary = now.replace(hour=1, minute=0, second=0, microsecond=0)
    if now < boundary:
        boundary -= timedelta(days=1)
    elapsed = int((now - boundary).total_seconds() // 14400)
    return (boundary + timedelta(hours=elapsed * 4)).isoformat(timespec="seconds")


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _add_snapshot(result: dict, now: datetime) -> dict:
    records = _read(HISTORY, [])
    current = {
        "slot": _slot_key(now),
        "method_version": result.get("method_version"),
        "btc_d": result["btc_d"]["value"],
        "total2": result["total2"]["value_usd"],
        "others": result["others"]["value_usd"],
    }
    by_slot = {row.get("slot"): row for row in records if row.get("slot")}
    by_slot[current["slot"]] = current
    records = sorted(by_slot.values(), key=lambda row: row["slot"])[-180:]
    current_at = datetime.fromisoformat(current["slot"])
    prior = [
        row for row in records
        if row.get("method_version") == current.get("method_version")
        and datetime.fromisoformat(row["slot"]) <= current_at - timedelta(hours=4)
    ]
    if prior:
        last = prior[-1]
        result["btc_d"]["change_4h_pct_point"] = current["btc_d"] - float(last["btc_d"])
        result["total2"]["change_4h_pct"] = _change(current["total2"], float(last["total2"]))
        result["others"]["change_4h_pct"] = _change(current["others"], float(last["others"]))
    else:
        result["btc_d"]["change_4h_pct_point"] = None
        result["total2"]["change_4h_pct"] = None
        result["others"]["change_4h_pct"] = None
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def collect(now: datetime | None = None) -> dict:
    now = now or datetime.now(KST)
    coins = _get(
        "/coins/markets",
        {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 125,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        },
    )
    result = calculate_proxy({}, coins if isinstance(coins, list) else [])
    result.update({"generated_at": now.isoformat(timespec="seconds"), "status": "ok"})
    return _add_snapshot(result, now)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = collect()
    except Exception as exc:  # 외부 데이터 장애가 전체 스캔을 멈추지 않게 안전 차단한다.
        previous = _read(OUTPUT, {})
        result = {
            **previous,
            "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
            "status": "stale" if previous else "error",
            "error": str(exc),
        }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"글로벌 시장 데이터 · {result.get('status')} · {OUTPUT}")


if __name__ == "__main__":
    main()
