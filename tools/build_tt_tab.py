#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑥ 땡처리 · 부산 출발 탭의 골격(CSS·마크업·JS)을 index.html 에 넣는다.

탭의 정적 부분만 다루는 도구다. 상품 데이터는 `const TTANG` 에 있고
`tools/master_db.py`(extract/inject/verify)와 `tools/merge_pus_deals.py` 가 채운다.

    python3 tools/build_tt_tab.py          # 넣기(이미 있으면 마커 사이만 교체)
    python3 tools/build_tt_tab.py --check  # 넣지 않고 상태만 확인

넣는 자리(마커로 감싸 두어 다시 돌려도 중복되지 않는다):
    CSS      : '/* ── 반응형' 앞
    NAV      : ⑤ 항공 탭 버튼 뒤
    SECTION  : <div class="note-grid" id="hotelNotes"> 앞
    TABS     : const tabs={...} 의 마지막 항목 뒤
    JS       : render(); 호출 앞
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
ASSETS = os.path.join(ROOT, 'tools', 'tt_tab')

NAV_START, NAV_END = '<!-- TT:NAV -->', '<!-- /TT:NAV -->'
SEC_START, SEC_END = '<!-- TT:SECTION -->', '<!-- /TT:SECTION -->'
CSS_START, CSS_END = '/* TT:CSS */', '/* /TT:CSS */'
JS_START, JS_END = '// TT:JS', '// /TT:JS'

TABS_ENTRY = ("tt:{title:'부산 출발 땡처리 항공권',"
              "sub:'부산(PUS) 출발 땡처리 항공권 — 공동구매·특가 두 채널을 노선·출발일·기간·잔여석 단위로 모아 "
              "출발일 달력과 노선별 표로 보여 줍니다. 날짜 칸·노선 행·상품 행을 누르면 그 상품 예약 페이지가 "
              "새 탭에서 바로 열립니다. / 성인 1인 왕복 총액(유류·세금 포함)',"
              "checked:'수집 기준: 2026-11-19 KST',start:'2026-11',end:'2027-11'}")

NAV_ANCHOR = ('    <button class="tab" data-tab="flight" type="button">'
              '<span class="t-full">⑤ 항공특가(부산)</span>'
              '<span class="t-short" aria-hidden="true">⑤ 항공</span> <b>47</b></button>\n')
SEC_ANCHOR = '  <div class="note-grid" id="hotelNotes">\n'
CSS_ANCHOR = '/* ── 반응형 ─'
JS_ANCHOR = '\nrender();\n</script>'


def asset(name):
    with open(os.path.join(ASSETS, name), encoding='utf-8') as fp:
        return fp.read().rstrip('\n')


def wrap(start, end, body, pad=''):
    return start + '\n' + body + '\n' + pad + end


def put(src, start, end, body, anchor, before=True, pad=''):
    """마커가 있으면 사이를 교체, 없으면 anchor 기준으로 새로 넣는다."""
    if start in src and end in src:
        a = src.index(start)
        b = src.index(end, a) + len(end)
        return src[:a] + wrap(start, end, body, pad) + src[b:], 'replaced'
    if anchor not in src:
        raise SystemExit('앵커를 찾지 못했습니다: %r' % anchor)
    i = src.index(anchor)
    block = wrap(start, end, body, pad)
    if before:
        return src[:i] + block + '\n' + src[i:], 'inserted'
    j = i + len(anchor)
    return src[:j] + block + '\n' + src[j:], 'inserted'


def add_tab_entry(src):
    if "tt:{title:'부산 출발 땡처리 항공권'" in src:
        return src, 'already'
    a = src.index('const tabs={')
    b = src.index('};', a)              # 탭 객체를 닫는 `}` 바로 앞에 넣는다
    if src[b - 1] != '}':
        raise SystemExit('const tabs 의 끝을 찾지 못했습니다: %r' % src[b - 6:b + 2])
    return src[:b] + ',' + TABS_ENTRY + src[b:], 'inserted'


def js_syntax_problem(src):
    """<script> 안 JS 문법 검사(esprima). 실패하면 사유 문자열, 통과하면 None.

    원본 코드가 ES2020 옵셔널 체이닝을 쓰기 때문에 검사 전에 `?.` / `??` 만 단순형으로 바꿔 파싱한다.
    esprima 가 없으면 검사하지 않는다(문법 사고를 막는 보조 장치일 뿐이다).
    """
    try:
        import esprima
    except ImportError:
        return None
    a = src.index('<script>') + len('<script>')
    b = src.rindex('</script>')
    js = src[a:b]
    js = js.replace('?.[', '[')
    js = re.sub(r'\?\.', '.', js)
    js = js.replace('??', '||')
    try:
        esprima.parseScript(js)
    except Exception as exc:                      # noqa: BLE001 - 파서 예외를 그대로 보여준다
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
    before_len = len(src)

    nav = ('    <button class="tab" data-tab="tt" type="button">'
           '<span class="t-full">⑥ 땡처리(부산)</span>'
           '<span class="t-short" aria-hidden="true">⑥ 땡처리</span> <b>0</b></button>')
    src, s_nav = put(src, NAV_START, NAV_END, nav, NAV_ANCHOR, before=False)
    src, s_sec = put(src, SEC_START, SEC_END, asset('section.html'), SEC_ANCHOR, before=True)
    src, s_css = put(src, CSS_START, CSS_END, asset('tab.css'), CSS_ANCHOR, before=True)
    src, s_js = put(src, JS_START, JS_END, asset('app.js'), JS_ANCHOR, before=True)
    src, s_tabs = add_tab_entry(src)

    print('nav     %s' % s_nav)
    print('section %s' % s_sec)
    print('css     %s' % s_css)
    print('tabs    %s' % s_tabs)
    print('js      %s' % s_js)
    print('index.html %d → %d bytes' % (before_len, len(src)))
    bad = js_syntax_problem(src)
    if bad:
        print('!! JS 문법 검사 실패 — 쓰지 않았습니다: %s' % bad)
        return 1
    if check:
        print('(--check: 쓰지 않았습니다)')
        return 0
    if src != open(INDEX, encoding='utf-8').read():
        with open(INDEX, 'w', encoding='utf-8') as fp:
            fp.write(src)
    print('index.html 갱신 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
