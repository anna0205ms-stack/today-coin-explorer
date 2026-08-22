@echo off
chcp 65001 > nul
cd /d "%~dp0"

where py > nul 2>&1
if errorlevel 1 (
  echo Python이 설치되어 있지 않거나 PATH에 등록되지 않았습니다.
  echo python.org에서 Python 3.11 이상 설치 후 다시 실행하세요.
  pause
  exit /b 1
)

if not exist .venv (
  echo [1/6] 가상환경 생성 중...
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat

echo [2/6] 필요한 패키지 설치/업데이트 중...
python -m pip install --upgrade pip
pip install -r scanner\requirements.txt
if errorlevel 1 goto :error

echo [3/6] 기존 A/B/C 업비트 KRW 코인 스캔 실행 중...
python scanner\box_screener.py
if errorlevel 1 goto :error

echo [4/6] 급등 전 D형 재탈환·압축 스캔 실행 중...
python scanner\pre_breakout_reclaim.py --all --min-trade-amount 3000000000 --output-json outputs\pre_breakout_reclaim.json --output-csv outputs\pre_breakout_reclaim.csv
if errorlevel 1 goto :error

echo [5/6] 상위 후보 차트와 현재 결과를 저장 중...
python scanner\bitcoin_regime.py
if errorlevel 1 goto :error
python scanner\chart_cache.py
if errorlevel 1 goto :error
python scanner\history_store.py
if errorlevel 1 goto :error
python scanner\watchlist_store.py
if errorlevel 1 goto :error
python scanner\outcome_tracker.py
if errorlevel 1 goto :error

echo [6/6] A/B/C/D Lite 화면 생성 중...
python scanner\unified_dashboard.py
if errorlevel 1 goto :error

echo.
echo 완료되었습니다.
echo outputs\index.html 을 확인하세요.
start "" "%~dp0outputs\index.html"
pause
exit /b 0

:error
echo.
echo 실행 중 오류가 발생했습니다.
echo outputs\logs\latest.log 또는 outputs\last_run_error.json 을 확인하세요.
pause
exit /b 1
