#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **필리핀 4개 노선(세부·마닐라·보홀·클락) 2027년 7~11월** 1차 실측을
`data/master_db.json` 의 `flights` 에 병합한다.

원본: `data-sources/flights-sea-new8/부산출발-필리핀4노선-세부마닐라보홀클락-7_11월.md`
  · 4노선 × 5패턴 × 22주 = 440칸
  · 실측 **126칸**(마닐라 57 · 클락 55 · 세부 12 · 보홀 2)
  · 예약창(2027-10-14) 밖 **140칸** → `noSale` 의 `status='unopened'`(미오픈)
  · 미조회 **174칸**(세부 63 · 보홀 73 · 마닐라 18 · 클락 20) → 추정 없이 빈칸으로 둔다

읽는 곳:
  · `## 4. 부산 ↔ 마닐라(MNL)` · `## 5. … 클락(CRK)` — `### 노선 · 패턴(박수)` 아래 상세 표
    (출발·귀국·최저 왕복 총액·항공사·직항/경유·가는편·비고)를 값의 원본으로 쓰고,
    `| 출발 주(목) | 목~일 3박 | … |` 주차 × 패턴 표와 (노선·출발일·패턴) 단위로 전수 대조한다.
  · `## 6. … 세부(CEB)` · `## 7. … 보홀·팡라오(TAG)` — 패턴 열이 붙은 상세 표.
  · `## 1. 이번 조사의 완료 범위` 표(노선별 75칸 · 실측 · 미조회 · 미오픈)와
    `## 3. 실측 결과 요약` 표(최저·평균·최고·최저 일정·항공사·경유), 절 머리 요약
    (`- 최저 **…** / 최고 … / 평균 …`, `- 직항이 최저가였던 칸 **…**`), `### 가장 싼 10칸`.

규칙:
  · 값은 원문 그대로. 항공사·경유지 이름만 원문 표기를 유지한다.
  · `미오픈`(예약창 밖)만 `noSale` 에 `status='unopened'` 로 남기고, 미조회(`—`)는 아무것도 넣지 않는다.
  · 호텔 538곳 · 아코르 SNU 43줄 · 출처 목록 · 패턴 정의 · 기존 `noSale` · 다른 노선은
    **바이트 동일성**으로 보존을 확인한다. 기존 필리핀 4노선(12~1월 180칸 + 2~6월 420칸)도 그대로 둔다.
  · `counts`(total · byMonth · holiday · daytrip)와 2027-07~11 `notes`(plain text — `**` 금지),
    `bookingWindow`(필리핀 4노선 2027-10-14)을 다시 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_ph4h2.py --dry-run
    python3 tools/merge_flights_ph4h2.py --note "..."
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources'))
MD = os.path.join(SRC, 'flights-sea-new8',
                  '부산출발-필리핀4노선-세부마닐라보홀클락-7_11월.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
PH4 = ('CEB', 'MNL', 'TAG', 'CRK')
PH4_CITY = {'CEB': '세부', 'MNL': '마닐라', 'TAG': '보홀(팡라오)', 'CRK': '클락'}
PH4_NAME = {'세부': 'CEB', '마닐라': 'MNL', '보홀·팡라오': 'TAG', '클락': 'CRK'}
PAT5 = ('목~일', '금~일', '토~월', '금~월', '목~월')
PAT_NIGHTS = {'목~일': 3, '금~일': 2, '토~월': 2, '금~월': 3, '목~월': 4}
H2_WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
                 for i in range(22))                    # 22주(마지막 목요일 2027-11-25)
LAST_SALE = '2027-10-14'                                # 예약창 상한(조회 시점)
UNOPENED_WEEKS = tuple(w for w in H2_WEEKS if w >= LAST_SALE)   # 16~22주차 7주

