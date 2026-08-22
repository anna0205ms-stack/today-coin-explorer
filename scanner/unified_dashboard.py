#!/usr/bin/env python3
"""MVP Lite용 오늘·유형별·날짜별 정적 화면 생성."""
from __future__ import annotations

import html
import json
import base64
from datetime import datetime, timedelta
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
}
ACTION_RANK={"진입 검토":0,"확인 대기":1,"진입가 대기":2,"추격 금지":3}


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
    links = [("메인 대시보드", "index.html", "dashboard"), ("오늘의 전체 스캔", "scan.html", "today"), ("관심종목 추적", "watchlist.html", "watch"), ("날짜별 기록", "history.html", "history")]
    cat = asset_uri("cat_entry.webp")
    return f'<nav><div class="app-brand"><img class="nav-cat" src="{cat}" alt="회색 고양이"><span class="app-title">오늘의 코인 탐험대</span></div>' + "".join(f'<a class="{"active" if active == key else ""}" href="{url}">{name}</a>' for name, url, key in links) + "</nav>"


def css():
    return """
:root{--bg:#030605;--panel:#0b1210;--inner:#111e18;--line:#174b35;--green:#00e783;--text:#f5fff8;--sub:#91a79b}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,#072217 0,transparent 25%),var(--bg);color:var(--text);font:14px/1.5 Arial,"Noto Sans KR",sans-serif}main{max-width:1380px;margin:auto;padding:28px}a{color:inherit;text-decoration:none}header{display:flex;justify-content:space-between;gap:18px;align-items:center}h1{margin:0;font-size:30px}h2{margin:0 0 12px}.sub{color:var(--sub)}.green{color:var(--green)}nav{display:flex;gap:8px;margin:22px 0;flex-wrap:wrap}nav a{padding:9px 14px;border:1px solid var(--line);border-radius:999px;background:#0b1511}nav a.active{border-color:var(--green);color:var(--green)}.date{padding:13px 19px;border:1px solid var(--green);border-radius:30px;background:#0b1511}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.type{position:relative;min-height:145px;padding:18px;border:1px solid;border-radius:20px;background:linear-gradient(145deg,#0b1210,#111d17)}.type strong{display:block;font-size:34px}.mascot{position:absolute;right:22px;top:40px;width:58px;height:54px;background:white;border-radius:48% 55% 45% 52%}.mascot:before{content:"• ᴗ •";position:absolute;color:#142019;left:13px;top:17px;font-weight:900}.panel{margin:17px 0;padding:20px;border:1px solid var(--line);border-radius:20px;background:linear-gradient(145deg,#0b1210,#111b16);overflow:auto}.candidate-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.candidate{padding:15px;border-radius:14px;background:var(--inner);border:1px solid #1e3b2d}.candidate b{font-size:17px}.kv{display:grid;grid-template-columns:auto 1fr;gap:5px 10px;margin-top:10px}.kv span:nth-child(odd){color:var(--sub)}.kv span:nth-child(even){text-align:right}.badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#20382c}.act0{color:#8ff0bd;border:1px solid #238b57}.act1{color:#ffd77f;background:#4e3b12}.act2{color:#bdd2c5}.act3{color:#ff9bac;background:#542326}.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.rule{padding:15px;border-radius:14px;background:var(--inner)}.rule b{display:block;color:var(--green);margin-bottom:6px}.flow{padding:18px;border:1px dashed var(--green);border-radius:14px;color:#c8ffdf}.chart{margin:12px 0 4px;border-radius:12px;background:#07100c;border:1px solid #173a2b;overflow:hidden}.chart svg{width:100%;height:auto;display:block}.reason{margin-top:10px;padding:10px;border-left:2px solid var(--green);background:#0a1611}.compact{display:grid;grid-template-columns:1.2fr .8fr .8fr 1fr 1fr;gap:8px;padding:10px;border-bottom:1px solid #1e3b2d;align-items:center}.star{border:0;background:transparent;color:#64756c;font-size:22px;cursor:pointer}.star.on{color:#ffd166}.timeline{font-size:12px;color:var(--sub);margin-top:8px}select{background:#0b1511;color:var(--text);border:1px solid var(--green);border-radius:12px;padding:10px}.empty{padding:30px;text-align:center;color:var(--sub)}@media(max-width:900px){.grid4,.rules{grid-template-columns:1fr 1fr}.candidate-grid{grid-template-columns:1fr}.compact{grid-template-columns:1fr 1fr}}@media(max-width:600px){main{padding:14px}.grid4,.rules{grid-template-columns:1fr}header{align-items:flex-start;flex-direction:column}.date{width:100%}}
.brand{display:flex;align-items:center;gap:12px}.nav-cat{width:42px;height:42px;border-radius:50%;object-fit:cover;object-position:50% 13%;margin-right:10px}.cat-face{width:48px;height:48px;border-radius:50%;object-fit:cover;object-position:50% 13%;border:1px solid var(--green);background:#111}.btc-card{display:grid;grid-template-columns:300px minmax(430px,1fr) 230px;gap:26px;align-items:center;padding:28px 32px;border:1px solid var(--state);border-radius:18px;background:#030605}.btc-price{font-size:28px;font-weight:800;margin:5px 0}.state-entry{--state:#00e783;--state-bg:#082418}.state-caution{--state:#ffc247;--state-bg:#2a210c}.state-stop{--state:#ff5d3a;--state-bg:#2b100a}.status-chip{display:block;margin:8px 0;padding:7px 11px;border:1px solid var(--state);border-radius:999px}.cat-main{width:100%;height:250px;object-fit:contain;filter:drop-shadow(0 12px 20px #000)}.action-card{display:grid;grid-template-columns:150px 1fr 1fr;gap:26px;align-items:center;padding:28px 34px;border:1px solid var(--state);border-radius:18px;background:var(--state-bg)}.warning-mark{font-size:78px;line-height:1;text-align:center;color:var(--state)}.action-big{font-size:42px;font-weight:900;color:var(--state)}.action-lines{border-left:1px solid var(--state);padding-left:34px}.action-lines div{margin:9px 0}.top-table{width:100%;border-collapse:collapse}.top-table th,.top-table td{padding:12px 10px;border-bottom:1px solid #23372d;text-align:left;white-space:nowrap}.top-table th{color:var(--green);font-size:12px}.candidate-row{position:relative}.trade-lock{display:inline-block;margin-left:8px;padding:2px 7px;border-radius:999px;background:#5a1b13;color:#ffb5a6;font-size:11px}.blocked-row{color:#b9aaa6;background:linear-gradient(90deg,rgba(80,18,10,.26),transparent)}.blocked-row td:first-child:before{content:"거래금지";display:inline-block;margin-right:7px;padding:2px 6px;border:1px solid #ff5d3a;border-radius:6px;color:#ff7b61;font-size:10px}.table-wrap{overflow:auto}.dashboard-panel{margin:17px 0;padding:20px;border:1px solid var(--line);border-radius:18px;background:#030605}@media(max-width:900px){.btc-card{grid-template-columns:1fr}.cat-main{height:190px}.action-card{grid-template-columns:1fr}.warning-mark{text-align:left}.action-lines{border-left:0;border-top:1px solid var(--state);padding:15px 0 0}}@media(max-width:600px){.action-big{font-size:30px}.btc-card{padding:16px}}
nav{display:flex;gap:24px;margin:0 0 20px;align-items:center;flex-wrap:wrap}.app-brand{display:flex;align-items:center;gap:10px;margin-right:8px}.app-title{font-size:18px;font-weight:900;color:#f4fff8;white-space:nowrap}.app-brand .nav-cat{margin-right:0}nav a{padding:14px 8px;border:0;border-bottom:2px solid transparent;border-radius:0;background:transparent;font-size:16px}nav a.active{border-color:var(--green);color:var(--green)}
.dual-chart{display:grid;grid-template-columns:1fr 1fr;gap:14px}.chart-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;font-weight:800}.chart-title small{color:var(--sub);font-weight:400}@media(max-width:900px){.dual-chart{grid-template-columns:1fr}}
.page-intro{margin:4px 0 18px}.page-intro h1{margin:0 0 4px}.how{margin-top:7px;color:#c8ffdf}.tip{position:relative;display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;margin-left:4px;border:1px solid #60756a;border-radius:50%;color:#a9b9b0;font-size:10px;cursor:help}.tip:hover:after{content:attr(data-tip);position:absolute;z-index:20;left:0;top:22px;width:220px;padding:9px;border:1px solid var(--green);border-radius:9px;background:#07100c;color:#fff;font-weight:400;white-space:normal}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.filter{padding:8px 13px;border:1px solid #31473c;border-radius:999px;background:#08100c;color:#fff;cursor:pointer}.filter.active{border-color:var(--accent,var(--green));color:var(--accent,var(--green))}.data-table{width:100%;border-collapse:collapse}.data-table th,.data-table td{padding:11px 9px;border-bottom:1px solid #26372f;text-align:left;white-space:nowrap}.data-table th{color:#a6b8ad;font-size:12px}.type-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.type-tab{padding:17px;border:1px solid var(--c);border-radius:16px;background:#050807}.type-tab strong{font-size:28px;color:var(--c)}.type-tab.active{box-shadow:0 0 16px color-mix(in srgb,var(--c) 35%,transparent);background:color-mix(in srgb,var(--c) 9%,#050807)}.expand{display:none}.expand.open{display:table-row}.expand td{padding:16px;background:#07100c}.expand-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.target-strip{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}.target-chip{padding:8px 12px;border:1px solid var(--accent,var(--green));border-radius:10px}.help-note{padding:10px 12px;border-left:2px solid var(--accent,var(--green));background:#0a1510;color:#cbd8d0}.calendar-layout{display:grid;grid-template-columns:300px 1fr;gap:16px}.calendar{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}.day{padding:9px;text-align:center;border-radius:8px}.day.has{color:#bfffd9}.day.selected{outline:1px solid var(--green);background:#0a2a19}.outcome{padding:3px 8px;border-radius:999px}.ok{color:#73eaa8;border:1px solid #23754b}.wait{color:#ffd166;border:1px solid #755b22}.bad{color:#ff8b78;border:1px solid #82372c}.muted{color:#a5b0aa;border:1px solid #45534b}@media(max-width:900px){.type-tabs,.calendar-layout,.expand-grid{grid-template-columns:1fr}.data-table{font-size:12px}}
.hero-guide{display:grid;grid-template-columns:1fr 190px;gap:20px;align-items:center;border-color:var(--accent)}.type-cat-wrap{position:relative;height:190px}.type-cat-wrap img{width:100%;height:100%;object-fit:contain}.type-token{position:absolute;right:7px;top:16px;width:58px;height:58px;border:3px solid var(--accent);border-radius:50%;background:#050807;color:var(--accent);font-size:28px;font-weight:900;text-align:center;line-height:52px}.row-click{cursor:pointer}.row-click:hover{background:#0d1b14}.section-label{margin:20px 0 8px;color:var(--accent,var(--green))}.status-line{display:flex;gap:12px;flex-wrap:wrap}.mini-stat{padding:10px 14px;border:1px solid #294438;border-radius:12px}.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.date-buttons{display:flex;gap:7px;flex-wrap:wrap}.date-btn{padding:8px 11px;border:1px solid #31473c;border-radius:10px;background:#08100c;color:#fff}.date-btn.active{border-color:var(--green);color:var(--green)}@media(max-width:900px){.hero-guide{grid-template-columns:1fr}.type-cat-wrap{height:150px}}
"""


