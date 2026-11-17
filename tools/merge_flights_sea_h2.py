#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **동남아 4개 노선**(푸꾸옥 PQC·코타키나발루 BKI·쿠알라룸푸르 KUL·비엔티안 VTE)
2027년 7~11월 22주 × 5패턴 **440칸**(실측 220 + 예약 미오픈 220) md → `data/master_db.json` 병합.

원문: `data-sources/flights-sea-new8/부산출발-동남아4노선-푸꾸옥코타쿠알라비엔티안-7_11월.md` (4번 보고)

읽는 곳:
  · `## 1. 부산 ↔ 푸꾸옥(PQC)` ~ `## 4. …` 절 — 노선 코드·직항 유무
  · `### 금~일(2박)` 등 5개 표 — 출발·귀국·총액·항공사·직항/경유·가는편·오는편·비고의 원본
  · `### 달력형 요약(주차 × 패턴, 왕복 최저가)` — 22주 × 5패턴 110칸(표와 전수 대조)
  · `**패턴별 요약**`·`**월별 요약**` — 패턴·월별 최저/평균/최고(파싱 결과와 대조)
  · `## 요약 — 4노선 최저가` 표 — 노선별 최저·일정·패턴·항공사·직항/경유

규칙:
  · 값은 원문 그대로. `미오픈`(예약창 2027-09-14 밖) 칸은 `noSale` 에 `status: unopened` 로 넣고
    가격을 만들지 않는다(0건·요금 미공개와 구분).
  · 원문이 말하는 칸 수(440 · 노선별 110)·실측 55칸의 최저/최고/평균·직항 칸 수·패턴별 최저/평균/최고·
    월별 최저/평균·달력표 110칸·노선별 최저가표를 파싱 결과와 **전수 대조**한다. 하나라도 다르면 멈춘다.
  · 이미 있는 칸은 건드리지 않고, 기존 금액이 하나라도 달라지면 멈춘다.
  · 호텔 538곳 · 아코르 SNU 43줄 · 출처 · 패턴 정의 · 기존 `noSale` · 다른 43개 노선은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · daytrip · holiday)와 2027-07~11 `notes`, `bookingWindow` 를 다시 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_sea_h2.py --dry-run
    python3 tools/merge_flights_sea_h2.py --note "..."
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
MD = os.path.join(ROOT, '..', '..', 'data-sources', 'flights-sea-new8',
                  '부산출발-동남아4노선-푸꾸옥코타쿠알라비엔티안-7_11월.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
PATTERNS = ('금~일', '토~월', '목~일', '금~월', '목~월')
NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
YEAR = 2027
WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
              for i in range(22))                       # 07-01 ~ 11-25 (목)
MEASURED = WEEKS[:11]                                   # 07-01 ~ 09-09
UNOPENED = WEEKS[11:]                                   # 09-16 ~ 11-25
LAST_SALE = '2027-09-14'

# 원문이 말하는 노선별 값 — (도시, 실측 칸, 최저, 최고, 평균, 직항 칸, 경유 칸)
EXPECT_ROUTE = {
    'PQC': ('푸꾸옥', 55, 423616, 780500, 624246, 26, 29),
    'BKI': ('코타키나발루', 55, 425000, 851200, 712273, 0, 55),
    'KUL': ('쿠알라룸푸르', 55, 411136, 436617, 421792, 0, 55),
    'VTE': ('비엔티안', 55, 417896, 1365374, 608394, 0, 55),
}
EXPECT_CELLS = 440
EXPECT_MEASURED = 220
EXPECT_UNOPENED = 220
EXPECT_BY_MONTH = {'2027-07': 100, '2027-08': 80, '2027-09': 40}
# 미오픈 220칸의 출발월 — 09/30 주의 금~일·금~월이 10/1로 넘어가 9월 48 · 10월 92 · 11월 80
EXPECT_UNOPENED_BY_MONTH = {'2027-09': 48, '2027-10': 92, '2027-11': 80}

ROUTE_HEAD = re.compile(r'^## (\d)\. 부산 ↔ (.+?)\(([A-Z]{3})\)$')
PAT_HEAD = re.compile(r'^### ([월화수목금토일]~[월화수목금토일])\((\d)박\)$')
ROW = re.compile(r'^\| (\d{2})/(\d{2}) \(([월화수목금토일])\) \| (\d{2})/(\d{2}) \| \*\*(.+?)\*\* \| '
                 r'(.+?) \| (.+?) \| (.+?) \| (.+?) \| (.*?) \|$')
