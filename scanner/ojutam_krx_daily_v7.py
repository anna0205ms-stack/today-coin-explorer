from pathlib import Path
import re
import ojutam_krx_daily as app
import ojutam_krx_daily_v6 as v6


def patch_scan_inline():
    p=Path('outputs/ojutam/scan.html')
    text=p.read_text(encoding='utf-8')
    text=re.sub(r'<div id="detailModal" class="modal">.*?</div></div><script src="https://unpkg.com/lightweight-charts@4\.2\.3/dist/lightweight-charts\.standalone\.production\.js"></script>', '<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>', text, count=1, flags=re.S)
    css='''<style>.modal,.modal-card,.modal-chart,.close{display:none!important}.expand{display:none}.expand.open{display:table-row}.expand td{padding:16px!important;background:#07100c}.expand-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(280px,.65fr);gap:14px;align-items:start}.inline-detail-chart{height:430px;border:1px solid #17392a;border-radius:12px;overflow:hidden;background:#020609}.chart-title{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}.chart-title small{color:var(--sub)}.target-strip{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.target-chip{padding:8px 10px;border:1px solid #315543;border-radius:10px;background:#08150f}.help-note{padding:12px 14px;border-left:2px solid var(--green);background:#0a1510}.help-note p{margin:5px 0 0;color:var(--sub)}.row-click{cursor:pointer}.row-click:hover{background:#0d1b14}@media(max-width:900px){.expand-grid{grid-template-columns:1fr}.inline-detail-chart{height:360px}.chart-title{align-items:flex-start;flex-direction:column}}</style>'''
    text=text.replace('</head>',css+'</head>',1)
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
