from pathlib import Path
import re
import ojutam_krx_daily as app
import ojutam_krx_daily_v6 as v6


def patch_scan_inline():
    p=Path('outputs/ojutam/scan.html')
    text=p.read_text(encoding='utf-8')
    text=re.sub(r'<div id="detailModal" class="modal">.*?</div></div><script src="https://unpkg.com/lightweight-charts@4\.2\.3/dist/lightweight-charts\.standalone\.production\.js"></script>', '<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>', text, count=1, flags=re.S)
    css='''<style>
.modal,.modal-card,.modal-chart,.close{display:none!important}
.expand{display:none}.expand.open{display:table-row}.expand td{padding:16px!important;background:#07100c}
.expand-inner{display:block}.inline-detail-chart{width:100%;height:470px;border:1px solid #17392a;border-radius:12px;overflow:hidden;background:#020609}
.chart-title{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}.chart-title>div{display:flex;justify-content:space-between;align-items:center;width:100%}.chart-title b{font-size:15px}.chart-title small{color:#58d6b4}
.target-strip{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.target-chip{padding:9px 12px;border:1px solid #58bfff;border-radius:10px;background:#08150f}
.help-note{margin-top:14px;padding:14px 16px;border-left:2px solid var(--green);background:#0a1510}.help-note b,.help-note p{margin:3px 0}.help-note strong{color:#f5fff8}
.detail-foot{margin-top:12px;padding:11px 13px;border-left:2px solid #58bfff;background:#0a1510;color:#b8cbc1}
.row-click{cursor:pointer}.row-click:hover{background:#0d1b14}
.judge-guide{margin:0 0 20px;padding:14px;border:1px solid #28513d;border-radius:15px;background:#06100b}.judge-guide summary{cursor:pointer;font-weight:900;color:#f2fff7}.judge-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:12px}.judge-card{padding:13px;border:1px solid #244638;border-radius:12px;background:#08130e}.judge-card b{display:inline-block;padding:5px 9px;border-radius:999px;margin-bottom:8px}.judge-card p{margin:0;color:#c3d2ca;font-size:12px}.j1 b{color:#56e6a7;border:1px solid #1fa563;background:#0b2b1d}.j2 b{color:#ffd45f;border:1px solid #8b6c12;background:#302809}.j3 b{color:#7fb4ff;border:1px solid #3c65a0;background:#0d2341}.j4 b{color:#ff8c98;border:1px solid #9a3b48;background:#3b1118}.judge-foot{margin-top:10px;color:#91a79b;font-size:12px}
@media(max-width:900px){.inline-detail-chart{height:390px}.judge-grid{grid-template-columns:1fr 1fr}.chart-title>div{align-items:flex-start;flex-direction:column}}
@media(max-width:600px){.judge-grid{grid-template-columns:1fr}.inline-detail-chart{height:340px}}
</style>'''
    text=text.replace('</head>',css+'</head>',1)
    guide='''<details class="judge-guide" open><summary>▼ 🐱 차트 현재판단 보는 법</summary><div class="judge-grid"><div class="judge-card j1"><b>유형 적합</b><p>해당 A~F 차트 모양이 일봉 기준으로 선명하게 잡힌 후보야.</p></div><div class="judge-card j2"><b>확인 필요</b><p>모양은 맞지만 지지·재테스트·거래량 같은 구조 확인이 더 필요한 후보야.</p></div><div class="judge-card j3"><b>관찰 후보</b><p>계획한 핵심 가격구간에 올 때까지 일봉 흐름을 관찰하는 후보야.</p></div><div class="judge-card j4"><b>추격 금지</b><p>이미 핵심 구간을 크게 지나왔거나 지금 따라붙기보다 다음 구조를 기다리는 편이 나은 상태야.</p></div></div><div class="judge-foot">이 페이지는 같은 차트 모양을 빠르게 모아 비교하는 곳이야.</div></details>'''
    marker='<section class="panel intro"><h2>전체 스캔 결과</h2>'
    text=text.replace(marker,guide+marker,1)
    text=text.replace('KRX 일봉 스캐너 정상 · 분봉 미사용 · <b>종목을 누르면 차트 상세</b>','KRX 일봉 스캐너 정상 · 분봉 미사용 · <b>종목을 누르면 아래에서 일봉 차트 펼침</b>')
    text=text.replace('A~F 유형 필터 → 종목 클릭 → 일봉 차트와 핵심구간 확인','A~F 유형 필터 → 종목 클릭 → 같은 자리에서 일봉 차트와 핵심구간 확인')
    p.write_text(text,encoding='utf-8')


def patch_index_labels():
    p=Path('outputs/ojutam/index.html')
    text=p.read_text(encoding='utf-8')
    replacements={'data-i="15">15m':'data-i="15">15분','data-i="60">1h':'data-i="60">1시간','data-i="240">4h':'data-i="240">4시간','data-i="D">1D':'data-i="D">일봉','data-i="W">1W':'data-i="W">주봉'}
    for a,b in replacements.items():text=text.replace(a,b)
    p.write_text(text,encoding='utf-8')


def generate(universe,buckets,date):
    v6.generate(universe,buckets,date)
    patch_scan_inline()
    patch_index_labels()

app.generate=generate
if __name__=='__main__':app.main()
