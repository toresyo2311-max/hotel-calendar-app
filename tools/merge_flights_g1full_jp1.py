#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 항공 특가에 **팀원 완결본 2건**을 한꺼번에 병합한다.

  1) 중국 G1 4개 노선(선양·다롄·광저우·샤먼) 2027년 2~6월 **420/420칸(100%)** 완주본
     — `data-sources/flights-china-new8/부산출발-중국4노선-선양다롄광저우샤먼-2_6월.md`
     기존 384칸(2박 168 + 목~일 84 + 금~월 84 + 목~월 48)은 금액이 그대로여서 두고,
     마지막 미조회였던 **4/29~6/24 목~월(4박) 9주 36칸**만 더한다. 판매편 0건·미조회 0칸.
  2) 일본 신규 7개 노선(구마모토·다카마쓰·마쓰야마·시즈오카·미야코지마·삿포로·가고시마)
     2027년 1월 **4주 × 5패턴 140칸 완결본**
     — `data-sources/flights-jp-new7/부산출발-일본7노선-1월-완결.md`
     값 **138칸** + 항공편 없음(`nosale`) **2칸**(다카마쓰 1/30 토~월 · 시즈오카 1/15 금~월).
     같은 파일의 **1월 당일치기 실측 21칸**(삿포로 2 · 시즈오카 9 · 구마모토 6 · 다카마쓰 4)도
     함께 넣는다 — 가고시마 1/22 1칸은 원문이 "사실상 불가"로 적은 값이라 넣지 않는다.
     기존 1월 칸은 노선별 3칸(12/31 주의 1/1·1/2 출발)뿐이라 새 1월 칸과 겹치지 않는다.

읽는 곳:
  · G1 — `## 2-1.`·`## 2-2.`·`### 3-1.`~`### 3-3.` 표(노선 × 21주)와 `## 부록 A` 의 병합용 줄 420개
  · G1 요약 — `## 1. 실측 현황`(칸 수) · `## 4.`(노선별 최저가 편·직항 칸 수) · `## 5.`(금~일 평균·최고·최저)
  · JP — `### 부산–구마모토 (KMJ) · 20칸 중 20칸 실측 · 최저 215,600원` 절과 그 아래 값 줄
  · JP 요약 — `## 먼저 결론`(노선별 최저·출발일·패턴) · `## 당일치기(0박 1일) — 1월 실측`(21칸)

규칙:
  · 값은 원문 그대로. `**항공편 없음**` 은 가격이 아니라 `flights.noSale`(`nosale`)로 넣는다.
  · 원문 표와 부록 줄을 **(노선·출발일·패턴) 단위 420칸 전수** 대조한다 — 한 칸이라도 다르면 멈춘다.
  · 이미 있는 칸은 중복으로 넣지 않고, 기존 금액이 하나라도 달라지면 멈춘다(갱신 0건).
  · 호텔 538곳 · 아코르 · 다른 노선 · 기존 딜·`noSale`·패턴 정의는 **바이트 동일성**으로 보존 확인.
  · `counts`(total · byMonth · holiday · daytrip)와 2027년 1·4·5·6월 `notes`(커버리지 문구)를 다시 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_g1full_jp1.py --dry-run
    python3 tools/merge_flights_g1full_jp1.py --note "2026-11-18 KST …"
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
BASE = os.path.dirname(os.path.dirname(ROOT))
MD_G1 = os.path.join(BASE, 'data-sources', 'flights-china-new8',
                     '부산출발-중국4노선-선양다롄광저우샤먼-2_6월.md')
