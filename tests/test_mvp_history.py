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
