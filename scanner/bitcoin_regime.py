#!/usr/bin/env python3
"""완성 일봉 박스와 완성 4시간봉으로 BTC 주추세·알트 진입 강도를 계산한다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "bitcoin_regime.json"
API = "https://api.upbit.com/v1"


def get(path: str, params: dict) -> list[dict]:
    req = Request(f"{API}{path}?{urlencode(params)}", headers={"Accept": "application/json", "User-Agent": "upbit-btc-regime/1.0"})
    with urlopen(req, timeout=30) as response:  # noqa: S310 - 고정된 공식 API
        return json.loads(response.read().decode("utf-8"))


def candles(unit: str, count: int) -> list[dict]:
    path = "/candles/days" if unit == "day" else "/candles/minutes/240"
    raw = get(path, {"market": "KRW-BTC", "count": count + 2})
    now = datetime.now(KST).replace(tzinfo=None)
    boundary = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if unit == "day":
        if now < boundary:
            boundary -= timedelta(days=1)
        completed = [x for x in raw if datetime.fromisoformat(x["candle_date_time_kst"]) < boundary]
    else:
        elapsed = (now - boundary).total_seconds()
        if elapsed < 0:
            boundary -= timedelta(days=1)
            elapsed = (now - boundary).total_seconds()
        boundary += timedelta(hours=4 * int(elapsed // 14400))
        completed = [x for x in raw if datetime.fromisoformat(x["candle_date_time_kst"]) < boundary]
    return list(reversed(completed[:count]))


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos); hi = min(lo + 1, len(ordered) - 1); weight = pos - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def chart_rows(rows: list[dict], count: int) -> list[list]:
    return [[x["candle_date_time_kst"], x["opening_price"], x["high_price"], x["low_price"], x["trade_price"], x["candle_acc_trade_volume"]] for x in rows[-count:]]


def candle_close_kst(candle: dict, unit: str) -> str:
    """업비트가 주는 봉 시작시각을 실제 봉 마감시각으로 바꾼다."""
    opened_at = datetime.fromisoformat(candle["candle_date_time_kst"])
    duration = timedelta(days=1) if unit == "day" else timedelta(hours=4)
    return (opened_at + duration).isoformat()


def classify(position: float, breakout_confirmed: bool, failed_breakout: bool) -> tuple[str, dict]:
    if failed_breakout or position < 0:
        return ("박스 하단 이탈" if position < 0 else "상단 돌파 실패", {"mode": "신규중단", "size_pct": 0, "new_entry": "중단", "existing": "단타 정리·현금 비중 확대"})
    if position > 1:
        if breakout_confirmed:
            return "상단 돌파 확인", {"mode": "선별 재개", "size_pct": 70, "new_entry": "돌파·리테스트형만", "existing": "추세 유지분 보유"}
        return "상단 돌파 시도", {"mode": "추격금지", "size_pct": 0, "new_entry": "완성봉·리테스트 대기", "existing": "단타 분할익절"}
    if position <= .15:
        return "박스 하단 매수존", {"mode": "공격", "size_pct": 100, "new_entry": "A/B/D 지지확인형 허용", "existing": "지지 유지 시 보유"}
    if position <= .45:
        return "하단 회복 구간", {"mode": "보통", "size_pct": 70, "new_entry": "확인된 후보만", "existing": "목표가까지 분할대응"}
    if position <= .60:
        return "박스 중심 공방", {"mode": "절반", "size_pct": 50, "new_entry": "절반 비중·손익비 우선", "existing": "짧게 분할익절"}
    if position < .70:
        return "상단 접근", {"mode": "축소", "size_pct": 25, "new_entry": "최상위 후보만", "existing": "수익 보호"}
    if position < .90:
        return "박스 상단 매도존", {"mode": "신규중단", "size_pct": 0, "new_entry": "중단", "existing": "단타 분할익절·정리 우선"}
    return "진한 매도존", {"mode": "신규중단", "size_pct": 0, "new_entry": "중단", "existing": "단타 대부분 정리"}


def analyze(daily: list[dict], four: list[dict]) -> dict:
    window = daily[-30:]
    low = quantile([float(x["low_price"]) for x in window], .10)
    high = quantile([float(x["high_price"]) for x in window], .90)
    if high <= low:
        raise ValueError("BTC 박스 폭이 올바르지 않습니다")
    center = sum(float(x["trade_price"]) * float(x["candle_acc_trade_volume"]) for x in window) / max(sum(float(x["candle_acc_trade_volume"]) for x in window), 1e-9)
    price = float(daily[-1]["trade_price"])
    span = high - low; position = (price - low) / span
    recent4 = four[-12:]; vol_avg = sum(float(x["candle_acc_trade_volume"]) for x in four[-25:-1]) / max(len(four[-25:-1]), 1)
    last4 = four[-1]
    upper_tests = sum(1 for x in four[-20:] if float(x["high_price"]) >= low + span * .90)
    retest_defended = any(high * .98 <= float(x["low_price"]) <= high * 1.02 and float(x["trade_price"]) >= high for x in recent4)
    breakout_confirmed = price > high and float(last4["trade_price"]) > high and float(last4["candle_acc_trade_volume"]) >= vol_avg * 1.2 and retest_defended
    failed_breakout = any(float(x["high_price"]) > high and float(x["trade_price"]) < low + span * .90 for x in recent4[-3:])
    state, policy = classify(position, breakout_confirmed, failed_breakout)
    slope = float(four[-1]["trade_price"]) / float(four[-4]["trade_price"]) - 1
    if failed_breakout:
        four_state = "상단 돌파 실패"
    elif breakout_confirmed:
        four_state = "상단 돌파·거래량 확인"
    elif upper_tests >= 3 and position >= .70:
        # 접촉 횟수는 내부 강도 계산에만 쓰고 화면에는 사람이 이해할 의미를 보여준다.
        four_state = "기존 박스 상단을 반복 시험 중·단기 과열주의"
    elif slope > .015:
        four_state = "단기 상승"
    elif slope < -.015:
        four_state = "단기 하락"
    else:
        four_state = "횡보 확인"
    return {
        "generated_at": datetime.now(KST).isoformat(timespec="minutes"),
        "market": "KRW-BTC",
        "basis": {"daily_end": candle_close_kst(daily[-1], "day"), "four_hour_end": candle_close_kst(four[-1], "4h")},
        "price": price,
        "box": {"lookback_days": 30, "low": round(low), "high": round(high), "center": round(center), "position_pct": round(position * 100, 1), "buy_zone": [round(low), round(low + span * .15)], "sell_zone": [round(low + span * .70), round(high)]},
        "daily_state": state,
        "four_hour_state": four_state,
        "upper_test_count": upper_tests,
        "breakout_confirmed": breakout_confirmed,
        "retest_defended": retest_defended,
        "alt_policy": {**policy, "reason": f"BTC 일봉 {state} · 4시간봉 {four_state}"},
        "charts": {"day": chart_rows(daily, 60), "4h": chart_rows(four, 48)},
    }


def main() -> None:
    result = analyze(candles("day", 80), candles("4h", 80))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{result['daily_state']} / 알트 {result['alt_policy']['mode']} {result['alt_policy']['size_pct']}%")


if __name__ == "__main__":
    main()
