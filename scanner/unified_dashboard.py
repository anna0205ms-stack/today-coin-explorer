#!/usr/bin/env python3
"""MVP Lite용 오늘·유형별·날짜별 정적 화면 생성."""
from __future__ import annotations

import html
import json
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
STORE = ROOT / "history" / "snapshots.json"
WATCH = ROOT / "history" / "watchlist.json"
BTC = OUT / "bitcoin_regime.json"
MARKET = OUT / "market_regime.json"
GLOBAL = OUT / "global_market_data.json"
INFO = {
    "A": ("A형", "#ff8297", "급등 후 첫 눌림", "강한 상승 → 거래량 감소 눌림 → 지지 확인 → 전고점 재도전", "매수존에서 하락 중단·저점 상승 확인", "첫 눌림 저점 또는 박스 하단 몸통 이탈", "직전 반등고점 → 급등고점 → 확장"),
    "B": ("B형", "#70c2ff", "바닥·박스 하단 반등", "장기 하락 → 바닥 박스 → 하단 재탈환 → 중심 반등", "박스 하단 재진입과 저점 상승 확인", "박스 최저점 또는 매수존 하단 몸통 이탈", "중심선 → 매도존 하단 → 박스 상단"),
    "C": ("C형", "#c3a7ff", "박스 상단 돌파·리테스트", "박스 횡보 → 상단 반복 접촉 → 돌파 → 상단 재지지", "완성봉 돌파 후 리테스트 방어 확인", "상단 아래 종가 복귀 또는 리테스트 저점 이탈", "박스 높이 확장 → 과거 매물대"),
    "D": ("D형", "#5ce2b3", "급등 전 재탈환·압축", "장기 하락 → 바닥 압축 → 매물대 하단 재탈환 → 4H 리테스트 → 상단 시도", "하단선 방어 또는 상단 돌파·재지지", "재탈환선 4H 몸통 이탈·하드스톱", "상단선 → 단기 확장 → 상위 매물대"),
    "E": ("E형", "#ffb454", "급락 후 0.382 기술적 반등", "급락·투매 → 핵심 하단 도달 → 4H 저점 방어 → 피보나치 0.382 반등", "투매저점 방어 + 4H 양봉·아래꼬리·저점 2% 회복", "투매저점 3% 하단 이탈 · 물타기 금지", "피보나치 0.382에서 전량청산 · 상승 전환 기대 금지"),
}
ACTION_RANK={"진입 검토":0,"조건부 진입":1,"확인 대기":2,"시장 대기":3,"진입가 대기":4,"익절 우선":5,"추격 금지":6}
D_STAGE_ORDER={"D4":0,"D3":1,"D2":2,"D1":3,"D0":4,"D-W":5,"D-F":6}
KST = timezone(timedelta(hours=9))
TRAINING_A_REV = "20260824-1"


def read(path: Path, default):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def asset_uri(name: str) -> str:
    path = OUT / "assets" / name
    if not path.exists():
        return f"assets/{name}"
    return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def fmt(value):
    if value is None:
        return "-"
    if isinstance(value, list):
        return " ~ ".join(fmt(x) for x in value) if value else "-"
    if isinstance(value, (int, float)):
        return f"{value:,.8f}".rstrip("0").rstrip(".")
    return html.escape(str(value))

def distance_to_entry(row):
    price=row.get("price"); entry=[x for x in row.get("entry",[]) if isinstance(x,(int,float))]
    if not isinstance(price,(int,float)) or not entry:return None
    lo,hi=min(entry),max(entry)
    if lo<=price<=hi:return 0.0
    edge=hi if price>hi else lo
    return round((price/edge-1)*100,1)

def action_badge(row):
    action=row.get("action","진입가 대기")
    style={"진입 검토":"act0","조건부 진입":"act1","확인 대기":"act1","시장 대기":"act2","진입가 대기":"act2","익절 우선":"act4","추격 금지":"act3"}.get(action,"act2")
    return f'<span class="badge {style}">{fmt(action)}</span>'

def remaining_condition(row):
    """현재판단 옆에 보여줄 실제 남은 확인 조건."""
    action = row.get("action", "진입가 대기")
    gate = row.get("market_gate") or {}
    if action in {"시장 대기", "조건부 진입", "익절 우선"} and gate.get("reason"):
        return f'{fmt(gate.get("stage"))} 시장판정 · {fmt(gate.get("reason"))}'
    missing = [fmt(value) for value in (row.get("missing") or []) if value not in (None, "", "없음")]
    if action == "진입 검토":
        return "업비트에서 완성봉·손익비 최종 확인"
    if action == "추격 금지":
        return "새 눌림 또는 새 구조 형성 대기"
    if missing and missing != ["관망"]:
        return " · ".join(missing)
    if action == "확인 대기":
        return "지지·리테스트 확인"
    return "계획한 진입구간 도착"

def action_cell(row):
    pattern = row.get("pattern_action")
    original = f'<div class="pattern-note">개별 차트 · {fmt(pattern)}</div>' if pattern and pattern != row.get("action") else ""
    return f'{action_badge(row)}{original}<div class="condition-note">남은 조건 · {remaining_condition(row)}</div>'

def action_guide():
    return '''<details class="action-guide" open><summary>🐱 현재판단 보는 법</summary><div class="action-guide-grid">
<div><span class="badge act0">진입 검토</span><p>조건을 충족했어. 업비트에서 완성봉과 손익비를 최종 확인해.</p></div>
<div><span class="badge act1">조건부 진입</span><p>개별 차트는 준비됐지만 시장이 완전히 열리지 않았어. 작은 비중으로 추가 조건까지 확인해.</p></div>
<div><span class="badge act1">확인 대기</span><p>후보는 맞지만 지지·리테스트 같은 마지막 조건을 더 확인해.</p></div>
<div><span class="badge act2">진입가 대기</span><p>구조는 관찰 중이야. 계획한 진입구간에 올 때까지 기다려.</p></div>
<div><span class="badge act3">추격 금지</span><p>진입 시점이 늦었어. 새 눌림이나 새 구조가 생기기 전에는 신규 매수하지 않아.</p></div>
<div><span class="badge act2">시장 대기</span><p>개별 차트는 좋아도 현재 시장 단계가 이 유형의 신규진입을 막고 있어.</p></div>
<div><span class="badge act4">익절 우선</span><p>과열 단계라 신규매수보다 기존 보유 물량의 수익 보호가 먼저야.</p></div>
</div><p class="guide-foot">오코탐은 후보를 빠르게 선별하는 도구야. 실제 진입은 업비트 차트에서 다시 확인해.</p></details>'''

def pattern_action_guide():
    """유형 후보 페이지는 시장 게이트가 아닌 개별 차트 모형만 설명한다."""
    return '''<details class="action-guide" open><summary>🐱 차트 현재판단 보는 법</summary><div class="action-guide-grid">
<div><span class="badge act0">진입 검토</span><p>해당 차트 모형의 진입 조건을 충족한 후보야.</p></div>
<div><span class="badge act1">확인 대기</span><p>모형은 맞지만 지지·리테스트 같은 마지막 차트 조건이 남았어.</p></div>
<div><span class="badge act2">진입가 대기</span><p>계획한 차트 진입구간에 올 때까지 관찰하는 후보야.</p></div>
<div><span class="badge act3">추격 금지</span><p>모형의 적정 진입구간을 이미 지나 새 눌림을 기다리는 상태야.</p></div>
</div><p class="guide-foot">이 페이지는 같은 차트 모형을 빠르게 모아 비교하는 곳이야.</p></details>'''

def pattern_row(row):
    """시장단계가 덮어쓴 행동을 제거하고 스캐너 원래 판정으로 되돌린다."""
    copy = dict(row)
    copy["action"] = row.get("pattern_action") or row.get("action") or "진입가 대기"
    copy["market_gate"] = {}
    return copy

def chart_svg(rows,width=600,height=160,levels=None):
    if not rows:return '<div class="empty">차트 데이터 없음</div>'
    rows=rows[-48:]; low=min(r[3] for r in rows); high=max(r[2] for r in rows); pad=max((high-low)*.08,high*.001);low-=pad;high+=pad
    y=lambda v:10+(high-v)/max(high-low,1e-9)*(height-20)
    step=width/len(rows); body=max(2,step*.55); parts=[f'<svg viewBox="0 0 {width} {height}">']
    for i,r in enumerate(rows):
        _,opn,hi,lo,close,_=r;x=(i+.5)*step;color="#00e783" if close>=opn else "#ff667e";top=min(y(opn),y(close));bottom=max(y(opn),y(close))
        parts.append(f'<line x1="{x:.1f}" y1="{y(hi):.1f}" x2="{x:.1f}" y2="{y(lo):.1f}" stroke="{color}"/><rect x="{x-body/2:.1f}" y="{top:.1f}" width="{body:.1f}" height="{max(1,bottom-top):.1f}" fill="{color}"/>')
    for value,color,label in levels or []:
        if isinstance(value,(int,float)) and low<=value<=high:
            yy=y(value);parts.append(f'<line x1="0" y1="{yy:.1f}" x2="{width}" y2="{yy:.1f}" stroke="{color}" stroke-dasharray="5 4"/><text x="5" y="{max(12,yy-3):.1f}" fill="{color}" font-size="10">{label} {fmt(value)}</text>')
    return ''.join(parts)+"</svg>"


def nav(active="dashboard"):
    links = [("메인 대시보드", "index.html", "dashboard"),
             ("관심종목 추적", "watchlist.html", "watch"), ("날짜별 기록", "history.html", "history")]
    cat = asset_uri("cat_entry.webp")
    scan_active = active == "today" or active.startswith("type_")
    scan_menu = f'''<details class="nav-drop" {"open" if scan_active else ""}><summary class="{"active" if scan_active else ""}">오늘의 전체 스캔 <span>▾</span></summary><div class="nav-drop-menu"><a class="{"active" if active == "today" else ""}" href="scan.html">전체 보기</a>{''.join(f'<a class="{"active" if active == f"type_{key.lower()}" else ""}" href="type_{key.lower()}.html">{key}형</a>' for key in "ABCDE")}</div></details>'''
    training_active = active.startswith("training_")
    training_menu = f'''<details class="nav-drop" {"open" if training_active else ""}><summary class="{"active" if training_active else ""}">훈련소 <span>▾</span></summary><div class="nav-drop-menu">{''.join(f'<a class="{"active" if active == f"training_{key.lower()}" else ""}" href="training_{key.lower()}.html{"?v=" + TRAINING_A_REV if key == "A" else ""}">{key}형</a>' for key in "ABCDE")}</div></details>'''
    first = f'<a class="{"active" if active == "dashboard" else ""}" href="index.html">메인 대시보드</a>'
    rest = "".join(f'<a class="{"active" if active == key else ""}" href="{url}">{name}</a>' for name, url, key in links[1:])
    return f'<nav><div class="app-brand"><img class="nav-cat" src="{cat}" alt="회색 고양이"><span class="app-title">오늘의 코인 탐험대</span></div>{first}{scan_menu}{training_menu}{rest}</nav>'


