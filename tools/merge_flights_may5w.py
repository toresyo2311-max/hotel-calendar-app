#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선의 2027년 5월 5주차(5/27~5/31) 5패턴 120칸** 실측을
`data/master_db.json` 의 `flights` 에 병합한다.

원본 4개(`data-sources/flights-2027-05/`, 2026-11-19 07:30~08:25 KST 실측):
  · 부산출발-24노선-5월5주-일본괌.md          — FUK·KIX·TYO·NGO·OKA·GUM 30칸
      ```table 블록의 `- [1, 목~일 05/27~05/30 (3박4일), ₩382,320 · 이스타 직항 1시간10분, ₩382,320 · 이스타 14:50]`
  · 부산출발-24노선-5월5주-중국.md            — PVG·BJS·NKG·HGH·TAO 25칸
      `| 05/27~05/30 | 목~일 | **₩380,802** | 대한항공+스프링항공 자가 환승(CJU 8시간40분) 21:15 → 07:35+1 · 11시간20분 | ₩402,044 · 대한항공 15:50 → 16:50 · 2시간 |`
  · 부산출발-24노선-5월5주-대만홍콩마카오.md   — TPE·HKG·KHH·RMQ·MFM 25칸
      `- ["목~일", "05-27~30 (3박4일)", "₩288,183", "타이거항공 타이완 · 직항 · 2h20"]`
  · 부산출발-24노선-5월5주-동남아.md          — BKK·CNX·DAD·CXR·HAN·SGN·SIN·DPS 40칸
      `| S01 | 05/27~05/30 (3박4일) | **₩364,871** [출처…] | 비엣젯항공 · 1회 경유 SGN · 8h35m (08:10→14:45) | 직항 0건 [출처…] |`

규칙:
  · 120칸 모두 `routes[].deals` 로 넣는다(`price` = 원문 금액 그대로, 반올림 없음).
    빈칸·추정 없음 — 원문이 120칸 전부 값을 적었다(미오픈·판매편 0건·요금 미공개 0칸).
  · `via` 는 그 칸 **최저가 편성**이 직항인지(`false`) 경유인지(`true`)로 적고, 원문이
    'OTA 최저가(편성 미확인)'로만 적은 칸(항저우 3칸)은 `null`.
  · `alt` 는 원문의 '직항 최저가'가 숫자로 있고 최저가보다 비쌀 때만 넣는다.
  · 이미 있는 칸은 건드리지 않는다(중복이면 멈춘다). 기존 24개 노선의 5/27~31 칸은 0칸이다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 패턴 정의 · 다른 노선·기존 딜·`noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-05 `notes` 앞머리에
    이번 120칸 문장을 넣는다(plain text — `**` 금지).
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_may5w.py --dry-run
    python3 tools/merge_flights_may5w.py
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
FILES = ('부산출발-24노선-5월5주-일본괌.md',
         '부산출발-24노선-5월5주-중국.md',
         '부산출발-24노선-5월5주-대만홍콩마카오.md',
         '부산출발-24노선-5월5주-동남아.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
          'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'NGO': '나고야',
        'OKA': '오키나와', 'GUM': '괌', 'PVG': '상하이', 'BJS': '베이징', 'NKG': '난징',
        'HGH': '항저우', 'TAO': '칭다오', 'TPE': '타이베이', 'HKG': '홍콩', 'KHH': '가오슝',
        'RMQ': '타이중', 'MFM': '마카오', 'BKK': '방콕', 'CNX': '치앙마이', 'DAD': '다낭',
        'CXR': '나트랑', 'HAN': '하노이', 'SGN': '호찌민', 'SIN': '싱가포르', 'DPS': '발리'}
MONTH = '2027-05'
WEEK_START, WEEK_END = '2027-05-27', '2027-05-31'
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver')
AIR = {'이스타': '이스타항공', '비엣젯': '비엣젯항공', '스프링': '스프링항공',
       '홍콩익스프레스': '홍콩 익스프레스항공', '에어차이나': '중국국제항공',
       '동방항공': '중국동방항공', '타이거': '타이거항공 타이완'}

