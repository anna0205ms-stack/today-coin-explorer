#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
BTC_FILE = OUT / "bitcoin_regime.json"
GLOBAL_FILE = OUT / "global_market_data.json"
REGIME_FILE = OUT / "market_regime.json"
UPBIT_BREADTH_FILE = OUT / "upbit_market_breadth.json"
BINANCE_FILE = OUT / "binance" / "latest.json"
KST = timezone(timedelta(hours=9))

STAGES = {
    "M0": ("위험장", "BTC 구조 훼손 · 알트 자금 이탈"),
    "M1": ("BTC 강세", "BTC 주도 · 알트 확산 약함"),
    "M2": ("알트 준비", "알트 버팀 · 순환 확인 전"),
    "M3": ("알트 시작", "BTC.D ↓ · TOTAL2 ↑ · OTHERS ↑"),
    "M4": ("알트 확산", "알트 상승 범위 확대"),
    "M5": ("과열 경계", "알트 확산 후 과열 구간"),
}


def read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def esc(value) -> str:
    import html
    return html.escape(str(value if value is not None else "-"))


def fmt_money(value: float | None) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    if abs(value) >= 1_000_000_000_000:
        return f"${value/1_000_000_000_000:.2f}T"
    if abs(value) >= 1_000_000_000:
        return f"${value/1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    return f"${value:,.0f}"


def fmt_usdt(value) -> str:
    return f"${float(value):,.0f}" if isinstance(value, (int, float)) else "-"


def direction(value, suffix="%"):
    if not isinstance(value, (int, float)):
        return "-", "flat"
    if value > 0:
        return f"+{value:.2f}{suffix} ↑", "up"
    if value < 0:
        return f"{value:.2f}{suffix} ↓", "down"
    return f"0.00{suffix} →", "flat"


def location_text(position):
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


def tradingview_chart():
    cfg = {
        "autosize": True,
        "symbol": "BINANCE:BTCUSDT",
        "interval": "D",
        "timezone": "Asia/Seoul",
        "theme": "dark",
        "style": "1",
        "locale": "kr",
        "backgroundColor": "rgba(5,8,12,1)",
        "gridColor": "rgba(42,46,57,0.35)",
        "hide_side_toolbar": False,
        "allow_symbol_change": False,
        "save_image": False,
        "calendar": False,
        "support_host": "https://www.tradingview.com"
    }
    config = json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")
    return f'''<div class="tv-wrap"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{config}</script></div></div>'''


def mascot_for(stage: str) -> str:
    if stage == "M0":
        return "assets/sukdol_stop.webp"
    if stage in {"M3", "M4"}:
        return "assets/sukdol_up.webp"
    return "assets/sukdol_caution.webp"


def header():
    return '''<header class="global-head"><a class="brand" href="index.html"><span class="brand-mark">✦</span><span><b>오늘의 코인 탐험대</b><small>통합 시장 대시보드</small></span></a><div class="market-switch"><a class="upbit" href="scan.html"><b>UPBIT</b><small>KRW</small></a><a class="binance" href="binance/scan.html"><b>BINANCE</b><small>SPOT USDT</small></a></div></header><nav class="main-nav"><a class="active" href="index.html">메인 대시보드</a><a href="scan.html">UPBIT 스캔</a><a href="binance/scan.html">BINANCE 스캔</a><a href="watchlist.html">UPBIT 관심</a><a href="binance/watchlist.html">BINANCE 관심</a><a href="history.html">기록</a><a href="training_a.html">훈련소</a></nav>'''


def common_subpage_header(is_binance: bool) -> str:
    if is_binance:
        home = "../index.html"
        upbit = "../scan.html"
        binance = "scan.html"
        active = "binance"
    else:
        home = "index.html"
        upbit = "scan.html"
        binance = "binance/scan.html"
        active = "upbit"
    return f'''<div class="oko-global-bar"><a class="oko-home" href="{home}"><span>✦</span><b>오늘의 코인 탐험대</b></a><div class="oko-market-switch"><a class="{'on' if active=='upbit' else ''}" href="{upbit}">UPBIT<small>KRW</small></a><a class="bin {'on' if active=='binance' else ''}" href="{binance}">BINANCE<small>SPOT USDT</small></a></div></div>'''


