from __future__ import annotations
import json, math, re, time, shutil
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import plotly.graph_objects as go

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'ready_backtest_results'; OUT.mkdir(exist_ok=True)
START=pd.Timestamp('2025-09-09'); END=pd.Timestamp('2026-09-09')
MIN_MARCAP=300_000_000_000; KRX_MIN_AMOUNT=3_000_000_000; UPBIT_MIN_AMOUNT=500_000_000
EXCLUDE_PATTERN=r'스팩|우$|우B$|우C$|리츠$|ETF|ETN|인프라|선물|인버스|레버리지'
SURGE_LOOKBACK=60; SURGE_MIN_PCT=20.0; PULLBACK_MIN_PCT=12.0; PULLBACK_MAX_PCT=45.0
BASE_DAYS=3; BASE_LOW_SPREAD_MAX_PCT=5.0; DRY_VOLUME_RATIO_MAX=0.80
READY_VOLUME_RATIO_MIN=1.50; READY_PRICE_CHANGE_MAX_PCT=6.0
TRIGGER_VOLUME_RATIO_MIN=2.50; TRIGGER_BREAKOUT_MIN_PCT=0.5
WINDOWS=(1,3,5,10,20); THS=(5,10,15,20,30,40)
FEATURES=['RecentSurgePct','PullbackPct','BaseLowSpreadPct','DryVolumeRatio','DayChangePct','VolumeRatio']
SPECS={'VolumeRatio':('>=',[1.6,1.75,2.0,2.25,2.5,3.0]),'BaseLowSpreadPct':('<=',[1.0,1.5,2.0,3.0,4.0]),'DryVolumeRatio':('<=',[0.35,0.45,0.55,0.65,0.75]),'DayChangePct':('>=',[0.5,1.0,1.5,2.0,3.0]),'RecentSurgePct':('>=',[25,30,40,50,70]),'PullbackPct':('>=',[15,18,20,25,30])}

def detect_signal(d):
    d=d.tail(max(SURGE_LOOKBACK+10,90)).copy()
    if len(d)<25:return None
    latest,prev=d.iloc[-1],d.iloc[-2]; close=float(latest.Close); pc=float(prev.Close)
    if pc<=0:return None
    hist=d.iloc[:-1].tail(SURGE_LOOKBACK); lows=hist.Low.to_numpy(float); highs=hist.High.to_numpy(float)
    best=0.; running=float(lows[0])
    for h,l in zip(highs,lows):
        if running>0:best=max(best,(float(h)/running-1)*100)
        running=min(running,float(l))
    if best<SURGE_MIN_PCT:return None
    peak=float(hist.High.tail(15).max()); pb=(peak-close)/peak*100 if peak>0 else 0; ppb=(peak-pc)/peak*100 if peak>0 else 0; ep=max(pb,ppb)
    if not(PULLBACK_MIN_PCT<=ep<=PULLBACK_MAX_PCT):return None
    def bm(base,prior):
        if len(base)<BASE_DAYS:return(False,999,1,0)
        lo0=float(base.Low.min());lo1=float(base.Low.max());spread=(lo1/lo0-1)*100 if lo0>0 else 999;rising=float(base.Low.iloc[-1])>=float(base.Low.iloc[0])*0.995;med=float(prior.median()) if len(prior) else 0;dry=float(base.Volume.mean())/med if med>0 else 1
        return(spread<=BASE_LOW_SPREAD_MAX_PCT and rising and dry<=DRY_VOLUME_RATIO_MAX,spread,dry,lo0)
    w=bm(d.iloc[-3:],d.Volume.iloc[-13:-4]);r=bm(d.iloc[-4:-1],d.Volume.iloc[-14:-5]);t=bm(d.iloc[-5:-2],d.Volume.iloc[-15:-6])
    chg=(close/pc-1)*100;vr=float(latest.Volume)/max(float(prev.Volume),1e-12);res=float(d.High.iloc[-6:-1].max());bo=(close/res-1)*100 if res>0 else -999
    stage=None;m=w
    if t[0] and vr>=TRIGGER_VOLUME_RATIO_MIN and bo>=TRIGGER_BREAKOUT_MIN_PCT:stage='TRIGGER';m=t
    elif r[0] and 0<=chg<=READY_PRICE_CHANGE_MAX_PCT and vr>=READY_VOLUME_RATIO_MIN:stage='READY';m=r
    elif w[0]:stage='WATCH';m=w
    if not stage:return None
    return {'Stage':stage,'RecentSurgePct':round(best,2),'PullbackPct':round(ep,2),'BaseLowSpreadPct':round(m[1],2),'DryVolumeRatio':round(m[2],3),'DayChangePct':round(chg,2),'VolumeRatio':round(vr,3),'Resistance':res,'BaseLow':m[3]}

