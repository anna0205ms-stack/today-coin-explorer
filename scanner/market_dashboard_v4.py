#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market_dashboard_v2 import inject_common_headers

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
BTC_FILE = OUT / "bitcoin_regime.json"
GLOBAL_FILE = OUT / "global_market_data.json"
REGIME_FILE = OUT / "market_regime.json"
UPBIT_BREADTH_FILE = OUT / "upbit_market_breadth.json"
BINANCE_FILE = OUT / "binance" / "latest.json"
KST = timezone(timedelta(hours=9))

STAGES = {
    "M0": ("위험장", "BTC 구조 훼손 · 알트 자금 이탈", "경계"),
    "M1": ("BTC 강세", "BTC 주도 · 알트 확산 약함", "선별"),
    "M2": ("알트 준비", "알트 버팀 · 순환 확인 전", "관찰"),
    "M3": ("알트 시작", "BTC.D ↓ · TOTAL2 ↑ · OTHERS ↑ · 알트 확산 시작", "알트 확산"),
    "M4": ("알트 확산", "알트 상승 범위 확대", "확산"),
    "M5": ("과열 경계", "알트 확산 후 과열 구간", "주의"),
}


def read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def e(value):
    return html.escape(str(value if value is not None else "-"))


def money(value):
    if not isinstance(value, (int, float)):
        return "-"
    if abs(value) >= 1_000_000_000_000:
        return f"${value/1_000_000_000_000:.2f}T"
    if abs(value) >= 1_000_000_000:
        return f"${value/1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    return f"${value:,.0f}"


def usdt(value):
    return f"${float(value):,.0f}" if isinstance(value, (int, float)) else "-"


def pct(value):
    return f"{float(value):.0f}%" if isinstance(value, (int, float)) else "-"


def direction(value, suffix="%"):
    if not isinstance(value, (int, float)):
        return "-", "flat", "→"
    if value > 0:
        return f"+{value:.2f}{suffix}", "up", "↑"
    if value < 0:
        return f"{value:.2f}{suffix}", "down", "↓"
    return f"0.00{suffix}", "flat", "→"


def location(position):
    if not isinstance(position, (int, float)):
        return "위치 확인 전"
    if position > 100:
        return "박스 상단 위"
    if position >= 70:
        return "박스 상단"
    if position >= 45:
        return "박스 중심권"
    if position >= 15:
        return "박스 하단~중심"
    if position >= 0:
        return "박스 하단"
    return "박스 하단 이탈"


def tv(symbol: str, interval: str, mini=False):
    config = {
        "autosize": True,
        "symbol": symbol,
        "interval": interval,
        "timezone": "Asia/Seoul",
        "theme": "dark",
        "style": "1",
        "locale": "kr",
        "backgroundColor": "rgba(6,9,13,1)",
        "gridColor": "rgba(44,49,59,0.25)",
        "hide_side_toolbar": mini,
        "hide_top_toolbar": mini,
        "hide_legend": mini,
        "allow_symbol_change": False,
        "save_image": False,
        "calendar": False,
        "support_host": "https://www.tradingview.com",
    }
    cfg = json.dumps(config, ensure_ascii=False).replace("</", "<\\/")
    cls = "tv-mini" if mini else "tv-main"
    return f'<div class="{cls}"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{cfg}</script></div></div>'


def stage_mascot(stage):
    return "assets/sukdol_up.webp" if stage in {"M3", "M4"} else "assets/sukdol_stop.webp" if stage == "M0" else "assets/sukdol_caution.webp"


