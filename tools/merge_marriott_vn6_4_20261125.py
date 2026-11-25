#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 베트남 6차 4곳 병합 (328 → 332곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-25 No.7(@no_7) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/a03363f4-no71/pickle/2026-11-25-2341/received/0-marriott_vietnam_batch6.json
    — 4곳(HANHS · HANSW · HANHP · HANLP) 365일(2026-12-01~2027-11-30) 세전 현금 KRW + 아워드 포인트.
      파일의 region 은 `베트남` 이고, ③ 탭은 1~5차와 같이 국가 단위(베트남)로 적는다.

규칙:
  · 신규 4곳은 m329~m332(베트남 20→24)로 메리어트 묶음 맨 뒤에 붙인다. 기존 328곳은 값·순서 그대로.
  · 국문명은 marriott.com/ko 공식 표기로 적는다 — HANHS `쉐라톤 하노이 호텔`, HANSW `쉐라톤 하노이 웨스트`,
    HANHP `포 포인츠 바이 쉐라톤 하장`, HANLP `포 포인츠 바이 쉐라톤 랑선`. 원자료의
    `포인트 하노이 Ha Giang` · `포인트 하노이 Lang Son` 은 이름이 잘려 왔고 도시도 하노이로 적혀 있어
    (하장은 하노이에서 약 300km · 랑선은 약 150km 떨어진 성도시) 도시 칸을 하장 · 랑선으로 바로잡는다.
  · HANSW 는 2026-12-01 · 2026-12-17 두 날에 스위트만 남아 1박 284만·265만 원의 고가가 실측됐다
    — 그 두 날의 값은 다른 날(15~27만 원)과 자릿수가 다르므로 note 에 밝힌다(보간·제외하지 않는다).
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

SRC = ('/workspace/memory/clones/a03363f4-no71/pickle/2026-11-25-2341/received/'
       '0-marriott_vietnam_batch6.json')
DAY = '2026-11-25'
FIRST = 329                       # m329~m332
CODES = ('HANHS', 'HANSW', 'HANHP', 'HANLP')
REGION = '베트남'
# 원자료 브랜드 → 카드 표기
BRAND = {'HANHS': '쉐라톤', 'HANSW': '쉐라톤',
         'HANHP': '포 포인츠 바이 쉐라톤', 'HANLP': '포 포인츠 바이 쉐라톤'}
NAME = {'HANHS': '쉐라톤 하노이 호텔',
        'HANSW': '쉐라톤 하노이 웨스트',
        'HANHP': '포 포인츠 바이 쉐라톤 하장',
        'HANLP': '포 포인츠 바이 쉐라톤 랑선'}
