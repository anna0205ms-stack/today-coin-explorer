#!/usr/bin/env python3
from __future__ import annotations
import html, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "binance"
HISTORY = ROOT / "history" / "binance" / "snapshots.json"
TYPE_DESC = {
    "A": "강한 상승 뒤 첫 눌림에서 지지를 확인하는 유형",
    "B": "긴 하락 뒤 바닥·박스 하단에서 반등을 찾는 유형",
    "C": "박스 상단 돌파 뒤 재지지와 추가 상승을 보는 유형",
    "D": "바닥 압축과 매물대 재탈환 뒤 급등 전 흐름을 찾는 유형",
    "E": "급락·투매 뒤 핵심 하단에서 0.382까지만 노리는 기술반등 유형",
}
CSS = r'''
:root{--bg:#090c0f;--panel:#10151a;--line:#27303a;--text:#f5f7fa;--muted:#98a2ad;--gold:#f5b800;--green:#51d483;--red:#ff6565;--blue:#55a7ff;--purple:#a978ff;--orange:#ff9d32}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 70% -10%,#1b1606 0,#090c0f 34%);color:var(--text);font-family:Inter,Pretendard,"Noto Sans KR",system-ui,sans-serif}.wrap{max-width:1480px;margin:auto;padding:18px 22px 40px}.top{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 4px}.brand{display:flex;align-items:center;gap:12px}.logo{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;border:1px solid #765c00;color:var(--gold);font-size:22px}.brand h1{font-size:26px;margin:0}.sub{font-size:12px;color:var(--gold);border:1px solid #4d3d00;padding:5px 9px;border-radius:999px}.switch{display:flex;border:1px solid #2b3138;border-radius:999px;overflow:hidden}.switch a{padding:9px 22px;text-decoration:none;color:#8d98a3}.switch .on{color:#171000;background:linear-gradient(#ffd74a,#e4a600);font-weight:800}.status{display:flex;gap:9px;flex-wrap:wrap}.chip{border:1px solid #29313a;background:#0e1318;border-radius:999px;padding:8px 12px;color:#aeb8c2;font-size:13px}.ok{color:#7ee89d}.nav{display:flex;gap:3px;overflow:auto;border-top:1px solid #222a31;border-bottom:1px solid #222a31;padding:0 4px;margin-bottom:16px}.nav a{white-space:nowrap;text-decoration:none;color:#aab2bb;padding:13px 18px;border-bottom:2px solid transparent}.nav a.active{color:var(--gold);border-color:var(--gold);font-weight:800}.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}.panel{background:linear-gradient(180deg,#11171c,#0c1116);border:1px solid #29323b;border-radius:17px;box-shadow:0 18px 50px rgba(0,0,0,.24);padding:18px}.title{font-weight:800;font-size:21px;margin-bottom:13px}.muted{color:var(--muted);font-size:13px}.hero{min-height:420px}.spark{width:100%;height:190px;background:linear-gradient(180deg,#111920,#0b1014);border-radius:12px;border:1px solid #202a33;padding:8px}.spark svg{width:100%;height:100%}.range{margin-top:16px}.bar{height:8px;background:linear-gradient(90deg,#5aa7ff,#38424f 54%,#ff6e6e);border-radius:10px;position:relative}.pin{position:absolute;top:-7px;width:18px;height:18px;border:4px solid #ffca28;background:#161b20;border-radius:50%}.labels{display:flex;justify-content:space-between;margin-top:10px}.labels b{display:block;font-size:22px}.blue{color:var(--blue)}.red{color:var(--red)}.gold{color:var(--gold)}.green{color:var(--green)}.stagebox{display:grid;grid-template-columns:180px 1fr;gap:18px;align-items:center}.cat{height:235px;display:flex;align-items:center;justify-content:center}.cat img{max-height:225px;max-width:175px;filter:drop-shadow(0 12px 18px #000)}.stages{display:flex;gap:6px;margin:7px 0 14px}.stage{padding:7px 11px;border:1px solid #343c43;color:#7e8790;border-radius:8px}.stage.on{background:var(--gold);color:#111;font-weight:900;border-color:#ffda54}.bigstage{font-size:32px;font-weight:900;color:var(--gold);margin:5px 0}.gates{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:14px}.gate{border:1px solid #2b343d;border-radius:9px;padding:9px 10px;font-size:13px}.row2{display:grid;grid-template-columns:.72fr 1.28fr;gap:14px;margin-top:14px}.scenario{display:grid;gap:10px}.scenario .item{display:grid;grid-template-columns:110px 1fr;gap:14px;border-top:1px solid #273039;padding:13px 0}.scenario .price{font-size:24px;font-weight:900}.cands{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.card{border:1px solid #303943;border-radius:13px;background:#0d1318;padding:13px;min-width:0}.cardhead{display:flex;justify-content:space-between;gap:8px;align-items:center}.market{font-size:18px;font-weight:850}.badge{font-weight:900;padding:4px 7px;border-radius:7px;background:#2a2039;color:#c5a4ff}.mini{height:42px;margin:9px 0}.mini svg{width:100%;height:100%}.stats{display:grid;grid-template-columns:1fr auto;gap:5px;font-size:13px}.star{cursor:pointer;color:#777;background:none;border:0;font-size:19px}.star.on{color:#ffd43b}.counts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.count{padding:7px 14px;border:1px solid #303943;border-radius:999px}.summary{display:flex;gap:16px;align-items:center;margin-top:14px;border-color:#594600}.summary strong{color:var(--gold);white-space:nowrap}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:10px 8px;border-bottom:1px solid #26303a;text-align:left;font-size:13px}.table th{color:#9ea8b2}.allgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.empty{padding:50px;text-align:center;color:#8f98a2}.footer{color:#65707c;text-align:center;font-size:12px;margin-top:26px}@media(max-width:1000px){.grid,.row2{grid-template-columns:1fr}.cands,.allgrid{grid-template-columns:repeat(2,1fr)}.switch{display:none}}@media(max-width:640px){.wrap{padding:10px}.top{align-items:flex-start}.brand h1{font-size:20px}.status{display:none}.cands,.allgrid{grid-template-columns:1fr}.stagebox{grid-template-columns:110px 1fr}.cat{height:160px}.cat img{max-height:155px;max-width:105px}.bigstage{font-size:25px}.gates{grid-template-columns:1fr}.nav a{padding:11px 12px}.labels b{font-size:17px}}
'''
JS = r'''const KEY='okotam_binance_watchlist';function saved(){try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch(e){return []}}function save(v){localStorage.setItem(KEY,JSON.stringify(v))}function sync(){const s=saved();document.querySelectorAll('[data-star]').forEach(b=>{b.classList.toggle('on',s.includes(b.dataset.star));b.textContent=s.includes(b.dataset.star)?'★':'☆'});if(document.body.dataset.page==='watchlist'){document.querySelectorAll('[data-market]').forEach(c=>c.style.display=s.includes(c.dataset.market)?'block':'none');const any=[...document.querySelectorAll('[data-market]')].some(c=>c.style.display!=='none');document.getElementById('watch-empty').style.display=any?'none':'block'}}document.addEventListener('click',e=>{const b=e.target.closest('[data-star]');if(!b)return;let s=saved(),m=b.dataset.star;s=s.includes(m)?s.filter(x=>x!==m):[...s,m];save(s);sync()});sync();'''

