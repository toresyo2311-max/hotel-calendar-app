#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""라이브 달력 칸 대조 — 새 21곳 중 8곳의 2026년 12월 칸을 tab10_hyatt.json 과 1칸씩 맞춰 본다."""
import datetime
import json

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = 'https://toresyo2311-max.github.io/hotel-calendar-app/?v=z232sa21t&diag=1#tab=hyatt'
DATA = json.load(open('/workspace/work/hyatt_sa21_20261127/data/app/tab10_hyatt.json'))
BYID = {h['id']: h for h in DATA['hotels']}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    pg.goto(URL, wait_until='load')
    pg.wait_for_timeout(2500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942')
        pg.click('#lockGo')
        pg.wait_for_timeout(1200)
    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2000)
    total_bad = 0
    for hid in ['hy593', 'hy598', 'hy601', 'hy607', 'hy608', 'hy609', 'hy611', 'hy613']:
        pg.select_option('#hotelSelect', value=hid)
        pg.wait_for_timeout(1500)
        got = pg.evaluate("""() => {const c=[...document.querySelectorAll('article.month-card')][0];
            const o={}; c.querySelectorAll('button.cal-day[data-date]').forEach(x=>{
              o[x.getAttribute('data-date')]=x.innerText.replace(/\\s+/g,'|').trim();});
            return o;}""")
        h = BYID[hid]
        pts = h['points']['$v']
        base = datetime.date.fromisoformat(h['points']['$d'])
        bad = []
        for i, v in enumerate(pts[:31]):
            d = (base + datetime.timedelta(days=i)).isoformat()
            txt = got.get(d, '')
            if v is None:
                ok = ('만P' not in txt)
            else:
                ok = ('%.1f만P' % (v / 10000)) in txt
            if not ok:
                bad.append((d, txt, v))
        total_bad += len(bad)
        print('%-6s %-34s dec칸 %2d · 불일치 %d %s' % (hid, h['name'], len(got), len(bad), bad[:3]))
    print('TOTAL mismatch', total_bad)
    b.close()
