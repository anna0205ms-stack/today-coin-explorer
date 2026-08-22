#!/usr/bin/env python3
"""GitHub Actions 4시간봉 스캔의 재시도와 중복 실행을 관리한다."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


KST = timezone(timedelta(hours=9))
CLOSE_HOURS = (1, 5, 9, 13, 17, 21)
STATE_PATH = Path("history/schedule_state.json")


def latest_closed_slot(now: datetime | None = None) -> datetime:
    current = (now or datetime.now(KST)).astimezone(KST)
    candidates = []
    for day_offset in (0, -1):
        day = (current + timedelta(days=day_offset)).date()
        for hour in CLOSE_HOURS:
            slot = datetime(day.year, day.month, day.day, hour, tzinfo=KST)
            if slot <= current:
                candidates.append(slot)
    return max(candidates)


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def slot_key(slot: datetime) -> str:
    return slot.isoformat(timespec="seconds")


def check(force: bool = False) -> int:
    slot = latest_closed_slot()
    completed = read_state().get("last_completed_slot")
    should_run = force or completed != slot_key(slot)
    reason = "manual" if force else ("new_slot" if should_run else "already_completed")

    # GitHub Actions의 GITHUB_OUTPUT에 그대로 붙일 수 있는 형식이다.
    print(f"should_run={'true' if should_run else 'false'}")
    print(f"slot={slot_key(slot)}")
    print(f"reason={reason}")
    return 0


def mark(slot_text: str | None = None) -> int:
    slot = datetime.fromisoformat(slot_text) if slot_text else latest_closed_slot()
    slot = slot.astimezone(KST)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "last_completed_slot": slot_key(slot),
        "completed_at": datetime.now(KST).isoformat(timespec="seconds"),
    }
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"완료 처리: {state['last_completed_slot']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--force", action="store_true")
    mark_parser = subparsers.add_parser("mark")
    mark_parser.add_argument("--slot")
    args = parser.parse_args()

    if args.command == "check":
        return check(force=args.force)
    return mark(slot_text=args.slot)


if __name__ == "__main__":
    raise SystemExit(main())
