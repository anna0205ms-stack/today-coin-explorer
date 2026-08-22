import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scanner" / "strategy_rules.py"
SPEC = importlib.util.spec_from_file_location("strategy_rules", MODULE_PATH)
SCREENER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(SCREENER)


class StrategyRuleTests(unittest.TestCase):
    def test_reward_risk_uses_first_target(self):
        self.assertEqual(SCREENER.reward_risk(100, 95, 105), 1.0)
        self.assertEqual(SCREENER.reward_risk(100, 100, 110), 0.0)
        self.assertEqual(SCREENER.reward_risk(100, 95, 99), 0.0)

    def test_execution_gate_waits_for_five_minute_confirmation(self):
        status, reasons, live_pos, live_move = SCREENER.execution_gate(
            analysis_close=100,
            live_price=101,
            buy_low=95,
            buy_high=105,
            box_top=150,
            center_low=120,
            first_target_rr=1.2,
            flow="매수존 반등대기",
        )
        self.assertEqual(status, "5분봉 확인대기")
        self.assertEqual(reasons, [])
        self.assertGreater(live_pos, 0)
        self.assertAlmostEqual(live_move, 1.0)

    def test_execution_gate_blocks_entry_above_buy_zone(self):
        status, reasons, _, _ = SCREENER.execution_gate(
            analysis_close=100,
            live_price=110,
            buy_low=95,
            buy_high=105,
            box_top=150,
            center_low=120,
            first_target_rr=1.5,
            flow="매수존 반등대기",
        )
        self.assertEqual(status, "관망")
        self.assertTrue(any("매수존 상단 초과" in reason for reason in reasons))
        self.assertTrue(any("급등" in reason for reason in reasons))

    def test_execution_gate_blocks_first_target_rr_below_one(self):
        status, reasons, _, _ = SCREENER.execution_gate(
            analysis_close=100,
            live_price=100,
            buy_low=95,
            buy_high=105,
            box_top=150,
            center_low=120,
            first_target_rr=0.99,
            flow="매수존 반등대기",
        )
        self.assertEqual(status, "관망")
        self.assertTrue(any("1차 익절 손익비" in reason for reason in reasons))

    def test_execution_gate_blocks_strong_downtrend(self):
        status, reasons, _, _ = SCREENER.execution_gate(
            analysis_close=100,
            live_price=100,
            buy_low=95,
            buy_high=105,
            box_top=150,
            center_low=120,
            first_target_rr=1.2,
            flow="강한 하락",
        )
        self.assertEqual(status, "관망")
        self.assertTrue(any("강한 하락" in reason for reason in reasons))

    def test_krw_tick_size_and_trade_plan(self):
        self.assertEqual(SCREENER.krw_tick_size(292), 1.0)
        self.assertEqual(SCREENER.krw_tick_size(15.1), 0.1)
        plan = SCREENER.build_trade_plan(
            buy_low=280,
            buy_high=295,
            box_span=100,
            target1=310,
            target2=350,
            target3=380,
        )
        self.assertEqual(plan["entry_levels"], [295.0, 287.0, 282.0])
        self.assertEqual(plan["entry_weights_pct"], [30, 30, 40])
        self.assertEqual(plan["stop"], 271.0)
        self.assertGreaterEqual(plan["first_target_rr"], 0)


if __name__ == "__main__":
    unittest.main()
