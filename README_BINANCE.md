# 오코탐 BINANCE · Spot USDT

기존 UPBIT 오코탐과 **데이터/API/유니버스/기록을 섞지 않는** Binance Spot USDT 전용판이다.

## 1차 범위

- Binance Spot `USDT` 현물 전용
- 24시간 Quote Volume 유동성 필터
- 완성 일봉 + 완성 4시간봉 기반 A/B/C/D/E 후보
- BTCUSDT 30일 박스와 M0~M5 시장 단계
- 시장 단계별 A~E 진입 게이트
- 진입구간 / 손절 / TP1 / RR
- 관심종목 별표(localStorage)
- 날짜별 스캔 기록
- GitHub Actions 자동 실행 및 Pages 배포

## 완전 분리 원칙

- UPBIT: `scanner/`, `history/`, `outputs/`
- BINANCE: `scanner_binance/`, `history/binance/`, `outputs/binance/`
- Binance판은 Upbit API, KRW 유니버스, KRW tick size를 호출하지 않는다.
- 공통으로 유지하는 것은 A~E 전략 철학과 M0~M5 행동 원칙뿐이다.

## 자동 실행

Binance 4시간봉은 UTC 00/04/08/12/16/20 마감이며 KST로 09/13/17/21/01/05시다.
전용 워크플로는 각 마감 이후 08/18/28/38분에 재시도하고 `history/binance/schedule_state.json`으로 중복 실행을 막는다.

## 웹

GitHub Pages 기준:

- UPBIT: `/today-coin-explorer/index.html`
- BINANCE: `/today-coin-explorer/binance/index.html`

## Futures 2차 확장

1차 버전은 Spot 차트 구조만 사용한다. 이후 별도 컨텍스트 모듈로 아래를 추가할 수 있다.

- Open Interest
- Funding Rate
- Top Trader Long/Short Positions
- Taker Buy/Sell Volume

이 데이터는 A~E 유형을 새로 만들지 않고, 이미 잡힌 후보의 **확인/과열 경고 컨텍스트**로만 사용한다.
