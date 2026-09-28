#!/usr/bin/env python3
"""Publish a long-range location map for every Upbit KRW market."""
from __future__ import annotations

import json
import math
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
API = "https://api.upbit.com/v1"
KST = timezone(timedelta(hours=9))
lock = threading.Lock()
last_request = 0.0


def get(path, params):
    global last_request
    url = API + path + "?" + urlencode(params)
    for attempt in range(5):
        try:
            with lock:
                delay = last_request + 0.17 - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                last_request = time.monotonic()
            with urlopen(Request(url, headers={"User-Agent": "okotam-rotation/1.0", "Accept": "application/json"}), timeout=16) as res:
                return json.load(res)
        except (HTTPError, URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt, 8))


def chart_rows(market):
    rows = get("/candles/days", {"market": market, "count": 200})
    if len(rows) == 200:
        older = get("/candles/days", {"market": market, "count": 200, "to": rows[-1]["candle_date_time_utc"] + "Z"})
        rows += older
    unique = {r["candle_date_time_kst"][:10]: r for r in rows}
    return [unique[k] for k in sorted(unique)]


def classify(rows):
    closes = [float(r["trade_price"]) for r in rows]
    if len(closes) < 30:
        return None
    # Trim isolated launch wicks by using closing prices and a robust upper bound.
    history = sorted(closes[:-14] if len(closes) > 45 else closes[:-1])
    low = history[max(0, int((len(history) - 1) * .02))]
    high = history[int((len(history) - 1) * .98)]
    current = closes[-1]
    if high <= low:
        return None
    location = (current - low) / (high - low) * 100
    breakout = (current / high - 1) * 100
    if location > 100:
        stage = "moon" if breakout >= 10 and current >= max(closes[-20:]) * .92 else "breakout"
    elif location < 33:
        stage = "low"
    elif location < 66:
        stage = "middle"
    else:
        stage = "high"
    # A small chart samples the entire period; detail retains each daily close.
    sampled = rows[::max(1, math.ceil(len(rows) / 100))]
    if sampled[-1] is not rows[-1]:
        sampled.append(rows[-1])
    return {"stage": stage, "location": round(location, 1), "above_high_pct": round(breakout, 1),
            "low": low, "high": high, "price": current, "low_date": rows[closes.index(min(closes))]["candle_date_time_kst"][:10],
            "high_date": rows[closes.index(max(closes))]["candle_date_time_kst"][:10],
            "days": len(rows), "spark": [round(float(r["trade_price"]), 8) for r in sampled],
            "daily": [[r["candle_date_time_kst"][:10], r["trade_price"]] for r in rows]}


def build_market(m):
    rows = chart_rows(m["market"])
    result = classify(rows)
    if result:
        result.update({"market": m["market"], "name": m["korean_name"], "symbol": m["market"].split("-", 1)[1]})
    return result


def collect():
    markets = [m for m in get("/market/all", {"is_details": "true"}) if m["market"].startswith("KRW-")]
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(build_market, m): m["market"] for m in markets}
        for future in as_completed(futures):
            try:
                item = future.result()
                if item:
                    results.append(item)
            except Exception as exc:
                failures.append(f"{futures[future]}: {type(exc).__name__}")
    if not results:
        raise RuntimeError("No long-range coin data; retaining the previous file")
    return {"updated_at": datetime.now(KST).isoformat(timespec="minutes"), "source": "Upbit KRW daily candles",
            "covered": len(results), "total": len(markets), "failed": failures,
            "coins": sorted(results, key=lambda x: (x["location"], x["symbol"]))}


def cached_preview():
    """Use stored daily histories only until the first full API scan succeeds."""
    results = []
    for path in (OUT / "daily").glob("KRW-*.json"):
        try:
            source = json.loads(path.read_text(encoding="utf-8"))
            rows = [{"candle_date_time_kst": str(r["date"]), "trade_price": r["close"]} for r in source["daily"]]
            item = classify(rows)
            if item:
                item.update({"market": source["code"], "name": source["name"], "symbol": source["code"].split("-")[1]})
                results.append(item)
        except (KeyError, ValueError, TypeError):
            continue
    if not results:
        return None
    names_file = OUT / "market_names.json"
    names = json.loads(names_file.read_text(encoding="utf-8")) if names_file.exists() else {}
    return {"updated_at": datetime.now(KST).isoformat(timespec="minutes"), "source": "stored Upbit daily candles (partial preview)",
            "covered": len(results), "total": max(len(names), len(results)), "failed": [], "partial": True,
            "coins": sorted(results, key=lambda x: (x["location"], x["symbol"]))}


