#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

STYLE = r'''<style id="oktam-space-header-style">
.topbar,.oko-global-bar{display:none!important}
.oktam-space-header{position:sticky;top:0;z-index:100000;background:linear-gradient(90deg,rgba(3,8,18,.99),rgba(4,8,15,.985) 52%,rgba(3,6,11,.99));border-bottom:1px solid #202b38;box-shadow:0 8px 28px rgba(0,0,0,.28);font-family:Inter,Pretendard,"Noto Sans KR",Arial,sans-serif}
.oktam-space-inner{max-width:1540px;height:112px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:20px;padding:0 22px;position:relative;overflow:hidden}
.oktam-space-inner:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 31% 18%,rgba(73,133,255,.15),transparent 17%),radial-gradient(circle at 62% 28%,rgba(255,255,255,.12) 0 1px,transparent 2px),radial-gradient(circle at 73% 61%,rgba(255,255,255,.12) 0 1px,transparent 2px),radial-gradient(circle at 48% 72%,rgba(74,122,255,.09),transparent 24%);pointer-events:none}
.oktam-brand{height:100%;min-width:0;display:flex;align-items:center;text-decoration:none;color:#fff;position:relative;z-index:2}
.oktam-astro-wrap{width:210px;height:100%;position:relative;flex:none;overflow:hidden}
.oktam-astro{position:absolute;left:50%;bottom:0;width:auto;height:108px;max-width:100%;object-fit:contain;object-position:center bottom;display:block;transform:translateX(-50%)}
.oktam-title-wrap{margin-left:10px;min-width:0}
.oktam-title{font-size:34px;line-height:1.05;font-weight:900;letter-spacing:-1.7px;white-space:nowrap;color:#f5f7fa;text-shadow:0 3px 18px rgba(0,0,0,.55)}
.oktam-title .accent{color:#24a8ff}
.oktam-subtitle{margin-top:8px;font-size:13px;color:#aab6c3;white-space:nowrap}
.oktam-market-switch{display:flex;gap:12px;position:relative;z-index:3;flex:none}
.oktam-market-switch a{width:156px;height:58px;border-radius:11px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-decoration:none;background:rgba(6,11,18,.88);transition:.15s ease;box-shadow:inset 0 0 20px rgba(0,0,0,.12)}
.oktam-market-switch b{font-size:17px;letter-spacing:.2px}.oktam-market-switch small{font-size:9px;font-weight:800;margin-top:2px;letter-spacing:.5px}
.oktam-market-switch .upbit{border:1px solid #2469ba;color:#66b5ff}.oktam-market-switch .upbit.active{background:linear-gradient(180deg,#102f69,#081c40);border-color:#3e8dff;color:#e9f5ff;box-shadow:0 0 20px rgba(46,131,255,.16)}
.oktam-market-switch .binance{border:1px solid #6a5206;color:#f4c52f}.oktam-market-switch .binance.active{background:linear-gradient(180deg,#332604,#1d1603);border-color:#d9a909;color:#ffe27a;box-shadow:0 0 20px rgba(245,197,51,.14)}
.oktam-market-switch a:hover{transform:translateY(-1px);filter:brightness(1.08)}
@media(max-width:900px){.oktam-space-inner{height:92px;padding:0 12px}.oktam-astro-wrap{width:130px}.oktam-astro{height:88px}.oktam-title-wrap{margin-left:0}.oktam-title{font-size:25px}.oktam-subtitle{font-size:11px}.oktam-market-switch a{width:112px;height:50px}}
@media(max-width:640px){.oktam-space-inner{height:72px;padding:0 8px;gap:7px}.oktam-astro-wrap{width:54px}.oktam-astro{height:68px;left:50%;bottom:0}.oktam-title{font-size:17px;letter-spacing:-.8px}.oktam-subtitle{display:none}.oktam-market-switch{gap:5px}.oktam-market-switch a{width:76px;height:43px;border-radius:9px}.oktam-market-switch b{font-size:12px}.oktam-market-switch small{font-size:7px}}
</style>'''


def header(home: str, upbit: str, binance: str, image_src: str, active: str = "") -> str:
    up = " active" if active == "upbit" else ""
    bn = " active" if active == "binance" else ""
    return f'''<header class="oktam-space-header" id="oktam-space-header"><div class="oktam-space-inner"><a class="oktam-brand" href="{home}"><span class="oktam-astro-wrap"><img class="oktam-astro" src="{image_src}" alt="우주복 숙돌이"></span><span class="oktam-title-wrap"><span class="oktam-title">오늘의 코인 <span class="accent">탐험대</span></span><span class="oktam-subtitle">시장을 탐험하고, 기회를 발견하세요.</span></span></a><div class="oktam-market-switch"><a class="upbit{up}" href="{upbit}"><b>UPBIT</b><small>KRW</small></a><a class="binance{bn}" href="{binance}"><b>BINANCE</b><small>SPOT USDT</small></a></div></div></header>'''


def patch(path: Path, is_binance: bool = False, is_main: bool = False):
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    image_src = "../assets/sukdol-stage.webp" if is_binance else "assets/sukdol-stage.webp"
    # repeated runs are idempotent
    if 'id="oktam-space-header"' in text:
        text = re.sub(
            r'(<img class="oktam-astro" src=")[^"]*(" alt="우주복 숙돌이">)',
            rf'\1{image_src}\2',
            text,
            count=1,
        )
        path.write_text(text, encoding="utf-8")
        return
    if is_binance:
        bar = header("../index.html", "../scan.html", "scan.html", image_src, "binance")
    elif is_main:
        bar = header("index.html", "scan.html", "binance/scan.html", image_src, "")
    else:
        bar = header("index.html", "scan.html", "binance/scan.html", image_src, "upbit")
    text = text.replace("</head>", STYLE + "</head>", 1)
    body_pos = text.find(">", text.find("<body"))
    if body_pos >= 0:
        text = text[:body_pos+1] + bar + text[body_pos+1:]
    path.write_text(text, encoding="utf-8")


def run():
    patch(OUT / "index.html", is_main=True)
    upbit_pages = [OUT / "scan.html", OUT / "watchlist.html", OUT / "history.html"]
    upbit_pages += [OUT / f"type_{k}.html" for k in "abcde"]
    upbit_pages += [OUT / f"training_{k}.html" for k in "abcde"]
    for p in upbit_pages:
        patch(p)
    bindir = OUT / "binance"
    if bindir.exists():
        for p in bindir.glob("*.html"):
            patch(p, is_binance=True)
    print("space header applied")


if __name__ == "__main__":
    run()
