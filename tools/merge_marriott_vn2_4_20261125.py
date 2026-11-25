#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 베트남 2차 4곳 병합 (312 → 316곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-25 No.7(@no_7) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/a03363f4-no71/pickle/2026-11-25-2153/received/0-marriott_vietnam_batch2.json
    — 4곳(CXRHT · NHASI · CXRNP · DADMR) 365일(2026-12-01~2027-11-30) 세전 현금 KRW + 아워드 포인트.
      파일의 region 은 `베트남` 이고, ③ 탭은 1차와 같이 국가 단위(베트남)로 적는다
      (카드에는 「베트남 · 나트랑」「베트남 · 다낭」처럼 국가와 도시가 함께 보인다).

규칙:
  · 신규 4곳은 m313~m316(베트남 4→8)로 메리어트 묶음 맨 뒤에 붙인다. 기존 312곳은 값·순서 그대로.
  · ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조한다 — 겹침이 있으면 alsoIn 양방향 +
    MAR_CROSS 를 반영해야 하므로, 이 스크립트는 겹침이 0곳이 아니면 멈춘다(수동 확인).
  · 원자료 브랜드·국문명이 `포인트` 로 잘려 온 CXRNP 는 기존 표기(포 포인츠 바이 쉐라톤)로 통일한다
    (2026-11-24 대만 7차 TPEFT 와 같은 처리). DADMR 국문명 끝의 `Danang` 은 카드에 도시가 따로
    보여 중복이라 뗀다.
  · note 는 원자료 값에서 확인되는 사실만 적는다 — 일수·값 범위·결번 구간·창 끝·null 보간 없음.
    세금·수수료 별도(세전) 기준임을 밝힌다.
  · 영문명 끝의 `®` 는 기존 카드 표기(161+536+312곳 모두 ® 없음)에 맞춰 떼고 싣는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/a03363f4-no71/pickle/2026-11-25-2153/received/'
       '0-marriott_vietnam_batch2.json')
DAY = '2026-11-25'
FIRST = 313                       # m313~m316
CODES = ('CXRHT', 'NHASI', 'CXRNP', 'DADMR')
REGION = '베트남'
# 원자료 브랜드·국문명 → 카드 표기(잘려 온 브랜드만 고친다)
BRAND = {'CXRHT': '메리어트', 'NHASI': '쉐라톤',
         'CXRNP': '포 포인츠 바이 쉐라톤', 'DADMR': '메리어트'}
NAME = {'CXRNP': '포 포인츠 바이 쉐라톤 나트랑', 'DADMR': '메리어트 다낭'}
# ① 호텔럭스와 같은 호텔 — 코드 → (① 호텔럭스 id, 원자료와 다른 ① 탭 표기)
TWIN = {}
# 호텔별 특이사항 — 원자료 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'CXRHT': '현금은 177,812원 173일 · 133,359원 124일 · 118,541원 18일 세 값이 기본이고, '
             '2026-12-09 하루만 271,657원(창 안 최고가)이며 2026-12-26 · 12-31 은 261,778원, '
             '뗏 연휴 2027-02-05~02-13 9일은 222,265원입니다. 아워드 포인트는 37,000P 37일 · '
             '30,000P 34일 · 31,000P 24일로 갈리고, 49,000P 28일이 2026-12-31 · '
             '2027-02-05~02-13 9일 · 2027-10-26~11-12 18일에 몰려 있습니다',
    'NHASI': '현금은 197,569원 191일 · 162,994원 49일 · 167,933원 30일이 기본이고, '
             '2027-01-08 하루만 605,965원(창 안 최고가 · 그 앞날 2027-01-07 은 310,183원)이며 '
             '2026-12-31 은 284,499원, 뗏 연휴 2027-02-05~02-09 5일은 232,143원입니다. '
             '아워드 포인트는 37,000P 109일 · 41,000P 58일 · 35,000P 47일로 갈립니다',
    'CXRNP': '현금은 66,679원 127일 · 79,027원 120일 · 81,497원 50일 세 값이 기본이고, '
             '뗏 연휴 2027-02-06~02-13 8일이 113,602원(창 안 최고가)이며 2026-12-31~'
             '2027-01-02 사흘은 98,784원입니다. 아워드 포인트는 23,000P 64일 · 26,500P 52일 · '
             '25,000P 49일로 갈리고, 31,000P 26일이 2026-12-31~2027-01-03 · '
             '2027-02-05~02-14 10일 · 2027-10-26~11-06 12일에 몰려 있습니다',
    'DADMR': '현금은 212,386원 119일 · 232,143원 90일 · 217,325원 48일이 기본이고, '
             '2027-04-15·04-16 이틀만 972,533원(창 안 최고가)이며 그 이틀과 2027-04-22~04-23 '
             '나흘은 아워드 포인트만 미게시입니다. 연말은 2026-12-31 563,071원 · '
             '2026-12-30 444,530원으로 올라갑니다. 아워드 포인트는 52,000P 가 203일로 대부분이고 '
             '49,000P 20일 · 47,000P 16일 · 50,000P 16일이 뒤를 잇습니다',
}
WINDOW_END = {
    'CXRHT': '현금·포인트가 함께 2027-11-12 에 끊겨 2027-11-13~11-30 18일이 예약 창 끝'
             '(Rate Unavailable)입니다',
    'NHASI': '현금은 2027-11-12 까지이고 아워드 포인트는 2027-11-06 에 먼저 끊겨 '
             '2027-11-07~11-30 24일이 미게시이며, 현금도 2027-11-13~11-30 18일이 예약 창 끝입니다',
    'CXRNP': '현금·포인트가 함께 2027-11-06 에 끊겨 2027-11-07~11-30 24일이 값 없이 끝납니다',
    'DADMR': '현금·포인트가 함께 2027-11-06 에 끊겨 2027-11-07~11-30 24일이 값 없이 끝납니다',
}


