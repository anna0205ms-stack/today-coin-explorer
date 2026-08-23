import pytest

from scanner.market_regime import apply_market_gate, build_regime, classify_market


def flow(*, btcd=0.0, btcd4=0.0, total2=0.0, others=0.0, btc=0.0, status="ok"):
    return {
        "status": status,
        "source": "test",
        "btc": {"price_change_24h_pct": btc},
        "btc_d": {"change_24h_pct_point": btcd, "change_4h_pct_point": btcd4},
        "total2": {"change_24h_pct": total2},
        "others": {"change_24h_pct": others},
    }


@pytest.mark.parametrize(
    ("global_data", "previous", "expected"),
    [
        (flow(status="stale"), None, "M0"),
        (flow(btcd=.2, total2=.5, others=.1, btc=2), None, "M1"),
        (flow(btcd=0, total2=.2, others=.1, btc=.1), None, "M2"),
        (flow(btcd=-.15, total2=.8, others=.4, btc=.3), None, "M3"),
        (flow(btcd=-.3, total2=2, others=2.5, btc=.5), None, "M4"),
        (flow(btcd=-.1, btcd4=.2, total2=.5, others=.2, btc=.2), "M4", "M5"),
    ],
)
def test_market_stage_rules(global_data, previous, expected):
    stage, _, _ = classify_market({"daily_state": "박스 중심", "four_hour_state": "횡보"}, global_data, previous)
    assert stage == expected


def test_gate_preserves_pattern_action_and_applies_final_action():
    regime = build_regime({}, flow(btcd=-.15, total2=.8, others=.4))
    gated = apply_market_gate({"type": "B", "action": "진입 검토"}, regime)

    assert regime["stage"] == "M3"
    assert gated["pattern_action"] == "진입 검토"
    assert gated["action"] == "조건부 진입"
    assert gated["market_gate"]["entry_allowed"] is True


def test_safety_action_is_never_weakened_by_market_gate():
    regime = build_regime({}, flow(status="stale"))
    gated = apply_market_gate({"type": "A", "action": "추격 금지"}, regime)

    assert gated["action"] == "추격 금지"
    assert gated["market_gate"]["entry_allowed"] is False


def test_alt_breadth_prevents_false_m0_and_detects_rotation():
    global_data = flow(btcd=-.12, total2=.39, others=.33, btc=0)
    global_data["breadth"] = {"positive_ratio_24h_pct": 60, "median_change_24h_pct": .4}

    stage, _, reasons = classify_market(
        {"daily_state": "상단 돌파 시도", "four_hour_state": "상단 20회 접촉·과열주의"},
        global_data,
    )

    assert stage == "M3"
    assert any("상승 비율 60%" in reason for reason in reasons)


def test_btc_overheat_caps_m3_entry_limit_without_forcing_m0():
    global_data = flow(btcd=-.12, total2=.39, others=.33, btc=0)
    global_data["breadth"] = {"positive_ratio_24h_pct": 60, "median_change_24h_pct": .4}

    regime = build_regime(
        {"daily_state": "상단 돌파 시도", "four_hour_state": "상단 20회 접촉·과열주의"},
        global_data,
    )

    assert regime["stage"] == "M3"
    assert regime["alt_entry_limit_pct"] == 45
    assert any("알트 펌핑은 인정" in reason for reason in regime["reasons"])
