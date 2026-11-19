#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **A조 12개 노선의 2027년 9월 5주(9/2~6 · 9/9~13 · 9/16~20 · 9/23~27 · 9/30~10/4)
5패턴 300칸** 가운데 빈칸 245칸을 실측한 원본과, 대상 외 재확인 1칸(방콕 10/1 금~일)을
`data/master_db.json` 의 `flights` 에 병합한다.

원본 1개(5번 보고서 `0-2027-09-groupA-rest.csv` + `1-2027-09-groupA-rest.md`,
2026-11-19 23:14~2026-11-20 00:40 KST 실측) — 성인 1인 왕복 총액(유류·세금 포함, KRW).

  · 노선 12개: 후쿠오카·오사카·도쿄·타이베이·홍콩·마카오·상하이·방콕·다낭·나트랑·난징·호찌민
  · CSV 246줄: route, week, pattern, dep, ret, nights, price_krw, airline, direct_or_via,
    via_city, duration, times, status, note
  · 12노선 × 5패턴 × 5주 = 300칸 가운데 **245칸은 웹앱에 없던 빈칸**이고, 1칸(방콕 10/1 금~일)은
    앱에 이미 있던 값을 같은 조건으로 다시 조회한 '대상 외 재확인' 칸이라 최신 실측으로 교체한다.
    나머지 54칸(앱에 이미 값이 있던 칸)은 이번 조사 대상이 아니므로 손대지 않는다
    (그중 나트랑·호찌민 10/1 금~일 2칸은 금액만 있고 편성이 확인되지 않은 `via: null` 칸).
  · 병합 뒤 300칸이 모두 금액을 가진다(자리표시·미조회 0칸).

규칙:
  · `via` 는 그 칸 **최저가 편성**이 직항(`false`)·경유(`true`)인지로 적는다.
  · `note` 는 기존 앱 표기(`경유 1회(서울) · 환승 3시간 20분 · 총 6시간 10분 (08:45-14:55)`,
    `직항 1시간 30분 (13:00-14:30)`) 꼴로 적는다 — 앱의 장시간 경유 배지가 note 의
    `환승 N시간` 을 읽어 12h+/20h+ 를 계산한다(flDur/flLongClass).
  · 환승 시간 대신 '환승 N회'만 표기된 칸(호찌민 4칸)은 경유 횟수와 다를 때만 총 소요 뒤에
    `환승 N회`를 붙이고(호찌민 9/16주 2칸) 환승 시간을 지어내지 않는다. 경유지가 '미표기'인
    칸(다낭 1 · 나트랑 2)은 `경유(경유지 미표기) · 총 …` 로 적는다.
  · 호찌민 9/16주 목요일 출발 2칸은 최저가가 항공 단독이 아니라 부산역(XMB)에서 서울까지
    철도로 이동한 뒤 항공으로 이어지는 연계 상품이다 — 원본 비고를 그대로 살려
    `XMB(부산역) 출발 철도+항공 연계` 를 note 끝에 붙인다.
  · 원본 CSV 의 실측 시각(`2026-11-20 00:31 KST 실측`)은 값이 아니라 조사 시각이므로 note 에 넣지 않는다.
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · ⑥ 땡처리 · 출처 목록 · 패턴 정의 · 주차 정의 · 다른 노선/기존 딜·`noSale` 은
    값 대조로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-09 `notes` 끝에 이번 병합
    문장을 덧붙인다(plain text — `**` 금지). `extended` 끝에 한 줄을 덧붙인다(`--note`).
  · 이 원본에는 '직항 최저 …원'·'잔여 9석 미만' 표기가 없으므로 `alt`·9석 미만 표시를 만들지 않는다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_groupA_sep.py --dry-run
    python3 tools/merge_flights_groupA_sep.py
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
    ROOT, '..', 'memory', 'clones', 'f0ee2d96-jin_5', 'pickle', '2026-11-20-0038',
    'received', '0-2027-09-groupA-rest.csv'))

WD = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}   # datetime.weekday()
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN')
CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'TPE': '타이베이', 'HKG': '홍콩',
        'MFM': '마카오', 'PVG': '상하이', 'BKK': '방콕', 'DAD': '다낭', 'CXR': '나트랑',
        'NKG': '난징', 'SGN': '호찌민'}
