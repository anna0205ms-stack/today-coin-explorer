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
INFO = {
    "A": ("A형", "#ff8297", "급등 후 첫 눌림", "강한 상승 → 거래량 감소 눌림 → 지지 확인 → 전고점 재도전", "매수존에서 하락 중단·저점 상승 확인", "첫 눌림 저점 또는 박스 하단 몸통 이탈", "직전 반등고점 → 급등고점 → 확장"),
    "B": ("B형", "#70c2ff", "바닥·박스 하단 반등", "장기 하락 → 바닥 박스 → 하단 재탈환 → 중심 반등", "박스 하단 재진입과 저점 상승 확인", "박스 최저점 또는 매수존 하단 몸통 이탈", "중심선 → 매도존 하단 → 박스 상단"),
    "C": ("C형", "#c3a7ff", "박스 상단 돌파·리테스트", "박스 횡보 → 상단 반복 접촉 → 돌파 → 상단 재지지", "완성봉 돌파 후 리테스트 방어 확인", "상단 아래 종가 복귀 또는 리테스트 저점 이탈", "박스 높이 확장 → 과거 매물대"),
    "D": ("D형", "#5ce2b3", "급등 전 재탈환·압축", "장기 하락 → 바닥 압축 → 매물대 하단 재탈환 → 4H 리테스트 → 상단 시도", "하단선 방어 또는 상단 돌파·재지지", "재탈환선 4H 몸통 이탈·하드스톱", "상단선 → 단기 확장 → 상위 매물대"),
    "E": ("E형", "#ffb454", "급락 후 0.382 기술적 반등", "급락·투매 → 핵심 하단 도달 → 4H 저점 방어 → 피보나치 0.382 반등", "투매저점 방어 + 4H 양봉·아래꼬리·저점 2% 회복", "투매저점 3% 하단 이탈 · 물타기 금지", "피보나치 0.382에서 전량청산 · 상승 전환 기대 금지"),
}
ACTION_RANK={"진입 검토":0,"확인 대기":1,"진입가 대기":2,"추격 금지":3}
D_STAGE_ORDER={"D4":0,"D3":1,"D2":2,"D1":3,"D0":4,"D-W":5,"D-F":6}
KST = timezone(timedelta(hours=9))


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
    action=row.get("action","진입가 대기");return f'<span class="badge act{ACTION_RANK.get(action,2)}">{fmt(action)}</span>'

def remaining_condition(row):
    """현재판단 옆에 보여줄 실제 남은 확인 조건."""
    action = row.get("action", "진입가 대기")
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
    return f'{action_badge(row)}<div class="condition-note">남은 조건 · {remaining_condition(row)}</div>'

def action_guide():
    return '''<details class="action-guide" open><summary>🐱 현재판단 보는 법</summary><div class="action-guide-grid">
<div><span class="badge act0">진입 검토</span><p>조건을 충족했어. 업비트에서 완성봉과 손익비를 최종 확인해.</p></div>
<div><span class="badge act1">확인 대기</span><p>후보는 맞지만 지지·리테스트 같은 마지막 조건을 더 확인해.</p></div>
<div><span class="badge act2">진입가 대기</span><p>구조는 관찰 중이야. 계획한 진입구간에 올 때까지 기다려.</p></div>
<div><span class="badge act3">추격 금지</span><p>진입 시점이 늦었어. 새 눌림이나 새 구조가 생기기 전에는 신규 매수하지 않아.</p></div>
</div><p class="guide-foot">오코탐은 후보를 빠르게 선별하는 도구야. 실제 진입은 업비트 차트에서 다시 확인해.</p></details>'''

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
    training_menu = f'''<details class="nav-drop" {"open" if training_active else ""}><summary class="{"active" if training_active else ""}">훈련소 <span>▾</span></summary><div class="nav-drop-menu">{''.join(f'<a class="{"active" if active == f"training_{key.lower()}" else ""}" href="training_{key.lower()}.html">{key}형</a>' for key in "ABCD")}</div></details>'''
    first = f'<a class="{"active" if active == "dashboard" else ""}" href="index.html">메인 대시보드</a>'
    rest = "".join(f'<a class="{"active" if active == key else ""}" href="{url}">{name}</a>' for name, url, key in links[1:])
    return f'<nav><div class="app-brand"><img class="nav-cat" src="{cat}" alt="회색 고양이"><span class="app-title">오늘의 코인 탐험대</span></div>{first}{scan_menu}{training_menu}{rest}</nav>'