# ── 원문이 말하는 값 ────────────────────────────────────────────────────────────
EXPECT = {
    'CEB': {'cells': 75, 'measured': 12, 'missing': 63, 'unopened': 35,
            'low': 453652, 'high': 803600, 'avg': 586284, 'direct': 0,
            'low_span': ('2027-07-01', '2027-07-05'), 'low_pat': '목~월',
            'low_airline': '베트남항공'},
    'MNL': {'cells': 75, 'measured': 57, 'missing': 18, 'unopened': 35,
            'low': 406456, 'high': 766600, 'avg': 430650, 'direct': 2,
            'low_span': ('2027-08-06', '2027-08-08'), 'low_pat': '금~일',
            'low_airline': '비엣젯항공'},
    'TAG': {'cells': 75, 'measured': 2, 'missing': 73, 'unopened': 35,
            'low': 553300, 'high': 565669, 'avg': 559484, 'direct': 0,
            'low_span': ('2027-07-02', '2027-07-04'), 'low_pat': '금~일',
            'low_airline': '필리핀항공'},
    'CRK': {'cells': 75, 'measured': 55, 'missing': 20, 'unopened': 35,
            'low': 409800, 'high': 765300, 'avg': 579507, 'direct': 0,
            'low_span': ('2027-09-03', '2027-09-06'), 'low_pat': '금~월',
            'low_airline': '홍콩 익스프레스항공'},
}
EXPECT_MEASURED = 126
EXPECT_UNOPENED = 140
EXPECT_MISSING = 174
EXPECT_TOTAL = 6076                 # 5,950 + 126
EXPECT_WEEKEND = 5801               # 전체 주말형 5,675 + 126(모두 1~4박)
EXPECT_WEEKEND_H2 = 1425            # 2027-06~11 주말형 1,299 + 126
EXPECT_DAYTRIP = 275
EXPECT_NOSALE = 191
EXPECT_NOFARE = 255
EXPECT_UNOPENED_TOTAL = 376         # 236 + 140
EXPECT_BY_MONTH = {'2027-07': 445, '2027-08': 294, '2027-09': 232,
                   '2027-10': 94, '2027-11': 1}
ROUTE_DEALS = {'CEB': 162, 'MNL': 207, 'TAG': 152, 'CRK': 205}   # 150 + 신규

TEXT_MUST = (
    '4노선 × 5패턴 × 22주 = 440칸',
    '실측 126칸',
    '140칸은 전부',
    '16주차(2027-10-14',
    '상한은 **2027-10-14**',
    '남은 174칸: 세부 63칸 · 마닐라 18칸 · 보홀·팡라오 73칸 · 클락 20칸',
    '가장 싼 조합은 **마닐라 2027-08-06 → 2027-08-08',
)

ROUTE_HEAD = re.compile(r'^## \d+\. 부산 ↔ (세부|마닐라|보홀·팡라오|클락)\(([A-Z]{3})\)')
SUB_HEAD = re.compile(r'^### (세부|마닐라|보홀·팡라오|클락) · ([월화수목금토일]~[월화수목금토일])\((\d)박\)$')
DETAIL_ROW = re.compile(r'^\| (\d{2})/(\d{2}) \(([월화수목금토일])\) \| (\d{2})/(\d{2}) \|')
MATRIX_ROW = re.compile(r'^\| (\d{2})/(\d{2}) 주 \|')
SUM_ROW = re.compile(r'^\| 부산 ↔ (세부|마닐라|보홀·팡라오|클락)\(([A-Z]{3})\) \| 75칸 \| \*\*(\d+)칸\*\* \| (\d+)칸 \| (\d+)칸 \|$')
OVER_ROW = re.compile(r'^\| (세부|마닐라|보홀·팡라오|클락) \| (\d+)칸 \| \*\*([\d,]+)원\*\* \| '
                      r'([\d,]+)원 \| ([\d,]+)원 \| (\d{2}/\d{2}~\d{2}/\d{2}) · '
                      r'([월화수목금토일]~[월화수목금토일])\((\d)박\) \| ([^|]+?) \| ([^|]+?) \|$')
HEAD_SUM = re.compile(r'^- 최저 \*\*([\d,]+)원\*\* / 최고 ([\d,]+)원 / 평균 ([\d,]+)원$')
HEAD_DIRECT = re.compile(r'^- 직항이 최저가였던 칸 \*\*(\d+)칸\*\* / 경유 (\d+)칸$')
TOP_ROW = re.compile(r'^\| (\d+) \| (세부|마닐라|보홀\(팡라오\)|클락) \| (\d{4}-\d{2}-\d{2}) → '
                     r'(\d{4}-\d{2}-\d{2}) \| ([^(|]+)\((\d)박\) \| \*\*([\d,]+)\*\* \| '
                     r'([^|]+?) \| ([^|]+?) \| ([^|]+?) \|$')


