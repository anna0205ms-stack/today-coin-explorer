from pathlib import Path
import re
import ojutam_krx_daily as app
import ojutam_krx_daily_v6 as v6


def patch_scan_inline():
    p=Path('outputs/ojutam/scan.html')
    text=p.read_text(encoding='utf-8')
    text=re.sub(r'<div id="detailModal" class="modal">.*?</div></div><script src="https://unpkg.com/lightweight-charts@4\.2\.3/dist/lightweight-charts\.standalone\.production\.js"></script>', '<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>', text, count=1, flags=re.S)
    css='''<style>
.modal,.modal-card,.modal-chart,.close{display:none!important}.expand{display:none}.expand.open{display:table-row}.expand td{padding:16px!important;background:#07100c}.expand-inner{display:block;width:100%;min-width:0}.inline-detail-chart{display:block;width:100%;height:470px;border:1px solid #17392a;border-radius:12px;overflow:hidden;background:#020609}.chart-title{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}.chart-title>div{display:flex;justify-content:space-between;align-items:center;width:100%}.chart-title b{font-size:15px}.chart-title small{color:#58d6b4}.target-strip{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.target-chip{padding:9px 12px;border:1px solid #58bfff;border-radius:10px;background:#08150f}.help-note{margin-top:14px;padding:14px 16px;border-left:2px solid var(--green);background:#0a1510}.help-note b,.help-note p{margin:3px 0}.help-note strong{color:#f5fff8}.row-click{cursor:pointer}.row-click:hover{background:#0d1b14}.judge-guide{margin:0 0 14px;padding:12px;border:1px solid #28513d;border-radius:15px;background:#06100b}.judge-guide summary{cursor:pointer;font-weight:900}.judge-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}.judge-card{padding:10px;border:1px solid #244638;border-radius:10px;background:#08130e}.judge-card b{display:inline-block;padding:4px 8px;border-radius:999px;margin-bottom:5px}.judge-card p{margin:0;color:#c3d2ca;font-size:11px}.j1 b{color:#56e6a7;border:1px solid #1fa563}.j2 b{color:#ffd45f;border:1px solid #8b6c12}.j3 b{color:#7fb4ff;border:1px solid #3c65a0}.j4 b{color:#ff8c98;border:1px solid #9a3b48}.search-bar{display:flex;align-items:center;gap:10px;margin:12px 0}.search-bar input{flex:1;min-width:0;padding:11px 13px;border:1px solid #315543;border-radius:11px;background:#06100b;color:#f5fff8;font-size:14px}.search-bar span{color:#91a79b;font-size:12px}.scan-table{min-width:1180px;width:100%;table-layout:fixed}.scan-table th:nth-child(1){width:62px}.scan-table th:nth-child(2){width:34%}.scan-table th:nth-child(3){width:21%}.scan-table th:nth-child(4){width:62px}.scan-table th:nth-child(5){width:105px}.scan-table th:nth-child(6){width:135px}.scan-table th:nth-child(7){width:76px}.scan-table th:nth-child(8){width:90px}.scan-table th:nth-child(9){width:78px}.scan-table th,.scan-table td{font-size:12px;line-height:1.35;padding:10px 8px}.scan-table th{font-size:11px}.judge{display:inline-block;padding:5px 8px;border-radius:999px;font-size:11px;font-weight:800}.j-entry{color:#62efa8;border:1px solid #1fa563;background:#0b2b1d}.j-wait{color:#ffd45f;border:1px solid #8b6c12;background:#302809}.j-zone{color:#7fb4ff;border:1px solid #3c65a0;background:#0d2341}.j-stop{color:#ff8c98;border:1px solid #9a3b48;background:#3b1118}.mini-condition,.mini-distance{margin-top:4px;color:#91a79b;font-size:10px}.empty-row{padding:30px!important;text-align:center;color:#91a79b}
@media(max-width:760px){.judge-guide{padding:10px}.judge-grid{grid-template-columns:1fr 1fr}.judge-card{padding:8px}.judge-card p{font-size:10px}.scan-summary{grid-template-columns:repeat(3,1fr)!important;gap:6px!important}.sum{padding:8px!important;border-radius:10px!important;font-size:10px!important;line-height:1.2!important}.sum strong{font-size:16px!important}.tabs{gap:5px!important}.tab{padding:6px 9px!important;font-size:11px!important}.search-bar{margin:8px 0}.search-bar input{padding:9px 10px;font-size:13px}.table-wrap{overflow:visible!important;border:0!important}.scan-table{min-width:0!important;width:100%!important}.scan-table thead{display:none}.scan-table,.scan-table tbody{display:block;width:100%}.scan-table tr.row-click{display:grid;grid-template-columns:28px minmax(110px,1.25fr) 88px 54px;gap:5px 8px;padding:10px 6px;border-bottom:1px solid #173226;align-items:center}.scan-table tr.row-click td{display:block!important;padding:0!important;border:0!important;white-space:normal!important;font-size:11px!important}.c-star{grid-column:1;grid-row:1/3}.c-stock{grid-column:2;grid-row:1/3}.c-judge{grid-column:3;grid-row:1/3}.c-score{grid-column:4;grid-row:1}.c-price{grid-column:4;grid-row:2}.c-entry,.c-stop,.c-target,.c-rr{display:none!important}.c-stock b{font-size:12px}.c-stock .sub,.mini-condition,.mini-distance{font-size:9px!important}.judge{font-size:9px!important;padding:4px 6px}.expand.open{display:block!important;width:100%!important}.expand.open td{display:block!important;width:100%!important;padding:10px 0!important;border:0!important}.expand-inner{width:100%!important;min-width:0!important}.inline-detail-chart{height:320px;width:100%!important;max-width:none!important;min-width:0!important}.inline-detail-chart>div,.inline-detail-chart table,.inline-detail-chart canvas{max-width:100%!important}.help-note{padding:10px 11px;font-size:11px}.target-chip{padding:7px 8px;font-size:10px}.chart-title b{font-size:13px}}
@media(max-width:430px){.judge-grid{grid-template-columns:1fr 1fr}.scan-summary{grid-template-columns:1fr 1fr!important}.scan-table tr.row-click{grid-template-columns:24px minmax(100px,1fr) 78px 48px;gap:4px 6px;padding:9px 2px}.inline-detail-chart{height:285px}}
</style>'''
    text=text.replace('</head>',css+'</head>',1)
    guide='''<details class="judge-guide" open><summary>▼ 🐱 차트 현재판단 보는 법</summary><div class="judge-grid"><div class="judge-card j1"><b>진입 검토</b><p>일봉 구조가 진입 조건에 가까운 후보.</p></div><div class="judge-card j2"><b>확인 대기</b><p>마지막 지지·안착 확인이 남은 후보.</p></div><div class="judge-card j3"><b>진입가 대기</b><p>계획한 가격구간까지 기다리는 후보.</p></div><div class="judge-card j4"><b>추격 금지</b><p>핵심 구간을 지나 새 구조를 기다리는 후보.</p></div></div></details>'''
    marker='<section class="panel intro"><h2>전체 스캔 결과</h2>'
    text=text.replace(marker,guide+marker,1)
    text=text.replace('</section><section id="scanSummary" class="scan-summary">','</section><div class="search-bar"><input id="stockSearch" type="search" inputmode="search" placeholder="종목명 또는 종목코드 검색"><span id="searchCount"></span></div><section id="scanSummary" class="scan-summary">',1)
    text=text.replace('<thead><tr><th>종목</th><th>유형</th><th>점수</th><th>흐름</th><th>한줄정리</th><th>관심</th></tr></thead>','<thead><tr><th>관심</th><th>종목</th><th>현재판단·남은 조건</th><th>점수</th><th>현재가·진입거리</th><th>진입</th><th>손절</th><th>1차 목표</th><th>손익비</th></tr></thead>',1)
    text=text.replace('KRX 일봉 스캐너 정상 · 분봉 미사용 · <b>종목을 누르면 차트 상세</b>','KRX 일봉 스캐너 정상 · 분봉 미사용 · <b>종목을 누르면 아래에서 상세 펼침</b>')
    # Always force the latest chart script after deploy; prevents iOS/Safari from reusing the previous JS.
    text=re.sub(r'scan_v6\.js(?:\?[^"\']*)?', 'scan_v6.js?v=20260902-chart-visible-1', text)
    p.write_text(text,encoding='utf-8')


