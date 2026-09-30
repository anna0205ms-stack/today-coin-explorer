from threading import Barrier
from unittest.mock import patch

from scanner_binance import render_dashboard as render


def bar():
    return {"open_time": 1, "close_time": 2, "open": 1., "high": 2., "low": .5, "close": 1.5, "volume": 5.}


def test_chart_requests_run_concurrently_and_deduplicate_markets():
    gate = Barrier(2)
    calls = []
    def fetch(market, interval, limit):
        calls.append((market, interval, limit))
        if interval == "1d": gate.wait(timeout=2)
        return [bar()]
    snap = {"candidates": [{"market": "AUSDT", "type": "A"},
                            {"market": "AUSDT", "type": "H"},
                            {"market": "BUSDT", "type": "B"}]}
    with patch.object(render, "fetch_klines", side_effect=fetch):
        assert render.enrich_candidate_charts(snap)
    assert len(calls) == 4
    assert ("AUSDT", "1d", 400) in calls
    assert ("BUSDT", "1d", 80) in calls
    assert all(row["charts"]["day"] and row["charts"]["4h"] for row in snap["candidates"])


def test_failed_market_keeps_other_market_charts_and_cached_charts():
    cached = {"day": [[1, 1, 2, .5, 1.5, 5]], "4h": [[1, 1, 2, .5, 1.5, 5]]}
    snap = {"candidates": [{"market": "BADUSDT", "type": "A"},
                            {"market": "GOODUSDT", "type": "D"},
                            {"market": "CACHEDUSDT", "type": "B", "charts": cached}]}
    def fetch(market, *args):
        if market == "BADUSDT": raise RuntimeError("outage")
        assert market != "CACHEDUSDT"
        return [bar()]
    with patch.object(render, "fetch_klines", side_effect=fetch):
        assert render.enrich_candidate_charts(snap)
    assert not snap["candidates"][0]["charts"]["day"]
    assert snap["candidates"][1]["charts"]["day"]
    assert snap["candidates"][1]["d_stage"] == "D0"
    assert snap["candidates"][2]["charts"] == cached
