#!/usr/bin/env python3
"""UPBIT KRW E형: 급락 뒤 0.382 기술적 반등 전용 스캐너.

E형은 추세 전환을 예측하지 않는다. 급락 파동의 저점이 하단 지지에서
멈춘 뒤 되돌림이 확인된 경우만 포착하고, 피보나치 0.382에서 전량 종료한다.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from box_screener import (
    fetch_daily_candles,
    fetch_minute_candles,
    fetch_universe,
    rounded_price,
)
from strategy_rules import reward_risk, tick_price


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUTPUT_JSON = OUT / "technical_rebound.json"
OUTPUT_CSV = OUT / "technical_rebound.csv"

MIN_DRAWDOWN_PCT = float(os.getenv("UPBIT_E_MIN_DRAWDOWN_PCT", "30"))
MIN_FAST_DROP_PCT = float(os.getenv("UPBIT_E_MIN_FAST_DROP_PCT", "15"))
MIN_VOLUME_RATIO = float(os.getenv("UPBIT_E_MIN_VOLUME_RATIO", "1.35"))
SUPPORT_TOLERANCE_PCT = float(os.getenv("UPBIT_E_SUPPORT_TOLERANCE_PCT", "6"))
STOP_BUFFER_PCT = float(os.getenv("UPBIT_E_STOP_BUFFER_PCT", "3"))
MAX_ENTRY_FIB = float(os.getenv("UPBIT_E_MAX_ENTRY_FIB", "0.236"))
MAX_ENTRY_ABOVE_LOW_PCT = float(os.getenv("UPBIT_E_MAX_ENTRY_ABOVE_LOW_PCT", "8"))
TARGET_FIB = 0.382
MIN_RR = float(os.getenv("UPBIT_E_MIN_RR", "1.0"))
MAX_RESULTS = int(os.getenv("UPBIT_E_MAX_RESULTS", "30"))
WORKERS = max(1, min(3, int(os.getenv("UPBIT_E_WORKERS", "3"))))


def _pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0 if b > 0 else 0.0


def _support_evidence(daily: pd.DataFrame, crash_low: float, low_pos: int) -> tuple[bool, float, str]:
    """과거 저점 군집 또는 하단 거래 집중 가격과의 근접도를 확인한다."""
    history = daily.iloc[max(0, low_pos - 240) : max(0, low_pos - 5)].copy()
    if len(history) < 35:
        return False, 99.0, "과거 하단 자료 부족"

    tolerance = SUPPORT_TOLERANCE_PCT / 100.0
    lows = history["Low"].to_numpy(dtype=float)
    near_lows = lows[np.abs(lows / crash_low - 1.0) <= tolerance]
    prior_low_distance = float(np.min(np.abs(lows / crash_low - 1.0)) * 100.0)

    typical = ((history["High"] + history["Low"] + history["Close"]) / 3.0).to_numpy(dtype=float)
    volume = history["Volume"].to_numpy(dtype=float)
    positive = typical[typical > 0]
    profile_distance = 99.0
    if len(positive) >= 20 and float(volume.sum()) > 0:
        lo, hi = float(np.quantile(positive, 0.02)), float(np.quantile(positive, 0.70))
        if hi > lo:
            edges = np.linspace(lo, hi, 25)
            bucket = np.clip(np.digitize(typical, edges) - 1, 0, len(edges) - 2)
            weights = np.bincount(bucket, weights=volume, minlength=len(edges) - 1)
            nodes = [(edges[i] + edges[i + 1]) / 2.0 for i in np.argsort(weights)[-5:]]
            profile_distance = min(abs(node / crash_low - 1.0) * 100.0 for node in nodes)

    if len(near_lows) >= 2:
        return True, prior_low_distance, f"과거 하단 저점 {len(near_lows)}회 군집"
    if profile_distance <= SUPPORT_TOLERANCE_PCT:
        return True, profile_distance, "하단 거래집중 매물대 근접"
    # 장기 최저권의 투매도 별도 하단으로 인정하되 거래량 확인은 상위 규칙에서 강제한다.
    if crash_low <= float(history["Low"].quantile(0.05)):
        return True, prior_low_distance, "장기 최저 5% 하단 투매"
    return False, min(prior_low_distance, profile_distance), "핵심 하단과 거리 큼"


def _last_crash_leg(daily: pd.DataFrame) -> Optional[dict]:
    """최근 저점과 그 전에 존재한 마지막 유효 고점으로 급락 파동을 고정한다."""
    view = daily.tail(100).copy()
    if len(view) < 60:
        return None
    # E형은 오래된 바닥이 아니라 최근 10개 완성 일봉 안의 투매를 대상으로 한다.
    low_window = view.tail(10)
    low_label = low_window["Low"].idxmin()
    low_pos = int(view.index.get_loc(low_label))
    if low_pos < 12:
        return None
    crash_low = float(view.iloc[low_pos]["Low"])

    pre = view.iloc[max(0, low_pos - 45) : low_pos - 1]
    if len(pre) < 10:
        return None
    broad_high = float(pre["High"].max())
    total_drawdown = (1.0 - crash_low / broad_high) * 100.0
    if total_drawdown < MIN_DRAWDOWN_PCT:
        return None

    # 피보나치는 45일 최고점이 아니라 투매 직전 마지막 유효 반등고점에 긋는다.
    # 그래야 장기 하락 전체가 아닌 '마지막 급락 파동의 정상 되돌림 0.382'가 된다.
    highs = view["High"].to_numpy(dtype=float)
    pivot_positions = []
    for i in range(max(2, low_pos - 30), low_pos - 2):
        if highs[i] >= highs[i - 2 : i].max() and highs[i] >= highs[i + 1 : i + 3].max():
            if (1.0 - crash_low / highs[i]) * 100.0 >= MIN_FAST_DROP_PCT:
                pivot_positions.append(i)
    high_pos = pivot_positions[-1] if pivot_positions else int(
        view.iloc[max(0, low_pos - 12) : low_pos - 2]["High"].to_numpy().argmax()
    ) + max(0, low_pos - 12)
    high_label = view.index[high_pos]
    swing_high = float(view.iloc[high_pos]["High"])
    fast_drop = (1.0 - crash_low / swing_high) * 100.0
    if fast_drop < MIN_FAST_DROP_PCT:
        return None

    crash_slice = view.iloc[max(high_pos, low_pos - 5) : low_pos + 1]
    base_volume = float(view.iloc[max(0, high_pos - 30) : high_pos]["Volume"].median())
    crash_volume = float(crash_slice["Volume"].max())
    volume_ratio = crash_volume / base_volume if base_volume > 0 else 0.0
    if volume_ratio < MIN_VOLUME_RATIO:
        return None

    absolute_low_pos = len(daily) - len(view) + low_pos
    support_ok, support_distance, support_reason = _support_evidence(
        daily, crash_low, absolute_low_pos
    )
    if not support_ok:
        return None

    return {
        "high": swing_high,
        "low": crash_low,
        "high_at": str(high_label),
        "low_at": str(low_label),
        "drawdown_pct": total_drawdown,
        "fast_drop_pct": fast_drop,
        "volume_ratio": volume_ratio,
        "support_distance_pct": support_distance,
        "support_reason": support_reason,
    }


def _four_hour_confirmation(frame: pd.DataFrame, crash_low: float) -> dict:
    recent = frame.tail(12).copy()
    if len(recent) < 5:
        return {"confirmed": False, "reason": "4시간봉 자료 부족", "close": None}
    last = recent.iloc[-1]
    last_close = float(last["Close"])
    recent_low = float(recent["Low"].min())
    body = abs(float(last["Close"]) - float(last["Open"]))
    lower_wick = min(float(last["Open"]), float(last["Close"])) - float(last["Low"])
    bullish = float(last["Close"]) > float(last["Open"])
    reclaimed = last_close >= recent_low * 1.02
    no_new_low = float(recent.tail(2)["Low"].min()) > recent_low * 0.998 or recent.index[-1] != recent["Low"].idxmin()
    wick_reversal = lower_wick >= max(body * 0.7, last_close * 0.004)
    confirmed = reclaimed and no_new_low and (bullish or wick_reversal)
    signals = []
    if bullish:
        signals.append("4H 양봉 전환")
    if wick_reversal:
        signals.append("4H 아래꼬리")
    if reclaimed:
        signals.append("투매저점 2% 회복")
    return {
        "confirmed": confirmed,
        "reason": " · ".join(signals) if signals else "4H 반등 확인 전",
        "close": last_close,
        "recent_low": recent_low,
        "low_held": recent_low >= crash_low * 0.985,
    }


def analyze_market(row: pd.Series, daily: pd.DataFrame, four_hour: pd.DataFrame) -> Optional[dict]:
    leg = _last_crash_leg(daily)
    if not leg:
        return None
    high, low = float(leg["high"]), float(leg["low"])
    span = high - low
    fib236 = low + span * MAX_ENTRY_FIB
    target = low + span * TARGET_FIB
    live = float(row.get("CurrentPrice") or daily["Close"].iloc[-1])
    confirm = _four_hour_confirmation(four_hour, low)

    stop = tick_price(low * (1.0 - STOP_BUFFER_PCT / 100.0), "down")
    entry_low = tick_price(low * 1.01, "up")
    # 대폭락에서는 0.236 자체도 저점에서 너무 멀 수 있다. 하단 반등 매매답게
    # 진입 상한을 투매저점 +8%와 0.236 중 낮은 값으로 제한한다.
    entry_high = tick_price(min(fib236, low * (1.0 + MAX_ENTRY_ABOVE_LOW_PCT / 100.0)), "down")
    target_price = tick_price(target, "down")
    planned_entry = (entry_low + entry_high) / 2.0
    rr = reward_risk(planned_entry, stop, target_price)
    progress = (live - low) / span if span > 0 else 1.0
    if rr < MIN_RR:
        return None

    if live < low or not bool(confirm.get("low_held", True)):
        status, action = "E실패", "추격 금지"
        missing = ["투매저점 재형성 대기"]
    elif progress >= TARGET_FIB:
        status, action = "E4 0.382 도달", "추격 금지"
        missing = ["기술적 반등 종료 · 신규진입 금지"]
    elif confirm["confirmed"] and progress <= MAX_ENTRY_FIB and rr >= MIN_RR:
        status, action = "E2 반등 확인", "진입 검토"
        missing = []
    elif confirm["confirmed"]:
        status, action = "E3 반등 진행", "추격 금지"
        missing = ["진입구간 통과 · 0.382 전량청산만 대기"]
    else:
        status, action = "E1 하단 도달", "확인 대기"
        missing = ["4시간봉 양봉·아래꼬리·저점 2% 회복 확인"]

    score = 0.0
    score += min(2.5, (leg["drawdown_pct"] - MIN_DRAWDOWN_PCT) / 15.0 + 1.0)
    score += min(2.0, leg["fast_drop_pct"] / 15.0)
    score += min(2.0, leg["volume_ratio"] / 1.5)
    score += 1.5 if leg["support_distance_pct"] <= 3 else 1.0
    score += 1.5 if confirm["confirmed"] else 0.0
    score += 0.5 if rr >= 1.5 else 0.0

    return {
        "market": str(row["Code"]),
        "name": str(row["Name"]),
        "type": "E",
        "status": status,
        "action": action,
        "score": round(min(score, 10.0), 1),
        "price": rounded_price(live),
        "entry": [rounded_price(entry_low), rounded_price(entry_high)],
        "stop": rounded_price(stop),
        "targets": [rounded_price(target_price)],
        "rr": round(rr, 2),
        "flow": "급락 추세 속 1회성 기술적 반등",
        "reason": f"{leg['support_reason']} · 낙폭 {leg['drawdown_pct']:.1f}% · 투매거래량 {leg['volume_ratio']:.1f}배 · {confirm['reason']}",
        "missing": missing,
        "fib": {
            "high": rounded_price(high), "low": rounded_price(low),
            "entry_limit_0.236": rounded_price(fib236),
            "full_exit_0.382": rounded_price(target_price),
            "high_at": leg["high_at"], "low_at": leg["low_at"],
        },
        "metrics": {
            "drawdown_pct": round(leg["drawdown_pct"], 2),
            "fast_drop_pct": round(leg["fast_drop_pct"], 2),
            "capitulation_volume_ratio": round(leg["volume_ratio"], 2),
            "support_distance_pct": round(leg["support_distance_pct"], 2),
            "rebound_progress_fib": round(progress, 3),
        },
        "exit_rule": "피보나치 0.382 전량청산 · 추세전환 기대 금지",
        "invalidation": "투매저점 3% 하단 이탈 시 종료 · 물타기 금지",
    }


def scan() -> list[dict]:
    universe = fetch_universe()
    records: list[dict] = []

    def inspect(row: pd.Series) -> Optional[dict]:
        try:
            daily = fetch_daily_candles(str(row["Code"]), 260)
            if len(daily) < 120:
                return None
            leg = _last_crash_leg(daily)
            if not leg:
                return None
            four_hour = fetch_minute_candles(str(row["Code"]), 240, 120)
            result = analyze_market(row, daily, four_hour)
            return result if result and result["status"] != "E실패" else None
        except Exception as exc:  # 한 종목 장애가 전체 E형 스캔을 막지 않는다.
            print(f"E scan skip {row.get('Code')}: {exc}")
            return None

    rows = [row for _, row in universe.iterrows()]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(inspect, row): str(row["Code"]) for row in rows}
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            if result:
                records.append(result)
            if index % 25 == 0 or index == len(futures):
                print(f"E scan progress {index}/{len(futures)} · candidates {len(records)}")
    action_rank = {"진입 검토": 0, "확인 대기": 1, "진입가 대기": 2, "추격 금지": 3}
    records.sort(key=lambda r: (action_rank.get(r["action"], 9), -float(r["score"]), -float(r["rr"])))
    return records[:MAX_RESULTS]


def write(records: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    flat = []
    for row in records:
        flat.append({
            "종목": row["market"], "단계": row["status"], "현재판단": row["action"],
            "점수": row["score"], "현재가": row["price"], "진입하단": row["entry"][0],
            "진입상단_0.236": row["entry"][1], "손절": row["stop"],
            "0.382전량청산": row["targets"][0], "손익비": row["rr"], "근거": row["reason"],
        })
    pd.DataFrame(flat).to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")


def main() -> None:
    records = scan()
    write(records)
    print(f"E형 기술적 반등: {len(records)}개 · {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
