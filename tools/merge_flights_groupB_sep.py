#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **B조 12개 노선의 2027년 9월 5주(9/2~6 · 9/9~13 · 9/16~20 ·
9/23~27 · 9/30~10/4) 5패턴 300칸**을 `data/master_db.json` 의 `flights` 에 병합한다.

원본 1개(5번 보고서 `0-2027-09-groupB-rest.csv` + `1-2027-09-groupB-rest.md`,
2026-11-20 10:46~13:57 KST 실측) — 성인 1인 왕복 총액(유류·세금 포함, KRW).

  · 노선 12개: 싱가포르·괌·나고야·오키나와·항저우·칭다오·하노이·치앙마이·발리·가오슝·타이중·베이징
  · CSV 300줄(머리글 1 + 300칸): route, week, pattern, dep, ret, nights, price_krw, airline,
    direct_or_via, via_city, duration, times, status, note
  · 12노선 × 5주 × 5패턴 = **300칸 전수 실측**(값 300 · 판매편 0건 0 · 편성 미확인 0)
  · 이 격자에 앱이 이미 갖고 있던 **12칸**(12노선 2027-10-01 금~일, 앞선 조회분 — 항공사·소요·
    시각 없이 '경유 · 직항 없음' 또는 '최저가 편 구성 미확인')은 같은 노선·출발일·패턴의 이번
    실측값(항공사·경유지·소요·시각 포함)으로 **교체**한다(같은 칸을 두 값으로 두지 않는다).
    나머지 **288칸**은 새로 넣는다.
  · 교체 12칸 평균 702,333원 → 632,717원.

규칙:
  · `via` 는 그 칸 **최저가 편성**이 직항(`false`)·경유(`true`)인지로 적는다.
  · `note` 는 기존 앱 표기(`경유 1회(마닐라) · 환승 22시간 35분 · 총 30시간 20분 (21:00-04:20+2)`,
    `직항 4시간 15분 (11:00-13:15)`) 꼴로 적는다 — 앱의 장시간 경유 배지가 note 의
    `환승 N시간` 을 읽어 12h+/20h+ 를 계산한다(flDur/flLongClass). 두 번 환승하는 칸은
    환승 시간 대신 경유지 두 곳을 적는다(`경유 2회(서울·다롄) · 총 9시간 40분 (08:00-16:40)`).
  · 원본이 함께 적은 비고를 값으로 살린다(원본에 있는 값만 넣는다).
      - `최단 일정(항공사 … N시간 M분) N원` → note 끝 `· 최단 N시간 M분 N원(항공사 …)`.
        앱은 `· 최단 …` 을 그대로 보여 준다(기존 22칸이 이 꼴).
        뒤에 붙은 `(13:57 재확인)` 은 조사 시각이라 버린다.
      - `최단 일정(…)도 동일 N원` 은 최저가 일정 자체가 최단 일정이라는 뜻이라 덧붙이지
        않는다(금액이 그 칸 최저가와 같은지 확인만 한다) — 1칸.
      - `최저가 일정 환승 N시간` → duration 의 `환승 N시간` 과 항상 같은 값이므로 중복해
        적지 않는다(다른 값이면 중단).
      - `액세스레일 결합 상품 (N원) 제외` → `철도+항공 결합상품 (N원)은 항공권이 아니어서
        제외` 로 적는다(제3자 상품·사이트 이름은 값·note 어디에도 넣지 않는다) — 13칸.
      - `첫 로드에서 0건 표시 → 재조회로 확보` 는 조회 과정 기록이라 넣지 않는다 — 1칸.
  · 원본 CSV 의 실측 시각(`2026-11-20 10:46 KST 실측`)은 값이 아니라 조사 시각이므로 note 에
    넣지 않는다.
  · 이 원본에는 `직항(항공사) N원` 꼴의 **직항 최저 금액 표기가 없어 `alt` 를 만들지 않는다**
    (최단 일정이 직항인 칸이 있지만 그것은 '그 금액대의 최단 일정'이지 '직항 최저가'가 아니다).
  · 호텔·아코르·⑥ 땡처리·출처 목록·패턴 정의·주차 정의·다른 노선/기존 딜·`noSale`·
    당일치기 메타는 값 대조로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-09 `notes` 끝에 이번 병합
    문장을 덧붙인다(plain text — 별표 금지). `extended` 끝에 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_groupB_sep.py --dry-run
    python3 tools/merge_flights_groupB_sep.py
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
    ROOT, '..', 'memory', 'clones', 'f0ee2d96-jin_5', 'pickle', '2026-11-20-1358',
    'received', '0-2027-09-groupB-rest.csv'))

WD = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}   # datetime.weekday()
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
CITY = {'SIN': '싱가포르', 'GUM': '괌', 'NGO': '나고야', 'OKA': '오키나와', 'HGH': '항저우',
        'TAO': '칭다오', 'HAN': '하노이', 'CNX': '치앙마이', 'DPS': '발리', 'KHH': '가오슝',
        'RMQ': '타이중', 'BJS': '베이징'}
