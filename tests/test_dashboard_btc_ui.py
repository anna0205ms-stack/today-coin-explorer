from scanner.unified_dashboard import box_location_text, dashboard_page


def test_box_location_uses_plain_language_instead_of_raw_percent():
    assert box_location_text({"position_pct": 226.7}) == "기존 30일 박스 상단 돌파 후 위에서 거래 중"
    assert box_location_text({"position_pct": 52}) == "기존 30일 박스 중심 부근"
    assert box_location_text({"position_pct": 8}) == "기존 30일 박스 하단 매수구간"


def test_dashboard_has_one_top_bitcoin_tradingview_chart():
    btc = {
        "price": 105_580_000,
        "daily_state": "상단 돌파 시도",
        "four_hour_state": "기존 박스 상단을 반복 시험 중·단기 과열주의",
        "box": {
            "position_pct": 226.7, "low": 88_990_100, "high": 96_322_220,
            "center": 92_656_160, "buy_zone": [88_990_100, 90_089_950],
            "sell_zone": [94_122_736, 96_322_220],
        },
        "binance": {"box": {
            "low": 78_200.25, "high": 84_900.50, "center": 81_550.75,
            "buy_zone": [78_200.25, 79_205.29],
            "sell_zone": [82_890.33, 84_900.50],
        }},
        "basis": {"four_hour_end": "2026-08-24T01:00:00"},
    }
    regime = {
        "stage": "M3", "name": "알트 시작", "plain": "알트 순환이 시작된 장",
        "alt_entry_limit_pct": 45, "confidence": 78, "reasons": ["테스트 근거"],
        "gates": {},
    }

    html = dashboard_page({"candidates": []}, {}, btc, {}, regime)
    body = html[html.index("<body>"):]

    assert body.count("BINANCE:BTCUSDT") == 1
    assert "UPBIT:BTCKRW" not in body
    assert body.index("btc-live-card") < body.index("market-hero")
    assert "차트 왼쪽 위 시간봉 메뉴" in body
    assert "기존 30일 박스 상단 돌파 후 위에서 거래 중" in body
    assert "박스 위치 · 226.7%" not in body
    assert "dual-chart" not in body
    assert "오늘 먼저 볼 후보 5" not in body
    assert "M은 Market(시장)의 약자" in body
    assert "M0 · 위험장" in body
    assert "M1 · BTC 주도" in body
    assert "M2 · 알트 준비" in body
    assert "M3 · 알트 순환 시작" in body
    assert "M4 · 알트 확산" in body
    assert "M5 · 과열·수익보호" in body
    assert 'market-stage-card current' in body
    assert "시장 단계가 바뀌면 숙도지의 표정과 행동 안내도 함께 바뀌어." in body
    assert "시장 단계가 바뀌면 고양이의 표정" not in body
    assert body.index("BTC 조정이 시작된다면") < body.index("market-hero")
    assert "4시간봉 마감 기준" in body
    assert "BINANCE · BTC/USDT · 4시간봉 마감 기준" in body
    assert "기존 박스 상단 $84,900.50 이탈 마감" in body
    assert "박스 중심 $81,550.75" in body
    assert "$78,200.25 ~ $79,205.29" in body
    assert "₩96,322,220" not in body
