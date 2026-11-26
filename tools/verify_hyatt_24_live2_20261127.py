#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 라이브 검증 2 — ④ 하얏트 24곳 새 카드별 값 표시 · 라이브 JSON · 날짜 시트 · 호텔별 메모.

실행:
  LD_LIBRARY_PATH=/workspace/.libs/root/usr/lib/x86_64-linux-gnu python3 tools/verify_hyatt_24_live2_20261127.py
"""
import os
import time
import json
import urllib.request

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/?v=z227hyatt24b&diag=1#tab=hyatt')
OUT = '/workspace/downloads/hyatt_24_2026-11-27'
STAMP = time.strftime('%Y-%m-%d-%H%M%S')
os.makedirs(OUT, exist_ok=True)

# 라이브 JSON
raw = urllib.request.urlopen('https://toresyo2311-max.github.io/hotel-calendar-app/'
                             'data/app/tab10_hyatt.json?x=%d' % time.time()).read()
tab = json.loads(raw)
hs = tab['hotels']
print('LIVE JSON hotels', len(hs), 'cells', sum(len(h['points']['$v']) for h in hs),
      'priced', sum(1 for h in hs for v in h['points']['$v'] if v is not None))
new = [h for h in hs if int(h['id'][2:]) >= 561]
print('new cards', len(new))
for h in new:
    assert '**' not in h['note'] and '개관 전' not in h['note'], h['code']
print('새 카드 24곳 메모 — ** · 「개관 전」 없음')


def w(pg, name):
    path = os.path.join(OUT, '%s-%s.png' % (name, STAMP))
    pg.screenshot(path=path)
    sizes = pg.evaluate('[innerWidth, document.documentElement.scrollWidth, document.body.scrollWidth]')
    print('shot %-44s sizes=%s overflow=%dpx' % (name, sizes, max(sizes[1], sizes[2]) - sizes[0]))
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

    # 도시 필터를 전체로
    opts = pg.evaluate("() => [...document.querySelectorAll('#citySelect option')].map(o=>o.textContent)")
    print('city first options', opts[:3])
    pg.select_option('#citySelect', index=0)
    pg.wait_for_timeout(1800)
    pool = pg.evaluate("() => [...document.querySelectorAll('#hotelSelect option')].map(o=>o.textContent)")
    print('hotelSelect options after 전체', len(pool))

    for name, tag, shot in (('파크 하얏트 하이데라바드', 'hydph', True),
                            ('하얏트 플레이스 토론토 에어포트', 'torza', True),
                            ('하얏트 스튜디오 프린스앨버트', 'caaae', True),
                            ('라 잠브라 리조트', 'agpub', False)):
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
                    first3:cells.slice(0,6).map(x=>x.textContent.replace(/\\s+/g,' ').trim())};}""")
        print(' ', name, info)
        pg.evaluate("() => {const c=document.querySelector('article.month-card');"
                    "if(c) window.scrollTo(0, c.getBoundingClientRect().top + window.scrollY - 120);}")
        pg.wait_for_timeout(400)
        if shot:
            w(pg, '05_390px_hyatt_card_%s' % tag)

    # 날짜 시트
    label = next((o for o in pool if '하얏트 플레이스 토론토 에어포트' in o), '')
    if label:
        pg.select_option('#hotelSelect', label=label)
        pg.wait_for_timeout(1600)
        clicked = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            if(!c) return false;
            const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/[0-9]+(\\.[0-9]+)?만?P/.test(x.textContent));
            if(!cells.length) return false; cells[3].click(); return true;}""")
        pg.wait_for_timeout(1500)
        print('day cell clicked', clicked)
        w(pg, '06_390px_hyatt_daysheet_torza')

    # 호텔별 메모(#hyattNotes)
    ok = pg.evaluate("""() => {const n=document.getElementById('hyattNotes');
        const d=n && n.closest('details'); if(!d) return false; d.open=true; d.scrollIntoView(); return true;}""")
    pg.wait_for_timeout(800)
    nt = pg.evaluate("() => (document.getElementById('hyattNotes')||{textContent:''}).textContent.replace(/\\s+/g,' ')")
    print('notes opened', ok, 'length', len(nt))
    for key in ('하얏트 하이데라바드 가치보울리', '파크 하얏트 토론토', '하얏트 스튜디오 프린스앨버트',
                '시크릿츠 란사로테 리조트 앤 스파', '라 잠브라 리조트', '알릴라 포트 비샹가르'):
        i = nt.find(key)
        print('---', key, 'found' if i >= 0 else 'MISSING')
        if i >= 0:
            print(nt[i:i + 300])
    pg.evaluate("() => {const d=document.getElementById('hyattNotes').closest('details');"
                "window.scrollTo(0, d.getBoundingClientRect().top + window.scrollY - 100);}")
    pg.wait_for_timeout(400)
    w(pg, '07_390px_hyatt_notes')

    print('console errors', len(errs))
    for e in errs[:8]:
        print('  ', e)
    print('overflow', pg.evaluate('document.documentElement.scrollWidth-390'))
    b.close()
