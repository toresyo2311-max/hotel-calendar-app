#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 베트남 4차 4곳 병합 (320 → 324곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-25 No.7(@no_7) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/a03363f4-no71/pickle/2026-11-25-2241/received/0-marriott_vietnam_batch4.json
    — 4곳(DADFP · VIISI · PQCJW · PQCOX) 365일(2026-12-01~2027-11-30) 세전 현금 KRW + 아워드 포인트.
      파일의 region 은 `베트남` 이고, ③ 탭은 1~3차와 같이 국가 단위(베트남)로 적는다
      (카드에는 「베트남 · 푸꾸옥」처럼 국가와 도시가 함께 보인다).

규칙:
  · 신규 4곳은 m321~m324(베트남 12→16)로 메리어트 묶음 맨 뒤에 붙인다. 기존 320곳은 값·순서 그대로.
  · PQCOX(목시 푸꾸옥 혼톰)는 2027년 1분기 개관 예정(Opening Q1 2027)으로 현금·포인트 365일이 모두
    비어 있다 — 0칸을 결측이 아니라 실측 결과로 싣고 note 에 개관 예정과 미게시를 명시한다
    (master_db.NO_POINT_CODES 등록, DADER·TPESX 와 같은 처리).
  · ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조한다 — 겹침이 있으면 alsoIn 양방향 +
    MAR_CROSS 를 반영해야 하므로, 이 스크립트는 겹침이 0곳이 아니면 멈춘다(수동 확인).
  · 원자료 국문명 DADFP `포인트 다낭 Danang` 은 브랜드가 `포인트`로 잘리고 도시가 두 번 들어와
    공식 한국어 지점명 `포 포인츠 바이 쉐라톤 다낭`(marriott.com/ko)으로 통일한다.
    PQCJW 는 `JW 메리어트 푸꾸옥 에메랄드 베이 리조트 앤 스파`, PQCOX 는 `목시 푸꾸옥 혼톰`
    (마리어트 한국어 페이지 표기 `혼톰`)으로 적는다.
  · note 는 원자료 값에서 확인되는 사실만 적는다 — 일수·값 범위·결번 구간·창 끝·null 보간 없음.
    세금·수수료 별도(세전) 기준임을 밝힌다.
  · 영문명 끝의 `®` 는 기존 카드 표기(161+536+320곳 모두 ® 없음)에 맞춰 떼고 싣는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/a03363f4-no71/pickle/2026-11-25-2241/received/'
       '0-marriott_vietnam_batch4.json')
DAY = '2026-11-25'
FIRST = 321                       # m321~m324
CODES = ('DADFP', 'VIISI', 'PQCJW', 'PQCOX')
REGION = '베트남'
# 현금·아워드 포인트가 365일 전부 미게시인 호텔 — PQCOX(개관 전)
NO_CASH = {'PQCOX'}
NO_POINTS = {'PQCOX'}
# 원자료 브랜드·국문명 → 카드 표기
BRAND = {'DADFP': '포 포인츠 바이 쉐라톤', 'VIISI': '쉐라톤',
         'PQCJW': 'JW 메리어트', 'PQCOX': '목시'}
NAME = {'DADFP': '포 포인츠 바이 쉐라톤 다낭',
        'VIISI': '쉐라톤 빈',
        'PQCJW': 'JW 메리어트 푸꾸옥 에메랄드 베이 리조트 앤 스파',
        'PQCOX': '목시 푸꾸옥 혼톰'}
