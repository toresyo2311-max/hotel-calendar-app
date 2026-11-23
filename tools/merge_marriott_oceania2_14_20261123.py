#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 오세아니아 2차 14곳 병합 (197 → 211곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-23 6번(@jin_6) 실측 · marriott.com availabilityCalendar):
  · memory/clones/146dd4d1-jin_6/pickle/2026-11-23-0946/received/
      0-marriott-wave1-oceania-part2-24.json — 14곳 × 365일(2026-12-01~2027-11-30)
    세전 현금 최저가(rates, KRW) + 아워드 포인트(points). 원자료에 호텔별 note 는 없다.

규칙:
  · 오세아니아 2차 14곳(호주 — 멜버른 3 · 브리즈번 5 · 골드코스트 1 · 시드니 5)을
    메리어트 묶음 맨 뒤에 붙인다. 기존 197곳은 값·순서·alsoIn 그대로.
  · id 는 211곳 기준 순번인 m198~m211.
  · 오세아니아 1차 23곳과 같은 note 규칙을 쓴다 — 코드·국가/도시·현금/포인트 일수·
    값 범위·결번 구간·호주 세금 포함 표시·조회 한도·null 보간 없음.
  · 호주 14곳은 1차 호주 12곳과 같이 현지 가격표시 규정상 달력 표시값이 세금 포함 총액이다
    (원자료 source 문구는 「세금·수수료 별도」로 1차와 같고, 1차도 같은 문구에 note 로
    세금 포함을 적었다 — 표기 방식을 1차와 똑같이 맞춘다).
  · null 은 보간하지 않는다(호텔별 예약창 상한 · 2027-11-07~12 체크인 불가 · 11-13 이후 조회 한도).
  · 브랜드 표기는 기존 카드와 맞춘다 — 원본 「포인트」는 「포 포인츠 바이 쉐라톤」,
    국문명도 1차 AKLFP 와 같은 방식으로 바로잡는다(값은 원자료 그대로).
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명·도시를 전수 대조한 결과
    W 시드니(SYDWH) 1곳이 h110 과 같은 호텔이라 alsoIn 을 양방향으로 잇는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-23-0946/received/'
       '0-marriott-wave1-oceania-part2-24.json')
DAY = '2026-11-23'
FIRST_ID = 198
# ① 호텔럭스(161곳)와 같은 호텔 — 코드 → (럭스 id, 럭스 ref_id)
OVERLAP = {
    'SYDWH': ('h110', '64b8f63006aff746daa72da3'),   # W 시드니
}
# 원자료 브랜드 표기 → 기존 카드와 같은 이름
BRAND_FIX = {'포인트': '포 포인츠 바이 쉐라톤'}
NAME_FIX = {'BNEFP': '포 포인츠 바이 쉐라톤 브리즈번'}
# 원자료 도시 칸이 상위 도시가 아닌 곳 — 같은 목적지로 묶어 도시 필터에서 한 번에 보이게 한다
CITY_FIX = {'OOLMV': '골드코스트'}
# 호주 전 14곳 — 현지 가격표시 규정상 달력 표시값이 세금 포함 총액
AUS = {'MELEL', 'MELWI', 'MELCY', 'BNEWH', 'BNEDT', 'BNEWI', 'BNECY', 'BNEFP',
       'OOLMV', 'SYDWH', 'SYDMC', 'SYDXP', 'SYDSI', 'SYDAK'}
