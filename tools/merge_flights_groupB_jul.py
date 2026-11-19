#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **B조 12개 노선의 2027년 7월 3주(7/15~19 · 7/22~26 · 7/29~8/2) 5패턴 180칸**을
`data/master_db.json` 의 `flights` 에 병합한다.

원본 1개(5번 보고서 `0-2027-07-groupB-rest.csv` + `1-2027-07-groupB-rest.md`,
2026-11-20 05:29~07:11 KST 실측) — 성인 1인 왕복 총액(유류·세금 포함, KRW).

  · 노선 12개: 싱가포르·괌·나고야·오키나와·항저우·칭다오·하노이·치앙마이·발리·가오슝·타이중·베이징
  · CSV 180줄(머리글 1 + 180칸): route, week, pattern, dep, ret, nights, price_krw, airline,
    direct_or_via, via_city, duration, times, status, note
  · 12노선 × 3주 × 5패턴 = **180칸 전수 실측**(값 180 · 판매편 0건 0 · 편성 미확인 0)
  · 이 격자에 앱이 이미 갖고 있던 **33칸**은 '가격표 실측 · 직항/경유 미확인' 자리표시라
    같은 노선·출발일·패턴의 이번 실측값(항공사·경유지·소요·시각 포함)으로 **교체**한다
    (같은 칸을 두 값으로 두지 않는다). 나머지 **147칸**은 새로 넣는다.
    교체 33칸 평균 667,282원 → 652,297원.

규칙:
  · `via` 는 그 칸 **최저가 편성**이 직항(`false`)·경유(`true`)인지로 적는다.
  · `note` 는 기존 앱 표기(`경유 1회(서울) · 환승 1시간 20분 · 총 3시간 55분 (16:10-20:05)`,
    `직항 2시간 10분 (09:25-11:35)`) 꼴로 적는다 — 앱의 장시간 경유 배지가 note 의
    `환승 N시간` 을 읽어 12h+/20h+ 를 계산한다(flDur/flLongClass).
  · 원본 CSV 의 실측 시각(`2026-11-20 05:29 KST 실측`)은 값이 아니라 조사 시각이므로 note 에 넣지 않는다.
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.
  · 호텔·아코르·⑥ 땡처리·출처 목록·패턴 정의·주차 정의·다른 노선/기존 딜·`noSale` 은
    값 대조로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-07 `notes` 끝에 이번 병합
    문장을 덧붙인다(plain text — 별표 금지). `extended` 끝에 한 줄을 덧붙인다(`--note`).
  · 이 원본에는 '직항 최저 …원'·'잔여 9석 미만' 표기가 없으므로 `alt`·9석 미만 표시를 만들지 않는다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_groupB_jul.py --dry-run
    python3 tools/merge_flights_groupB_jul.py
