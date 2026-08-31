#!/usr/bin/env python3
"""유형별 후보의 비교용 일봉·4시간봉 차트 데이터를 저장한다."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KST = timezone(timedelta(hours=9))
API = "https://api.upbit.com/v1"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
HEADERS = {"Accept": "application/json", "User-Agent": "upbit-mvp-lite-chart/1.0"}


def read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def abc_type(row: dict) -> str:
    tag = str(row.get("진입성향태그", ""))
    if "급등후첫눌림" in tag:
        return "A"
    if "박스하단" in tag or "박스중단" in tag:
        return "B"
    if "박스상단" in tag:
        return "C"
    return "OTHER"


def fetch(market: str, unit: str, count: int) -> list[list]:
    path = "/candles/days" if unit == "day" else "/candles/minutes/240"
    url = API + path + "?" + urlencode({"market": market, "count": count})
    with urlopen(Request(url, headers=HEADERS), timeout=30) as response:  # noqa: S310
        rows = json.loads(response.read().decode("utf-8"))
    duration = timedelta(days=1) if unit == "day" else timedelta(hours=4)
    now = datetime.now(KST)
    compact = []
    for row in reversed(rows):
        start = datetime.fromisoformat(row["candle_date_time_kst"]).replace(tzinfo=KST)
        if start + duration > now:
            continue
        compact.append([
            row["candle_date_time_kst"], float(row["opening_price"]), float(row["high_price"]),
            float(row["low_price"]), float(row["trade_price"]), float(row["candle_acc_trade_volume"]),
        ])
    time.sleep(0.13)
    return compact


def selected_markets(limit: int | None = None) -> list[str]:
    groups = {kind: [] for kind in "ABCDEF"}
    for row in read(OUT / "latest_scan.json", []):
        kind = abc_type(row)
        if kind in groups:
            action_rank = 0 if row.get("실전진입판정") == "진입조건충족" else 1 if row.get("실전진입판정") == "5분봉 확인대기" else 2
            groups[kind].append((action_rank, -float(row.get("점수") or 0), row.get("코드")))
    status_rank = {"진입확인": 0, "선매수감시": 1, "준비": 2, "늦음·추격금지": 3}
    for row in read(OUT / "pre_breakout_reclaim.json", []):
        if row.get("status") not in {"제외", "자료부족", "오류"}:
            groups["D"].append((status_rank.get(row.get("status"), 9), -float(row.get("score") or 0), row.get("market")))
    action_rank = {"진입 검토": 0, "확인 대기": 1, "진입가 대기": 2, "추격 금지": 3}
    for row in read(OUT / "technical_rebound.json", []):
        if row.get("status") != "E실패":
            groups["E"].append((action_rank.get(row.get("action"), 9), -float(row.get("score") or 0), row.get("market")))
    for row in read(OUT / "global_supply.json", []):
        groups["F"].append((action_rank.get(row.get("action"), 9), -float(row.get("score") or 0), row.get("market")))
    markets = []
    for kind in "ABCDEF":
        ranked=sorted(groups[kind])
        markets.extend(market for _, _, market in (ranked[:limit] if limit else ranked) if market)
    return list(dict.fromkeys(markets))


def main() -> None:
    cache = {}
    markets = selected_markets()

    def load(market):
        return market, {"day": fetch(market, "day", 60), "4h": fetch(market, "4h", 48)}

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(load, market): market for market in markets}
        for future in as_completed(futures):
            market = futures[future]
            try:
                name, charts = future.result()
                cache[name] = charts
            except Exception as exc:  # 네트워크 한 종목 실패가 전체 화면을 막지 않는다.
                cache[market] = {"day": [], "4h": [], "error": str(exc)}
    (OUT / "chart_cache.json").write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"chart cache: {len(cache)} markets")


if __name__ == "__main__":
    main()
