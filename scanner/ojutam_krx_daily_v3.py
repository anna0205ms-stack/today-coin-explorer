from __future__ import annotations

import pandas as pd
import yfinance as yf
import ojutam_krx_daily as app
import ojutam_krx_daily_v2 as base


def _norm_yf(x: pd.DataFrame) -> pd.DataFrame:
    if x is None or x.empty:
        return pd.DataFrame()
    q=x.copy()
    rename={c:str(c).title() for c in q.columns}
    q=q.rename(columns=rename)
    keep=[c for c in ["Open","High","Low","Close","Volume"] if c in q.columns]
    if len(keep)<5:return pd.DataFrame()
    q=q[keep].dropna(subset=["Open","High","Low","Close"])
    q.index=pd.to_datetime(q.index).tz_localize(None)
    q["Amount"]=q["Close"]*q["Volume"]
    return q[["Open","High","Low","Close","Volume","Amount"]]


def load_latest():
    universe,frames,date=base.load_marcap_fixed()
    items=[]
    ticker_to_code={}
    for _,r in universe.iterrows():
        code=str(r.Code).zfill(6); ticker=code+(".KS" if str(r.Market)=="KOSPI" else ".KQ")
        items.append(ticker);ticker_to_code[ticker]=code
    for start in range(0,len(items),50):
        chunk=items[start:start+50]
        try:
            raw=yf.download(chunk,period="14d",interval="1d",group_by="ticker",auto_adjust=False,threads=True,progress=False,timeout=25)
        except Exception as e:
            print("daily refresh chunk failed",start,e);continue
        for ticker in chunk:
            code=ticker_to_code[ticker]
            try:
                if isinstance(raw.columns,pd.MultiIndex):
                    if ticker in raw.columns.get_level_values(0): sub=raw[ticker]
                    elif ticker in raw.columns.get_level_values(1): sub=raw.xs(ticker,axis=1,level=1)
                    else: continue
                else:
                    if len(chunk)!=1: continue
                    sub=raw
                q=_norm_yf(sub)
                if q.empty: continue
                old=frames.get(code,pd.DataFrame())
                merged=pd.concat([old,q]).sort_index()
                merged=merged[~merged.index.duplicated(keep="last")]
                frames[code]=merged
            except Exception:
                continue
    latest=max((f.index.max() for f in frames.values() if f is not None and not f.empty),default=pd.Timestamp(date))
    return universe,frames,pd.Timestamp(latest).date().isoformat()


app.load_marcap=load_latest

if __name__=="__main__":
    app.main()
    # IMPORTANT: v3 is the actual workflow entry point. Patch the generated
    # dashboard here so the public HTML replaces the representative stock hero
    # with KOSPI and KOSDAQ market-index charts.
    base.patch_market_indices()
