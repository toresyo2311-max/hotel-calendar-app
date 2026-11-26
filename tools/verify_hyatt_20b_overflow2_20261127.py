#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""넘침 67px 의 정체 — 도시 필터를 기존 지점으로 바꿔도 같은지."""
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b9&diag=1#tab=hyatt'

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    pg.goto(URL, wait_until='load'); pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942'); pg.click('#lockGo'); pg.wait_for_timeout(1500)
    pg.click('button[data-tab="hyatt"]'); pg.wait_for_timeout(2500)
    pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .filter(d=>d.textContent.includes('카테고리 · 특이사항')); if(d.length) d[0].open=true;}""")
    pg.wait_for_timeout(700)
    print('base', pg.evaluate('[390, document.documentElement.scrollWidth]'))
    for city in ('뉴욕', '도쿄', '마드리드'):
        try:
            pg.select_option('#citySelect', label=city)
        except Exception as e:
            print(city, 'select fail', str(e)[:60]); continue
        pg.wait_for_timeout(1200)
        w = pg.evaluate('[innerWidth, document.documentElement.scrollWidth]')
        print(city, w, 'overflow', w[1]-w[0])
        if w[1] > 390:
            print('  widest page:', pg.evaluate("""() => [...document.querySelectorAll('body *')]
                .map(e=>({r:Math.round(e.getBoundingClientRect().right), tag:e.tagName, id:e.id,
                          cls:(e.className||'').toString().slice(0,30), t:(e.textContent||'').trim().slice(0,40)}))
                .filter(o=>o.r>392).sort((a,b)=>b.r-a.r).slice(0,6)"""))
    b.close()