MONTH = '2027-09'
GRID_START, GRID_END = '2027-09-02', '2027-10-02'   # 9/2주 목요일 ~ 9/30주 토~월(10/2)
WEEK_THU = ('2027-09-02', '2027-09-09', '2027-09-16', '2027-09-23', '2027-09-30')
WEEK_LABEL = {'2027-09-02': '9/2~6', '2027-09-09': '9/9~13', '2027-09-16': '9/16~20',
              '2027-09-23': '9/23~27', '2027-09-30': '9/30~10/4'}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver', '아고다', '부킹', '호텔스컴바인', '마이리얼트립', '야놀자', '여기어때')
# 원본의 항공사 표기를 앱 표기(괄호)로 다듬는다 — 뜻은 그대로, 운항사만 괄호로
AIRLINE_FIX = {'캐세이퍼시픽항공 홍콩 익스프레스항공에서 운항': '캐세이퍼시픽항공(홍콩 익스프레스항공 운항)',
               '베트남항공 퍼시픽 항공에서 운항': '베트남항공(퍼시픽 항공 운항)'}

# 원본 보고서(1-2027-09-groupA-rest.md)의 집계 — 파서가 같은 숫자를 내는지 대조한다
EXPECT_CELLS = 246            # CSV 246행 = 대상 빈칸 245칸 + 대상 외 재확인 1칸
EXPECT_NEW = 245
EXPECT_REPLACED = 1
EXPECT_GRID = 300             # 12노선 × 5주 × 5패턴
EXPECT_EXISTING = 55          # 병합 전 이 격자에 이미 있던 값(그중 1칸을 재확인 교체)
EXPECT_MONTH_CELLS = {'2027-09': 229, '2027-10': 16}   # 출발일 기준 월별 (재확인 1칸 제외)
EXPECT_OVERALL = (276600, 874200)      # 상하이 9/4 토~월 · 마카오 9/11 토~월
EXPECT_SUM = 124554300
EXPECT_AVG = 506318
EXPECT_PAT_SUM = {'금~일': 14521500, '토~월': 25944800, '목~일': 28290900,
                  '금~월': 28275900, '목~월': 27521200}
EXPECT_PAT_CELLS = {'금~일': 27, '토~월': 52, '목~일': 55, '금~월': 56, '목~월': 56}
EXPECT_PAT_AVG = {'금~일': 537833, '토~월': 498938, '목~일': 514380,
                  '금~월': 504927, '목~월': 491450}
EXPECT_DIRECT = 110
EXPECT_WEEK_NEW = {'2027-09-02': 54, '2027-09-09': 55, '2027-09-16': 49,
                   '2027-09-23': 56, '2027-09-30': 31}
EXPECT_WEEK_AVG = {'2027-09-02': 481581, '2027-09-09': 536347, '2027-09-16': 526751,
                   '2027-09-23': 479175, '2027-09-30': 512663}
EXPECT_BUCKET = {'40만원 미만': 34, '40만~50만원': 102, '50만~60만원': 73,
                 '60만~70만원': 19, '70만원 이상': 18}
# 노선: (칸수, 최저, 최고, 평균(반올림), 최저가가 직항인 칸)
EXPECT_ROUTE = {
    'FUK': (12, 323700, 473600, 398875, 12), 'KIX': (16, 359200, 556500, 411506, 14),
    'TYO': (16, 471800, 665300, 521106, 15), 'TPE': (17, 415000, 450800, 434765, 17),
    'HKG': (22, 283300, 496200, 388150, 22), 'MFM': (23, 555700, 874200, 683252, 0),
    'PVG': (23, 276600, 608000, 448317, 14), 'BKK': (23, 408000, 779400, 521983, 0),
    'DAD': (23, 462100, 708200, 536357, 0), 'CXR': (23, 458500, 771900, 541322, 16),
    'NKG': (24, 486500, 642900, 557446, 0), 'SGN': (24, 449900, 694700, 529946, 0),
}
# 9월 달력(출발일 → 그 날 실측 노선 수 · 최저)
EXPECT_DAY = {'2027-09-02': (12, 291400), '2027-09-03': (12, 328500),
              '2027-09-04': (11, 276600), '2027-09-09': (12, 354500),
              '2027-09-10': (12, 435500), '2027-09-11': (11, 337800),
              '2027-09-16': (12, 434300), '2027-09-17': (12, 411500),
              '2027-09-18': (11, 319000), '2027-09-23': (12, 359200),
              '2027-09-24': (12, 326400), '2027-09-25': (11, 326400),
              '2027-09-30': (8, 291600), '2027-10-01': (8, 291600),
              '2027-10-02': (8, 427600)}
