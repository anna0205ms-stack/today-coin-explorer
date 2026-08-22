"""동일 코인 재진입과 일일 손실을 제한하는 실행 안전규칙."""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional


KST = timezone(timedelta(hours=9))
MAX_SAME_MARKET_ENTRIES = int(os.getenv("UPBIT_MAX_SAME_MARKET_ENTRIES", "2"))
COOLDOWN_MINUTES = int(os.getenv("UPBIT_REENTRY_COOLDOWN_MINUTES", "30"))
LOSS_COOLDOWN_MINUTES = int(os.getenv("UPBIT_LOSS_COOLDOWN_MINUTES", "120"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("UPBIT_MAX_CONSECUTIVE_LOSSES", "2"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("UPBIT_DAILY_LOSS_LIMIT_PCT", "2.0"))
TRADING_CAPITAL_KRW = float(os.getenv("UPBIT_TRADING_CAPITAL_KRW", "2000000"))


def _parse_time(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def load_trade_history(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate_overtrade(
    history: List[dict],
    *,
    market: str,
    now_kst: Optional[datetime] = None,
    trading_capital_krw: float = TRADING_CAPITAL_KRW,
) -> Dict[str, object]:
    """당일 동일 코인 진입·쿨다운·연속손실·손실한도를 검사한다."""
    now = (now_kst or datetime.now(KST)).astimezone(KST)
    today_rows: List[dict] = []
    for row in history:
        entered = _parse_time(str(row.get("entry_time_kst", "")))
        if entered and entered.date() == now.date():
            enriched = dict(row)
            enriched["_entry"] = entered
            enriched["_exit"] = _parse_time(str(row.get("exit_time_kst", "")))
            enriched["_pnl"] = _float(row.get("net_pnl_krw"))
            today_rows.append(enriched)

    market_rows = [row for row in today_rows if str(row.get("market", "")) == market]
    reasons: List[str] = []
    if len(market_rows) >= MAX_SAME_MARKET_ENTRIES:
        reasons.append(f"동일 코인 당일 {MAX_SAME_MARKET_ENTRIES}회 진입 한도 도달")

    exited = sorted((row for row in market_rows if row.get("_exit")), key=lambda row: row["_exit"])
    if exited:
        last = exited[-1]
        required = LOSS_COOLDOWN_MINUTES if last["_pnl"] < 0 else COOLDOWN_MINUTES
        elapsed = (now - last["_exit"]).total_seconds() / 60.0
        if elapsed < required:
            reasons.append(f"직전 청산 후 {required}분 쿨다운 미충족({elapsed:.0f}분 경과)")

    completed = sorted((row for row in today_rows if row.get("_exit")), key=lambda row: row["_exit"])
    consecutive_losses = 0
    for row in reversed(completed):
        if row["_pnl"] < 0:
            consecutive_losses += 1
        else:
            break
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        reasons.append(f"당일 {MAX_CONSECUTIVE_LOSSES}연속 손실 — 거래 종료")

    daily_pnl = sum(row["_pnl"] for row in completed)
    loss_limit = trading_capital_krw * DAILY_LOSS_LIMIT_PCT / 100.0
    if daily_pnl <= -loss_limit:
        reasons.append(f"당일 손실한도 -{DAILY_LOSS_LIMIT_PCT:.1f}% 도달")

    return {
        "status": "진입금지" if reasons else "진입가능",
        "reasons": reasons,
        "same_market_entries": len(market_rows),
        "daily_completed_trades": len(completed),
        "daily_realized_pnl_krw": round(daily_pnl, 2),
        "consecutive_losses": consecutive_losses,
    }
