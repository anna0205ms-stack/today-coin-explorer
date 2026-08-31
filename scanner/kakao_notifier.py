#!/usr/bin/env python3
"""F형 전진 단계(F1→F2, F2→F3)를 한 번만 카카오 나에게 보내기한다."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "history" / "watchlist.json"
STATE = ROOT / "history" / "notification_state.json"


def read(path: Path, default):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def pending_f_transitions(watchlist: dict, sent: set[str], markets: set[str] | None = None) -> list[dict]:
    events = []
    for market, item in (watchlist.get("items") or {}).items():
        if markets and market not in markets:
            continue
        for event in item.get("timeline") or []:
            if event.get("transition") not in {"F1->F2", "F2->F3"}:
                continue
            event_id = f'{market}:{event.get("transition")}:{event.get("at")}'
            if event_id not in sent:
                events.append({**event, "market": market, "event_id": event_id})
    return sorted(events, key=lambda row: row.get("at") or "")


def post(url: str, data: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, data=urlencode(data).encode(), headers=headers), timeout=20) as response:  # noqa: S310
        return json.loads(response.read().decode())


def main() -> None:
    key, refresh = os.getenv("KAKAO_REST_API_KEY"), os.getenv("KAKAO_REFRESH_TOKEN")
    if not key or not refresh:
        print("카카오 인증정보 없음 · 알림 건너뜀")
        return
    state = read(STATE, {"sent_f_transitions": []})
    sent = set(state.get("sent_f_transitions") or [])
    raw_markets = os.getenv("KAKAO_WATCH_MARKETS", "").strip()
    markets = {value.strip().upper() for value in raw_markets.split(",") if value.strip()} or None
    events = pending_f_transitions(read(WATCHLIST, {}), sent, markets)
    if not events:
        print("새 F형 단계전환 알림 없음")
        return
    token_data = {"grant_type": "refresh_token", "client_id": key, "refresh_token": refresh}
    if os.getenv("KAKAO_CLIENT_SECRET"):
        token_data["client_secret"] = os.environ["KAKAO_CLIENT_SECRET"]
    access = post("https://kauth.kakao.com/oauth/token", token_data)["access_token"]
    for event in events:
        position = f" · F2 매물대 {event['f2_zone_position']}" if event.get("f2_zone_position") else ""
        text = f"[오코탐 F형] {event['market']} {event['transition'].replace('->', ' → ')}{position}\n가격 {event.get('price')} · {event.get('at')}"
        template = {"object_type": "text", "text": text, "link": {"web_url": "https://anna0205ms-stack.github.io/today-coin-explorer/type_f.html", "mobile_web_url": "https://anna0205ms-stack.github.io/today-coin-explorer/type_f.html"}}
        post("https://kapi.kakao.com/v2/api/talk/memo/default/send", {"template_object": json.dumps(template, ensure_ascii=False)}, access)
        sent.add(event["event_id"])
    state["sent_f_transitions"] = sorted(sent)[-500:]
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"F형 단계전환 카카오 알림 {len(events)}건")


if __name__ == "__main__":
    main()
