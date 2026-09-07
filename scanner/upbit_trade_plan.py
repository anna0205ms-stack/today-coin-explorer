"""A~F 구조선을 현재 가격 기준의 공통 실전 매매계획으로 변환한다."""
from __future__ import annotations

from strategy_rules import reward_risk, tick_price

TYPE_LABEL = {
    "A": "첫 눌림 지지", "B": "박스 하단 지지", "C": "돌파선 재지지",
    "D": "재탈환선 지지", "E": "투매저점 방어", "F": "글로벌 매물대 지지",
}


def _numbers(values):
    return [float(value) for value in (values or []) if isinstance(value, (int, float)) and value > 0]


def build_current_trade_plan(row: dict) -> dict:
    out = dict(row)
    current = row.get("price")
    entries = _numbers(row.get("entry"))
    targets = _numbers(row.get("targets"))
    stop = row.get("stop")
    if not isinstance(current, (int, float)) or not entries or not isinstance(stop, (int, float)):
        out["trade_plan"] = {"current": current, "status": "계획값 확인", "reason": "진입·손절 구조선 자료 부족", "remain": "차트 구조 다시 계산", "entry_low": None, "entry_high": None, "average_entry": None, "stop": stop, "target1": None, "target2": None, "extension": None, "rr1": None, "distance_pct": None}
        return out

    low, high = min(entries), max(entries)
    mid = (low + high) / 2
    average = high * .30 + mid * .30 + low * .40
    target1 = targets[0] if targets else None
    target2 = targets[1] if len(targets) > 1 else None
    extension = targets[2] if len(targets) > 2 else None
    rr1 = reward_risk(average, float(stop), target1) if target1 else 0.0
    if low <= current <= high: distance = 0.0
    elif current > high: distance = (current / high - 1) * 100
    else: distance = -(low / current - 1) * 100
    risk_pct = (average - stop) / average * 100 if average > stop else 99.0
    label = TYPE_LABEL.get(str(row.get("type")), "핵심 지지")

    if current <= stop:
        status, remain = "구조 무효", "재진입 금지 · 새 구조 형성 대기"
    elif target1 and current >= target1:
        status, remain = "목표 접근·익절 우선", "신규 추격 금지 · 목표구간 분할 대응"
    elif distance == 0 and rr1 >= 1:
        status, remain = "진입 검토", f"{label} 반응 확인 후 분할 진입"
    elif distance == 0:
        status, remain = "확인 대기", "1차 목표까지 손익비 부족 · 추가 지지 확인"
    elif 0 < distance <= 3:
        status, remain = "확인 대기", "매수구간 접근 · 4시간봉 지지 확인"
    elif 0 < distance <= 8:
        status, remain = "눌림 대기", "현재 구조 안의 진입구간 재접근 대기"
    elif distance > 8:
        status, remain = "추격 금지", "현재가 추격 금지 · 새 눌림 구조 대기"
    else:
        status, remain = "재탈환 확인", f"진입구간 아래 · {label} 재탈환 확인"

    notes = [label, "현재 위치 양호" if abs(distance) <= 3 else "매수자리 이격", "손절 짧음" if risk_pct <= 6 else "손절폭 큼"]
    plan = {"current": tick_price(current), "status": status, "reason": " · ".join(notes), "remain": remain,
            "entry_low": tick_price(low, "down"), "entry_high": tick_price(high, "down"),
            "average_entry": tick_price(average), "stop": tick_price(stop, "down"),
            "target1": tick_price(target1) if target1 else None, "target2": tick_price(target2) if target2 else None,
            "extension": tick_price(extension) if extension else None, "rr1": round(rr1, 2),
            "distance_pct": round(distance, 2)}
    out["trade_plan"] = plan
    out["pattern_action"] = status
    out["action"] = status
    out["entry"] = [plan["entry_low"], plan["entry_high"]]
    out["stop"] = plan["stop"]
    out["targets"] = [value for value in (plan["target1"], plan["target2"], plan["extension"]) if value is not None]
    out["rr"] = plan["rr1"]
    return out
