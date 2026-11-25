#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 베트남 8차 4곳 병합 (336 → 340곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-26 No.7(@no_7) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/a03363f4-no71/pickle/2026-11-26-0048/received/0-marriott_vietnam_batch8.json
    — 4곳(SGNJT · SGNBS · SGNBR · SGNMD) 365일(2026-12-01~2027-11-30) 세전 현금 KRW + 아워드 포인트.
      파일의 region 은 `베트남` 이고, ③ 탭은 1~7차와 같이 국가 단위(베트남)로 적는다. 네 곳 모두 호찌민.

규칙:
  · 신규 4곳은 m337~m340(베트남 28→32)으로 메리어트 묶음 맨 뒤에 붙인다. 기존 336곳은 값·순서 그대로.
  · 국문명은 marriott.com/ko 공식 표기로 적는다 —
    SGNJT `JW 메리어트 호텔 앤 스위트 사이공, 더 아파트먼트`(ko 페이지 「JW 메리어트 호텔 & 스위트
    사이공, 더 아파트먼트에 오신 것을 환영합니다」),
    SGNBR `르네상스 리버사이드 호텔 사이공`(ko 페이지 「르네상스 리버사이드 호텔 사이공에 오신 것을
    환영합니다」), SGNMD `르메르디앙 사이공`(ko 페이지 「르메르디앙 사이공에 오신 것을 환영합니다」).
    SGNBS 는 marriott.com/ko 가 한국어 페이지를 내지 않아(영문 그대로) 기존 디자인 호텔스 카드 관례
    (`디자인 호텔스 + 도시 + 고유명`)로 `디자인 호텔스 호찌민 바흐 스위트` 로 적는다 — note 에 밝힌다.
  · SGNJT 는 7차 SGNJS(JW 메리어트 호텔 앤 스위트 사이공)와 같은 복합 시설의 아파트먼트(레지던스 타워)를
    marriott.com 이 별도 숙소 코드로 파는 것이라 중복 카드가 아니다(공식 SGNJS ko 페이지 「305개의 객실과
    스위트, 그리고 260개의 아파트먼트」) — note 에 밝힌다.
  · SGNJT · SGNMD 는 아워드 포인트 캘린더가 365일 전부 미게시(0칸)다 — 0칸을 결측이 아니라 실측 결과로
    싣고 NO_POINT_CODES 에 등록한다(재실측 대상). 나머지 두 곳은 포인트 값이 있다.
  · ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조한다 — 겹침이 있으면 alsoIn 양방향 +
    MAR_CROSS 를 반영해야 하므로, 이 스크립트는 겹침이 0곳이 아니면 멈춘다(수동 확인).
  · note 는 원자료 값에서 확인되는 사실만 적는다 — 일수·값 범위·결번 구간·창 끝·null 보간 없음.
    세금·수수료 별도(세전) 기준임을 밝힌다.
  · 영문명 끝의 `™` 는 기존 디자인 호텔스 카드 표기 그대로 두고 싣는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/a03363f4-no71/pickle/2026-11-26-0048/received/'
       '0-marriott_vietnam_batch8.json')
DAY = '2026-11-26'
FIRST = 337                       # m337~m340
CODES = ('SGNJT', 'SGNBS', 'SGNBR', 'SGNMD')
REGION = '베트남'
# 원자료 브랜드 → 카드 표기
BRAND = {'SGNJT': 'JW 메리어트', 'SGNBS': '디자인 호텔스',
         'SGNBR': '르네상스', 'SGNMD': '르메르디앙'}
# marriott.com/ko 공식 한국어명(SGNBS 는 ko 페이지 없음 — 기존 카드 관례)
NAME = {'SGNJT': 'JW 메리어트 호텔 앤 스위트 사이공, 더 아파트먼트',
        'SGNBS': '디자인 호텔스 호찌민 바흐 스위트',
        'SGNBR': '르네상스 리버사이드 호텔 사이공',
        'SGNMD': '르메르디앙 사이공'}
