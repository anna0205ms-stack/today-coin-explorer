from __future__ import annotations

from pathlib import Path
import json
import re

import pandas as pd
import yfinance as yf

import ojutam_krx_daily as app
import ojutam_krx_daily_v3 as data
import ojutam_krx_daily_v4 as v4

app.load_marcap = data.load_latest


def _rows_from_df(df):
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    out=[]
    for idx,row in df.dropna(subset=['Open','High','Low','Close']).iterrows():
        ts = idx.tz_localize(None) if getattr(idx, 'tzinfo', None) else idx
        if getattr(ts, 'hour', 0) or getattr(ts, 'minute', 0):
            t = int(pd.Timestamp(ts).timestamp())
        else:
            t = pd.Timestamp(ts).strftime('%Y-%m-%d')
        out.append({'time':t,'open':float(row.Open),'high':float(row.High),'low':float(row.Low),'close':float(row.Close)})
    return out


def _levels(candles, lookback=80):
    q=candles[-lookback:] if len(candles)>lookback else candles
    if not q:return {}
    highs=sorted(float(r['high']) for r in q); lows=sorted(float(r['low']) for r in q); n=len(q)
    hi=highs[max(0,min(n-1,round((n-1)*.90)))]; lo=lows[max(0,min(n-1,round((n-1)*.10)))]
    if hi<=lo: hi=max(highs);lo=min(lows)
    return {'high':hi,'center':(hi+lo)/2,'low':lo}


def _download(symbol, interval, period):
    try:
        df=yf.download(symbol,interval=interval,period=period,progress=False,auto_adjust=False,threads=False)
        return _rows_from_df(df)
    except Exception as e:
        print('index tf fetch',symbol,interval,e); return []


def index_timeframes(symbol):
    m15=_download(symbol,'15m','60d')
    h1=_download(symbol,'60m','730d')
    d1=_download(symbol,'1d','2y')
    w1=_download(symbol,'1wk','10y')
    h4=[]
    if h1:
        df=pd.DataFrame(h1)
        df['dt']=pd.to_datetime(df['time'],unit='s')
        df=df.set_index('dt')
        rs=df.resample('4h').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
        h4=[{'time':int(idx.timestamp()),'open':float(r.open),'high':float(r.high),'low':float(r.low),'close':float(r.close)} for idx,r in rs.iterrows()]
    out={}
    for key,rows in [('15',m15),('60',h1),('240',h4),('D',d1),('W',w1)]:
        close=rows[-1]['close'] if rows else None; prev=rows[-2]['close'] if len(rows)>1 else close
        out[key]={'rows':rows[-500:],'levels':_levels(rows),'price':close,'change':((close/prev)-1)*100 if close is not None and prev else None}
    return out


