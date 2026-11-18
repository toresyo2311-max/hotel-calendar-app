#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선의 2027년 5월 3~4주차(5/13~17 · 5/20~24) 5패턴 240칸**
실측을 `data/master_db.json` 의 `flights` 에 병합한다.

원본 4개(`data-sources/flights-2027-05/`, 2026-11-19 06:57~08:40 KST 실측):
  · 부산출발-24노선-5월3_4주-일본괌.md          — FUK·KIX·TYO·NGO·OKA·GUM 60칸
      ```table 블록(노선별 10칸) `- [1, 목~일 05/13~05/16 (3박4일), ₩507,922, ₩507,922, 이스타항공 직항 1시간 10분]`
  · 부산출발-24노선-5월3_4주-중국.md            — PVG·BJS·NKG·HGH·TAO 50칸
      `| 05/13~05/16 | 목~일 | **₩532,342** | 대한항공 **직항** 1시간55분 (PUS 08:35 → PVG 09:30) | ₩532,342 대한항공 (같은 편) |`
  · 부산출발-24노선-5월3_4주-대만홍콩마카오.md   — TPE·HKG·KHH·RMQ·MFM 50칸
      `- [목~일, 05-13~16 (3박4일), ₩397,830, 타이거항공 타이완 · 직항 · 2h20]`
  · 부산출발-24노선-5월3_4주-동남아.md          — BKK·CNX·DAD·CXR·HAN·SGN·SIN·DPS 80칸
      `| S01 | 05/13~05/16 (목~일) | **₩375,172** | 비엣젯항공 · 1회 SGN · 8h35m (08:10→14:45) | 직항 0건 |`

규칙:
  · 240칸 모두 `routes[].deals` 로 넣는다(`price` = 원문 '전체 최저가' 그대로, 반올림 없음).
    빈칸·추정 없음 — 원문이 240칸 전부 값을 적었다(미오픈·판매편 0건·요금 미공개 0칸).
  · `via` 는 그 칸 **최저가 편성**이 직항인지(`false`) 경유인지(`true`)로 적고, 원문이
    편성을 특정하지 못한 1칸(상하이 5/13~17 — 최저가 탭 값만 있고 목록 최저는 직항)은 `null`.
  · `alt` 는 원문의 '직항 최저가'가 숫자로 있고 최저가보다 비쌀 때만 넣는다.
  · 이미 있는 칸은 건드리지 않는다(중복이면 멈춘다). 기존 24개 노선의 2027년 5월 칸은 0칸이다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 패턴 정의 · 다른 노선·기존 딜·`noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip, 최상위 deals)를 다시 세고, 2027-05 `notes`
    앞머리에 이번 240칸 문장을 넣는다(plain text — `**` 금지).
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_may34w.py --dry-run
    python3 tools/merge_flights_may34w.py
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
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-2027-05'))
FILES = ('부산출발-24노선-5월3_4주-일본괌.md',
         '부산출발-24노선-5월3_4주-중국.md',
         '부산출발-24노선-5월3_4주-대만홍콩마카오.md',
         '부산출발-24노선-5월3_4주-동남아.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
          'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
JP_ROUTES = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'NGO': '나고야',
             'OKA': '오키나와', 'GUM': '괌'}
CN_ROUTES = {'PVG': '상하이', 'BJS': '베이징', 'NKG': '난징', 'HGH': '항저우', 'TAO': '칭다오'}
TW_ROUTES = {'TPE': '타이베이', 'HKG': '홍콩', 'KHH': '가오슝', 'RMQ': '타이중', 'MFM': '마카오'}
SEA_ROUTES = {'BKK': '방콕', 'CNX': '치앙마이', 'DAD': '다낭', 'CXR': '나트랑',
              'HAN': '하노이', 'SGN': '호찌민', 'SIN': '싱가포르', 'DPS': '발리'}
CITY = dict(list(JP_ROUTES.items()) + list(CN_ROUTES.items()) + list(TW_ROUTES.items())
            + list(SEA_ROUTES.items()))
MONTH = '2027-05'
WEEK_THU = ('2027-05-13', '2027-05-20')       # 원문의 3주차·4주차 (목요일 기준)
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver')

