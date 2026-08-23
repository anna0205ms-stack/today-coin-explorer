from scanner.pre_breakout_reclaim import classify_d_stage


def candles(closes, lows=None, highs=None):
    lows = lows or [value * 0.99 for value in closes]
    highs = highs or [value * 1.01 for value in closes]
    return [
        {"open": close, "high": high, "low": low, "close": close, "volume": 1.0, "time": str(index)}
        for index, (close, low, high) in enumerate(zip(closes, lows, highs))
    ]


def test_d0_before_reclaim():
    result = classify_d_stage(candles([90, 93, 96]), 100, 110, 95, True)
    assert result[0] == "D0"


def test_d1_first_reclaim_without_retest():
    result = classify_d_stage(candles([95, 101, 106], lows=[94, 100.5, 104]), 100, 110, 95, True)
    assert result[0] == "D1"


def test_d2_lower_retest_defended():
    result = classify_d_stage(candles([95, 103, 102], lows=[94, 101, 100]), 100, 110, 95, True)
    assert result[0] == "D2"


def test_d3_upper_break_holds():
    result = classify_d_stage(candles([101, 108, 112]), 100, 110, 95, True)
    assert result[0] == "D3"


def test_d4_expansion_and_upper_retest():
    result = classify_d_stage(
        candles([101, 111, 120, 113], lows=[99, 109, 116, 110], highs=[103, 113, 121, 115]),
        100, 110, 95, True,
    )
    assert result[0] == "D4"


def test_warning_after_upper_break_is_lost():
    result = classify_d_stage(candles([101, 112, 108]), 100, 110, 95, True)
    assert result[0] == "D-W"


def test_failure_after_two_lower_closes():
    result = classify_d_stage(candles([101, 103, 98, 97]), 100, 110, 95, True)
    assert result[0] == "D-F"