def money(text):
    return int(re.sub(r'[^\d]', '', text))


def cells_of(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def date_of(mm, dd, year=2027):
    return datetime.date(year, int(mm), int(dd))


def parse(text):
    """상세 표 → deals, 주차 표 → matrix, 1·3절 표 → 요약."""
    deals, matrix, summary, over, heads, tops = {}, {}, {}, {}, {}, {}
    code = sub_pat = table = None
    row_count = collections.Counter()
    unmeasured = []
    for raw in text.splitlines():
        line = raw.strip()
        m = ROUTE_HEAD.match(line)
        if m:
            code, sub_pat, table = m.group(2), None, None
            if code not in PH4:
                raise SystemExit('예상 밖 노선: %s' % line)
            matrix[code] = {}
            continue
        if line.startswith('## '):
            code = sub_pat = table = None
            continue
        m = SUB_HEAD.match(line)
        if m:
            name, pat, nights = m.groups()
            if PH4_NAME[name] != code:
                raise SystemExit('절과 노선이 다릅니다: %s' % line)
            if PAT_NIGHTS[pat] != int(nights):
                raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
            sub_pat = pat
            table = None
            continue
        m = SUM_ROW.match(line)
        if m:
            name, c, measured, missing, unopened = m.groups()
            if c != PH4_NAME[name]:
                raise SystemExit('1절 표 노선 코드가 다릅니다: %s' % line)
            summary[c] = {'measured': int(measured), 'missing': int(missing),
                          'unopened': int(unopened)}
            continue
        m = OVER_ROW.match(line)
        if m:
            (name, n, low, avg, high, span, pat, nights, airline, via) = m.groups()
            c = PH4_NAME[name]
            if PAT_NIGHTS[pat] != int(nights):
                raise SystemExit('3절 박수 표기가 다릅니다: %s' % line)
            a, b = span.split('~')
            over[c] = {'cells': int(n), 'low': money(low), 'avg': money(avg),
                       'high': money(high),
                       'low_span': ('2027-' + a.replace('/', '-'), '2027-' + b.replace('/', '-')),
                       'low_pat': pat, 'airline': airline.strip(), 'via': via.strip()}
            continue
        m = HEAD_SUM.match(line)
        if m and code and sub_pat is None:
            heads.setdefault(code, {})['sum'] = (money(m.group(1)), money(m.group(2)),
                                                 money(m.group(3)))
            continue
        m = HEAD_DIRECT.match(line)
        if m and code:
            heads.setdefault(code, {})['direct'] = int(m.group(1))
            continue
        m = TOP_ROW.match(line)
        if m:
            (rank, city, d1, d2, pat, nights, price, airline, via, go) = m.groups()
            c = {'세부': 'CEB', '마닐라': 'MNL', '보홀(팡라오)': 'TAG', '클락': 'CRK'}[city]
            tops[int(rank)] = {'code': c, 'date': d1, 'back': d2, 'pattern': pat,
                               'nights': int(nights), 'price': money(price),
                               'airline': airline.strip()}
            continue
        if not code or not line.startswith('|'):
            continue
        cells = cells_of(line)
        if cells and cells[0] == '출발 주(목)':
            table = ('matrix', [c.split(' ')[0] for c in cells[1:]])
            if table[1] != list(PAT5):
                raise SystemExit('주차 표 패턴 순서가 다릅니다: %s' % line)
            continue
        if cells and cells[0] == '출발':
            table = ('detail', None)
            continue
        if table and table[0] == 'matrix':
            m = MATRIX_ROW.match(line)
            if not m:
                continue
            thu = date_of(m.group(1), m.group(2))
            if thu.isoweekday() != 4:
                raise SystemExit('주차 표 시작일이 목요일이 아닙니다: %s' % line)
            vals = cells[1:]
            if len(vals) != 5:
                raise SystemExit('주차 표 칸 수가 5가 아닙니다: %s' % line)
            for pat, val in zip(PAT5, vals):
                d = (thu + datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7))
                matrix[code][(d.isoformat(), pat)] = None if val == '—' else money(val)
            continue
        if table and table[0] == 'detail':
            m = DETAIL_ROW.match(line)
            if not m:
                continue
            mm, dd, wd, bmm, bdd = m.groups()
            out = date_of(mm, dd)
            back = date_of(bmm, bdd)
            if WD[wd] != out.isoweekday() % 7:
                raise SystemExit('%s 의 요일 표기가 맞지 않습니다: %s' % (out, line))
            if len(cells) == 7:
                if sub_pat is None:
                    raise SystemExit('패턴 절 없이 7열 상세 줄이 나왔습니다: %s' % line)
                pat, rest = sub_pat, cells[2:]
                nights = PAT_NIGHTS[pat]
            elif len(cells) == 8:
                pm = re.match(r'^([월화수목금토일]~[월화수목금토일])\((\d)박\)$', cells[2])
                if not pm:
                    raise SystemExit('패턴 열 표기가 이상합니다: %s' % line)
                pat, nights = pm.group(1), int(pm.group(2))
                if PAT_NIGHTS.get(pat) != nights:
                    raise SystemExit('패턴·박수가 어긋납니다: %s' % line)
                rest = cells[3:]
            else:
                raise SystemExit('상세 줄 열 수가 7·8이 아닙니다: %s' % line)
            price, airline, via, going, memo = rest
            if back != out + datetime.timedelta(days=nights):
                raise SystemExit('%s 귀국일이 %d박과 맞지 않습니다: %s' % (out, nights, line))
            if out < datetime.date(2027, 7, 1) or out > datetime.date(2027, 11, 29):
                raise SystemExit('2027년 7~11월 밖 출발일입니다: %s' % line)
            key = (code, out.isoformat(), pat)
            if price == '—':
                if memo != '미조회':
                    raise SystemExit('값이 없는데 미조회 표기가 아닙니다: %s' % line)
                unmeasured.append(key)
                continue
            if key in deals:
                raise SystemExit('%s 중복' % (key,))
            if out >= datetime.date.fromisoformat(LAST_SALE):
                raise SystemExit('예약창 밖 출발일에 값이 있습니다: %s' % line)
            note = '%s · 가는편 %s' % (via, going)
            if memo and memo != '—':
                note += ' · ' + memo
            deals[key] = {'date': out.isoformat(), 'back': back.isoformat(), 'pattern': pat,
                          'price': money(price), 'airline': airline,
                          'via': via.startswith('경유'), 'note': note}
            row_count[code] += 1
    return deals, matrix, summary, over, heads, tops, unmeasured


