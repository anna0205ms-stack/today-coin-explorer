#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BINANCE Spot USDT A/B/C/D/E/G scanner.

UPBIT scanner와 데이터 수집/유니버스/API/호가단위를 완전히 분리한다.
공개 Binance Spot market-data만 읽으며 주문은 실행하지 않는다.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "outputs" / "binance"
HISTORY_DIR = ROOT / "history" / "binance"
LATEST = OUT / "latest.json"
SNAPSHOTS = HISTORY_DIR / "snapshots.json"

API = os.getenv("BINANCE_SPOT_API", "https://data-api.binance.vision/api/v3")
MIN_QUOTE_VOLUME = float(os.getenv("BINANCE_MIN_24H_QUOTE_VOLUME", "2000000"))
_configured_symbol_limit = int(os.getenv("BINANCE_MAX_SYMBOLS", "0"))
MAX_SYMBOLS = _configured_symbol_limit if _configured_symbol_limit > 0 else None
REQUEST_INTERVAL = float(os.getenv("BINANCE_API_INTERVAL", "0.035"))
KST = timezone(timedelta(hours=9))
HEADERS = {"Accept": "application/json", "User-Agent": "okotan-binance-spot/1.0"}

STABLE_BASES = {
    "USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "AEUR", "EURI", "TRY", "BRL", "GBP",
    "JPY", "RUB", "UAH", "BIDR", "IDRT", "BVND", "NGN", "ZAR", "PLN", "RON", "ARS",
    "USDT", "USDS", "USD1", "USDG", "USDE", "USDD", "PYUSD", "RLUSD",
    "EURC", "EURCV", "GUSD", "FRAX", "LUSD", "UST", "USTC",
}
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")

GATE_RULES = {
    "M0": {"A": "BLOCK", "B": "BLOCK", "C": "BLOCK", "D": "BLOCK", "E": "CONDITIONAL", "G": "WATCH"},
    "M1": {"A": "CONDITIONAL", "B": "BLOCK", "C": "CONDITIONAL", "D": "WATCH", "E": "CONDITIONAL", "G": "WATCH"},
    "M2": {"A": "CONDITIONAL", "B": "CONDITIONAL", "C": "CONDITIONAL", "D": "WATCH", "E": "CONDITIONAL", "G": "WATCH"},
    "M3": {"A": "ALLOW", "B": "CONDITIONAL", "C": "ALLOW", "D": "ALLOW", "E": "WATCH", "G": "ALLOW"},
    "M4": {"A": "ALLOW", "B": "CONDITIONAL", "C": "ALLOW", "D": "ALLOW", "E": "WATCH", "G": "ALLOW"},
    "M5": {"A": "PROTECT", "B": "BLOCK", "C": "PROTECT", "D": "BLOCK", "E": "CONDITIONAL", "G": "WATCH"},
}
for _stage, _code in {"M0": "BLOCK", "M1": "WATCH", "M2": "CONDITIONAL", "M3": "ALLOW", "M4": "ALLOW", "M5": "PROTECT"}.items():
    GATE_RULES[_stage]["H"] = _code
    GATE_RULES[_stage]["F"] = _code
GATE_LABELS = {"ALLOW": "진입 허용", "CONDITIONAL": "조건부", "WATCH": "관찰", "BLOCK": "신규 금지", "PROTECT": "익절 우선"}
STAGE_INFO = {
    "M0": ("위험장", 0), "M1": ("BTC만 강함", 20), "M2": ("알트 준비", 35),
    "M3": ("알트 시작", 65), "M4": ("알트 확산", 85), "M5": ("과열 경계", 15),
}


class ScanError(RuntimeError):
    pass


