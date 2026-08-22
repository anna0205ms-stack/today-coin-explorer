"""매매일지의 진입성향 태그별 성과를 누적·요약한다."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def aggregate_performance(rows: Iterable[dict]) -> List[Dict[str, object]]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        if str(row.get("status", "완료")) != "완료":
            continue
        groups[str(row.get("entry_signature") or "미분류")].append(row)

    result: List[Dict[str, object]] = []
    for tag, trades in groups.items():
        pnls = [_float(row.get("net_pnl_krw")) for row in trades]
        capitals = [_float(row.get("deployed_capital_krw")) for row in trades]
        returns = [pnl / capital for pnl, capital in zip(pnls, capitals) if capital > 0]
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        count = len(trades)
        result.append({
            "entry_signature": tag,
            "trades": count,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(len(wins) / count * 100.0, 2) if count else 0.0,
            "net_pnl_krw": round(sum(pnls), 2),
            "average_return_pct": round(sum(returns) / len(returns) * 100.0, 3) if returns else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
            "max_loss_krw": round(min(losses), 2) if losses else 0.0,
            "sample_status": "학습가능" if count >= 20 else f"표본부족({count}/20)",
        })
    return sorted(result, key=lambda row: (-int(row["trades"]), -float(row["net_pnl_krw"])))


def write_learning_outputs(output_dir: Path, summary: List[Dict[str, object]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "learning_by_signature.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "entry_signature", "trades", "wins", "losses", "win_rate_pct", "net_pnl_krw",
        "average_return_pct", "profit_factor", "max_loss_krw", "sample_status",
    ]
    with (output_dir / "learning_by_signature.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)
