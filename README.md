# UPBIT A/B/C/D 스캐너 — MVP Lite v3

비트코인 큰 추세를 먼저 보고, 업비트 KRW 코인을 A/B/C/D 차트 유형으로 나눠 매매 후보를 찾는 가벼운 스캐너야. 공개 시세만 읽고 주문은 실행하지 않아.

## 화면 사용 순서

1. `outputs/index.html`에서 BTC 일봉·4시간봉과 오늘의 알트 진입 강도를 확인해.
2. `outputs/scan.html`에서 전체 후보의 단계·진입거리·손절·목표·손익비를 비교해.
3. A/B/C/D 유형 화면에서 필요한 후보를 여러 개 펼쳐 차트를 비교해.
4. 계속 볼 종목은 별표를 눌러 고정하고 `outputs/watchlist.html`에서 추적해.
5. `outputs/history.html`에서 과거 후보의 24시간·72시간 결과를 복기해.

## A/B/C/D 유형

- A형: 강한 상승 뒤 첫 눌림에서 지지를 확인하는 유형
- B형: 긴 하락 뒤 바닥·박스 하단에서 반등을 찾는 유형
- C형: 박스 상단 돌파 뒤 재지지와 추가 상승을 보는 유형
- D형: 바닥 압축과 매물대 재탈환 뒤 급등 전 흐름을 찾는 유형

## BTC와 알트 진입 강도

- BTC 일봉 오전 9시 마감으로 큰 추세와 박스를 잡아.
- 완성 4시간봉으로 횡보·재지지·돌파 실패를 확인해.
- 박스 하단은 매수존, 상단은 매도존으로 봐.
- BTC가 매도존에 가까우면 알트 신규진입을 줄이고, 상단 돌파 실패나 구조 이탈이면 0%로 막아.
- 0%여도 후보는 사라지지 않고 `거래금지·관찰만`으로 계속 보여.

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
python scanner/bitcoin_regime.py
python scanner/chart_cache.py
python scanner/history_store.py
python scanner/watchlist_store.py
python scanner/outcome_tracker.py
python scanner/unified_dashboard.py
```

GitHub Pages를 쓸 때는 저장소 Settings → Pages → Source를 `GitHub Actions`로 선택하면 돼.