def fwd(g,i):
    c=float(g.iloc[i].Close);fut20=g.iloc[i+1:i+21]
    if len(fut20)==0:return None
    out={'MFE20Pct':round((float(fut20.High.max())/c-1)*100,2),'MAE20Pct':round((float(fut20.Low.min())/c-1)*100,2)}
    for w in WINDOWS:
        f=g.iloc[i+1:i+1+w];mfe=(float(f.High.max())/c-1)*100 if len(f) else np.nan
        for th in THS:out[f'Hit{w}d_{th}pct']=bool(math.isfinite(mfe) and mfe>=th)
    out['SurgeSuccess']=bool(out.get('Hit5d_20pct') or out.get('Hit10d_30pct') or out.get('Hit20d_40pct'))
    return out

def make_charts(groups,ready,market,n=5):
    root=OUT/market/'charts';shutil.rmtree(root,ignore_errors=True);(root/'success').mkdir(parents=True);(root/'failure').mkdir(parents=True)
    samples=[('success',ready[ready.SurgeSuccess==True].sort_values('MFE20Pct',ascending=False).head(n)),('failure',ready[ready.SurgeSuccess==False].sort_values('MAE20Pct').head(n))]
    for label,df in samples:
        for _,r in df.iterrows():
            g=groups.get(str(r.Code))
            if g is None:continue
            dt=pd.Timestamp(r.Date);ids=g.index[g.Date==dt].tolist()
            if not ids:continue
            i=ids[0];x=g.iloc[max(0,i-45):min(len(g),i+21)]
            fig=go.Figure(go.Candlestick(x=x.Date,open=x.Open,high=x.High,low=x.Low,close=x.Close));fig.add_vline(x=dt.timestamp()*1000,line_dash='dash',annotation_text='READY');fig.update_layout(title=f'{r.Name} {r.Code} | READY {dt.date()} | MFE20 {r.MFE20Pct}% / MAE20 {r.MAE20Pct}%',xaxis_rangeslider_visible=False)
            safe=re.sub(r'[^0-9A-Za-z가-힣_-]+','_',str(r.Name))[:30];fig.write_html(root/label/f'{safe}_{str(r.Code).replace("/","-")}_{dt.date()}_{label}.html',include_plotlyjs='cdn')

def summarize(ready,market):
    rows=[]
    for w in WINDOWS:
        for th in THS:
            col=f'Hit{w}d_{th}pct';hits=int(ready[col].sum()) if len(ready) else 0;rows.append({'Market':market,'WindowDays':w,'ThresholdPct':th,'READYSignals':len(ready),'Hits':hits,'HitRatePct':round(hits/len(ready)*100,2) if len(ready) else None})
    pd.DataFrame(rows).to_csv(OUT/market/'granular_hit_rates.csv',index=False,encoding='utf-8-sig')
    return {'market':market,'ready_total':len(ready),'success':int(ready.SurgeSuccess.sum()) if len(ready) else 0,'failure':int((~ready.SurgeSuccess).sum()) if len(ready) else 0,'success_rate_pct':round(float(ready.SurgeSuccess.mean()*100),2) if len(ready) else None,'mfe20_median':round(float(ready.MFE20Pct.median()),2) if len(ready) else None,'mae20_median':round(float(ready.MAE20Pct.median()),2) if len(ready) else None}

