"""Exercise the shared exchange type search, including collapsed P lists."""
import re
import shutil
import subprocess

import pytest

from scanner import unified_dashboard as dashboard
from scanner_binance.render_dashboard import binanceize


@pytest.mark.parametrize("key", list("ABCDEFGH") + ["P1", "P2", "P3", "P4"])
@pytest.mark.parametrize("exchange", ["upbit", "binance"])
def test_every_type_has_search_even_when_empty(key, exchange):
    page = dashboard.type_page(key, {"candidates": []})
    if exchange == "binance":
        page = binanceize(page)
    assert 'id="typeCoinSearch"' in page
    assert 'id="typeSearchCount" aria-live="polite"' in page
    assert 'id="typeSearchEmpty"' in page
    assert 'id="typeTable"' in page
    assert 'addEventListener("input",applyTypeFilters)' in page
    assert "이번 기준봉 후보 없음" in page


def test_type_search_indexes_names_and_escapes_attributes():
    page = dashboard.type_page("A", {"candidates": [{
        "market": "KRW-XRP", "type": "A", "name": '리플 "Ripple"',
        "english_name": "XRP", "action": "확인 대기", "entry": [],
    }]})
    assert 'data-search="KRW-XRP 리플 &quot;Ripple&quot; XRP  "' in page
    assert 'data-action="확인 대기"' in page


def test_search_filter_composition_and_hidden_details_in_javascript():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for generated JavaScript behavior")
    page = dashboard.type_page("P1", {"candidates": []})
    script = re.search(r'<script id="typeSearchScript">(.*?)</script>', page, re.S).group(1)
    harness = r'''
const assert=require('assert');
const makeClass=()=>({values:new Set(),toggle(k,v){if(v)this.values.add(k);else this.values.delete(k)},remove(k){this.values.delete(k)},add(k){this.values.add(k)}});
const rows=Array.from({length:8},(_,i)=>({dataset:{stage:'D1',action:i===7?'진입 검토':'확인 대기',search:i===7?'KRW-XRP 리플 XRP':'KRW-COIN'+i},style:{},classList:makeClass(),nextElementSibling:{style:{},classList:makeClass()}}));
const input={value:'',addEventListener(){}};
const count={textContent:''},empty={hidden:true};
const document={querySelectorAll(q){return q==='#typeTable tr.row-click'?rows:[]},getElementById(id){return {typeCoinSearch:input,typeSearchCount:count,typeSearchEmpty:empty}[id]},addEventListener(e,f){f()}};
'''
    checks = r'''
assert.equal(rows.filter(r=>r.style.display!=='none').length,6);
input.value='  xRp  ';applyTypeFilters();
assert.equal(rows[7].style.display,'');assert.equal(count.textContent,'1개 표시 / 8개 전체');
expandAll(true);assert(rows[7].nextElementSibling.classList.values.has('open'));
assert(!rows[0].nextElementSibling.classList.values.has('open'));
filterAction('확인 대기',{classList:makeClass()});
assert.equal(count.textContent,'0개 표시 / 8개 전체');assert.equal(empty.hidden,false);
assert(!rows[7].nextElementSibling.classList.values.has('open'));
input.value='리플';filterAction('전체',{classList:makeClass()});
assert.equal(count.textContent,'1개 표시 / 8개 전체');
input.value='';applyTypeFilters();showAllTypeRows({classList:makeClass()});
assert.equal(count.textContent,'8개 표시 / 8개 전체');
filterAction('진입 검토',{classList:makeClass()});
assert.equal(count.textContent,'1개 표시 / 8개 전체');
'''
    subprocess.run([node, "-e", harness + script + checks], check=True, capture_output=True, text=True)
