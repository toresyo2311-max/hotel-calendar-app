#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""중국 신규 8노선 **2027년 2~6월 추가 완주본 2건**을 `data/master_db.json` 의 `flights` 에 병합한다.

  1) 선양·다롄·광저우·샤먼(G1) — `…-선양다롄광저우샤먼-2_6월-2박.md`
     누적 253/420칸. 앞선 병합으로 들어간 2박 168칸(금~일 84 + 토~월 84)은 그대로 두고,
     새로 찬 **목~일(3박) 84칸 + 선양 2/5~8 금~월(3박) 1칸 = 85칸**만 더한다. 목~월 84칸은 미조회.
  2) 연길·장가계·구이린·황산(G2) — `…-연길장가계구이린황산-2_6월-금일.md`
     누적 168/420칸(2박 100%). 금~일 84칸은 앞선 병합분과 금액이 같아야 하고(갱신 0건),
     새로 찬 **토~월(2박) 48칸**(연길 6 · 장가계 14 · 구이린 14 · 황산 14)과
     **황산 3/20 토~월 판매편 0건 1칸**(기존 2/6~3/13 6칸에 더해 7칸)을 더한다.
     연길 6/5 토~월 1칸은 이미 있으므로 중복이다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_china_26m_final8.py --dry-run
    python3 tools/merge_flights_china_26m_final8.py

읽는 곳(두 원문의 부록 '병합용 줄' + 실측표 + 1·5절 요약):
  · G1 값 — `- 2027-02-04 · 목~일 · PUS–XMN · 651,100원 · 이스타항공 · 직항 2h50`
  · G2 값 — `- 2027-03-27(토) · 토~월(2박) · PUS–TXN · 954,600원 · Air China · 경유(Beijing 22h 45m, 총 27h 30m)`
  · 0건 — `- 2027-03-20(토) · 토~월(2박) · PUS–TXN · 판매편 없음(0건)` → `flights.noSale`
  · 미조회 — G1 표의 `—`, G2 의 `—`·`미측정` → 넣지 않고 gaps 로만 센다.

규칙:
  · 값(가격·날짜·소요시간)은 원문 그대로. 항공사·경유지 이름만 앱 표기(한국어)로 옮긴다.
  · 원문 표와 부록 줄을 **(노선·출발일·패턴) 단위 420칸씩 전수** 대조한다 — 한 칸이라도 다르면 멈춘다.
  · 이미 있는 칸은 중복으로 넣지 않고, 기존 금액이 하나라도 달라지면 멈춘다.
  · 호텔 538곳 · 아코르 · 다른 24개 노선은 **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)와 2027년 2~6월 `notes`(커버리지 문구)를 다시 쓴다.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.join(os.path.dirname(os.path.dirname(ROOT)), 'data-sources', 'flights-china-new8')
MD_G1 = os.path.join(SRC, '부산출발-중국4노선-선양다롄광저우샤먼-2_6월-2박.md')
MD_G2 = os.path.join(SRC, '부산출발-중국4노선-연길장가계구이린황산-2_6월-금일.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
G1_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN')
G2_ROUTES = ('YNJ', 'DYG', 'KWL', 'TXN')
CITY = {'SHE': '선양', 'DLC': '다롄', 'CAN': '광저우', 'XMN': '샤먼',
        'YNJ': '연길/옌지', 'DYG': '장가계', 'KWL': '구이린', 'TXN': '황산'}

# 원문이 말하는 칸 수 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT_G1 = {
    'cells': 253,                        # 실측 완료 253/420 (2박 168 + 목~일 84 + 금~월 1)
    'gaps': 167,
    'nosale': 0,
    'per': {                             # 노선·패턴별 값이 있는 칸 수
        'SHE': {'목~일': 21, '금~일': 21, '토~월': 21, '금~월': 1, '목~월': 0},
        'DLC': {'목~일': 21, '금~일': 21, '토~월': 21, '금~월': 0, '목~월': 0},
        'CAN': {'목~일': 21, '금~일': 21, '토~월': 21, '금~월': 0, '목~월': 0},
        'XMN': {'목~일': 21, '금~일': 21, '토~월': 21, '금~월': 0, '목~월': 0},
    },
    # 5절 성수기 특징 — 금~일 평균·최고·최저(원)
    '금~일': {'SHE': (538167, 713600, 463500), 'DLC': (466567, 607100, 373300),
              'CAN': (545043, 775200, 501100), 'XMN': (555929, 758400, 464500)},
    'overall': (373100, 884000),         # 전체 최저(다롄 3/11~14 목~일) · 최고(샤먼 2/6~8 토~월)
}
EXPECT_G2 = {
    'values': {'YNJ': 42, 'DYG': 42, 'KWL': 42, 'TXN': 22},
    'nosale': {'YNJ': 0, 'DYG': 0, 'KWL': 0, 'TXN': 20},
    'gaps': 252,
    'cells': 420,
    'coverage': 168,                     # 4노선 × 21주 × 5패턴 420칸 중 168칸(40%)
    # 1절 요약표의 노선별 최저·최고(원)
    'minmax': {'YNJ': (455700, 927100), 'DYG': (691100, 904100),
               'KWL': (535200, 879900), 'TXN': (791900, 1035900)},
}
# 21주 — 목요일 기준(2027-02-04 ~ 2027-06-24), 금·토 출발은 +1·+2일
WEEKS = ('2027-02-04', '2027-02-11', '2027-02-18', '2027-02-25',
         '2027-03-04', '2027-03-11', '2027-03-18', '2027-03-25',
         '2027-04-01', '2027-04-08', '2027-04-15', '2027-04-22', '2027-04-29',
         '2027-05-06', '2027-05-13', '2027-05-20', '2027-05-27',
         '2027-06-03', '2027-06-10', '2027-06-17', '2027-06-24')