# 원본이 스스로 적은 값 — 파싱이 조용히 빠뜨리거나 바꾸지 않았는지 대조한다
EXPECT_FILE = {
    '일본괌': (60, ('FUK', 'GUM', 'KIX', 'NGO', 'OKA', 'TYO'), 363085, 1033500),
    '중국': (50, ('BJS', 'HGH', 'NKG', 'PVG', 'TAO'), 305942, 822300),
    '대만홍콩마카오': (50, ('HKG', 'KHH', 'MFM', 'RMQ', 'TPE'), 273396, 1002900),
    '동남아': (80, ('BKK', 'CNX', 'CXR', 'DAD', 'DPS', 'HAN', 'SGN', 'SIN'), 266570, 711300),
}
# 노선 → (전체 최저, 전체 최고) — 각 파일의 노선별 요약 표와 같다
EXPECT_ROUTE = {
    'FUK': (363085, 670600), 'KIX': (426400, 673400), 'TYO': (542800, 795900),
    'NGO': (657700, 865203), 'OKA': (455900, 1033500), 'GUM': (658100, 888100),
    'PVG': (305942, 532342), 'BJS': (450400, 822300), 'NKG': (491718, 569500),
    'HGH': (472800, 699100), 'TAO': (499118, 686100),
    'TPE': (273396, 397830), 'HKG': (332370, 583546), 'KHH': (399700, 613400),
    'RMQ': (399700, 654600), 'MFM': (537900, 1002900),
    'BKK': (354411, 375172), 'CNX': (328401, 711300), 'DAD': (331573, 659700),
    'CXR': (352374, 581183), 'HAN': (266570, 377547), 'SGN': (295172, 352373),
    'SIN': (507376, 617191), 'DPS': (430222, 588184),
}
# 주차 → (출발일 범위, (최저, 최고), 직항이 최저가인 칸, 패턴 평균)
EXPECT_WEEK = (
    ('3주차', '2027-05-13', '2027-05-17', (276160, 1033500), 40,
     {'토~월': 500981, '금~월': 510430, '금~일': 550387, '목~월': 590767, '목~일': 625078}),
    ('4주차', '2027-05-20', '2027-05-24', (266570, 783000), 43,
     {'토~월': 456831, '금~월': 462037, '목~일': 473249, '금~일': 481741, '목~월': 494095}),
)
EXPECT_CELLS = 240
EXPECT_UNKNOWN_VIA = 1        # 상하이 5/13~17 — 최저가 탭 값(편성 미확인)
EXPECT_TOTAL = 7760 + EXPECT_CELLS
EXPECT_BY_MONTH_MAY = 423 + EXPECT_CELLS
EXPECT_DAYTRIP = 318
EXPECT_ALTS = {('BJS', '2027-05-13', '목~일'): 617688,
               ('FUK', '2027-05-20', '목~월'): None,
               ('SIN', '2027-05-20', '목~일'): 642000,
               ('TYO', '2027-05-14', '금~일'): 782900}
# 원본 베이징 표가 '전체 최저가'보다 '직항 최저가'를 더 낮게 적은 3칸.
# (베이징 5/13~16 · 5/14~16 · 5/20~23 — 원문의 '최저가' 탭 값과 직항 필터 값이 뒤집힌 칸.
#  값을 고치지 않고 원문 그대로 넣고, 화면에는 경유 금액과 함께 직항 금액이 보이게 둔다.)
EXPECT_ALT_BELOW = {('BJS', '2027-05-13', '목~일'): 617688,
                    ('BJS', '2027-05-14', '금~일'): 631048,
                    ('BJS', '2027-05-20', '목~일'): 492467}


def read(name):
    return open(os.path.join(SRC, name), encoding='utf-8').read()


def won(text):
    m = re.search(r'₩?\s*([\d,]+)', text)
    return int(m.group(1).replace(',', '')) if m else None


def dur(text):
    """'1시간55분' / '1시간 10분' / '2h20' / '8h35m' → '1시간 55분'."""
    if text is None:
        return ''
    t = text.strip()
    m = re.match(r'^(\d+)\s*h\s*(\d+)?\s*m?$', t)
    if m:
        return '%d시간 %s분' % (int(m.group(1)), m.group(2) or '0')
    m = re.match(r'^(\d+)\s*시간\s*(\d+)?\s*분?$', t)
    if m:
        return '%d시간 %s분' % (int(m.group(1)), m.group(2) or '0')
    return t


DUR_RE = re.compile(r'(\d+)\s*(?:시간\s*(\d+)?\s*분?|h\s*(\d+)?\s*m?)')