def download_krx_year(y):
    p=OUT/'cache'/f'marcap-{y}.parquet';p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists() and p.stat().st_size>100000:return p
    urls=[f'https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{y}.parquet',f'https://github.com/FinanceData/marcap/raw/refs/heads/master/data/marcap-{y}.parquet']
    err=[]
    for u in urls:
        try:
            with requests.get(u,stream=True,timeout=(20,300),headers={'User-Agent':'Mozilla/5.0'}) as r:
                r.raise_for_status();tmp=p.with_suffix('.part')
                with tmp.open('wb') as f:
                    for ch in r.iter_content(1024*1024):
                        if ch:f.write(ch)
                if tmp.stat().st_size<100000:raise RuntimeError('small')
                tmp.replace(p);return p
        except Exception as e:err.append(str(e))
    raise RuntimeError(f'KRX {y} download failed: {err}')

def run_krx():
    (OUT/'KRX').mkdir(parents=True,exist_ok=True);dfs=[]
    for y in (2025,2026):
        p=download_krx_year(y);d=pd.read_parquet(p)
        if 'Date' not in d.columns:d=d.reset_index()
        d['Date']=pd.to_datetime(d.Date).dt.tz_localize(None);d['Code']=d.Code.astype(str).str.extract(r'(\d+)',expand=False).str.zfill(6);d['Name']=d.Name.astype(str);d['Market']=d.Market.astype(str).str.upper();d.loc[d.Market.str.startswith('KOSPI',na=False),'Market']='KOSPI';d.loc[d.Market.str.startswith('KOSDAQ',na=False),'Market']='KOSDAQ'
        for c in ['Open','High','Low','Close','Volume','Amount','Marcap']:d[c]=pd.to_numeric(d[c],errors='coerce')
        dfs.append(d[['Date','Code','Name','Market','Open','High','Low','Close','Volume','Amount','Marcap']])
    allx=pd.concat(dfs,ignore_index=True).sort_values(['Code','Date']);sig=[];groups={}
    for code,g in allx.groupby('Code'):
        g=g.dropna().sort_values('Date').reset_index(drop=True);groups[str(code)]=g
        for i in range(89,len(g)):
            row=g.iloc[i];dt=row.Date
            if not(START<=dt<=END):continue
            if row.Market not in('KOSPI','KOSDAQ') or re.search(EXCLUDE_PATTERN,str(row.Name)):continue
            if float(row.Marcap)<MIN_MARCAP or float(row.Amount)<KRX_MIN_AMOUNT:continue
            z=detect_signal(g.iloc[:i+1])
            if z:
                m=fwd(g,i)
                if m:sig.append({'Date':dt,'Code':code,'Name':row.Name,'Market':row.Market,'Close':float(row.Close),'Amount':float(row.Amount),'Marcap':float(row.Marcap),**z,**m})
    s=pd.DataFrame(sig);s.to_csv(OUT/'KRX'/'all_signals.csv',index=False,encoding='utf-8-sig');ready=s[s.Stage=='READY'].copy() if len(s) else pd.DataFrame();ready.to_csv(OUT/'KRX'/'ready_signals.csv',index=False,encoding='utf-8-sig')
    if len(ready):make_charts(groups,ready,'KRX')
    return ready,groups,summarize(ready,'KRX')

def upbit_get(path,params=None,retries=5):
    url='https://api.upbit.com/v1'+path
    for n in range(retries):
        try:
            r=requests.get(url,params=params,timeout=30,headers={'accept':'application/json','User-Agent':'READYBacktest/1.0'})
            if r.status_code==429:time.sleep(.5*(n+1));continue
            r.raise_for_status();return r.json()
        except Exception:
            if n==retries-1:raise
            time.sleep(.5*(n+1))

