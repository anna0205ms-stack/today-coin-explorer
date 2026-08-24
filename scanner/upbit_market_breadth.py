#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from box_screener import fetch_universe

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "upbit_market_breadth.json"
KST = timezone(timedelta(hours=9))


def main() -> None:
    universe = fetch_universe()
    changes = universe["ChangeRate24h"].dropna().astype(float)
    positive = float((changes > 0).mean() * 100.0) if len(changes) else None
    median = float(changes.median()) if len(changes) else None
    payload = {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "source": "UPBIT KRW scanner universe",
        "sample_count": int(len(changes)),
        "positive_ratio_24h_pct": round(positive, 1) if positive is not None else None,
        "median_change_24h_pct": round(median, 2) if median is not None else None,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