# 원본이 스스로 적은 값 — 파싱이 조용히 빠뜨리거나 바꾸지 않았는지 대조한다
EXPECT_FILE = {
    '일본괌': (30, ('FUK', 'GUM', 'KIX', 'NGO', 'OKA', 'TYO'), 333438, 733100),
    '중국': (25, ('BJS', 'HGH', 'NKG', 'PVG', 'TAO'), 286047, 569500),
    '대만홍콩마카오': (25, ('HKG', 'KHH', 'MFM', 'RMQ', 'TPE'), 288183, 849300),
    '동남아': (40, ('BKK', 'CNX', 'CXR', 'DAD', 'DPS', 'HAN', 'SGN', 'SIN'), 282171, 605230),
}
# 노선 → (최저, 최고) — 각 파일의 노선 요약과 같다
EXPECT_ROUTE = {
    'FUK': (333438, 429700), 'KIX': (411844, 453400), 'TYO': (542800, 587800),
    'NGO': (657700, 702700), 'OKA': (482400, 713000), 'GUM': (683100, 733100),
    'PVG': (286047, 404447), 'BJS': (412300, 499900), 'NKG': (481502, 569500),
    'HGH': (473637, 513100), 'TAO': (473400, 518700),
    'TPE': (288183, 302983), 'HKG': (315415, 383495), 'KHH': (399700, 633400),
    'RMQ': (399700, 460000), 'MFM': (749300, 849300),
    'BKK': (354361, 364871), 'CNX': (328401, 553300), 'DAD': (331573, 469900),
    'CXR': (352374, 378375), 'HAN': (282171, 323772), 'SGN': (295172, 295172),
    'SIN': (507209, 605230), 'DPS': (570134, 586523),
}
EXPECT_CELLS = 120
EXPECT_OVERALL = (282171, 849300)
EXPECT_AVG = {'목~일': 481303, '금~일': 465632, '토~월': 466150,
              '금~월': 457678, '목~월': 491480}
EXPECT_DIRECT = 45
EXPECT_UNKNOWN_VIA = 7        # 항저우 3칸 · 칭다오 4칸 — '최저가 탭 값(편성 미확인)'
EXPECT_ALTS = 9
EXPECT_TOTAL = 8120 + EXPECT_CELLS
EXPECT_BY_MONTH = 687 + 120
EXPECT_DAYTRIP = 318


def read(name):
    return open(os.path.join(SRC, name), encoding='utf-8').read()


def won(text):
    m = re.search(r'([\d,]+)', text)
    return int(m.group(1).replace(',', '')) if m else None


def dur(text):
    """'4시간55분' / '1h10m' / '4h30m' / '8h35m' → '4시간 55분'."""
    if not text:
        return ''
    t = text.strip()
    m = re.match(r'^(\d+)\s*h\s*(\d+)?\s*m?$', t)
    if m:
        return '%d시간 %s분' % (int(m.group(1)), (m.group(2) or '0').rjust(2, '0'))
    m = re.match(r'^(\d+)\s*시간\s*(\d+)?\s*분?$', t)
    if m:
        return '%d시간 %s분' % (int(m.group(1)), (m.group(2) or '0').rjust(2, '0'))
    return t


def norm_dur(text):
    """문장 안의 '1시간10분' → '1시간 10분'."""
    def rep(m):
        return '%s시간 %s분' % (m.group(1), (m.group(2) or '0').rjust(2, '0'))
    return re.sub(r'(\d+)\s*시간\s*(\d+)?\s*분?', rep, text)


def air_name(text):
    t = text.strip()
    for k, v in AIR.items():
        if t == k:
            return v
    t = re.sub(r'^이스타\+', '이스타항공+', t)
    return t


def date_of(start_md, pat):
    m, d = [int(x) for x in re.split(r'[/-]', start_md)]
    dt = datetime.date(2027, m, d)
    if (WD[pat[0]] - (dt.weekday() + 1) % 7) % 7 != 0:
        raise SystemExit('요일 불일치 %s %s' % (start_md, pat))
    return dt.isoformat()