CAL = re.compile(r'^\| (\d{2})/(\d{2}) 주 \(W(\d+)\) \|(.+)\|\s*$')
PSUM = re.compile(r'^\| ([월화수목금토일]~[월화수목금토일])\((\d)박\) \| \*\*([\d,]+)원\*\* \| '
                  r'([\d,]+)원 \| ([\d,]+)원 \| (\d{2})/(\d{2})~(\d{2})/(\d{2}) \|$')
MSUM = re.compile(r'^\| 2027년 (\d+)월 \| \*\*([\d,]+)원\*\* \| ([\d,]+)원 \| '
                  r'(\d{2})/(\d{2})~(\d{2})/(\d{2}) · ([월화수목금토일]~[월화수목금토일])\(\d박\) \|$')
TOTAL = re.compile(r'^- 실측 (\d+)칸 최저 \*\*([\d,]+)원\*\* / 최고 \*\*([\d,]+)원\*\* / '
                   r'평균 \*\*([\d,]+)원\*\*')
DIRECT = re.compile(r'^- 최저가가 직항이었던 칸 \*\*(\d+)칸\*\* / 경유였던 칸 (\d+)칸')
TOP = re.compile(r'^\| \*\*부산 ↔ (.+?)\(([A-Z]{3})\)\*\* \| \*\*([\d,]+)원\*\* \| '
                 r'(\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2}) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|')
SUMM = re.compile(r'^\| ([가-힣()]+) \| ([\d,]+)원 \| ([\d,]+)원 \| ([\d,]+)원 \| '
                  r'(?:\*\*([\d,]+)원\*\* \(([\d/]+)~([\d/]+), ([^,]+), ([^)]+)\)|직항 조회 0건) \|$')


def money(text):
    return int(str(text).replace(',', '').replace('원', '').strip())