def css():
    return """
:root{--bg:#030605;--panel:#0b1210;--inner:#111e18;--line:#174b35;--green:#00e783;--text:#f5fff8;--sub:#91a79b}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,#072217 0,transparent 25%),var(--bg);color:var(--text);font:14px/1.5 Arial,"Noto Sans KR",sans-serif}main{max-width:1380px;margin:auto;padding:28px}a{color:inherit;text-decoration:none}header{display:flex;justify-content:space-between;gap:18px;align-items:center}h1{margin:0;font-size:30px}h2{margin:0 0 12px}.sub{color:var(--sub)}.green{color:var(--green)}nav{display:flex;gap:8px;margin:22px 0;flex-wrap:wrap}nav a{padding:9px 14px;border:1px solid var(--line);border-radius:999px;background:#0b1511}nav a.active{border-color:var(--green);color:var(--green)}.date{padding:13px 19px;border:1px solid var(--green);border-radius:30px;background:#0b1511}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.type{position:relative;min-height:145px;padding:18px;border:1px solid;border-radius:20px;background:linear-gradient(145deg,#0b1210,#111d17)}.type strong{display:block;font-size:34px}.mascot{position:absolute;right:22px;top:40px;width:58px;height:54px;background:white;border-radius:48% 55% 45% 52%}.mascot:before{content:"• ᴗ •";position:absolute;color:#142019;left:13px;top:17px;font-weight:900}.panel{margin:17px 0;padding:20px;border:1px solid var(--line);border-radius:20px;background:linear-gradient(145deg,#0b1210,#111b16);overflow:auto}.candidate-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.candidate{padding:15px;border-radius:14px;background:var(--inner);border:1px solid #1e3b2d}.candidate b{font-size:17px}.kv{display:grid;grid-template-columns:auto 1fr;gap:5px 10px;margin-top:10px}.kv span:nth-child(odd){color:var(--sub)}.kv span:nth-child(even){text-align:right}.badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#20382c}.act0{color:#8ff0bd;border:1px solid #238b57}.act1{color:#ffd77f;background:#4e3b12}.act2{color:#bdd2c5}.act3{color:#ff9bac;background:#542326}.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.rule{padding:15px;border-radius:14px;background:var(--inner)}.rule b{display:block;color:var(--green);margin-bottom:6px}.flow{padding:18px;border:1px dashed var(--green);border-radius:14px;color:#c8ffdf}.chart{margin:12px 0 4px;border-radius:12px;background:#07100c;border:1px solid #173a2b;overflow:hidden}.chart svg{width:100%;height:auto;display:block}.reason{margin-top:10px;padding:10px;border-left:2px solid var(--green);background:#0a1611}.compact{display:grid;grid-template-columns:1.2fr .8fr .8fr 1fr 1fr;gap:8px;padding:10px;border-bottom:1px solid #1e3b2d;align-items:center}.star{border:0;background:transparent;color:#64756c;font-size:22px;cursor:pointer}.star.on{color:#ffd166}.timeline{font-size:12px;color:var(--sub);margin-top:8px}select{background:#0b1511;color:var(--text);border:1px solid var(--green);border-radius:12px;padding:10px}.empty{padding:30px;text-align:center;color:var(--sub)}@media(max-width:900px){.grid4,.rules{grid-template-columns:1fr 1fr}.candidate-grid{grid-template-columns:1fr}.compact{grid-template-columns:1fr 1fr}}@media(max-width:600px){main{padding:14px}.grid4,.rules{grid-template-columns:1fr}header{align-items:flex-start;flex-direction:column}.date{width:100%}}
.brand{display:flex;align-items:center;gap:12px}.nav-cat{width:42px;height:42px;border-radius:50%;object-fit:cover;object-position:50% 13%;margin-right:10px}.cat-face{width:48px;height:48px;border-radius:50%;object-fit:cover;object-position:50% 13%;border:1px solid var(--green);background:#111}.btc-card{display:grid;grid-template-columns:300px minmax(430px,1fr);gap:26px;align-items:center;padding:28px 32px;border:1px solid var(--state);border-radius:18px;background:#030605}.btc-price{font-size:28px;font-weight:800;margin:5px 0}.state-entry{--state:#00e783;--state-bg:#082418}.state-caution{--state:#ffc247;--state-bg:#2a210c}.state-stop{--state:#ff5d3a;--state-bg:#2b100a}.status-chip{display:block;margin:8px 0;padding:7px 11px;border:1px solid var(--state);border-radius:999px}.cat-main{width:180px;height:205px;object-fit:contain;filter:drop-shadow(0 12px 20px #000)}.action-card{display:grid;grid-template-columns:150px 1fr 1fr;gap:26px;align-items:center;padding:28px 34px;border:1px solid var(--state);border-radius:18px;background:var(--state-bg)}.warning-mark{font-size:78px;line-height:1;text-align:center;color:var(--state)}.action-big{font-size:42px;font-weight:900;color:var(--state)}.action-lines{border-left:1px solid var(--state);padding-left:34px}.action-lines div{margin:9px 0}.top-table{width:100%;border-collapse:collapse}.top-table th,.top-table td{padding:12px 10px;border-bottom:1px solid #23372d;text-align:left;white-space:nowrap}.top-table th{color:var(--green);font-size:12px}.candidate-row{position:relative}.trade-lock{display:inline-block;margin-left:8px;padding:2px 7px;border-radius:999px;background:#5a1b13;color:#ffb5a6;font-size:11px}.blocked-row{color:#b9aaa6;background:linear-gradient(90deg,rgba(80,18,10,.26),transparent)}.blocked-row td:first-child:before{content:"거래금지";display:inline-block;margin-right:7px;padding:2px 6px;border:1px solid #ff5d3a;border-radius:6px;color:#ff7b61;font-size:10px}.table-wrap{overflow:auto}.dashboard-panel{margin:17px 0;padding:20px;border:1px solid var(--line);border-radius:18px;background:#030605}@media(max-width:900px){.btc-card{grid-template-columns:1fr}.cat-main{height:180px}.action-card{grid-template-columns:1fr}.warning-mark{text-align:left}.action-lines{border-left:0;border-top:1px solid var(--state);padding:15px 0 0}}@media(max-width:600px){.action-big{font-size:30px}.btc-card{padding:16px}}
.act0{color:#a9ffd0;background:#123c27;border:1px solid #35d47f}.act1{color:#ffe39a;background:#4e3b12;border:1px solid #d9a928}.act2{color:#cae0ff;background:#1c314d;border:1px solid #588bcc}.act3{color:#ffb0be;background:#542326;border:1px solid #d95770}.condition-note{max-width:250px;margin-top:5px;color:#b6c5bc;font-size:11px;line-height:1.35;white-space:normal}.action-guide{margin:10px 0 17px;padding:12px 14px;border:1px solid #29483a;border-radius:14px;background:#07110c}.action-guide summary{cursor:pointer;color:#dcf8e7;font-weight:800}.action-guide-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:12px}.action-guide-grid>div{padding:11px;border:1px solid #233d31;border-radius:12px;background:#0b1611}.action-guide-grid p{margin:7px 0 0;color:#b9c8c0;font-size:12px}.guide-foot{margin:10px 0 0;color:#8fa399;font-size:12px}@media(max-width:900px){.action-guide-grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.action-guide-grid{grid-template-columns:1fr}.condition-note{max-width:190px}}
nav{display:flex;gap:24px;margin:0 0 20px;align-items:center;flex-wrap:wrap}.app-brand{display:flex;align-items:center;gap:10px;margin-right:8px}.app-title{font-size:18px;font-weight:900;color:#f4fff8;white-space:nowrap}.app-brand .nav-cat{margin-right:0}nav a{padding:14px 8px;border:0;border-bottom:2px solid transparent;border-radius:0;background:transparent;font-size:16px}nav a.active{border-color:var(--green);color:var(--green)}
.nav-drop{position:relative}.nav-drop summary{list-style:none;padding:14px 8px;border-bottom:2px solid transparent;font-size:16px;cursor:pointer}.nav-drop summary::-webkit-details-marker{display:none}.nav-drop summary.active{border-color:var(--green);color:var(--green)}.nav-drop-menu{position:absolute;z-index:40;left:0;top:48px;display:grid;min-width:150px;padding:7px;border:1px solid var(--line);border-radius:12px;background:#07100c;box-shadow:0 14px 28px #000}.nav-drop:not([open]) .nav-drop-menu{display:none}.nav-drop-menu a{padding:9px 12px;border:0;border-radius:8px;font-size:14px}.nav-drop-menu a:hover,.nav-drop-menu a.active{background:#0d2118;color:var(--green)}
.dual-chart{display:grid;grid-template-columns:1fr 1fr;gap:14px}.chart-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;font-weight:800}.chart-title small{color:var(--sub);font-weight:400}@media(max-width:900px){.dual-chart{grid-template-columns:1fr}}
.page-intro{margin:4px 0 18px}.page-intro h1{margin:0 0 4px}.how{margin-top:7px;color:#c8ffdf}.tip{position:relative;display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;margin-left:4px;border:1px solid #60756a;border-radius:50%;color:#a9b9b0;font-size:10px;cursor:help}.tip:hover:after{content:attr(data-tip);position:absolute;z-index:20;left:0;top:22px;width:220px;padding:9px;border:1px solid var(--green);border-radius:9px;background:#07100c;color:#fff;font-weight:400;white-space:normal}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.filter{padding:8px 13px;border:1px solid #31473c;border-radius:999px;background:#08100c;color:#fff;cursor:pointer}.filter.active{border-color:var(--accent,var(--green));color:var(--accent,var(--green))}.data-table{width:100%;border-collapse:collapse}.data-table th,.data-table td{padding:11px 9px;border-bottom:1px solid #26372f;text-align:left;white-space:nowrap}.data-table th{color:#a6b8ad;font-size:12px}.type-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.type-tab{padding:17px;border:1px solid var(--c);border-radius:16px;background:#050807}.type-tab strong{font-size:28px;color:var(--c)}.type-tab.active{box-shadow:0 0 16px color-mix(in srgb,var(--c) 35%,transparent);background:color-mix(in srgb,var(--c) 9%,#050807)}.expand{display:none}.expand.open{display:table-row}.expand td{padding:16px;background:#07100c}.expand-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.target-strip{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}.target-chip{padding:8px 12px;border:1px solid var(--accent,var(--green));border-radius:10px}.help-note{padding:10px 12px;border-left:2px solid var(--accent,var(--green));background:#0a1510;color:#cbd8d0}.calendar-layout{display:grid;grid-template-columns:300px 1fr;gap:16px}.calendar{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}.day{padding:9px;text-align:center;border-radius:8px}.day.has{color:#bfffd9}.day.selected{outline:1px solid var(--green);background:#0a2a19}.outcome{padding:3px 8px;border-radius:999px}.ok{color:#73eaa8;border:1px solid #23754b}.wait{color:#ffd166;border:1px solid #755b22}.bad{color:#ff8b78;border:1px solid #82372c}.muted{color:#a5b0aa;border:1px solid #45534b}@media(max-width:900px){.type-tabs,.calendar-layout,.expand-grid{grid-template-columns:1fr}.data-table{font-size:12px}}
.hero-guide{display:grid;grid-template-columns:1fr 190px;gap:20px;align-items:center;border-color:var(--accent)}.type-cat-wrap{position:relative;height:190px}.type-cat-wrap img{width:100%;height:100%;object-fit:contain}.type-token{position:absolute;right:7px;top:16px;width:58px;height:58px;border:3px solid var(--accent);border-radius:50%;background:#050807;color:var(--accent);font-size:28px;font-weight:900;text-align:center;line-height:52px}.row-click{cursor:pointer}.row-click:hover{background:#0d1b14}.section-label{margin:20px 0 8px;color:var(--accent,var(--green))}.status-line{display:flex;gap:12px;flex-wrap:wrap}.mini-stat{padding:10px 14px;border:1px solid #294438;border-radius:12px}.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.date-buttons{display:flex;gap:7px;flex-wrap:wrap}.date-btn{padding:8px 11px;border:1px solid #31473c;border-radius:10px;background:#08100c;color:#fff}.date-btn.active{border-color:var(--green);color:var(--green)}@media(max-width:900px){.hero-guide{grid-template-columns:1fr}.type-cat-wrap{height:150px}}
.system-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 18px;padding:11px 14px;border:1px solid #244b38;border-radius:14px;background:#07110c}.system-dot{width:9px;height:9px;border-radius:50%;background:#00e783;box-shadow:0 0 10px #00e783}.system-bar.waiting .system-dot{background:#ffc247;box-shadow:0 0 10px #ffc247}.system-bar.late .system-dot{background:#ff5d3a;box-shadow:0 0 10px #ff5d3a}.system-divider{color:#365443}.update-stamp{margin-top:7px;color:var(--sub);font-size:12px}@media(max-width:600px){.system-bar{align-items:flex-start}.system-divider{display:none}.system-item{width:100%}}
.training-tabs{display:flex;gap:8px;margin:10px 0 18px}.training-tab{padding:9px 15px;border:1px solid var(--line);border-radius:10px}.training-tab.active{border-color:#ff8297;color:#ff8297;background:#170b0e}.stage-rail{display:grid;grid-template-columns:repeat(8,1fr);gap:7px;margin:14px 0}.stage-card{padding:11px;border:1px solid #31473c;border-radius:11px;background:#08100c}.stage-card strong{display:block;font-size:16px}.stage-card span{color:var(--sub);font-size:12px}.stage-card.hot{border-color:var(--green);background:#082418}.stage-card.hot strong{color:var(--green)}.stage-matrix{width:100%;border-collapse:collapse}.stage-matrix th,.stage-matrix td{padding:10px;border-bottom:1px solid #26372f;text-align:left;vertical-align:top}.stage-matrix th{color:var(--sub);font-size:12px}.training-grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:14px}.training-chart{border:1px solid #173a2b;border-radius:12px;background:#07100c;overflow:hidden}.training-chart svg{display:block;width:100%;height:auto}.training-notes{border:1px solid #26372f;border-radius:12px;overflow:hidden}.training-note{padding:12px;border-bottom:1px solid #26372f}.training-note:last-child{border:0}.training-note b{display:block;color:var(--green);margin-bottom:3px}.precision-table{width:100%;border-collapse:collapse}.precision-table th,.precision-table td{padding:10px;border-bottom:1px solid #26372f;text-align:left;vertical-align:top}.precision-table th{color:var(--sub);font-size:12px}.scenario-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.scenario{padding:14px;border:1px solid #294438;border-radius:14px;background:#07100c}.scenario.success{border-color:#00e783}.scenario.warning{border-color:#ffd166}.scenario.failure{border-color:#ff667e}.scenario h3{margin:0 0 8px}.scenario svg{width:100%;height:auto;display:block;border-bottom:1px solid #26372f;margin-bottom:9px}.scenario dl{margin:0}.scenario dt{margin-top:8px;font-weight:800}.scenario dd{margin:2px 0;color:var(--sub)}.training-close{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;margin-top:16px;border:1px solid var(--line);background:var(--line)}.training-close div{padding:13px;background:#07100c}.training-close b{display:block;margin-bottom:4px}.training-close span{color:var(--sub)}@media(max-width:900px){.stage-rail{grid-template-columns:repeat(4,1fr)}.training-grid,.scenario-grid{grid-template-columns:1fr}.training-close{grid-template-columns:1fr 1fr}}@media(max-width:600px){.stage-rail,.training-close{grid-template-columns:1fr 1fr}.nav-drop-menu{position:static;margin-top:4px}}
.daily-context-layout{display:grid;grid-template-columns:210px minmax(0,1fr);gap:18px;align-items:start}.context-copy{display:grid;gap:10px}.context-point{padding:10px 0;border-bottom:1px solid #26372f}.context-point:last-child{border:0}.context-point b{display:block;color:#dfffee}.context-point span{color:var(--sub)}.timeframe-flow{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0 16px}.timeframe-flow div{padding:10px;border:1px solid #294438;border-radius:11px;background:#07100c;text-align:center}.timeframe-flow b{display:block;color:var(--green)}.mtf-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.mtf-card{padding:13px;border:1px solid #294438;border-radius:14px;background:#07100c}.mtf-card h3{margin:0}.mtf-card p{min-height:42px;margin:4px 0 9px;color:var(--sub)}.mtf-card svg{display:block;width:100%;height:auto}.chart-legend{display:flex;gap:14px;flex-wrap:wrap;margin:0 0 12px;color:var(--sub)}.chart-legend span:before{content:"";display:inline-block;width:18px;height:7px;margin-right:6px;border-radius:4px;background:var(--legend)}.stage-detail-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.stage-detail{display:grid;grid-template-columns:90px 1fr;gap:10px;padding:12px;border:1px solid #294438;border-radius:12px;background:#07100c}.stage-detail strong{color:var(--green);font-size:16px}.stage-detail p{margin:2px 0;color:var(--sub)}.stage-detail b{color:var(--text)}.exit-grid{display:grid;grid-template-columns:minmax(280px,.8fr) minmax(360px,1.2fr);gap:16px}.exit-rules{display:grid}.exit-rule{padding:10px 0;border-bottom:1px solid #26372f}.exit-rule:last-child{border:0}.exit-rule b{display:block}.exit-rule span{color:var(--sub)}@media(max-width:900px){.daily-context-layout,.exit-grid{grid-template-columns:1fr}.mtf-grid{grid-template-columns:1fr}.timeframe-flow{grid-template-columns:1fr 1fr}.stage-detail-grid{grid-template-columns:1fr}}@media(max-width:600px){.timeframe-flow{grid-template-columns:1fr}.stage-detail{grid-template-columns:75px 1fr}}
.grid4,.type-tabs{grid-template-columns:repeat(5,1fr)}@media(max-width:900px){.grid4,.type-tabs{grid-template-columns:1fr 1fr}}@media(max-width:600px){.grid4,.type-tabs{grid-template-columns:1fr}}
.strategy-model{margin:0 0 18px;padding:18px;border:1px solid var(--accent);border-radius:18px;background:#050807}.strategy-model h2{margin:0 0 5px;color:var(--accent)}.strategy-model img{display:block;width:100%;height:auto;margin-top:14px;border:1px solid #294438;border-radius:14px}.stage-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}.stage-card{padding:13px;border:1px solid #31473c;border-radius:12px;background:#0a1310}.stage-card b{display:block;margin-bottom:5px;color:var(--accent)}.stage-card.danger{border-color:#87404a}.stage-card.danger b{color:#ff8297}@media(max-width:900px){.stage-grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.stage-grid{grid-template-columns:1fr}}
.e-mtf-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.e-mtf-card{padding:13px;border:1px solid #294438;border-radius:14px;background:#07100c}.e-mtf-card h3{margin:0}.e-mtf-card p{min-height:64px;margin:5px 0 10px;color:var(--sub)}.e-mtf-card svg{display:block;width:100%;height:auto}.e-plan-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.e-plan{padding:13px;border-top:2px solid var(--accent);background:#07100c}.e-plan b{display:block;margin-bottom:5px}.e-plan span{color:var(--sub)}.e-scenario-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.e-scenario-panel{display:none;grid-template-columns:minmax(0,1.2fr) minmax(260px,.8fr);gap:18px;align-items:center}.e-scenario-panel.open{display:grid}.e-scenario-panel svg{display:block;width:100%;height:auto}.e-scenario-copy{display:grid;gap:10px}.e-scenario-copy p{margin:0;color:var(--sub)}.e-check-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.e-check{padding:12px;border-top:1px solid #294438}.e-check b{display:block;margin-bottom:4px}.e-check span{color:var(--sub)}@media(max-width:900px){.e-mtf-grid,.e-plan-grid,.e-check-grid{grid-template-columns:1fr 1fr}.e-scenario-panel{grid-template-columns:1fr}}@media(max-width:600px){.e-mtf-grid,.e-plan-grid,.e-check-grid{grid-template-columns:1fr}}
.act4{color:#9fc4ff;background:#17345b;border:1px solid #568bd5}.pattern-note{margin-top:5px;color:#d5e7dc;font-size:11px}.market-hero{display:grid;grid-template-columns:170px minmax(0,1fr) 260px;gap:20px;align-items:center;border-color:var(--market-color)}.market-stage{display:grid;place-items:center;width:120px;height:120px;border:1px solid var(--market-color);border-radius:50%;background:#07100c;font-size:30px;font-weight:900}.market-stage small{display:block;font-size:12px;color:var(--sub);text-align:center}.market-title{font-size:32px;font-weight:900;color:var(--market-color)}.market-reason-title{margin-top:10px;color:var(--text);font-size:12px;font-weight:900}.market-reasons{margin:5px 0 0;padding-left:18px;color:var(--sub)}.market-limit{text-align:center}.market-limit strong{display:block;font-size:38px;color:var(--market-color)}.market-mascot{display:flex;align-items:center;gap:24px;margin-top:-9px;border-color:var(--market-color);background:linear-gradient(90deg,#030605,#07100c)}.market-mascot-copy b{display:block;margin-bottom:6px;color:var(--market-color);font-size:22px}.market-flow-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:14px 0}.market-flow-stat{padding:11px;border:1px solid var(--line);border-radius:11px;background:#050a07}.market-flow-stat b{display:block;color:var(--green);font-size:16px}.gate-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;border:1px solid var(--line);background:var(--line)}.gate-item{padding:13px;background:#07100c}.gate-item b{display:block;margin-bottom:5px}.gate-item span{display:inline-block;margin-bottom:5px;font-weight:800}.gate-ALLOW span{color:#00e783}.gate-CONDITIONAL span,.gate-WATCH span{color:#ffd166}.gate-BLOCK span{color:#ff667e}.gate-PROTECT span{color:#70a7ff}.market-chart-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.tv-card{min-height:330px;padding:12px;border:1px solid var(--line);border-radius:14px;background:#07100c}.tv-card h3{margin:0 0 7px}.tradingview-widget-container{height:285px}.tradingview-widget-container__widget{height:100%}.proxy-note{margin-top:8px;color:var(--sub);font-size:11px}.gate-chip{display:block;margin-top:4px;color:var(--sub);font-size:11px}@media(max-width:900px){.market-hero{grid-template-columns:120px 1fr}.market-limit{grid-column:1/-1;text-align:left}.market-mascot{align-items:flex-start}.market-flow-strip,.gate-grid,.market-chart-grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.market-hero,.market-flow-strip,.gate-grid,.market-chart-grid{grid-template-columns:1fr}.market-stage{width:88px;height:88px}.market-title{font-size:24px}.market-mascot{flex-direction:column;align-items:center}.market-mascot-copy{text-align:center}}
.btc-live-card{border-color:#1f8d5f}.btc-live-head{display:flex;justify-content:space-between;gap:18px;align-items:end;margin-bottom:12px}.btc-live-head h2{margin:0;color:#ffd166}.btc-summary-grid{display:grid;grid-template-columns:1.1fr 1fr 1.3fr 1.5fr;gap:8px;margin:12px 0}.btc-summary-item{padding:10px 12px;border:1px solid var(--line);border-radius:11px;background:#050a07}.btc-summary-item span{display:block;color:var(--sub);font-size:11px}.btc-summary-item b{display:block;margin-top:3px;color:var(--text)}.btc-tv-wrap{height:520px;border:1px solid var(--line);border-radius:14px;overflow:hidden}.btc-tv-wrap .tradingview-widget-container{height:100%}@media(max-width:900px){.btc-summary-grid{grid-template-columns:1fr 1fr}.btc-live-head{align-items:start;flex-direction:column}.btc-tv-wrap{height:460px}}@media(max-width:600px){.btc-summary-grid{grid-template-columns:1fr}.btc-tv-wrap{height:390px}}
.market-stage-guide{border-color:var(--market-color)}.market-stage-guide h2{margin-bottom:4px}.market-stage-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.market-stage-card{padding:13px;border:1px solid #294438;border-radius:13px;background:#07100c}.market-stage-card strong{display:block;margin-bottom:4px;color:var(--stage-color);font-size:17px}.market-stage-card span{color:var(--sub)}.market-stage-card.current{border-color:var(--stage-color);background:color-mix(in srgb,var(--stage-color) 11%,#07100c);box-shadow:0 0 14px color-mix(in srgb,var(--stage-color) 22%,transparent)}.market-stage-card.current:before{content:"현재 단계";display:inline-block;margin-bottom:7px;padding:2px 7px;border-radius:999px;background:var(--stage-color);color:#041008;font-size:10px;font-weight:900}@media(max-width:900px){.market-stage-grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.market-stage-grid{grid-template-columns:1fr}}
"""


