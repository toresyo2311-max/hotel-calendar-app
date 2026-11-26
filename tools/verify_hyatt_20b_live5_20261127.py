#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기존 포인트 전용 호텔(2026-11-26 병합분)과 새 호텔의 날짜 클릭 패널 동작이 같은지 대조."""
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b5&diag=1#tab=hyatt'

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    ctx = b.new_context(viewport={'width': 390, 'height': 844})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='load')
    pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942')
        pg.click('#lockGo')
        pg.wait_for_timeout(1500)
    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2500)
    for nm in ('그랜드 하얏트 싱가포르', '안다즈 도하'):
        lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", nm)
        if not lab:
            print('missing', nm); continue
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1600)
        pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/P/.test(x.textContent));
            cells[4].click();}""")
        pg.wait_for_timeout(1200)
        t = pg.evaluate("""() => document.body.innerText.replace(/\\s+/g,' ')""")
        i = t.find('1박 · KRW')
        print('%-22s panel: %s' % (nm, t[i-40:i+180] if i>=0 else '(no panel)'))
    b.close()
