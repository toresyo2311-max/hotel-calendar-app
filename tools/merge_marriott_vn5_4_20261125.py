#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 베트남 5차 4곳 병합 (324 → 328곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-25 No.7(@no_7) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/a03363f4-no71/pickle/2026-11-25-2300/received/0-marriott_vietnam_batch5.json
    — 4곳(PQCSR · PQCFI · HANJW · HANBN) 365일(2026-12-01~2027-11-30) 세전 현금 KRW + 아워드 포인트.
      파일의 region 은 `베트남` 이고, ③ 탭은 1~4차와 같이 국가 단위(베트남)로 적는다.

규칙:
  · 신규 4곳은 m325~m328(베트남 16→20)로 메리어트 묶음 맨 뒤에 붙인다. 기존 324곳은 값·순서 그대로.
  · PQCFI(페어필드 바이 메리어트 푸꾸옥 혼톰)는 2027년 1분기 개관 예정(Opening Q1 2027 — 메리어트
    신규 개관 안내)으로 현금·포인트 365일이 모두 비어 있고, HANBN(박닌 메리어트 호텔)은 원자료에서
    marriott.com 숙소 페이지가 404(미등록)·미판매로 확인돼 역시 365일이 모두 비어 있다. 0칸을 결측이
    아니라 실측 결과로 싣고 note 에 상태를 명시한다(master_db.NO_POINT_CODES 등록).
  · ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조한다 — 겹침이 있으면 alsoIn 양방향 +
    MAR_CROSS 를 반영해야 하므로, 이 스크립트는 겹침이 0곳이 아니면 멈춘다(수동 확인).
  · 국문명은 marriott.com/ko 공식 표기로 적는다 — PQCSR `쉐라톤 푸꾸옥 롱 비치 리조트`,
    HANJW `JW 메리어트 호텔 하노이`. PQCFI 는 `페어필드 바이 메리어트 푸꾸옥 혼톰`,
    HANBN 은 `박닌 메리어트 호텔`(원자료 국문명 `메리어트 하노이 Bac Ninh` 를 바로잡음).
  · HANBN 의 도시 칸은 원자료 값(하노이)을 그대로 두되 note 에 박닌성 박닌 소재임을 밝힌다.
  · note 는 원자료 값에서 확인되는 사실만 적는다 — 일수·값 범위·결번 구간·창 끝·null 보간 없음.
    세금·수수료 별도(세전) 기준임을 밝힌다.
  · 영문명 끝의 `®` 는 기존 카드 표기에 맞춰 떼고 싣는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/a03363f4-no71/pickle/2026-11-25-2300/received/'
       '0-marriott_vietnam_batch5.json')
DAY = '2026-11-25'
FIRST = 325                       # m325~m328
CODES = ('PQCSR', 'PQCFI', 'HANJW', 'HANBN')
REGION = '베트남'
# 현금·아워드 포인트가 365일 전부 미게시인 호텔 — PQCFI(개관 전) · HANBN(페이지 404)
NO_CASH = {'PQCFI', 'HANBN'}
NO_POINTS = {'PQCFI', 'HANBN'}
# 원자료 브랜드 → 카드 표기
BRAND = {'PQCSR': '쉐라톤', 'PQCFI': '페어필드 바이 메리어트',
         'HANJW': 'JW 메리어트', 'HANBN': '메리어트'}
NAME = {'PQCSR': '쉐라톤 푸꾸옥 롱 비치 리조트',
        'PQCFI': '페어필드 바이 메리어트 푸꾸옥 혼톰',
        'HANJW': 'JW 메리어트 호텔 하노이',
        'HANBN': '박닌 메리어트 호텔'}
