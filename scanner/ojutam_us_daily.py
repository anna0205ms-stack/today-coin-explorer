from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

import ojutam_krx_daily as app
import ojutam_krx_daily_v6 as v6
import ojutam_krx_daily_v7  # installs the current production renderer

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "outputs" / "ojutam" / "us"
HISTORY = ROOT / "history" / "ojutam_us_snapshots.json"
NASDAQ_LIST = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"


def nasdaq_symbols() -> pd.DataFrame:
    req = Request(NASDAQ_LIST, headers={"User-Agent": "Mozilla/5.0"})
    raw = urlopen(req, timeout=30).read().decode("utf-8", "replace")
    q = pd.read_csv(io.StringIO(raw), sep="|")
    q = q[q["Symbol"].notna() & q["Security Name"].notna()].copy()
    q = q[q["Test Issue"].eq("N")]
    q = q[~q["Symbol"].astype(str).str.contains(r"[$.^/]", regex=True)]
    bad = r"(ETF|ETN|Warrant|Right|Unit|Preferred|Depositary|Acquisition|SPAC|Fund)"
    q = q[~q["Security Name"].str.contains(bad, case=False, na=False, regex=True)]
    q["Symbol"] = q["Symbol"].astype(str).str.strip()
    return q[["Symbol", "Security Name"]].drop_duplicates("Symbol")


def normalized(raw: pd.DataFrame, ticker: str, single: bool) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if ticker in raw.columns.get_level_values(0):
                q = raw[ticker].copy()
            elif ticker in raw.columns.get_level_values(1):
                q = raw.xs(ticker, axis=1, level=1).copy()
            else:
                return pd.DataFrame()
        elif single:
            q = raw.copy()
        else:
            return pd.DataFrame()
        q.columns = [str(c).title() for c in q.columns]
        q = q[["Open", "High", "Low", "Close", "Volume"]].dropna(
            subset=["Open", "High", "Low", "Close"]
        )
        q.index = pd.to_datetime(q.index).tz_localize(None)
        q["Amount"] = q["Close"] * q["Volume"]
        return q[["Open", "High", "Low", "Close", "Volume", "Amount"]]
    except Exception:
        return pd.DataFrame()


def load_nasdaq():
    listed = nasdaq_symbols()
    names = dict(zip(listed["Symbol"], listed["Security Name"]))
    symbols = listed["Symbol"].tolist()
    frames = {}
    for start in range(0, len(symbols), 100):
        chunk = symbols[start : start + 100]
        try:
            raw = yf.download(
                chunk, period="2y", interval="1d", group_by="ticker",
                auto_adjust=False, threads=True, progress=False, timeout=40,
            )
        except Exception as exc:
            print("NASDAQ chunk failed", start, exc)
            continue
        for ticker in chunk:
            q = normalized(raw, ticker, len(chunk) == 1)
            if len(q) < 140:
                continue
            tail = q.tail(20)
            price = float(tail["Close"].iloc[-1])
            dollar_volume = float(tail["Amount"].median())
            if price < 2 or dollar_volume < 20_000_000:
                continue
            frames[ticker] = q
        print("NASDAQ", min(start + len(chunk), len(symbols)), "/", len(symbols), "liquid", len(frames))
    if not frames:
        raise RuntimeError("NASDAQ market data unavailable")
    universe = pd.DataFrame(
        [{"Code": s, "Name": names.get(s, s), "Market": "NASDAQ"} for s in frames]
    )
    latest = max(q.index.max() for q in frames.values()).date().isoformat()
    return universe, frames, latest


def scan_us(universe, frames):
    buckets = {k: [] for k in app.LETTERS}
    for _, row in universe.iterrows():
        code = str(row.Code)
        for item in app.analyze_one(code, str(row.Name), "NASDAQ", frames.get(code)):
            buckets[item["type"]].append(item)
    for key in app.LETTERS:
        buckets[key].sort(key=lambda x: -x["score"])
        buckets[key] = buckets[key][:30]
    return buckets


def market_facts(payload):
    rows = payload.get("D", {}).get("rows", [])
    if not rows:
        return "-", "-"
    close = float(rows[-1]["close"])
    prev = float(rows[-2]["close"]) if len(rows) > 1 else close
    change = (close / prev - 1) * 100 if prev else 0
    return f"{close:,.2f}", f"{change:+.2f}%"


