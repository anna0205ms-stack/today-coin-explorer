from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "ojutam"

KRX_2026 = [
    ("2026-01-01", "신정", "휴장"),
    ("2026-02-16", "설 연휴", "휴장"),
    ("2026-02-17", "설날", "휴장"),
    ("2026-02-18", "설 연휴", "휴장"),
    ("2026-03-02", "3·1절 대체공휴일", "휴장"),
    ("2026-05-01", "근로자의 날", "휴장"),
    ("2026-05-05", "어린이날", "휴장"),
    ("2026-05-25", "부처님오신날 대체공휴일", "휴장"),
    ("2026-06-03", "전국동시지방선거일", "휴장"),
    ("2026-07-17", "제헌절", "휴장"),
    ("2026-08-17", "광복절 대체공휴일", "휴장"),
    ("2026-09-24", "추석 연휴", "휴장"),
    ("2026-09-25", "추석", "휴장"),
    ("2026-09-28", "추석 대체공휴일", "휴장"),
    ("2026-10-05", "개천절 대체공휴일", "휴장"),
    ("2026-10-09", "한글날", "휴장"),
    ("2026-12-25", "성탄절", "휴장"),
    ("2026-12-31", "연말휴장", "휴장"),
]

NASDAQ_2026 = [
    ("2026-01-01", "New Year's Day", "휴장"),
    ("2026-01-19", "Martin Luther King Jr. Day", "휴장"),
    ("2026-02-16", "Presidents Day", "휴장"),
    ("2026-04-03", "Good Friday", "휴장"),
    ("2026-05-25", "Memorial Day", "휴장"),
    ("2026-06-19", "Juneteenth", "휴장"),
    ("2026-07-03", "Independence Day (Observed)", "휴장"),
    ("2026-09-07", "Labor Day", "휴장"),
    ("2026-11-26", "Thanksgiving Day", "휴장"),
    ("2026-11-27", "Day after Thanksgiving", "조기폐장 13:00 ET"),
    ("2026-12-24", "Christmas Eve", "조기폐장 13:00 ET"),
    ("2026-12-25", "Christmas Day", "휴장"),
]

START = "<!-- OJUTAM-MARKET-CALENDAR:START -->"
END = "<!-- OJUTAM-MARKET-CALENDAR:END -->"

CSS = """<style id=\"ojutam-market-calendar-style\">
.market-calendar{max-width:1500px;margin:8px auto 0;padding:0 22px;font:12px/1.45 system-ui,'Noto Sans KR',sans-serif;color:#9fb4a9}.market-calendar-box{border:1px solid #244b38;border-radius:12px;background:#07100c;padding:9px 12px}.market-calendar-line{display:flex;gap:8px 12px;align-items:center;flex-wrap:wrap}.market-calendar-title{font-weight:900;color:#dfffee}.market-calendar-status{font-weight:800;color:#00e783}.market-calendar-status.closed{color:#ff8c98}.market-calendar-status.early{color:#ffd45f}.market-calendar-next{color:#b9d0c4}.market-calendar details{margin-top:5px}.market-calendar summary{cursor:pointer;color:#6f8b7e}.market-calendar-list{display:flex;gap:5px 12px;flex-wrap:wrap;margin-top:6px;color:#789489}.market-calendar-list span{white-space:nowrap}@media(max-width:760px){.market-calendar{padding:0 12px;margin-top:6px;font-size:10px}.market-calendar-box{padding:8px 9px}.market-calendar-line{gap:5px 8px}}
</style>"""


def _today(is_us: bool):
    tz = ZoneInfo("America/New_York") if is_us else ZoneInfo("Asia/Seoul")
    return datetime.now(tz).date()


def _status_and_next(items, today):
    today_s = today.isoformat()
    today_item = next((x for x in items if x[0] == today_s), None)
    future = [x for x in items if x[0] > today_s]
    nxt = future[0] if future else None
    if today_item:
        cls = "early" if "조기" in today_item[2] else "closed"
        status = f"오늘 {today_item[2]} · {today_item[1]}"
    elif today.weekday() >= 5:
        cls = "closed"
        status = "오늘 주말 휴장"
    else:
        cls = ""
        status = "오늘 정상 개장일"
    return cls, status, nxt


def _fmt_date(s: str) -> str:
    d = datetime.fromisoformat(s)
    weekday = "월화수목금토일"[d.weekday()]
    return f"{d.month}/{d.day}({weekday})"


def block(is_us: bool) -> str:
    items = NASDAQ_2026 if is_us else KRX_2026
    market = "NASDAQ" if is_us else "KRX"
    today = _today(is_us)
    cls, status, nxt = _status_and_next(items, today)
    next_text = "올해 예정 휴장 없음" if not nxt else f"다음 일정 {_fmt_date(nxt[0])} · {nxt[1]} · {nxt[2]}"
    rows = "".join(f"<span>{_fmt_date(d)} {name} · {kind}</span>" for d, name, kind in items if d >= today.isoformat())
    note = "미국 동부시간(ET) 기준" if is_us else "한국시간(KST) 기준"
    return (
        START + CSS +
        '<section class="market-calendar"><div class="market-calendar-box">'
        '<div class="market-calendar-line">'
        f'<span class="market-calendar-title">📅 {market} 휴장일</span>'
        f'<span class="market-calendar-status {cls}">{status}</span>'
        f'<span class="market-calendar-next">{next_text}</span>'
        f'<span>· {note}</span>'
        '</div>'
        '<details><summary>2026 휴장·조기폐장 일정 보기</summary>'
        f'<div class="market-calendar-list">{rows}</div></details>'
        '</div></section>' + END
    )


def patch(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    text = re.sub(re.escape(START) + r".*?" + re.escape(END), "", text, flags=re.S)
    rel = path.relative_to(OUT)
    is_us = bool(rel.parts and rel.parts[0] == "us")
    insert_at = text.lower().find("<div class=\"wrap\"")
    if insert_at < 0:
        body_end = text.lower().find(">", text.lower().find("<body"))
        insert_at = body_end + 1 if body_end >= 0 else 0
    text = text[:insert_at] + block(is_us) + text[insert_at:]
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    pages = list(OUT.rglob("*.html")) if OUT.exists() else []
    for p in pages:
        patch(p)
    print("OJUTAM market calendar patched:", len(pages))


if __name__ == "__main__":
    main()
