#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP 탭 예약 사이트 실측 병합 — h19 하얏트 리젠시 다낭 365일 완결분
(2026-11-21, 5번(@jin_5) 전달분 5차).

반영 내용
  · h19 하얏트 리젠시 다낭 리조트 앤 스파 — 2026-12-01~2027-11-30 365칸 완결.
    요금 322일 · 요금 없음 43일(2027-10-19~11-30 = 예약 오픈 호라이즌 밖).
    이미 값이 있던 121일(2026-12-01~2027-03-31)은 그대로 두고
    2027-04-01~2027-10-18 201칸을 채운다(요금 없음 43칸은 null 유지).
  · h16·h17·h18 은 이미 365일 완결, h20 인터컨티넨탈 다낭은 121일 실측분 유지 —
    모두 한 칸도 건드리지 않는다(2027-04-01~11-30 244일은 미실측 null 그대로).

겹친 구간(2026-12-01~2027-03-31 121일)의 값이 기존 master_db.json 과 한 칸도 다르지
않음을 먼저 확인하고, 다르면 중단한다.

값은 고치기만 하고 counts·배포본은 건드리지 않는다 —
이어서 `python3 tools/master_db.py refresh && python3 tools/master_db.py inject`.
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC_IN = ('/workspace/memory/clones/f0ee2d96-jin_5/pickle/2026-11-21-1256/received/'
          '0-2026-11-20-vip-hotelux-h16-h20.json')

USD_KRW = 1331.56
WIN_START = '2026-12-01'
WIN_END = '2027-11-30'

HEAD = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-21 KST 5번(@jin_5) 전달분. '
        '예약 사이트 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 '
        'approximate.sumReservation USD 총액) ')
TAIL = ' 앱 고정 환율 USD 1 = ₩1,331.56 로 환산.'
FEE_NOTE = ('객실 목록이 다 불러온 뒤 값이 안정될 때까지 확인했고, 요금 없는 날'
            '(객실 목록 0건)은 빈칸으로 두고 추정·보간하지 않았습니다.')

SRC = {
    'h19': (HEAD + '2026-12-01~2027-11-30 365일 전수(요금 322일).' + TAIL +
            ' 요금 없음 43일(2027-10-19~11-30, 사이트가 1박 판매를 열지 않은 예약 오픈 '
            '호라이즌 밖 구간)은 빈칸입니다. 겹친 2026-12-01~2027-03-31 121일은 기존 값과 '
            '전부 같았고 2027-04-01~2027-10-18 201일을 새로 채웠습니다. ' + FEE_NOTE),
}

EXT_ADD = (' / 2026-11-21 KST ① VIP 예약 사이트 실측 병합(5차) — h19 하얏트 리젠시 다낭 '
           '2026-12-01~2027-11-30 365일 완결(요금 322일·판매 없음 43일, '
           '2027-04-01~10-18 신규 201칸 · 방콕 3곳 + 하얏트 리젠시 다낭 4곳 모두 365일 완결, '
           '인터컨티넨탈 다낭 1곳만 2027-03-31까지)(5번 전달, USD→₩ 1,331.56)')
SRC_FILES = ['VIP 예약 사이트 실측 2026-11-21 — h19 하얏트 리젠시 다낭 365일 완결 (5번 전달)']


def load(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def days_of(a, b):
    d, out = dt.date.fromisoformat(a), []
    while d <= dt.date.fromisoformat(b):
        out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def to_krw(usd):
    return int(round(usd * USD_KRW)) if isinstance(usd, (int, float)) else None


def main():
    master = load(MASTER)
    data = load(SRC_IN)['hotels']
    byid = {h['id']: h for h in master['hotels']}
    report = []

    untouched = {hid: json.dumps(byid[hid]['rates'], sort_keys=True)
                 for hid in ('h16', 'h17', 'h18', 'h20')}

    # --- 이미 값이 있던 칸이 하나라도 달라지거나 사라지면 멈춘다
    exist = byid['h19']['rates']
    bad, lost, refilled = [], [], []
    for row in data['h19']['daily']:
        day, new = row['date'], to_krw(row.get('usd'))
        old = exist.get(day)
        if old is not None and new is not None and old != new:
            bad.append((day, old, new))
        elif old is not None and new is None:
            lost.append((day, old))
        elif old is None and new is not None and day in exist:
            refilled.append(day)
    if bad:
        sys.exit('h19 기존 값과 다른 칸 %d개 — %s' % (len(bad), bad[:5]))
    if lost:
        sys.exit('h19 값이 사라지는 칸 %d개 — %s' % (len(lost), lost[:5]))
    report.append('h19 기존 값 %d칸 모두 일치(변경 0) · 비어 있던 칸 중 새로 채울 칸 %d개'
                  % (sum(1 for v in exist.values() if v), len(refilled)))

    # --- h19 365칸 채우기
    tgt = byid['h19']
    before = dict(tgt['rates'])
    daily = {x['date']: x.get('usd') for x in data['h19']['daily']}
    rates, added, dropped = {}, 0, 0
    for day in days_of(WIN_START, WIN_END):
        usd = daily.get(day)
        old = before.get(day)
        rates[day] = to_krw(usd)
        if old is None and rates[day] is not None:
            added += 1
        elif old is not None and rates[day] is None:
            dropped += 1
    tgt['rates'] = rates
    tgt['source'] = SRC['h19']
    vals = [v for v in rates.values() if v]
    low = min(vals)
    lowday = [d for d, v in rates.items() if v == low]
    report.append('h19 %d칸/요금 %d · 신규 %d칸 · 요금없음 %d칸 · 최저 %s원(%s) · 최고 %s원'
                  % (len(rates), len(vals), added,
                     sum(1 for v in rates.values() if not v), f'{low:,}',
                     ','.join(lowday[:3]), f'{max(vals):,}'))
    if dropped:
        report.append('  h19 요금이 사라진 칸: %d' % dropped)

    # --- 나머지 4곳은 한 칸도 바뀌지 않았는지
    for hid in ('h16', 'h17', 'h18', 'h20'):
        if json.dumps(byid[hid]['rates'], sort_keys=True) != untouched[hid]:
            sys.exit('%s 값이 바뀌었습니다 — 중단' % hid)
        tail_null = sum(1 for d, v in byid[hid]['rates'].items()
                        if v is None and d >= '2027-04-01')
        report.append('%s 그대로 — 2027-04-01~11-30 null %d칸' % (hid, tail_null))

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
