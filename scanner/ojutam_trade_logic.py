from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import pandas as pd


def _f(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _atr(df: pd.DataFrame, n: int = 14) -> float:
    q = df.tail(max(n + 2, 20))
    if len(q) < 3:
        return 0.0
    prev = q["Close"].shift(1)
    tr = pd.concat([(q["High"] - q["Low"]), (q["High"] - prev).abs(), (q["Low"] - prev).abs()], axis=1).max(axis=1)
    return _f(tr.tail(n).mean())


def _trendline_low(df: pd.DataFrame, n: int = 30) -> Tuple[float, float]:
    q = df.tail(n)
    if len(q) < 10:
        return 0.0, 0.0
    ys = [float(x) for x in q["Low"]]
    xs = list(range(len(ys)))
    xm = sum(xs) / len(xs)
    ym = sum(ys) / len(ys)
    den = sum((x - xm) ** 2 for x in xs) or 1.0
    slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / den
    intercept = ym - slope * xm
    return intercept + slope * (len(ys) - 1), slope


def _pivot_lows(df: pd.DataFrame, lookback: int = 70) -> List[float]:
    q = df.tail(lookback)
    vals = q["Low"].astype(float).tolist()
    out: List[float] = []
    for i in range(2, len(vals) - 2):
        if vals[i] <= min(vals[i - 2:i]) and vals[i] <= min(vals[i + 1:i + 3]):
            out.append(vals[i])
    return out


def _pivot_highs(df: pd.DataFrame, lookback: int = 140) -> List[float]:
    q = df.tail(lookback)
    vals = q["High"].astype(float).tolist()
    out: List[float] = []
    for i in range(2, len(vals) - 2):
        if vals[i] >= max(vals[i - 2:i]) and vals[i] >= max(vals[i + 1:i + 3]):
            out.append(vals[i])
    return out


def _dedupe_levels(values: List[float], pct: float = 0.012) -> List[float]:
    out: List[float] = []
    for value in sorted(v for v in values if v > 0):
        if not out or abs(value / out[-1] - 1.0) > pct:
            out.append(value)
        else:
            out[-1] = max(out[-1], value)
    return out


def _nearest_valid_support(item: dict, df: pd.DataFrame, cur: float, atr: float) -> Tuple[Optional[float], float, float, List[str]]:
    close = df["Close"].astype(float)
    ema20 = _f(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = _f(close.ewm(span=50, adjust=False).mean().iloc[-1])
    trend, slope = _trendline_low(df, 30)
    levels = item.get("levels") or {}
    anchors = []
    for key in ("support", "base_high", "box_high", "reclaim", "weekly_ema50", "capitulation_low"):
        v = _f(levels.get(key))
        if v > 0:
            anchors.append(v)
    anchors += _pivot_lows(df, 70)
    anchors += [ema20, ema50]
    floor = cur * 0.88
    ceiling = cur * 1.01
    if slope > 0 and trend > 0:
        floor = max(floor, trend * 0.985)
    valid = [v for v in anchors if floor <= v <= ceiling]
    reasons: List[str] = []
    if not valid:
        return None, trend, slope, ["현재 상승구조 안에 유효한 신규 지지구간 없음"]
    support = max(valid)
    if slope > 0 and support < trend * 0.985:
        return None, trend, slope, ["옛 진입가 재방문 시 상승 추세선 훼손"]
    if support < cur * 0.92:
        reasons.append("매수구간과 현재가 이격 큼")
    if ema20 > 0 and support >= ema20 * 0.985:
        reasons.append("단기 추세 지지 근접")
    return support, trend, slope, reasons


def _targets(item: dict, df: pd.DataFrame, cur: float, avg: float, atr: float) -> Tuple[float, float, float]:
    levels = item.get("levels") or {}
    highs = _pivot_highs(df, 150)
    for key in ("swing_high", "base_high", "prior_high", "box_high", "reclaim", "recent_high", "historical_supply"):
        v = _f(levels.get(key))
        if v > 0:
            highs.append(v)
    threshold = max(cur * 1.006, avg * 1.02)
    resistances = _dedupe_levels([v for v in highs if v > threshold], 0.01)
    fallback = max(atr, cur * 0.018)
    t1 = resistances[0] if resistances else cur + fallback * 1.4
    t2 = resistances[1] if len(resistances) > 1 else t1 + fallback * 1.5
    ext = resistances[2] if len(resistances) > 2 else t2 + fallback * 1.5
    return t1, t2, ext


def apply_trade_context(item: dict, df: pd.DataFrame) -> dict:
    """패턴 탐지는 유지하고, 현재 위치 중심의 실전 선별 점수/매매안을 후단에 붙인다."""
    out = dict(item)
    if df is None or len(df) < 60:
        return out
    d = df.tail(220).copy()
    cur = _f(d["Close"].iloc[-1])
    atr = _atr(d)
    pattern_score = _f(out.get("score"), 0.0)
    out["pattern_score"] = round(pattern_score, 1)

    support, trend, slope, notes = _nearest_valid_support(out, d, cur, atr)
    if not support:
        out["score"] = round(min(pattern_score * 0.45, 4.5), 1)
        out["trade_plan"] = {
            "current": cur, "status": "새 구조 대기", "reason": " · ".join(notes),
            "entry_low": None, "entry_high": None, "average_entry": None,
            "stop": None, "target1": None, "target2": None, "extension": None,
            "rr1": None, "distance_pct": None,
        }
        return out

    zone_pad = max(atr * 0.35, support * 0.008)
    entry_low = support - zone_pad * 0.45
    entry_high = support + zone_pad * 0.65
    if slope > 0 and trend > 0:
        entry_low = max(entry_low, trend * 0.99)
    entry_high = min(entry_high, cur * 1.01)
    if entry_low >= entry_high:
        entry_low = support * 0.995
        entry_high = support * 1.008

    mid = (entry_low + entry_high) / 2.0
    average = entry_high * 0.30 + mid * 0.30 + entry_low * 0.40
    invalid_anchor = min(entry_low, support)
    stop = invalid_anchor - max(atr * 0.45, invalid_anchor * 0.012)
    t1, t2, ext = _targets(out, d, cur, average, atr)

    risk = average - stop
    rr1 = (t1 - average) / risk if risk > 0 and t1 > average else 0.0
    risk_pct = risk / average * 100.0 if average > 0 else 99.0
    if cur < entry_low:
        distance = -(entry_low - cur) / cur * 100.0
    elif cur > entry_high:
        distance = (cur - entry_high) / entry_high * 100.0
    else:
        distance = 0.0

    # 10점 = 패턴 모양이 아니라 '지금 실제로 매매 검토할 가치'에 가깝도록 현재 위치 비중을 가장 크게 둔다.
    if distance == 0:
        position_pts = 4.0
    elif 0 < distance <= 2:
        position_pts = 3.6
    elif 0 < distance <= 5:
        position_pts = 2.8
    elif 0 < distance <= 8:
        position_pts = 1.8
    elif 0 < distance <= 12:
        position_pts = 0.8
    elif distance < 0 and abs(distance) <= 2:
        position_pts = 2.8
    else:
        position_pts = 0.0

    pattern_pts = min(2.0, pattern_score / 10.0 * 2.0)
    structure_pts = 1.0
    if slope > 0 and trend > 0 and cur < trend:
        structure_pts = 0.0
    elif slope <= 0:
        structure_pts = 0.55

    if risk_pct <= 4:
        stop_pts = 1.5
    elif risk_pct <= 6:
        stop_pts = 1.1
    elif risk_pct <= 8:
        stop_pts = 0.6
    else:
        stop_pts = 0.15

    if rr1 >= 1.5:
        rr_pts = 1.5
    elif rr1 >= 1.2:
        rr_pts = 1.2
    elif rr1 >= 1.0:
        rr_pts = 0.8
    else:
        rr_pts = 0.2

    total = min(10.0, position_pts + pattern_pts + structure_pts + stop_pts + rr_pts)
    if cur <= stop:
        status = "구조 무효"
        total = min(total, 3.0)
        remain = "재진입 금지 · 새 구조 형성 대기"
    elif distance == 0 and rr1 >= 1.0:
        status = "진입 검토"
        remain = "지지 반응 확인 후 분할 진입"
    elif 0 < distance <= 3:
        status = "확인 대기"
        remain = "매수구간 접근 · 지지 확인"
    elif 0 < distance <= 8:
        status = "진입가 대기"
        remain = "현재 상승구조 안의 유효 지지구간 대기"
    elif distance > 8:
        status = "추격 금지"
        total = min(total, 5.4)
        remain = "옛 진입가 추적 금지 · 새 지지구조 대기"
    else:
        status = "확인 대기"
        remain = "지지 재탈환 확인"

    if rr1 < 1.0 and status == "진입 검토":
        status = "확인 대기"
        remain = "1차 저항까지 손익비 부족"
        total = min(total, 6.4)

    short_notes = list(notes)
    short_notes.append("현재 위치 양호" if abs(distance) <= 3 else "매수자리 이격")
    short_notes.append("손절 짧음" if risk_pct <= 6 else "손절폭 큼")
    if rr1 >= 1.0:
        short_notes.append("1차 목표 현실적")
    out["score"] = round(total, 1)
    out["trade_plan"] = {
        "current": round(cur, 6), "status": status, "reason": " · ".join(short_notes[:3]),
        "remain": remain,
        "entry_low": round(entry_low, 6), "entry_high": round(entry_high, 6),
        "average_entry": round(average, 6), "stop": round(stop, 6),
        "target1": round(t1, 6), "target2": round(t2, 6), "extension": round(ext, 6),
        "rr1": round(rr1, 2), "distance_pct": round(distance, 2),
        "trendline": round(trend, 6) if trend > 0 else None,
    }
    return out
