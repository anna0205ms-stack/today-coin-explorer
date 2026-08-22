import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scanner" / "trade_learning.py"
SPEC = importlib.util.spec_from_file_location("trade_learning", MODULE_PATH)
LEARNING = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(LEARNING)


class TradeLearningTests(unittest.TestCase):
    def test_aggregate_by_signature(self):
        rows = [
            {"status": "완료", "entry_signature": "하단", "net_pnl_krw": "100", "deployed_capital_krw": "1000"},
            {"status": "완료", "entry_signature": "하단", "net_pnl_krw": "-50", "deployed_capital_krw": "1000"},
            {"status": "보유 중", "entry_signature": "추격", "net_pnl_krw": "", "deployed_capital_krw": "1000"},
        ]
        result = LEARNING.aggregate_performance(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["trades"], 2)
        self.assertEqual(result[0]["win_rate_pct"], 50.0)
        self.assertEqual(result[0]["net_pnl_krw"], 50.0)
        self.assertEqual(result[0]["profit_factor"], 2.0)


if __name__ == "__main__":
    unittest.main()
