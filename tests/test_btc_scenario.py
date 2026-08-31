import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

import btc_scenario
import kakao_notifier


BOX = {"low": 60.0, "high": 80.0}
CORRECTION = {"defense1": 69.0, "defense2": 63.0, "invalid": 58.0}


def rows(closes, volumes=None, lows=None, highs=None):
    volumes = volumes or [100.0] * len(closes)
    lows = lows or [value - 1 for value in closes]
    highs = highs or [value + 1 for value in closes]
    return [[i, closes[i], highs[i], lows[i], closes[i], volumes[i], (i + 1) * 14_400_000] for i in range(len(closes))]


def base(value=75.0, count=30):
    return [value] * count


def test_up_ready_near_box_top_without_confirmation():
    code, _ = btc_scenario.classify(rows(base(79.0)), BOX, CORRECTION)
    assert code == "UP_READY"


def test_up_confirmation_requires_close_volume_and_retest():
    closes = base(77.0)
    closes[-1] = 81.0
    volumes = [100.0] * 30
    volumes[-1] = 150.0
    lows = [value - 1 for value in closes]
    lows[-1] = 79.2
    code, reasons = btc_scenario.classify(rows(closes, volumes, lows), BOX, CORRECTION)
    assert code == "UP_CONFIRMED"
    assert "거래량 1.2배 이상" in reasons


def test_up_acceleration_needs_existing_up_state_and_higher_structure():
    closes = base(77.0)
    closes[-3:] = [80.5, 81.0, 82.0]
    volumes = [100.0] * 30
    volumes[-1] = 150.0
    lows = [value - 1 for value in closes]
    highs = [value + 1 for value in closes]
    lows[-3:] = [79.0, 80.0, 80.5]
    highs[-3:] = [81.0, 82.0, 83.0]
    code, _ = btc_scenario.classify(rows(closes, volumes, lows, highs), BOX, CORRECTION, "UP_CONFIRMED")
    assert code == "UP_ACCEL"


def test_down_ready_before_failed_reclaim_confirmation():
    closes = base(79.0)
    closes[-1] = 77.5
    highs = [value + 1 for value in closes]
    highs[-1] = 77.9
    code, _ = btc_scenario.classify(rows(closes, highs=highs), BOX, CORRECTION)
    assert code == "DOWN_READY"


def test_down_confirmation_by_two_completed_closes():
    closes = base(79.0)
    closes[-2:] = [77.8, 77.2]
    code, _ = btc_scenario.classify(rows(closes), BOX, CORRECTION)
    assert code == "DOWN_CONFIRMED"


def test_down_acceleration_below_first_target_with_lower_structure():
    closes = base(79.0)
    closes[-3:] = [71.0, 69.0, 67.0]
    lows = [value - 1 for value in closes]
    highs = [value + 1 for value in closes]
    code, _ = btc_scenario.classify(rows(closes, lows=lows, highs=highs), BOX, CORRECTION, "DOWN_CONFIRMED")
    assert code == "DOWN_ACCEL"


def test_confirmed_up_does_not_flip_during_unconfirmed_noise():
    closes = base(79.0)
    closes[-1] = 79.5
    code, _ = btc_scenario.classify(rows(closes), BOX, CORRECTION, "UP_CONFIRMED")
    assert code == "UP_CONFIRMED"


def test_confirmed_down_is_invalid_only_after_upper_recovery():
    closes = base(79.0)
    closes[-1] = 80.5
    code, reasons = btc_scenario.classify(rows(closes), BOX, CORRECTION, "DOWN_CONFIRMED")
    assert code == "UP_READY"
    assert "조정 시나리오 무효" in reasons


def test_history_baseline_does_not_alert_then_records_invalidating_change():
    first = {"generated_at": "2026-08-31T09:00:00+09:00", "code": "UP_CONFIRMED", "label": "상승 확인", "price": 81.0, "market_stage": "M2", "reasons": []}
    history, event = btc_scenario.update_history(first, {})
    assert event["alert"] is False
    second = {"generated_at": "2026-08-31T13:00:00+09:00", "code": "DOWN_CONFIRMED", "label": "조정 확인", "price": 77.0, "market_stage": "M1", "reasons": ["되돌림 실패"]}
    history, event = btc_scenario.update_history(second, history)
    assert event["invalidated"] == "UP" and event["alert"] is True
    pending = kakao_notifier.pending_btc_transitions(history, set())
    assert len(pending) == 1
    assert kakao_notifier.pending_btc_transitions(history, {pending[0]["event_id"]}) == []
