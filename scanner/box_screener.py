# -*- coding: utf-8 -*-
"""업비트 KRW 급등 후 박스권 매수존·중심존·매도존 흐름 스캐너.

기능
- 업비트 KRW 마켓 페어 목록과 24시간 거래대금 수집
- 유의/주의 페어 및 저유동성 페어 제외
- 공개 Quotation API만 사용해 최근 일봉 수집(API 키 불필요)
- 완성된 일봉 기준 급등 → 조정 → 박스권 후보 점수화
- 실전 복기 규칙으로 1차 손익비·현재가 추격 여부·5분봉 확인 대기 판정
- 최신 CSV/JSON/Markdown, 종목별 JSON 및 HTML 차트 생성

실행
    python scanner/box_screener.py
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:  # 시세 스캔은 계속하고 HTML 차트만 생략한다.
    go = None
    make_subplots = None
from strategy_rules import LIVE_CHASE_PCT, MIN_TARGET1_RR, build_trade_plan, execution_gate
from timeframe_rules import multi_timeframe_gate
from overtrade_rules import evaluate_overtrade, load_trade_history
from trade_learning import aggregate_performance, write_learning_outputs


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
DAILY_DIR = OUTPUT_DIR / "daily"
CHART_DIR = OUTPUT_DIR / "charts"
LOG_DIR = OUTPUT_DIR / "logs"
INTRADAY_DIR = OUTPUT_DIR / "intraday"

API_BASE = "https://api.upbit.com/v1"
QUOTE_CURRENCY = os.getenv("UPBIT_QUOTE", "KRW").upper()
MIN_24H_TRADE_AMOUNT = float(os.getenv("UPBIT_MIN_24H_TRADE_AMOUNT", "3000000000"))
EXCLUDE_WARNING = os.getenv("UPBIT_EXCLUDE_WARNING", "true").lower() not in {"0", "false", "no"}
EXCLUDE_CAUTION = os.getenv("UPBIT_EXCLUDE_CAUTION", "true").lower() not in {"0", "false", "no"}
TARGET_COUNT = int(os.getenv("UPBIT_TARGET_COUNT", "30"))
MIN_OUTPUT_COUNT = int(os.getenv("UPBIT_MIN_OUTPUT_COUNT", "20"))
LOOKBACK_CANDLES = int(os.getenv("UPBIT_LOOKBACK_CANDLES", "400"))
MIN_DAILY_CANDLES = int(os.getenv("UPBIT_MIN_DAILY_CANDLES", "220"))
API_INTERVAL = float(os.getenv("UPBIT_API_INTERVAL", "0.13"))
TICKER_CHUNK_SIZE = 50
CANDLE_PAGE_SIZE = 200

KST = timezone(timedelta(hours=9))
HTTP_HEADERS = {"Accept": "application/json", "User-Agent": "upbit-box-scanner/5.0-learning-risk-control"}


class ScanError(RuntimeError):
    pass


def setup_logging() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    INTRADAY_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "latest.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, encoding="utf-8")],
        force=True,
    )


def chunks(items: Sequence[str], size: int) -> Iterable[List[str]]:
    for idx in range(0, len(items), size):
        yield list(items[idx : idx + size])


def _remaining_sec(header: str) -> Optional[int]:
    match = re.search(r"sec=(\d+)", header or "")
    return int(match.group(1)) if match else None


def upbit_get(path: str, params: Optional[dict] = None, *, attempts: int = 5, label: str = "업비트 API"):
    """업비트 Quotation API 호출. 429/5xx 재시도와 초당 제한을 보수적으로 지킨다."""
    url = f"{API_BASE}{path}"
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            query = urlencode(params or {})
            request_url = f"{url}?{query}" if query else url
            request = Request(request_url, headers=HTTP_HEADERS)
            with urlopen(request, timeout=30) as response:  # noqa: S310 - 고정된 공식 API 호스트
                payload = json.loads(response.read().decode("utf-8"))
                remaining = _remaining_sec(response.headers.get("Remaining-Req", ""))
            time.sleep(max(API_INTERVAL, 0.22 if remaining is not None and remaining <= 2 else API_INTERVAL))
            return payload
        except HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt < attempts:
                retry_after = float(exc.headers.get("Retry-After", "1"))
                time.sleep(max(retry_after, 1.0) * attempt)
                continue
            logging.warning("%s 실패 (%d/%d): HTTP %s", label, attempt, attempts, exc.code)
            if attempt < attempts:
                time.sleep(min(2 ** attempt, 12))
        except URLError as exc:
            last_exc = exc
            logging.warning("%s 실패 (%d/%d): %s", label, attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(min(2 ** attempt, 12))
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logging.warning("%s 실패 (%d/%d): %s", label, attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(min(2 ** attempt, 12))
    raise ScanError(f"{label} 최종 실패: {last_exc}")


def _event_flags(item: dict) -> Tuple[bool, List[str]]:
    event = item.get("market_event") or {}
    warning = bool(event.get("warning")) or str(item.get("market_warning", "")).upper() == "CAUTION"
    caution = event.get("caution") or {}
    caution_flags = [str(key) for key, value in caution.items() if bool(value)] if isinstance(caution, dict) else []
    return warning, caution_flags


def fetch_universe() -> pd.DataFrame:
    markets = upbit_get("/market/all", {"is_details": "true"}, label="업비트 페어 목록")
    if not isinstance(markets, list) or not markets:
        raise ScanError("업비트 페어 목록이 비어 있습니다.")

    rows: List[dict] = []
    prefix = f"{QUOTE_CURRENCY}-"
    for item in markets:
        market = str(item.get("market", ""))
        if not market.startswith(prefix):
            continue
        warning, caution_flags = _event_flags(item)
        rows.append({
            "Code": market,
            "Name": str(item.get("korean_name") or market.split("-", 1)[-1]),
            "EnglishName": str(item.get("english_name") or ""),
            "Market": f"UPBIT-{QUOTE_CURRENCY}",
            "Warning": warning,
            "CautionFlags": ",".join(caution_flags),
        })

    if not rows:
        raise ScanError(f"업비트 {QUOTE_CURRENCY} 마켓 페어가 없습니다.")

    market_codes = [row["Code"] for row in rows]
    ticker_map: Dict[str, dict] = {}
    ticker_chunks = list(chunks(market_codes, TICKER_CHUNK_SIZE))
    for idx, group in enumerate(ticker_chunks, start=1):
        logging.info("현재가/거래대금 수집 %d/%d (%d페어)", idx, len(ticker_chunks), len(group))
        payload = upbit_get("/ticker", {"markets": ",".join(group)}, label="업비트 현재가")
        if isinstance(payload, list):
            ticker_map.update({str(item.get("market")): item for item in payload})

    enriched: List[dict] = []
    for row in rows:
        ticker = ticker_map.get(row["Code"])
        if not ticker:
            continue
        row.update({
            "CurrentPrice": float(ticker.get("trade_price") or 0),
            "Amount": float(ticker.get("acc_trade_price_24h") or 0),
            "ChangeRate24h": float(ticker.get("signed_change_rate") or 0) * 100.0,
            "Timestamp": int(ticker.get("timestamp") or 0),
        })
        enriched.append(row)

    universe = pd.DataFrame(enriched)
    if universe.empty:
        raise ScanError("업비트 현재가 데이터 결합 결과가 비어 있습니다.")

    universe = universe[universe["CurrentPrice"] > 0]
    universe = universe[universe["Amount"] >= MIN_24H_TRADE_AMOUNT]
    if EXCLUDE_WARNING:
        universe = universe[~universe["Warning"]]
    if EXCLUDE_CAUTION:
        universe = universe[universe["CautionFlags"].fillna("").eq("")]
    universe = universe.sort_values("Amount", ascending=False).drop_duplicates("Code").reset_index(drop=True)

    if len(universe) < 10:
        raise ScanError(
            f"유니버스가 비정상적으로 작습니다: {len(universe)}페어. "
            "UPBIT_MIN_24H_TRADE_AMOUNT 또는 경보 제외 설정을 확인하세요."
        )
    logging.info(
        "유니버스: %d페어 / 최소 24시간 거래대금 %.0f원 / 경보 제외=%s / 주의 제외=%s",
        len(universe), MIN_24H_TRADE_AMOUNT, EXCLUDE_WARNING, EXCLUDE_CAUTION,
    )
    return universe


def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    columns = ["Open", "High", "Low", "Close", "Volume", "Amount"]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["Open", "High", "Low", "Close"])
    out = out[(out[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    out["Volume"] = out["Volume"].fillna(0.0)
    out["Amount"] = out["Amount"].fillna(0.0)
    return out[columns]


def _active_upbit_day_start(now_kst: Optional[datetime] = None) -> pd.Timestamp:
    now = now_kst or datetime.now(KST)
    boundary = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now < boundary:
        boundary -= timedelta(days=1)
    return pd.Timestamp(boundary.replace(tzinfo=None))


def fetch_daily_candles(market: str, count: int = LOOKBACK_CANDLES) -> pd.DataFrame:
    records: List[dict] = []
    to_value: Optional[str] = None
    pages = max(1, math.ceil((count + 2) / CANDLE_PAGE_SIZE))

    for page in range(pages):
        params = {"market": market, "count": min(CANDLE_PAGE_SIZE, count + 2 - len(records))}
        if params["count"] <= 0:
            break
        if to_value:
            params["to"] = to_value
        payload = upbit_get("/candles/days", params, label=f"{market} 일봉")
        if not isinstance(payload, list) or not payload:
            break
        records.extend(payload)
        earliest = payload[-1].get("candle_date_time_utc")
        if not earliest or len(payload) < params["count"]:
            break
        to_value = f"{earliest}Z" if not str(earliest).endswith("Z") else str(earliest)

    if not records:
        return clean_ohlcv(pd.DataFrame())

    normalized: List[dict] = []
    for item in records:
        dt = item.get("candle_date_time_kst") or item.get("candle_date_time_utc")
        if not dt:
            continue
        normalized.append({
            "Date": pd.Timestamp(dt),
            "Open": item.get("opening_price"),
            "High": item.get("high_price"),
            "Low": item.get("low_price"),
            "Close": item.get("trade_price"),
            "Volume": item.get("candle_acc_trade_volume", 0),
            "Amount": item.get("candle_acc_trade_price", 0),
        })

    daily = pd.DataFrame(normalized).set_index("Date")
    daily = clean_ohlcv(daily)
    # 업비트 일봉은 09:00 KST에 전환된다. 진행 중인 일봉은 흐름판정에서 제외한다.
    daily = daily[daily.index < _active_upbit_day_start()]
    return daily.tail(count)


def fetch_minute_candles(market: str, unit: int, count: int = 200) -> pd.DataFrame:
    """업비트 완성 분봉을 수집한다. 거래가 없던 구간은 API 특성상 생성되지 않는다."""
    payload = upbit_get(
        f"/candles/minutes/{unit}",
        {"market": market, "count": min(count, CANDLE_PAGE_SIZE)},
        label=f"{market} {unit}분봉",
    )
    if not isinstance(payload, list) or not payload:
        return clean_ohlcv(pd.DataFrame())
    normalized: List[dict] = []
    for item in payload:
        dt = item.get("candle_date_time_kst") or item.get("candle_date_time_utc")
        if not dt:
            continue
        normalized.append({
            "Date": pd.Timestamp(dt),
            "Open": item.get("opening_price"),
            "High": item.get("high_price"),
            "Low": item.get("low_price"),
            "Close": item.get("trade_price"),
            "Volume": item.get("candle_acc_trade_volume", 0),
            "Amount": item.get("candle_acc_trade_price", 0),
        })
    frame = clean_ohlcv(pd.DataFrame(normalized).set_index("Date"))
    now_naive = pd.Timestamp(datetime.now(KST).replace(tzinfo=None))
    return frame[frame.index + pd.Timedelta(minutes=unit) <= now_naive].tail(count)


def collect_daily_data(universe: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str], List[str]]:
    frames: Dict[str, pd.DataFrame] = {}
    sources: Dict[str, str] = {}
    failed: List[str] = []

    for idx, row in universe.iterrows():
        code = str(row["Code"])
        try:
            frame = fetch_daily_candles(code)
            if len(frame) >= MIN_DAILY_CANDLES:
                frames[code] = frame
                sources[code] = "Upbit Quotation API / candles/days"
            else:
                failed.append(code)
                logging.warning("%s 일봉 부족: %d개", code, len(frame))
        except Exception as exc:  # noqa: BLE001
            failed.append(code)
            logging.warning("%s 일봉 수집 실패: %s", code, exc)

        if (idx + 1) % 20 == 0 or idx + 1 == len(universe):
            logging.info("일봉 수집: %d/%d / 성공 %d / 실패 %d", idx + 1, len(universe), len(frames), len(failed))

    if len(frames) < max(10, int(len(universe) * 0.5)):
        raise ScanError(f"일봉 확보 페어가 부족합니다: {len(frames)}/{len(universe)}")
    return frames, sources, failed



def recent_swing_low(daily: pd.DataFrame, box_bottom: float) -> float:
    recent = daily.tail(45)
    if len(recent) < 8:
        return box_bottom * 0.97
    lows = recent["Low"].to_numpy(dtype=float)
    swing_indices: List[int] = []
    for i in range(2, len(lows) - 2):
        if lows[i] <= lows[i - 2 : i].min() and lows[i] <= lows[i + 1 : i + 3].min():
            swing_indices.append(i)
    if swing_indices:
        value = lows[swing_indices[-1]]
    else:
        value = float(recent.iloc[-12:-1]["Low"].min())
    # 지나치게 먼 저점은 실전 종료선으로 부적합하므로 박스 하단 -7% 안쪽으로 제한한다.
    return max(value, box_bottom * 0.93)


def classify_mode(surge: float, post_days: int, box_width: float, retrace: float) -> Optional[str]:
    """완성 일봉 기준으로 급등 후 박스 성숙도를 구분한다."""
    if surge >= 40 and post_days >= 15 and box_width <= 0.60 and retrace <= 0.80:
        return "엄격"
    if surge >= 30 and post_days >= 10 and box_width <= 0.70 and retrace <= 0.85:
        return "완화"
    if surge >= 20 and post_days >= 7 and box_width <= 1.00 and retrace <= 0.95:
        return "관찰보충"
    return None


def tier(score: float) -> str:
    if score >= 7.0:
        return "1순위"
    if score >= 5.5:
        return "2순위"
    if score >= 4.0:
        return "3순위"
    return "4순위"


def rounded_price(value: float):
    if not math.isfinite(value) or value <= 0:
        return 0
    if value >= 1000:
        return int(round(value))
    digits = min(12, max(1, 3 - int(math.floor(math.log10(value)))))
    return round(value, digits)


def format_price(value: float) -> str:
    value = float(value)
    if not math.isfinite(value):
        return "-"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    text = f"{value:,.12f}".rstrip("0").rstrip(".")
    return text or "0"



def weighted_balance_price(
    daily: pd.DataFrame,
    start_date: pd.Timestamp,
    box_bottom: float,
    box_top: float,
) -> float:
    """고점 이후 거래가 집중된 가격을 중심선으로 계산한다.

    단순 박스 중간값보다 실제 체결 흐름을 반영하기 위해
    고점 이후 일봉의 전형가격(H+L+C)/3을 거래량으로 가중한다.
    결과가 박스 가장자리로 치우치지 않도록 박스 25~75% 안으로 제한한다.
    """
    post_daily = daily[daily.index > start_date].copy()
    if len(post_daily) < 5:
        post_daily = daily.tail(60).copy()

    typical = (post_daily["High"] + post_daily["Low"] + post_daily["Close"]) / 3.0
    volume = pd.to_numeric(post_daily["Volume"], errors="coerce").fillna(0.0).clip(lower=0.0)
    if float(volume.sum()) > 0:
        center = float((typical * volume).sum() / volume.sum())
    else:
        center = float(post_daily["Close"].median())

    span = box_top - box_bottom
    return min(max(center, box_bottom + span * 0.25), box_bottom + span * 0.75)


def classify_price_flow(
    daily: pd.DataFrame,
    *,
    buy_low: float,
    buy_high: float,
    deep_buy_high: float,
    center_low: float,
    center_high: float,
    sell_low: float,
    deep_sell_low: float,
    sell_high: float,
) -> Tuple[str, str]:
    """최근 종가와 장악 캔들로 현재 흐름을 5단계로 판정한다."""
    recent = daily.tail(25).copy()
    if len(recent) < 3:
        return "중립", "일봉 데이터가 부족해 존 위치만 확인"

    latest = recent.iloc[-1]
    previous = recent.iloc[-2]
    op = float(latest["Open"])
    cl = float(latest["Close"])
    prev_cl = float(previous["Close"])
    bullish = cl > op
    bearish = cl < op

    # 진한 존을 몸통으로 통과하고 종가가 안착했는지를 우선한다.
    strong_up_engulf = bullish and cl >= deep_sell_low and min(op, prev_cl) <= sell_low
    strong_down_engulf = bearish and cl <= deep_buy_high and max(op, prev_cl) >= buy_high

    tail5 = float(recent["Close"].tail(5).mean())
    prev5 = float(recent["Close"].iloc[-10:-5].mean()) if len(recent) >= 10 else prev_cl
    rising = tail5 > prev5
    falling = tail5 < prev5

    if cl > sell_high or strong_up_engulf:
        reason = "진한 매도존을 양봉 몸통으로 장악하고 종가 안착" if strong_up_engulf else "매도존 상단 돌파 종가"
        return "강한 상승", reason
    if cl >= sell_low:
        return "상승·매도구간", "매도존 내부 진입 — 2·3차 분할매도 구간"
    if cl > center_high:
        return ("상승", "중심존 위에서 종가 유지" + (" + 단기 종가 기울기 상승" if rising else ""))
    if center_low <= cl <= center_high:
        return "중립·공방", "회색 중심존에서 수급 균형 확인"
    if cl < buy_low:
        return "강한 하락", "매수존 하단 이탈 종가 — 신규 매수 중단"
    if buy_low <= cl <= buy_high:
        if strong_down_engulf:
            return "강한 하락", "진한 매수존을 음봉 몸통으로 장악하고 종가 마감"
        return ("하락·매수구간" if falling else "매수존 반등대기", "매수존 내부 — 지지 캔들 확인 전 선매수 금지")
    return ("하락" if falling else "하단 회복"), "매수존과 중심존 사이의 회복 여부 확인"


def analyze_one(row: pd.Series, daily: pd.DataFrame) -> Optional[dict]:
    """완성된 일봉만으로 급등·조정·박스·흐름을 판정한다.

    최신 티커 가격은 장중 참고값으로만 저장하고, 후보 점수와 박스 위치,
    조정 깊이, 손익비 및 흐름 판정은 마지막 완성 일봉 종가를 사용한다.
    """
    if len(daily) < 120:
        return None

    analysis_close = float(daily["Close"].iloc[-1])
    live_price = float(row.get("CurrentPrice", analysis_close) or analysis_close)

    # 최근 약 6개월에 해당하는 완성 일봉 180개에서 급등 구간을 탐색한다.
    d180 = daily.iloc[-180:].copy()
    lo_rel = int(np.argmin(d180["Low"].to_numpy()))
    after_low = d180.iloc[lo_rel:]
    if after_low.empty:
        return None
    hi_rel_after = int(np.argmax(after_low["High"].to_numpy()))
    hi_rel = lo_rel + hi_rel_after

    s_lo = float(d180["Low"].iloc[lo_rel])
    s_hi = float(d180["High"].iloc[hi_rel])
    if s_lo <= 0 or s_hi <= s_lo:
        return None
    surge = (s_hi / s_lo - 1.0) * 100.0

    global_hi_pos = len(daily) - len(d180) + hi_rel
    peak_day = pd.Timestamp(daily.index[global_hi_pos])
    post = daily.iloc[global_hi_pos + 1 :].copy()
    if len(post) < 7:
        return None

    top = float(post["High"].max())
    bot = float(post["Low"].min())
    if bot <= 0 or top <= bot:
        return None
    span = top - bot
    box_width = top / bot - 1.0
    retrace = (s_hi - analysis_close) / (s_hi - s_lo)
    mode = classify_mode(surge, len(post), box_width, retrace)
    if mode is None:
        return None

    surge_slice = daily.iloc[(len(daily) - len(d180) + lo_rel) : global_hi_pos + 1]
    surge_vol = float(surge_slice["Volume"].mean()) if not surge_slice.empty else 0.0
    post_vol = float(post["Volume"].mean()) if not post.empty else 0.0
    vol_drop = (1.0 - post_vol / surge_vol) * 100.0 if surge_vol > 0 else 0.0
    pos = (analysis_close - bot) / span * 100.0 if span > 0 else 50.0
    flags: List[str] = []
    # 장중 현재가는 후보 선정에 사용하지 않고, 완성 일봉 박스 이탈 여부 참고 태그만 붙인다.
    if live_price < bot:
        flags.append("장중하단이탈")
    elif live_price > top:
        flags.append("장중상단돌파")
    if retrace > 0.618:
        flags.append("조정깊음")
    if vol_drop < 20:
        flags.append("거래량주의")
    if len(post) < 15:
        flags.append("박스미성숙")
    if surge < 40:
        flags.append("급등폭완화")
    if box_width > 0.60:
        flags.append("박스폭넓음")
    if mode == "관찰보충":
        flags.append("관찰보충")

    # ── 사용자가 확정한 3존 전략 ───────────────────────────────────────
    # 매수존: 박스 하단 0~15%, 진한 매수존: 하단 0~5%
    # 중심존: 급등 고점 이후 일봉 거래량 가중 중심가격 주변
    # 매도존: 박스 상단 70~100%, 진한 매도존: 상단 90~100%
    buy_low = bot
    buy_high = bot + span * 0.15
    deep_buy_low = bot
    deep_buy_high = bot + span * 0.05

    center = weighted_balance_price(daily, peak_day, bot, top)
    center_half = max(span * 0.025, center * 0.008)
    center_low = max(buy_high, center - center_half)
    center_high = min(top - span * 0.30, center + center_half)
    if center_high <= center_low:
        center_low = bot + span * 0.45
        center_high = bot + span * 0.55
        center = (center_low + center_high) / 2.0

    sell_low = top - span * 0.30
    sell_high = top
    deep_sell_low = top - span * 0.10
    deep_sell_high = top

    swing_low = recent_swing_low(daily, bot)
    target1 = center
    target2 = sell_low
    target3 = top
    trade_plan = build_trade_plan(
        buy_low=buy_low,
        buy_high=buy_high,
        box_span=span,
        target1=target1,
        target2=target2,
        target3=target3,
    )
    stop = float(trade_plan["stop"])
    flow, flow_reason = classify_price_flow(
        daily,
        buy_low=buy_low,
        buy_high=buy_high,
        deep_buy_high=deep_buy_high,
        center_low=center_low,
        center_high=center_high,
        sell_low=sell_low,
        deep_sell_low=deep_sell_low,
        sell_high=sell_high,
    )

    # 실전 복기 핵심: 최종 박스 상단이 아니라 '1차 익절가'가 손절과 최소 1:1이어야 한다.
    first_target_rr = float(trade_plan["first_target_rr"])
    final_target_rr = float(trade_plan["final_target_rr"])
    gate_status, gate_reasons, live_pos, live_move = execution_gate(
        analysis_close=analysis_close,
        live_price=live_price,
        buy_low=buy_low,
        buy_high=buy_high,
        box_top=top,
        center_low=center_low,
        first_target_rr=first_target_rr,
        flow=flow,
    )

    score = 0.0
    score += 2 if surge >= 100 else 1.5 if surge >= 70 else 1 if surge >= 50 else 0.5 if surge >= 40 else 0
    score += 2 if retrace <= 0.382 else 1.5 if retrace <= 0.5 else 1 if retrace <= 0.618 else 0
    score += 2 if vol_drop >= 40 else 1 if vol_drop >= 20 else 0.5 if vol_drop >= 10 else 0
    score += 2 if 0 <= pos <= 15 else 0.5 if 15 < pos <= 30 else 0
    score += 1 if first_target_rr >= 1.5 else 0.5 if first_target_rr >= MIN_TARGET1_RR else 0
    score += 0.5 if box_width <= 0.45 else 0
    if mode == "완화":
        score -= 0.5
    elif mode == "관찰보충":
        score -= 1.0

    if pos < 0:
        zone = "하단이탈·관망"
    elif pos <= 15:
        zone = "매수존·확인대기"
    elif pos <= 30:
        zone = "하단반등대기"
    elif pos >= 70:
        zone = "매도구간·추격금지"
    else:
        zone = "대기"

    if first_target_rr < MIN_TARGET1_RR:
        flags.append("1차손익비미달")
    if live_price > buy_high:
        flags.append("현재가매수존초과")
    if live_move >= LIVE_CHASE_PCT and live_price > buy_high:
        flags.append("장중급등추격주의")
    if gate_status != "5분봉 확인대기":
        flags.append("신규진입관망")

    if flow == "강한 하락" and "하락흐름" not in flags:
        flags.append("하락흐름")
    if flow == "강한 상승" and "상승돌파" not in flags:
        flags.append("상승돌파")

    data_date = daily.index.max().date().isoformat()

    return {
        "종목명": str(row["Name"]),
        "코드": str(row["Code"]),
        "시장": str(row["Market"]),
        "영문명": str(row.get("EnglishName", "")),
        "분석시간봉": "1D",
        "신호기준": "마지막 완성 일봉 종가",
        "24시간거래대금": int(round(float(row.get("Amount", 0)))),
        "24시간등락률_pct": round(float(row.get("ChangeRate24h", 0)), 2),
        "시장경보": bool(row.get("Warning", False)),
        "주의사유": str(row.get("CautionFlags", "")),
        "점수": round(score, 1),
        "위치분류": zone,
        "흐름판정": flow,
        "흐름근거": flow_reason,
        "현재가": rounded_price(live_price),
        "일봉기준종가": rounded_price(analysis_close),
        "박스하단": rounded_price(bot),
        "박스상단": rounded_price(top),
        "박스내위치_pct": int(round(pos)),
        "장중박스위치_pct": int(round(live_pos)),
        "장중등락_완성일봉대비_pct": round(live_move, 2),
        "매수존하단": rounded_price(buy_low),
        "매수존상단": rounded_price(buy_high),
        "진한매수존하단": rounded_price(deep_buy_low),
        "진한매수존상단": rounded_price(deep_buy_high),
        "중심존하단": rounded_price(center_low),
        "중심선": rounded_price(center),
        "중심존상단": rounded_price(center_high),
        "매도존하단": rounded_price(sell_low),
        "매도존상단": rounded_price(sell_high),
        "진한매도존하단": rounded_price(deep_sell_low),
        "진한매도존상단": rounded_price(deep_sell_high),
        "급등폭_pct": int(round(surge)),
        "조정깊이_pct": int(round(retrace * 100)),
        "거래량감소_pct": int(round(vol_drop)),
        "박스경과일": int(len(post)),
        "1차익절손익비": round(first_target_rr, 2),
        "최종목표손익비": round(final_target_rr, 2),
        # 기존 소비자의 키 호환을 유지하되 의미는 더 보수적인 1차 익절 손익비로 변경한다.
        "참고손익비": round(first_target_rr, 2),
        "실전진입판정": gate_status,
        "일봉안전판정": gate_status,
        "진입금지사유": " / ".join(gate_reasons),
        "5분봉확인규칙": "매수존 터치 후 5분봉 종가 재진입 + 양봉 전환 + 직전 저점 미이탈 시에만 진입",
        "추가매수규칙": "최초 진입 전에 정한 매수존 내부 2~3회만 허용; 손절가 이탈 후 추가매수 금지",
        "주의": ",".join(flags),
        "선별모드": mode,
        # 기존 키는 매수존 호환용으로 유지한다.
        "진입구간하단": rounded_price(buy_low),
        "진입구간상단": rounded_price(buy_high),
        "1차분할매수가_30pct": trade_plan["entry_levels"][0],
        "2차분할매수가_30pct": trade_plan["entry_levels"][1],
        "3차분할매수가_40pct": trade_plan["entry_levels"][2],
        "계획평균매수가": trade_plan["planned_average"],
        "손절가": trade_plan["stop"],
        "일봉매매종료라인": rounded_price(swing_low),
        "일차익절_35pct": trade_plan["targets"][0],
        "이차익절_35pct": trade_plan["targets"][1],
        "최종목표_30pct": trade_plan["targets"][2],
        "데이터기준일": data_date,
        "_box_width": box_width,
    }

def select_candidates(universe: pd.DataFrame, frames: Dict[str, pd.DataFrame]) -> List[dict]:
    records: List[dict] = []
    for idx, row in universe.iterrows():
        frame = frames.get(row["Code"])
        if frame is None or frame.empty:
            continue
        try:
            record = analyze_one(row, frame)
            if record:
                records.append(record)
        except Exception as exc:  # noqa: BLE001
            logging.debug("분석 실패 %s %s: %s", row["Code"], row["Name"], exc)
        if (idx + 1) % 50 == 0:
            logging.info("분석 진행: %d/%d", idx + 1, len(universe))

    mode_order = {"엄격": 0, "완화": 1, "관찰보충": 2}
    records.sort(
        key=lambda x: (
            0 if x["실전진입판정"] == "5분봉 확인대기" else 1,
            mode_order.get(x["선별모드"], 9),
            -float(x["점수"]),
            -float(x["1차익절손익비"]),
            float(x["박스내위치_pct"]),
        )
    )

    strict = [r for r in records if r["선별모드"] == "엄격"]
    relaxed = [r for r in records if r["선별모드"] == "완화"]
    observe = [r for r in records if r["선별모드"] == "관찰보충"]
    selected = (strict + relaxed + observe)[:TARGET_COUNT]
    if len(selected) < MIN_OUTPUT_COUNT:
        logging.warning("최소 목표 %d페어 미달: %d페어", MIN_OUTPUT_COUNT, len(selected))

    for rec in selected:
        rec["순위"] = tier(float(rec["점수"]))
        rec.pop("_box_width", None)
    return selected


def collect_intraday_data(records: List[dict]) -> Tuple[Dict[str, Dict[int, pd.DataFrame]], List[str]]:
    """일봉 후보에 대해서만 4H·1H·15m·5m 완성봉을 수집한다."""
    counts = {240: 120, 60: 160, 15: 200, 5: 200}
    frames: Dict[str, Dict[int, pd.DataFrame]] = {}
    failed: List[str] = []
    for idx, candidate in enumerate(records, start=1):
        code = str(candidate["코드"])
        market_frames: Dict[int, pd.DataFrame] = {}
        for unit, count in counts.items():
            try:
                frame = fetch_minute_candles(code, unit, count)
                if len(frame) >= 8:
                    market_frames[unit] = frame
                else:
                    failed.append(f"{code}:{unit}m")
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{code}:{unit}m")
                logging.warning("%s %d분봉 수집 실패: %s", code, unit, exc)
        frames[code] = market_frames
        logging.info("분봉 수집: %d/%d / %s", idx, len(records), code)
    return frames, failed


def apply_intraday_gates(records: List[dict], frames: Dict[str, Dict[int, pd.DataFrame]]) -> None:
    """일봉 후보를 멀티타임프레임 최종 상태와 사용자 진입성향 태그로 보강한다."""
    for candidate in records:
        gate = multi_timeframe_gate(
            daily_status=str(candidate["일봉안전판정"]),
            frames=frames.get(str(candidate["코드"]), {}),
            buy_low=float(candidate["매수존하단"]),
            buy_high=float(candidate["매수존상단"]),
            stop=float(candidate["손절가"]),
        )
        candidate["실전진입판정"] = gate["status"]
        candidate["진입성향태그"] = gate["signature"]
        states = gate["states"]
        candidate["4시간봉판정"] = states.get("4h", "자료부족")
        candidate["1시간봉판정"] = states.get("1h", "자료부족")
        candidate["15분봉판정"] = states.get("15m", "자료부족")
        candidate["5분봉판정"] = states.get("5m", "자료부족")
        combined = [candidate["진입금지사유"]] if candidate["진입금지사유"] else []
        combined.extend(str(reason) for reason in gate["reasons"] if reason)
        candidate["진입금지사유"] = " / ".join(dict.fromkeys(combined))

    history = load_trade_history(ROOT / "data" / "trade_history.csv")
    for candidate in records:
        overtrade = evaluate_overtrade(history, market=str(candidate["코드"]), now_kst=datetime.now(KST))
        candidate["과매매판정"] = overtrade["status"]
        candidate["당일동일코인진입횟수"] = overtrade["same_market_entries"]
        candidate["과매매금지사유"] = " / ".join(overtrade["reasons"])
        if overtrade["status"] == "진입금지":
            candidate["실전진입판정"] = "관망"
            combined = [candidate["진입금지사유"]] if candidate["진입금지사유"] else []
            combined.extend(overtrade["reasons"])
            candidate["진입금지사유"] = " / ".join(dict.fromkeys(combined))

    status_order = {"진입조건충족": 0, "5분봉 확인대기": 1, "관망": 2}
    records.sort(
        key=lambda x: (
            status_order.get(str(x["실전진입판정"]), 9),
            -float(x["점수"]),
            -float(x["1차익절손익비"]),
        )
    )


def json_safe_records(df: pd.DataFrame) -> List[dict]:
    out: List[dict] = []
    for dt, row in df.iterrows():
        out.append(
            {
                "date": pd.Timestamp(dt).date().isoformat(),
                "open": rounded_price(float(row["Open"])),
                "high": rounded_price(float(row["High"])),
                "low": rounded_price(float(row["Low"])),
                "close": rounded_price(float(row["Close"])),
                "volume": float(row["Volume"]) if math.isfinite(float(row["Volume"])) else 0,
                "amount": int(round(float(row.get("Amount", 0)))) if math.isfinite(float(row.get("Amount", 0))) else 0,
            }
        )
    return out


def json_safe_minutes(df: pd.DataFrame) -> List[dict]:
    out: List[dict] = []
    for dt, row in df.iterrows():
        out.append({
            "time_kst": pd.Timestamp(dt).isoformat(),
            "open": rounded_price(float(row["Open"])),
            "high": rounded_price(float(row["High"])),
            "low": rounded_price(float(row["Low"])),
            "close": rounded_price(float(row["Close"])),
            "volume": float(row["Volume"]) if math.isfinite(float(row["Volume"])) else 0,
            "amount": int(round(float(row.get("Amount", 0)))) if math.isfinite(float(row.get("Amount", 0))) else 0,
        })
    return out


def write_daily_json(candidate: dict, daily: pd.DataFrame, source: str) -> None:
    payload = {
        "name": candidate["종목명"],
        "code": candidate["코드"],
        "market": candidate["시장"],
        "data_source": source,
        "data_date": candidate["데이터기준일"],
        "strategy_version": "upbit-buy-center-sell-flow-v5-learning-risk-control",
        "execution_gate": {
            "status": candidate["실전진입판정"],
            "daily_status": candidate["일봉안전판정"],
            "block_reasons": candidate["진입금지사유"],
            "attraction_signature": candidate["진입성향태그"],
            "timeframe_states": {
                "4h": candidate["4시간봉판정"],
                "1h": candidate["1시간봉판정"],
                "15m": candidate["15분봉판정"],
                "5m": candidate["5분봉판정"],
            },
            "five_minute_confirmation": candidate["5분봉확인규칙"],
            "averaging_rule": candidate["추가매수규칙"],
            "first_target_rr": candidate["1차익절손익비"],
            "minimum_first_target_rr": MIN_TARGET1_RR,
        },
        "flow": {
            "status": candidate["흐름판정"],
            "reason": candidate["흐름근거"],
        },
        "levels": {
            "box_bottom": candidate["박스하단"],
            "box_top": candidate["박스상단"],
            "buy_zone_low": candidate["매수존하단"],
            "buy_zone_high": candidate["매수존상단"],
            "deep_buy_zone_low": candidate["진한매수존하단"],
            "deep_buy_zone_high": candidate["진한매수존상단"],
            "center_zone_low": candidate["중심존하단"],
            "center_line": candidate["중심선"],
            "center_zone_high": candidate["중심존상단"],
            "sell_zone_low": candidate["매도존하단"],
            "sell_zone_high": candidate["매도존상단"],
            "deep_sell_zone_low": candidate["진한매도존하단"],
            "deep_sell_zone_high": candidate["진한매도존상단"],
            "stop": candidate["손절가"],
            "planned_entries": [
                {"price": candidate["1차분할매수가_30pct"], "weight_pct": 30},
                {"price": candidate["2차분할매수가_30pct"], "weight_pct": 30},
                {"price": candidate["3차분할매수가_40pct"], "weight_pct": 40},
            ],
            "planned_average": candidate["계획평균매수가"],
            "daily_exit_line": candidate["일봉매매종료라인"],
            "target_1_35pct": candidate["일차익절_35pct"],
            "target_2_35pct": candidate["이차익절_35pct"],
            "target_3_30pct": candidate["최종목표_30pct"],
        },
        "scan_metrics": candidate,
        "daily": json_safe_records(daily.tail(260)),
    }
    (DAILY_DIR / f"{candidate['코드']}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_intraday_json(candidate: dict, frames: Dict[int, pd.DataFrame]) -> None:
    payload = {
        "code": candidate["코드"],
        "strategy_version": "upbit-buy-center-sell-flow-v5-learning-risk-control",
        "only_completed_candles": True,
        "timeframes": {
            str(unit): json_safe_minutes(frame) for unit, frame in sorted(frames.items(), reverse=True)
        },
    }
    (INTRADAY_DIR / f"{candidate['코드']}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_price_line(fig, price: float, label: str, dash: str = "dash") -> None:
    fig.add_hline(
        y=price,
        line_dash=dash,
        line_width=1.3,
        annotation_text=f"{label} {format_price(price)}",
        annotation_position="top left",
        row=1,
        col=1,
    )


def write_chart(candidate: dict, daily: pd.DataFrame) -> None:
    if go is None or make_subplots is None:
        (CHART_DIR / f"{candidate['코드']}.html").write_text(
            "<!doctype html><meta charset='utf-8'><title>차트 생성 생략</title>"
            f"<h1>{candidate['종목명']} ({candidate['코드']})</h1>"
            "<p>시세 스캔은 완료됐지만 이 환경에는 plotly가 없어 HTML 차트만 생략했습니다.</p>",
            encoding="utf-8",
        )
        return
    view = daily.tail(180)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.76, 0.24],
        subplot_titles=(f"{candidate['종목명']} ({candidate['코드']}) 일봉", "거래량"),
    )
    fig.add_trace(
        go.Candlestick(
            x=view.index,
            open=view["Open"],
            high=view["High"],
            low=view["Low"],
            close=view["Close"],
            name="일봉",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(go.Bar(x=view.index, y=view["Volume"], name="거래량", opacity=0.55), row=2, col=1)

    # 매수존: 연한 초록, 하단 심화존: 진한 초록
    fig.add_hrect(
        y0=candidate["매수존하단"], y1=candidate["매수존상단"],
        fillcolor="rgba(46, 204, 113, 0.18)", line_width=0,
        annotation_text="매수존", annotation_position="inside top left", row=1, col=1,
    )
    fig.add_hrect(
        y0=candidate["진한매수존하단"], y1=candidate["진한매수존상단"],
        fillcolor="rgba(39, 174, 96, 0.38)", line_width=0,
        annotation_text="진한 매수존", annotation_position="inside bottom left", row=1, col=1,
    )

    # 중심존: 수급 균형·첫 익절 판단 구간
    fig.add_hrect(
        y0=candidate["중심존하단"], y1=candidate["중심존상단"],
        fillcolor="rgba(149, 165, 166, 0.34)", line_width=0,
        annotation_text="회색 중심존", annotation_position="inside top left", row=1, col=1,
    )

    # 매도존: 연한 빨강, 상단 심화존: 진한 빨강
    fig.add_hrect(
        y0=candidate["매도존하단"], y1=candidate["매도존상단"],
        fillcolor="rgba(231, 76, 60, 0.18)", line_width=0,
        annotation_text="매도존", annotation_position="inside bottom left", row=1, col=1,
    )
    fig.add_hrect(
        y0=candidate["진한매도존하단"], y1=candidate["진한매도존상단"],
        fillcolor="rgba(192, 57, 43, 0.38)", line_width=0,
        annotation_text="진한 매도존", annotation_position="inside top left", row=1, col=1,
    )

    add_price_line(fig, candidate["현재가"], "장중 현재가", "dot")
    add_price_line(fig, candidate["일봉기준종가"], "완성 일봉 종가", "dash")
    add_price_line(fig, candidate["박스하단"], "박스 하단", "solid")
    add_price_line(fig, candidate["박스상단"], "박스 상단", "solid")
    add_price_line(fig, candidate["중심선"], "중심선·1차 35%", "dash")
    add_price_line(fig, candidate["매도존하단"], "2차 35%", "dash")
    add_price_line(fig, candidate["최종목표_30pct"], "3차 30%", "dash")
    add_price_line(fig, candidate["손절가"], "기본 손절", "dot")
    add_price_line(fig, candidate["일봉매매종료라인"], "일봉 종료선", "dot")

    fig.add_annotation(
        x=0.01, y=0.99, xref="paper", yref="paper",
        text=(
            f"실전판정: {candidate['실전진입판정']} · 1차 RR {candidate['1차익절손익비']}<br>"
            f"진입유형: {candidate.get('진입성향태그', '-')} · 4H {candidate.get('4시간봉판정', '-')} · 1H {candidate.get('1시간봉판정', '-')}<br>"
            f"계획매수: {candidate['1차분할매수가_30pct']} / {candidate['2차분할매수가_30pct']} / {candidate['3차분할매수가_40pct']} · 손절 {candidate['손절가']}<br>"
            f"흐름: {candidate['흐름판정']} · {candidate['흐름근거']}<br>"
            f"진입 제한: {candidate['진입금지사유'] or '없음 — 5분봉 확인 필요'}"
        ),
        showarrow=False, align="left",
        bgcolor="rgba(17,17,17,0.72)", bordercolor="rgba(255,255,255,0.25)",
        font=dict(size=12),
    )

    fig.update_layout(
        template="plotly_dark",
        height=920,
        title=(
            f"{candidate['순위']} · {candidate['위치분류']} · {candidate['실전진입판정']} · "
            f"점수 {candidate['점수']} · 1차 손익비 {candidate['1차익절손익비']}"
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend_orientation="h",
        legend_y=1.02,
        margin=dict(l=55, r=25, t=110, b=45),
    )
    fig.update_yaxes(title_text="가격", row=1, col=1)
    fig.update_yaxes(title_text="거래량", row=2, col=1)
    fig.write_html(
        CHART_DIR / f"{candidate['코드']}.html",
        include_plotlyjs="cdn",
        full_html=True,
        config={"displaylogo": False, "responsive": True},
    )


def md_table(records: List[dict]) -> str:
    headers = [
        "순위", "종목명", "코드", "실전판정", "위치", "흐름", "점수", "현재가", "일봉기준종가",
        "24h거래대금", "24h등락", "매수존", "분할매수30/30/40", "손절", "중심선", "매도존", "박스위치",
        "1차RR", "진입유형", "4H/1H/15m/5m", "진입제한", "주의",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in records:
        values = [
            r["순위"], r["종목명"], r["코드"], r["실전진입판정"], r["위치분류"], r["흐름판정"], f"{r['점수']:.1f}",
            format_price(r["현재가"]), format_price(r["일봉기준종가"]),
            f"{r['24시간거래대금'] / 100_000_000:.1f}억", f"{r['24시간등락률_pct']:+.2f}%",
            f"{format_price(r['매수존하단'])}~{format_price(r['매수존상단'])}",
            f"{format_price(r['1차분할매수가_30pct'])}/{format_price(r['2차분할매수가_30pct'])}/{format_price(r['3차분할매수가_40pct'])}",
            format_price(r["손절가"]),
            format_price(r["중심선"]),
            f"{format_price(r['매도존하단'])}~{format_price(r['매도존상단'])}",
            f"{r['박스내위치_pct']}%", f"{r['1차익절손익비']:.2f}", r["진입성향태그"],
            f"{r['4시간봉판정']}/{r['1시간봉판정']}/{r['15분봉판정']}/{r['5분봉판정']}",
            r["진입금지사유"] or "조건 충족", r["주의"] or "-",
        ]
        lines.append("| " + " | ".join(str(v).replace("|", "/") for v in values) + " |")
    return "\n".join(lines)


def write_index(records: List[dict], market_date: str) -> None:
    rows = []
    for r in records:
        rows.append(
            "<tr>"
            f"<td>{r['순위']}</td><td>{r['종목명']}</td><td>{r['코드']}</td>"
            f"<td>{r['실전진입판정']}</td><td>{r['위치분류']}</td><td>{r['흐름판정']}</td><td>{r['점수']}</td>"
            f"<td>{format_price(r['현재가'])}</td>"
            f"<td>{format_price(r['일봉기준종가'])}</td>"
            f"<td>{r['24시간거래대금'] / 100_000_000:.1f}억</td><td>{r['24시간등락률_pct']:+.2f}%</td>"
            f"<td>{format_price(r['매수존하단'])}~{format_price(r['매수존상단'])}</td>"
            f"<td>{format_price(r['중심선'])}</td>"
            f"<td>{format_price(r['매도존하단'])}~{format_price(r['매도존상단'])}</td>"
            f"<td>{r['1차익절손익비']}</td><td>{r['진입금지사유'] or '5분봉 확인'}</td><td>{r['주의'] or '-'}</td>"
            f"<td><a href='charts/{r['코드']}.html'>차트 열기</a></td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>UPBIT KRW 일봉 매수존·매도존 스캔</title>
<style>body{{font-family:system-ui,sans-serif;margin:28px;background:#111;color:#eee}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #444;padding:8px;text-align:right}}th{{background:#222;position:sticky;top:0}}td:nth-child(2),th:nth-child(2),td:nth-child(5),th:nth-child(5),td:nth-child(12),th:nth-child(12){{text-align:left}}a{{color:#75bfff}}</style></head>
<body><h1>UPBIT KRW 일봉 매수존·중심존·매도존 스캔</h1>
<p>데이터 기준일: {market_date} · 후보 {len(records)}페어 · 익절 35% / 35% / 30%</p>
<table><thead><tr><th>순위</th><th>종목명</th><th>코드</th><th>실전판정</th><th>위치</th><th>흐름</th><th>점수</th><th>현재가</th><th>일봉기준종가</th><th>24h거래대금</th><th>24h등락</th><th>매수존</th><th>중심선</th><th>매도존</th><th>1차RR</th><th>진입제한</th><th>주의</th><th>HTML</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")


def write_outputs(
    records: List[dict],
    universe: pd.DataFrame,
    frames: Dict[str, pd.DataFrame],
    sources: Dict[str, str],
    failed: List[str],
    intraday_frames: Dict[str, Dict[int, pd.DataFrame]],
    intraday_failed: List[str],
) -> None:
    if not records:
        raise ScanError("선별된 후보가 0페어입니다.")

    market_date = max(r["데이터기준일"] for r in records)
    generated_at = datetime.now(KST).isoformat(timespec="seconds")

    for old_file in DAILY_DIR.glob("*.json"):
        old_file.unlink()
    for old_file in CHART_DIR.glob("*.html"):
        old_file.unlink()
    for old_file in INTRADAY_DIR.glob("*.json"):
        old_file.unlink()

    for candidate in records:
        daily = frames[candidate["코드"]]
        write_daily_json(candidate, daily, sources.get(candidate["코드"], "unknown"))
        write_intraday_json(candidate, intraday_frames.get(candidate["코드"], {}))
        write_chart(candidate, daily)

    output_df = pd.DataFrame(records)
    # 사용자가 기존 CSV와 호환해 읽을 수 있도록 % 표기는 컬럼명에 포함한다.
    rename_map = {
        "박스내위치_pct": "박스내위치%",
        "급등폭_pct": "급등폭%",
        "조정깊이_pct": "조정깊이%",
        "거래량감소_pct": "거래량감소%",
        "일차익절_35pct": "1차익절_35%",
        "이차익절_35pct": "2차익절_35%",
        "최종목표_30pct": "3차익절_30%",
    }
    output_df.rename(columns=rename_map).to_csv(OUTPUT_DIR / "latest_scan.csv", index=False, encoding="utf-8-sig")
    (OUTPUT_DIR / "latest_scan.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    counts = pd.Series([r["순위"] for r in records]).value_counts().to_dict()
    mode_counts = pd.Series([r["선별모드"] for r in records]).value_counts().to_dict()
    flow_counts = pd.Series([r["흐름판정"] for r in records]).value_counts().to_dict()
    gate_counts = pd.Series([r["실전진입판정"] for r in records]).value_counts().to_dict()
    metadata = {
        "status": "success",
        "strategy_version": "upbit-buy-center-sell-flow-v5-learning-risk-control",
        "generated_at_kst": generated_at,
        "market_date": market_date,
        "universe_count": int(len(universe)),
        "ohlcv_success_count": int(len(frames)),
        "candidate_count": int(len(records)),
        "minimum_target_met": len(records) >= MIN_OUTPUT_COUNT,
        "tier_counts": {k: int(v) for k, v in counts.items()},
        "selection_mode_counts": {k: int(v) for k, v in mode_counts.items()},
        "flow_counts": {k: int(v) for k, v in flow_counts.items()},
        "execution_gate_counts": {k: int(v) for k, v in gate_counts.items()},
        "failed_tickers_count": len(failed),
        "failed_tickers": failed[:100],
        "intraday_failed_count": len(intraday_failed),
        "intraday_failed": intraday_failed[:200],
        "rules": {
            "quote_currency": QUOTE_CURRENCY,
            "min_24h_trade_amount": MIN_24H_TRADE_AMOUNT,
            "exclude_warning": EXCLUDE_WARNING,
            "exclude_caution": EXCLUDE_CAUTION,
            "lookback_daily_candles": LOOKBACK_CANDLES,
            "strict_surge_pct": 40,
            "analysis_timeframe": "1D",
            "signal_price_source": "latest_completed_daily_close",
            "strict_min_box_days": 15,
            "strict_max_box_width_pct": 60,
            "strict_max_retrace_pct": 80,
            "min_output_count": MIN_OUTPUT_COUNT,
            "target_count": TARGET_COUNT,
            "buy_zone_pct": [0, 15],
            "deep_buy_zone_pct": [0, 5],
            "sell_zone_pct": [70, 100],
            "deep_sell_zone_pct": [90, 100],
            "partial_sell_pct": [35, 35, 30],
            "flow_close_priority": True,
            "minimum_first_target_rr": MIN_TARGET1_RR,
            "live_chase_guard_pct": LIVE_CHASE_PCT,
            "entry_zone_max_pct": 15,
            "requires_5m_confirmation": True,
            "auto_timeframes_minutes": [240, 60, 15, 5],
            "uses_completed_intraday_candles_only": True,
            "planned_entry_weights_pct": [30, 30, 40],
            "averaging_below_stop_forbidden": True,
            "same_market_max_entries_per_day": 2,
            "same_market_cooldown_minutes": 30,
            "loss_cooldown_minutes": 120,
            "max_consecutive_losses": 2,
            "daily_loss_limit_pct": 2.0,
        },
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = [
        "# UPBIT KRW 일봉 매수존·중심존·매도존 스캔",
        "",
        f"- 생성 시각(KST): {generated_at}",
        f"- 데이터 기준일: {market_date}",
        f"- 유니버스: {len(universe)}페어",
        f"- 기준: 업비트 {QUOTE_CURRENCY} 마켓 / 24시간 거래대금 {MIN_24H_TRADE_AMOUNT:,.0f}원 이상",
        f"- 시장경보 제외: {EXCLUDE_WARNING} / 주의 이벤트 제외: {EXCLUDE_CAUTION}",
        f"- OHLCV 확보: {len(frames)}페어",
        f"- 최종 후보: {len(records)}페어",
        "- 전략 버전: upbit-buy-center-sell-flow-v5-learning-risk-control",
        f"- 엄격/완화/관찰보충: {mode_counts.get('엄격', 0)} / {mode_counts.get('완화', 0)} / {mode_counts.get('관찰보충', 0)}",
        f"- 진입조건충족/5분봉 확인대기/관망: {gate_counts.get('진입조건충족', 0)} / {gate_counts.get('5분봉 확인대기', 0)} / {gate_counts.get('관망', 0)}",
        "",
        "> 후보 선별은 마지막 완성 일봉 기준이며, 최종 실전판정은 완성 4시간·1시간·15분·5분봉을 자동 확인합니다. 1차 익절가 기준 손익비 1 미만은 자동 관망입니다. 분할매수는 30%·30%·40%, 분할익절은 35%·35%·30%입니다.",
        "",
        md_table(records),
        "",
        "## 개별 리딩 파일",
        "",
        "- 일봉 JSON: `outputs/daily/{종목코드}.json`",
        "- 멀티타임프레임 JSON: `outputs/intraday/{종목코드}.json`",
        "- 레벨 차트: `outputs/charts/{종목코드}.html`",
        "- 전체 차트 목록: `outputs/index.html`",
    ]
    (OUTPUT_DIR / "latest_report.md").write_text("\n".join(report), encoding="utf-8")
    learning = aggregate_performance(load_trade_history(ROOT / "data" / "trade_history.csv"))
    write_learning_outputs(OUTPUT_DIR, learning)
    write_index(records, market_date)


def write_failure_metadata(exc: Exception) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "failed",
        "generated_at_kst": datetime.now(KST).isoformat(timespec="seconds"),
        "error": str(exc),
        "note": "이 파일은 마지막 실행 실패 상태만 기록합니다. 기존 성공 결과는 삭제하지 않습니다.",
    }
    (OUTPUT_DIR / "last_run_error.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    setup_logging()
    logging.info("UPBIT KRW 박스 스캔 시작")
    try:
        universe = fetch_universe()
        frames, sources, failed = collect_daily_data(universe)
        records = select_candidates(universe, frames)
        intraday_frames, intraday_failed = collect_intraday_data(records)
        apply_intraday_gates(records, intraday_frames)
        write_outputs(records, universe, frames, sources, failed, intraday_frames, intraday_failed)
        error_file = OUTPUT_DIR / "last_run_error.json"
        if error_file.exists():
            error_file.unlink()
        logging.info("완료: %d페어", len(records))
        print(pd.DataFrame(records).to_string(index=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        logging.exception("스캔 실패")
        write_failure_metadata(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