SAT_WEEKS = tuple((datetime.date.fromisoformat(w) + datetime.timedelta(days=2)).isoformat()
                  for w in WEEKS)
# 황산 토~월 판매편 0건 — 2/6~3/20 7주(3/20 은 이번 원문에서 '2회 확인 0건'), 3/27 부터는 값
TXN_SAT_NOSALE = SAT_WEEKS[:7]
# 이번에 새로 차는 칸 — G1 85칸(목~일 84 + 금~월 1) · G2 값 48칸 + 0건 1칸
NEW_G1, NEW_G2_VALUES, NEW_G2_NOSALE = 85, 48, 1
PREV_TOTAL = 2717
NEW_TOTAL = PREV_TOTAL + NEW_G1 + NEW_G2_VALUES

# 원문 표기 → 앱 표기 (번역일 뿐, 값은 바꾸지 않는다)
AIRLINE_KO = [
    ('China Eastern Airlines', '중국동방항공'),
    ('Shanghai Airlines', '상하이항공'),
    ('China Southern Airlines', '중국남방항공'),
    ('Asiana Airlines', '아시아나항공'),
    ('Juneyao Airlines', '주니야오항공'),
    ('Greater Bay Airlines', '그레이터베이항공'),
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
              ('Nanjing', '난징'), ('Guangzhou', '광저우')]

LINE_G1 = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · PUS–([A-Z]{3}) · (.+)$')
LINE_G2 = re.compile(r'^- (\d{4}-\d{2}-\d{2})\([월화수목금토일]\) · ([월화수목금토일]~[월화수목금토일])'
                     r'\((\d)박\) · PUS–([A-Z]{3}) · (.+)$')
SEC_G1 = re.compile(r'^#{2,3} (?:2-[12]|3-[123])\. ([월화수목금토일]~[월화수목금토일])')
HEAD_G1 = re.compile(r'^\| 노선 \| (.+) \|$')
ROW_G1 = re.compile(r'^\| ([^|]+?) \(([A-Z]{3})\) \| (.+?) \|$')
COL_G1 = re.compile(r'^(\d{1,2})/(\d{1,2})~(\d{1,2})/(\d{1,2})$')
TAB_G2_HEAD = re.compile(r'^### .*\(([A-Z]{3})\)$')
TAB_G2_ROW = re.compile(r'^\| (\d{2})/(\d{2}) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$')
TAB_G2_COLS = {'목~일': 0, '금~일': 1, '토~월': 2, '금~월': 3, '목~월': 4}


# ---------------------------------------------------------------- 표기 변환
def timespan_g1(text):
    """'상하이 2h35, 총7h00' → '상하이 2시간 35분, 총 7시간' (값은 그대로)."""
    def one(m):
        h, mi = int(m.group(1)), m.group(2)
        out = '%d시간' % h
        if mi and int(mi):
            out += ' %d분' % int(mi)
        return out
    text = re.sub(r'(\d{1,2})h\s*(\d{1,2})?', one, text)
    return re.sub(r'총\s*(?=\d)', '총 ', text).replace('  ', ' ').strip()


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
    for chunk in re.split(r'\s*(?:,|\+|/)\s*', (raw or '').strip()):
        if not chunk:
            continue
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