MONTH = '2027-09'
GRID_START, GRID_END = '2027-09-02', '2027-10-04'
WEEK_THU = ('2027-09-02', '2027-09-09', '2027-09-16', '2027-09-23', '2027-09-30')
WEEK_LABEL = {'2027-09-02': '9/2~6', '2027-09-09': '9/9~13', '2027-09-16': '9/16~20',
              '2027-09-23': '9/23~27', '2027-09-30': '9/30~10/4'}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver', '아고다', '부킹', '호텔스컴바인', '마이리얼트립', '야놀자', '여기어때',
          '액세스레일')
# 같은 항공사를 띄어쓰기만 달리 적은 원본 표기 → 앱에 이미 많은 쪽 표기
AIRLINE_FIX = {
    '홍콩익스프레스항공': '홍콩 익스프레스항공',
    '트리니티항공·홍콩익스프레스항공': '트리니티항공·홍콩 익스프레스항공',
    '트리니티항공·일본트랜스오션항공': '트리니티항공·일본 트랜스오션항공',
    '대한항공·타이거항공타이완': '대한항공·타이거항공 타이완',
    '캐세이퍼시픽항공(홍콩익스프레스 운항)': '캐세이퍼시픽항공(홍콩 익스프레스 운항)',
    '싱가포르항공(스쿠트 운항)': '싱가포르항공(스쿠트항공 운항)',
}

# 원본 보고서(1-2027-09-groupB-rest.md)의 집계 — 파서가 같은 숫자를 내는지 대조한다
EXPECT_CELLS = 300            # CSV 300행 = 300칸 전수
EXPECT_VALUES = 300           # 그중 금액이 있는 칸
EXPECT_NOSALE = 0             # 판매편 0건(NA) 0칸
EXPECT_GRID = 300             # 12노선 × 5주 × 5패턴
EXPECT_REPLACE = 12           # 앱에 있던 2027-10-01 금~일 앞선 조회 칸 → 실측값 교체
EXPECT_NEW = 288              # 새로 넣는 칸
EXPECT_OVERALL = (420800, 1101700)       # 발리 9/9~13 목~일 · 오키나와 9/30~10/4 금~월
EXPECT_SUM = 186298000
EXPECT_AVG = 620993
# 보고서 '요약'은 중앙값을 606,200원(300칸 가운데 151번째 값)으로 적었지만, 300칸은 짝수라
# 150·151번째(598,500 · 606,200)의 평균 602,350원이 중앙값이다(7·8월 B조도 같은 평균 방식).
EXPECT_MEDIAN = 602350
EXPECT_DIRECT = 34            # 최저가가 직항인 칸
EXPECT_MONTH_CELLS = {'2027-09': 264, '2027-10': 36}   # 출발일 기준(9/30주 10/1·10/2 포함)
EXPECT_PAT = {                # 패턴: (칸수, 합, 평균(반올림))
    '목~일': (60, 36504500, 608408), '금~일': (60, 37134500, 618908),
    '토~월': (60, 38227100, 637118), '금~월': (60, 37756300, 629272),
    '목~월': (60, 36675600, 611260),
}
# 노선: (값 칸수, 판매편 0건 칸수, 최저, 최고, 평균(반올림), 최저가가 직항인 칸)
EXPECT_ROUTE = {
    'SIN': (25, 0, 423300, 842300, 551436, 2),
    'GUM': (25, 0, 593400, 1090700, 758132, 0),
    'NGO': (25, 0, 491700, 874400, 665488, 0),
    'OKA': (25, 0, 519200, 1101700, 693360, 12),
    'HGH': (25, 0, 486200, 873200, 630572, 0),
    'TAO': (25, 0, 464700, 689200, 553284, 0),
    'HAN': (25, 0, 453000, 755200, 521648, 4),
    'CNX': (25, 0, 606200, 925800, 745900, 2),
    'DPS': (25, 0, 420800, 941800, 561932, 0),
    'KHH': (25, 0, 476700, 899700, 637872, 0),
    'RMQ': (25, 0, 436400, 897100, 627016, 9),
    'BJS': (25, 0, 447000, 630300, 505280, 5),
}
EXPECT_GRID_ROUTE = {c: (v[2], v[3]) for c, v in EXPECT_ROUTE.items()}
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
EXPECT_WEEK = {'2027-09-02': (60, 32872700, 547878, 420900, 845000),
               '2027-09-09': (60, 42089200, 701487, 420800, 1074600),
               '2027-09-16': (60, 39387300, 656455, 429100, 1090700),
               '2027-09-23': (60, 33533300, 558888, 428000, 832500),
               '2027-09-30': (60, 38415500, 640258, 423300, 1101700)}
EXPECT_WEEK_AVG = {k: v[2] for k, v in EXPECT_WEEK.items()}
# 10만원 단위 구간 분포
EXPECT_BUCKET = {'30만원 미만': 0, '30만~40만원': 0, '40만~50만원': 77,
                 '50만~60만원': 73, '60만~70만원': 76, '70만~80만원': 33,
                 '80만~90만원': 29, '90만~100만원': 8, '100만원 이상': 4}
# 9월 달력 — 출발일: (그 날 실측 칸수, 그 날 최저, 그 날 최고)
EXPECT_DAY = {'2027-09-02': (24, 464700, 641600), '2027-09-03': (24, 437200, 845000),
              '2027-09-04': (12, 420900, 845000), '2027-09-09': (24, 420800, 816600),
              '2027-09-10': (24, 437900, 1074600), '2027-09-11': (12, 630300, 1074600),
              '2027-09-16': (24, 484700, 897100), '2027-09-17': (24, 429100, 1090700),
              '2027-09-18': (12, 442300, 874100), '2027-09-23': (24, 484200, 677100),
              '2027-09-24': (24, 437000, 832500), '2027-09-25': (12, 428000, 831500),
              '2027-09-30': (24, 427900, 899700), '2027-10-01': (24, 423300, 1101700),
              '2027-10-02': (12, 448800, 947800)}
