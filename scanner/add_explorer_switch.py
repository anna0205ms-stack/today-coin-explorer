from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
MARKER = "explorer-switcher"

STYLE = r'''<style id="explorer-switcher-style">
#explorer-switcher{max-width:1500px;margin:10px auto 0;padding:0 22px;display:flex;justify-content:flex-end;position:relative;z-index:90;font-family:system-ui,"Noto Sans KR",sans-serif}
#explorer-switcher .explorer-switch-inner{display:inline-flex;gap:3px;padding:4px;border:1px solid #244b38;border-radius:13px;background:#06100b;box-shadow:0 6px 18px rgba(0,0,0,.22)}
#explorer-switcher a{display:flex;align-items:center;gap:7px;min-height:36px;padding:7px 12px;border:0!important;border-radius:9px!important;background:transparent!important;color:#8fa399!important;text-decoration:none!important;font-size:12px!important;font-weight:800!important;line-height:1!important;white-space:nowrap}
#explorer-switcher a span{font-size:10px;color:#698277;font-weight:600}
#explorer-switcher a.active{background:#0b2619!important;color:#00e783!important;box-shadow:inset 0 0 0 1px #00e783}
#explorer-switcher a:hover{color:#dfffee!important;background:#0b1912!important}
#explorer-switcher a.active:hover{color:#00e783!important;background:#0b2619!important}
@media(max-width:760px){#explorer-switcher{padding:0 12px;margin-top:7px;justify-content:stretch}#explorer-switcher .explorer-switch-inner{display:grid;grid-template-columns:1fr 1fr;width:100%}#explorer-switcher a{justify-content:center;padding:7px 8px}}
</style>'''


def rel_href(page: Path, target: Path) -> str:
    return os.path.relpath(target, page.parent).replace(os.sep, "/")


def switch_html(page: Path) -> str:
    ojutam_root = OUT / "ojutam" / "index.html"
    okotam_root = OUT / "index.html"
    in_ojutam = OUT / "ojutam" in page.parents
    oko = rel_href(page, okotam_root)
    oju = rel_href(page, ojutam_root)
    return (
        '<div id="explorer-switcher" aria-label="탐험대 전환">'
        '<div class="explorer-switch-inner">'
        f'<a class="{"" if in_ojutam else "active"}" href="{oko}">COIN 오코탐 <span>UPBIT</span></a>'
        f'<a class="{"active" if in_ojutam else ""}" href="{oju}">KRX 오주탐 <span>STOCK</span></a>'
        '</div></div>'
    )


def patch(page: Path) -> bool:
    try:
        text = page.read_text(encoding="utf-8")
    except Exception:
        return False
    if "<body" not in text.lower():
        return False

    # Idempotent: remove an older injected switch/style first.
    text = re.sub(r'<style id="explorer-switcher-style">.*?</style>', '', text, flags=re.S)
    text = re.sub(r'<div id="explorer-switcher".*?</div></div>', '', text, count=1, flags=re.S)

    # Put styling in head and switch immediately after the body tag.
    if "</head>" in text:
        text = text.replace("</head>", STYLE + "</head>", 1)
    else:
        text = STYLE + text
    text = re.sub(r'(<body[^>]*>)', r'\1' + switch_html(page), text, count=1, flags=re.I)
    page.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    count = 0
    for page in OUT.rglob("*.html"):
        if patch(page):
            count += 1
    print(f"explorer switch patched: {count} html files")


if __name__ == "__main__":
    main()