# 대상 외 재확인 1칸 — 앱 기입력 → 재실측
EXPECT_RECHECK = {('BKK', '2027-10-01', '금~일'): (416600, 408000)}
# 병합 뒤 300칸 격자의 노선별 (최저, 최고) — 이번 실측분 + 앞선 조사분 54칸
EXPECT_GRID_ROUTE = {'FUK': (323700, 532500), 'KIX': (359200, 654100),
                     'TYO': (471800, 812500), 'TPE': (312400, 450800),
                     'HKG': (283300, 651800), 'MFM': (555700, 896000),
                     'PVG': (276600, 619000), 'BKK': (408000, 779400),
                     'DAD': (462100, 708200), 'CXR': (458500, 771900),
                     'NKG': (486500, 657500), 'SGN': (449900, 694700)}
EXPECT_GRID_OVERALL = (276600, 896000)


def rnd(x):
    """보고서와 같은 반올림(0.5 올림)."""
    return int(decimal.Decimal(str(x)).quantize(0, rounding=decimal.ROUND_HALF_UP))


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

    total, inner = '', ''
    m = re.fullmatch(r'총\s*(.+?)(?:\((.*)\))?', dur)
    if not m:
        raise SystemExit('경유 소요시간을 읽지 못했습니다: %r' % dur)
    total, inner = m.group(1).strip(), (m.group(2) or '').strip()
    info['total'] = total
    if inner:
        if not inner.startswith('환승'):
            raise SystemExit('환승 문장을 읽지 못했습니다: %r' % inner)
        rest = inner[2:].strip()
        if re.fullmatch(r'\d+회', rest):          # '환승 3회' — 시간 표기가 없는 칸
            info['transfers'] = rest
        else:
            info['lay'] = norm_dur(rest)

    if city == '미표기':                          # 경유지 자체가 표시되지 않은 칸
        if info['lay'] or info['transfers']:
            raise SystemExit('경유지 미표기 칸에 환승 표기가 있습니다: %r' % row)
        note = '경유(경유지 미표기) · 총 ' + norm_dur(total) + ' (' + times + ')'
        return note, True, info

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
            if row['status'] != '값':
                raise SystemExit('%s 상태가 값이 아닙니다: %r' % (row['dep'], row['status']))
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
            # 실측 시각 뒤의 원본 비고 — 지금은 호찌민 XMB 연계 2칸뿐이다
            pieces = [p.strip() for p in row['note'].split(' · ')]
            if not re.match(r'^2026-11-(?:19|20) \d\d:\d\d KST 실측$', pieces[0]):
                raise SystemExit('실측 시각 표기를 읽지 못했습니다: %r' % pieces[0])
            for extra in pieces[1:]:
                m = re.fullmatch(r'XMB 출발 철도\+항공 연계, 서울 (\d+)회 환승', extra)
                if not m:
                    raise SystemExit('%s 처리하지 못한 비고: %r' % (row['dep'], extra))
                if row['via_city'].strip() != '서울' or info['transfers'] != m.group(1) + '회':
                    raise SystemExit('%s XMB 비고와 경유 표기가 어긋납니다: %r' % (code, row))
                note += ' · XMB(부산역) 출발 철도+항공 연계'
            key = (code, row['dep'], pat)
            if key in cells:
                raise SystemExit('중복 칸 %s %s %s' % key)
            cells[key] = dict(code=code, date=row['dep'], back=row['ret'], pattern=pat,
                              price=price, airline=airline, via=via,
                              note=note, ord=ord_)
    return cells


