#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 라이브 검증 — ④ 하얏트 20곳 병합(z220) · 마드리드 · 델리 · 도하 달력·카드·상세 시트.

  1) ④ 하얏트 탭 배지 485 · aria-label  2) 기준(basis) 머리줄 · 🆕 20곳 줄  3) 주의(caution) 새 항목
  4) 마드리드 필터 달력 5) 뉴델리 6) 도하 7) 호텔 목록(남아시아 표기) 8) 상세 시트 공홈 링크
  9) 콘솔 에러 · 가로 넘침
"""
import os
import time

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b&diag=1#tab=hyatt')
OUT = '/workspace/downloads/hyatt_20b_2026-11-27'
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

    # 1) 탭 버튼
    print('tab badge:', pg.evaluate("""() => {const b=document.querySelector('button[data-tab="hyatt"]');
        return b ? b.textContent.replace(/\\s+/g,' ').trim()+' || '+b.getAttribute('aria-label') : '';}"""))

    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2500)

    # 2) 기준 줄
    print('BASIS:', txt(pg, '#basis', 900))
    pg.evaluate("() => window.scrollTo(0,0)")
    pg.wait_for_timeout(300)
    w(pg, '01_390px_hyatt_header')

    # 3) 주의문 — 하얏트 탭
    print('CAUTION:', txt(pg, '#caution', 700))

    # 호텔 목록의 남아시아 표기
    try:
        pg.click('#hotelFoldBtn')
        pg.wait_for_timeout(900)
        rows = pg.evaluate("""() => [...document.querySelectorAll('.hotel-row')]
            .map(r=>r.textContent.replace(/\\s+/g,' ').trim())
            .filter(t=>/남아시아|마드리드|도하|뉴델리/.test(t)).slice(0,12)""")
        print('hotel rows(남아시아·마드리드·도하·뉴델리):', rows)
        w(pg, '02_390px_hyatt_hotel_list')
        pg.click('#hotelFoldBtn')
        pg.wait_for_timeout(500)
    except Exception as e:                                 # noqa: BLE001
        print('hotel fold skip', e)

    for city, tag in (('마드리드', 'madrid'), ('뉴델리', 'delhi'), ('도하', 'doha')):
        opts = pg.evaluate("() => [...document.querySelectorAll('#citySelect option')].map(o=>o.textContent)")
        print('cities', len(opts), city in opts)
        pg.select_option('#citySelect', label=city)
        pg.wait_for_timeout(2200)
        cards = pg.evaluate("() => document.querySelectorAll('article.month-card').length")
        names = pg.evaluate("""() => [...document.querySelectorAll('article.month-card h3, article.month-card .mc-h, article.month-card b')]
            .map(x=>x.textContent.replace(/\\s+/g,' ').trim()).slice(0,4)""")
        print('%s cards=%d heads=%s' % (city, cards, names))
        if cards:
            scroll_to(pg, 'article.month-card')
            print(' card:', txt(pg, 'article.month-card', 320))
            w(pg, '03_390px_hyatt_%s_calendar' % tag)

    # 상세 시트 — 도하 안다즈(365일) 셀
    try:
        label = pg.evaluate("""() => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes('안다즈 도하')); return o ? o.textContent : '';}""")
        print('hotel label', label)
        if label:
            pg.select_option('#hotelSelect', label=label)
            pg.wait_for_timeout(2000)
            scroll_to(pg, 'article.month-card')
            print(' dohaz card:', txt(pg, 'article.month-card', 380))
            w(pg, '04_390px_hyatt_doha_andaz_calendar')
            clicked = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
                if(!c) return false;
                const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/\\d{3,}/.test(x.textContent.replace(/,/g,'')));
                if(!cells.length) return false; cells[3].click(); return true;}""")
            pg.wait_for_timeout(1400)
            print('cell clicked', clicked)
            print('links', pg.evaluate("""() => [...new Set([...document.querySelectorAll('a[href*="hyatt.com"]')]
                .map(a=>a.getAttribute('href')))].slice(0,6)"""))
            w(pg, '05_390px_hyatt_doha_day_sheet')
    except Exception as e:                                 # noqa: BLE001
        print('sheet skip', e)

    print('console errors', len(errs))
    for e in errs[:10]:
        print('  ', e)
    print('overflow max', max(max(s[1], s[2]) for _, _, s in shots) - 390)
    b.close()

print('\nSHOTS')
for n, path, s in shots:
    print(n, path, s)
