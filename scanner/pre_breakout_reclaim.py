#!/usr/bin/env python3
"""UPBIT KRW 급등 전 매물대 재탈환·압축형 스캐너."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.upbit.com/v1"
KST = timezone(timedelta(hours=9))
HEADERS = {"Accept": "application/json", "User-Agent": "pre-breakout-reclaim/1.0"}


def api_get(path: str, params: dict | None = None):
    url = API + path
    if params:
        url += "?" + urlencode(params)
    with urlopen(Request(url, headers=HEADERS), timeout=30) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    time.sleep(0.13)
    return payload


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def candles(market: str, kind: str, count: int, asof: datetime | None = None) -> list[dict]:
    path = "/candles/days" if kind == "day" else f"/candles/minutes/{kind}"
    params = {"market": market, "count": min(count, 200)}
    if asof:
        params["to"] = asof.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = api_get(path, params)
    rows.reverse()
    duration = timedelta(days=1) if kind == "day" else timedelta(minutes=int(kind))
    cutoff = asof or datetime.now(KST)
    normalized = [
        {
            "time": row["candle_date_time_kst"],
            "open": float(row["opening_price"]),
            "high": float(row["high_price"]),
            "low": float(row["low_price"]),
            "close": float(row["trade_price"]),
            "volume": float(row["candle_acc_trade_volume"]),
        }
        for row in rows
    ]
    # Upbit includes the candle that is still forming. Candidate and entry
    # decisions must use only candles whose full interval has ended.
    return [
        row
        for row in normalized
        if datetime.fromisoformat(row["time"]).replace(tzinfo=KST) + duration <= cutoff
    ]


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0 if b else 0.0


def cluster_levels(history: list[dict], floor: float, ceiling: float) -> list[tuple[float, int]]:
    """OHLC 반복 가격을 약 2.5% 폭으로 묶어 상단 매물대 경계를 근사한다."""
    if floor <= 0:
        return []
    step = math.log(1.025)
    bins: dict[int, list[float]] = {}
    for row in history:
        for key in ("open", "high", "low", "close"):
            value = row[key]
            if floor <= value <= ceiling:
                idx = round(math.log(value / floor) / step)
                bins.setdefault(idx, []).append(value)
    levels = [(median(vals), len(vals)) for vals in bins.values() if len(vals) >= 4]
    return sorted(levels, key=lambda item: item[0])


def derive_levels(days: list[dict], base_high: float, signal_close: float) -> tuple[float, float, str]:
    historical = days[:-23] if len(days) > 45 else days[:-10]
    ceiling = max((row["high"] for row in historical), default=base_high * 1.6)
    candidates = cluster_levels(historical, base_high * 1.03, ceiling)
    if not candidates:
        return base_high * 1.10, base_high * 1.20, "fallback"
    reclaimed = [item for item in candidates if item[0] <= signal_close * 0.95]
    lower = reclaimed[-1][0] if reclaimed else candidates[0][0]
    overhead = [item for item in candidates if item[0] >= signal_close * 1.003]
    upper = overhead[0][0] if overhead else max(signal_close * 1.04, lower * 1.08)
    return lower, upper, "auto"


def analyze(
    market: str,
    days: list[dict],
    hours4: list[dict],
    lower_override: float | None = None,
    upper_override: float | None = None,
    target3_override: float | None = None,
) -> dict:
    if len(days) < 55 or len(hours4) < 12:
        return {"market": market, "status": "자료부족", "score": 0}

    impulse = days[-3:]
    base = days[-23:-3]
    earlier = days[-63:-23]
    base_low = min(row["low"] for row in base)
    base_high = max(row["high"] for row in base)
    base_mid = (base_low + base_high) / 2.0
    base_width = pct(base_high, base_low)
    prior_high = max(row["high"] for row in earlier)
    decline = max(0.0, pct(prior_high, base_mid))
    volume_multiple = max(row["volume"] for row in impulse) / max(median([row["volume"] for row in base]), 1e-9)

    lower, upper, level_source = derive_levels(days, base_high, days[-1]["close"])
    if lower_override is not None:
        lower, level_source = lower_override, "manual"
    if upper_override is not None:
        upper, level_source = upper_override, "manual"
    if upper <= lower:
        upper = lower * 1.08

    last_day = days[-1]
    recent4 = hours4[-4:]
    last4 = hours4[-1]
    retest_low = min(row["low"] for row in recent4[-2:])
    compression_width = pct(max(row["high"] for row in recent4), min(row["low"] for row in recent4))
    higher_lows = recent4[-1]["low"] >= recent4[-2]["low"] or recent4[-1]["close"] > recent4[-2]["close"]

    checks = {
        "장기하락": decline >= 15.0,
        "베이스압축": 14 <= len(base) <= 30 and base_width <= 20.0,
        "거래량시동": volume_multiple >= 3.0,
        "하단선재탈환": last_day["close"] >= lower * 0.98,
        "4H리테스트": retest_low <= lower * 1.03 and last4["close"] >= lower,
        "4H재압축": compression_width <= 18.0 and higher_lows,
        "상단선접근": last4["close"] >= upper * 0.92 or max(row["high"] for row in recent4) >= upper,
    }
    score = sum(checks.values())
    current = last4["close"]
    distance_above_upper = pct(current, upper)
    body_invalidation = lower
    hard_stop = min(lower * 0.985, retest_low * 0.985)
    target1 = upper
    target2 = max(upper * 1.045, max(row["high"] for row in impulse))
    target3 = target3_override or max(target2 * 1.25, prior_high)
    targets = sorted({round(target1, 8), round(target2, 8), round(target3, 8)})
    max_entry_for_one_r = (target1 + hard_stop) / 2.0
    aggressive_available = max_entry_for_one_r >= lower
    entry_high = max(lower, min(upper, lower * 1.04, max_entry_for_one_r))
    entry_low = max(lower, retest_low) if retest_low <= entry_high else lower
    planned_entry = (entry_low + entry_high) / 2.0
    risk = planned_entry - hard_stop
    first_rr = (target1 - planned_entry) / risk if risk > 0 else 0.0

    if distance_above_upper >= 8.0:
        status = "늦음·추격금지"
    elif score >= 7 and first_rr >= 1.0:
        status = "진입확인"
    elif score >= 5:
        status = "선매수감시"
    elif score >= 3:
        status = "준비"
    else:
        status = "제외"

    return {
        "market": market,
        "status": status,
        "score": score,
        "checks": checks,
        "level_source": level_source,
        "lower_reclaim_level": round(lower, 8),
        "upper_break_level": round(upper, 8),
        "base_days": len(base),
        "base_low": base_low,
        "base_high": base_high,
        "base_width_pct": round(base_width, 2),
        "prior_decline_pct": round(decline, 2),
        "impulse_volume_multiple": round(volume_multiple, 2),
        "four_hour_retest_low": retest_low,
        "four_hour_compression_pct": round(compression_width, 2),
        "last_completed_4h_close": current,
        "aggressive_entry_zone": [round(entry_low, 8), round(entry_high, 8)] if aggressive_available else [],
        "confirmation_entry_zone": [round(upper, 8), round(upper * 1.015, 8)],
        "confirmation_rule": "상단선 돌파 종가 확인 후 상단선 리테스트 방어 시에만 사용",
        "body_invalidation": round(body_invalidation, 8),
        "hard_stop": round(hard_stop, 8),
        "targets": targets,
        "first_target_rr": round(first_rr, 2),
        "missing_conditions": [name for name, passed in checks.items() if not passed],
        "candle_start_time": last4["time"],
        "candle_end_time": (datetime.fromisoformat(last4["time"]).replace(tzinfo=KST) + timedelta(hours=4)).isoformat(),
    }


def universe(min_trade_amount: float) -> list[str]:
    markets = [row["market"] for row in api_get("/market/all") if row["market"].startswith("KRW-")]
    selected = []
    for start in range(0, len(markets), 100):
        tickers = api_get("/ticker", {"markets": ",".join(markets[start:start + 100])})
        selected.extend(row["market"] for row in tickers if float(row.get("acc_trade_price_24h", 0)) >= min_trade_amount)
    return selected


def save_results(results: list[dict], json_path: str | None, csv_path: str | None) -> None:
    if json_path:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    if csv_path:
        path = Path(csv_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = ["market", "status", "score", "lower_reclaim_level", "upper_break_level", "aggressive_entry_zone", "confirmation_entry_zone", "hard_stop", "targets", "first_target_rr", "candle_end_time"]
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", default="KRW-TRUMP")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--asof")
    parser.add_argument("--lower-level", type=float)
    parser.add_argument("--upper-level", type=float)
    parser.add_argument("--target3-level", type=float)
    parser.add_argument("--min-trade-amount", type=float, default=3_000_000_000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output-json")
    parser.add_argument("--output-csv")
    args = parser.parse_args()
    asof = parse_time(args.asof)
    markets = universe(args.min_trade_amount) if args.all else [args.market]
    def scan_one(market: str) -> dict:
        try:
            return analyze(
                market,
                candles(market, "day", 120, asof),
                candles(market, "240", 100, asof),
                args.lower_level if len(markets) == 1 else None,
                args.upper_level if len(markets) == 1 else None,
                args.target3_level if len(markets) == 1 else None,
            )
        except Exception as exc:  # noqa: BLE001
            return {"market": market, "status": "오류", "score": 0, "error": str(exc)}

    results = []
    if args.all and args.workers > 1:
        with ThreadPoolExecutor(max_workers=min(args.workers, 8)) as executor:
            futures = {executor.submit(scan_one, market): market for market in markets}
            for index, future in enumerate(as_completed(futures), 1):
                result = future.result()
                results.append(result)
                print(f"{index}/{len(markets)} {result['market']} {result['status']} {result['score']}")
    else:
        for index, market in enumerate(markets, 1):
            result = scan_one(market)
            results.append(result)
            if args.all:
                print(f"{index}/{len(markets)} {market} {result['status']} {result['score']}")
    order = {"진입확인": 0, "선매수감시": 1, "준비": 2, "늦음·추격금지": 3, "제외": 4, "자료부족": 5, "오류": 6}
    results.sort(key=lambda row: (order.get(row["status"], 9), -row.get("score", 0)))
    save_results(results, args.output_json, args.output_csv)
    print(json.dumps(results if args.all else results[0], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
