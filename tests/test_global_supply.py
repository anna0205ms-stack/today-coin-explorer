from scanner.global_supply import classify_stage, historical_supply_zone, trade_plan


def candle(day, low, high, close):
    opened = close * 0.99
    start = 1_700_000_000_000 + day * 86_400_000
    return [start, str(opened), str(high), str(low), str(close), "100", start + 86_399_000]


def test_historical_zone_finds_old_congestion_near_current_price():
    history = [candle(i, 5.7 + (i % 3) * .03, 6.8 - (i % 4) * .04, 6.1 + (i % 5) * .08) for i in range(120)]
    recent = [candle(120 + i, 2 + i * .08, 2.4 + i * .1, 2.2 + i * .09) for i in range(45)]
    zone = historical_supply_zone(history + recent, 6.25)
    assert zone is not None
    assert zone["lower"] < 6.25 < zone["upper"]
    assert zone["days"] >= 20


def test_f_type_uses_only_three_simple_stages():
    zone = {"lower": 5.8, "upper": 6.7}
    recent = [candle(i, 5.5, 6.6, 6.2) for i in range(3)]
    assert classify_stage(5.3, zone, recent)[:2] == ("F1", "신고가 상승")
    assert classify_stage(6.2, zone, recent)[:2] == ("F2", "매물대 도착")
    breakout = [candle(i, 6.65, 7.1, 6.9) for i in range(3)]
    assert classify_stage(6.9, zone, breakout)[:2] == ("F3", "매물대 돌파")


def test_f2_plan_waits_and_targets_global_zone_top():
    plan = trade_plan("F2", 9000, 6.3, {"lower": 5.8, "upper": 6.7})
    assert plan["action"] == "확인 대기"
    assert plan["stop"] < min(plan["entry"])
    assert plan["targets"][0] > max(plan["entry"])