def norm_dur_anywhere(text):
    def rep(m):
        if m.group(1) and (m.group(2) or 'h' in m.group(0)):
            mins = m.group(2) or m.group(3) or '0'
            return '%d시간 %s분' % (int(m.group(1)), mins)
        return m.group(0)
    t = DUR_RE.sub(rep, text)
    t = t.replace('시간 분', '시간')
    t = re.sub(r'(\d+)시간\s*0분', r'\1시간', t)
    t = re.sub(r'\s*,\s*', ', ', t)
    return re.sub(r'\s{2,}', ' ', t).strip()


def date_of(mmdd, pat):
    """'05/13~05/16' + 패턴 → 출발일(요일 일치 확인)."""
    start = mmdd.split('~')[0].strip()
    m, d = [int(x) for x in start.split('/')]
    dt = datetime.date(2027, m, d)
    if (WD[pat[0]] - (dt.weekday() + 1) % 7) % 7 != 0:
        raise SystemExit('요일 불일치 %s %s' % (mmdd, pat))
    return dt.isoformat()


def cell(seen, key, **kw):
    if key in seen:
        raise SystemExit('중복 칸 %s' % (key,))
    seen[key] = kw


# ---------------------------------------------------------------- 일본·괌
def parse_jp(text):
    cells, code = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r'^title:\s*([A-Z]{3})\s', line)
        if m:
            code = m.group(1)
            if code not in JP_ROUTES:
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        m = re.match(r'^-\s*\[(?P<n>\d+),\s*(?P<pat>[월화수목금토일]~[월화수목금토일])\s*'
                     r'(?P<md>\d\d/\d\d~\d\d/\d\d)\s*\((?P<nights>\d)박\d일\),\s*'
                     r'(?P<price>₩[\d,]+)(?: ★최저)?,\s*'
                     r'(?P<direct>₩[\d,]+|[^,]+),\s*(?P<combo>.+)\]$', line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:50])
        pat = m.group('pat')
        if PAT_NIGHTS[pat] != int(m.group('nights')):
            raise SystemExit('%s 박수 불일치' % pat)
        date = date_of(m.group('md'), pat)
        price = won(m.group('price'))
        direct_raw = m.group('direct').strip()
        alt = won(direct_raw) if direct_raw.startswith('₩') else None
        combo = m.group('combo').strip()
        head, _, tail = combo.partition(' · ')
        air = re.match(r'^(?:경유 최저\s*)?([가-힣A-Za-z+]+)', head).group(1)
        is_direct = ('직항' in head) and ('경유' not in head) and ('자가환승' not in head)
        if is_direct:
            via = False
            dm = re.search(r'직항\s+(\d+시간(?:\s*\d+분)?)', head)
            note = '직항' + (' ' + dur(dm.group(1)) if dm else '')
            pm = re.search(r'\(([^)]+)\)\s*$', head)
            if pm and '직항' not in pm.group(1):
                other = re.match(r'^([가-힣]+)\s+([\d,]+)$', pm.group(1).strip())
                if other:
                    note += ' · 다른 직항 %s %s원' % (other.group(1), other.group(2))
                else:
                    note += ' · 다른 직항 %s' % pm.group(1).strip()
            alt = None
        else:
            via = True
            tm = re.search(r'(\d+시간(?:\s*\d+분)?)', head)
            if '자가환승' in head:
                note = '자가환승(별도 발권)'
            else:
                note = '경유 1회' if '1회' in head else '경유'
            if tm:
                note += (' · 총 ' if '1회' in note else ' · ') + dur(tm.group(1))
        if '가격 미표시' in combo:
            note += ' · 직항 가격 미표시'
        elif '직항 0건' in tail or '직항 0건' in combo:
            note += ' · 직항편 없음'
        elif '직항 표시 없음' in tail:
            note += ' · 직항 가격 미표시'
        m2 = re.search(r'직항 ([\d,]+) ([가-힣]+)$', combo)
        if m2 and not is_direct:
            alt = int(m2.group(1).replace(',', ''))
            note += ' · 직항 최저 %s원(%s)' % (format(alt, ','), m2.group(2))
        cell(cells, (code, date, pat), code=code, date=date, pattern=pat, price=price,
             via=via, airline=air, alt=alt if alt and alt != price else None, note=note)
    return cells