# 원본의 장시간 경유 — 환승 12시간 이상 20시간 미만 43칸 · 20시간 이상 56칸
EXPECT_LONG = (43, 56)
EXPECT_LONG15 = 85            # 환승 대기 15시간 이상(보고서 '참고'의 85칸)
EXPECT_MAX_LAY = 1420         # 가장 긴 환승 23시간 40분
# 총 소요가 20시간을 넘는 칸
EXPECT_TOTAL_OVER_20H = 92
# 이 원본에는 '직항(항공사) N원' 꼴의 직항 최저 금액 표기가 없어 alt 를 만들지 않는다
EXPECT_ALT = {}
# '최단 …' 대안 일정을 note 에 덧붙인 칸 — 최저가 일정 자체가 최단인 1칸은 덧붙이지 않는다
EXPECT_SHORTEST = 113
EXPECT_SHORT_SAME = 1         # `…도 동일` — 최단 일정 = 최저가 일정
# 앞선 조회로 앱에 있던 12칸 — 이번 실측값으로 교체한다(기존 → 신규)
EXPECT_REPLACE_CELLS = {
    ('SIN', '2027-10-01', '금~일'): (438700, 423300),
    ('GUM', '2027-10-01', '금~일'): (953900, 833500),
    ('NGO', '2027-10-01', '금~일'): (936200, 797400),
    ('OKA', '2027-10-01', '금~일'): (764500, 955200),
    ('HGH', '2027-10-01', '금~일'): (851100, 522700),
    ('TAO', '2027-10-01', '금~일'): (636700, 582600),
    ('HAN', '2027-10-01', '금~일'): (465200, 453000),
    ('CNX', '2027-10-01', '금~일'): (947000, 920100),
    ('DPS', '2027-10-01', '금~일'): (436400, 427900),
    ('KHH', '2027-10-01', '금~일'): (923600, 647600),
    ('RMQ', '2027-10-01', '금~일'): (441100, 437300),
    ('BJS', '2027-10-01', '금~일'): (633600, 592000),
}
EXPECT_REPLACE_OLD_AVG = 702333
EXPECT_REPLACE_NEW_AVG = 632717
# 이번 원본이 쓴 note 꼴 — 출발-도착 시각이 괄호 앞 공백 뒤에 붙는다
GRP_B_SEP_NOTE = re.compile(r' \(\d\d:\d\d-\d\d:\d\d[^)]*\)')
RAIL_NOTE = re.compile(r'^액세스레일 결합 상품(?:\(([\d,]+)원\))? 제외$')
SHORTEST_NOTE = re.compile(r'^최단 일정\((.+)\)(도 동일)? ([\d,]+)원(?:\([\d:]+ 재확인\))?$')
LAY_NOTE = re.compile(r'^최저가 일정 환승 (\d+시간(?:\s?\d+분)?)$')
RELINK_NOTE = re.compile(r'^첫 로드에서 \d+건 표시 → 재조회로 확보$')


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
    """'9시간 5분' → '9시간 05분', '1시간' → '1시간', '21시간5분' → '21시간 05분'."""
    text = text.strip().replace('  ', ' ')
    m = re.fullmatch(r'(\d+)\s*시간\s*(\d+)?\s*분?', text)
    if m:
        return m.group(1) + '시간' + ((' ' + m.group(2).rjust(2, '0') + '분')
                                     if m.group(2) else '')
    m = re.fullmatch(r'(\d+)\s*분', text)
    if m:
        return m.group(1).rjust(2, '0') + '분'
    raise SystemExit('소요시간 형식 이상: %r' % text)


