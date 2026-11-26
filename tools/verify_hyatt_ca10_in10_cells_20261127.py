#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 560곳 라이브 390×844 — 달력 칸 값 · 배지 · 제목 · 스크린샷 재확인."""
import os

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/'
       '?v=z226ca10in10b&diag=1#tab=hyatt')
OUT = '/workspace/downloads/hyatt_ca10_in10_2026-11-27'
os.makedirs(OUT, exist_ok=True)

errors, consoles = [], []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
    pg = ctx.new_page()
    pg.on('console', lambda m: consoles.append((m.type, m.text)))
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(URL, wait_until='load')
    pg.wait_for_timeout(3500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942')
        pg.click('#lockGo')
        pg.wait_for_timeout(2000)
    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2500)

    print('badge', pg.eval_on_selector('button[data-tab="hyatt"] b', 'e=>e.textContent.trim()'))

    struct = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
        if(!c) return 'no month-card';
        return {cls:c.className, heads:c.querySelectorAll('.cal-day').length,
                txt:c.textContent.replace(/\\s+/g,' ').slice(0,200)};}""")
    print('month-card', struct)

    def pick(name, shot):
        lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", name)
        if not lab:
            print('  MISSING', name)
            return
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1800)
        info = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            if(!c) return null;
            const days=[...c.querySelectorAll('.cal-day')];
            const filled=days.map(d=>d.textContent.replace(/\\s+/g,' ').trim()).filter(t=>/P|만/.test(t));
            return {n:days.length, filled:filled.length, sample:filled.slice(0,6)};}""")
        print('  %-26s %s' % (name, info))
        c = pg.query_selector('article.month-card')
        if c:
            c.scroll_into_view_if_needed()
            pg.wait_for_timeout(700)
            c.screenshot(path=os.path.join(OUT, shot))

    pick('하얏트 플레이스 몬트리올 다운타운', '02_montreal_downtown_cal.png')
    pick('하얏트 플레이스 몬트리올 에어포트', '03_montreal_airport_cal.png')
    pick('호텔 X 토론토', '04_hotelx_toronto_cal.png')
    pick('하얏트 리젠시 첸나이', '05_chennai_regency_cal.png')
    pick('하얏트 리젠시 데라둔 리조트 앤 스파', '06_dehradun_resort_cal.png')
    pick('하얏트 센트릭 화이트필드 벵갈루루', '07_whitefield_cal.png')
    pick('하얏트 리젠시 나이아가라 폴스 폴스뷰', '10_niagara_fallsview_cal.png')
    pick('하얏트 플레이스 하리드와르', '11_haridwar_cal.png')

    ov = pg.evaluate('() => document.documentElement.scrollWidth - window.innerWidth')
    print('overflow px =', ov)
    print('console errors:', [c for c in consoles if c[0] == 'error'])
    print('page errors:', errors)
    b.close()
