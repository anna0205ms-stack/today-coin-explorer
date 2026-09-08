from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "ojutam"
MARK = "OJUTAM-TRADE-TRACKER-CHART"

JS = r'''(()=>{
const IS_US=location.pathname.includes('/ojutam/us/');
const TRACK_KEY=IS_US?'ojutamTradeTrackerUS':'ojutamTradeTrackerKRX';
let DATA={candidates:[]};
let charts=[];
let observers=[];
let rendering=false;
const safeParse=(s,d)=>{try{return JSON.parse(s)||d}catch(e){return d}};
const tracker=()=>safeParse(localStorage.getItem(TRACK_KEY)||'{}',{});
const n=v=>typeof v==='number'&&Number.isFinite(v)?v:(v!==null&&v!==''&&Number.isFinite(Number(v))?Number(v):null);
function current(code){return (DATA.candidates||[]).find(x=>String(x.market)===String(code));}
function plan(r){const p=r?.trade_plan||{};return{avg:n(p.average_entry),stop:n(p.stop),t1:n(p.target1),t2:n(p.target2)};}
function destroy(){for(const ro of observers){try{ro.disconnect()}catch(e){}}observers=[];for(const c of charts){try{c.remove()}catch(e){}}charts=[];}
function addPriceLine(series,price,title,color){if(n(price)==null)return;series.createPriceLine({price:Number(price),color,lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title});}
function rowOf(x){
  if(Array.isArray(x))return{time:String(x[0]).slice(0,10),open:+x[1],high:+x[2],low:+x[3],close:+x[4]};
  if(x&&typeof x==='object')return{time:String(x.time||x.date||'').slice(0,10),open:+x.open,high:+x.high,low:+x.low,close:+x.close};
  return null;
}
function drawCard(card){
  const code=card.dataset.trackCode,r=current(code);
  let box=card.querySelector('.track-chart-wrap');
  if(!box){
    box=document.createElement('section');
    box.className='track-chart-wrap';
    box.innerHTML='<div class="track-chart-head"><b>일봉 차트</b><span>현재 구조 · 평균진입/손절/TP1/TP2</span></div><div class="track-chart"></div>';
    const compare=card.querySelector('.track-compare');
    if(compare)compare.insertAdjacentElement('beforebegin',box);else card.appendChild(box);
  }
  const el=box.querySelector('.track-chart');
  if(!el)return;
  el.innerHTML='';
  if(!window.LightweightCharts){el.innerHTML='<div class="track-chart-empty">차트 라이브러리를 불러오지 못했어. 새로고침 후 다시 확인해줘.</div>';return;}
  if(!r){el.innerHTML='<div class="track-chart-empty">현재 스캔 후보에서 이탈해 실시간 차트는 현재 분석 복귀 시 다시 표시돼.</div>';return;}
  const raw=(r.charts?.day||r.charts?.D||[]);
  const rows=raw.slice(-180).map(rowOf).filter(x=>x&&x.time&&Number.isFinite(x.open)&&Number.isFinite(x.high)&&Number.isFinite(x.low)&&Number.isFinite(x.close));
  if(!rows.length){el.innerHTML='<div class="track-chart-empty">일봉 데이터가 없어.</div>';return;}
  const height=window.matchMedia('(max-width:760px)').matches?250:300;
  const width=Math.max(1,Math.floor(el.getBoundingClientRect().width||el.parentElement?.getBoundingClientRect().width||600));
  const ch=LightweightCharts.createChart(el,{width,height,layout:{background:{type:'solid',color:'#020609'},textColor:'#91a9b7'},grid:{vertLines:{color:'#17252e'},horzLines:{color:'#17252e'}},rightPriceScale:{borderVisible:false},timeScale:{rightOffset:5,barSpacing:6,minBarSpacing:2},handleScale:{mouseWheel:true,pinch:true},handleScroll:{pressedMouseMove:true,mouseWheel:true,horzTouchDrag:true}});
  charts.push(ch);
  const s=ch.addCandlestickSeries({upColor:'#20dfa4',downColor:'#ff514c',borderUpColor:'#20dfa4',borderDownColor:'#ff514c',wickUpColor:'#20dfa4',wickDownColor:'#ff514c',priceLineVisible:false,lastValueVisible:true});
  s.setData(rows);
  const p=plan(r);
  addPriceLine(s,p.avg,'평균진입','#58bfff');
  addPriceLine(s,p.stop,'손절','#ff667e');
  addPriceLine(s,p.t1,'TP1','#00e783');
  addPriceLine(s,p.t2,'TP2','#00c7ff');
  ch.timeScale().fitContent();
  const ro=new ResizeObserver(()=>{try{const h=window.matchMedia('(max-width:760px)').matches?250:300;ch.resize(Math.max(1,Math.floor(el.getBoundingClientRect().width)),h)}catch(e){}});
  ro.observe(el);
  observers.push(ro);
}
function render(){
  if(rendering)return;
  rendering=true;
  try{destroy();document.querySelectorAll('.trade-track-card[data-track-code]').forEach(drawCard);}finally{requestAnimationFrame(()=>{rendering=false;});}
}
function css(){if(document.getElementById('ojutam-tracker-chart-style'))return;const s=document.createElement('style');s.id='ojutam-tracker-chart-style';s.textContent=`.track-chart-wrap{margin:10px 0 12px;padding:10px;border:1px solid #203c30;border-radius:11px;background:#050a07}.track-chart-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:7px}.track-chart-head b{font-size:12px;color:#e9fff4}.track-chart-head span{font-size:10px;color:#789489}.track-chart{height:300px;width:100%;min-width:0;position:relative}.track-chart-empty{height:120px;display:flex;align-items:center;justify-content:center;text-align:center;color:#789489;font-size:11px;padding:16px}@media(max-width:760px){.track-chart-wrap{padding:7px;margin:8px 0 10px}.track-chart-head{align-items:flex-start;flex-direction:column;gap:2px}.track-chart{height:250px}.track-chart canvas{max-width:100%!important}}`;document.head.appendChild(s);}
async function init(){
  css();
  try{DATA=await fetch('scan_data.json?trackchart='+Date.now(),{cache:'no-store'}).then(r=>r.json())}catch(e){DATA={candidates:[]}};
  render();
  const root=document.getElementById('ojutamTradeTracker');
  if(root){
    new MutationObserver(muts=>{
      if(rendering)return;
      const structural=muts.some(m=>m.target===root);
      if(structural)requestAnimationFrame(render);
    }).observe(root,{childList:true,subtree:false});
  }
  window.addEventListener('storage',()=>requestAnimationFrame(render));
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();'''


def inject(path: Path, asset: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if "OJUTAM-TRADE-TRACKER" not in text:
        return False
    if MARK in text:
        return False
    libs = '<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>'
    tag = f'<!-- {MARK} -->{libs}<script src="{asset}?v=20260908-r12-chart2"></script>'
    text = text.replace('</body>', tag + '</body>', 1)
    path.write_text(text, encoding='utf-8')
    return True


def main() -> None:
    if not OUT.exists():
        raise SystemExit('outputs/ojutam missing')
    (OUT / 'trade_tracker_chart.js').write_text(JS, encoding='utf-8')
    us = OUT / 'us'
    if us.exists():
        (us / 'trade_tracker_chart.js').write_text(JS, encoding='utf-8')
    count=0
    for p in OUT.glob('*.html'):
        count += int(inject(p,'trade_tracker_chart.js'))
    if us.exists():
        for p in us.glob('*.html'):
            count += int(inject(p,'trade_tracker_chart.js'))
    print('OJUTAM trade tracker chart pages',count)


if __name__ == '__main__':
    main()