def ranges(nulls):
    """null 날짜 목록 -> 연속 구간 문자열 목록."""
    ds = sorted(nulls)
    out = []
    for d in ds:
        dd = datetime.date.fromisoformat(d)
        if out and (dd - out[-1][1]).days == 1:
            out[-1][1] = dd
        else:
            out.append([dd, dd])
    return ['%s~%s' % (a, b) if a != b else str(a) for a, b in out]


def load():
    with open(SRC, encoding='utf-8') as fp:
        doc = json.load(fp)
    if doc['checked_at'] != DAY:
        raise SystemExit('베트남 2차 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('region') != '베트남':
        raise SystemExit('원본 region %r (베트남 이어야 함)' % doc.get('region'))
    hotels = doc['hotels']
    if len(hotels) != 4:
        raise SystemExit('베트남 2차 원본 호텔 %d곳 (4곳이어야 함)' % len(hotels))
    if tuple(h['code'] for h in hotels) != CODES:
        raise SystemExit('원본 코드 순서가 다름: %s' % [h['code'] for h in hotels])
    for h in hotels:
        if h['country'] != '베트남':
            raise SystemExit('%s 국가 %s (베트남 이어야 함)' % (h['code'], h['country']))
        if h.get('region') != '베트남':
            raise SystemExit('%s region %r (베트남 이어야 함)' % (h['code'], h.get('region')))
        if h['code'] not in BRAND:
            raise SystemExit('%s 브랜드 표기 미정' % h['code'])
    return hotels


def build(h, hid):
    rates, pt_map = h['rates'], h['points']
    for name, vals in (('rates', rates), ('points', pt_map)):
        if len(vals) != 365:
            raise SystemExit('%s %s 칸 %d개 (365 이어야 함)' % (h['code'], name, len(vals)))
        for d in vals:
            if not (M.WINDOW_START <= d <= M.WINDOW_END):
                raise SystemExit('%s %s 날짜 %s 창 밖' % (h['code'], name, d))
    cash_days = sum(1 for v in rates.values() if isinstance(v, (int, float)))
    pt_days = sum(1 for v in pt_map.values() if isinstance(v, int))
    cash_vals = [v for v in rates.values() if isinstance(v, (int, float))]
    pt_vals = [v for v in pt_map.values() if isinstance(v, int)]
    if not cash_vals:
        raise SystemExit('%s 현금 값 0칸 — 수록 기준 확인 필요' % h['code'])
    if not pt_vals:
        raise SystemExit('%s 아워드 포인트 0칸 — 원본 확인 필요' % h['code'])

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], h['city'], cash_days, pt_days)]
    notes.append('현금 (세전) %s~%s원' % (format(min(cash_vals), ','), format(max(cash_vals), ',')))
    notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))

    cash_gap_days = [d for d, v in rates.items() if not isinstance(v, (int, float))]
    pt_gap_days = [d for d, v in pt_map.items() if not isinstance(v, int)]
    cash_gap = ranges(cash_gap_days)
    pt_gap = ranges(pt_gap_days)
    notes.append('현금 결번 %d일 %d개 구간(%s)' % (
        len(cash_gap_days), len(cash_gap), ' · '.join(cash_gap)))
    notes.append('포인트 결번 %d일 %d개 구간(%s)' % (
        len(pt_gap_days), len(pt_gap), ' · '.join(pt_gap)))
    notes.append(EXTRA[h['code']])
    notes.append(WINDOW_END[h['code']])
    twin = TWIN.get(h['code'])
    if twin:
        notes.append('① 호텔럭스 %s(%s)와 같은 호텔이라 alsoIn 으로 양방향 연결했습니다'
                     % (twin[0], twin[1]))
    notes.append('null 은 그 날 값 미게시이며 보간하지 않았습니다.')

    english = h['english'].replace('®', '').strip()
    if english.endswith(','):
        english = english[:-1].strip()
    return {
        'id': hid,
        'group': 'marriott',
        'brand': BRAND[h['code']],
        'city': h['city'],
        'region': REGION,
        'name': NAME.get(h['code'], h['name']),
        'english': english,
        'promotion': '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days),
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
                   '아워드 포인트 캘린더(%s 기준) · No.7 실측 marriott_vietnam_batch2 '
                   '베트남 2차 4곳 365일' % (DAY, DAY)),
        'code': h['code'],
        'rates': rates,
        'points': pt_map,
        'note': ' · '.join(notes),
    }


