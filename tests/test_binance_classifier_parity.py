from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scanner'))

import pandas as pd
from scanner_binance import binance_spot_scanner as bn
from scanner import box_screener as ub
from scanner import h_breakout as uh


def rows(count=200):
    return [dict(open_time=i*86_400_000, close_time=(i+1)*86_400_000-1,
                 open=94., high=100., low=90., close=95., volume=10000., quote_volume=950000.)
            for i in range(count)]


def frame(data):
    return pd.DataFrame([{k.title():r[k] for k in ('open','high','low','close','volume')} for r in data],
                        index=pd.date_range('2026-01-01', periods=len(data), freq='D'))


def test_g_historical_windows_match_upbit():
    data = rows(400)
    for i, r in enumerate(data):
        r['close'] = 92. if i%2 else 98.
    left = bn._g_historical_boxes(data, len(data))
    right = ub._g_historical_boxes(frame(data), len(data))
    assert len(left) == len(right)
    assert [(r['low'],r['high'],r['start'],r['end']) for r in left] == [
        (r['low'],r['high'],r['start'],r['end']) for r in right]


def test_h_post_box_resistance_uses_ratio_not_fixed_last60_count():
    data = rows()
    for i in range(155,161):
        data[i].update(high=105., close=104.)
    data[-1].update(high=105.,close=103.,quote_volume=1_030_000.)
    box = {'low':90., 'high':100., 'length':45, 'inside':.9, 'inside_ratio':.9, 'start':15,'end':59}
    with patch.object(bn, '_g_historical_boxes', return_value=[box]), patch.object(uh, '_g_historical_boxes',return_value=[box]):
        a = bn.scan_h({'symbol':'TESTUSDT','base':'TEST','tick':.01}, data)
        krw = frame(data)
        krw['Volume'] *= 1000
        b = uh.analyze_h_breakout({'Code':'KRW-TEST'}, krw)
    assert a is not None and b is not None
    assert a['h_breakout_age'] == b['h_breakout_age'] == 0
    assert a['h_distance_pct'] == b['h_distance_pct'] == 3.


def test_h_rejects_chasing_daily_rise_and_stablecoin():
    data = rows(); data[-1]['close']=120.
    assert bn.scan_h({'symbol':'TESTUSDT','base':'TEST','tick':.01},data) is None
    assert bn.scan_h({'symbol':'USD1USDT','base':'USD1','tick':.01},rows()) is None


def test_f_uses_binance_data_and_shared_supply_classifier():
    data = rows(400)
    for i in range(200,392):
        data[i].update(open=70.,high=72.,low=68.,close=70.)
    for i in range(392,400):
        cl = 80.+(i-392)*16/7
        data[i].update(open=cl*.99,high=cl*1.01,low=cl*.98,close=cl)
    zone={'lower':90.,'upper':100.,'days':30,'inside_ratio':.9,'start':'2025-01-01','end':'2025-02-01'}
    with patch('scanner.global_supply.historical_supply_zone',return_value=zone):
        result=bn.scan_f({'symbol':'TESTUSDT','base':'TEST','tick':.01},data)
    assert result and result['type']=='F' and result['f_stage']=='F2'
    assert result['trend_lookback_days']==200
    assert result['trend_basis']=='BINANCE_200_DAY_HIGH'
    assert result['global_zone']==zone


def test_all_classifier_types_have_market_gates():
    for stage in bn.STAGE_INFO:
        assert set(bn.GATE_RULES[stage])==set('ABCDEFGH')


def test_d_adapter_matches_shared_scorer_and_lifecycle():
    from scanner.pre_breakout_reclaim import analyze
    from datetime import datetime, timezone
    data = rows(120)
    data[-1]['volume'] *= 4
    four = rows(100)
    for r in four:
        r['close'] = 103.
    def adapt(rs):
        return [{**r, 'time':datetime.fromtimestamp(r['open_time']/1000,timezone.utc)
                 .astimezone(bn.KST).isoformat()} for r in rs]
    expected = analyze('TESTUSDT',adapt(data),adapt(four))
    actual = bn.scan_d({'symbol':'TESTUSDT','base':'TEST','tick':.01},data,four)
    assert actual is not None
    assert actual['checks']==expected['checks']
    assert actual['d_stage']==expected['d_stage']
    assert actual['status']==expected['status']
    assert actual['rr']==expected['first_target_rr']


def test_d_adapter_imports_in_clean_package_subprocess():
    import subprocess
    import json
    data = rows(120)
    data[-1]['volume'] *= 4
    four = rows(100)
    for r in four:
        r['close'] = 103.
    source = ('import json,sys;from scanner_binance.binance_spot_scanner import scan_d;'
              'p=json.load(sys.stdin);r=scan_d(p[0],p[1],p[2]);assert r and r["type"]=="D"')
    result = subprocess.run([sys.executable,'-c',source],
                            input=json.dumps([{'symbol':'TESTUSDT','base':'TEST','tick':.01},data,four]),
                            text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr


def test_real_token_ending_up_is_not_mistaken_for_leveraged_token():
    info = {"symbols": [{"symbol": base + "USDT", "baseAsset": base, "quoteAsset": "USDT", "status": "TRADING"}
                        for base in ("JUP", "BTC", "BTCUP", "USDC")]}
    tickers = [{"symbol": base + "USDT", "quoteVolume": "3000000", "lastPrice": "1", "priceChangePercent": "0"}
               for base in ("JUP", "BTC", "BTCUP", "USDC")]
    with patch.object(bn, "api_get", side_effect=[info, tickers]):
        result = bn.fetch_universe(limit=None)
    assert {row["base"] for row in result} == {"JUP", "BTC"}
