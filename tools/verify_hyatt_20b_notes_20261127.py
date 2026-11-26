#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""새 20곳 메모가 펼친 목록에서 가로 넘침을 만드는지 확인."""
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b8&diag=1#tab=hyatt'

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    pg.goto(URL, wait_until='load'); pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942'); pg.click('#lockGo'); pg.wait_for_timeout(1500)
    pg.click('button[data-tab="hyatt"]'); pg.wait_for_timeout(2500)
    # 메모 목록 details 열기
    print('notes details:', pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .filter(d=>d.textContent.includes('카테고리 · 특이사항')); if(!d.length) return 'none';
        d[0].open=true; return d[0].textContent.slice(0,40);}"""))
    pg.wait_for_timeout(700)
    for code_label, nm in (('전체(485)', None), ('안다즈 도하', '안다즈 도하'), ('비자야와다', '하얏트 플레이스 비자야와다')):
        if nm:
            lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
                .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", nm)
            pg.select_option('#hotelSelect', label=lab); pg.wait_for_timeout(1200)
        w = pg.evaluate('[innerWidth, document.documentElement.scrollWidth]')
        print(code_label, w, 'overflow', w[1]-w[0])
        if nm:
            print('  widest:', pg.evaluate("""() => [...document.querySelectorAll('#hyattNotes *')]
                .map(e=>Math.round(e.getBoundingClientRect().right)).sort((a,b)=>b-a).slice(0,3)"""))
    b.close()
