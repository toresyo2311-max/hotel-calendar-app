#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미참여 카드 · 기준(basis) 🆕 줄 · 주의문 캡처(모달 닫은 상태)."""
import os, time
from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z220hyatt20b6&diag=1#tab=hyatt'
OUT = '/workspace/downloads/hyatt_20b_2026-11-27'
ST = time.strftime('%Y-%m-%d-%H%M%S')


def w(pg, name):
    path = os.path.join(OUT, '%s-%s.png' % (name, ST))
    pg.screenshot(path=path)
    s = pg.evaluate('[innerWidth, document.documentElement.scrollWidth, document.body.scrollWidth]')
    print('%-44s %s overflow=%d' % (name, s, max(s[1], s[2]) - s[0]), path)


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
    pg.click('button[data-tab="hyatt"]'); pg.wait_for_timeout(2500)

    for nm, tag in (('하얏트 플레이스 비자야와다', 'vgazv'), ('바이아 프린시페 이스케이프 코랄 플라야', 'bp023')):
        lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", nm)
        pg.select_option('#hotelSelect', label=lab); pg.wait_for_timeout(1600)
        # 모달이 열려 있으면 닫기
        pg.evaluate("""() => {document.querySelectorAll('#modalClose,[data-close]').forEach(b=>b.click());
            document.body.click();}""")
        pg.wait_for_timeout(400)
        pg.evaluate("() => {const el=document.querySelector('article.month-card'); if(el) window.scrollTo(0, el.getBoundingClientRect().top+scrollY-190)}")
        pg.wait_for_timeout(500)
        w(pg, '09_390px_hyatt_%s_card' % tag)

    # 기준(basis)
    pg.evaluate("() => {const b=document.querySelector('#basis'); window.scrollTo(0, b.getBoundingClientRect().top+scrollY-90)}")
    pg.wait_for_timeout(500)
    w(pg, '10_390px_hyatt_basis')
    # 주의문 펼침
    try:
        pg.evaluate("""() => {const c=document.querySelector('#caution');
            const d=c && c.closest('details'); if(d) d.open=true;}""")
        pg.evaluate("() => {const c=document.querySelector('#caution'); window.scrollTo(0, c.getBoundingClientRect().top+scrollY-90)}")
        pg.wait_for_timeout(600)
        w(pg, '11_390px_hyatt_caution')
    except Exception as e:
        print('caution skip', e)
    print('console errors', len(errs), errs[:3])
    b.close()