# 원자료 도시 칸 → 카드 도시 (HANHP·HANLP 원자료의 `하노이` 는 잘못된 표기)
CITY = {'HANHS': '하노이', 'HANSW': '하노이', 'HANHP': '하장', 'HANLP': '랑선'}
# ① 호텔럭스와 같은 호텔 — 코드 → (① 호텔럭스 id, ① 탭 표기). ① 탭 161곳에 하노이·하장·랑선 호텔이 없다
TWIN = {}
# 호텔별 특이사항 — 원자료 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'HANHS': '현금은 158,055원 77일(2027-02-19~02-21 · 02-26 · 02-28 · 04-04 · 04-10~04-11 등 주말·비수기에 산발) · '
             '197,569원 74일 · 167,933원 26일(2027-01-29~02-14 포함) · 271,657원 27일(2026-12-25 · '
             '2027-10-18~11-12가 한 값)이 기본이고, 2026-12-16 하루만 617,403원(창 안 최고가)이며 '
             '2026-12-08 587,507원 · 2026-12-10 571,910원 · 2026-12-28 568,011원이 그 뒤를 잇습니다. '
             '아워드 포인트는 31,500P 가 120일로 최빈·최고이고 30,500P 53일 · 30,000P 45일 · '
             '31,000P 24일로 갈리며, 2027-02-05~02-07 사흘만 22,500P(창 안 최저)입니다',
    'HANSW': '현금은 246,961원 78일 · 180,281원 64일 · 187,690원 55일 · 170,403원 26일이 기본이고 '
             '155,585원 20일이 최저(2027-02-05~02-14 · 02-19~02-21 등)입니다. '
             '2026-12-01 2,840,055원 · 2026-12-17 2,652,364원 두 날은 다른 날의 10배가 넘는데, '
             '원자료 실측에서 그 두 날만 스위트가 남아 스위트 요금이 잡힌 값입니다'
             '(나머지 날은 15~27만 원대 — 보간·제외하지 않고 실측값 그대로 실었습니다). '
             '아워드 포인트는 26,500P 가 95일로 최빈이고 30,000P 44일 · 27,000P 40일 · 31,000P 30일이며 '
             '22,000P 가 2027-01-31 · 2027-02-05 이틀의 최저입니다',
    'HANHP': '하장성 하장시 소재(하노이에서 약 300km)입니다. '
             '현금은 2026-12-01~12-31 31일이 75,351원, 2027-01-01~11-12 316일이 73,981원으로 한 값씩 '
             '이어지고(창 안 73,981~75,351원), 아워드 포인트는 17,500P 가 298일로 최빈·최저 · '
             '2026-12월 31일이 18,500P · 2027-10-26~11-12 18일만 22,000P 입니다',
    'HANLP': '랑선성 랑선시 소재(하노이에서 약 150km)입니다. '
             '현금은 2026-12월 31일이 62,720원(창 안 최저) · 2027-01-01~02-26 과 2027-03-07~11-12 '
             '308일이 65,856원이고, 2027-02-27~03-06 여드레만 277,109원(창 안 최고가)입니다. '
             '아워드 포인트는 16,500P 가 291일로 최빈 · 2026-12월 28일이 14,500P(창 안 최저) · '
             '2027-02-27~03-06 여드레와 2027-10-26~11-12 18일이 22,000P 입니다',
}
WINDOW_END = {
    'HANHS': '현금은 2027-11-12 까지이고 포인트는 2027-11-06 에 먼저 끊겨 2027-11-07~11-30 24일이 '
             '미게시이며, 현금·포인트 모두 2027-11-13~11-30 18일이 예약 창 끝(Rate Unavailable)입니다',
    'HANSW': '현금·포인트가 함께 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝'
             '(Rate Unavailable)입니다',
    'HANHP': '현금·포인트가 함께 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝'
             '(Rate Unavailable)입니다',
    'HANLP': '현금·포인트가 함께 2027-11-12 까지여서 2027-11-13~11-30 18일이 예약 창 끝'
             '(Rate Unavailable)입니다',
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
        raise SystemExit('베트남 6차 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('region') != '베트남':
        raise SystemExit('원본 region %r (베트남 이어야 함)' % doc.get('region'))
    hotels = doc['hotels']
    if len(hotels) != 4:
        raise SystemExit('베트남 6차 원본 호텔 %d곳 (4곳이어야 함)' % len(hotels))
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
                   'No.7 실측 marriott_vietnam_batch6 베트남 6차 4곳 365일' % (DAY, pt_src)),
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

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 328곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (
        '2026-11-25 KST ③ 메리어트 베트남 6차 4곳 병합(328→332곳 · 베트남 24 · 통합 1,029곳) — '
        'HANHS 쉐라톤 하노이 호텔(현금 344칸 · 포인트 299칸) · HANSW 쉐라톤 하노이 웨스트(345 · 343) · '
        'HANHP 포 포인츠 바이 쉐라톤 하장(347 · 347) · HANLP 포 포인츠 바이 쉐라톤 랑선(347 · 347) 4곳'
        '(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 세전 현금·아워드 포인트 실측(2026-11-25 · '
        'No.7(@no_7) 전달본), 원자료 region 이 베트남이고 1~5차와 같이 지역 칸을 베트남으로 적음'
        '(카드에 「베트남 · 하노이」「베트남 · 하장」「베트남 · 랑선」), 원자료 국문명 `포인트 하노이 '
        'Ha Giang`·`포인트 하노이 Lang Son` 은 잘려 와 marriott.com/ko 공식 표기 `포 포인츠 바이 '
        '쉐라톤 하장`·`포 포인츠 바이 쉐라톤 랑선` 으로 바로잡고 도시 칸도 하장·랑선으로 고침, '
        'HANSW 2026-12-01 2,840,055원·2026-12-17 2,652,364원 은 스위트만 남은 두 날의 실측값, '
        'HANHS 현금 158,055~617,403원(158,055원 77일 · 2026-12-16 하루만 617,403원 최고가) · '
        '포인트 22,500~31,500P(31,500P 120일), HANSW 현금 155,585~2,840,055원 · 포인트 22,000~31,000P, '
        'HANHP 현금 73,981~75,351원 · 포인트 17,500~22,000P, HANLP 현금 62,720~277,109원'
        '(2027-02-27~03-06 여드레만 277,109원) · 포인트 14,500~22,500P, 네 곳 모두 2027-11-13~30 18일이 '
        '예약 창 끝이고 HANHS 는 포인트가 2027-11-06 에 먼저 끊김(현금 11-12까지), '
        '① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳(alsoIn·MAR_CROSS 추가 0쌍, '
        '1차 CXRJW↔h22 1쌍 그대로 77곳, ① 탭에 하노이·하장·랑선 호텔 없음)'
        % (cash, pts))
    if '베트남 6차 4곳 병합' not in master.get('extended', ''):
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