def api_get(path: str, params: dict | None = None, attempts: int = 5):
    url = API + path
    if params:
        url += "?" + urlencode(params)
    last = None
    for attempt in range(1, attempts + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            time.sleep(REQUEST_INTERVAL)
            return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(min(2 ** attempt, 10))
    raise ScanError(f"Binance API 실패: {path} / {last}")


def pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0 if b else 0.0


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    w = pos - lo
    return ordered[lo] * (1 - w) + ordered[hi] * w


def reward_risk(entry: float, stop: float, target: float) -> float:
    risk = entry - stop
    reward = target - entry
    return reward / risk if risk > 0 and reward > 0 else 0.0


def decimals_from_tick(tick: float) -> int:
    if tick <= 0:
        return 8
    text = f"{tick:.12f}".rstrip("0")
    return len(text.split(".", 1)[1]) if "." in text else 0


def round_tick(value: float, tick: float, mode: str = "nearest") -> float:
    if tick <= 0:
        return round(value, 8)
    units = value / tick
    if mode == "down":
        units = math.floor(units + 1e-10)
    elif mode == "up":
        units = math.ceil(units - 1e-10)
    else:
        units = round(units)
    return round(units * tick, decimals_from_tick(tick))


def fetch_universe(min_quote_volume: float | None = MIN_QUOTE_VOLUME, limit: int | None = MAX_SYMBOLS) -> list[dict]:
    info = api_get("/exchangeInfo")
    tickers = api_get("/ticker/24hr")
    ticker_map = {str(x.get("symbol")): x for x in tickers if isinstance(x, dict)}
    rows = []
    for item in info.get("symbols", []):
        symbol = str(item.get("symbol", ""))
        base = str(item.get("baseAsset", ""))
        quote = str(item.get("quoteAsset", ""))
        if quote != "USDT" or item.get("status") != "TRADING":
            continue
        if item.get("isSpotTradingAllowed") is False:
            continue
        if base in STABLE_BASES or base.endswith(LEVERAGED_SUFFIXES):
            continue
        ticker = ticker_map.get(symbol)
        if not ticker:
            continue
        quote_volume = float(ticker.get("quoteVolume") or 0)
        last_price = float(ticker.get("lastPrice") or 0)
        change = float(ticker.get("priceChangePercent") or 0)
        if last_price <= 0:
            continue
        if min_quote_volume is not None and quote_volume < float(min_quote_volume):
            continue
        filters = {f.get("filterType"): f for f in item.get("filters", []) if isinstance(f, dict)}
        tick = float((filters.get("PRICE_FILTER") or {}).get("tickSize") or 0.00000001)
        rows.append({
            "symbol": symbol, "base": base, "quote": quote, "price": last_price,
            "quote_volume": quote_volume, "change_24h_pct": change, "tick": tick,
        })
    rows.sort(key=lambda x: x["quote_volume"], reverse=True)
    return rows if limit is None else rows[:limit]


def fetch_klines(symbol: str, interval: str, limit: int) -> list[dict]:
    raw = api_get("/klines", {"symbol": symbol, "interval": interval, "limit": min(limit + 2, 1000)})
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    out = []
    for row in raw:
        if int(row[6]) >= now_ms:
            continue
        out.append({
            "open_time": int(row[0]), "close_time": int(row[6]),
            "open": float(row[1]), "high": float(row[2]), "low": float(row[3]), "close": float(row[4]),
            "volume": float(row[5]), "quote_volume": float(row[7]),
        })
    return out[-limit:]


def four_hour_confirm(rows: list[dict], level: float | None = None) -> tuple[bool, str]:
    if len(rows) < 4:
        return False, "4H 자료 부족"
    last, prev = rows[-1], rows[-2]
    bullish = last["close"] > last["open"] and last["close"] >= prev["close"]
    higher_low = last["low"] >= min(x["low"] for x in rows[-4:-1]) * 0.995
    reclaim = True if level is None else last["close"] >= level
    ok = bullish and higher_low and reclaim
    bits = []
    if bullish: bits.append("4H 양봉 전환")
    if higher_low: bits.append("저점 방어")
    if level is not None and reclaim: bits.append("기준선 종가 방어")
    return ok, " · ".join(bits) if bits else "4H 확인 전"


def candidate(symbol: str, typ: str, stage: str, score: float, action: str, price: float,
              entry_low: float, entry_high: float, stop: float, target: float, tick: float,
              reason: str, spark: list[float], extra: dict | None = None) -> dict | None:
    if entry_high <= entry_low or stop >= entry_low or target <= entry_high:
        return None
    planned = (entry_low + entry_high) / 2
    rr = reward_risk(planned, stop, target)
    if rr < 0.8:
        return None
    return {
        "market": symbol, "type": typ, "stage": stage, "score": round(min(10.0, score), 1),
        "pattern_action": action, "action": action, "price": round_tick(price, tick),
        "entry": [round_tick(entry_low, tick, "up"), round_tick(entry_high, tick, "down")],
        "stop": round_tick(stop, tick, "down"), "targets": [round_tick(target, tick, "down")],
        "rr": round(rr, 2), "reason": reason, "spark": [round(x, 10) for x in spark[-30:]],
        "extra": extra or {},
    }


def scan_a(row: dict, d: list[dict], h4: list[dict]) -> dict | None:
    if len(d) < 55 or len(h4) < 8:
        return None
    view = d[-18:]
    med_vol = max(median([x["volume"] for x in d[-45:-18]]), 1e-9)
    impulses = []
    for i, x in enumerate(view[:-2]):
        gain = pct(x["close"], x["open"])
        vr = x["volume"] / med_vol
        impulses.append((gain + max(0, vr - 1) * 2, i, gain, vr))
    _, idx, gain, vr = max(impulses)
    if gain < 7.5 or vr < 1.35:
        return None
    impulse_abs = len(d) - len(view) + idx
    before = d[max(0, impulse_abs - 12):impulse_abs]
    after = d[impulse_abs:]
    if len(before) < 6:
        return None
    support = max(x["high"] for x in before)
    high = max(x["high"] for x in after)
    current = d[-1]["close"]
    pullback = (1 - current / high) * 100 if high else 0
    if not (2.5 <= pullback <= 18.0) or current < support * 0.97:
        return None
    ok4, reason4 = four_hour_confirm(h4, support)
    entry_low = max(support, current * 0.985)
    entry_high = min(current * 1.01, high * 0.985)
    stop = min(support * 0.965, min(x["low"] for x in h4[-6:]) * 0.985)
    target = high
    stage = "A2→A3" if ok4 else "A2"
    action = "진입 검토" if ok4 else "확인 대기"
    score = 5.2 + min(1.6, gain / 10) + min(1.4, vr / 2) + (1.3 if ok4 else 0) + (0.5 if pullback <= 10 else 0)
    return candidate(row["symbol"], "A", stage, score, action, current, entry_low, entry_high, stop, target,
                     row["tick"], f"강한 일봉 +{gain:.1f}% · 거래량 {vr:.1f}배 · 눌림 {pullback:.1f}% · {reason4}",
                     [x["close"] for x in h4])


def scan_b(row: dict, d: list[dict], h4: list[dict]) -> dict | None:
    if len(d) < 90 or len(h4) < 8:
        return None
    prior_high = max(x["high"] for x in d[-90:-12])
    recent = d[-12:]
    low = min(x["low"] for x in recent)
    current = d[-1]["close"]
    drawdown = (1 - low / prior_high) * 100 if prior_high else 0
    if drawdown < 25 or current < low * 1.035:
        return None
    old_lows = [x["low"] for x in d[-90:-15]]
    support_dist = min(abs(x / low - 1) * 100 for x in old_lows) if old_lows else 99
    if support_dist > 8 and low > quantile(old_lows, 0.08):
        return None
    ok4, reason4 = four_hour_confirm(h4)
    if not ok4 and current < low * 1.06:
        action, stage = "확인 대기", "B1"
    else:
        action, stage = "진입 검토", "B2"
    entry_low, entry_high = current * 0.985, current * 1.01
    stop = low * 0.97
    resistance = max(x["high"] for x in d[-35:-5])
    target = max(current * 1.10, min(resistance, current * 1.22))
    score = 4.8 + min(2, drawdown / 20) + (1.5 if ok4 else 0.3) + (1.2 if support_dist <= 4 else 0.5)
    return candidate(row["symbol"], "B", stage, score, action, current, entry_low, entry_high, stop, target,
                     row["tick"], f"장기 낙폭 {drawdown:.1f}% · 하단 지지거리 {support_dist:.1f}% · {reason4}",
                     [x["close"] for x in h4])


def scan_c(row: dict, d: list[dict], h4: list[dict]) -> dict | None:
    if len(d) < 50 or len(h4) < 10:
        return None
    resistance = max(x["high"] for x in d[-40:-6])
    if resistance <= 0:
        return None
    recent = d[-6:]
    broke = any(x["close"] >= resistance * 1.003 for x in recent)
    current = d[-1]["close"]
    if not broke or current < resistance * 0.985:
        return None
    retest = any(x["low"] <= resistance * 1.025 and x["close"] >= resistance * 0.995 for x in h4[-8:])
    ok4, reason4 = four_hour_confirm(h4, resistance)
    defended = retest and ok4
    stage = "C2" if defended else "C1"
    action = "진입 검토" if defended else "재지지 확인 대기"
    entry_low = resistance * 0.995
    entry_high = resistance * 1.018
    stop = resistance * 0.965
    base_low = min(x["low"] for x in d[-40:-6])
    box_height = max(resistance - base_low, resistance * 0.05)
    target = max(resistance * 1.07, resistance + box_height * 0.45)
    vol_now = median([x["volume"] for x in recent])
    vol_prev = max(median([x["volume"] for x in d[-30:-6]]), 1e-9)
    vr = vol_now / vol_prev
    score = 5.2 + (1.7 if defended else 0.4) + min(1.5, vr / 1.5) + min(1.0, max(0, pct(current, resistance)) / 4)
    return candidate(row["symbol"], "C", stage, score, action, current, entry_low, entry_high, stop, target,
                     row["tick"], f"일봉 상단 돌파 · 거래량 {vr:.1f}배 · {'재지지 확인' if retest else '재지지 대기'} · {reason4}",
                     [x["close"] for x in h4])


def scan_d(row: dict, d: list[dict], h4: list[dict]) -> dict | None:
    """Use the shared pure D scorer/lifecycle with Binance-only completed bars."""
    from scanner.pre_breakout_reclaim import analyze
    def adapt(rows):
        return [{**x, "time": datetime.fromtimestamp(x["open_time"]/1000, timezone.utc)
                 .astimezone(KST).isoformat()} for x in rows]
    result = analyze(row["symbol"], adapt(d[-120:]), adapt(h4[-100:]))
    if result["status"] in {"제외", "자료부족", "오류"}:
        return None
    tick = row["tick"]
    status = result["status"]
    action = {"진입확인":"진입 검토", "선매수감시":"확인 대기", "준비":"진입가 대기", "늦음·추격금지":"추격 금지"}.get(status,"진입가 대기")
    entry = result["aggressive_entry_zone"] or result["confirmation_entry_zone"]
    return {
        "market":row["symbol"],"name":row.get("base",row["symbol"]),"type":"D",
        "stage":result["d_stage"],"status":status,"score":result["score"],
        "d_stage":result["d_stage"],"d_stage_label":result["d_stage_label"],
        "d_stage_reason":result["d_stage_reason"],"checks":result["checks"],
        "pattern_action":action,"action":action,
        "price":round_tick(result["last_completed_4h_close"],tick),
        "entry":[round_tick(x,tick) for x in entry],
        "stop":round_tick(result["hard_stop"],tick,"down"),
        "targets":[round_tick(x,tick,"down") for x in result["targets"]],
        "rr":result["first_target_rr"],
        "reason":" · ".join(k for k,v in result["checks"].items() if v),
        "missing":result["missing_conditions"],
        "spark":[round(x["close"],10) for x in h4[-30:]],
        "extra":{"lower":result["lower_reclaim_level"],"upper":result["upper_break_level"]},
    }


def scan_e(row: dict, d: list[dict], h4: list[dict]) -> dict | None:
    if len(d) < 75 or len(h4) < 8:
        return None
    view = d[-100:]
    low_window = view[-10:]
    low = min(x["low"] for x in low_window)
    low_idx = max(i for i, x in enumerate(view) if x["low"] == low)
    if low_idx < 15:
        return None
    pre = view[max(0, low_idx - 45):low_idx]
    broad_high = max(x["high"] for x in pre)
    drawdown = (1 - low / broad_high) * 100
    if drawdown < 30:
        return None
    pivot = max(x["high"] for x in view[max(0, low_idx - 12):low_idx])
    fast_drop = (1 - low / pivot) * 100
    if fast_drop < 15:
        return None
    base_vol = max(median([x["volume"] for x in pre[-30:]]), 1e-9)
    crash_vol = max(x["volume"] for x in view[max(0, low_idx - 5):low_idx + 1])
    vr = crash_vol / base_vol
    if vr < 1.35:
        return None
    history = view[:max(0, low_idx - 5)]
    if len(history) < 30:
        return None
    support_dist = min(abs(x["low"] / low - 1) * 100 for x in history)
    support_ok = support_dist <= 6 or low <= quantile([x["low"] for x in history], 0.05)
    if not support_ok:
        return None
    current = d[-1]["close"]
    span = pivot - low
    fib236 = low + span * 0.236
    target = low + span * 0.382
    if current >= target:
        return None
    ok4, reason4 = four_hour_confirm(h4)
    entry_low = low * 1.01
    entry_high = min(fib236, low * 1.08)
    stop = low * 0.97
    progress = (current - low) / span if span else 1
    if current <= entry_high and ok4:
        stage, action = "E2", "진입 검토"
    elif current <= entry_high:
        stage, action = "E1", "확인 대기"
    else:
        stage, action = "E3", "추격 금지"
    score = 5.0 + min(1.5, drawdown / 25) + min(1.5, fast_drop / 15) + min(1.2, vr / 2) + (1.2 if ok4 else 0.2)
    return candidate(row["symbol"], "E", stage, score, action, current, entry_low, entry_high, stop, target,
                     row["tick"], f"급락 {drawdown:.1f}% · 마지막 파동 -{fast_drop:.1f}% · 투매량 {vr:.1f}배 · {reason4}",
                     [x["close"] for x in h4], {"fib236": fib236, "fib382": target, "progress": round(progress, 3)})



def _g_historical_boxes(d: list[dict], upto: int) -> list[dict]:
    """과거 윗 가격층 후보를 넓게 찾는다. G형은 시각형태 우선."""
    hist=d[:upto]
    if len(hist)<70:
        return []
    boxes=[]
    search_start=max(0,len(hist)-190)
    for length in (24,32,45,60,80):
        for end_i in range(search_start+length, max(search_start+length, len(hist)-12), 3):
            if end_i>len(hist)-12:
                break
            seg=hist[end_i-length:end_i]
            if len(seg)<length:
                continue
            lows=[x["low"] for x in seg]; highs=[x["high"] for x in seg]; closes=[x["close"] for x in seg]
            box_low=quantile(lows,.18); box_high=quantile(highs,.82)
            if box_low<=0 or box_high<=box_low:
                continue
            width=box_high/box_low-1
            if width<.045 or width>.24:
                continue
            inside=sum(1 for x in closes if box_low<=x<=box_high)/len(closes)
            if inside<.64:
                continue
            mid=(box_low+box_high)/2
            if sum(1 for x in closes if x<=mid)<max(4,int(length*.15)):
                continue
            if sum(1 for x in closes if x>=mid)<max(4,int(length*.15)):
                continue
            boxes.append({"low":box_low,"high":box_high,"length":length,"inside":inside,
                          "start":end_i-length,"end":end_i-1})
    boxes.sort(key=lambda z:(z["low"],-z["length"],-z["inside"]))
    out=[]
    for box in boxes:
        if any(abs(box["low"]/x["low"]-1)<.025 and abs(box["high"]/x["high"]-1)<.04 for x in out):
            continue
        out.append(box)
    return out


def scan_g(row: dict, d: list[dict]) -> dict | None:
    """G형: 아래 가격층에서 올라와 최신 완성 일봉이 저항매물대 하단을 처음 장악."""
    if len(d)<100:
        return None
    i=len(d)-1
    cur=d[i]; prev=d[i-1]
    prev_close=float(prev["close"])
    op,hi,lo,cl=(float(cur["open"]),float(cur["high"]),float(cur["low"]),float(cur["close"]))
    recent=d[max(0,i-45):i]
    if not recent:
        return None
    recent_low=min(x["low"] for x in recent)
    best=None
    for box in _g_historical_boxes(d,i):
        b0,b1=float(box["low"]),float(box["high"])
        span=b1-b0
        if span<=0:
            continue

        lower_days=sum(1 for x in recent if x["close"]<b0*.93)
        if lower_days<3 or recent_low>b0*.94:
            continue

        r12=d[max(0,i-11):i+1]
        if len(r12)<6:
            continue
        first_avg=sum(x["close"] for x in r12[:4])/4
        last_avg=sum(x["close"] for x in r12[-4:])/4
        if last_avg<=first_avg*1.02:
            continue

        earlier=d[max(0,i-4):i]
        first_take=(
            prev_close<b0*.998
            and min(op,prev_close)<=b0*1.008
            and cl>b0
            and all(x["close"]<b0*1.002 for x in earlier)
        )
        if not first_take:
            continue

        pos=(cl-b0)/span
        if pos<.08 or pos>.68:
            continue
        if cl>=b1*.99 or hi>=b1*1.05:
            continue

        score=box["inside"]*100+box["length"]*.15-abs(pos-.30)*10
        cand={"box_low":b0,"box_high":b1,"wick":lo,"pos":pos,"lower_days":lower_days,
              "box_days":box["length"],"inside":box["inside"],"score":score}
        if best is None or cand["score"]>best["score"]:
            best=cand
    if best is None:
        return None

    b0,b1,w=best["box_low"],best["box_high"],best["wick"]
    tick=row["tick"]
    return {
        "market":row["symbol"],"type":"G","stage":"A급 · 오늘 첫 장악",
        "score":round(min(10.0,7.0+best["inside"]*3.0),1),
        "pattern_action":"관찰","action":"관찰","price":round_tick(cl,tick),
        "entry":[round_tick(w,tick,"up"),round_tick(b0,tick,"down")],
        "stop":round_tick(w*.985,tick,"down"),"targets":[round_tick(b1,tick,"down")],
        "rr":None,
        "reason":"아랫동네에서 반등해 오늘 완성 일봉이 저항매물대 하단을 처음 몸통·종가로 장악",
        "spark":[round(x["close"],10) for x in d[-30:]],
        "g_reclaim_date":datetime.fromtimestamp(cur["close_time"]/1000, timezone.utc).astimezone(KST).strftime("%Y-%m-%d"),
        "g_supply_low":round_tick(b0,tick),"g_supply_high":round_tick(b1,tick),
        "g_wick_support":round_tick(w,tick),"g_box_top":round_tick(b1,tick),
        "g_close_depth_pct":round(best["pos"]*100,1),
        "g_box_days":best["box_days"],"g_box_inside_ratio":round(best["inside"]*100,1),
        "g_lower_zone_days":best["lower_days"],
        "extra":{},
    }


def scan_h(row: dict, d: list[dict]) -> dict | None:
    """H: completed daily close above a meaningful older resistance band."""
    if len(d) < 100 or row.get("base") in STABLE_BASES:
        return None
    last, prev = d[-1]["close"], d[-2]["close"]
    if last <= 0 or prev <= 0 or d[-1]["quote_volume"] < 250_000 or pct(last, prev) > 15:
        return None
    upper_floor = quantile([x["high"] for x in d[-185:-5]], .85)
    choices = []

    def consider(low: float, high: float, strength: float, fallback: bool = False):
        if high < upper_floor or not 1.5 <= pct(last, high) <= 18:
            return
        # One of the last five completed bars first closed above the upper
        # boundary, and every later completed close remained above it.
        for age in range(4, -1, -1):
            i = len(d) - 1 - age
            if d[i-1]["close"] <= high < d[i]["close"] and all(x["close"] > high for x in d[i:]):
                rank = (-pct(last, high), strength, -age) if fallback else (strength, -age, -pct(last, high))
                choices.append((rank, low, high, age))
                break

    # Keep the same box windows and post-box resistance validation as Upbit.
    # Truncating five bars before box discovery shifts every rolling window.
    for box in _g_historical_boxes(d, len(d)):
        low, high = box["low"], box["high"]
        if box["end"] >= len(d)-6:
            continue
        closed = d[box["end"]+1:-5]
        if len(closed) >= 12 and sum(x["close"] > high*1.025 for x in closed)/len(closed) > .15:
            continue
        consider(low, high, box["length"]*box["inside"])
    if not choices:
        highs = [x["high"] for x in d[:-5]]
        for anchor in highs[-160:]:
            touches = [i for i, value in enumerate(highs) if abs(value/anchor-1) <= .018]
            if len(touches) < 2 or max(touches)-min(touches) < 10:
                continue
            high = median([highs[i] for i in touches])
            if sum(x["close"] > high*1.025 for x in d[-60:-5]) > 4:
                continue
            low = quantile([x["low"] for x in d[min(touches):max(touches)+1]], .25)
            if .70 <= low/high <= .96:
                consider(low, high, (max(touches)-min(touches))*min(1.0,len(touches)/4), fallback=True)
    if not choices:
        return None
    _, low, high, age = max(choices, key=lambda x:x[0])
    distance = pct(last, high)
    chased = distance > 8
    status = "추격 금지" if chased else "첫 돌파" if age == 0 else "상단 위 유지"
    tick = row["tick"]
    return {
        "market": row["symbol"], "type": "H", "stage": status, "status": status,
        "score": round(max(0, min(10, 8-distance*.18)), 1),
        "pattern_action": "추격 금지" if chased else "확인 대기", "action": "추격 금지" if chased else "확인 대기",
        "price": round_tick(last, tick), "analysis_close": round_tick(last, tick),
        "entry": [round_tick(high, tick, "up"), round_tick(high*1.025, tick, "up")],
        "stop": round_tick(high*.985, tick, "down"), "targets": [], "rr": None,
        "reason": "완성 일봉이 과거 저항 매물대 상단 위에서 마감",
        "spark": [round(x["close"], 10) for x in d[-30:]],
        "h_zone_low": round_tick(low, tick), "h_zone_high": round_tick(high, tick),
        "h_distance_pct": round(distance, 2), "h_breakout_age": age,
        "h_daily_rise_pct": round(pct(last,prev),2),
        "h_daily_value_usdt": round(d[-1]["quote_volume"]),
        "h_candle_date": datetime.fromtimestamp(d[-1]["close_time"]/1000, timezone.utc).astimezone(KST).strftime("%Y-%m-%d"),
        "extra": {},
    }


def scan_f(row: dict, d: list[dict]) -> dict | None:
    """Binance recent-high trend meeting its own older supply; no Upbit I/O."""
    from scanner.global_supply import (upbit_new_high_trend, historical_supply_zone,
                                      classify_stage, f2_zone_position)
    if len(d) < 120:
        return None
    # The trend's horizon is explicit: Binance has a much longer listing history
    # than a newly listed KRW pair. Compare the current 200-day cycle to older
    # Binance supply rather than silently treating a 400-bar high as listing ATH.
    trend = upbit_new_high_trend([
        {"trade_price": x["close"], "high_price": x["high"], "low_price": x["low"]}
        for x in d[-200:]
    ])
    if not trend:
        return None
    raw = [[x["open_time"], x["open"], x["high"], x["low"], x["close"],
            x["volume"], x["close_time"]] for x in d]
    current = d[-1]["close"]
    zone = historical_supply_zone(raw, current)
    if not zone:
        return None
    stage, label, missing = classify_stage(current, zone, raw)
    low, high = zone["lower"], zone["upper"]
    if stage == "F3":
        entry_low, entry_high, stop, target = high*.99, high*1.02, high*.955, high+(high-low)*.70
        action = "진입 검토"
    else:
        entry_low, entry_high, stop, target = low*.98, low*(1.03 if stage == "F2" else 1.02), low*.95, high
        action = "확인 대기" if stage == "F2" else "진입가 대기"
    item = candidate(row["symbol"], "F", stage,
        min(10, 5+trend["upbit_rise_pct"]/50+zone["inside_ratio"]*2+zone["days"]/60),
        action, current, entry_low, entry_high, stop, target, row["tick"],
        f'Binance 최근 200일 고점권 상승 + {zone["start"]}~{zone["end"]} 과거 횡보 매물대',
        [x["close"] for x in d])
    if item is None:
        return None
    position = f2_zone_position(current, zone)
    item.update({"status": label, "f_stage": stage, "f_stage_label": label,
                 "global_zone": zone, "missing": missing,
                 "f2_zone_position": position["label"] if stage == "F2" else None,
                 "f2_zone_position_pct": position["ratio_pct"] if stage == "F2" else None,
                 "f2_zone_mid": position["mid"], "trend_lookback_days": 200,
                 "trend_basis": "BINANCE_200_DAY_HIGH"})
    return item


def btc_regime(btc_daily: list[dict], btc4: list[dict], universe: list[dict]) -> dict:
    window = btc_daily[-30:]
    low = quantile([x["low"] for x in window], 0.10)
    high = quantile([x["high"] for x in window], 0.90)
    center = sum(x["close"] * x["volume"] for x in window) / max(sum(x["volume"] for x in window), 1e-9)
    price = btc_daily[-1]["close"]
    position = (price - low) / max(high - low, 1e-9)
    btc24 = next((x["change_24h_pct"] for x in universe if x["symbol"] == "BTCUSDT"), 0.0)
    alts = [x for x in universe if x["symbol"] != "BTCUSDT"]
    changes = [x["change_24h_pct"] for x in alts]
    breadth = sum(1 for x in changes if x > 0) / max(len(changes), 1) * 100
    med = median(changes)
    slope4 = pct(btc4[-1]["close"], btc4[-4]["close"]) if len(btc4) >= 4 else 0
    structural_risk = price < low or (slope4 < -3 and position < 0.35)
    if structural_risk or (btc24 < -2 and breadth < 35):
        stage, confidence = "M0", 90
        reasons = ["BTC 박스 하단 훼손 또는 단기 급락", f"Binance USDT 알트 상승비율 {breadth:.0f}%"]
    elif position >= 0.90 and breadth >= 65 and med >= 1.5:
        stage, confidence = "M5", 78
        reasons = ["BTC 박스 상단 과열권", f"알트 상승비율 {breadth:.0f}% · 중앙값 {med:+.1f}%"]
    elif breadth >= 65 and med >= 1.2 and btc24 > -1:
        stage, confidence = "M4", 84
        reasons = [f"알트 상승비율 {breadth:.0f}%", f"알트 24H 중앙값 {med:+.1f}%"]
    elif breadth >= 55 and med >= 0.35 and btc24 > -1.5:
        stage, confidence = "M3", 81
        reasons = [f"알트 상승비율 {breadth:.0f}%", "Binance 현물 기준 자금 확산 시작"]
    elif btc24 >= 0.7 and breadth <= 45:
        stage, confidence = "M1", 76
        reasons = [f"BTC 24H {btc24:+.1f}%", f"알트 상승비율은 {breadth:.0f}%로 확산 부족"]
    else:
        stage, confidence = "M2", 70
        reasons = [f"알트 상승비율 {breadth:.0f}% · 중앙값 {med:+.1f}%", "확산 또는 위험 신호가 아직 확정되지 않음"]
    name, limit = STAGE_INFO[stage]
    state = "박스 하단 매수존" if position <= .15 else "하단 회복 구간" if position <= .45 else "박스 중심 공방" if position <= .65 else "상단 접근" if position < .90 else "박스 상단 매도존"
    four_state = "단기 상승" if slope4 > 1.5 else "단기 하락" if slope4 < -1.5 else "횡보 확인"
    span = high - low
    return {
        "stage": stage, "name": name, "confidence": confidence, "alt_entry_limit_pct": limit, "reasons": reasons,
        "breadth": {"positive_ratio_24h_pct": round(breadth, 1), "median_change_24h_pct": round(med, 2)},
        "btc": {
            "market": "BTCUSDT", "price": round(price, 2), "daily_state": state, "four_hour_state": four_state,
            "box": {"low": round(low, 2), "center": round(center, 2), "high": round(high, 2), "position_pct": round(position * 100, 1)},
            "correction": {"defense1": round(low + span * 0.45, 2), "defense2": round(low + span * 0.15, 2), "invalid": round(low * 0.98, 2)},
            "spark": [round(x["close"], 2) for x in btc4[-48:]],
        },
        "gates": {t: {"code": GATE_RULES[stage][t], "label": GATE_LABELS[GATE_RULES[stage][t]]} for t in "ABCDEFGH"},
    }


def apply_gate(c: dict, regime: dict) -> dict:
    row = dict(c)
    code = regime["gates"][row["type"]]["code"]
    pattern_action = row["pattern_action"]
    if pattern_action == "추격 금지":
        final = pattern_action
    elif code == "BLOCK":
        final = "시장 대기"
    elif code == "WATCH" and pattern_action == "진입 검토":
        final = "시장 대기"
    elif code == "CONDITIONAL" and pattern_action == "진입 검토":
        final = "조건부 진입"
    elif code == "PROTECT":
        final = "익절 우선"
    else:
        final = pattern_action
    row["action"] = final
    row["market_gate"] = {"code": code, "label": GATE_LABELS[code], "stage": regime["stage"]}
    return row


def scan() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    universe = fetch_universe()
    by_symbol = {x["symbol"]: x for x in universe}
    if "BTCUSDT" not in by_symbol:
        btc_ticker = api_get("/ticker/24hr", {"symbol": "BTCUSDT"})
        by_symbol["BTCUSDT"] = {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT", "price": float(btc_ticker["lastPrice"]), "quote_volume": float(btc_ticker["quoteVolume"]), "change_24h_pct": float(btc_ticker["priceChangePercent"]), "tick": 0.01}
        universe.insert(0, by_symbol["BTCUSDT"])
    btc_daily = fetch_klines("BTCUSDT", "1d", 90)
    btc4 = fetch_klines("BTCUSDT", "4h", 90)
    regime = btc_regime(btc_daily, btc4, universe)

    found: list[dict] = []
    failures: list[str] = []
    examined = {key: 0 for key in "ABCDEFGH"}
    scope = {}
    for idx, row in enumerate(universe, start=1):
        symbol = row["symbol"]
        try:
            daily = btc_daily if symbol == "BTCUSDT" else fetch_klines(symbol, "1d", 120)
            four = btc4 if symbol == "BTCUSDT" else fetch_klines(symbol, "4h", 100)
            if len(daily) < 50 or len(four) < 8:
                continue
            for fn in (scan_a, scan_b, scan_c, scan_d, scan_e):
                examined[fn.__name__[-1].upper()] += 1
                item = fn(row, daily, four)
                if item:
                    found.append(apply_gate(item, regime))
        except Exception as exc:
            failures.append(f"{symbol}: {exc}")
        if idx % 20 == 0:
            print(f"Binance scan {idx}/{len(universe)} · candidates {len(found)}")

    # G형은 거래대금/상위 N 필터 없이 Binance Spot USDT 전체를 별도 스캔한다.
    g_universe = fetch_universe(min_quote_volume=None, limit=None)
    g_found = 0
    for idx, row in enumerate(g_universe, start=1):
        symbol=row["symbol"]
        try:
            supply_daily = fetch_klines(symbol, "1d", 1000)
            daily = supply_daily[-400:]
            for scan_fn in (scan_f, scan_g, scan_h):
                examined[scan_fn.__name__[-1].upper()] += 1
                item = scan_fn(row, supply_daily if scan_fn is scan_f else daily)
                if item:
                    found.append(apply_gate(item, regime))
                    if item["type"] == "G": g_found += 1
        except Exception as exc:
            failures.append(f"G {symbol}: {exc}")
        if idx % 50 == 0:
            print(f"Binance G scan {idx}/{len(g_universe)} · G candidates {g_found}")

    scope = {row["symbol"]: {"liquid_universe": row["symbol"] in by_symbol,
             "quote_volume": row["quote_volume"], "F_G_H": "full_spot_universe"}
             for row in g_universe}
    found.sort(key=lambda x: (
        x["type"] == "G" and x.get("stage") == "A급 · 오늘 첫 장악",
        x["action"] in {"진입 검토", "조건부 진입"},
        x["score"],
        float(x["rr"] or 0),
    ), reverse=True)
    counts = {t: sum(1 for x in found if x["type"] == t) for t in "ABCDEFGH"}
    now = datetime.now(KST)
    completed_4h = datetime.fromtimestamp(btc4[-1]["close_time"] / 1000, timezone.utc).astimezone(KST).isoformat(timespec="seconds")
    result = {
        "generated_at": now.isoformat(timespec="seconds"), "basis_4h_end": completed_4h,
        "source": "BINANCE SPOT USDT", "universe_count": len(universe), "min_quote_volume": MIN_QUOTE_VOLUME, "g_universe_count": len(g_universe), "g_min_quote_volume": None,
        "market_regime": regime, "counts": counts, "candidates": found, "failures": failures[:30], "failure_count": len(failures),
        "scan_diagnostics": {"examined_counts": examined, "symbol_scope": scope,
            "daily_lookback": {"A_B_C_D_E": 120, "G_H": 400, "F_supply": 1000, "F_trend": 200},
            "liquid_universe_limit": MAX_SYMBOLS},
    }
    LATEST.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        history = json.loads(SNAPSHOTS.read_text(encoding="utf-8"))
        if not isinstance(history, list): history = []
    except (OSError, json.JSONDecodeError):
        history = []
    history.append({
        "generated_at": result["generated_at"], "basis_4h_end": completed_4h, "market_regime": regime,
        "counts": counts, "top": [{k: x[k] for k in ("market", "type", "stage", "score", "action", "price", "rr")} for x in found[:20]],
    })
    SNAPSHOTS.write_text(json.dumps(history[-180:], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BINANCE {regime['stage']} {regime['name']} · universe {len(universe)} · candidates {len(found)}")
    return result


if __name__ == "__main__":
    scan()
