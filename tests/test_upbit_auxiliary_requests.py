from unittest.mock import patch
from scanner import global_supply
from scanner import outcome_tracker


def test_f_routes_only_upbit_collection_through_paced_retry_client():
    with patch.object(global_supply, "paced_upbit_get", return_value=[{"trade_price": 100}]) as fetch:
        result = global_supply.get_json("https://api.upbit.com/v1/candles/days?market=KRW-X&count=200")
    assert result == [{"trade_price": 100}]
    fetch.assert_called_once_with("/candles/days?market=KRW-X&count=200")


def test_outcomes_use_same_paced_client_and_preserve_time_order():
    rows = [{"candle_date_time_kst": t, "high_price": h, "low_price": 90}
            for t, h in [("2026-09-30T17:00:00", 110), ("2026-09-30T13:00:00", 105)]]
    with patch.object(outcome_tracker, "paced_upbit_get", return_value=rows) as fetch:
        result = outcome_tracker.fetch("KRW-X")
    fetch.assert_called_once_with("/candles/minutes/240", {"market": "KRW-X", "count": 200})
    assert [c["high"] for c in result] == [105., 110.]
