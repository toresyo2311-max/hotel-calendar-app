#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 베트남 1차 4곳 병합 (308 → 312곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py refresh` → `inject`).

입력(2026-11-25 No.7(@no_7) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/a03363f4-no71/pickle/2026-11-25-2122/received/0-marriott_vietnam_batch1.json
    — 4곳(CXRJW · CXRWI · VCASI · VCALM) 365일(2026-12-01~2027-11-30) 세전 현금 KRW + 아워드 포인트.
      파일의 region 은 `동남아` 인데, ③ 탭은 한국·일본·대만처럼 국가 단위로 묶고 ② 아코르도
      베트남을 `베트남` 으로 두므로 카드 region 은 `베트남` 으로 적는다(도시 칸이 깜라인·껀터라
      카드에는 「베트남 · 깜라인」처럼 국가와 도시가 함께 보인다).

규칙:
  · 신규 4곳은 m309~m312(베트남 0→4)로 메리어트 묶음 맨 뒤에 붙인다. 기존 308곳은 값·순서 그대로.
  · CXRJW(JW 메리어트 깜라인 Bay)는 ① 호텔럭스 h22(JW 메리어트 캄란 베이 리조트 앤 스파)와
    같은 호텔이라 alsoIn 을 양방향으로 잇고(요금 출처가 달라 두 탭 모두 수록), 나머지 3곳은
    ① 탭 161곳과 코드·영문명·국문명·도시를 전수 대조해 겹침이 없다.
  · note 는 원자료 값에서 확인되는 사실만 적는다 — 일수·값 범위·결번 구간·창 끝·null 보간 없음.
    세금·수수료 별도(세전) 기준임을 밝힌다.
  · 영문명 끝의 `®` 는 기존 카드 표기(161+536+308곳 모두 ® 없음)에 맞춰 떼고 싣는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/a03363f4-no71/pickle/2026-11-25-2122/received/'
       '0-marriott_vietnam_batch1.json')
DAY = '2026-11-25'
FIRST = 309                       # m309~m312
CODES = ('CXRJW', 'CXRWI', 'VCASI', 'VCALM')
REGION = '베트남'
# ① 호텔럭스와 같은 호텔 — 코드 → (① 호텔럭스 id, 원자료 국문명과 다른 ① 탭 표기)
TWIN = {'CXRJW': ('h22', 'JW 메리어트 캄란 베이 리조트 앤 스파')}
# 호텔별 특이사항 — 원자료 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'CXRJW': '2027-02-05~02-14 뗏 연휴 10일이 518,618원 이상으로 올라가고 그중 2027-02-07 하루만 '
             '1,210,110원(창 안 최고가)이며 그날 아워드 포인트만 미게시입니다. 현금은 321,049원 87일 · '
             '370,441원 61일 · 311,171원 47일이 기본이고, 아워드 포인트는 48,000P 58일 · 52,000P 53일 · '
             '49,000P 50일이 기본에 61,000P 가 42일(2026-12-24~12-29 6일 연속 포함)입니다',
    'CXRWI': '2027-02-06~02-11 6일 연속 296,353원이 창 안 최고가(뗏 연휴)이고 177,812원이 95일로 가장 '
             '흔합니다. 아워드 포인트는 41,000P 62일 · 37,000P 38일 · 29,000P 37일로 갈립니다',
    'VCASI': '현금은 다섯 값뿐으로 88,906원 310일 · 96,314원 22일 · 101,254원 10일 · 91,375원 3일 · '
             '106,193원 2일(2027-01-01~01-02 가 창 안 최고가)이고, 아워드 포인트는 29,000P 161일 · '
             '30,000P 63일 · 41,000P 52일(2026-12-05~2027-02-08 연말·뗏 구간 중심)입니다',
    'VCALM': '2026-12-28 하루만 1,264,441원(창 안 최고가)이고 그날과 2027-01-02 는 아워드 포인트만 '
             '미게시입니다. 2027-04-01~10-24 207일이 212,386원 한 값(창 안 최저가)으로 평탄합니다',
}
WINDOW_END = {
    'CXRJW': '현금·포인트가 함께 2027-11-06 에 끊겨 2027-11-07~11-30 24일이 값 없이 끝납니다'
             '(예약 창 끝 11-13 보다 6일 이릅니다)',
    'CXRWI': '현금은 2027-11-12 까지이고 아워드 포인트는 2027-11-06 에 먼저 끊겨 2027-11-07~11-30 24일이 '
             '미게시입니다(예약 창 끝 11-13 보다 6일 이릅니다)',
    'VCASI': '현금·포인트가 함께 2027-11-12 에 끊겨 2027-11-13~11-30 18일이 예약 창 끝(Rate Unavailable)입니다',
    'VCALM': '현금·포인트가 함께 2027-10-24 에 끊겨 2027-10-25~11-30 37일이 값 없이 끝납니다'
             '(예약 창 끝 11-13 보다 19일 이릅니다)',
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
        raise SystemExit('베트남 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('region') != '베트남':
        raise SystemExit('원본 region %r (베트남 여야 함)' % doc.get('region'))
    hotels = doc['hotels']
    if len(hotels) != 4:
        raise SystemExit('베트남 원본 호텔 %d곳 (4곳이어야 함)' % len(hotels))
    if tuple(h['code'] for h in hotels) != CODES:
        raise SystemExit('원본 코드 순서가 다름: %s' % [h['code'] for h in hotels])
    for h in hotels:
        if h['country'] != '베트남':
            raise SystemExit('%s 국가 %s (베트남 이어야 함)' % (h['code'], h['country']))
        if h.get('region') != '동남아':
            raise SystemExit('%s region %r (동남아 여야 함)' % (h['code'], h.get('region')))
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
        'brand': h['brand'],
        'city': h['city'],
        'region': REGION,
        'name': h['name'],
        'english': english,
        'promotion': '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days),
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
                   '아워드 포인트 캘린더(%s 기준) · No.7 실측 marriott_vietnam_batch1 '
                   '베트남 1차 4곳 365일' % (DAY, DAY)),
        'code': h['code'],
        'rates': rates,
        'points': pt_map,
        'note': ' · '.join(notes),
    }


