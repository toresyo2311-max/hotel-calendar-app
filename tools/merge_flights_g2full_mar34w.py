#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 항공 특가에 **팀원 완결본 3건**을 한꺼번에 병합한다.

  1) 중국 G2 4개 노선(연길·장가계·구이린·황산) 2027년 2~6월 **420/420칸(100%)** 완주본
     — `data-sources/flights-china-new8/부산출발-중국4노선-연길장가계구이린황산-2_6월.md`
     기존 336칸(금~일·토~월·목~일·금~월)은 금액이 그대로여서 두고,
     마지막 미조회였던 **목~월(4박) 21주 84칸**(값 77 + 황산 판매편 0건 7)만 더한다.
     값 384칸 + 0건 36칸, 미조회 0칸.
  2) 기존 24개 노선 **2027년 3월 3주차(3/18~22) 120칸 완본** — 5번 보고
     `data-sources/flights-2027-03/부산출발-항공특가-2027년3월-3주차.md`
  3) 기존 24개 노선 **2027년 3월 4주차(3/25~29) 120칸 완본** — 5번 보고 (2026-11-18 추가 도착)
     `data-sources/flights-2027-03/부산출발-항공특가-2027년3월-4주차.md`
     2·3을 합치면 3월 1~4주차 480칸(100%)이 된다.

읽는 곳:
  · G2 부록 — `- 2027-02-04(목) · 목~월(4박) · PUS–YNJ · 904,900원 · Eastar Jet, Jeju Air · 경유(Seoul 7h 55m, 총11h 35m)`
    (0건 칸은 `- … · PUS–TXN · 판매편 없음(0건)`)
  · G2 표 — `## 2. 노선별 21주 × 5패턴 실측표` 의 노선별 표(주(목) × 5패턴)를 부록과 전수 대조
  · G2 요약 — `## 1. 결론 요약`(노선별 105칸·0건·최저/최고) · `### 3-4.`(목~월 값 77·0건 7)
  · 3월 3·4주차 — `### 부산–상하이 (PVG)` 절 머리 + `- 2027-03-19~03-21 · 금~일·2박 · PUS–PVG · 334,800원 · 춘추항공 · 직항 …`
    (4주차는 `- 2027-03-26 · 금~일·2박 · …` 처럼 출발일 하루만 적은 줄)
  · 3·4주차 요약 — `## 한눈에`(120조합 · 전체 최저/최고 · 패턴 평균 · 경유 칸 수) · `## 노선별 최저가 순위` 24줄

규칙:
  · 값은 원문 그대로. 항공사·경유지 이름만 앱 표기(한국어)로 옮긴다.
  · 원문이 말하는 칸 수·최저/최고·패턴 평균·경유 칸 수·순위표를 파싱 결과와 **전수 대조**한다.
  · 이미 있는 칸은 중복으로 넣지 않고, 기존 금액이 하나라도 달라지면 멈춘다(갱신 0건).
  · 호텔 538곳 · 아코르 · 다른 노선 · 기존 딜·`noSale`·패턴 정의는 **바이트 동일성**으로 보존 확인.
  · `counts`(total · byMonth · holiday · daytrip)와 2027년 2~6월 `notes`(커버리지 문구)를 다시 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_g2full_mar34w.py --dry-run
    python3 tools/merge_flights_g2full_mar34w.py --note "2026-11-18 KST …"
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources'))
MD_G2 = os.path.join(SRC, 'flights-china-new8',
                     '부산출발-중국4노선-연길장가계구이린황산-2_6월.md')
MD_MAR3 = os.path.join(SRC, 'flights-2027-03', '부산출발-항공특가-2027년3월-3주차.md')
MD_MAR4 = os.path.join(SRC, 'flights-2027-03', '부산출발-항공특가-2027년3월-4주차.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
PATTERNS = ('금~일', '토~월', '목~일', '금~월', '목~월')
G2_ROUTES = ('YNJ', 'DYG', 'KWL', 'TXN')
G2_CITY = {'YNJ': '연길/옌지', 'DYG': '장가계', 'KWL': '구이린', 'TXN': '황산'}
MAR_ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR',
              'NKG', 'SGN', 'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX',
              'DPS', 'KHH', 'RMQ', 'BJS')
MAR_CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'TPE': '타이베이', 'HKG': '홍콩',
            'MFM': '마카오', 'PVG': '상하이', 'BKK': '방콕', 'DAD': '다낭', 'CXR': '나트랑',
            'NKG': '난징', 'SGN': '호찌민', 'SIN': '싱가포르', 'GUM': '괌', 'NGO': '나고야',
            'OKA': '오키나와', 'HGH': '항저우', 'TAO': '칭다오', 'HAN': '하노이', 'CNX': '치앙마이',
            'DPS': '발리', 'KHH': '가오슝', 'RMQ': '타이중', 'BJS': '베이징'}

# 원문이 말하는 값 — 파싱이 조용히 빠뜨리거나 숫자를 밀지 않았는지 대조한다
EXPECT_G2 = {
    'cells': 420, 'values': 384, 'nosale': 36, 'gaps': 0,
    'per_route': 105, 'per_pat': 84,
    'minmax': {'YNJ': (455700, 932000), 'DYG': (686700, 904100),
               'KWL': (525900, 879900), 'TXN': (783500, 2588000)},
    'mins': {'YNJ': (455700, '2027-03-26', '금~일'),
             'DYG': (686700, '2027-03-04', '목~일'),
             'KWL': (525900, '2027-03-04', '목~월'),
             'TXN': (783500, '2027-04-08', '목~월')},
    'direct': {'YNJ': 1, 'DYG': 0, 'KWL': 0, 'TXN': 0},
    'frimon': {'values': 77, 'nosale': 7},
}
# 3월 3주차 — 원문 `## 한눈에`
EXPECT_MAR3 = {
    'cells': 120, 'start': '2027-03-18', 'end': '2027-03-22',
    'overall': (245600, 553000), 'via': 37,
    'avg': {'금~일': 396646, '토~월': 372962, '목~일': 394392,
            '금~월': 380479, '목~월': 372646},
    'low': (245600, '2027-03-20', '토~월'),          # 후쿠오카
    'high': (553000, '2027-03-18', '목~일'),         # 도쿄
}
# 3월 4주차 — 원문 `## 한눈에`
EXPECT_MAR4 = {
    'cells': 120, 'start': '2027-03-25', 'end': '2027-03-29',
    'overall': (278400, 701200), 'via': 31,
    'avg': {'금~일': 462850, '토~월': 474225, '목~일': 456408,
            '금~월': 473550, '목~월': 468962},
    'low': (278400, '2027-03-26', '금~월'),          # 상하이
    'high': (701200, '2027-03-26', '금~월'),         # 치앙마이
}
NEW_G2 = 84            # 셀 84칸 — 값 77 + 판매편 0건 7(딜 건수는 77)
NEW_MAR = 240
PREV_TOTAL = 5633
NEW_TOTAL = PREV_TOTAL + 77 + NEW_MAR           # 5,950
NEW_BY_MONTH = {'2027-02': 12, '2027-03': 13 + 240, '2027-04': 20,
                '2027-05': 16, '2027-06': 16}

