#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scanner"
OUT = ROOT / "outputs"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text((SCANNER / "dashboard_v5.html").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "dashboard_v5.css").write_text((SCANNER / "dashboard_v5.css").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "dashboard_v5_overrides.css").write_text((SCANNER / "dashboard_v5_overrides.css").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "dashboard_v5.js").write_text((SCANNER / "dashboard_v5.js").read_text(encoding="utf-8"), encoding="utf-8")
    # header_astronaut.b64 is a reviewed UI asset committed in outputs.
    # Do not regenerate or overwrite it during scans.
    print(OUT / "index.html")


if __name__ == "__main__":
    main()