def upbit_markets():
    rows=upbit_get('/market/all',{'is_details':'false'});return[(r['market'],r.get('korean_name') or r['market']) for r in rows if r['market'].startswith('KRW-')]

def upbit_candles(code):
    out=[];to=None
    for _ in range(3):
        p={'market':code,'count':200}
        if to:p['to']=to
        rows=upbit_get('/candles/days',p)
        if not rows:break
        out.extend(rows);oldest=rows[-1]['candle_date_time_utc'];to=oldest+'Z';time.sleep(.12)
        if pd.Timestamp(oldest)<START-pd.Timedelta(days=120):break
    seen={}
    for x in out:seen[x['candle_date_time_kst']]=x
    d=pd.DataFrame(list(seen.values()))
    if len(d)==0:return d
    d['Date']=pd.to_datetime(d.candle_date_time_kst).dt.tz_localize(None);d['Open']=d.opening_price.astype(float);d['High']=d.high_price.astype(float);d['Low']=d.low_price.astype(float);d['Close']=d.trade_price.astype(float);d['Volume']=d.candle_acc_trade_volume.astype(float);d['Amount']=d.candle_acc_trade_price.astype(float)
    return d[['Date','Open','High','Low','Close','Volume','Amount']].sort_values('Date').drop_duplicates('Date').reset_index(drop=True)

def run_upbit():
    (OUT/'UPBIT').mkdir(parents=True,exist_ok=True);sig=[];groups={};universe=upbit_markets();print('UPBIT markets',len(universe),flush=True)
    for n,(code,name) in enumerate(universe,1):
        try:g=upbit_candles(code)
        except Exception as e:print('UPBIT fail',code,e,flush=True);continue
        if len(g)<100:continue
        groups[code]=g
        for i in range(89,len(g)):
            row=g.iloc[i];dt=row.Date
            if not(START<=dt<=END) or float(row.Amount)<UPBIT_MIN_AMOUNT:continue
            z=detect_signal(g.iloc[:i+1])
            if z:
                m=fwd(g,i)
                if m:sig.append({'Date':dt,'Code':code,'Name':name,'Market':'UPBIT-KRW','Close':float(row.Close),'Amount':float(row.Amount),**z,**m})
        if n%25==0:print('UPBIT',n,'signals',len(sig),flush=True)
    s=pd.DataFrame(sig);s.to_csv(OUT/'UPBIT'/'all_signals.csv',index=False,encoding='utf-8-sig');ready=s[s.Stage=='READY'].copy() if len(s) else pd.DataFrame();ready.to_csv(OUT/'UPBIT'/'ready_signals.csv',index=False,encoding='utf-8-sig')
    if len(ready):make_charts(groups,ready,'UPBIT')
    return ready,groups,summarize(ready,'UPBIT')

def cond_mask(df,f,op,v):
    x=pd.to_numeric(df[f],errors='coerce');return(x>=v if op=='>=' else x<=v).fillna(False)

def eval_mask(df,m):
    if len(df)==0:return{'n':0,'coverage':0,'rate':None,'uplift':None}
    base=float(df.SurgeSuccess.mean()*100);x=df[m];rate=float(x.SurgeSuccess.mean()*100) if len(x) else None;return{'n':len(x),'coverage':len(x)/len(df)*100,'rate':rate,'uplift':rate-base if rate is not None else None}

