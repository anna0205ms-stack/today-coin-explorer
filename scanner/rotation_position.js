(() => {
  const labels = {low:'하단',middle:'중단',high:'상단',breakout:'상단 돌파',moon:'🚀 TO THE MOON'};
  const colors = {low:'#20dfa4',middle:'#f4d54e',high:'#ff9b57',breakout:'#ef44ff',moon:'#00ccef'};
  const notes = {low:'장기 범위의 아래쪽',middle:'바닥을 벗어난 중간 가격대',high:'장기 범위의 높은 가격대',breakout:'과거 상단 위로 올라온 상태',moon:'상단을 크게 넘고 고점을 높이는 상태'};
  const order = Object.keys(labels);
  const pegged = new Set(['USDT','USDC','USDS','USD1','USDG','USDE','DAI','FDUSD','TUSD','PYUSD','RLUSD','USDD','EURC','EURCV','GUSD','FRAX','LUSD','UST','USTC','XAUT','PAXG']);
  const $ = id => document.getElementById(id);
  let data;
  let trade = {};
  let activeStage = null;
  let visibleCount = 12;
  const esc = v => String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const price = v => Number(v).toLocaleString('ko-KR',{maximumFractionDigits:8});
  function points(values,width,height){
    if (!values || values.length < 2) return '';
    const lo=Math.min(...values),hi=Math.max(...values),span=hi-lo || 1;
    return values.map((v,i)=>`${(i/(values.length-1)*width).toFixed(1)},${(height-7-(v-lo)/span*(height-14)).toFixed(1)}`).join(' ');
  }
  function spark(coin){
    return `<svg class="coin-chart" viewBox="0 0 220 67" preserveAspectRatio="none" role="img" aria-label="${esc(coin.symbol)} 장기 일봉 흐름"><polyline points="${points(coin.spark,220,67)}" fill="none" stroke="${colors[coin.stage]}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
  }
  function card(coin){
    const loc=locationLabel(coin);
    return `<button class="position-coin" style="--group-color:${colors[coin.stage]}" data-market="${esc(coin.market)}"><div class="coin-top"><span><strong>${esc(coin.name)}</strong> <small>${esc(coin.symbol)}</small></span><b>${loc}</b></div>${spark(coin)}<span class="coin-foot">${labels[coin.stage]} · 장기 일봉 ${coin.days}개 · 큰 차트 보기 ↗</span></button>`;
  }
  function locationLabel(coin){
    return coin.location < 0 ? '기준 하단 아래' : coin.location > 100 ? `상단 +${coin.above_high_pct}%` : `${coin.location}%`;
  }
  function render(){
    const counts=Object.fromEntries(order.map(k=>[k,data.coins.filter(c=>c.stage===k).length]));
    const total=data.coins.length || 1;
    $('updated').textContent=`최근 업데이트 ${data.updated_at.replace('T',' ').slice(0,16)} KST`;
    $('coverage').textContent=`분류 ${data.covered}/${data.total}개${data.excluded?` · 가격 연동 ${data.excluded}개 제외`:''}${data.partial?' · 일부 데이터 미수집':''}`;
    $('overview').innerHTML=`<h3>전체 위치 분포</h3><div class="distribution" aria-label="위치별 코인 비율">${order.map(k=>`<button type="button" data-stage="${k}" style="width:${counts[k]/total*100}%;background:${colors[k]}" title="${labels[k]} ${counts[k]}개 보기" aria-label="${labels[k]} ${counts[k]}개 보기"></button>`).join('')}</div><p class="overview-help">구간을 누르면 해당 코인이 열려요.</p><div class="jump-links">${order.map(k=>`<button type="button" data-stage="${k}" aria-expanded="${activeStage===k}" class="${activeStage===k?'active':''}" style="--group-color:${colors[k]}">${labels[k]} ${counts[k]}개</button>`).join('')}</div>`;
    const tools=document.querySelector('.rotation-tools');
    tools.hidden=!activeStage;
    if (!activeStage){$('groups').innerHTML='';return;}
    const sort=$('sort').value;
    const coins=data.coins.filter(c=>c.stage===activeStage).sort((a,b)=>sort==='trade'?(trade[b.market]||0)-(trade[a.market]||0):sort==='name'?a.name.localeCompare(b.name,'ko'):a.location-b.location);
    const displayed=coins.slice(0,visibleCount);
    $('groups').innerHTML=`<section class="position-group" id="group-${activeStage}" style="--group-color:${colors[activeStage]}"><button type="button" class="group-heading" data-collapse="true" aria-label="${labels[activeStage]} 목록 닫기"><span>▼ ${labels[activeStage]} · ${coins.length}개</span><small>접기</small></button><p>${notes[activeStage]} · ${Math.min(visibleCount,coins.length)}개 표시</p><div class="coin-list">${coins.length?displayed.map(card).join(''):'해당 위치의 코인이 없습니다.'}</div>${visibleCount<coins.length?`<button type="button" class="show-more" data-more="true">다음 ${Math.min(12,coins.length-visibleCount)}개 보기 ↓</button>`:''}</section>`;
  }
  function openDetail(coin){
    $('detail-title').textContent=`${coin.name} (${coin.market}) · ${labels[coin.stage]}`;
    $('detail-location').innerHTML=`<p>장기 위치 ${locationLabel(coin)}</p><div class="location-track"><span style="width:${Math.max(0,Math.min(100,coin.location))}%"></span></div>`;
    const values=coin.daily.map(x=>Number(x[1])),lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1;
    const y=v=>330-(v-lo)/span*300;
    const x=i=>32+i/(values.length-1)*660;
    const poly=values.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
    const mark=(value,color,title)=>`<line x1="32" x2="692" y1="${y(value)}" y2="${y(value)}" stroke="${color}" stroke-dasharray="5 5"/><text x="36" y="${Math.max(18,y(value)-6)}" fill="${color}" font-size="12">${title} ${price(value)}</text>`;
    $('big-chart').innerHTML=`<rect x="0" y="0" width="720" height="350" fill="#071119"/><polyline points="${poly}" fill="none" stroke="#00ccef" stroke-width="2.4"/>${mark(coin.low,'#20dfa4','기준 하단')}${mark(coin.high,'#f4d54e','기준 상단')}<circle cx="${x(values.length-1)}" cy="${y(coin.price)}" r="5" fill="#f3f8fb"/>`;
    $('detail-bounds').textContent=`${coin.daily[0][0]} ~ ${coin.daily.at(-1)[0]} · 기준 하단 ${price(coin.low)}원 · 기준 상단 ${price(coin.high)}원 · 현재 ${price(coin.price)}원. 기준값은 종가 분포의 2%, 98% 지점입니다.`;
    $('detail').hidden=false;document.body.style.overflow='hidden';history.replaceState(null,'',`#coin-${coin.market}`);
  }
  $('overview').addEventListener('click',e=>{const el=e.target.closest('[data-stage]');if(!el)return;activeStage=activeStage===el.dataset.stage?null:el.dataset.stage;visibleCount=12;render();if(activeStage)$('groups').scrollIntoView({behavior:'smooth',block:'start'});});
  $('groups').addEventListener('click',e=>{const el=e.target.closest('[data-market]');if(el){openDetail(data.coins.find(c=>c.market===el.dataset.market));return}if(e.target.closest('[data-more]')){visibleCount+=12;render();return}if(e.target.closest('[data-collapse]')){activeStage=null;render();$('overview').scrollIntoView({behavior:'smooth',block:'start'})}});
  $('close').onclick=()=>{$('detail').hidden=true;document.body.style.overflow='';history.replaceState(null,'',location.pathname);};
  $('sort').onchange=()=>{visibleCount=12;render()};
  fetch('rotation_position.json?'+Date.now()).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(d=>{const before=d.coins.length;d.coins=d.coins.filter(c=>!pegged.has(c.symbol));const removed=before-d.coins.length;d.covered=d.coins.length;d.total-=removed;d.excluded=(d.excluded||0)+removed;data=d;render();const target=location.hash.match(/^#coin-(KRW-[A-Z0-9]+)$/);if(target){const coin=data.coins.find(c=>c.market===target[1]);if(coin)openDetail(coin)};return fetch('https://api.upbit.com/v1/ticker/all?quote_currencies=KRW')}).then(r=>r.ok?r.json():[]).then(rows=>{trade=Object.fromEntries(rows.map(r=>[r.market,r.acc_trade_price_24h]));if($('sort').value==='trade')render()}).catch(e=>{if(!data){$('overview').textContent='순환매 데이터를 불러오지 못했습니다. 다음 업데이트 후 다시 확인해 주세요.';console.error(e)}});
})();
