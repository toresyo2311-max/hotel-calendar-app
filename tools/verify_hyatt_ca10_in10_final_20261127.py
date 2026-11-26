#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""최종 검증 — 390×844 라이브(④ 하얏트 560곳) : 배지·제목·부제·달력·스페인 6곳 메모·콘솔·넘침."""
import os

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/'
       '?v=z226final&diag=1#tab=hyatt')
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

    badge = pg.eval_on_selector('button[data-tab="hyatt"] b', 'e=>e.textContent.trim()')
    title = pg.eval_on_selector('#sectionTitle', 'e=>e.textContent.trim()')
    sub = pg.eval_on_selector('#sectionSubtitle', 'e=>e.textContent.trim()')
    print('badge', badge)
    print('title', title)
    print('sub  ', sub)
    print('overflow(closed)', pg.evaluate('() => document.documentElement.scrollWidth - window.innerWidth'))
    pg.screenshot(path=os.path.join(OUT, '01_hyatt_tab_560_top.png'))

    def pick(name, slug):
        lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", name)
        if not lab:
            print('  MISSING', name)
            return
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1700)
        pg.evaluate("""() => {const s=document.querySelector('#hotelSelect');
            (s.closest('section,div.card,div.panel')||s).scrollIntoView({block:'start'}); window.scrollBy(0,-90);}""")
        pg.wait_for_timeout(700)
        pg.screenshot(path=os.path.join(OUT, slug + '_selector.png'))
        c = pg.query_selector('article.month-card')
        if c:
            c.scroll_into_view_if_needed()
            pg.wait_for_timeout(500)
            pg.evaluate('() => window.scrollBy(0,-70)')
            pg.wait_for_timeout(400)
            pg.screenshot(path=os.path.join(OUT, slug + '_cal.png'))
        info = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            if(!c) return null; const days=[...c.querySelectorAll('.cal-day')];
            const filled=days.map(d=>d.textContent.replace(/\\s+/g,' ').trim()).filter(t=>/만P|P/.test(t));
            return [days.length, filled.length, filled.slice(0,3)];}""")
        print('  %-28s %s' % (name, info))

    for nm, slug in (
            ('하얏트 플레이스 몬트리올 다운타운', '02_montreal_downtown'),
            ('하얏트 플레이스 몬트리올 에어포트', '03_montreal_airport'),
            ('하얏트 리젠시 나이아가라 폴스 폴스뷰', '04_niagara_fallsview'),
            ('호텔 X 토론토', '05_hotelx_toronto'),
            ('하얏트 리젠시 첸나이', '06_chennai_regency'),
            ('하얏트 리젠시 데라둔 리조트 앤 스파', '07_dehradun_resort'),
            ('하얏트 센트릭 화이트필드 벵갈루루', '08_whitefield_bengaluru'),
            ('하얏트 플레이스 하리드와르', '09_haridwar')):
        pick(nm, slug)

    # 스페인 1차 6곳 카드 메모
    lab = pg.evaluate("""() => {const o=[...document.querySelectorAll('#hotelSelect option')]
        .find(o=>o.textContent.includes('알루아 골프 트리니다드')); return o?o.textContent:''}""")
    if lab:
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1500)
    pg.evaluate("""() => {const d=document.querySelector('#hotelNotes'); if(d) d.open=true;}""")
    pg.wait_for_timeout(1000)
    r = pg.evaluate("""() => {const p=[...document.querySelectorAll('#hyattNotes p')]
        .find(p=>p.textContent.includes('알루아 골프 트리니다드'));
        if(!p) return null; p.id='esNoteTarget'; const b=p.getBoundingClientRect();
        return {top:b.top+window.scrollY, h:b.height, t:p.textContent};}""")
    if r:
        print('es note chars', len(r['t']), '| ** 없음', '**' not in r['t'],
              '| 미표출', '실제 어워드 재고 미표출' in r['t'], '| los=2', 'los=2' in r['t'])
        pg.evaluate("(y)=>window.scrollTo(0,y)", max(0, r['top'] - 60))
        pg.wait_for_timeout(800)
        pg.screenshot(path=os.path.join(OUT, '10_spain6_note.png'))
    # 새 20곳 메모 한 장
    r2 = pg.evaluate("""() => {const p=[...document.querySelectorAll('#hyattNotes p')]
        .find(p=>p.textContent.includes('하얏트 플레이스 몬트리올 다운타운'));
        if(!p) return null; const b=p.getBoundingClientRect(); return {top:b.top+window.scrollY};}""")
    if r2:
        pg.evaluate("(y)=>window.scrollTo(0,y)", max(0, r2['top'] - 60))
        pg.wait_for_timeout(700)
        pg.screenshot(path=os.path.join(OUT, '11_new_hotel_note.png'))
        print('new-hotel note shot OK')

    print('overflow(final)', pg.evaluate('() => document.documentElement.scrollWidth - window.innerWidth'))
    print('console errors:', [c for c in consoles if c[0] == 'error'])
    print('page errors:', errors)
    b.close()
