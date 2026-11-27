#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 라이브 검증 — ④ 하얏트 남아시아 마지막 21곳(z232) · 몰디브·인도 달력.

  1) ④ 하얏트 탭 배지 613 · aria-label  2) 기준(basis) 머리줄 · 남아시아 61
  3) 주의(caution)  4) 몰디브(라 아톨) 필터 달력  5) 인도 콜카타 달력
  6) 파크 하얏트 몰디브 하다하 · 하얏트 리젠시 콜카타 달력·상세 시트 7) 콘솔 에러 · 가로 넘침
"""
import os
import time

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/?v=z232sa21&diag=1#tab=hyatt')
OUT = '/workspace/downloads/hyatt_sa21_2026-11-27'
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
    print('BASIS:', txt(pg, '#basis', 700))
    print('SUB:', txt(pg, '#sectionSubtitle', 400))
    print('CHECK:', txt(pg, '#checktime', 400))
    pg.evaluate("() => window.scrollTo(0,0)")
    pg.wait_for_timeout(300)
    w(pg, '01_390px_hyatt_header')

    # 3) 주의문
    print('CAUTION:', txt(pg, '#caution', 500))

    # 호텔 목록의 남아시아 표기
    try:
        pg.click('#hotelFoldBtn')
        pg.wait_for_timeout(900)
        rows = pg.evaluate("""() => [...document.querySelectorAll('.hotel-row')]
            .map(r=>r.textContent.replace(/\\s+/g,' ').trim())
            .filter(t=>/남아시아|몰디브|네팔|콜카타|뭄바이|푸네|코치/.test(t)).slice(0,12)""")
        print('hotel rows(남아시아·몰디브·네팔):', rows)
        w(pg, '02_390px_hyatt_hotel_list')
        pg.click('#hotelFoldBtn')
        pg.wait_for_timeout(500)
    except Exception as e:                                 # noqa: BLE001
        print('hotel fold skip', e)

    for city, tag in (('라 아톨', 'maldives'), ('콜카타', 'kolkata')):
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

    # 상세 — 몰디브 파크 하얏트 · 인도 하얏트 리젠시 콜카타
    # ① 호텔별 달력만 먼저 (시트가 열리기 전에 인도 달력까지 찍는다)
    for hotel, city, tag in (('파크 하얏트 몰디브 하다하', '가푸 알리푸 아톨', 'maldives_parkhyatt'),
                             ('하얏트 리젠시 콜카타', '콜카타', 'kolkata_regency')):
        pg.select_option('#citySelect', label=city)
        pg.wait_for_timeout(1800)
        label = pg.evaluate("""(name) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(name)); return o ? o.textContent : '';}""", hotel)
        print('hotel label', hotel, '→', label)
        if not label:
            continue
        pg.select_option('#hotelSelect', label=label)
        pg.wait_for_timeout(2000)
        scroll_to(pg, 'article.month-card')
        print(' card:', txt(pg, 'article.month-card', 380))
        w(pg, '04_390px_hyatt_%s_calendar' % tag)

    # ② 이어서 상세 시트 (몰디브는 마지막에 찍어 인도 달력을 가리지 않게)
    for hotel, city, tag in (('파크 하얏트 몰디브 하다하', '가푸 알리푸 아톨', 'maldives_parkhyatt'),
                             ('하얏트 리젠시 콜카타', '콜카타', 'kolkata_regency')):
        pg.select_option('#citySelect', label=city)
        pg.wait_for_timeout(1500)
        label = pg.evaluate("""(name) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(name)); return o ? o.textContent : '';}""", hotel)
        if not label:
            continue
        pg.select_option('#hotelSelect', label=label)
        pg.wait_for_timeout(1800)
        scroll_to(pg, 'article.month-card')
        clicked = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            if(!c) return false;
            const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/만P|,?\\d{3,}P/.test(x.textContent));
            if(!cells.length) return false; cells[3].click(); return true;}""")
        pg.wait_for_timeout(1400)
        print(' cell clicked', tag, clicked)
        w(pg, '05_390px_hyatt_%s_day_sheet' % tag)
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(500)

    print('console errors', len(errs))
    for e in errs[:10]:
        print('  ', e)
    print('overflow max', max(max(s[1], s[2]) for _, _, s in shots) - 390)
    b.close()

print('\nSHOTS')
for n, path, s in shots:
    print(n, path, s)
