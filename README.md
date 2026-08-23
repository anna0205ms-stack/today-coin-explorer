# UPBIT A/B/C/D/E 스캐너 — MVP Lite v4

비트코인 큰 추세를 먼저 보고, 업비트 KRW 코인을 A/B/C/D/E 차트 유형으로 나눠 매매 후보를 찾는 가벼운 스캐너야. 공개 시세만 읽고 주문은 실행하지 않아.

## 화면 사용 순서

1. `outputs/index.html`에서 M0~M5 시장 단계, BTC.D·TOTAL2·OTHERS, 오늘의 알트 진입 한도를 확인해.
2. `outputs/scan.html`에서 전체 후보의 단계·진입거리·손절·목표·손익비를 비교해.
3. A/B/C/D/E 유형 화면에서 필요한 후보를 여러 개 펼쳐 차트를 비교해.
4. 계속 볼 종목은 별표를 눌러 고정하고 `outputs/watchlist.html`에서 추적해.
5. `outputs/history.html`에서 과거 후보의 24시간·72시간 결과를 복기해.

## A/B/C/D/E 유형

- A형: 강한 상승 뒤 첫 눌림에서 지지를 확인하는 유형
- B형: 긴 하락 뒤 바닥·박스 하단에서 반등을 찾는 유형
- C형: 박스 상단 돌파 뒤 재지지와 추가 상승을 보는 유형
- D형: 바닥 압축과 매물대 재탈환 뒤 급등 전 흐름을 찾는 유형
  - D0 바닥 압축 후보 → D1 하단선 재탈환 → D2 하단 리테스트 확인
  - D3 상단 돌파·확장 → D4 확장 후 상단 리테스트 재진입
  - D-W: 상단 돌파 반납 또는 하단선 첫 이탈 경고
  - D-F: 재탈환 뒤 하단선 아래 완성 4시간봉 2개 연속 마감
- E형: 급락·투매 뒤 핵심 하단에서 확인되는 1회성 기술적 반등을 피보나치 0.382까지만 노리는 유형

E형은 상승 전환을 기대하는 전략이 아니다. 투매저점 방어와 4시간봉 반등을 확인한 뒤 진입하며,
급락 파동의 피보나치 0.382에서 전량청산한다. 투매저점 3% 하단 이탈 시 종료하고 물타기는 금지한다.

## M0~M5 시장 단계와 알트 진입 허용

- BTC 일봉·완성 4시간봉 구조와 BTC.D·TOTAL2·OTHERS 자금 흐름을 합쳐 M0~M5를 판정해.
- M0 위험장 → M1 BTC만 강함 → M2 알트 준비 → M3 알트 시작 → M4 알트 확산 → M5 과열 경계 순서야.
- 각 M단계에는 A/B/C/D/E별 `진입 허용·조건부·관찰만·신규 금지·익절 우선` 게이트가 있어.
- 후보의 개별 차트 판정은 `pattern_action`에 보존하고, 시장 게이트를 반영한 최종 행동은 `action`에 저장해.
- TradingView 차트는 화면 확인용 원본 지수이고, 자동판정은 CoinGecko 공개 시총으로 만든 프록시를 사용해.
- 글로벌 데이터가 없거나 오래되면 안전하게 M0로 차단하되 후보 자체는 지우지 않아.

## 기록과 관심종목

- 스캔 결과는 `history/snapshots.json`에 마감시간별로 쌓여. 새 결과가 이전 기록을 지우지 않아.
- 한 번 관심목록에 들어온 종목은 다음 조건에서 빠져도 `조건 약화`로 남아 있어.
- 구조 무효일 때만 자동 보관해.
- 별표 고정은 현재 브라우저에 바로 저장되고 자동 보관되지 않아.
- MVP라 로그인·다중 사용자 계정은 넣지 않았어.

## 자동 실행

GitHub Actions는 KST 01:10·05:10·09:10·13:10·17:10·21:10에 스캔해. 09:10 기록은 오전 9시 마감 일봉과 4시간봉을 함께 반영해.

## 로컬 실행

Windows에서는 `실행하기.bat`을 실행해. 직접 실행하려면:

```bash
pip install -r scanner/requirements.txt
python scanner/box_screener.py
python scanner/pre_breakout_reclaim.py --all --workers 8 --min-trade-amount 3000000000 --output-json outputs/pre_breakout_reclaim.json --output-csv outputs/pre_breakout_reclaim.csv
python scanner/technical_rebound.py
python scanner/bitcoin_regime.py
python scanner/global_market_data.py
python scanner/market_regime.py
python scanner/chart_cache.py
python scanner/history_store.py
python scanner/watchlist_store.py
python scanner/outcome_tracker.py
python scanner/unified_dashboard.py
```

GitHub Pages를 쓸 때는 저장소 Settings → Pages → Source를 `GitHub Actions`로 선택하면 돼.