# ---------------------------------------------------------------- 중국
def parse_cn_combo(combo):
    """중국 표의 '최저 편성' 문장 → (note, via, airline)."""
    if combo.startswith('목록 최저 = '):
        return ('최저가 탭 값(편성 미확인)', None, None)
    if combo.startswith('날짜 표 값'):
        body = re.search(r'\((.*)\)$', combo)
        body = body.group(1) if body else ''
        note = '날짜 표 값'
        air = None
        if '대한항공' in body:
            note += ' · 대한항공 1회(인천)'
            air = '대한항공'
        note += ' · 목록 미확인'
        return (note, True, air)
    body, _, tail = combo.partition(' · ')
    if ' 직항' in body:
        air, _, rest = body.partition(' 직항')
        note = '직항'
        tm = re.search(r'(\d+시간\s*\d*분?)', rest)
        if tm:
            note += ' ' + dur(norm_dur_anywhere(tm.group(1)))
        hm = re.search(r'(\d\d:\d\d)\s*→\s*(\d\d:\d\d)', rest)
        if hm:
            note += '(%s-%s)' % (hm.group(1), hm.group(2))
        return (note, False, air.strip())
    m = re.match(r'^(?P<air>[가-힣]+(?:\+[가-힣]+)?)\s*(?P<n>\d)회경유'
                 r'(?:\((?P<inner>[^)]*)\))?\s*(?P<total>[\d시간분]*)$', body)
    if not m:
        raise SystemExit('중국 편성 문장을 읽지 못했습니다: %r' % combo)
    note = '경유 %s회' % m.group('n')
    if m.group('inner'):
        note += '(%s)' % norm_dur_anywhere(m.group('inner').strip())
    if m.group('total'):
        note += ' · 총 %s' % dur(norm_dur_anywhere(m.group('total')))
    if tail.startswith('목록'):
        note += ' · 목록 최저 %s원' % tail.replace('목록 최저 ', '').replace('목록 ', '')
    return (note, True, m.group('air'))


def parse_cn(text):
    cells, code = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if re.match(r'^##\s', line):
            found = [c for c in re.findall(r'\(([A-Z]{3})', line) if c in CN_ROUTES]
            code = found[0] if found else None
            continue
        m = re.match(r'^\|\s*(?P<md>\d\d/\d\d~\d\d/\d\d)\s*\|\s*'
                     r'(?P<pat>[월화수목금토일]~[월화수목금토일])\s*\|\s*'
                     r'\*\*(?P<price>₩[\d,]+)\*\*\s*\|\s*(?P<combo>.+?)\s*\|\s*'
                     r'(?P<direct>.+?)\s*\|$', line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:50])
        pat = m.group('pat')
        date = date_of(m.group('md'), pat)
        price = won(m.group('price'))
        combo = m.group('combo').replace('**', '').strip()
        direct_raw = m.group('direct').replace('**', '').strip()
        alt = won(direct_raw) if re.match(r'^₩', direct_raw) else None
        note, via, air = parse_cn_combo(combo)
        if '직항 0건' in direct_raw:
            note += ' · 직항편 없음'
            alt = None
        elif '가격 미표시' in direct_raw:
            note += ' · 직항 가격 미표시'
            alt = None
        elif via is False:
            alt = None
        elif alt is not None and alt != price:
            mm = re.search(r'₩[\d,]+\s*([가-힣]+)', direct_raw)
            note += ' · 직항 최저 %s원%s' % (format(alt, ','),
                                            '(%s)' % mm.group(1) if mm else '')
        cell(cells, (code, date, pat), code=code, date=date, pattern=pat, price=price,
             via=via, airline=air, alt=alt if alt and alt != price else None, note=note)
    return cells


# ---------------------------------------------------------------- 대만·홍콩·마카오
def parse_tw(text):
    cells, code = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if re.match(r'^##\s', line):
            m2 = re.search(r'\(([A-Z]{3})\)', line)
            code = m2.group(1) if m2 and m2.group(1) in TW_ROUTES else None
            continue
        m = re.match(r'^-\s*\[(?P<pat>[월화수목금토일]~[월화수목금토일]),\s*'
                     r'(?P<md>\d\d-\d\d~\d\d)\s*\((?P<nights>\d)박\d일\),\s*'
                     r'(?P<price>₩[\d,]+),\s*(?P<combo>.+)\]$', line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:50])
        pat = m.group('pat')
        if PAT_NIGHTS[pat] != int(m.group('nights')):
            raise SystemExit('%s 박수 불일치' % pat)
        date = date_of(m.group('md').replace('-', '/'), pat)
        price = won(m.group('price'))
        parts = [p.strip() for p in m.group('combo').split(' · ')]
        air = parts[0]
        if parts[1] == '직항':
            note = '직항' + (' ' + dur(parts[2]) if len(parts) > 2 else '')
            via = False
        else:
            lay = re.match(r'^([A-Z]{3})\s*(\d)회$', parts[1])
            note = '경유 %s회(%s)' % (lay.group(2), lay.group(1)) if lay else '경유'
            if len(parts) > 2:
                note += ' · 총 ' + dur(parts[2])
            via = True
        if code in ('TPE', 'HKG') and via:
            raise SystemExit('%s 최저가가 직항이 아닙니다: %s' % (code, line[:60]))
        cell(cells, (code, date, pat), code=code, date=date, pattern=pat, price=price,
             via=via, airline=air, alt=None, note=note)
    return cells