def tip(label, text):
    return f'{label}<span class="tip" data-tip="{html.escape(text, quote=True)}">ⓘ</span>'


def page_intro(title, purpose, how):
    return f'<section class="page-intro"><h1>{title}</h1><div class="sub">{purpose}</div><div class="how">{how}</div></section>'


def shell(title, body, basis, active="dashboard"):
    pins='''<script>function getPins(){try{return JSON.parse(localStorage.getItem("upbitPins")||"[]")}catch(e){return []}}function togglePin(m,b){let p=getPins();p=p.includes(m)?p.filter(x=>x!==m):[...p,m];localStorage.setItem("upbitPins",JSON.stringify(p));if(b){b.classList.toggle("on",p.includes(m));b.textContent=p.includes(m)?"★":"☆"}if(typeof renderWatch==="function")renderWatch()}document.addEventListener("DOMContentLoaded",()=>document.querySelectorAll(".star").forEach(b=>{let on=getPins().includes(b.dataset.market);b.classList.toggle("on",on);b.textContent=on?"★":"☆"}))</script>'''
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css()}</style></head><body><main>{nav(active)}{body}</main>{pins}</body></html>'


def grouped(snapshot):
    groups = {key: [] for key in "ABCD"}
    for row in snapshot.get("candidates", []):
        if row.get("type") in groups:
            groups[row["type"]].append(row)
    for rows in groups.values():
        rows.sort(key=lambda row: (ACTION_RANK.get(row.get("action"),9),-float(row.get("score") or 0),str(row.get("market") or "")))
    return groups

