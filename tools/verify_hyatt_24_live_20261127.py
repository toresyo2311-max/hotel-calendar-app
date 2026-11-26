#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 라이브 검증 — ④ 하얏트 24곳 병합(z227 · 560→584곳).

  1) ④ 하얏트 탭 배지 584 · aria-label  2) 탭 제목·부제  3) 기준(basis) 머리줄 · 🆕 24곳 줄
  4) 주의(caution) 새 항목  5) 하이데라바드 · 자이푸르 · 토론토 · 프린스앨버트 · 스페인 달력
  6) 새 카드 메시지(「Coming Soon」 문구가 달력 전체를 미오픈으로 칠하지 않는지)  7) 콘솔 에러 · 가로 넘침

실행:
  LD_LIBRARY_PATH=/workspace/.libs/root/usr/lib/x86_64-linux-gnu python3 tools/verify_hyatt_24_live_20261127.py
(이 환경의 headless chromium 은 libnspr4 등 시스템 라이브러리가 /workspace/.libs 아래에 있어 위 경로가 필요하다)
"""
import os
import time

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/?v=z227hyatt24&diag=1#tab=hyatt')
OUT = '/workspace/downloads/hyatt_24_2026-11-27'
STAMP = time.strftime('%Y-%m-%d-%H%M%S')
os.makedirs(OUT, exist_ok=True)
shots = []


def w(pg, name):
    path = os.path.join(OUT, '%s-%s.png' % (name, STAMP))
    pg.screenshot(path=path)
    sizes = pg.evaluate('[innerWidth, document.documentElement.scrollWidth, document.body.scrollWidth]')
    shots.append((name, path, sizes))
    print('shot %-46s sizes=%s overflow=%dpx' % (name, sizes, max(sizes[1], sizes[2]) - sizes[0]))
    print('   ', path)


def scroll_to(pg, sel, pad=150):
    pg.evaluate("""([sel,pad]) => {const el=document.querySelector(sel);
        if(el) window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - pad);}""", [sel, pad])
    pg.wait_for_timeout(500)


def txt(pg, sel, n=400):
    return pg.evaluate("""([sel,n]) => {const e=document.querySelector(sel);
        return e ? e.textContent.replace(/\\s+/g,' ').slice(0,n) : '';}""", [sel, n])


def card(pg):
    return pg.evaluate("""() => ({cards: document.querySelectorAll('article.month-card').length,
        vals: document.querySelectorAll('article.month-card .cal-day').length,
        head: (document.querySelector('article.month-card')||{textContent:''}).textContent.replace(/\\s+/g,' ').slice(0,60),
        sample: [...document.querySelectorAll('article.month-card .cal-day')].map(x=>x.textContent.trim()).slice(0,10)})""")


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
    print('unlocked:', not pg.evaluate("() => document.documentElement.classList.contains('locked')"))

    print('tab badge/basis-aria:', pg.evaluate("""() => {const b=document.querySelector('button[data-tab="hyatt"]');
        return b ? b.textContent.replace(/\\s+/g,' ').trim()+' || '+b.getAttribute('aria-label') : '';}"""))

    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2500)

    print('BASIS:', txt(pg, '#basis', 700))
    pg.evaluate("() => window.scrollTo(0,0)")
    pg.wait_for_timeout(300)
    w(pg, '01_390px_hyatt_header_584')

    print('CAUTION:', txt(pg, '#caution', 600))

    # 호텔 목록 — 새 도시 표기
    try:
        pg.click('#hotelFoldBtn')
        pg.wait_for_timeout(900)
        rows = pg.evaluate("""() => [...document.querySelectorAll('.hotel-row')]
            .map(r=>r.textContent.replace(/\\s+/g,' ').trim())
            .filter(t=>/하이데라바드|자이푸르|토론토|화이트호스|윈저|프린스앨버트|메노르카|란사로테|미하스/.test(t)).slice(0,14)""")
        print('hotel rows:', rows)
        w(pg, '02_390px_hyatt_hotel_list_new_cities')
        pg.click('#hotelFoldBtn')
        pg.wait_for_timeout(500)
    except Exception as e:                                 # noqa: BLE001
        print('hotel fold skip', e)

    for city, tag in (('하이데라바드', 'hyderabad'), ('자이푸르', 'jaipur'), ('토론토', 'toronto'),
                      ('프린스앨버트', 'princealbert'), ('메노르카', 'menorca'), ('란사로테', 'lanzarote')):
        opts = pg.evaluate("() => [...document.querySelectorAll('#citySelect option')].map(o=>o.textContent)")
        print('cities', len(opts), city, city in opts)
        if city not in opts:
            continue
        pg.select_option('#citySelect', label=city)
        pg.wait_for_timeout(2200)
        print('%s %s' % (city, card(pg)))
        scroll_to(pg, 'article.month-card')
        print(' card:', txt(pg, 'article.month-card', 220))
        w(pg, '03_390px_hyatt_%s_calendar' % tag)

    print('console errors', len(errs))
    for e in errs[:10]:
        print('  ', e)
    print('overflow max', max(max(s[1], s[2]) for _, _, s in shots) - 390)
    b.close()

print('\nSHOTS')
for n, path, s in shots:
    print(n, path, s)