def patch_dashboard_timeframes():
    path=Path('outputs/ojutam/index.html')
    if not path.exists(): return
    kospi=index_timeframes('^KS11'); kosdaq=index_timeframes('^KQ11')
    payload=json.dumps({'kospi':kospi,'kosdaq':kosdaq},ensure_ascii=False).replace('</','<\\/')
    text=path.read_text(encoding='utf-8')
    # Add period controls inside each index header.
    text=re.sub(r'(<h3>KOSPI</h3><small>)(.*?)(</small>)',r'\1유가증권시장\3<div class="idx-periods" data-index="kospi"><button data-i="15">15m</button><button data-i="60">1h</button><button data-i="240">4h</button><button class="active" data-i="D">1D</button><button data-i="W">1W</button></div>',text,count=1)
    text=re.sub(r'(<h3>KOSDAQ</h3><small>)(.*?)(</small>)',r'\1코스닥시장\3<div class="idx-periods" data-index="kosdaq"><button data-i="15">15m</button><button data-i="60">1h</button><button data-i="240">4h</button><button class="active" data-i="D">1D</button><button data-i="W">1W</button></div>',text,count=1)
    css='''<style>.idx-periods{display:flex;gap:5px;margin-top:6px;flex-wrap:wrap}.idx-periods button{border:1px solid #315543;border-radius:7px;background:#07100c;color:#9fb4a9;padding:4px 7px;cursor:pointer}.idx-periods button.active{background:#00e783;color:#021009;border-color:#00e783;font-weight:800}@media(max-width:760px){.idx-periods button{min-height:34px}}</style>'''
    text=text.replace('</head>',css+'</head>',1)
    # Remove v4 inline index chart script; replace with timeframe-aware renderer.
    text=re.sub(r'<script src="https://unpkg.com/lightweight-charts@4\.2\.3/dist/lightweight-charts\.standalone\.production\.js"></script><script>\(\(\)=>\{const marketData=.*?</script>','',text,flags=re.S)
    js=f'''<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script><script>(()=>{{const marketData={payload};const inst={{}};let boxVisible=true;function draw(name,interval='D'){{const id=name==='kospi'?'kospiChart':'kosdaqChart',el=document.getElementById(id),p=marketData[name]?.[interval];if(!el||!p?.rows?.length||!window.LightweightCharts)return;if(inst[name]?.ro)inst[name].ro.disconnect();el.innerHTML='';const chart=LightweightCharts.createChart(el,{{width:el.clientWidth,height:el.clientHeight,layout:{{background:{{type:'solid',color:'#020609'}},textColor:'#91a9b7'},grid:{{vertLines:{{color:'#17252e'}},horzLines:{{color:'#17252e'}}}},rightPriceScale:{{borderColor:'#29404d',autoScale:true}},timeScale:{{borderColor:'#29404d',timeVisible:interval!=='D'&&interval!=='W',rightOffset:8,barSpacing:7,minBarSpacing:2}},crosshair:{{mode:LightweightCharts.CrosshairMode.Normal}},handleScale:{{axisPressedMouseMove:{{time:true,price:true}},mouseWheel:true,pinch:true}},handleScroll:{{pressedMouseMove:true,mouseWheel:true,horzTouchDrag:true,vertTouchDrag:true}},kineticScroll:{{mouse:true,touch:true}}}});const series=chart.addCandlestickSeries({{upColor:'#20dfa4',downColor:'#ff514c',borderUpColor:'#20dfa4',borderDownColor:'#ff514c',wickUpColor:'#20dfa4',wickDownColor:'#ff514c',priceLineVisible:true,lastValueVisible:true}});series.setData(p.rows);const lines=[];function redraw(){{lines.splice(0).forEach(x=>series.removePriceLine(x));if(!boxVisible)return;[['high','상단','#ff6259'],['center','중심','#26dca1'],['low','하단','#63a0f2']].forEach(([k,t,c])=>{{const price=p.levels?.[k];if(typeof price==='number')lines.push(series.createPriceLine({{price,color:c,lineWidth:2,axisLabelVisible:true,title:`${{t}} ${{price.toLocaleString(undefined,{{maximumFractionDigits:2}})}}`}}))}})}}redraw();chart.timeScale().fitContent();const ro=new ResizeObserver(()=>chart.resize(el.clientWidth,el.clientHeight));ro.observe(el);inst[name]={{chart,series,redraw,ro}}}}document.querySelectorAll('.idx-periods').forEach(g=>g.addEventListener('click',e=>{{const b=e.target.closest('button[data-i]');if(!b)return;g.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));draw(g.dataset.index,b.dataset.i)}}));draw('kospi','D');draw('kosdaq','D');document.getElementById('krxAutoFit')?.addEventListener('click',()=>Object.values(inst).forEach(x=>{{x.chart.timeScale().fitContent();x.chart.priceScale('right').applyOptions({{autoScale:true}})}}));document.getElementById('krxBoxToggle')?.addEventListener('click',e=>{{boxVisible=!boxVisible;e.currentTarget.textContent=`박스선 ${{boxVisible?'ON':'OFF'}}`;Object.values(inst).forEach(x=>x.redraw())}})}})();</script>'''
    text=text.replace('</body>',js+'</body>',1)
    path.write_text(text,encoding='utf-8')


