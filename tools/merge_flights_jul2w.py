#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선의 2027년 7월 2주차(7/8~7/12) 5패턴 120칸** 실측을
`data/master_db.json` 의 `flights` 에 병합한다.

원본 1개(`data-sources/flights-2027-07/부산출발-항공특가-2027년7월-2주차.md`,
2026-11-19 15:00~15:47 KST 실측) — 24개 노선 5패턴 120칸 전수(미확인·추정 0칸).
  · 노선 절: `### 부산–상하이(PVG)` / `### 부산–도쿄(TYO/NRT·HND)` / `### 부산–베이징(BJS/PEK·PKX)`
    → 절 머리 괄호의 첫 3글자를 노선 코드로 읽는다.
  · 칸 1줄:
    `- 7/9(금) → 7/11(일) · ①금~일·2박 · **417,900원** · 중국남방항공 · 경유(선양 2시간30분, 총7시간20분, 11:20-17:40) · 38개 검색됨 · 직항편 우선 527,400원`
    (직항 칸: `직항 1시간(09:05-10:05)` · 경유 칸: 괄호 안에 경유지·총 소요·출도착 시각이 모두 들어간다)
    이번 원본의 비고: `N개 검색됨` · `직항편 우선 …원` · `직항 운임 미표시` · `9석 미만` · `도착 NRT/TPE`.

규칙:
  · 120칸 모두 `routes[].deals` 로 넣는다(`price` = 원문 금액 그대로, 반올림 없음).
  · `via` 는 그 칸 **최저가 편성**이 직항(`false`)·경유(`true`)인지로 적는다.
  · `note` 는 `직항 1시간 00분 (09:05-10:05)` / `경유(선양 2시간 30분) · 총 7시간 20분 (11:20-17:40)`
    꼴로 적고, `직항편 없음`·`잔여 9석 미만`·`직항 금액 …원` 을 덧붙인다(공항 코드는 시각 뒤 괄호 안).
  · `alt` 는 원문의 '직항편 우선' 금액이 최저가보다 비쌀 때만 넣는다.
  · 이 주차에 **이미 있던 '가격표' 자리표시 칸** 18칸(5패턴)은 같은 노선·출발일·패턴이므로
    이번 실측값으로 **교체**한다(같은 칸을 두 값으로 두지 않는다). 0박 당일치기 칸
    (상하이 7/8 목~목 481,100원) 은 이 조사 범위 밖이므로 그대로 둔다.
  · 호텔 538곳 · 아코르 · ⑥ 땡처리 · 출처 목록 · 패턴 정의 · 다른 노선/기존 딜·`noSale` 은
    값 대조로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-07 `notes` 끝에
    이번 120칸 문장을 덧붙인다(plain text — `**` 금지).
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jul2w.py --dry-run
    python3 tools/merge_flights_jul2w.py
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-2027-07'))
FILE = '부산출발-항공특가-2027년7월-2주차.md'

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
          'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'NGO': '나고야',
        'OKA': '오키나와', 'GUM': '괌', 'PVG': '상하이', 'BJS': '베이징', 'NKG': '난징',
        'HGH': '항저우', 'TAO': '칭다오', 'TPE': '타이베이', 'HKG': '홍콩', 'KHH': '가오슝',
        'RMQ': '타이중', 'MFM': '마카오', 'BKK': '방콕', 'CNX': '치앙마이', 'DAD': '다낭',
        'CXR': '나트랑', 'HAN': '하노이', 'SGN': '호찌민', 'SIN': '싱가포르', 'DPS': '발리'}
MONTH = '2027-07'
WEEK_START, WEEK_END = '2027-07-08', '2027-07-12'
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver')
_DUR_RE = re.compile(r'(\d+)\s*시간(?:\s*(\d+)\s*분)?|(\d+)\s*분')

EXPECT_CELLS = 120
EXPECT_OVERALL = (272300, 840000)          # 후쿠오카 7/8~12 목~월 · 괌 7/9~11 금~일
EXPECT_SUM = 60700800
EXPECT_AVG = {'토~월': 495429, '금~월': 503775, '목~월': 508446,
              '금~일': 509725, '목~일': 511825}
