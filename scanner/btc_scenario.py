#!/usr/bin/env python3
"""BTCUSDT 박스 상단 기준 양방향 시나리오를 판정하고 변화기록을 누적한다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bitcoin_regime import binance_candles

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
HISTORY = ROOT / "history" / "btc_scenario_history.json"
BINANCE = OUT / "binance" / "latest.json"
REGIME = OUT / "market_regime.json"
OUTPUT = OUT / "btc_scenario.json"

LABELS = {
    "UP_READY": "상승 준비",
    "UP_CONFIRMED": "상승 확인",
    "UP_ACCEL": "상승 가속",
    "DOWN_READY": "조정 확인 대기",
    "DOWN_CONFIRMED": "조정 확인",
    "DOWN_ACCEL": "조정 가속",
    "NEUTRAL": "방향 확인 중",
}


def read(path: Path, default):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def family(code: str | None) -> str:
    if str(code).startswith("UP_"):
        return "UP"
    if str(code).startswith("DOWN_"):
        return "DOWN"
    return "NEUTRAL"


def _higher_structure(rows: list[list]) -> bool:
    recent = rows[-3:]
    return len(recent) == 3 and float(recent[-1][2]) >= float(recent[0][2]) and float(recent[-1][3]) >= float(recent[0][3])


def _lower_structure(rows: list[list]) -> bool:
    recent = rows[-3:]
    return len(recent) == 3 and float(recent[-1][2]) <= float(recent[0][2]) and float(recent[-1][3]) <= float(recent[0][3])


def classify(rows: list[list], box: dict, correction: dict, previous_code: str | None = None) -> tuple[str, list[str]]:
    """완성 4시간봉만 사용하며 준비→확인→가속과 반대 시나리오 전환을 판정한다."""
    if len(rows) < 25:
        raise ValueError("BTC 4시간봉이 25개 이상 필요합니다")
    low, upper = float(box["low"]), float(box["high"])
    span = upper - low
    if span <= 0:
        raise ValueError("BTC 박스 폭이 올바르지 않습니다")
    down_line = upper * 0.98
    closes = [float(row[4]) for row in rows]
    last = rows[-1]
    close = closes[-1]
    volume = float(last[5])
    volume_avg = sum(float(row[5]) for row in rows[-25:-1]) / 24
    retest_defended = any(down_line <= float(row[3]) <= upper * 1.02 and float(row[4]) >= upper for row in rows[-3:])
    up_confirmed = close > upper and volume >= volume_avg * 1.2 and retest_defended
    failed_reclaim = any(down_line <= float(row[2]) <= upper * 1.02 and float(row[4]) < down_line for row in rows[-3:])
    two_below = closes[-1] < down_line and closes[-2] < down_line
    down_confirmed = close < down_line and (failed_reclaim or two_below)
    position = (close - low) / span
    slope = closes[-1] / closes[-4] - 1
    reasons = []

    # 확인·가속 상태는 반대편 확인 조건 또는 정식 무효선이 나오기 전까지 유지한다.
    # 준비 상태에는 이 고정 규칙을 적용하지 않아 최초 확인에 거래량·재지지를 반드시 요구한다.
    if previous_code in {"UP_CONFIRMED", "UP_ACCEL"} and not down_confirmed:
        if up_confirmed and closes[-2] > upper and _higher_structure(rows):
            return "UP_ACCEL", ["상단 위 4시간봉 연속 안착", "고점·저점 상승"]
        return "UP_CONFIRMED", ["상승 확인 상태 유지", "조정 확인 조건 미충족"]
    if previous_code in {"DOWN_CONFIRMED", "DOWN_ACCEL"} and not up_confirmed:
        if close > upper:
            return "UP_READY", ["조정 시나리오 무효", "상승 거래량·재지지 확인 대기"]
        defense1 = correction.get("defense1")
        if isinstance(defense1, (int, float)) and close < defense1 and _lower_structure(rows):
            return "DOWN_ACCEL", ["1차 목표 이탈", "반등 고점·저점 하락"]
        return "DOWN_CONFIRMED", ["조정 확인 상태 유지", "상승 확인 조건 미충족"]

    if up_confirmed:
        if family(previous_code) == "UP" and closes[-2] > upper and _higher_structure(rows):
            return "UP_ACCEL", ["상단 위 4시간봉 연속 안착", "고점·저점 상승"]
        return "UP_CONFIRMED", ["상단 4시간봉 종가 돌파", "거래량 1.2배 이상", "상단 재지지"]
    if down_confirmed:
        defense1 = correction.get("defense1")
        if family(previous_code) == "DOWN" and isinstance(defense1, (int, float)) and close < defense1 and _lower_structure(rows):
            return "DOWN_ACCEL", ["1차 목표 이탈", "반등 고점·저점 하락"]
        return "DOWN_CONFIRMED", ["조정 확인선 이탈", "되돌림 회복 실패" if failed_reclaim else "4시간봉 2개 연속 이탈"]
    if position >= 0.85 and slope >= -0.015:
        return "UP_READY", ["박스 상단 85% 이상 접근", "최근 4시간 구조 급락 아님"]
    if close < down_line:
        return "DOWN_READY", ["조정 확인선 아래 마감", "되돌림 확인 대기"]
    reasons.append("상승·조정 확정 조건 미충족")
    return "NEUTRAL", reasons


def alt_action(code: str, stage: str) -> str:
    fam = family(code)
    if fam == "UP":
        return {
            "M0": "BTC만 확인 · 알트 신규 진입 중단",
            "M1": "알트 대기",
            "M2": "A·C·D·F 눌림형 조건부",
            "M3": "확인된 후보 진입 확대",
            "M4": "확산 대응 · 급등 추격 금지",
            "M5": "상승 중이어도 분할익절",
        }.get(stage, "시장단계 확인 후 선별")
    if fam == "DOWN":
        return {
            "M0": "신규 진입 중단 · 현금 확대",
            "M1": "알트 비중 축소",
            "M2": "1차 목표 반등만 소액",
            "M3": "신규 진입 축소 · 보유분 보호",
            "M4": "강한 종목만 선별 유지",
            "M5": "과열 해소 조정 · 적극 보호",
        }.get(stage, "신규 진입 축소 · 방어 우선")
    return "방향 확인 전 추격 금지"


def build(rows: list[list], btc: dict, stage: str, previous_code: str | None = None) -> dict:
    box = btc.get("box") or {}
    correction = btc.get("correction") or {}
    code, reasons = classify(rows, box, correction, previous_code)
    low, upper = float(box["low"]), float(box["high"])
    width = upper - low
    down_line = upper * 0.98
    current = float(rows[-1][4])
    return {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "basis_four_hour_close": datetime.fromtimestamp(int(rows[-1][6]) / 1000, timezone.utc).astimezone(KST).isoformat(timespec="seconds"),
        "code": code,
        "label": LABELS[code],
        "family": family(code),
        "market_stage": stage,
        "price": round(current, 2),
        "btc_state": {
            "daily_state": btc.get("daily_state"),
            "four_hour_state": btc.get("four_hour_state"),
            "box_position_pct": btc.get("box", {}).get("position_pct"),
        },
        "reasons": reasons,
        "alt_action": alt_action(code, stage),
        "levels": {
            "box_low": round(low, 2),
            "box_high": round(upper, 2),
            "up_confirm": round(upper, 2),
            "down_confirm": round(down_line, 2),
            "retest_low": round(down_line, 2),
            "retest_high": round(upper, 2),
            "up_target1": round(upper + width * 0.25, 2),
            "up_target2": round(upper + width * 0.50, 2),
            "up_invalid": round(down_line, 2),
            "down_target1": correction.get("defense1"),
            "down_target2": correction.get("defense2"),
            "down_invalid": round(upper, 2),
            "structure_invalid": correction.get("invalid"),
        },
    }


def update_history(current: dict, history: dict) -> tuple[dict, dict | None]:
    history = history or {"current": None, "timeline": []}
    previous = history.get("current") or {}
    if previous.get("code") == current.get("code"):
        history["current"] = current
        history["updated_at"] = current.get("generated_at")
        return history, None
    previous_code = previous.get("code")
    invalidated = family(previous_code) if previous_code and family(previous_code) != family(current.get("code")) else None
    event = {
        "at": current.get("generated_at"),
        "from": previous_code,
        "from_label": previous.get("label"),
        "to": current.get("code"),
        "to_label": current.get("label"),
        "invalidated": invalidated if invalidated in {"UP", "DOWN"} else None,
        "price": current.get("price"),
        "market_stage": current.get("market_stage"),
        "reasons": current.get("reasons") or [],
        "alert": bool(previous_code),
    }
    history.setdefault("timeline", []).append(event)
    history["timeline"] = history["timeline"][-200:]
    history["current"] = current
    history["updated_at"] = current.get("generated_at")
    return history, event


def main() -> None:
    binance = read(BINANCE, {})
    btc = (binance.get("market_regime") or {}).get("btc") or {}
    if not btc.get("box"):
        raise ValueError("outputs/binance/latest.json의 BTC 박스가 없습니다")
    regime = read(REGIME, {})
    history = read(HISTORY, {"current": None, "timeline": []})
    previous_code = (history.get("current") or {}).get("code")
    current = build(binance_candles("4h", 80), btc, str(regime.get("stage") or "M?"), previous_code)
    history, event = update_history(current, history)
    OUTPUT.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    transition = f" · {event.get('from_label')} → {event.get('to_label')}" if event and event.get("alert") else ""
    print(f"BTC 시나리오 {current['label']}{transition}")


if __name__ == "__main__":
    main()
