from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

# 자동 scan/schedule 커밋은 제외하고, 사용자 요청으로 묶이는 의미 있는 기능 변경만 기록한다.
HISTORY = {
    "oco": {
        "label": "OCO LAB · 오늘의 코인 탐험대",
        "revision": 12,
        "entries": [
            ("2026-09-08", "R12", "전 페이지 JIWON 발행/저작권·복제금지·버전 타임라인 적용"),
            ("2026-09-07", "R11", "저유동성 종목 제외 기준 및 스캔 재시도 안정화"),
            ("2026-09-02", "R10", "모바일 최근 업데이트 시각·검색 접근성 보강"),
            ("2026-08-31", "R9", "BTC 과거 횡보 구조 기준 박스 재산정 및 차트 연동"),
            ("2026-08-31", "R8", "모바일 보조차트 이동·팬·가독성 개선"),
            ("2026-08-24", "R7", "확정 PC·모바일 메인 대시보드 UI 및 숙돌이 자산 반영"),
            ("2026-08-24", "R6", "BTC·BTC.D·TOTAL2·OTHERS 시장단계 M0~M5 및 상승/조정 시나리오 구조 확장"),
            ("2026-08-24", "R5", "통합 시장 대시보드·시장 단계/후보 압축 구조 적용"),
            ("2026-08-23", "R4", "관심/추적·구조무효 보관·변화기록 및 알림 흐름 보강"),
            ("2026-08-23", "R3", "F형 과거 매물대 하단/중앙/상단 구조와 변화기록 확장"),
            ("2026-08-23", "R2", "E형 급락 후 기술적 반등·훈련소/사례 구조 추가"),
            ("2026-08-22", "R1", "A~D 패턴 후보·현재판단·루딩식 대응 구조의 기본 골격 정리"),
        ],
    },
    "oju": {
        "label": "OJU LAB · 오늘의 주식 탐험대",
        "revision": 10,
        "entries": [
            ("2026-09-08", "R10", "전 페이지 JIWON 발행/저작권·복제금지·버전 타임라인 적용"),
            ("2026-09-08", "R9", "A~G 유형별 30개 제한 제거·실제 전체 탐지 개수 표시"),
            ("2026-09-07", "R8", "현재 위치 중심 우선순위·평균진입·구조손절·1차/2차 목표 적용"),
            ("2026-09-07", "R7", "주봉 EMA50 첫 터치 G형 및 거래 유동성 필터 보강"),
            ("2026-09-02", "R6", "KRX 평일 15:40·20:00 KST 자동 갱신 일정 확정"),
            ("2026-09-02", "R5", "NASDAQ 스캐너·US100/DXY 및 미장 시간봉 연결"),
            ("2026-08-31", "R4", "종목 클릭 하단 상세·현재판단/남은조건·매매안 UI 도입"),
            ("2026-08-31", "R3", "A~F 일봉 패턴 그룹형 전체 스캔 대시보드 적용"),
            ("2026-08-31", "R2", "KOSPI/KOSDAQ 인터랙티브 시장차트 및 국장 대시보드 확장"),
            ("2026-08-31", "R1", "오주탐 KRX 일봉 차트 탐색기 최초 공개 골격 생성"),
        ],
    },
}

START = "<!-- JIWON-RELEASE-FOOTER:START -->"
END = "<!-- JIWON-RELEASE-FOOTER:END -->"

CSS = """<style id=\"jiwon-release-footer-style\">
.jiwon-release-footer{max-width:1640px;margin:52px auto 18px;padding:19px 18px;border-top:1px solid rgba(70,150,112,.28);color:#789489;font:11px/1.55 system-ui,'Noto Sans KR',sans-serif}.jiwon-release-main{display:flex;gap:8px 16px;align-items:center;flex-wrap:wrap}.jiwon-release-main b{color:#b9d0c4;letter-spacing:.04em}.jiwon-release-footer details{margin-top:9px}.jiwon-release-footer summary{cursor:pointer;color:#8ba89a}.jiwon-release-timeline{display:grid;gap:6px;margin-top:9px}.jiwon-release-row{display:grid;grid-template-columns:82px 38px 1fr;gap:8px;padding:6px 0;border-top:1px solid rgba(70,150,112,.12)}.jiwon-release-note{margin-top:5px;color:#5f776b}@media(max-width:620px){.jiwon-release-footer{margin-top:34px;padding:15px 12px}.jiwon-release-row{grid-template-columns:74px 34px 1fr;font-size:10px}}
</style>"""


def block(product: str) -> str:
    cfg = HISTORY[product]
    rows = "".join(
        f'<div class="jiwon-release-row"><span>{date}</span><b>{rev}</b><span>{text}</span></div>'
        for date, rev, text in cfg["entries"]
    )
    return (
        START + CSS +
        '<footer class="jiwon-release-footer">'
        '<div class="jiwon-release-main">'
        f'<b>Published by JIWON</b><span>{cfg["label"]}</span><span>Revision {cfg["revision"]}</span>'
        '</div>'
        '<div>© 2026 JIWON. All Rights Reserved. · Unauthorized copying, reproduction or redistribution prohibited.</div>'
        '<details><summary>Version history · 업데이트 기록</summary>'
        f'<div class="jiwon-release-timeline">{rows}</div></details>'
        '<div class="jiwon-release-note">Revision count excludes automated scan/schedule refresh commits and groups one requested feature change as one revision.</div>'
        '</footer>' + END
    )


def clean_old(text: str) -> str:
    text = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', text, flags=re.S)
    text = re.sub(r'<style id="ojutam-release-footer-style">.*?</style>', '', text, flags=re.S)
    text = re.sub(r'<footer class="ojutam-release-footer".*?</footer>', '', text, flags=re.S)
    return text


def inject(path: Path, product: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    if "</body>" not in text.lower():
        return False
    text = clean_old(text)
    idx = text.lower().rfind("</body>")
    text = text[:idx] + block(product) + text[idx:]
    path.write_text(text, encoding="utf-8")
    return True


def apply(product: str) -> int:
    n = 0
    if product == "oju":
        paths = (OUT / "ojutam").rglob("*.html") if (OUT / "ojutam").exists() else []
        for p in paths:
            n += int(inject(p, "oju"))
    elif product == "oco":
        for p in OUT.rglob("*.html"):
            if (OUT / "ojutam") in p.parents:
                continue
            n += int(inject(p, "oco"))
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", choices=["oco", "oju", "all"], default="all")
    args = ap.parse_args()
    products = ["oco", "oju"] if args.product == "all" else [args.product]
    for product in products:
        print(product, "footer pages", apply(product))


if __name__ == "__main__":
    main()