def header():
    return '''<header class="topbar"><a class="brand" href="index.html"><span class="compass">✦</span><span><b>오늘의 코인 탐험대</b><small>통합 시장 대시보드</small></span></a><div class="market-switch"><a class="upbit" href="scan.html"><b>UPBIT</b><small>KRW</small></a><a class="binance" href="binance/scan.html"><b>BINANCE</b><small>SPOT USDT</small></a></div></header><nav class="nav"><a class="active" href="index.html">메인 대시보드</a><a href="scan.html">전체 스캔</a><a href="type_a.html">A형</a><a href="type_b.html">B형</a><a href="type_c.html">C형</a><a href="type_d.html">D형</a><a href="type_e.html">E형</a><a href="watchlist.html">관심종목</a><a href="history.html">기록</a><a href="training_a.html">훈련소</a></nav>'''


def render():
    btc = read(BTC_FILE, {})
    global_data = read(GLOBAL_FILE, {})
    regime = read(REGIME_FILE, {})
    upbit_breadth = read(UPBIT_BREADTH_FILE, {})
    binance = read(BINANCE_FILE, {})

    stage = str(regime.get("stage") or "M?")
    stage_name, stage_short, mascot_word = STAGES.get(stage, (str(regime.get("name") or "시장 확인"), "시장 데이터 확인", "관찰"))
    stage_color = {"M0":"#ff5d55","M1":"#f2bf48","M2":"#e7cc63","M3":"#61df91","M4":"#42e487","M5":"#ff886f"}.get(stage, "#9ca8b4")

    btc_d = global_data.get("btc_d") or {}
    total2 = global_data.get("total2") or {}
    others = global_data.get("others") or {}
    breadth = global_data.get("breadth") or {}
    bd_move, bd_cls, bd_arrow = direction(btc_d.get("change_4h_pct_point"), "%p")
    t2_move, t2_cls, t2_arrow = direction(total2.get("change_4h_pct"))
    ot_move, ot_cls, ot_arrow = direction(others.get("change_4h_pct"))

    breg = binance.get("market_regime") or {}
    bbtc = breg.get("btc") or {}
    bbox = bbtc.get("box") or (btc.get("binance") or {}).get("box") or {}
    corr = bbtc.get("correction") or {}
    btc_price = bbtc.get("price") or (btc.get("binance") or {}).get("price")
    btc_daily = bbtc.get("daily_state") or "-"
    btc_four = bbtc.get("four_hour_state") or "-"
    btc_position = location(bbox.get("position_pct"))

    all_ratio = breadth.get("positive_ratio_24h_pct")
    binance_ratio = (breg.get("breadth") or {}).get("positive_ratio_24h_pct")
    upbit_ratio = upbit_breadth.get("positive_ratio_24h_pct")

    times = [global_data.get("generated_at"), binance.get("generated_at"), upbit_breadth.get("generated_at")]
    updated = max([str(x) for x in times if x] or [datetime.now(KST).isoformat()]).replace("T", " ")[:16]

    breadth_state = "확산" if isinstance(all_ratio, (int,float)) and all_ratio >= 60 else "중립" if isinstance(all_ratio, (int,float)) and all_ratio >= 45 else "약세"
    breadth_cls = "up" if breadth_state == "확산" else "flat" if breadth_state == "중립" else "down"

    help_box = f'''<details class="stage-help"><summary>{e(stage)}가 뭔가</summary><div><b>{e(stage)} · {e(stage_name)}</b><span>{e(stage_short)}</span><small>M0 위험 → M1 BTC 강세 → M2 알트 준비 → M3 알트 시작 → M4 알트 확산 → M5 과열</small></div></details>'''

    doc = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>오늘의 코인 탐험대</title><style>