def norm_desc_g1(desc):
    """G1 원문 편구성 → {via, note}. '경유(상하이 2h35, 총7h00)' · '직항 2h50' · '경유 서울 9h45, 총 12h40(심야)'."""
    d = (desc or '').strip()
    if d.startswith('경유'):
        body = timespan_g1(d[2:].strip())
        return {'via': True,
                'note': '경유' + (body if body.startswith('(') else ' ' + body if body else '')}
    if d.startswith('직항'):
        return {'via': False, 'note': timespan_g1(d)}
    raise SystemExit('경유/직항 표기가 아닙니다(원문 확인 필요): %r' % d)


def norm_desc_g2(desc):
    """G2 원문 편구성 → {via, note}."""
    d = (desc or '').strip()
    m = re.fullmatch(r'경유\((.*)\)', d)
    if m:
        parts = [timespan_g2(city_words(p.strip())) for p in m.group(1).split(',')]
        parts = [p for p in parts if p and p != '총']
        return {'via': True, 'note': '경유' + ('(%s)' % ', '.join(parts) if parts else '')}
    if d.startswith('경유'):
        return {'via': True, 'note': '경유'}
    if d.startswith('직항'):
        return {'via': False, 'note': timespan_g2(d)}
    return {'via': None, 'note': d or '직항/경유 미확인'}


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    nights = (WD[b] - WD[a]) % 7 or 7
    return (start + datetime.timedelta(days=nights)).isoformat()


# ---------------------------------------------------------------- 파싱
def parse_g1_appendix(text):
    values, gaps = {}, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('- 20'):
            continue
        m = LINE_G1.match(line)
        if not m:
            raise SystemExit('G1 부록 줄 형식이 예상과 다릅니다: %s' % line)
        date, pattern, code, body = m.groups()
        if body.startswith('미측정'):
            gaps.append((code, date, pattern))
            continue
        fields = [f.strip() for f in body.split(' · ')]
        pm = re.fullmatch(r'([\d,]+)원', fields[0])
        if not pm:
            raise SystemExit('G1 부록 금액을 읽지 못했습니다: %s' % line)
        key = (code, date, pattern)
        if key in values:
            raise SystemExit('G1 부록에 같은 칸이 두 번 있습니다: %s' % (key,))
        deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern,
                'price': int(pm.group(1).replace(',', ''))}
        if len(fields) > 1 and fields[1]:
            deal['airline'] = fields[1]
        if len(fields) > 2:
            info = norm_desc_g1(' · '.join(fields[2:]))
            deal['via'] = info['via']
            deal['note'] = info['note']
        values[key] = deal
    return values, gaps


def parse_g1_tables(text):
    """2-1(금~일)·2-2(토~월)·3-1(목~일)·3-2(금~월)·3-3(목~월) 표 → 420칸."""
    out, section, heads, seen = {}, None, None, 0
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#'):
            m = SEC_G1.match(line)
            section, heads = (m.group(1) if m else None), None
            continue
        if section is None:
            continue
        m = HEAD_G1.match(line)
        if m:
            heads = [c.strip() for c in m.group(1).split('|')]
            for h in heads:
                if not COL_G1.match(h):
                    raise SystemExit('G1 표 머리가 날짜 범위가 아닙니다: %r' % h)
            continue
        m = ROW_G1.match(line)
        if not m:
            continue
        if heads is None:
            raise SystemExit('G1 표 머리 없이 노선 줄이 나왔습니다: %s' % line)
        city, code, cells = m.groups()
        if code not in G1_ROUTES:
            raise SystemExit('G1 에 없는 노선입니다: %s' % line)
        if city.strip() != CITY[code]:
            raise SystemExit('노선 이름이 다릅니다: %s / %s' % (city, code))
        vals = [c.strip() for c in cells.split('|')]
        if len(vals) != len(heads):
            raise SystemExit('표 열 수가 머리와 다릅니다: %s' % line)
        for h, v in zip(heads, vals):
            sm, sd, em, ed = COL_G1.match(h).groups()
            start = datetime.date(2027, int(sm), int(sd))
            end = datetime.date(2027, int(em), int(ed))
            pat = '%s~%s' % ('일월화수목금토'[start.isoweekday() % 7],
                             '일월화수목금토'[end.isoweekday() % 7])
            if pat != section:
                raise SystemExit('%s %s 칸이 절 제목(%s)과 다릅니다: %s'
                                 % (code, start.isoformat(), section, line))
            key = (code, start.isoformat(), pat)
            if v in ('—', '-', ''):
                out[key] = '—'
            elif v == '0건':
                out[key] = 'NOSALE'
            elif re.fullmatch(r'[\d,]+', v):
                out[key] = int(v.replace(',', ''))
            else:
                raise SystemExit('표 칸 값을 읽지 못했습니다: %s' % line)
            seen += 1
    return out, seen