# ① 호텔럭스와 같은 호텔 — 코드 → (① 호텔럭스 id, ① 탭 표기). ① 탭 161곳에 하노이·푸꾸옥 호텔이 없다
TWIN = {}
# 호텔별 특이사항 — 원자료 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'PQCSR': '현금은 158,055원 149일(2027-05-02~09-01 · 09-05~09-30이 비수기 최저) · '
             '197,569원 36일(2027-04-30~05-01 · 09-02~09-04 · 2027-10월 31일 전체) · '
             '222,265원 28일(2027-03월 중순 · 2027-11-01~11-12) · 187,690원 15일(2027-04-01~04-15) · '
             '172,872원 14일(2027-04-16~04-29)이 기본이고, 2026-12-01 하루만 814,972원(창 안 최고가)이며 '
             '2026-12-24 634,300원 · 2027-01-07 592,707원이 그 뒤를 잇습니다. '
             '아워드 포인트는 29,000P 가 134일(2027-05~09월)로 최빈·최저이고 '
             '48,000P 78일(연말연시 · 설 연휴 · 2027-10-26~11-12) · 30,000P 39일 · '
             '37,000P 16일(2027-03월) · 31,000P 14일로 갈립니다',
    'HANJW': '현금은 296,353원 135일(2027-07-02~11-12가 한 값으로 이어짐) · 281,535원 53일 · '
             '246,961원 30일 · 256,839원 18일 · 237,082원 18일 · 325,988원 16일(2027-03월 평일)이 '
             '기본이고, 2026-12-08 하루만 7,102,607원(창 안 최고가)이며 2027-01-12 1,185,414원 · '
             '2027-02-02 963,149원이 그 뒤를 잇습니다(최저는 2026-12-20 하루 212,386원). '
             '아워드 포인트는 43,000P 가 132일로 최빈·최고이고 42,000P 82일 · 39,000P 45일 · '
             '38,000P 16일 · 37,000P 13일로 갈리며, 2027-02-20 하루만 27,000P(창 안 최저)입니다',
    'PQCFI': '2027년 1분기 개관 예정(Opening Q1 2027 · 메리어트 신규 개관 안내)이라 '
             '2026-12-01~2027-11-30 365일이 현금·포인트 모두 미게시입니다(오픈 후 재실측이 필요합니다)',
    'HANBN': '원자료 실측에서 marriott.com 숙소 페이지가 404(미등록)이고 판매가 열려 있지 않아 '
             '2026-12-01~2027-11-30 365일이 현금·포인트 모두 미게시입니다'
             '(메리어트가 박닌 첫 5성급으로 예고한 호텔 — 등록·판매 개시 후 재실측이 필요합니다)',
}
WINDOW_END = {
    'PQCSR': '현금·포인트가 함께 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝'
             '(Rate Unavailable)이고, 포인트는 2026-12-01 이 비어 12-02 부터 시작합니다',
    'HANJW': '포인트가 2027-11-06 에 먼저 끊겨 2027-11-07~11-30 24일이 미게시이고(현금은 2027-11-12까지), '
             '현금·포인트 모두 2027-11-13~11-30 18일이 예약 창 끝(Rate Unavailable)입니다',
    'PQCFI': '개관 전이라 예약 창 자체가 열리지 않았습니다(예약 창 끝이 아니라 전 기간 미게시)',
    'HANBN': '페이지가 404(미등록)라 예약 창 자체가 열리지 않았습니다(예약 창 끝이 아니라 전 기간 미게시)',
}
# 도시 칸과 실제 소재지가 다른 호텔 — note 에 밝힌다
CITY_NOTE = {
    'HANBN': '박닌성 박닌 소재(하노이 인근)로, 원자료의 도시 칸(하노이)을 그대로 두었습니다',
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
        raise SystemExit('베트남 5차 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('region') != '베트남':
        raise SystemExit('원본 region %r (베트남 이어야 함)' % doc.get('region'))
    hotels = doc['hotels']
    if len(hotels) != 4:
        raise SystemExit('베트남 5차 원본 호텔 %d곳 (4곳이어야 함)' % len(hotels))
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
    if h['code'] in CITY_NOTE:
        notes.append(CITY_NOTE[h['code']])
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
    elif h['code'] == 'PQCFI':
        promo = '현금·아워드 포인트 미게시(%s 기준 · 365일) · 2027년 1분기 개관 예정' % DAY
        pt_src = '아워드 포인트 캘린더(%s 기준 · 365일 미게시)' % DAY
    else:
        promo = '현금·아워드 포인트 미게시(%s 기준 · 365일) · marriott.com 페이지 404(미등록)' % DAY
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
                   'No.7 실측 marriott_vietnam_batch5 베트남 5차 4곳 365일' % (DAY, pt_src)),
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

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 324곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (
        '2026-11-25 KST ③ 메리어트 베트남 5차 4곳 병합(324→328곳 · 베트남 20 · 통합 1,025곳) — '
        'PQCSR 쉐라톤 푸꾸옥 롱 비치 리조트(현금 325칸 · 포인트 336칸) · '
        'HANJW JW 메리어트 호텔 하노이(340 · 329) · '
        'PQCFI 페어필드 바이 메리어트 푸꾸옥 혼톰(0 · 0 — 2027년 1분기 개관 예정) · '
        'HANBN 박닌 메리어트 호텔(0 · 0 — marriott.com 페이지 404 미등록·미판매) 4곳'
        '(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 세전 현금·아워드 포인트 실측(2026-11-25 · '
        'No.7(@no_7) 전달본), 원자료 region 이 베트남이고 1~4차와 같이 지역 칸을 베트남으로 적음'
        '(카드에 「베트남 · 푸꾸옥」「베트남 · 하노이」), PQCFI·HANBN 은 현금·포인트 365일 모두 '
        '미게시(0칸 — 보간 없이 그대로 수록, NO_POINT_CODES 등록 · 재실측 대상), PQCSR 현금 '
        '158,055~814,972원(158,055원 149일 · 2026-12-01 하루만 814,972원 최고가) · 포인트 '
        '29,000~48,000P(29,000P 134일 · 48,000P 78일), HANJW 현금 212,386~7,102,607원'
        '(296,353원 135일 · 2026-12-08 하루만 7,102,607원 최고가 · 최저 2026-12-20 212,386원) · '
        '포인트 27,000~43,000P(43,000P 132일), PQCSR 은 현금·포인트가 함께 2027-11-12 까지이고, '
        'HANJW 는 포인트가 2027-11-06 에 먼저 끊겨 11-07~30 24일이 미게시(현금은 11-12까지), '
        '① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳(alsoIn·MAR_CROSS 추가 0쌍, '
        '1차 CXRJW↔h22 1쌍 그대로 77곳, ① 탭에 푸꾸옥·하노이 호텔 없음)'
        % (cash, pts))
    if '베트남 5차 4곳 병합' not in master.get('extended', ''):
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