def build_note(row):
    """CSV 한 줄 → (note, via, alt, 태그). 원본 비고는 note 끝에 살린다."""
    kind = row['direct_or_via'].strip()
    times = row['times'].strip()
    dur = row['duration'].strip()
    city = row['via_city'].strip()
    lay = ''
    hops = [h.strip() for h in city.replace('(2회)', '').split('·') if h.strip()]
    hops = [h.replace('(인천)', '').replace('호찌민시', '호찌민').replace('호치민', '호찌민')
            for h in hops]
    if kind == '직항':
        if city:
            raise SystemExit('직항인데 경유지가 있습니다: %r' % row)
        note, via = '직항 ' + norm_dur(dur) + ' (' + times + ')', False
    elif kind == '경유':
        via = True
        m = re.fullmatch(r'총\s*(.+?)\((.*)\)', dur)
        if not m:
            raise SystemExit('경유 소요시간을 읽지 못했습니다: %r' % dur)
        total, inner = m.group(1).strip(), m.group(2).strip()
        if not inner.startswith('환승'):
            raise SystemExit('환승 문장을 읽지 못했습니다: %r' % inner)
        rest = inner[2:].strip()
        if re.fullmatch(r'\d+회', rest):
            if rest != '%d회' % len(hops) or len(hops) < 2:
                raise SystemExit('%s 환승 횟수와 경유지가 맞지 않습니다: %r / %r'
                                 % (row['dep'], dur, city))
            note = '경유 %d회(%s) · 총 %s (%s)' % (len(hops), '·'.join(hops),
                                                 norm_dur(total), times)
        else:
            if len(hops) != 1:
                raise SystemExit('경유지가 한 곳이 아닙니다: %r' % row)
            lay = norm_dur(rest)
            note = ('경유 1회(%s) · 환승 %s · 총 %s (%s)'
                    % (hops[0], lay, norm_dur(total), times))
    else:
        raise SystemExit('편성 표기를 읽지 못했습니다: %r' % kind)

    pieces = [p.strip() for p in row['note'].split(' · ')]
    if not re.match(r'^2026-11-20 \d\d:\d\d KST 실측$', pieces[0]):
        raise SystemExit('실측 시각 표기를 읽지 못했습니다: %r' % pieces[0])
    alt, tags = None, {'shortest': 0, 'same': 0, 'rail': 0, 'relink': 0}
    for p in pieces[1:]:
        m = LAY_NOTE.match(p)
        if m:                                   # duration 의 환승 시간과 같은 값 — 중복
            if not lay:
                raise SystemExit('%s 환승 시간이 없는 칸에 환승 비고: %r' % (row['dep'], p))
            if norm_dur(m.group(1)) != lay:
                raise SystemExit('%s 최저가 일정 환승이 소요와 다릅니다: %r / %r'
                                 % (row['dep'], m.group(1), lay))
            continue
        m = SHORTEST_NOTE.match(p)
        if m:
            inner, same, price = m.group(1), bool(m.group(2)), int(m.group(3).replace(',', ''))
            mm = re.fullmatch(r'(.+?) (\d+시간(?:\s\d+분)?|\d+분)', inner)
            if not mm:
                raise SystemExit('%s 최단 일정의 소요를 읽지 못했습니다: %r'
                                 % (row['dep'], inner))
            air, dur2 = mm.group(1).strip(), norm_dur(mm.group(2))
            if same:
                if price != int(row['price_krw']):
                    raise SystemExit('%s 최단 일정 동일 금액이 최저가와 다릅니다: %r'
                                     % (row['dep'], p))
                tags['same'] += 1
                continue
            if price < int(row['price_krw']):
                raise SystemExit('%s 최단 일정 금액이 최저가보다 쌉니다: %r'
                                 % (row['dep'], p))
            note += ' · 최단 %s %s원(%s)' % (dur2, format(price, ','), air)
            tags['shortest'] += 1
            continue
        m = RAIL_NOTE.match(p)
        if m:
            note += (' · 철도+항공 결합상품' + (' %s원' % format(int(m.group(1).replace(',', '')),
                                                          ',') if m.group(1) else '')
                     + '은 항공권이 아니어서 제외')
            tags['rail'] += 1
            continue
        if RELINK_NOTE.match(p):
            tags['relink'] += 1
            continue
        raise SystemExit('%s 처리하지 못한 비고: %r' % (row['dep'], p))
    return note, via, alt, tags