# 원문 표기 → 앱 표기 (번역일 뿐, 값은 바꾸지 않는다)
AIRLINE_KO = [
    ('China Eastern Airlines', '중국동방항공'),
    ('Shanghai Airlines', '상하이항공'),
    ('China Southern Airlines', '중국남방항공'),
    ('Asiana Airlines', '아시아나항공'),
    ('Juneyao Airlines', '주니야오항공'),
    ('Shandong Airlines', '산둥항공'),
    ('Trinity Airways', '트리니티항공'),
    ('Spring Airlines', '춘추항공'),
    ('Korean Air', '대한항공'),
    ('Eastar Jet', '이스타항공'),
    ('Jeju Air', '제주항공'),
    ('Jin Air', '진에어'),
    ('Air China', '중국국제항공'),
    ('Air Busan', '에어부산'),
    ('HK Express', '홍콩익스프레스'),
    ('Cathay Pacific', '캐세이퍼시픽'),
    ('Xiamen Airlines', '샤먼항공'),
]
AIRPORT_KO = [('Jeju City', '제주'), ('Hong Kong', '홍콩'), ('Seoul', '서울'),
              ('Beijing', '베이징'), ('Shanghai', '상하이'), ('Jeju', '제주'),
              ('Nanjing', '난징'), ('Guangzhou', '광저우'), ('Fuzhou', '푸저우')]

LINE_G2 = re.compile(r'^- (\d{4}-\d{2}-\d{2})\([월화수목금토일]\) · ([월화수목금토일]~[월화수목금토일])'
                     r'\((\d)박\) · PUS–([A-Z]{3}) · (.+)$')
TAB_G2_HEAD = re.compile(r'^### (.+?) \(([A-Z]{3})\)$')
TAB_G2_ROW = re.compile(r'^\| (\d{2})/(\d{2}) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$')
TAB_G2_COLS = ('목~일', '금~일', '토~월', '금~월', '목~월')
SUM_G2_ROW = re.compile(r'^\| (.+?) \(([A-Z]{3})\) \| 105/105 \| (\d+)칸 \| \*\*([\d,]+)\*\* \| '
                        r'(\d{4}-\d{2}-\d{2})\([월화수목금토일]\) ([월화수목금토일]~[월화수목금토일]) \| '
                        r'([\d,]+) \| (.+?) \|$', re.M)

MAR_HEAD = re.compile(r'^### 부산–(.+) \(([A-Z]{3}(?:/[A-Z]{3})?)\)$')
MAR_CELL_RANGE = re.compile(r'^- (\d{4}-\d{2}-\d{2})~(\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일])·(\d)박 · '
                            r'PUS–([A-Z]{3}) · ([\d,]+)원 · ([^·]+?) · (.+)$')
MAR_CELL_ONE = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일])·(\d)박 · '
                          r'PUS–([A-Z]{3}) · ([\d,]+)원 · ([^·]+?) · (.+)$')
MAR_RANK = re.compile(r'^- ([\d,]+)원 · (.+?)\(([A-Z]{3})(?:/[A-Z]{3})?\) · (\d{4}-\d{2}-\d{2}) '
                      r'(?:[①②③④⑤] )?(\S+?)·(\d)박 · (.+)$', re.M)


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def nights_of(pattern):
    return (WD[pattern[-1]] - WD[pattern[0]]) % 7


# ---------------------------------------------------------------- 표기 변환
def timespan_g2(text):
    """'22h 45m' → '22시간 45분' (원문 값은 그대로)."""
    def one(m):
        h, mi = m.group(1), m.group(2)
        return '%s시간' % int(h) + (' %d분' % int(mi) if mi and int(mi) else '')
    text = re.sub(r'(\d{1,2})h\s*(\d{1,2})?m?\b', one, text)
    return re.sub(r'총(\d)', r'총 \1', text)


def city_words(text):
    for en, ko in AIRPORT_KO:
        text = re.sub(r'\b%s\b' % re.escape(en), ko, text)
    return text.replace('2 stops', '2회').replace('1 stop', '1회')


def airline_ko(raw):
    """'China Eastern Airlines Shanghai Airlines' → '중국동방항공+상하이항공'."""
    names = sorted(AIRLINE_KO, key=lambda x: -len(x[0]))
    out = []
    for chunk in re.split(r'\s*(?:,|/)\s*', (raw or '').strip()):
        if not chunk:
            continue
        # 콤마 없이 두 항공사가 붙은 표기('Airlines Shanghai Airlines')도 처리
        i = 0
        while i < len(chunk):
            for en, ko in names:
                if chunk.startswith(en, i):
                    if ko not in out:
                        out.append(ko)
                    i += len(en)
                    while i < len(chunk) and chunk[i] == ' ':
                        i += 1
                    break
            else:
                raise SystemExit('모르는 항공사 표기입니다(번역표에 추가 필요): %r' % raw)
    return '+'.join(out)


