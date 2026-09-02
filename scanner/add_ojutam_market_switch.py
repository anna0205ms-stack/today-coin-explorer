from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OJUTAM = ROOT / "outputs" / "ojutam"

STYLE = r'''<style id="ojutam-market-switch-style">
#ojutam-market-switch{display:flex;justify-content:center;padding:7px 12px 0;background:#030605;font-family:system-ui,"Noto Sans KR",sans-serif}
#ojutam-market-switch .inner{display:grid;grid-template-columns:1fr 1fr;gap:4px;width:min(520px,100%);padding:4px;border:1px solid #244b38;border-radius:12px;background:#06100b}
#ojutam-market-switch a{display:flex;justify-content:center;align-items:center;gap:6px;min-height:36px;padding:7px;border-radius:8px;color:#8fa399;text-decoration:none;font-weight:800}
#ojutam-market-switch a span{font-size:11px;color:#698277}
#ojutam-market-switch a.active{color:#00e783;background:#0b2619;box-shadow:inset 0 0 0 1px #00e783}
</style>'''


def href(page: Path, target: Path) -> str:
    return os.path.relpath(target, page.parent).replace(os.sep, "/")


def patch(page: Path) -> bool:
    text = page.read_text(encoding="utf-8")
    if "<body" not in text.lower():
        return False
    is_us = OJUTAM / "us" in page.parents
    name = page.name
    kr = OJUTAM / name
    us = OJUTAM / "us" / name
    # Every generated US page mirrors the domestic page name.
    bar = (
        '<div id="ojutam-market-switch" aria-label="주식 시장 전환"><div class="inner">'
        f'<a class="{"active" if not is_us else ""}" href="{href(page, kr)}">국장 <span>| KRX</span></a>'
        f'<a class="{"active" if is_us else ""}" href="{href(page, us)}">미장 <span>| NASDAQ</span></a>'
        '</div></div>'
    )
    text = re.sub(r'<style id="ojutam-market-switch-style">.*?</style>', "", text, flags=re.S)
    text = re.sub(r'<div id="ojutam-market-switch".*?</div></div>', "", text, count=1, flags=re.S)
    text = text.replace("</head>", STYLE + "</head>", 1)
    marker = re.search(r'<div id="explorer-switcher".*?</div></div>', text, flags=re.S)
    if marker:
        text = text[:marker.end()] + bar + text[marker.end():]
    else:
        text = re.sub(r'(<body[^>]*>)', r'\1' + bar, text, count=1, flags=re.I)
    page.write_text(text, encoding="utf-8")
    return True


def main():
    count = 0
    for page in OJUTAM.rglob("*.html"):
        count += int(patch(page))
    print("OJUTAM market switch patched:", count)


if __name__ == "__main__":
    main()