def patch_us_dashboard(out: Path):
    payload = {"us100": v6.tf("^NDX"), "dxy": v6.tf("DX-Y.NYB")}
    (out / "index_timeframes.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    us_price, us_change = market_facts(payload["us100"])
    dx_price, dx_change = market_facts(payload["dxy"])
    p = out / "index.html"
    text = p.read_text(encoding="utf-8")
    text = text.replace("한국 시장 기준 차트", "미국 시장 기준 차트")
    text = text.replace("KOSPI · KOSDAQ 일봉 구조", "US100 · DXY 일봉 구조")
    text = text.replace("KOSPI", "US100").replace("KOSDAQ", "DXY")
    text = text.replace("유가증권시장", "NASDAQ 100").replace("코스닥시장", "미국 달러 인덱스")
    text = text.replace("kospi", "us100").replace("kosdaq", "dxy")
    text = text.replace("krxAutoFit", "usAutoFit").replace("krxBoxToggle", "usBoxToggle")
    text = re.sub(
        r'(<h3>US100</h3>.*?<div><b>).*?(</b><span>).*?(</span>)',
        lambda m: m.group(1) + us_price + m.group(2) + us_change + m.group(3),
        text, count=1, flags=re.S,
    )
    text = re.sub(
        r'(<h3>DXY</h3>.*?<div><b>).*?(</b><span>).*?(</span>)',
        lambda m: m.group(1) + dx_price + m.group(2) + dx_change + m.group(3),
        text, count=1, flags=re.S,
    )
    # The shared dashboard script is KRX-specific. Build a US-specific copy so
    # timeframe buttons address the us100/dxy payload and chart containers.
    shared_js = (ROOT / "outputs" / "ojutam" / "index_v6.js").read_text(encoding="utf-8")
    us_js = shared_js
    us_js = us_js.replace(
        "name==='kospi'?'kospiChart':'kosdaqChart'",
        "name==='us100'?'us100Chart':'dxyChart'",
    )
    us_js = us_js.replace("draw('kospi','D')", "draw('us100','D')")
    us_js = us_js.replace("draw('kosdaq','D')", "draw('dxy','D')")
    us_js = us_js.replace("'krxAutoFit'", "'usAutoFit'")
    us_js = us_js.replace("'krxBoxToggle'", "'usBoxToggle'")
    (out / "index_us.js").write_text(us_js, encoding="utf-8")
    text = text.replace(
        '<script src="index_v6.js"></script>',
        '<script src="index_us.js?v=20260902-us100-dxy-1"></script>',
    )
    p.write_text(text, encoding="utf-8")


def localize_us(out: Path):
    replacements = {
        "한국주식 차트를 탐험하고": "미국주식 차트를 탐험하고",
        "KRX 일봉 스캐너": "NASDAQ 일봉 스캐너",
        "KRX ": "NASDAQ ",
        "코스피시장": "NASDAQ",
        'localStorage.getItem("ojutamPins")': 'localStorage.getItem("ojutamPinsUS")',
        'localStorage.setItem("ojutamPins"': 'localStorage.setItem("ojutamPinsUS"',
        "../assets/": "../../assets/",
    }
    for page in out.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        page.write_text(text, encoding="utf-8")


def main():
    universe, frames, date = load_nasdaq()
    buckets = scan_us(universe, frames)
    with tempfile.TemporaryDirectory(prefix="ojutam-us-") as td:
        staging = Path(td)
        out = staging / "outputs" / "ojutam"
        out.mkdir(parents=True, exist_ok=True)
        production = ROOT / "outputs" / "ojutam"
        for asset in ("scan_v6.js", "index_v6.js"):
            source = production / asset
            if source.exists():
                shutil.copy2(source, out / asset)
        app.OUT = out
        app.HISTORY = HISTORY
        previous = Path.cwd()
        os.chdir(staging)
        try:
            app.generate(universe, buckets, date)
            patch_us_dashboard(out)
            localize_us(out)
        finally:
            os.chdir(previous)
        DEST.parent.mkdir(parents=True, exist_ok=True)
        if DEST.exists():
            shutil.rmtree(DEST)
        shutil.copytree(out, DEST)
    print("OJUTAM US", date, len(universe), {k: len(buckets[k]) for k in app.LETTERS})


if __name__ == "__main__":
    main()