def cell(cells, key, **kw):
    if key in cells:
        raise SystemExit('중복 칸 %s' % (key,))
    cells[key] = kw


# ---------------------------------------------------------------- 일본·괌
def parse_jp(text):
    cells, code = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r'^title:\s*([A-Z]{3})\s', line)
        if m:
            code = m.group(1)
            if code not in ('FUK', 'KIX', 'TYO', 'NGO', 'OKA', 'GUM'):
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        m = re.match(r'^-\s*\[\d+,\s*(?P<pat>[월화수목금토일]~[월화수목금토일])\s*'
                     r'(?P<m1>\d\d)/(?P<d1>\d\d)~(?P<m2>\d\d)/(?P<d2>\d\d)\s*'
                     r'\((?P<nights>\d)박\d일\),\s*(?P<price>₩[\d,]+)(?:\s*★최저)?\s*·\s*'
                     r'(?P<combo>[^,]+?),\s*(?P<direct>[^\]]+)\]$', line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:60])
        pat = m.group('pat')
        if PAT_NIGHTS[pat] != int(m.group('nights')):
            raise SystemExit('%s 박수 불일치' % pat)
        date = date_of('%s/%s' % (m.group('m1'), m.group('d1')), pat)
        price = won(m.group('price'))
        combo = m.group('combo').strip()
        cm = re.match(r'^(?P<air>[^ ]+)\s+(?P<leg>직항|\d회)\s*(?P<rest>.*)$', combo)
        if not cm:
            raise SystemExit('%s 편성 문장을 읽지 못했습니다: %r' % (code, combo))
        airline = air_name(cm.group('air'))
        if cm.group('leg') == '직항':
            via = False
            note = '직항' + (' ' + dur(cm.group('rest')) if cm.group('rest') else '')
        else:
            via = True
            note = '경유 %s회' % cm.group('leg')[:1]
            if cm.group('rest'):
                note += ' · 총 ' + dur(cm.group('rest'))
        alt = None
        direct = m.group('direct').strip()
        if '직항 0건' in direct:
            hub = re.search(r'직항 0건\s*\((.+?)\)', direct)
            note += ' · 직항편 없음' + ('(%s)' % hub.group(1) if hub else '')
        elif direct.startswith('₩'):
            alt = won(direct)
            dm = re.search(r'·\s*([^\s·]+)', direct[direct.find('·'):] if '·' in direct else '')
            if alt <= price or via is False:
                alt = None
            else:
                note += ' · 직항 최저 %s원%s' % (
                    format(alt, ','), '(%s)' % air_name(dm.group(1)) if dm else '')
        else:
            raise SystemExit('%s 직항 열을 읽지 못했습니다: %r' % (code, direct))
        cell(cells, (code, date, pat), code=code, date=date, pattern=pat, price=price,
             airline=airline, via=via, alt=alt, note=note)
    return cells


# ---------------------------------------------------------------- 중국
def parse_cn_combo(combo):
    combo = combo.replace('**', '').strip()
    if combo.startswith('OTA 최저가'):
        m = re.search(r'목록 최저는\s*(.+?)\s*·\s*([\d,]+)$', combo)
        note = '최저가 탭 값(편성 미확인)'
        if m:
            note += ' · 목록 최저 %s원(%s)' % (m.group(2), norm_dur(m.group(1)))
        return note, None, None
    m = re.match(r'^(?P<air>.+?)\s+(?P<leg>직항|자가 환승|\d회 경유)\s*'
                 r'(?:\((?P<inner>[^)]*)\))?\s*'
                 r'(?P<times>\d\d:\d\d\s*→\s*\d\d:\d\d(?:\+\d)?)?\s*'
                 r'(?:·\s*(?P<total>\d+시간\s*\d*분?)?)?\s*(?:·\s*(?P<extra>.*))?$', combo)
    if not m:
        raise SystemExit('중국 편성 문장을 읽지 못했습니다: %r' % combo)
    airline = air_name(m.group('air'))
    times = (m.group('times') or '').replace(' → ', '-').replace(' ', '')
    total = dur(m.group('total')) if m.group('total') else ''
    extra = (' · ' + m.group('extra').strip()) if m.group('extra') else ''
    if m.group('leg') == '직항':
        note = '직항' + (' ' + total if total else '')
        if times:
            note += '(%s)' % times
        return note, False, airline
    if m.group('leg') == '자가 환승':
        note = '자가환승(별도 발권)'
        if total:
            note += ' · 총 ' + total
        if times:
            note += ' (%s)' % times
        return note, True, airline
    note = '경유 %s회' % m.group('leg')[:1]
    if m.group('inner'):
        hub = m.group('inner').split()[0]
        note += '(%s)' % hub
        lay = re.search(r'(\d+시간\s*\d*분?)', m.group('inner'))
        if lay:
            note += ' · 환승 ' + dur(lay.group(1))
    if total:
        note += ' · 총 ' + total
    if times:
        note += ' (%s)' % times
    return note, True, airline