def common_and_ab(k,u):
    out=OUT/'COMMON';out.mkdir(exist_ok=True);cands=[]
    for f,(op,vals) in SPECS.items():
        for v in vals:
            name=f'{f} {op} {v:g}';a=eval_mask(k,cond_mask(k,f,op,v));b=eval_mask(u,cond_mask(u,f,op,v));cands.append({'Filter':name,'KRX_N':a['n'],'KRX_CoveragePct':round(a['coverage'],2),'KRX_SuccessRatePct':round(a['rate'],2) if a['rate'] is not None else None,'KRX_UpliftPp':round(a['uplift'],2) if a['uplift'] is not None else None,'UPBIT_N':b['n'],'UPBIT_CoveragePct':round(b['coverage'],2),'UPBIT_SuccessRatePct':round(b['rate'],2) if b['rate'] is not None else None,'UPBIT_UpliftPp':round(b['uplift'],2) if b['uplift'] is not None else None})
    c=pd.DataFrame(cands);c.to_csv(out/'common_filter_candidates.csv',index=False,encoding='utf-8-sig');robust=c[(c.KRX_UpliftPp>=2)&(c.UPBIT_UpliftPp>=2)&(c.KRX_CoveragePct>=8)&(c.UPBIT_CoveragePct>=8)].copy()
    if len(robust):robust['Score']=robust[['KRX_UpliftPp','UPBIT_UpliftPp']].min(axis=1)+.1*robust[['KRX_CoveragePct','UPBIT_CoveragePct']].min(axis=1);robust=robust.sort_values('Score',ascending=False)
    robust.to_csv(out/'robust_conditions.csv',index=False,encoding='utf-8-sig');best=robust.iloc[0].to_dict() if len(robust) else None;rows=[]
    for market,df in [('KRX',k),('UPBIT',u)]:
        rows.append({'Version':'READY_v1','Market':market,'Signals':len(df),'SuccessRatePct':round(float(df.SurgeSuccess.mean()*100),2) if len(df) else None,'Hit5d10Pct':round(float(df['Hit5d_10pct'].mean()*100),2) if len(df) else None,'Hit10d20Pct':round(float(df['Hit10d_20pct'].mean()*100),2) if len(df) else None,'MFE20Median':round(float(df.MFE20Pct.median()),2) if len(df) else None,'MAE20Median':round(float(df.MAE20Pct.median()),2) if len(df) else None})
        if best:
            f,op,val=re.match(r'(.+?) (>=|<=) ([0-9.]+)$',best['Filter']).groups();x=df[cond_mask(df,f,op,float(val))];rows.append({'Version':'READY_v2','Market':market,'Signals':len(x),'SuccessRatePct':round(float(x.SurgeSuccess.mean()*100),2) if len(x) else None,'Hit5d10Pct':round(float(x['Hit5d_10pct'].mean()*100),2) if len(x) else None,'Hit10d20Pct':round(float(x['Hit10d_20pct'].mean()*100),2) if len(x) else None,'MFE20Median':round(float(x.MFE20Pct.median()),2) if len(x) else None,'MAE20Median':round(float(x.MAE20Pct.median()),2) if len(x) else None})
    ab=pd.DataFrame(rows);ab.to_csv(out/'READY_v1_vs_v2.csv',index=False,encoding='utf-8-sig');decision='KEEP_V1'
    if best:
        piv=ab.pivot(index='Market',columns='Version',values='SuccessRatePct')
        if all(piv.loc[m,'READY_v2']>=piv.loc[m,'READY_v1']+2 for m in piv.index):decision='ADOPT_V2'
    rec={'best_common_filter':best,'decision':decision,'principle':'KRX/UPBIT data and liquidity filters separate; only common price/volume features intersected.'};(out/'recommendation.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2,default=str),encoding='utf-8');return best,ab,decision

def main():
    print('=== KRX ===',flush=True);k,kg,ks=run_krx();print(json.dumps(ks,ensure_ascii=False),flush=True);print('=== UPBIT ===',flush=True);u,ug,us=run_upbit();print(json.dumps(us,ensure_ascii=False),flush=True);best,ab,decision=common_and_ab(k,u);result={'period':[str(START.date()),str(END.date())],'KRX':ks,'UPBIT':us,'best_common_filter':best,'decision':decision};(OUT/'FINAL_SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2,default=str),flush=True)
if __name__=='__main__':main()
