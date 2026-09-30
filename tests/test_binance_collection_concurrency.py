from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from scanner_binance import binance_spot_scanner as bn


def test_api_workers_overlap_but_starts_are_paced():
    starts = []
    active = 0
    maximum = 0
    lock = threading.Lock()

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args):
            nonlocal active
            with lock: active -= 1
        def read(self):
            time.sleep(.15)
            return b'[]'

    def fake_open(*args, **kwargs):
        nonlocal active, maximum
        with lock:
            starts.append(time.monotonic())
            active += 1
            maximum = max(maximum, active)
        return Response()

    with patch.object(bn, '_next_request_start', 0), patch.object(bn, 'REQUEST_INTERVAL', .05), patch.object(bn, 'urlopen', fake_open):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: bn.api_get('/klines', {'symbol':str(i)}), range(4)))
    assert results == [[],[],[],[]]
    assert maximum >= 2
    assert all(b-a >= .045 for a,b in zip(starts, starts[1:]))


def test_retry_also_reserves_a_request_start():
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise URLError('fixture failure')
    with patch.object(bn, 'urlopen', fail), patch.object(bn, 'wait_for_request_start') as paced, patch.object(bn.time, 'sleep'):
        try:
            bn.api_get('/klines', attempts=2)
        except bn.ScanError:
            pass
        else:
            raise AssertionError('failure should propagate after retries')
    assert len(calls) == paced.call_count == 2


def test_parallel_collection_preserves_order_and_isolates_symbol_failure():
    markets = [{'symbol':s} for s in ['SLOW','FAIL','FAST']]
    def fetch(symbol, interval, limit):
        if symbol == 'SLOW': time.sleep(.04)
        if symbol == 'FAIL': raise ValueError('fixture')
        return [{'symbol':symbol,'interval':interval}]
    with patch.object(bn, 'fetch_klines', fetch):
        with ThreadPoolExecutor(max_workers=4) as pool:
            result = list(pool.map(lambda row:bn.collect_market_frames(row,[],[]), markets))
            supply = list(pool.map(bn.collect_supply_frames, markets))
    assert [x[0]['symbol'] for x in result] == ['SLOW','FAIL','FAST']
    assert result[1][3] and not result[0][3] and not result[2][3]
    assert [x[0]['symbol'] for x in supply] == ['SLOW','FAIL','FAST']
    assert supply[1][2] and not supply[0][2] and not supply[2][2]


def test_clean_subprocess_interval_floor_and_import():
    import os
    env = dict(os.environ, BINANCE_API_INTERVAL='0.001')
    source = 'from scanner_binance.binance_spot_scanner import REQUEST_INTERVAL,SCAN_WORKERS;assert REQUEST_INTERVAL==.05 and SCAN_WORKERS==4'
    result = subprocess.run([sys.executable,'-c',source],cwd=Path(__file__).resolve().parents[1],env=env,text=True,capture_output=True)
    assert result.returncode == 0,result.stderr
