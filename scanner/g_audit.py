#!/usr/bin/env python3
import json, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np

API="https://api.upbit.com/v1"
OUT=Path(__file__).resolve().parents[1]/"outputs"/"g_visual_candidates.json"
HEAD={"Accept":"application/json","User-Agent":"g-audit/1.0"}

def get(path, params=None):
    url=API+path
    if params: url+="?"+urllib.parse.urlencode(params)
    for n in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=30) as r:
                data=json.loads(r.read().decode())
            time.sleep(0.03)
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
    """넓은 시각검수용 후보: 아래 가격층에서 올라와 과거 윗박스 하단 근처/안쪽에 도달한 차트."""
    if len(a)<100: return None
    i=len(a)-1
    cur=a[i]; prev=a[i-1]
    recent=a[max(0,i-45):i]
    recent_low=min(x["l"] for x in recent)
    recent_high=max(x["h"] for x in recent)
    best=None
    for b in historical_boxes(a,i):
        lo,hi=b["low"],b["high"]; span=hi-lo
        if span<=0: continue

        # 분명한 아래 가격층이 있었어야 함
        lower_zone_days=sum(1 for x in recent if x["c"] < lo*0.93)
        if lower_zone_days < 5: continue
        if recent_low > lo*0.88: continue

        # 최근 12봉은 아래에서 윗박스 하단 쪽으로 올라오는 흐름
        r12=a[max(0,i-11):i+1]
        if len(r12)<6: continue
        first_avg=sum(x["c"] for x in r12[:4])/4
        last_avg=sum(x["c"] for x in r12[-4:])/4
        if last_avg <= first_avg*1.04: continue

        # 현재 완성 일봉이 하단 주변 또는 박스 하단부에 있어야 함
        pos=(cur["c"]-lo)/span
        if pos < -0.08 or pos > 0.62: continue

        # 윗박스 상단까지 이미 장악/돌파한 움직임은 제외
        if cur["c"] >= hi*0.985 or cur["h"] >= hi*1.03: continue

        # 오늘이 '첫 하단 장악'이면 A급 플래그
        earlier=a[max(0,i-10):i]
        first_take=(prev["c"]<lo*.995 and cur["c"]>lo and
                    all(x["c"]<lo*.995 for x in earlier))
        depth=(cur["c"]-lo)/span*100

        cand={"market":market,"name":name,"date":cur["date"],"box_low":lo,"box_high":hi,
              "open":cur["o"],"high":cur["h"],"low":cur["l"],"close":cur["c"],
              "position_pct":pos*100,"first_take":bool(first_take),
              "box_days":b["days"],"inside_pct":b["inside"]*100,
              "lower_zone_days":lower_zone_days,
              "ohlc":a[-120:]}
        # visual review priority: first_take, close near lower edge, clear old box
        score=(100 if first_take else 0)+b["inside"]*30+b["days"]*.1-abs(pos)*10
        if best is None or score>best[0]: best=(score,cand)
    return best[1] if best else None


def main():
    markets=get("/market/all",{"is_details":"true"})
    krw=[m for m in markets if m["market"].startswith("KRW-")]
    out=[]
    def one(m):
        try:
            a=days(m["market"])
            return classify(m["market"],m.get("korean_name") or m["market"],a)
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs=[ex.submit(one,m) for m in krw]
        for n,fut in enumerate(as_completed(futs),1):
            r=fut.result()
            if r: out.append(r)
            if n%30==0: print("scan",n,"/",len(krw),"hits",len(out),flush=True)
    out.sort(key=lambda x:(not x["first_take"], abs(x["position_pct"]), -x["inside_pct"], -x["box_days"]))
    OUT.write_text(json.dumps({"generated_at":"2026-09-28","rule":"시각검수용 넓은 후보: 아래 가격층 → 과거 윗박스 하단 접근/진입, 상단 미장악","candidates":out},ensure_ascii=False,indent=2),encoding="utf-8")
    summary=[{k:v for k,v in x.items() if k!="ohlc"} for x in out]
    (OUT.parent/"g_visual_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")

    def ascii_chart(x, width=64, height=18):
        a=x["ohlc"][-width:]
        vals=[p["c"] for p in a]
        lo=min(min(p["l"] for p in a),x["box_low"])
        hi=max(max(p["h"] for p in a),x["box_high"])
        span=max(hi-lo,1e-12)
        grid=[[" " for _ in range(len(a))] for _ in range(height)]
        def row(v):
            return max(0,min(height-1, int(round((hi-v)/span*(height-1)))))
        rlo=row(x["box_low"]); rhi=row(x["box_high"])
        for col in range(len(a)):
            if grid[rlo][col]==" ": grid[rlo][col]="-"
            if grid[rhi][col]==" ": grid[rhi][col]="="
        for col,p in enumerate(a):
            rh=row(p["h"]); rl=row(p["l"]); rc=row(p["c"])
            for rr in range(min(rh,rl),max(rh,rl)+1):
                if grid[rr][col]==" ": grid[rr][col]="|"
            grid[rc][col]="*"
        lines=["".join(r) for r in grid]
        return "\n".join(lines)

    visual=[]
    for x in [z for z in out if z.get("first_take")][:20]:
        visual.append(f'### {x["market"]} {x["name"]}  box={x["box_low"]:.8g}~{x["box_high"]:.8g} close={x["close"]:.8g}\n'+ascii_chart(x))
    (OUT.parent/"g_visual_ascii.txt").write_text("\n\n".join(visual),encoding="utf-8")
    print(json.dumps(summary[:30],ensure_ascii=False,indent=2))

if __name__=="__main__": main()
