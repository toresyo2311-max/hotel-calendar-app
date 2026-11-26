#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 캐나다 2차 10 · 인도 2차 10 = 20곳 병합(540→560) + 스페인 1차 6곳 사유 정정
— 배포된 라이브 URL 390×844 모바일 검증 + 스크린샷."""
import os

from playwright.sync_api import sync_playwright

EXE = ('/workspace/.cache/ms-playwright/chromium_headless_shell-1255/'
       'chrome-headless-shell-linux64/chrome-headless-shell')
URL = ('https://toresyo2311-max.github.io/hotel-calendar-app/'
       '?v=z226ca10in10&diag=1#tab=hyatt')
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
        print('lock: unlocked')

    pg.click('button[data-tab="hyatt"]')
    pg.wait_for_timeout(3000)

    badge = pg.eval_on_selector('button[data-tab="hyatt"] b', 'e=>e.textContent.trim()')
    aria = pg.eval_on_selector('button[data-tab="hyatt"]', 'e=>e.getAttribute("aria-label")')
    title = pg.eval_on_selector('#sectionTitle', 'e=>e.textContent.trim()')
    print('badge =', badge)
    print('aria  =', aria)
    print('title =', title)

    ov = pg.evaluate('() => document.documentElement.scrollWidth - window.innerWidth')
    print('overflow px =', ov)

    pg.screenshot(path=os.path.join(OUT, '01_hyatt_tab_560_top.png'))

    # 부제 · 기준 · 주의 펼침 상태 확인
    sub = pg.eval_on_selector('#sectionSubtitle', 'e=>e.textContent.trim()')
    print('sub   =', sub[:220])
    txt = pg.evaluate('() => document.body.textContent')
    for probe in ('남아시아 35', '캐나다 30', '560곳', '캐나다 2차 10 · 인도 2차 10 = 20곳',
                  '실제 어워드 재고 미표출', '7,300칸 가운데 6,976칸'):
        print('probe %-32s %s' % (probe, 'OK' if probe in txt else 'MISSING'))

    # 새 호텔 달력 — 호텔 선택
    def pick(name, shot, expect_nums):
        lab = pg.evaluate("""(nm) => {const o=[...document.querySelectorAll('#hotelSelect option')]
            .find(o=>o.textContent.includes(nm)); return o?o.textContent:''}""", name)
        if not lab:
            print('  MISSING hotel option:', name)
            return
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1800)
        got = pg.evaluate("""() => {const c=document.querySelector('article.month-card');
            return c ? c.textContent.replace(/\\s+/g,' ') : ''}""")
        pg.screenshot(path=os.path.join(OUT, shot))
        print('  %-28s option=%s | month card %d자 | 값 표본 %s'
              % (name, lab[:42], len(got), ''.join('1' if n in got else '0' for n in expect_nums)))

    pick('하얏트 플레이스 몬트리올 다운타운', '02_montreal_downtown_cal.png', ['12,000', '15,000'])
    pick('하얏트 플레이스 몬트리올 에어포트', '03_montreal_airport_cal.png', ['8,000', '12,000'])
    pick('호텔 X 토론토', '04_hotelx_toronto_cal.png', ['15,000', '25,000'])
    pick('하얏트 리젠시 첸나이', '05_chennai_regency_cal.png', ['4,500', '6,000'])
    pick('하얏트 리젠시 데라둔 리조트 앤 스파', '06_dehradun_resort_cal.png', ['12,000', '15,000'])
    pick('하얏트 센트릭 화이트필드 벵갈루루', '07_whitefield_cal.png', ['7,500', '10,000'])

    # 스페인 1차 6곳 — 카드 메모(특이사항) 펼쳐 확인
    lab = pg.evaluate("""() => {const o=[...document.querySelectorAll('#hotelSelect option')]
        .find(o=>o.textContent.includes('알루아 골프 트리니다드')); return o?o.textContent:''}""")
    if lab:
        pg.select_option('#hotelSelect', label=lab)
        pg.wait_for_timeout(1500)
    pg.evaluate("""() => {const d=[...document.querySelectorAll('details')]
        .find(d=>d.querySelector('summary')&&d.querySelector('summary').textContent.includes('호텔별 카테고리'));
        if(d){d.open=true; d.scrollIntoView({block:'start'});}}""")
    pg.wait_for_timeout(900)
    note_ok = pg.evaluate("""() => {const t=document.querySelector('#hyattNotes');
        if(!t) return '';
        const p=[...t.querySelectorAll('p')].find(p=>p.textContent.includes('알루아 골프 트리니다드'));
        return p?p.textContent:''}""")
    print('spain note contains 실제 어워드 재고 미표출:', '실제 어워드 재고 미표출' in note_ok,
          '| los=2:', 'los=2' in note_ok, '| chars', len(note_ok))
    if note_ok:
        pg.evaluate("""() => {const p=[...document.querySelectorAll('#hyattNotes p')]
            .find(p=>p.textContent.includes('알루아 골프 트리니다드'));
            if(p) p.scrollIntoView({block:'center'});}""")
        pg.wait_for_timeout(600)
    pg.screenshot(path=os.path.join(OUT, '08_spain6_note_recheck.png'))

    # 캐나다 30 · 남아시아 35 지역 라벨/필터 확인
    pg.screenshot(path=os.path.join(OUT, '09_after_note_overflow.png'))
    ov2 = pg.evaluate('() => document.documentElement.scrollWidth - window.innerWidth')
    print('overflow px (after) =', ov2)

    print('console errors:', [c for c in consoles if c[0] == 'error'])
    print('page errors:', errors)
    b.close()

print('screenshots ->', OUT, sorted(os.listdir(OUT)))
