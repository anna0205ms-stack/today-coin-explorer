#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
ASSETS = OUT / "assets"
INDEX = OUT / "index.html"
EXPECTED = {"up": 3, "caution": 2}


def encoded(name: str) -> str | None:
    full = ASSETS / f"sukdol_{name}.webp.base64"
    if full.exists() and full.read_text(encoding="utf-8").strip():
        return full.read_text(encoding="utf-8").strip()
    count = EXPECTED.get(name)
    if count:
        parts = [ASSETS / f"sukdol_{name}_{i}.txt" for i in range(1, count + 1)]
        if all(p.exists() for p in parts):
            return "".join(p.read_text(encoding="utf-8").strip() for p in parts)
    return None


def main() -> None:
    if not INDEX.exists():
        return
    fallback = encoded("stop")
    html = INDEX.read_text(encoding="utf-8")
    for state in ("stop", "up", "caution"):
        data = encoded(state) or fallback
        if data:
            html = html.replace(f"assets/sukdol_{state}.webp", f"data:image/webp;base64,{data}")
    INDEX.write_text(html, encoding="utf-8")
    print(INDEX)


if __name__ == "__main__":
    main()
