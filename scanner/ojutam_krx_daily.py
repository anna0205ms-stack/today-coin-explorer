from __future__ import annotations

import html, json, math, re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "ojutam"
HISTORY = ROOT / "history" / "ojutam_snapshots.json"
KST = timezone(timedelta(hours=9))
LETTERS = "ABCDEF"
INFO = {
    "A": ("#ff8297", "급등 후 첫 눌림", "강한 상승 → 첫 눌림 → 전고점 재도전 후보"),
    "B": ("#70c2ff", "바닥·박스 하단 반등", "장기 하락 → 바닥 횡보 → 하단 회복"),
    "C": ("#c3a7ff", "박스 상단 돌파", "박스 횡보 → 상단 반복 접촉 → 돌파"),
    "D": ("#5ce2b3", "재탈환·압축", "장기 하락 → 바닥 압축 → 매물대 재탈환 접근"),
    "E": ("#ffb454", "급락 후 기술적 반등", "급락·투매 → 하단 형성 → 기술적 반등 후보"),
    "F": ("#56d6ff", "고점권·과거 매물대", "신고가·고점권 상승 → 과거 횡보 매물대 접근"),
}


def esc(v): return html.escape(str(v if v not in (None, "") else "-"))
def finite(v, default=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception:return default

def pct(a,b): return (a/b-1)*100 if b else 0.0

def load_marcap():
    frames=[]
    for year in (2024,2025,2026):
        url=f"https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.csv.gz"
        try:
            x=pd.read_csv(url,dtype={"Code":str},compression="gzip")
            x["Date"]=pd.to_datetime(x["Date"])
            frames.append(x)
        except Exception as e:
            print("marcap",year,e)
    if not frames: raise RuntimeError("marcap data unavailable")
    allx=pd.concat(frames,ignore_index=True).sort_values(["Code","Date"])
    last_date=allx["Date"].max()
    latest=allx[allx["Date"]==last_date].copy()
    latest["Code"]=latest["Code"].astype(str).str.zfill(6)
    latest=latest[latest["Market"].isin(["KOSPI","KOSDAQ"])]
    latest=latest[(latest["Marcap"]>=300_000_000_000) & (latest["Amount"]>=3_000_000_000)]
    bad=re.compile(r"(스팩|SPAC|리츠|REIT|ETF|ETN|인버스|레버리지|선물|우$|우B$|우C$|우선주)",re.I)
    latest=latest[~latest["Name"].astype(str).str.contains(bad,na=False)]
    codes=set(latest["Code"])
    allx["Code"]=allx["Code"].astype(str).str.zfill(6)
    allx=allx[allx["Code"].isin(codes)]
    frames_by_code={}
    for code,g in allx.groupby("Code"):
        q=g.set_index("Date")[["Open","High","Low","Close","Volume","Amount"]].copy().sort_index()
        q=q[~q.index.duplicated(keep="last")]
        frames_by_code[code]=q
    return latest.reset_index(drop=True), frames_by_code, last_date.date().isoformat()


def row_base(code,name,market,typ,score,flow,reason,levels,df):
    return {"code":code,"market":code,"name":name,"exchange":market,"type":typ,"score":round(score,1),"flow":flow,"reason":reason,"levels":levels,"charts":{"day":chart_rows(df)}}

def chart_rows(df,n=180):
    out=[]
    for dt,r in df.tail(n).iterrows():
        out.append([pd.Timestamp(dt).isoformat(),finite(r.Open),finite(r.High),finite(r.Low),finite(r.Close),finite(r.Volume)])
    return out


def analyze_one(code,name,market,df):
    if df is None or len(df)<140:return []
    d=df.tail(280).copy(); c=d.Close; h=d.High; l=d.Low; v=d.Volume
    cur=finite(c.iloc[-1]); recent=d.tail(120); base30=d.tail(30); base60=d.tail(60)
    high120=finite(recent.High.max()); low120=finite(recent.Low.min()); pos=(cur-low120)/max(high120-low120,1e-9)
    prior=d.iloc[:-20].tail(140); prior_high=finite(prior.High.max()) if len(prior) else high120
    vol20=finite(v.tail(20).median(),1); vol5=finite(v.tail(5).mean(),1)
    out=[]
    # A: strong rise then first controlled pullback
    low_idx=recent.Low.idxmin(); after=recent.loc[low_idx:]
    peak=finite(after.High.max()) if len(after) else high120
    rise=pct(peak,finite(recent.loc[low_idx,"Low"])) if len(after) else 0
    pull=max(0,pct(peak,cur)*-1) if False else (peak-cur)/peak*100 if peak else 0
    if rise>=35 and 4<=pull<=28 and cur>=low120*1.18:
        score=min(10,4+rise/18+(28-pull)/12+(1 if vol5<=vol20*1.25 else 0))
        out.append(row_base(code,name,market,"A",score,INFO["A"][2],f"최근 상승 {rise:.0f}% 뒤 고점 대비 {pull:.1f}% 눌림",{"swing_high":peak,"support":finite(base30.Low.min())},d))
    # B: long decline, compact base, lower-half recovery
    b_lo=finite(base30.Low.min()); b_hi=finite(base30.High.max()); bw=pct(b_hi,b_lo); decline=(prior_high-b_lo)/prior_high*100 if prior_high else 0
    recovery=(cur-b_lo)/max(b_hi-b_lo,1e-9)
    if decline>=25 and bw<=28 and recovery<=0.72 and cur>=b_lo*1.02:
        score=min(10,4+decline/18+(28-bw)/10+(0.8 if cur>finite(base30.Close.iloc[-6:].mean()) else 0))
        out.append(row_base(code,name,market,"B",score,INFO["B"][2],f"과거 고점 대비 {decline:.0f}% 하락 후 {bw:.1f}% 폭 바닥 박스",{"base_low":b_lo,"base_high":b_hi,"prior_high":prior_high},d))
    # C: box top repeatedly tested and current at/through top
    bx=base60.iloc[:-3] if len(base60)>10 else base60; xlo=finite(bx.Low.min()); xhi=finite(bx.High.max()); xw=pct(xhi,xlo)
    touches=int((bx.High>=xhi*0.975).sum())
    if 7<=xw<=38 and touches>=2 and cur>=xhi*0.96:
        breakout=pct(cur,xhi); score=min(10,5+touches*.45+(38-xw)/20+max(0,breakout)/3)
        out.append(row_base(code,name,market,"C",score,INFO["C"][2],f"박스 상단 {touches}회 접촉 · 현재 상단 대비 {breakout:+.1f}%",{"box_low":xlo,"box_high":xhi},d))
    # D: prolonged decline + tight base + reclaim approach
    base20=d.iloc[-25:-3]; blo=finite(base20.Low.min()); bhi=finite(base20.High.max()); bwidth=pct(bhi,blo); ddecl=(prior_high-blo)/prior_high*100 if prior_high else 0
    impulse=finite(v.tail(3).max())/max(finite(v.iloc[-25:-3].median()),1)
    if ddecl>=20 and bwidth<=20 and cur>=bhi*0.93 and impulse>=1.25:
        score=min(10,4+ddecl/22+(20-bwidth)/10+min(2,impulse/2))
        out.append(row_base(code,name,market,"D",score,INFO["D"][2],f"{ddecl:.0f}% 하락 후 {bwidth:.1f}% 압축 · 거래량 {impulse:.1f}배",{"base_low":blo,"reclaim":bhi,"prior_high":prior_high},d))
    # E: capitulation and rebound from major low
    low20=finite(d.tail(20).Low.min()); dd=(high120-low20)/high120*100 if high120 else 0; bounce=pct(cur,low20)
    volratio=finite(v.tail(10).max())/max(finite(v.tail(60).median()),1)
    if dd>=30 and 2<=bounce<=25 and low20<=low120*1.04 and volratio>=1.15:
        score=min(10,4+dd/20+(25-bounce)/18+min(2,volratio/2))
        out.append(row_base(code,name,market,"E",score,INFO["E"][2],f"고점 대비 {dd:.0f}% 급락 뒤 저점에서 {bounce:.1f}% 반등",{"capitulation_low":low20,"rebound_ref":low20*1.382},d))
    # F: near high after strong advance, approaching prior supply
    low90=finite(d.tail(90).Low.min()); rise90=pct(cur,low90); near=(high120-cur)/high120*100 if high120 else 100
    hist=d.iloc[:-60].tail(160); hh=finite(hist.High.max()) if len(hist) else 0
    if rise90>=30 and near<=12 and hh>0 and cur>=hh*0.78:
        dist=(hh-cur)/hh*100; score=min(10,4+rise90/25+(12-near)/6+max(0,10-abs(dist))/8)
        out.append(row_base(code,name,market,"F",score,INFO["F"][2],f"90일 저점 대비 {rise90:.0f}% 상승 · 과거 매물대까지 {dist:+.1f}%",{"recent_high":high120,"historical_supply":hh},d))
    return out


def scan(universe,frames):
    buckets={k:[] for k in LETTERS}
    for _,r in universe.iterrows():
        code=str(r.Code).zfill(6)
        for item in analyze_one(code,str(r.Name),str(r.Market),frames.get(code)):
            buckets[item["type"]].append(item)
    for k in LETTERS:
        buckets[k].sort(key=lambda x:-x["score"]); buckets[k]=buckets[k][:30]
    return buckets


def css(): return r'''
:root{--bg:#030605;--panel:#08110d;--line:#1c4432;--text:#f5fff8;--sub:#8fa399;--green:#00e783}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 85% 0,#082719 0,transparent 28%),var(--bg);color:var(--text);font:14px/1.5 system-ui,"Noto Sans KR",sans-serif}a{color:inherit;text-decoration:none}.wrap{max-width:1500px;margin:auto;padding:22px}.mast{display:flex;justify-content:space-between;align-items:center;gap:20px}.brand{display:flex;align-items:center;gap:13px}.brand img{width:72px;height:72px;object-fit:contain}.brand h1{margin:0;font-size:30px}.brand h1 span{color:var(--green)}.sub{color:var(--sub)}.time{text-align:right;color:var(--sub)}.time b{display:block;color:#eafff2}.nav{display:flex;gap:17px;align-items:center;margin:20px 0;border-bottom:1px solid #183a2b}.nav>a,.drop>summary{padding:12px 3px;border-bottom:2px solid transparent;white-space:nowrap;cursor:pointer;list-style:none}.nav .on{color:var(--green);border-color:var(--green)}.drop{position:relative}.drop summary::-webkit-details-marker{display:none}.drop>div{position:absolute;z-index:20;top:45px;left:0;min-width:160px;padding:7px;border:1px solid var(--line);border-radius:12px;background:#07100c;box-shadow:0 16px 30px #000}.drop:not([open])>div{display:none}.drop div a{display:block;padding:8px 10px;border-radius:8px}.drop div a:hover{background:#0d2118;color:var(--green)}.panel{border:1px solid var(--line);border-radius:18px;background:linear-gradient(145deg,#060c09,#0b1510)}.cockpit{display:grid;grid-template-columns:250px minmax(560px,1fr) 290px;gap:12px}.status{min-height:520px;padding:20px;display:flex;flex-direction:column;justify-content:flex-end}.status img{width:100%;height:245px;object-fit:contain}.status strong{font-size:66px;line-height:1;color:var(--green)}.hero{padding:16px}.hero h2{margin:0}.chart{margin-top:10px;border:1px solid #17392a;border-radius:13px;background:#050a07;overflow:hidden}.chart svg{display:block;width:100%;height:auto}.guide{padding:17px}.stage{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid #1c3329}.stage img{width:30px;height:30px}.stage b{display:block}.stage small{color:var(--sub)}.six{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-top:12px}.type{padding:13px;border:1px solid var(--c);border-radius:15px;background:#06100b}.type strong{font-size:26px;color:var(--c);display:block}.type small{color:var(--sub)}.bottom{display:grid;grid-template-columns:.8fr 1.2fr;gap:12px;margin-top:12px}.summary,.toplist,.intro,.training{padding:18px}.summary img{width:100px;height:100px;object-fit:contain}.toprow{display:grid;grid-template-columns:38px 1fr 65px 65px;gap:8px;padding:9px 0;border-bottom:1px solid #1d352a}.rank{font-size:20px;color:var(--green)}.gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px}.card{border:1px solid #224234;border-radius:15px;background:#07100c;overflow:hidden}.card-head{display:flex;justify-content:space-between;padding:11px 12px 5px}.card-head b{font-size:16px}.tag{padding:3px 8px;border:1px solid var(--c);border-radius:999px;color:var(--c)}.why{padding:9px 12px;border-top:1px solid #1b362a}.why small{display:block;color:var(--sub);margin-top:3px}.star{border:0;background:transparent;color:#ffd166;font-size:22px;cursor:pointer}.history{padding:12px 0;border-bottom:1px solid #1b362a}.flow{padding:14px;border:1px dashed var(--accent);border-radius:12px}.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-top:12px}.step{padding:12px;border:1px solid #294438;border-radius:12px}.step b{display:block;color:var(--accent)}@media(max-width:1100px){.cockpit{grid-template-columns:210px 1fr}.guide{grid-column:1/-1}.six{grid-template-columns:repeat(3,1fr)}.bottom{grid-template-columns:1fr}}@media(max-width:760px){.wrap{padding:12px}.mast{align-items:flex-start}.cockpit{grid-template-columns:1fr}.status{min-height:auto}.status img{height:170px}.guide{grid-column:auto}.six{grid-template-columns:1fr 1fr}.gallery{grid-template-columns:1fr}.nav{overflow-x:auto}.drop>div{position:fixed;top:120px;left:12px}.steps{grid-template-columns:1fr 1fr}}
'''

def nav(active):
    scans=''.join(f'<a href="type_{k.lower()}.html">{k}형</a>' for k in LETTERS)
    trains=''.join(f'<a href="training_{k.lower()}.html">{k}형</a>' for k in LETTERS)
    return f'<nav class="nav"><a class="{"on" if active=="home" else ""}" href="index.html">메인 대시보드</a><details class="drop"><summary>오늘의 전체 스캔 ▾</summary><div><a href="scan.html">전체 보기</a>{scans}</div></details><details class="drop"><summary>훈련소 ▾</summary><div>{trains}</div></details><a class="{"on" if active=="watch" else ""}" href="watchlist.html">관심종목 추적</a><a class="{"on" if active=="history" else ""}" href="history.html">날짜별 기록</a></nav>'

def shell(title,body,active,date,generated):
    js='''<script>function pins(){try{return JSON.parse(localStorage.getItem("ojutamPins")||"[]")}catch(e){return []}}function togglePin(c,b){let p=pins();p=p.includes(c)?p.filter(x=>x!==c):[...p,c];localStorage.setItem("ojutamPins",JSON.stringify(p));if(b)b.textContent=p.includes(c)?"★":"☆"}document.addEventListener("DOMContentLoaded",()=>{let p=pins();document.querySelectorAll(".star").forEach(b=>b.textContent=p.includes(b.dataset.code)?"★":"☆")})</script>'''
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{esc(title)} · 오늘의 주식 탐험대</title><style>{css()}</style></head><body><div class="wrap"><header class="mast"><a class="brand" href="index.html"><img src="../assets/sukdol-stage.webp"><div><h1>오늘의 주식 <span>탐험대</span></h1><p class="sub">한국주식 차트를 탐험하고, 볼 만한 모양을 발견하세요.</p></div></a><div class="time">데이터 기준일<b>{date}</b>최근 업데이트<b>{generated}</b></div></header>{nav(active)}{body}</div>{js}</body></html>'

def chart_svg(rows,width=820,height=390,count=180,levels=None):
    if not rows:return '<div class="sub">차트 데이터 없음</div>'
    rows=rows[-count:]; lo=min(float(r[3]) for r in rows); hi=max(float(r[2]) for r in rows); pad=max((hi-lo)*.06,hi*.002);lo-=pad;hi+=pad
    y=lambda z:12+(hi-z)/max(hi-lo,1e-9)*(height-30); step=width/len(rows); body=max(1.2,step*.58); p=[f'<svg viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" fill="#050a07"/>']
    for label,val in (levels or {}).items():
        if isinstance(val,(int,float)) and lo<=val<=hi:
            yy=y(val);p.append(f'<line x1="0" y1="{yy:.1f}" x2="{width}" y2="{yy:.1f}" stroke="#ffd166" stroke-dasharray="5 4" opacity=".7"/><text x="6" y="{max(11,yy-4):.1f}" fill="#ffd166" font-size="9">{esc(label)}</text>')
    for i,r in enumerate(rows):
        _,o,h,l,c,_=r;o=float(o);h=float(h);l=float(l);c=float(c);x=(i+.5)*step;col="#00e783" if c>=o else "#ff667e";a=min(y(o),y(c));b=max(y(o),y(c));p.append(f'<line x1="{x:.1f}" y1="{y(h):.1f}" x2="{x:.1f}" y2="{y(l):.1f}" stroke="{col}"/><rect x="{x-body/2:.1f}" y="{a:.1f}" width="{body:.1f}" height="{max(1,b-a):.1f}" fill="{col}"/>')
    return ''.join(p)+'</svg>'

def card(r):
    t=r["type"]; color=INFO[t][0]
    return f'<article class="card" style="--c:{color}"><div class="card-head"><div><b>{esc(r["name"])}</b><div class="sub">{r["code"]} · {r["exchange"]} · {r["score"]}점</div></div><div><span class="tag">{t}형</span><button class="star" data-code="{r["code"]}" onclick="togglePin(this.dataset.code,this)">☆</button></div></div><div class="chart">{chart_svg(r["charts"]["day"],620,270,150,r.get("levels"))}</div><div class="why"><b>{esc(r["flow"])}</b><small>{esc(r["reason"])}</small></div></article>'

def generate(universe,buckets,date):
    OUT.mkdir(parents=True,exist_ok=True); now=datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    rows=[x for k in LETTERS for x in buckets[k]]; rows.sort(key=lambda x:-x["score"])
    counts={k:len(buckets[k]) for k in LETTERS}; total=len(rows)
    rep=rows[0] if rows else None
    guide=''.join(f'<div class="stage"><img src="../assets/{"sukdol-key-caution.webp" if k in "EF" else "sukdol-key-up.webp"}"><span><b>{k}형 · {INFO[k][1]}</b><small>{INFO[k][2]}</small></span></div>' for k in LETTERS)
    hero=(f'<article class="panel hero"><h2>대표 일봉 · {esc(rep["name"])}</h2><div class="sub">{rep["code"]} · {rep["type"]}형 · {esc(rep["flow"])}</div><div class="chart">{chart_svg(rep["charts"]["day"],820,390,180,rep.get("levels"))}</div><p class="sub">기본 자동 스캔은 일봉만 사용해. 진입판정이 아니라 볼 차트를 골라주는 탐색 화면이야.</p></article>' if rep else '<article class="panel hero">후보 없음</article>')
    status=f'<article class="panel status"><span class="sub">오늘의 탐색 상태</span><strong>{total}</strong><h2>개 차트 후보 발견</h2><p class="sub">KRX {len(universe)}종목을 일봉으로 훑었어.</p><img src="../assets/sukdol-plain-up.webp"></article>'
    types=''.join(f'<a class="type" style="--c:{INFO[k][0]}" href="type_{k.lower()}.html"><strong>{k} · {counts[k]}</strong><b>{INFO[k][1]}</b><small>{INFO[k][2]}</small></a>' for k in LETTERS)
    top=''.join(f'<div class="toprow"><span class="rank">{i}</span><span><b>{esc(r["name"])}</b><small class="sub"> {r["code"]}</small></span><b>{r["type"]}형</b><b>{r["score"]}점</b></div>' for i,r in enumerate(rows[:5],1))
    home=f'<main><section class="cockpit">{status}{hero}<aside class="panel guide"><h2>A~F 차트 모양</h2>{guide}</aside></section><section class="six">{types}</section><section class="bottom"><article class="panel summary"><h2>▱ 오늘 탐색 요약</h2><ul><li>전체 스캔 대상 <b>{len(universe)}종목</b></li><li>발견 후보 <b>{total}개</b></li><li>기준 시간봉 <b>일봉 1D</b></li><li>분봉 <b>기본 스캔에서 사용 안 함</b></li></ul><div style="display:flex;gap:16px;align-items:center"><img src="../assets/sukdol-caution.webp"><p class="sub">점수보다 차트 모양을 먼저 봐. 유형 페이지에서 일봉을 쭉 훑는 게 오주탐의 핵심이야.</p></div></article><article class="panel toplist"><h2>오늘 먼저 볼 차트</h2>{top}</article></section></main>'
    (OUT/"index.html").write_text(shell("메인 대시보드",home,"home",date,now),encoding="utf-8")
    # gallery pages
    def gallery_page(title,items,active):
        body=f'<section class="panel intro"><h2>{esc(title)}</h2><p class="sub">일봉 차트 모양을 빠르게 눈으로 확인해.</p></section><section class="gallery">'+''.join(card(r) for r in items)+'</section>'
        return shell(title,body,active,date,now)
    (OUT/"scan.html").write_text(gallery_page("오늘의 전체 스캔",rows,"scan"),encoding="utf-8")
    for k in LETTERS:(OUT/f"type_{k.lower()}.html").write_text(gallery_page(f"{k}형 · {INFO[k][1]}",buckets[k],k),encoding="utf-8")
    # watchlist: embeds rows and renders matching cards client-side
    data=json.dumps(rows,ensure_ascii=False).replace('</','<\\/')
    watch=f'<section class="panel intro"><h2>관심종목 추적</h2><p class="sub">별표한 차트를 다시 모아보는 곳.</p></section><div id="watch" class="gallery"></div><script>const rows={data};function renderWatch(){{let p=pins();watch.innerHTML=rows.filter(r=>p.includes(r.code)).map(r=>`<article class="card"><div class="card-head"><b>${{r.name}}</b><span class="tag">${{r.type}}형</span></div><div class="why">${{r.flow}}<small>${{r.reason}}</small></div></article>`).join("")||`<div class="panel intro">별표한 종목이 아직 없어.</div>`}}document.addEventListener("DOMContentLoaded",renderWatch)</script>'
    (OUT/"watchlist.html").write_text(shell("관심종목",watch,"watch",date,now),encoding="utf-8")
    # history
    try: hist=json.loads(HISTORY.read_text(encoding="utf-8"))
    except Exception:hist=[]
    snap={"date":date,"snapshot_at":now,"counts":counts,"candidate_count":total};hist=[x for x in hist if x.get("date")!=date]+[snap];hist=hist[-60:];HISTORY.parent.mkdir(parents=True,exist_ok=True);HISTORY.write_text(json.dumps(hist,ensure_ascii=False,indent=2),encoding="utf-8")
    hbody='<section class="panel intro"><h2>날짜별 기록</h2><p class="sub">그날 어떤 차트 모양이 얼마나 잡혔는지 확인.</p>'+''.join(f'<div class="history"><b>{x["date"]}</b> · '+" / ".join(f'{k}:{x["counts"].get(k,0)}' for k in LETTERS)+f' · 총 {x["candidate_count"]}개</div>' for x in reversed(hist))+'</section>'
    (OUT/"history.html").write_text(shell("날짜별 기록",hbody,"history",date,now),encoding="utf-8")
    # training A-F
    steps={
      "A":["강한 상승 확인","첫 눌림 확인","지지 구간 확인","전고점 재도전 관찰"],"B":["장기 하락","바닥 횡보","하단 회복","박스 내부 반응"],"C":["박스 형성","상단 반복 접촉","상단 돌파","재지지 여부"],"D":["장기 하락","바닥 압축","매물대 재탈환","확장 준비"],"E":["급락·투매","핵심 저점","반등 시작","기술적 반등"],"F":["고점권 상승","과거 횡보대 접근","매물 소화","돌파/거절 관찰"]}
    for k in LETTERS:
        sb=''.join(f'<div class="step"><b>{i}</b>{esc(s)}</div>' for i,s in enumerate(steps[k],1)); sample=buckets[k][0] if buckets[k] else None; sample_html=(f'<div class="chart">{chart_svg(sample["charts"]["day"],900,400,180,sample.get("levels"))}</div><p>{esc(sample["reason"])}</p>' if sample else '<p class="sub">오늘은 이 유형 후보가 없어.</p>')
        body=f'<section class="panel training" style="--accent:{INFO[k][0]}"><img src="../assets/sukdol-stage.webp" style="width:90px;float:right"><h2>{k}형 훈련소 · {INFO[k][1]}</h2><div class="flow">{INFO[k][2]}</div><div class="steps">{sb}</div><h3>오늘 실제 예시</h3>{sample_html}</section>'
        (OUT/f"training_{k.lower()}.html").write_text(shell(f"{k}형 훈련소",body,"training",date,now),encoding="utf-8")
    (OUT/"latest.json").write_text(json.dumps({"market_date":date,"generated_at":now,"counts":counts,"universe_count":len(universe),"candidates":rows},ensure_ascii=False),encoding="utf-8")
    print("OJUTAM",date,len(universe),counts,total)


def main():
    universe,frames,date=load_marcap(); buckets=scan(universe,frames); generate(universe,buckets,date)

if __name__=="__main__": main()