def patch_mobile_chart_script():
    p=Path('outputs/ojutam/scan_v6.js')
    text=p.read_text(encoding='utf-8')
    mobile_decl="const mobile=window.matchMedia('(max-width:760px)').matches;"
    while mobile_decl+mobile_decl in text:
        text=text.replace(mobile_decl+mobile_decl,mobile_decl)
    if "function drawInline(code,type){const mobile=" not in text:
        text=text.replace("function drawInline(code,type){", "function drawInline(code,type){const mobile=window.matchMedia('(max-width:760px)').matches;")
    text=text.replace("rightPriceScale:{borderColor:'#29404d',autoScale:true}", "rightPriceScale:{borderColor:'#29404d',autoScale:true,visible:!mobile,borderVisible:!mobile}")
    text=text.replace("timeScale:{borderColor:'#29404d',rightOffset:8,barSpacing:7,minBarSpacing:2}", "timeScale:{borderColor:'#29404d',rightOffset:mobile?0:8,barSpacing:mobile?4.5:7,minBarSpacing:2}")
    text=text.replace("priceLineVisible:true,lastValueVisible:true", "priceLineVisible:!mobile,lastValueVisible:!mobile,priceScaleId:mobile?'':'right'")
    text=text.replace("axisLabelVisible:true,title:k.replaceAll('_',' ')", "axisLabelVisible:!mobile,title:mobile?'':k.replaceAll('_',' ')")
    text=text.replace("axisLabelVisible:true,title})", "axisLabelVisible:!mobile,title:mobile?'':title})")
    text=text.replace("chart.timeScale().fitContent();ro=new ResizeObserver(()=>chart?.resize(el.clientWidth,el.clientHeight));", "if(mobile){try{chart.priceScale('right').applyOptions({visible:false,borderVisible:false})}catch(e){}}chart.timeScale().fitContent();const fit=()=>{const w=Math.max(1,Math.floor(el.getBoundingClientRect().width));chart?.resize(w,el.clientHeight);chart?.timeScale().fitContent()};requestAnimationFrame(()=>requestAnimationFrame(fit));ro=new ResizeObserver(fit);")
    p.write_text(text,encoding='utf-8')


