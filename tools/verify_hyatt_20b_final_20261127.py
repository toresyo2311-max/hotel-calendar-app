#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""최종 라이브 확인 — 배지·조회 기준·세 도시 달력·콘솔·넘침(2026-11-27 배포본 z221 위)."""
import os, time
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=final220hyatt&diag=1#tab=hyatt'
OUT = '/workspace/downloads/hyatt_20b_2026-11-27'
ST = time.strftime('%Y-%m-%d-%H%M%S')

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    errs = []
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until='load'); pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942'); pg.click('#lockGo'); pg.wait_for_timeout(1500)
    print('badge:', pg.evaluate("""() => document.querySelector('button[data-tab="hyatt"]').textContent.replace(/\\s+/g,' ').trim()"""))
    pg.click('button[data-tab="hyatt"]'); pg.wait_for_timeout(2500)
    print('checked:', pg.evaluate("""() => {const e=[...document.querySelectorAll('*')]
        .find(x=>x.children.length===0 && /조회 기준: 2026-11-22~23/.test(x.textContent));
        return e? e.textContent.slice(0,220):'(not found)'}"""))
    for city, tag in (('마드리드','madrid'), ('뉴델리','delhi'), ('도하','doha')):
        pg.select_option('#citySelect', label=city); pg.wait_for_timeout(1800)
        n = pg.evaluate("() => document.querySelectorAll('article.month-card').length")
        w = pg.evaluate('[innerWidth, document.documentElement.scrollWidth]')
        print(city, 'cards', n, 'width', w, 'overflow', w[1]-w[0])
        pg.evaluate("() => {const el=document.querySelector('article.month-card'); if(el) scrollTo(0, el.getBoundingClientRect().top+scrollY-190)}")
        pg.wait_for_timeout(400)
        path = os.path.join(OUT, '12_390px_hyatt_%s_final-%s.png' % (tag, ST))
        pg.screenshot(path=path); print('  ', path)
    print('console errors', len(errs), errs[:3])
    b.close()
