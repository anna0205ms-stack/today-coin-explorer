#!/usr/bin/env python3
"""UPBIT KRW F형: 신규 상장 신고가와 글로벌 과거 매물대 비교 스캐너."""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUTPUT_JSON = OUT / "global_supply.json"
OUTPUT_CSV = OUT / "global_supply.csv"
KST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "oko-tam-f-scanner/1.0"}


def get_json(url: str):
    with urlopen(Request(url, headers=HEADERS), timeout=25) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def completed_upbit_days(rows: list[dict], now: datetime | None = None) -> list[dict]:
    now = (now or datetime.now(KST)).astimezone(KST)
    completed = []
    for row in reversed(rows):
        start = datetime.fromisoformat(row["candle_date_time_kst"]).replace(tzinfo=KST)
        if start + timedelta(days=1) <= now:
            completed.append(row)
    return completed


def completed_binance_days(rows: list[list], now_ms: int | None = None) -> list[list]:
    now_ms = now_ms or int(time.time() * 1000)
    return [row for row in rows if int(row[6]) < now_ms]


def quantile(values: list[float], q: float) -> float:
    values = sorted(values)
    if not values:
        return math.nan
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def upbit_new_high_trend(days: list[dict]) -> dict | None:
    """업비트 상장 이력 안에서 신고가 추세가 실제로 시작됐는지 판별한다."""
    if len(days) < 12:
        return None
    closes = [float(row["trade_price"]) for row in days]
    highs = [float(row["high_price"]) for row in days]
    lows = [float(row["low_price"]) for row in days]
    price = closes[-1]
    prior_high = max(highs[:-1])
    lookback = min(30, len(closes) - 1)
    base = min(lows[-lookback - 1:-1])
    rise = price / base - 1 if base else 0
    near_high = price / max(highs) if max(highs) else 0
    recent_gain = price / closes[max(0, len(closes) - 8)] - 1
    # 신고가를 찍은 직후 첫 조정도 놓치지 않도록 고점 대비 25% 이내까지 포함한다.
    if rise < 0.35 or near_high < 0.75 or recent_gain < 0.10:
        return None
    return {
        "price": price,
        "upbit_days": len(days),
        "upbit_prior_high": prior_high,
        "upbit_rise_pct": round(rise * 100, 1),
        "upbit_near_high_pct": round(near_high * 100, 1),
        "upbit_recent_gain_pct": round(recent_gain * 100, 1),
    }


def historical_supply_zone(rows: list[list], current: float) -> dict | None:
    """최근 상승 이전의 20~60일 횡보 중 현재가와 가장 가까운 공급대를 찾는다."""
    history = rows[:-45] if len(rows) > 90 else []
    if len(history) < 60 or current <= 0:
        return None
    candidates = []
    for length in (20, 30, 45, 60):
        for start in range(0, len(history) - length + 1, 5):
            window = history[start:start + length]
            lows = [float(row[3]) for row in window]
            highs = [float(row[2]) for row in window]
            closes = [float(row[4]) for row in window]
            lower = quantile(lows, 0.20)
            upper = quantile(highs, 0.80)
            width = upper / lower - 1 if lower else 99
            if not 0.08 <= width <= 0.38:
                continue
            inside = sum(lower <= close <= upper for close in closes) / len(closes)
            if inside < 0.65:
                continue
            distance = 0 if lower <= current <= upper else lower / current - 1 if current < lower else current / upper - 1
            if distance > 0.22:
                continue
            end_ms = int(window[-1][6])
            score = inside * 4 + min(length, 45) / 20 - width - distance * 3
            candidates.append((score, -distance, end_ms, lower, upper, length, inside, window[0][0], window[-1][6]))
    if not candidates:
        return None
    _, _, _, lower, upper, length, inside, start_ms, end_ms = max(candidates)
    return {
        "lower": round(lower, 8), "upper": round(upper, 8), "days": length,
        "inside_ratio": round(inside, 2),
        "start": datetime.fromtimestamp(int(start_ms) / 1000, timezone.utc).date().isoformat(),
        "end": datetime.fromtimestamp(int(end_ms) / 1000, timezone.utc).date().isoformat(),
    }


def classify_stage(current: float, zone: dict, recent: list[list]) -> tuple[str, str, list[str]]:
    lower, upper = zone["lower"], zone["upper"]
    closes = [float(row[4]) for row in recent[-3:]]
    lows = [float(row[3]) for row in recent[-3:]]
    if current > upper * 1.02 and (sum(close > upper for close in closes) >= 2 or min(lows) <= upper * 1.03):
        return "F3", "매물대 돌파", ["상단 돌파 후 재지지 확인"]
    if current >= lower * 0.97:
        return "F2", "매물대 도착", ["글로벌 매물 소화", "높은 저점 또는 상단 돌파 확인"]
    return "F1", "신고가 상승", ["글로벌 매물대 하단 도착 대기"]