EXPECT_DIRECT = 39          # 직항이 최저가인 칸
EXPECT_ALT = 25             # '직항편 우선' 금액을 함께 적은 칸
EXPECT_THIN = 3             # '9석 미만' 표시가 붙은 칸(괌 ③④⑤)
EXPECT_NODIRECT = 55        # '직항 운임 미표시' 칸(경유 최저 81칸 중 55칸)
EXPECT_PLACEHOLDER = 18     # 이 주차에 남아 있던 '가격표' 자리표시 칸(5패턴, 교체 대상)
EXPECT_SKIPPED = 1          # 같은 주차의 0박 자리표시(상하이 7/8 목~목) — 범위 밖이라 그대로

ROUTE_MINMAX = {
    'PVG': (318500, 505800), 'FUK': (272300, 318900), 'KIX': (382900, 402600),
    'TYO': (480200, 541000), 'BKK': (429000, 431300), 'DAD': (499500, 501100),
    'CXR': (484400, 513300), 'TPE': (436400, 440000), 'HKG': (296500, 335500),
    'MFM': (613500, 735100), 'NKG': (503100, 553400), 'SGN': (470700, 471000),
    'SIN': (444000, 450000), 'GUM': (635600, 840000), 'NGO': (621200, 680900),
    'OKA': (494400, 643800), 'HGH': (503100, 620600), 'TAO': (494800, 504300),
    'HAN': (462000, 463900), 'CNX': (549600, 759100), 'DPS': (450600, 450600),
    'KHH': (552500, 593800), 'RMQ': (435400, 587600), 'BJS': (452500, 519900),
}
# 이 주차 5패턴 전부 최저가가 직항인 노선 — 후쿠오카·오사카·도쿄·나트랑·타이베이·홍콩
EXPECT_ALLDIRECT = ('FUK', 'KIX', 'TYO', 'CXR', 'TPE', 'HKG')
# 5패턴 전부 직항 운임이 표시되지 않은 노선(원문 '한눈에'와 칸별 값이 같다 — 9개)
EXPECT_NODIRECT_ROUTES = ('BKK', 'DAD', 'MFM', 'NKG', 'GUM', 'NGO', 'HGH', 'TAO', 'DPS')
# 원문 최저가 순위(1~5위)와 최고가 순위 — 값이 통째로 밀리면 여기서 걸린다
EXPECT_LOWEST = {('FUK', '2027-07-08', '목~월'): 272300,
                 ('HKG', '2027-07-10', '토~월'): 296500,
                 ('PVG', '2027-07-10', '토~월'): 318500,
                 ('KIX', '2027-07-10', '토~월'): 382900,
                 ('BKK', '2027-07-09', '금~일'): 429000}
EXPECT_HIGHEST = {('GUM', '2027-07-09', '금~일'): 840000,
                  ('GUM', '2027-07-10', '토~월'): 804500,
                  ('CNX', '2027-07-09', '금~일'): 759100}


def read():
    path = os.path.join(SRC, FILE)
    if not os.path.isfile(path):
        raise SystemExit('원본이 없습니다: %s' % path)
    return open(path, encoding='utf-8').read()


def won(text):
    m = re.search(r'([\d,]+)', text)
    return int(m.group(1).replace(',', '')) if m else None


def norm_dur(text):
    """'1시간10분' → '1시간 10분', '30시간' → '30시간 00분', '55분' 그대로."""
    def rep(m):
        if m.group(1):
            return '%s시간 %s분' % (m.group(1), (m.group(2) or '00').rjust(2, '0'))
        return '%s분' % m.group(3)
    return _DUR_RE.sub(rep, text).strip()