def norm_desc_g2(desc):
    """G2 원문 편구성 → {via, note}."""
    d = (desc or '').strip()
    m = re.fullmatch(r'경유\((.*)\)', d)
    if m:
        parts = [timespan_g2(city_words(p.strip())) for p in m.group(1).split(',')]
        parts = [p for p in parts if p and p != '총']
        return {'via': True, 'note': '경유' + ('(%s)' % ', '.join(parts) if parts else '')}
    m = re.fullmatch(r'직항\((.*)\)', d)
    if m:
        return {'via': False, 'note': '직항(%s)' % timespan_g2(city_words(m.group(1)))}
    if d.startswith('경유'):
        return {'via': True, 'note': timespan_g2(city_words(d))}
    if d.startswith('직항'):
        return {'via': False, 'note': timespan_g2(city_words(d))}
    raise SystemExit('경유/직항 표기가 아닙니다(원문 확인 필요): %r' % d)


def tidy_mar(desc):
    """'직항 1시간55분(22:10-23:05)' → '직항 1시간 55분(22:10-23:05)'."""
    d = re.sub(r'(\d+)시간(\d+)분', r'\1시간 \2분', desc)
    d = re.sub(r'총(\d)', r'총 \1', d)
    return d.strip()


# ---------------------------------------------------------------- 파싱: 중국 G2
def parse_g2_appendix(text):
    values, nosale = {}, {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('- 20'):
            continue
        m = LINE_G2.match(line)
        if not m:
            raise SystemExit('G2 부록 줄 형식이 예상과 다릅니다: %s' % line)
        date, pattern, nights, code, body = m.groups()
        if code not in G2_ROUTES:
            raise SystemExit('G2 에 없는 노선입니다: %s' % line)
        if int(nights) != nights_of(pattern):
            raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
        key = (code, date, pattern)
        if key in values or key in nosale:
            raise SystemExit('G2 부록에 같은 칸이 두 번 있습니다: %s' % (key,))
        if body.startswith('판매편 없음'):
            nosale[key] = {'code': code, 'date': date, 'back': back_date(date, pattern),
                           'pattern': pattern, 'note': '검색 결과 0건(판매편 없음)'}
            continue
        fields = [f.strip() for f in body.split(' · ')]
        pm = re.fullmatch(r'([\d,]+)원', fields[0])
        if not pm:
            raise SystemExit('G2 부록 금액을 읽지 못했습니다: %s' % line)
        deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern,
                'price': int(pm.group(1).replace(',', ''))}
        airline, info = fields[1], fields[2] if len(fields) > 2 else ''
        if airline.startswith('편구성 미확인'):
            deal['via'] = None
            deal['note'] = '편구성 미확인(결과 목록에 카드 미노출)'
        else:
            deal['airline'] = airline_ko(airline)
            desc = norm_desc_g2(' · '.join(fields[2:]) if len(fields) > 2 else info)
            deal['via'] = desc['via']
            deal['note'] = desc['note']
        values[key] = deal
    return values, nosale


def parse_g2_tables(text):
    """`## 2.` 노선별 표(주(목) × 5패턴) → 420칸."""
    out, code, seen = {}, None, 0
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('## ') and not line.startswith('## 2.'):
            code = None
            continue
        m = TAB_G2_HEAD.match(line)
        if m:
            city, c = m.groups()
            if c not in G2_ROUTES:
                raise SystemExit('G2 표에 예상 밖 노선: %s' % line)
            if city.strip() != G2_CITY[c]:
                raise SystemExit('G2 표 도시 이름이 다릅니다: %s (%s)' % (line, G2_CITY[c]))
            code = c
            continue
        if not code:
            continue
        m = TAB_G2_ROW.match(line)
        if not m:
            continue
        mm, dd = int(m.group(1)), int(m.group(2))
        thu = datetime.date(2027, mm, dd)
        if thu.isoweekday() != 4:
            raise SystemExit('G2 표 주(목) 날짜가 목요일이 아닙니다: %s' % line)
        for pat, cell in zip(TAB_G2_COLS, m.groups()[2:]):
            cell = cell.strip()
            start = thu + datetime.timedelta(days=(WD[pat[0]] - 4) % 7)
            key = (code, start.isoformat(), pat)
            if key in out:
                raise SystemExit('G2 표에 같은 칸이 두 번 있습니다: %s' % (key,))
            if cell == '0건':
                out[key] = 'NOSALE'
            elif re.fullmatch(r'[\d,]+( \*\*직항\*\*)?', cell):
                out[key] = int(cell.split()[0].replace(',', ''))
            else:
                raise SystemExit('G2 표 칸 값을 읽지 못했습니다: %s' % line)
            seen += 1
    return out, seen


