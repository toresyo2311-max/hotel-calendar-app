#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑦ 마일리지(부산) 탭의 골격(CSS·마크업·JS)과 연결 고리를 index.html 에 넣는다.

자료는 `data/app/tab8_mileage.json`(tools/collect_mileage.py 가 만든다)이고,
탭을 처음 열 때 지연 로딩한다. ⑦ 은 🌲 휴양림(tab7_forest.json) 다음 자리에 놓는다.

    python3 tools/build_mileage_tab.py          # 넣기(이미 있으면 마커 사이만 교체)
    python3 tools/build_mileage_tab.py --check  # 넣지 않고 상태만 확인

넣는 자리(마커로 감싸 두어 다시 돌려도 중복되지 않는다):
    CSS      : '/* ── 반응형' 앞
    NAV      : 휴양림 버튼 블록 뒤
    SECTION  : 발렛 패널 앞
    TABS     : const tabs={...} 의 valet 항목 앞
    JS       : function activate(tab){ 앞
연결 고리도 함께 손본다 — 이미 되어 있으면 건드리지 않는다.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
ASSETS = os.path.join(ROOT, 'tools', 'mileage_tab')

NAV_START, NAV_END = '<!-- MILEAGE:NAV -->', '<!-- /MILEAGE:NAV -->'
SEC_START, SEC_END = '<!-- MILEAGE:SECTION -->', '<!-- /MILEAGE:SECTION -->'
CSS_START, CSS_END = '/* MILEAGE:CSS */', '/* /MILEAGE:CSS */'
JS_START, JS_END = '// MILEAGE:JS', '// /MILEAGE:JS'

TABS_ENTRY = ("mileage:{title:'⑦ 마일리지(부산) — 부산 출발 보너스 좌석과 필요 마일',"
              "sub:'대한항공이 공개하는 보너스 좌석 현황(하루 1회 갱신 · 앞으로 360일)을 매일 옮긴 스냅샷으로 "
              "부산/김해(PUS) 출발 노선의 날짜별 일반석·프레스티지 보너스와 프레스티지 승급 좌석을 12개월 달력으로 봅니다. "
              "원천에 좌석 수량·수수료·기재가 없어 표시하지 않고, 필요 마일은 항공사 공제표로 계산합니다. / "
              "좌석 수량은 항공사 화면에서 확인',"
              "checked:'수집 기준: 2026-11-22 KST · 대한항공 공개 보너스 좌석 현황',start:'2026-12',end:'2027-11'}")

NAV_HTML = ('    <button class="tab" data-tab="mileage" type="button" aria-label="마일리지 부산 — 부산 출발 보너스 좌석">'
            '⑦ 마일리지(부산) <b hidden>—</b></button>')

HOOKS = [
    ('setDealPanels',
     "const fp=document.getElementById('frPanel');if(fp)fp.hidden=which!=='forest';",
     "const fp=document.getElementById('frPanel');if(fp)fp.hidden=which!=='forest';"
     "const mp=document.getElementById('mgPanel');if(mp)mp.hidden=which!=='mileage';"),
    ('render() 디스패치',
     "if(st.tab==='forest'){renderForest();hashSync();return}",
     "if(st.tab==='forest'){renderForest();hashSync();return}\n"
     "  if(st.tab==='mileage'){renderMileage();hashSync();return}"),
    ('DATA_READY',
     "forest:false};",
     "forest:false,mileage:false};"),
    ('DATA_BUST',
     "forest:'2026-11-22a'};",
     "forest:'2026-11-22a',mileage:'2026-11-22a'};"),
    ('PART_FILE',
     "forest:'tab7_forest.json'};",
     "forest:'tab7_forest.json',mileage:'tab8_mileage.json'};"),
    ('loadPart',
     "    }else if(tab==='forest'){\n      Object.assign(FRD,data);frPrep();\n    }",
     "    }else if(tab==='forest'){\n      Object.assign(FRD,data);frPrep();\n"
     "    }else if(tab==='mileage'){\n      Object.assign(MGD,data);mgPrep();\n"
     "      if(st.tab==='mileage')renderMileage();\n    }"),
    ('HOTEL_TABS 제외 확인', None, None),
]


def asset(name):
    with open(os.path.join(ASSETS, name), encoding='utf-8') as fp:
        return fp.read().rstrip('\n')


def wrap(start, end, body, pad=''):
    return start + '\n' + body + '\n' + pad + end


def put(src, start, end, body, anchor, before=True, pad=''):
    if start in src and end in src:
        a = src.index(start)
        b = src.index(end, a) + len(end)
        return src[:a] + wrap(start, end, body, pad) + src[b:], 'replaced'
    if anchor not in src:
        raise SystemExit('앵커를 찾지 못했습니다: %r' % anchor[:60])
    i = src.index(anchor)
    block = wrap(start, end, body, pad)
    if before:
        return src[:i] + block + '\n' + src[i:], 'inserted'
    j = i + len(anchor)
    return src[:j] + block + '\n' + src[j:], 'inserted'


def add_tab_entry(src):
    if "mileage:{title:'⑦ 마일리지(부산)" in src:
        return src, 'already'
    anchor = 'valet:{title:'
    if anchor not in src:
        raise SystemExit('const tabs 의 valet 항목을 찾지 못했습니다')
    i = src.index(anchor)
    return src[:i] + TABS_ENTRY + ',' + src[i:], 'inserted'


def js_syntax_problem(src):
    try:
        import esprima
    except ImportError:
        return None
    anchor = src.index('function render(')
    a = src.rindex('<script>', 0, anchor) + len('<script>')
    b = src.index('</script>', anchor)
    js = src[a:b]
    js = js.replace('?.[', '[')
    js = re.sub(r'\?\.', '.', js)
    js = js.replace('??', '||')
    try:
        esprima.parseScript(js)
    except Exception as exc:                      # noqa: BLE001
        line = getattr(exc, 'lineNumber', None)
        ctx = ''
        if line:
            rows = js.split('\n')[max(0, line - 2):line + 1]
            ctx = ' || '.join(r.strip()[:100] for r in rows)
        return '%s (line %s) %s' % (exc, line, ctx)
    return None


def main(argv):
    check = '--check' in argv
    with open(INDEX, encoding='utf-8') as fp:
        src = fp.read()
    before = len(src)

    src, s_nav = put(src, NAV_START, NAV_END, NAV_HTML, '<!-- /FOREST:NAV -->', before=False)
    src, s_sec = put(src, SEC_START, SEC_END, asset('section.html'), '  <section id="valetPanel"')
    src, s_css = put(src, CSS_START, CSS_END, asset('tab.css'), '/* ── 반응형 ─')
    src, s_js = put(src, JS_START, JS_END, asset('app.js'), 'function activate(tab){')
    src, s_tabs = add_tab_entry(src)

    hooks = []
    for name, old, new in HOOKS:
        if old is None:
            continue
        if new in src:
            hooks.append((name, 'already'))
            continue
        if old not in src:
            raise SystemExit('연결 고리를 찾지 못했습니다: %s\n  %r' % (name, old[:90]))
        src = src.replace(old, new, 1)
        hooks.append((name, 'patched'))

    print('nav     %s' % s_nav)
    print('section %s' % s_sec)
    print('css     %s' % s_css)
    print('js      %s' % s_js)
    print('tabs    %s' % s_tabs)
    for n, s in hooks:
        print('hook    %-16s %s' % (n, s))
    print('index.html %d → %d bytes' % (before, len(src)))
    bad = js_syntax_problem(src)
    if bad:
        print('!! JS 문법 검사 실패 — 쓰지 않았습니다: %s' % bad)
        return 1
    if check:
        print('(--check: 쓰지 않았습니다)')
        return 0
    with open(INDEX, 'w', encoding='utf-8') as fp:
        fp.write(src)
    print('index.html 갱신 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