def css():
    return """
:root{--bg:#030605;--panel:#0b1210;--inner:#111e18;--line:#174b35;--green:#00e783;--text:#f5fff8;--sub:#91a79b}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,#072217 0,transparent 25%),var(--bg);color:var(--text);font:14px/1.5 Arial,"Noto Sans KR",sans-serif}main{max-width:1380px;margin:auto;padding:28px}a{color:inherit;text-decoration:none}header{display:flex;justify-content:space-between;gap:18px;align-items:center}h1{margin:0;font-size:30px}h2{margin:0 0 12px}.sub{color:var(--sub)}.green{color:var(--green)}nav{display:flex;gap:8px;margin:22px 0;flex-wrap:wrap}nav a{padding:9px 14px;border:1px solid var(--line);border-radius:999px;background:#0b1511}nav a.active{border-color:var(--green);color:var(--green)}.date{padding:13px 19px;border:1px solid var(--green);border-radius:30px;background:#0b1511}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.type{position:relative;min-height:145px;padding:18px;border:1px solid;border-radius:20px;background:linear-gradient(145deg,#0b1210,#111d17)}.type strong{display:block;font-size:34px}.mascot{position:absolute;right:22px;top:40px;width:58px;height:54px;background:white;border-radius:48% 55% 45% 52%}.mascot:before{content:"• ᴗ •";position:absolute;color:#142019;left:13px;top:17px;font-weight:900}.panel{margin:17px 0;padding:20px;border:1px solid var(--line);border-radius:20px;background:linear-gradient(145deg,#0b1210,#111b16);overflow:auto}.candidate-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.candidate{padding:15px;border-radius:14px;background:var(--inner);border:1px solid #1e3b2d}.candidate b{font-size:17px}.kv{display:grid;grid-template-columns:auto 1fr;gap:5px 10px;margin-top:10px}.kv span:nth-child(odd){color:var(--sub)}.kv span:nth-child(even){text-align:right}.badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#20382c}.act0{color:#8ff0bd;border:1px solid #238b57}.act1{color:#ffd77f;background:#4e3b12}.act2{color:#bdd2c5}.act3{color:#ff9bac;background:#542326}.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.rule{padding:15px;border-radius:14px;background:var(--inner)}.rule b{display:block;color:var(--green);margin-bottom:6px}.flow{padding:18px;border:1px dashed var(--green);border-radius:14px;color:#c8ffdf}.chart{margin:12px 0 4px;border-radius:12px;background:#07100c;border:1px solid #173a2b;overflow:hidden}.chart svg{width:100%;height:auto;display:block}.reason{margin-top:10px;padding:10px;border-left:2px solid var(--green);background:#0a1611}.compact{display:grid;grid-template-columns:1.2fr .8fr .8fr 1fr 1fr;gap:8px;padding:10px;border-bottom:1px solid #1e3b2d;align-items:center}.star{border:0;background:transparent;color:#64756c;font-size:22px;cursor:pointer}.star.on{color:#ffd166}.timeline{font-size:12px;color:var(--sub);margin-top:8px}select{background:#0b1511;color:var(--text);border:1px solid var(--green);border-radius:12px;padding:10px}.empty{padding:30px;text-align:center;color:var(--sub)}@media(max-width:900px){.grid4,.rules{grid-template-columns:1fr 1fr}.candidate-grid{grid-template-columns:1fr}.compact{grid-template-columns:1fr 1fr}}@media(max-width:600px){main{padding:14px}.grid4,.rules{grid-template-columns:1fr}header{align-items:flex-start;flex-direction:column}.date{width:100%}}
.brand{display:flex;align-items:center;gap:12px}.nav-cat{width:42px;height:42px;border-radius:50%;object-fit:cover;object-position:50% 13%;margin-right:10px}.cat-face{width:48px;height:48px;border-radius:50%;object-fit:cover;object-position:50% 13%;border:1px solid var(--green);background:#111}.btc-card{display:grid;grid-template-columns:300px minmax(430px,1fr) 230px;gap:26px;align-items:center;padding:28px 32px;border:1px solid var(--state);border-radius:18px;background:#030605}.btc-price{font-size:28px;font-weight:800;margin:5px 0}.state-entry{--state:#00e783;--state-bg:#082418}.state-caution{--state:#ffc247;--state-bg:#2a210c}.state-stop{--state:#ff5d3a;--state-bg:#2b100a}.status-chip{display:block;margin:8px 0;padding:7px 11px;border:1px solid var(--state);border-radius:999px}.cat-main{width:100%;height:250px;object-fit:contain;filter:drop-shadow(0 12px 20px #000)}.action-card{display:grid;grid-template-columns:150px 1fr 1fr;gap:26px;align-items:center;padding:28px 34px;border:1px solid var(--state);border-radius:18px;background:var(--state-bg)}.warning-mark{font-size:78px;line-height:1;text-align:center;color:var(--state)}.action-big{font-size:42px;font-weight:900;color:var(--state)}.action-lines{border-left:1px solid var(--state);padding-left:34px}.action-lines div{margin:9px 0}.top-table{width:100%;border-collapse:collapse}.top-table th,.top-table td{padding:12px 10px;border-bottom:1px solid #23372d;text-align:left;white-space:nowrap}.top-table th{color:var(--green);font-size:12px}.candidate-row{position:relative}.trade-lock{display:inline-block;margin-left:8px;padding:2px 7px;border-radius:999px;background:#5a1b13;color:#ffb5a6;font-size:11px}.blocked-row{color:#b9aaa6;background:linear-gradient(90deg,rgba(80,18,10,.26),transparent)}.blocked-row td:first-child:before{content:"거래금지";display:inline-block;margin-right:7px;padding:2px 6px;border:1px solid #ff5d3a;border-radius:6px;color:#ff7b61;font-size:10px}.table-wrap{overflow:auto}.dashboard-panel{margin:17px 0;padding:20px;border:1px solid var(--line);border-radius:18px;background:#030605}@media(max-width:900px){.btc-card{grid-template-columns:1fr}.cat-main{height:190px}.action-card{grid-template-columns:1fr}.warning-mark{text-align:left}.action-lines{border-left:0;border-top:1px solid var(--state);padding:15px 0 0}}@media(max-width:600px){.action-big{font-size:30px}.btc-card{padding:16px}}
.act0{color:#a9ffd0;background:#123c27;border:1px solid #35d47f}.act1{color:#ffe39a;background:#4e3b12;border:1px solid #d9a928}.act2{color:#cae0ff;background:#1c314d;border:1px solid #588bcc}.act3{color:#ffb0be;background:#542326;border:1px solid #d95770}.condition-note{max-width:250px;margin-top:5px;color:#b6c5bc;font-size:11px;line-height:1.35;white-space:normal}.action-guide{margin:10px 0 17px;padding:12px 14px;border:1px solid #29483a;border-radius:14px;background:#07110c}.action-guide summary{cursor:pointer;color:#dcf8e7;font-weight:800}.action-guide-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:12px}.action-guide-grid>div{padding:11px;border:1px solid #233d31;border-radius:12px;background:#0b1611}.action-guide-grid p{margin:7px 0 0;color:#b9c8c0;font-size:12px}.guide-foot{margin:10px 0 0;color:#8fa399;font-size:12px}@media(max-width:900px){.action-guide-grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.action-guide-grid{grid-template-columns:1fr}.condition-note{max-width:190px}}
nav{display:flex;gap:24px;margin:0 0 20px;align-items:center;flex-wrap:wrap}.app-brand{display:flex;align-items:center;gap:10px;margin-right:8px}.app-title{font-size:18px;font-weight:900;color:#f4fff8;white-space:nowrap}.app-brand .nav-cat{margin-right:0}nav a{padding:14px 8px;border:0;border-bottom:2px solid transparent;border-radius:0;background:transparent;font-size:16px}nav a.active{border-color:var(--green);color:var(--green)}
.nav-drop{position:relative}.nav-drop summary{list-style:none;padding:14px 8px;border-bottom:2px solid transparent;font-size:16px;cursor:pointer}.nav-drop summary::-webkit-details-marker{display:none}.nav-drop summary.active{border-color:var(--green);color:var(--green)}.nav-drop-menu{position:absolute;z-index:40;left:0;top:48px;display:grid;min-width:150px;padding:7px;border:1px solid var(--line);border-radius:12px;background:#07100c;box-shadow:0 14px 28px #000}.nav-drop:not([open]) .nav-drop-menu{display:none}.nav-drop-menu a{padding:9px 12px;border:0;border-radius:8px;font-size:14px}.nav-drop-menu a:hover,.nav-drop-menu a.active{background:#0d2118;color:var(--green)}
.dual-chart{display:grid;grid-template-columns:1fr 1fr;gap:14px}.chart-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;font-weight:800}.chart-title small{color:var(--sub);font-weight:400}@media(max-width:900px){.dual-chart{grid-template-columns:1fr}}
.page-intro{margin:4px 0 18px}.page-intro h1{margin:0 0 4px}.how{margin-top:7px;color:#c8ffdf}.tip{position:relative;display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;margin-left:4px;border:1px solid #60756a;border-radius:50%;color:#a9b9b0;font-size:10px;cursor:help}.