# ---------------------------------------------------------------- 동남아
def parse_sea(text):
    cells, code = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if re.match(r'^###\s', line):
            m2 = re.search(r'\(([A-Z]{3})\)', line)
            code = m2.group(1) if m2 and m2.group(1) in SEA_ROUTES else None
            continue
        m = re.match(r'^\|\s*(?P<n>S\d\d)\s*\|\s*(?P<md>\d\d/\d\d~\d\d/\d\d)\s*'
                     r'\((?P<pat>[월화수목금토일]~[월화수목금토일])\)\s*\|\s*'
                     r'\*\*(?P<price>₩[\d,]+)\*\*.*?\|\s*(?P<combo>.+?)\s*\|\s*'
                     r'(?P<direct>.+?)\s*\|$', line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:50])
        pat = m.group('pat')
        date = date_of(m.group('md'), pat)
        price = won(m.group('price'))
        combo = re.sub(r'\s*\[출처:[^\]]*\]', '', m.group('combo')).strip()
        direct_raw = re.sub(r'\s*\[출처:[^\]]*\]', '', m.group('direct'))
        direct_raw = direct_raw.replace('**', '').strip()
        alt = won(direct_raw) if direct_raw.startswith('₩') else None
        parts = [p.strip() for p in combo.split(' · ')]
        air = parts[0]
        if len(parts) > 1 and parts[1].startswith('직항'):
            via = False
            dm = re.search(r'(\d+h\s*\d*m?)', parts[1])
            note = '직항' + (' ' + dur(dm.group(1)) if dm else '')
            pm = re.search(r'\(([^)]*)\)$', parts[1])
            if pm:
                note += '(%s)' % pm.group(1).replace('→', '-')
            alt = None
        else:
            via = True
            lay = re.match(r'^(\d)회\s*([A-Z]{3})$', parts[1]) if len(parts) > 1 else None
            note = '경유 %s회(%s)' % (lay.group(1), lay.group(2)) if lay else '경유'
            if len(parts) > 2:
                note += ' · 총 ' + dur(parts[2].split(' (')[0].strip())
                pm = re.search(r'\(([^)]*)\)', parts[2])
                if pm:
                    note += ' (%s)' % pm.group(1).replace('→', '-')
        if direct_raw == '직항 0건':
            note += ' · 직항편 없음'
            alt = None
        elif '가격 미표시' in direct_raw:
            note += ' · 직항 가격 미표시'
            alt = None
        elif alt is not None and alt != price:
            mm = re.search(r'₩[\d,]+\s*([가-힣]+)', direct_raw)
            note += ' · 직항 최저 %s원%s' % (format(alt, ','),
                                            '(%s)' % mm.group(1) if mm else '')
        cell(cells, (code, date, pat), code=code, date=date, pattern=pat, price=price,
             via=via, airline=air, alt=alt if alt and alt != price else None, note=note)
    return cells


def parse_all():
    cells = {}
    for name, fn in zip(FILES, (parse_jp, parse_cn, parse_tw, parse_sea)):
        path = os.path.join(SRC, name)
        if not os.path.isfile(path):
            raise SystemExit('원본이 없습니다: %s' % path)
        got = fn(read(name))
        tag = name.split('-')[-1].replace('.md', '')
        want = EXPECT_FILE[tag]
        if len(got) != want[0]:
            raise SystemExit('%s %d칸 (원문 %d칸)' % (name, len(got), want[0]))
        codes = tuple(sorted({k[0] for k in got}))
        if codes != want[1]:
            raise SystemExit('%s 노선 %s (원문 %s)' % (name, list(codes), list(want[1])))
        ps = [c['price'] for c in got.values()]
        if (min(ps), max(ps)) != want[2:]:
            raise SystemExit('%s 최저·최고 %s (원문 %s)' % (name, (min(ps), max(ps)), want[2:]))
        for k, v in got.items():
            if k in cells:
                raise SystemExit('파일 간 중복 %s' % (k,))
            cells[k] = v
    return cells


