#!/usr/bin/env python3
from pathlib import Path
from header_art import HEADER_CAT_DATA

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scanner"
OUT = ROOT / "outputs"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text((SCANNER / "dashboard_v5.html").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "dashboard_v5.css").write_text((SCANNER / "dashboard_v5.css").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "dashboard_v5.js").write_text((SCANNER / "dashboard_v5.js").read_text(encoding="utf-8"), encoding="utf-8")
    prefix = "data:image/webp;base64,"
    data = HEADER_CAT_DATA[len(prefix):] if HEADER_CAT_DATA.startswith(prefix) else HEADER_CAT_DATA
    (OUT / "header_astronaut.b64").write_text(data, encoding="utf-8")
    print(OUT / "index.html")


if __name__ == "__main__":
    main()