"""
import argparse
import collections
import csv
import datetime
import decimal
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
CSV_DEFAULT = os.path.normpath(os.path.join(
    ROOT, '..', 'memory', 'clones', 'f0ee2d96-jin_5', 'pickle', '2026-11-20-0713',
    'received', '0-2027-07-groupB-rest.csv'))

WD = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}   # datetime.weekday()
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
CITY = {'SIN': '싱가포르', 'GUM': '괌', 'NGO': '나고야', 'OKA': '오키나와', 'HGH': '항저우',
        'TAO': '칭다오', 'HAN': '하노이', 'CNX': '치앙마이', 'DPS': '발리', 'KHH': '가오슝',
        'RMQ': '타이중', 'BJS': '베이징'}
MONTH = '2027-07'
GRID_START, GRID_END = '2027-07-15', '2027-08-02'   # 7/15주 목요일 ~ 7/29주 토~월(7/31 출발·8/2 귀국)
WEEK_THU = ('2027-07-15', '2027-07-22', '2027-07-29')
WEEK_LABEL = {'2027-07-15': '7/15~19', '2027-07-22': '7/22~26', '2027-07-29': '7/29~8/2'}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver', '아고다', '부킹', '호텔스컴바인', '마이리얼트립', '야놀자', '여기어때')
AIRLINE_FIX = {}

# 원본 보고서(1-2027-07-groupB-rest.md)의 집계 — 파서가 같은 숫자를 내는지 대조한다
EXPECT_CELLS = 180            # CSV 180행 = 180칸 전수
EXPECT_VALUES = 180           # 그중 금액이 있는 칸
EXPECT_NOSALE = 0             # 판매편 0건(NA) 0칸
EXPECT_GRID = 180             # 12노선 × 3주 × 5패턴
EXPECT_REPLACE = 33           # 앱의 '가격표' 자리표시를 실측값으로 교체
EXPECT_NEW = 147              # 새로 넣는 칸
EXPECT_OVERALL = (433700, 995100)        # 타이중 7/15~19 금~일 · 괌 7/22~26 금~일
EXPECT_SUM = 117803900
EXPECT_AVG = 654466
EXPECT_MEDIAN = 644200
EXPECT_DIRECT = 22            # 최저가가 직항인 칸
EXPECT_MONTH_CELLS = {'2027-07': 180}    # 출발일 기준 월별(금액 칸)
EXPECT_PAT = {                # 패턴: (칸수, 합, 평균(반올림))
    '금~일': (36, 22818600, 633850), '토~월': (36, 25301900, 702831),
    '목~일': (36, 22149800, 615272), '금~월': (36, 23896400, 663789),
    '목~월': (36, 23637200, 656589),
}
# 노선: (값 칸수, 판매편 0건 칸수, 최저, 최고, 평균(반올림), 최저가가 직항인 칸)
EXPECT_ROUTE = {
    'SIN': (15, 0, 448800, 803600, 651687, 3),
    'GUM': (15, 0, 637600, 995100, 789433, 0),
    'NGO': (15, 0, 549600, 701700, 644200, 0),
    'OKA': (15, 0, 512500, 864400, 627340, 8),
    'HGH': (15, 0, 501700, 683700, 600547, 0),
    'TAO': (15, 0, 500600, 584800, 553420, 0),
    'HAN': (15, 0, 483000, 714200, 603500, 0),
    'CNX': (15, 0, 581100, 907400, 785367, 2),
    'DPS': (15, 0, 442300, 833000, 634427, 0),
    'KHH': (15, 0, 632900, 759200, 691747, 0),
    'RMQ': (15, 0, 433700, 968600, 734653, 5),
    'BJS': (15, 0, 447100, 652500, 537273, 4),
}
EXPECT_GRID_ROUTE = {c: (v[2], v[3]) for c, v in EXPECT_ROUTE.items()}
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
EXPECT_WEEK = {'2027-07-15': (60, 36056400, 600940, 433700, 992700),
               '2027-07-22': (60, 40173400, 669557, 452100, 995100),
               '2027-07-29': (60, 41574100, 692902, 453200, 994700)}
EXPECT_WEEK_AVG = {k: v[2] for k, v in EXPECT_WEEK.items()}
# 10만원 단위 구간 분포 — 보고서 '구간 분포' 표와 같은 8구간
EXPECT_BUCKET = {'30만원 미만': 0, '30만~40만원': 0, '40만~50만원': 18,
                 '50만~60만원': 49, '60만~70만원': 61, '70만~80만원': 23,
                 '80만~90만원': 19, '90만~100만원': 10, '100만원 이상': 0}
# 7월 달력 — 출발일: (그 날 실측 노선 수, 그 날 최저)
EXPECT_DAY = {'2027-07-15': (12, 442300), '2027-07-16': (12, 433700),
              '2027-07-17': (12, 503500), '2027-07-22': (12, 500600),
              '2027-07-23': (12, 452100), '2027-07-24': (12, 552800),
              '2027-07-29': (12, 532200), '2027-07-30': (12, 453200),
              '2027-07-31': (12, 574700)}
# 원본은 총 소요가 20시간을 넘는 칸이 38칸 — 앱 배지는 환승(대기) 시간으로 12h+/20h+를 붙인다
EXPECT_LONG = (15, 24)        # 환승 12시간 이상 20시간 미만 15칸 · 20시간 이상 24칸
EXPECT_TOTAL_OVER_20H = 38
# 2회 환승 5칸(환승 시간 미표기 — note 에 '환승' 대신 '경유 2회'만 적는다)
EXPECT_TWOHOP = {('HGH', '2027-07-15', '목~일'), ('HGH', '2027-07-22', '목~일'),
                 ('HGH', '2027-07-29', '목~일'), ('CNX', '2027-07-16', '금~월'),
                 ('CNX', '2027-07-17', '토~월')}
# 병합 전 격자에 '가격표' 자리표시로 있던 33칸 — 이번 실측값으로 교체한다(기존 → 신규)
EXPECT_REPLACE_CELLS = {
    ('CNX', '2027-07-15', '목~월'): (638500, 684000),
    ('CNX', '2027-07-15', '목~일'): (664100, 695400),
    ('DPS', '2027-07-15', '목~월'): (428200, 442300),
    ('DPS', '2027-07-16', '금~월'): (454100, 740900),
    ('DPS', '2027-07-17', '토~월'): (989800, 568500),
    ('DPS', '2027-07-22', '목~일'): (536300, 588400),
    ('DPS', '2027-07-29', '목~월'): (566100, 782900),
    ('GUM', '2027-07-15', '목~일'): (652400, 684500),
    ('GUM', '2027-07-17', '토~월'): (987600, 985500),
    ('GUM', '2027-07-22', '목~일'): (832500, 638800),
    ('GUM', '2027-07-29', '목~일'): (596700, 638800),
    ('HAN', '2027-07-16', '금~월'): (486600, 483000),
    ('HGH', '2027-07-17', '토~월'): (593500, 648400),
    ('KHH', '2027-07-30', '금~월'): (742000, 711100),
    ('NGO', '2027-07-17', '토~월'): (709800, 665500),
    ('OKA', '2027-07-15', '목~월'): (689400, 611800),
    ('OKA', '2027-07-15', '목~일'): (628900, 616400),
    ('OKA', '2027-07-16', '금~월'): (759300, 864400),
    ('OKA', '2027-07-16', '금~일'): (810200, 667900),
    ('OKA', '2027-07-17', '토~월'): (816200, 727200),
    ('OKA', '2027-07-22', '목~일'): (506300, 512500),
    ('OKA', '2027-07-23', '금~월'): (654900, 645200),
    ('OKA', '2027-07-29', '목~월'): (596300, 587700),
    ('OKA', '2027-07-29', '목~일'): (542600, 532200),
    ('OKA', '2027-07-30', '금~월'): (635700, 648900),
    ('OKA', '2027-07-30', '금~일'): (641900, 595800),
    ('SIN', '2027-07-16', '금~월'): (459300, 448800),
    ('SIN', '2027-07-22', '목~일'): (544100, 653800),
    ('SIN', '2027-07-23', '금~월'): (1195100, 751000),
    ('SIN', '2027-07-29', '목~월'): (809800, 803600),
    ('SIN', '2027-07-30', '금~월'): (652200, 800900),
    ('TAO', '2027-07-23', '금~일'): (600000, 550600),
    ('TAO', '2027-07-30', '금~일'): (599900, 549100),
}
EXPECT_REPLACE_OLD_AVG = 667282
EXPECT_REPLACE_NEW_AVG = 652297
# 이번 원본이 쓴 note 꼴 — 출발-도착 시각이 괄호 앞 공백 뒤에 붙는다
GRP_B_JUL_NOTE = re.compile(r' \(\d\d:\d\d-\d\d:\d\d[^)]*\)$')


def rnd(x):
    """보고서와 같은 반올림(0.5 올림)."""
    return int(decimal.Decimal(str(x)).quantize(0, rounding=decimal.ROUND_HALF_UP))


def median(values):
    v = sorted(values)
    n = len(v)
    if n % 2:
        return v[n // 2]
    mid = (v[n // 2 - 1] + v[n // 2]) / 2
    return int(mid) if mid == int(mid) else mid


def norm_dur(text):
    """'9시간 5분' → '9시간 05분', '1시간' → '1시간', '50분' → '50분'."""
    text = text.strip()
    m = re.fullmatch(r'(\d+)\s*시간(?:\s*(\d+)\s*분)?', text)
    if m:
        return m.group(1) + '시간' + ((' ' + m.group(2).rjust(2, '0') + '분')
                                     if m.group(2) else '')
    m = re.fullmatch(r'(\d+)\s*분', text)
    if m:
        return m.group(1).rjust(2, '0') + '분'
    raise SystemExit('소요시간 형식 이상: %r' % text)


def build_note(row):
    """CSV 한 줄 → note. (alt·9석 미만은 이 원본에 없다)"""
    kind = row['direct_or_via'].strip()
    times = row['times'].strip()
    dur = row['duration'].strip()
    city = row['via_city'].strip()
    info = dict(lay='', transfers='', total='')
    if kind == '직항':
        if city:
            raise SystemExit('직항인데 경유지가 있습니다: %r' % row)
        note = '직항 ' + norm_dur(dur) + ' (' + times + ')'
        return note, False, info
    if kind != '경유':
        raise SystemExit('편성 표기를 읽지 못했습니다: %r' % kind)

    m = re.fullmatch(r'총\s*(.+?)(?:\((.*)\))?', dur)
    if not m:
        raise SystemExit('경유 소요시간을 읽지 못했습니다: %r' % dur)
    total, inner = m.group(1).strip(), (m.group(2) or '').strip()
    info['total'] = total
    if inner:
        if not inner.startswith('환승'):
            raise SystemExit('환승 문장을 읽지 못했습니다: %r' % inner)
        rest = inner[2:].strip()
        if re.fullmatch(r'\d+회', rest):          # '환승 2회' — 시간 표기가 없는 칸
            info['transfers'] = rest
        else:
            info['lay'] = norm_dur(rest)

    hops = [h.strip() for h in city.replace('(2회)', '').split('·') if h.strip()]
    hops = [h.replace('(인천)', '').replace('호찌민시', '호찌민') for h in hops]
    if not hops:
        raise SystemExit('경유지가 없습니다: %r' % row)
    # 앱이 note 의 '환승 N시간' 을 읽어 장시간 경유 배지(12h+ · 20h+)를 계산하므로
    # 구 표기(`경유 1회(서울) · 환승 3시간 20분 · 총 6시간 10분 (…)`)를 쓴다.
    note = '경유 %d회(%s)' % (len(hops), '·'.join(hops))
    if info['lay']:
        note += ' · 환승 ' + info['lay']
    note += ' · 총 ' + norm_dur(total) + ' (' + times + ')'
    if info['transfers'] and int(info['transfers'][:-1]) != len(hops):
        note += ' · 환승 ' + info['transfers']
    return note, True, info


def parse(path):
    if not os.path.isfile(path):
        raise SystemExit('원본 CSV 가 없습니다: %s' % path)
    cells = {}
    with open(path, encoding='utf-8-sig', newline='') as fp:
        for ord_, row in enumerate(csv.DictReader(fp)):
            code = row['route'].strip()
            if code not in ROUTES:
                raise SystemExit('알 수 없는 노선 %s' % code)
            pat = row['pattern'].strip()
            if pat not in PAT_NIGHTS:
                raise SystemExit('%s 알 수 없는 패턴 %r' % (code, pat))
            date = datetime.date.fromisoformat(row['dep'])
            back = datetime.date.fromisoformat(row['ret'])
            nights = int(row['nights'])
            if PAT_NIGHTS[pat] != nights:
                raise SystemExit('%s %s 박수 불일치: %s' % (code, row['dep'], row['nights']))
            if (back - date).days != nights:
                raise SystemExit('%s 출발·귀국 간격이 박수와 다릅니다: %s' % (code, row))
            if WD[pat[0]] != date.weekday() or WD[pat[-1]] != back.weekday():
                raise SystemExit('%s 요일 불일치: %s %s' % (code, row['dep'], pat))
            if not (GRID_START <= row['dep'] <= GRID_END):
                raise SystemExit('%s 출발일이 이번 범위 밖: %s' % (code, row['dep']))
            thu = (date - datetime.timedelta(days=(date.weekday() - WD['목']) % 7)).isoformat()
            if WEEK_LABEL.get(thu) != row['week'].strip():
                raise SystemExit('%s 주차 표기 불일치: %s %s (%s)'
                                 % (code, row['dep'], row['week'], WEEK_LABEL.get(thu)))
            key = (code, row['dep'], pat)
            if key in cells:
                raise SystemExit('중복 칸 %s %s %s' % key)
            # 실측 시각 뒤의 원본 비고
            pieces = [p.strip() for p in row['note'].split(' · ')]
            if not re.match(r'^2026-11-20 \d\d:\d\d KST 실측$', pieces[0]):
                raise SystemExit('실측 시각 표기를 읽지 못했습니다: %r' % pieces[0])

            if row['status'] == 'NA':
                raise SystemExit('%s: 이 원본에는 판매편 0건 칸이 없어야 합니다: %r'
                                 % (code, row))

            if row['status'] != '값':
                raise SystemExit('%s 상태가 값이 아닙니다: %r' % (row['dep'], row['status']))
            if len(pieces) > 1:
                raise SystemExit('%s 처리하지 못한 비고: %r' % (row['dep'], pieces[1:]))
            price = int(row['price_krw'])
            if price <= 0:
                raise SystemExit('%s 금액이 양의 정수가 아닙니다' % code)
            note, via, info = build_note(row)
            if '**' in note or '[' in note or '출처' in note:
                raise SystemExit('%s note 에 마크업이 있습니다: %r' % (code, note))
            if via and '총' not in note:
                raise SystemExit('%s 경유 칸에 총 소요시간이 없습니다: %r' % (code, note))
            if not via and '직항' not in note:
                raise SystemExit('%s 직항 칸 note 이상: %r' % (code, note))
            airline = row['airline'].strip()
            airline = AIRLINE_FIX.get(airline, airline) or None
            for word in BANNED:
                if word in note or word in (airline or ''):
                    raise SystemExit('%s 값에 제3자 사이트 이름(%s)이 있습니다' % (code, word))
            cells[key] = dict(code=code, date=row['dep'], back=row['ret'], pattern=pat,
                              price=price, airline=airline, via=via,
                              note=note, ord=ord_)
    return cells


def check(cells):
    n = len(cells)
    if n != EXPECT_CELLS or n != EXPECT_VALUES:
        raise SystemExit('%d칸 (기대 %d칸)' % (n, EXPECT_CELLS))
    codes = {k[0] for k in cells}
    if codes != set(ROUTES):
        raise SystemExit('노선이 12개가 아닙니다: %s' % sorted(codes))
    ps = [c['price'] for c in cells.values()]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('최저·최고 %s (원문 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    if sum(ps) != EXPECT_SUM:
        raise SystemExit('금액 합 %d (원문 %d)' % (sum(ps), EXPECT_SUM))
    if rnd(sum(ps) / len(ps)) != EXPECT_AVG:
        raise SystemExit('평균 %d (원문 %d)' % (rnd(sum(ps) / len(ps)), EXPECT_AVG))
    if median(ps) != EXPECT_MEDIAN:
        raise SystemExit('중앙값 %s (원문 %s)' % (median(ps), EXPECT_MEDIAN))
    for pat, (cnt, total, avg) in EXPECT_PAT.items():
        v = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if len(v) != cnt or sum(v) != total or rnd(sum(v) / len(v)) != avg:
            raise SystemExit('%s 집계 %s (원문 %s)'
                             % (pat, (len(v), sum(v), rnd(sum(v) / len(v))), (cnt, total, avg)))
    direct = sum(1 for c in cells.values() if c['via'] is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (원문 %d)' % (direct, EXPECT_DIRECT))
    for code in ROUTES:
        v = [c for k, c in cells.items() if k[0] == code]
        prices = [c['price'] for c in v]
        got = (len(v), 0, min(prices), max(prices), rnd(sum(prices) / len(prices)),
               sum(1 for c in v if c['via'] is False))
        if got != EXPECT_ROUTE[code]:
            raise SystemExit('%s 집계 %s (원문 %s)' % (code, got, EXPECT_ROUTE[code]))
    # 출발일별 — 그 날 노선 수(중복 없이)와 최저
    per_day = collections.defaultdict(lambda: [set(), []])
    for c in cells.values():
        per_day[c['date']][0].add(c['code'])
        per_day[c['date']][1].append(c['price'])
    for date, (cnt, low) in EXPECT_DAY.items():
        got = per_day.get(date)
        if not got or (len(got[0]), min(got[1])) != (cnt, low):
            raise SystemExit('%s 달력 집계 %s (원문 %s)'
                             % (date, got and (len(got[0]), min(got[1])), (cnt, low)))
    if set(per_day) != set(EXPECT_DAY):
        raise SystemExit('출발일 집합이 다릅니다: %s' % sorted(set(per_day) ^ set(EXPECT_DAY)))
    # 주차별 칸수·합·평균·최저/최고
    weeks = collections.defaultdict(list)
    for c in cells.values():
        dt = datetime.date.fromisoformat(c['date'])
        weeks[(dt - datetime.timedelta(days=(dt.weekday() - WD['목']) % 7)).isoformat()] \
            .append(c['price'])
    if set(weeks) != set(WEEK_THU):
        raise SystemExit('주차 집합이 다릅니다: %s' % sorted(weeks))
    for thu in WEEK_THU:
        v = weeks[thu]
        got = (len(v), sum(v), rnd(sum(v) / len(v)), min(v), max(v))
        if got != EXPECT_WEEK[thu]:
            raise SystemExit('%s 주차 집계 %s (원문 %s)' % (thu, got, EXPECT_WEEK[thu]))
    # 10만원 단위 구간
    bucket = collections.Counter({k: 0 for k in EXPECT_BUCKET})
    edges = (300000, 400000, 500000, 600000, 700000, 800000, 900000, 1000000)
    names = ('30만원 미만', '30만~40만원', '40만~50만원', '50만~60만원',
             '60만~70만원', '70만~80만원', '80만~90만원', '90만~100만원', '100만원 이상')
    for p in ps:
        idx = sum(1 for e in edges if p >= e)
        bucket[names[idx]] += 1
    if dict(bucket) != EXPECT_BUCKET:
        raise SystemExit('구간 분포 %s (원문 %s)' % (dict(bucket), EXPECT_BUCKET))
    # 월별 칸수
    mcount = collections.Counter(c['date'][:7] for c in cells.values())
    if dict(mcount) != EXPECT_MONTH_CELLS:
        raise SystemExit('월별 %s (기대 %s)' % (dict(mcount), EXPECT_MONTH_CELLS))
    # 장시간 경유 — 앱과 같은 식(환승 N시간)
    long_cells = []
    for c in cells.values():
        m = re.search(r'환승\s*(\d+)시간\s*(?:(\d+)분)?', c['note'] if c['via'] else '')
        if m:
            long_cells.append(int(m.group(1)) * 60 + int(m.group(2) or 0))
    got_long = (sum(1 for x in long_cells if 720 <= x < 1200),
                sum(1 for x in long_cells if x >= 1200))
    if got_long != EXPECT_LONG:
        raise SystemExit('장시간 경유 %s (기대 %s)' % (got_long, EXPECT_LONG))
    if sum(1 for c in cells.values() if c['via']) - len(long_cells) != len(EXPECT_TWOHOP):
        raise SystemExit('환승 시간 미표기 경유 칸 %d칸 (기대 %d칸)'
                         % (sum(1 for c in cells.values() if c['via']) - len(long_cells),
                            len(EXPECT_TWOHOP)))
    two = {k for k, c in cells.items() if c['via'] and '환승' not in c['note']}
    if two != EXPECT_TWOHOP:
        raise SystemExit('2회 환승 칸이 다릅니다: %s' % sorted(two ^ EXPECT_TWOHOP))
    # 총 소요 20시간 초과 칸(보고서 38칸) — note 의 '총 N시간' 또는 직항 '직항 N시간'
    over = 0
    for c in cells.values():
        m = re.search(r'총\s*(\d+)시간\s*(?:(\d+)분)?', c['note']) or \
            re.search(r'직항\s*(\d+)시간\s*(?:(\d+)분)?', c['note'])
        if m and int(m.group(1)) * 60 + int(m.group(2) or 0) > 1200:
            over += 1
    if over != EXPECT_TOTAL_OVER_20H:
        raise SystemExit('총 소요 20시간 초과 %d칸 (원문 %d칸)' % (over, EXPECT_TOTAL_OVER_20H))
    return cells


def recount(fl):
    all_deals = [d for r in fl['routes'] for d in r['deals']]
    by_month = collections.Counter(d['date'][:7] for d in all_deals)
    fl['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month.get(k, 0) for k in fl['months']},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals
                       if d['pattern'].split('~')[0] == d['pattern'].split('~')[-1]),
    }
    return fl['counts']


def span_text(d):
    if d['date'][:7] == d['back'][:7]:
        return '%d/%d~%d' % (int(d['date'][5:7]), int(d['date'][8:10]), int(d['back'][8:10]))
    return '%d/%d~%d/%d' % (int(d['date'][5:7]), int(d['date'][8:10]),
                            int(d['back'][5:7]), int(d['back'][8:10]))


def cell_text(d):
    """'타이중 7/16~18 금~일 433,700원(스타룩스 직항 2시간 30분, 12:30-14:00)'"""
    air = d.get('airline') or '항공사 미확인'
    note = d.get('note') or ''
    m = re.match(r'^직항 (\S+(?: \d+분)?) \((.*)\)$', note)
    if m:
        detail = '직항 %s, %s' % (m.group(1), m.group(2))
    else:
        hops = re.search(r'경유 (\d회)\(([^)]*)\)', note)
        lay_m = re.search(r'환승 (\d+시간(?: \d+분)?)', note)
        tot = re.search(r'총 (\S+(?: \d+분)?)', note)
        detail = '경유 %s' % (hops.group(2) if hops else '(경유지 미표기)')
        if lay_m:
            detail += ' 환승 %s' % lay_m.group(1)
        if tot:
            detail += ' · 총 %s' % tot.group(1)
    return '%s %s %s %s원(%s %s)' % (CITY[d['code']], span_text(d), d['pattern'],
                                     format(d['price'], ','), air, detail)


def month_note(grid, replaced):
    ps = [d['price'] for d in grid]
    avg = rnd(sum(ps) / len(ps))
    pat = collections.defaultdict(list)
    for d in grid:
        pat[d['pattern']].append(d['price'])
    pat_avg = sorted(((p, rnd(sum(v) / len(v))) for p, v in pat.items()), key=lambda kv: kv[1])
    wk = collections.defaultdict(list)
    for d in grid:
        dt = datetime.date.fromisoformat(d['date'])
        wk[(dt - datetime.timedelta(days=(dt.weekday() - WD['목']) % 7)).isoformat()] \
            .append(d['price'])
    week_avg = [(WEEK_LABEL[k], rnd(sum(v) / len(v))) for k, v in sorted(wk.items())]
    week_ratio = '%.1f' % ((week_avg[-1][1] / week_avg[0][1] - 1) * 100)
    direct = sum(1 for d in grid if d.get('via') is False)
    nodirect = [c for c in ROUTES
                if not any(d.get('via') is False for d in grid if d['code'] == c)]
    lo = min(grid, key=lambda d: (d['price'], d['code']))
    hi = min(grid, key=lambda d: (-d['price'], d['code']))
    rep_old = rnd(sum(r[1] for r in replaced) / len(replaced))
    rep_new = rnd(sum(r[2] for r in replaced) / len(replaced))
    bucket = collections.Counter({k: 0 for k in EXPECT_BUCKET})
    edges = (300000, 400000, 500000, 600000, 700000, 800000, 900000, 1000000)
    names = ('30만원 미만', '30만~40만원', '40만~50만원', '50만~60만원',
             '60만~70만원', '70만~80만원', '80만~90만원', '90만~100만원', '100만원 이상')
    for p in ps:
        bucket[names[sum(1 for e in edges if p >= e)]] += 1
    bucket_text = ' · '.join('%s %d칸' % (k, bucket[k]) for k in names
                             if bucket[k] or k in ('40만~50만원',))
    long20 = sorted(((d, re.search(r'환승 (\d+시간(?: \d+분)?)', d['note']).group(1))
                     for d in grid
                     if d.get('via') and
                     re.search(r'환승 (\d+)시간\s*(?:(\d+)분)?', d['note']) and
                     (int(re.search(r'환승 (\d+)시간\s*(?:(\d+)분)?', d['note']).group(1)) * 60
                      + int(re.search(r'환승 (\d+)시간\s*(?:(\d+)분)?',
                                      d['note']).group(2) or 0)) >= 1200),
                    key=lambda t: -int(t[1].split('시간')[0]))
    long20_text = ' · '.join(
        '%s %s %s 환승 %s(총 %s)' % (CITY[d['code']], span_text(d), d['pattern'], l,
                                   re.search(r'총 (\S+(?: \d+분)?)', d['note']).group(1))
        for d, l in long20[:3])
    sent = (
        '2027년 7월 15~31일 출발분은 부산 출발 B조 12개 노선(싱가포르·괌·나고야·오키나와·'
        '항저우·칭다오·하노이·치앙마이·발리·가오슝·타이중·베이징)의 3주(7/15~19 · 7/22~26 · '
        '7/29~8/2) 5패턴 180칸을 전수 실측해 넣었습니다 — 이 격자에 가격표 자리표시'
        '(직항/경유 미확인)로만 있던 ' + str(len(replaced)) + '칸은 같은 노선·출발일·패턴의 '
        '실측값으로 교체했고(교체 칸 평균 ' + format(rep_old, ',') + '원 → '
        + format(rep_new, ',') + '원), 빈칸 ' + str(len(grid) - len(replaced))
        + '칸을 새로 넣어 이 세 주 5패턴이 ' + str(len(grid)) + '/180칸 모두 금액입니다'
        '(판매편 0건 0칸 · 편성 미확인 0칸 · 추정·보간 없음). '
        '이 격자 최저는 ' + cell_text(lo) + '이고, 최고는 ' + cell_text(hi)
        + '으로 최저의 ' + ('%.2f' % (hi['price'] / lo['price'])) + '배입니다. '
        '180칸 평균 ' + format(avg, ',') + '원 · 중앙값 ' + format(median(ps), ',') + '원이고 '
        '주차 평균은 ' + ' · '.join('%s %s원' % (w, format(v, ',')) for w, v in week_avg)
        + '으로 마지막 주(7/29~8/2)가 첫 주보다 ' + week_ratio + '% 비쌉니다. 패턴 평균은 '
        + ' < '.join('%s %s원' % (p, format(v, ',')) for p, v in pat_avg)
        + ' 순입니다(1·5위 차 ' + format(pat_avg[-1][1] - pat_avg[0][1], ',') + '원). '
        '최저가가 직항인 칸은 ' + str(direct) + '칸(오키나와 8 · 타이중 5 · 베이징 4 · '
        '싱가포르 3 · 치앙마이 2)이고 경유 ' + str(len(grid) - direct) + '칸이며, '
        + '·'.join(CITY[c] for c in nodirect) + ' ' + str(len(nodirect))
        + '개 노선은 15칸 모두 최저가가 경유입니다. 10만원 단위로는 ' + bucket_text + '입니다. '
        '경유 대기가 긴 칸은 ' + long20_text + ' 등이고, 환승 12시간 이상 20시간 미만이 '
        + str(EXPECT_LONG[0]) + '칸 · 20시간 이상이 ' + str(EXPECT_LONG[1])
        + '칸이라 앱의 경유 12h+ · 20h+ 경고가 붙으며, 총 소요가 20시간을 넘는 칸은 '
        + str(EXPECT_TOTAL_OVER_20H) + '칸입니다. 항저우 3칸(7/15·7/22·7/29 목~일)과 '
        '치앙마이 2칸(7/16·7/17 금~월·토~월)은 2회 환승이라 환승 시간 대신 경유지 2곳만 '
        '적었습니다. 이 원본에는 직항 최저 금액·잔여 9석 표기가 없어 직항 금액 병기와 '
        '잔여석 표시를 만들지 않았습니다.')
    return sent


def main(argv):
    ap = argparse.ArgumentParser(description='B조 12노선 2027년 7월 3주 180칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--csv', default=CSV_DEFAULT)
    ap.add_argument('--note', default=None)
    args = ap.parse_args(argv)

    cells = check(parse(args.csv))
    print('파싱 %d칸 — 값 %d — 최저 %s · 최고 %s · 평균 %s · 직항이 최저인 칸 %d · 경유 %d'
          % (len(cells), len(cells),
             format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ','),
             format(rnd(sum(c['price'] for c in cells.values()) / len(cells)), ','),
             sum(1 for c in cells.values() if c['via'] is False),
             sum(1 for c in cells.values() if c['via'] is True)))

    master = json.load(open(MASTER, encoding='utf-8'))
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다' % code)

    frozen = {k: json.dumps(master.get(k), ensure_ascii=False, sort_keys=True)
              for k in ('hotels', 'accor', 'sources', 'window', 'built', 'voucherExpiry',
                        'schema', 'version', 'ttang')}
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    weeks_before = json.dumps(fl['weeks'], ensure_ascii=False)
    notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    deals_before = {c: json.loads(json.dumps(routes[c]['deals'])) for c in ROUTES}
    daytrip_before = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    other_before = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    before_total = fl['counts']['total']
    before_jul = fl['counts']['byMonth'][MONTH]
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])

    # 이 격자에 이미 있던 칸 — '가격표' 자리표시(직항/경유 미확인)만 교체 대상이다
    placeholders = {}
    for code in ROUTES:
        for d in routes[code]['deals']:
            if not (GRID_START <= d['date'] <= GRID_END) or d['pattern'] not in PAT_NIGHTS:
                continue          # 0박 당일치기 등 이번 조사 범위 밖은 건드리지 않는다
            if d.get('src') != '가격표' or d.get('note') != '가격표 실측 · 직항/경유 미확인':
                raise SystemExit('이 격자에 예상 밖의 기존 칸: %s %s'
                                 % (code, json.dumps(d, ensure_ascii=False)))
            placeholders[(code, d['date'], d['pattern'])] = d
    if len(placeholders) != EXPECT_REPLACE:
        raise SystemExit('자리표시 칸 %d개 (기대 %d개)' % (len(placeholders), EXPECT_REPLACE))
    for key, (old_want, new_want) in EXPECT_REPLACE_CELLS.items():
        got = placeholders.get(key)
        if got is None:
            raise SystemExit('교체할 자리표시가 없습니다: %s' % (key,))
        if got['price'] != old_want or cells[key]['price'] != new_want:
            raise SystemExit('교체 칸 금액이 다릅니다: %s 기존 %s → 신규 %s (보고서 %s → %s)'
                             % (key, got['price'], cells[key]['price'],
                                old_want, new_want))
    old_avg = rnd(sum(d['price'] for d in placeholders.values()) / len(placeholders))
    new_avg = rnd(sum(cells[k]['price'] for k in placeholders) / len(placeholders))
    if (old_avg, new_avg) != (EXPECT_REPLACE_OLD_AVG, EXPECT_REPLACE_NEW_AVG):
        raise SystemExit('교체 칸 평균 %s → %s (기대 %s → %s)'
                         % (old_avg, new_avg, EXPECT_REPLACE_OLD_AVG, EXPECT_REPLACE_NEW_AVG))
    new_keys = set(cells) - set(placeholders)
    if len(new_keys) != EXPECT_NEW:
        raise SystemExit('새 칸 %d개 (기대 %d개)' % (len(new_keys), EXPECT_NEW))
    grid_keys = {(code, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(WD[pat[0]] - WD['목']) % 7)).isoformat(), pat)
                 for code in ROUTES for thu in WEEK_THU for pat in PAT_NIGHTS}
    if len(grid_keys) != EXPECT_GRID:
        raise SystemExit('격자 %d칸 (기대 %d칸)' % (len(grid_keys), EXPECT_GRID))
    if set(cells) != grid_keys:
        raise SystemExit('원본이 격자를 다 덮지 않습니다: %s'
                         % sorted(grid_keys ^ set(cells))[:6])
    print('자리표시 %d칸 교체(평균 %s원 → %s원) · 새 칸 %d칸 추가'
          % (len(placeholders), format(old_avg, ','), format(new_avg, ','), len(new_keys)))

    def make(v):
        deal = collections.OrderedDict()
        deal['date'] = v['date']
        deal['back'] = v['back']
        deal['pattern'] = v['pattern']
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        deal['note'] = v['note']
        return json.loads(json.dumps(deal))

    replaced = []
    for key, old in placeholders.items():
        deals = routes[key[0]]['deals']
        idx = next(i for i, d in enumerate(deals)
                   if (d['date'], d['pattern']) == (key[1], key[2]))
        deals[idx] = make(cells[key])
        replaced.append((key, old['price'], cells[key]['price']))
    added = []
    for key in sorted(new_keys):
        routes[key[0]]['deals'].append(make(cells[key]))
        added.append(key)
    for code in ROUTES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))
        have = [(d['date'], d['pattern']) for d in routes[code]['deals']]
        if len(set(have)) != len(have):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for d in routes[code]['deals']:
            for word in BANNED:
                if word in json.dumps(d, ensure_ascii=False):
                    raise SystemExit('%s %s 값에 제3자 사이트 이름(%s)이 있습니다'
                                     % (code, d['date'], word))

    counts = recount(fl)
    if counts['total'] != before_total + len(added):
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], before_total + len(added)))
    if counts['byMonth'][MONTH] != before_jul + len(added):
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                 before_jul + len(added)))

    # 병합 뒤 격자 180칸 검사
    grid = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if GRID_START <= d['date'] <= GRID_END
            and d['pattern'] in PAT_NIGHTS]
    if len(grid) != EXPECT_GRID:
        raise SystemExit('이 격자 %d칸 (기대 %d칸)' % (len(grid), EXPECT_GRID))
    if [d for d in grid if not d.get('price')]:
        raise SystemExit('금액 없는 칸이 있습니다')
    if [d for d in grid if d.get('src')]:
        raise SystemExit('가격표 자리표시 칸이 남아 있습니다')
    if [d for d in grid if not d.get('note')]:
        raise SystemExit('note 없는 칸이 있습니다')
    if [d for d in grid if d.get('alt')]:
        raise SystemExit('이 원본에 없는 직항 금액 병기가 붙었습니다')
    unknown = [(d['code'], d['date'], d['pattern']) for d in grid if d.get('via') is None]
    if unknown:
        raise SystemExit('편성 미확인 칸이 생겼습니다: %s' % sorted(unknown)[:4])
    ps = [d['price'] for d in grid]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('격자 최저·최고 %s (기대 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    if rnd(sum(ps) / len(ps)) != EXPECT_AVG:
        raise SystemExit('격자 평균 %d (기대 %d)' % (rnd(sum(ps) / len(ps)), EXPECT_AVG))
    if median(ps) != EXPECT_MEDIAN:
        raise SystemExit('격자 중앙값 %s (기대 %s)' % (median(ps), EXPECT_MEDIAN))
    for code, (low, high) in EXPECT_GRID_ROUTE.items():
        v = [d['price'] for d in grid if d['code'] == code]
        if len(v) != 15 or (min(v), max(v)) != (low, high):
            raise SystemExit('격자 %s %d칸 %s (기대 (15, %s))'
                             % (code, len(v), (min(v), max(v)), (low, high)))
    direct = sum(1 for d in grid if d.get('via') is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (기대 %d)' % (direct, EXPECT_DIRECT))
    week = collections.defaultdict(list)
    for d in grid:
        dt = datetime.date.fromisoformat(d['date'])
        week[(dt - datetime.timedelta(days=(dt.weekday() - WD['목']) % 7)).isoformat()] \
            .append(d['price'])
    for thu, want in EXPECT_WEEK_AVG.items():
        v = week[thu]
        if not v or rnd(sum(v) / len(v)) != want:
            raise SystemExit('%s 주차 평균 %s (기대 %d)' % (thu, v and rnd(sum(v) / len(v)), want))
    for d in grid:
        note = d['note']
        if d.get('via') is True and '총' not in note:
            raise SystemExit('%s %s 경유 칸에 총 소요시간이 없습니다' % (d['code'], d['date']))
        if d.get('via') is False and '직항' not in note:
            raise SystemExit('%s %s 직항 칸 note 이상' % (d['code'], d['date']))
        if not GRP_B_JUL_NOTE.search(note):
            raise SystemExit('%s %s note 에 출발-도착 시각이 없습니다: %r'
                             % (d['code'], d['date'], note))
        if '가격표' in note or '2026-11-2' in note:
            raise SystemExit('%s %s note 에 자리표시·조사 시각이 남았습니다'
                             % (d['code'], d['date']))

    # 보존 확인
    for key, old in frozen.items():
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != old:
            raise SystemExit('%s 가 바뀌었습니다' % key)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다')
    if json.dumps(fl['weeks'], ensure_ascii=False) != weeks_before:
        raise SystemExit('주차 정의가 바뀌었습니다')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != other_before:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('기존 noSale 기록이 바뀌었습니다')
    for code in ROUTES:
        old = deals_before[code]
        cur = routes[code]['deals']
        if len(cur) != len(old) + sum(1 for k in new_keys if k[0] == code):
            raise SystemExit('%s 딜 %d건 (기존 %d + 이번 %d)'
                             % (code, len(cur), len(old),
                                sum(1 for k in new_keys if k[0] == code)))
        have = {(d['date'], d['pattern']): d for d in cur}
        if len(have) != len(cur):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for o in old:
            got = have[(o['date'], o['pattern'])]
            key3 = (code, o['date'], o['pattern'])
            if key3 in placeholders:      # 이번에 교체한 칸만 달라져야 한다
                if json.dumps(got, ensure_ascii=False, sort_keys=True) == \
                        json.dumps(o, ensure_ascii=False, sort_keys=True):
                    raise SystemExit('%s 교체 칸이 그대로입니다: %s %s' % key3)
                continue
            if json.dumps(got, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(o, ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 기존 딜이 바뀌었습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
        keys = [(d['date'], WD[d['pattern'][0]]) for d in cur]
        if keys != sorted(keys):
            raise SystemExit('%s 딜 정렬이 깨졌습니다' % code)
        if json.dumps(routes[code]['daytrip'], ensure_ascii=False) != daytrip_before[code]:
            raise SystemExit('%s 당일치기 요약이 바뀌었습니다' % code)

    month_sent = month_note(grid, replaced)
    if '**' in month_sent or '[' in month_sent:
        raise SystemExit('notes 문장에 마크업이 있습니다')
    for word in BANNED:
        if word in month_sent:
            raise SystemExit('notes 문장에 제3자 사이트 이름(%s)이 있습니다' % word)
    fl['notes'][MONTH] = fl['notes'][MONTH].rstrip() + ' ' + month_sent
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')
    for word in BANNED:
        if word in json.dumps(fl['notes'], ensure_ascii=False):
            raise SystemExit('notes 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    note = args.note or (
        '2026-11-20 KST ⑤ 항공 부산 출발 B조 12개 노선 2027년 7월 3주(7/15~19 · 7/22~26 · '
        '7/29~8/2) 5패턴 180칸 완결 — 가격표 자리표시 %d칸 교체 + 빈칸 %d칸 실측, '
        '최저 타이중 7/15~19 금~일 433,700원(스타룩스 직항), 직항이 최저가인 칸 %d, '
        '총 %s→%s건'
        % (len(placeholders), len(new_keys), direct,
           format(before_total, ','), format(counts['total'], ',')))
    master['extended'] = (before_extended + ' / ' + note).strip(' /')

    print('교체 %d칸 + 신규 %d칸 · 격자 %d칸 모두 금액 · 최저 %s · 최고 %s'
          % (len(replaced), len(added), len(grid),
             format(min(ps), ','), format(max(ps), ',')))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'],
             counts['daytrip']))
    print('2027-07 %d → %d건' % (before_jul, counts['byMonth'][MONTH]))
    print('환승 12시간 이상 20시간 미만 %d칸 · 20시간 이상 %d칸'
          % (EXPECT_LONG[0], EXPECT_LONG[1]))
    print('notes[2027-07] 새 문장:', month_sent)
    print('extended 추가:', note)

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        return 0
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('저장: %s' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