def tip(label, text):
    return f'{label}<span class="tip" data-tip="{html.escape(text, quote=True)}">ⓘ</span>'


def page_intro(title, purpose, how):
    return f'<section class="page-intro"><h1>{title}</h1><div class="sub">{purpose}</div><div class="how">{how}</div></section>'


def market_gate_panel(regime):
    gates = regime.get("gates") or {}
    icons = {"ALLOW": "✓", "CONDITIONAL": "△", "WATCH": "○", "BLOCK": "×", "PROTECT": "↘"}
    labels = {
        "A": "강한 상승 후 눌림", "B": "바닥 추세반전", "C": "돌파 후 재지지",
        "D": "급등 전 재탈환", "E": "급락 후 기술적 반등",
    }
    cells = []
    for key in "ABCDE":
        gate = gates.get(key) or {"code": "BLOCK", "label": "판정 없음", "reason": "시장 데이터 확인 대기"}
        code = gate.get("code", "BLOCK")
        cells.append(f'<div class="gate-item gate-{fmt(code)}"><b>{key}형 · {labels[key]}</b><span>{icons.get(code,"·")} {fmt(gate.get("label"))}</span><div class="sub">{fmt(gate.get("reason"))}</div></div>')
    return f'<section class="panel"><h2>현재 시장에서 A~E형을 어떻게 볼까?</h2><div class="sub">개별 차트 조건을 충족해도 이 허용표가 최종 행동을 결정해.</div><div class="gate-grid" style="margin-top:12px">{"".join(cells)}</div></section>'


def tradingview_widget(symbol, title, note):
    config = json.dumps({
        "autosize": True, "symbol": symbol, "interval": "240", "timezone": "Asia/Seoul",
        "theme": "dark", "style": "1", "locale": "kr", "allow_symbol_change": False,
        "calendar": False, "support_host": "https://www.tradingview.com",
    }, ensure_ascii=False).replace("</", "<\\/")
    return f'''<div class="tv-card"><h3>{title}</h3><div class="sub">{note}</div><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{config}</script></div></div>'''


def bitcoin_tradingview_widget():
    """메인 최상단용 BTC 차트. TradingView 상단 메뉴에서 일봉·4H를 바꾼다."""
    config = json.dumps({
        "autosize": True, "symbol": "BINANCE:BTCUSDT", "interval": "240", "timezone": "Asia/Seoul",
        "theme": "dark", "style": "1", "locale": "kr", "allow_symbol_change": False,
        "calendar": False, "support_host": "https://www.tradingview.com",
    }, ensure_ascii=False).replace("</", "<\\/")
    return f'''<div class="btc-tv-wrap"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{config}</script></div></div>'''


