#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 대만 7차 4곳 병합 (303 → 307곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.refresh` → `master_db.py inject`).

입력(2026-11-24 6번(@jin_6) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/146dd4d1-jin_6/pickle/2026-11-24-0921/received/0-marriott-wave1-tw-hk-mo-47.json
    — 누적 27곳(27/47곳 완료)
  · 신규 4곳(TPESC·TPEFT·RMQMD·RMQOX)은 파일 안에 흩어져 있다(24·25·26·27번). 그래서 위치로
    자르지 않고 **기존 정본에 없는 코드 4개만** 골라 넣는다(중복 추가 금지).

규칙:
  · 신규 4곳은 m304~m307(대만 23→27)으로 메리어트 묶음 맨 뒤에 붙인다. 기존 303곳은 값·순서·alsoIn 그대로.
  · note 는 대만 1~6차와 같은 꼴 — 코드·국가/도시·현금/포인트 일수·값 범위·결번 구간·예약 창 끝·null 보간 없음.
    6번이 전한 특이사항은 **실측값과 대조해 확인된 사실만** 남긴다.
  · TPESC(트리뷰트 포트폴리오 타이베이 Suz Catorze)는 아워드 포인트 캘린더가 365일 전부 미게시다
    — 0칸을 그대로 싣고 note 에 어워드 재고 없음을 명시하며 master_db.NO_POINT_CODES 에 등록한다.
    현금은 2027-05-01~2027-11-06 190일이 667,202원 한 값으로 평탄하다(실측 그대로 · 보간 아님).
  · TPEFT 는 원자료 브랜드가 `포인트`(국문명 `포인트 타이베이 Bali`)로 잘려 왔다 — 기존 대만·한국
    포 포인츠 표기(`포 포인츠 바이 쉐라톤`, TPELF·TPEPJ·k15~k19)에 맞춘다.
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명·도시를 전수 대조한다(겹침 0 예상).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-24-0921/received/'
       '0-marriott-wave1-tw-hk-mo-47.json')
