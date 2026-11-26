#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스페인 1차 6곳 사유 정정 화면 증거 — 주의(caution) 항목 + 카드 메모를 펼쳐 캡처."""
import os

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/'
       '?v=z226ca10in10d&diag=1#tab=hyatt')
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

    # 1) 주의(caution) 목록의 스페인 6곳 항목
    found = pg.evaluate("""() => {const lis=[...document.querySelectorAll('#caution li')];
        const li=lis.find(x=>x.textContent.includes('성인2·2박(numAdults=2'));
        if(!li) return null; li.id='esCautionTarget'; return li.textContent.length;}""")
    print('caution li chars', found)
    if found:
        pg.evaluate("""() => {const li=document.querySelector('#esCautionTarget');
            li.scrollIntoView({block:'start'}); window.scrollBy(0,-60);}""")
        pg.wait_for_timeout(700)
        pg.screenshot(path=os.path.join(OUT, '11_spain6_caution.png'))
        li = pg.query_selector('#esCautionTarget')
        li.screenshot(path=os.path.join(OUT, '11b_spain6_caution_item.png'))

    # 2) 카드 메모(호텔별 특이사항) — details 열고 해당 p 캡처
    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(1200)
    pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .find(d=>d.querySelector('summary')&&d.querySelector('summary').textContent.includes('호텔별 카테고리'));
        if(d){if(!d.open){d.querySelector('summary').click();}}}""")
    pg.wait_for_timeout(1200)
    n = pg.evaluate("""() => {const t=document.querySelector('#hyattNotes'); if(!t) return -1;
        const p=[...t.querySelectorAll('p')].find(p=>p.textContent.includes('알루아 골프 트리니다드'));
        if(!p) return 0; p.id='esNoteTarget'; return p.textContent.length;}""")
    print('note p chars', n)
    if n and n > 0:
        pg.evaluate("""() => {const p=document.querySelector('#esNoteTarget');
            p.scrollIntoView({block:'start'}); window.scrollBy(0,-60);}""")
        pg.wait_for_timeout(800)
        pg.screenshot(path=os.path.join(OUT, '12_spain6_note.png'))
        txt = pg.evaluate("() => document.querySelector('#esNoteTarget').textContent")
        print('note has 미표출:', '실제 어워드 재고 미표출' in txt, '| los=2:', 'los=2' in txt)
    b.close()
print(sorted(os.listdir(OUT)))