def box_location_text(box):
    """내부 계산용 백분율을 사람이 이해할 가격 위치로 바꾼다."""
    value = box.get("position_pct")
    if not isinstance(value, (int, float)):
        return "위치 확인 전"
    if value < 0:
        return "기존 30일 박스 하단 아래"
    if value <= 15:
        return "기존 30일 박스 하단 매수구간"
    if value <= 45:
        return "기존 30일 박스 하단과 중심 사이"
    if value <= 60:
        return "기존 30일 박스 중심 부근"
    if value < 70:
        return "기존 30일 박스 상단 접근 중"
    if value <= 100:
        return "기존 30일 박스 상단 구간"
    return "기존 30일 박스 상단 돌파 후 위에서 거래 중"


def system_status(basis):
    stamp = str((basis or {}).get("snapshot_at") or "")
    visible = stamp.replace("T", " ")[:16] if stamp else "기록 전"
    return f'''<section class="system-bar" id="systemBar" data-last="{html.escape(stamp, quote=True)}"><span class="system-dot"></span><b id="systemState">상태 확인 중</b><span class="system-divider">|</span><span class="system-item">최근 스캔 기준봉 · <b>{visible} KST</b></span><span class="system-divider">|</span><span class="system-item" id="nextLabel">다음 자동 갱신 · <b id="nextUpdate">계산 중</b></span></section><script>(function(){{const bar=document.getElementById("systemBar"),state=document.getElementById("systemState"),nextEl=document.getElementById("nextUpdate"),nextLabel=document.getElementById("nextLabel"),hours=[1,5,9,13,17,21],now=new Date(),kst=new Date(now.getTime()+9*3600000),y=kst.getUTCFullYear(),m=kst.getUTCMonth(),d=kst.getUTCDate();const slot=(dd,h)=>new Date(Date.UTC(y,m,dd,h-9));let closed=hours.map(h=>slot(d,h)).filter(x=>x<=now).pop();if(!closed)closed=slot(d-1,21);let next=hours.map(h=>slot(d,h)).find(x=>x>now);if(!next)next=slot(d+1,1);const last=bar.dataset.last?new Date(bar.dataset.last):null,fmt=x=>new Intl.DateTimeFormat("ko-KR",{{timeZone:"Asia/Seoul",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}}).format(x),hour=x=>new Intl.DateTimeFormat("ko-KR",{{timeZone:"Asia/Seoul",hour:"2-digit",minute:"2-digit",hour12:false}}).format(x);if(last&&last>=closed){{state.textContent="정상 작동";nextEl.textContent=fmt(next)+" KST"}}else{{const retry=new Date(Math.ceil((now.getTime()+1000)/600000)*600000);nextLabel.firstChild.textContent="다음 자동 복구 확인 · ";nextEl.textContent=fmt(retry)+" KST";if(now-closed<=40*60000){{bar.classList.add("waiting");state.textContent=hour(closed)+" 마감봉 갱신 중"}}else{{bar.classList.add("late");state.textContent=hour(closed)+" 갱신 지연 · 자동복구 대기"}}}}}})()</script>'''


def shell(title, body, basis, active="dashboard"):
    pins='''<script>function getPins(){try{return JSON.parse(localStorage.getItem("upbitPins")||"[]")}catch(e){return []}}function togglePin(m,b){let p=getPins();p=p.includes(m)?p.filter(x=>x!==m):[...p,m];localStorage.setItem("upbitPins",JSON.stringify(p));if(b){b.classList.toggle("on",p.includes(m));b.textContent=p.includes(m)?"★":"☆"}if(typeof renderWatch==="function")renderWatch()}document.addEventListener("DOMContentLoaded",()=>document.querySelectorAll(".star").forEach(b=>{let on=getPins().includes(b.dataset.market);b.classList.toggle("on",on);b.textContent=on?"★":"☆"}))</script>'''
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css()}</style></head><body><main>{nav(active)}{system_status(basis)}{body}</main>{pins}</body></html>'


def grouped(snapshot):
    groups = {key: [] for key in "ABCDE"}
    for row in snapshot.get("candidates", []):
        if row.get("type") in groups:
            groups[row["type"]].append(row)
    for key, rows in groups.items():
        if key == "D":
            rows.sort(key=lambda row: (D_STAGE_ORDER.get(row.get("d_stage"), 9), ACTION_RANK.get(row.get("action"),9),-float(row.get("score") or 0)))
        else:
            rows.sort(key=lambda row: (ACTION_RANK.get(row.get("action"),9),-float(row.get("score") or 0),str(row.get("market") or "")))
    return groups

def dist_text(row):
    value=distance_to_entry(row)
    if value is None:return "-"
    if value==0:return "구간 안"
    return f'{abs(value):.1f}% {"위" if value>0 else "아래"}'


def main_page(snapshot, btc):
    groups=grouped(snapshot)
    regime=snapshot.get("market_regime") or read(MARKET,{})
    updated=str(snapshot.get("snapshot_at") or "-").replace("T"," ")[:16]
    cards="".join(f'<a class="type-tab" href="type_{k.lower()}.html" style="--c:{INFO[k][1]}"><strong>{k}형 · {len(groups[k])}</strong><div>{INFO[k][2]}</div><div class="update-stamp">최근 갱신 · {updated} KST</div></a>' for k in "ABCDE")
    rows=sum(groups.values(),[]);rows.sort(key=lambda r:(ACTION_RANK.get(r.get("action"),9),-float(r.get("score") or 0),-float(r.get("rr") or 0)))
    trs=[]
    for r in rows:
        targets=r.get("targets") or []
        trs.append(f'<tr data-type="{r.get("type")}" data-action="{fmt(r.get("action"))}"><td><button class="star" data-market="{fmt(r.get("market"))}" onclick="togglePin(\'{fmt(r.get("market"))}\',this)">☆</button></td><td><b>{fmt(r.get("market"))}</b></td><td>{fmt(r.get("type"))}형</td><td>{action_cell(r)}</td><td>{fmt(r.get("score"))}</td><td>{fmt(r.get("price"))}<br><small class="sub">{dist_text(r)}</small></td><td>{fmt(r.get("entry"))}</td><td>{fmt(r.get("stop"))}</td><td>{fmt(targets[0] if targets else None)}</td><td>{fmt(r.get("rr"))}R</td></tr>')
    blocked=int(regime.get("alt_entry_limit_pct") or 0)==0
    filters=''.join(f'<button class="filter" data-kind="{k}" onclick="setType(\'{k}\',this)">{k if k=="ALL" else k+"형"}</button>' for k in ["ALL","A","B","C","D","E"])
    body=page_intro("오늘의 전체 스캔","업비트 KRW 전체에서 A/B/C/D/E 조건에 맞는 후보를 한 번에 비교하는 곳","① 유형 선택 → ② 단계·점수 비교 → ③ 진입거리·손절·손익비 확인 → ④ 관심종목은 별표")
    body+=market_gate_panel(regime)
    body+=f'<div class="type-tabs">{cards}</div><section class="panel"><div class="toolbar"><div class="filters" id="typeFilters">{filters}</div><div>{"<span class=trade-lock>시장 M0 · 신규진입 금지</span>" if blocked else ""}</div></div>{action_guide()}<div class="table-wrap"><table class="data-table"><thead><tr><th>관심</th><th>종목</th><th>유형</th><th>최종판단·남은 조건</th><th>점수</th><th>{tip("현재가·진입거리","현재가가 진입구간에서 얼마나 떨어져 있는지 보여줘")}</th><th>진입구간</th><th>{tip("손절가","차트 구조가 무효가 되는 가격")}</th><th>{tip("1차 목표가","처음으로 일부 이익을 정리할 가격")}</th><th>{tip("손익비","감수할 손실 대비 기대수익 비율")}</th></tr></thead><tbody id="scanRows">{"".join(trs)}</tbody></table></div></section><script>let selectedType="ALL";function setType(k,b){{selectedType=k;document.querySelectorAll("#typeFilters .filter").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll("#scanRows tr").forEach(r=>r.style.display=k==="ALL"||r.dataset.type===k?"":"none")}}document.addEventListener("DOMContentLoaded",()=>document.querySelector("#typeFilters .filter").click())</script>'
    return shell("오늘의 전체 스캔",body,snapshot,"today")


def dashboard_page(snapshot, watch, btc, market_data, regime):
    box=btc.get("box",{})
    size=int(regime.get("alt_entry_limit_pct") or 0);blocked=size==0
    state="entry" if size>=65 else "caution" if size>0 else "stop";state_class=f"state-{state}";cat=asset_uri(f"cat_{state}.webp")
    colors={"M0":"#ff5d3a","M1":"#ffc247","M2":"#ffd166","M3":"#70c2ff","M4":"#00e783","M5":"#ff8297"};market_color=colors.get(regime.get("stage"),"#91a79b")
    reasons="".join(f'<li>{fmt(reason)}</li>' for reason in regime.get("reasons",[]))
    def change_value(section, key4, key24, suffix="%"):
        block=market_data.get(section) or {};value=block.get(key4);label="4H"
        if value is None:value=block.get(key24);label="24H"
        if not isinstance(value,(int,float)):return "측정 전", label
        return f'{value:+.2f}{suffix}', label
    btcd_value,btcd_period=change_value("btc_d","change_4h_pct_point","change_24h_pct_point","%p")
    total2_value,total2_period=change_value("total2","change_4h_pct","change_24h_pct")
    others_value,others_period=change_value("others","change_4h_pct","change_24h_pct")
    breadth=(market_data.get("breadth") or {}).get("positive_ratio_24h_pct")
    breadth_value=f'{breadth:.0f}%' if isinstance(breadth,(int,float)) else "측정 전"
    stage_key=str(regime.get("stage") or "M?")
    mascot_advice={
        "M0":"멈춰. 시장과 BTC 구조가 함께 회복될 때까지 신규진입 금지.",
        "M1":"BTC만 강한 구간. 알트는 독립 강세 종목만 아주 작게.",
        "M2":"알트가 버티는 중. 지금은 후보를 고르고 눌림을 기다려.",
        "M3":"알트 순환이 시작됐어. 강한 종목의 첫 눌림만 선별해.",
        "M4":"알트 확산 구간. 허용형은 진입하되 급등 추격은 금지.",
        "M5":"수익 보호가 먼저. 신규매수보다 분할익절과 손절 상향.",
    }.get(stage_key,"시장 데이터를 다시 확인하는 중이야.")
    stage_info={
        "M0":("위험장","BTC 구조나 알트 자금 흐름이 무너진 장. 신규진입 차단."),
        "M1":("BTC 주도","비트코인만 강하고 알트 확산이 약한 장. 알트는 소액·선별."),
        "M2":("알트 준비","알트가 버티며 자금 이동을 준비하는 장. 후보 선별 후 눌림 대기."),
        "M3":("알트 순환 시작","BTC.D 하락과 TOTAL2·OTHERS 상승이 겹치는 장. 강한 알트 첫 눌림 검토."),
        "M4":("알트 확산","상승이 대형에서 중소형 알트로 넓어진 장. 허용형 선별 진입·추격 금지."),
        "M5":("과열·수익보호","알트 확산 뒤 과열과 되돌림 위험이 커진 장. 신규매수보다 분할익절."),
    }
    stage_cards="".join(
        f'<div class="market-stage-card {"current" if key==stage_key else ""}" style="--stage-color:{colors[key]}"><strong>{key} · {title}</strong><span>{description}</span></div>'
        for key,(title,description) in stage_info.items()
    )
    intro=page_intro("메인 대시보드","BTC와 시장 자금 흐름을 먼저 보고 오늘 알트코인을 매매해도 되는지 판단하는 곳","① 바이낸스 BTC 일봉·4시간봉 → ② 시장 M단계 → ③ BTC.D·TOTAL2·OTHERS → ④ A~E 허용표")
    stage=fmt(regime.get("stage") or "M?");name=fmt(regime.get("name") or "시장 데이터 확인")
    btc_location=box_location_text(box)
    body=intro+f'''<section class="panel btc-live-card"><div class="btc-live-head"><div><h2>BTC · 바이낸스 실시간 차트</h2><div class="sub">차트 왼쪽 위 시간봉 메뉴에서 <b>1일</b> 또는 <b>4시간</b>을 선택해서 봐.</div></div><div><b>BINANCE · BTC/USDT</b><div class="sub">오코탐 구조판정 · {str(btc.get('basis',{}).get('four_hour_end','-')).replace('T',' ')} 완성봉 반영</div></div></div><div class="btc-summary-grid"><div class="btc-summary-item"><span>일봉 해석</span><b>{fmt(btc.get("daily_state"))}</b></div><div class="btc-summary-item"><span>4시간봉 해석</span><b>{fmt(btc.get("four_hour_state"))}</b></div><div class="btc-summary-item"><span>현재 가격 위치</span><b>{fmt(btc_location)}</b></div><div class="btc-summary-item"><span>‘박스’란?</span><b>최근 30일 주요 저점~고점 가격 범위</b></div></div>{bitcoin_tradingview_widget()}</section>
<section class="panel market-hero" style="--market-color:{market_color}"><div class="market-stage"><div>{stage}<small>시장 {str(regime.get('stage') or 'M?').replace('M','')}단계</small></div></div><div><div class="sub">쉽게 말하면 · {fmt(regime.get("plain"))}</div><div class="market-title">{name}</div><div class="market-reason-title">왜 {stage}로 판정했나</div><ul class="market-reasons">{reasons}</ul><div class="proxy-note">자동판정 · CoinGecko 상위 125개 프록시 · 신뢰도 {fmt(regime.get("confidence"))}%</div></div><div class="market-limit"><span>오늘 알트 신규진입 한도</span><strong>{size}%</strong><div>{"새 매수 금지" if blocked else "개별 조건 확인 후 분할진입"}</div></div></section>
<section class="dashboard-panel market-mascot {state_class}" style="--market-color:{market_color}"><img class="cat-main" src="{cat}" alt="시장 {stage} 상태 고양이"><div class="market-mascot-copy"><b>{stage} · 오늘의 오코탐 행동</b><div>{fmt(mascot_advice)}</div><div class="sub" style="margin-top:7px">시장 단계가 바뀌면 고양이의 표정과 행동 안내도 함께 바뀌어.</div></div></section>
<section class="panel market-stage-guide" style="--market-color:{market_color}"><h2>M단계란?</h2><div class="sub"><b>M은 Market(시장)의 약자</b>야. BTC와 알트 자금 흐름이 현재 어느 국면인지 M0~M5로 표시해. 숫자가 높을수록 무조건 좋은 것은 아니며, M5는 과열 뒤 수익을 보호하는 단계야.</div><div class="market-stage-grid">{stage_cards}</div></section>
{market_gate_panel(regime)}
<section class="panel"><h2>알트 자금 흐름 차트</h2><div class="sub">같은 시간축에서 BTC.D 하락과 TOTAL2·OTHERS 상승이 함께 나오는지 확인해.</div><div class="market-flow-strip"><div class="market-flow-stat"><span>BTC.D · {btcd_period}</span><b>{btcd_value}</b></div><div class="market-flow-stat"><span>TOTAL2 · {total2_period}</span><b>{total2_value}</b></div><div class="market-flow-stat"><span>OTHERS · {others_period}</span><b>{others_value}</b></div><div class="market-flow-stat"><span>알트 상승 종목 · 24H</span><b>{breadth_value}</b></div></div><div class="market-chart-grid">{tradingview_widget("CRYPTOCAP:BTC.D","BTC.D","비트코인 독점 강도")}{tradingview_widget("CRYPTOCAP:TOTAL2","TOTAL2","BTC 제외 알트 시총")}{tradingview_widget("CRYPTOCAP:OTHERS","OTHERS","상위 10개 제외 중소형 시총")}</div><div class="proxy-note">차트는 TradingView 상위 125개 원본 지수. 자동값도 CoinGecko 상위 125개만 같은 시점에서 합산하며, 4H 기록이 생기기 전에는 24H를 표시해.</div></section>
'''
    return shell("메인 대시보드",body,snapshot,"dashboard")