CITY = {'SGNJT': '호찌민', 'SGNBS': '호찌민', 'SGNBR': '호찌민', 'SGNMD': '호찌민'}
# ① 호텔럭스와 같은 호텔 — 코드 → (① 호텔럭스 id, ① 탭 표기). ① 탭 161곳에 호찌민 호텔이 없다
TWIN = {}
# 아워드 포인트 캘린더 365일 미게시(0칸) — 실측 결과 그대로 싣고 NO_POINT_CODES 등록
ZERO_POINT = {'SGNJT', 'SGNMD'}
# 호텔별 특이사항 — 원자료 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'SGNJT': '현금은 345,745원 86일 · 306,232원 85일 · 405,016원 69일 · 355,624원 41일이 기본이고 '
             '306,232원 85일 가운데 2026-12-04~12-06 · 12-11~12-13 · 12-18~12-19 여드레와 '
             '2027-02-05 이후 77일(금·토·일 중심)이 창 안 최저이며, 2026-12-31 하루만 '
             '839,668원(창 안 최고가) · 2026-12-30 592,707원입니다. 아워드 포인트 캘린더는 '
             '2026-12-01~2027-11-30 365일이 전부 미게시(0칸)입니다. 7차에 넣은 SGNJS'
             '(JW 메리어트 호텔 앤 스위트 사이공)와 같은 복합 시설의 아파트먼트(레지던스 타워)를 '
             'marriott.com 이 별도 숙소 코드로 파는 것이라 중복 카드가 아닙니다(공식 SGNJS ko 페이지 '
             '「305개의 객실과 스위트, 그리고 260개의 아파트먼트」 · 주소 Corner Nguyen Du Street & '
             'Le Van Huu Street).',
    'SGNBS': '현금은 270,357원 105일 · 259,959원 78일 · 296,353원 69일 · 285,955원 54일이 기본이고 '
             '239,162원 4일(2026-12-11~12-13 · 12-20)이 창 안 최저, 2027-01-02 하루만 369,142원'
             '(창 안 최고가) · 2026-12-24~12-26·12-28 306,751원입니다. 아워드 포인트는 43,000P '
             '89일 · 48,000P 73일 · 40,000P 64일 · 47,000P 47일로 갈리며 37,000P 7일'
             '(2026-12-04~12-06 · 12-11~12-13 등)이 창 안 최저, 48,000P 가 2027-01-04~01-08 '
             '등에서 최고입니다. marriott.com/ko 는 이 호텔의 한국어 페이지를 내지 않아(영문 페이지만) '
             '국문명은 기존 디자인 호텔스 카드 표기 관례(디자인 호텔스 + 도시 + 고유명)에 따라 '
             '`디자인 호텔스 호찌민 바흐 스위트`로 적었습니다(공식 영문명 Bach Suites Saigon, '
             'a Member of Design Hotels).',
    'SGNBR': '현금은 222,265원 53일 · 242,022원 43일 · 237,082원 23일 · 192,629원 23일이 기본이고 '
             '192,629원 23일(2027-02-01~02-23)이 창 안 최저, 2026-12-31 하루만 642,099원(창 안 '
             '최고가) · 2026-12-30 360,563원 · 2026-12-03·12-08 286,475원입니다. 아워드 포인트는 '
             '31,000P 169일이 기본이고 30,500P 24일 · 30,000P 22일 · 29,500P 20일로 갈리며 '
             '22,500P 가 2027-02-06~02-13 등에서 창 안 최저입니다. 현금 결번은 2026-12-02 · '
             '2026-12-09~12-10 세 날과 2027-11-13~11-30 18일이고, 포인트는 2026-12-02 · 12-04 · '
             '12-09~12-10 · 12-26 · 12-30~12-31 · 2027-06-30 · 2027-11-13~11-30 26일이 '
             '미게시입니다.',
    'SGNMD': '현금은 296,353원이 347일 가운데 245일로 기본이고 271,657원 32일 · 222,265원 24일 · '
             '286,475원 18일이 그 뒤를 잇습니다. 222,265원 24일(2027-01-29~02-21 등)이 창 안 최저, '
             '2026-12-31 하루만 666,795원(창 안 최고가) · 2026-12-30 395,138원입니다. 아워드 '
             '포인트 캘린더는 2026-12-01~2027-11-30 365일이 전부 미게시(0칸)입니다.',
}
WINDOW_END = {
    'SGNJT': '현금이 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝입니다',
    'SGNBS': '현금·포인트가 함께 2027-11-02 까지여서 2027-11-03~11-30 28일이 예약 창 끝입니다',
    'SGNBR': '현금이 2027-11-12 까지 · 포인트는 2027-11-12 까지여서 2027-11-13~11-30 18일이 '
             '예약 창 끝입니다',
    'SGNMD': '현금이 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝입니다',
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
        raise SystemExit('베트남 8차 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('region') != '베트남':
        raise SystemExit('원본 region %r (베트남 이어야 함)' % doc.get('region'))
    hotels = doc['hotels']
    if len(hotels) != 4:
        raise SystemExit('베트남 8차 원본 호텔 %d곳 (4곳이어야 함)' % len(hotels))
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
    if not pt_vals and h['code'] not in ZERO_POINT:
        raise SystemExit('%s 아워드 포인트 0칸 — 원본 확인 필요' % h['code'])
    if pt_vals and h['code'] in ZERO_POINT:
        raise SystemExit('%s 아워드 포인트 값이 있는데 ZERO_POINT 로 표시됨' % h['code'])

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], CITY[h['code']], cash_days, pt_days)]
    notes.append('현금 (세전) %s~%s원' % (format(min(cash_vals), ','), format(max(cash_vals), ',')))
    if pt_vals:
        notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))
    else:
        notes.append('포인트 0칸 — 아워드 포인트 캘린더 365일 전부 미게시(보간 없음)')

    cash_gap_days = [d for d, v in rates.items() if not isinstance(v, (int, float))]
    pt_gap_days = [d for d, v in pt_map.items() if not isinstance(v, int)]
    cash_gap = ranges(cash_gap_days)
    pt_gap = ranges(pt_gap_days)
    if cash_gap:
        notes.append('현금 결번 %d일 %d개 구간(%s)' % (
            len(cash_gap_days), len(cash_gap), ' · '.join(cash_gap)))
    if pt_gap and not ZERO_POINT.issuperset({h['code']}):
        notes.append('포인트 결번 %d일 %d개 구간(%s)' % (
            len(pt_gap_days), len(pt_gap), ' · '.join(pt_gap)))
    notes.append(EXTRA[h['code']])
    notes.append(WINDOW_END[h['code']])
    if h['city'] != CITY[h['code']]:
        notes.append('원자료의 도시 칸(%s)을 실제 소재지 %s으로 바로잡았습니다' % (h['city'], CITY[h['code']]))
    twin = TWIN.get(h['code'])
    if twin:
        notes.append('① 호텔럭스 %s(%s)와 같은 호텔이라 alsoIn 으로 양방향 연결했습니다'
                     % (twin[0], twin[1]))
    notes.append('null 은 그 날 값 미게시이며 보간하지 않았습니다.')

    english = h['english'].strip()
    if english.endswith(','):
        english = english[:-1].strip()
    if pt_vals:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days)
        pt_src = '아워드 포인트 캘린더(%s 기준)' % DAY
    else:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 0일(전 기간 미게시)' % DAY
        pt_src = '아워드 포인트 캘린더(%s 기준 — 365일 미게시)' % DAY
    return {
        'id': hid,
        'group': 'marriott',
        'brand': BRAND[h['code']],
        'city': CITY[h['code']],
        'region': REGION,
        'name': NAME[h['code']],
        'english': english,
        'promotion': promo,
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / %s · '
                   'No.7 실측 marriott_vietnam_batch8 베트남 8차 4곳 365일' % (DAY, pt_src)),
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
        eng = h['english'].replace('®', '').replace('™', '').strip().lower()
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
    cities = [(h['code'], CITY[h['code']], by_city.get(CITY[h['code']], [])) for h in hotels]
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

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 336곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (
        '2026-11-26 KST ③ 메리어트 베트남 8차 4곳 병합(336→340곳 · 베트남 32 · 통합 1,037곳) — '
        'SGNJT JW 메리어트 호텔 앤 스위트 사이공, 더 아파트먼트(현금 347칸 · 포인트 0칸) · '
        'SGNBS 디자인 호텔스 호찌민 바흐 스위트(328 · 290) · '
        'SGNBR 르네상스 리버사이드 호텔 사이공(344 · 339) · SGNMD 르메르디앙 사이공(347 · 0) 4곳'
        '(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 세전 현금·아워드 포인트 실측(2026-11-26 · '
        'No.7(@no_7) 전달본), 네 곳 모두 호찌민이고 원자료 국문명(`JW 메리어트 호찌민 Saigon`·'
        '`디자인 호텔스 호찌민 Bach Saigon`·`르네상스 호찌민 Riverside Saigon`·`르메르디앙 호찌민 '
        'Saigon`)은 marriott.com/ko 공식 표기로 바로잡음(디자인 호텔스는 ko 페이지가 없어 카드 관례), '
        'SGNJT·SGNMD 는 아워드 포인트 캘린더 365일 미게시(0칸 — NO_POINT_CODES 등록, 보간 없음), '
        'SGNJT 현금 306,232~839,668원(2026-12-31 하루만 839,668원) · SGNBS 현금 239,162~369,142원 · '
        '포인트 37,000~48,000P · SGNBR 현금 192,629~642,099원(2026-12-31 하루만 642,099원) · '
        '포인트 22,500~31,000P(31,000P 169일) · SGNMD 현금 222,265~666,795원(296,353원 245일 · '
        '2026-12-31 하루만 666,795원), SGNBS 는 2027-11-02 까지·나머지 세 곳은 2027-11-12 까지여서 '
        '예약 창 끝이 11-03~30(28일)·11-13~30(18일), ① 호텔럭스 161곳과 코드·영문명·국문명·도시 '
        '전수 대조 — 겹침 0곳(alsoIn·MAR_CROSS 추가 0쌍, 1차 CXRJW↔h22 1쌍 그대로 77곳, ① 탭에 '
        '호찌민 호텔 없음)'
        % (cash, pts))
    if '베트남 8차 4곳 병합' not in master.get('extended', ''):
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