def check(cells):
    if len(cells) != EXPECT_CELLS:
        raise SystemExit('%d칸 (기대 %d칸)' % (len(cells), EXPECT_CELLS))
    if {k[0] for k in cells} != set(ROUTES):
        raise SystemExit('노선이 24개가 아닙니다: %s' % sorted({k[0] for k in cells}))
    # 24노선 × 10칸(목·금·토 출발 5패턴, 두 주)
    want = set()
    for code in ROUTES:
        for thu in WEEK_THU:
            for pat in PAT_NIGHTS:
                d = (datetime.date.fromisoformat(thu) +
                     datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
                want.add((code, d, pat))
    if set(cells) != want:
        raise SystemExit('칸 집합이 24노선 × 두 주 5패턴과 다릅니다: %s'
                         % sorted(set(cells) ^ want)[:6])
    for code, (lo, hi) in EXPECT_ROUTE.items():
        ps = [c['price'] for k, c in cells.items() if k[0] == code]
        if (min(ps), max(ps)) != (lo, hi):
            raise SystemExit('%s 최저·최고 %s (원문 %s)' % (code, (min(ps), max(ps)), (lo, hi)))
        if len(ps) != 10:
            raise SystemExit('%s %d칸 (기대 10칸)' % (code, len(ps)))
    for label, start, end, overall, direct, avg in EXPECT_WEEK:
        rows = [c for c in cells.values() if start <= c['date'] <= end]
        if len(rows) != 120:
            raise SystemExit('%s %d칸 (기대 120칸)' % (label, len(rows)))
        ps = [c['price'] for c in rows]
        if (min(ps), max(ps)) != overall:
            raise SystemExit('%s 최저·최고 %s (원문 %s)' % (label, (min(ps), max(ps)), overall))
        got = sum(1 for c in rows if c['via'] is False)
        if got != direct:
            raise SystemExit('%s 직항이 최저가인 칸 %d (원문 %d)' % (label, got, direct))
        for pat, want_avg in avg.items():
            v = [c['price'] for c in rows if c['pattern'] == pat]
            if len(v) != 24:
                raise SystemExit('%s %s %d칸 (기대 24칸)' % (label, pat, len(v)))
            if abs(sum(v) / len(v) - want_avg) > 1:
                raise SystemExit('%s %s 평균 %.1f (원문 %d)'
                                 % (label, pat, sum(v) / len(v), want_avg))
    unk = [k for k, c in cells.items() if c['via'] is None]
    if len(unk) != EXPECT_UNKNOWN_VIA:
        raise SystemExit('편성 미확인 칸 %d (기대 %d): %s'
                         % (len(unk), EXPECT_UNKNOWN_VIA, unk))
    for key, alt in EXPECT_ALTS.items():
        got = cells[key]['alt']
        if got != alt:
            raise SystemExit('%s 직항 최저 %s (원문 %s)' % (key, got, alt))
    for k, c in cells.items():
        if c['alt'] is not None and c['alt'] <= c['price']:
            if EXPECT_ALT_BELOW.get(k) != c['alt']:
                raise SystemExit('%s 직항 최저가가 최저가 이하입니다: %s <= %s'
                                 % (k, c['alt'], c['price']))
        if c['price'] <= 0:
            raise SystemExit('%s 가격이 양의 정수가 아닙니다' % (k,))
        if not c['airline'] and c['via'] is not None:
            raise SystemExit('%s 항공사 비어 있음' % (k,))
        if not c['note']:
            raise SystemExit('%s note 비어 있음' % (k,))
        if '**' in c['note'] or '[' in c['note']:
            raise SystemExit('%s note 에 마크업이 있습니다: %r' % (k, c['note']))
        for word in BANNED:
            if word in c['note'] or word in (c['airline'] or ''):
                raise SystemExit('%s 값에 제3자 사이트 이름(%s)이 있습니다' % (k, word))
    # 원문 표에 남은 '직항 최저' 값이 최저가보다 비싼 3칸(BJS)은 원문 자체가 그렇게 적었다
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


def week_note(rows, label):
    lo = min(rows, key=lambda d: d['price'])
    hi = max(rows, key=lambda d: d['price'])
    agg = collections.defaultdict(list)
    for d in rows:
        agg[d['pattern']].append(d['price'])
    avg = ' < '.join('{} {}원'.format(p, format(round(sum(v) / len(v)), ','))
                     for p, v in sorted(agg.items(), key=lambda kv: sum(kv[1]) / len(kv[1])))
    direct = sum(1 for d in rows if d.get('via') is False)
    unk = sum(1 for d in rows if d.get('via') is None)
    span = lambda d: '%d/%d~%d/%d' % (int(d['date'][5:7]), int(d['date'][8:10]),
                                      int(d['back'][5:7]), int(d['back'][8:10]))
    ties_lo = sum(1 for d in rows if d['price'] == lo['price'])
    ties_hi = sum(1 for d in rows if d['price'] == hi['price'])
    return (label + ' 최저는 ' + CITY[lo['code']] + ' ' + span(lo) + ' ' + lo['pattern'] + ' '
            + format(lo['price'], ',') + '원(' + (lo['airline'] or '항공사 미확인') + ' '
            + _viaword(lo) + (' · 같은 금액 %d칸' % ties_lo if ties_lo > 1 else '')
            + ')이고, 최고는 ' + CITY[hi['code']] + ' ' + span(hi) + ' '
            + hi['pattern'] + ' ' + format(hi['price'], ',') + '원('
            + (hi['airline'] or '항공사 미확인') + ' ' + _viaword(hi)
            + (' · 같은 금액 %d칸' % ties_hi if ties_hi > 1 else '') + ')입니다. 직항이 최저가인 칸 '
            + str(direct) + ' · 경유 ' + str(len(rows) - direct - unk)
            + (' · 편성 미확인 ' + str(unk) if unk else '') + '칸이고, 패턴 평균은 ' + avg + ' 순입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 5월 3~4주 240칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ④ 항공 기존 24개 노선 2027년 5월 3~4주차(5/13~17 · 5/20~24) '
        '5패턴 240칸 완결 — 최저 하노이 5/20~24 목~월 266,570원(직항), 직항이 최저가인 칸 83, '
        '총 7,760→8,000건'))
    args = ap.parse_args(argv)

    cells = check(parse_all())
    print('파싱 240칸 — 최저 %s · 최고 %s · 직항이 최저인 칸 %d · 편성 미확인 %d'
          % (format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ','),
             sum(1 for c in cells.values() if c['via'] is False),
             sum(1 for c in cells.values() if c['via'] is None)))

    master = json.load(open(MASTER, encoding='utf-8'))
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다' % code)

    before = {k: json.dumps(master.get(k), ensure_ascii=False, sort_keys=True)
              for k in ('hotels', 'accor', 'sources', 'window', 'built', 'voucherExpiry',
                        'schema', 'version')}
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    before_deals = {c: json.dumps(routes[c]['deals'], ensure_ascii=False) for c in ROUTES}
    before_daytrip = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_may = fl['counts']['byMonth'][MONTH]
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])

    added = []
    for (code, date, pat), v in sorted(cells.items()):
        if any(d['date'] == date and d['pattern'] == pat for d in routes[code]['deals']):
            raise SystemExit('이미 있는 칸입니다: %s %s %s' % (code, date, pat))
        deal = collections.OrderedDict()
        deal['date'] = date
        deal['back'] = (datetime.date.fromisoformat(date) +
                        datetime.timedelta(days=PAT_NIGHTS[pat])).isoformat()
        deal['pattern'] = pat
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt']:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        routes[code]['deals'].append(json.loads(json.dumps(deal)))
        added.append((code, date, pat))
        for word in BANNED:
            if word in json.dumps(deal, ensure_ascii=False):
                raise SystemExit('%s %s 값에 제3자 사이트 이름이 있습니다' % (code, date))
    if len(added) != EXPECT_CELLS:
        raise SystemExit('신규 %d칸 (기대 %d칸)' % (len(added), EXPECT_CELLS))
    for code in ROUTES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))

    counts = recount(fl)
    if counts['total'] != EXPECT_TOTAL:
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], EXPECT_TOTAL))
    if counts['byMonth'][MONTH] != EXPECT_BY_MONTH_MAY:
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                  EXPECT_BY_MONTH_MAY))
    if counts['daytrip'] != EXPECT_DAYTRIP:
        raise SystemExit('당일치기 %d건 (기대 %d건)' % (counts['daytrip'], EXPECT_DAYTRIP))
    if counts['holiday'] != 185:
        raise SystemExit('연휴 칸 %d건 (기대 185)' % counts['holiday'])

    w3 = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
          for d in r['deals'] if '2027-05-13' <= d['date'] <= '2027-05-17']
    w4 = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
          for d in r['deals'] if '2027-05-20' <= d['date'] <= '2027-05-24']
    if (len(w3), len(w4)) != (120, 120):
        raise SystemExit('5월 3·4주차 칸 %d · %d (기대 120 · 120)' % (len(w3), len(w4)))
    # 직항편이 아예 없는 10개 노선(원문 각 절이 '직항 0건'으로 적은 노선)
    nodirect = [c for c in ROUTES
                if all('직항편 없음' in cells[k]['note'] for k in cells if k[0] == c)]
    if sorted(nodirect) != sorted(['NGO', 'GUM', 'BKK', 'CNX', 'DPS', 'NKG', 'HGH']):
        raise SystemExit('직항편 없음 표기가 예상과 다릅니다: %s' % sorted(nodirect))
    # 원문이 '직항 0건'을 칸마다 적지 않은 대만 3노선(가오슝·타이중·마카오)은 절 제목으로 확인
    nodirect = ['NGO', 'GUM', 'BKK', 'CNX', 'DPS', 'KHH', 'RMQ', 'MFM', 'NKG', 'HGH']
    via_only = {}
    for code in ('SIN', 'BJS', 'TAO'):
        via_only[code] = sum(1 for k in cells if k[0] == code and cells[k]['via'] is not False
                             and '직항편 없음' not in cells[k]['note'])
    if via_only != {'SIN': 10, 'BJS': 9, 'TAO': 8}:
        raise SystemExit('직항이 있으나 최저가가 경유인 칸 집계가 다릅니다: %s' % via_only)
    head = ('기존 24개 노선은 2027년 5월 3~4주차(5/13~17 · 5/20~24) 5패턴 240칸을 전부 실측했습니다'
            '(빈칸·추정 0칸). ' + week_note(w3, '3주차(5/13~17)') + ' '
            + week_note(w4, '4주차(5/20~24)') + ' '
            '직항편이 있는 노선은 후쿠오카·오사카·도쿄·오키나와·타이베이·홍콩·상하이·베이징·칭다오·'
            '나트랑·다낭·하노이·호찌민·싱가포르 14개이고, 나고야·괌·방콕·치앙마이·발리·가오슝·'
            '타이중·마카오·난징·항저우 10개 노선은 이 두 주에 직항편이 없습니다. 싱가포르 10칸·'
            '베이징 9칸·칭다오 8칸은 직항이 있지만 최저가가 경유이고, 상하이 5/13~17 1칸은 '
            '최저가만 표시되고 편성이 확인되지 않아 미확인으로 두었습니다. 베이징은 같은 칸에서 '
            '직항이 경유 금액보다 싸게 표시된 3칸(5/13~16 · 5/14~16 · 5/20~23)이 원문에 있어 '
            '그대로 적었습니다.')
    if fl['notes'][MONTH].startswith('중국 8개 노선은'):
        fl['notes'][MONTH] = head + ' ' + fl['notes'][MONTH]
    else:
        raise SystemExit('2027-05 notes 의 첫 문장이 예상과 다릅니다: %r'
                         % fl['notes'][MONTH][:40])

    # 보존 확인
    for key, old in before.items():
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != old:
            raise SystemExit('%s 가 바뀌었습니다' % key)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('noSale 이 바뀌었습니다')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다')
    for code in ROUTES:
        old = json.loads(before_deals[code])
        cur = routes[code]['deals']
        if len(cur) != len(old) + 10:
            raise SystemExit('%s 딜 %d건 (기존 %d + 10)' % (code, len(cur), len(old)))
        have = {(d['date'], d['pattern']): d for d in cur}
        if len(have) != len(cur):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for o in old:
            got = have.get((o['date'], o['pattern']))
            if json.dumps(got, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(o, ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 기존 딜이 바뀌었습니다: %s %s' % (code, o['date'], o['pattern']))
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

    print('신규 %d칸 · 총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (len(added), before_total, counts['total'],
             counts['total'] - counts['daytrip'], counts['daytrip']))
    print('2027-05 %d → %d건' % (before_may, counts['byMonth'][MONTH]))
    print('notes[2027-05] 앞부분:', fl['notes'][MONTH][:400])

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