def build_note(leg):
    """`직항 1시간 00분 (09:05-10:05)` / `경유(선양 2시간 30분) · 총 7시간 20분 (11:20-17:40)`."""
    kind = '직항' if leg.startswith('직항') else ('경유' if leg.startswith('경유') else None)
    if kind is None:
        raise SystemExit('편성 문장을 읽지 못했습니다: %r' % leg)
    rest = leg[len(kind):].strip()
    if kind == '직항':
        m = re.fullmatch(r'(.+?)\(([^)]*)\)', rest)
        if not m:
            raise SystemExit('직항 소요시간·시각을 읽지 못했습니다: %r' % leg)
        dur, times = m.group(1).strip(), m.group(2).strip()
        if not re.search(r'\d\d:\d\d', times):
            raise SystemExit('직항 시각을 읽지 못했습니다: %r' % leg)
        return '직항 ' + norm_dur(dur) + ' (' + times + ')', False
    m = re.fullmatch(r'\(([^)]*)\)', rest)
    if not m:
        raise SystemExit('경유 괄호를 읽지 못했습니다: %r' % leg)
    pieces = [p.strip() for p in m.group(1).split(',') if p.strip()]
    hops, total, times = [], None, None
    for p in pieces:
        tm = re.match(r'^총\s*(.+)$', p)
        if tm:
            total = norm_dur(tm.group(1))
            continue
        if re.fullmatch(r'\d\d:\d\d\s*-\s*\d\d:\d\d(?:\+\d)?', p):
            times = re.sub(r'\s*-\s*', '-', p)
            continue
        hops.append(norm_dur(p))
    if not hops:
        raise SystemExit('경유지가 없습니다: %r' % leg)
    if not total or not times:
        raise SystemExit('경유 총 소요·시각을 읽지 못했습니다: %r' % leg)
    return '경유(' + ', '.join(hops) + ') · 총 ' + total + ' (' + times + ')', True


def parse():
    cells, code = {}, None
    for raw in read().splitlines():
        line = raw.strip()
        m = re.match(r'^###\s*부산[–-].*?\(([A-Z]{3})', line)
        if m:
            code = m.group(1)
            if code not in ROUTES:
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        if not line.startswith('- 7/'):
            continue
        if code is None:
            raise SystemExit('노선 없이 칸: %s' % line[:60])
        line = re.sub(r'\s*\[출처:[^\]]*\]', '', line).strip()
        parts = [p.strip() for p in line[2:].split(' · ')]
        if len(parts) < 5:
            raise SystemExit('%s 칸 형식을 읽지 못했습니다: %r' % (code, line[:80]))
        dm = re.match(r'^7/(\d+)\(.\)\s*→\s*7/(\d+)\(.\)$', parts[0])
        if not dm:
            raise SystemExit('%s 날짜를 읽지 못했습니다: %r' % (code, parts[0]))
        pm = re.match(r'^[①②③④⑤]([월화수목금토일]~[월화수목금토일])·(\d)박$', parts[1])
        if not pm:
            raise SystemExit('%s 패턴을 읽지 못했습니다: %r' % (code, parts[1]))
        pat = pm.group(1)
        if PAT_NIGHTS[pat] != int(pm.group(2)):
            raise SystemExit('%s 박수 불일치: %s' % (code, parts[1]))
        date = datetime.date(2027, 7, int(dm.group(1)))
        back = datetime.date(2027, 7, int(dm.group(2)))
        if (back - date).days != PAT_NIGHTS[pat]:
            raise SystemExit('%s 출발·귀국 간격이 박수와 다릅니다: %s' % (code, parts[0]))
        if (WD[pat[0]] - (date.weekday() + 1) % 7) % 7 != 0:
            raise SystemExit('%s 요일 불일치: %s %s' % (code, date.isoformat(), pat))
        price = won(parts[2])
        if not price:
            raise SystemExit('%s 금액을 읽지 못했습니다: %r' % (code, parts[2]))
        airline = parts[3].strip()
        note, via = build_note(parts[4].strip())
        alt, thin, no_direct, dest, count = None, False, False, None, False
        for more in parts[5:]:
            if more.startswith('직항편 우선'):
                got = re.search(r'([\d,]{6,})', more)
                if not got:
                    raise SystemExit('%s 직항 금액을 읽지 못했습니다: %r' % (code, more))
                alt = int(got.group(1).replace(',', ''))
                if alt <= price:
                    raise SystemExit('%s 직항 금액이 최저가보다 싸거나 같습니다: %s' % (code, more))
            elif more == '직항 운임 미표시':
                no_direct = True
            elif more == '9석 미만':
                thin = True
            elif more.startswith('도착 '):
                dest = more[3:].strip()
                if not re.fullmatch(r'[A-Z]{3}', dest):
                    raise SystemExit('%s 도착 공항 코드가 이상합니다: %r' % (code, more))
            elif re.fullmatch(r'\d+개 검색됨', more):
                count = True
            else:
                raise SystemExit('%s 처리하지 못한 비고: %r' % (code, more))
        if count is False:
            raise SystemExit('%s 검색 편수가 없습니다: %r' % (code, line[:80]))
        if no_direct and alt:
            raise SystemExit('%s 직항 없음인데 직항 금액이 있습니다' % code)
        if dest:
            if via:
                raise SystemExit('%s 경유 칸에 도착 공항이 붙었습니다' % code)
            note = note[:-1] + ' ' + dest + ')'
        if alt:
            note += ' · 직항 금액 ' + format(alt, ',') + '원'
        if no_direct:
            note += ' · 직항편 없음'
        if thin:
            note += ' · 잔여 9석 미만'
        if (code, date.isoformat(), pat) in cells:
            raise SystemExit('중복 칸 %s %s %s' % (code, date.isoformat(), pat))
        cells[(code, date.isoformat(), pat)] = dict(
            code=code, date=date.isoformat(), back=back.isoformat(), pattern=pat,
            price=price, airline=airline or None, via=via, alt=alt, thin=thin,
            no_direct=no_direct, note=note)
    return cells


