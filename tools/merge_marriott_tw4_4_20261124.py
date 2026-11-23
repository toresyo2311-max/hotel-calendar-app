#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 대만 4차 4곳 병합 (291 → 295곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py refresh` → `inject`).

입력(2026-11-24 6번(@jin_6) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/146dd4d1-jin_6/pickle/2026-11-24-0617/received/
      0-marriott-wave1-tw-hk-mo-47.json — 누적 15곳 가운데 **뒤 4곳**
      (앞 11곳 KHHGM·KHHLC·KHHMC·TPELF·TPEHS·TPEYR·TPEPJ·TPESY·TPETW·TTTSI·TPEWH 은
       m281~m291 로 이미 수록 — 중복 추가 금지)
  365일(2026-12-01~2027-11-30) 세전 현금 최저가(rates, KRW) + 아워드 포인트(points).

규칙:
  · 신규 4곳(TPEDS·TPEAL·TPECD·TPECY)은 m292~m295(대만 11→15)로 메리어트 묶음 맨 뒤에 붙인다.
    기존 291곳은 값·순서·alsoIn 그대로.
  · note 규칙은 대만 1~3차와 같다 — 코드·국가/도시·현금/포인트 일수·값 범위·결번 구간·예약 창 끝·
    null 보간 없음. 6번이 전한 특이사항은 값에서 확인되는 사실만 적고, 어긋나면 실측값을 쓴다.
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명·도시를 전수 대조한 결과 같은 호텔이
    한 곳도 없어(① 탭 12개 도시에 대만 없음) alsoIn 을 붙이지 않는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-24-0617/received/'
       '0-marriott-wave1-tw-hk-mo-47.json')
DAY = '2026-11-24'
FIRST = 292              # m292~m295
CODES = ('TPEDS', 'TPEAL', 'TPECD', 'TPECY')
DONE_CODES = ('KHHGM', 'KHHLC', 'KHHMC', 'TPELF', 'TPEHS', 'TPEYR', 'TPEPJ',
              'TPESY', 'TPETW', 'TTTSI', 'TPEWH')   # m281~m291 로 이미 수록
