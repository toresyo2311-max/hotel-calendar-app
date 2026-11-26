#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 라이브 검증 — ④ 하얏트 스페인 3차 마지막 8곳 병합(z228 · 584→592곳).

  1) ④ 하얏트 탭 배지 592 · aria-label 유럽 146
  2) 탭 제목·부제(592곳 · 스페인 53)
  3) 기준(basis) 머리줄 592 · 🆕 8곳 줄  4) 주의(caution) 새 항목
  5) 테네리페 · 세비야 · 란사로테 달력  6) 새 카드 8곳 값 표시
  7) 콘솔 에러 · 가로 넘침

실행:
  LD_LIBRARY_PATH=/workspace/.libs/root/usr/lib/x86_64-linux-gnu python3 tools/verify_hyatt_es8_live_20261127.py
"""
import os
import time

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/?v=z228hyatt8&diag=1#tab=hyatt')
OUT = '/workspace/downloads/hyatt_es_final8_2026-11-27'
STAMP = time.strftime('%Y-%m-%d-%H%M%S')
os.makedirs(OUT, exist_ok=True)
shots = []


def w(pg, name):
    path = os.path.join(OUT, '%s-%s.png' % (name, STAMP))
    pg.screenshot(path=path)
    sizes = pg.evaluate('[innerWidth, document.documentElement.scrollWidth, document.body.scrollWidth]')
    shots.append((name, path, sizes))
    print('shot %-48s sizes=%s overflow=%dpx' % (name, sizes, max(sizes[1], sizes[2]) - sizes[0]))
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
        numbered: [...document.querySelectorAll('article.month-card .cal-day')]
            .filter(x=>/[0-9]+(\\.[0-9]+)?만?P/.test(x.textContent)).length,
        cells: document.querySelectorAll('article.month-card .cal-day').length,
        sample: [...document.querySelectorAll('article.month-card .cal-day')].map(x=>x.textContent.trim()).slice(0,8)})""")


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

    nav = pg.evaluate("""() => {const b=document.querySelector('button[data-tab="hyatt"]');
        return b ? b.textContent.replace(/\\s+/g,' ').trim()+' || '+b.getAttribute('aria-label') : '';}""")
    print('tab badge/aria:', nav)

    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2500)

    basis = pg.evaluate("() => (document.getElementById('basis')||{textContent:''}).textContent.replace(/\\s+/g,' ')")
    print('BASIS head:', basis[:180])
    print('BASIS has 592:', '④ 하얏트 592곳' in basis, '| 스페인 53:', '스페인 53 — 테네리페 9' in basis)
    i = basis.find('스페인 3차 마지막 8곳')
    print('BASIS new row:', basis[i:i + 260] if i >= 0 else 'MISSING')

    caution = pg.evaluate("() => (document.getElementById('caution')||{textContent:''}).textContent.replace(/\\s+/g,' ')")
    j = caution.find('스페인 3차 마지막 8곳')
    print('CAUTION new item:', caution[j:j + 260] if j >= 0 else 'MISSING')
    print('CAUTION 런사로테 문구:', '란사로테의 그랜드 하얏트 란사로테 플라야 도라다 리조트는 364일' in caution)

    pg.evaluate("() => window.scrollTo(0,0)")
    pg.wait_for_timeout(300)
    w(pg, '01_390px_hyatt_header_592')

    # 호텔 목록 — 새 도시 표기
    try:
        pg.click('#hotelFoldBtn')
        pg.wait_for_timeout(900)
        rows = pg.evaluate("""() => [...document.querySelectorAll('.hotel-row')]
            .map(r=>r.textContent.replace(/\\s+/g,' ').trim())
            .filter(t=>/테네리페|세비야|란사로테/.test(t)).slice(0,16)""")
        print('hotel rows:', rows)
        w(pg, '02_390px_hyatt_hotel_list_new_cities')
        pg.click('#hotelFoldBtn')
        pg.wait_for_timeout(500)
    except Exception as e:                                 # noqa: BLE001
        print('hotel fold skip', e)

    for city, tag in (('테네리페', 'tenerife'), ('세비야', 'seville'), ('란사로테', 'lanzarote')):
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
