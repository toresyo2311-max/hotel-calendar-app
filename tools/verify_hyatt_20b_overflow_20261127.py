#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주의문 펼침 상태 가로 넘침 원인 찾기."""
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b7&diag=1#tab=hyatt'

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    pg.goto(URL, wait_until='load'); pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942'); pg.click('#lockGo'); pg.wait_for_timeout(1500)
    pg.click('button[data-tab="hyatt"]'); pg.wait_for_timeout(2500)
    print('closed', pg.evaluate('[innerWidth, document.documentElement.scrollWidth]'))
    pg.evaluate("""() => {const c=document.querySelector('#caution'); const d=c.closest('details'); if(d) d.open=true;}""")
    pg.wait_for_timeout(600)
    print('open', pg.evaluate('[innerWidth, document.documentElement.scrollWidth]'))
    print('widest:', pg.evaluate("""() => [...document.querySelectorAll('body *')]
        .map(e=>({w:e.getBoundingClientRect().right + window.scrollX, tag:e.tagName, id:e.id, cls:(e.className||'').toString().slice(0,40), t:(e.textContent||'').trim().slice(0,60)}))
        .filter(o=>o.w>396).sort((a,b)=>b.w-a.w).slice(0,8)"""))
    b.close()
