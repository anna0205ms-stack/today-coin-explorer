from __future__ import annotations

from pathlib import Path
import json
import re

import ojutam_krx_daily as app
import ojutam_krx_daily_v2 as base
import ojutam_krx_daily_v3 as data


app.load_marcap = data.load_latest
_original_generate = app.generate


def box_levels(rows):
    """Robust recent structure box for market-index context.

    Use recent completed daily candles and trim one-off spikes so the lines act like
    the OkoTam dashboard's upper / center / lower structure guides rather than raw extrema.
    """
    q = rows[-80:] if len(rows) > 80 else rows
    if not q:
        return {}
    highs = sorted(float(r[2]) for r in q)
    lows = sorted(float(r[3]) for r in q)
    n = len(q)
    hi_i = max(0, min(n - 1, round((n - 1) * 0.90)))
    lo_i = max(0, min(n - 1, round((n - 1) * 0.10)))
    high = highs[hi_i]
    low = lows[lo_i]
    if high <= low:
        high = max(highs)
        low = min(lows)
    return {"high": high, "center": (high + low) / 2, "low": low}


def index_payload(symbol):
    try:
        rows = base.fetch_index(symbol, count=220)
    except Exception as e:
        print("index fetch", symbol, e)
        rows = []
    if not rows:
        return {"rows": [], "levels": {}, "price": None, "change": None}
    close = float(rows[-1][4])
    prev = float(rows[-2][4]) if len(rows) > 1 else close
    change = ((close / prev) - 1) * 100 if prev else 0.0
    candles = [
        {"time": r[0], "open": float(r[1]), "high": float(r[2]), "low": float(r[3]), "close": float(r[4])}
        for r in rows
    ]
    return {"rows": candles, "levels": box_levels(rows), "price": close, "change": change}


def patch_dashboard_indices():
    path = Path("outputs/ojutam/index.html")
    if not path.exists():
        return
    kospi = index_payload("^KS11")
    kosdaq = index_payload("^KQ11")

    def facts(p):
        price = p.get("price")
        change = p.get("change")
        return ("-" if price is None else f"{price:,.2f}", "-" if change is None else f"{change:+.2f}%")

    kp, kpc = facts(kospi)
    kd, kdc = facts(kosdaq)
    block = f'''<article class="panel hero market-indices">
      <div class="market-title-row"><div><h2>한국 시장 기준 차트</h2><div class="sub">KOSPI · KOSDAQ 일봉 구조를 먼저 보고 A~F 후보를 훑어.</div></div><div class="market-actions"><button id="krxAutoFit" type="button">자동맞춤</button><button id="krxBoxToggle" type="button" aria-pressed="true">박스선 ON</button></div></div>
      <section class="index-chart"><div class="index-head"><div><h3>KOSPI</h3><small>유가증권시장 · 1D</small></div><div><b>{kp}</b><span>{kpc}</span></div></div><div id="kospiChart" class="live-index-chart"><div class="chart-loading">KOSPI 차트 불러오는 중</div></div></section>
      <section class="index-chart"><div class="index-head"><div><h3>KOSDAQ</h3><small>코스닥시장 · 1D</small></div><div><b>{kd}</b><span>{kdc}</span></div></div><div id="kosdaqChart" class="live-index-chart"><div class="chart-loading">KOSDAQ 차트 불러오는 중</div></div></section>
      <p class="sub market-help">마우스/손가락으로 좌우 이동 · 휠/핀치 확대축소. 박스 상단·중심·하단은 차트 좌표에 붙어서 같이 움직여.</p>
    </article>'''

    css = '''<style>
.market-indices{display:flex;flex-direction:column;gap:10px}.market-title-row,.index-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.market-title-row h2,.index-head h3{margin:0}.market-actions{display:flex;gap:7px;flex-wrap:wrap}.market-actions button{border:1px solid #315543;border-radius:9px;background:#08150f;color:#eafff2;padding:7px 10px;cursor:pointer}.market-actions button:hover{border-color:#00e783;color:#00e783}.index-chart{border:1px solid #17392a;border-radius:13px;padding:10px;background:#060d09}.index-head small{color:var(--sub)}.index-head>div:last-child{text-align:right}.index-head b{display:block;font-size:18px}.index-head span{color:#a7b8af;font-size:12px}.live-index-chart{height:235px;margin-top:7px;border:1px solid #17392a;border-radius:10px;overflow:hidden;background:#020609;position:relative;touch-action:none}.chart-loading{position:absolute;inset:0;display:grid;place-items:center;color:var(--sub);font-size:12px}.market-help{margin:2px 0 0}@media(max-width:760px){.market-title-row{align-items:flex-start;flex-direction:column}.live-index-chart{height:250px}.market-actions{width:100%}}
</style>'''

    script_data = json.dumps({"kospi": kospi, "kosdaq": kosdaq}, ensure_ascii=False).replace("</", "<\\/")
    js = f'''<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script><script>
(()=>{{
const marketData={script_data};
const instances=[]; let boxVisible=true;
function build(id,payload){{
 const el=document.getElementById(id); if(!el||!window.LightweightCharts||!payload.rows?.length)return;
 el.innerHTML='';
 const chart=LightweightCharts.createChart(el,{{width:el.clientWidth,height:el.clientHeight,layout:{{background:{{type:'solid',color:'#020609'}},textColor:'#91a9b7',fontFamily:'Inter, Pretendard, Arial, sans-serif',fontSize:11}},grid:{{vertLines:{{color:'#17252e'}},horzLines:{{color:'#17252e'}}}},rightPriceScale:{{borderColor:'#29404d',autoScale:true,scaleMargins:{{top:.08,bottom:.08}}}},timeScale:{{borderColor:'#29404d',timeVisible:false,rightOffset:8,barSpacing:7,minBarSpacing:2}},crosshair:{{mode:LightweightCharts.CrosshairMode.Normal}},handleScale:{{axisPressedMouseMove:{{time:true,price:true}},mouseWheel:true,pinch:true}},handleScroll:{{pressedMouseMove:true,mouseWheel:true,horzTouchDrag:true,vertTouchDrag:true}},kineticScroll:{{mouse:true,touch:true}}}});
 const series=chart.addCandlestickSeries({{upColor:'#20dfa4',downColor:'#ff514c',borderUpColor:'#20dfa4',borderDownColor:'#ff514c',wickUpColor:'#20dfa4',wickDownColor:'#ff514c',priceLineVisible:true,lastValueVisible:true}});
 series.setData(payload.rows);
 const lines=[];
 function redraw(){{lines.splice(0).forEach(x=>series.removePriceLine(x)); if(!boxVisible)return; const cfg=[['high','상단','#ff6259'],['center','중심','#26dca1'],['low','하단','#63a0f2']]; cfg.forEach(([key,title,color])=>{{const price=payload.levels?.[key];if(typeof price==='number')lines.push(series.createPriceLine({{price,color,lineWidth:2,lineStyle:LightweightCharts.LineStyle.Solid,axisLabelVisible:true,title:`${{title}} ${{price.toLocaleString(undefined,{{maximumFractionDigits:2}})}}`}}))}})}}
 redraw(); chart.timeScale().fitContent(); const ro=new ResizeObserver(()=>chart.resize(el.clientWidth,el.clientHeight));ro.observe(el); instances.push({{chart,series,redraw}});
}}
build('kospiChart',marketData.kospi); build('kosdaqChart',marketData.kosdaq);
document.getElementById('krxAutoFit')?.addEventListener('click',()=>instances.forEach(x=>{{x.chart.timeScale().fitContent();x.chart.priceScale('right').applyOptions({{autoScale:true}})}}));
document.getElementById('krxBoxToggle')?.addEventListener('click',e=>{{boxVisible=!boxVisible;e.currentTarget.textContent=`박스선 ${{boxVisible?'ON':'OFF'}}`;e.currentTarget.setAttribute('aria-pressed',String(boxVisible));instances.forEach(x=>x.redraw())}});
}})();
</script>'''

    text = path.read_text(encoding="utf-8")
    text = re.sub(r'<article class="panel hero(?: market-indices)?">.*?</article>', block, text, count=1, flags=re.S)
    if "live-index-chart" not in text.split("</head>", 1)[0]:
        text = text.replace("</head>", css + "</head>", 1)
    text = text.replace("</body>", js + "</body>", 1)
    path.write_text(text, encoding="utf-8")