DAY = '2026-11-24'
FIRST = 304                        # m304~m307
CODES = ('TPESC', 'TPEFT', 'RMQMD', 'RMQOX')
EXPECT_POS = (24, 25, 26, 27)      # 원본 안 위치(1부터) — 흩어진 배치 확인용
EXPECT_SRC = 27                    # 누적 27곳
# 아워드 포인트 캘린더가 전 기간 미게시인 호텔 — TPESC(어워드 재고 없음)
NO_POINTS = {'TPESC'}
# 현금 요금 캘린더가 전 기간 미게시인 호텔 — 이번 4곳은 없다
NO_CASH = set()
# 원자료 브랜드 표기 → 기존 카드와 같은 이름(포인트 → 포 포인츠 바이 쉐라톤)
BRAND_FIX = {'포인트': '포 포인츠 바이 쉐라톤'}
# 원자료 국문명 → 기존 표기 규칙(브랜드 국문명 + 도시 + 영문 지명). 4곳 중 TPEFT 만 잘려 왔다
NAME_FIX = {'포인트 타이베이 Bali': '포 포인츠 바이 쉐라톤 타이베이 Bali'}
# 호텔별 특이사항 — 6번이 전한 내용 가운데 실측값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'TPESC': '2027-05-01~2027-11-06 190일이 667,202원 한 값으로 평탄하고(실측 그대로 · 보간 아님), 그 구간을 빼면 2026-12-05 391,787원이 창 안 최고가이며 '
             '2027-01-11~01-14 · 01-17 등 174,558원이 최저가(15일)입니다. 아워드 포인트는 '
             '2026-12-01~2027-11-30 365일 전부 미게시(0일)라 아워드 재고가 없어 35k 숙박권 대상이 아닙니다',
    'TPEFT': '아워드 포인트는 2026-12-31~2027-02-28 60일이 통째로 비고, 2027-03-06 이후에는 토요일을 '
             '중심으로 결번이 반복됩니다(2027-04-03~04-05 · 2027-04-30~05-01 은 금·일요일까지). '
             '포인트는 23,000P 가 173일로 기본이고 2027-10-25~11-06 13일만 32,000P 입니다. '
             '현금은 2026-12-12 351,485원이 창 안 최고가(2026-12-05·12-19·12-26 307,795원)이고 '
             '2027-01-03 이후 값이 있는 날 가운데 212일이 창 안 최저가 203,182원입니다(토요일은 하루도 없습니다). 마리어트 공홈 주소는 '
             'No 8 Guanhai Boulevard, Bali District, New Taipei City(신베이시 바리구)입니다',
    'RMQMD': '현금·아워드 포인트가 함께 2027-04-01~11-30 244일 비어 창 안 후반 8개월이 통째로 '
             '미게시입니다(예약 창 끝 2027-11-13~30 과 별개로 훨씬 이릅니다 — 6번이 전한 '
             '"2027-04~11 재고 없음"과 실측이 일치합니다). 현금은 2027-01-20 380,150원이 창 안 '
             '최고가이고 2027-02-04~02-09 6일과 2027-02-14 이 341,359원으로 그 뒤를 잇습니다(2026-12-31 321,964원). 166,800원이 '
             '69일로 기본값이고, 아워드 포인트는 2026-12-05 65,000P 가 최고가(현금은 그 날 미게시)이며 '
             '2027-02-05~02-07 이 62,000~63,000P 로 고가입니다',
    'RMQOX': '현금 2027-03-27 191,912원 · 2027-02-06~02-09 190,075원이 창 안 최고가이고 '
             '2027-02-21 75,662원이 최저가입니다. 아워드 포인트는 14,500P(2027-02-18~02-19)~25,000P '
             '(2026-12-31 · 2027-02-06~02-09 · 2027-07-03·07-10·07-17 · 2027-11-04~11-06)이며 '
             '2027-07 이후 현금은 값이 있는 날이 124,130~162,921원으로 올라섭니다',
}
# 호텔별 창 끝 안내 — 현금·포인트가 끊기는 날이 호텔마다 달라 그대로 적는다
WINDOW_END_NOTE = {
    'TPESC': '현금이 2027-11-06 에 끊겨 2027-11-07~11-30 24일이 비며, 예약 창 끝 구간'
             '(2027-11-13~30)보다 6일 이릅니다(6번은 11-07 이후 미게시로 전달 — 실측 결번은 11-30 까지입니다)',
    'TPEFT': '현금·아워드 포인트가 함께 2027-11-06 에 끊겨 2027-11-07~11-30 24일이 비며, 예약 창 끝 구간'
             '(2027-11-13~30)보다 6일 이릅니다',
    'RMQMD': '2027-04-01 이후는 예약 창 끝이 아니라 창 안 8개월이 통째로 미게시라, 예약 창 끝 구간'
             '(2027-11-13~30)을 따로 가를 수 없습니다',
    'RMQOX': '현금·아워드 포인트가 함께 2027-11-06 에 끊겨 2027-11-07~11-30 24일이 비며, 예약 창 끝 구간'
             '(2027-11-13~30)보다 6일 이릅니다',
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
    if len(hotels) != EXPECT_SRC:
        raise SystemExit('대만 원본 호텔 %d곳 (누적 %d곳이어야 함)' % (len(hotels), EXPECT_SRC))
    # 위치로 자르지 않는다 — 코드로 고르고, 흩어진 위치(24~27번)만 확인한다
    pos = {}
    for i, h in enumerate(hotels):
        pos.setdefault(h['code'], []).append(i + 1)
    picked = []
    for code, want in zip(CODES, EXPECT_POS):
        if pos.get(code) != [want]:
            raise SystemExit('%s 위치 %s (기대 %d번 한 곳)' % (code, pos.get(code), want))
        picked.append(hotels[want - 1])
    for h in picked:
        if h['country'] != '대만':
            raise SystemExit('%s 국가 %s (대만 이어야 함)' % (h['code'], h['country']))
    return picked


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
    if not cash_vals and h['code'] not in NO_CASH:
        raise SystemExit('%s 현금 값 0칸 — 수록 기준 확인 필요' % h['code'])
    if not pt_vals and h['code'] not in NO_POINTS:
        raise SystemExit('%s 아워드 포인트 0칸 — 6번 원본 확인 필요' % h['code'])
    if pt_vals and h['code'] in NO_POINTS:
        raise SystemExit('%s 는 포인트 0칸이어야 하는데 %d칸' % (h['code'], len(pt_vals)))
    if cash_vals and h['code'] in NO_CASH:
        raise SystemExit('%s 는 현금 0칸이어야 하는데 %d칸' % (h['code'], len(cash_vals)))

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], h['city'], cash_days, pt_days)]
    if cash_vals:
        notes.append('현금 (세전) %s~%s원' % (format(min(cash_vals), ','), format(max(cash_vals), ',')))
    else:
        notes.append('현금은 365일 전부 미게시(0일) — 보간하지 않았습니다')
    if pt_vals:
        notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))
    else:
        notes.append('아워드 포인트는 365일 전부 미게시(0일) — 보간하지 않았습니다(어워드 재고 없음)')

    cash_gap = ranges([d for d, v in rates.items() if not isinstance(v, (int, float))])
    pt_gap = ranges([d for d, v in pt_map.items() if not isinstance(v, int)])
    if cash_gap and cash_vals:
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
    elif cash_vals:
        promo = '아워드 포인트 캘린더 미게시(%s 기준 · 365일) · 현금 %d일' % (DAY, cash_days)
        pt_src = '아워드 포인트 캘린더(%s 기준 · 365일 미게시)' % DAY
    else:
        promo = '현금·아워드 포인트 미게시(%s 기준 · 365일)' % DAY
        pt_src = '아워드 포인트 캘린더(%s 기준 · 365일 미게시)' % DAY
    return {
        'id': hid,
        'group': 'marriott',
        'brand': BRAND_FIX.get(h['brand'], h['brand']),
        'city': h['city'],
        'region': region,
        'name': NAME_FIX.get(h['name'], h['name']),
        'english': h['english'],
        'promotion': promo,
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / %s · 6번 실측 %s 365일'
                   % (DAY, pt_src, label)),
        'code': h['code'],
        'rates': rates,
        'points': pt_map,
        'note': ' · '.join(notes),
    }


