#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""<details> 를 닫으면 넘침이 사라지는지 · 도쿄(기존 지점)에서도 같은지."""
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20ba&diag=1#tab=hyatt'

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    pg.goto(URL, wait_until='load'); pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942'); pg.click('#lockGo'); pg.wait_for_timeout(1500)
    pg.click('button[data-tab="hyatt"]'); pg.wait_for_timeout(2500)
    pg.select_option('#citySelect', label='도쿄'); pg.wait_for_timeout(1500)
    print('도쿄 closed', pg.evaluate('[390, document.documentElement.scrollWidth]'))
    pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .filter(d=>d.textContent.includes('카테고리 · 특이사항')); if(d.length) d[0].open=true;}""")
    pg.wait_for_timeout(700)
    print('도쿄 open  ', pg.evaluate('[390, document.documentElement.scrollWidth]'))
    pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .filter(d=>d.textContent.includes('카테고리 · 특이사항')); if(d.length) d[0].open=false;}""")
    pg.wait_for_timeout(500)
    print('도쿄 closed again', pg.evaluate('[390, document.documentElement.scrollWidth]'))
    print('month strip overflow-x:', pg.evaluate("""() => {const btns=[...document.querySelectorAll('button')]
        .filter(b=>/^\\d+월$/.test(b.textContent.trim())); if(!btns.length) return 'none';
        let e=btns[0].parentElement, out=[];
        for(let i=0;i<4 && e;i++,e=e.parentElement){const cs=getComputedStyle(e);
            out.push(e.tagName+'.'+(e.className||'').toString().slice(0,20)+' ox='+cs.overflowX+' w='+Math.round(e.getBoundingClientRect().width));}
        return out;}"""))
    b.close()