def type_page(key, snapshot):
    name, color, title, flow, entry, stop, take = INFO[key]
    rows = [pattern_row(row) for row in grouped(snapshot)[key]]
    rows.sort(key=lambda row: (ACTION_RANK.get(row.get("action"), 9), -float(row.get("score") or 0)))
    purpose={"A":"강한 상승 뒤 첫 눌림에서 지지를 확인하고 반등 후보를 찾는 곳","B":"긴 하락 뒤 바닥·박스 하단에서 상승 전환 후보를 찾는 곳","C":"박스 상단 돌파 뒤 재지지하는 추가 상승 후보를 찾는 곳","D":"바닥 압축과 매물대 재탈환으로 급등 전 후보를 찾는 곳","E":"급락한 코인이 핵심 하단에서 멈춘 뒤 나오는 1회성 기술적 반등만 0.382까지 노리는 곳"}[key]
    intro=page_intro(f"{name} 후보",purpose,"① 원칙 확인 → ② 단계별 후보 비교 → ③ 필요한 종목만 펼쳐보기 → ④ 자세한 건 업비트에서 확인")
    cat=asset_uri("cat_entry.webp")
    guide=f'<section class="panel hero-guide" style="--accent:{color}"><div><h2 style="color:{color}">{title}</h2><div class="flow" style="border-color:{color}">{flow}</div><div class="rules" style="margin-top:12px"><div class="rule"><b style="color:{color}">진입</b>{entry}</div><div class="rule"><b style="color:{color}">손절</b>{stop}</div><div class="rule"><b style="color:{color}">분할익절</b>{take}</div></div></div><div class="type-cat-wrap"><img src="{cat}" alt="{name} 안내 고양이"><span class="type-token">{key}</span></div></section>'
    trs=[]
    for i,r in enumerate(rows):
        targets=r.get("targets") or []; charts=r.get("charts") or {}; levels=[(r.get("stop"),"#ff667e","손절")]+[(x,color,"진입") for x in r.get("entry",[]) if isinstance(x,(int,float))]
        missing=remaining_condition(r)
        stage_line = f'<br><b>D형 생애주기</b> · {fmt(r.get("d_stage"))} {fmt(r.get("d_stage_label"))}<br><b>단계 근거</b> · {fmt(r.get("d_stage_reason"))}' if key == "D" else ""
        detail=f'<div class="expand-grid"><div><div class="chart-title">일봉 <small>큰 추세</small></div><div class="chart">{chart_svg(charts.get("day",[]),600,190,levels)}</div></div><div><div class="chart-title">4시간봉 <small>진입 흐름</small></div><div class="chart">{chart_svg(charts.get("4h",[]),600,190,levels)}</div></div></div><div class="reason"><b>포착 이유</b> · {fmt(r.get("reason"))}<br><b>차트 현재판단</b> · {fmt(r.get("action"))}{stage_line}<br><b>남은 조건</b> · {missing}</div><div class="target-strip"><span class="target-chip">진입 {fmt(r.get("entry"))}</span><span class="target-chip">손절 {fmt(r.get("stop"))}</span><span class="target-chip">목표 {fmt(targets[:3])}</span><span class="target-chip">{fmt(r.get("rr"))}R</span></div><p class="help-note">세부 차트와 실제 진입 여부는 업비트에서 확인</p>'
        stage_badge = f'<span class="badge">{fmt(r.get("d_stage"))} · {fmt(r.get("d_stage_label"))}</span><br>' if key == "D" else ""
        trs.append(f'<tr class="row-click" data-stage="{fmt(r.get("d_stage"))}" onclick="toggleRow({i})"><td><button class="star" data-market="{fmt(r.get("market"))}" onclick="event.stopPropagation();togglePin(\'{fmt(r.get("market"))}\',this)">☆</button></td><td><b>{fmt(r.get("market"))}</b></td><td>{stage_badge}{action_cell(r)}</td><td>{fmt(r.get("score"))}</td><td>{fmt(r.get("price"))}<br><small class="sub">{dist_text(r)}</small></td><td>{fmt(r.get("entry"))}</td><td>{fmt(r.get("stop"))}</td><td>{fmt(targets[0] if targets else None)}</td><td>{fmt(r.get("rr"))}R</td></tr><tr id="detail{i}" class="expand"><td colspan="9">{detail}</td></tr>')
    filter_values = ["전체","D0","D1","D2","D3","D4","D-W","D-F"] if key == "D" else ["전체","진입 검토","확인 대기","진입가 대기","추격 금지"]
    buttons=''.join(f'<button class="filter {"active" if a=="전체" else ""}" onclick="filterAction(\'{a}\',this)">{a}</button>' for a in filter_values)
    table=f'<section class="panel" style="--accent:{color}"><div class="toolbar"><div class="filters" id="actionFilters">{buttons}</div><div><button class="filter" onclick="expandAll(true)">모두 펼치기</button> <button class="filter" onclick="expandAll(false)">모두 접기</button></div></div>{pattern_action_guide()}<div class="table-wrap"><table class="data-table"><thead><tr><th>관심</th><th>종목</th><th>현재판단·남은 조건</th><th>점수</th><th>현재가·진입거리</th><th>진입</th><th>손절</th><th>1차 목표</th><th>손익비</th></tr></thead><tbody>{"".join(trs) or "<tr><td colspan=9 class=empty>이번 기준봉 후보 없음</td></tr>"}</tbody></table></div></section>'
    script='''<script>function toggleRow(i){document.getElementById("detail"+i).classList.toggle("open")}function expandAll(open){document.querySelectorAll(".expand").forEach(x=>x.classList.toggle("open",open))}function filterAction(a,b){document.querySelectorAll("#actionFilters .filter").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll("tr.row-click").forEach(r=>{const stageMatch=r.dataset.stage===a;const show=a==="전체"||stageMatch||r.textContent.includes(a);r.style.display=show?"":"none";const d=r.nextElementSibling;if(!show)d.classList.remove("open")})}</script>'''
    return shell(name,intro+guide+table+script,snapshot,f"type_{key.lower()}")


def training_scenario_svg(kind):
    ys = {
        "success": [98,91,96,80,84,62,49,31],
        "warning": [98,91,96,80,88,79,91,96],
        "failure": [98,91,96,80,94,108,119,132],
    }[kind]
    candles=[]
    for i,y in enumerate(ys):
        x=24+i*42
        rising = (i > 0 and y < ys[i-1]) or (i == 0)
        color = "#00e783" if rising else "#ff667e"
        height = 18 if i in {3,5} else 13
        candles.append(f'<line x1="{x}" y1="{y-14}" x2="{x}" y2="{y+18}" stroke="{color}"/><rect x="{x-7}" y="{y-height/2}" width="14" height="{height}" fill="{color}"/>')
    return f'''<svg viewBox="0 0 344 145" role="img" aria-label="{kind} 캔들 흐름"><rect width="344" height="145" fill="#050a07"/><rect x="0" y="78" width="344" height="28" fill="#3c3011" opacity=".55"/><line x1="0" y1="78" x2="344" y2="78" stroke="#ffd166" stroke-dasharray="5 4"/>{''.join(candles)}<circle cx="150" cy="70" r="5" fill="#00e783"/><text x="126" y="60" fill="#00e783" font-size="10">A3 진입</text><g opacity=".65">{''.join(f'<rect x="{17+i*42}" y="{132-(12+i*2 if kind=="success" else 10)}" width="14" height="{12+i*2 if kind=="success" else 10}" fill="#00e783"/>' for i in range(8))}</g></svg>'''


