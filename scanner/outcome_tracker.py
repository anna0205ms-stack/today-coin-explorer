#!/usr/bin/env python3
"""과거 후보의 24시간·72시간 진입/목표/손절 결과를 가볍게 갱신한다."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KST=timezone(timedelta(hours=9));ROOT=Path(__file__).resolve().parents[1];STORE=ROOT/"history"/"snapshots.json"
API="https://api.upbit.com/v1/candles/minutes/240";HEADERS={"Accept":"application/json","User-Agent":"upbit-mvp-outcome/1.0"}

def read():
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else []

def fetch(market,count=24):
    url=API+"?"+urlencode({"market":market,"count":count})
    with urlopen(Request(url,headers=HEADERS),timeout=25) as response: # noqa: S310
        rows=json.loads(response.read().decode("utf-8"))
    time.sleep(.13)
    return sorted([{"at":datetime.fromisoformat(r["candle_date_time_kst"]).replace(tzinfo=KST),"high":float(r["high_price"]),"low":float(r["low_price"])} for r in rows],key=lambda x:x["at"])

def evaluate(row,candles,end):
    entry=[x for x in row.get("entry",[]) if isinstance(x,(int,float))];stop=row.get("stop");targets=[x for x in row.get("targets",[]) if isinstance(x,(int,float))]
    if not entry or not isinstance(stop,(int,float)):return {"status":"자료 부족","mfe_pct":None,"mae_pct":None}
    fill=max(entry);target=targets[0] if targets else None;seen=[c for c in candles if c["at"]<end]
    touched=False;highs=[];lows=[]
    for c in seen:
        if not touched and c["low"]<=fill<=c["high"]:touched=True
        if not touched:continue
        highs.append(c["high"]);lows.append(c["low"])
        if c["low"]<=stop:return {"status":"손절 도달","mfe_pct":round((max(highs)/fill-1)*100,2),"mae_pct":round((min(lows)/fill-1)*100,2)}
        if isinstance(target,(int,float)) and c["high"]>=target:return {"status":"1차 목표 성공","mfe_pct":round((max(highs)/fill-1)*100,2),"mae_pct":round((min(lows)/fill-1)*100,2)}
    if not touched:return {"status":"진입 미도달","mfe_pct":None,"mae_pct":None}
    return {"status":"진입 후 진행","mfe_pct":round((max(highs)/fill-1)*100,2),"mae_pct":round((min(lows)/fill-1)*100,2)}

def update(now=None):
    now=now or datetime.now(KST);records=read();needs={}
    for record in records:
        start=datetime.fromisoformat(record["snapshot_at"])
        for horizon in (24,72):
            if now>=start+timedelta(hours=horizon):
                for row in record.get("candidates",[]):
                    if str(horizon)+"h" not in row.get("outcomes",{}):needs.setdefault(row.get("market"),[]).append((record,row,horizon,start))
    caches={}
    for market in [m for m in needs if m]:
        try:caches[market]=fetch(market,24)
        except Exception as exc:caches[market]=[];print(f"outcome fetch failed {market}: {exc}")
    for market,jobs in needs.items():
        for _,row,horizon,start in jobs:
            row.setdefault("outcomes",{})[str(horizon)+"h"]=evaluate(row,caches.get(market,[]),start+timedelta(hours=horizon))
    if needs:STORE.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"outcomes: {sum(map(len,needs.values()))} updated")

if __name__=="__main__":update()
