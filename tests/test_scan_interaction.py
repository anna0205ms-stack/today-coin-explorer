from scanner.unified_dashboard import main_page


def test_scan_page_keeps_inline_charts_and_search():
    candle = ["2026-09-07T09:00:00+09:00", 100.0, 105.0, 98.0, 103.0, 1000.0]
    candidate = {
        "market": "KRW-XRP", "type": "A", "action": "눌림 대기",
        "score": 80, "price": 103.0, "entry": [98.0, 100.0],
        "stop": 95.0, "targets": [108.0, 112.0, 120.0], "rr": 1.8,
        "charts": {"day": [candle], "4h": [candle]},
        "trade_plan": {"reason": "첫 눌림 지지", "remain": "진입구간 재접근 대기", "average_entry": 99.0, "target1": 108.0, "target2": 112.0, "extension": 120.0, "distance_pct": 3.0},
    }
    page = main_page({"snapshot_at": "2026-09-07T21:00:00+09:00", "candidates": [candidate]}, {})
    assert 'id="coinSearch"' in page
    assert 'onclick="toggleScanRow(0)"' in page
    assert 'id="scanDetail0"' in page
    assert "일봉" in page and "4시간봉" in page
    assert "눌러서 차트 보기" in page