def esc(x): return html.escape(str(x))
def money(x):
    try:
        x=float(x)
        if x>=1000:return f"{x:,.0f}"
        if x>=1:return f"{x:,.4f}".rstrip('0').rstrip('.')
        return f"{x:.8f}".rstrip('0').rstrip('.')
    except:return str(x)

def spark(values,color="#f5b800",w=500,h=160):
    vals=[float(x) for x in values if x is not None]
    if len(vals)<2:return ""
    lo,hi=min(vals),max(vals); span=max(hi-lo,1e-9); pts=[]
    for i,v in enumerate(vals):
        x=i/(len(vals)-1)*w; y=h-((v-lo)/span*h*.82+h*.09); pts.append(f"{x:.1f},{y:.1f}")
    return f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none"><polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="3" vector-effect="non-scaling-stroke"/></svg>'

def nav(active):
    items=[('today','index.html','오늘'),('scan','scan.html','전체스캔'),('A','a.html','A형'),('B','b.html','B형'),('C','c.html','C형'),('D','d.html','D형'),('E','e.html','E형'),('watchlist','watchlist.html','관심종목'),('history','history.html','기록'),('training','training.html','훈련소')]
    return '<div class="nav">'+''.join(f'<a class="{"active" if k==active else ""}" href="{u}">{t}</a>' for k,u,t in items)+'</div>'

def header(data,active):
    stamp=esc(data.get('generated_at','첫 스캔 전'))
    return f'''<div class="top"><div class="brand"><div class="logo">✦</div><div><h1>오늘의 코인 탐험대</h1><span class="sub">BINANCE · SPOT USDT</span></div></div><div class="switch"><a href="../index.html">UPBIT</a><a class="on" href="index.html">BINANCE</a></div><div class="status"><span class="chip">최근 스캔 {stamp[-14:-6] if len(stamp)>14 else stamp} KST</span><span class="chip ok">● 정상 작동</span></div></div>{nav(active)}'''