def cell_date(thu, pat):
    return (datetime.date.fromisoformat(thu) +
            datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()


def _md(mon_day):
    """'07/02' → '2027-07-02'"""
    m, d = mon_day.split('/')
    return '%d-%s-%s' % (YEAR, m, d)


def parse(text):
    """원문 → {(code, date, pattern): 값 또는 '미오픈'} + 표(달력·패턴·월·머리) 사본."""
    lines = text.split('\n')
    cells, cal, psum, msum, heads = {}, {}, {}, {}, {}
    code = pat = None
    section = None
    for ln in lines:
        m = ROUTE_HEAD.match(ln)
        if m:
            code, pat, section = m.group(3), None, None
            heads[code] = {'city': m.group(2), 'total': None, 'direct': None,
                           'direct_flag': False, 'via_flag': False}
            continue
        if ln.startswith('## '):
            code = pat = section = None
            continue
        if not code:
            continue
        if ln.startswith('### 달력형 요약'):
            section = 'cal'
            continue
        m = PAT_HEAD.match(ln)
        if m:
            pat, section = m.group(1), 'pat'
            if int(m.group(2)) != NIGHTS[pat]:
                raise SystemExit('%s %s 박수 %s (기대 %s)' % (code, pat, m.group(2), NIGHTS[pat]))
            continue
        if ln.startswith('**패턴별 요약**'):
            pat, section = None, 'psum'
            continue
        if ln.startswith('**월별 요약**'):
            pat, section = None, 'msum'
            continue
        if ln.startswith('### ') or ln.startswith('**'):
            pat, section = None, None
            continue
        if '- **직항 있음**' in ln:
            heads[code]['direct_flag'] = True
        if '- **직항 조회 0건**' in ln:
            heads[code]['via_flag'] = True
        m = TOTAL.match(ln)
        if m and '직항' not in ln:
            heads[code]['total'] = (int(m.group(1)), money(m.group(2)), money(m.group(3)),
                                    money(m.group(4)))
            continue
        m = DIRECT.match(ln)
        if m:
            heads[code]['direct'] = (int(m.group(1)), int(m.group(2)))
            continue
        if section == 'cal':
            m = CAL.match(ln)
            if m:
                cal.setdefault(code, {})[(m.group(1), m.group(2))] = \
                    [v.strip() for v in m.group(4).split('|')]
            continue
        if section == 'psum':
            m = PSUM.match(ln)
            if m:
                psum.setdefault(code, {})[m.group(1)] = (
                    money(m.group(3)), money(m.group(4)), money(m.group(5)),
                    '%s/%s~%s/%s' % (m.group(6), m.group(7), m.group(8), m.group(9)))
            continue
        if section == 'msum':
            m = MSUM.match(ln)
            if m:
                msum.setdefault(code, {})[int(m.group(1))] = (
                    money(m.group(2)), money(m.group(3)),
                    _md('%s/%s' % (m.group(4), m.group(5))), m.group(8))
            continue
        if section == 'pat' and pat:
            m = ROW.match(ln)
            if not m:
                continue
            mm, dd, wd = m.group(1), m.group(2), m.group(3)
            date = '%d-%s-%s' % (YEAR, mm, dd)
            back = '%d-%s-%s' % (YEAR, m.group(4), m.group(5))
            if WD[wd] != WD[pat[0]]:
                raise SystemExit('%s %s %s 출발 요일 %s (패턴 %s)' % (code, date, pat, wd, pat))
            if datetime.date.fromisoformat(back) != (datetime.date.fromisoformat(date) +
                                                    datetime.timedelta(days=NIGHTS[pat])):
                raise SystemExit('%s %s %s 귀국일 %s 가 박수와 다릅니다' % (code, date, pat, back))
            price = m.group(6)
            if price == '미오픈':
                if (m.group(7), m.group(8), m.group(9), m.group(10)) != ('—', '—', '—', '—'):
                    raise SystemExit('%s %s %s 미오픈 칸에 다른 값이 있습니다' % (code, date, pat))
                cells[(code, date, pat)] = '미오픈'
            else:
                cells[(code, date, pat)] = (money(price), m.group(7), m.group(8), m.group(9),
                                            m.group(10), m.group(11), back)
    return cells, cal, psum, msum, heads


def top_table(text):
    """`## 요약 — 4노선 최저가` 표(노선별 최저·일정·패턴·항공사·직항/경유)."""
    out = {}
    for ln in text.split('\n'):
        m = TOP.match(ln)
        if m:
            out[m.group(2)] = (money(m.group(3)), m.group(4), m.group(6).strip(),
                               m.group(7).strip(), m.group(8).strip())
    return out


def summary_table(text):
    """노선별 '55칸 중 최저 / 평균 / 최고 / 직항만 골랐을 때 최저' 표."""
    out = {}
    for ln in text.split('\n'):
        m = SUMM.match(ln)
        if m:
            out[m.group(1)] = (money(m.group(2)), money(m.group(3)), money(m.group(4)),
                               money(m.group(5)) if m.group(5) else None,
                               (m.group(6), m.group(7), m.group(8).strip()) if m.group(5) else None)
    return out


def check(text, cells, cal, psum, msum, heads, tops, summs):
    bad = []
    if len(cells) != EXPECT_CELLS:
        bad.append('칸 %d (원문 440)' % len(cells))
    by_route = collections.Counter(c for (c, d, p) in cells)
    for code, n in by_route.items():
        if n != 110:
            bad.append('%s %d칸 (기대 110칸)' % (code, n))
    if set(by_route) != set(EXPECT_ROUTE):
        bad.append('노선 %s (기대 %s)' % (sorted(by_route), sorted(EXPECT_ROUTE)))
    opened = {k for k, v in cells.items() if v != '미오픈'}
    closed = {k for k, v in cells.items() if v == '미오픈'}
    if (len(opened), len(closed)) != (EXPECT_MEASURED, EXPECT_UNOPENED):
        bad.append('실측 %d·미오픈 %d (원문 220·220)' % (len(opened), len(closed)))
    want_open = {(c, cell_date(thu, p), p) for c in EXPECT_ROUTE for thu in MEASURED for p in PATTERNS}
    want_closed = {(c, cell_date(thu, p), p) for c in EXPECT_ROUTE for thu in UNOPENED for p in PATTERNS}
    if opened != want_open:
        bad.append('실측 칸 위치가 원문과 다릅니다: %s' % sorted(opened ^ want_open)[:4])
    if closed != want_closed:
        bad.append('미오픈 칸 위치가 원문과 다릅니다: %s' % sorted(closed ^ want_closed)[:4])
    for month, want in EXPECT_BY_MONTH.items():
        got = sum(1 for (c, d, p) in opened if d[:7] == month)
        if got != want:
            bad.append('%s 실측 %d칸 (원문 %d칸)' % (month, got, want))
    if '%s(화)까지' % LAST_SALE not in text.replace('2027-09-14(화)', LAST_SALE + '(화)'):
        bad.append('예약창 마지막 판매일(2027-09-14) 문장을 찾지 못했습니다')

    for code, (city, n, low, high, avg, ndirect, nvia) in EXPECT_ROUTE.items():
        h = heads.get(code) or {}
        if h.get('city') != city:
            bad.append('%s 도시 이름 %r (기대 %s)' % (code, h.get('city'), city))
        vals = [v[0] for k, v in cells.items() if k[0] == code and v != '미오픈']
        if len(vals) != n:
            bad.append('%s 실측 %d칸 (원문 %d칸)' % (code, len(vals), n))
            continue
        if (min(vals), max(vals), round(sum(vals) / len(vals))) != (low, high, avg):
            bad.append('%s 최저/최고/평균 %s (원문 %s)' % (
                code, (min(vals), max(vals), round(sum(vals) / len(vals))), (low, high, avg)))
        t = h.get('total')
        if t != (n, low, high, avg):
            bad.append('%s 절 머리 요약 %s (원문 %s)' % (code, t, (n, low, high, avg)))
        dc = h.get('direct')
        if dc != (ndirect, nvia):
            bad.append('%s 직항/경유 칸 %s (원문 %s)' % (code, dc, (ndirect, nvia)))
        got_direct = sum(1 for k, v in cells.items()
                         if k[0] == code and v != '미오픈' and not v[2].startswith('경유'))
        if got_direct != ndirect:
            bad.append('%s 최저가 직항 칸 %d (원문 %d)' % (code, got_direct, ndirect))
        if city == '푸꾸옥' and not h.get('direct_flag'):
            bad.append('푸꾸옥 절 머리에 직항 있음 표기가 없습니다')
        if city != '푸꾸옥' and not h.get('via_flag'):
            bad.append('%s 절 머리에 직항 조회 0건 표기가 없습니다' % code)

        # 달력표(22주 × 5패턴) 전수 대조
        calr = cal.get(code) or {}
        if len(calr) != 22:
            bad.append('%s 달력표 %d주 (기대 22주)' % (code, len(calr)))
        for thu in WEEKS:
            key = (thu[5:7], thu[8:10])
            row = calr.get(key)
            if row is None:
                bad.append('%s 달력표 %s 주 없음' % (code, thu))
                continue
            if len(row) != 5:
                bad.append('%s 달력표 %s 칸 수 %d' % (code, thu, len(row)))
                continue
            for pat, v in zip(PATTERNS, row):
                cell = cells.get((code, cell_date(thu, pat), pat))
                if cell is None:
                    bad.append('%s %s %s 칸 없음' % (code, cell_date(thu, pat), pat))
                elif cell == '미오픈':
                    if v != '미오픈':
                        bad.append('%s %s %s 달력표 %r (표에는 미오픈)' % (code, thu, pat, v))
                elif money(v) != cell[0]:
                    bad.append('%s %s %s 달력표 %s ≠ 표 %d' % (code, thu, pat, v, cell[0]))

        # 패턴별 요약
        ps = psum.get(code) or {}
        if len(ps) != 5:
            bad.append('%s 패턴별 요약 %d줄 (기대 5줄)' % (code, len(ps)))
        for pat in PATTERNS:
            vals2 = [(v[0], k[1]) for k, v in cells.items()
                     if k[0] == code and k[2] == pat and v != '미오픈']
            want = (min(p for p, _ in vals2), round(sum(p for p, _ in vals2) / len(vals2)),
                    max(p for p, _ in vals2))
            got = ps.get(pat)
            if got is None:
                bad.append('%s %s 패턴 요약 없음' % (code, pat))
            elif got[:3] != want:
                bad.append('%s %s 패턴 요약 %s (계산 %s)' % (code, pat, got[:3], want))
            else:
                # 동률이 많아(같은 금액이 여러 주) 적힌 일정의 금액이 그 패턴 최저인지만 본다.
                md = _md(got[3].split('~')[0])
                cell = cells.get((code, md, pat))
                if cell is None or cell == '미오픈' or cell[0] != want[0]:
                    bad.append('%s %s 최저 일정 %s 칸이 최저가가 아닙니다' % (code, pat, got[3]))

        # 월별 요약(7·8·9월)
        ms = msum.get(code) or {}
        if set(ms) != {7, 8, 9}:
            bad.append('%s 월별 요약 %s (기대 7·8·9월)' % (code, sorted(ms)))
        for mon in (7, 8, 9):
            vals3 = [(v[0], k[1], k[2]) for k, v in cells.items()
                     if k[0] == code and v != '미오픈' and int(k[1][5:7]) == mon]
            low3 = min(vals3)
            want = (low3[0], round(sum(p for p, _, _ in vals3) / len(vals3)))
            got = ms.get(mon)
            if got is None:
                bad.append('%s %d월 요약 없음' % (code, mon))
            elif got[0] != want[0] or got[1] != want[1]:
                bad.append('%s %d월 요약 %s (계산 %s)' % (code, mon, got[:2], want))
            else:
                cell = cells.get((code, got[2], got[3]))
                if cell is None or cell == '미오픈' or cell[0] != want[0]:
                    bad.append('%s %d월 최저 일정 %s %s 가 최저가가 아닙니다'
                               % (code, mon, got[2], got[3]))

        # 요약 — 4노선 최저가 표
        tp = tops.get(code)
        lowk = min((v[0], k[1], k[2]) for k, v in cells.items()
                   if k[0] == code and v != '미오픈')
        if tp is None:
            bad.append('%s 요약표 없음' % code)
        else:
            cell = cells.get((code, tp[1], tp[2].split('(')[0]))
            if cell is None or cell == '미오픈' or cell[0] != tp[0]:
                bad.append('%s 요약표 %s 일정의 값이 표와 다릅니다' % (code, tp[1]))
            elif tp[0] != min(v[0] for k, v in cells.items()
                             if k[0] == code and v != '미오픈'):
                bad.append('%s 요약표 %d 는 기간 최저가가 아닙니다' % (code, tp[0]))

        # 노선별 최저/평균/최고 4칸 표
        sm = summs.get(city)
        if sm is None:
            bad.append('%s 최저/평균/최고 표 없음' % city)
        elif sm[:3] != (low, avg, high):
            bad.append('%s 최저/평균/최고 표 %s (원문 %s)' % (city, sm[:3], (low, avg, high)))
        elif (sm[3] is None) != (ndirect == 0):
            bad.append('%s 직항만 골랐을 때 최저 %s (직항 %d칸)' % (city, sm[3], ndirect))
        elif sm[3] is not None and sm[3] != low:
            bad.append('%s 직항만 골랐을 때 최저 %d (전짐 최저 %d)' % (city, sm[3], low))
    return bad


def deal_of(code, date, pat, val):
    price, airline, via_text, go, back_leg, memo, back = val
    note = '%s %s · 오는편 %s' % (via_text, go, back_leg)
    if memo:
        note += ' · ' + memo
    return {'date': date, 'back': back, 'pattern': pat, 'price': price,
            'airline': airline, 'via': via_text.startswith('경유'), 'note': note}


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


def month_note(fl, month, use):
    """동남아 4개 노선의 그 달 커버리지 — 실측/미오픈을 실제 데이터에서 세어 문장으로 만든다."""
    routes = {r['code']: r for r in fl['routes']}
    got = [(d['price'], d['date'], d['pattern'], code, d.get('airline', ''))
           for code in ('PQC', 'BKI', 'KUL', 'VTE') for d in routes[code]['deals']
           if d['date'][:7] == month and '2027-07-01' <= d['date'] <= '2027-11-29']
    up = [n for n in fl['noSale'] if n['code'] in ('PQC', 'BKI', 'KUL', 'VTE')
          and n['date'][:7] == month and n['status'] == 'unopened']
    city = {c: EXPECT_ROUTE[c][0] for c in EXPECT_ROUTE}
    body = ('동남아 4개 노선(푸꾸옥·코타키나발루·쿠알라룸푸르·비엔티안)은 2027년 7~11월 22주 × 5패턴 '
            '440칸 가운데 ')
    if got and not up:
        low = min(got)
        return (body + '이 달 %d칸을 전부 실측했습니다 — 이 달 최저는 %s %s %s %s원(%s)입니다.'
                % (len(got), city[low[3]], low[1], low[2], format(low[0], ','), low[4]))
    if got and up:
        low = min(got)
        return (body + '이 달은 %d칸이 실측이고 %d칸이 미오픈입니다(예약창 %s까지). 실측 최저는 '
                '%s %s %s %s원(%s)입니다.'
                % (len(got), len(up), LAST_SALE, city[low[3]], low[1], low[2],
                   format(low[0], ','), low[4]))
    return (body + '예약창이 %s까지라 이 달 %d칸 전부 미오픈입니다(항공사 스케줄 미개시).'
            % (LAST_SALE, len(up)))


def notes_update(fl, before_notes):
    for month in ('2027-07', '2027-08', '2027-09', '2027-10', '2027-11'):
        fl['notes'][month] = (before_notes[month].rstrip() + ' ' +
                              month_note(fl, month, True))
    bw = fl['bookingWindow']
    bw['note'] = (bw['note'].rstrip() +
                  ' 동남아 4개 노선(푸꾸옥·코타키나발루·쿠알라룸푸르·비엔티안)은 2027-09-14 출발분까지만 '
                  '열려 있고 9/15 이후·10~11월은 미오픈입니다.')
    bw['sea4End'] = LAST_SALE


def main(argv):
    ap = argparse.ArgumentParser(description='동남아 4노선 2027년 7~11월 440칸 → flights 병합')
    ap.add_argument('--md', default=MD)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    cells, cal, psum, msum, heads = parse(text)
    tops, summs = top_table(text), summary_table(text)
    bad = check(text, cells, cal, psum, msum, heads, tops, summs)
    print('  파싱: %d칸 (실측 %d · 미오픈 %d) — 노선별 %s'
          % (len(cells), sum(1 for v in cells.values() if v != '미오픈'),
             sum(1 for v in cells.values() if v == '미오픈'),
             dict(collections.Counter(c for c, d, p in cells))))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다:\n  - ' + '\n  - '.join(bad))

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}

    snap = {k: json.dumps(master.get(k), ensure_ascii=False, sort_keys=True)
            for k in ('hotels', 'accor', 'sources')}
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    notes_before = {m: fl['notes'][m] for m in ('2027-07', '2027-08', '2027-09',
                                                '2027-10', '2027-11')}
    bw_before = {k: v for k, v in fl['bookingWindow'].items() if k not in ('note', 'sea4End')}
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    other = [r for r in fl['routes'] if r['code'] not in EXPECT_ROUTE]
    other_before = json.dumps(other, ensure_ascii=False, sort_keys=True)
    held_before = {}
    for code in EXPECT_ROUTE:
        for d in routes[code]['deals']:
            held_before[(code, d['date'], d['pattern'])] = json.dumps(d, ensure_ascii=False,
                                                                     sort_keys=True)

    added, dup, conflicts = [], [], []
    for (code, date, pat), val in sorted(cells.items()):
        r = routes[code]
        have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pat), None)
        marked = next((n for n in fl['noSale']
                       if n['code'] == code and n['date'] == date and n['pattern'] == pat), None)
        if val == '미오픈':
            if have is not None:
                conflicts.append((code, date, pat, '미오픈', have['price']))
            elif marked is not None:
                dup.append((code, date, pat))
            else:
                fl['noSale'].append({'code': code, 'date': date,
                                     'back': (datetime.date.fromisoformat(date) +
                                              datetime.timedelta(days=NIGHTS[pat])).isoformat(),
                                     'pattern': pat, 'status': 'unopened',
                                     'note': '예약창 밖(%s까지) — 항공사 스케줄 미개시' % LAST_SALE})
                added.append((code, date, pat, 'unopened'))
        else:
            if have is not None:
                if have.get('price') != val[0]:
                    conflicts.append((code, date, pat, have.get('price'), val[0]))
                dup.append((code, date, pat))
            elif marked is not None:
                conflicts.append((code, date, pat, 'noSale', val[0]))
            else:
                r['deals'].append(deal_of(code, date, pat, val))
                added.append((code, date, pat, val[0]))
    if conflicts:
        raise SystemExit('기존 값과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts[:8])
    if dup:
        raise SystemExit('중복 칸이 있습니다: %s' % dup[:5])
    if len(added) != EXPECT_CELLS:
        raise SystemExit('신규 %d칸 (기대 %d칸)' % (len(added), EXPECT_CELLS))
    for r in fl['routes']:
        if r['code'] in EXPECT_ROUTE:
            r['deals'].sort(key=lambda d: (d['date'], d['pattern']))

    counts, by_month = recount(fl)
    master['counts']['deals'] = counts['total']
    notes_update(fl, notes_before)

    # ── 보존·건수 검증 ──
    if counts['total'] != before_total + EXPECT_MEASURED:
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], before_total + EXPECT_MEASURED))
    for k, v in snap.items():
        if json.dumps(master.get(k), ensure_ascii=False, sort_keys=True) != v:
            raise SystemExit('%s 데이터가 바뀌었습니다.' % k)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다.')
    if json.dumps(other, ensure_ascii=False, sort_keys=True) != other_before:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다.')
    after = {}
    for code in EXPECT_ROUTE:
        for d in routes[code]['deals']:
            after[(code, d['date'], d['pattern'])] = json.dumps(d, ensure_ascii=False,
                                                                sort_keys=True)
    lost = [k for k, v in held_before.items() if after.get(k) != v]
    if lost:
        raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % lost[:5])
    if json.dumps(fl['noSale'][:len(json.loads(nosale_before))], ensure_ascii=False) != nosale_before:
        raise SystemExit('기존 noSale 순서/내용이 바뀌었습니다.')
    if {k: v for k, v in fl['bookingWindow'].items() if k not in ('note', 'sea4End')} != bw_before:
        raise SystemExit('예약창 정보가 바뀌었습니다(주석 외).')
    if fl['bookingWindow'].get('sea4End') != LAST_SALE:
        raise SystemExit('동남아 4노선 예약창(%s)이 기록되지 않았습니다.' % LAST_SALE)
    for r in fl['routes']:
        keys = [(d['date'], d['pattern']) for d in r['deals']]
        if len(keys) != len(set(keys)):
            raise SystemExit('%s (출발일·패턴) 중복' % r['code'])
    marks = collections.Counter(n.get('status') or 'nosale' for n in fl['noSale'])
    if marks['unopened'] != 16 + EXPECT_UNOPENED:
        raise SystemExit('미오픈 %d칸 (기대 %d칸)' % (marks['unopened'], 16 + EXPECT_UNOPENED))
    if marks['nosale'] != 182 or marks['nofare'] != 255:
        raise SystemExit('판매편 0건/요금 미공개 %s (기대 182/255)' % dict(marks))
    got_month = {m: sum(1 for a in added if a[1][:7] == m and a[3] != 'unopened')
                 for m in EXPECT_BY_MONTH}
    got_up = {m: sum(1 for a in added if a[1][:7] == m and a[3] == 'unopened')
              for m in ('2027-09', '2027-10', '2027-11')}
    if got_month != EXPECT_BY_MONTH or got_up != EXPECT_UNOPENED_BY_MONTH or \
            sum(got_up.values()) != EXPECT_UNOPENED:
        raise SystemExit('월별 신규 칸 실측 %s · 미오픈 %s (기대 %s · %s)'
                         % (got_month, got_up, EXPECT_BY_MONTH, EXPECT_UNOPENED_BY_MONTH))

    print('신규 %d칸 (실측 %d · 미오픈 %d) — 실측 월별 %s · 미오픈 월별 %s'
          % (len(added), len(added) - EXPECT_UNOPENED, EXPECT_UNOPENED, got_month, got_up))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'], counts['daytrip']))
    print('월별: %s' % counts['byMonth'])
    print('노선별 건수: %s' % ', '.join('%s %d' % (r['code'], len(r['deals']))
                                    for r in fl['routes'] if r['code'] in EXPECT_ROUTE))
    print('표시: 판매편 0건 %d · 요금 미공개 %d · 미오픈 %d'
          % (marks['nosale'], marks['nofare'], marks['unopened']))

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        json.dump(fl, open(os.path.join(ROOT, 'data', '.sea_h2_dry_flights.json'), 'w'),
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