def make_type_list_pages():
    src=Path('outputs/ojutam/scan.html').read_text(encoding='utf-8')
    names={'A':'급등 후 첫 눌림','B':'바닥·박스 하단 반등','C':'박스 상단 돌파','D':'재탈환·압축','E':'급락 후 기술적 반등','F':'고점권·과거 매물대'}
    for k,name in names.items():
        text=src.replace('<body>','<body data-ojutam-filter="'+k+'">',1)
        text=text.replace('<title>전체 스캔 결과','<title>'+k+'형 · '+name,1)
        text=text.replace('<h2>전체 스캔 결과</h2>','<h2>'+k+'형 · '+name+'</h2>',1)
        text=text.replace('A~F 유형 필터 → 종목 클릭 → 일봉 차트와 핵심구간 확인',k+'형 후보를 리스트로 먼저 보고, 종목을 누르면 일봉 차트와 진입·손절·목표를 확인',1)
        Path(f'outputs/ojutam/type_{k.lower()}.html').write_text(text,encoding='utf-8')


def patch_index_labels():
    p=Path('outputs/ojutam/index.html');text=p.read_text(encoding='utf-8')
    replacements={'data-i="15">15m':'data-i="15">15분','data-i="60">1h':'data-i="60">1시간','data-i="240">4h':'data-i="240">4시간','data-i="D">1D':'data-i="D">일봉','data-i="W">1W':'data-i="W">주봉'}
    for a,b in replacements.items():text=text.replace(a,b)
    p.write_text(text,encoding='utf-8')


def generate(universe,buckets,date):
    v6.generate(universe,buckets,date)
    patch_scan_inline()
    patch_mobile_chart_script()
    make_type_list_pages()
    patch_index_labels()

app.generate=generate
if __name__=='__main__':app.main()
