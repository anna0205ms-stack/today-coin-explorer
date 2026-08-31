const btcScenarioUsd=value=>typeof value==="number"?`$${value.toLocaleString(undefined,{maximumFractionDigits:0})}`:"-";
const btcScenarioRange=(low,high)=>`${btcScenarioUsd(low)}~${btcScenarioUsd(high)}`;

function renderBtcScenario(data){
  const levels=data.levels||{};
  const up=document.getElementById("upScenario"),down=document.getElementById("downScenario");
  const set=(id,value)=>{const node=document.getElementById(id);if(node)node.textContent=value};
  set("activeScenario",`현재 활성 · ${data.label||"확인 중"}`);
  set("upConfirm",btcScenarioUsd(levels.up_confirm));
  set("upRetest",btcScenarioRange(levels.retest_low,levels.retest_high));
  set("upTarget1",btcScenarioUsd(levels.up_target1));
  set("upTarget2",btcScenarioUsd(levels.up_target2));
  set("upInvalid",`${btcScenarioUsd(levels.up_invalid)} 이탈`);
  set("downConfirm",btcScenarioUsd(levels.down_confirm));
  set("downRetest",btcScenarioRange(levels.retest_low,levels.retest_high));
  set("downTarget1",btcScenarioUsd(levels.down_target1));
  set("downTarget2",btcScenarioUsd(levels.down_target2));
  set("downInvalid",`${btcScenarioUsd(levels.down_invalid)} 회복`);
  set("upAltAction",data.family==="UP"?data.alt_action:"상승 확인 전 추격 금지");
  set("downAltAction",data.family==="DOWN"?`${data.alt_action} · 최종 구조선 ${btcScenarioUsd(levels.structure_invalid)}`:"조정 확인 전 예단 금지");
  [up,down].forEach(node=>node?.classList.remove("active-ready","active-confirmed"));
  set("upScenarioState",data.family==="UP"?`현재 · ${data.label}`:"대기");
  set("downScenarioState",data.family==="DOWN"?`현재 · ${data.label}`:"대기");
  const active=data.family==="UP"?up:data.family==="DOWN"?down:null;
  if(active)active.classList.add(String(data.code||"").endsWith("READY")?"active-ready":"active-confirmed");
}

fetch("btc_scenario.json",{cache:"no-store"})
  .then(response=>{if(!response.ok)throw new Error(`BTC scenario ${response.status}`);return response.json()})
  .then(renderBtcScenario)
  .catch(error=>{console.error(error);const node=document.getElementById("activeScenario");if(node)node.textContent="현재 활성 · 데이터 확인 필요"});