def training_context_svg():
    """A0 한 봉이 아니라 장기 일봉 문맥을 먼저 읽게 하는 훈련용 도식."""
    closes = [74,79,76,72,68,65,61,58,55,51,48,44,42,39,37,35,33,32,31,30,31,30,32,31,33,32,34,33,32,34,33,35,34,36,35,37,36,38,37,39,38,41,45,52,61,70,75,72,74,71,73,76,74,77,75,78]
    volumes = [28,36,32,27,25,24,23,21,20,19,18,17,16,15,14,13,12,11,10,10,9,9,8,8,7,7,8,7,7,8,7,8,8,9,8,10,9,11,10,12,11,14,19,28,46,70,58,34,28,25,23,24,22,25,21,24]
    width, height, top, bottom = 980, 445, 24, 365
    low, high = 24, 86
    y = lambda value: top + (high-value)/(high-low)*(bottom-top)
    step = width/len(closes); body = max(5, step*.54)
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="과거 고점, 장기 하락, 하단 횡보, A0 수급봉과 과거 고점 재접근을 보여주는 일봉 차트"><rect width="{width}" height="{height}" fill="#050a07"/>']
    for value in [30,40,50,60,70,80]:
        parts.append(f'<line x1="0" y1="{y(value):.1f}" x2="{width}" y2="{y(value):.1f}" stroke="#183427"/>')
    parts += [
        f'<rect x="0" y="{y(82):.1f}" width="{width}" height="{y(70)-y(82):.1f}" fill="#143b2b" opacity=".7"/>',
        f'<rect x="{step*17:.1f}" y="{y(41):.1f}" width="{step*25:.1f}" height="{y(28)-y(41):.1f}" fill="#3c3011" opacity=".55"/>',
        f'<rect x="{step*44:.1f}" y="{y(58):.1f}" width="{step*12:.1f}" height="{y(51)-y(58):.1f}" fill="#4a3214" opacity=".62"/>',
    ]
    previous = closes[0] + 2
    for i,(close,volume) in enumerate(zip(closes,volumes)):
        opn = previous + (i%3-1)*.7; hi=max(opn,close)+1.2+(i%2)*.6; lo=min(opn,close)-1-(i%4)*.25
        x=(i+.5)*step;color="#00e783" if close>=opn else "#ff667e";top_body=min(y(opn),y(close));bottom_body=max(y(opn),y(close))
        parts.append(f'<line x1="{x:.1f}" y1="{y(hi):.1f}" x2="{x:.1f}" y2="{y(lo):.1f}" stroke="{color}"/><rect x="{x-body/2:.1f}" y="{top_body:.1f}" width="{body:.1f}" height="{max(2,bottom_body-top_body):.1f}" fill="{color}"/><rect x="{x-body/2:.1f}" y="{height-10-volume*.58:.1f}" width="{body:.1f}" height="{volume*.58:.1f}" fill="{color}" opacity=".55"/>')
        previous=close
    labels = [(18,18,"① 과거 고점·상단 매물대"),(175,135,"② 장기 하락"),(315,294,"③ 하단 횡보·수급 압축"),(650,255,"④ A0 수급봉"),(785,48,"⑤ 과거 고점 재접근"),(825,124,"⑥ A1 기준선 지지"),(795,225,"A2 예상구간")]
    for x_pos,y_pos,text in labels:
        parts.append(f'<text x="{x_pos}" y="{y_pos}" fill="#eafff2" font-size="12" font-weight="700">{text}</text>')
    parts.append(f'<line x1="{step*17:.1f}" y1="{y(41):.1f}" x2="{step*43:.1f}" y2="{y(41):.1f}" stroke="#ffd166" stroke-width="2" stroke-dasharray="6 5"/><text x="12" y="437" fill="#91a79b" font-size="11">거래량 · A0에서 장기 평균 대비 급증</text></svg>')
    return ''.join(parts)


def training_mtf_svg(kind):
    data = {
        "4시간봉": [(72,74,66,68),(68,70,61,63),(63,65,56,58),(58,60,52,54),(54,57,51,55),(55,62,54,61),(61,67,60,65),(65,71,63,69),(69,74,67,72)],
        "1시간봉": [(59,60,55,56),(56,57,53,54),(54,55,51,52),(52,54,51,53),(53,55,52,54),(54,59,53,58),(58,62,57,61),(61,65,60,64),(64,67,62,66)],
        "5분봉": [(55,56,53,54),(54,55,52,53),(53,54,51.5,52),(52,53,51.8,52.4),(52.4,54,52,53.5),(53.5,58,53,57.5),(57.5,61,57,60),(60,63,59,62),(62,65,61,64)],
    }[kind]
    width,height=320,190;low,high=49,76;y=lambda value:12+(high-value)/(high-low)*150;step=width/len(data);body=step*.42
    parts=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{kind} A형 확대 차트"><rect width="{width}" height="{height}" fill="#050a07"/><rect x="0" y="{y(58):.1f}" width="{width}" height="{y(51)-y(58):.1f}" fill="#3c3011" opacity=".55"/>']
    for value in [54,62,70]:parts.append(f'<line x1="0" y1="{y(value):.1f}" x2="{width}" y2="{y(value):.1f}" stroke="#183427"/>')
    for i,(opn,hi,lo,close) in enumerate(data):
        x=(i+.5)*step;color="#00e783" if close>=opn else "#ff667e";a=min(y(opn),y(close));b=max(y(opn),y(close))
        parts.append(f'<line x1="{x:.1f}" y1="{y(hi):.1f}" x2="{x:.1f}" y2="{y(lo):.1f}" stroke="{color}"/><rect x="{x-body/2:.1f}" y="{a:.1f}" width="{body:.1f}" height="{max(2,b-a):.1f}" fill="{color}"/>')
    if kind=="5분봉":parts.append(f'<text x="196" y="{y(59):.1f}" fill="#00e783" font-size="11" font-weight="700">A3-초기</text><line x1="0" y1="{y(51.3):.1f}" x2="{width}" y2="{y(51.3):.1f}" stroke="#ff667e" stroke-dasharray="5 4"/><text x="6" y="{y(51.3)-4:.1f}" fill="#ff8a9c" font-size="10">실행 손절</text>')
    parts.append('</svg>');return ''.join(parts)


def training_exit_svg():
    return '''<svg viewBox="0 0 420 280" role="img" aria-label="전일 장대양봉 몸통 기준 분할청산"><rect width="420" height="280" fill="#050a07"/><line x1="190" y1="28" x2="190" y2="250" stroke="#00e783" stroke-width="3"/><rect x="160" y="68" width="60" height="150" fill="#00e783"/><line x1="35" y1="214" x2="390" y2="214" stroke="#ffd166" stroke-width="2"/><text x="38" y="205" fill="#ffd166" font-size="11">1차 · 몸통 하단 / 근접 공급대</text><line x1="35" y1="76" x2="390" y2="76" stroke="#00e783" stroke-width="2"/><text x="230" y="67" fill="#8fffc4" font-size="11">2차 · 몸통 상단</text><line x1="35" y1="34" x2="390" y2="34" stroke="#9cbfff" stroke-width="2" stroke-dasharray="6 5"/><text x="230" y="25" fill="#b8ccff" font-size="11">잔량 · 전일 고점</text><text x="120" y="270" fill="#91a79b" font-size="11">전일 장대양봉 몸통에서 계획대로 분할 회수</text></svg>'''


def e_training_mtf_svg(kind):
    data = {
        "일봉": [(86,88,80,82),(82,84,75,77),(77,79,69,71),(71,73,61,63),(63,65,51,54),(54,57,43,46),(46,49,35,38),(38,41,28,31),(31,36,27,34),(34,40,32,38)],
        "4시간봉": [(72,74,63,65),(65,67,52,55),(55,58,42,45),(45,49,36,39),(39,43,31,35),(35,42,30,40),(40,47,38,45),(45,51,43,49),(49,55,47,53),(53,58,51,56)],
        "15분봉": [(57,58,52,53),(53,55,49,50),(50,52,46,47),(47,49,44,46),(46,48,44,45),(45,48,44,47),(47,50,46,49),(49,53,48,52),(52,56,51,55),(55,59,54,58)],
        "5분봉": [(51,52,48,49),(49,50,46,47),(47,49,45,46),(46,48,45,47),(47,50,46,49),(49,54,48,53),(53,58,52,57),(57,61,56,60),(60,64,59,63),(63,67,62,66)],
    }[kind]
    width,height=320,190;low=min(row[2] for row in data)-3;high=max(row[1] for row in data)+3
    y=lambda value:12+(high-value)/max(high-low,1e-9)*150;step=width/len(data);body=step*.42
    parts=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="E형 {kind} 확대 차트"><rect width="{width}" height="{height}" fill="#050a07"/><rect x="0" y="{y(low+8):.1f}" width="{width}" height="{y(low+2)-y(low+8):.1f}" fill="#164d3b" opacity=".45"/>']
    for i,(opn,hi,lo,close) in enumerate(data):
        x=(i+.5)*step;color="#00e783" if close>=opn else "#ff667e";a=min(y(opn),y(close));b=max(y(opn),y(close))
        parts.append(f'<line x1="{x:.1f}" y1="{y(hi):.1f}" x2="{x:.1f}" y2="{y(lo):.1f}" stroke="{color}"/><rect x="{x-body/2:.1f}" y="{a:.1f}" width="{body:.1f}" height="{max(2,b-a):.1f}" fill="{color}"/>')
    if kind=="4시간봉":parts.append(f'<text x="188" y="{y(48):.1f}" fill="#ffb454" font-size="11" font-weight="700">E2 반등 확인</text>')
    if kind=="5분봉":parts.append(f'<circle cx="{step*5.5:.1f}" cy="{y(53):.1f}" r="5" fill="#ffb454"/><text x="{step*5.7:.1f}" y="{y(53)-9:.1f}" fill="#ffb454" font-size="10">실행 진입</text>')
    parts.append('</svg>');return ''.join(parts)


def e_training_scenario_svg(kind):
    closes={
        "success":[78,68,55,43,34,31,35,40,46,53,61,68,74,80],
        "warning":[78,68,55,43,34,31,35,40,44,41,37,34,32,35],
        "failure":[78,68,55,43,34,31,35,39,34,29,25,22,19,17],
    }[kind]
    width,height=620,230;low=12;high=84;y=lambda value:12+(high-value)/(high-low)*190;step=width/len(closes);body=step*.42
    parts=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="E형 {kind} 시나리오"><rect width="{width}" height="{height}" fill="#050a07"/><rect x="0" y="{y(36):.1f}" width="{width}" height="{y(27)-y(36):.1f}" fill="#164d3b" opacity=".42"/><line x1="0" y1="{y(72):.1f}" x2="{width}" y2="{y(72):.1f}" stroke="#ffd166" stroke-width="2"/><text x="520" y="{y(72)-5:.1f}" fill="#ffd166" font-size="11">0.382 전량청산</text><line x1="0" y1="{y(23):.1f}" x2="{width}" y2="{y(23):.1f}" stroke="#ff667e" stroke-dasharray="6 4"/><text x="520" y="{y(23)-5:.1f}" fill="#ff8b9d" font-size="11">저점 -3%</text>']
    previous=closes[0]+4
    for i,close in enumerate(closes):
        opn=previous;hi=max(opn,close)+2;lo=min(opn,close)-2-(2 if i==5 else 0);x=(i+.5)*step;color="#00e783" if close>=opn else "#ff667e";a=min(y(opn),y(close));b=max(y(opn),y(close))
        parts.append(f'<line x1="{x:.1f}" y1="{y(hi):.1f}" x2="{x:.1f}" y2="{y(lo):.1f}" stroke="{color}"/><rect x="{x-body/2:.1f}" y="{a:.1f}" width="{body:.1f}" height="{max(2,b-a):.1f}" fill="{color}"/>');previous=close
    parts.append('</svg>');return ''.join(parts)


