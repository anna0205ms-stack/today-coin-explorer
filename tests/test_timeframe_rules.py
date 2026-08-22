import importlib.util
import unittest
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "scanner" / "timeframe_rules.py"
SPEC = importlib.util.spec_from_file_location("timeframe_rules", MODULE_PATH)
RULES = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(RULES)


def frame(rows):
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"])


class TimeframeRuleTests(unittest.TestCase):
    def setUp(self):
        self.structure = frame([
            [105, 107, 101, 104, 100],
            [104, 106, 100, 103, 90],
            [103, 105, 99, 102, 80],
        ])
        self.f15 = frame([
            [104, 105, 102, 103, 100],
            [103, 104, 101, 102, 100],
            [102, 103, 100, 101, 90],
            [101, 103, 100, 102, 80],
            [102, 103, 101, 102, 70],
            [102, 104, 101, 103, 75],
            [103, 104, 102, 103, 70],
            [103, 105, 102, 104, 80],
        ])
        self.f5_confirmed = frame([
            [104, 105, 102, 103, 100],
            [103, 104, 100, 101, 100],
            [101, 102, 99, 100, 90],
            [100, 102, 99, 101, 80],
            [101, 102, 100, 101, 70],
            [101, 104, 100, 103, 100],
        ])

    def test_full_confirmation(self):
        result = RULES.multi_timeframe_gate(
            daily_status="5분봉 확인대기",
            frames={240: self.structure, 60: self.structure, 15: self.f15, 5: self.f5_confirmed},
            buy_low=98,
            buy_high=104,
            stop=95,
        )
        self.assertEqual(result["status"], "진입조건충족")

    def test_stop_breach_blocks(self):
        broken = self.structure.copy()
        broken.loc[broken.index[-1], "Low"] = 94
        result = RULES.multi_timeframe_gate(
            daily_status="5분봉 확인대기",
            frames={240: broken, 60: self.structure, 15: self.f15, 5: self.f5_confirmed},
            buy_low=98,
            buy_high=104,
            stop=95,
        )
        self.assertEqual(result["status"], "관망")
        self.assertIn("4시간봉 하단 훼손", result["reasons"])

    def test_no_five_minute_turn_keeps_waiting(self):
        falling = self.f5_confirmed.copy()
        falling.iloc[-1] = [103, 103, 100, 100, 150]
        result = RULES.multi_timeframe_gate(
            daily_status="5분봉 확인대기",
            frames={240: self.structure, 60: self.structure, 15: self.f15, 5: falling},
            buy_low=98,
            buy_high=104,
            stop=95,
        )
        self.assertEqual(result["status"], "5분봉 확인대기")


if __name__ == "__main__":
    unittest.main()