def parse(path):
    if not os.path.isfile(path):
        raise SystemExit('원본 CSV 가 없습니다: %s' % path)
    cells = {}
    tags = collections.Counter()
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
            if row['status'] == 'NA':
                raise SystemExit('%s: 이 원본에는 판매편 0건 칸이 없어야 합니다: %r'
                                 % (code, row))
            if row['status'] != '값':
                raise SystemExit('%s 상태가 값이 아닙니다: %r' % (row['dep'], row['status']))
            price = int(row['price_krw'])
            if price <= 0:
                raise SystemExit('%s 금액이 양의 정수가 아닙니다' % code)
            note, via, alt, tg = build_note(row)
            tags.update(tg)
            if '**' in note or '[' in note or '출처' in note:
                raise SystemExit('%s note 에 마크업이 있습니다: %r' % (code, note))
            if via and '총' not in note:
                raise SystemExit('%s 경유 칸에 총 소요시간이 없습니다: %r' % (code, note))
            if not via and '직항' not in note:
                raise SystemExit('%s 직항 칸 note 이상: %r' % (code, note))
            if not GRP_B_SEP_NOTE.search(note):
                raise SystemExit('%s note 에 출발-도착 시각이 없습니다: %r' % (code, note))
            airline = row['airline'].strip()
            airline = AIRLINE_FIX.get(airline, airline) or None
            for word in BANNED:
                if word in note or word in (airline or ''):
                    raise SystemExit('%s 값에 제3자 사이트·상품 이름(%s)이 있습니다' % (code, word))
            cells[key] = dict(code=code, date=row['dep'], back=row['ret'], pattern=pat,
                              price=price, airline=airline, via=via, alt=alt,
                              note=note, ord=ord_)
    return cells, tags


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
        raise SystemExit('중앙값 %s (기대 %s)' % (median(ps), EXPECT_MEDIAN))
    for pat, (cnt, total, avg) in EXPECT_PAT.items():
        v = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if len(v) != cnt or sum(v) != total or rnd(sum(v) / len(v)) != avg:
            raise SystemExit('%s 집계 %s (원문 %s)'
                             % (pat, (len(v), sum(v), rnd(sum(v) / len(v))),
                                (cnt, total, avg)))
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
    # 출발일별 — 그 날 칸수와 최저/최고
    per_day = collections.defaultdict(list)
    for c in cells.values():
        per_day[c['date']].append(c['price'])
    for date, (cnt, low, high) in EXPECT_DAY.items():
        got = per_day.get(date)
        if not got or (len(got), min(got), max(got)) != (cnt, low, high):
            raise SystemExit('%s 달력 집계 %s (원문 %s)'
                             % (date, got and (len(got), min(got), max(got)),
                                (cnt, low, high)))
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
    names = ('30만원 미만', '30만~40만원', '40만~50만원', '50만~60만원',
             '60만~70만원', '70만~80만원', '80만~90만원', '90만~100만원', '100만원 이상')
    edges = (300000, 400000, 500000, 600000, 700000, 800000, 900000, 1000000)
    bucket = collections.Counter({k: 0 for k in EXPECT_BUCKET})
    for p in ps:
        bucket[names[sum(1 for e in edges if p >= e)]] += 1
    if dict(bucket) != EXPECT_BUCKET:
        raise SystemExit('구간 분포 %s (원문 %s)' % (dict(bucket), EXPECT_BUCKET))
    # 월별 칸수
    mcount = collections.Counter(c['date'][:7] for c in cells.values())
    if dict(mcount) != EXPECT_MONTH_CELLS:
        raise SystemExit('월별 %s (기대 %s)' % (dict(mcount), EXPECT_MONTH_CELLS))
    # 장시간 경유 — 앱과 같은 식(환승 N시간)
    lay_min = []
    for c in cells.values():
        m = re.search(r'환승\s*(\d+)시간\s*(?:(?:\s)?(\d+)분)?', c['note'] if c['via'] else '')
        if m:
            lay_min.append(int(m.group(1)) * 60 + int(m.group(2) or 0))
    got_long = (sum(1 for x in lay_min if 720 <= x < 1200),
                sum(1 for x in lay_min if x >= 1200))
    if got_long != EXPECT_LONG:
        raise SystemExit('장시간 경유 %s (기대 %s)' % (got_long, EXPECT_LONG))
    if sum(1 for x in lay_min if x >= 900) != EXPECT_LONG15:
        raise SystemExit('환승 15시간 이상 %d칸 (보고서 %d칸)'
                         % (sum(1 for x in lay_min if x >= 900), EXPECT_LONG15))
    if max(lay_min) != EXPECT_MAX_LAY:
        raise SystemExit('가장 긴 환승 %d분 (기대 %d분)' % (max(lay_min), EXPECT_MAX_LAY))
    # 총 소요 20시간 초과
    over = 0
    for c in cells.values():
        m = re.search(r'총\s*(\d+)시간\s*(?:(\d+)분)?', c['note']) or \
            re.search(r'직항\s*(\d+)시간\s*(?:(\d+)분)?', c['note'])
        if m and int(m.group(1)) * 60 + int(m.group(2) or 0) > 1200:
            over += 1
    if over != EXPECT_TOTAL_OVER_20H:
        raise SystemExit('총 소요 20시간 초과 %d칸 (원문 %d칸)' % (over, EXPECT_TOTAL_OVER_20H))
    # 직항 최저 금액(alt) — 이 원본에는 없다
    got_alt = {k: c['alt'] for k, c in cells.items() if c['alt'] is not None}
    if got_alt != EXPECT_ALT:
        raise SystemExit('직항 최저 금액 칸이 다릅니다: %s' % sorted(got_alt))
    short = sum(1 for c in cells.values() if '최단 ' in c['note'])
    if short != EXPECT_SHORTEST:
        raise SystemExit('최단 대안을 적은 칸 %d (기대 %d)' % (short, EXPECT_SHORTEST))
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


def dur_of(note, kind='총'):
    m = re.search(kind + r'\s*(\S+(?: \d+분)?)', note)
    return m.group(1) if m else ''


def cell_text(d):
    """'발리 9/9~12 목~일 420,800원(베트남항공 경유 1회(하노이) ...)'"""
    air = d.get('airline') or '항공사 미확인'
    note = d.get('note') or ''
    m = re.match(r'^직항 (\S+(?: \d+분)?) \(([^)]*)\)', note)
    if m:
        detail = '직항 %s, %s' % (m.group(1), m.group(2))
    else:
        hops = re.search(r'(경유 \d회\([^)]*\))', note)
        lay = re.search(r'환승 (\d+시간(?: \d+분)?)', note)
        tot = dur_of(note)
        when = re.search(r'\((\d\d:\d\d-\d\d:\d\d[^)]*)\)', note)
        detail = hops.group(1) if hops else '경유지 미표기'
        if lay:
            detail += ' 환승 %s' % lay.group(1)
        if tot:
            detail += ' · 총 %s' % tot
        if when:
            detail += ', %s' % when.group(1)
    return '%s %s %s %s원(%s %s)' % (CITY[d['code']], span_text(d), d['pattern'],
                                     format(d['price'], ','), air, detail)


