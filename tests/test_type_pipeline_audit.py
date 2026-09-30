"""Regression coverage for scanner eligibility and cross-stage G metadata."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
import box_screener
import history_store


def test_g_h_collection_accepts_classifier_history_floor(monkeypatch):
    universe = pd.DataFrame([{"Code": f"KRW-T{i}", "Name": f"T{i}"} for i in range(10)])
    frame = pd.DataFrame({"Close": range(150)})
    monkeypatch.setattr(box_screener, "fetch_daily_candles", lambda market: frame)
    frames, _, failed = box_screener.collect_daily_data(universe, min_candles=100)
    assert len(frames) == 10
    assert not failed
    with pytest.raises(box_screener.ScanError):
        box_screener.collect_daily_data(universe)


def test_g_snapshot_preserves_values_shown_in_type_detail():
    row = {"market": "KRW-T", "analysis_close": 103.5,
           "g_close_depth_pct": 27.5, "g_box_days": 32,
           "g_box_inside_ratio": 88.2, "g_lower_zone_days": 15,
           "g_supply_low": 100, "g_supply_high": 112,
           "g_reclaim_date": "2026-09-29"}
    normalized = history_store.normalize_g(row)
    for key in ("analysis_close", "g_close_depth_pct", "g_box_days",
                "g_box_inside_ratio", "g_lower_zone_days", "g_supply_low",
                "g_supply_high", "g_reclaim_date"):
        assert normalized[key] == row[key]


def test_healthy_empty_abc_scan_clears_stale_results(tmp_path, monkeypatch):
    import json
    output = tmp_path / "outputs"
    output.mkdir()
    for name in ("DAILY_DIR", "CHART_DIR", "INTRADAY_DIR"):
        directory = output / name.lower()
        directory.mkdir()
        monkeypatch.setattr(box_screener, name, directory)
    monkeypatch.setattr(box_screener, "OUTPUT_DIR", output)
    monkeypatch.setattr(box_screener, "write_learning_outputs", lambda *args: None)
    monkeypatch.setattr(box_screener, "aggregate_performance", lambda *args: {})
    (output / "latest_scan.json").write_text('[{"코드":"KRW-STALE"}]')
    universe = pd.DataFrame([{"Code": "KRW-T", "Name": "T", "EnglishName": "T"}])
    frames = {"KRW-T": pd.DataFrame({"Close": [100]}, index=pd.to_datetime(["2026-09-29"]))}
    box_screener.write_outputs([], universe, frames, {}, [], {}, [])
    assert json.loads((output / "latest_scan.json").read_text()) == []
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["status"] == "success"
    assert metadata["candidate_count"] == 0
    assert metadata["market_date"] == "2026-09-29"


def test_missing_daily_data_does_not_overwrite_live_results(tmp_path, monkeypatch):
    output = tmp_path / "outputs"
    output.mkdir()
    monkeypatch.setattr(box_screener, "OUTPUT_DIR", output)
    live = output / "latest_scan.json"
    live.write_text('[{"코드":"KRW-KEEP"}]')
    with pytest.raises(box_screener.ScanError):
        box_screener.write_outputs([], pd.DataFrame(), {}, {}, [], {}, [])
    assert "KRW-KEEP" in live.read_text()


def test_request_start_pacing_is_shared_across_workers(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import upbit_rate_limit
    clock = [10.0]
    sleeps = []
    monkeypatch.setattr(upbit_rate_limit, "_next_start", 0.0)
    monkeypatch.setattr(upbit_rate_limit.time, "monotonic", lambda: clock[0])
    def sleep(delay):
        sleeps.append(delay)
        clock[0] += delay
    monkeypatch.setattr(upbit_rate_limit.time, "sleep", sleep)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: upbit_rate_limit.wait_for_request_slot(), range(8)))
    assert len(sleeps) == 7
    assert all(delay >= .1299 for delay in sleeps)
    assert clock[0] >= 10.9


def test_d_retries_rate_limit_instead_of_dropping_pair(monkeypatch):
    import io
    from email.message import Message
    from urllib.error import HTTPError
    import pre_breakout_reclaim
    headers = Message()
    headers["Retry-After"] = "1"
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'[{"trade_price":100}]'
    def open_request(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise HTTPError("https://api.upbit.com", 429, "Rate limit", headers, io.BytesIO())
        return Response()
    slots, delays = [], []
    monkeypatch.setattr(pre_breakout_reclaim, "urlopen", open_request)
    monkeypatch.setattr(pre_breakout_reclaim, "wait_for_request_slot", lambda: slots.append(1))
    monkeypatch.setattr(pre_breakout_reclaim.time, "sleep", delays.append)
    assert pre_breakout_reclaim.api_get("/candles/days") == [{"trade_price": 100}]
    assert len(calls) == len(slots) == 2
    assert delays == [1.0]


def test_d_does_not_retry_permanent_http_error(monkeypatch):
    from urllib.error import HTTPError
    import pre_breakout_reclaim
    def fail(*args, **kwargs):
        raise HTTPError("https://api.upbit.com", 400, "Bad request", {}, None)
    monkeypatch.setattr(pre_breakout_reclaim, "urlopen", fail)
    monkeypatch.setattr(pre_breakout_reclaim, "wait_for_request_slot", lambda: None)
    with pytest.raises(HTTPError):
        pre_breakout_reclaim.api_get("/candles/days")
