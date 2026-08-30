#!/usr/bin/env python3
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scanner"
OUT = ROOT / "outputs"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text((SCANNER / "dashboard_v5.html").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "dashboard_v5.css").write_text((SCANNER / "dashboard_v5.css").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "dashboard_v5.js").write_text((SCANNER / "dashboard_v5.js").read_text(encoding="utf-8"), encoding="utf-8")
    assets_out = OUT / "assets"
    assets_out.mkdir(parents=True, exist_ok=True)
    for asset in (SCANNER / "assets").glob("sukdol-*"):
        shutil.copy2(asset, assets_out / asset.name)
    # header_astronaut.b64 is a reviewed UI asset committed in outputs.
    # Do not regenerate or overwrite it during scans.
    print(OUT / "index.html")


if __name__ == "__main__":
    main()