def inject_common_headers():
    upbit_pages = [OUT / "scan.html", OUT / "watchlist.html", OUT / "history.html"]
    upbit_pages += [OUT / f"type_{k}.html" for k in "abcde"]
    upbit_pages += [OUT / f"training_{k}.html" for k in "abcde"]
    binance_dir = OUT / "binance"
    binance_pages = [p for p in binance_dir.glob("*.html") if p.name != "index.html"] if binance_dir.exists() else []
    style = '''<style id="oko-global-style">.oko-global-bar{position:sticky;top:0;z-index:99999;height:66px;background:rgba(4,7,10,.97);backdrop-filter:blur(14px);border-bottom:1px solid #252b33;display:flex;align-items:center;justify-content:space-between;padding:0 24px;font-family:Inter,Pretendard,"Noto Sans KR",system-ui,sans-serif}.oko-home{display:flex;align-items:center;gap:11px;color:#fff;text-decoration:none;font-size:20px}.oko-home>span{width:34px;height:34px;border:1px solid #d5aa28;border-radius:50%;display:grid;place-items:center;color:#f2c33b}.oko-market-switch{display:flex;gap:8px}.oko-market-switch a{min-width:112px;padding:8px 14px;border-radius:12px;border:1px solid #303944;color:#9ba6b1;text-decoration:none;text-align:center;font-weight:800}.oko-market-switch a small{display:block;font-size:9px;font-weight:700;margin-top:2px}.oko-market-switch a.on{color:#05100d;background:#63e2bd;border-color:#63e2bd}.oko-market-switch a.bin.on{color:#171000;background:#f6c52d;border-color:#f6c52d}.oko-market-switch a.bin{border-color:#55430c}.app-brand{display:none!important}@media(max-width:640px){.oko-global-bar{padding:0 10px;height:58px}.oko-home b{font-size:15px}.oko-market-switch a{min-width:82px;padding:7px 8px;font-size:12px}}</style>'''
    for path, is_binance in [(p, False) for p in upbit_pages] + [(p, True) for p in binance_pages]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "oko-global-bar" in text:
            continue
        bar = common_subpage_header(is_binance)
        text = text.replace("</head>", style + "</head>", 1)
        pos = text.find(">", text.find("<body"))
        if pos >= 0:
            text = text[:pos+1] + bar + text[pos+1:]
        path.write_text(text, encoding="utf-8")


def render():
    btc = read(BTC_FILE, {})
    global_data = read(GLOBAL_FILE, {})
    regime = read(REGIME_FILE, {})
    upbit_breadth = read(UPBIT_BREADTH_FILE, {})
    binance = read(BINANCE_FILE, {})

    stage = str(regime.get("stage") or "M?")
    stage_name, stage_short = STAGES.get(stage, (str(regime.get("name") or "시장 확인"), "시장 데이터 확인"))
    market_color = {"M0":"#ff5d3a","M1":"#f0ba45","M2":"#f0cc64","M3":"#72d7a1","M4":"#45df8a","M5":"#ff8b73"}.get(stage, "#a6b0ba")

    g_btc_d = global_data.get("btc_d") or {}
    g_total2 = global_data.get("total2") or {}
    g_others = global_data.get("others") or {}
    g_breadth = global_data.get("breadth") or {}
    btc_d_chg, btc_d_cls = direction(g_btc_d.get("change_4h_pct_point"), "%p")
    total2_chg, total2_cls = direction(g_total2.get("change_4h_pct"))
    others_chg, others_cls = direction(g_others.get("change_4h_pct"))

    breg = binance.get("market_regime") or {}
    bbtc = breg.get("btc") or {}
    bbox = bbtc.get("box") or (btc.get("binance") or {}).get("box") or {}
    correction = bbtc.get("correction") or {}
    btc_price = bbtc.get("price") or (btc.get("binance") or {}).get("price")
    btc_daily = bbtc.get("daily_state") or "-"
    btc_four = bbtc.get("four_hour_state") or "-"
    btc_loc = location_text(bbox.get("position_pct"))

    global_ratio = g_breadth.get("positive_ratio_24h_pct")
    binance_ratio = (breg.get("breadth") or {}).get("positive_ratio_24h_pct")
    upbit_ratio = upbit_breadth.get("positive_ratio_24h_pct")

    def pct_value(v):
        return f"{v:.0f}%" if isinstance(v, (int,float)) else "-"

    latest_times = [global_data.get("generated_at"), binance.get("generated_at"), upbit_breadth.get("generated_at")]
    latest = max([str(x) for x in latest_times if x] or [datetime.now(KST).isoformat()])
    update_label = latest.replace("T", " ")[:16]

    stage_help = f'''<details class="stage-help"><summary>ⓘ {esc(stage)}가 뭔가</summary><div><b>{esc(stage)} · {esc(stage_name)}</b><span>{esc(stage_short)}</span><small>M0 위험 → M1 BTC 강세 → M2 알트 준비 → M3 알트 시작 → M4 알트 확산 → M5 과열</small></div></details>'''

    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>오늘의 코인 탐험대</title><style>