def crosscheck_lux(master, hotels):
    """① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조(도시는 같은 도시 호텔 목록까지)."""
    lux = [x for x in master['hotels'] if x.get('group') == 'lux']
    lcodes = {x.get('code') for x in lux if x.get('code')}
    lenames = {(x.get('english') or '').strip().lower() for x in lux}
    lnames = {x.get('name') for x in lux}
    hits = []
    for h in hotels:
        eng = h['english'].replace('®', '').strip().lower()
        card_name = NAME.get(h['code'], h['name'])
        if h['code'] in lcodes or eng in lenames or card_name in lnames:
            hit = [x for x in lux
                   if x.get('code') == h['code']
                   or (x.get('english') or '').strip().lower() == eng
                   or x.get('name') == card_name]
            hits.append((h['code'], [(x['id'], x['name']) for x in hit]))
    by_city = {}
    for x in lux:
        by_city.setdefault(x.get('city'), []).append((x['id'], x['name']))
    cities = [(h['code'], h['city'], by_city.get(h['city'], [])) for h in hotels]
    return len(lux), hits, cities


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    src = load()

    if master['hotels'][0].get('group') != 'lux':
        raise SystemExit('정본 첫 카드가 ① 이 아닙니다 — 정본 상태 확인 필요')

    ids = {h['id'] for h in master['hotels']}
    codes = {h.get('code') for h in master['hotels'] if h.get('code')}
    names = {(h.get('english') or '').strip().lower() for h in master['hotels']}
    mar_ids = [h['id'] for h in master['hotels'] if h.get('group') == 'marriott']
    if max(int(x[1:]) for x in mar_ids) != FIRST - 1:
        raise SystemExit('정본 마지막 메리어트 id 가 m%d 가 아닙니다' % (FIRST - 1))

    new = []
    for i, h in enumerate(src):
        hid = 'm%d' % (FIRST + i)
        if hid in ids:
            raise SystemExit('이미 있는 id: %s' % hid)
        if h['code'] in codes:
            raise SystemExit('이미 있는 code: %s (중복 추가 금지)' % h['code'])
        eng = h['english'].replace('®', '').strip().lower()
        twin_id = TWIN.get(h['code'], (None,))[0]
        if eng in names and not twin_id:
            raise SystemExit('이미 있는 영문명: %s' % h['english'])
        new.append(build(h, hid))

    lux_n, lux_hits, lux_cities = crosscheck_lux(master, src)
    print('① 호텔럭스 %d곳 대조 — 겹침 %d곳 %s' % (lux_n, len(lux_hits), lux_hits))
    for code, city, twins in lux_cities:
        print('   %s %s — ① 탭 같은 도시 %d곳 %s' % (code, city, len(twins), twins))
    if len(lux_hits) != len(TWIN):
        raise SystemExit('① 탭 겹침 %d곳 (기대 %d곳 — alsoIn·MAR_CROSS 연결 여부를 먼저 정하세요)'
                         % (len(lux_hits), len(TWIN)))

    # alsoIn 양방향 — 신규 카드와 ① 호텔(lux) 쪽 모두
    for card, h in zip(new, src):
        twin = TWIN.get(h['code'])
        if not twin:
            continue
        card['alsoIn'] = twin[0]
        lux = [x for x in master['hotels'] if x['id'] == twin[0]]
        if not lux:
            raise SystemExit('① 호텔 %s 없음' % twin[0])
        if lux[0].get('alsoIn'):
            raise SystemExit('① 호텔 %s 에 이미 alsoIn %s' % (twin[0], lux[0]['alsoIn']))
        lux[0]['alsoIn'] = card['id']

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 312곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (
        '2026-11-25 KST ③ 메리어트 베트남 2차 4곳 병합(312→316곳 · 베트남 8 · 통합 1,013곳) — '
        'CXRHT 메리어트 나트랑 Hon Tre Island(현금 344칸 · 포인트 342칸) · NHASI 쉐라톤 나트랑'
        '(347 · 337) · CXRNP 포 포인츠 바이 쉐라톤 나트랑(341 · 341) · DADMR 메리어트 다낭'
        '(341 · 335) 4곳(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 세전 현금·아워드 포인트 '
        '실측(2026-11-25 · No.7(@no_7) 전달본), 원자료 region 이 베트남이고 1차와 같이 지역 칸을 '
        '베트남으로 적음(카드에 「베트남 · 나트랑」「베트남 · 다낭」), ① 호텔럭스 161곳과 코드·'
        '영문명·국문명·도시 전수 대조 — 겹침 0곳(alsoIn·MAR_CROSS 추가 0쌍, 1차 CXRJW↔h22 1쌍 그대로 77곳), '
        'CXRHT 현금 118,541~271,657원(177,812원 173일 · 133,359원 124일 · 118,541원 18일 · '
        '2026-12-09 하루만 최고가) · 포인트 29,000~49,000P(결번 23일 — 2026-12-09~12-12 · '
        '2026-12-26 · 2027-11-13~11-30), NHASI 현금 145,707~605,965원(2027-01-08 하루만 '
        '605,965원 최고가 · 197,569원 191일) · 포인트 32,000~41,000P(포인트만 2027-11-07~11-30 '
        '24일 미게시), CXRNP 현금 56,801~113,602원(뗏 2027-02-06~02-13 8일이 최고가 · 66,679원 '
        '127일) · 포인트 22,500~31,000P(현금·포인트 함께 2027-11-07~11-30 24일 값 없음), '
        'DADMR 현금 182,751~972,533원(2027-04-15·04-16 이틀만 972,533원 최고가 · 212,386원 119일) · '
        '포인트 37,000~52,000P(52,000P 가 203일 · 그 이틀과 2027-04-22~04-23 은 포인트만 미게시)'
        % (cash, pts))
    if '베트남 2차 4곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + ' / ' + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 4곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for x in master['hotels'] if x.get('group') == 'marriott'), cash, pts))
    for card in new:
        print('  %s %s %s (현금 %d칸 · 포인트 %d칸 · alsoIn %s)' % (
            card['id'], card['code'], card['name'],
            sum(1 for v in card['rates'].values() if isinstance(v, (int, float))),
            sum(1 for v in card['points'].values() if isinstance(v, int)),
            card.get('alsoIn', '-')))
        print('     note: %s' % card['note'])


if __name__ == '__main__':
    main()
