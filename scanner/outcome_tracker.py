#!/usr/bin/env python3
"""후보 발생 뒤 24시간·72시간의 진입/목표/손절 결과를 갱신한다."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "history" / "snapshots.json"
API = "https://api.upbit.com/v1/candles/minutes/240"
HEADERS = {"Accept": "application/json", "User-Agent": "upbit-outcome-validator/2.0"}


def read() -> list[dict]:
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else []


def fetch(market: str, count: int = 200) -> list[dict]:
    """최근 4시간봉을 받아 모든 미완료 24H/72H 구간에 재사용한다."""
    url = API + "?" + urlencode({"market": market, "count": count})
    with urlopen(Request(url, headers=HEADERS), timeout=25) as response:  # noqa: S310
        rows = json.loads(response.read().decode("utf-8"))
    time.sleep(0.13)
    return sorted(
        [{
            "at": datetime.fromisoformat(row["candle_date_time_kst"]).replace(tzinfo=KST),
            "high": float(row["high_price"]), "low": float(row["low_price"]),
        } for row in rows], key=lambda item: item["at"],
    )


def evaluate(row: dict, candles: list[dict], start: datetime, end: datetime) -> dict:
    entry = [value for value in row.get("entry", []) if isinstance(value, (int, float))]
    stop = row.get("stop")
    targets = [value for value in row.get("targets", []) if isinstance(value, (int, float))]
    empty = {"mfe_pct": None, "mae_pct": None, "entry_at": None, "resolved_at": None}
    if not entry or not isinstance(stop, (int, float)):
        return {"status": "자료 부족", **empty}
    fill = max(entry)
    target = targets[0] if targets else None
    if stop >= fill or not isinstance(target, (int, float)) or target <= fill:
        return {"status": "계획값 오류", **empty}
    seen = [candle for candle in candles if start <= candle["at"] < end]
    touched = False
    highs: list[float] = []
    lows: list[float] = []
    entry_at = None
    for candle in seen:
        if not touched and candle["low"] <= fill <= candle["high"]:
            touched = True
            entry_at = candle["at"].isoformat()
        if not touched:
            continue
        highs.append(candle["high"]); lows.append(candle["low"])
        # 같은 4시간봉에서 목표·손절이 함께 닿으면 보수적으로 손절을 먼저 처리한다.
        if candle["low"] <= stop:
            return {"status": "손절 도달", "mfe_pct": round((max(highs)/fill-1)*100, 2),
                    "mae_pct": round((min(lows)/fill-1)*100, 2), "entry_at": entry_at,
                    "resolved_at": candle["at"].isoformat()}
        if isinstance(target, (int, float)) and candle["high"] >= target:
            return {"status": "1차 목표 성공", "mfe_pct": round((max(highs)/fill-1)*100, 2),
                    "mae_pct": round((min(lows)/fill-1)*100, 2), "entry_at": entry_at,
                    "resolved_at": candle["at"].isoformat()}
    if not touched:
        return {"status": "진입 미도달", **empty}
    return {"status": "진입 후 진행", "mfe_pct": round((max(highs)/fill-1)*100, 2),
            "mae_pct": round((min(lows)/fill-1)*100, 2), "entry_at": entry_at, "resolved_at": None}


def update(now: datetime | None = None, refresh: bool = False) -> int:
    now = (now or datetime.now(KST)).astimezone(KST)
    records = read(); jobs = []; markets = set()
    for record in records:
        start = datetime.fromisoformat(record["snapshot_at"]).astimezone(KST)
        for horizon in (24, 72):
            end = start + timedelta(hours=horizon)
            if now < end:
                continue
            for row in record.get("candidates", []):
                previous = row.get("outcomes", {}).get(f"{horizon}h")
                # v1 결과에는 entry_at이 없어 후보 이전 봉이 섞였을 수 있다. 최초 1회 자동 교정한다.
                if refresh or previous is None or "entry_at" not in previous:
                    jobs.append((row, horizon, start, end))
                    if row.get("market"): markets.add(row["market"])
    caches = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch, market): market for market in sorted(markets)}
        for future in as_completed(futures):
            market = futures[future]
            try: caches[market] = future.result()
            except Exception as exc:
                caches[market] = []; print(f"outcome fetch failed {market}: {exc}")
    changed = 0
    for row, horizon, start, end in jobs:
        candles = caches.get(row.get("market"), [])
        if not candles: continue
        row.setdefault("outcomes", {})[f"{horizon}h"] = evaluate(row, candles, start, end)
        changed += 1
    if changed:
        STORE.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"outcomes: {changed} updated · {len(markets)} markets")
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="기존 결과도 정확한 시간창으로 다시 계산")
    update(refresh=parser.parse_args().refresh)