def check(cells):
    if len(cells) != EXPECT_CELLS:
        raise SystemExit('%d칸 (기대 %d칸)' % (len(cells), EXPECT_CELLS))
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
    for pat, want in EXPECT_PAT_SUM.items():
        v = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if len(v) != EXPECT_PAT_CELLS[pat]:
            raise SystemExit('%s %d칸 (원문 %d칸)' % (pat, len(v), EXPECT_PAT_CELLS[pat]))
        if sum(v) != want:
            raise SystemExit('%s 합 %d (원문 %d)' % (pat, sum(v), want))
        if rnd(sum(v) / len(v)) != EXPECT_PAT_AVG[pat]:
            raise SystemExit('%s 평균 %d (원문 %d)'
                             % (pat, rnd(sum(v) / len(v)), EXPECT_PAT_AVG[pat]))
    direct = sum(1 for c in cells.values() if c['via'] is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (원문 %d)' % (direct, EXPECT_DIRECT))
    for code in ROUTES:
        v = [c for k, c in cells.items() if k[0] == code]
        prices = [c['price'] for c in v]
        got = (len(v), min(prices), max(prices), rnd(sum(prices) / len(prices)),
               sum(1 for c in v if c['via'] is False))
        if got != EXPECT_ROUTE[code]:
            raise SystemExit('%s 집계 %s (원문 %s)' % (code, got, EXPECT_ROUTE[code]))
    per_day = collections.defaultdict(lambda: [set(), []])
    for c in cells.values():
        per_day[c['date']][0].add(c['code'])
        per_day[c['date']][1].append(c['price'])
    for date, (n, low) in EXPECT_DAY.items():
        got = per_day.get(date)
        if not got or (len(got[0]), min(got[1])) != (n, low):
            raise SystemExit('%s 달력 집계 %s (원문 %s)'
                             % (date, got and (len(got[0]), min(got[1])), (n, low)))
    if set(per_day) != set(EXPECT_DAY):
        raise SystemExit('출발일 집합이 다릅니다: %s' % sorted(set(per_day) ^ set(EXPECT_DAY)))
    # 주차별 신규 칸수(재확인 1칸 제외)와 주차 평균(원본 246칸 기준)
    weeks = collections.defaultdict(lambda: [0, []])
    for key, c in cells.items():
        thu = (datetime.date.fromisoformat(c['date']) - datetime.timedelta(
            days=(datetime.date.fromisoformat(c['date']).weekday() - WD['목']) % 7)).isoformat()
        weeks[thu][1].append(c['price'])
        if key not in EXPECT_RECHECK:
            weeks[thu][0] += 1
    if set(weeks) != set(WEEK_THU):
        raise SystemExit('주차 집합이 다릅니다: %s' % sorted(weeks))
    for thu in WEEK_THU:
        if weeks[thu][0] != EXPECT_WEEK_NEW[thu]:
            raise SystemExit('%s 신규 %d칸 (기대 %d칸)' % (thu, weeks[thu][0], EXPECT_WEEK_NEW[thu]))
        got = rnd(sum(weeks[thu][1]) / len(weeks[thu][1]))
        if got != EXPECT_WEEK_AVG[thu]:
            raise SystemExit('%s 평균 %d (기대 %d)' % (thu, got, EXPECT_WEEK_AVG[thu]))
    # 10만원 단위 구간
    bucket = collections.Counter()
    for p in ps:
        if p < 400000:
            bucket['40만원 미만'] += 1
        elif p < 500000:
            bucket['40만~50만원'] += 1
        elif p < 600000:
            bucket['50만~60만원'] += 1
        elif p < 700000:
            bucket['60만~70만원'] += 1
        else:
            bucket['70만원 이상'] += 1
    if dict(bucket) != EXPECT_BUCKET:
        raise SystemExit('구간 분포 %s (원문 %s)' % (dict(bucket), EXPECT_BUCKET))
    # 월별 신규 칸수(재확인 1칸 제외)
    mcount = collections.Counter(c['date'][:7] for k, c in cells.items() if k not in EXPECT_RECHECK)
    if dict(mcount) != EXPECT_MONTH_CELLS:
        raise SystemExit('월별 신규 %s (기대 %s)' % (dict(mcount), EXPECT_MONTH_CELLS))
    # XMB 철도+항공 연계 2칸이 그대로 남아 있는지
    combo = [k for k, c in cells.items() if 'XMB(부산역)' in c['note']]
    if set(combo) != {('SGN', '2027-09-16', '목~일'), ('SGN', '2027-09-16', '목~월')}:
        raise SystemExit('XMB 연계 칸이 다릅니다: %s' % sorted(combo))
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


def main(argv):
    ap = argparse.ArgumentParser(description='A조 12노선 2027년 9월 5주 300칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--csv', default=CSV_DEFAULT)
    ap.add_argument('--note', default=None)
    args = ap.parse_args(argv)

    cells = check(parse(args.csv))
    print('파싱 %d칸 — 최저 %s · 최고 %s · 평균 %s · 직항이 최저인 칸 %d · 경유 %d'
          % (len(cells), format(min(c['price'] for c in cells.values()), ','),
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
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    deals_before = {c: json.loads(json.dumps(routes[c]['deals'])) for c in ROUTES}
    daytrip_before = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    other_before = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_sep = fl['counts']['byMonth'][MONTH]
    before_oct = fl['counts']['byMonth']['2027-10']
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])
    before_weeks = json.dumps(fl['weeks'], ensure_ascii=False)
    before_nosale_sep = [n for n in fl['noSale']
                         if n.get('date', '')[:7] in (MONTH, '2027-10')]

    # 이 격자에 이미 있던 값 — 1칸은 재확인 교체, 나머지는 이번 조사 밖이라 그대로 둔다
    # 0박 당일치기 2칸(후쿠오카·타이베이 10/2 토~토)은 5패턴 격자 밖이라 손대지 않는다
    existing, daytrip_cells = {}, []
    for code in ROUTES:
        for d in routes[code]['deals']:
            if not (GRID_START <= d['date'] <= GRID_END):
                continue
            if d['pattern'] not in PAT_NIGHTS:
                daytrip_cells.append((code, d['date'], d['pattern']))
                continue
            existing[(code, d['date'], d['pattern'])] = d
    if sorted(daytrip_cells) != [('FUK', '2027-10-02', '토~토'),
                                 ('TPE', '2027-10-02', '토~토')]:
        raise SystemExit('이 범위의 5패턴 밖 기존 칸이 다릅니다: %s' % sorted(daytrip_cells))
    if len(existing) != EXPECT_EXISTING:
        raise SystemExit('기존 칸 %d개 (기대 %d개): %s'
                         % (len(existing), EXPECT_EXISTING, sorted(existing)))
    replaced_keys = set(cells) & set(existing)
    if replaced_keys != set(EXPECT_RECHECK):
        raise SystemExit('교체할 칸이 다릅니다: %s (기대 %s)'
                         % (sorted(replaced_keys), sorted(EXPECT_RECHECK)))
    for key, (old_want, _new) in EXPECT_RECHECK.items():
        if existing[key]['price'] != old_want:
            raise SystemExit('재확인 칸 기존 금액이 다릅니다: %s %s (기대 %s)'
                             % (key, existing[key]['price'], format(old_want, ',')))
    new_keys = set(cells) - replaced_keys
    if len(new_keys) != EXPECT_NEW:
        raise SystemExit('새 칸 %d개 (기대 %d개)' % (len(new_keys), EXPECT_NEW))
    kept_keys = set(existing) - replaced_keys
    grid_keys = {(code, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(WD[pat[0]] - WD['목']) % 7)).isoformat(), pat)
                 for code in ROUTES for thu in WEEK_THU for pat in PAT_NIGHTS}
    if len(grid_keys) != EXPECT_GRID:
        raise SystemExit('격자 %d칸 (기대 %d칸)' % (len(grid_keys), EXPECT_GRID))
    if set(cells) | kept_keys != grid_keys:
        raise SystemExit('격자가 메워지지 않습니다: %s'
                         % sorted(grid_keys - (set(cells) | kept_keys))[:6])
    print('기존 %d칸 가운데 %d칸 재확인 교체 · 새 칸 %d칸 추가 · 그대로 두는 기존 칸 %d개'
          % (len(existing), len(replaced_keys), len(new_keys), len(kept_keys)))

    def make(v, pattern):
        deal = collections.OrderedDict()
        deal['date'] = v['date']
        deal['back'] = v['back']
        deal['pattern'] = pattern
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        deal['note'] = v['note']
        return json.loads(json.dumps(deal))

    replaced = []
    rep = {}
    for key in sorted(replaced_keys):
        code, date, pat = key
        old = existing[key]
        deals = routes[code]['deals']
        idx = next(i for i, d in enumerate(deals) if (d['date'], d['pattern']) == (date, pat))
        deals[idx] = make(cells[key], pat)
        replaced.append((code, date, pat, old['price'], cells[key]['price'], old.get('via'),
                         cells[key]['via']))
        rep[key] = (old['price'], cells[key]['price'])

    added = []
    for key in sorted(new_keys):
        code, date, pat = key
        routes[code]['deals'].append(make(cells[key], pat))
        added.append(key)
    for code in ROUTES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))
        for d in routes[code]['deals']:
            for word in BANNED:
                if word in json.dumps(d, ensure_ascii=False):
                    raise SystemExit('%s %s 값에 제3자 사이트 이름(%s)이 있습니다'
                                     % (code, d['date'], word))

    counts = recount(fl)
    if counts['total'] != before_total + len(added):
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], before_total + len(added)))
    if counts['byMonth'][MONTH] != before_sep + EXPECT_MONTH_CELLS[MONTH]:
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                 before_sep + EXPECT_MONTH_CELLS[MONTH]))
    if counts['byMonth']['2027-10'] != before_oct + EXPECT_MONTH_CELLS['2027-10']:
        raise SystemExit('2027-10 %d건 (기대 %d건)'
                         % (counts['byMonth']['2027-10'],
                            before_oct + EXPECT_MONTH_CELLS['2027-10']))

    grid = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if GRID_START <= d['date'] <= GRID_END
            and d['pattern'] in PAT_NIGHTS]
    if len(grid) != EXPECT_GRID:
        raise SystemExit('이 달 5패턴 칸 %d칸 (기대 %d칸)' % (len(grid), EXPECT_GRID))
    left = [d for d in grid if not d.get('price')]
    if left:
        raise SystemExit('금액 없는 칸 %d칸' % len(left))
    overall = (min(d['price'] for d in grid), max(d['price'] for d in grid))
    if overall != EXPECT_GRID_OVERALL:
        raise SystemExit('병합 뒤 격자 최저·최고 %s (기대 %s)' % (overall, EXPECT_GRID_OVERALL))
    unknown = [(d['code'], d['date'], d['pattern']) for d in grid if d.get('via') is None]
    if sorted(unknown) != [('CXR', '2027-10-01', '금~일'), ('SGN', '2027-10-01', '금~일')]:
        raise SystemExit('편성 미확인 칸이 다릅니다: %s' % sorted(unknown))

    # 이번 실측분(246칸)의 집계 — 재확인 1칸은 최신 값으로 격자에서 읽는다
    measured = [dict(d, code=r['code'], ord=cells[(r['code'], d['date'], d['pattern'])]['ord'])
                for r in fl['routes'] if r['code'] in ROUTES
                for d in r['deals'] if (r['code'], d['date'], d['pattern']) in cells]
    if len(measured) != EXPECT_CELLS:
        raise SystemExit('이번 실측분 %d칸 (기대 %d칸)' % (len(measured), EXPECT_CELLS))
    pats = collections.defaultdict(list)
    for d in measured:
        pats[d['pattern']].append(d['price'])
    pat_avg = sorted(((p, rnd(sum(v) / len(v))) for p, v in pats.items()), key=lambda kv: kv[1])
    direct = sum(1 for d in measured if d.get('via') is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (기대 %d)' % (direct, EXPECT_DIRECT))
    nodirect = [c for c in ROUTES
                if not any(d.get('via') is False for d in measured if d['code'] == c)]
    # 같은 금액이 여러 칸일 때는 원본 CSV 순서(보고서 '요약'의 최저 칸)를 따른다
    lo = min(measured, key=lambda d: (d['price'], d['ord']))
    hi = min(measured, key=lambda d: (-d['price'], d['ord']))
    avg = rnd(sum(d['price'] for d in measured) / len(measured))
    if avg != EXPECT_AVG:
        raise SystemExit('실측 평균 %d (원문 %d)' % (avg, EXPECT_AVG))
    weeks = collections.defaultdict(list)
    for d in measured:
        dt = datetime.date.fromisoformat(d['date'])
        weeks[(dt - datetime.timedelta(days=(dt.weekday() - WD['목']) % 7)).isoformat()] \
            .append(d['price'])
    week_avg = [(WEEK_LABEL[k], rnd(sum(v) / len(v))) for k, v in sorted(weeks.items())]

    def lay(d):
        m = re.search(r'환승\s*(\d+)시간\s*(?:(\d+)분)?', d.get('note') or '')
        return (int(m.group(1)) * 60 + int(m.group(2) or 0)) if m else None

    long12 = [d for d in measured if lay(d) is not None and 720 <= lay(d) < 1200]
    long20 = [d for d in measured if lay(d) is not None and lay(d) >= 1200]
    combo = [d for d in measured if 'XMB(부산역)' in (d.get('note') or '')]

    def cell_text(d):
        """'후쿠오카 9/2~6 목~월 323,700원(이스타항공 직항 1시간 10분, 14:50-16:00)'"""
        span = ('%d/%d~%d' % (int(d['date'][5:7]), int(d['date'][8:10]), int(d['back'][8:10]))
                if d['date'][:7] == d['back'][:7] else
                '%d/%d~%d/%d' % (int(d['date'][5:7]), int(d['date'][8:10]),
                                 int(d['back'][5:7]), int(d['back'][8:10])))
        air = d.get('airline') or '항공사 미확인'
        note = d.get('note') or ''
        m = re.match(r'^직항 (\S+(?: \d+분)?) \(([^)]*)\)', note)
        if m:
            detail = '직항 %s, %s' % (m.group(1), m.group(2))
        else:
            lay_m = re.search(r'환승 ([^·]+?) · 총 ([^ ]+(?: \d+분)?)', note)
            hops = re.search(r'경유 \d회\(([^)]*)\)', note)
            if lay_m and hops:
                detail = '경유(%s), 환승 %s · 총 %s' % (hops.group(1), lay_m.group(1),
                                                    lay_m.group(2))
            else:
                # 환승 시간 대신 '환승 N회'만 있는 칸 · 경유지 미표기 칸
                m2 = re.search(r'총 ([^ ]+(?: \d+분)?)', note)
                detail = '경유 %s%s' % (hops.group(1) if hops else '(경유지 미표기)',
                                        (' · 총 ' + m2.group(1)) if m2 else '')
        return '%s %s %s %s원(%s %s)' % (CITY[d['code']], span, d['pattern'],
                                         format(d['price'], ','), air, detail)

    if len(measured) != EXPECT_CELLS:
        raise SystemExit('집계 대상이 %d칸입니다' % len(measured))

    month_sent = (
        '2027년 9월은 부산 출발 A조 12개 노선(후쿠오카·오사카·도쿄·타이베이·홍콩·마카오·상하이·'
        '방콕·다낭·나트랑·난징·호찌민)의 5주(9/2~6 · 9/9~13 · 9/16~20 · 9/23~27 · 9/30~10/4) '
        '5패턴 300칸 가운데 웹앱에 비어 있던 245칸을 전부 실측해 넣었습니다 — 이 12개 노선의 '
        '이 다섯 주 5패턴은 이제 300/300칸 모두 금액이 있습니다. 앱에 이미 있던 1칸'
        '(방콕 10/1 금~일 ' + format(rep[('BKK', '2027-10-01', '금~일')][0], ',')
        + '원 → ' + format(rep[('BKK', '2027-10-01', '금~일')][1], ',')
        + '원)은 같은 조건으로 다시 조회한 값으로 바꿨고, 나머지 54칸은 앞선 조사에서 이미 값이 '
        '있던 칸이라 이번에 다시 조회하지 않았습니다(추정·보간 없음 · 그중 나트랑·호찌민 '
        '10/1 금~일 2칸은 금액만 있고 편성이 확인되지 않아 그대로 두었습니다). '
        '이번 원본 246칸 최저는 ' + cell_text(lo) + '이고, 최고는 ' + cell_text(hi)
        + '으로 최저의 ' + ('%.2f' % (hi['price'] / lo['price'])) + '배입니다. 246칸 평균은 '
        + format(avg, ',') + '원이고 주차 평균은 '
        + ' · '.join('%s %s원' % (w, format(v, ',')) for w, v in week_avg)
        + '입니다(9/9~13주가 가장 비싸고 9/23~27주가 가장 쌉니다). 패턴 평균은 '
        + ' < '.join('%s %s원' % (p, format(v, ',')) for p, v in pat_avg)
        + ' 순으로, 4박 목~월이 2박 금~일보다 '
        + format(pat_avg[-1][1] - pat_avg[0][1], ',') + '원 쌉니다. 최저가가 직항인 칸은 '
        + str(direct) + '칸, 경유 ' + str(len(measured) - direct) + '칸이고 '
        + '·'.join(CITY[c] for c in nodirect) + ' ' + str(len(nodirect))
        + '개 노선은 이 달 실측분이 모두 경유입니다(마카오는 부산 직항편 자체가 없습니다). '
        + '10만원 단위로는 40만원 미만 34칸 · 40만~50만원 102칸 · 50만~60만원 73칸 · '
        '60만~70만원 19칸 · 70만원 이상 18칸입니다. '
        + '경유 대기가 긴 칸은 마카오 9/11~13 토~월 타이베이 20시간 5분 환승(총 24시간 25분) · '
        '난징 9/3~5 금~일 홍콩 23시간 50분 환승(총 30시간 15분)이고, 환승 12시간 이상 '
        '20시간 미만이 ' + str(len(long12)) + '칸 · 20시간 이상이 ' + str(len(long20))
        + '칸이라 앱의 경유 12h+ · 20h+ 경고가 붙습니다. '
        + '호찌민은 9/16주 목요일 출발 2칸(목~일 · 목~월)의 최저가가 항공 단독이 아니라 '
        '부산역(XMB)에서 서울까지 철도로 간 뒤 항공으로 이어지는 연계 상품이라 note 에 그 사실을 '
        '적어 두었습니다 — 그대로 예약하기 어려울 수 있으니 같은 표의 다른 칸과 비교해 판단하시면 됩니다. '
        + '다낭 9/16~19 목~일 1칸과 나트랑 9/10~12 금~일 · 금~월 2칸은 최저가 편성의 경유지가 '
        '화면에 표시되지 않아 경유지 미표기로 적었습니다. 0박 당일치기 2칸(후쿠오카·타이베이 10/2 토~토)은 '
        '이번 조사 범위 밖이라 그대로 두었습니다.')
    if '**' in month_sent:
        raise SystemExit('notes 문장에 마크다운 별표가 있습니다')
    for word in BANNED:
        if word in month_sent:
            raise SystemExit('notes 문장에 제3자 사이트 이름(%s)이 있습니다' % word)
    fl['notes'][MONTH] = fl['notes'][MONTH].rstrip() + ' ' + month_sent

    for key, old in frozen.items():
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != old:
            raise SystemExit('%s 가 바뀌었습니다' % key)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다')
    if json.dumps(fl['weeks'], ensure_ascii=False) != before_weeks:
        raise SystemExit('주차 정의가 바뀌었습니다')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('noSale 이 바뀌었습니다')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != other_before:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다')
    for code in ROUTES:
        old = deals_before[code]
        cur = routes[code]['deals']
        want = len(old) + sum(1 for k in new_keys if k[0] == code)
        if len(cur) != want:
            raise SystemExit('%s 딜 %d건 (기존 %d + 이번 %d)' % (code, len(cur), len(old),
                                                              want - len(old)))
        have = {(d['date'], d['pattern']): d for d in cur}
        if len(have) != len(cur):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for o in old:
            got = have.get((o['date'], o['pattern']))
            if got is None:
                raise SystemExit('%s 기존 딜이 사라졌습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
            if (code, o['date'], o['pattern']) in replaced_keys:
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
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')
    for word in BANNED:
        if word in json.dumps(fl['notes'], ensure_ascii=False):
            raise SystemExit('notes 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    if [n for n in fl['noSale'] if n.get('date', '')[:7] in (MONTH, '2027-10')] != before_nosale_sep:
        raise SystemExit('2027-09·10 noSale 기록이 바뀌었습니다')

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    note = args.note or (
        '2026-11-20 KST ⑤ 항공 부산 출발 A조 12개 노선 2027년 9월 5주(9/2~6 · 9/9~13 · '
        '9/16~20 · 9/23~27 · 9/30~10/4) 5패턴 300칸 완결 — 빈칸 245칸 실측 + 재확인 1칸'
        '(방콕 10/1 416,600→408,000원), 최저 상하이 9/4~6 토~월 276,600원(춘추항공 직항), '
        '직항이 최저가인 칸 %d, 총 %s→%s건'
        % (direct, format(before_total, ','), format(counts['total'], ',')))
    master['extended'] = (before_extended + ' / ' + note).strip(' /')

    print('교체 %d칸' % len(replaced))
    for code, date, pat, oldp, newp, oldv, newv in replaced:
        print('  %s %s %s %s → %s원 (via %s → %s)'
              % (code, date, pat, format(oldp, ','), format(newp, ','), oldv, newv))
    print('신규 %d칸 · 격자 %d칸 모두 금액 · 최저 %s · 최고 %s'
          % (len(added), len(grid), format(overall[0], ','), format(overall[1], ',')))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'],
             counts['daytrip']))
    print('2027-09 %d → %d건 · 2027-10 %d → %d건'
          % (before_sep, counts['byMonth'][MONTH], before_oct, counts['byMonth']['2027-10']))
    print('12시간 이상 환승 %d칸 · 20시간 이상 %d칸 · XMB 연계 %d칸 · 그대로 두는 당일치기 %d칸'
          % (len(long12), len(long20), len(combo), len(daytrip_cells)))
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