def parse_cn(text):
    cells, code = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if re.match(r'^##\s', line):
            found = [c for c in re.findall(r'\(([A-Z]{3})', line) if c in
                     ('PVG', 'BJS', 'NKG', 'HGH', 'TAO')]
            code = found[0] if found else None
            continue
        m = re.match(r'^\|\s*(?P<m1>\d\d)/(?P<d1>\d\d)~(?P<m2>\d\d)/(?P<d2>\d\d)\s*\|\s*'
                     r'(?P<pat>[월화수목금토일]~[월화수목금토일])\s*\|\s*'
                     r'\*\*(?P<price>₩[\d,]+)\*\*\s*\|\s*(?P<combo>.+?)\s*\|\s*'
                     r'(?P<direct>.+?)\s*\|$', line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:60])
        pat = m.group('pat')
        date = date_of('%s/%s' % (m.group('m1'), m.group('d1')), pat)
        price = won(m.group('price'))
        note, via, airline = parse_cn_combo(m.group('combo'))
        direct = m.group('direct').replace('**', '').strip()
        alt = None
        if direct == '직항 0건':
            note += ' · 직항편 없음'
        elif direct.startswith('직항 왕복 조합 0건'):
            note += ' · 직항 왕복 조합 없음'
        elif direct.startswith('가격 확인 불가') or direct.startswith('가격 미표시'):
            note += ' · 직항 가격 미표시'
        elif direct.startswith('₩'):
            alt = won(direct)
            if alt <= price or via is False:
                alt = None
            else:
                mm = re.search(r'₩[\d,]+\s*·\s*([^\s()]+)', direct)
                note += ' · 직항 최저 %s원%s' % (
                    format(alt, ','), '(%s)' % air_name(mm.group(1)) if mm else '')
        else:
            raise SystemExit('%s 직항 열을 읽지 못했습니다: %r' % (code, direct))
        cell(cells, (code, date, pat), code=code, date=date, pattern=pat, price=price,
             airline=airline, via=via, alt=alt, note=note)
    return cells