:root{{--bg:#05070a;--panel:#0d1117;--line:#252d37;--text:#f3f5f7;--muted:#94a0ad;--mint:#63e2bd;--gold:#f6c52d;--red:#ff665d;--purple:#a978ff;--market:{market_color}}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 50% -10%,#11141a 0,#05070a 33%);color:var(--text);font-family:Inter,Pretendard,"Noto Sans KR",system-ui,sans-serif}}.wrap{{max-width:1500px;margin:auto;padding:0 18px 44px}}.global-head{{position:sticky;top:0;z-index:1000;height:88px;display:flex;align-items:center;justify-content:space-between;background:rgba(5,7,10,.96);backdrop-filter:blur(16px);border-bottom:1px solid #202630;padding:0 10px}}.brand{{display:flex;align-items:center;gap:14px;color:#fff;text-decoration:none}}.brand-mark{{width:45px;height:45px;border:1px solid #d8af35;border-radius:50%;display:grid;place-items:center;color:#f7cf4c;font-size:23px}}.brand b{{display:block;font-size:26px}}.brand small{{display:block;color:#99a4af;margin-top:4px}}.market-switch{{display:flex;gap:10px}}.market-switch a{{min-width:142px;padding:10px 16px;border-radius:13px;text-align:center;text-decoration:none;border:1px solid #35404c}}.market-switch b{{display:block;font-size:15px}}.market-switch small{{display:block;font-size:10px;margin-top:3px}}.market-switch .upbit{{color:#7edfff;border-color:#174f84}}.market-switch .binance{{color:#f7c62e;border-color:#594608}}.main-nav{{display:flex;gap:4px;overflow:auto;border-bottom:1px solid #252b33;margin-bottom:18px}}.main-nav a{{color:#a2abb5;text-decoration:none;padding:13px 15px;white-space:nowrap;border-bottom:2px solid transparent}}.main-nav a.active{{color:#fff;border-color:var(--market)}}.hero{{display:grid;grid-template-columns:.82fr 1.38fr;gap:14px}}.panel{{background:linear-gradient(180deg,#0e1319,#090d12);border:1px solid var(--line);border-radius:18px;padding:18px}}.stage-panel{{position:relative;min-height:390px;overflow:hidden}}.stage-copy{{position:relative;z-index:3;width:58%;padding:12px 0 0 12px}}.stage-kicker{{color:#aeb7c0;font-size:13px}}.stage-code{{font-size:88px;font-weight:950;line-height:.9;color:var(--market);letter-spacing:-4px;margin-top:14px}}.stage-name{{font-size:30px;font-weight:900;margin-top:12px}}.stage-facts{{color:#a9b2bc;margin-top:12px;font-size:15px;line-height:1.7}}.mascot{{position:absolute;right:-12px;bottom:-25px;width:45%;max-height:355px;object-fit:contain;object-position:bottom;filter:drop-shadow(0 18px 28px #000)}}.stage-help{{position:absolute;z-index:5;left:28px;bottom:22px;width:58%;border:1px solid #303944;background:#080c11;border-radius:12px}}.stage-help summary{{cursor:pointer;padding:11px 13px;color:#dfe5eb;font-weight:800}}.stage-help>div{{padding:0 13px 12px;display:grid;gap:5px;color:#aab4be}}.stage-help b{{color:#fff}}.stage-help span{{font-size:13px}}.stage-help small{{font-size:11px;color:#7f8a95}}.btc-panel{{min-height:390px;padding:13px}}.btc-head{{display:flex;align-items:center;justify-content:space-between;padding:4px 6px 10px}}.btc-head h2{{margin:0;font-size:20px}}.btc-head .facts{{display:flex;gap:14px;color:#aab4be;font-size:12px;flex-wrap:wrap;justify-content:flex-end}}.btc-head .facts b{{color:#fff}}.tv-wrap{{height:320px;border:1px solid #202832;border-radius:12px;overflow:hidden}}.tradingview-widget-container,.tradingview-widget-container__widget{{height:100%;width:100%}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:14px}}.metric{{min-height:155px}}.metric h3{{margin:0;color:#cdd4db;font-size:15px}}.metric strong{{display:block;font-size:31px;margin-top:18px}}.metric .move{{display:block;margin-top:8px;font-weight:800}}.up{{color:#51d483}}.down{{color:#ff6b6b}}.flat{{color:#adb6bf}}.metric small{{display:block;color:#73808c;margin-top:15px}}.exchange-lines{{display:grid;gap:13px;margin-top:15px}}.ex-line{{display:grid;grid-template-columns:85px 1fr 52px;align-items:center;gap:8px}}.ex-line b{{font-size:13px}}.bar{{height:7px;border-radius:999px;background:#202730;overflow:hidden}}.fill{{height:100%;border-radius:inherit}}.fill.bin{{background:var(--gold)}}.fill.upb{{background:#4ca6ff}}.correction{{margin-top:14px;border-color:#5b2828;display:grid;grid-template-columns:210px 1fr;gap:20px;position:relative;overflow:hidden}}.correction-title{{padding:10px 0}}.correction-title h2{{margin:0;font-size:22px}}.correction-title p{{margin:8px 0 0;color:#8e99a5;font-size:12px}}.correction-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.level{{border:1px solid #343c46;border-radius:13px;padding:15px;background:#0a0e13}}.level span{{font-size:13px;color:#9ba6b1}}.level b{{display:block;font-size:25px;margin-top:7px}}.level.one b{{color:#55d89b}}.level.two b{{color:#f2b84d}}.level.bad b{{color:#ff6961}}.risk-cat{{position:absolute;left:108px;bottom:-70px;width:130px;opacity:.92}}.foot{{display:flex;justify-content:space-between;color:#6f7b86;font-size:11px;margin-top:13px;padding:0 4px}}@media(max-width:1000px){{.hero{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}.correction{{grid-template-columns:1fr}}.risk-cat{{display:none}}}}@media(max-width:640px){{.wrap{{padding:0 10px 30px}}.global-head{{height:72px}}.brand b{{font-size:18px}}.brand small{{display:none}}.brand-mark{{width:36px;height:36px}}.market-switch a{{min-width:84px;padding:8px}}.market-switch small{{font-size:8px}}.stage-code{{font-size:68px}}.stage-copy{{width:65%}}.mascot{{width:43%}}.stage-help{{width:calc(100% - 40px)}}.metrics{{grid-template-columns:1fr 1fr}}.correction-grid{{grid-template-columns:1fr}}.btc-head{{align-items:flex-start;gap:8px;flex-direction:column}}}}
</style></head><body><div class="wrap">{header()}<section class="hero"><div class="panel stage-panel"><div class="stage-copy"><div class="stage-kicker">현재 시장 단계</div><div class="stage-code">{esc(stage)}</div><div class="stage-name">{esc(stage_name)}</div><div class="stage-facts">BTC.D {"↓" if (g_btc_d.get("change_4h_pct_point") or 0)<0 else "↑" if (g_btc_d.get("change_4h_pct_point") or 0)>0 else "→"} · TOTAL2 {"↑" if (g_total2.get("change_4h_pct") or 0)>0 else "↓" if (g_total2.get("change_4h_pct") or 0)<0 else "→"} · OTHERS {"↑" if (g_others.get("change_4h_pct") or 0)>0 else "↓" if (g_others.get("change_4h_pct") or 0)<0 else "→"}<br>전체 알트 확산 {pct_value(global_ratio)}</div></div><img class="mascot" src="{mascot_for(stage)}" alt="숙돌이">{stage_help}</div><div class="panel btc-panel"><div class="btc-head"><h2>BTCUSDT</h2><div class="facts"><span>일봉 <b>{esc(btc_daily)}</b></span><span>4H <b>{esc(btc_four)}</b></span><span>현재 <b>{fmt_usdt(btc_price)}</b></span><span>위치 <b>{esc(btc_loc)}</b></span></div></div>{tradingview_chart()}</div></section><section class="metrics"><div class="panel metric"><h3>BTC.D</h3><strong>{g_btc_d.get("value",0):.2f}%</strong><span class="move {btc_d_cls}">{btc_d_chg}</span><small>4H</small></div><div class="panel metric"><h3>TOTAL2</h3><strong>{fmt_money(g_total2.get("value_usd"))}</strong><span class="move {total2_cls}">{total2_chg}</span><small>BTC 제외 시총</small></div><div class="panel metric"><h3>OTHERS</h3><strong>{fmt_money(g_others.get("value_usd"))}</strong><span class="move {others_cls}">{others_chg}</span><small>중소형 알트</small></div><div class="panel metric"><h3>전체 알트 확산</h3><strong>{pct_value(global_ratio)}</strong><span class="move {"up" if isinstance(global_ratio,(int,float)) and global_ratio>=60 else "flat"}">{"확산" if isinstance(global_ratio,(int,float)) and global_ratio>=60 else "중립" if isinstance(global_ratio,(int,float)) and global_ratio>=45 else "약세"}</span><small>24H 상승 종목 비율</small></div><div class="panel metric"><h3>거래소별 알트 확산</h3><div class="exchange-lines"><div class="ex-line"><b style="color:#f6c52d">BINANCE</b><div class="bar"><div class="fill bin" style="width:{max(0,min(100,float(binance_ratio or 0)))}%"></div></div><strong style="font-size:17px;margin:0">{pct_value(binance_ratio)}</strong></div><div class="ex-line"><b style="color:#58aaff">UPBIT</b><div class="bar"><div class="fill upb" style="width:{max(0,min(100,float(upbit_ratio or 0)))}%"></div></div><strong style="font-size:17px;margin:0">{pct_value(upbit_ratio)}</strong></div></div><small>24H 상승 종목 비율</small></div></section><section class="panel correction"><div class="correction-title"><h2>⚠ BTC 조정 시나리오</h2><p>BINANCE · BTCUSDT</p><img class="risk-cat" src="assets/sukdol_stop.webp" alt="숙돌이 경계"></div><div class="correction-grid"><div class="level one"><span>1차 방어</span><b>{fmt_usdt(correction.get("defense1"))}</b></div><div class="level two"><span>2차 방어</span><b>{fmt_usdt(correction.get("defense2"))}</b></div><div class="level bad"><span>구조 훼손</span><b>{fmt_usdt(correction.get("invalid"))}</b></div></div></section><div class="foot"><span>BTC 차트 · TradingView BINANCE:BTCUSDT</span><span>업데이트 {esc(update_label)} KST</span></div></div></body></html>'''

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    inject_common_headers()
    print(OUT / "index.html")


if __name__ == "__main__":
    render()