def dist_text(row):
    value=distance_to_entry(row)
    if value is None:return "-"
    if value==0:return "구간 안"
    return f'{abs(value):.1f}% {"위" if value>0 else "아래"}'


def main_page(snapshot, btc):
    groups=grouped(snapshot)
    cards="".join(f'<a class="type-tab" href="type_{k.lower()}.html" style="--c:{INFO[k][1]}"><strong>{k}형 · {len(groups[k])}</strong><div>{INFO[k][2]}</div></a>' for k in "ABCD")
    rows=sum(groups.values(),[]);rows.sort(key=lambda r:(ACTION_RANK.get(r.get("action"),9),-float(r.get("score") or 0),-float(r.get("rr") or 0)))
    trs=[]
    for r in rows:
        targets=r.get("targets") or []
        trs.append(f'<tr data-type="{r.get("type")}" data-action="{fmt(r.get("action"))}"><td><button class="star" data-market="{fmt(r.get("market"))}" onclick="togglePin(\'{fmt(r.get("market"))}\',this)">☆</button></td><td><b>{fmt(r.get("market"))}</b></td><td>{fmt(r.get("type"))}형</td><td>{action_badge(r)}</td><td>{fmt(r.get("score"))}</td><td>{fmt(r.get("price"))}<br><small class="sub">{dist_text(r)}</small></td><td>{fmt(r.get("entry"))}</td><td>{fmt(r.get("stop"))}</td><td>{fmt(targets[0] if targets else None)}</td><td>{fmt(r.get("rr"))}R</td></tr>')
    blocked=int(btc.get("alt_policy",{}).get("size_pct") or 0)==0
    filters=''.join(f'<button class="filter" data-kind="{k}" onclick="setType(\'{k}\',this)">{k if k=="ALL" else k+"형"}</button>' for k in ["ALL","A","B","C","D"])
    body=page_intro("오늘의 전체 스캔","업비트 KRW 전체에서 A/B/C/D 조건에 맞는 후보를 한 번에 비교하는 곳","① 유형 선택 → ② 단계·점수 비교 → ③ 진입거리·손절·손익비 확인 → ④ 관심종목은 별표")
    body+=f'<div class="type-tabs">{cards}</div><section class="panel"><div class="toolbar"><div class="filters" id="typeFilters">{filters}</div><div>{"<span class=trade-lock>BTC 거래금지 · 관찰만</span>" if blocked else ""}</div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>관심</th><th>종목</th><th>유형</th><th>단계</th><th>점수</th><th>{tip("현재가·진입거리","현재가가 진입구간에서 얼마나 떨어져 있는지 보여줘")}</th><th>진입구간</th><th>{tip("손절가","차트 구조가 무효가 되는 가격")}</th><th>{tip("1차 목표가","처음으로 일부 이익을 정리할 가격")}</th><th>{tip("손익비","감수할 손실 대비 기대수익 비율")}</th></tr></thead><tbody id="scanRows">{"".join(trs)}</tbody></table></div></section><script>let selectedType="ALL";function setType(k,b){{selectedType=k;document.querySelectorAll("#typeFilters .filter").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll("#scanRows tr").forEach(r=>r.style.display=k==="ALL"||r.dataset.type===k?"":"none")}}document.addEventListener("DOMContentLoaded",()=>document.querySelector("#typeFilters .filter").click())</script>'
    return shell("오늘의 전체 스캔",body,snapshot,"today")