# ---------------------------------------------------------------- 대만·홍콩·마카오
def parse_tw(text):
    cells, code = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if re.match(r'^##\s', line):
            m2 = re.search(r'\(([A-Z]{3})\)', line)
            code = m2.group(1) if m2 and m2.group(1) in ('TPE', 'HKG', 'KHH', 'RMQ', 'MFM') \
                else None
            continue
        m = re.match(r'^-\s*\["(?P<pat>[월화수목금토일]~[월화수목금토일])",\s*'
                     r'"(?P<m1>\d\d)-(?P<d1>\d\d)~(?P<d2>\d\d)\s*\((?P<nights>\d)박\d일\)",\s*'
                     r'"(?P<price>₩[\d,]+)",\s*"(?P<combo>[^"]+)"\]$', line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:60])
        pat = m.group('pat')
        if PAT_NIGHTS[pat] != int(m.group('nights')):
            raise SystemExit('%s 박수 불일치' % pat)
        date = date_of('%s/%s' % (m.group('m1'), m.group('d1')), pat)
        price = won(m.group('price'))
        parts = [p.strip() for p in m.group('combo').split(' · ')]
        airline = air_name(parts[0])
        if len(parts) < 3:
            raise SystemExit('%s 편성 문장을 읽지 못했습니다: %r' % (code, m.group('combo')))
        if '직항' in parts[1]:
            via = False
            note = '직항' + (' ' + dur(parts[2]) if parts[2] else '')
        elif '경유' in parts[1] or '회' in parts[1]:
            via = True
            hm = re.match(r'^(?P<hub>[A-Z]{3})\s*(?P<n>\d)회', parts[1])
            note = ('경유 %s회(%s)' % (hm.group('n'), hm.group('hub'))) if hm else '경유'
            if parts[2]:
                note += ' · 총 ' + dur(parts[2])
        else:
            raise SystemExit('%s 편성 문장을 읽지 못했습니다: %r' % (code, m.group('combo')))
        cell(cells, (code, date, pat), code=code, date=date, pattern=pat, price=price,
             airline=airline, via=via, alt=None, note=note)
    return cells


