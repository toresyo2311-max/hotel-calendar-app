#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑧ 마일리지발권 탭의 골격(CSS·마크업·JS)을 index.html 에 넣는다.

한 탭에서 두 자료를 함께 본다.
  · 대한항공(스카이패스) — data/app/tab8_mileage.json (tools/collect_mileage.py 가 매일 04:00 만든다)
  · 외항사 9개 프로그램 — data/app/tab9_partner_mileage.json · _icn.json (tools/build_partner_tab.py)

    python3 tools/build_mileage_tab.py            # 넣기(이미 있으면 마커 사이만 교체)
    python3 tools/build_mileage_tab.py --check    # 넣지 않고 상태만 확인

넣는 자리(마커로 감싸 두어 다시 돌려도 중복되지 않는다):
    CSS      : '/* ── 반응형' 앞
    NAV      : 옛 ⑧ 마일리지 자리(<!-- MILEAGE:NAV --> … <!-- /MILEAGE:NAV -->)
    SECTION  : 발렛 패널 앞
    JS       : function activate(tab){ 앞
연결 고리도 함께 손본다 — 이미 되어 있으면 건드리지 않는다.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
ASSETS = os.path.join(ROOT, 'tools', 'mileage_tab')
APPDIR = os.path.join(ROOT, 'data', 'app')

NAV_START, NAV_END = '<!-- MILEAGE:NAV -->', '<!-- /MILEAGE:NAV -->'
SEC_START, SEC_END = '<!-- MILEAGE:SECTION -->', '<!-- /MILEAGE:SECTION -->'
CSS_START, CSS_END = '/* MILEAGE:CSS */', '/* /MILEAGE:CSS */'
JS_START, JS_END = '// MILEAGE:JS', '// /MILEAGE:JS'

NAV_HTML = ('    <button class="tab" data-tab="mileage" type="button" '
            'aria-label="마일리지발권 — 대한항공(스카이패스) 부산 14개 노선과 외항사 9개 프로그램 보너스 좌석">'
            '<span class="t-full">⑧ 마일리지발권</span>'
            '<span class="t-short" aria-hidden="true">⑧ 마일발권</span> <b>0</b></button>')

HOOKS = [
    ('setDealPanels',
     "const fp=document.getElementById('frPanel');if(fp)fp.hidden=which!=='forest';",
     "const fp=document.getElementById('frPanel');if(fp)fp.hidden=which!=='forest';"
     "const mp=document.getElementById('mgPanel');if(mp)mp.hidden=which!=='mileage';"
     "const sbx=document.getElementById('snapshotBox');if(sbx)sbx.style.display=which==='mileage'?'none':'';"),
    ('render() 디스패치',
     "if(st.tab==='forest'){renderForest();hashSync();return}",
     "if(st.tab==='forest'){renderForest();hashSync();return}\n"
     "  if(st.tab==='mileage'){renderMileage();hashSync();return}"),
    ('tabNeeds',
     "function tabNeeds(tab){\n  if(tab==='valet')return ['valet'];",
     "function tabNeeds(tab){\n  if(tab==='mileage')return ['mileage','mileage-pt'];\n  if(tab==='valet')return ['valet'];"),
    ('DATA_READY',
     "forest:false};",
     "forest:false,mileage:false,'mileage-pt':false};"),
    ('DATA_BUST',
     "forest:'2026-11-22b'};",
     "forest:'2026-11-22b',mileage:'2026-11-22b','mileage-pt':'2026-11-22b'};"),
    ('PART_FILE',
     "forest:'tab7_forest.json'};",
     "forest:'tab7_forest.json',mileage:'tab8_mileage.json','mileage-pt':'tab9_partner_mileage.json'};"),
    ('loadPart',
     "    }else if(tab==='forest'){\n      Object.assign(FRD,data);frPrep();\n    }",
     "    }else if(tab==='forest'){\n      Object.assign(FRD,data);frPrep();\n"
     "    }else if(tab==='mileage'){\n      Object.assign(MGD,data);mlKEPrep();\n"
     "      if(st.tab==='mileage')renderMileage();\n"
     "    }else if(tab==='mileage-pt'){\n      PDS.PUS=data;PMD=data;ptPrep();\n"
     "      if(st.tab==='mileage')renderMileage();\n    }"),
    ('해시 별칭',
     "function applyHashState(p){\n  let tab=p.get('tab');",
     "function applyHashState(p){\n  let tab=p.get('tab');\n"
     "  if(tab==='partner-mileage')tab='mileage';   /* 2026-11-22 통합 — 옛 ⑨ 외항사 주소는 ⑧ 마일리지발권으로 */"),
    ('hashchange 가드',
     "if(!p||!(tabs[p.get('tab')]||p.get('tab')==='china'||p.get('tab')==='domestic'))return;",
     "if(!p||!(tabs[p.get('tab')]||p.get('tab')==='partner-mileage'||p.get('tab')==='china'||p.get('tab')==='domestic'))return;"),
]


def asset(name):
    with open(os.path.join(ASSETS, name), encoding='utf-8') as fp:
        return fp.read().rstrip('\n')


def put(src, start, end, body, anchor, before=True, pad=''):
    block = start + '\n' + body + '\n' + pad + end
    if start in src and end in src:
        a = src.index(start)
        b = src.index(end, a) + len(end)
        return src[:a] + block + src[b:]
    if anchor not in src:
        raise SystemExit('앵커를 찾지 못했습니다: %r' % anchor[:60])
    i = src.index(anchor)
    if before:
        return src[:i] + block + '\n' + src[i:]
    j = i + len(anchor)
    return src[:j] + '\n' + block + src[j:]


def js_syntax_problem(src):
    """이 탭이 넣은 JS 블록만 문법 검사한다(본문의 다른 코드는 손대지 않는다)."""
    try:
        import esprima
    except ImportError:
        return None
    if JS_START not in src or JS_END not in src:
        return 'MILIAGE:JS 블록을 찾지 못했습니다'
    a = src.index(JS_START) + len(JS_START)
    b = src.index(JS_END, a)
    js = src[a:b]
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


def bump_bust(src, token):
    """DATA_BUST 의 두 마일리지 키 값을 올린다(브라우저 HTTP 캐시 회피)."""
    m = re.search(r'const DATA_BUST=\{[^}]*\}', src)
    if not m:
        return src, 0
    line = m.group(0)
    new = line
    new, n1 = re.subn(r"(mileage:')([^']*)(')", lambda x: x.group(1) + token + x.group(3), new, count=1)
    new, n2 = re.subn(r"('mileage-pt':')([^']*)(')", lambda x: x.group(1) + token + x.group(3), new, count=1)
    return src[:m.start()] + new + src[m.end():], n1 + n2


def observed():
    """두 자료의 기준 시각을 읽어 탭 설명의 checked 문구를 만든다."""
    import json
    ke = pt = ''
    try:
        with open(os.path.join(APPDIR, 'tab8_mileage.json'), encoding='utf-8') as fp:
            ke = (json.load(fp) or {}).get('observedLabel', '')
    except Exception:                             # noqa: BLE001
        pass
    try:
        with open(os.path.join(APPDIR, 'tab9_partner_mileage.json'), encoding='utf-8') as fp:
            pt = (json.load(fp) or {}).get('observedLabel', '')
    except Exception:                             # noqa: BLE001
        pass
    parts = []
    if ke:
        parts.append('대한항공 ' + ke)
    if pt:
        parts.append('외항사 ' + pt)
    return ' · '.join(parts) or '2026-11-22 KST'


def main(argv):
    check = '--check' in argv
    with open(INDEX, encoding='utf-8') as fp:
        src = fp.read()
    before = len(src)
    log = []

    src = put(src, NAV_START, NAV_END, NAV_HTML, '<!-- /TT:NAV -->', before=False)
    log.append('nav     교체')
    src = put(src, SEC_START, SEC_END, asset('section.html'), '  <section id="valetPanel"')
    log.append('section 교체')
    src = put(src, CSS_START, CSS_END, asset('tab.css'), '/* ── 반응형 ─')
    log.append('css     교체')
    src = put(src, JS_START, JS_END, asset('app.js'), 'function activate(tab){')
    log.append('js      교체')

    for name, old, new in HOOKS:
        if new and new in src:
            log.append('hook    %-14s 이미 됨' % name)
            continue
        if name in ('DATA_BUST', 'PART_FILE', 'DATA_READY') and "'mileage-pt':" in src:
            log.append('hook    %-14s 이미 됨' % name)
            continue
        if old not in src:
            log.append('hook    %-14s !! 없음' % name)
            continue
        src = src.replace(old, new, 1)
        log.append('hook    %-14s 적용' % name)

    import datetime
    kst = datetime.timezone(datetime.timedelta(hours=9))
    token = datetime.datetime.now(kst).strftime('%Y-%m-%d z%H%M').replace(' z', 'z')
    src, nb = bump_bust(src, token)
    log.append('DATA_BUST 캐시 값 %s' % ('상향 ' + token if nb else '!! 못 찾음'))

    # 탭 설명의 기준 문구만 이번 자료 기준으로 맞춘다
    obs = observed()
    src, n = re.subn(r"(mileage:\{title:'⑧ 마일리지발권[^}]*?checked:')[^']*(')",
                     lambda m: m.group(1) + '수집 기준: ' + obs + ' · 대한항공 공개 보너스 좌석 · 외항사 9개 프로그램 실측' + m.group(2),
                     src, count=1)
    log.append('탭 기준 문구 %s' % ('갱신' if n else '그대로'))

    print('\n'.join(log))
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
