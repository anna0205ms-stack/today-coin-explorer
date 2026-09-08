from pathlib import Path

from scanner.trade_tracker_ui import JS, write_tracker_asset
from scanner.unified_dashboard import main_page, watchlist_page


def candidate(market="KRW-XRP"):
    candle = ["2026-09-08T09:00:00+09:00", 100, 105, 98, 103, 1000]
    return {
        "market": market, "name": "리플", "type": "B", "score": 7,
        "price": 103, "entry": [98, 100], "stop": 95,
        "targets": [108, 112], "action": "확인 대기",
        "reason": "박스 하단 지지", "charts": {"day": [candle], "4h": [candle]},
    }


def test_tracker_uses_separate_exchange_storage_and_required_states():
    assert "okoTradeTrackerUpbitV1" in JS
    assert "okoTradeTrackerBinanceV1" in JS
    assert "upbitPins" in JS and "binancePins" in JS
    for label in ("당시 계획 유지", "계획 약화 · 대응 필요", "당시 구조 무효", "새 구조 형성"):
        assert label in JS


def test_tracker_contains_snapshot_buy_charts_compare_and_timeline():
    for label in ("💰 실제 매수함", "당시 계획", "현재 분석", "일봉", "4시간봉", "변화 기록"):
        assert label in JS
    assert "snapshot:snapshot(r)" in JS
    assert "item.snapshot.charts" in JS


def test_pages_embed_current_candidates_and_tracker_asset(tmp_path: Path):
    basis = {"snapshot_at": "2026-09-08T09:00:00+09:00", "candidates": [candidate()]}
    scan = main_page(basis, {})
    watch = watchlist_page({"items": {}}, basis)
    assert "window.OKO_TRACK_DATA=" in scan
    assert 'src="trade_tracker.js?v=20260908-1"' in scan
    assert "내 매매 추적 목록" in watch
    write_tracker_asset(tmp_path)
    assert (tmp_path / "trade_tracker.js").read_text(encoding="utf-8") == JS