def checks_g2(text, values, nosale, tables, seen):
    bad = []
    if seen != EXPECT_G2['cells'] or len(tables) != EXPECT_G2['cells']:
        bad.append('G2 표 %d칸/%d칸 (기대 420)' % (seen, len(tables)))
    if len(values) != EXPECT_G2['values'] or len(nosale) != EXPECT_G2['nosale']:
        bad.append('G2 값 %d칸 + 0건 %d칸 (기대 %d + %d)'
                   % (len(values), len(nosale), EXPECT_G2['values'], EXPECT_G2['nosale']))
    if len(values) + len(nosale) != EXPECT_G2['cells']:
        bad.append('G2 값+0건 %d칸 (기대 420)' % (len(values) + len(nosale)))
    mismatch = []
    for key, got in tables.items():
        if key in values:
            if values[key]['price'] != got:
                mismatch.append('%s 표 %s / 부록 %s' % (key, got, values[key]['price']))
        elif key in nosale:
            if got != 'NOSALE':
                mismatch.append('%s 표 %s / 부록 0건' % (key, got))
        else:
            mismatch.append('%s 부록에 없음' % (key,))
    if (set(values) | set(nosale)) != set(tables):
        mismatch.append('부록에만 있는 칸 %d개' % len((set(values) | set(nosale)) - set(tables)))
    if mismatch:
        bad.append('G2 표·부록 불일치 %d건: %s' % (len(mismatch), mismatch[:6]))
    for code in G2_ROUTES:
        vals = {k: v for k, v in values.items() if k[0] == code}
        nos = {k: v for k, v in nosale.items() if k[0] == code}
        if len(vals) + len(nos) != EXPECT_G2['per_route']:
            bad.append('G2 %s %d칸 (기대 105칸)' % (code, len(vals) + len(nos)))
        for pat in PATTERNS:
            n = sum(1 for k in vals if k[2] == pat) + sum(1 for k in nos if k[2] == pat)
            if n != EXPECT_G2['per_pat'] // 4:
                bad.append('G2 %s %s %d칸 (기대 %d칸)' % (code, pat, n, EXPECT_G2['per_pat'] // 4))
        ps = [d['price'] for d in vals.values()]
        lo, hi = min(ps), max(ps)
        if (lo, hi) != EXPECT_G2['minmax'][code]:
            bad.append('G2 %s 최저·최고 %s (기대 %s)' % (code, (lo, hi), EXPECT_G2['minmax'][code]))
        low = min((d['price'], d['date'], d['pattern']) for d in vals.values())
        if low != EXPECT_G2['mins'][code]:
            bad.append('G2 %s 최저 칸 %s (원문 %s)' % (code, low, EXPECT_G2['mins'][code]))
        direct = sum(1 for d in vals.values() if d.get('via') is False)
        if direct != EXPECT_G2['direct'][code]:
            bad.append('G2 %s 직항 최저 %d칸 (원문/기대 %d칸)'
                       % (code, direct, EXPECT_G2['direct'][code]))
    # 1절 요약표 — 노선별 105/105·0건·최저/최고
    rows = {}
    for m in SUM_G2_ROW.finditer(text):
        city, code, zero, low, date, pat, high, direct = m.groups()
        if code not in G2_ROUTES:
            continue
        if city.strip() != G2_CITY[code]:
            bad.append('G2 요약표 도시 이름 %r (%s)' % (city, G2_CITY[code]))
        rows[code] = (int(zero), int(low.replace(',', '')), date, pat,
                      int(high.replace(',', '')), direct)
    if set(rows) != set(G2_ROUTES):
        bad.append('G2 요약표 노선 %s' % sorted(set(rows) ^ set(G2_ROUTES)))
    for code, (zero, low, date, pat, high, _) in rows.items():
        vals = [d for k, d in values.items() if k[0] == code]
        got_zero = sum(1 for k in nosale if k[0] == code)
        got_low = min((d['price'], d['date'], d['pattern']) for d in vals)
        got_high = max(d['price'] for d in vals)
        if zero != got_zero or low != got_low[0] or date != got_low[1] or pat != got_low[2] \
                or high != got_high:
            bad.append('G2 %s 요약표(0건 %d·최저 %d %s %s·최고 %d) / 계산(0건 %d·최저 %s·최고 %d)'
                       % (code, zero, low, date, pat, high,
                          got_zero, got_low, got_high))
    # 커버리지 문장
    for phrase in ('420칸 중 420칸(100%) 조회 완료', '값이 잡힌 칸 384, 판매편 0건 36, 미조회 0칸',
                   '목~월 84/84'):
        if phrase not in text:
            bad.append('G2 원문 문장을 찾지 못했습니다: %s' % phrase)
    # 3-4절 — 목~월 84칸 값 77 · 0건 7
    frimon = {k for k in values if k[2] == '목~월'}
    frimon_ns = {k for k in nosale if k[2] == '목~월'}
    if (len(frimon), len(frimon_ns)) != (EXPECT_G2['frimon']['values'],
                                         EXPECT_G2['frimon']['nosale']):
        bad.append('G2 목~월 값 %d·0건 %d (원문 77·7)' % (len(frimon), len(frimon_ns)))
    if '84칸 중 **값이 잡힌 칸 77, 판매편 0건 7**' not in text:
        bad.append('G2 3-4절 값/0건 문장을 찾지 못했습니다')
    # 0건 36칸의 패턴 구성
    ns_by_pat = {p: sum(1 for k in nosale if k[2] == p) for p in PATTERNS}
    if ns_by_pat != {'금~일': 13, '토~월': 7, '목~일': 0, '금~월': 9, '목~월': 7}:
        bad.append('G2 0건 패턴 구성 %s (원문 금~일 13·토~월 7·금~월 9·목~월 7)' % ns_by_pat)
    return bad


# ---------------------------------------------------------------- 파싱: 3월 3·4주차
def parse_mar(text, expect):
    """24개 노선 120칸 + 순위표 24줄."""
    cells, heads, code = {}, {}, None
    lo, hi = expect['start'], expect['end']
    for raw in text.splitlines():
        line = raw.strip()
        m = MAR_HEAD.match(line)
        if m:
            city, c = m.groups()
            c = c.split('/')[0]
            if c not in MAR_ROUTES:
                raise SystemExit('3월 주차 파일에 예상 밖 노선: %s' % line)
            if not city.startswith(MAR_CITY[c]):
                raise SystemExit('도시 이름이 다릅니다: %s (%s)' % (line, MAR_CITY[c]))
            code = c
            heads[c] = city
            continue
        if line.startswith('## ') or line.startswith('### '):
            code = None
            continue
        if not code:
            continue
        m = MAR_CELL_RANGE.match(line)
        end = None
        if m:
            date, mend, pat, nights, rc, price, airline, desc = m.groups()
            end = '%s-%s' % (date[:4], mend)
        else:
            m = MAR_CELL_ONE.match(line)
            if not m:
                continue
            date, pat, nights, rc, price, airline, desc = m.groups()
        if rc != code:
            raise SystemExit('절과 노선 코드가 다릅니다: %s' % line)
        if int(nights) != nights_of(pat):
            raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
        if not (lo <= date <= hi):
            raise SystemExit('3월 주차 범위 밖 출발일입니다: %s' % line)
        back = back_date(date, pat)
        if end and end != back:
            raise SystemExit('귀국일 표기가 패턴과 다릅니다: %s' % line)
        deal = {'date': date, 'back': back, 'pattern': pat,
                'price': int(price.replace(',', '')), 'airline': airline.strip()}
        body, tail = desc, ''
        if ' (직항 최저' in desc or ' (직항편 없음)' in desc:
            body, tail = desc.rsplit(' (', 1)
            tail = tail[:-1]
        body = tidy_mar(body)
        if not (body.startswith('직항') or body.startswith('경유')):
            raise SystemExit('직항/경유 표기가 아닙니다: %s' % line)
        deal['via'] = body.startswith('경유')
        note = body
        if tail:
            note += ' · ' + tidy_mar(tail)
            mm = re.search(r'직항 최저 ([\d,]+)', tail)
            if mm:
                deal['alt'] = int(mm.group(1).replace(',', ''))
        deal['note'] = note
        if any(d['date'] == date and d['pattern'] == pat for d in cells.get(code, [])):
            raise SystemExit('%s %s %s 중복' % (code, date, pat))
        cells.setdefault(code, []).append(deal)
    rank = []
    for m in MAR_RANK.finditer(text):
        price, city, rc, date, pat, nights, desc = m.groups()
        rank.append((int(price.replace(',', '')), rc, date, pat, desc.strip()))
    return cells, heads, rank


def checks_mar(text, cells, heads, rank, expect, label):
    bad = []
    if set(cells) != set(MAR_ROUTES) or set(heads) != set(MAR_ROUTES):
        bad.append('%s 노선 집합이 다릅니다: %s' % (label, sorted(set(cells) ^ set(MAR_ROUTES))))
    total = sum(len(v) for v in cells.values())
    if total != expect['cells']:
        bad.append('%s 값 %d칸 (기대 %d칸)' % (label, total, expect['cells']))
    for code in MAR_ROUTES:
        deals = cells.get(code) or []
        if len(deals) != 5 or {d['pattern'] for d in deals} != set(PATTERNS):
            bad.append('%s %s %d칸·패턴 %s (기대 5칸 전부)'
                       % (label, code, len(deals), sorted(d['pattern'] for d in deals)))
    prices = [d['price'] for v in cells.values() for d in v]
    if (min(prices), max(prices)) != expect['overall']:
        bad.append('%s 전체 최저·최고 %s (원문 %s)'
                   % (label, (min(prices), max(prices)), expect['overall']))
    low = min((d['price'], d['date'], d['pattern']) for v in cells.values() for d in v)
    high = max((d['price'], d['date'], d['pattern']) for v in cells.values() for d in v)
    if low[0] != expect['low'][0]:
        bad.append('%s 최저 칸 %s (원문 %s)' % (label, low, expect['low']))
    if high[0] != expect['high'][0]:
        bad.append('%s 최고 칸 %s (원문 %s)' % (label, high, expect['high']))
    for p, want in expect['avg'].items():
        ps = [d['price'] for v in cells.values() for d in v if d['pattern'] == p]
        if int(round(sum(ps) / len(ps))) != want:
            bad.append('%s %s 평균 %d원 (원문 %d원)'
                       % (label, p, round(sum(ps) / len(ps)), want))
    via = sum(1 for v in cells.values() for d in v if d['via'])
    if via != expect['via']:
        bad.append('%s 경유 최저가 %d칸 (원문 %d칸)' % (label, via, expect['via']))
    if len(rank) != 24:
        bad.append('%s 순위표 %d줄 (기대 24줄)' % (label, len(rank)))
    if {r[1] for r in rank} != set(MAR_ROUTES):
        bad.append('%s 순위표 노선 집합이 다릅니다: %s'
                   % (label, sorted({r[1] for r in rank} ^ set(MAR_ROUTES))))
    for price, code, date, pat, desc in rank:
        lo = min(cells.get(code) or [], key=lambda d: d['price'])
        if (lo['price'], lo['date'], lo['pattern']) != (price, date, pat):
            bad.append('%s %s 순위표 %s (계산 %s)'
                       % (label, code, (price, date, pat),
                          (lo['price'], lo['date'], lo['pattern'])))
        if lo['airline'] not in desc:
            bad.append('%s %s 순위표 항공사 %r / 본문 %r' % (label, code, desc, lo['airline']))
        if ('경유' in desc) != lo['via']:
            bad.append('%s %s 순위표 직항/경유 표기가 본문과 다릅니다: %s' % (label, code, desc))

    # 원문 `한눈에` 에 적힌 고정 문구
    if '24개 노선 × 5패턴 = 120조합 전수 실측 완료' not in text:
        bad.append('%s 120조합 완료 문장을 찾지 못했습니다' % label)
    for phrase in ('빈칸이나 추정치는 없습니다',):
        if phrase not in text:
            bad.append('%s 원문 문장을 찾지 못했습니다: %s' % (label, phrase))
    return bad


# ---------------------------------------------------------------- 병합
def merge(master, values, nosale):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in {k[0] for k in values} | {k[0] for k in nosale}:
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)
    added, dup, conflicts = [], [], []
    for key in sorted(values):
        code, date, pattern = key
        deal = values[key]
        r = routes[code]
        have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
        if have is not None:
            if have.get('price') != deal['price']:
                conflicts.append((key, have.get('price'), deal['price']))
            dup.append(key)
            continue
        r['deals'].append(deal)
        added.append(key)
    if conflicts:
        raise SystemExit('기존 금액과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts[:5])
    for r in fl['routes']:
        r['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))
    known = {(n['code'], n['date'], n['pattern']) for n in fl['noSale']}
    deal_keys = {(r['code'], d['date'], d['pattern']) for r in fl['routes'] for d in r['deals']}
    new_ns = []
    for key in sorted(nosale):
        if key in known:
            continue
        if key in deal_keys:
            raise SystemExit('판매편 0건 칸이 실측 딜과 겹칩니다: %s' % (key,))
        fl['noSale'].append(nosale[key])
        new_ns.append(key)
    fl['noSale'].sort(key=lambda n: (n['code'], n['date']))
    all_deals = [d for r in fl['routes'] for d in r['deals']]
    by_month = {}
    for d in all_deals:
        by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    fl['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month[k] for k in sorted(by_month)},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals if d['pattern'].split('~')[0] == d['pattern'].split('~')[1]),
    }
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = len(all_deals)
    return added, dup, new_ns


def fmt(n):
    return format(n, ',')


def notes_update(fl):
    """월별 커버리지 문구 — 2027년 2~6월. 중국 8노선은 두 4노선군 모두 420/420칸 완결."""
    def cnt(codes, month, pattern=None, values=True):
        if values:
            return sum(1 for r in fl['routes'] if r['code'] in codes for d in r['deals']
                       if d['date'][:7] == month and (pattern is None or d['pattern'] == pattern))
        return sum(1 for n in fl['noSale'] if n['code'] in codes and n['date'][:7] == month
                   and (pattern is None or n['pattern'] == pattern))

    def pats(codes, month):
        return {p: cnt(codes, month, p) for p in PATTERNS}

    def bd(counter):
        return ' · '.join('%s %d' % (p, counter[p]) for p in PATTERNS if counter.get(p))

    def low_of(codes, month):
        best = None
        for r in fl['routes']:
            if r['code'] not in codes:
                continue
            for d in r['deals']:
                if d['date'][:7] != month:
                    continue
                key = (d['price'], d['date'], d['pattern'], r['city'], d.get('via'))
                if best is None or key < best:
                    best = key
        return best

    g1 = ('SHE', 'DLC', 'CAN', 'XMN')
    g2 = ('YNJ', 'DYG', 'KWL', 'TXN')
    for m in ('2027-02', '2027-03', '2027-04', '2027-05', '2027-06'):
        pass

    def low_text(codes, month):
        p = low_of(codes, month)
        if not p:
            return ''
        how = ' 직항' if p[4] is False else ''
        return '%s %d/%d %s %s원%s' % (p[3], int(p[1][5:7]), int(p[1][8:10]),
                                       p[2], fmt(p[0]), how)

    # 2027-02
    g1p, g2p = pats(g1, '2027-02'), pats(g2, '2027-02')
    fl['notes']['2027-02'] = (
        '기존 24개 노선은 2027년 2월 1~4주 × 5패턴 480칸을 전부 실측했습니다(1주차 설 연휴 120칸 포함, 빈칸 0칸). '
        '중국 8개 노선은 2027년 2~6월 21주 × 5패턴을 모두 조회해 선양·다롄·광저우·샤먼과 연길·장가계·구이린·황산이 '
        '모두 420/420칸(100%%) 완결입니다 — 이 달 선양·다롄·광저우·샤먼 %d칸(%s), 연길·장가계·구이린·황산 값 %d칸(%s) '
        '+ 황산 판매편 0건 %d칸. 연길·장가계·구이린·황산의 이 달 최저는 %s입니다. '
        '필리핀 4개 노선은 2027년 2~6월 420칸을 전부 실측했습니다 — 이 달 80칸이고 최저는 세부 2027-02-18 목~월 317,560원입니다. '
        '동남아 4개 노선도 420칸 전부 실측 — 이 달 80칸, 최저는 푸꾸옥 2027-02-27 토~월 411,161원입니다.'
        % (cnt(g1, '2027-02'), bd(g1p), cnt(g2, '2027-02'), bd(g2p),
           cnt(g2, '2027-02', values=False), low_text(g2, '2027-02')))
    # 2027-03
    g1p, g2p = pats(g1, '2027-03'), pats(g2, '2027-03')
    w3 = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in MAR_ROUTES
          for d in r['deals'] if '2027-03-18' <= d['date'] <= '2027-03-22']
    w4 = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in MAR_ROUTES
          for d in r['deals'] if '2027-03-25' <= d['date'] <= '2027-03-29']
    def pick(rows, key):
        hit = [d for d in rows if d['price'] == key[0] and d['date'] == key[1]
               and d['pattern'] == key[2]]
        return hit[0] if hit else min(rows, key=lambda d: d['price'])
    w3low = pick(w3, EXPECT_MAR3['low'])
    w4low = pick(w4, EXPECT_MAR4['low'])
    fl['notes']['2027-03'] = (
        '기존 24개 노선은 3월 1~4주차(3/4~8 · 3/11~15 · 3/18~22 · 3/25~29) 5패턴 480칸을 전부 실측해 2027년 3월을 완결했습니다 — '
        '1주차 최저 후쿠오카 3/4~8 목~월 243,200원, 2주차 후쿠오카 3/11~15 목~월 238,100원, '
        '3주차 %s %s %s %s원, 4주차 %s %s %s %s원입니다. '
        '중국 8개 노선은 2027년 2~6월 21주 × 5패턴을 모두 조회해 두 4노선군 모두 420/420칸(100%%) 완결입니다 — '
        '이 달 선양·다롄·광저우·샤먼 %d칸(%s), 연길·장가계·구이린·황산 값 %d칸(%s) + 황산 판매편 0건 %d칸이고, '
        '연길·장가계·구이린·황산의 이 달 최저는 %s입니다. '
        '필리핀 4개 노선은 이 달 80칸(최저 세부 2027-03-11 목~일 265,706원), 동남아 4개 노선은 이 달 80칸'
        '(최저 푸꾸옥 2027-03-04 목~월 375,254원)입니다.'
        % (MAR_CITY[w3low['code']], '%d/%d' % (int(w3low['date'][5:7]), int(w3low['date'][8:10])),
           w3low['pattern'], fmt(w3low['price']),
           MAR_CITY[w4low['code']], '%d/%d' % (int(w4low['date'][5:7]), int(w4low['date'][8:10])),
           w4low['pattern'], fmt(w4low['price']),
           cnt(g1, '2027-03'), bd(g1p), cnt(g2, '2027-03'), bd(g2p),
           cnt(g2, '2027-03', values=False), low_text(g2, '2027-03')))
    # 2027-04
    g1p, g2p = pats(g1, '2027-04'), pats(g2, '2027-04')
    fl['notes']['2027-04'] = (
        '중국 8개 노선의 2027년 4월입니다 — 선양·다롄·광저우·샤먼 %d칸(%s), 연길·장가계·구이린·황산 값 %d칸(%s) '
        '+ 황산 판매편 0건 %d칸입니다. 두 4노선군 모두 2027년 2~6월 21주 × 5패턴 420/420칸(100%%)을 완결했습니다 — '
        '선양·다롄·광저우·샤먼은 4/29~6/24 목~월(4박) 9주를 이번에 마저 채웠고, 연길·장가계·구이린·황산도 목~월(4박) 84칸을 '
        '채워 미조회 0칸입니다. 연길·장가계·구이린·황산의 이 달 최저는 %s입니다. '
        '필리핀 4개 노선은 이 달 96칸, 동남아 4개 노선은 이 달 96칸을 실측했습니다.'
        % (cnt(g1, '2027-04'), bd(g1p), cnt(g2, '2027-04'), bd(g2p),
           cnt(g2, '2027-04', values=False), low_text(g2, '2027-04')))
    # 2027-05
    g1p, g2p = pats(g1, '2027-05'), pats(g2, '2027-05')
    fl['notes']['2027-05'] = (
        '중국 8개 노선은 2027년 2~6월 21주 × 5패턴을 모두 조회해 두 4노선군 모두 420/420칸(100%%) 완결입니다 — '
        '이 달 선양·다롄·광저우·샤먼 %d칸(%s), 연길·장가계·구이린·황산 값 %d칸(%s) + 황산 판매편 0건 %d칸입니다. '
        '연길·장가계·구이린·황산의 이 달 최저는 %s입니다. '
        '필리핀 4개 노선은 이 달 84칸(최저 마닐라 5/7 금~월 411,918원), 동남아 4개 노선은 이 달 84칸'
        '(최저 푸꾸옥 5/20 목~월 292,051원 직항)입니다.'
        % (cnt(g1, '2027-05'), bd(g1p), cnt(g2, '2027-05'), bd(g2p),
           cnt(g2, '2027-05', values=False), low_text(g2, '2027-05')))
    # 2027-06
    g1p, g2p = pats(g1, '2027-06'), pats(g2, '2027-06')
    fl['notes']['2027-06'] = (
        '중국 8개 노선은 2027년 2~6월 21주 × 5패턴을 모두 조회해 두 4노선군 모두 420/420칸(100%%) 완결입니다 — '
        '이 달 선양·다롄·광저우·샤먼 %d칸(%s), 연길·장가계·구이린·황산 값 %d칸(%s) + 황산 판매편 0건 %d칸입니다. '
        '연길·장가계·구이린·황산의 이 달 최저는 %s입니다. '
        '필리핀 4개 노선 80칸(최저 클락 6/18 금~월 409,800원), 동남아 4개 노선 80칸(최저 푸꾸옥 6/3 목~월 292,051원)을 '
        '전부 실측했고, 기존 24개 노선의 6월 131칸(주말형 124 · 당일치기 7)도 함께 들어 있습니다.'
        % (cnt(g1, '2027-06'), bd(g1p), cnt(g2, '2027-06'), bd(g2p),
           cnt(g2, '2027-06', values=False), low_text(g2, '2027-06')))


def main(argv):
    ap = argparse.ArgumentParser(description='중국 G2 2~6월 완결 + 3월 3·4주차 → master_db.json 병합')
    ap.add_argument('--g2', default=MD_G2)
    ap.add_argument('--mar3', default=MD_MAR3)
    ap.add_argument('--mar4', default=MD_MAR4)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    t_g2 = open(args.g2, encoding='utf-8').read()
    t3 = open(args.mar3, encoding='utf-8').read()
    t4 = open(args.mar4, encoding='utf-8').read()

    values, nosale = parse_g2_appendix(t_g2)
    tables, seen = parse_g2_tables(t_g2)
    bad = checks_g2(t_g2, values, nosale, tables, seen)

    c3, h3, r3 = parse_mar(t3, EXPECT_MAR3)
    c4, h4, r4 = parse_mar(t4, EXPECT_MAR4)
    bad += checks_mar(t3, c3, h3, r3, EXPECT_MAR3, '3월 3주차')
    bad += checks_mar(t4, c4, h4, r4, EXPECT_MAR4, '3월 4주차')
    # 3주차·4주차가 같은 칸을 두 번 담지 않는지
    k3 = {(c, d['date'], d['pattern']) for c, ds in c3.items() for d in ds}
    k4 = {(c, d['date'], d['pattern']) for c, ds in c4.items() for d in ds}
    if k3 & k4:
        bad.append('3·4주차에 같은 칸이 있습니다: %s' % sorted(k3 & k4)[:5])
    if k3 | k4 and len(k3 | k4) != 240:
        bad.append('3·4주차 합계 %d칸 (기대 240칸)' % len(k3 | k4))

    print('  G2 값 %d칸 + 0건 %d칸 = %d칸 · 표 대조 %d칸'
          % (len(values), len(nosale), len(values) + len(nosale), seen))
    print('  G2 목~월 %d칸 (값 %d + 0건 %d)'
          % (sum(1 for k in values if k[2] == '목~월') + sum(1 for k in nosale if k[2] == '목~월'),
             sum(1 for k in values if k[2] == '목~월'),
             sum(1 for k in nosale if k[2] == '목~월')))
    for label, cells in (('3월 3주차', c3), ('3월 4주차', c4)):
        ps = [d['price'] for v in cells.values() for d in v]
        print('  %s %d칸 · %s ~ %s원'
              % (label, sum(len(v) for v in cells.values()), fmt(min(ps)), fmt(max(ps))))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    touched = set(G2_ROUTES) | set(MAR_ROUTES)
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in touched],
                              ensure_ascii=False, sort_keys=True)
    before_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False,
                                                                     sort_keys=True)
                     for r in fl['routes'] if r['code'] in touched for d in r['deals']}
    before_nosale = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_meta = {r['code']: json.dumps({k: v for k, v in r.items()
                                          if k not in ('deals',)}, ensure_ascii=False, sort_keys=True)
                   for r in fl['routes'] if r['code'] not in touched}
    before_notes = {k: v for k, v in fl['notes'].items()
                    if k not in ('2027-02', '2027-03', '2027-04', '2027-05', '2027-06')}
    before_patterns = json.dumps(fl['patterns'], ensure_ascii=False)

    # G2 는 목~월(4박)만 새로 넣는다 — 나머지 336칸은 중복(금액 동일)이어야 한다
    frimon_values = {k: v for k, v in values.items() if k[2] == '목~월'}
    frimon_nosale = {k: v for k, v in nosale.items() if k[2] == '목~월'}
    added_g2, dup_g2, new_ns_g2 = merge(master, frimon_values, frimon_nosale)
    if len(added_g2) != 77 or len(new_ns_g2) != 7:
        raise SystemExit('G2 목~월 신규 값 %d칸 + 0건 %d칸 (기대 77 + 7)'
                         % (len(added_g2), len(new_ns_g2)))
    # 같은 G2 파일의 나머지 336칸은 기존과 금액이 같아야 한다(중복으로만 확인)
    dup_check = {k: v for k, v in values.items() if k[2] != '목~월'}
    _, dup_other, _ = merge(master, dup_check, {})
    if len(dup_other) != len(dup_check):
        raise SystemExit('G2 기존 336칸 가운데 %d칸이 중복으로 확인되지 않았습니다'
                         % (len(dup_check) - len(dup_other)))

    flat3 = {(code, d['date'], d['pattern']): d for code, ds in c3.items() for d in ds}
    flat4 = {(code, d['date'], d['pattern']): d for code, ds in c4.items() for d in ds}
    added3, dup3, _ = merge(master, flat3, {})
    added4, dup4, _ = merge(master, flat4, {})
    if len(added3) != 120 or dup3:
        raise SystemExit('3월 3주차 신규 %d칸·중복 %d칸 (기대 120·0)' % (len(added3), len(dup3)))
    if len(added4) != 120 or dup4:
        raise SystemExit('3월 4주차 신규 %d칸·중복 %d칸 (기대 120·0)' % (len(added4), len(dup4)))

    notes_update(fl)

    # 보존·집계 검증
    if fl['counts']['total'] != NEW_TOTAL:
        raise SystemExit('총 %d건 (기대 %d건)' % (fl['counts']['total'], NEW_TOTAL))
    for m, n in NEW_BY_MONTH.items():
        if fl['counts']['byMonth'].get(m, 0) - before_by_month.get(m, 0) != n:
            raise SystemExit('%s 증가 %d칸 (기대 %d칸)'
                             % (m, fl['counts']['byMonth'].get(m, 0) - before_by_month.get(m, 0), n))
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] not in touched],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 항공 노선 데이터가 바뀌었습니다.')
    after_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False,
                                                                    sort_keys=True)
                    for r in fl['routes'] if r['code'] in touched for d in r['deals']}
    lost = [k for k in before_within if before_within[k] != after_within.get(k)]
    if lost:
        raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % lost[:5])
    keyf = lambda n: json.dumps(n, ensure_ascii=False, sort_keys=True)
    old_ns = sorted(json.loads(before_nosale), key=keyf)
    kept_ns = sorted([n for n in fl['noSale']
                      if (n['code'], n['date'], n['pattern'])
                      not in set(new_ns_g2)], key=keyf)
    if [keyf(n) for n in kept_ns] != [keyf(n) for n in old_ns]:
        raise SystemExit('기존 판매편 0건 기록이 바뀌었습니다.')
    after_meta = {r['code']: json.dumps({k: v for k, v in r.items() if k not in ('deals',)},
                                        ensure_ascii=False, sort_keys=True)
                  for r in fl['routes'] if r['code'] not in touched}
    if after_meta != before_meta:
        raise SystemExit('다른 노선의 메타가 바뀌었습니다.')
    if {k: v for k, v in fl['notes'].items()
            if k not in ('2027-02', '2027-03', '2027-04', '2027-05', '2027-06')} != before_notes:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다.')
    if json.dumps(fl['patterns'], ensure_ascii=False) != before_patterns:
        raise SystemExit('패턴 정의가 바뀌었습니다.')
    for r in fl['routes']:
        keys = [(d['date'], d['pattern']) for d in r['deals']]
        if len(keys) != len(set(keys)):
            raise SystemExit('%s (출발일·패턴) 중복' % r['code'])
        for d in r['deals']:
            if not isinstance(d.get('price'), int) or d['price'] <= 0:
                raise SystemExit('%s %s 가격 이상: %r' % (r['code'], d['date'], d.get('price')))
            if d['back'] != (datetime.date.fromisoformat(d['date']) +
                             timedelta_days(nights_of(d['pattern']))).isoformat():
                raise SystemExit('%s %s 귀국일이 박수와 다릅니다' % (r['code'], d['date']))

    print('G2 신규 %d칸 + 판매편 0건 %d칸(중복 336칸 금액 동일) · 3월 3주차 %d칸 · 4주차 %d칸'
          % (len(added_g2), len(new_ns_g2), len(added3), len(added4)))
    print('총 %d건 → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, fl['counts']['total'],
        fl['counts']['total'] - fl['counts']['daytrip'], fl['counts']['daytrip']))
    print('월별: %s' % fl['counts']['byMonth'])
    print('노선별: %s' % ', '.join('%s %d' % (r['code'], len(r['deals'])) for r in fl['routes']
                                  if r['code'] in set(G2_ROUTES)))
    print('noSale %d건 (신규 %d건)' % (len(fl['noSale']), len(new_ns_g2)))

    for m in ('2027-02', '2027-03', '2027-04', '2027-05', '2027-06'):
        if '%d' in fl['notes'][m] or '%s' in fl['notes'][m]:
            raise SystemExit('%s notes 에 서식 문자가 남았습니다: %s' % (m, fl['notes'][m]))
        if '**' in fl['notes'][m]:
            raise SystemExit('%s notes 에 마크다운 별표가 남았습니다: %s' % (m, fl['notes'][m]))
        print('  note %s: %s' % (m, fl['notes'][m][:90] + '…'))

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        return 0
    if args.note:
        master['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('wrote %s' % os.path.relpath(MASTER, ROOT))
    return 0


def timedelta_days(days):
    return datetime.timedelta(days=days)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
