"""차트 출력과 독립적으로 검증 가능한 실전 진입 안전규칙."""

from __future__ import annotations

import math
import os
from typing import Dict, List, Tuple


MIN_TARGET1_RR = float(os.getenv("UPBIT_MIN_TARGET1_RR", "1.0"))
LIVE_CHASE_PCT = float(os.getenv("UPBIT_LIVE_CHASE_PCT", "5.0"))
STOP_BUFFER_PCT = float(os.getenv("UPBIT_STOP_BUFFER_PCT", "3.0"))


def krw_tick_size(price: float) -> float:
    """2025-07-31 이후 업비트 KRW 마켓 호가 단위를 반환한다."""
    if price >= 1_000_000:
        return 1_000.0
    if price >= 500_000:
        return 500.0
    if price >= 100_000:
        return 100.0
    if price >= 50_000:
        return 50.0
    if price >= 10_000:
        return 10.0
    if price >= 5_000:
        return 5.0
    if price >= 100:
        return 1.0
    if price >= 10:
        return 0.1
    if price >= 1:
        return 0.01
    if price >= 0.1:
        return 0.001
    if price >= 0.01:
        return 0.0001
    if price >= 0.001:
        return 0.00001
    if price >= 0.0001:
        return 0.000001
    if price >= 0.00001:
        return 0.0000001
    return 0.00000001


def tick_price(value: float, mode: str = "nearest") -> float:
    """계획 가격을 실제 KRW 호가 단위에 맞춘다."""
    tick = krw_tick_size(value)
    units = value / tick
    if mode == "down":
        units = math.floor(units + 1e-10)
    elif mode == "up":
        units = math.ceil(units - 1e-10)
    else:
        units = round(units)
    return round(units * tick, 8)


def build_trade_plan(
    *,
    buy_low: float,
    buy_high: float,
    box_span: float,
    target1: float,
    target2: float,
    target3: float,
) -> Dict[str, object]:
    """하단으로 갈수록 비중을 늘리는 3회 분할매수 계획을 만든다.

    1차는 매수존 상단, 2차는 박스 하단에서 7.5%, 3차는 2.5% 지점이며
    비중은 30/30/40이다. 손절은 박스 하단 3% 아래로 고정한다.
    """
    raw_levels = [buy_high, buy_low + box_span * 0.075, buy_low + box_span * 0.025]
    levels = [tick_price(value, "down") for value in raw_levels]
    weights = [30, 30, 40]
    average = sum(level * weight for level, weight in zip(levels, weights)) / 100.0
    stop = tick_price(buy_low * (1.0 - STOP_BUFFER_PCT / 100.0), "down")
    targets = [tick_price(target1), tick_price(target2), tick_price(target3)]
    planned_average = tick_price(average)
    return {
        "entry_levels": levels,
        "entry_weights_pct": weights,
        "planned_average": planned_average,
        "stop": stop,
        "targets": targets,
        "target_weights_pct": [35, 35, 30],
        "first_target_rr": reward_risk(planned_average, stop, targets[0]),
        "final_target_rr": reward_risk(planned_average, stop, targets[2]),
    }


def reward_risk(entry: float, stop: float, target: float) -> float:
    """진입가에서 목표가까지의 보상/손실 비율을 안전하게 계산한다."""
    risk = entry - stop
    reward = target - entry
    if risk <= 0 or reward <= 0:
        return 0.0
    return reward / risk


def execution_gate(
    *,
    analysis_close: float,
    live_price: float,
    buy_low: float,
    buy_high: float,
    box_top: float,
    center_low: float,
    first_target_rr: float,
    flow: str,
) -> Tuple[str, List[str], float, float]:
    """일봉 후보와 장중 현재가를 분리해 실제 진입 전 행동을 정한다.

    일봉은 후보 선정의 기준으로 유지한다. 장중 현재가는 매수존을 벗어난
    추격 진입을 막는 실행 안전장치로만 사용하며 점수에는 넣지 않는다.
    최종 체결은 5분봉 지지 확인 후 사용자가 결정한다.
    """
    span = max(box_top - buy_low, 1e-9)
    live_position = (live_price - buy_low) / span * 100.0
    live_move = (live_price / analysis_close - 1.0) * 100.0 if analysis_close > 0 else 0.0
    reasons: List[str] = []

    if flow == "강한 하락":
        reasons.append("완성 일봉이 강한 하락 흐름")
    if first_target_rr < MIN_TARGET1_RR:
        reasons.append(f"1차 익절 손익비 {first_target_rr:.2f} < {MIN_TARGET1_RR:.2f}")
    if live_price < buy_low:
        reasons.append("장중 현재가가 박스 하단 이탈")
    elif live_price > buy_high:
        reasons.append("장중 현재가가 매수존 상단 초과")
    if live_price >= center_low:
        reasons.append("현재가가 중심존 이상 — 추격 금지")
    if live_move >= LIVE_CHASE_PCT and live_price > buy_high:
        reasons.append(f"완성 일봉 종가 대비 +{live_move:.1f}% 급등 — 추격 금지")
    if not (buy_low <= analysis_close <= buy_high):
        reasons.append("완성 일봉 종가가 매수존 밖")

    status = "5분봉 확인대기" if not reasons else "관망"
    return status, reasons, live_position, live_move
