import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

import kakao_notifier
import watchlist_store
from unified_dashboard import training_page, type_page


def f_candidate(stage="F2", position="상단"):
    return {"market":"KRW-PROM","name":"PROM","type":"F","score":8.8,"status":"매물대 도착","f_stage":stage,"f_stage_label":"매물대 도착" if stage=="F2" else "신고가 상승","f2_zone_position":position if stage=="F2" else None,"f2_zone_position_pct":76.0 if stage=="F2" else None,"price":9000,"entry":[8200,8500],"stop":7900,"targets":[9300],"action":"확인 대기","global_zone":{"lower":5.83,"upper":6.66}}


def test_f_training_matches_preview_and_explains_f2_thirds():
    page=training_page("F",{"snapshot_at":"2026-08-31T09:00:00+09:00"})
    for text in ("왜 글로벌 차트를 같이 봐야 하나","UPBIT · PROM/KRW","BINANCE · PROM/USDT","F형은 세 단계만 기억","F1 · 신고가 상승","F2 · 매물대 도착","F3 · 매물대 돌파","하단 · 0~33%","중앙 · 33~67%","상단 · 67~100%","성공 · 경고 · 실패 복기"):
        assert text in page


def test_f_candidate_page_shows_f2_position():
    page=type_page("F",{"snapshot_at":"2026-08-31T09:00:00+09:00","candidates":[f_candidate()]})
    assert "F2 · 매물대 도착 · 상단" in page
    assert "매물대 상단 (76%)" in page


def test_watchlist_records_forward_transition_and_notifier_deduplicates(tmp_path, monkeypatch):
    snapshots=tmp_path/"snapshots.json";store=tmp_path/"watchlist.json"
    store.write_text(json.dumps({"updated_at":"old","items":{"KRW-PROM":{"market":"KRW-PROM","first_seen":"old","last_seen":"old","daily_status":"관심 유지","archived":False,"archive_reason":None,"timeline":[],"four_hour":{"types":["F"],"f_stage":"F1"}}}},ensure_ascii=False),encoding="utf-8")
    snapshots.write_text(json.dumps([{"snapshot_at":"2026-08-31T09:00:00+09:00","candidates":[f_candidate()]}],ensure_ascii=False),encoding="utf-8")
    monkeypatch.setattr(watchlist_store,"SNAPSHOTS",snapshots);monkeypatch.setattr(watchlist_store,"STORE",store)
    state=watchlist_store.update();event=state["items"]["KRW-PROM"]["timeline"][-1]
    assert event["transition"]=="F1->F2" and event["alert"] is True
    pending=kakao_notifier.pending_f_transitions(state,set())
    assert len(pending)==1 and pending[0]["f2_zone_position"]=="상단"
    assert kakao_notifier.pending_f_transitions(state,{pending[0]["event_id"]})==[]