def dashboard_page(snapshot, watch, btc):
    policy=btc.get("alt_policy",{});box=btc.get("box",{});charts=btc.get("charts",{})
    groups=grouped(snapshot); all_rows=sum(groups.values(),[])
    actionable=[x for x in all_rows if x.get("action") in {"진입 검토","확인 대기"}]
    actionable.sort(key=lambda x:(ACTION_RANK.get(x.get("action"),9),-float(x.get("rr") or 0),-float(x.get("score") or 0)))
    levels=[(box.get("buy_zone",[None,None])[1],"#00e783","매수존"),(box.get("center"),"#d9e0dc","중심"),(box.get("sell_zone",[None])[0],"#ff5d3a","매도존")]
    day_chart=chart_svg(charts.get("day",[]),520,240,levels)
    four_chart=chart_svg(charts.get("4h",[]),520,240,levels)
    blocked=policy.get("size_pct")==0
    top_rows=[]
    for row in actionable[:5]:
        targets=row.get("targets") or []
        top_rows.append(f'<tr class="candidate-row {"blocked-row" if blocked else ""}"><td><b>{fmt(row.get("market"))}</b></td><td>{fmt(row.get("type"))}형</td><td>{fmt(row.get("action"))}</td><td>{fmt(row.get("entry"))}</td><td>{fmt(row.get("stop"))}</td><td>{fmt(targets[0] if targets else None)}</td><td>{fmt(row.get("score"))}점</td><td>{fmt(row.get("rr"))}R</td></tr>')
    top="".join(top_rows) or '<tr><td colspan="8" class="empty">확인 대기 이상 후보 없음</td></tr>'
    size=int(policy.get("size_pct") or 0)
    state="entry" if size>=70 else "caution" if size>0 else "stop"
    state_class=f"state-{state}"; cat=asset_uri(f"cat_{state}.webp")
    position=float(box.get("position_pct") or 0)
    if size == 0 and position >= 70:
        action_title="BTC 박스권 상단 · 매도구간 진입"
    elif size == 0:
        action_title="BTC 구조 이탈 · 신규진입 중단"
    elif size < 70:
        action_title="BTC 중심~상단 · 알트 비중 축소"
    else:
        action_title="BTC 지지 확인 · 선별 진입"
    intro=page_intro("메인 대시보드","비트코인의 큰 추세를 먼저 보고, 오늘 알트코인을 매매해도 되는지 판단하는 곳","① BTC 일봉·4시간봉 확인 → ② 오늘의 행동 확인 → ③ 먼저 볼 후보 확인")
    body=intro+f'''<section class="dashboard-panel btc-card {state_class}"><div><div style="color:var(--state);font-weight:800">BTC 시장상태</div><div class="btc-price">₩{fmt(btc.get("price"))}</div><span class="status-chip">일봉 · {fmt(btc.get("daily_state"))}</span><span class="status-chip">4시간봉 · {fmt(btc.get("four_hour_state"))}</span><span class="status-chip">박스 위치 · {fmt(box.get("position_pct"))}%</span><div class="sub">{str(btc.get('basis',{}).get('four_hour_end','-')).replace('T',' ')} 마감</div></div><div><div class="dual-chart"><div><div class="chart-title">일봉 <small>큰 추세·박스</small></div><div class="chart">{day_chart}</div></div><div><div class="chart-title">4시간봉 <small>횡보·재지지 확인</small></div><div class="chart">{four_chart}</div></div></div><div class="sub">매수존 {fmt(box.get("buy_zone"))} · 중심 {fmt(box.get("center"))} · 매도존 {fmt(box.get("sell_zone"))}</div></div><img class="cat-main" src="{cat}" alt="BTC {fmt(policy.get('mode'))} 상태 고양이"></section>
<section class="dashboard-panel action-card {state_class}"><div class="warning-mark">⚠</div><div><div style="color:var(--state);font-size:18px">오늘의 행동</div><div class="action-big">{action_title}</div><div style="margin-top:8px">알트 신규진입 한도 · <b>{size}%</b></div></div><div class="action-lines"><div>신규진입 · <b>{fmt(policy.get("new_entry"))}</b></div><div>보유종목 · <b>{fmt(policy.get("existing"))}</b></div><div>확인조건 · <b>4시간봉 상단 재지지</b></div></div></section>
<section class="dashboard-panel"><h2>오늘 먼저 볼 후보 5</h2>{'<span class="trade-lock">BTC 거래금지 · 관찰만</span>' if blocked else ''}<div class="table-wrap"><table class="top-table"><thead><tr><th>종목</th><th>유형</th><th>단계</th><th>진입구간</th><th>손절가</th><th>1차 목표가</th><th>점수</th><th>손익비</th></tr></thead><tbody>{top}</tbody></table></div><p><a class="green" href="scan.html">오늘의 전체 스캔 보기 →</a></p></section>'''
    return shell("메인 대시보드",body,snapshot,"dashboard")