def parse_g2_appendix(text):
    values, nosale, gaps = {}, {}, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('- 20'):
            continue
        m = LINE_G2.match(line)
        if not m:
            raise SystemExit('G2 부록 줄 형식이 예상과 다릅니다: %s' % line)
        date, pattern, nights, code, body = m.groups()
        n = (WD[pattern[-1]] - WD[pattern[0]]) % 7 or 7
        if int(nights) != n:
            raise SystemExit('%s %s 박수 표기(%s박)가 패턴(%s)과 다릅니다' % (code, date, nights, pattern))
        if body.startswith('미측정'):
            gaps.append((code, date, pattern))
            continue
        key = (code, date, pattern)
        if body == '판매편 없음(0건)':
            nosale[key] = {'code': code, 'date': date, 'back': back_date(date, pattern),
                           'pattern': pattern, 'note': '검색 결과 0건(판매편 없음)'}
            continue
        if key in values:
            raise SystemExit('G2 부록에 같은 칸이 두 번 있습니다: %s' % (key,))
        fields = [f.strip() for f in body.split(' · ')]
        pm = re.fullmatch(r'([\d,]+)원', fields[0])
        if not pm:
            raise SystemExit('G2 부록 금액을 읽지 못했습니다: %s' % line)
        deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern,
                'price': int(pm.group(1).replace(',', ''))}
        airline = airline_ko(fields[1]) if len(fields) > 1 else ''
        if airline:
            deal['airline'] = airline
        info = norm_desc_g2(' · '.join(fields[2:])) if len(fields) > 2 else norm_desc_g2('')
        for k in ('via', 'note'):
            if info.get(k) is not None:
                deal[k] = info[k]
        values[key] = deal
    return values, nosale, gaps


def parse_g2_tables(text):
    out, code, seen = {}, None, 0
    for raw in text.splitlines():
        line = raw.strip()
        m = TAB_G2_HEAD.match(line)
        if m:
            code = m.group(1)
            if code not in G2_ROUTES:
                raise SystemExit('G2 에 없는 노선입니다: %s' % line)
            continue
        if code is None:
            continue
        m = TAB_G2_ROW.match(line)
        if not m:
            continue
        mm, dd, *cells = m.groups()
        if len(cells) != 5:
            raise SystemExit('G2 표 열이 5개가 아닙니다: %s' % line)
        thu = datetime.date(2027, int(mm), int(dd))
        if thu.isoweekday() != 4:
            raise SystemExit('G2 표의 주 구분이 목요일이 아닙니다: %s' % line)
        for label, idx in TAB_G2_COLS.items():
            cell = cells[idx].strip()
            date = (thu + datetime.timedelta(days=(WD[label[0]] - 4) % 7)).isoformat()
            if cell == '—':
                out[(code, date, label)] = '—'
            elif cell == '0건':
                out[(code, date, label)] = 'NOSALE'
            elif re.fullmatch(r'[\d,]+', cell):
                out[(code, date, label)] = int(cell.replace(',', ''))
            elif re.fullmatch(r'[\d,]+\s*\*\*직항\*\*', cell):
                out[(code, date, label)] = int(cell.split()[0].replace(',', ''))
            else:
                raise SystemExit('G2 표 칸 값을 읽지 못했습니다: %s' % line)
            seen += 1
    return out, seen


def num(pattern, text, name):
    m = re.search(pattern, text)
    if not m:
        raise SystemExit('요약 문장을 찾지 못했습니다: %s' % name)
    return int(m.group(1).replace(',', ''))


