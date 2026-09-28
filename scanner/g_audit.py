#!/usr/bin/env python3
import json, time, urllib.parse, urllib.request
from pathlib import Path
import numpy as np

API="https://api.upbit.com/v1"
OUT=Path(__file__).resolve().parents[1]/"outputs"/"g_audit_latest.json"
HEAD={"Accept":"application/json","User-Agent":"g-audit/1.0"}

def get(path, params=None):
    url=API+path
    if params: url+="?"+urllib.parse.urlencode(params)
    for n in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=30) as r:
                data=json.loads(r.read().decode())
            time.sleep(0.12)
            return data
        except Exception:
            if n==4: raise
            time.sleep(1+n)

def days(market,count=200):
    data=get("/candles/days",{"market":market,"count":count})
    rows=[]
    for x in reversed(data):
        rows.append({
          "date":x["candle_date_time_kst"][:10],
          "o":float(x["opening_price"]),"h":float(x["high_price"]),
          "l":float(x["low_price"]),"c":float(x["trade_price"])
        })
    # Upbit current daily candle is ongoing; drop latest row.
    return rows[:-1]

def historical_boxes(a, upto):
    boxes=[]
    for length in (24,32,45,60,80):
        start=max(0,upto-190)
        for e in range(start+length, max(start+length,upto-12), 3):
            if e>upto-12: break
            seg=a[e-length:e]
            if len(seg)<length: continue
            lows=np.array([x["l"] for x in seg]); highs=np.array([x["h"] for x in seg]); closes=np.array([x["c"] for x in seg])
            lo=float(np.quantile(lows,.18)); hi=float(np.quantile(highs,.82))
            if lo<=0 or hi<=lo: continue
            width=hi/lo-1
            if not (.045<=width<=.24): continue
            inside=float(((closes>=lo)&(closes<=hi)).mean())
            if inside<.64: continue
            mid=(lo+hi)/2
            if (closes<=mid).sum()<max(4,int(length*.15)) or (closes>=mid).sum()<max(4,int(length*.15)): continue
            boxes.append({"low":lo,"high":hi,"days":length,"inside":inside,"start":e-length,"end":e-1})
    boxes.sort(key=lambda z:(z["low"],-z["days"],-z["inside"]))
    out=[]
    for b in boxes:
        if any(abs(b["low"]/x["low"]-1)<.025 and abs(b["high"]/x["high"]-1)<.04 for x in out): continue
        out.append(b)
    return out

def classify(market,name,a):
    if len(a)<100: return None
    i=len(a)-1
    cur=a[i]; prev=a[i-1]
    prior45=a[max(0,i-45):i]
    recent_low=min(x["l"] for x in prior45)
    best=None
    for b in historical_boxes(a,i):
        lo,hi=b["low"],b["high"]; span=hi-lo
        if prev["c"]>=lo*.995: continue
        if recent_low>lo*.93: continue
        if min(cur["o"],prev["c"])>lo*1.005: continue
        if cur["c"]<=lo: continue
        depth=(cur["c"]-lo)/span
        if depth<.10: continue
        # only lower-edge reclaim; upper half/top not captured
        if cur["c"]>=lo+span*.60: continue
        if cur["h"]>=hi*1.02: continue
        earlier=a[max(0,i-10):i]
        if any(x["c"]>=lo*.995 for x in earlier): continue
        cand={"market":market,"name":name,"date":cur["date"],"box_low":lo,"box_high":hi,
              "open":cur["o"],"high":cur["h"],"low":cur["l"],"close":cur["c"],
              "depth_pct":depth*100,"box_days":b["days"],"inside_pct":b["inside"]*100}
        score=b["inside"]*100 + b["days"]*.15 - depth*8
        if best is None or score>best[0]: best=(score,cand)
    return best[1] if best else None

def main():
    markets=get("/market/all",{"is_details":"true"})
    krw=[m for m in markets if m["market"].startswith("KRW-")]
    out=[]
    for n,m in enumerate(krw,1):
        try:
            a=days(m["market"])
            r=classify(m["market"],m.get("korean_name") or m["market"],a)
            if r: out.append(r)
        except Exception as e:
            pass
        if n%30==0: print("scan",n,"/",len(krw),"hits",len(out),flush=True)
    out.sort(key=lambda x:(-x["inside_pct"],-x["box_days"],x["depth_pct"]))
    OUT.write_text(json.dumps({"generated_at":"2026-09-28","rule":"오늘 완성 일봉이 과거 횡보박스 하단을 처음 장악, 상단 미장악","candidates":out},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out[:20],ensure_ascii=False,indent=2))

if __name__=="__main__": main()
