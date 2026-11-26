#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 라이브 검증 2 — ④ 하얏트 592곳: 새 카드 8곳 값 · 라이브 JSON · 날짜 시트 · 호텔별 메모.

실행:
  LD_LIBRARY_PATH=/workspace/.libs/root/usr/lib/x86_64-linux-gnu python3 tools/verify_hyatt_es8_live2_20261127.py
"""
import os
import time
import json
import urllib.request

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/?v=z228hyatt8b&diag=1#tab=hyatt')
OUT = '/workspace/downloads/hyatt_es_final8_2026-11-27'
STAMP = time.strftime('%Y-%m-%d-%H%M%S')
os.makedirs(OUT, exist_ok=True)

# 라이브 JSON
raw = urllib.request.urlopen('https://toresyo2311-max.github.io/hotel-calendar-app/'
                             'data/app/tab10_hyatt.json?x=%d' % time.time()).read()
tab = json.loads(raw)
hs = tab['hotels']
print('LIVE JSON hotels', len(hs), 'cells', sum(len(h['points']['$v']) for h in hs),
      'priced', sum(1 for h in hs for v in h['points']['$v'] if v is not None))
new = [h for h in hs if int(h['id'][2:]) >= 585]
print('new cards', len(new), [h['code'] for h in new])
for h in new:
    assert '**' not in h['note'] and '개관 전' not in h['note'] and 'http' not in h['note'], h['code']
    print('  %s %-6s %-30s %3d일 %s' % (h['id'], h['code'], h['name'],
                                        sum(1 for v in h['points']['$v'] if v is not None), h['city']))
print('새 카드 8곳 메모 — ** · 「개관 전」 · URL 없음')


def w(pg, name):
    path = os.path.join(OUT, '%s-%s.png' % (name, STAMP))
    pg.screenshot(path=path)
    sizes = pg.evaluate('[innerWidth, document.documentElement.scrollWidth, document.body.scrollWidth]')
    print('shot %-46s sizes=%s overflow=%dpx' % (name, sizes, max(sizes[1], sizes[2]) - sizes[0]))
    print('   ', path)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    errs = []
    pg.on('console', lambda m: errs.append('console.%s: %s' % (m.type, m.text)) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append('pageerror: %s' % e))
    pg.goto(URL, wait_until='load')
    pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942')
        pg.click('#lockGo')
        pg.wait_for_timeout(1500)
    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2500)

    opts = pg.evaluate("() => [...document.querySelectorAll('#citySelect option')].map(o=>o.textContent)")
    pg.select_option('#citySelect', index=0)
    pg.wait_for_timeout(1800)
    pool = pg.evaluate("() => [...document.querySelectorAll('#hotelSelect option')].map(o=>o.textContent)")
    print('hotelSelect options after 전체', len(pool))

    for name, tag, shot in (('알루아솔 오로타바 밸리', 'asora', True),
                            ('톰슨 세비야', 'svqth', True),
                            ('알루아 테네리페', 'alten', True),
                            ('그랜드 하얏트 란사로테 플라야 도라다 리조트', 'drepd', True),
                            ('바이아 프린시페 익스플로어 산 펠리페', 'bp019', True),
                            ('하얏트 지바 하르딘 트로피칼 테네리페', 'drjtf', False)):
        label = next((o for o in pool if name in o), '')
        print('label', name, '->', label)
        if not label:
            continue
        pg.select_option('#hotelSelect', label=label)
        pg.wait_for_timeout(1800)
        info = pg.evaluate("""() => {
            const c=document.querySelector('article.month-card');
            const cells=c?[...c.querySelectorAll('.cal-day')]:[];
            return {cards:document.querySelectorAll('article.month-card').length,
                    numbered:cells.filter(x=>/[0-9]+(\\.[0-9]+)?만?P/.test(x.textContent)).length,
                    first3:cells.slice(1,6).map(x=>x.textContent.replace(/\\s+/g,' ').trim())};}""")
        print(' ', name, info)
        pg.evaluate("() => {const c=document.querySelector('article.month-card');"
                    "if(c) window.scrollTo(0, c.getBoundingClientRect().top + window.scrollY - 120);}")
        pg.wait_for_timeout(400)
        if shot:
            w(pg, '05_390px_hyatt_card_%s' % tag)

    # 날짜 시트
    label = next((o for o in pool if '그랜드 하얏트 란사로테' in o), '')
    if label:
        pg.select_option('#hotelSelect', label=label)
        pg.wait_for_timeout(1600)
        clicked = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            if(!c) return false;
            const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/[0-9]+(\\.[0-9]+)?만?P/.test(x.textContent));
            if(!cells.length) return false; cells[3].click(); return true;}""")
        pg.wait_for_timeout(1500)
        print('day cell clicked', clicked)
        w(pg, '06_390px_hyatt_daysheet_drepd')

    # 호텔별 메모(#hyattNotes)
    ok = pg.evaluate("""() => {const n=document.getElementById('hyattNotes');
        const d=n && n.closest('details'); if(!d) return false; d.open=true; d.scrollIntoView(); return true;}""")
    pg.wait_for_timeout(800)
    nt = pg.evaluate("() => (document.getElementById('hyattNotes')||{textContent:''}).textContent.replace(/\\s+/g,' ')")
    print('notes opened', ok, 'length', len(nt))
    for key in ('알루아솔 오로타바 밸리', '톰슨 세비야', '알루아 테네리페', '그랜드 하얏트 란사로테 플라야 도라다 리조트',
                '바이아 프린시페 익스플로어 산 펠리페', '하얏트 지바 하르딘 트로피칼 테네리페'):
        i = nt.find(key)
        print('---', key, 'found' if i >= 0 else 'MISSING')
        if i >= 0:
            print(nt[i:i + 260])
    pg.evaluate("""() => {const n=document.getElementById('hyattNotes');
        const d=n.closest('details'); window.scrollTo(0, d.getBoundingClientRect().top + window.scrollY - 120);}""")
    pg.wait_for_timeout(400)
    w(pg, '07_390px_hyatt_notes')

    print('console errors', len(errs))
    for e in errs[:8]:
        print('  ', e)
    print('overflow', pg.evaluate('document.documentElement.scrollWidth-390'))
    b.close()