:root{{--bg:#05070a;--card:#0d1117;--line:#26303a;--text:#f3f5f7;--muted:#96a1ad;--gold:#f5c533;--blue:#4da7ff;--red:#ff635d;--green:#58dd92;--stage:{stage_color}}}
*{{box-sizing:border-box}}body{{margin:0;background:#05070a;color:var(--text);font-family:Inter,Pretendard,"Noto Sans KR",system-ui,sans-serif}}a{{color:inherit;text-decoration:none}}.page{{max-width:1540px;margin:auto;padding:0 18px 28px}}.topbar{{position:sticky;top:0;z-index:1000;height:94px;display:flex;align-items:center;justify-content:space-between;background:rgba(5,7,10,.98);border-bottom:1px solid #202832;padding:0 14px}}.brand{{display:flex;align-items:center;gap:15px}}.compass{{width:56px;height:56px;border:1px solid #e2b637;border-radius:50%;display:grid;place-items:center;color:#f5cb46;font-size:28px}}.brand b{{display:block;font-size:30px;letter-spacing:-1px}}.brand small{{display:inline-block;margin-top:5px;padding:3px 11px;border:1px solid #343b52;border-radius:999px;color:#c5cbe0;background:#171831}}.market-switch{{display:flex;gap:14px}}.market-switch a{{min-width:160px;padding:11px 18px;border:1px solid #333c48;border-radius:11px;text-align:center}}.market-switch b{{display:block;font-size:17px}}.market-switch small{{display:block;font-size:10px;margin-top:2px}}.market-switch .upbit{{color:#5faeff;border-color:#1e5e9d}}.market-switch .binance{{color:#f6c52d;border-color:#69520a}}.nav{{display:flex;align-items:center;gap:6px;overflow:auto;height:54px;border-bottom:1px solid #252c35;margin-bottom:16px}}.nav a{{white-space:nowrap;color:#aeb6c0;padding:16px 24px 13px;border-bottom:2px solid transparent}}.nav a.active{{color:#fff;border-color:#8b6cff}}.panel{{background:linear-gradient(180deg,#0e1319,#090d12);border:1px solid var(--line);border-radius:17px}}.hero{{display:grid;grid-template-columns:42% 58%;gap:14px}}.stage-panel{{min-height:388px;padding:0;overflow:hidden;position:relative;display:grid;grid-template-columns:47% 53%;align-items:stretch}}.hero-cat-wrap{{position:relative;overflow:hidden}}.hero-cat{{position:absolute;left:-12px;bottom:-20px;width:115%;height:108%;object-fit:contain;object-position:left bottom;filter:drop-shadow(0 18px 26px #000)}}.stage-info{{padding:42px 22px 22px 0;position:relative;z-index:2}}.stage-label{{font-size:16px;color:#d7dce3;font-weight:700}}.stage-code{{font-size:100px;line-height:.95;font-weight:950;color:var(--stage);letter-spacing:-5px;margin-top:12px}}.stage-name{{font-size:31px;font-weight:900;color:var(--stage);margin-top:8px}}.stage-help{{margin-top:25px;border:1px solid #303a44;background:#090d12;border-radius:12px;overflow:hidden}}.stage-help summary{{list-style:none;cursor:pointer;padding:12px 15px;font-weight:800;font-size:16px}}.stage-help summary::-webkit-details-marker{{display:none}}.stage-help div{{display:grid;gap:5px;padding:0 15px 13px;color:#aeb7c0}}.stage-help b{{color:#fff}}.stage-help small{{font-size:11px;color:#77828e}}.btc-panel{{min-height:388px;padding:13px}}.btc-head{{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:2px 6px 10px}}.btc-head h2{{font-size:21px;margin:0}}.btc-facts{{display:flex;gap:14px;flex-wrap:wrap;justify-content:flex-end;color:#9da7b2;font-size:12px}}.btc-facts b{{color:#fff}}.tv-main{{height:326px;border:1px solid #202934;border-radius:10px;overflow:hidden}}.tradingview-widget-container,.tradingview-widget-container__widget{{width:100%;height:100%}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:14px}}.metric{{height:220px;padding:15px;overflow:hidden}}.metric-top{{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}}.metric h3{{margin:0;font-size:17px}}.metric strong{{display:block;font-size:26px;margin-top:7px}}.move{{font-weight:800;margin-top:8px;font-size:13px}}.up{{color:#4edd88}}.down{{color:#ff6460}}.flat{{color:#a8b1bb}}.tv-mini{{height:128px;margin-top:8px;border:1px solid #222a33;border-radius:8px;overflow:hidden}}.breadth strong{{font-size:34px;margin-top:20px}}.breadth-meter{{display:flex;gap:3px;margin-top:20px}}.breadth-meter i{{display:block;flex:1;height:18px;border-radius:3px;background:#242b34}}.breadth-meter i.on{{background:var(--stage)}}.metric small{{display:block;color:#7d8894;margin-top:9px}}.exchange{{padding-top:17px}}.exchange-lines{{display:grid;gap:18px;margin-top:26px}}.ex{{display:grid;grid-template-columns:85px 1fr 48px;gap:8px;align-items:center}}.ex b{{font-size:13px}}.bar{{height:7px;border-radius:999px;background:#222a33;overflow:hidden}}.fill{{height:100%;border-radius:inherit}}.fill.bin{{background:var(--gold)}}.fill.upb{{background:#4b8cff}}.bottom{{display:grid;grid-template-columns:37% 63%;gap:14px;margin-top:14px}}.summary{{height:244px;position:relative;overflow:hidden;padding:24px 28px;border-color:#334f43}}.summary h2{{margin:0;font-size:20px}}.summary-stage{{font-size:36px;color:var(--stage);font-weight:900;margin-top:35px}}.summary-word{{font-size:20px;color:#a9b2bc;margin-top:17px}}.summary-cat{{position:absolute;right:-6px;bottom:-20px;width:46%;height:105%;object-fit:contain;object-position:right bottom;filter:drop-shadow(0 16px 22px #000)}}.correction{{height:244px;position:relative;overflow:hidden;padding:20px 28px;border-color:#6a2a2a}}.correction h2{{margin:0 0 18px;font-size:22px}}.levels{{display:grid;grid-template-columns:1fr;gap:8px;padding-right:250px}}.level{{display:grid;grid-template-columns:140px 180px 1fr;align-items:center;border:1px solid #303944;border-radius:9px;padding:11px 16px;background:#0a0e13}}.level span{{font-size:18px;font-weight:900}}.level b{{font-size:23px}}.level.one span,.level.one b{{color:#56df91}}.level.two span,.level.two b{{color:#f0b642}}.level.bad span,.level.bad b{{color:#ff625e}}.level em{{font-style:normal;color:#9da7b2;font-size:13px}}.risk-cat{{position:absolute;right:10px;bottom:-32px;width:230px;height:108%;object-fit:contain;object-position:right bottom;filter:drop-shadow(0 16px 22px #000)}}.foot{{display:flex;justify-content:space-between;color:#697582;font-size:11px;padding:12px 3px 0}}
@media(max-width:1050px){{.hero,.bottom{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}.levels{{padding-right:190px}}.risk-cat{{width:190px}}}}@media(max-width:650px){{.page{{padding:0 9px 24px}}.topbar{{height:72px;padding:0 6px}}.compass{{width:38px;height:38px;font-size:20px}}.brand b{{font-size:18px}}.brand small{{display:none}}.market-switch a{{min-width:84px;padding:7px}}.nav a{{padding:14px 12px}}.stage-panel{{grid-template-columns:45% 55%;min-height:330px}}.stage-code{{font-size:70px}}.stage-name{{font-size:23px}}.stage-info{{padding-top:28px}}.metrics{{grid-template-columns:1fr}}.correction{{height:auto;min-height:330px}}.levels{{padding-right:0}}.level{{grid-template-columns:100px 1fr}}.level em{{grid-column:1/-1}}.risk-cat{{opacity:.18;width:230px}}}}
</style></head><body><div class="page">{header()}
<section class="hero"><div class="panel stage-panel"><div class="hero-cat-wrap"><img class="hero-cat" src="{stage_mascot(stage)}" alt="숙돌이"></div><div class="stage-info"><div class="stage-label">현재 시장 단계</div><div class="stage-code">{e(stage)}</div><div class="stage-name">{e(stage_name)}</div>{help_box}</div></div><div class="panel btc-panel"><div class="btc-head"><h2>BTCUSDT</h2><div class="btc-facts"><span>일봉 <b>{e(btc_daily)}</b></span><span>4H <b>{e(btc_four)}</b></span><span>현재 <b>{usdt(btc_price)}</b></span><span>위치 <b>{e(btc_position)}</b></span></div></div>{tv("BINANCE:BTCUSDT","D",False)}</div></section>
<section class="metrics"><div class="panel metric"><div class="metric-top"><div><h3>BTC.D</h3><strong>{float(btc_d.get('value') or 0):.2f}%</strong></div><span class="move {bd_cls}">{bd_move} {bd_arrow}</span></div>{tv("CRYPTOCAP:BTC.D","240",True)}</div><div class="panel metric"><div class="metric-top"><div><h3>TOTAL2</h3><strong>{money(total2.get('value_usd'))}</strong></div><span class="move {t2_cls}">{t2_move} {t2_arrow}</span></div>{tv("CRYPTOCAP:TOTAL2","240",True)}</div><div class="panel metric"><div class="metric-top"><div><h3>OTHERS</h3><strong>{money(others.get('value_usd'))}</strong></div><span class="move {ot_cls}">{ot_move} {ot_arrow}</span></div>{tv("CRYPTOCAP:OTHERS","240",True)}</div><div class="panel metric breadth"><h3>알트 확산도</h3><strong>{pct(all_ratio)}</strong><span class="move {breadth_cls}">{breadth_state}</span><div class="breadth-meter">{''.join('<i class="on"></i>' if isinstance(all_ratio,(int,float)) and i < round(all_ratio/10) else '<i></i>' for i in range(10))}</div><small>24H 상승 종목 비율</small></div><div class="panel metric exchange"><h3>거래소별 알트 확산도</h3><div class="exchange-lines"><div class="ex"><b style="color:#f5c533">BINANCE</b><div class="bar"><div class="fill bin" style="width:{max(0,min(100,float(binance_ratio or 0)))}%"></div></div><strong>{pct(binance_ratio)}</strong></div><div class="ex"><b style="color:#4d96ff">UPBIT</b><div class="bar"><div class="fill upb" style="width:{max(0,min(100,float(upbit_ratio or 0)))}%"></div></div><strong>{pct(upbit_ratio)}</strong></div></div><small>24H 상승 종목 비율</small></div></section>
<section class="bottom"><div class="panel summary"><h2>시장 요약</h2><div class="summary-stage">{e(stage)} {e(stage_name)}</div><div class="summary-word">숙돌이 · {e(mascot_word)}</div><img class="summary-cat" src="assets/sukdol_caution.webp" alt="숙돌이 방패"></div><div class="panel correction"><h2>⚠ BTC 조정 시나리오</h2><div class="levels"><div class="level one"><span>1차 방어</span><b>{usdt(corr.get('defense1'))}</b><em>단기 지지</em></div><div class="level two"><span>2차 방어</span><b>{usdt(corr.get('defense2'))}</b><em>중요 지지</em></div><div class="level bad"><span>구조 훼손</span><b>{usdt(corr.get('invalid'))}</b><em>구조 이탈</em></div></div><img class="risk-cat" src="assets/sukdol_stop.webp" alt="숙돌이 정지"></div></section>
<div class="foot"><span>BTC/BTC.D/TOTAL2/OTHERS · TradingView 캔들</span><span>업데이트 {e(updated)} KST</span></div></div></body></html>'''

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(doc, encoding="utf-8")
    inject_common_headers()
    print(OUT / "index.html")


if __name__ == "__main__":
    render()
