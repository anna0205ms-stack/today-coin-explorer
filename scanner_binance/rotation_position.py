#!/usr/bin/env python3
"""Binance Spot USDT long-range map, independent of Upbit outputs."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scanner.rotation_position import classify  # shared chart-position math only

OUT = ROOT / 'outputs' / 'binance'
API = os.getenv('BINANCE_SPOT_API', 'https://data-api.binance.vision/api/v3')
KST = timezone(timedelta(hours=9))
request_lock = threading.Lock()
last_request = 0.0
# Exact base-asset symbols: no fuzzy matching that would drop unrelated coins.
PEGGED = {'USDT', 'USDC', 'USDS', 'USD1', 'USDG', 'USDE', 'DAI', 'FDUSD', 'TUSD',
          'PYUSD', 'RLUSD', 'USDD', 'EURC', 'EURCV', 'GUSD', 'FRAX', 'LUSD',
          'UST', 'USTC', 'XAUT', 'PAXG', 'EUR', 'GBP', 'BIDR', 'BRL', 'TRY',
          'AUD', 'RUB', 'UAH', 'ARS', 'ZAR', 'JPY', 'PLN', 'RON', 'AEUR', 'EURI',
          'WBTC', 'WBETH', 'WETH', 'BTCB', 'WBNB', 'BETH'}


def get(path: str, params: dict | None = None):
    global last_request
    url = API + path + ('?' + urlencode(params) if params else '')
    for attempt in range(5):
        try:
            with request_lock:
                wait = last_request + 0.04 - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                last_request = time.monotonic()
            with urlopen(Request(url, headers={'User-Agent': 'okotam-binance-rotation/1.0'}), timeout=20) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt, 8))


def eligible_symbols(exchange_info):
    tradable = [s for s in exchange_info['symbols'] if s.get('status') == 'TRADING'
                and s.get('quoteAsset') == 'USDT' and s.get('isSpotTradingAllowed', False)]
    excluded = [s for s in tradable if s['baseAsset'] in PEGGED]
    return [s for s in tradable if s['baseAsset'] not in PEGGED], len(excluded)


def build(symbol, volume):
    candles = get('/klines', {'symbol': symbol['symbol'], 'interval': '1d', 'limit': 400})
    rows = [{'trade_price': float(k[4]), 'candle_date_time_kst':
             datetime.fromtimestamp(int(k[0]) / 1000, KST).strftime('%Y-%m-%d')} for k in candles]
    item = classify(rows)
    if item:
        item.update(market=symbol['symbol'], symbol=symbol['baseAsset'],
                    name=symbol['baseAsset'], quote_volume_24h=volume.get(symbol['symbol'], 0))
    return item


def collect():
    symbols, excluded = eligible_symbols(get('/exchangeInfo'))
    tickers = get('/ticker/24hr')
    volumes = {t['symbol']: float(t['quoteVolume']) for t in tickers}
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(build, symbol, volumes): symbol['symbol'] for symbol in symbols}
        for future in as_completed(futures):
            try:
                item = future.result()
                if item:
                    results.append(item)
            except Exception as error:
                failures.append(f'{futures[future]}: {type(error).__name__}')
    if not results:
        raise RuntimeError('No Binance daily candles: retaining previous data')
    return {'updated_at': datetime.now(KST).isoformat(timespec='minutes'),
            'source': 'Binance Spot USDT daily candles', 'covered': len(results),
            'total': len(symbols), 'excluded': excluded, 'failed': failures,
            'coins': sorted(results, key=lambda x: (x['location'], x['symbol']))}


def cached_preview():
    """Use existing Binance candles as an explicitly partial initial preview."""
    source = OUT / 'latest.json'
    if not source.exists():
        return None
    report = json.loads(source.read_text(encoding='utf-8'))
    results = []
    seen = set()
    for candidate in report.get('candidates', []):
        market = candidate.get('market', '')
        if not market.endswith('USDT') or market in seen:
            continue
        base = market[:-4]
        if base in PEGGED:
            continue
        seen.add(market)
        candles = candidate.get('charts', {}).get('day', [])
        rows = [{'trade_price': float(k[4]), 'candle_date_time_kst':
                 datetime.fromtimestamp(int(k[0]) / 1000, KST).strftime('%Y-%m-%d')}
                for k in candles if isinstance(k, list) and len(k) > 4]
        item = classify(rows)
        if item:
            item.update(market=market, symbol=base, name=base, quote_volume_24h=0)
            results.append(item)
    if not results:
        return None
    return {'updated_at': report.get('generated_at'), 'source': 'stored Binance candidate candles (partial preview)',
            'covered': len(results), 'total': report.get('universe_count', len(results)),
            'excluded': 0, 'partial': True, 'failed': [],
            'coins': sorted(results, key=lambda x: (x['location'], x['symbol']))}


def render():
    source = (ROOT / 'scanner' / 'rotation_position.py').read_text(encoding='utf-8')
    # The shared renderer is adapted only inside the Binance outputs directory.
    start = source.index("    page = '''<!doctype html>") + len("    page = '''")
    end = source.index("'''\n    (OUT / \"rotation_position.html\")", start)
    page = source[start:end]
    page = page.replace('href="dashboard_v5.css"', 'href="../dashboard_v5.css"')
    # The Binance masthead and main-dashboard tab stay in the Binance area.
    page = page.replace('src="assets/sukdol-stage.webp"', 'src="../assets/sukdol-stage.webp"')
    page = page.replace('<b>UPBIT</b><small>KRW</small>', '<b>UPBIT</b><small>KRW</small>')
    page = page.replace('class="exchange selected" href="rotation_position.html"', 'class="exchange" href="../rotation_position.html"')
    page = page.replace('class="exchange binance" href="binance/scan.html"', 'class="exchange binance selected" href="rotation_position.html"')
    page = page.replace('href="type_', 'href="type_')
    page = page.replace('원 ·', ' USDT ·').replace('원.', ' USDT.')
    page = page.replace('스테이블코인과 금 가격 연동 토큰은 제외합니다.', '가격 연동 자산과 래핑 토큰은 제외합니다.')
    (OUT / 'rotation_position.html').write_text(page, encoding='utf-8')
    shutil.copy2(ROOT / 'scanner' / 'rotation_position.css', OUT / 'rotation_position.css')
    js = (ROOT / 'scanner' / 'rotation_position.js').read_text(encoding='utf-8')
    js = js.replace('}원 · 기준 상단 ${price(coin.high)}원 · 현재 ${price(coin.price)}원.', '} USDT · 기준 상단 ${price(coin.high)} USDT · 현재 ${price(coin.price)} USDT.')
    js = js.replace('/^#coin-(KRW-[A-Z0-9]+)$/', '/^#coin-([A-Z0-9]+USDT)$/')
    js = js.replace("let trade = {};", "let trade = {};")
    js = js.replace('data=d;render();', 'data=d;trade=Object.fromEntries(data.coins.map(c=>[c.market,c.quote_volume_24h||0]));render();')
    js = re.sub(r";return fetch\('https://api\.upbit\.com/v1/ticker/all\?quote_currencies=KRW'\).*?\.catch\(e=>", ';return []}).catch(e=>', js, flags=re.S)
    # Preserve the error handler closing delimiters and avoid cross-exchange HTTP calls.
    (OUT / 'rotation_position.js').write_text(js, encoding='utf-8')


def inject_nav():
    for page in OUT.glob('*.html'):
        if page.name == 'rotation_position.html':
            continue
        content = page.read_text(encoding='utf-8')
        if 'href="rotation_position.html"' in content:
            continue
        m = re.search(r'<details class="nav-drop"[^>]*>.*?</details>', content, flags=re.S)
        if m:
            content = content[:m.end()] + '<a href="rotation_position.html">순환매 위치</a>' + content[m.end():]
        else:
            content = re.sub(r'(<a[^>]*href="scan\.html"[^>]*>.*?</a>)',
                             r'\1<a href="rotation_position.html">순환매 위치</a>', content, count=1, flags=re.S)
        page.write_text(content, encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    render()
    inject_nav()
    try:
        data = collect()
        (OUT / 'rotation_position.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        print(f"Binance rotation: {data['covered']}/{data['total']}")
    except Exception as error:
        print(f'Binance rotation refresh failed, retaining previous data: {error}')
        if not (OUT / 'rotation_position.json').exists():
            preview = cached_preview()
            if preview:
                (OUT / 'rotation_position.json').write_text(json.dumps(preview, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            else:
                raise


if __name__ == '__main__':
    main()