def crosscheck_lux(master, src):
    """① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조."""
    lux = [h for h in master['hotels'] if h.get('group') == 'lux']
    lcodes = {h.get('code') for h in lux}
    lenames = {(h.get('english') or '').strip().lower() for h in lux}
    lnames = {h.get('name') for h in lux}
    lcities = {h.get('city') for h in lux}
    hits = []
    for h in src:
        if h['code'] in lcodes or h['english'].strip().lower() in lenames or h['name'] in lnames:
            hits.append((h['code'], h['name']))
    return len(lux), hits, sorted(lcities)


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
        new.append(build(h, hid, '대만', 'marriott-wave1-tw-hk-mo 대만 7차 4곳'))

    lux_n, lux_hits, lux_cities = crosscheck_lux(master, src)
    print('① 호텔럭스 %d곳 대조 — 겹침 %d곳 %s' % (lux_n, len(lux_hits), lux_hits))
    print('   ① 탭 도시: %s' % ', '.join(lux_cities))
    if lux_hits:
        raise SystemExit('① 탭과 겹치는 호텔이 있습니다 — alsoIn 연결 여부를 먼저 정하세요')

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 303곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = ('2026-11-24 KST ③ 메리어트 대만 7차 4곳 병합(303→307곳 · 대만 27 · 통합 1,004곳) — '
            'TPESC 트리뷰트 포트폴리오 타이베이 Suz Catorze · TPEFT 포 포인츠 바이 쉐라톤 타이베이 Bali · '
            'RMQMD 르메르디앙 타이중 · RMQOX 목시 타이중 4곳(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 '
            '세전 현금·아워드 포인트 실측(2026-11-24 · 6번(@jin_6) 전달본), 누적 27곳 원본 가운데 기존 정본에 '
            '없는 코드 4개만 골라 추가(기존 23곳 중복 0건), TPESC 는 아워드 포인트 365일 전부 미게시(0칸 — '
            '어워드 재고 없음으로 NO_POINT_CODES 등록)이고 현금은 2027-05-01~2027-11-06 190일이 667,202원 '
            '한 값으로 평탄(실측 그대로), TPEFT 는 원자료 브랜드·국문명이 `포인트`로 잘려 와 기존 표기 '
            '`포 포인츠 바이 쉐라톤`으로 통일했고 포인트가 2026-12-31~2027-02-28 60일 비고 2027-03 이후 '
            '토요일 중심으로 결번 반복, RMQMD 는 현금·포인트가 2027-04-01~11-30 244일 통째로 미게시'
            '(6번 전달 "2027-04~11 재고 없음"과 실측 일치), RMQOX 는 2027-03-27 191,912원 최고가 · '
            '2027-02-21 75,662원 최저가, 네 곳 모두 현금·포인트가 2027-11-06(TPESC·TPEFT·RMQOX) 또는 '
            '2027-03-31(RMQMD)에 끊김, ① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳'
            % (cash, pts))
    if '대만 7차 4곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + ' / ' + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 4곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for h in master['hotels'] if h.get('group') == 'marriott'), cash, pts))
    for hid in ('m304', 'm305', 'm306', 'm307'):
        h = next((x for x in master['hotels'] if x['id'] == hid), None)
        if h:
            print('  %s %s %s (현금 %d칸 · 포인트 %d칸)' % (
                hid, h['code'], h['name'],
                sum(1 for v in h['rates'].values() if isinstance(v, (int, float))),
                sum(1 for v in h['points'].values() if isinstance(v, int))))


if __name__ == '__main__':
    main()