def grid_cells():
    """4노선 × 22주 × 5패턴 = 440칸의 (노선, 출발일, 패턴) 집합."""
    out = set()
    for code in PH4:
        for thu in H2_WEEKS:
            t = datetime.date.fromisoformat(thu)
            for pat in PAT5:
                d = t + datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)
                out.add((code, d.isoformat(), pat))
    return out


def check(text, deals, matrix, summary, over, heads, tops, unmeasured):
    bad = []
    for need in TEXT_MUST:
        if need not in text:
            bad.append('원문 문장(%s)을 찾지 못했습니다' % need)
    grid = grid_cells()
    got_unopened = {(c, d, p) for (c, d, p) in grid if d >= LAST_SALE}
    miss = {(c, d, p) for (c, d, p) in grid if d < LAST_SALE} - set(deals) - set(unmeasured)
    if len(grid) != 440:
        bad.append('격자 %d칸 (440칸이어야 함)' % len(grid))
    if len(deals) != EXPECT_MEASURED:
        bad.append('실측 %d칸 (원문 %d칸)' % (len(deals), EXPECT_MEASURED))
    if len(got_unopened) != EXPECT_UNOPENED:
        bad.append('미오픈 %d칸 (원문 %d칸)' % (len(got_unopened), EXPECT_UNOPENED))
    if not set(unmeasured) <= grid or set(unmeasured) & set(deals):
        bad.append('상세 표의 미조회 줄 %d개가 격자·실측과 어긋납니다' % len(unmeasured))
    if len(miss) + len(unmeasured) != EXPECT_MISSING:
        bad.append('미조회 %d칸 + 표기 %d칸 = %d칸 (원문 %d칸)'
                   % (len(miss), len(unmeasured), len(miss) + len(unmeasured), EXPECT_MISSING))
    if set(deals) & got_unopened or set(deals) & miss:
        bad.append('실측 칸이 미오픈·미조회 칸과 겹칩니다')
    for code in PH4:
        want = EXPECT[code]
        mine = {k: v for k, v in deals.items() if k[0] == code}
        if len(mine) != want['measured']:
            bad.append('%s 실측 %d칸 (원문 %d칸)' % (code, len(mine), want['measured']))
        per = collections.Counter(k[2] for k in mine)
        if len(per) and set(per) - set(PAT5):
            bad.append('%s 에 5패턴 밖 패턴이 있습니다: %s' % (code, sorted(set(per) - set(PAT5))))
        m_miss = {k for k in miss if k[0] == code} | {k for k in unmeasured if k[0] == code}
        m_up = {k for k in got_unopened if k[0] == code}
        if len(m_miss) != want['missing']:
            bad.append('%s 미조회 %d칸 (원문 %d칸)' % (code, len(m_miss), want['missing']))
        if len(m_up) != want['unopened']:
            bad.append('%s 미오픈 %d칸 (원문 %d칸)' % (code, len(m_up), want['unopened']))
        s = summary.get(code) or {}
        if (s.get('measured'), s.get('missing'), s.get('unopened')) != \
                (want['measured'], want['missing'], want['unopened']):
            bad.append('1절 표 %s 값 %s (원문 %s)' % (code, s, want))
        prices = [d['price'] for d in mine.values()]
        if len(prices) != want['measured']:
            continue
        if (min(prices), max(prices)) != (want['low'], want['high']):
            bad.append('%s 최저·최고 %s (원문 %s)'
                       % (code, (min(prices), max(prices)), (want['low'], want['high'])))
        avg = sum(prices) / len(prices)
        o = over.get(code) or {}
        if o.get('avg') not in (int(avg), round(avg)):
            bad.append('%s 평균 %d/%d (원문 %s)' % (code, int(avg), round(avg), o.get('avg')))
        if (o.get('low'), o.get('high')) != (want['low'], want['high']):
            bad.append('3절 표 %s 최저·최고 %s (원문 %s)'
                       % (code, (o.get('low'), o.get('high')), (want['low'], want['high'])))
        if (o.get('low_span'), o.get('low_pat')) != (want['low_span'], want['low_pat']):
            bad.append('3절 표 %s 최저 일정 %s (원문 %s)'
                       % (code, (o.get('low_span'), o.get('low_pat')),
                          (want['low_span'], want['low_pat'])))
        if o.get('cells') != want['measured']:
            bad.append('3절 표 %s 칸 수 %s (원문 %s)' % (code, o.get('cells'), want['measured']))
        if not o.get('airline', '').startswith(want['low_airline']):
            bad.append('3절 표 %s 최저 항공사 %r (원문 %r)'
                       % (code, o.get('airline'), want['low_airline']))
        low = deals.get((code, want['low_span'][0], want['low_pat']))
        if not low or low['price'] != want['low'] or low['back'] != want['low_span'][1]:
            bad.append('%s 최저 칸(원문 %s %s %s)이 없습니다'
                       % (code, want['low_span'][0], want['low_pat'], want['low']))
        elif not low['airline'].startswith(want['low_airline']):
            bad.append('%s 최저 칸 항공사 %r (원문 %r)'
                       % (code, low['airline'], want['low_airline']))
        h = heads.get(code) or {}
        if h:
            if h.get('sum') != (want['low'], want['high'], o.get('avg')):
                bad.append('%s 절 머리 요약 %s (원문 %s)' % (code, h.get('sum'),
                                                         (want['low'], want['high'], o.get('avg'))))
        n_direct = sum(1 for d in mine.values() if d['via'] is False)
        if n_direct != want['direct']:
            bad.append('%s 직항이 최저가인 칸 %d (원문 %d)' % (code, n_direct, want['direct']))
        if h and h.get('direct') != want['direct']:
            bad.append('%s 절 머리 직항 칸 수 %s (원문 %d)' % (code, h.get('direct'), want['direct']))
        # 주차 × 패턴 표 ↔ 상세(MNL·CRK)
        mat = matrix.get(code) or {}
        if mat:
            if len(mat) != 22 * 5:
                bad.append('%s 주차 표 %d칸 (22주 × 5패턴 110칸이어야 함)' % (code, len(mat)))
            for (d, pat), val in mat.items():
                hit = deals.get((code, d, pat))
                if val is None:
                    if hit is not None:
                        bad.append('%s %s %s 주차 표는 —인데 상세에 %s'
                                   % (code, d, pat, hit['price']))
                elif hit is None:
                    bad.append('%s %s %s 주차 표에 %s인데 상세에 없음' % (code, d, pat, val))
                elif hit['price'] != val:
                    bad.append('%s %s %s 주차 표 %s ≠ 상세 %s'
                               % (code, d, pat, val, hit['price']))
        # 세부·보홀은 상세 줄이 주차 순서가 아니므로 패턴별 개수만 본다
    # 가장 싼 10칸
    if len(tops) != 10:
        bad.append('가장 싼 10칸 표 %d줄' % len(tops))
    ordered = sorted(d['price'] for d in deals.values())
    for i in range(1, 11):
        row = tops.get(i)
        if not row:
            continue
        if row['price'] != ordered[i - 1]:
            bad.append('가장 싼 %d위 금액 %s (계산 %s)' % (i, row['price'], ordered[i - 1]))
        hit = deals.get((row['code'], row['date'], row['pattern']))
        if not hit or hit['back'] != row['back'] or hit['price'] != row['price']:
            bad.append('가장 싼 %d위 칸 %s 가 상세와 다릅니다' % (i, row))
        elif not hit['airline'].startswith(row['airline']):
            bad.append('가장 싼 %d위 항공사 %r (상세 %r)' % (i, row['airline'], hit['airline']))
    all_low = min(d['price'] for d in deals.values())
    if all_low != 406456 or deals[('MNL', '2027-08-06', '금~일')]['price'] != 406456:
        bad.append('전체 최저 %s (원문 마닐라 2027-08-06 금~일 406,456원)' % all_low)
    if sum(1 for d in deals.values() if d['price'] == 406456) < 10:
        bad.append('406,456원 칸이 10칸 미만입니다')
    return bad


