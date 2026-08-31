#!/usr/bin/env python3
"""최신 A/B/C/D/E/F 결과를 단일 JSON 파일에 계속 누적한다."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market_regime import apply_market_gate

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
STORE = ROOT / "history" / "snapshots.json"
MARKET_REGIME = OUTPUTS / "market_regime.json"


def read_json(path: Path, default):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def abc_type(row: dict) -> str:
    tag = str(row.get("진입성향태그", ""))
    if "급등후첫눌림" in tag:
        return "A"
    if "박스하단" in tag or "박스중단" in tag:
        return "B"
    if "박스상단" in tag:
        return "C"
    return "OTHER"


def normalize_abc(row: dict) -> dict:
    entry = [row.get("진입구간하단"), row.get("진입구간상단")]
    price, stop, target = row.get("현재가"), row.get("손절가"), row.get("일차익절_35pct")
    valid_entry = [x for x in entry if isinstance(x, (int, float))]
    entry_mid = sum(valid_entry) / len(valid_entry) if valid_entry else None
    rr = (target - entry_mid) / (entry_mid - stop) if all(isinstance(x, (int, float)) for x in (target, entry_mid, stop)) and entry_mid > stop else None
    action = "진입 검토" if row.get("실전진입판정") == "진입조건충족" else "확인 대기" if row.get("실전진입판정") == "5분봉 확인대기" else "진입가 대기"
    return {
        "market": row.get("코드"), "name": row.get("종목명"), "type": abc_type(row),
        "score": row.get("점수", 0), "status": row.get("실전진입판정", "관망"),
        "price": price, "entry": entry, "stop": stop,
        "targets": [row.get("일차익절_35pct"), row.get("이차익절_35pct"), row.get("최종목표_30pct")],
        "flow": row.get("흐름판정"), "action": action,
        "reason": row.get("진입성향태그") or row.get("흐름판정"),
        "missing": [] if action == "진입 검토" else [row.get("실전진입판정") or "하위 시간봉 확인"],
        "rr": round(rr, 2) if rr is not None else None,
    }


def normalize_d(row: dict) -> dict:
    status = row.get("status")
    action = {"진입확인": "진입 검토", "선매수감시": "확인 대기", "준비": "진입가 대기", "늦음·추격금지": "추격 금지"}.get(status, "진입가 대기")
    passed = [name for name, ok in (row.get("checks") or {}).items() if ok]
    return {
        "market": row.get("market"), "name": str(row.get("market", "")).replace("KRW-", ""), "type": "D",
        "score": row.get("score", 0), "status": status,
        "d_stage": row.get("d_stage", "D0"),
        "d_stage_label": row.get("d_stage_label", "단계 미분류"),
        "d_stage_reason": row.get("d_stage_reason", ""),
        "price": row.get("last_completed_4h_close"),
        "entry": row.get("aggressive_entry_zone") or row.get("confirmation_entry_zone") or [],
        "stop": row.get("hard_stop"), "targets": row.get("targets") or [],
        "flow": ", ".join(row.get("missing_conditions", [])) or "조건충족",
        "action": action, "reason": " · ".join(passed),
        "missing": row.get("missing_conditions") or [], "rr": row.get("first_target_rr"),
    }


def normalize_e(row: dict) -> dict:
    """E형의 단일 0.382 전량청산 계획을 공통 후보 형식으로 옮긴다."""
    return {
        "market": row.get("market"), "name": row.get("name"), "type": "E",
        "score": row.get("score", 0), "status": row.get("status"),
        "price": row.get("price"), "entry": row.get("entry") or [],
        "stop": row.get("stop"), "targets": row.get("targets") or [],
        "flow": row.get("flow"), "action": row.get("action", "확인 대기"),
        "reason": row.get("reason"), "missing": row.get("missing") or [],
        "rr": row.get("rr"), "fib": row.get("fib") or {},
        "exit_rule": row.get("exit_rule"), "invalidation": row.get("invalidation"),
    }


def normalize_f(row: dict) -> dict:
    """F형 글로벌 과거 매물대 판정을 공통 후보 형식으로 옮긴다."""
    return {
        "market": row.get("market"), "name": row.get("name"), "type": "F",
        "score": row.get("score", 0), "status": row.get("status"),
        "f_stage": row.get("f_stage"), "f_stage_label": row.get("f_stage_label"),
        "f2_zone_position": row.get("f2_zone_position"),
        "f2_zone_position_pct": row.get("f2_zone_position_pct"),
        "f2_zone_mid": row.get("f2_zone_mid"),
        "price": row.get("price"), "entry": row.get("entry") or [],
        "stop": row.get("stop"), "targets": row.get("targets") or [],
        "flow": row.get("flow"), "action": row.get("action", "확인 대기"),
        "reason": row.get("reason"), "missing": row.get("missing") or [],
        "rr": row.get("rr"), "global_zone": row.get("global_zone") or {},
        "binance_symbol": row.get("binance_symbol"), "binance_price": row.get("binance_price"),
    }


def completed_4h_at(now: datetime) -> datetime:
    """KST 01/05/09/13/17/21시 중 가장 최근 마감 시각을 반환한다."""
    now = now.astimezone(KST)
    today_slots = [now.replace(hour=h, minute=0, second=0, microsecond=0) for h in (1, 5, 9, 13, 17, 21)]
    past = [slot for slot in today_slots if slot <= now]
    return max(past) if past else (now - timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)


def append_snapshot(at: datetime | None = None) -> dict:
    at = completed_4h_at(at or datetime.now(KST))
    abc_rows = read_json(OUTPUTS / "latest_scan.json", [])
    d_rows = read_json(OUTPUTS / "pre_breakout_reclaim.json", [])
    e_rows = read_json(OUTPUTS / "technical_rebound.json", [])
    f_rows = read_json(OUTPUTS / "global_supply.json", [])
    candidates = [normalize_abc(r) for r in abc_rows if abc_type(r) in "ABC"]
    candidates += [normalize_d(r) for r in d_rows if r.get("status") not in {"제외", "자료부족", "오류"}]
    candidates += [normalize_e(r) for r in e_rows if r.get("status") != "E실패"]
    candidates += [normalize_f(r) for r in f_rows]
    market_regime = read_json(MARKET_REGIME, {})
    if market_regime.get("stage"):
        candidates = [apply_market_gate(row, market_regime) for row in candidates]
    chart_cache = read_json(OUTPUTS / "chart_cache.json", {})
    for row in candidates:
        if row.get("market") in chart_cache:
            row["charts"] = chart_cache[row["market"]]
    payload = {
        "snapshot_at": at.isoformat(), "date": at.strftime("%Y-%m-%d"), "time": at.strftime("%H:%M"),
        "counts": {k: sum(r["type"] == k for r in candidates) for k in "ABCDEF"},
        "candidates": candidates,
    }
    if market_regime:
        payload["market_regime"] = market_regime
    btc = read_json(OUTPUTS / "bitcoin_regime.json", {})
    if btc:
        payload["btc"] = {k: btc.get(k) for k in ("price", "daily_state", "four_hour_state", "box", "basis")}
        payload["alt_policy"] = btc.get("alt_policy", {})
    STORE.parent.mkdir(parents=True, exist_ok=True)
    records = read_json(STORE, [])
    by_time = {record.get("snapshot_at"): record for record in records}
    by_time[payload["snapshot_at"]] = payload
    records = sorted(by_time.values(), key=lambda record: record.get("snapshot_at", ""))
    STORE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--at", help="KST ISO datetime; 생략하면 최근 완성 4시간봉")
    args = parser.parse_args()
    at = datetime.fromisoformat(args.at) if args.at else None
    if at and at.tzinfo is None:
        at = at.replace(tzinfo=KST)
    saved = append_snapshot(at)
    print(f'{STORE} · {saved["snapshot_at"]} · {len(saved["candidates"])} candidates')


if __name__ == "__main__":
    main()
