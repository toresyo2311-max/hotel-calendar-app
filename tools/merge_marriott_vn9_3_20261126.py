#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 베트남 9차(마지막) 3곳 병합 (340 → 343곳 · 베트남 32 → 35).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-26 No.7(@no_7) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/a03363f4-no71/pickle/2026-11-26-0128/received/0-marriott_vietnam_batch9.json
    — 3곳(SGNSI · SGNAK · SGNFI) 365일(2026-12-01~2027-11-30) 세전 현금 KRW + 아워드 포인트.
      파일의 region 은 `베트남` 이고, ③ 탭은 1~8차와 같이 국가 단위(베트남)로 적는다.

규칙:
  · 신규 3곳은 m341~m343(베트남 32→35)으로 메리어트 묶음 맨 뒤에 붙인다. 기존 340곳은 값·순서 그대로.
  · 국문명은 marriott.com/ko 공식 표기로 적는다 —
    SGNAK `빈펄 랜드마크 81, 오토그래프 컬렉션`(ko 페이지 「빈펄 랜드마크 81, 오토그래프 컬렉션에 오신
    것을 환영합니다」), SGNFI `페어필드 바이 메리어트 사우스 빈즈엉성`(ko 페이지 「페어필드 바이 메리어트
    사우스 빈즈엉성에 오신 것을 환영합니다」).
    SGNSI 는 marriott.com/ko 가 이 호텔의 한국어 페이지를 내지 않아(ko 호텔 목록에서 영어명 + `영어`
    표기 · /ko 호텔 상세 URL 은 /en-us 로 넘어감) 8차 SGNBS 와 같은 카드 관례(브랜드 + 사이공 + 고유명)
    로 `쉐라톤 사이공 그랜드 오페라 호텔` 로 적는다 — note 에 밝힌다.
  · SGNFI 는 원자료 도시 칸이 `호찌민` 이지만 공식 ko 페이지가 「빈즈엉성 투언안시」·주소
    「Vietnam-Singapore Industrial Park (VSIP), Binh Hoa Ward」로 적는 빈즈엉성(성) 소재라
    도시를 `빈즈엉` 으로 적는다(호찌민 시내에서 14.8km) — note 에 밝힌다.
  · 세 곳 모두 아워드 포인트 값이 있어 NO_POINT_CODES 등록 대상은 없다.
  · ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조한다 — 겹침이 있으면 alsoIn 양방향 +
    MAR_CROSS 를 반영해야 하므로, 이 스크립트는 겹침이 0곳이 아니면 멈춘다(수동 확인).
  · note 는 원자료 값에서 확인되는 사실만 적는다 — 일수·값 범위·결번 구간·창 끝·null 보간 없음.
    세금·수수료 별도(세전) 기준임을 밝힌다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/a03363f4-no71/pickle/2026-11-26-0128/received/'
       '0-marriott_vietnam_batch9.json')
DAY = '2026-11-26'
FIRST = 341                       # m341~m343
CODES = ('SGNSI', 'SGNAK', 'SGNFI')
REGION = '베트남'
# 원자료 브랜드 → 카드 표기(③ 탭 기존 표기 그대로)
BRAND = {'SGNSI': '쉐라톤', 'SGNAK': '오토그래프 컬렉션', 'SGNFI': '페어필드 바이 메리어트'}
# marriott.com/ko 공식 한국어명(SGNSI 는 ko 한국어 페이지 없음 — 기존 카드 관례)
NAME = {'SGNSI': '쉐라톤 사이공 그랜드 오페라 호텔',
        'SGNAK': '빈펄 랜드마크 81, 오토그래프 컬렉션',
        'SGNFI': '페어필드 바이 메리어트 사우스 빈즈엉성'}