# ---------------------------------------------------------------- 동남아
def parse_sea(text):
    cells, code = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if re.match(r'^###\s', line):
            m2 = re.search(r'\(([A-Z]{3})\)', line)
            code = m2.group(1) if m2 and m2.group(1) in (
                'BKK', 'CNX', 'DAD', 'CXR', 'HAN', 'SGN', 'SIN', 'DPS') else None
            continue
        m = re.match(r'^\|\s*S\d\d\s*\|\s*(?P<m1>\d\d)/(?P<d1>\d\d)~(?P<m2>\d\d)/(?P<d2>\d\d)\s*'
                     r'\((?P<nights>\d)박\d일\)\s*\|\s*\*\*(?P<price>₩[\d,]+)\*\*[^|]*\|\s*'
                     r'(?P<combo>.+?)\s*\|\s*(?P<direct>[^|]+?)\s*\|$', line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:60])
        date = datetime.date(2027, int(m.group('m1')), int(m.group('d1'))).isoformat()
        # 패턴은 (n박)만 주어지므로 출발 요일로 정한다
        pat = {2: None, 3: None, 4: '목~월'}[int(m.group('nights'))]
        dow = datetime.date.fromisoformat(date).weekday()
        if int(m.group('nights')) == 2:
            pat = '금~일' if dow == 4 else '토~월'
        elif int(m.group('nights')) == 3:
            pat = '목~일' if dow == 3 else '금~월'
        if pat is None or PAT_NIGHTS[pat] != int(m.group('nights')):
            raise SystemExit('%s 칸의 패턴을 정하지 못했습니다: %s' % (code, line[:60]))
        price = won(m.group('price'))
        combo = re.sub(r'\s*\[출처:[^\]]*\]', '', m.group('combo')).strip()
        parts = [p.strip() for p in combo.split(' · ')]
        airline = air_name(parts[0])
        if len(parts) < 3:
            raise SystemExit('%s 편성 문장을 읽지 못했습니다: %r' % (code, combo))
        leg = parts[1]
        if leg == '직항':
            via = False
            note = '직항'
        else:
            via = True
            lm = re.match(r'^(?P<n>\d)회 경유\s*(?P<hub>\(?[A-Z,]+\)?)?$', leg)
            if not lm:
                raise SystemExit('%s 경유 문장을 읽지 못했습니다: %r' % (code, leg))
            note = '경유 %s회' % lm.group('n')
            if lm.group('hub'):
                note += '(%s)' % lm.group('hub').strip('()')
        dm = re.match(r'^(?P<d>\d+h\s*\d*m?|\d+시간\s*\d*분?)\s*(?P<t>\(.*\))?$', parts[2])
        if not dm:
            raise SystemExit('%s 소요시간을 읽지 못했습니다: %r' % (code, parts[2]))
        note += (' · 총 ' if via else ' ') + dur(dm.group('d'))
        if dm.group('t'):
            note += ' ' + dm.group('t').replace('→', '-')
        if len(parts) > 3:
            note += ' · ' + parts[3]
        alt = None
        direct = re.sub(r'\s*\[출처:[^\]]*\]', '', m.group('direct')).strip()
        if direct == '직항 0건':
            note += ' · 직항편 없음'
        elif direct.startswith('가격 미표시'):
            note += ' · 직항 가격 미표시'
        elif direct.startswith('₩'):
            alt = won(direct)
            if alt <= price:
                alt = None
            else:
                note += ' · 직항 최저 %s원' % format(alt, ',')
        else:
            raise SystemExit('%s 직항 열을 읽지 못했습니다: %r' % (code, direct))
        cell(cells, (code, date, pat), code=code, date=date, pattern=pat, price=price,
             airline=airline, via=via, alt=alt, note=note)
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
    want = set()
    for code in ROUTES:
        for pat in PAT_NIGHTS:
            d = (datetime.date.fromisoformat(WEEK_START) +
                 datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
            want.add((code, d, pat))
    if set(cells) != want:
        raise SystemExit('칸 집합이 24노선 × 5패턴과 다릅니다: %s'
                         % sorted(set(cells) ^ want)[:6])
    ps = [c['price'] for c in cells.values()]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('최저·최고 %s (원문 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    for pat, want_avg in EXPECT_AVG.items():
        v = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if len(v) != 24:
            raise SystemExit('%s %d칸 (기대 24칸)' % (pat, len(v)))
        if abs(sum(v) / len(v) - want_avg) > 1:
            raise SystemExit('%s 평균 %.1f (원문 %d)' % (pat, sum(v) / len(v), want_avg))
    direct = sum(1 for c in cells.values() if c['via'] is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (원문 %d)' % (direct, EXPECT_DIRECT))
    unk = [k for k, c in cells.items() if c['via'] is None]
    if len(unk) != EXPECT_UNKNOWN_VIA:
        raise SystemExit('편성 미확인 칸 %d (기대 %d): %s' % (len(unk), EXPECT_UNKNOWN_VIA, unk))
    if sum(1 for c in cells.values() if c['alt']) != EXPECT_ALTS:
        raise SystemExit('직항 최저를 함께 적은 칸 %d (원문 %d)'
                         % (sum(1 for c in cells.values() if c['alt']), EXPECT_ALTS))
    for code, (lo, hi) in EXPECT_ROUTE.items():
        v = [c['price'] for k, c in cells.items() if k[0] == code]
        if len(v) != 5:
            raise SystemExit('%s %d칸 (기대 5칸)' % (code, len(v)))
        if (min(v), max(v)) != (lo, hi):
            raise SystemExit('%s 최저·최고 %s (원문 %s)' % (code, (min(v), max(v)), (lo, hi)))
    for k, c in cells.items():
        if c['alt'] is not None and c['alt'] <= c['price']:
            raise SystemExit('%s 직항 최저가가 최저가 이하입니다: %s <= %s'
                             % (k, c['alt'], c['price']))
        if c['price'] <= 0:
            raise SystemExit('%s 가격이 양의 정수가 아닙니다' % (k,))
        if not c['note']:
            raise SystemExit('%s note 비어 있음' % (k,))
        if '**' in c['note'] or '[' in c['note'] or '출처' in c['note']:
            raise SystemExit('%s note 에 마크업이 있습니다: %r' % (k, c['note']))
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
    unk = sum(1 for d in rows if d.get('via') is None)
    ties_lo = sum(1 for d in rows if d['price'] == lo['price'])
    ties_hi = sum(1 for d in rows if d['price'] == hi['price'])
    return (label + ' 최저는 ' + CITY[lo['code']] + ' ' + span(lo) + ' ' + lo['pattern'] + ' '
            + format(lo['price'], ',') + '원(' + (lo['airline'] or '항공사 미확인') + ' '
            + _viaword(lo) + (' · 같은 금액 %d칸' % ties_lo if ties_lo > 1 else '')
            + ')이고, 최고는 ' + CITY[hi['code']] + ' ' + span(hi) + ' ' + hi['pattern'] + ' '
            + format(hi['price'], ',') + '원(' + (hi['airline'] or '항공사 미확인') + ' '
            + _viaword(hi) + (' · 같은 금액 %d칸' % ties_hi if ties_hi > 1 else '')
            + ')입니다. 직항이 최저가인 칸 ' + str(direct) + ' · 경유 '
            + str(len(rows) - direct - unk)
            + (' · 편성 미확인 ' + str(unk) if unk else '') + '칸이고, 패턴 평균은 '
            + avg + ' 순입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 5월 5주(5/27~31) 120칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ④ 항공 기존 24개 노선 2027년 5월 5주차(5/27~31) '
        '5패턴 120칸 완결 — 최저 하노이 5/27~30 목~일 282,171원(직항), '
        '직항이 최저가인 칸 45, 총 8,120→8,240건'))
    args = ap.parse_args(argv)

    cells = check(parse_all())
    print('파싱 %d칸 — 최저 %s · 최고 %s · 직항이 최저인 칸 %d · 경유 %d · 편성 미확인 %d'
          % (len(cells), format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ','),
             sum(1 for c in cells.values() if c['via'] is False),
             sum(1 for c in cells.values() if c['via'] is True),
             sum(1 for c in cells.values() if c['via'] is None)))
    for k in sorted(cells)[:4]:
        print('  예:', k, cells[k])

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

    clash = [(c, d['date'], d['pattern']) for c in ROUTES for d in routes[c]['deals']
             if WEEK_START <= d['date'] <= WEEK_END]
    if clash:
        raise SystemExit('기존 24개 노선에 이 주 칸이 이미 있습니다: %s' % clash[:4])

    added = []
    for (code, date, pat), v in sorted(cells.items()):
        deal = collections.OrderedDict()
        deal['date'] = date
        deal['back'] = (datetime.date.fromisoformat(date) +
                        datetime.timedelta(days=PAT_NIGHTS[pat])).isoformat()
        deal['pattern'] = pat
        deal['price'] = v['price']
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
    if counts['byMonth'][MONTH] != EXPECT_BY_MONTH:
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                  EXPECT_BY_MONTH))
    if counts['daytrip'] != EXPECT_DAYTRIP:
        raise SystemExit('당일치기 %d건 (기대 %d건)' % (counts['daytrip'], EXPECT_DAYTRIP))
    if counts['holiday'] != 185:
        raise SystemExit('연휴 칸 %d건 (기대 185)' % counts['holiday'])

    rows = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if WEEK_START <= d['date'] <= WEEK_END]
    if len(rows) != EXPECT_CELLS:
        raise SystemExit('이 주 칸 %d칸 (기대 %d칸)' % (len(rows), EXPECT_CELLS))

    if not fl['notes'][MONTH].startswith('2027년 5월 1주차(4/29~5/3)'):
        raise SystemExit('2027-05 notes 의 첫 문장이 예상과 다릅니다: %r'
                         % fl['notes'][MONTH][:40])
    week_sent = ('2027년 5월 5주차(5/27~31) 24개 노선 5패턴 120칸도 전부 실측했습니다 — 이 주는 '
                 '앱의 주차 선택에서 5월 4주(5/27~6/2)로 표시됩니다. '
                 + week_note(rows, '이 주(5/27~31)')
                 + ' 이 주는 한국 공휴일이 없고 일본도 골든위크가 끝나 24개 노선 120칸이 '
                   '282,171~849,300원으로 5월 1주차(325,800~1,067,400원)보다 폭이 좁고, '
                   '패턴 평균은 3박(금~월)이 가장 싸고 4박(목~월)이 가장 비쌉니다.')
    fl['notes'][MONTH] = fl['notes'][MONTH] + ' ' + week_sent

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
        if len(cur) != len(old) + 5:
            raise SystemExit('%s 딜 %d건 (기존 %d + 5)' % (code, len(cur), len(old)))
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
    print('notes[2027-05] 새 문장:', week_sent[:400])

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
