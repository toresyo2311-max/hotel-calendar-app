#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 560곳 라이브 390×844 — 호텔 선택 + 달력 + 스페인 6곳 메모 스크린샷."""
import os

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/'
       '?v=z226ca10in10c&diag=1#tab=hyatt')
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

    def pick(name, slug):
        lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", name)
        if not lab:
            print('  MISSING', name)
            return
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1800)
        # 호텔 선택 상자 + 달력 머리글이 함께 보이게 스크롤
        pg.evaluate("""() => {const s=document.querySelector('#hotelSelect');
            const box=s.closest('section,div.card,div.panel')||s;
            box.scrollIntoView({block:'start'}); window.scrollBy(0,-90);}""")
        pg.wait_for_timeout(700)
        pg.screenshot(path=os.path.join(OUT, slug + '_selector.png'))
        c = pg.query_selector('article.month-card')
        if c:
            c.scroll_into_view_if_needed()
            pg.wait_for_timeout(500)
            pg.evaluate('() => window.scrollBy(0,-70)')
            pg.wait_for_timeout(400)
            pg.screenshot(path=os.path.join(OUT, slug + '_cal.png'))
        vals = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            if(!c) return null; const t=c.textContent.replace(/\\s+/g,' ').trim();
            return t.slice(0,160);}""")
        print('  %-26s %s' % (name, vals))

    for nm, slug in (
            ('하얏트 플레이스 몬트리올 다운타운', '02_montreal_downtown'),
            ('하얏트 플레이스 몬트리올 에어포트', '03_montreal_airport'),
            ('호텔 X 토론토', '04_hotelx_toronto'),
            ('하얏트 리젠시 첸나이', '05_chennai_regency'),
            ('하얏트 리젠시 데라둔 리조트 앤 스파', '06_dehradun_resort'),
            ('하얏트 센트릭 화이트필드 벵갈루루', '07_whitefield_bengaluru'),
            ('하얏트 리젠시 나이아가라 폴스 폴스뷰', '08_niagara_fallsview'),
            ('하얏트 플레이스 하리드와르', '09_haridwar')):
        pick(nm, slug)

    # 스페인 1차 6곳 — 카드 메모(특이사항) 펼쳐 화면에 담기
    lab = pg.evaluate("""() => {const o=[...document.querySelectorAll('#hotelSelect option')]
        .find(o=>o.textContent.includes('알루아 골프 트리니다드')); return o?o.textContent:''}""")
    if lab:
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1600)
    pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .find(d=>d.querySelector('summary')&&d.querySelector('summary').textContent.includes('호텔별 카테고리'));
        if(d){d.open=true;}}""")
    pg.wait_for_timeout(800)
    note = pg.evaluate("""() => {const t=document.querySelector('#hyattNotes');
        if(!t) return '';
        const p=[...t.querySelectorAll('p')].find(p=>p.textContent.includes('알루아 골프 트리니다드'));
        return p?p.textContent:''}""")
    print('spain note chars', len(note), '| 미표출 문구', '실제 어워드 재고 미표출' in note)
    if note:
        pg.evaluate("""() => {const p=[...document.querySelectorAll('#hyattNotes p')]
            .find(p=>p.textContent.includes('알루아 골프 트리니다드'));
            if(p){p.id='esNoteTarget'; p.scrollIntoView({block:'start'});} }""")
        pg.wait_for_timeout(700)
        pg.screenshot(path=os.path.join(OUT, '10_spain6_note_viewport.png'))
        t = pg.query_selector('#esNoteTarget')
        if t:
            t.screenshot(path=os.path.join(OUT, '10b_spain6_note_card.png'))

    ov = pg.evaluate('() => document.documentElement.scrollWidth - window.innerWidth')
    print('overflow px =', ov)
    print('console errors:', [c for c in consoles if c[0] == 'error'])
    print('page errors:', errors)
    b.close()

print(sorted(os.listdir(OUT)))