def month_note(fl, month):
    """필리핀 4개 노선의 그 달 커버리지 — 실측·미조회·미오픈을 실제 데이터에서 센다(plain text)."""
    routes = {r['code']: r for r in fl['routes']}
    got = [(d['price'], d['date'], d['pattern'], code, d.get('airline', ''))
           for code in PH4 for d in routes[code]['deals']
           if d['date'][:7] == month and '2027-07-01' <= d['date'] <= '2027-11-29']
    up = [n for n in fl['noSale'] if n['code'] in PH4 and n['date'][:7] == month
          and (n.get('status') or 'nosale') == 'unopened']
    total = sum(1 for (c, d, p) in grid_cells() if d[:7] == month)
    miss = total - len(got) - len(up)
    body = ('필리핀 4개 노선(세부·마닐라·보홀·클락)은 2027년 7~11월 22주 × 5패턴 440칸 가운데 ')
    if not got and up and not miss:
        txt = (body + '예약창이 %s 출발분까지라 이 달 %d칸 전부 미오픈입니다(항공사 스케줄 미개시).'
               % (LAST_SALE, len(up)))
        return txt
    tail = []
    if up:
        tail.append('%d칸은 미오픈(예약창 %s까지)' % (len(up), LAST_SALE))
    if miss:
        tail.append('%d칸은 미조회(—)' % miss)
    if got:
        txt = body + '이 달 %d칸을 실측' % len(got)
        txt += ('했고 ' + ' · '.join(tail) + '입니다.') if tail else '했습니다.'
        low = min(got)
        txt += (' 이 달 최저는 %s %s %s %s원(%s)입니다.'
                % (PH4_CITY[low[3]], low[1], low[2], format(low[0], ','), low[4]))
    else:
        txt = body + '이 달 실측값은 없고 ' + ' · '.join(tail) + '입니다.'
    return txt


