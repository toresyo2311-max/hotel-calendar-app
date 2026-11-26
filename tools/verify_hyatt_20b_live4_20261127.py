#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 — 날짜 칸 클릭 동작 상세 확인(무엇이 열리는가 · 공홈 URL)."""
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b4&diag=1#tab=hyatt'

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    ctx = b.new_context(viewport={'width': 390, 'height': 844})
    pg = ctx.new_page()
    errs = []
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until='load')
    pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942')
        pg.click('#lockGo')
        pg.wait_for_timeout(1500)
    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2500)
    lab = pg.evaluate("""() => {const o=[...document.querySelectorAll('#hotelSelect option')]
        .find(o=>o.textContent.includes('안다즈 도하')); return o?o.textContent:''}""")
    pg.select_option('#hotelSelect', label=lab)
    pg.wait_for_timeout(1800)
    print('cell html', pg.evaluate("""() => {const c=document.querySelector('article.month-card');
        const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/P/.test(x.textContent));
        return cells[4].outerHTML.slice(0,300);}"""))
    pg.evaluate("""() => {const c=document.querySelector('article.month-card');
        const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/P/.test(x.textContent));
        cells[4].click();}""")
    pg.wait_for_timeout(1500)
    print('visible overlays:', pg.evaluate("""() => [...document.querySelectorAll('body *')]
        .filter(e=>e.id && e.offsetParent && /sheet|Sheet|modal|Modal|dayinfo|detail/i.test(e.id))
        .map(e=>e.id+':'+e.className).slice(0,10)"""))
    print('nav state:', pg.evaluate("""() => ({hash: location.hash, href: location.href})"""))
    print('any hyatt href:', pg.evaluate("""() => [...new Set([...document.querySelectorAll('[href*="hyatt.com"]')].map(a=>a.getAttribute('href')))]"""))
    print('body tail text:', pg.evaluate("""() => document.body.innerText.replace(/\\s+/g,' ').slice(-700)"""))
    print('console errors', len(errs), errs[:3])
    b.close()
