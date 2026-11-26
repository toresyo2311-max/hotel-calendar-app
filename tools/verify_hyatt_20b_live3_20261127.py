#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""390×844 — 날짜 칸 클릭 시 새 탭으로 열리는 공홈 URL 확인(단일 링크 호텔)."""
import time
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b3&diag=1#tab=hyatt'

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
    for nm, code in (('안다즈 도하', 'dohaz'), ('하얏트 라이푸르', 'rprhy'),
                     ('하얏트 리젠시 마드리드 레지던스', 'madra')):
        lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", nm)
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1600)
        try:
            with ctx.expect_page(timeout=8000) as pi:
                ok = pg.evaluate("""() => {const c=document.querySelector('article.month-card'); if(!c) return false;
                    const cells=[...c.querySelectorAll('.cal-day')].filter(x=>/P/.test(x.textContent));
                    if(!cells.length) return false; cells[4].click(); return cells[4].textContent.trim();}""")
            newp = pi.value
            print('%-22s cell=%-8s -> %s' % (nm, ok, newp.url))
            newp.close()
        except Exception as e:                            # noqa: BLE001
            print('%-22s no popup: %s' % (nm, str(e)[:120]))
    print('console errors', len(errs), errs[:3])
    b.close()