# ① 호텔럭스와 같은 호텔 — 코드 → (① 호텔럭스 id, ① 탭 표기). ① 탭 161곳에 푸꾸옥·빈 호텔이 없다
TWIN = {}
# 호텔별 특이사항 — 원자료 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'DADFP': '현금은 98,784원 59일 · 93,845원 55일 · 113,602원 51일 · 91,375원 43일이 기본이고, '
             '2026-12-30 하루만 197,569원(창 안 최고가)이며 2027-01-01 187,690원 · '
             '2026-12-26~12-28 158,055원이 그 뒤를 잇습니다(2027-10-15~11-12 29일은 83,966원으로 최저 구간). '
             '아워드 포인트는 22,500P 가 88일로 최빈·최고이고(2026-12-16~12-24 · 2027-02-05~02-10 · '
             '2027-07~08월 대부분 · 2027-10-26~11-06), 17,500P 31일 · 16,000P 30일 · 18,000P 29일로 '
             '갈리며 2027-10-18 하루만 14,500P 입니다',
    'VIISI': '현금은 96,218원 309일 · 93,209원 30일(2026-12-01~12-30)이 거의 전부이고, '
             '2026-12-31 하루만 102,356원(창 안 최고가) · 2027-01-01 100,495원입니다. '
             '아워드 포인트는 26,000P 296일 · 24,000P 30일(2026-12-01~12-30)이 기본이고 '
             '31,000P 가 14일(2026-12-31~2027-01-01 · 2027-10-26~11-06)이며 2027-01-12 하루만 '
             '26,500P 입니다',
    'PQCJW': '현금은 488,983원 75일 · 409,955원 39일 · 414,895원 29일이 기본이고, '
             '2027-11-06 과 2027-11-09~11-12 5일이 2,469,613원(창 안 최고가)이며 '
             '2026-12-30 1,852,209원 · 2026-12-16 1,827,513원 · 2026-12-09 1,778,121원이 그 뒤를 잇습니다. '
             '아워드 포인트는 73,000P 가 163일로 최빈이고 66,000P 34일 · 65,000P 29일 · 67,000P 24일 · '
             '64,000P 20일로 갈리며 2026-12-18 하루만 75,000P(창 안 최고)입니다',
    'PQCOX': '2027년 1분기 개관 예정(Opening Q1 2027)이라 2026-12-01~2027-11-30 365일이 현금·포인트 '
             '모두 미게시입니다(오픈 후 재실측이 필요합니다)',
}
WINDOW_END = {
    'DADFP': '현금은 2027-11-12 까지이고(2027-11-13~11-30 18일 예약 창 끝 · Rate Unavailable) '
             '아워드 포인트는 2027-11-06 에 먼저 끊겨 2027-11-07~11-30 24일이 미게시입니다',
    'VIISI': '현금·포인트가 함께 2027-11-06 에 끊겨 2027-11-07~11-30 24일이 값 없이 끝납니다',
    'PQCJW': '현금·포인트가 함께 2027-11-12 까지이고 2027-11-13~11-30 18일이 예약 창 끝'
             '(Rate Unavailable)입니다',
    'PQCOX': '개관 전이라 예약 창 자체가 열리지 않았습니다(예약 창 끝이 아니라 전 기간 미게시)',
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
        raise SystemExit('베트남 4차 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('region') != '베트남':
        raise SystemExit('원본 region %r (베트남 이어야 함)' % doc.get('region'))
    hotels = doc['hotels']
    if len(hotels) != 4:
        raise SystemExit('베트남 4차 원본 호텔 %d곳 (4곳이어야 함)' % len(hotels))
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
    if not cash_vals and h['code'] not in NO_CASH:
        raise SystemExit('%s 현금 값 0칸 — 수록 기준 확인 필요' % h['code'])
    if not pt_vals and h['code'] not in NO_POINTS:
        raise SystemExit('%s 아워드 포인트 0칸 — 원본 확인 필요' % h['code'])
    if cash_vals and h['code'] in NO_CASH:
        raise SystemExit('%s 는 현금 0칸이어야 하는데 %d칸' % (h['code'], len(cash_vals)))
    if pt_vals and h['code'] in NO_POINTS:
        raise SystemExit('%s 는 포인트 0칸이어야 하는데 %d칸' % (h['code'], len(pt_vals)))

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], h['city'], cash_days, pt_days)]
    if cash_vals:
        notes.append('현금 (세전) %s~%s원' % (format(min(cash_vals), ','), format(max(cash_vals), ',')))
    else:
        notes.append('현금은 365일 전부 미게시(0일) — 보간하지 않았습니다')
    if pt_vals:
        notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))
    else:
        notes.append('아워드 포인트는 365일 전부 미게시(0일) — 보간하지 않았습니다')

    cash_gap_days = [d for d, v in rates.items() if not isinstance(v, (int, float))]
    pt_gap_days = [d for d, v in pt_map.items() if not isinstance(v, int)]
    cash_gap = ranges(cash_gap_days)
    pt_gap = ranges(pt_gap_days)
    if cash_gap and cash_vals:
        notes.append('현금 결번 %d일 %d개 구간(%s)' % (
            len(cash_gap_days), len(cash_gap), ' · '.join(cash_gap)))
    if pt_gap and pt_vals:
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
    if pt_vals:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days)
        pt_src = '아워드 포인트 캘린더(%s 기준)' % DAY
    elif cash_vals:
        promo = '아워드 포인트 캘린더 미게시(%s 기준) · 현금 %d일' % (DAY, cash_days)
        pt_src = '아워드 포인트 캘린더(%s 기준 · 365일 미게시)' % DAY
    else:
        promo = ('현금·아워드 포인트 미게시(%s 기준 · 365일) · 2027년 1분기 개관 예정' % DAY)
        pt_src = '아워드 포인트 캘린더(%s 기준 · 365일 미게시)' % DAY
    return {
        'id': hid,
        'group': 'marriott',
        'brand': BRAND[h['code']],
        'city': h['city'],
        'region': REGION,
        'name': NAME[h['code']],
        'english': english,
        'promotion': promo,
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / %s · '
                   'No.7 실측 marriott_vietnam_batch4 베트남 4차 4곳 365일' % (DAY, pt_src)),
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
        card_name = NAME[h['code']]
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

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 320곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (
        '2026-11-25 KST ③ 메리어트 베트남 4차 4곳 병합(320→324곳 · 베트남 16 · 통합 1,021곳) — '
        'DADFP 포 포인츠 바이 쉐라톤 다낭(현금 344칸 · 포인트 338칸) · VIISI 쉐라톤 빈(341 · 341) · '
        'PQCJW JW 메리어트 푸꾸옥 에메랄드 베이 리조트 앤 스파(327 · 315) · '
        'PQCOX 목시 푸꾸옥 혼톰(0 · 0 — 2027년 1분기 개관 예정) 4곳'
        '(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 세전 현금·아워드 포인트 실측(2026-11-25 · '
        'No.7(@no_7) 전달본), 원자료 region 이 베트남이고 1~3차와 같이 지역 칸을 베트남으로 적음'
        '(카드에 「베트남 · 푸꾸옥」), PQCOX 는 개관 전이라 현금·포인트 365일 모두 미게시(0칸 — 보간 없이 '
        '그대로 수록, NO_POINT_CODES 등록, 오픈 후 재실측 필요), DADFP 현금 83,966~197,569원'
        '(98,784원 59일 · 2026-12-30 하루만 197,569원 최고가 · 2027-10-15~11-12 83,966원 최저) · '
        '포인트 14,500~22,500P(22,500P 가 88일로 최빈·최고), VIISI 현금 93,209~102,356원'
        '(96,218원 309일 · 2026-12-31 하루만 102,356원 최고가) · 포인트 24,000~31,000P'
        '(26,000P 296일), PQCJW 현금 409,955~2,469,613원(488,983원 75일 · 2027-11-06·11-09~11-12 5일 '
        '2,469,613원 최고가 · 2026-12-30 1,852,209원) · 포인트 64,000~75,000P(73,000P 163일), '
        'DADFP 는 포인트가 2027-11-06 에 먼저 끊기고 현금은 11-12 까지, VIISI 는 현금·포인트가 함께 '
        '2027-11-06 에 끊기며, PQCJW 는 둘 다 2027-11-12 까지(11-13~30 18일 예약 창 끝), '
        '① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳(alsoIn·MAR_CROSS 추가 0쌍, '
        '1차 CXRJW↔h22 1쌍 그대로 77곳, ① 탭에 푸꾸옥·빈 호텔 없음)'
        % (cash, pts))
    if '베트남 4차 4곳 병합' not in master.get('extended', ''):
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