def notes_update(fl, before_notes):
    for month in ('2027-07', '2027-08', '2027-09', '2027-10', '2027-11'):
        fl['notes'][month] = (before_notes[month].rstrip() + ' ' + month_note(fl, month))
    bw = fl['bookingWindow']
    bw['note'] = (bw['note'].rstrip() +
                  ' 필리핀 4개 노선(세부·마닐라·보홀·클락)은 2027-10-14 출발분까지만 열려 있고 '
                  '10/15 이후·11월은 미오픈입니다.')
    bw['ph4End'] = LAST_SALE


def recount(fl):
    all_deals = [d for r in fl['routes'] for d in r['deals']]
    by_month = {}
    for d in all_deals:
        by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    fl['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month[k] for k in sorted(by_month)},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals
                       if d['pattern'].split('~')[0] == d['pattern'].split('~')[1]),
    }
    return fl['counts'], by_month


def main(argv):
    ap = argparse.ArgumentParser(description='필리핀 4노선 2027년 7~11월 → flights 병합')
    ap.add_argument('--md', default=MD)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    deals, matrix, summary, over, heads, tops, unmeasured = parse(text)
    bad = check(text, deals, matrix, summary, over, heads, tops, unmeasured)
    print('  파싱: 실측 %d칸 — %s · 미오픈 %d칸 · 미조회 %d칸'
          % (len(deals), dict(collections.Counter(k[0] for k in deals)),
             sum(1 for (c, d, p) in grid_cells() if d >= LAST_SALE),
             EXPECT_MISSING))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다:\n  - ' + '\n  - '.join(bad))

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}

    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    sources_before = json.dumps(master.get('sources'), ensure_ascii=False)
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    notes_before = {m: fl['notes'][m] for m in ('2027-07', '2027-08', '2027-09',
                                                '2027-10', '2027-11')}
    bw_before = json.dumps({k: v for k, v in fl['bookingWindow'].items()
                            if k not in ('note', 'ph4End')}, ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    other_codes = set(r['code'] for r in fl['routes']) - set(PH4)
    before_ph = {code: json.dumps(routes[code]['deals'], ensure_ascii=False, sort_keys=True)
                 for code in PH4}
    before_other = json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                              ensure_ascii=False, sort_keys=True)
    before_weekend = sum(1 for r in fl['routes'] for d in r['deals']
                         if d['date'] >= '2027-06-01'
                         and d['pattern'].split('~')[0] != d['pattern'].split('~')[1])

    added, dup, conflicts = [], [], []
    for (code, date, pattern), deal in sorted(deals.items()):
        have = next((d for d in routes[code]['deals']
                     if d['date'] == date and d['pattern'] == pattern), None)
        if have is not None:
            if have.get('price') != deal['price']:
                conflicts.append((code, date, pattern, have.get('price'), deal['price']))
            dup.append((code, date, pattern))
            continue
        if any(n['code'] == code and n['date'] == date and n['pattern'] == pattern
               for n in fl['noSale']):
            conflicts.append((code, date, pattern, 'noSale', deal['price']))
            continue
        routes[code]['deals'].append(deal)
        added.append((code, date, pattern, deal['price']))
    for (code, date, pattern) in sorted({(c, d, p) for (c, d, p) in grid_cells()
                                         if d >= LAST_SALE},
                                        key=lambda k: (k[1], k[0], k[2])):
        if any(d['date'] == date and d['pattern'] == pattern for d in routes[code]['deals']):
            conflicts.append((code, date, pattern, 'deal', 'unopened'))
            continue
        if any(n['code'] == code and n['date'] == date and n['pattern'] == pattern
               for n in fl['noSale']):
            conflicts.append((code, date, pattern, 'noSale', 'unopened'))
            continue
        back = (datetime.date.fromisoformat(date) +
                datetime.timedelta(days=PAT_NIGHTS[pattern])).isoformat()
        fl['noSale'].append({'code': code, 'date': date, 'back': back, 'pattern': pattern,
                             'status': 'unopened',
                             'note': '예약창 밖(2027-10-14까지) — 항공사 스케줄 미개시'})
        added.append((code, date, pattern, 'unopened'))
    if conflicts:
        raise SystemExit('기존 값과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts[:8])
    if dup:
        raise SystemExit('이미 있는 칸이 있습니다: %s' % dup[:5])
    if len(added) != EXPECT_MEASURED + EXPECT_UNOPENED:
        raise SystemExit('신규 %d칸 (기대 %d칸)' % (len(added), EXPECT_MEASURED + EXPECT_UNOPENED))
    for code in PH4:
        routes[code]['deals'].sort(key=lambda d: (d['date'], d['pattern']))

    counts, by_month = recount(fl)
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = counts['total']
    notes_update(fl, notes_before)

    # ── 보존·건수 검증 ──
    if counts['total'] != EXPECT_TOTAL:
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], EXPECT_TOTAL))
    if counts['daytrip'] != EXPECT_DAYTRIP:
        raise SystemExit('당일치기 %d건 (기대 %d건)' % (counts['daytrip'], EXPECT_DAYTRIP))
    weekend = sum(1 for r in fl['routes'] for d in r['deals']
                  if d['date'] >= '2027-06-01'
                  and d['pattern'].split('~')[0] != d['pattern'].split('~')[1])
    if weekend != EXPECT_WEEKEND_H2:
        raise SystemExit('6~11월 주말형 %d칸 (기대 %d칸)' % (weekend, EXPECT_WEEKEND_H2))
    if counts['total'] - counts['daytrip'] != EXPECT_WEEKEND:
        raise SystemExit('주말형 %d칸 (기대 %d칸)'
                         % (counts['total'] - counts['daytrip'], EXPECT_WEEKEND))
    for m, want in EXPECT_BY_MONTH.items():
        if counts['byMonth'].get(m) != want:
            raise SystemExit('%s %s건 (기대 %d건)' % (m, counts['byMonth'].get(m), want))
    for code, want in ROUTE_DEALS.items():
        if len(routes[code]['deals']) != want:
            raise SystemExit('%s 딜 %d건 (기대 %d건)' % (code, len(routes[code]['deals']), want))
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps(master.get('sources'), ensure_ascii=False) != sources_before:
        raise SystemExit('출처 목록이 바뀌었습니다.')
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다.')
    if json.dumps({k: v for k, v in fl['bookingWindow'].items()
                   if k not in ('note', 'ph4End')},
                  ensure_ascii=False, sort_keys=True) != bw_before:
        raise SystemExit('예약창 정보가 바뀌었습니다(주석 외).')
    if fl['bookingWindow'].get('ph4End') != LAST_SALE:
        raise SystemExit('필리핀 4노선 예약창(2027-10-14)이 기록되지 않았습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다.')
    for code in PH4:
        now = json.dumps(routes[code]['deals'][:len(json.loads(before_ph[code]))],
                         ensure_ascii=False, sort_keys=True)
        old = json.loads(before_ph[code])
        now_list = routes[code]['deals'][:len(old)]
        if json.dumps(now_list, ensure_ascii=False, sort_keys=True) != json.dumps(old, ensure_ascii=False, sort_keys=True):
            raise SystemExit('%s 기존 딜이 사라지거나 바뀌었습니다.' % code)
    if json.dumps(fl['noSale'][:len(json.loads(nosale_before))], ensure_ascii=False) \
            != nosale_before:
        raise SystemExit('기존 noSale 순서/내용이 바뀌었습니다.')
    stat = collections.Counter(n.get('status') or 'nosale' for n in fl['noSale'])
    for key, want in (('nosale', EXPECT_NOSALE), ('nofare', EXPECT_NOFARE),
                      ('unopened', EXPECT_UNOPENED_TOTAL)):
        if stat[key] != want:
            raise SystemExit('%s %d칸 (기대 %d칸)' % (key, stat[key], want))
    if len(fl['noSale']) != EXPECT_NOSALE + EXPECT_NOFARE + EXPECT_UNOPENED_TOTAL:
        raise SystemExit('noSale 목록 %d줄' % len(fl['noSale']))
    if '**' in json.dumps({m: fl['notes'][m] for m in EXPECT_BY_MONTH}, ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다.')

    print('신규 %d칸 (실측 %d · 미오픈 %d)'
          % (len(added), EXPECT_MEASURED, EXPECT_UNOPENED))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'],
             counts['total'] - counts['daytrip'], counts['daytrip']))
    print('월별: %s' % counts['byMonth'])
    print('월별 증가: %s' % {m: counts['byMonth'].get(m, 0) - before_by_month.get(m, 0)
                            for m in counts['byMonth']})
    print('표시: 판매편 0건 %d · 요금 미공개 %d · 미오픈 %d'
          % (stat['nosale'], stat['nofare'], stat['unopened']))
    print('노선별 건수: %s' % ', '.join('%s %d' % (c, len(routes[c]['deals'])) for c in PH4))
    for code in PH4:
        mine = routes[code]['deals']
        print('  %s 최저 %s / 최고 %s' % (code, format(min(d['price'] for d in mine), ','),
                                       format(max(d['price'] for d in mine), ',')))

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        json.dump(fl, open(os.path.join(ROOT, 'data', '.ph4h2_dry_flights.json'), 'w'),
                  ensure_ascii=False)
        return 0
    if args.note:
        master['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('저장: %s' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