# 호텔별 특이사항 — 원자료(값)에서 그대로 읽히는 사실만 적는다
EXTRA = {
    'MELEL': '2027-10-01~10-24 24일이 현금·포인트 함께 결번입니다',
    'MELCY': '2027-10-01~10-24 24일이 현금·포인트 함께 결번입니다',
    'MELWI': '2027-01-15~01-28 열흘이 40만~139만원으로 창 안 최고 구간입니다(2027-01-28 1,385,898원)',
    'BNEDT': '2027-05-14~15가 2,355,937원·2,533,525원으로 창 안 최고가입니다 — 같은 날 다른 '
             '브리즈번 4곳은 84만원 이하입니다',
    'OOLMV': '포인트가 171일만 게시되고, 비는 날의 대부분이 금·토요일(금 48일 · 토 49일)입니다 — '
             '2026-12-18~2027-01-02 연말과 2027-09-17~11-30도 포인트가 없습니다',
    'SYDWH': '2027-10-01~11-30 61일이 현금·포인트 함께 결번입니다(2027-09-30 이후 값 없음 — '
             '판매 중단인지 호텔별 예약창 상한인지는 구분하지 않음)',
    'SYDMC': '2027-10-01~11-30 61일이 현금·포인트 함께 결번입니다(2027-09-30 이후 값 없음)',
    'SYDXP': '2027-10-01~11-30 61일이 현금·포인트 함께 결번입니다(2027-09-30 이후 값 없음)',
    'SYDAK': '2027-10-01~11-30 61일이 현금·포인트 함께 결번입니다(2027-09-30 이후 값 없음)',
    'SYDSI': '2027-10-28~11-30 34일이 현금·포인트 함께 결번입니다(2027-10-27 이후 값 없음)',
    'OOLMV_CITY': '소재지는 골드코스트 서퍼스파라다이스입니다 — 원자료 도시 칸(서퍼스파라다이스)을 '
                  '골드코스트 기존 3곳과 함께 보도록 「골드코스트」로 묶었습니다(값은 원자료 그대로).',
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
        raise SystemExit('원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    hotels = doc['hotels']
    if len(hotels) != 14:
        raise SystemExit('원본 호텔 %d곳 (14 이어야 함)' % len(hotels))
    codes = [h['code'] for h in hotels]
    if len(set(codes)) != len(codes):
        raise SystemExit('원본 코드 중복: %s' % codes)
    for h in hotels:
        if h['country'] != '호주':
            raise SystemExit('%s 국가 %s (호주 이어야 함)' % (h['code'], h['country']))
    return hotels, os.path.basename(SRC)


def build(h, hid):
    rates, points = h['rates'], h['points']
    for name, vals in (('rates', rates), ('points', points)):
        if len(vals) != 365:
            raise SystemExit('%s %s 칸 %d개 (365 이어야 함)' % (h['code'], name, len(vals)))
        for d in vals:
            if not (M.WINDOW_START <= d <= M.WINDOW_END):
                raise SystemExit('%s %s 날짜 %s 창 밖' % (h['code'], name, d))
    cash_days = sum(1 for v in rates.values() if isinstance(v, (int, float)))
    pt_days = sum(1 for v in points.values() if isinstance(v, int))
    cash_vals = [v for v in rates.values() if isinstance(v, (int, float))]
    pt_vals = [v for v in points.values() if isinstance(v, int)]
    if not cash_vals:
        raise SystemExit('%s 현금 값 0칸 — 수록 기준 확인 필요' % h['code'])

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], h['city'], cash_days, pt_days)]
    tax = ' (세금 포함 총액)' if h['code'] in AUS else ' (세전)'
    notes.append('현금%s %s~%s원' % (tax, format(min(cash_vals), ','), format(max(cash_vals), ',')))
    if pt_vals:
        notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))
    else:
        notes.append('아워드 포인트 미게시 — 포인트 캘린더 0일(365일 전부 null)')

    cash_gap = ranges([d for d, v in rates.items() if not isinstance(v, (int, float))])
    pt_gap = ranges([d for d, v in points.items() if not isinstance(v, int)])
    if cash_gap:
        notes.append('현금 결번 %d개 구간(%s)' % (len(cash_gap), ' · '.join(cash_gap)))
    if pt_gap and pt_vals:
        notes.append('포인트 결번 %d개 구간(%s)' % (len(pt_gap), ' · '.join(pt_gap)))
    if h['code'] in EXTRA:
        notes.append(EXTRA[h['code']])
    if h['code'] in CITY_FIX:
        notes.append(EXTRA['OOLMV_CITY'])
    if h['code'] in AUS:
        notes.append('호주는 현지 가격표시 규정상 달력 표시값이 세금 포함 총액과 같습니다')
    notes.append('2027-11-07~12는 체크인 불가, 2027-11-13 이후는 조회 한도(오늘+355일)이며 '
                 '판매 중단과 구분하지 않습니다')
    notes.append('null 은 그 날 값 미게시이며 보간하지 않았습니다.')

    if pt_days:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days)
    else:
        promo = '아워드 포인트 캘린더 미게시(0일) · 현금 %d일' % cash_days

    card = {
        'id': hid,
        'group': 'marriott',
        'brand': BRAND_FIX.get(h['brand'], h['brand']),
        'city': CITY_FIX.get(h['code'], h['city']),
        'region': '오세아니아',
        'name': NAME_FIX.get(h['code'], h['name']),
        'english': h['english'],
        'promotion': promo,
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
                   '아워드 포인트 캘린더(%s 기준) · 6번 실측 marriott-wave1-oceania-part2 365일'
                   % (DAY, DAY)),
        'code': h['code'],
        'rates': rates,
        'points': points,
        'note': ' · '.join(notes),
    }
    if h['code'] in OVERLAP:
        card['alsoIn'] = OVERLAP[h['code']][0]
        card['alsoInLabel'] = '① 호텔럭스'
    return card


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    src, srcname = load()

    ids = {h['id'] for h in master['hotels']}
    codes = {h.get('code') for h in master['hotels'] if h.get('group') == 'marriott'}
    new = []
    for i, h in enumerate(src):
        hid = 'm%02d' % (FIRST_ID + i)
        if hid in ids:
            raise SystemExit('이미 있는 id: %s' % hid)
        if h['code'] in codes:
            raise SystemExit('이미 있는 code: %s' % h['code'])
        new.append(build(h, hid))

    # 메리어트 묶음 맨 뒤(일본 2차 30곳 다음)에 붙인다 — 기존 197곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    # ① 호텔럭스 쪽 alsoIn — 양방향 연결
    by_id = {h['id']: h for h in master['hotels']}
    for code, (lux_id, _ref) in OVERLAP.items():
        lux = by_id.get(lux_id)
        if not lux or lux.get('group') != 'lux':
            raise SystemExit('① 호텔럭스 %s 없음' % lux_id)
        if lux.get('alsoIn'):
            raise SystemExit('① 호텔럭스 %s 는 이미 alsoIn %s' % (lux_id, lux['alsoIn']))
        mar = next(x for x in new if x['code'] == code)
        lux['alsoIn'] = mar['id']

    if srcname not in master['sources']:
        master['sources'].append(srcname)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (' / 2026-11-23 KST ③ 메리어트 오세아니아 2차 14곳 병합(197→211곳 · 오세아니아 37) — '
            'MELEL 엘리먼트 멜버른 Richmond ~ SYDAK 오토그래프 시드니 Pier One 365일 세금 포함 '
            '현금·아워드 포인트 실측(현금 %d칸 · 포인트 %d칸 / 14×365=5,110칸), '
            '호주(멜버른 3 · 브리즈번 5 · 골드코스트 1 · 시드니 5) 14곳은 1차 호주 12곳과 같이 '
            '현지 규정상 세금 포함 총액, 시드니 5곳(2027-10-01~11-30 4곳·10-28~11-30 1곳)·'
            '멜버른 2곳(2027-10-01~10-24)이 결번, '
            '① 호텔럭스 161곳과 전수 대조 — 겹침 1곳(SYDWH W 시드니↔h110) alsoIn 양방향 연결'
            % (cash, pts))
    if '오세아니아 2차 14곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 14곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for h in master['hotels'] if h.get('group') == 'marriott'), cash, pts))


if __name__ == '__main__':
    main()