def render():
    page = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>순환매 위치 | 오늘의 코인 탐험대</title><link rel="stylesheet" href="dashboard_v5.css"><link rel="stylesheet" href="rotation_position.css"></head><body><div class="dashboard"><header class="masthead"><a class="brand" href="index.html"><img src="assets/sukdol-stage.webp" alt="숙돌이"><div><h1>오늘의 코인 <span>탐험대</span></h1><p>시장을 탐험하고, 기회를 발견하세요.</p></div></a><div class="exchange-area"><div class="market-switch"><a class="exchange selected" href="rotation_position.html"><b>UPBIT</b><small>KRW</small></a><a class="exchange binance" href="binance/scan.html"><b>◆ BINANCE</b><small>SPOT USDT</small></a></div></div></header><nav class="nav"><a href="index.html">메인 대시보드</a><a href="scan.html">전체 스캔</a><a class="selected" href="rotation_position.html">순환매 위치</a><a href="type_a.html">A형</a><a href="type_b.html">B형</a><a href="type_c.html">C형</a><a href="type_d.html">D형</a><a href="type_e.html">E형</a><a href="type_f.html">F형</a><a href="type_g.html">G형</a><a href="type_p1.html">P형</a><a href="watchlist.html">관심종목</a></nav><main class="rotation"><header class="rotation-head"><h2>알트 순환매 위치</h2><p>장기 일봉에서 현재 가격이 어디에 있는지 확인해요.</p><small id="updated">데이터 불러오는 중</small></header><section id="overview" class="rotation-overview panel"></section><div class="rotation-tools"><label>정렬 <select id="sort"><option value="location">위치 낮은 순</option><option value="trade">거래대금 높은 순</option><option value="name">이름순</option></select></label><span id="coverage"></span></div><div id="groups"></div><section id="detail" class="detail" hidden><button id="close" type="button">← 목록으로</button><h2 id="detail-title"></h2><div id="detail-location"></div><svg id="big-chart" viewBox="0 0 720 350" role="img" aria-label="장기 일봉 종가 차트"></svg><div id="detail-bounds"></div></section><p class="rotation-note">위치는 최근 최대 400개 일봉의 종가 범위로 계산합니다. 짧은 상장 이력은 해당 기간만 사용하며, 위치는 매수 신호가 아닙니다.</p></main></div><script src="rotation_position.js"></script></body></html>'''
    (OUT / "rotation_position.html").write_text(page, encoding="utf-8")
    for name in ("rotation_position.css", "rotation_position.js"):
        shutil.copy2(ROOT / "scanner" / name, OUT / name)


def inject_nav():
    # Generated pages are recreated by every scheduled scan, so patch after all renderers.
    for p in [OUT / "index.html", OUT / "scan.html", *OUT.glob("type_*.html")]:
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        if "rotation_position.html" in s:
            continue
        if p.name == "index.html":
            s = s.replace('<a href="scan.html">전체 스캔</a>', '<a href="scan.html">전체 스캔</a><a href="rotation_position.html">순환매 위치</a>', 1)
        else:
            # The candidate pages use a menu titled "오늘의 전체 스캔".
            m = re.search(r'(<details class="nav-drop">.*?</details>)', s, flags=re.S)
            if m:
                s = s[:m.end()] + '<a href="rotation_position.html">순환매 위치</a>' + s[m.end():]
        p.write_text(s, encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    render()
    inject_nav()
    try:
        result = collect()
        (OUT / "rotation_position.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"rotation position: {result['covered']}/{result['total']} coins")
    except Exception as exc:
        target = OUT / "rotation_position.json"
        if not target.exists():
            preview = cached_preview()
            if preview:
                target.write_text(json.dumps(preview, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"rotation data refresh failed; previous data retained: {exc}")


if __name__ == "__main__":
    main()