def type_page(key, snapshot):
    name, color, title, flow, entry, stop, take = INFO[key]
    rows = grouped(snapshot)[key]
    purpose={"A":"강한 상승 뒤 첫 눌림에서 지지를 확인하고 반등 후보를 찾는 곳","B":"긴 하락 뒤 바닥·박스 하단에서 상승 전환 후보를 찾는 곳","C":"박스 상단 돌파 뒤 재지지하는 추가 상승 후보를 찾는 곳","D":"바닥 압축과 매물대 재탈환으로 급등 전 후보를 찾는 곳"}[key]
    intro=page_intro(f"{name} 후보",purpose,"① 원칙 확인 → ② 단계별 후보 비교 → ③ 필요한 종목만 펼쳐보기 → ④ 자세한 건 업비트에서 확인")
    cat=asset_uri("cat_entry.webp")
    guide=f'<section class="panel hero-guide" style="--accent:{color}"><div><h2 style="color:{color}">{title}</h2><div class="flow" style="border-color:{color}">{flow}</div><div class="rules" style="margin-top:12px"><div class="rule"><b style="color:{color}">진입</b>{entry}</div><div class="rule"><b style="color:{color}">손절</b>{stop}</div><div class="rule"><b style="color:{color}">분할익절</b>{take}</div></div></div><div class="type-cat-wrap"><img src="{cat}" alt="{name} 안내 고양이"><span class="type-token">{key}</span></div></section>'
    trs=[]
    for i,r in enumerate(rows):
        targets=r.get("targets") or []; charts=r.get("charts") or {}; levels=[(r.get("stop"),"#ff667e","손절")]+[(x,color,"진입") for x in r.get("entry",[]) if isinstance(x,(int,float))]
        missing=" · ".join(fmt(x) for x in r.get("missing",[])) or "없음"
        detail=f'<div class="expand-grid"><div><div class="chart-title">일봉 <small>큰 추세</small></div><div class="chart">{chart_svg(charts.get("day",[]),600,190,levels)}</div></div><div><div class="chart-title">4시간봉 <small>진입 흐름</small></div><div class="chart">{chart_svg(charts.get("4h",[]),600,190,levels)}</div></div></div><div class="reason"><b>포착 이유</b> · {fmt(r.get("reason"))}<br><b>현재 판단</b> · {fmt(r.get("action"))}<br><b>남은 조건</b> · {missing}</div><div class="target-strip"><span class="target-chip">진입 {fmt(r.get("entry"))}</span><span class="target-chip">손절 {fmt(r.get("stop"))}</span><span class="target-chip">목표 {fmt(targets[:3])}</span><span class="target-chip">{fmt(r.get("rr"))}R</span></div><p class="help-note">세부 차트와 실제 진입 여부는 업비트에서 확인</p>'
        trs.append(f'<tr class="row-click" onclick="toggleRow({i})"><td><button class="star" data-market="{fmt(r.get("market"))}" onclick="event.stopPropagation();togglePin(\'{fmt(r.get("market"))}\',this)">☆</button></td><td><b>{fmt(r.get("market"))}</b></td><td>{action_badge(r)}</td><td>{fmt(r.get("score"))}</td><td>{fmt(r.get("price"))}<br><small class="sub">{dist_text(r)}</small></td><td>{fmt(r.get("entry"))}</td><td>{fmt(r.get("stop"))}</td><td>{fmt(targets[0] if targets else None)}</td><td>{fmt(r.get("rr"))}R</td></tr><tr id="detail{i}" class="expand"><td colspan="9">{detail}</td></tr>')
    buttons=''.join(f'<button class="filter {"active" if a=="전체" else ""}" onclick="filterAction(\'{a}\',this)">{a}</button>' for a in ["전체","진입 검토","확인 대기","진입가 대기","추격 금지"])
    table=f'<section class="panel" style="--accent:{color}"><div class="toolbar"><div class="filters" id="actionFilters">{buttons}</div><div><button class="filter" onclick="expandAll(true)">모두 펼치기</button> <button class="filter" onclick="expandAll(false)">모두 접기</button></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>관심</th><th>종목</th><th>단계</th><th>점수</th><th>현재가·진입거리</th><th>진입</th><th>손절</th><th>1차 목표</th><th>손익비</th></tr></thead><tbody>{"".join(trs) or "<tr><td colspan=9 class=empty>이번 기준봉 후보 없음</td></tr>"}</tbody></table></div></section>'
    script='''<script>function toggleRow(i){document.getElementById("detail"+i).classList.toggle("open")}function expandAll(open){document.querySelectorAll(".expand").forEach(x=>x.classList.toggle("open",open))}function filterAction(a,b){document.querySelectorAll("#actionFilters .filter").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll("tr.row-click").forEach(r=>{const show=a==="전체"||r.textContent.includes(a);r.style.display=show?"":"none";const d=r.nextElementSibling;if(!show)d.classList.remove("open")})}</script>'''
    return shell(name,intro+guide+table+script,snapshot)

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
    tabs=''.join(f'<button class="type-tab {"active" if k=="A" else ""}" style="--c:{INFO[k][1]}" onclick="setWatchType(\'{k}\',this)"><strong>{k}형</strong><div>{INFO[k][2]}</div></button>' for k in "ABCD")
    intro=page_intro("관심종목 추적","한 번 포착된 종목을 지우지 않고 보관하면서 4시간봉 변화를 계속 확인하는 곳","① A/B/C/D 선택 → ② 고정 관심 확인 → ③ 단계·진입거리 확인 → ④ 변화기록 펼쳐보기")
    note='<p class="help-note">별표는 지금 쓰는 브라우저에 바로 저장돼. 다른 사람의 관심종목과 섞이지 않아.</p>'
    body=intro+f'''<div class="type-tabs">{tabs}</div>{note}<div id="watchRoot"></div><script>const watchItems={data};let watchType="A";const esc=s=>String(s??"-").replace(/[&<>]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;"}}[c]));const num=x=>typeof x==="number"?x.toLocaleString("ko-KR",{{maximumFractionDigits:8}}):esc(x);function dtext(x){{const f=x.display||{{}},p=f.price,e=f.entry||[];if(typeof p!=="number"||!e.length)return "-";const lo=Math.min(...e),hi=Math.max(...e);if(p>=lo&&p<=hi)return "구간 안";const edge=p>hi?hi:lo;return Math.abs((p/edge-1)*100).toFixed(1)+"% "+(p>hi?"위":"아래")}}function row(x){{const f=x.display||{{}},ts=(x.types||[]),dup=ts.length>1?`<span class="badge">${{ts.join("/")}} 중복신호</span>`:"",events=(x.timeline||[]).slice(-8).reverse().map(e=>`<div>${{esc(String(e.at||"").slice(5,16).replace("T"," "))}} · ${{esc((e.types||[]).join("/"))}}형 · ${{esc(e.action)}} · ${{esc(e.note)}}</div>`).join("");const targets=f.targets||[];return `<tr class="row-click" onclick="this.nextElementSibling.classList.toggle('open')"><td><button class="star" data-market="${{esc(x.market)}}" onclick="event.stopPropagation();togglePin('${{esc(x.market)}}',this)">☆</button></td><td><b>${{esc(x.market)}}</b> ${{dup}}</td><td>${{esc(ts.join("/"))}}형</td><td>${{esc(f.action||x.daily_status)}}</td><td>${{num(f.price)}}<br><small class="sub">${{dtext(x)}}</small></td><td>${{esc((f.entry||[]).join(" ~ "))}}</td><td>${{num(f.stop)}}</td><td>${{num(targets[0])}}</td><td>${{num(f.score)}}점 · ${{num(f.rr)}}R</td><td>${{esc(String((x.four_hour||{{}}).last_seen||x.last_seen||"-").slice(5,16).replace("T"," "))}}</td></tr><tr class="expand"><td colspan="10"><b>4시간봉 변화기록</b><div class="timeline">${{events||"아직 변화기록 없음"}}</div></td></tr>`}}function section(title,rows){{return `<h2 class="section-label">${{title}} · ${{rows.length}}개</h2><div class="table-wrap"><table class="data-table"><thead><tr><th>관심</th><th>종목</th><th>신호</th><th>단계</th><th>현재가·진입거리</th><th>진입</th><th>손절</th><th>1차 목표</th><th>점수·손익비</th><th>최근확인</th></tr></thead><tbody>${{rows.map(row).join("")||"<tr><td colspan=10 class=empty>없음</td></tr>"}}</tbody></table></div>`}}function renderWatch(){{const p=getPins(),all=watchItems.filter(x=>(x.types||[]).includes(watchType)),fixed=all.filter(x=>p.includes(x.market)),active=all.filter(x=>!p.includes(x.market)&&!x.archived),archived=all.filter(x=>!p.includes(x.market)&&x.archived);watchRoot.innerHTML=`<section class="panel" style="--accent:${{({{A:"#ff8297",B:"#70c2ff",C:"#c3a7ff",D:"#5ce2b3"}})[watchType]}}">${{section("⭐ 고정 관심",fixed)}}${{section("활성 추적",active)}}${{section("구조 무효 보관",archived)}}</section>`;document.querySelectorAll(".star").forEach(b=>{{const on=p.includes(b.dataset.market);b.classList.toggle("on",on);b.textContent=on?"★":"☆"}})}}function setWatchType(k,b){{watchType=k;document.querySelectorAll(".type-tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");renderWatch()}}document.addEventListener("DOMContentLoaded",renderWatch)</script>'''
    return shell("관심종목 추적",body,basis,"watch")


