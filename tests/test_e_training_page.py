import unittest

from scanner.unified_dashboard import training_page, type_page


class ETrainingPageTests(unittest.TestCase):
    def setUp(self):
        self.basis = {
            "date": "2026-08-24",
            "time": "01:00",
            "snapshot_at": "2026-08-24T01:00:00+09:00",
            "market_regime": {
                "stage": "M0",
                "gates": {"E": {"code": "BLOCK", "label": "신규 금지", "reason": "테스트 시장 게이트"}},
            },
            "candidates": [
                {
                    "market": "KRW-TEST",
                    "type": "E",
                    "action": "시장 대기",
                    "pattern_action": "진입 검토",
                    "market_gate": {"stage": "M0", "label": "신규 금지", "reason": "테스트 시장 게이트"},
                    "score": 88,
                    "price": 100,
                    "entry": [96, 104],
                    "stop": 90,
                    "targets": [118],
                    "rr": 1.5,
                    "reason": "급락 후 하단 반등",
                    "missing": [],
                    "charts": {},
                }
            ],
        }

    def test_type_page_is_pattern_group_only(self):
        page = type_page("E", self.basis)
        self.assertIn("진입 검토", page)
        self.assertNotIn("테스트 시장 게이트", page)
        self.assertNotIn("시장 반영 최종판단", page)
        self.assertNotIn("신규 금지", page)

    def test_e_training_contains_expanded_textbook(self):
        page = training_page("E", self.basis)
        for text in [
            "일봉 · 급락 위치",
            "4시간봉 · 저점 방어",
            "15분봉 · 매도 둔화",
            "5분봉 · 실행 진입",
            "E0~E-F 단계 의미",
            "성공 · 경고 · 실패 복기",
            "진입 전 최종 체크",
            "0.382 지정가 전량청산",
        ]:
            self.assertIn(text, page)

    def test_training_navigation_contains_e(self):
        page = training_page("E", self.basis)
        self.assertIn('href="training_e.html"', page)


if __name__ == "__main__":
    unittest.main()
