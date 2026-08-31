from __future__ import annotations

from datetime import date
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

app.load_marcap=load_marcap_fixed

if __name__=="__main__":
    app.main()
