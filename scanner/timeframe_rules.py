"""완성 분봉만 사용하는 멀티타임프레임 진입 판정 규칙."""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd


def _last(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    return frame.tail(count).copy()


def structure_intact(frame: pd.DataFrame, *, buy_low: float, stop: float) -> Tuple[bool, str]:
    """꼬리의 매수존 터치는 허용하되 손절가 저가 이탈과 하단 종가 이탈은 차단한다."""
    recent = _last(frame, 3)
    if len(recent) < 3:
        return False, "완성봉 3개 미만"
    if float(recent["Low"].min()) <= stop:
        return False, "최근 3개 봉 저가가 손절가 이탈"
    if float(recent["Close"].iloc[-1]) < buy_low:
        return False, "최근 완성봉 종가가 박스 하단 이탈"
    return True, "박스 하단 유지"


def decline_decelerated(frame: pd.DataFrame) -> Tuple[bool, str]:
    """15분봉의 가격·저가·거래량이 함께 악화될 때만 하락 가속으로 본다."""
    recent = _last(frame, 8)
    if len(recent) < 4:
        return False, "완성봉 4개 미만"
    last, prev, prev2 = recent.iloc[-1], recent.iloc[-2], recent.iloc[-3]
    last_return = float(last["Close"] / prev["Close"] - 1.0)
    prev_return = float(prev["Close"] / prev2["Close"] - 1.0)
    candle_range = max(float(last["High"] - last["Low"]), 1e-12)
    close_near_low = float(last["Close"] - last["Low"]) / candle_range <= 0.25
    median_volume = float(recent["Volume"].iloc[:-1].median())
    volume_expand = median_volume > 0 and float(last["Volume"]) >= median_volume * 1.2
    lower_low = float(last["Low"]) < float(prev["Low"])
    accelerating = last_return <= -0.005 and last_return < prev_return and close_near_low and volume_expand and lower_low
    if accelerating:
        return False, f"하락 가속 지속({last_return * 100:.2f}%)"
    return True, "하락 가속 중단 또는 미확인"


def five_minute_confirmation(frame: pd.DataFrame, *, buy_low: float, buy_high: float) -> Tuple[bool, List[str]]:
    """매수존 터치 후 종가 재진입·양봉 전환·직전 저점 미이탈을 모두 확인한다."""
    recent = _last(frame, 6)
    if len(recent) < 4:
        return False, ["완성봉 4개 미만"]
    last = recent.iloc[-1]
    prior = recent.iloc[-3:-1]
    reasons: List[str] = []
    touched = bool(((recent["Low"] <= buy_high) & (recent["High"] >= buy_low)).any())
    close_reentered = buy_low <= float(last["Close"]) <= buy_high
    bullish_turn = float(last["Close"]) > float(last["Open"]) and float(last["Close"]) > float(recent["Close"].iloc[-2])
    prior_low_intact = float(last["Low"]) >= float(prior["Low"].min())
    if not touched:
        reasons.append("최근 6개 5분봉이 매수존 미접촉")
    if not close_reentered:
        reasons.append("최근 5분봉 종가가 매수존 안에 없음")
    if not bullish_turn:
        reasons.append("양봉 전환·직전 종가 회복 미확인")
    if not prior_low_intact:
        reasons.append("직전 2개 봉 저점 이탈")
    return not reasons, reasons


def attraction_signature(frame5: pd.DataFrame, frame15: pd.DataFrame) -> str:
    """사용자의 반복 진입 성향을 학습용 태그로 구분한다."""
    f5 = _last(frame5, 20)
    f15 = _last(frame15, 6)
    if len(f5) < 5 or len(f15) < 4:
        return "판정자료부족"
    span5 = float(f5["High"].max() - f5["Low"].min())
    pos5 = (float(f5["Close"].iloc[-1]) - float(f5["Low"].min())) / span5 * 100.0 if span5 > 0 else 50.0
    impulse15 = float(f15["High"].max() / f15["Low"].min() - 1.0) * 100.0
    pullback = float(f5["Close"].iloc[-1]) < float(f5["High"].max())
    if impulse15 >= 5.0 and pullback and pos5 >= 55:
        return "급등후첫눌림·추격주의"
    if pos5 <= 35:
        return "단기박스하단·되돌림매수"
    if pos5 >= 70:
        return "단기박스상단·추격주의"
    return "박스중단·반등기대"


def multi_timeframe_gate(
    *,
    daily_status: str,
    frames: Dict[int, pd.DataFrame],
    buy_low: float,
    buy_high: float,
    stop: float,
) -> Dict[str, object]:
    """4H→1H→15m→5m 순서로 최종 진입 상태를 계산한다."""
    required = [240, 60, 15, 5]
    missing = [unit for unit in required if unit not in frames or frames[unit].empty]
    reasons: List[str] = []
    if daily_status != "5분봉 확인대기":
        reasons.append("일봉·현재가 안전조건 미통과")
    if missing:
        reasons.append("분봉 데이터 부족: " + ",".join(str(unit) for unit in missing))
        return {"status": "관망", "reasons": reasons, "states": {}, "signature": "판정자료부족"}

    intact4h, reason4h = structure_intact(frames[240], buy_low=buy_low, stop=stop)
    intact1h, reason1h = structure_intact(frames[60], buy_low=buy_low, stop=stop)
    stopped15, reason15 = decline_decelerated(frames[15])
    confirmed5, reasons5 = five_minute_confirmation(frames[5], buy_low=buy_low, buy_high=buy_high)
    states = {
        "4h": reason4h,
        "1h": reason1h,
        "15m": reason15,
        "5m": "진입 확인" if confirmed5 else " / ".join(reasons5),
    }
    if not intact4h:
        reasons.append("4시간봉 하단 훼손")
    if not intact1h:
        reasons.append("1시간봉 하단 훼손")
    if not stopped15:
        reasons.append("15분봉 하락 가속")
    if daily_status == "5분봉 확인대기" and intact4h and intact1h and stopped15:
        status = "진입조건충족" if confirmed5 else "5분봉 확인대기"
    else:
        status = "관망"
    return {
        "status": status,
        "reasons": reasons + ([] if confirmed5 else reasons5),
        "states": states,
        "signature": attraction_signature(frames[5], frames[15]),
    }
