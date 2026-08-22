from scanner.bitcoin_regime import classify


def test_buy_zone_allows_full_size():
    state, policy = classify(.10, False, False)
    assert state == "박스 하단 매수존"
    assert policy["size_pct"] == 100


def test_sell_zone_stops_new_alt_entries():
    state, policy = classify(.75, False, False)
    assert state == "박스 상단 매도존"
    assert policy["size_pct"] == 0
    assert policy["new_entry"] == "중단"


def test_failed_breakout_has_priority():
    state, policy = classify(.95, False, True)
    assert state == "상단 돌파 실패"
    assert policy["size_pct"] == 0


def test_confirmed_breakout_reopens_selectively():
    state, policy = classify(1.05, True, False)
    assert state == "상단 돌파 확인"
    assert policy["size_pct"] == 70
