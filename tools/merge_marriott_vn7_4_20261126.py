#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 베트남 7차 4곳 병합 (332 → 336곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-25 No.7(@no_7) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/a03363f4-no71/pickle/2026-11-26-0023/received/0-marriott_vietnam_batch7.json
    — 4곳(HPHSI · DADHA · DADMC · SGNJS) 365일(2026-12-01~2027-11-30) 세전 현금 KRW + 아워드 포인트.
      파일의 region 은 `베트남` 이고, ③ 탭은 1~6차와 같이 국가 단위(베트남)로 적는다.

규칙:
  · 신규 4곳은 m333~m336(베트남 24→28)으로 메리어트 묶음 맨 뒤에 붙인다. 기존 332곳은 값·순서 그대로.
  · 국문명은 marriott.com/ko 공식 표기로 적는다 — HPHSI `쉐라톤 하이퐁`,
    DADHA `르네상스 다낭 호이안 리조트 앤 스파`(ko 페이지 「르네상스 다낭 호이안 리조트 & 스파에 오신 것을
    환영합니다」), DADMC `호이안 메리어트 리조트 앤 스파`(ko 첫 화면 신규 오픈 호텔 목록 `호이안 메리어트
    리조트 & 스파`), SGNJS `JW 메리어트 호텔 앤 스위트 사이공`(ko 페이지 「JW 메리어트 호텔 & 스위트
    사이공에 오신 것을 환영합니다」). 원자료 국문명(`르네상스 호이안 Danang` · `메리어트 호이안` ·
    `JW 메리어트 호찌민 Saigon`)은 잘려 와 공식 표기로 바로잡는다.
  · DADHA 는 현금이 2027-09-04 까지이고, 포인트는 2026-12~2027-01 두 달(62일)만 표출된 뒤
    2027-02-01~11-30 303일이 미게시다 — note·주의문에 밝힌다(보간하지 않는다).
  · DADMC 는 2026-12-15 개관 예정(공식 페이지 Special Opening Offer 「Stay from December 15, 2026」)이라
    2026-12-01~12-14 14일이 개관 전 미게시다 — note·주의문에 밝힌다.
  · ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조한다 — 겹침이 있으면 alsoIn 양방향 +
    MAR_CROSS 를 반영해야 하므로, 이 스크립트는 겹침이 0곳이 아니면 멈춘다(수동 확인).
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

SRC = ('/workspace/memory/clones/a03363f4-no71/pickle/2026-11-26-0023/received/'
       '0-marriott_vietnam_batch7.json')
DAY = '2026-11-25'
FIRST = 333                       # m333~m336
CODES = ('HPHSI', 'DADHA', 'DADMC', 'SGNJS')
REGION = '베트남'
# 원자료 브랜드 → 카드 표기
BRAND = {'HPHSI': '쉐라톤', 'DADHA': '르네상스',
         'DADMC': '메리어트', 'SGNJS': 'JW 메리어트'}
# marriott.com/ko 공식 한국어명(앱 표기는 & 를 「앤」 으로 적는 기존 카드 관습을 따른다)
NAME = {'HPHSI': '쉐라톤 하이퐁',
        'DADHA': '르네상스 다낭 호이안 리조트 앤 스파',
        'DADMC': '호이안 메리어트 리조트 앤 스파',
        'SGNJS': 'JW 메리어트 호텔 앤 스위트 사이공'}