MD_JP = os.path.join(BASE, 'data-sources', 'flights-jp-new7',
                     '부산출발-일본7노선-1월-완결.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
G1_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN')
G1_CITY = {'SHE': '선양', 'DLC': '다롄', 'CAN': '광저우', 'XMN': '샤먼'}
G1_PATS = ('목~일', '금~일', '토~월', '금~월', '목~월')
# 원문이 말하는 값 — 파싱이 조용히 빠뜨리거나 숫자를 밀지 않았는지 대조한다
EXPECT_G1 = {
    'cells': 420, 'per_route': 105, 'per_pat': 21, 'nosale': 0, 'gaps': 0,
    'overall': (317400, 884000),          # 최저 다롄 3/4 목~월 · 최고 샤먼 2/6 토~월
    '금~일': {'SHE': (538167, 713600, 463500), 'DLC': (466567, 607100, 373300),
              'CAN': (545043, 775200, 501100), 'XMN': (555929, 758400, 464500)},
    'minmax': {'SHE': (417700, 759800), 'DLC': (317400, 663000),
               'CAN': (500700, 821600), 'XMN': (462400, 884000)},
    'direct': {'SHE': 10, 'DLC': 0, 'CAN': 3, 'XMN': 1},   # 원문 4절 '직항이 최저가인 칸'
}
JP_ROUTES = ('KMJ', 'TAK', 'MYJ', 'FSZ', 'MMY', 'CTS', 'KOJ')
# 노선 → (도시, 값 칸, 전체 칸, 1월 최저가, 최저 출발일, 최저 패턴, 당일치기 칸 수)
EXPECT_JP = {
    'KMJ': ('구마모토', 20, 20, 215600, '2027-01-28', '목~월', 6),
    'TAK': ('다카마쓰', 19, 20, 243900, '2027-01-28', '목~월', 4),
    'MYJ': ('마쓰야마', 20, 20, 264500, '2027-01-07', '목~월', 0),
    'FSZ': ('시즈오카', 19, 20, 277600, '2027-01-30', '토~월', 9),
    'MMY': ('미야코지마', 20, 20, 391300, '2027-01-07', '목~일', 0),
    'CTS': ('삿포로', 20, 20, 480600, '2027-01-14', '목~월', 2),
    'KOJ': ('가고시마', 20, 20, 524700, '2027-01-28', '목~일', 0),
}
# 원문 '당일치기(0박 1일) — 1월 실측' 절의 값. 가고시마 1/22 512,800원은 "사실상 불가"라 넣지 않는다.
JP_DAYTRIP = {
    'CTS': [('2027-01-09', 632200), ('2027-01-22', 861200)],
    'FSZ': [('2027-01-18', 305100), ('2027-01-25', 339600), ('2027-01-28', 354200),
            ('2027-01-27', 356400), ('2027-01-21', 359200), ('2027-01-16', 438600),
            ('2027-01-17', 474300), ('2027-01-23', 479500), ('2027-01-20', 485500)],
    'KMJ': [('2027-01-20', 368100), ('2027-01-18', 369700), ('2027-01-21', 424400),
            ('2027-01-27', 429000), ('2027-01-22', 474700), ('2027-01-24', 490500)],
    'TAK': [('2027-01-19', 735100), ('2027-01-25', 739700), ('2027-01-15', 784200),
            ('2027-01-22', 794500)],
}
JP_NOSALE = {('TAK', '2027-01-30', '토~월'): '가격표에도 항공편이 없습니다(항공편 없음)',
             ('FSZ', '2027-01-15', '금~월'): '가격표에도 항공편이 없습니다(항공편 없음)'}
NEW_G1, G1_DUP = 36, 384
NEW_JP_VALUES, NEW_JP_DAYTRIP = 138, 21
PREV_TOTAL = 5438
NEW_TOTAL = PREV_TOTAL + NEW_G1 + NEW_JP_VALUES + NEW_JP_DAYTRIP     # 5,633
NEW_BY_MONTH = {'2027-01': NEW_JP_VALUES + NEW_JP_DAYTRIP, '2027-04': 4,
                '2027-05': 16, '2027-06': 16}                        # 161 · 4 · 16 · 16

LINE_G1 = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · PUS–([A-Z]{3}) · (.+)$')
SEC_G1 = re.compile(r'^#{2,3} (?:2-[12]|3-[123])\. ([월화수목금토일]~[월화수목금토일])')
HEAD_G1 = re.compile(r'^\| 노선 \| (.+) \|$')
ROW_G1 = re.compile(r'^\| ([^|]+?) \(([A-Z]{3})\) \| (.+?) \|$')
COL_G1 = re.compile(r'^(\d{1,2})/(\d{1,2})~(\d{1,2})/(\d{1,2})$')
DIRECT_G1 = re.compile(r'(\d+)/105칸 직항이 최저가')
SEC4_G1 = re.compile(r'^\| ([^|]+?) \(([A-Z]{3})\) \| [^|]+ \| (.+?) \|$')

HEAD_JP = re.compile(r'^### 부산–(.+?) \(([A-Z]{3})\) · (\d+)칸 중 (\d+)칸 실측 · 최저 ([\d,]+)원$')
CELL_JP = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · .+? · (.+)$')
CONCL_JP = re.compile(r'^- \*\*(.+?)\*\*: ([\d,]+)원 — (\d{4}-\d{2}-\d{2}) 출발 (\S+)$', re.M)


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    nights = (WD[b] - WD[a]) % 7
    return (start + datetime.timedelta(days=nights)).isoformat()


def nights_of(pattern):
    return (WD[pattern[-1]] - WD[pattern[0]]) % 7


# ---------------------------------------------------------------- 표기 변환
def times(text):
    """'상하이 2h35, 총7h00' → '상하이 2시간 35분, 총 7시간' (값은 그대로)."""
    def one(m):
        h, mi = int(m.group(1)), m.group(2)
        out = '%d시간' % h
        if mi is not None and int(mi):
            out += ' %d분' % int(mi)
        return out
    text = re.sub(r'(\d{1,2})h(\d{2})?', one, text)
    return re.sub(r'총\s*(?=\d)', '총 ', text).replace('  ', ' ').strip()


def norm_desc_g1(desc):
    """G1 부록 편구성 → {via, note}."""
    d = (desc or '').strip()
    if d.startswith('경유(') and d.endswith(')'):
        return {'via': True, 'note': '경유(%s)' % times(d[5:-1])}
    if d.startswith('경유'):
        return {'via': True, 'note': times(d)}
    if d.startswith('직항'):
        return {'via': False, 'note': times(d)}
    raise SystemExit('경유/직항 표기가 아닙니다(원문 확인 필요): %r' % d)


def normalize_hhmm(inner):
    """'11:55-13:25' → '11:55→13:25'."""
    def one(m):
        return '%s→%s' % (m.group(1), m.group(2))
    return re.sub(r'(\d{1,2}:\d{2})-(\d{1,2}:\d{2})', one, inner)


def norm_desc_jp(desc):
    """일본 원문 편구성 → {via, note, alt}."""
    d = (desc or '').strip()
    alt = None
    parts = [p.strip() for p in d.split(' / ')]
    if len(parts) == 2 and parts[1].startswith('직항최저'):
        alt = int(re.sub(r'[^\d]', '', parts[1]))
        d = parts[0]
    short = ''
    if d.endswith(' 9석 미만'):
        d, short = d[:-len(' 9석 미만')].strip(), ' · 잔여 9석 미만'
    m = re.fullmatch(r'직항\((.*)\)', d)
    if m:
        inner = normalize_hhmm(m.group(1))
        note = '직항 ' + inner.replace(', ', ' · ')
        return {'via': False, 'note': note + short, 'alt': alt}
    m = re.fullmatch(r'경유\((.*)\)', d)
    if m:
        note = '경유(%s)' % times(m.group(1))
        return {'via': True, 'note': note + short, 'alt': alt}
    if d.startswith('직항'):
        return {'via': False, 'note': times(d) + short, 'alt': alt}
    if d.startswith('경유'):
        return {'via': True, 'note': times(d) + short, 'alt': alt}
    if d in ('직항/경유 미확인', '미확인'):
        return {'via': None, 'note': None, 'alt': alt}
    raise SystemExit('일본 원문 편구성 표기가 예상과 다릅니다: %r' % desc)


# ---------------------------------------------------------------- 파싱: 중국 G1
def parse_g1_appendix(text):
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('- 20'):
            continue
        m = LINE_G1.match(line)
        if not m:
            raise SystemExit('G1 부록 줄 형식이 예상과 다릅니다: %s' % line)
        date, pattern, code, body = m.groups()
        if code not in G1_ROUTES:
            raise SystemExit('G1 에 없는 노선입니다: %s' % line)
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
    return values


def parse_g1_tables(text):
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
        if code not in G1_ROUTES or city.strip() != G1_CITY[code]:
            raise SystemExit('G1 노선 이름이 다릅니다: %s' % line)
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
                raise SystemExit('%s %s 칸이 절 제목(%s)과 다릅니다' % (code, start.isoformat(), section))
            key = (code, start.isoformat(), pat)
            if key in out:
                raise SystemExit('G1 표에 같은 칸이 두 번 있습니다: %s' % (key,))
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


def summary_g1(text, values):
    bad = []
    grid = int(re.search(r'\| 전체 격자 \| \*\*([\d,]+)칸\*\*', text).group(1).replace(',', ''))
    done = int(re.search(r'\| 실측 완료 \| \*\*([\d,]+)칸\*\*', text).group(1).replace(',', ''))
    zero = int(re.search(r'\| 판매편 없음\(0건\) \| \*\*([\d,]+)칸\*\*', text).group(1).replace(',', ''))
    rest = int(re.search(r'\| 미조회 \| \*\*([\d,]+)칸\*\*', text).group(1).replace(',', ''))
    if (grid, done, zero, rest, len(values)) != (420, 420, 0, 0, 420):
        bad.append('G1 요약 칸 수(격자 %d·실측 %d·0건 %d·미조회 %d·파싱 %d)'
                   % (grid, done, zero, rest, len(values)))
    lo = int(re.search(r'- 전체 최저 \*\*([\d,]+)원\*\*', text).group(1).replace(',', ''))
    hi = int(re.search(r'- 전체 최고 \*\*([\d,]+)원\*\*', text).group(1).replace(',', ''))
    prices = [d['price'] for d in values.values()]
    if (min(prices), max(prices)) != (lo, hi) or (lo, hi) != EXPECT_G1['overall']:
        bad.append('G1 전체 최저·최고 %s (요약 %s / 기대 %s)'
                   % ((min(prices), max(prices)), (lo, hi), EXPECT_G1['overall']))
    if values[('DLC', '2027-03-04', '목~월')]['price'] != 317400:
        bad.append('G1 전체 최저 칸(다롄 3/4 목~월)이 317,400원이 아닙니다')
    if values[('XMN', '2027-02-06', '토~월')]['price'] != 884000:
        bad.append('G1 전체 최고 칸(샤먼 2/6 토~월)이 884,000원이 아닙니다')
    for code in G1_ROUTES:
        m = re.search(r'- \*\*%s 금~일\*\* 평균 ([\d,]+)원 · 최고 ([\d,]+)원[^·]*· 최저 ([\d,]+)원'
                      % G1_CITY[code], text)
        if not m:
            raise SystemExit('G1 5절 금~일 요약을 찾지 못했습니다: %s' % code)
        avg, top, bottom = (int(x.replace(',', '')) for x in m.groups())
        ps = [d['price'] for (c, _, p), d in values.items() if c == code and p == '금~일']
        calc = round(sum(ps) / len(ps))
        if (calc, max(ps), min(ps)) != (avg, top, bottom):
            bad.append('G1 %s 금~일 평균·최고·최저 계산 %s (요약 %s)'
                       % (code, (calc, max(ps), min(ps)), (avg, top, bottom)))
        if (avg, top, bottom) != EXPECT_G1['금~일'][code]:
            bad.append('G1 %s 금~일 요약 %s (기대 %s)'
                       % (code, (avg, top, bottom), EXPECT_G1['금~일'][code]))
        per = [d['price'] for (c, _, _), d in values.items() if c == code]
        if (min(per), max(per)) != EXPECT_G1['minmax'][code]:
            bad.append('G1 %s 최저·최고 %s (기대 %s)'
                       % (code, (min(per), max(per)), EXPECT_G1['minmax'][code]))
    # 4절 — 노선별 '직항이 최저가인 칸' 수
    for m in SEC4_G1.finditer(text):
        city, code, last = m.groups()
        if code not in G1_ROUTES:
            continue
        dm = DIRECT_G1.search(last)
        want = int(dm.group(1)) if dm else 0
        got = sum(1 for (c, _, _), d in values.items() if c == code and d.get('via') is False)
        if got != want or want != EXPECT_G1['direct'][code]:
            bad.append('G1 %s 직항 최저 칸 %d (원문 %d / 기대 %d)'
                       % (code, got, want, EXPECT_G1['direct'][code]))
    return bad


# ---------------------------------------------------------------- 파싱: 일본 1월
def parse_jp(text):
    values, nosale, heads, code = {}, {}, {}, None
    for raw in text.splitlines():
        line = raw.strip()
        m = HEAD_JP.match(line)
        if m:
            city, code, total, got, low = m.groups()
            if code not in EXPECT_JP:
                raise SystemExit('예상 밖 노선: %s' % line)
            heads[code] = (city, int(total), int(got), int(low.replace(',', '')))
            continue
        if line.startswith('## ') or line.startswith('### '):
            code = None
            continue
        if not code:
            continue
        m = CELL_JP.match(line)
        if not m:
            continue
        date, pat, body = m.groups()
        key = (code, date, pat)
        if key in values or key in nosale:
            raise SystemExit('%s %s %s 중복' % key)
        if body.startswith('**항공편 없음**'):
            nosale[key] = {'code': code, 'date': date, 'back': back_date(date, pat),
                           'pattern': pat, 'note': '가격표에도 항공편이 없습니다(항공편 없음)'}
            continue
        fields = [f.strip() for f in body.split(' · ')]
        pm = re.fullmatch(r'([\d,]+)원', fields[0])
        if not pm:
            raise SystemExit('일본 금액을 읽지 못했습니다: %s' % line)
        deal = {'date': date, 'back': back_date(date, pat), 'pattern': pat,
                'price': int(pm.group(1).replace(',', ''))}
        airline = fields[1] if len(fields) > 1 else ''
        if airline.startswith('항공사 미확인'):
            deal.update({'via': None, 'src': '가격표',
                         'note': '가격표 실측 · 항공사·직항/경유 미확인'})
        else:
            info = norm_desc_jp(' · '.join(fields[2:]))
            deal['airline'] = airline
            deal['src'] = '실시간'
            if info['via'] is not None:
                deal['via'] = info['via']
            if info['note']:
                deal['note'] = info['note']
            if info['alt']:
                deal['alt'] = info['alt']
                deal['note'] = deal.get('note', '') + ' · 직항 최저 %s원' % format(info['alt'], ',')
        values[key] = deal
    concl = {m.group(1): (int(m.group(2).replace(',', '')), m.group(3), m.group(4))
             for m in CONCL_JP.finditer(text)}
    return values, nosale, heads, concl


def _concl_of(concl, city):
    for name, val in concl.items():
        if name.startswith(city):
            return val
    return None


def checks_jp(text, values, nosale, heads, concl):
    bad = []
    for code, (city, got, total, low, lo_date, lo_pat, days) in EXPECT_JP.items():
        head = heads.get(code)
        if not head:
            bad.append('일본 %s 절 머리를 찾지 못했습니다' % code)
            continue
        if (not head[0].startswith(city) or head[1] != total or head[2] != got
                or head[3] != low):
            bad.append('일본 %s 절 머리 %s (기대 %s %d칸 중 %d칸 · 최저 %d)'
                       % (code, head, city, total, got, low))
        vals = {k: v for k, v in values.items() if k[0] == code}
        nos = {k: v for k, v in nosale.items() if k[0] == code}
        if len(vals) != got:
            bad.append('일본 %s 값 %d칸 (원문 %d칸)' % (code, len(vals), got))
        if len(vals) + len(nos) != total:
            bad.append('일본 %s 값+항공편없음 %d칸 (원문 %d칸)' % (code, len(vals) + len(nos), total))
        if sum(1 for _ in JP_DAYTRIP.get(code, [])) != days:
            bad.append('일본 %s 당일치기 %d칸 (기대 %d칸)'
                       % (code, len(JP_DAYTRIP.get(code, [])), days))
        ps = [(d['price'], d['date'], d['pattern']) for d in vals.values()]
        hit, hd, hp = min(ps)
        if (hit, hd, hp) != (low, lo_date, lo_pat):
            bad.append('일본 %s 최저 칸 %s (원문 %s)' % (code, (hit, hd, hp), (low, lo_date, lo_pat)))
        if _concl_of(concl, city) != (low, lo_date, lo_pat):
            bad.append('일본 %s 결론 줄 %s (기대 %s)'
                       % (city, _concl_of(concl, city), (low, lo_date, lo_pat)))
        # 4주 × 5패턴 = 20칸이 값 또는 항공편 없음으로 다 찼는지
        weeks = ('2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
        for thu in weeks:
            for pat in ('금~일', '토~월', '목~일', '금~월', '목~월'):
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
                if (code, dt, pat) not in values and (code, dt, pat) not in nosale:
                    bad.append('일본 %s %s %s 칸이 비어 있습니다' % (code, dt, pat))
    if len(values) != NEW_JP_VALUES or len(nosale) != len(JP_NOSALE):
        bad.append('일본 값 %d칸 + 항공편없음 %d칸 (기대 %d + %d)'
                   % (len(values), len(nosale), NEW_JP_VALUES, len(JP_NOSALE)))
    if set(nosale) != set(JP_NOSALE):
        bad.append('일본 항공편 없음 칸이 원문과 다릅니다: %s' % sorted(set(nosale) ^ set(JP_NOSALE)))
    # 원문 완료 범위 문장
    if '7개 노선 × 4주 × 5패턴 = **140칸 전부 실측(100%)**' not in text:
        bad.append('원문 완료 범위 문장을 찾지 못했습니다')
    # 당일치기 절 — 손으로 적은 값이 원문에 실제로 있는지 확인
    day = text.split('## 당일치기(0박 1일) — 1월 실측', 1)
    if len(day) != 2:
        raise SystemExit('원문에서 1월 당일치기 절을 찾지 못했습니다')
    body = day[1]
    for code, rows in JP_DAYTRIP.items():
        for d, price in rows:
            md, dd = int(d[5:7]), int(d[8:10])
            seg = '%d/%d' % (md, dd)
            if seg not in body or format(price, ',') not in body:
                bad.append('일본 당일치기 %s %s %s원이 원문에 없습니다' % (code, d, format(price, ',')))
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


JP_META_ADD = {
    'CTS': (' 1월은 1/9 632,200원 · 1/22 861,200원 두 날짜만 조회했고 둘 다 표시 최저 조합(현지 약 1시간)입니다.'),
    'KMJ': (' 1월은 1/15~1/29 가운데 6일 성립(368,100~490,500원 · 직항 11:55 출국·14:30 귀국 조합).'),
    'FSZ': (' 1월은 1/15~1/29 가운데 9일 성립(305,100~485,500원) — 1월 직항은 09:50 출국·12:00 귀국이라 현지 20분입니다.'),
    'TAK': (' 1월은 1/15~1/29 가운데 4일만 성립하고 전부 경유입니다(735,100~794,500원 · 대한항공이 진에어를 운항, 서울 경유 총 3시간 50분).'),
    'KOJ': (' 1월에는 1/15~1/29 가운데 1/22만 성립(512,800원)했지만 출국 직항이 15:55뿐이라 실사용이 어려워 달력에 넣지 않았습니다.'),
    'MYJ': (' 1월(1/15~1/29)에도 같은 날 왕복이 잡히지 않습니다.'),
    'MMY': (' 1월(1/15~1/29)에도 귀국 직항이 없어 같은 날 왕복이 잡히지 않습니다.'),
}


def _bd(counter):
    """패턴별 칸 수를 화면 문구 순서(금~일·토~월·목~일·금~월·목~월)로 적는다."""
    return ' · '.join('%s %d' % (p, counter[p])
                      for p in ('금~일', '토~월', '목~일', '금~월', '목~월') if counter.get(p))


def notes_update(fl, nums):
    """월별 커버리지 문구 — nums[월] = (G1 칸수·패턴카운터, G2 칸수·패턴카운터, 황산 0건 칸)."""
    g1_4, g2_4, _ = nums['2027-04']
    g1_5, g2_5, txn_5 = nums['2027-05']
    g1_6, g2_6, txn_6 = nums['2027-06']
    fl['notes']['2027-01'] = (
        '기존 24개 노선은 1월 4주 × 5패턴 480칸을 전부 실측했습니다. 중국 신규 8개 노선은 9주 × 5패턴 '
        '완본의 1월분(1/1·1/2 출발 포함)을 담았고 — 선양·다롄·광저우·샤먼 92칸, 연길·장가계·구이린·황산 '
        '78칸(황산 판매편 0건 포함) — 필리핀 4개 노선 92칸 · 동남아 4개 노선 92칸입니다. '
        '일본 7개 노선은 1월 4주 × 5패턴 **140칸을 완결**했습니다(값 138칸 + 항공편 없음 2칸 — '
        '다카마쓰 1/30 토~월 · 시즈오카 1/15 금~월). 이 달 이 7개 노선 최저는 '
        '구마모토 1/28~2/1 목~월 215,600원(이스타항공 직항), 다음이 다카마쓰 1/28~2/1 243,900원 · '
        '마쓰야마 1/7~1/11 264,500원이고, 가장 비싼 노선은 가고시마(최저 524,700원)입니다. '
        '당일치기 1월 실측 21칸(삿포로 2 · 시즈오카 9 · 구마모토 6 · 다카마쓰 4)도 함께 넣었습니다.')
    fl['notes']['2027-04'] = (
        '중국 신규 8개 노선의 2027년 4월을 실측했습니다 — 선양·다롄·광저우·샤먼은 이 달 %d칸(%s), '
        '연길·장가계·구이린·황산은 %d칸(%s · 황산 금~일 판매편 0건 포함)입니다. 이번에 선양·다롄·광저우·샤먼의 '
        '4/29~6/24 목~월(4박) 9주를 채워 2027년 2~6월 **420/420칸(100%%)** 을 완주했습니다. '
        '연길·장가계·구이린·황산은 3·4박 가운데 목~월(4박)만 미조회(—)입니다.'
        % (sum(g1_4.values()), _bd(g1_4), sum(g2_4.values()), _bd(g2_4)))
    fl['notes']['2027-05'] = (
        '중국 신규 8개 노선은 2박(금~일·토~월)에 목~일·금~월·목~월까지 21주를 조사해 선양·다롄·광저우·샤먼이 '
        '**420/420칸(100%%)** 입니다 — 이 달 %d칸(%s). 연길·장가계·구이린·황산은 이 달 %d칸(%s) '
        '+ 황산 판매편 0건 %d칸이고, 목~월(4박)만 미조회(—)입니다. 필리핀 4개 노선은 2027년 2~6월 420칸 '
        '전부 실측(이 달 84칸 · 최저 마닐라 5/7 금~월 411,918원), 동남아 4개 노선도 420칸 전부 실측'
        '(이 달 84칸 · 최저 푸꾸옥 5/20 목~월 292,051원 직항)입니다.'
        % (sum(g1_5.values()), _bd(g1_5), sum(g2_5.values()), _bd(g2_5), txn_5))
    fl['notes']['2027-06'] = (
        '중국 신규 8개 노선은 2박에 3·4박까지 21주를 조사해 선양·다롄·광저우·샤먼이 **420/420칸(100%%)** 입니다 — '
        '이 달 %d칸(%s). 연길·장가계·구이린·황산은 이 달 %d칸(%s) + 황산 판매편 0건 %d칸이고 '
        '목~월(4박)만 미조회(—)입니다. 필리핀 4개 노선 80칸(최저 클락 6/18 금~월 409,800원), 동남아 4개 노선 '
        '80칸(최저 푸꾸옥 6/3 목~월 292,051원)을 전부 실측했고, 기존 24개 노선의 6월 131칸'
        '(주말형 124 · 당일치기 7)도 함께 들어 있습니다.'
        % (sum(g1_6.values()), _bd(g1_6), sum(g2_6.values()), _bd(g2_6), txn_6))


def main(argv):
    ap = argparse.ArgumentParser(description='중국 G1 2~6월 완결 + 일본 7노선 1월 완결 → master_db.json 병합')
    ap.add_argument('--g1', default=MD_G1)
    ap.add_argument('--jp', default=MD_JP)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    t1 = open(args.g1, encoding='utf-8').read()
    t2 = open(args.jp, encoding='utf-8').read()

    g1 = parse_g1_appendix(t1)
    tab1, seen1 = parse_g1_tables(t1)
    jp, jp_ns, jp_heads, jp_concl = parse_jp(t2)

    bad = []
    # 1) G1 부록 ↔ 표 전수 대조
    if len(g1) != EXPECT_G1['cells'] or seen1 != 420 or len(tab1) != 420:
        bad.append('G1 값 %d칸 · 표 %d칸/%d (기대 420)' % (len(g1), seen1, len(tab1)))
    mismatch = []
    for key, got in tab1.items():
        if key not in g1:
            mismatch.append('G1 %s 부록에 없음(표 %s)' % (key, got))
        elif got != g1[key]['price']:
            mismatch.append('G1 %s 부록 %s / 표 %s' % (key, g1[key]['price'], got))
    if set(g1) - set(tab1):
        mismatch.append('G1 부록에만 있는 칸 %d개' % len(set(g1) - set(tab1)))
    if mismatch:
        bad.append('G1 부록·표 불일치 %d건: %s' % (len(mismatch), mismatch[:6]))
    for code in G1_ROUTES:
        per = {p: sum(1 for (c, _, pp) in g1 if c == code and pp == p) for p in G1_PATS}
        if set(per) != set(G1_PATS) or any(v != EXPECT_G1['per_pat'] for v in per.values()):
            bad.append('G1 %s 패턴별 칸 수 %s (기대 각 %d)' % (code, per, EXPECT_G1['per_pat']))
    for key in g1:
        if nights_of(key[2]) != (datetime.date.fromisoformat(g1[key]['back']) -
                                 datetime.date.fromisoformat(key[1])).days:
            bad.append('G1 %s 귀국일이 박수와 다릅니다' % (key,))
    bad.extend(summary_g1(t1, g1))

    # 2) 일본 1월
    bad.extend(checks_jp(t2, jp, jp_ns, jp_heads, jp_concl))

    print('  G1 값 %d칸(노선별 105 · 패턴별 21) · 표 대조 %d칸 · 0건 0칸' % (len(g1), seen1))
    print('  JP 값 %d칸 + 항공편 없음 %d칸 + 당일치기 %d칸 = %d칸'
          % (len(jp), len(jp_ns), sum(len(v) for v in JP_DAYTRIP.values()),
             len(jp) + len(jp_ns) + sum(len(v) for v in JP_DAYTRIP.values())))
    for code in JP_ROUTES:
        ps = [d['price'] for k, d in jp.items() if k[0] == code]
        print('    %s %d/%d칸 최저 %s원' % (code, len(ps), EXPECT_JP[code][2],
                                          format(min(ps), ',')))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    # 3) 당일치기 셀 생성
    for code, rows in JP_DAYTRIP.items():
        for date, price in rows:
            pat = '%s~%s' % tuple('일월화수목금토'[datetime.date.fromisoformat(date).isoweekday() % 7]
                                  for _ in range(2))
            jp[(code, date, pat)] = {'date': date, 'back': date, 'pattern': pat, 'price': price,
                                     'via': None, 'src': '실시간',
                                     'note': '당일치기(0박) 표시 최저 · 항공사·직항/경유 미확인'}

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    touched = set(G1_ROUTES) | set(JP_ROUTES)
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in touched],
                              ensure_ascii=False, sort_keys=True)
    before_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False,
                                                                     sort_keys=True)
                     for r in fl['routes'] if r['code'] in touched for d in r['deals']}
    before_nosale = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_meta = {r['code']: json.dumps(r.get('daytrip'), ensure_ascii=False, sort_keys=True)
                   for r in fl['routes'] if r['code'] not in set(JP_ROUTES)}
    before_notes = {k: v for k, v in fl['notes'].items()
                    if k not in ('2027-01', '2027-04', '2027-05', '2027-06')}
    before_patterns = json.dumps(fl['patterns'], ensure_ascii=False)

    added_g1, dup_g1, _ = merge(master, g1, {})
    added_jp, dup_jp, new_ns = merge(master, jp, jp_ns)
    if len(added_g1) != NEW_G1 or len(dup_g1) != G1_DUP:
        raise SystemExit('G1 신규 %d칸·중복 %d칸 (기대 %d·%d)'
                         % (len(added_g1), len(dup_g1), NEW_G1, G1_DUP))
    if len(added_jp) != NEW_JP_VALUES + NEW_JP_DAYTRIP or len(dup_jp) != 0:
        raise SystemExit('JP 신규 %d칸·중복 %d칸 (기대 %d·0)'
                         % (len(added_jp), len(dup_jp), NEW_JP_VALUES + NEW_JP_DAYTRIP))
    if len(new_ns) != len(JP_NOSALE):
        raise SystemExit('JP 항공편 없음 신규 %d칸 (기대 %d칸)' % (len(new_ns), len(JP_NOSALE)))

    # 4) 당일치기 메타에 1월 실측을 덧붙인다(12월 사실은 그대로)
    for r in fl['routes']:
        if r['code'] in JP_META_ADD:
            add = JP_META_ADD[r['code']]
            if add.strip() not in (r['daytrip'].get('note') or ''):
                r['daytrip']['note'] = (r['daytrip'].get('note') or '').rstrip() + add

    # 5) 월별 notes — 이번 병합 뒤 실제 칸 수로 계산해 넣는다
    def month_count(month, codes):
        return sum(1 for r in fl['routes'] if r['code'] in codes for d in r['deals']
                   if d['date'][:7] == month)
    g2 = ('YNJ', 'DYG', 'KWL', 'TXN')
    txn = {m: sum(1 for n in fl['noSale'] if n['code'] == 'TXN' and n['date'][:7] == m)
           for m in ('2027-04', '2027-05', '2027-06')}
    def pat_counter(month, codes):
        out = {}
        for r in fl['routes']:
            if r['code'] not in codes:
                continue
            for d in r['deals']:
                if d['date'][:7] == month:
                    out[d['pattern']] = out.get(d['pattern'], 0) + 1
        return out
    notes_update(fl, {m: (pat_counter(m, G1_ROUTES), pat_counter(m, g2), txn[m])
                      for m in ('2027-04', '2027-05', '2027-06')})

    # 6) 보존 검증
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
                      if (n['code'], n['date'], n['pattern']) not in set(new_ns)], key=keyf)
    if [keyf(n) for n in kept_ns] != [keyf(n) for n in old_ns]:
        raise SystemExit('기존 판매편 0건 기록이 바뀌었습니다.')
    after_meta = {r['code']: json.dumps(r.get('daytrip'), ensure_ascii=False, sort_keys=True)
                  for r in fl['routes'] if r['code'] not in set(JP_ROUTES)}
    if after_meta != before_meta:
        raise SystemExit('다른 노선의 daytrip 메타가 바뀌었습니다.')
    if {k: v for k, v in fl['notes'].items()
            if k not in ('2027-01', '2027-04', '2027-05', '2027-06')} != before_notes:
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
                             datetime.timedelta(days=nights_of(d['pattern']))).isoformat():
                raise SystemExit('%s %s 귀국일이 박수와 다릅니다' % (r['code'], d['date']))

    print('G1 신규 %d칸(중복 %d칸) · JP 신규 %d칸 + 항공편 없음 %d칸'
          % (len(added_g1), len(dup_g1), len(added_jp), len(new_ns)))
    print('총 %d건 → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, fl['counts']['total'],
        fl['counts']['total'] - fl['counts']['daytrip'], fl['counts']['daytrip']))
    print('월별: %s' % fl['counts']['byMonth'])
    print('노선별: %s' % ', '.join('%s %d' % (r['code'], len(r['deals'])) for r in fl['routes']
                                  if r['code'] in touched))
    print('noSale %d건 (신규 %d건)' % (len(fl['noSale']), len(new_ns)))

    for m in ('2027-01', '2027-04', '2027-05', '2027-06'):
        if '%d' in fl['notes'][m] or '%s' in fl['notes'][m]:
            raise SystemExit('%s notes 에 서식 문자가 남았습니다: %s' % (m, fl['notes'][m]))
        print('  note %s: %s' % (m, fl['notes'][m][:80] + '…'))

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


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