# 원자료 브랜드 표기 → 기존 카드와 같은 이름(이번 4곳은 디자인 호텔스·알로프트·코트야드 모두 기존 표기와 같다)
BRAND_FIX = {}
# 아워드 포인트 캘린더가 전 기간 미게시인 호텔 — 이번 4곳은 모두 포인트가 실려 있어 없다
NO_POINTS = set()
# 호텔별 특이사항 — 6번이 전한 내용 가운데 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'TPEDS': '2027-07-01~11-30 153일은 현금·아워드 포인트가 함께 미게시로 창 끝까지 값이 없고'
             '(6번은 2027-07-01 이후 미게시로 전달), 2026-12-29 824,815원이 창 안 최고가입니다',
    'TPEAL': '2026-12-25~12-26 크리스마스 연휴와 2026-12-31 이 현금 결번이고, 아워드 포인트는 '
             '2027-11-06 까지만 게시되어 현금(11-12까지)보다 6일 먼저 끊깁니다',
    'TPECD': '2026-12-31 2,125,738원이 창 안 최고가이고 2026-12-05 2,086,947원이 그 뒤를 잇습니다'
             '(연말·연초 주말 고가). 아워드 포인트는 2027-11-06 까지만 게시되어 현금보다 6일 먼저 끊깁니다',
    'TPECY': '2026-12-26 717,630원 · 2026-12-31 705,993원이 창 안 고가 구간이고, 현금·아워드 포인트가 '
             '모두 2027-11-06 까지만 게시되어 2027-11-13~30 예약 창 끝보다 6일 먼저 끊깁니다',
}
# 호텔별 창 끝 안내 — 실측에서 값이 끊긴 구간이 호텔마다 달라 그대로 적는다
WINDOW_END_NOTE = {
    'TPEDS': '2027-07-01~11-30 153일은 판매 중단인지 예약 창 끝인지 구분하지 않고 값이 없는 그대로 두었습니다',
    'TPEAL': '2027-11-13~11-30 18일은 예약 창 끝(Rate Unavailable)이며 매진·판매 중단과 구분하지 않습니다',
    'TPECD': '2027-11-13~11-30 18일은 예약 창 끝(Rate Unavailable)이며 매진·판매 중단과 구분하지 않습니다',
    'TPECY': '2027-11-07~11-30 24일은 현금·아워드 포인트가 함께 값 없이 끝납니다(예약 창 끝 구간 11-13~30보다 6일 이릅니다)',
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
        raise SystemExit('대만 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    hotels = doc['hotels']
    if len(hotels) != 15:
        raise SystemExit('대만 원본 호텔 %d곳 (누적 15곳이어야 함)' % len(hotels))
    got = tuple(h['code'] for h in hotels[:11])
    if got != DONE_CODES:
        raise SystemExit('앞 11곳이 이미 수록분과 다름: %s' % (got,))
    new = hotels[11:]
    if tuple(h['code'] for h in new) != CODES:
        raise SystemExit('뒤 4곳 코드가 다름: %s' % [h['code'] for h in new])
    for h in new:
        if h['country'] != '대만':
            raise SystemExit('%s 국가 %s (대만 이어야 함)' % (h['code'], h['country']))
    return new


def build(h, hid, region, label):
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
    if not pt_vals and h['code'] not in NO_POINTS:
        raise SystemExit('%s 아워드 포인트 0칸 — 6번 원본 확인 필요' % h['code'])
    if pt_vals and h['code'] in NO_POINTS:
        raise SystemExit('%s 는 포인트 0칸이어야 하는데 %d칸' % (h['code'], len(pt_vals)))

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], h['city'], cash_days, pt_days)]
    notes.append('현금 (세전) %s~%s원' % (format(min(cash_vals), ','), format(max(cash_vals), ',')))
    if pt_vals:
        notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))
    else:
        notes.append('아워드 포인트는 365일 전부 미게시(0일) — 보간하지 않았습니다')

    cash_gap = ranges([d for d, v in rates.items() if not isinstance(v, (int, float))])
    pt_gap = ranges([d for d, v in pt_map.items() if not isinstance(v, int)])
    if cash_gap:
        notes.append('현금 결번 %d개 구간(%s)' % (len(cash_gap), ' · '.join(cash_gap)))
    if pt_gap and pt_vals:
        notes.append('포인트 결번 %d개 구간(%s)' % (len(pt_gap), ' · '.join(pt_gap)))
    if h['code'] in EXTRA:
        notes.append(EXTRA[h['code']])
    notes.append(WINDOW_END_NOTE[h['code']])
    notes.append('null 은 그 날 값 미게시이며 보간하지 않았습니다.')

    if pt_vals:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days)
        pt_src = '아워드 포인트 캘린더(%s 기준)' % DAY
    else:
        promo = '아워드 포인트 캘린더 미게시(%s 기준) · 현금 %d일' % (DAY, cash_days)
        pt_src = '아워드 포인트 캘린더(%s 기준 · 365일 미게시)' % DAY
    return {
        'id': hid,
        'group': 'marriott',
        'brand': BRAND_FIX.get(h['brand'], h['brand']),
        'city': h['city'],
        'region': region,
        'name': h['name'],
        'english': h['english'],
        'promotion': promo,
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / %s · 6번 실측 %s 365일'
                   % (DAY, pt_src, label)),
        'code': h['code'],
        'rates': rates,
        'points': pt_map,
        'note': ' · '.join(notes),
    }


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    src = load()

    ids = {h['id'] for h in master['hotels']}
    codes = {h.get('code') for h in master['hotels'] if h.get('code')}
    names = {(h.get('english') or '').strip().lower() for h in master['hotels']}
    new = []
    for i, h in enumerate(src):
        hid = 'm%d' % (FIRST + i)
        if hid in ids:
            raise SystemExit('이미 있는 id: %s' % hid)
        if h['code'] in codes:
            raise SystemExit('이미 있는 code: %s (중복 추가 금지)' % h['code'])
        if h['english'].strip().lower() in names:
            raise SystemExit('이미 있는 영문명: %s' % h['english'])
        new.append(build(h, hid, '대만', 'marriott-wave1-tw-hk-mo 대만 4차 4곳'))

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 291곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = ('2026-11-24 KST ③ 메리어트 대만 4차 4곳 병합(291→295곳 · 대만 15) — TPEDS 디자인 호텔스 '
            '타이베이 Proverbs · TPEAL 알로프트 타이베이 Zhongshan · TPECD 코트야드 바이 메리어트 '
            '타이베이 Downtown · TPECY 코트야드 바이 메리어트 타이베이 4곳(현금 %d칸 · 포인트 %d칸 / '
            '4×365=1,460칸) 365일 세전 현금·아워드 포인트 실측(2026-11-24 · 6번(@jin_6) 전달본), '
            '누적 15곳 원본 가운데 앞 11곳은 m281~m291 로 이미 수록 — 뒤 4곳만 추가(중복 0건), '
            'TPEDS 는 2027-07-01~11-30 153일 현금·포인트 함께 미게시(2026-12-29 824,815원 창 안 최고가), '
            'TPEAL 은 2026-12-25~26·12-31 결번이고 포인트가 2027-11-06 에 끊기며, TPECD 2026-12-31 '
            '2,125,738원 · 2026-12-05 2,086,947원(창 안 최고가·차고가), TPECY 2026-12-26 717,630원 · '
            '2026-12-31 705,993원 고가에 현금·포인트 모두 2027-11-06 까지(예약 창 끝보다 6일 이릅), '
            '① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳'
            % (cash, pts))
    if '대만 4차 4곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + ' / ' + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 4곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for h in master['hotels'] if h.get('group') == 'marriott'), cash, pts))
    for hid in ('m292', 'm293', 'm294', 'm295'):
        h = next((x for x in master['hotels'] if x['id'] == hid), None)
        if h:
            print('  %s %s %s (현금 %d칸 · 포인트 %d칸)' % (
                hid, h['code'], h['name'],
                sum(1 for v in h['rates'].values() if isinstance(v, (int, float))),
                sum(1 for v in h['points'].values() if isinstance(v, int))))


if __name__ == '__main__':
    main()
