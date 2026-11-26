#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스페인 1차 6곳 사유 정정 + 이번 20곳 기준 행 화면 증거(390×844)."""
import os

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/'
       '?v=z226ca10in10e&diag=1#tab=hyatt')
OUT = '/workspace/downloads/hyatt_ca10_in10_2026-11-27'

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
    pg = ctx.new_page()
    pg.goto(URL, wait_until='load')
    pg.wait_for_timeout(3500)
    el = pg.query_selector('#lockPin')
    if el and el.is_visible():
        pg.fill('#lockPin', '7942')
        pg.click('#lockGo')
        pg.wait_for_timeout(2000)
    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(2500)

    # 기준(📊) fold 펼치기
    pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .find(d=>d.querySelector('summary')&&d.querySelector('summary').textContent.includes('1,040곳'));
        if(d) d.open=true;}""")
    pg.wait_for_timeout(900)

    def shot_row(probe, el_id, fname):
        r = pg.evaluate("""([probe,idn]) => {const rows=[...document.querySelectorAll('#basis .note-row')];
            const a=rows.find(x=>x.textContent.includes(probe));
            if(!a) return null; a.id=idn; const r=a.getBoundingClientRect();
            return {top:r.top+window.scrollY, h:r.height};}""", [probe, el_id])
        if not r:
            print('  row not found:', probe[:30])
            return
        pg.evaluate("(y) => window.scrollTo(0, y)", max(0, r['top'] - 70))
        pg.wait_for_timeout(800)
        pg.screenshot(path=os.path.join(OUT, fname))
        print('  saved %s (row top %.0f h %.0f)' % (fname, r['top'], r['h']))

    shot_row('캐나다 2차 10 · 인도 2차 10 = 20곳', 'row20', '13_basis_row_20places.png')
    shot_row('성인2·2박(numAdults=2', 'rowEs', '14_basis_row_spain6.png')

    # 카드 메모(호텔별 특이사항) — 스페인 알루아 골프 트리니다드
    lab = pg.evaluate("""() => {const o=[...document.querySelectorAll('#hotelSelect option')]
        .find(o=>o.textContent.includes('알루아 골프 트리니다드')); return o?o.textContent:''}""")
    if lab:
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1600)
    pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .find(d=>d.querySelector('summary')&&d.querySelector('summary').textContent.includes('호텔별 카테고리'));
        if(d) d.open=true;}""")
    pg.wait_for_timeout(1000)
    r = pg.evaluate("""() => {const t=document.querySelector('#hyattNotes'); if(!t) return null;
        const p=[...t.querySelectorAll('p')].find(p=>p.textContent.includes('알루아 골프 트리니다드'));
        if(!p) return null; p.id='esNoteTarget'; const r=p.getBoundingClientRect();
        return {top:r.top+window.scrollY, h:r.height, chars:p.textContent.length};}""")
    print('es note', r)
    if r:
        pg.evaluate("(y) => window.scrollTo(0, y)", max(0, r['top'] - 70))
        pg.wait_for_timeout(800)
        pg.screenshot(path=os.path.join(OUT, '12_spain6_note.png'))
    print('overflow', pg.evaluate('() => document.documentElement.scrollWidth - window.innerWidth'))
    b.close()