def month_note(grid, replaced, tags):
    ps = [d['price'] for d in grid]
    avg = rnd(sum(ps) / len(ps))
    pat = collections.defaultdict(list)
    for d in grid:
        pat[d['pattern']].append(d['price'])
    pat_avg = sorted(((p, rnd(sum(v) / len(v))) for p, v in pat.items()),
                     key=lambda kv: kv[1])
    wk = collections.defaultdict(list)
    for d in grid:
        dt = datetime.date.fromisoformat(d['date'])
        wk[(dt - datetime.timedelta(days=(dt.weekday() - WD['목']) % 7)).isoformat()] \
            .append(d['price'])
    week_avg = [(WEEK_LABEL[k], rnd(sum(v) / len(v))) for k, v in sorted(wk.items())]
    lo_w = min(week_avg, key=lambda t: (t[1], t[0]))
    hi_w = min(week_avg, key=lambda t: (-t[1], t[0]))
    week_ratio = '%.1f' % (abs(hi_w[1] / lo_w[1] - 1) * 100)
    direct = sum(1 for d in grid if d.get('via') is False)
    nodirect = [c for c in ROUTES
                if not any(d.get('via') is False for d in grid if d['code'] == c)]
    by_direct = collections.Counter(d['code'] for d in grid if d.get('via') is False)
    direct_text = ' · '.join('%s %d' % (CITY[c], n) for c, n in by_direct.most_common())
    lo = min(grid, key=lambda d: (d['price'], d['code'], d['pattern']))
    hi = min(grid, key=lambda d: (-d['price'], d['code'], d['pattern']))
    rep_old = rnd(sum(r[1] for r in replaced) / len(replaced))
    rep_new = rnd(sum(r[2] for r in replaced) / len(replaced))
    names = ('30만원 미만', '30만~40만원', '40만~50만원', '50만~60만원',
             '60만~70만원', '70만~80만원', '80만~90만원', '90만~100만원', '100만원 이상')
    edges = (300000, 400000, 500000, 600000, 700000, 800000, 900000, 1000000)
    bucket = collections.Counter({k: 0 for k in names})
    for p in ps:
        bucket[names[sum(1 for e in edges if p >= e)]] += 1
    bucket_text = ' · '.join('%s %d칸' % (k, bucket[k]) for k in names if bucket[k])
    longs = []
    for d in grid:
        if d.get('via') is not True:
            continue
        m = re.search(r'환승 (\d+)시간(?: (\d+)분)?', d['note'])
        if not m:
            continue
        v = int(m.group(1)) * 60 + int(m.group(2) or 0)
        longs.append((v, d, m.group(0)[3:]))
    longs.sort(key=lambda t: -t[0])
    long_text = ' · '.join('%s %s %s 환승 %s(총 %s)'
                           % (CITY[d['code']], span_text(d), d['pattern'], l, dur_of(d['note']))
                           for _, d, l in longs[:2])
    short_n = sum(1 for d in grid if '최단 ' in d['note'])
    rail_n = sum(1 for d in grid if '철도+항공 결합상품' in d['note'])
    sent = (
        '2027년 9월은 부산 출발 B조 12개 노선(싱가포르·괌·나고야·오키나와·항저우·칭다오·'
        '하노이·치앙마이·발리·가오슝·타이중·베이징)의 5주(9/2~6 · 9/9~13 · 9/16~20 · '
        '9/23~27 · 9/30~10/4) 5패턴 300칸을 전수 실측해 넣었습니다 — 이 격자에 앞선 조회로만 '
        '있던 ' + str(len(replaced)) + '칸(12노선 10/1 금~일, 항공사·소요·시각 없이 경유·직항 '
        '여부만 있던 칸)은 같은 노선·출발일·패턴의 실측값(항공사·경유지·소요·시각 포함)으로 '
        '교체했고(교체 칸 평균 ' + format(rep_old, ',') + '원 → ' + format(rep_new, ',')
        + '원), 빈칸 ' + str(len(grid) - len(replaced)) + '칸을 새로 넣어 이 다섯 주 5패턴이 '
        + str(len(grid)) + '/300칸 모두 금액입니다(판매편 0건 0칸 · 편성 미확인 0칸 · '
        '추정·보간 없음). 9/30주(9/30~10/6)는 9/30 출발 24칸을 9월로 세고, 10/1·10/2 출발 '
        '36칸(10/1 금~일·금~월, 10/2 토~월)은 10월 출발이며 이 가운데 10/1 금~일 12칸은 앞선 '
        '조회분을 교체한 칸입니다. 이 격자 최저는 ' + cell_text(lo) + '이고, 최고는 '
        + cell_text(hi) + '으로 최저의 ' + ('%.2f' % (hi['price'] / lo['price'])) + '배입니다. '
        '300칸 평균 ' + format(avg, ',') + '원 · 중앙값 ' + format(median(ps), ',') + '원'
        '(300칸은 짝수라 150·151번째 값 598,500 · 606,200의 평균 — 원본 보고서는 606,200으로 '
        '적었습니다)이고 '
        '주차 평균은 ' + ' · '.join('%s %s원' % (w, format(v, ',')) for w, v in week_avg)
        + '으로 ' + ('%s 주가 %s 주보다 ' % (hi_w[0], lo_w[0])) + week_ratio + '% 비쌉니다. 패턴 평균은 '
        + ' < '.join('%s %s원' % (p, format(v, ',')) for p, v in pat_avg)
        + ' 순입니다(1·5위 차 ' + format(pat_avg[-1][1] - pat_avg[0][1], ',') + '원). '
        '최저가가 직항인 칸은 ' + str(direct) + '칸(' + direct_text + ')이고 경유 '
        + str(len(grid) - direct) + '칸이며, ' + '·'.join(CITY[c] for c in nodirect) + ' '
        + str(len(nodirect)) + '개 노선은 25칸 모두 최저가가 경유입니다. 10만원 단위로는 '
        + bucket_text + '입니다. 경유 대기가 긴 칸은 ' + long_text + ' 등이고, 환승 12시간 '
        '이상 20시간 미만이 ' + str(EXPECT_LONG[0]) + '칸 · 20시간 이상이 '
        + str(EXPECT_LONG[1]) + '칸(15시간 이상 85칸)이라 앱의 경유 12h+ · 20h+ 경고가 붙으며, '
        '총 소요가 20시간을 넘는 칸은 ' + str(EXPECT_TOTAL_OVER_20H) + '칸입니다. 원본이 함께 '
        '적은 값도 살렸습니다 — 최저가 일정보다 짧은 대안 일정이 조회된 ' + str(short_n)
        + '칸은 note 에 그 소요·금액·항공사를 덧붙였고, 조회 화면의 최저가 카드가 철도+항공 '
        '결합상품이던 ' + str(rail_n) + '칸은 상품 이름 없이 결합상품 금액만 적어 제외했습니다. '
        '이 원본에는 직항 최저 금액 표기와 잔여 9석 표기가 없어 직항 금액(alt)과 잔여석 표시를 '
        '만들지 않았습니다.')
    return sent