def summary_g1(text, values):
    bad = []
    grid = num(r'\| 전체 격자 \| \*\*([\d,]+)칸\*\*', text, '전체 격자')
    done = num(r'\| 실측 완료 \| \*\*([\d,]+)칸\*\*', text, '실측 완료')
    zero = num(r'\| 판매편 없음\(0건\) \| \*\*([\d,]+)칸\*\*', text, '판매편 없음')
    rest = num(r'\| 미조회 \| \*\*([\d,]+)칸\*\*', text, '미조회')
    if (grid, done, zero, rest, len(values)) != (420, 253, 0, 167, 253):
        bad.append('G1 요약 칸 수(격자 %d·실측 %d·0건 %d·미조회 %d·파싱 %d)'
                   % (grid, done, zero, rest, len(values)))
    lo = num(r'- 전체 최저 \*\*([\d,]+)원\*\*', text, '전체 최저')
    hi = num(r'- 전체 최고 \*\*([\d,]+)원\*\*', text, '전체 최고')
    prices = [d['price'] for d in values.values()]
    if (min(prices), max(prices)) != (lo, hi) or (lo, hi) != EXPECT_G1['overall']:
        bad.append('G1 전체 최저·최고 %s (요약 %s / 기대 %s)'
                   % ((min(prices), max(prices)), (lo, hi), EXPECT_G1['overall']))
    for code in G1_ROUTES:
        m = re.search(r'- \*\*%s 금~일\*\* 평균 ([\d,]+)원 · 최고 ([\d,]+)원[^·]*· 최저 ([\d,]+)원'
                      % CITY[code], text)
        if not m:
            raise SystemExit('G1 5절 금~일 요약을 찾지 못했습니다: %s' % CITY[code])
        avg, top, bottom = (int(x.replace(',', '')) for x in m.groups())
        ps = [d['price'] for (c, _, p), d in values.items() if c == code and p == '금~일']
        calc = round(sum(ps) / len(ps))
        if (calc, max(ps), min(ps)) != (avg, top, bottom):
            bad.append('G1 %s 금~일 평균·최고·최저 계산 %s (요약 %s)'
                       % (CITY[code], (calc, max(ps), min(ps)), (avg, top, bottom)))
        if (avg, top, bottom) != EXPECT_G1['금~일'][code]:
            bad.append('G1 %s 금~일 요약 %s (기대 %s)'
                       % (CITY[code], (avg, top, bottom), EXPECT_G1['금~일'][code]))
    # 목~일 직항 2칸 — 브리프가 지목한 값
    for key, price in ((('XMN', '2027-02-04', '목~일'), 651100),
                       (('CAN', '2027-02-11', '목~일'), 594700)):
        d = values.get(key)
        if not d or d['price'] != price or d.get('via') is not False:
            bad.append('G1 직항 칸이 다릅니다: %s %s' % (key, d))
    return bad


def summary_g2(text, values, nosale, gaps):
    bad = []
    cov = num(r'4노선 × 21주 × 5패턴 = \*\*420칸 중 ([\d,]+)칸', text, 'G2 커버리지')
    filled = num(r'값이 잡힌 칸 ([\d,]+)', text, 'G2 값')
    zero = num(r'판매편 0건 ([\d,]+)', text, 'G2 0건')
    rest = num(r'미조회 ([\d,]+)칸', text, 'G2 미조회')
    if (cov, filled, zero, rest) != (EXPECT_G2['coverage'], len(values), len(nosale), len(gaps)):
        bad.append('G2 요약 칸 수(조회 %d·값 %d·0건 %d·미조회 %d)와 파싱(%d/%d/%d)이 다릅니다'
                   % (cov, filled, zero, rest, len(values), len(nosale), len(gaps)))
    for code in G2_ROUTES:
        m = re.search(r'\| %s \([A-Z]{3}\) \| (\d+)/105 \| (\d+)칸 \| \*\*([\d,]+)\*\*.*?\| ([\d,]+) \|'
                      % re.escape(CITY[code].replace('/', '/')) , text)
        if not m:
            raise SystemExit('G2 1절 요약표를 찾지 못했습니다: %s' % code)
        ps = [d['price'] for (c, _, _), d in values.items() if c == code]
        got = (min(ps), max(ps))
        if got != EXPECT_G2['minmax'][code]:
            bad.append('G2 %s 최저·최고 %s (요약표 기대 %s)' % (code, got, EXPECT_G2['minmax'][code]))
        if int(m.group(2)) != len(nosale) and code == 'TXN' and int(m.group(2)) != 20:
            bad.append('G2 황산 0건 %s칸 (기대 20칸)' % m.group(2))
    got_sat = {d for (c, d, p) in nosale if c == 'TXN' and p == '토~월'}
    if got_sat != set(TXN_SAT_NOSALE):
        bad.append('G2 황산 토~월 0건 날짜가 2/6~3/20 7주와 다릅니다: %s' % sorted(got_sat))
    if values.get(('YNJ', '2027-02-13', '토~월'), {}).get('via') is not False:
        bad.append('G2 연길 2/13 토~월이 직항이 아닙니다')
    if values.get(('TXN', '2027-06-05', '토~월'), {}).get('price') != 791900:
        bad.append('G2 황산 6/5 토~월 791,900원이 아닙니다')
    return bad


