#!/usr/bin/env python3
from __future__ import annotations
import html,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scanner.unified_dashboard import css as upbit_css,asset_uri
OUT=ROOT/"outputs"/"binance";HISTORY=ROOT/"history"/"binance"/"snapshots.json"
INFO={"A":("급등 후 첫 눌림","#ff8297","강한 상승 뒤 첫 눌림에서 지지를 확인"),"B":("바닥 반등","#70c2ff","긴 하락 뒤 바닥·박스 하단에서 반등 확인"),"C":("돌파 후 재지지","#c3a7ff","박스 상단 돌파 뒤 재지지와 추가 상승 확인"),"D":("급등 전 재탈환","#5ce2b3","바닥 압축과 매물대 재탈환 흐름 확인"),"E":("급락 후 기술반등","#ffb454","급락 뒤 핵심 하단에서 0.382 기술반등 확인")}
def esc(v):return html.escape(str(v if v is not None else "-"))
def num(v):
 try:return f"{float(v):,.8f}".rstrip("0").rstrip(".")
 except:return esc(v)
def nav(active="today"):
 cat=asset_uri("cat_entry.webp");sa=active=="today" or active.startswith("type_");ta=active.startswith("training_")
 scan=f'''<details class="nav-drop" {"open" if sa else ""}><summary class="{"active" if sa else ""}">오늘의 전체 스캔 <span>▾</span></summary><div class="nav-drop-menu"><a class="{"active" if active=="today" else ""}" href="scan.html">전체 보기</a>{''.join(f'<a class="{"active" if active==f"type_{k.lower()}" else ""}" href="type_{k.lower()}.html">{k}형</a>' for k in "ABCDE")}</div></details>'''
 train=f'''<details class="nav-drop" {"open" if ta else ""}><summary class="{"active" if ta else ""}">훈련소 <span>▾</span></summary><div class="nav-drop-menu">{''.join(f'<a class="{"active" if active==f"training_{k.lower()}" else ""}" href="training_{k.lower()}.html">{k}형</a>' for k in "ABCDE")}</div></details>'''
 return f'''<nav><div class="app-brand"><img class="nav-cat" src="{cat}" alt="회색 고양이"><span class="app-title">오늘의 코인 탐험대</span></div><a href="../index.html">메인 대시보드</a>{scan}{train}<a class="{"active" if active=="watch" else ""}" href="watchlist.html">관심종목 추적</a><a class="{"active" if active=="history" else ""}" href="history.html">날짜별 기록</a></nav>'''
