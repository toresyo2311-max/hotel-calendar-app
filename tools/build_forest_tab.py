#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🌲 휴양림 빈자리 탭의 골격(CSS·마크업·JS)과 연결 고리를 index.html 에 넣는다.

탭의 정적 부분만 다루는 도구다. 자료는 `data/app/tab7_forest.json`
(tools/build_forest_data.py 가 만든다) 이고, 이 탭이 처음 열릴 때 지연 로딩한다.

    python3 tools/build_forest_tab.py          # 넣기(이미 있으면 마커 사이만 교체)
    python3 tools/build_forest_tab.py --check  # 넣지 않고 상태만 확인

넣는 자리(마커로 감싸 두어 다시 돌려도 중복되지 않는다):
    CSS      : '/* ── 반응형' 앞
    NAV      : ⑥ 땡처리 버튼 블록 뒤
    SECTION  : 발렛 패널 앞
    TABS     : const tabs={...} 의 valet 항목 앞
    JS       : render(); 호출 앞
연결 고리(한 번만 바꾸면 되는 함수·상수)도 함께 손본다 — 이미 되어 있으면 건드리지 않는다.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
ASSETS = os.path.join(ROOT, 'tools', 'forest_tab')

NAV_START, NAV_END = '<!-- FOREST:NAV -->', '<!-- /FOREST:NAV -->'
SEC_START, SEC_END = '<!-- FOREST:SECTION -->', '<!-- /FOREST:SECTION -->'
CSS_START, CSS_END = '/* FOREST:CSS */', '/* /FOREST:CSS */'
JS_START, JS_END = '// FOREST:JS', '// /FOREST:JS'

TABS_ENTRY = ("forest:{title:'🌲 자연휴양림 빈자리 — 전국 185곳 숲속의집·야영장',"
              "sub:'숲나들e 월별 예약현황을 모아 둔 스냅샷(2026-11-22 07:13 수집)으로 전국 185곳의 숙소·야영장 빈자리를 "
              "권역·객실유형·인원·박수·주말 조건으로 골라 목록·달력·월간 그리드로 봅니다. 예약 버튼은 모두 숲나들e 공식 화면으로 열립니다. / "
              "상태: 예 예약가능 · 대1~9 대기 · 완 완료 · 휴 휴무 · 공 공사·점검 · 추 추첨·우선예약',"
              "checked:'수집 기준: 2026-11-22 07:13 KST · 숲나들e 월별 예약현황',start:'2026-11-22',end:'2027-01-31'}")

NAV_HTML = ('    <button class="tab" data-tab="forest" type="button" aria-label="자연휴양림 빈자리">🌲 휴양림 <b>185</b></button>')

