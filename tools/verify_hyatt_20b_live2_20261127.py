#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 라이브 검증 2 — 상세 시트(공홈 링크) · '자료 없음' 표기가 기존 포인트 전용 카드와 같은지."""
import os
import time

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b2&diag=1#tab=hyatt'
OUT = '/workspace/downloads/hyatt_20b_2026-11-27'
STAMP = time.strftime('%Y-%m-%d-%H%M%S')


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

    # 기존 포인트 전용 카드(그랜드 하얏트 싱가포르 · 2026-11-26 병합분)와 새 카드의 표기를 견준다
    pg.select_option('#citySelect', label='싱가포르')
    pg.wait_for_timeout(2000)
    pg.evaluate("() => {const el=document.querySelector('article.month-card'); if(el) window.scrollTo(0, el.getBoundingClientRect().top+scrollY-150)}")
    pg.wait_for_timeout(400)
    print('SINGAPORE card:', pg.evaluate("""() => {const c=document.querySelector('article.month-card');
        return c? c.textContent.replace(/\\s+/g,' ').slice(0,160):''}"""))
    w(pg, '06_390px_hyatt_singapore_reference')

    # 새 카드와 상세 시트 — 안다즈 도하
    pg.select_option('#citySelect', value='all')
    pg.wait_for_timeout(1500)
    print('city options reset', pg.evaluate("() => document.querySelector('#citySelect').value"))
    label = pg.evaluate("""() => {const o=[...document.querySelectorAll('#hotelSelect option')]
        .find(o=>o.textContent.includes('안다즈 도하')); return o?o.textContent:''}""")
    pg.select_option('#hotelSelect', label=label)
    pg.wait_for_timeout(1800)
    res = pg.evaluate("""() => {const c=document.querySelector('article.month-card'); if(!c) return null;
        const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/P/.test(x.textContent));
        if(!cells.length) return null; cells[4].click();
        return cells[4].textContent.replace(/\\s+/g,' ').trim();}""")
    pg.wait_for_timeout(1500)
    print('clicked cell', res)
    print('sheet text:', pg.evaluate("""() => {const s=[...document.querySelectorAll('#bkSheet,#daySheet,[id*=Sheet]')]
        .find(e=>e.offsetParent && e.getBoundingClientRect().height>80);
        return s? s.textContent.replace(/\\s+/g,' ').slice(0,600) : '(no sheet)'}"""))
    print('hyatt links', pg.evaluate("""() => [...new Set([...document.querySelectorAll('a[href*="hyatt.com"]')]
        .map(a=>a.getAttribute('href')))]"""))
    w(pg, '07_390px_hyatt_doha_day_sheet')

    # 기준(basis) 🆕 줄
    print('BASIS NEW ROW:', pg.evaluate("""() => {const b=document.querySelector('#basis');
        if(!b) return ''; const t=b.textContent.replace(/\\s+/g,' ');
        const i=t.indexOf('2026-11-27에 ④ 하얏트'); return i<0? '(not found)': t.slice(i, i+700);}"""))
    pg.evaluate("() => window.scrollTo(0,0)")
    pg.wait_for_timeout(400)

    # 미참여 2곳 카드 메모
    for nm in ('바이아 프린시페 이스케이프 코랄 플라야', '하얏트 플레이스 비자야와다'):
        lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", nm)
        if not lab:
            print('option missing', nm)
            continue
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1500)
        print(nm, '->', pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            return c? c.textContent.replace(/\\s+/g,' ').slice(0,120):''}"""))
        pg.evaluate("() => {const el=document.querySelector('article.month-card'); if(el) window.scrollTo(0, el.getBoundingClientRect().top+scrollY-150)}")
    w(pg, '08_390px_hyatt_vgazv_card')

    print('console errors', len(errs))
    for e in errs[:8]:
        print('  ', e)
    b.close()