def render_scan_table_with_modal(buckets,date):
    rows=[r for k in app.LETTERS for r in buckets[k]]
    latest={'market_date':date,'generated_at':app.datetime.now(app.KST).isoformat(),'universe_count':None,'counts':{k:len(buckets[k]) for k in app.LETTERS},'candidates':rows}
    data_json=json.dumps(latest,ensure_ascii=False).replace('</','<\\/')
    now=app.datetime.now(app.KST).strftime('%Y-%m-%d %H:%M')
    body='''<style>.system-bar{margin:0 0 18px;padding:9px 14px;border:1px solid #173829;border-radius:11px;background:#06100b;display:flex;justify-content:space-between;color:var(--sub)}.scan-summary{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:16px}.sum{padding:13px;border:1px solid var(--c);border-radius:14px;background:#06100b;color:inherit;text-align:left}.sum strong{display:block;font-size:22px;color:var(--c)}.tabs{display:flex;gap:7px;overflow-x:auto;margin-bottom:10px}.tab{border:1px solid #274638;border-radius:999px;background:#07100c;color:#b6c9c0;padding:7px 13px}.tab.on{background:var(--green);color:#021009}.table-wrap{overflow:auto;border:1px solid #1d3b2d;border-radius:15px}.scan-table{width:100%;border-collapse:collapse;min-width:1050px}.scan-table th,.scan-table td{padding:11px;border-bottom:1px solid #173226;text-align:left}.scan-table th{color:var(--sub)}.scan-table tr[data-code]{cursor:pointer}.scan-table tr[data-code]:hover{background:#0a1912}.badge{border:1px solid var(--c);color:var(--c);border-radius:999px;padding:3px 7px}.modal{position:fixed;inset:0;z-index:1000;background:#000b;display:none;align-items:center;justify-content:center;padding:20px}.modal.open{display:flex}.modal-card{width:min(1100px,100%);max-height:92vh;overflow:auto;background:#06100b;border:1px solid #28513d;border-radius:18px;padding:16px}.modal-head{display:flex;justify-content:space-between;gap:10px}.modal-chart{height:520px;margin-top:10px;border:1px solid #17392a;border-radius:12px;overflow:hidden}.close{border:1px solid #315543;background:#07100c;color:#fff;border-radius:9px;padding:7px 11px}.detail-meta{display:flex;gap:12px;flex-wrap:wrap;color:var(--sub);margin-top:6px}@media(max-width:760px){.scan-summary{grid-template-columns:1fr 1fr}.modal{padding:8px}.modal-card{padding:12px}.modal-chart{height:380px}}</style><div class="system-bar"><b>KRX 일봉 스캐너 정상 · 분봉 미사용</b><span>종목을 누르면 차트 상세가 열려.</span></div><section class="panel intro"><h2>전체 스캔 결과</h2><p class="sub">A~F 유형으로 빠르게 필터하고, 종목 행을 눌러 일봉 차트와 핵심구간을 확인해.</p></section><section id="scanSummary" class="scan-summary"></section><div id="scanTabs" class="tabs"></div><div class="table-wrap"><table class="scan-table"><thead><tr><th>종목</th><th>유형</th><th>점수</th><th>흐름</th><th>한줄정리</th><th>관심</th></tr></thead><tbody id="scanBody"></tbody></table></div><div id="detailModal" class="modal" role="dialog" aria-modal="true"><div class="modal-card"><div class="modal-head"><div><h2 id="detailTitle" style="margin:0"></h2><div id="detailMeta" class="detail-meta"></div></div><button id="detailClose" class="close" type="button">닫기</button></div><div id="detailChart" class="modal-chart"></div><div id="detailReason" class="detail-meta"></div></div></div><script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script><script>const DATA='''+data_json+''',INFO={A:['#ff8297','급등 후 첫 눌림'],B:['#70c2ff','바닥·박스 하단 반등'],C:['#c3a7ff','박스 상단 돌파'],D:['#5ce2b3','재탈환·압축'],E:['#ffb454','급락 후 기술적 반등'],F:['#56d6ff','고점권·과거 매물대']};let filter='ALL',detailChart=null,detailRo=null;function pins(){try{return JSON.parse(localStorage.getItem('ojutamPins')||'[]')}catch(e){return[]}}function toggle(c,b,e){e.stopPropagation();let p=pins();p=p.includes(c)?p.filter(x=>x!==c):[...p,c];localStorage.setItem('ojutamPins',JSON.stringify(p));b.textContent=p.includes(c)?'★':'☆'}function render(){scanSummary.innerHTML='ABCDEF'.split('').map(k=>`<button class="sum" style="--c:${INFO[k][0]}" onclick="setFilter('${k}')"><strong>${k} · ${DATA.counts[k]||0}</strong>${INFO[k][1]}</button>`).join('');scanTabs.innerHTML=['ALL',...'ABCDEF'].map(k=>`<button class="tab ${filter===k?'on':''}" onclick="setFilter('${k}')">${k==='ALL'?'ALL '+DATA.candidates.length:k+'형 '+(DATA.counts[k]||0)}</button>`).join('');const p=pins();scanBody.innerHTML=DATA.candidates.filter(r=>filter==='ALL'||r.type===filter).map(r=>`<tr data-code="${r.market}" onclick="openDetail('${r.market}','${r.type}')"><td><b>${r.name}</b><div class="sub">${r.market} · ${r.exchange}</div></td><td><span class="badge" style="--c:${INFO[r.type][0]}">${r.type}형</span></td><td>${r.score??'-'}</td><td>${r.flow||'-'}</td><td class="sub">${r.reason||'-'}</td><td><button class="star" onclick="toggle('${r.market}',this,event)">${p.includes(r.market)?'★':'☆'}</button></td></tr>`).join('')}function setFilter(k){filter=k;render()}function openDetail(code,type){const r=DATA.candidates.find(x=>x.market===code&&x.type===type)||DATA.candidates.find(x=>x.market===code);if(!r)return;detailTitle.textContent=`${r.name} · ${r.type}형`;detailMeta.innerHTML=`<span>${r.market} · ${r.exchange}</span><span>점수 ${r.score??'-'}</span><span>${r.flow||''}</span>`;detailReason.textContent=r.reason||'';detailModal.classList.add('open');if(detailRo)detailRo.disconnect();detailChart?.remove?.();detailChart=null;const el=detailChartEl=document.getElementById('detailChart');el.innerHTML='';const rows=(r.charts?.day||[]).map(x=>({time:String(x[0]).slice(0,10),open:+x[1],high:+x[2],low:+x[3],close:+x[4]}));if(!rows.length){el.innerHTML='<div class="sub" style="padding:30px">일봉 데이터 없음</div>';return}detailChart=LightweightCharts.createChart(el,{width:el.clientWidth,height:el.clientHeight,layout:{background:{type:'solid',color:'#020609'},textColor:'#91a9b7'},grid:{vertLines:{color:'#17252e'},horzLines:{color:'#17252e'}},rightPriceScale:{borderColor:'#29404d'},timeScale:{borderColor:'#29404d',rightOffset:8,barSpacing:7},handleScale:{mouseWheel:true,pinch:true},handleScroll:{pressedMouseMove:true,mouseWheel:true,horzTouchDrag:true}});const s=detailChart.addCandlestickSeries({upColor:'#20dfa4',downColor:'#ff514c',borderUpColor:'#20dfa4',borderDownColor:'#ff514c',wickUpColor:'#20dfa4',wickDownColor:'#ff514c'});s.setData(rows);Object.entries(r.levels||{}).filter(([,v])=>typeof v==='number').slice(0,4).forEach(([k,v])=>s.createPriceLine({price:v,color:'#ffd166',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title:k.replaceAll('_',' ')}));detailChart.timeScale().fitContent();detailRo=new ResizeObserver(()=>detailChart.resize(el.clientWidth,el.clientHeight));detailRo.observe(el)}detailClose.onclick=()=>detailModal.classList.remove('open');detailModal.onclick=e=>{if(e.target===detailModal)detailModal.classList.remove('open')};render();</script>'''
    Path('outputs/ojutam/scan.html').write_text(app.shell('전체 스캔 결과',body,'scan',date,now),encoding='utf-8')


def generate_v5(universe,buckets,date):
    v4.generate_v4(universe,buckets,date)
    patch_dashboard_timeframes()
    render_scan_table_with_modal(buckets,date)

app.generate=generate_v5

if __name__=='__main__':
    app.main()
