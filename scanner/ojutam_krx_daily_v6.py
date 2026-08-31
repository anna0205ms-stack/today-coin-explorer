from __future__ import annotations
from pathlib import Path
import json,re
import pandas as pd
import yfinance as yf
import ojutam_krx_daily as app
import ojutam_krx_daily_v3 as data
import ojutam_krx_daily_v4 as v4

app.load_marcap=data.load_latest


def rows(df):
    if df is None or df.empty:return []
    if isinstance(df.columns,pd.MultiIndex):df.columns=[c[0] for c in df.columns]
    out=[]
    for idx,r in df.dropna(subset=['Open','High','Low','Close']).iterrows():
        ts=pd.Timestamp(idx)
        t=int(ts.timestamp()) if ts.hour or ts.minute else ts.strftime('%Y-%m-%d')
        out.append({'time':t,'open':float(r.Open),'high':float(r.High),'low':float(r.Low),'close':float(r.Close)})
    return out


def levels(rs):
    q=rs[-80:]
    if not q:return {}
    hs=sorted(x['high'] for x in q);ls=sorted(x['low'] for x in q);n=len(q)
    hi=hs[round((n-1)*.90)];lo=ls[round((n-1)*.10)]
    return {'high':hi,'center':(hi+lo)/2,'low':lo}


def dl(symbol,interval,period):
    try:return rows(yf.download(symbol,interval=interval,period=period,progress=False,auto_adjust=False,threads=False))
    except Exception as e:print('tf',symbol,interval,e);return []


def tf(symbol):
    m15=dl(symbol,'15m','60d');h1=dl(symbol,'60m','730d');d1=dl(symbol,'1d','2y');w1=dl(symbol,'1wk','10y');h4=[]
    if h1:
        f=pd.DataFrame(h1);f['dt']=pd.to_datetime(f['time'],unit='s');f=f.set_index('dt')
        z=f.resample('4h').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
        h4=[{'time':int(i.timestamp()),'open':float(r.open),'high':float(r.high),'low':float(r.low),'close':float(r.close)} for i,r in z.iterrows()]
    return {k:{'rows':r[-500:],'levels':levels(r)} for k,r in [('15',m15),('60',h1),('240',h4),('D',d1),('W',w1)]}


def patch_index():
    p=Path('outputs/ojutam/index.html');text=p.read_text(encoding='utf-8')
    text=re.sub(r'(<h3>KOSPI</h3><small>).*?(</small>)',r'\1유가증권시장\2<div class="idx-periods" data-index="kospi"><button data-i="15">15m</button><button data-i="60">1h</button><button data-i="240">4h</button><button class="active" data-i="D">1D</button><button data-i="W">1W</button></div>',text,count=1)
    text=re.sub(r'(<h3>KOSDAQ</h3><small>).*?(</small>)',r'\1코스닥시장\2<div class="idx-periods" data-index="kosdaq"><button data-i="15">15m</button><button data-i="60">1h</button><button data-i="240">4h</button><button class="active" data-i="D">1D</button><button data-i="W">1W</button></div>',text,count=1)
    css='<style>.idx-periods{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}.idx-periods button{border:1px solid #315543;border-radius:7px;background:#07100c;color:#9fb4a9;padding:5px 8px;cursor:pointer}.idx-periods button.active{background:#00e783;color:#021009;border-color:#00e783;font-weight:800}</style>'
    text=text.replace('</head>',css+'</head>',1).replace('</body>','<script src="index_v6.js"></script></body>',1)
    p.write_text(text,encoding='utf-8')
    Path('outputs/ojutam/index_timeframes.json').write_text(json.dumps({'kospi':tf('^KS11'),'kosdaq':tf('^KQ11')},ensure_ascii=False),encoding='utf-8')


def scan_page(universe,buckets,date):
    now=app.datetime.now(app.KST).strftime('%Y-%m-%d %H:%M')
    data={'market_date':date,'generated_at':now,'universe_count':len(universe),'counts':{k:len(buckets[k]) for k in app.LETTERS},'candidates':[r for k in app.LETTERS for r in buckets[k]]}
    Path('outputs/ojutam/scan_data.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    body='''<style>.system-bar{padding:9px 14px;border:1px solid #173829;border-radius:11px;background:#06100b;color:var(--sub);margin-bottom:18px}.scan-summary{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:15px 0}.sum{padding:13px;border:1px solid var(--c);border-radius:14px;background:#06100b;color:inherit;text-align:left}.sum strong{display:block;font-size:22px;color:var(--c)}.tabs{display:flex;gap:7px;overflow-x:auto;margin-bottom:10px}.tab{border:1px solid #274638;border-radius:999px;background:#07100c;color:#b6c9c0;padding:7px 13px}.tab.on{background:var(--green);color:#021009}.table-wrap{overflow:auto;border:1px solid #1d3b2d;border-radius:15px}.scan-table{width:100%;border-collapse:collapse;min-width:1000px}.scan-table th,.scan-table td{padding:11px;border-bottom:1px solid #173226;text-align:left}.scan-table tr[data-code]{cursor:pointer}.scan-table tr[data-code]:hover{background:#0a1912}.badge{border:1px solid var(--c);color:var(--c);border-radius:999px;padding:3px 7px}.modal{position:fixed;inset:0;z-index:1000;background:#000b;display:none;align-items:center;justify-content:center;padding:16px}.modal.open{display:flex}.modal-card{width:min(1100px,100%);max-height:92vh;overflow:auto;background:#06100b;border:1px solid #28513d;border-radius:18px;padding:16px}.modal-head{display:flex;justify-content:space-between}.modal-chart{height:520px;margin-top:10px;border:1px solid #17392a;border-radius:12px;overflow:hidden}.close{border:1px solid #315543;background:#07100c;color:#fff;border-radius:9px;padding:7px 11px}@media(max-width:760px){.scan-summary{grid-template-columns:1fr 1fr}.modal-chart{height:380px}}</style><div class="system-bar">KRX 일봉 스캐너 정상 · 분봉 미사용 · <b>종목을 누르면 차트 상세</b></div><section class="panel intro"><h2>전체 스캔 결과</h2><p class="sub">A~F 유형 필터 → 종목 클릭 → 일봉 차트와 핵심구간 확인</p></section><section id="scanSummary" class="scan-summary"></section><div id="scanTabs" class="tabs"></div><div class="table-wrap"><table class="scan-table"><thead><tr><th>종목</th><th>유형</th><th>점수</th><th>흐름</th><th>한줄정리</th><th>관심</th></tr></thead><tbody id="scanBody"></tbody></table></div><div id="detailModal" class="modal"><div class="modal-card"><div class="modal-head"><div><h2 id="detailTitle"></h2><div id="detailMeta" class="sub"></div></div><button id="detailClose" class="close">닫기</button></div><div id="detailChart" class="modal-chart"></div><p id="detailReason" class="sub"></p></div></div><script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script><script src="scan_v6.js"></script>'''
    Path('outputs/ojutam/scan.html').write_text(app.shell('전체 스캔 결과',body,'scan',date,now),encoding='utf-8')


def generate(universe,buckets,date):
    v4.generate_v4(universe,buckets,date);patch_index();scan_page(universe,buckets,date)

app.generate=generate
if __name__=='__main__':app.main()
