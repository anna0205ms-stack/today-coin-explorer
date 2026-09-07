from scanner.market_regime import apply_market_gate
from scanner.upbit_trade_plan import build_current_trade_plan


def candidate(price):
    return {
        "market": "KRW-TEST", "type": "A", "price": price,
        "entry": [958.0, 972.0], "stop": 934.0,
        "targets": [1030.0, 1085.0, 1140.0], "action": "확인 대기",
    }


def test_trade_plan_in_entry_zone_is_entry_review():
    row = build_current_trade_plan(candidate(965.0))
    assert row["trade_plan"]["status"] == "진입 검토"
    assert row["trade_plan"]["average_entry"] == 964.0
    assert row["trade_plan"]["target2"] == 1085.0


def test_trade_plan_above_entry_waits_for_pullback():
    row = build_current_trade_plan(candidate(1015.0))
    assert row["trade_plan"]["status"] == "눌림 대기"
    assert 4 < row["trade_plan"]["distance_pct"] < 5


def test_trade_plan_far_above_entry_forbids_chasing():
    row = candidate(1060.0)
    row["targets"] = [1120.0, 1180.0, 1240.0]
    assert build_current_trade_plan(row)["action"] == "추격 금지"


def test_trade_plan_below_stop_invalidates_structure():
    assert build_current_trade_plan(candidate(930.0))["action"] == "구조 무효"


def test_market_gate_remains_final_authority_and_keeps_pattern_action():
    row = build_current_trade_plan(candidate(965.0))
    gated = apply_market_gate(row, {"stage": "M0", "alt_entry_limit_pct": 0, "allowed_types": [], "reasons": ["위험장"]})
    assert gated["pattern_action"] == "진입 검토"
    assert gated["action"] == "시장 대기"
    assert gated["trade_plan"]["status"] == "진입 검토"
