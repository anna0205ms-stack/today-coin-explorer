from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "ojutam"
MARK = "OJUTAM-TRADE-TRACKER"

JS = r'''(()=>{
const IS_US=location.pathname.includes('/ojutam/us/');
const PIN_KEY=IS_US?'ojutamPinsUS':'ojutamPins';
const TRACK_KEY=IS_US?'ojutamTradeTrackerUS':'ojutamTradeTrackerKRX';
const DATA_URL=location.pathname.includes('/us/')?'scan_data.json':'scan_data.json';
let CURRENT={candidates:[],market_date:'',generated_at:''};
const safeParse=(s,d)=>{try{return JSON.parse(s)||d}catch(e){return d}};
const pins=()=>safeParse(localStorage.getItem(PIN_KEY)||'[]',[]);
const savePins=v=>localStorage.setItem(PIN_KEY,JSON.stringify(v));
const tracker=()=>safeParse(localStorage.getItem(TRACK_KEY)||'{}',{});
const saveTracker=v=>localStorage.setItem(TRACK_KEY,JSON.stringify(v));
const n=v=>typeof v==='number'&&Number.isFinite(v)?v:(v!==null&&v!==''&&Number.isFinite(Number(v))?Number(v):null);
const px=v=>n(v)==null?'-':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:2});
const pct=v=>n(v)==null?'-':`${v>0?'+':''}${Number(v).toFixed(1)}%`;
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function findCurrent(code){return (CURRENT.candidates||[]).find(x=>String(x.market)===String(code));}
function planOf(r){const p=r?.trade_plan||{},day=r?.charts?.day||[];const cur=n(p.current)!=null?n(p.current):(day.length?n(day[day.length-1][4]):null);return{current:cur,status:p.status||'확인 대기',remain:p.remain||'현재 구조 확인',reason:p.reason||r?.reason||'-',average:n(p.average_entry),stop:n(p.stop),t1:n(p.target1),t2:n(p.target2),t3:n(p.extension),rr:n(p.rr1)};}
function snapOf(r){const p=planOf(r);return{code:String(r.market),name:r.name||r.market,type:r.type||'-',score:n(r.score),savedAt:new Date().toISOString(),marketDate:CURRENT.market_date||'',generatedAt:CURRENT.generated_at||'',plan:p};}
function ensureSnapshot(code){const r=findCurrent(code);if(!r)return;const t=tracker();if(!t[code])t[code]={snapshot:snapOf(r),active:true,bought:false,events:[]};else t[code].active=true;saveTracker(t);}
function setActive(code,active){const t=tracker();if(t[code]){t[code].active=active;saveTracker(t);}}
function migratePins(){const t=tracker();let changed=false;for(const code of pins()){if(!t[code]){const r=findCurrent(code);if(r){t[code]={snapshot:snapOf(r),active:true,bought:false,events:[{at:new Date().toISOString(),kind:'복구',text:'기존 별표를 현재 시점부터 추적 시작'}]};changed=true;}}else if(!t[code].active){t[code].active=true;changed=true;}}if(changed)saveTracker(t);}
function verdict(item,cur){if(!cur)return['🔴','현재 후보 이탈','tracker-red'];const old=item.snapshot,now=planOf(cur);if(now.status==='구조 무효')return['🔴','당시 구조 무효','tracker-red'];if(cur.type!==old.type)return['🔵',`새 구조 형성 · ${old.type}→${cur.type}`,'tracker-blue'];if(now.status==='새 구조 대기'||now.status==='추격 금지')return['🟠',now.status,'tracker-warn'];const stop=n(old.plan?.stop),cp=n(now.current);if(stop!=null&&cp!=null){const gap=(cp/stop-1)*100;if(gap<0)return['🔴','당시 손절선 이탈','tracker-red'];if(gap<2)return['🟡','계획 약화 · 손절선 근접','tracker-warn'];}const ds=(n(cur.score)||0)-(n(old.score)||0);if(ds<=-2)return['🟡','계획 약화 · 점수 하락','tracker-warn'];return['🟢','당시 계획 유지','tracker-green'];}
function recordChanges(){const t=tracker();let dirty=false;for(const [code,item] of Object.entries(t)){if(!item.active)continue;const cur=findCurrent(code),now=cur?planOf(cur):null;const sig=cur?`${CURRENT.market_date}|${cur.type}|${cur.score}|${now.status}|${now.current}`:`${CURRENT.market_date}|OUT`;if(item.lastSig===sig)continue;item.lastSig=sig;const [icon,label]=verdict(item,cur);item.events=item.events||[];item.events.push({at:new Date().toISOString(),kind:'변화',text:`${icon} ${label}${cur?` · ${cur.type}형 · ${cur.score??'-'}점 · ${px(now.current)}`:''}`});item.events=item.events.slice(-30);dirty=true;}if(dirty)saveTracker(t);}
function card(code,item){const s=item.snapshot,cur=findCurrent(code),now=cur?planOf(cur):null,[icon,label,cls]=verdict(item,cur);const old=s.plan||{};const change=(n(old.current)!=null&&n(now?.current)!=null)?(now.current/old.current-1)*100:null;const events=(item.events||[]).slice(-6).reverse().map(e=>`<li><span>${esc((e.at||'').slice(0,10))}</span>${esc(e.text)}</li>`).join('')||'<li>아직 변화 기록 없음</li>';return `<article class="trade-track-card ${cls}" data-track-code="${esc(code)}"><div class="track-head"><div><b>${esc(s.name)}</b><span>${esc(code)} · 당시 ${esc(s.type)}형</span></div><div class="track-actions"><button class="buy-btn ${item.bought?'on':''}" data-buy="${esc(code)}">${item.bought?'💰 실제 매수함':'＋ 실제 매수함'}</button><button class="untrack-btn" data-untrack="${esc(code)}">별표 해제</button></div></div><div class="track-verdict"><strong>${icon} ${esc(label)}</strong>${change==null?'':`<span>별표 당시가 대비 ${pct(change)}</span>`}</div><div class="track-compare"><section><h4>당시 계획 <small>${esc(s.marketDate||s.savedAt?.slice(0,10)||'')}</small></h4><p><b>${esc(s.type)}형 · ${s.score??'-'}점</b></p><p>당시가 ${px(old.current)}</p><p>평균진입 ${px(old.average)} · 손절 ${px(old.stop)}</p><p>TP1 ${px(old.t1)} · TP2 ${px(old.t2)}</p><p class="track-state">${esc(old.status||'-')}</p><p class="track-reason">${esc(old.reason||'-')}</p></section><section><h4>현재 분석 <small>${esc(CURRENT.market_date||'')}</small></h4>${cur?`<p><b>${esc(cur.type)}형 · ${cur.score??'-'}점</b></p><p>현재가 ${px(now.current)}</p><p>평균진입 ${px(now.average)} · 손절 ${px(now.stop)}</p><p>TP1 ${px(now.t1)} · TP2 ${px(now.t2)}</p><p class="track-state">${esc(now.status)}</p><p class="track-reason">${esc(now.remain)} · ${esc(now.reason)}</p>`:`<p><b>현재 스캔 후보에서 이탈</b></p><p class="track-reason">당시 계획은 보존돼 있어. 현재 스캐너에서 다시 포착되면 현재 분석이 자동 비교돼.</p>`}</section></div><details class="track-timeline"><summary>변화 기록</summary><ul>${events}</ul></details></article>`;}
function renderTracker(){let host=document.getElementById('ojutamTradeTracker');if(!host){const table=document.querySelector('.table-wrap');if(!table)return;host=document.createElement('section');host.id='ojutamTradeTracker';host.className='ojutam-tracker';table.parentNode.insertBefore(host,table);}const t=tracker(),active=Object.entries(t).filter(([,v])=>v.active);host.innerHTML=`<div class="tracker-title"><div><h2>⭐ 내 매매 추적 목록</h2><p>별표한 순간의 계획은 고정 보관하고, 현재 스캔 분석과 비교해.</p></div><span>${active.length}종목</span></div>${active.length?`<div class="tracker-grid">${active.map(([c,i])=>card(c,i)).join('')}</div>`:'<div class="tracker-empty">별표한 종목이 아직 없어. 후보의 ☆를 누르면 당시 계획이 여기 저장돼.</div>'}`;host.querySelectorAll('[data-buy]').forEach(b=>b.onclick=e=>{e.stopPropagation();const t=tracker(),c=b.dataset.buy;if(t[c]){t[c].bought=!t[c].bought;t[c].events=t[c].events||[];t[c].events.push({at:new Date().toISOString(),kind:'매수',text:t[c].bought?'💰 실제 매수 표시':'실제 매수 표시 해제'});saveTracker(t);renderTracker();}});host.querySelectorAll('[data-untrack]').forEach(b=>b.onclick=e=>{e.stopPropagation();const c=b.dataset.untrack;savePins(pins().filter(x=>x!==c));setActive(c,false);document.querySelectorAll(`button.star`).forEach(x=>{if((x.getAttribute('onclick')||'').includes(`'${c}'`))x.textContent='☆'});renderTracker();});}
function installToggle(){const old=window.toggleScanPin;window.toggleScanPin=function(code,b,e){const was=pins().includes(code);if(typeof old==='function')old(code,b,e);else{e?.stopPropagation();let p=pins();p=was?p.filter(x=>x!==code):[...p,code];savePins(p);if(b)b.textContent=was?'☆':'★';}const now=pins().includes(code);if(now)ensureSnapshot(code);else setActive(code,false);recordChanges();renderTracker();};}
function css(){if(document.getElementById('ojutam-tracker-style'))return;const s=document.createElement('style');s.id='ojutam-tracker-style';s.textContent=`.ojutam-tracker{margin:16px 0 18px;padding:16px;border:1px solid #28513d;border-radius:16px;background:#06100b}.tracker-title{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.tracker-title h2{margin:0 0 4px;font-size:18px}.tracker-title p{margin:0;color:#8ca699;font-size:12px}.tracker-title>span{border:1px solid #315543;border-radius:999px;padding:5px 9px;color:#a7c2b4;font-size:11px}.tracker-grid{display:grid;gap:12px;margin-top:14px}.trade-track-card{border:1px solid #274638;border-left:3px solid #58bfff;border-radius:13px;padding:13px;background:#08130e}.trade-track-card.tracker-red{border-left-color:#ff667e}.trade-track-card.tracker-warn{border-left-color:#ffd45f}.trade-track-card.tracker-green{border-left-color:#56e6a7}.trade-track-card.tracker-blue{border-left-color:#58bfff}.track-head,.track-verdict{display:flex;justify-content:space-between;gap:10px;align-items:center}.track-head b{font-size:15px}.track-head span{display:block;color:#8ca699;font-size:10px;margin-top:2px}.track-actions{display:flex;gap:6px}.track-actions button{border:1px solid #315543;border-radius:8px;background:#07100c;color:#b9d0c4;padding:6px 8px;font-size:10px;cursor:pointer}.buy-btn.on{border-color:#d5a929;color:#ffd45f;background:#2d2508}.track-verdict{margin:10px 0;padding:9px 10px;border-radius:9px;background:#0b1a12}.track-verdict span{color:#9db2a7;font-size:11px}.track-compare{display:grid;grid-template-columns:1fr 1fr;gap:10px}.track-compare section{padding:10px;border:1px solid #203c30;border-radius:10px;background:#07100c}.track-compare h4{margin:0 0 7px;font-size:12px;color:#d9e8e0}.track-compare h4 small{float:right;color:#6f8b7d;font-weight:400}.track-compare p{margin:4px 0;font-size:11px;color:#a9bcb2}.track-compare p b{color:#eef8f3}.track-state{color:#ffd45f!important}.track-reason{color:#789489!important}.track-timeline{margin-top:9px;color:#8fa99b;font-size:10px}.track-timeline summary{cursor:pointer}.track-timeline ul{margin:7px 0 0;padding-left:17px}.track-timeline li{margin:4px 0}.track-timeline li span{display:inline-block;min-width:78px;color:#647d71}.tracker-empty{margin-top:12px;padding:18px;text-align:center;border:1px dashed #29493b;border-radius:10px;color:#789489;font-size:12px}@media(max-width:760px){.ojutam-tracker{padding:11px;margin:10px 0}.tracker-title h2{font-size:15px}.track-head{align-items:flex-start}.track-actions{flex-direction:column}.track-compare{grid-template-columns:1fr}.track-verdict{align-items:flex-start;flex-direction:column}.tracker-title p{font-size:10px}}`;document.head.appendChild(s);}
async function init(){css();installToggle();try{CURRENT=await fetch(DATA_URL+'?tracker='+Date.now(),{cache:'no-store'}).then(r=>r.json());}catch(e){CURRENT={candidates:[]};}migratePins();recordChanges();renderTracker();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();'''


def inject_page(path: Path, asset: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if MARK in text:
        return False
    if "scan_v6.js" not in text:
        return False
    tag = f'<!-- {MARK} --><script src="{asset}?v=20260908-r12"></script>'
    text = text.replace("</body>", tag + "</body>", 1)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    if not OUT.exists():
        raise SystemExit("outputs/ojutam missing")
    (OUT / "trade_tracker.js").write_text(JS, encoding="utf-8")
    us = OUT / "us"
    if us.exists():
        (us / "trade_tracker.js").write_text(JS, encoding="utf-8")
    count = 0
    for p in OUT.glob("*.html"):
        count += int(inject_page(p, "trade_tracker.js"))
    if us.exists():
        for p in us.glob("*.html"):
            count += int(inject_page(p, "trade_tracker.js"))
    print("OJUTAM trade tracker pages", count)


if __name__ == "__main__":
    main()
