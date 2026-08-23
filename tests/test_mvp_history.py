import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
import history_store


def test_completed_4h_slot():
    at = datetime(2026, 8, 22, 17, 12, tzinfo=history_store.KST)
    assert history_store.completed_4h_at(at).strftime("%Y-%m-%d %H:%M") == "2026-08-22 17:00"


def test_append_deduplicates_same_slot(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "latest_scan.json").write_text("[]", encoding="utf-8")
    (outputs / "pre_breakout_reclaim.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(history_store, "OUTPUTS", outputs)
    monkeypatch.setattr(history_store, "STORE", tmp_path / "history" / "snapshots.json")
    at = datetime(2026, 8, 22, 17, 12, tzinfo=history_store.KST)
    history_store.append_snapshot(at)
    history_store.append_snapshot(at)
    records = json.loads(history_store.STORE.read_text(encoding="utf-8"))
    assert len(records) == 1
    assert records[0]["time"] == "17:00"


def test_append_applies_market_gate_to_candidate(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "latest_scan.json").write_text(
        json.dumps([
            {
                "코드": "KRW-TEST", "종목명": "TEST", "진입성향태그": "급등후첫눌림",
                "실전진입판정": "진입조건충족", "현재가": 100,
                "진입구간하단": 95, "진입구간상단": 100, "손절가": 90,
                "일차익절_35pct": 110, "이차익절_35pct": 120, "최종목표_30pct": 130,
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    (outputs / "pre_breakout_reclaim.json").write_text("[]", encoding="utf-8")
    regime = {
        "stage": "M0", "name": "위험장", "alt_entry_limit_pct": 0,
        "gates": {"A": {"code": "BLOCK", "label": "신규 금지", "reason": "위험장"}},
    }
    market_path = outputs / "market_regime.json"
    market_path.write_text(json.dumps(regime, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(history_store, "OUTPUTS", outputs)
    monkeypatch.setattr(history_store, "MARKET_REGIME", market_path)
    monkeypatch.setattr(history_store, "STORE", tmp_path / "history" / "snapshots.json")

    saved = history_store.append_snapshot(datetime(2026, 8, 22, 17, 12, tzinfo=history_store.KST))

    candidate = saved["candidates"][0]
    assert candidate["pattern_action"] == "진입 검토"
    assert candidate["action"] == "시장 대기"
    assert candidate["market_gate"]["entry_allowed"] is False
