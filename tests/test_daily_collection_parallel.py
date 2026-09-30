"""Daily downloads overlap latency without changing output order or safety gates."""
import sys
import threading
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
import box_screener


def test_daily_collection_parallel_bounded_and_deterministic(monkeypatch):
    codes = [f"KRW-T{i}" for i in range(12)]
    universe = pd.DataFrame({"Code": codes})
    frame = pd.DataFrame({"Close": range(220)})
    barrier = threading.Barrier(4)
    lock = threading.Lock()
    active = peak = 0
    started = []
    def fetch(code):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            started.append(code)
            first_batch = len(started) <= 4
        try:
            if first_batch:
                barrier.wait(timeout=3)
            if code == "KRW-T4":
                raise RuntimeError("temporary API failure")
            if code == "KRW-T7":
                return frame.iloc[:90]
            return frame
        finally:
            with lock:
                active -= 1
    monkeypatch.setattr(box_screener, "fetch_daily_candles", fetch)
    frames, sources, failed = box_screener.collect_daily_data(universe)
    expected = [code for code in codes if code not in {"KRW-T4", "KRW-T7"}]
    assert peak == 4
    assert list(frames) == list(sources) == expected
    assert failed == ["KRW-T4", "KRW-T7"]
    assert len(started) == 12


def test_parallel_collection_retains_minimum_data_guard(monkeypatch):
    universe = pd.DataFrame({"Code": [f"KRW-T{i}" for i in range(20)]})
    monkeypatch.setattr(box_screener, "fetch_daily_candles", lambda code: pd.DataFrame({"Close": range(90)}))
    with pytest.raises(box_screener.ScanError, match="0/20"):
        box_screener.collect_daily_data(universe)
