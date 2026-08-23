from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

from technical_rebound import TARGET_FIB, _last_crash_leg, analyze_market


def make_daily() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=180, freq="D")
    close = np.full(180, 92.0)
    close[20:30] = 72.0  # 과거 하단 저점 군집
    close[130:155] = np.linspace(95, 120, 25)
    close[155:176] = np.linspace(118, 70, 21)
    close[176:] = [72, 73, 74, 75]
    frame = pd.DataFrame(index=dates)
    frame["Open"] = close * 1.01
    frame["High"] = close * 1.025
    frame["Low"] = close * 0.975
    frame["Close"] = close
    frame["Volume"] = 100.0
    frame.loc[dates[173:177], "Volume"] = 300.0
    frame["Amount"] = frame["Close"] * frame["Volume"]
    return frame


def make_four_hour() -> pd.DataFrame:
    dates = pd.date_range("2026-06-28", periods=12, freq="4h")
    close = np.array([75, 73, 71, 69, 70, 69.5, 70.5, 71, 72, 73, 74, 75], dtype=float)
    frame = pd.DataFrame(index=dates)
    frame["Open"] = close - 0.7
    frame["High"] = close + 0.8
    frame["Low"] = close - 0.8
    frame["Close"] = close
    frame["Volume"] = 100.0
    frame["Amount"] = frame["Close"] * frame["Volume"]
    return frame


def test_crash_leg_requires_real_drawdown_and_lower_support():
    leg = _last_crash_leg(make_daily())
    assert leg is not None
    assert leg["drawdown_pct"] >= 30
    assert "하단" in leg["support_reason"]


def test_e_type_uses_single_fib_0382_exit():
    daily = make_daily()
    row = pd.Series({"Code": "KRW-TEST", "Name": "테스트", "CurrentPrice": 75.0})
    result = analyze_market(row, daily, make_four_hour())
    assert result is not None
    assert result["type"] == "E"
    assert len(result["targets"]) == 1
    assert result["entry"][1] <= result["fib"]["low"] * 1.081
    expected = result["fib"]["low"] + (result["fib"]["high"] - result["fib"]["low"]) * TARGET_FIB
    assert abs(result["targets"][0] - expected) <= 1.0  # KRW 호가 반올림 허용
    assert "전량청산" in result["exit_rule"]
    assert "추세전환 기대 금지" in result["exit_rule"]
