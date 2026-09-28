"""H형: 과거 저항 매물대 상단을 완성 일봉 종가로 돌파한 코인."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from box_screener import _g_historical_boxes, rounded_price

KST = timezone(timedelta(hours=9))
STABLES = {"USDT", "USDC", "DAI", "TUSD", "USDD", "USD1", "FDUSD", "PYUSD", "USDE"}
MAX_CHASE_PCT = 8.0
MAX_DAILY_RISE_PCT = 15.0
MIN_DAILY_TRADE_KRW = 300_000_000


def analyze_h_breakout(row, daily):
    """Use completed Upbit daily bars only; distinguish a fresh break from a hold."""
    market = str(row["Code"])
    if market.removeprefix("KRW-") in STABLES or len(daily) < 100:
        return None
    closes = daily["Close"].astype(float)
    last = float(closes.iloc[-1])
    previous = float(closes.iloc[-2])
    if last <= 0 or previous <= 0:
        return None
    daily_rise = (last / previous - 1) * 100
    recent_value = float(daily["Close"].iloc[-1] * daily["Volume"].iloc[-1])
    if recent_value < MIN_DAILY_TRADE_KRW or daily_rise > MAX_DAILY_RISE_PCT:
        return None

    # Find historic horizontal boxes whose upper boundary was resistance before
    # the latest breakout. A box must finish before the 5-bar breakout window.
    choices = []
    for box in _g_historical_boxes(daily, len(daily)):
        upper, lower = box["high"], box["low"]
        if box["end"] >= len(daily) - 6 or not lower < upper < last:
            continue
        if (last / upper - 1) * 100 > 18:
            continue
        closed = closes.iloc[box["end"] + 1:-5]
        if len(closed) >= 12 and (closed > upper * 1.025).mean() > .15:
            continue
        breakout = None
        for age in range(4, -1, -1):
            i = len(daily) - 1 - age
            if i < 1:
                continue
            if closes.iloc[i-1] <= upper and closes.iloc[i] > upper:
                breakout = age
                break
        if breakout is None or (closes.iloc[-breakout-1:] <= upper).any():
            continue
        distance = (last / upper - 1) * 100
        # Prefer a well established box, then a recent and still nearby break.
        rank = (box["length"] * box["inside_ratio"], -breakout, -distance)
        choices.append((rank, box, breakout, distance))
    if not choices:
        # Some long-term supply zones have sparse swing highs rather than a
        # continuous sideways box (ONDO is one example). Two separated
        # rejections near the same level still form a resistance band.
        highs = daily["High"].astype(float).iloc[:-5]
        for anchor in highs.iloc[-160:]:
            touches = [i for i, value in enumerate(highs) if abs(value / anchor - 1) <= .018]
            if len(touches) < 2 or max(touches) - min(touches) < 10:
                continue
            upper = float(highs.iloc[touches].median())
            if not upper < last or (last / upper - 1) * 100 > 18:
                continue
            if (closes.iloc[-60:-5] > upper * 1.025).sum() > 4:
                continue
            age = next((a for a in range(4, -1, -1)
                if closes.iloc[-a-2] <= upper < closes.iloc[-a-1]
                and (closes.iloc[-a-1:] > upper).all()), None)
            if age is None:
                continue
            low = float(daily["Low"].iloc[min(touches):max(touches)+1].quantile(.25))
            if not .70 <= low / upper <= .96:
                continue
            distance = (last / upper - 1) * 100
            box = {"low": low, "high": upper, "length": max(touches)-min(touches), "inside_ratio": min(1.0, len(touches)/4)}
            choices.append(((-distance, box["length"] * box["inside_ratio"], -age), box, age, distance))
    if not choices:
        return None
    _, box, age, distance = max(choices, key=lambda item: item[0])
    upper, lower = float(box["high"]), float(box["low"])
    chased = distance > MAX_CHASE_PCT
    status = "추격 금지" if chased else "첫 돌파" if age == 0 else "상단 위 유지"
    # A scalp's upside must be measured against the next real resistance;
    # fixed percentage targets would create a false trade plan.
    return {
        "market": market, "name": row.get("Name") or market.removeprefix("KRW-"),
        "type": "H", "score": round(min(99, 60 + box["length"] * .25 + box["inside_ratio"] * 12 - distance), 1),
        "status": status, "action": "추격 금지" if chased else "확인 대기",
        "price": rounded_price(last), "analysis_close": rounded_price(last),
        "entry": [rounded_price(upper), rounded_price(upper * 1.025)],
        "stop": rounded_price(upper * .985), "targets": [], "rr": None,
        "reason": "완성 일봉이 과거 저항 매물대 상단 위에서 마감",
        "missing": ["다음 봉에서 상단 지지 및 가까운 위쪽 저항 확인"],
        "h_zone_low": rounded_price(lower), "h_zone_high": rounded_price(upper),
        "h_distance_pct": round(distance, 2), "h_breakout_age": age,
        "h_daily_rise_pct": round(daily_rise, 2),
        "h_daily_value_krw": round(recent_value),
        "h_candle_date": str(daily.index[-1])[:10],
    }


def scan_h_breakout(universe, frames):
    results = []
    for _, row in universe.iterrows():
        daily = frames.get(str(row["Code"]))
        if daily is None or daily.empty:
            continue
        result = analyze_h_breakout(row, daily)
        if result:
            results.append(result)
    return sorted(results, key=lambda r: (r["action"] == "추격 금지", r["h_breakout_age"], r["h_distance_pct"]))