def training_page(key, basis):
    color = INFO[key][1]
    if key == "E":
        intro = page_intro(
            "훈련소 · E형",
            "급락 뒤 핵심 하단에서 나오는 첫 기술적 반등만 피보나치 0.382까지 먹고 끝내는 매매를 복기하는 페이지",
            "일봉 급락 위치 → 4시간봉 저점 방어 → 15분봉 매도 둔화 → 5분봉 실행 → 0.382 전량청산",
        )
        model = '''<section class="strategy-model" style="--accent:#ffb454"><h2>이 페이지는 이런 E형 차트를 모아둔 곳이야</h2><div class="sub">완전한 상승 전환을 기대하지 않고, 급락 뒤 하단에서 나오는 첫 기술적 반등만 피보나치 0.382까지 먹고 끝내는 종목을 보여줘.</div><img src="assets/e_type_technical_rebound_guide.png" alt="E형 급락 후 0.382 기술적 반등 모형 차트"><div class="stage-grid"><div class="stage-card"><b>E1 · 하단 도달</b>급락이 매물대 하단에 닿았지만 아직 떨어지는 중이야. 매수하지 않고 4시간봉 반응을 기다려.</div><div class="stage-card"><b>E2 · 반등 확인</b>투매저점을 지키고 4시간봉 양봉·아래꼬리·저점 2% 회복이 나왔어. 저점 +1~8%이면서 0.236 이하일 때만 진입 검토해.</div><div class="stage-card danger"><b>E3 · 반등 진행</b>진입구간을 이미 지나 반등 중이야. 신규 매수는 추격 금지하고, 보유자만 0.382 청산을 기다려.</div><div class="stage-card danger"><b>E4 · 0.382 도달</b>기술적 반등 목표가 끝났어. 전량청산하고 더 오를 것이라는 기대나 재진입을 하지 않아.</div></div></section>'''
        stages = [
            ("E0","급락 포착","단기간 30% 이상 급락하고 마지막 하락파동에 투매 거래량이 붙은 후보.","과거 매물대 하단과 저점 위치 확인"),
            ("E1","하단 도달","가격이 과거 매물대 하단에 닿았지만 하락은 아직 진행 중.","선매수 없이 4시간봉 반응 대기"),
            ("E2","반등 확인","투매저점을 지키고 4시간봉 양봉·아래꼬리 또는 저점 2% 회복 확인.","저점 +1~8%·0.236 이하에서 실행 타점 확인"),
            ("E3","반등 진행","첫 반등이 진행돼 원래 진입구간을 벗어난 상태.","보유분만 0.382 목표 관리"),
            ("E4","목표 도달","급락파동 피보나치 0.382에 도달해 기술적 반등 완료.","전량청산하고 E형 매매 종료"),
            ("E-W","경고","0.236 아래에서 반복 저항이 나오고 투매저점을 다시 시험.","보유분 축소·저점 재확인"),
            ("E-F","가설 폐기","투매저점 아래 3% 손절선에 도달.","즉시 종료·물타기 없이 후보 제외"),
        ]
        stage_details=''.join(f'<div class="stage-detail"><strong>{stage}<br>{name}</strong><div><p><b>의미</b> {meaning}</p><p><b>대응</b> {action}</p></div></div>' for stage,name,meaning,action in stages)
        day=e_training_mtf_svg("일봉");h4=e_training_mtf_svg("4시간봉");m15=e_training_mtf_svg("15분봉");m5=e_training_mtf_svg("5분봉")
        success=e_training_scenario_svg("success");warning=e_training_scenario_svg("warning");failure=e_training_scenario_svg("failure")
        body = intro + model + f'''
<section class="panel" style="--accent:{color}"><h2>2. 시간봉을 좁혀 실제 타점 찾기</h2><div class="timeframe-flow"><div><b>일봉</b>급락 위치</div><div><b>4시간봉</b>E2 저점 방어</div><div><b>15분봉</b>매도 둔화</div><div><b>5분봉</b>실행 진입</div></div><div class="e-mtf-grid"><article class="e-mtf-card"><h3>일봉 · 급락 위치</h3><p>고점 대비 급락폭과 과거 매물대 하단이 겹치는지 확인해.</p>{day}</article><article class="e-mtf-card"><h3>4시간봉 · 저점 방어</h3><p>장대음봉 뒤 아래꼬리·양봉·저점 회복으로 E2를 판정해.</p>{h4}</article><article class="e-mtf-card"><h3>15분봉 · 매도 둔화</h3><p>저점 재시험에서 음봉이 작아지고 매도 압력이 줄어드는지 확인해.</p>{m15}</article><article class="e-mtf-card"><h3>5분봉 · 실행 진입</h3><p>직전 하락봉 고가 재탈환과 첫 높은 저점에서 실제 타점을 잡아.</p>{m5}</article></div><p class="help-note">일봉은 급락의 전체 위치, 4시간봉은 반등 가능성, 15분봉은 매도 둔화, 5분봉은 실행 타점을 담당해.</p></section>
<section class="panel" style="--accent:{color}"><h2>3. E0~E-F 단계 의미</h2><div class="stage-detail-grid">{stage_details}</div></section>
<section class="panel" style="--accent:{color}"><h2>4. 진입·손절·청산 계획</h2><div class="e-plan-grid"><div class="e-plan"><b>후보</b><span>단기간 30% 이상 급락 + 투매 거래량 + 과거 하단</span></div><div class="e-plan"><b>E2 진입</b><span>저점 방어 확인 후 저점 +1~8%, 피보나치 0.236 이하</span></div><div class="e-plan"><b>손절</b><span>투매저점 아래 3%. 진입 후 손절선을 더 아래로 넓히지 않음</span></div><div class="e-plan"><b>청산</b><span>피보나치 0.382에서 전량청산. 추가 상승은 E형 범위 밖</span></div></div></section>
<section class="panel" style="--accent:{color}"><h2>5. 성공 · 경고 · 실패 복기</h2><div class="e-scenario-tabs"><button class="filter active" onclick="showEScenario('success',this)">성공</button><button class="filter" onclick="showEScenario('warning',this)">경고</button><button class="filter" onclick="showEScenario('failure',this)">실패</button></div><div id="e-success" class="e-scenario-panel open">{success}<div class="e-scenario-copy"><h3>성공 · 계획대로 0.382 회수</h3><p>투매저점을 지킨 뒤 0.236을 통과하고 0.382에 도달해. 여기서 전량청산하며 이후 상승은 E형 매매 범위가 아니야.</p><div class="target-chip">대응 · 0.382 지정가 전량청산</div></div></div><div id="e-warning" class="e-scenario-panel">{warning}<div class="e-scenario-copy"><h3>경고 · 0.236 아래에서 반등 둔화</h3><p>첫 반등은 나왔지만 0.236을 넘지 못하고 음봉이 커지며 투매저점을 다시 시험해.</p><div class="target-chip">대응 · 보유분 축소·저점 재확인</div></div></div><div id="e-failure" class="e-scenario-panel">{failure}<div class="e-scenario-copy"><h3>실패 · 투매저점 재이탈</h3><p>반등 확인 뒤에도 투매저점을 깨고 손절선에 닿아. 기술적 반등 가설이 끝난 상태야.</p><div class="target-chip">대응 · 투매저점 -3% 즉시 종료</div></div></div></section>
<section class="panel" style="--accent:{color}"><h2>6. 진입 전 최종 체크</h2><div class="e-check-grid"><div class="e-check"><b>급락폭</b><span>고점 대비 30% 이상인가</span></div><div class="e-check"><b>위치</b><span>과거 매물대 하단인가</span></div><div class="e-check"><b>확인</b><span>4시간봉 투매저점을 방어했는가</span></div><div class="e-check"><b>손익비</b><span>0.382까지 최소 1R인가</span></div></div></section>
<script>function showEScenario(key,button){{document.querySelectorAll('.e-scenario-panel').forEach(x=>x.classList.remove('open'));document.getElementById('e-'+key).classList.add('open');document.querySelectorAll('.e-scenario-tabs .filter').forEach(x=>x.classList.remove('active'));button.classList.add('active')}}</script>'''
        return shell("훈련소 E형", body, basis, "training_e")
    if key != "A":
        body = page_intro(f"훈련소 · {key}형", f"{INFO[key][2]} 사례를 멀티타임프레임으로 복기하는 페이지", "차트 교과서 준비 중")
        body += f'''<section class="panel" style="--accent:{color};border-color:{color}"><h2 style="color:{color}">{key}형 훈련 자료 준비 중</h2><p class="sub">A형과 동일하게 큰 시간봉의 구조선 → 진입 시간봉 → 손절·분할청산 → 성공·경고·실패 복기 순서로 확장됩니다.</p><a class="green" href="training_a.html">A형 교과서 보기 →</a></section>'''
        return shell(f"훈련소 {key}형", body, basis, f"training_{key.lower()}")

    stages = [
        ("A0","수급 포착","장기 하단 횡보를 거래량 동반 장대양봉으로 돌파해 과거 고점·상단 매물대까지 재접근.","추격하지 않고 종가 구조 확인"),
        ("A1","후보 확정","A0 이후 횡보 상단·돌파선 위에서 일봉 마감. 유입 수급이 가격을 유지.","A2·무효화선·목표구간 설정"),
        ("A2","눌림 도달","계획한 상위 시간봉 매수구간 도착. 가격 조건만 충족하고 반전 수급은 미확인.","선매수 금지·5분봉 반전 대기"),
        ("A3-초기","최적 진입","저점 방어·음봉 축소·확장 양봉·거래량 증가·직전 하락봉 고가 재탈환.","진입 검토·기준봉 저점 실행 손절"),
        ("A3-진행","보유 판단","반전 이후 상승 저점 유지. 방향은 확인됐지만 신규 진입 손익비는 감소.","보유 관리·잔여 상승폭 재계산"),
        ("A4","청산 구간","전일 몸통·시간봉 공급대 도달. 신규 추격에 불리한 가격 위치.","보유분 분할청산"),
        ("A-W","경고","핵심 지지·계획 매수선 이탈. 지지 가설이 흔들리는 상태.","재탈환 전 대기·진입분 축소"),
        ("A-F","가설 폐기","일봉·4시간봉 구조 무효화선 종가 이탈.","전량 종료·후보 제외"),
    ]
    stage_details = ''.join(f'<div class="stage-detail"><strong>{s}<br>{name}</strong><div><p><b>의미</b> {meaning}</p><p><b>대응</b> {action}</p></div></div>' for s,name,meaning,action in stages)
    success = training_scenario_svg("success")
    warning = training_scenario_svg("warning")
    failure = training_scenario_svg("failure")
    daily = training_context_svg(); h4=training_mtf_svg("4시간봉"); h1=training_mtf_svg("1시간봉"); m5=training_mtf_svg("5분봉"); exit_chart=training_exit_svg()
    intro = page_intro("훈련소 · A형", "장기 일봉 구조에서 의미 있는 수급을 찾고 4시간봉 → 1시간봉 → 5분봉으로 타점을 좁히는 실전 복기", "일봉에서 위치 선정 → 4시간봉에서 A2 압축 → 1시간봉에서 대기 → 5분봉에서 A3 진입")
    body = intro + f'''
<section class="panel" style="--accent:{color}"><h2>1. 일봉 · A0가 의미 있는 이유</h2><div class="chart-legend"><span style="--legend:#174b35">과거 고점·상단 매물대</span><span style="--legend:#ffd166">하단 횡보·수급 압축</span><span style="--legend:#a36b25">A2 예상구간</span></div><div class="daily-context-layout"><div class="context-copy"><div class="context-point"><b>과거 고점</b><span>이전 급락이 시작됐고 물린 물량이 남아 있는 공급대</span></div><div class="context-point"><b>하단 횡보</b><span>장기 하락 후 저점이 낮아지지 않고 거래량이 감소한 수급 압축</span></div><div class="context-point"><b>A0 수급봉</b><span>횡보 상단을 돌파해 멀리 있던 과거 고점까지 가격을 다시 연결</span></div><div class="context-point"><b>A1 후보 확정</b><span>A0 이후 기준선 위에서 가격을 유지해 다음 눌림 후보 확정</span></div></div><div class="training-chart">{daily}</div></div><p class="help-note">A0는 장대양봉이라서 중요한 것이 아니다. 하단에서 압축된 가격이 거래량을 동반해 횡보 상단을 돌파하고 과거 고점까지 재접근했기 때문에 의미가 있다.</p></section>
<section class="panel" style="--accent:{color}"><h2>2. 상위 구조에서 실제 진입까지</h2><div class="timeframe-flow"><div><b>일봉</b>후보·큰 구조</div><div><b>4시간봉</b>A2 범위 압축</div><div><b>1시간봉</b>대기 가격 확정</div><div><b>5분봉</b>A3 진입 확인</div></div><div class="mtf-grid"><article class="mtf-card"><h3>4시간봉</h3><p>일봉 돌파선·매물대 하단·이전 저항의 지지 전환이 겹치는 범위로 A2 압축</p>{h4}</article><article class="mtf-card"><h3>1시간봉</h3><p>A2 내부에서 음봉 실체와 하락 거래량이 줄고 저점이 방어되는지 확인</p>{h1}</article><article class="mtf-card"><h3>5분봉</h3><p>저점 방어 → 확장 양봉·거래량 증가 → 직전 하락봉 고가 재탈환 시 A3-초기</p>{m5}</article></div><p class="help-note">일봉·4시간봉은 위치를 정하고, 1시간봉은 대기 가격을 좁힌다. 실제 진입은 5분봉 A3-초기에서만 결정한다.</p></section>
<section class="panel" style="--accent:{color}"><h2>3. A0~A-F 단계 의미</h2><div class="stage-detail-grid">{stage_details}</div></section>
<section class="panel" style="--accent:{color}"><h2>4. 일봉 기준 분할청산</h2><div class="exit-grid"><div class="training-chart">{exit_chart}</div><div class="exit-rules"><div class="exit-rule"><b>1차 · 전일 몸통 하단 / 가장 가까운 시간봉 공급대</b><span>반등이 처음 부딪히는 공급구간에서 일부 회수.</span></div><div class="exit-rule"><b>2차 · 전일 장대양봉 몸통 상단</b><span>높은 가격대 체결 물량과 저점 매수자의 차익실현이 겹치는 구간.</span></div><div class="exit-rule"><b>잔량 · 전일 고점</b><span>5분봉 상승 저점과 거래량이 유지될 때만 보유.</span></div><div class="exit-rule"><b>조기 종료</b><span>목표 전이라도 A3 반전 기준봉 저점 또는 재상승 구조가 깨지면 청산.</span></div><div class="exit-rule"><b>진입 필터</b><span>계획 진입가에서 1차 청산가까지 최소 1R이 나오지 않으면 진입하지 않음.</span></div></div></div><p class="help-note">실행 손절은 5분봉 반전 저점이다. 단타 진입 후 손절을 일봉 구조 무효화선까지 넓히지 않는다.</p></section>
<section class="panel"><h2>청산 시나리오</h2><div class="scenario-grid"><article class="scenario success"><h3>성공</h3>{success}<dl><dt>1차 청산</dt><dd>가장 가까운 분봉·시간봉 공급대 일부 회수</dd><dt>2차 청산</dt><dd>전일 몸통 상단·고점 중첩 구간</dd><dt>잔량</dt><dd>상승 저점·거래량 유지 조건부 보유</dd></dl></article><article class="scenario warning"><h3>경고</h3>{warning}<dl><dt>경고</dt><dd>재돌파 실패·거래량 둔화·매수가 재시험</dd><dt>대응</dt><dd>비중 축소. 반전 기준봉 저점 이탈 시 조기 종료</dd></dl></article><article class="scenario failure"><h3>실패</h3>{failure}<dl><dt>A-W</dt><dd>핵심 지지 이탈. 재탈환 전 재진입 금지</dd><dt>A-F</dt><dd>구조 무효화선 종가 이탈. 가설 폐기·전량 종료</dd></dl></article></div><div class="training-close"><div><b>후보 선정</b><span>거래량 동반 확장·돌파선 지지</span></div><div><b>진입</b><span>A2 내부 A3-초기 확인</span></div><div><b>청산</b><span>공급대별 분할·근거 붕괴 시 조기 종료</span></div><div><b>폐기</b><span>실행 손절과 구조 무효화 분리</span></div></div></section>'''
    return shell("훈련소 A형", body, basis, "training_a")