CITY = {'SGNSI': '호찌민', 'SGNAK': '호찌민', 'SGNFI': '빈즈엉'}
# ① 호텔럭스와 같은 호텔 — 코드 → (① 호텔럭스 id, ① 탭 표기). ① 탭 161곳에 호찌민·빈즈엉 호텔이 없다
TWIN = {}
# 아워드 포인트 캘린더 365일 미게시(0칸) — 세 곳 모두 포인트 값이 있어 대상 없음
ZERO_POINT = set()
# 호텔별 특이사항 — 원자료 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'SGNSI': '현금은 321,049원이 247일로 기본이고 246,961원 22일 · 311,171원 20일 · 281,535원 14일이 '
             '그 뒤를 잇습니다. 246,961원 22일(2027-01-29~02-21)이 창 안 최저, 2026-12-31 하루만 '
             '740,883원 · 2026-12-30 444,530원이고, 2027-03-11 하루만 3,398,187원으로 창 안 최고가입니다'
             '(다른 날의 10배 이상 — No.7 이 DOM `.price-section` 재확인으로 실제 표시값임을 검증했고 '
             '같은 날 포인트는 미게시). 아워드 포인트는 44,000P 85일 · 37,000P 51일 · 40,000P 31일 · '
             '38,000P 30일로 갈리며 31,000P 3일(2027-02-13 · 2027-07-10~07-11)이 창 안 최저입니다. '
             'marriott.com/ko 는 이 호텔의 한국어 페이지를 내지 않아(ko 호텔 목록에 영어명 + `영어` 표기, '
             '/ko 호텔 상세 주소는 /en-us 로 넘어감) 국문명은 8차 SGNBS 와 같은 기존 카드 관례'
             '(브랜드 + 사이공 + 고유명)로 `쉐라톤 사이공 그랜드 오페라 호텔`로 적었습니다(공식 영문명 '
             'Sheraton Saigon Grand Opera Hotel · 주소 88 Dong Khoi, Saigon Ward).',
    'SGNAK': '현금은 261,778원이 232일로 기본이고 246,961원 35일 · 296,353원 30일 · 271,657원 18일이 '
             '그 뒤를 잇습니다. 246,961원 35일(2026-12-07 · 12-11~12-20 · 2027-01-29~02-03 · 02-06~02-21 · 02-27~02-28)이 창 안 최저, 2026-12-31 하루만 '
             '740,883원(창 안 최고가) · 2026-12-30 493,922원입니다. 아워드 포인트는 44,000P 110일 · '
             '42,000P 51일 · 41,000P 49일 · 43,000P 43일로 갈리며 34,000P 3일(2027-05-10 · 05-12 · '
             '09-12)이 창 안 최저입니다. 공식 ko 페이지「빈펄 랜드마크 81, 오토그래프 컬렉션」 · 주소 '
             '720A Dien Bien Phu, Thanh My Tay ward(빈홈 센트럴 파크 레지던스 내 · 랜드마크 81).',
    'SGNFI': '현금은 86,436원 135일 · 81,497원 133일 · 91,375원 45일 · 83,966원 25일이 기본이고 '
             '81,497원 133일(2026-12-18~12-31 · 2027-01~10 주말 중심)이 창 안 최저, 2027-03-09 하루만 110,742원(창 안 '
             '최고가) · 2026-12-03 96,314원입니다. 아워드 포인트는 13,500P 97일 · 20,500P 44일 · '
             '17,000P 23일 · 14,000P 23일 · 18,000P 22일로 갈리며 13,500P 97일이 창 안 최저입니다. '
             '공식 ko 페이지「페어필드 바이 메리어트 사우스 빈즈엉성」 · 주소 No 5 Huu Nghi Avenue, '
             'Vietnam-Singapore Industrial Park (VSIP), Binh Hoa Ward 이고 페이지 본문이 「빈즈엉성 '
             '투언안시」·「WTC Binh Duong New City 인근」으로 적습니다(공식 목록에서도 '
             '호찌민 시내에서 14.8km로 표시).',
}
WINDOW_END = {
    'SGNSI': '현금·포인트가 함께 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝입니다',
    'SGNAK': '현금·포인트가 함께 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝입니다',
    'SGNFI': '현금·포인트가 함께 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝입니다',
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
        raise SystemExit('베트남 9차 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('region') != '베트남':
        raise SystemExit('원본 region %r (베트남 이어야 함)' % doc.get('region'))
    hotels = doc['hotels']
    if len(hotels) != 3:
        raise SystemExit('베트남 9차 원본 호텔 %d곳 (3곳이어야 함)' % len(hotels))
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

    english = h['english'].strip()
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
                   'No.7 실측 marriott_vietnam_batch9 베트남 9차 3곳 365일' % (DAY, pt_src)),
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

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 340곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (
        '2026-11-26 KST ③ 메리어트 베트남 9차(마지막) 3곳 병합(340→343곳 · 베트남 35 · 통합 1,040곳) — '
        'SGNSI 쉐라톤 사이공 그랜드 오페라 호텔(현금 346칸 · 포인트 343칸) · '
        'SGNAK 빈펄 랜드마크 81, 오토그래프 컬렉션(347 · 341) · '
        'SGNFI 페어필드 바이 메리어트 사우스 빈즈엉성(347 · 347) 3곳'
        '(현금 %d칸 · 포인트 %d칸 / 3×365=1,095칸) 365일 세전 현금·아워드 포인트 실측(2026-11-26 · '
        'No.7(@no_7) 전달본) — 이로써 베트남 35곳(1~9차) 전량 반영, 원자료 국문명'
        '(`쉐라톤 호찌민 Saigon Grand Opera`·`오토그래프 컬렉션 호찌민 Vinpearl Landmark 81`·'
        '`페어필드 바이 메리어트 호찌민 South Binh Duong`)은 marriott.com/ko 공식 표기로 바로잡음'
        '(SGNSI 는 ko 한국어 페이지가 없어 카드 관례), SGNFI 는 실제 소재지인 빈즈엉으로 도시 구분, '
        'SGNSI 2027-03-11 하루만 3,398,187원(DOM 재확인) · 2026-12-31 740,883원, '
        'SGNAK 현금 246,961~740,883원(2026-12-31 하루만 740,883원) · 포인트 34,000~44,000P, '
        'SGNFI 현금 81,497~110,742원(2027-03-09 하루만 110,742원) · 포인트 13,500~20,500P, '
        '세 곳 모두 2027-11-12 까지여서 예약 창 끝이 11-13~30(18일), ① 호텔럭스 161곳과 코드·영문명·'
        '국문명·도시 전수 대조 — 겹침 0곳(alsoIn·MAR_CROSS 추가 0쌍, 1차 CXRJW↔h22 1쌍 그대로 77곳, '
        '① 탭에 호찌민·빈즈엉 호텔 없음)'
        % (cash, pts))
    if '베트남 9차' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + ' / ' + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 3곳 현금 %d칸 · 포인트 %d칸)' % (
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
