#!/usr/bin/env python3
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scanner import unified_dashboard as up
from scanner_binance.binance_spot_scanner import fetch_klines

OUT = ROOT / "outputs" / "binance"
LATEST = OUT / "latest.json"
HISTORY = ROOT / "history" / "binance" / "snapshots.json"

D_STAGE_LABELS = {
    "D0": ("후보", "바닥 압축과 재탈환 전 단계"),
    "D1": ("재탈환", "핵심 매물대 하단 재탈환"),
    "D2": ("리테스트 확인", "재탈환선 방어와 재지지 확인"),
    "D3": ("실행", "상단 돌파 또는 실행 조건 확인"),
    "D4": ("확장", "돌파 뒤 상승 확장 진행"),
    "D-W": ("경고", "재탈환 구조가 흔들리는 단계"),
    "D-F": ("실패", "핵심 구조 이탈로 가설 폐기"),
}


def read_json(path: Path, default):
    try:
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            return copy.deepcopy(default)
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(default)


def completed_slot(value: str | None) -> tuple[str, str]:
    if not value:
        return "기록 전", "-"
    try:
        dt = datetime.fromisoformat(value)
        if dt.second >= 50 or dt.minute == 59:
            dt += timedelta(seconds=1)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except ValueError:
        return str(value)[:10], str(value)[11:16] or "-"


def adapt_latest(raw: dict) -> dict:
    snap = copy.deepcopy(raw or {})
    generated = str(snap.get("generated_at") or "")
    date, time = completed_slot(snap.get("basis_4h_end") or generated)
    regime = snap.get("market_regime") or {}
    snap["snapshot_at"] = generated
    snap["date"] = date
    snap["time"] = time
    snap["btc"] = copy.deepcopy(regime.get("btc") or {})
    snap["alt_policy"] = {"size_pct": regime.get("alt_entry_limit_pct")}
    snap.setdefault("candidates", [])
    snap.setdefault("counts", {})
    return snap


def chart_rows(rows: list[dict]) -> list[list[float]]:
    return [
        [
            row.get("close_time") or row.get("open_time") or 0,
            row.get("open"), row.get("high"), row.get("low"), row.get("close"), row.get("volume"),
        ]
        for row in rows
        if all(isinstance(row.get(key), (int, float)) for key in ("open", "high", "low", "close", "volume"))
    ]


def enrich_candidate_charts(snapshot: dict) -> bool:
    """UPBIT 후보 페이지와 같은 일봉/4H 상세 차트를 Binance API만으로 채운다."""
    candidates = snapshot.get("candidates") or []
    long_markets = {item.get("market") for item in candidates if item.get("type") in {"F", "G", "H"}}
    missing_markets = list(dict.fromkeys(
        str(row.get("market")) for row in candidates if row.get("market")
        and (not (row.get("charts") or {}).get("day") or not (row.get("charts") or {}).get("4h"))
    ))

    def load_charts(market):
        try:
            day = fetch_klines(market, "1d", 400 if market in long_markets else 80)
            h4 = fetch_klines(market, "4h", 80)
            return {"day": chart_rows(day), "4h": chart_rows(h4)}
        except Exception as exc:
            print(f"BINANCE chart enrichment skipped {market}: {exc}")
            return {"day": [], "4h": []}

    with ThreadPoolExecutor(max_workers=4) as pool:
        cache = dict(zip(missing_markets, pool.map(load_charts, missing_markets)))
    changed = False
    for row in candidates:
        market = str(row.get("market") or "")
        if not market:
            continue
        charts = row.get("charts") or {}
        if not charts.get("day") or not charts.get("4h"):
            row["charts"] = cache[market]
            changed = True
        if row.get("type") == "D":
            stage = str(row.get("d_stage") or row.get("stage") or "D0")
            label, reason = D_STAGE_LABELS.get(stage, ("관찰", "D형 구조 확인"))
            if not row.get("d_stage"):
                row["d_stage"] = stage
                changed = True
            if not row.get("d_stage_label"):
                row["d_stage_label"] = label
                changed = True
            if not row.get("d_stage_reason"):
                row["d_stage_reason"] = reason
                changed = True
    return changed


def adapt_history(records: list, current: dict) -> list[dict]:
    out: list[dict] = []
    for raw in records or []:
        item = copy.deepcopy(raw or {})
        generated = str(item.get("generated_at") or item.get("snapshot_at") or "")
        date, time = completed_slot(item.get("basis_4h_end") or generated)
        item["snapshot_at"] = generated
        item.setdefault("date", date)
        item.setdefault("time", time)
        regime = item.get("market_regime") or {}
        item.setdefault("btc", copy.deepcopy(regime.get("btc") or {}))
        item.setdefault("alt_policy", {"size_pct": regime.get("alt_entry_limit_pct")})
        if not item.get("candidates") and item.get("top"):
            item["candidates"] = copy.deepcopy(item.get("top") or [])
        item.setdefault("candidates", [])
        item.setdefault("counts", {})
        out.append(item)

    if current.get("snapshot_at"):
        full = copy.deepcopy(current)
        for row in full.get("candidates", []):
            row.pop("charts", None)
        if out and str(out[-1].get("generated_at") or out[-1].get("snapshot_at")) == str(current.get("generated_at") or current.get("snapshot_at")):
            out[-1] = full
        else:
            out.append(full)
    return out[-180:]


