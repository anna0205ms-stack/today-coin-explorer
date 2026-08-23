#!/usr/bin/env python3
"""BTC 구조와 글로벌 자금 흐름을 합쳐 M0~M5 시장 단계와 A~E 게이트를 만든다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUTPUT = OUT / "market_regime.json"
SNAPSHOTS = ROOT / "history" / "snapshots.json"

STAGES = {
    "M0": ("위험장", "코인을 새로 사면 안 되는 장", 0),
    "M1": ("BTC만 강함", "비트코인만 오르고 알트는 힘이 없는 장", 20),
    "M2": ("알트 준비", "알트가 버티기 시작해 후보를 골라둘 장", 35),
    "M3": ("알트 시작", "돈이 비트코인에서 대형 알트로 이동하기 시작한 장", 65),
    "M4": ("알트 확산", "여러 알트가 함께 오르기 좋은 장", 85),
    "M5": ("과열 경계", "뒤늦게 따라 사지 말고 수익을 챙길 장", 15),
}

GATE_RULES = {
    "M0": {"A": ("BLOCK", "시장 하락에서 첫 눌림은 추가 하락 위험"), "B": ("BLOCK", "바닥 확인 전에는 추세반전으로 보지 않음"), "C": ("BLOCK", "돌파 실패 가능성이 높은 위험장"), "D": ("BLOCK", "재탈환이 나와도 시장 확인 전에는 대기"), "E": ("CONDITIONAL", "극단적 과매도와 반등 확인 때만 최소 비중")},
    "M1": {"A": ("CONDITIONAL", "BTC보다 강한 독립 종목만"), "B": ("BLOCK", "알트 전반이 약해 바닥잡기 금지"), "C": ("CONDITIONAL", "거래량 돌파와 재지지 모두 필요"), "D": ("WATCH", "재탈환 후보를 미리 모으는 단계"), "E": ("CONDITIONAL", "급락 종목의 짧은 반등만")},
    "M2": {"A": ("CONDITIONAL", "첫 눌림 지지 확인 후 작은 비중"), "B": ("CONDITIONAL", "바닥 방어와 고점 상승을 모두 확인"), "C": ("CONDITIONAL", "돌파보다 재지지 확인을 우선"), "D": ("WATCH", "D1~D2 후보를 미리 선별"), "E": ("CONDITIONAL", "시장 추세 매매와 별도로 짧게")},
    "M3": {"A": ("ALLOW", "첫 눌림 지지가 확인되면 진입"), "B": ("CONDITIONAL", "대형 알트 강세가 해당 종목까지 번지는지 확인"), "C": ("ALLOW", "돌파선 재지지에서 진입"), "D": ("ALLOW", "D2~D3 재탈환 후보 우선"), "E": ("WATCH", "정상 상승형이 더 유리한 단계")},
    "M4": {"A": ("ALLOW", "첫 눌림 지지가 확인되면 진입"), "B": ("CONDITIONAL", "못 오른 후발주가 아닌지 재확인"), "C": ("ALLOW", "상단 재지지 때 추격 없이 진입"), "D": ("ALLOW", "D2~D3 확인 후보를 우선"), "E": ("WATCH", "상승장에서는 정상 추세형을 우선")},
    "M5": {"A": ("PROTECT", "신규매수보다 보유 물량 수익 보호"), "B": ("BLOCK", "못 오른 종목을 후발주로 착각하지 않기"), "C": ("PROTECT", "재지지 실패 시 빠르게 정리"), "D": ("BLOCK", "급등 전 후보가 아니라 분배 구간일 수 있음"), "E": ("CONDITIONAL", "개별 급락의 0.382 반등만 짧게")},
}

GATE_LABELS = {"ALLOW": "진입 허용", "CONDITIONAL": "조건부", "WATCH": "관찰만", "BLOCK": "신규 금지", "PROTECT": "익절 우선"}


def read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _maybe_num(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _previous_stage() -> str | None:
    records = read(SNAPSHOTS, [])
    if not records:
        return None
    regime = records[-1].get("market_regime") or {}
    return regime.get("stage")


def classify_market(btc: dict, global_data: dict, previous_stage: str | None = None) -> tuple[str, int, list[str]]:
    if global_data.get("status") != "ok":
        return "M0", 100, ["BTC.D·TOTAL2·OTHERS 데이터가 최신이 아니어서 안전 차단"]

    daily = str(btc.get("daily_state") or "")
    four = str(btc.get("four_hour_state") or "")
    btcd24 = _num((global_data.get("btc_d") or {}).get("change_24h_pct_point"))
    btcd4 = _maybe_num((global_data.get("btc_d") or {}).get("change_4h_pct_point"))
    total2 = _num((global_data.get("total2") or {}).get("change_24h_pct"))
    others = _num((global_data.get("others") or {}).get("change_24h_pct"))
    total2_4 = _maybe_num((global_data.get("total2") or {}).get("change_4h_pct"))
    others_4 = _maybe_num((global_data.get("others") or {}).get("change_4h_pct"))
    btc24 = _num((global_data.get("btc") or {}).get("price_change_24h_pct"))
    breadth = _maybe_num((global_data.get("breadth") or {}).get("positive_ratio_24h_pct"))
    median_alt = _maybe_num((global_data.get("breadth") or {}).get("median_change_24h_pct"))
    structural_risk = "이탈" in daily or "돌파 실패" in four
    breadth_weak = breadth is None or breadth <= 40
    breadth_alive = breadth is None or breadth >= 50
    breadth_broad = breadth is None or breadth >= 60
    flow_crash_24h = total2 <= -2 and others <= -2.5 and breadth_weak
    flow_crash_4h = total2_4 is not None and others_4 is not None and total2_4 <= -1.2 and others_4 <= -1.8
    breadth_text = f"상위 10개 밖 알트 상승 비율 {breadth:.0f}% · 중앙값 {median_alt:+.1f}%" if breadth is not None and median_alt is not None else "알트 상승 종목 비율 확인 전"

    if structural_risk:
        return "M0", 92, [f"BTC 구조 훼손: 일봉 {daily} · 4시간봉 {four}", "BTC 구조가 먼저 무너져 신규 알트 진입을 차단"]
    if flow_crash_24h or flow_crash_4h or (btc24 < -2 and btcd24 > 0.15 and breadth_weak):
        return "M0", 88, [f"알트 자금 동반 이탈: TOTAL2 {total2:+.1f}% · OTHERS {others:+.1f}%", breadth_text]
    if previous_stage == "M4" and ((btcd4 is not None and btcd4 >= 0.15) or (others_4 is not None and others_4 <= -1.5)):
        return "M5", 78, ["직전 M4 이후 4시간 과열 종료 신호", f"BTC.D 4H {(btcd4 or 0):+.2f}%p · OTHERS 4H {(others_4 or 0):+.1f}%"]
    if btcd24 <= -0.20 and total2 >= 1.5 and others >= 2.0 and others >= total2 + 0.3 and breadth_broad:
        return "M4", 86, [f"BTC.D {btcd24:+.2f}%p · TOTAL2 {total2:+.1f}% · OTHERS {others:+.1f}%", breadth_text]
    if btcd24 <= -0.10 and total2 >= 0.5 and others >= -0.2 and breadth_alive:
        return "M3", 82, [f"BTC.D {btcd24:+.2f}%p · TOTAL2 {total2:+.1f}% · OTHERS {others:+.1f}%", breadth_text]
    if btc24 > 0.5 and btcd24 >= 0.10 and (total2 < btc24 or others < total2) and (breadth is None or breadth <= 50):
        return "M1", 78, [f"BTC {btc24:+.1f}%와 BTC.D {btcd24:+.2f}%p가 함께 상승", f"알트 확산 부족 · {breadth_text}"]
    return "M2", 70, [f"BTC.D {btcd24:+.2f}%p · TOTAL2 {total2:+.1f}% · OTHERS {others:+.1f}%", f"알트 순환 확정 전 · {breadth_text}"]


def apply_market_gate(candidate: dict, regime: dict) -> dict:
    row = dict(candidate)
    pattern_action = row.get("pattern_action") or row.get("action") or "진입가 대기"
    code, reason = GATE_RULES[regime["stage"]].get(row.get("type"), ("BLOCK", "시장 단계와 맞지 않음"))
    final_action = pattern_action
    if pattern_action == "추격 금지":
        final_action = pattern_action
    elif code == "BLOCK":
        final_action = "시장 대기"
    elif code == "WATCH" and pattern_action == "진입 검토":
        final_action = "시장 대기"
    elif code == "CONDITIONAL" and pattern_action == "진입 검토":
        final_action = "조건부 진입"
    elif code == "PROTECT":
        final_action = "익절 우선"
    row.update(
        {
            "pattern_action": pattern_action,
            "action": final_action,
            "market_gate": {
                "code": code,
                "label": GATE_LABELS[code],
                "reason": reason,
                "stage": regime["stage"],
                "entry_allowed": code in {"ALLOW", "CONDITIONAL"} and pattern_action != "추격 금지",
            },
        }
    )
    return row


def build_regime(btc: dict, global_data: dict, previous_stage: str | None = None) -> dict:
    stage, confidence, reasons = classify_market(btc, global_data, previous_stage)
    name, plain, limit = STAGES[stage]
    four = str(btc.get("four_hour_state") or "")
    if "과열주의" in four and stage in {"M2", "M3", "M4"}:
        limit = min(limit, 45)
        confidence = min(confidence, 78)
        reasons.append("BTC는 상단 과열 구간 · 알트 펌핑은 인정하되 추격 대신 눌림만 선별")
    gates = {key: {"code": code, "label": GATE_LABELS[code], "reason": reason} for key, (code, reason) in GATE_RULES[stage].items()}
    return {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "stage": stage,
        "name": name,
        "plain": plain,
        "confidence": confidence,
        "alt_entry_limit_pct": limit,
        "reasons": reasons,
        "gates": gates,
        "data_status": global_data.get("status", "missing"),
        "source": global_data.get("source", "missing"),
    }


def main() -> None:
    regime = build_regime(read(OUT / "bitcoin_regime.json", {}), read(OUT / "global_market_data.json", {}), _previous_stage())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(regime, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"시장 {regime['stage']} {regime['name']} · 신규진입 {regime['alt_entry_limit_pct']}%")


if __name__ == "__main__":
    main()