def candidate_card(c):
    typ=c.get('type','?'); colors={'A':'#a978ff','B':'#55a7ff','C':'#51d483','D':'#ff9d32','E':'#ff6565'}; col=colors.get(typ,'#f5b800')
    en=c.get('entry',[0,0]); t=(c.get('targets') or [0])[0]
    return f'''<div class="card" data-market="{esc(c.get('market'))}"><div class="cardhead"><div><div class="market">{esc(c.get('market'))}</div><div class="muted">{typ}형 {esc(c.get('score'))} · {esc(c.get('action'))}</div></div><div><span class="badge" style="background:{col}22;color:{col}">{esc(c.get('stage'))}</span><button class="star" data-star="{esc(c.get('market'))}">☆</button></div></div><div class="mini">{spark(c.get('spark',[]),col,320,70)}</div><div class="stats"><span>진입</span><b>{money(en[0])} ~ {money(en[1])}</b><span class="red">손절</span><b class="red">{money(c.get('stop'))}</b><span class="green">TP1</span><b class="green">{money(t)}</b><span class="blue">RR</span><b class="blue">{esc(c.get('rr'))}</b></div><div class="muted" style="margin-top:9px;line-height:1.45">{esc(c.get('reason',''))}</div></div>'''

def shell(data,active,body,page=''):
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>오코탐 BINANCE</title><style>{CSS}</style></head><body data-page="{page}"><div class="wrap">{header(data,active)}{body}<div class="footer">BINANCE Spot USDT 공개 시세 기반 · 주문 실행 없음 · UPBIT 스캐너와 데이터/결과 완전 분리</div></div><script>{JS}</script></body></html>'''

def today(data):
    reg=data.get('market_regime',{}); btc=reg.get('btc',{}); box=btc.get('box',{}); corr=btc.get('correction',{}); stage=reg.get('stage','M2'); pos=max(0,min(100,float(box.get('position_pct',50))))
    cats={'M0':'../assets/cat_stop.webp','M5':'../assets/cat_caution.webp'}; cat=cats.get(stage,'../assets/cat_entry.webp')
    top=data.get('candidates',[])[:3]
    gate_html=''.join(f'<div class="gate"><b>{t}형</b> · {esc((reg.get("gates",{}).get(t) or {}).get("label","-"))}</div>' for t in 'ABCDE')
    cards=''.join(candidate_card(c) for c in top) or '<div class="empty">현재 상위 후보 없음</div>'
    counts=''.join(f'<span class="count">{t} {data.get("counts",{}).get(t,0)}개</span>' for t in 'ABCDE'); reasons=' · '.join(reg.get('reasons',[])[:2])
    body=f'''<div class="grid"><section class="panel hero"><div class="title">₿ BTCUSDT 시장 상태</div><div class="muted">Binance BTCUSDT 완성 일봉 / 4H · 기준봉 {esc(data.get('basis_4h_end','-'))}</div><div class="spark" style="margin-top:12px">{spark(btc.get('spark',[]),'#f5b800')}</div><div class="range"><div class="bar"><span class="pin" style="left:calc({pos}% - 9px)"></span></div><div class="labels"><div>박스 하단<b class="blue">${money(box.get('low',0))}</b></div><div style="text-align:center">중심<b class="blue">${money(box.get('center',0))}</b></div><div style="text-align:right">박스 상단<b class="red">${money(box.get('high',0))}</b></div></div></div><div class="counts"><span class="count">일봉 · {esc(btc.get('daily_state','-'))}</span><span class="count">4H · {esc(btc.get('four_hour_state','-'))}</span><span class="count gold">현재 ${money(btc.get('price',0))}</span></div></section><section class="panel hero"><div class="title">현재 시장 단계</div><div class="stagebox"><div class="cat"><img src="{cat}" alt="숙도지"></div><div><div class="stages">{''.join(f'<span class="stage {"on" if s==stage else ""}">{s}</span>' for s in ['M0','M1','M2','M3','M4','M5'])}</div><div class="bigstage">{esc(stage)} {esc(reg.get('name',''))}</div><div style="font-size:19px">신규 알트 진입 한도 <b class="gold">{esc(reg.get('alt_entry_limit_pct',0))}%</b></div><p class="muted">시장 단계가 바뀌면 숙도지의 표정과 행동 안내도 함께 바뀌어.</p><div class="gates">{gate_html}</div></div></div></section></div><div class="row2"><section class="panel"><div class="title">🛡 BTC 조정이 시작된다면</div><div class="scenario"><div class="item"><div>1차 방어<div class="price blue">{money(corr.get('defense1',0))}</div></div><div>알트 신규진입 축소</div></div><div class="item"><div>2차 방어<div class="price gold">{money(corr.get('defense2',0))}</div></div><div>단타 정리 · 현금 확대</div></div><div class="item"><div>구조 훼손<div class="price red">{money(corr.get('invalid',0))}</div></div><div>신규진입 중단</div></div></div></section><section class="panel"><div class="title">🏆 BINANCE USDT 현재 상위 후보</div><div class="cands">{cards}</div><div class="counts">{counts}</div></section></div><section class="panel summary"><strong>💡 오늘의 한줄 요약</strong><span>{esc(reasons or '시장 데이터 수집 후 자동으로 요약해.')}</span></section>'''
    return shell(data,'today',body)

def listing(data,typ=None,active='scan',watch=False):
    rows=data.get('candidates',[]); rows=[c for c in rows if typ is None or c.get('type')==typ]; cards=''.join(candidate_card(c) for c in rows)
    title='전체 스캔' if typ is None else f'{typ}형 후보 · {TYPE_DESC[typ]}'
    empty='<div class="empty" id="watch-empty">별표로 고정한 BINANCE 후보가 아직 없어.</div>' if watch else '<div class="empty">현재 조건을 통과한 후보가 없어.</div>'
    body=f'<section class="panel"><div class="title">{esc(title)}</div><div class="muted">USDT 현물 · 유니버스 {esc(data.get("universe_count",0))}개 · 최소 24H 거래대금 ${money(data.get("min_quote_volume",0))}</div><div class="allgrid" style="margin-top:14px">{cards}</div>{empty if not cards or watch else ""}</section>'
    return shell(data,active,body,'watchlist' if watch else '')

def history_page(data):
    try: hist=json.loads(HISTORY.read_text(encoding='utf-8')); hist=hist[-30:][::-1]
    except: hist=[]
    rows=''.join(f'<tr><td>{esc(x.get("generated_at",""))}</td><td>{esc((x.get("market_regime") or {}).get("stage",""))}</td><td>{esc((x.get("market_regime") or {}).get("name",""))}</td><td>{" / ".join(f"{t}:{(x.get("counts") or {}).get(t,0)}" for t in "ABCDE")}</td></tr>' for x in hist)
    body=f'<section class="panel"><div class="title">날짜별 BINANCE 스캔 기록</div><table class="table"><thead><tr><th>생성시각</th><th>시장단계</th><th>상태</th><th>A~E 후보수</th></tr></thead><tbody>{rows}</tbody></table>{"" if rows else "<div class=empty>첫 스캔 기록 전이야.</div>"}</section>'
    return shell(data,'history',body)

def training(data):
    blocks=''.join(f'<div class="card"><div class="market">{t}형</div><p>{esc(desc)}</p><div class="muted">현재 후보 {data.get("counts",{}).get(t,0)}개</div></div>' for t,desc in TYPE_DESC.items())
    body=f'<section class="panel"><div class="title">BINANCE A~E 훈련소</div><div class="allgrid">{blocks}</div><p class="muted" style="margin-top:14px">전략 정의는 UPBIT판과 같은 철학을 쓰지만, Binance판은 Binance USDT 완성봉과 Binance 호가단위만 사용한다.</p></section>'
    return shell(data,'training',body)

def render():
    OUT.mkdir(parents=True,exist_ok=True)
    try: data=json.loads((OUT/'latest.json').read_text(encoding='utf-8'))
    except: data={"generated_at":"첫 스캔 전","market_regime":{"stage":"M2","name":"알트 준비","alt_entry_limit_pct":35,"gates":{},"btc":{"box":{},"correction":{},"spark":[]}},"counts":{},"candidates":[]}
    pages={'index.html':today(data),'scan.html':listing(data),'a.html':listing(data,'A','A'),'b.html':listing(data,'B','B'),'c.html':listing(data,'C','C'),'d.html':listing(data,'D','D'),'e.html':listing(data,'E','E'),'watchlist.html':listing(data,None,'watchlist',True),'history.html':history_page(data),'training.html':training(data)}
    for name,text in pages.items():(OUT/name).write_text(text,encoding='utf-8')
    print('BINANCE dashboard rendered:', ', '.join(pages))

if __name__=='__main__': render()