CITY = {'HPHSI': '하이퐁', 'DADHA': '호이안', 'DADMC': '호이안', 'SGNJS': '호찌민'}
# ① 호텔럭스와 같은 호텔 — 코드 → (① 호텔럭스 id, ① 탭 표기). ① 탭 161곳에 하이퐁·호이안·호찌민 호텔이 없다
TWIN = {}
# 호텔별 특이사항 — 원자료 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'HPHSI': '현금은 93,845원 245일(2026-12-21 이후 기본값) · 98,784원 49일 · 108,662원 17일 · '
             '103,723원 14일이 기본이고 88,906원 8일(2026-12-04~12-05 · 12-11~12-13 · 12-18~12-20)이 '
             '창 안 최저, 2026-12-08 하루만 251,900원(창 안 최고가)이며 2026-12-06 · 2027-03-15 · '
             '2027-07-12 사흘이 138,298원입니다. 아워드 포인트는 23,000P 가 134일로 최빈이고 '
             '26,000P 48일 · 24,500P 41일 · 22,000P 31일 · 21,500P 23일로 갈리며, '
             '19,500P 8일(2026-12-25 · 12-27 · 2027-09-10~12 등)이 창 안 최저입니다',
    'DADHA': '현금은 공식 달력 기준 2027-09-04 까지만 값이 있고 2027-09-05~11-30 87일은 미게시입니다. '
             '113,602원 64일 · 111,132원 53일 · 108,662원 43일 · 118,541원 43일 · 107,675원 28일이 '
             '기본이고 98,784원 4일(2026-12-09~12-12)이 창 안 최저, 2026-12-31 하루만 177,812원으로 '
             '최고이며 2027-01-01 162,994원 · 2026-12-26·12-29·12-30 사흘 158,055원이 그 뒤를 잇습니다. '
             '아워드 포인트는 2026-12-01~2027-01-31 두 달 62일만 표출되고 2027-02-01~11-30 303일은 '
             '미게시이며, 값은 31,200P 14일 · 30,400P 13일 · 29,600P 9일(최저) · 52,000P 9일'
             '(2026-12-24~2027-01-01 최고)로 갈립니다',
    'DADMC': '2026-12-15 개관 예정이라 개관 전인 2026-12-01~12-14 14일은 현금·포인트 모두 미게시입니다'
             '(공식 페이지 Special Opening Offer 「Stay from December 15, 2026」). '
             '현금은 177,812원 186일이 기본이고 207,447원 64일 · 217,325원 25일 · 187,690원 18일 · '
             '197,569원 13일이며, 개관일부터 2026-12-20 엿새가 172,872원(창 안 최저), '
             '2026-12-29~12-31 사흘만 246,961원(창 안 최고)입니다. 아워드 포인트는 37,000P 가 107일로 '
             '최빈·최저이고 50,000P 43일 · 39,000P 30일 · 43,000P 30일 · 44,000P 27일로 갈립니다',
    'SGNJS': '현금은 296,353원 92일(창 안 최저) · 335,867원 83일 · 395,138원 58일 · 345,745원 42일이 '
             '기본이고, 2027년 3월이 444,530원 19일로 높으며 2026-12-31 하루만 790,276원(창 안 최고가) · '
             '2026-12-30 493,922원 · 2027-03-16 563,071원입니다. 아워드 포인트는 32,000P 가 71일로 '
             '최빈·최저이고 33,600P 60일 · 34,400P 41일 · 44,800P 32일 · 36,800P 24일로 갈리며, '
             '2026-12월 초 56,000P 9일이 창 안 최고입니다',
}
WINDOW_END = {
    'HPHSI': '현금은 2027-11-06 까지이고 포인트가 2027-11-07~11-30 24일 미게시여서, '
             '현금·포인트 모두 2027-11-07~11-30 24일이 예약 창 끝입니다',
    'DADHA': '현금은 2027-09-04 까지 · 포인트는 2027-01-31 까지이고, 그 뒤는 위에 적은 대로 '
             '미게시(2027-11-07~11-30 24일은 예약 창 끝)입니다',
    'DADMC': '현금·포인트가 함께 2027-11-06 까지여서 2027-11-07~11-30 24일이 예약 창 끝입니다',
    'SGNJS': '현금·포인트가 함께 2027-11-06 까지여서 2027-11-07~11-30 24일이 예약 창 끝입니다',
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
        raise SystemExit('베트남 7차 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('region') != '베트남':
        raise SystemExit('원본 region %r (베트남 이어야 함)' % doc.get('region'))
    hotels = doc['hotels']
    if len(hotels) != 4:
        raise SystemExit('베트남 7차 원본 호텔 %d곳 (4곳이어야 함)' % len(hotels))
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
        h['code'], h['country'], CITY[h['code']], cash_days, pt_days)]
    notes.append('현금 (세전) %s~%s원' % (format(min(cash_vals), ','), format(max(cash_vals), ',')))
    notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))

    cash_gap_days = [d for d, v in rates.items() if not isinstance(v, (int, float))]
    pt_gap_days = [d for d, v in pt_map.items() if not isinstance(v, int)]
    cash_gap = ranges(cash_gap_days)
    pt_gap = ranges(pt_gap_days)
    if cash_gap:
        notes.append('현금 결번 %d일 %d개 구간(%s)' % (
            len(cash_gap_days), len(cash_gap), ' · '.join(cash_gap)))
    if pt_gap:
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

    english = h['english'].replace('®', '').strip()
    if english.endswith(','):
        english = english[:-1].strip()
    promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days)
    pt_src = '아워드 포인트 캘린더(%s 기준)' % DAY
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
                   'No.7 실측 marriott_vietnam_batch7 베트남 7차 4곳 365일' % (DAY, pt_src)),
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

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 332곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (
        '2026-11-26 KST ③ 메리어트 베트남 7차 4곳 병합(332→336곳 · 베트남 28 · 통합 1,033곳) — '
        'HPHSI 쉐라톤 하이퐁(현금 341칸 · 포인트 338칸) · DADHA 르네상스 다낭 호이안 리조트 앤 스파'
        '(278 · 62) · DADMC 호이안 메리어트 리조트 앤 스파(327 · 326) · '
        'SGNJS JW 메리어트 호텔 앤 스위트 사이공(341 · 338) 4곳'
        '(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 세전 현금·아워드 포인트 실측(2026-11-25 · '
        'No.7(@no_7) 전달본), 원자료 국문명(`르네상스 호이안 Danang`·`메리어트 호이안`·'
        '`JW 메리어트 호찌민 Saigon`)은 잘려 와 marriott.com/ko 공식 표기로 바로잡음, '
        'DADHA 현금 98,784~177,812원(2027-09-04까지 · 2027-09-05~11-30 87일 미게시) · '
        '포인트 29,600~52,000P(2026-12~2027-01 62일만 표출 · 2027-02-01~11-30 303일 미게시), '
        'DADMC 2026-12-15 개관 예정으로 12-01~12-14 14일 개관 전 미게시(현금 172,872~246,961원 · '
        '포인트 37,000~50,000P), HPHSI 현금 88,906~251,900원(2026-12-08 하루만 251,900원) · '
        '포인트 19,500~26,000P(23,000P 134일), SGNJS 현금 296,353~790,276원(2026-12-31 하루만 '
        '790,276원) · 포인트 32,000~56,000P, 네 곳 모두 2027-11-07~11-30 24일이 예약 창 끝, '
        '① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳(alsoIn·MAR_CROSS 추가 0쌍, '
        '1차 CXRJW↔h22 1쌍 그대로 77곳, ① 탭에 하이퐁·호이안·호찌민 호텔 없음)'
        % (cash, pts))
    if '베트남 7차 4곳 병합' not in master.get('extended', ''):
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