def main(argv):
    ap = argparse.ArgumentParser(description='B조 12노선 2027년 9월 5주 300칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--csv', default=CSV_DEFAULT)
    ap.add_argument('--note', default=None)
    args = ap.parse_args(argv)

    parsed, tags = parse(args.csv)
    cells = check(parsed)
    print('파싱 %d칸 — 값 %d — 최저 %s · 최고 %s · 평균 %s · 직항이 최저인 칸 %d · 경유 %d'
          % (len(cells), len(cells),
             format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ','),
             format(rnd(sum(c['price'] for c in cells.values()) / len(cells)), ','),
             sum(1 for c in cells.values() if c['via'] is False),
             sum(1 for c in cells.values() if c['via'] is True)))
    print('비고 살림 — 최단 대안 %d칸 · 최단=최저가 %d칸 · 철도 결합상품 %d칸 · 재조회 확보 %d칸'
          % (tags['shortest'], tags['same'], tags['rail'], tags['relink']))
    if tags['shortest'] != EXPECT_SHORTEST or tags['same'] != EXPECT_SHORT_SAME:
        raise SystemExit('최단 대안 칸수가 다릅니다: %s' % dict(tags))

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
    before_sep = fl['counts']['byMonth'][MONTH]
    before_oct = fl['counts']['byMonth']['2027-10']
    before_weekend = sum(1 for r in fl['routes'] for d in r['deals']
                         if d['date'] >= '2027-06-01'
                         and d['pattern'].split('~')[0] != d['pattern'].split('~')[-1])
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])

    # 이 격자에 이미 있던 칸 — 12노선 10/1 금~일 앞선 조회분만 교체 대상이다
    existing, odd = {}, []
    for code in ROUTES:
        for d in routes[code]['deals']:
            if not (GRID_START <= d['date'] <= GRID_END):
                continue          # 이번 조사 범위 밖(다른 달)은 건드리지 않는다
            if d['pattern'] not in PAT_NIGHTS:
                odd.append((code, d['date'], d['pattern']))
                continue          # 0박 당일치기는 이번 조사 대상이 아니다
            existing[(code, d['date'], d['pattern'])] = d
    if odd:
        raise SystemExit('이 범위에 5패턴이 아닌 기존 칸: %s' % odd)
    if len(existing) != EXPECT_REPLACE:
        raise SystemExit('기존 칸 %d개 (기대 %d개): %s'
                         % (len(existing), EXPECT_REPLACE, sorted(existing)))
    for key, (old_want, new_want) in EXPECT_REPLACE_CELLS.items():
        got = existing.get(key)
        if got is None:
            raise SystemExit('교체할 기존 칸이 없습니다: %s' % (key,))
        if got['price'] != old_want or cells[key]['price'] != new_want:
            raise SystemExit('교체 칸 금액이 다릅니다: %s 기존 %s → 신규 %s (보고서 %s → %s)'
                             % (key, got['price'], cells[key]['price'], old_want, new_want))
        if got.get('airline') or GRP_B_SEP_NOTE.search(got.get('note') or ''):
            raise SystemExit('교체 칸이 이미 상세 실측값입니다: %s %r' % (key, got.get('note')))
    old_avg = rnd(sum(d['price'] for d in existing.values()) / len(existing))
    new_avg = rnd(sum(cells[k]['price'] for k in existing) / len(existing))
    if (old_avg, new_avg) != (EXPECT_REPLACE_OLD_AVG, EXPECT_REPLACE_NEW_AVG):
        raise SystemExit('교체 칸 평균 %s → %s (기대 %s → %s)'
                         % (old_avg, new_avg, EXPECT_REPLACE_OLD_AVG, EXPECT_REPLACE_NEW_AVG))
    new_keys = set(cells) - set(existing)
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
    print('기존 %d칸 교체(평균 %s원 → %s원) · 새 칸 %d칸 추가'
          % (len(existing), format(old_avg, ','), format(new_avg, ','), len(new_keys)))

    def make(v):
        deal = collections.OrderedDict()
        deal['date'] = v['date']
        deal['back'] = v['back']
        deal['pattern'] = v['pattern']
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt'] is not None:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        return json.loads(json.dumps(deal))

    replaced = []
    for key in sorted(existing):
        code, date, pat = key
        old = existing[key]
        deals = routes[code]['deals']
        idx = next(i for i, d in enumerate(deals) if (d['date'], d['pattern']) == (date, pat))
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
                    raise SystemExit('%s %s 값에 제3자 사이트·상품 이름(%s)이 있습니다'
                                     % (code, d['date'], word))

    counts = recount(fl)
    if counts['total'] != before_total + len(added):
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], before_total + len(added)))
    if counts['byMonth'][MONTH] != before_sep + len([k for k in added if k[1][:7] == MONTH]):
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                 before_sep + len([k for k in added
                                                                   if k[1][:7] == MONTH])))
    week_after = sum(1 for r in fl['routes'] for d in r['deals']
                     if d['date'] >= '2027-06-01'
                     and d['pattern'].split('~')[0] != d['pattern'].split('~')[-1])
    if week_after != before_weekend + len(added):
        raise SystemExit('6~11월 주말형 %d건 (기대 %d건)' % (week_after,
                                                        before_weekend + len(added)))

    # 병합 뒤 격자 300칸 검사
    grid = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if GRID_START <= d['date'] <= GRID_END
            and d['pattern'] in PAT_NIGHTS]
    if len(grid) != EXPECT_GRID:
        raise SystemExit('이 격자 %d칸 (기대 %d칸)' % (len(grid), EXPECT_GRID))
    if [d for d in grid if not d.get('price')]:
        raise SystemExit('금액 없는 칸이 있습니다')
    if [d for d in grid if d.get('src')]:
        raise SystemExit('앞선 조회 표시(src)가 남아 있습니다')
    if [d for d in grid if not d.get('note')]:
        raise SystemExit('note 없는 칸이 있습니다')
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
        if len(v) != 25 or (min(v), max(v)) != (low, high):
            raise SystemExit('격자 %s %d칸 %s (기대 (25, %s))'
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
    got_alt = {(d['code'], d['date'], d['pattern']): d['alt'] for d in grid if d.get('alt')}
    if got_alt != EXPECT_ALT:
        raise SystemExit('격자 직항 최저 금액이 다릅니다: %s' % sorted(got_alt))
    for d in grid:
        note = d['note']
        if d.get('via') is True and '총' not in note:
            raise SystemExit('%s %s 경유 칸에 총 소요시간이 없습니다' % (d['code'], d['date']))
        if d.get('via') is False and '직항' not in note:
            raise SystemExit('%s %s 직항 칸 note 이상' % (d['code'], d['date']))
        if not GRP_B_SEP_NOTE.search(note):
            raise SystemExit('%s %s note 에 출발-도착 시각이 없습니다: %r'
                             % (d['code'], d['date'], note))
        if ('가격표' in note or '2026-11' in note or '액세스레일' in note
                or '구성 미확인' in note or '최저가 편' in note):
            raise SystemExit('%s %s note 에 자리표시·조사 시각·상품 이름이 남았습니다'
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
            if key3 in existing:          # 이번에 교체한 칸만 달라져야 한다
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

    month_sent = month_note(grid, replaced, tags)
    if '**' in month_sent or '[' in month_sent:
        raise SystemExit('notes 문장에 마크업이 있습니다')
    for word in BANNED:
        if word in month_sent:
            raise SystemExit('notes 문장에 제3자 사이트·상품 이름(%s)이 있습니다' % word)
    fl['notes'][MONTH] = fl['notes'][MONTH].rstrip() + ' ' + month_sent
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    note = args.note or (
        '2026-11-20 KST ⑤ 항공 부산 출발 B조 12개 노선 2027년 9월 5주(9/2~6 · 9/9~13 · '
        '9/16~20 · 9/23~27 · 9/30~10/4) 5패턴 300칸 완결 — 앞선 조회 12칸(10/1 금~일) 교체 + '
        '빈칸 288칸 실측, 최저 발리 9/9~13 목~일 420,800원, 직항이 최저가인 칸 %d, '
        '총 %s→%s건'
        % (direct, format(before_total, ','), format(counts['total'], ',')))
    master['extended'] = (before_extended + ' / ' + note).strip(' /')

    print('교체 %d칸 + 신규 %d칸 · 격자 %d칸 모두 금액 · 최저 %s · 최고 %s'
          % (len(replaced), len(added), len(grid),
             format(min(ps), ','), format(max(ps), ',')))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'],
             counts['daytrip']))
    print('2027-09 %d → %d건 · 2027-10 %d → %d건'
          % (before_sep, counts['byMonth'][MONTH], before_oct, counts['byMonth']['2027-10']))
    print('환승 12시간 이상 20시간 미만 %d칸 · 20시간 이상 %d칸'
          % (EXPECT_LONG[0], EXPECT_LONG[1]))
    print('최단 대안 병기 %d칸 · 철도 결합상품 비고 %d칸' % (EXPECT_SHORTEST, tags['rail']))
    print('notes[2027-09] 새 문장:', month_sent)
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
