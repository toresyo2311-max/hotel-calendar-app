#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP 탭 HoteLux 실측 병합 — h16~h20 (2026-11-20, 5번(@jin_5) 전달분 2차).

반영 내용
  · h16 월도프 아스토리아 방콕 — 2027-04-04~04-11 8일 추가(1차 124일 → 132일,
    2026-12-01~2027-04-11 전수). 2027-04-12 이후는 미실측이라 null 유지.
  · h17 만다린 오리엔탈 방콕 · h18 카펠라 방콕 · h19 하얏트 리젠시 다낭 ·
    h20 인터컨티넨탈 다낭 선 페닐슐라 — 실측 대기(0칸)에서 365칸으로.
    2026-12-01~2027-03-31 실측(요금 없음은 null), 2027-04-01~11-30 은 미실측 null.

값은 고치기만 하고 counts·배포본은 건드리지 않는다 —
이어서 `python3 tools/master_db.py refresh && python3 tools/master_db.py inject`.
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC_IN = ('/workspace/memory/clones/f0ee2d96-jin_5/pickle/2026-11-20-1328/received/'
          '0-2026-11-20-vip-hotelux-h16-h20.json')

USD_KRW = 1331.56
WIN_START = '2026-12-01'
WIN_END = '2027-11-30'

HEAD = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 5번(@jin_5) 전달분. '
        '예약 사이트 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 '
        'approximate.sumReservation USD 총액) ')
TAIL = ' 앱 고정 환율 USD 1 = ₩1,331.56 로 환산.'
FEE_NOTE = ('객실 목록이 다 불러온 뒤 값이 안정될 때까지 확인했고(h18은 요금 필터 병합 완료까지 '
            '추가 확인), 요금 없는 날(객실 목록 0건)은 빈칸으로 두고 추정·보간하지 않았습니다.')

SRC = {
    'h16': (HEAD + '2026-12-01~2027-04-11 132일 전수(1차 124일에 2027-04-04~04-11 8일 추가).' + TAIL +
            ' 2027-04-12~11-30 233일은 미실측이라 빈칸입니다. ' + FEE_NOTE),
    'h17': (HEAD + '2026-12-01~2027-03-31 121일 중 요금 118일.' + TAIL +
            ' 요금 없음 3일(2026-12-29~12-31)·미실측 2027-04-01~11-30 244일은 빈칸입니다. ' + FEE_NOTE),
    'h18': (HEAD + '2026-12-01~2027-03-31 121일 중 요금 115일.' + TAIL +
            ' 요금 없음 6일(2026-12-29~12-31 · 2027-01-01 · 02-09 · 03-03)·'
            '미실측 2027-04-01~11-30 244일은 빈칸입니다. ' + FEE_NOTE),
    'h19': (HEAD + '2026-12-01~2027-03-31 121일 전수(요금 없음 0일).' + TAIL +
            ' 2026-12-01은 1차 조회에서 일시적으로 객실 목록 0건이었으나 재조회에서 156.13이 '
            '확인되어 재조회값을 실었습니다. 미실측 2027-04-01~11-30 244일은 빈칸입니다. ' + FEE_NOTE),
    'h20': (HEAD + '2026-12-01~2027-03-31 121일 중 요금 97일.' + TAIL +
            ' 요금 없음 24일(2026-12-23~2027-01-02 · 2027-02-05~02-11 · 03-26~03-31)은 1박 '
            '조회에서 판매 불가였고, 인접 판매일을 같은 세션에서 다시 재어 사이트가 정상 요금을 '
            '내는 것을 확인했습니다. 미실측 2027-04-01~11-30 244일은 빈칸입니다. '
            '2027-03-23만 USD 6,140.21(약 817만원)로 튀는데, 그날 조회된 객실 중 최저가가 그 '
            '값이었습니다(앞뒤 날짜는 USD 1,100 수준) — 보정하지 않고 그대로 실었습니다. ' + FEE_NOTE),
}

EXT_ADD = (' / 2026-11-20 ① VIP 예약 사이트 실측 병합(2차) — h16 방콕 2027-04-04~04-11 8일 추가로 '
           '2026-12-01~2027-04-11 132일 · h17 만다린 오리엔탈 방콕·h18 카펠라 방콕·'
           'h19 하얏트 리젠시 다낭·h20 인터컨티넨탈 다낭 4곳 2026-12-01~2027-03-31 실측'
           '(365칸 · 이후 미실측 null), 요금 전무 호텔 0곳(5번 전달, USD→₩ 1,331.56)')
SRC_FILES = ['VIP 예약 사이트 실측 2026-11-20 — h16~h20 (5번 전달, h16 132일 · h17~h20 121일)']


def load(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def days_of(a, b):
    d, out = dt.date.fromisoformat(a), []
    while d <= dt.date.fromisoformat(b):
        out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def main():
    master = load(MASTER)
    data = load(SRC_IN)['hotels']
    byid = {h['id']: h for h in master['hotels']}
    report = []

    # --- h16: 기존 365칸에 실측분만 채우고 나머지는 비운다
    tgt = byid['h16']
    before = dict(tgt['rates'])
    daily = {x['date']: x.get('usd') for x in data['h16']['daily']}
    rates, added, lost = {}, 0, []
    for day in days_of(WIN_START, WIN_END):
        usd = daily.get(day)
        if usd is None:
            rates[day] = None
            if before.get(day):
                lost.append(day)
            continue
        rates[day] = int(round(usd * USD_KRW))
        if not before.get(day):
            added += 1
    tgt['rates'] = rates
    tgt['source'] = SRC['h16']
    report.append('h16 %d일(%d → %d) 추가 %d · 잃은 값 %d' % (
        sum(1 for v in rates.values() if v), sum(1 for v in before.values() if v),
        sum(1 for v in rates.values() if v), added, len(lost)))
    if lost:
        report.append('  h16 값이 사라진 날: %s' % ', '.join(lost[:10]))

    # --- h17~h20: 365칸 신규
    for hid in ('h17', 'h18', 'h19', 'h20'):
        tgt = byid[hid]
        if not tgt:
            sys.exit('호텔 없음: %s' % hid)
        daily = {x['date']: x.get('usd') for x in data[hid]['daily']}
        rates = {}
        for day in days_of(WIN_START, WIN_END):
            usd = daily.get(day)
            rates[day] = int(round(usd * USD_KRW)) if isinstance(usd, (int, float)) else None
        vals = [v for v in rates.values() if v]
        low = min(vals)
        lowday = [d for d, v in rates.items() if v == low][0]
        tgt['rates'] = rates
        tgt['source'] = SRC[hid]
        report.append('%s %d칸/값 %d · 최저 %s원(%s) · 최고 %s원' % (
            hid, len(rates), len(vals), f'{low:,}', lowday, f'{max(vals):,}'))

    if EXT_ADD not in master['extended']:
        master['extended'] = master['extended'] + EXT_ADD
    for s in SRC_FILES:
        if s not in master['sources']:
            master['sources'].append(s)

    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
    for line in report:
        print(line)


if __name__ == '__main__':
    main()
