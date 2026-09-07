import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

import outcome_tracker
import unified_dashboard


def candle(at, high, low):
    return {"at": at, "high": high, "low": low}


def test_outcome_ignores_candles_before_detection():
    start = datetime(2026, 9, 1, 9, tzinfo=outcome_tracker.KST)
    row = {"entry": [100, 105], "stop": 90, "targets": [120]}
    candles = [
        candle(start - timedelta(hours=4), 130, 80),
        candle(start, 110, 100),
        candle(start + timedelta(hours=4), 121, 106),
    ]
    result = outcome_tracker.evaluate(row, candles, start, start + timedelta(hours=24))
    assert result["status"] == "1차 목표 성공"
    assert result["entry_at"] == start.isoformat()


def test_same_candle_target_and_stop_is_conservative_stop():
    start = datetime(2026, 9, 1, 9, tzinfo=outcome_tracker.KST)
    row = {"entry": [100, 105], "stop": 90, "targets": [120]}
    result = outcome_tracker.evaluate(
        row, [candle(start, 125, 85)], start, start + timedelta(hours=24)
    )
    assert result["status"] == "손절 도달"


def test_repeated_candidate_is_one_episode_within_eight_hours():
    base = datetime(2026, 9, 1, 9, tzinfo=outcome_tracker.KST)
    row = {"market": "KRW-TEST", "type": "A"}
    records = [
        {"snapshot_at": base.isoformat(), "candidates": [row]},
        {"snapshot_at": (base + timedelta(hours=4)).isoformat(), "candidates": [row]},
        {"snapshot_at": (base + timedelta(hours=12)).isoformat(), "candidates": [row]},
    ]
    assert len(unified_dashboard.candidate_episodes(records)) == 1


def test_candidate_reappearing_after_gap_starts_new_episode():
    base = datetime(2026, 9, 1, 9, tzinfo=outcome_tracker.KST)
    row = {"market": "KRW-TEST", "type": "A"}
    records = [
        {"snapshot_at": base.isoformat(), "candidates": [row]},
        {"snapshot_at": (base + timedelta(hours=12)).isoformat(), "candidates": [row]},
    ]
    assert len(unified_dashboard.candidate_episodes(records)) == 2