def matrix_expect():
    """원문의 '가격 매트릭스' 표 → 노선별 (최저, 최고) · 노선 최저 · 패턴 평균."""
    text = read()
    sect = text.split('## 가격 매트릭스')[1].split('## 날짜·패턴별')[0]
    out, low, avg = {}, {}, {}
    for line in sect.splitlines():
        row = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(row) != 7:
            continue
        m = re.match(r'^[^|]*?\(([A-Z]{3})[^)]*\)$', row[0])
        if m:
            vals = []
            for c in row[1:6]:
                c = c.replace('**', '').replace('원', '').replace(',', '').strip()
                if not c.isdigit():
                    raise SystemExit('%s 표 값 이상: %r' % (m.group(1), c))
                vals.append(int(c))
            low_c = row[6].replace('**', '').replace('원', '').replace(',', '').strip()
            if not low_c.isdigit():
                raise SystemExit('%s 노선 최저 값 이상: %r' % (m.group(1), low_c))
            out[m.group(1)] = (min(vals), max(vals))
            low[m.group(1)] = int(low_c)
            continue
        if '패턴 평균' in row[0]:
            for pat, c in zip(('금~일', '토~월', '목~일', '금~월', '목~월'), row[1:6]):
                c = c.replace('**', '').replace('원', '').replace(',', '').strip()
                if not c.isdigit():
                    raise SystemExit('패턴 평균 값 이상: %r' % c)
                avg[pat] = int(c)
    return out, low, avg