def synthetic_watch(snapshot: dict) -> dict:
    items = {}
    for row in snapshot.get("candidates", []):
        market = str(row.get("market") or "")
        if not market:
            continue
        existing = items.setdefault(market, {
            "market": market,
            "first_seen": snapshot.get("snapshot_at"),
            "last_seen": snapshot.get("snapshot_at"),
            "archived": False,
            "daily_status": row.get("action"),
            "four_hour": {},
            "timeline": [],
        })
        types = set(existing["four_hour"].get("types") or [])
        if row.get("type"):
            types.add(row.get("type"))
        old_score = float(existing["four_hour"].get("score") or -1)
        new_score = float(row.get("score") or 0)
        if new_score >= old_score:
            existing["four_hour"].update({
                "price": row.get("price"), "entry": row.get("entry"), "stop": row.get("stop"),
                "targets": row.get("targets"), "score": row.get("score"), "rr": row.get("rr"),
                "action": row.get("action"), "last_seen": snapshot.get("snapshot_at"),
            })
        existing["four_hour"]["types"] = sorted(types)
        existing["timeline"].append({
            "at": snapshot.get("snapshot_at"), "types": [row.get("type")],
            "action": row.get("action"), "note": row.get("reason") or "스캔 후보",
        })
    return {"items": items}


def binanceize(page: str) -> str:
    replacements = [
        ("upbitPins", "binancePins"),
        ("업비트 신고가 상승", "BINANCE 최근 200일 고점권 상승"),
        ("신규상장 신고가", "최근 200일 고점권 상승"),
        ("업비트 KRW", "BINANCE SPOT USDT"),
        ("업비트 차트", "BINANCE 차트"),
        ("업비트에서", "BINANCE에서"),
        ("업비트", "BINANCE"),
        ('src="assets/', 'src="../assets/'),
        ('href="index.html">메인 대시보드', 'href="../index.html">메인 대시보드'),
    ]
    for old, new in replacements:
        page = page.replace(old, new)
    return page



def binance_main_page(snapshot: dict, btc: dict) -> str:
    """UPBIT 전체 스캔과 동일한 레이아웃/구성을 그대로 사용하고 데이터만 Binance로 바꾼다."""
    return binanceize(up.main_page(snapshot, btc))

def render():
    OUT.mkdir(parents=True, exist_ok=True)
    up.write_tracker_asset(OUT)
    raw = read_json(LATEST, {"generated_at": "", "basis_4h_end": "", "market_regime": {}, "counts": {}, "candidates": []})
    snapshot = adapt_latest(raw)
    if enrich_candidate_charts(snapshot):
        persisted = copy.deepcopy(snapshot)
        persisted.pop("snapshot_at", None)
        persisted.pop("date", None)
        persisted.pop("time", None)
        persisted.pop("btc", None)
        persisted.pop("alt_policy", None)
        LATEST.write_text(json.dumps(persisted, ensure_ascii=False, indent=2), encoding="utf-8")

    history = adapt_history(read_json(HISTORY, []), snapshot)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    watch = synthetic_watch(snapshot)
    btc = snapshot.get("btc") or {}

    pages: dict[str, str] = {
        "index.html": binance_main_page(snapshot, btc),
        "scan.html": binance_main_page(snapshot, btc),
        "watchlist.html": binanceize(up.watchlist_page(watch, snapshot)),
        "history.html": binanceize(up.history_page(history)),
    }
    for key in ("A","B","C","D","E","F","G","H","P1","P2","P3","P4"):
        type_page = binanceize(up.type_page(key, snapshot))
        pages[f"type_{key.lower()}.html"] = type_page
        pages[f"{key.lower()}.html"] = type_page
        if key in "ABCDEF":
            pages[f"training_{key.lower()}.html"] = binanceize(up.training_page(key, snapshot))
    pages["training.html"] = pages["training_a.html"]

    # The shared templates embed the saved-plan data and load this Binance-local asset.
    # Fail the scan before publishing if either half of the tracker is missing.
    if not (OUT / "trade_tracker.js").is_file():
        raise RuntimeError("BINANCE tracker script was not generated")
    for name in ("index.html", "scan.html", "watchlist.html"):
        if "window.OKO_TRACK_DATA=" not in pages[name] or 'src="trade_tracker.js' not in pages[name]:
            raise RuntimeError(f"BINANCE tracker is incomplete in {name}")

    for name, content in pages.items():
        (OUT / name).write_text(content, encoding="utf-8")
    print("BINANCE pages now use UPBIT templates:", ", ".join(pages))


if __name__ == "__main__":
    render()
