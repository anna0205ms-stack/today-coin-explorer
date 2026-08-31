#!/usr/bin/env python3
"""일봉 관심종목과 4시간봉 유형 변화를 삭제 없이 누적한다."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];SNAPSHOTS=ROOT/"history"/"snapshots.json";STORE=ROOT/"history"/"watchlist.json"
def read(path,default):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():return default
    return json.loads(path.read_text(encoding="utf-8"))
def update():
    snapshots=read(SNAPSHOTS,[])
    if not snapshots:return {}
    snap=snapshots[-1];stamp=snap.get("snapshot_at");state=read(STORE,{"updated_at":None,"items":{}});items=state.setdefault("items",{});current={}
    for row in snap.get("candidates",[]):
        market=row.get("market")
        if market:current.setdefault(market,[]).append({k:v for k,v in row.items() if k!="charts"})
    for market,rows in current.items():
        item=items.setdefault(market,{"market":market,"first_seen":stamp,"last_seen":stamp,"daily_status":"신규 관심","archived":False,"archive_reason":None,"timeline":[]})
        was_new=item.get("last_seen")==stamp and not item.get("four_hour");item["last_seen"]=stamp;item["daily_status"]="신규 관심" if was_new else "관심 유지";item["archived"]=False;item["archive_reason"]=None
        types=sorted({r.get("type") for r in rows if r.get("type")});best=sorted(rows,key=lambda r:({"진입 검토":0,"확인 대기":1,"진입가 대기":2,"추격 금지":3}.get(r.get("action"),9),-float(r.get("score") or 0)))[0]
        previous=item.get("four_hour",{});prev_types=previous.get("types",[])
        f_row=next((r for r in rows if r.get("type")=="F"),None);prev_stage=previous.get("f_stage");new_stage=f_row.get("f_stage") if f_row else None
        item["four_hour"]={"types":types,"primary_type":best.get("type"),"action":best.get("action"),"status":best.get("status"),"score":best.get("score"),"price":best.get("price"),"entry":best.get("entry"),"stop":best.get("stop"),"last_seen":stamp,"f_stage":new_stage,"f_stage_label":f_row.get("f_stage_label") if f_row else None,"f2_zone_position":f_row.get("f2_zone_position") if f_row else None}
        invalid=all(isinstance(r.get("price"),(int,float)) and isinstance(r.get("stop"),(int,float)) and r["price"]<r["stop"] for r in rows)
        if invalid:item["archived"]=True;item["archive_reason"]="구조 무효선 이탈";item["daily_status"]="구조 무효"
        forward=(prev_stage,new_stage) in {("F1","F2"),("F2","F3")}
        note=f"{prev_stage} → {new_stage} · {f_row.get('f_stage_label')}" if forward else "유형 전환" if prev_types and prev_types!=types else "4시간봉 갱신"
        if forward and f_row.get("f2_zone_position"):note+=f" · 매물대 {f_row.get('f2_zone_position')}"
        event={"at":stamp,"types":types,"action":best.get("action"),"price":best.get("price"),"score":best.get("score"),"note":note,"transition":f"{prev_stage}->{new_stage}" if forward else None,"alert":forward,"f_stage":new_stage,"f2_zone_position":f_row.get("f2_zone_position") if f_row else None}
        if not item["timeline"] or item["timeline"][-1].get("at")!=stamp:item["timeline"].append(event)
        item["timeline"]=item["timeline"][-60:]
    for market,item in items.items():
        if market not in current and not item.get("archived"):
            item["daily_status"]="조건 약화";previous=item.get("four_hour",{});previous["action"]="조건 약화";previous["last_checked"]=stamp;item["four_hour"]=previous
            if not item["timeline"] or item["timeline"][-1].get("at")!=stamp:item["timeline"].append({"at":stamp,"types":previous.get("types",[]),"action":"조건 약화","price":previous.get("price"),"score":previous.get("score"),"note":"현재 스캔 미포착·관심 유지"})
    state["updated_at"]=stamp;STORE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8");return state
if __name__=="__main__":
    state=update();print(f'{STORE} · {len(state.get("items",{}))} markets')