def render_grouped_scan(buckets, date):
    now = app.datetime.now(app.KST).strftime("%Y-%m-%d %H:%M")
    chips = ''.join(f'<a href="#type-{k.lower()}" class="scan-chip" style="--c:{app.INFO[k][0]}">{k}형 <b>{len(buckets[k])}</b></a>' for k in app.LETTERS)
    sections=[]
    for k in app.LETTERS:
        color, name, desc = app.INFO[k]
        cards=''.join(app.card(r) for r in buckets[k]) or '<div class="panel intro"><p class="sub">오늘 이 유형 후보 없음</p></div>'
        sections.append(f'''<section class="scan-type-block" id="type-{k.lower()}" style="--c:{color}">
          <div class="scan-type-head"><div><span class="scan-letter">{k}</span><div><h2>{k}형 · {app.esc(name)}</h2><p>{app.esc(desc)}</p></div></div><a href="type_{k.lower()}.html">{k}형만 크게 보기 →</a></div>
          <div class="gallery">{cards}</div>
        </section>''')
    style='''<style>.scan-jump{position:sticky;top:0;z-index:15;display:flex;gap:8px;overflow-x:auto;padding:10px 0 12px;background:linear-gradient(#030605 75%,transparent)}.scan-chip{flex:0 0 auto;border:1px solid var(--c);color:var(--c);border-radius:999px;padding:7px 11px;background:#07100c}.scan-type-block{scroll-margin-top:62px;margin:18px 0 28px}.scan-type-head{display:flex;justify-content:space-between;align-items:center;gap:12px;border:1px solid var(--c);border-radius:16px;padding:14px 16px;background:linear-gradient(135deg,#07100c,#091610)}.scan-type-head>div{display:flex;align-items:center;gap:12px}.scan-type-head h2,.scan-type-head p{margin:0}.scan-type-head p{color:var(--sub);margin-top:2px}.scan-type-head>a{color:var(--c);white-space:nowrap}.scan-letter{display:grid;place-items:center;width:44px;height:44px;border-radius:12px;background:var(--c);color:#031009;font-size:25px;font-weight:900}@media(max-width:760px){.scan-type-head{align-items:flex-start;flex-direction:column}.scan-type-head>a{margin-left:56px}}</style>'''
    body=f'''{style}<section class="panel intro"><h2>오늘의 전체 스캔 · A~F 유형별</h2><p class="sub">오코탐처럼 유형별로 묶었어. 한 유형 안에서 일봉 차트들을 연속으로 훑고 다음 유형으로 넘어가면 돼.</p></section><nav class="scan-jump">{chips}</nav>{''.join(sections)}'''
    Path("outputs/ojutam/scan.html").write_text(app.shell("오늘의 전체 스캔", body, "scan", date, now), encoding="utf-8")


def generate_v4(universe, buckets, date):
    _original_generate(universe, buckets, date)
    patch_dashboard_indices()
    render_grouped_scan(buckets, date)


app.generate = generate_v4

if __name__ == "__main__":
    app.main()