def watchlist_page(watch,basis):
    current={}
    for row in basis.get("candidates",[]):
        current.setdefault(row.get("market"),[]).append(row)
    items=[]
    for item in watch.get("items",{}).values():
        copy={**item}; rows=current.get(item.get("market"),[])
        if rows:
            best=sorted(rows,key=lambda r:(ACTION_RANK.get(r.get("action"),9),-float(r.get("score") or 0)))[0]
            copy["display"]={k:best.get(k) for k in ("price","entry","stop","targets","score","rr","action")}
            copy["types"]=sorted({r.get("type") for r in rows if r.get("type")})
        else:
            f=item.get("four_hour",{});copy["display"]={**f};copy["types"]=f.get("types",[])
        items.append(copy)
    data=json.dumps(items,ensure_ascii=False).replace("</","<\\/")
    tabs=''.join(f'<button class="type-tab {"active" if k=="A" else ""}" style="--c:{INFO[k][1]}" onclick="setWatchType(\'{k}\',this)"><strong>{k}형</strong><div>{INFO[k][2]}</div></button>' for k in "ABCDE")
    intro=page_intro("관심종목 추적","한 번 포착된 종목을 지우지 않고 보관하면서 4시간봉 변화를 계속 확인하는 곳","① A/B/C/D/E 선택 → ② 고정 관심 확인 → ③ 단계·진입거리 확인 → ④ 변화기록 펼쳐보기")
    note='<p class="help-note">별표는 지금 쓰는 브라우저에 바로 저장돼. 다른 사람의 관심종목과 섞이지 않아.</p>'
    body=intro+f'''<div class="type-tabs">{tabs}</div>{note}<div id="watchRoot"></div><script>const watchItems={data};let watchType="A";const esc=s=>String(s??"-").replace(/[&<>]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;"}}[c]));const num=x=>typeof x==="number"?x.toLocaleString("ko-KR",{{maximumFractionDigits:8}}):esc(x);function dtext(x){{const f=x.display||{{}},p=f.price,e=f.entry||[];if(typeof p!=="number"||!e.length)return "-";const lo=Math.min(...e),hi=Math.max(...e);if(p>=lo&&p<=hi)return "구간 안";const edge=p>hi?hi:lo;return Math.abs((p/edge-1)*100).toFixed(1)+"% "+(p>hi?"위":"아래")}}function row(x){{const f=x.display||{{}},ts=(x.types||[]),dup=ts.length>1?`<span class="badge">${{ts.join("/")}} 중복신호</span>`:"",events=(x.timeline||[]).slice(-8).reverse().map(e=>`<div>${{esc(String(e.at||"").slice(5,16).replace("T"," "))}} · ${{esc((e.types||[]).join("/"))}}형 · ${{esc(e.action)}} · ${{esc(e.note)}}</div>`).join("");const targets=f.targets||[];return `<tr class="row-click" onclick="this.nextElementSibling.classList.toggle('open')"><td><button class="star" data-market="${{esc(x.market)}}" onclick="event.stopPropagation();togglePin('${{esc(x.market)}}',this)">☆</button></td><td><b>${{esc(x.market)}}</b> ${{dup}}</td><td>${{esc(ts.join("/"))}}형</td><td>${{esc(f.action||x.daily_status)}}</td><td>${{num(f.price)}}<br><small class="sub">${{dtext(x)}}</small></td><td>${{esc((f.entry||[]).join(" ~ "))}}</td><td>${{num(f.stop)}}</td><td>${{num(targets[0])}}</td><td>${{num(f.score)}}점 · ${{num(f.rr)}}R</td><td>${{esc(String((x.four_hour||{{}}).last_seen||x.last_seen||"-").slice(5,16).replace("T"," "))}}</td></tr><tr class="expand"><td colspan="10"><b>4시간봉 변화기록</b><div class="timeline">${{events||"아직 변화기록 없음"}}</div></td></tr>`}}function section(title,rows){{return `<h2 class="section-label">${{title}} · ${{rows.length}}개</h2><div class="table-wrap"><table class="data-table"><thead><tr><th>관심</th><th>종목</th><th>신호</th><th>단계</th><th>현재가·진입거리</th><th>진입</th><th>손절</th><th>1차 목표</th><th>점수·손익비</th><th>최근확인</th></tr></thead><tbody>${{rows.map(row).join("")||"<tr><td colspan=10 class=empty>없음</td></tr>"}}</tbody></table></div>`}}function renderWatch(){{const p=getPins(),all=watchItems.filter(x=>(x.types||[]).includes(watchType)),fixed=all.filter(x=>p.includes(x.market)),active=all.filter(x=>!p.includes(x.market)&&!x.archived),archived=all.filter(x=>!p.includes(x.market)&&x.archived);watchRoot.innerHTML=`<section class="panel" style="--accent:${{({{A:"#ff8297",B:"#70c2ff",C:"#c3a7ff",D:"#5ce2b3",E:"#ffb454"}})[watchType]}}">${{section("⭐ 고정 관심",fixed)}}${{section("활성 추적",active)}}${{section("구조 무효 보관",archived)}}</section>`;document.querySelectorAll(".star").forEach(b=>{{const on=p.includes(b.dataset.market);b.classList.toggle("on",on);b.textContent=on?"★":"☆"}})}}function setWatchType(k,b){{watchType=k;document.querySelectorAll(".type-tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");renderWatch()}}document.addEventListener("DOMContentLoaded",renderWatch)</script>'''
    return shell("관심종목 추적",body,basis,"watch")


def history_page(records):
    records=[{**record,"candidates":[{key:value for key,value in row.items() if key!="charts"} for row in record.get("candidates",[])]} for record in records]
    data = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    intro=page_intro("날짜별 기록","과거 후보가 진입구간·목표가·손절가에 닿았는지 확인하고 스캐너 성과를 복기하는 곳","① 날짜 선택 → ② 마감시간 선택 → ③ 당시 후보 확인 → ④ 24H·72H 결과 비교")
    body=intro+f'''<section class="panel"><div id="dateButtons" class="date-buttons"></div><div id="timeButtons" class="filters"></div></section><section class="panel" id="saved"></section><script>const records={data};let selected=records.length?records.length-1:-1;const esc=s=>String(s??"-").replace(/[&<>]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;"}}[c]));const num=x=>typeof x==="number"?x.toLocaleString("ko-KR",{{maximumFractionDigits:8}}):esc(x);function badge(o){{if(!o)return '<span class="outcome wait">확인 예정</span>';const s=o.status||"확인 예정",c=s.includes("목표")||s.includes("진입")?"ok":s.includes("손절")?"bad":s.includes("예정")||s.includes("진행")?"wait":"muted";return `<span class="outcome ${{c}}">${{esc(s)}}</span><br><small class="sub">최대 +${{num(o.mfe_pct)}}% / ${{num(o.mae_pct)}}%</small>`}}function drawDates(){{const dates=[...new Set(records.map(r=>r.date))].sort().reverse();dateButtons.innerHTML=dates.map(d=>`<button class="date-btn ${{records[selected]?.date===d?'active':''}}" onclick="pickDate('${{d}}')">${{d}}</button>`).join("");drawTimes()}}function pickDate(d){{const ids=records.map((r,i)=>r.date===d?i:-1).filter(i=>i>=0);selected=ids[ids.length-1];drawDates();render()}}function drawTimes(){{const d=records[selected]?.date;const slots=["01:00","05:00","09:00","13:00","17:00","21:00"];timeButtons.innerHTML=slots.map(t=>{{const i=records.findIndex(r=>r.date===d&&r.time===t);return `<button class="filter ${{records[selected]?.time===t?'active':''}}" ${{i<0?'disabled':''}} onclick="selected=${{i}};drawTimes();render()">${{t}}${{t==='09:00'?' · 일봉+4H':''}}</button>`}}).join("")}}function render(){{if(selected<0){{saved.innerHTML='<div class="empty">첫 기록 전이야.</div>';return}}const r=records[selected],counts=r.counts||{{}},btc=r.btc||{{}},policy=r.alt_policy||btc.alt_policy||{{}};const acts={{}};(r.candidates||[]).forEach(x=>acts[x.action]=(acts[x.action]||0)+1);let out=`<div class="status-line"><span class="mini-stat">BTC ${{esc(btc.daily_state||'-')}} / ${{esc(btc.four_hour_state||'-')}}</span><span class="mini-stat">알트 진입강도 ${{esc(policy.size_pct??'-')}}%</span><span class="mini-stat">A${{counts.A||0}} · B${{counts.B||0}} · C${{counts.C||0}} · D${{counts.D||0}} · E${{counts.E||0}}</span><span class="mini-stat">진입검토 ${{acts['진입 검토']||0}} · 확인대기 ${{acts['확인 대기']||0}}</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>종목</th><th>유형</th><th>단계</th><th>당시가</th><th>진입</th><th>손절</th><th>1차 목표</th><th>손익비</th><th>24H 결과</th><th>72H 결과</th></tr></thead><tbody>`;out+=(r.candidates||[]).map(x=>`<tr><td><b>${{esc(x.market)}}</b></td><td>${{esc(x.type)}}형</td><td>${{esc(x.action)}}</td><td>${{num(x.price)}}</td><td>${{esc((x.entry||[]).join(' ~ '))}}</td><td>${{num(x.stop)}}</td><td>${{num((x.targets||[])[0])}}</td><td>${{num(x.rr)}}R</td><td>${{badge((x.outcomes||{{}})['24h'])}}</td><td>${{badge((x.outcomes||{{}})['72h'])}}</td></tr>`).join('');out+='</tbody></table></div>';const done=(r.candidates||[]).flatMap(x=>Object.values(x.outcomes||{{}}));const wins=done.filter(x=>String(x.status).includes('목표')).length,stops=done.filter(x=>String(x.status).includes('손절')).length,best=Math.max(0,...done.map(x=>Number(x.mfe_pct)||0)),fall=Math.min(0,...done.map(x=>Number(x.mae_pct)||0));out+=`<div class="status-line" style="margin-top:14px"><span class="mini-stat">목표 성공 ${{wins}}</span><span class="mini-stat">손절 ${{stops}}</span><span class="mini-stat">최고 상승 +${{best.toFixed(1)}}%</span><span class="mini-stat">최대 하락 ${{fall.toFixed(1)}}%</span></div>`;saved.innerHTML=out}}drawDates();render();</script>'''
    basis = records[-1] if records else {}
    return shell("날짜별 기록", body, basis, "history")


def generate():
    records = read(STORE, [])
    watch = read(WATCH, {"items":{}})
    latest = records[-1] if records else {"date": "기록 전", "time": "-", "candidates": []}
    btc = read(BTC, {})
    market_data = read(GLOBAL, {})
    regime = latest.get("market_regime") or read(MARKET, {})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(dashboard_page(latest,watch,btc,market_data,regime), encoding="utf-8")
    (OUT / "scan.html").write_text(main_page(latest,btc), encoding="utf-8")
    for key in "ABCDE":
        (OUT / f"type_{key.lower()}.html").write_text(type_page(key, latest), encoding="utf-8")
        (OUT / f"training_{key.lower()}.html").write_text(training_page(key, latest), encoding="utf-8")
    for old in OUT.glob("coin_*.html"):
        old.unlink()
    for old in OUT.glob("main_dashboard_review_*.html"):
        old.unlink()
    (OUT / "history.html").write_text(history_page(records), encoding="utf-8")
    (OUT / "watchlist.html").write_text(watchlist_page(watch,latest),encoding="utf-8")
    print(OUT / "index.html")


if __name__ == "__main__":
    generate()
