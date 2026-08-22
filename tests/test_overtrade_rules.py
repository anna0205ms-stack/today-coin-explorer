import importlib.util
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scanner" / "overtrade_rules.py"
SPEC = importlib.util.spec_from_file_location("overtrade_rules", MODULE_PATH)
RULES = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(RULES)
KST = timezone(timedelta(hours=9))


class OvertradeRuleTests(unittest.TestCase):
    def test_third_same_market_entry_is_blocked(self):
        rows = [
            {"market": "KRW-SOON", "entry_time_kst": "2026-08-01T09:00:00+09:00", "exit_time_kst": "2026-08-01T09:10:00+09:00", "net_pnl_krw": "1000"},
            {"market": "KRW-SOON", "entry_time_kst": "2026-08-01T12:00:00+09:00", "exit_time_kst": "2026-08-01T12:10:00+09:00", "net_pnl_krw": "2000"},
        ]
        result = RULES.evaluate_overtrade(rows, market="KRW-SOON", now_kst=datetime(2026, 8, 1, 15, 0, tzinfo=KST))
        self.assertEqual(result["status"], "진입금지")
        self.assertTrue(any("2회" in reason for reason in result["reasons"]))

    def test_loss_requires_longer_cooldown(self):
        rows = [{"market": "KRW-MMT", "entry_time_kst": "2026-08-01T10:00:00+09:00", "exit_time_kst": "2026-08-01T10:10:00+09:00", "net_pnl_krw": "-5000"}]
        result = RULES.evaluate_overtrade(rows, market="KRW-MMT", now_kst=datetime(2026, 8, 1, 11, 0, tzinfo=KST))
        self.assertEqual(result["status"], "진입금지")
        self.assertTrue(any("120분" in reason for reason in result["reasons"]))

    def test_daily_loss_limit_blocks(self):
        rows = [{"market": "KRW-A", "entry_time_kst": "2026-08-01T10:00:00+09:00", "exit_time_kst": "2026-08-01T10:10:00+09:00", "net_pnl_krw": "-40000"}]
        result = RULES.evaluate_overtrade(rows, market="KRW-B", now_kst=datetime(2026, 8, 1, 15, 0, tzinfo=KST), trading_capital_krw=2000000)
        self.assertEqual(result["status"], "진입금지")
        self.assertTrue(any("손실한도" in reason for reason in result["reasons"]))


if __name__ == "__main__":
    unittest.main()