def watch_js():return '''<script>const WATCH_KEY="okotam_binance_watchlist";function getPins(){try{return JSON.parse(localStorage.getItem(WATCH_KEY)||"[]")}catch(e){return[]}}function togglePin(m){let p=getPins();p=p.includes(m)?p.filter(x=>x!==m):[...p,m];localStorage.setItem(WATCH_KEY,JSON.stringify(p));syncStars();if(typeof renderWatch==="function")renderWatch()}function syncStars(){const p=getPins();document.querySelectorAll("[data-market]").forEach(b=>{const on=p.includes(b.dataset.market);b.classList.toggle("on",on);b.textContent=on?"★":"☆"})}document.addEventListener("DOMContentLoaded",syncStars)</script>'''
def shell(title,body,data,active="today"):
 stamp=esc(data.get("generated_at","첫 스캔 전"))
 return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · 오코탐 BINANCE</title><style>{upbit_css()}</style></head><body><main>{nav(active)}<div class="system-bar"><span class="system-dot"></span><b>BINANCE SPOT USDT</b><span class="system-divider">|</span><span class="system-item">최근 업데이트 {stamp}</span><span class="system-divider">|</span><span class="system-item">정상 작동</span><span style="margin-left:auto"><a class="green" href="../scan.html">UPBIT KRW 보기 →</a></span></div>{body}<footer class="sub" style="margin:28px 0 8px">BINANCE Spot USDT 공개 시세 기반 · 주문 실행 없음 · UPBIT 데이터와 완전 분리</footer></main>{watch_js()}</body></html>'''
def intro(t,s,h):return f'<div class="page-intro"><h1>{esc(t)}</h1><div class="sub">{esc(s)}</div><div class="how">{esc(h)}</div></div>'
def aclass(a):return "act0" if "진입" in str(a) else "act1" if "대기" in str(a) else "act3" if "금지" in str(a) else "act2"
def rows_html(rows,watch=False):
 out=[]
 for c in rows:
  market=esc(c.get("market"));typ=esc(c.get("type","?"));action=esc(c.get("action","확인 대기"));stage=esc(c.get("stage","-"));entry=c.get("entry") or [];targets=c.get("targets") or []
  star=f'<button class="star" data-market="{market}" onclick="event.stopPropagation();togglePin(\'{market}\')">☆</button>'
  out.append(f'''<tr class="row-click" data-action="{action}" onclick="this.nextElementSibling.classList.toggle('open')"><td>{star}</td><td><b>{market}</b></td><td>{typ}형 · {stage}<br><span class="badge {aclass(action)}">{action}</span></td><td>{num(c.get("score"))}점</td><td>{num(c.get("price"))}</td><td>{esc(" ~ ".join(num(x) for x in entry))}</td><td>{num(c.get("stop"))}</td><td>{num(targets[0] if targets else None)}</td><td>{num(c.get("rr"))}R</td></tr><tr class="expand"><td colspan="9"><div class="expand-grid"><div><b>판단 근거</b><div class="reason">{esc(c.get("reason","스캔 조건 충족"))}</div></div><div><b>목표 계획</b><div class="target-strip">{''.join(f'<span class="target-chip">TP{i+1} {num(v)}</span>' for i,v in enumerate(targets))}</div></div></div></td></tr>''')
 return "".join(out)
def table(rows):
 return f'''<div class="table-wrap"><table class="data-table"><thead><tr><th>관심</th><th>종목</th><th>현재판단·단계</th><th>점수</th><th>현재가·진입거리</th><th>진입</th><th>손절</th><th>1차 목표</th><th>손익비</th></tr></thead><tbody>{rows_html(rows) or "<tr><td colspan=9 class=empty>이번 기준봉 후보 없음</td></tr>"}</tbody></table></div>'''
def controls():return '''<div class="toolbar"><div class="filters" id="actionFilters"><button class="filter active" onclick="filterRows('전체',this)">전체</button><button class="filter" onclick="filterRows('진입',this)">진입 검토</button><button class="filter" onclick="filterRows('대기',this)">확인 대기</button><button class="filter" onclick="filterRows('금지',this)">거래 금지</button></div><div><button class="filter" onclick="expandAll(true)">모두 펼치기</button> <button class="filter" onclick="expandAll(false)">모두 접기</button></div></div><script>function expandAll(v){document.querySelectorAll(".expand").forEach(x=>x.classList.toggle("open",v))}function filterRows(q,b){document.querySelectorAll("#actionFilters .filter").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll(".row-click").forEach(x=>{const on=q==="전체"||(x.dataset.action||"").includes(q);x.style.display=on?"":"none";x.nextElementSibling.style.display=on?"":"none"})}</script>'''
def listing(data,typ=None):
 rows=[x for x in data.get("candidates",[]) if typ is None or x.get("type")==typ];title="오늘의 전체 스캔" if typ is None else f"{typ}형 · {INFO[typ][0]}"
 tabs="".join(f'<a class="type-tab {"active" if typ==k else ""}" style="--c:{INFO[k][1]}" href="type_{k.lower()}.html"><strong>{k}형</strong><div>{INFO[k][0]}</div></a>' for k in "ABCDE")
 body=intro(title,f'BINANCE USDT 현물 · 유니버스 {data.get("universe_count",0)}개 · 기준봉 {data.get("basis_4h_end","-")}','행을 누르면 판단 근거와 목표 계획이 펼쳐집니다.')+f'<div class="type-tabs">{tabs}</div><section class="panel" style="--accent:{INFO.get(typ,("", "#00e783"))[1]}">{controls()}{table(rows)}</section>'
 return shell(title,body,data,"today" if typ is None else f"type_{typ.lower()}")
def watch_page(data):
 tabs="".join(f'<button class="type-tab {"active" if k=="A" else ""}" style="--c:{INFO[k][1]}" onclick="setWatchType(\'{k}\',this)"><strong>{k}형</strong><div>{INFO[k][0]}</div></button>' for k in "ABCDE");payload=json.dumps(data.get("candidates",[]),ensure_ascii=False).replace("</","<\\/")
 body=intro("관심종목 추적","브라우저에 고정한 BINANCE USDT 후보만 유형별로 확인","별표는 UPBIT 관심종목과 분리 저장됩니다.")+f'''<div class="type-tabs">{tabs}</div><p class="help-note">별표는 지금 쓰는 브라우저에 바로 저장됩니다.</p><div id="watchRoot"></div><script>const watchItems={payload};let watchType="A";function setWatchType(k,b){{watchType=k;document.querySelectorAll(".type-tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");renderWatch()}}function renderWatch(){{const pins=getPins(),rs=watchItems.filter(x=>x.type===watchType&&pins.includes(x.market));watchRoot.innerHTML='<section class="panel">'+(rs.length?'<div class="candidate-grid">'+rs.map(x=>'<article class="candidate"><b>'+x.market+'</b><div class="kv"><span>단계</span><span>'+x.stage+'</span><span>진입</span><span>'+(x.entry||[]).join(" ~ ")+'</span><span>손절</span><span>'+x.stop+'</span><span>1차 목표</span><span>'+((x.targets||[])[0]||"-")+'</span></div></article>').join("")+'</div>':'<div class="empty">고정한 후보 없음</div>')+'</section>';syncStars()}}document.addEventListener("DOMContentLoaded",renderWatch)</script>'''
 return shell("관심종목 추적",body,data,"watch")
def history_page(data):
 try:records=json.loads(HISTORY.read_text(encoding="utf-8"))[-60:]
 except:records=[]
 trs="".join(f'<tr><td>{esc(x.get("generated_at"))}</td><td>{esc((x.get("market_regime") or {}).get("stage"))}</td><td>{esc((x.get("market_regime") or {}).get("name"))}</td><td>{" · ".join(f"{k}{(x.get("counts") or {}).get(k,0)}" for k in "ABCDE")}</td></tr>' for x in records[::-1])
 body=intro("날짜별 기록","BINANCE 스캔 당시의 후보와 시장단계를 다시 확인","저장된 스캔을 시간순으로 확인합니다.")+f'<section class="panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>생성시각</th><th>시장단계</th><th>상태</th><th>A~E 후보수</th></tr></thead><tbody>{trs or "<tr><td colspan=4 class=empty>첫 기록 전입니다.</td></tr>"}</tbody></table></div></section>'
 return shell("날짜별 기록",body,data,"history")
def training_page(data,k):
 name,color,desc=INFO[k];body=intro(f"훈련소 · {k}형",f"{desc} 사례를 멀티타임프레임으로 복기하는 페이지","큰 구조 → 진입 시간봉 → 손절·분할청산 → 성공·경고·실패 순서로 봅니다.")
 body+=f'''<section class="strategy-model" style="--accent:{color}"><h2>{k}형 · {name}</h2><div class="sub">BINANCE USDT 완성봉에 같은 판정 원칙을 적용합니다.</div><div class="stage-grid"><div class="stage-card"><b>{k}0 · 후보</b>큰 구조와 거래량 확인</div><div class="stage-card"><b>{k}1 · 관찰</b>핵심 가격대 접근</div><div class="stage-card"><b>{k}2 · 확인</b>지지·재탈환 확인</div><div class="stage-card"><b>{k}3 · 실행</b>손절이 짧은 자리만 진입</div></div></section><section class="panel" style="--accent:{color}"><h2>시간봉을 좁혀 실제 타점 찾기</h2><div class="timeframe-flow"><div><b>일봉</b>후보·큰 구조</div><div><b>4시간봉</b>핵심 범위</div><div><b>1시간봉</b>대기 가격</div><div><b>5분봉</b>실행 확인</div></div><p class="help-note">일봉과 4시간봉은 위치를 정하고, 실제 진입은 낮은 시간봉 확인 뒤 결정합니다.</p></section><section class="panel"><h2>진입 전 최종 체크</h2><div class="training-close"><div><b>후보 선정</b><span>구조·거래량 충족</span></div><div><b>진입</b><span>확인봉 뒤 실행</span></div><div><b>청산</b><span>공급대별 분할</span></div><div><b>폐기</b><span>손절선 이탈</span></div></div></section>'''
 return shell(f"훈련소 {k}형",body,data,f"training_{k.lower()}")
def render():
 OUT.mkdir(parents=True,exist_ok=True)
 try:data=json.loads((OUT/"latest.json").read_text(encoding="utf-8"))
 except:data={"generated_at":"첫 스캔 전","candidates":[],"counts":{}}
 pages={"index.html":listing(data),"scan.html":listing(data),"watchlist.html":watch_page(data),"history.html":history_page(data)}
 for k in "ABCDE":
  pages[f"type_{k.lower()}.html"]=listing(data,k);pages[f"{k.lower()}.html"]=pages[f"type_{k.lower()}.html"];pages[f"training_{k.lower()}.html"]=training_page(data,k)
 pages["training.html"]=pages["training_a.html"]
 for n,c in pages.items():(OUT/n).write_text(c,encoding="utf-8")
 print("BINANCE UPBIT-parity pages rendered:",", ".join(pages))
if __name__=="__main__":render()