def check(cells):
    if len(cells) != EXPECT_CELLS:
        raise SystemExit('%d칸 (기대 %d칸)' % (len(cells), EXPECT_CELLS))
    codes = {k[0] for k in cells}
    if codes != set(ROUTES):
        raise SystemExit('노선이 24개가 아닙니다: %s' % sorted(codes))
    want = set()
    for code in ROUTES:
        for pat, nights in PAT_NIGHTS.items():
            d = (datetime.date.fromisoformat(WEEK_START) +
                 datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7))
            want.add((code, d.isoformat(), pat))
    if set(cells) != want:
        raise SystemExit('칸 집합이 24노선 × 5패턴과 다릅니다: %s'
                         % sorted(set(cells) ^ want)[:6])
    ps = [c['price'] for c in cells.values()]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('최저·최고 %s (원문 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    if sum(ps) != EXPECT_SUM:
        raise SystemExit('합계 %d (원문 %d)' % (sum(ps), EXPECT_SUM))
    for pat, want_avg in EXPECT_AVG.items():
        v = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if len(v) != 24:
            raise SystemExit('%s %d칸 (기대 24칸)' % (pat, len(v)))
        if round(sum(v) / len(v)) != want_avg:
            raise SystemExit('%s 평균 %.1f (원문 %d)' % (pat, sum(v) / len(v), want_avg))
    direct = sum(1 for c in cells.values() if c['via'] is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (원문 %d)' % (direct, EXPECT_DIRECT))
    if any(c['via'] is None for c in cells.values()):
        raise SystemExit('via 미확인 칸이 있습니다')
    thin = sum(1 for c in cells.values() if c['thin'])
    if thin != EXPECT_THIN:
        raise SystemExit('9석 미만 표시 칸 %d (원문 %d)' % (thin, EXPECT_THIN))
    alt = sum(1 for c in cells.values() if c['alt'])
    if alt != EXPECT_ALT:
        raise SystemExit('직항 금액 병기 %d칸 (원문 %d칸)' % (alt, EXPECT_ALT))
    nod = sum(1 for c in cells.values() if c['no_direct'])
    if nod != EXPECT_NODIRECT:
        raise SystemExit('직항 운임 미표시 %d칸 (원문 %d칸)' % (nod, EXPECT_NODIRECT))
    by_route = collections.defaultdict(list)
    for k, c in cells.items():
        by_route[k[0]].append(c)
    for code in EXPECT_ALLDIRECT:
        if any(c['via'] is not False for c in by_route[code]):
            raise SystemExit('%s 5패턴이 모두 직항이어야 합니다' % code)
    for code in EXPECT_NODIRECT_ROUTES:
        if any(not c['no_direct'] or c['alt'] for c in by_route[code]):
            raise SystemExit('%s 5패턴 전부 직항 운임 없음이어야 합니다' % code)
    for code, (lo, hi) in ROUTE_MINMAX.items():
        v = [c['price'] for c in by_route[code]]
        if len(v) != 5:
            raise SystemExit('%s %d칸 (기대 5칸)' % (code, len(v)))
        if (min(v), max(v)) != (lo, hi):
            raise SystemExit('%s 최저·최고 %s (스크립트 상수 %s)' % (code, (min(v), max(v)), (lo, hi)))
    for key, price in EXPECT_LOWEST.items():
        if cells[key]['price'] != price:
            raise SystemExit('최저 순위 칸 %s %s (기대 %d)' % (key, cells[key]['price'], price))
    for key, price in EXPECT_HIGHEST.items():
        if cells[key]['price'] != price:
            raise SystemExit('최고 칸 %s %s (기대 %d)' % (key, cells[key]['price'], price))
    exp, exp_low, exp_avg = matrix_expect()
    if set(exp) != set(ROUTES):
        raise SystemExit('매트릭스 표 노선이 24개가 아닙니다: %s' % sorted(exp))
    if exp_avg != EXPECT_AVG:
        raise SystemExit('매트릭스 표 패턴 평균 %s (스크립트 상수 %s)' % (exp_avg, EXPECT_AVG))
    for code in ROUTES:
        if exp[code] != ROUTE_MINMAX[code]:
            raise SystemExit('%s 매트릭스 표 %s (스크립트 상수 %s)'
                             % (code, exp[code], ROUTE_MINMAX[code]))
        if exp_low[code] != exp[code][0]:
            raise SystemExit('%s 표의 노선 최저 %d 가 5패턴 최저 %d 와 다릅니다'
                             % (code, exp_low[code], exp[code][0]))
    for k, c in cells.items():
        if c['alt'] is not None and c['alt'] <= c['price']:
            raise SystemExit('%s 직항 금액이 최저가 이하입니다' % (k,))
        if c['price'] <= 0:
            raise SystemExit('%s 가격이 양의 정수가 아닙니다' % (k,))
        if not c['note']:
            raise SystemExit('%s note 비어 있음' % (k,))
        if '**' in c['note'] or '[' in c['note'] or '출처' in c['note']:
            raise SystemExit('%s note 에 마크업이 있습니다: %r' % (k, c['note']))
        if '총' in c['note'] and c['via'] is False:
            raise SystemExit('%s 직항인데 총 소요시간이 붙었습니다: %r' % (k, c['note']))
        if c['via'] is True and '총' not in c['note']:
            raise SystemExit('%s 경유인데 총 소요시간이 없습니다: %r' % (k, c['note']))
        if '직항편 없음' in c['note'] and c['alt']:
            raise SystemExit('%s 직항편 없음인데 직항 금액이 있습니다' % (k,))
        if c['note'].count('직항 금액') != (1 if c['alt'] else 0):
            raise SystemExit('%s 직항 금액 표기가 alt 와 다릅니다: %r' % (k, c['note']))
        if c['note'].count('잔여 9석 미만') != (1 if c['thin'] else 0):
            raise SystemExit('%s 잔여석 표기가 thin 과 다릅니다: %r' % (k, c['note']))
        for word in BANNED:
            if word in c['note'] or word in (c['airline'] or ''):
                raise SystemExit('%s 값에 제3자 사이트 이름(%s)이 있습니다' % (k, word))
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


def _viaword(d):
    return '직항' if d.get('via') is False else ('경유' if d.get('via') else '편성 미확인')


def span(d):
    return '%d/%d~%d/%d' % (int(d['date'][5:7]), int(d['date'][8:10]),
                            int(d['back'][5:7]), int(d['back'][8:10]))


def week_note(rows, label):
    lo = min(rows, key=lambda d: d['price'])
    hi = max(rows, key=lambda d: d['price'])
    agg = collections.defaultdict(list)
    for d in rows:
        agg[d['pattern']].append(d['price'])
    avg = ' < '.join('{} {}원'.format(p, format(round(sum(v) / len(v)), ','))
                     for p, v in sorted(agg.items(), key=lambda kv: sum(kv[1]) / len(kv[1])))
    direct = sum(1 for d in rows if d.get('via') is False)
    ties_lo = sum(1 for d in rows if d['price'] == lo['price'])
    ties_hi = sum(1 for d in rows if d['price'] == hi['price'])
    return (label + ' 최저는 ' + CITY[lo['code']] + ' ' + span(lo) + ' ' + lo['pattern'] + ' '
            + format(lo['price'], ',') + '원(' + (lo['airline'] or '항공사 미확인') + ' '
            + _viaword(lo) + (' · 같은 금액 %d칸' % ties_lo if ties_lo > 1 else '')
            + ')이고, 최고는 ' + CITY[hi['code']] + ' ' + span(hi) + ' ' + hi['pattern'] + ' '
            + format(hi['price'], ',') + '원(' + (hi['airline'] or '항공사 미확인') + ' '
            + _viaword(hi) + (' · 같은 금액 %d칸' % ties_hi if ties_hi > 1 else '')
            + ')입니다. 직항이 최저가인 칸 ' + str(direct) + ' · 경유 '
            + str(len(rows) - direct) + '칸이고, 패턴 평균은 ' + avg + ' 순입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 7월 2주(7/8~12) 120칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ⑤ 항공 기존 24개 노선 2027년 7월 2주차(7/8~12) '
        '5패턴 120칸 완결 — 최저 후쿠오카 7/8~12 272,300원(트리니티항공 직항), '
        '직항이 최저가인 칸 39, 가격표 자리표시 18칸 교체, 총 9,229→9,331건'))
    args = ap.parse_args(argv)

    cells = check(parse())
    print('파싱 %d칸 — 최저 %s · 최고 %s · 직항이 최저인 칸 %d · 경유 %d · 잔여 9석 미만 %d · 직항 금액 병기 %d · 직항 운임 미표시 %d'
          % (len(cells), format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ','),
             sum(1 for c in cells.values() if c['via'] is False),
             sum(1 for c in cells.values() if c['via'] is True),
             sum(1 for c in cells.values() if c['thin']),
             sum(1 for c in cells.values() if c['alt']),
             sum(1 for c in cells.values() if c['no_direct'])))
    for k in sorted(cells)[:2]:
        print('  예:', k, cells[k])

    master = json.load(open(MASTER, encoding='utf-8'))
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다' % code)

    before = {k: json.dumps(master.get(k), ensure_ascii=False, sort_keys=True)
              for k in ('hotels', 'accor', 'sources', 'window', 'built', 'voucherExpiry',
                        'schema', 'version', 'ttang')}
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    weeks_before = json.dumps(fl['weeks'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    booking_before = json.dumps(fl['bookingWindow'], ensure_ascii=False, sort_keys=True)
    notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    before_deals = {c: json.dumps(routes[c]['deals'], ensure_ascii=False) for c in ROUTES}
    before_daytrip = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_jul = fl['counts']['byMonth'][MONTH]
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])

    # 이 주차에 남아 있던 자리표시 칸 — 같은 (노선·출발일·패턴)이므로 이번 실측으로 교체한다.
    placeholders = {}
    skipped = []
    for code in ROUTES:
        for d in routes[code]['deals']:
            if WEEK_START <= d['date'] <= WEEK_END:
                if d['pattern'] not in PAT_NIGHTS:
                    skipped.append((code, d['date'], d['pattern']))
                    continue
                if d.get('src') != '가격표' or d.get('note') != '가격표 실측 · 직항/경유 미확인':
                    raise SystemExit('이 주차에 예상 밖의 기존 칸: %s %s'
                                     % (code, json.dumps(d, ensure_ascii=False)))
                placeholders[(code, d['date'], d['pattern'])] = d
    if len(placeholders) != EXPECT_PLACEHOLDER:
        raise SystemExit('자리표시 칸 %d개 (기대 %d개): %s'
                         % (len(placeholders), EXPECT_PLACEHOLDER, sorted(placeholders)))
    if len(skipped) != EXPECT_SKIPPED:
        raise SystemExit('범위 밖 0박 칸 %d개 (기대 %d개): %s'
                         % (len(skipped), EXPECT_SKIPPED, skipped))
    extra_keys = set(cells) - set(placeholders)
    print('자리표시 %d칸 교체 · 새 칸 %d칸 추가 (이 조사 범위 밖 0박 칸 %d개는 그대로: %s)'
          % (len(placeholders), len(extra_keys), len(skipped), skipped))

    def make_deal(v, pat):
        deal = collections.OrderedDict()
        deal['date'] = v['date']
        deal['back'] = v['back']
        deal['pattern'] = pat
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt']:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        return json.loads(json.dumps(deal))

    replaced = []
    for key, old in placeholders.items():
        v = cells[key]
        deals = routes[key[0]]['deals']
        idx = next(i for i, d in enumerate(deals) if (d['date'], d['pattern']) == key[1:])
        deals[idx] = make_deal(v, key[2])
        replaced.append((key[0], key[1], key[2], old['price'], v['price']))

    added = []
    for key in sorted(extra_keys):
        routes[key[0]]['deals'].append(make_deal(cells[key], key[2]))
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
    if counts['byMonth'][MONTH] != before_jul + len(added):
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                 before_jul + len(added)))

    rows = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if WEEK_START <= d['date'] <= WEEK_END
            and d['pattern'] in PAT_NIGHTS]
    if len(rows) != EXPECT_CELLS:
        raise SystemExit('이 주 칸 %d칸 (기대 %d칸)' % (len(rows), EXPECT_CELLS))
    ps = [d['price'] for d in rows]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('이 주 최저·최고 %s (기대 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    if any(d.get('src') for d in rows):
        raise SystemExit('이 주에 가격표 자리표시 칸이 남아 있습니다')

    avg120 = round(sum(ps) / len(ps))
    week_sent = ('2027년 7월 2주차(7/8~12) 24개 노선 5패턴 120칸도 전부 실측했습니다 — '
                 '이 주에도 한국 공휴일이 없고(일본 해의 날은 7/19로 이 주 밖) 주말 수요만 '
                 '반영된 주차이며, ' + week_note(rows, '이 주(7/8~12)')
                 + ' 이 주는 토요일 출발·월요일 귀국 2박(②)이 가장 싸고 목요일 출발·일요일 '
                   '귀국 3박(③)이 가장 비싸 1·5위 차이가 16,396원입니다(1주차와 순서가 '
                   '달라 1주차의 1위였던 목~월 4박이 이 주에는 3위). 120칸 평균은 '
                 + format(avg120, ',') + '원으로 1주차(7/1~5) 519,282원보다 13,442원 '
                   '(-2.6%) 낮습니다. 가격표 자리표시 18칸은 실측값으로 교체했고, 같은 주의 '
                   '0박 당일치기 1칸(상하이 7/8 목~목)은 이 조사 범위 밖이라 그대로 두었습니다.')
    if '**' in week_sent:
        raise SystemExit('notes 문장에 마크다운 별표가 있습니다')
    for word in BANNED:
        if word in week_sent:
            raise SystemExit('notes 문장에 제3자 사이트 이름(%s)이 있습니다' % word)
    fl['notes'][MONTH] = fl['notes'][MONTH].rstrip() + ' ' + week_sent

    for key, old in before.items():
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != old:
            raise SystemExit('%s 가 바뀌었습니다' % key)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다')
    if json.dumps(fl['weeks'], ensure_ascii=False) != weeks_before:
        raise SystemExit('주차 정의가 바뀌었습니다')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('noSale 이 바뀌었습니다')
    if json.dumps(fl['bookingWindow'], ensure_ascii=False, sort_keys=True) != booking_before:
        raise SystemExit('bookingWindow 가 바뀌었습니다')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다')
    for code in ROUTES:
        old = json.loads(before_deals[code])
        cur = routes[code]['deals']
        expect_n = len(old) + 5 - sum(1 for k in placeholders if k[0] == code)
        if len(cur) != expect_n:
            raise SystemExit('%s 딜 %d건 (기존 %d + 이번 %d)'
                             % (code, len(cur), len(old),
                                5 - sum(1 for k in placeholders if k[0] == code)))
        have = {(d['date'], d['pattern']): d for d in cur}
        if len(have) != len(cur):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for o in old:
            key = (o['date'], o['pattern'])
            got = have.get(key)
            if got is None:
                raise SystemExit('%s 기존 딜이 사라졌습니다: %s %s' % (code, o['date'], o['pattern']))
            if (code, o['date'], o['pattern']) in placeholders:
                continue          # 이번 실측으로 교체된 칸
            if json.dumps(got, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(o, ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 기존 딜이 바뀌었습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
        keys = [(d['date'], WD[d['pattern'][0]]) for d in cur]
        if keys != sorted(keys):
            raise SystemExit('%s 딜 정렬이 깨졌습니다' % code)
        if json.dumps(routes[code]['daytrip'], ensure_ascii=False) != before_daytrip[code]:
            raise SystemExit('%s 당일치기 요약이 바뀌었습니다' % code)
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')
    for word in BANNED:
        if word in json.dumps(fl['notes'], ensure_ascii=False):
            raise SystemExit('notes 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    master['extended'] = (before_extended + ' / ' + args.note).strip(' /')

    print('교체 %d칸(평균 %s원 → %s원) · 신규 %d칸'
          % (len(replaced),
             format(round(sum(r[3] for r in replaced) / len(replaced)), ','),
             format(round(sum(r[4] for r in replaced) / len(replaced)), ','),
             len(added)))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'],
             counts['total'] - counts['daytrip'], counts['daytrip']))
    print('2027-07 %d → %d건' % (before_jul, counts['byMonth'][MONTH]))
    print('notes[2027-07] 새 문장:', week_sent)

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