def crosscheck_lux(master, hotels):
    """① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조."""
    lux = [x for x in master['hotels'] if x.get('group') == 'lux']
    lcodes = {x.get('code') for x in lux if x.get('code')}
    lenames = {(x.get('english') or '').strip().lower() for x in lux}
    lnames = {x.get('name') for x in lux}
    hits = []
    for h in hotels:
        eng = h['english'].replace('®', '').strip().lower()
        if h['code'] in lcodes or eng in lenames or h['name'] in lnames:
            hit = [x for x in lux
                   if x.get('code') == h['code']
                   or (x.get('english') or '').strip().lower() == eng
                   or x.get('name') == h['name']]
            hits.append((h['code'], [(x['id'], x['name']) for x in hit]))
    return len(lux), hits, sorted({x.get('city') for x in lux})


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
    print('   ① 탭 도시: %s' % ', '.join(lux_cities))
    if len(lux_hits) != len(TWIN):
        raise SystemExit('① 탭 겹침 %d곳 (기대 %d곳 — alsoIn 연결 여부를 먼저 정하세요)'
                          % (len(lux_hits), len(TWIN)))
    for code, hit in lux_hits:
        want = TWIN.get(code)
        if not want or hit != [want]:
            raise SystemExit('%s ① 탭 짝이 %s (기대 %s)' % (code, hit, want))

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

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 308곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (
        '2026-11-25 KST ③ 메리어트 베트남 1차 4곳 병합(308→312곳 · 베트남 4 · 통합 1,009곳) — '
        'CXRJW JW 메리어트 깜라인 Bay(현금 341칸 · 포인트 340칸) · CXRWI 웨스틴 깜라인(347 · 341) · '
        'VCASI 쉐라톤 껀터(347 · 347) · VCALM 오토그래프 컬렉션 껀터 Legacy Mekong(328 · 326) 4곳'
        '(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 세전 현금·아워드 포인트 실측'
        '(2026-11-25 · No.7(@no_7) 전달본), 원자료 region 은 동남아이나 ③ 탭은 국가 단위로 묶어 '
        '지역 칸을 베트남으로 적음(② 아코르와 같은 표기 — 카드에 「베트남 · 깜라인」), '
        'CXRJW 는 ① 호텔럭스 h22(JW 메리어트 캄란 베이 리조트 앤 스파)와 같은 호텔이라 alsoIn 양방향 '
        '연결(나머지 3곳은 ① 탭 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳), '
        'CXRJW 현금 281,535~1,210,110원(결번 24일 2027-11-07~11-30 · 2027-02-07 하루가 최고가이고 '
        '그날 포인트만 미게시) · 포인트 46,000~61,000P(결번 25일 2027-02-07 · 2027-11-07~11-30), '
        'CXRWI 현금 158,055~296,353원 · 포인트 29,000~41,000P(포인트만 2027-11-07~11-30 24일 미게시), '
        'VCASI 현금 88,906~106,193원 · 포인트 29,000~41,000P(둘 다 2027-11-13~11-30 18일 예약 창 끝), '
        'VCALM 현금 212,386~1,264,441원 · 포인트 35,000~48,000P(2026-12-28 1,264,441원 최고가 · '
        '2027-04-01~10-24 207일 212,386원 평탄 · 현금·포인트 함께 2027-10-25~11-30 37일 값 없음)'
        % (cash, pts))
    if '베트남 1차 4곳 병합' not in master.get('extended', ''):
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
