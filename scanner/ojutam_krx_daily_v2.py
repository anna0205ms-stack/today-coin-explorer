from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import json
import re
import requests
import pandas as pd
import ojutam_krx_daily as app


def load_marcap_fixed():
    frames=[]
    current=date.today().year
    for year in (current-2,current-1,current):
        loaded=False
        for ext in ("parquet","csv.gz"):
            url=f"https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.{ext}"
            try:
                if ext=="parquet":
                    x=pd.read_parquet(url)
                else:
                    x=pd.read_csv(url,dtype={"Code":str},compression="gzip",low_memory=False)
                x["Date"]=pd.to_datetime(x["Date"])
                frames.append(x);loaded=True
                print("marcap",year,ext,len(x));break
            except Exception as e:
                print("marcap fallback",year,ext,e)
        if not loaded and year>=current-1:
            raise RuntimeError(f"marcap {year} unavailable")
    allx=pd.concat(frames,ignore_index=True).sort_values(["Code","Date"])
    last_date=allx["Date"].max()
    latest=allx[allx["Date"]==last_date].copy()
    latest["Code"]=latest["Code"].astype(str).str.extract(r"(\d+)",expand=False).str.zfill(6)
    latest["Market"]=latest["Market"].astype(str).str.upper()
    latest.loc[latest["Market"].str.startswith("KOSPI",na=False),"Market"]="KOSPI"
    latest.loc[latest["Market"].str.startswith("KOSDAQ",na=False),"Market"]="KOSDAQ"
    for col in ("Marcap","Amount"):
        latest[col]=pd.to_numeric(latest[col],errors="coerce").fillna(0)
    latest=latest[latest["Market"].isin(["KOSPI","KOSDAQ"])]
    latest=latest[(latest["Marcap"]>=300_000_000_000)&(latest["Amount"]>=3_000_000_000)]
    latest=latest[~latest["Name"].astype(str).str.contains(r"스팩|SPAC|리츠|REIT|ETF|ETN|인프라|선물|인버스|레버리지|우$|우B$|우C$|우선주",case=False,regex=True,na=False)]
    latest=latest.drop_duplicates("Code").reset_index(drop=True)
    codes=set(latest["Code"])
    allx["Code"]=allx["Code"].astype(str).str.extract(r"(\d+)",expand=False).str.zfill(6)
    allx=allx[allx["Code"].isin(codes)].copy()
    for col in ("Open","High","Low","Close","Volume","Amount"):
        allx[col]=pd.to_numeric(allx[col],errors="coerce")
    frames_by_code={}
    for code,g in allx.groupby("Code"):
        q=g.set_index("Date")[["Open","High","Low","Close","Volume","Amount"]].sort_index().dropna(subset=["Open","High","Low","Close"])
        q=q[~q.index.duplicated(keep="last")]
        frames_by_code[code]=q
    return latest,frames_by_code,last_date.date().isoformat()


def fetch_index(symbol: str, count: int = 150):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol, safe='')}?range=1y&interval=1d&events=history"
    r=requests.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    result=r.json()["chart"]["result"][0]
    ts=result.get("timestamp") or []
    q=result["indicators"]["quote"][0]
    rows=[]
    for i,t in enumerate(ts):
        vals=[q.get(k,[None]*len(ts))[i] for k in ("open","high","low","close")]
        if any(v is None for v in vals): continue
        rows.append((datetime.fromtimestamp(t).strftime("%Y-%m-%d"),*map(float,vals)))
    return rows[-count:]


def index_svg(rows,width=820,height=220):
    if not rows:return '<div class="sub">지수 데이터 없음</div>'
    lows=[r[3] for r in rows]; highs=[r[2] for r in rows]
    lo=min(lows); hi=max(highs); pad=max((hi-lo)*.06,1);lo-=pad;hi+=pad
    y=lambda v: 10+(hi-v)/max(hi-lo,1e-9)*(height-24)
    step=width/len(rows); body=max(1.5,step*.58)
    p=[f'<svg viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" fill="#050a07"/>']
    for i,(_,o,h,l,c) in enumerate(rows):
        x=(i+.5)*step; col="#00e783" if c>=o else "#ff667e"; a=min(y(o),y(c)); b=max(y(o),y(c))
        p.append(f'<line x1="{x:.1f}" y1="{y(h):.1f}" x2="{x:.1f}" y2="{y(l):.1f}" stroke="{col}"/><rect x="{x-body/2:.1f}" y="{a:.1f}" width="{body:.1f}" height="{max(1,b-a):.1f}" fill="{col}"/>')
    p.append('</svg>');return ''.join(p)


def patch_market_indices():
    path=Path("outputs/ojutam/index.html")
    if not path.exists(): return
    try: kospi=fetch_index("^KS11")
    except Exception as e: print("KOSPI index",e); kospi=[]
    try: kosdaq=fetch_index("^KQ11")
    except Exception as e: print("KOSDAQ index",e); kosdaq=[]
    def facts(rows):
        if not rows:return ("-","-")
        close=rows[-1][4]; prev=rows[-2][4] if len(rows)>1 else close
        pct=(close/prev-1)*100 if prev else 0
        return (f"{close:,.2f}",f"{pct:+.2f}%")
    kp,kpc=facts(kospi); kd,kdc=facts(kosdaq)
    block=f'''<article class="panel hero market-indices"><div class="heading"><div><h2>한국 시장 기준 차트</h2><div class="sub">오코탐의 BTC 기준 차트 자리를 KOSPI · KOSDAQ으로 바꿨어.</div></div></div><section class="index-chart"><div class="index-head"><div><h3>KOSPI</h3><small>유가증권시장</small></div><div><b>{kp}</b><span>{kpc}</span></div></div><div class="chart">{index_svg(kospi)}</div></section><section class="index-chart"><div class="index-head"><div><h3>KOSDAQ</h3><small>코스닥시장</small></div><div><b>{kd}</b><span>{kdc}</span></div></div><div class="chart">{index_svg(kosdaq)}</div></section><p class="sub">시장 전체 흐름을 먼저 보고, 아래 A~F 후보 차트를 훑는 구조야.</p></article>'''
    text=path.read_text(encoding="utf-8")
    text=re.sub(r'<article class="panel hero">.*?</article>',block,text,count=1,flags=re.S)
    extra='''<style>.market-indices{display:flex;flex-direction:column;gap:10px}.index-chart{border:1px solid #17392a;border-radius:13px;padding:10px;background:#060d09}.index-head{display:flex;justify-content:space-between;align-items:end;gap:10px}.index-head h3{margin:0;font-size:18px}.index-head small{color:var(--sub)}.index-head>div:last-child{text-align:right}.index-head b{display:block;font-size:18px}.index-head span{color:#a7b8af;font-size:12px}.index-chart .chart{margin-top:7px}@media(max-width:760px){.index-chart .chart{overflow-x:auto}.index-chart svg{min-width:620px}}</style>'''
    text=text.replace('</head>',extra+'</head>',1)
    path.write_text(text,encoding="utf-8")


app.load_marcap=load_marcap_fixed

if __name__=="__main__":
    app.main()
    patch_market_indices()