def history_page(records):
    records=[{**record,"candidates":[{key:value for key,value in row.items() if key!="charts"} for row in record.get("candidates",[])]} for record in records]
    data = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    intro=page_intro("날짜별 기록","과거 후보가 진입구간·목표가·손절가에 닿았는지 확인하고 스캐너 성과를 복기하는 곳","① 날짜 선택 → ② 마감시간 선택 → ③ 당시 후보 확인 → ④ 24H·72H 결과 비교")
    body=intro+f'''<section class="panel"><div id="dateButtons" class="date-buttons"></div><div id="timeButtons" class="filters"></div></section><section class="panel" id="saved"></section><script>const records={data};let selected=records.length?records.length-1:-1;const esc=s=>String(s??"-").replace(/[&<>]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;"}}[c]));const num=x=>typeof x==="number"?x.toLocaleString("ko-KR",{{maximumFractionDigits:8}}):esc(x);function badge(o){{if(!o)return '<span class="outcome wait">확인 예정</span>';const s=o.status||"확인 예정",c=s.includes("목표")||s.includes("진입")?"ok":s.includes("손절")?"bad":s.includes("예정")||s.includes("진행")?"wait":"muted";return `<span class="outcome ${{c}}">${{esc(s)}}</span><br><small class="sub">최대 +${{num(o.mfe_pct)}}% / ${{num(o.mae_pct)}}%</small>`}}function drawDates(){{const dates=[...new Set(records.map(r=>r.date))].sort().reverse();dateButtons.innerHTML=dates.map(d=>`<button class="date-btn ${{records[selected]?.date===d?'active':''}}" onclick="pickDate('${{d}}')">${{d}}</button>`).join("");drawTimes()}}function pickDate(d){{const ids=records.map((r,i)=>r.date===d?i:-1).filter(i=>i>=0);selected=ids[ids.length-1];drawDates();render()}}function drawTimes(){{const d=records[selected]?.date;const slots=["01:00","05:00","09:00","13:00","17:00","21:00"];timeButtons.innerHTML=slots.map(t=>{{const i=records.findIndex(r=>r.date===d&&r.time===t);return `<button class="filter ${{records[selected]?.time===t?'active':''}}" ${{i<0?'disabled':''}} onclick="selected=${{i}};drawTimes();render()">${{t}}${{t==='09:00'?' · 일봉+4H':''}}</button>`}}).join("")}}function render(){{if(selected<0){{saved.innerHTML='<div class="empty">첫 기록 전이야.</div>';return}}const r=records[selected],counts=r.counts||{{}},btc=r.btc||{{}},policy=r.alt_policy||btc.alt_policy||{{}};const acts={{}};(r.candidates||[]).forEach(x=>acts[x.action]=(acts[x.action]||0)+1);let out=`<div class="status-line"><span class="mini-stat">BTC ${{esc(btc.daily_state||'-')}} / ${{esc(btc.four_hour_state||'-')}}</span><span class="mini-stat">알트 진입강도 ${{esc(policy.size_pct??'-')}}%</span><span class="mini-stat">A${{counts.A||0}} · B${{counts.B||0}} · C${{counts.C||0}} · D${{counts.D||0}}</span><span class="mini-stat">진입검토 ${{acts['진입 검토']||0}} · 확인대기 ${{acts['확인 대기']||0}}</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>종목</th><th>유형</th><th>단계</th><th>당시가</th><th>진입</th><th>손절</th><th>1차 목표</th><th>손익비</th><th>24H 결과</th><th>72H 결과</th></tr></thead><tbody>`;out+=(r.candidates||[]).map(x=>`<tr><td><b>${{esc(x.market)}}</b></td><td>${{esc(x.type)}}형</td><td>${{esc(x.action)}}</td><td>${{num(x.price)}}</td><td>${{esc((x.entry||[]).join(' ~ '))}}</td><td>${{num(x.stop)}}</td><td>${{num((x.targets||[])[0])}}</td><td>${{num(x.rr)}}R</td><td>${{badge((x.outcomes||{{}})['24h'])}}</td><td>${{badge((x.outcomes||{{}})['72h'])}}</td></tr>`).join('');out+='</tbody></table></div>';const done=(r.candidates||[]).flatMap(x=>Object.values(x.outcomes||{{}}));const wins=done.filter(x=>String(x.status).includes('목표')).length,stops=done.filter(x=>String(x.status).includes('손절')).length,best=Math.max(0,...done.map(x=>Number(x.mfe_pct)||0)),fall=Math.min(0,...done.map(x=>Number(x.mae_pct)||0));out+=`<div class="status-line" style="margin-top:14px"><span class="mini-stat">목표 성공 ${{wins}}</span><span class="mini-stat">손절 ${{stops}}</span><span class="mini-stat">최고 상승 +${{best.toFixed(1)}}%</span><span class="mini-stat">최대 하락 ${{fall.toFixed(1)}}%</span></div>`;saved.innerHTML=out}}drawDates();render();</script>'''
    basis = records[-1] if records else {}
    return shell("날짜별 기록", body, basis, "history")


def generate():
    records = read(STORE, [])
    watch = read(WATCH, {"items":{}})
    latest = records[-1] if records else {"date": "기록 전", "time": "-", "candidates": []}
    btc = read(BTC, {})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(dashboard_page(latest,watch,btc), encoding="utf-8")
    (OUT / "scan.html").write_text(main_page(latest,btc), encoding="utf-8")
    for key in "ABCD":
        (OUT / f"type_{key.lower()}.html").write_text(type_page(key, latest), encoding="utf-8")
    for old in OUT.glob("coin_*.html"):
        old.unlink()
    for old in OUT.glob("main_dashboard_review_*.html"):
        old.unlink()
    (OUT / "history.html").write_text(history_page(records), encoding="utf-8")
    (OUT / "watchlist.html").write_text(watchlist_page(watch,latest),encoding="utf-8")
    print(OUT / "index.html")


if __name__ == "__main__":
    generate()
