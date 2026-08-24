#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "history" / "binance" / "schedule_state.json"


def slot(now: datetime | None = None) -> datetime:
    now = now or datetime.now(KST)
    anchors = [1, 5, 9, 13, 17, 21]
    candidates = [now.replace(hour=h, minute=0, second=0, microsecond=0) for h in anchors if now.hour >= h]
    if candidates:
        return candidates[-1]
    prev = now - timedelta(days=1)
    return prev.replace(hour=21, minute=0, second=0, microsecond=0)


def read_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--force", action="store_true")
    m = sub.add_parser("mark")
    m.add_argument("--slot", required=True)
    a = p.parse_args()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    if a.cmd == "check":
        s = slot().isoformat()
        done = read_state().get("last_completed_slot") == s
        print(f"slot={s}")
        print(f"should_run={'true' if a.force or not done else 'false'}")
    else:
        STATE.write_text(json.dumps({"last_completed_slot": a.slot, "completed_at": datetime.now(KST).isoformat(timespec="seconds")}, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