# ---------------------------------------------------------------- 병합
def merge(master, values, nosale):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in set(G1_ROUTES) | set(G2_ROUTES):
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)

    added, dup, conflicts = [], [], []
    for (code, date, pattern), deal in sorted(values.items()):
        r = routes[code]
        have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
        if have is not None:
            if have.get('price') != deal['price']:
                conflicts.append((code, date, pattern, have.get('price'), deal['price']))
            dup.append((code, date, pattern))
            continue
        r['deals'].append(deal)
        added.append((code, date, pattern, deal['price']))
    if conflicts:
        raise SystemExit('기존 금액과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts)

    for r in fl['routes']:
        r['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))

    known = {(n['code'], n['date'], n['pattern']) for n in fl['noSale']}
    deal_keys = {(r['code'], d['date'], d['pattern']) for r in fl['routes'] for d in r['deals']}
    new_nosale = []
    for key, entry in sorted(nosale.items()):
        if key in known:
            continue
        if key in deal_keys:
            raise SystemExit('판매편 0건 칸이 실측 딜과 겹칩니다: %s' % (key,))
        fl['noSale'].append(entry)
        new_nosale.append(key)
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
    return added, dup, new_nosale


def notes_update(fl):
    """화면 커버리지 문구(월별 notes)를 이번 조사 범위에 맞춘다."""
    fl['notes']['2027-02'] = (
        '기존 24개 노선은 2027년 2월 1~4주 × 5패턴 480칸을 전부 실측했습니다(1주차 설 연휴 120칸 포함, 빈칸 0칸). '
        '중국 8개 노선은 2박(금~일·토~월) 4주씩 64칸을 실측했고, 선양·다롄·광저우·샤먼의 목~일(3박) 4주 16칸과 '
        '선양 2/5~8 금~월(3박) 1칸을 더했습니다(황산은 2/6~2/27 토~월 판매편이 없어 0건). '
        '중국 8개 노선의 나머지 3·4박(목~일·금~월·목~월)은 미조회(—)입니다.')
    fl['notes']['2027-03'] = (
        '중국 8개 노선의 2027년 3월 2박을 실측했습니다 — 선양·다롄·광저우·샤먼은 금~일·토~월·목~일 4주씩, '
        '연길·장가계·구이린·황산은 금~일·토~월 4주씩입니다(황산 금~일·토~월은 3/6~3/20 판매편이 없어 0건). '
        '선양·다롄·광저우·샤먼의 금~월·목~월과 연길·장가계·구이린·황산의 3·4박, 다른 노선은 미조회(—)입니다.')
    fl['notes']['2027-04'] = (
        '선양·다롄·광저우·샤먼은 금~일 5주·토~월 4주·목~일 5주(4/29 포함)를, 연길·장가계·구이린·황산은 '
        '금~일·토~월 4주씩을 실측했습니다(황산 금~일은 4/2~4/30 판매편이 없어 0건). '
        '나머지 노선·패턴은 미조회(—)입니다.')
    fl['notes']['2027-05'] = (
        '중국 8개 노선의 2027년 5월 2박과 선양·다롄·광저우·샤먼의 목~일(3박)을 실측했습니다 — '
        '금~일 4주(5/28 포함)·토~월 5주·목~일 4주이고, 연길·장가계·구이린·황산은 금~일 5주·토~월 5주입니다'
        '(황산 금~일은 5/7~5/28 판매편이 없어 0건). 3·4박과 다른 노선은 미조회(—)입니다.')
    fl['notes']['2027-06'] = (
        '중국 8개 노선의 2027년 6월 2박을 실측했습니다 — 선양·다롄·광저우·샤먼은 금~일·토~월·목~일 4주씩(48칸), '
        '연길·장가계·구이린·황산은 금~일·토~월 4주씩입니다(황산 금~일은 6월 네 주 모두 판매편이 없어 0건). '
        '선양·다롄·광저우·샤먼의 금~월·목~월과 연길·장가계·구이린·황산의 3·4박, 다른 노선은 미조회(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='중국 8노선 2027년 2~6월 완주본 2건 → master_db.json flights 병합')
    ap.add_argument('--g1', default=MD_G1)
    ap.add_argument('--g2', default=MD_G2)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    t1 = open(args.g1, encoding='utf-8').read()
    t2 = open(args.g2, encoding='utf-8').read()
    v1, gaps1 = parse_g1_appendix(t1)
    tab1, seen1 = parse_g1_tables(t1)
    v2, ns2, gaps2 = parse_g2_appendix(t2)
    tab2, seen2 = parse_g2_tables(t2)

    bad = []
    # 1) G1 원문 칸 수와 파싱 결과
    per1 = {c: {p: 0 for p in ('목~일', '금~일', '토~월', '금~월', '목~월')} for c in G1_ROUTES}
    for code, _, pat in v1:
        if code not in per1 or pat not in per1[code]:
            raise SystemExit('G1 예상 밖 (노선·패턴) 칸입니다: %s %s' % (code, pat))
        per1[code][pat] += 1
    if len(v1) != EXPECT_G1['cells']:
        bad.append('G1 값 %d칸 (기대 %d칸)' % (len(v1), EXPECT_G1['cells']))
    # G1 부록에는 미측정 줄을 적지 않았다 — 표의 `—` 로 센다
    gaps1 = [k for k, v in tab1.items() if v == '—']
    if len(gaps1) != EXPECT_G1['gaps']:
        bad.append('G1 미조회 칸 %d개 (기대 %d개)' % (len(gaps1), EXPECT_G1['gaps']))
    if len(v1) + len(gaps1) != 420:
        bad.append('G1 값+미조회 %d칸 (기대 420칸)' % (len(v1) + len(gaps1)))
    for code in G1_ROUTES:
        if per1[code] != EXPECT_G1['per'][code]:
            bad.append('G1 %s 노선·패턴별 칸 수 %s (기대 %s)'
                       % (code, per1[code], EXPECT_G1['per'][code]))
    # 2) G1 부록 ↔ 표 전수 대조 (420칸)
    if seen1 != 420 or len(tab1) != 420:
        bad.append('G1 표 칸 수 %d/%d (기대 420)' % (seen1, len(tab1)))
    mismatch = []
    for key, got in tab1.items():
        if key in v1:
            if got != v1[key]['price']:
                mismatch.append('G1 %s 부록 %s / 표 %s' % (key, v1[key]['price'], got))
        elif got != '—':
            mismatch.append('G1 %s 부록에 없는데 표는 %s' % (key, got))
    if mismatch:
        bad.append('G1 부록·표 불일치 %d건: %s' % (len(mismatch), mismatch[:6]))
    bad.extend(summary_g1(t1, v1))

    # 3) G2 원문 칸 수와 파싱 결과
    per2 = {c: {'values': 0, 'nosale': 0} for c in G2_ROUTES}
    for code, _, _ in v2:
        per2[code]['values'] += 1
    for code, _, _ in ns2:
        per2[code]['nosale'] += 1
    for code in G2_ROUTES:
        if per2[code] != {'values': EXPECT_G2['values'][code], 'nosale': EXPECT_G2['nosale'][code]}:
            bad.append('G2 %s 값 %d/0건 %d (기대 %d/%d)'
                       % (code, per2[code]['values'], per2[code]['nosale'],
                          EXPECT_G2['values'][code], EXPECT_G2['nosale'][code]))
    if len(v2) + len(ns2) + len(gaps2) != EXPECT_G2['cells']:
        bad.append('G2 값+0건+미측정 %d칸 (기대 %d칸)'
                   % (len(v2) + len(ns2) + len(gaps2), EXPECT_G2['cells']))
    if len(v2) + len(ns2) != EXPECT_G2['coverage']:
        bad.append('G2 조회 칸 %d칸 (기대 %d칸)' % (len(v2) + len(ns2), EXPECT_G2['coverage']))
    if seen2 != 420 or len(tab2) != 420:
        bad.append('G2 표 칸 수 %d/%d (기대 420)' % (seen2, len(tab2)))
    for code in G2_ROUTES:
        if {p for (c, _, p) in list(v2) + list(ns2) + gaps2 if c == code} - set(TAB_G2_COLS):
            bad.append('G2 %s 에 5패턴 밖 칸이 있습니다' % code)
    mismatch = []
    for key, got in tab2.items():
        if key in v2:
            if got != v2[key]['price']:
                mismatch.append('G2 %s 부록 %s / 표 %s' % (key, v2[key]['price'], got))
        elif key in ns2:
            if got != 'NOSALE':
                mismatch.append('G2 %s 0건인데 표는 %s' % (key, got))
        elif got != '—':
            mismatch.append('G2 %s 부록 미측정인데 표는 %s' % (key, got))
    for key in gaps2:
        if tab2.get(key) != '—':
            bad.append('G2 부록 미측정 칸이 표에서는 값이 있습니다: %s' % (key,))
    if mismatch:
        bad.append('G2 부록·표 불일치 %d건: %s' % (len(mismatch), mismatch[:6]))
    bad.extend(summary_g2(t2, v2, ns2, gaps2))

    print('  G1 값 %d칸(목~일 %d·금~일 %d·토~월 %d·금~월 %d) · 미조회 %d칸 · 표 대조 %d칸'
          % (len(v1), sum(1 for k in v1 if k[2] == '목~일'),
             sum(1 for k in v1 if k[2] == '금~일'),
             sum(1 for k in v1 if k[2] == '토~월'),
             sum(1 for k in v1 if k[2] == '금~월'), len(gaps1), len(tab1)))
    print('  G2 값 %d칸 + 0건 %d칸 = %d칸 · 미측정 %d칸 · 표 대조 %d칸'
          % (len(v2), len(ns2), len(v2) + len(ns2), len(gaps2), len(tab2)))
    print('  G2 노선별: %s' % ', '.join(
        '%s %d/%d' % (c, per2[c]['values'], per2[c]['nosale']) for c in G2_ROUTES))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_total = fl['counts']['total']
    before_other = json.dumps([r for r in fl['routes']
                               if r['code'] not in set(G1_ROUTES) | set(G2_ROUTES)],
                              ensure_ascii=False, sort_keys=True)
    before_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False, sort_keys=True)
                     for r in fl['routes'] if r['code'] in set(G1_ROUTES) | set(G2_ROUTES)
                     for d in r['deals']}
    before_nosale = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_by_month = dict(fl['counts']['byMonth'])

    added1, dup1, _ = merge(master, v1, {})
    added2, dup2, new_ns2 = merge(master, v2, ns2)
    notes_update(fl)

    if len(dup1) != 168 or len(added1) != NEW_G1:
        raise SystemExit('G1 중복 %d칸·신규 %d칸 (기대 168·%d)'
                         % (len(dup1), len(added1), NEW_G1))
    if len(dup2) != 100 or len(added2) != NEW_G2_VALUES:
        raise SystemExit('G2 중복 %d칸·신규 %d칸 (기대 100·%d)'
                         % (len(dup2), len(added2), NEW_G2_VALUES))
    if len(new_ns2) != NEW_G2_NOSALE:
        raise SystemExit('G2 신규 0건 %d칸 (기대 %d칸): %s' % (len(new_ns2), NEW_G2_NOSALE, new_ns2))

    # 4) 보존 검증 — 호텔·아코르·다른 노선·기존 딜은 한 바이트도 바뀌면 안 된다
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] not in set(G1_ROUTES) | set(G2_ROUTES)],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 항공 노선 데이터가 바뀌었습니다.')
    after_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False, sort_keys=True)
                    for r in fl['routes'] if r['code'] in set(G1_ROUTES) | set(G2_ROUTES)
                    for d in r['deals']}
    lost = [k for k in before_within if before_within[k] != after_within.get(k)]
    if lost:
        raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % lost[:5])
    old_ns = {tuple(sorted(n.items())) for n in json.loads(before_nosale)}
    if not old_ns <= {tuple(sorted(n.items())) for n in fl['noSale']}:
        raise SystemExit('기존 판매편 0건 기록이 바뀌었습니다.')
    for r in fl['routes']:
        if r['code'] in set(G1_ROUTES) | set(G2_ROUTES):
            keys = [(d['date'], d['pattern']) for d in r['deals']]
            if len(keys) != len(set(keys)):
                raise SystemExit('%s (출발일·패턴) 중복' % r['code'])

    if fl['counts']['total'] != NEW_TOTAL:
        raise SystemExit('총 %d건 (기대 %d건)' % (fl['counts']['total'], NEW_TOTAL))

    print('G1 신규 딜 %d건(중복 %d건) · G2 신규 딜 %d건(중복 %d건) · 신규 0건 %d건 → noSale %d건'
          % (len(added1), len(dup1), len(added2), len(dup2), len(new_ns2), len(fl['noSale'])))
    print('총 %d건 → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, fl['counts']['total'],
        fl['counts']['total'] - fl['counts']['daytrip'], fl['counts']['daytrip']))
    print('월별: %s' % fl['counts']['byMonth'])
    print('월별 증가: %s' % {m: fl['counts']['byMonth'].get(m, 0) - before_by_month.get(m, 0)
                             for m in EXPECT_MONTH_KEYS})
    print('8노선 건수: %s' % ', '.join(
        '%s %d' % (r['code'], len(r['deals'])) for r in fl['routes']
        if r['code'] in set(G1_ROUTES) | set(G2_ROUTES)))

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


EXPECT_MONTH_KEYS = ('2027-02', '2027-03', '2027-04', '2027-05', '2027-06')

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