def trade_plan(stage: str, upbit_price: float, binance_price: float, zone: dict) -> dict:
    ratio = upbit_price / binance_price
    lower_krw, upper_krw = zone["lower"] * ratio, zone["upper"] * ratio
    if stage == "F3":
        entry = [upper_krw * 0.99, upper_krw * 1.02]
        stop = upper_krw * 0.955
        target = upper_krw + (upper_krw - lower_krw) * 0.70
        action = "진입 검토"
    elif stage == "F2":
        entry = [lower_krw * 0.98, lower_krw * 1.03]
        stop = lower_krw * 0.95
        target = upper_krw
        action = "확인 대기"
    else:
        entry = [lower_krw * 0.98, lower_krw * 1.02]
        stop = lower_krw * 0.95
        target = upper_krw
        action = "진입가 대기"
    entry = [round(value, 4) for value in entry]
    stop, target = round(stop, 4), round(target, 4)
    midpoint = sum(entry) / 2
    rr = (target - midpoint) / (midpoint - stop) if midpoint > stop else None
    return {"entry": entry, "stop": stop, "targets": [target], "rr": round(rr, 2) if rr else None, "action": action}


def analyze(market: str, upbit_rows: list[dict], binance_rows: list[list]) -> dict | None:
    days = completed_upbit_days(upbit_rows)
    trend = upbit_new_high_trend(days)
    binance_days = completed_binance_days(binance_rows)
    if not trend or len(binance_days) < 120:
        return None
    binance_price = float(binance_days[-1][4])
    zone = historical_supply_zone(binance_days, binance_price)
    if not zone:
        return None
    stage, label, missing = classify_stage(binance_price, zone, binance_days)
    plan = trade_plan(stage, trend["price"], binance_price, zone)
    score = min(10, 5 + trend["upbit_rise_pct"] / 50 + zone["inside_ratio"] * 2 + zone["days"] / 60)
    return {
        "market": market, "name": market.replace("KRW-", ""), "binance_symbol": market.replace("KRW-", "") + "USDT",
        "status": label, "f_stage": stage, "f_stage_label": label,
        "price": trend["price"], "binance_price": binance_price,
        "score": round(score, 1), **plan, **trend,
        "global_zone": zone, "missing": missing,
        "reason": f'업비트 신고가 흐름 + 바이낸스 {zone["start"]}~{zone["end"]} 과거 횡보 매물대',
        "flow": f'{stage} · {label}',
        "basis": datetime.now(KST).isoformat(timespec="minutes"),
    }


def fetch_market(market: str) -> dict | None:
    ticker = market.replace("KRW-", "")
    upbit = get_json("https://api.upbit.com/v1/candles/days?" + urlencode({"market": market, "count": 200}))
    trend = upbit_new_high_trend(completed_upbit_days(upbit))
    if not trend:
        return None
    binance = get_json("https://api.binance.com/api/v3/klines?" + urlencode({"symbol": ticker + "USDT", "interval": "1d", "limit": 1000}))
    return analyze(market, upbit, binance)


def scan_all(workers: int = 6) -> list[dict]:
    markets = [row["market"] for row in get_json("https://api.upbit.com/v1/market/all?is_details=false") if row["market"].startswith("KRW-")]
    symbols = {row["symbol"] for row in get_json("https://api.binance.com/api/v3/exchangeInfo")["symbols"] if row.get("status") == "TRADING" and row.get("quoteAsset") == "USDT"}
    markets = [market for market in markets if market.replace("KRW-", "") + "USDT" in symbols]
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_market, market): market for market in markets}
        for future in as_completed(futures):
            try:
                row = future.result()
                if row:
                    results.append(row)
            except Exception:
                continue
    return sorted(results, key=lambda row: (row["f_stage"], -row["score"]))


def write_outputs(rows: list[dict], json_path: Path = OUTPUT_JSON, csv_path: Path = OUTPUT_CSV) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["market", "f_stage", "f_stage_label", "action", "score", "price", "entry", "stop", "targets", "rr", "reason"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.market:
        row = fetch_market(args.market)
        rows = [row] if row else []
    else:
        rows = scan_all(args.workers)
    write_outputs(rows)
    print(f"F형 글로벌 매물대: {len(rows)}개 · {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