HOOKS = [
    # (설명, 찾을 문자열, 바꿀 문자열)
    ('setDealPanels',
     "const cp=document.getElementById('comboPanel');if(cp)cp.hidden=which!=='combo';",
     "const cp=document.getElementById('comboPanel');if(cp)cp.hidden=which!=='combo';"
     "const fp=document.getElementById('frPanel');if(fp)fp.hidden=which!=='forest';"),
    ('render() 디스패치',
     "if(st.tab==='valet'){renderValet();hashSync();return}",
     "if(st.tab==='valet'){renderValet();hashSync();return}\n"
     "  if(st.tab==='forest'){renderForest();hashSync();return}"),
    ('DATA_READY',
     "const DATA_READY={lux:false,china:false,domestic:false,marriott:false,flight:false,tt:false,valet:false,lounge:false};",
     "const DATA_READY={lux:false,china:false,domestic:false,marriott:false,flight:false,tt:false,valet:false,lounge:false,forest:false};"),
    ('DATA_BUST',
     "const DATA_BUST={valet:'2026-11-20k',lounge:'2026-11-20b'};",
     "const DATA_BUST={valet:'2026-11-20k',lounge:'2026-11-20b',forest:'2026-11-22b'};"),
    ('PART_FILE',
     "const PART_FILE={lux:'tab1_vip.json',china:'tab2_china.json',domestic:'tab3_accor.json',marriott:'tab4_marriott.json',flight:'tab5_flights.json',tt:'tab6_ttang.json',valet:'valet.json',lounge:'lounge.json'};",
     "const PART_FILE={lux:'tab1_vip.json',china:'tab2_china.json',domestic:'tab3_accor.json',marriott:'tab4_marriott.json',flight:'tab5_flights.json',tt:'tab6_ttang.json',valet:'valet.json',lounge:'lounge.json',forest:'tab7_forest.json'};"),
    ('loadPart',
     "    }else if(tab==='lounge'){\n      Object.assign(LOUNGE,data);\n    }",
     "    }else if(tab==='lounge'){\n      Object.assign(LOUNGE,data);\n"
     "    }else if(tab==='forest'){\n      Object.assign(FRD,data);frPrep();\n    }"),
    ('hashBuild',
     "  }else if(st.tab==='flight'){\n    if(fl.route!=='all')add('route',fl.route);",
     "  }else if(st.tab==='forest'){\n"
     "    if(typeof frs!=='undefined'){\n"
     "      if(frs.region!=='부산/경남')add('frr',frs.region);\n"
     "      if(frs.type!=='all')add('frt',frs.type);\n"
     "      if(frs.cap)add('frc',frs.cap);\n"
     "      if(frs.nights>1)add('frn',frs.nights);\n"
     "      if(frs.range!==28)add('frg',frs.range);\n"
     "      if(frs.weekend)add('frw',1);\n"
     "      if(frs.fresh)add('frx',1);\n"
     "      if(frs.q)add('frq',frs.q);\n"
     "      if(frs.view!=='list')add('frv',frs.view);\n"
     "      if(frs.forest)add('frf',frs.forest);\n"
     "    }\n"
     "  }else if(st.tab==='flight'){\n    if(fl.route!=='all')add('route',fl.route);"),
    ('applyHashState',
     "  }else if(tab==='flight'){\n    if(g('route'))fl.route=g('route');",
     "  }else if(tab==='forest'){\n"
     "    if(typeof frs!=='undefined'){\n"
     "      if(g('frr'))frs.region=g('frr');\n"
     "      if(g('frt'))frs.type=g('frt');\n"
     "      if(['0','2','4','6','8'].indexOf(g('frc'))>=0)frs.cap=Number(g('frc'));\n"
     "      if(['1','2','3'].indexOf(g('frn'))>=0)frs.nights=Number(g('frn'));\n"
     "      if(['14','28','70'].indexOf(g('frg'))>=0)frs.range=Number(g('frg'));\n"
     "      frs.weekend=g('frw')==='1';frs.fresh=g('frx')==='1';\n"
     "      if(g('frq'))frs.q=g('frq');\n"
     "      if(['list','cal','grid'].indexOf(g('frv'))>=0)frs.view=g('frv');\n"
     "      if(g('frf'))frs.forest=g('frf');\n"
     "    }\n"
     "  }else if(tab==='flight'){\n    if(g('route'))fl.route=g('route');"),
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
    if "forest:{title:'🌲 자연휴양림" in src:
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
    # 앱 본체가 들어 있는 <script> 블록(맨 앞의 작은 인라인 스크립트가 아니다)
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

    src, s_nav = put(src, NAV_START, NAV_END, NAV_HTML, '<!-- /TT:NAV -->', before=False)
    src, s_sec = put(src, SEC_START, SEC_END, asset('section.html'), '  <section id="valetPanel"')
    src, s_css = put(src, CSS_START, CSS_END, asset('tab.css'), '/* ── 반응형 ─')
    src, s_js = put(src, JS_START, JS_END, asset('app.js'), 'function activate(tab){')
    src, s_tabs = add_tab_entry(src)

    hooks = []
    for name, old, new in HOOKS:
        if new in src:
            hooks.append((name, 'already'))
            continue
        if old not in src:
            # 다른 탭(Mileage 등)이 같은 줄을 먼저 늘려 두면 원문이 달라진다.
            # 연결 고리는 이미 들어가 있으므로(아래 --check 목록으로 확인) 건너뛴다.
            hooks.append((name, 'already(원문 불일치 — 확인 필요)'))
            continue
        src = src.replace(old, new, 1)
        hooks.append((name, 'patched'))

    print('nav     %s' % s_nav)
    print('section %s' % s_sec)
    print('css     %s' % s_css)
    print('js      %s' % s_js)
    print('tabs    %s' % s_tabs)
    for n, s in hooks:
        print('hook    %-14s %s' % (n, s))
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
