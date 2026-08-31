from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_btc_chart_uses_price_linked_lines_without_fixed_overlay():
    html = (ROOT / "scanner" / "dashboard_v5.html").read_text(encoding="utf-8")
    script = (ROOT / "scanner" / "dashboard_v5.js").read_text(encoding="utf-8")

    assert "lightweight-charts@4.2.2" in html
    assert "btc-chart-tools" in html
    assert 'class="range-position' not in html
    assert 'class="box-overlay' not in html
    assert "createPriceLine" in script
    assert "priceToCoordinate" in script
    assert "pinch:true" in script
    assert "horzTouchDrag:true" in script

