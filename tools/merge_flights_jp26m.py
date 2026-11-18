#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)
2027년 2~6월(21주 × 7패턴 = 1,029칸)** 실측을 `data/master_db.json` 의 `flights` 에 병합한다.

원본: `data-sources/flights-jp-new7/`
  · `0-pus_jp_flights_2027_02_06_summary.md` — 노선별·월별·패턴별 요약, 1,029칸 상태 합계
  · `1-pus_jp_flights_2027_02_06_part1.md` — 구마모토·가고시마·시즈오카·마쓰야마 (월별 5패턴 표 + 당일치기)
  · `2-pus_jp_flights_2027_02_06_part2.md` — 다카마쓰·미야코지마·삿포로
  · `3-pus_jp_flights_2027_02_06_matrix.csv` — 1,029줄 전체 매트릭스(값의 원본)

값의 원본은 CSV(칸 단위)이고, md 3건은 **전수 대조용**으로만 쓴다:
  · 절 머리 `기간 최저`·`직항 최저`·`직항 요금이 잡히는 마지막 출발일` — CSV 최저 칸과 대조
  · 월별 5패턴 표(2~6월) — 그 달·그 패턴의 CSV 최저가·출발일·항공사·직항/경유·소요를 대조
  · 월별 당일치기 줄 — 그 달 0박 칸의 상태별 개수와 실측값을 대조
  · 요약 md 의 노선별 기간 최저·월별 최저·패턴별 최저·당일치기 표·노선별 특징·1,029칸 합계 문장

규칙:
  · `측정` 523칸만 `routes[].deals` 로 넣는다(값은 CSV 원문 그대로, 반올림 없음).
  · `0건` 303칸은 `noSale` 의 `status='nosale'`, `요금미공개` 98칸은 `status='nofare'` 로 남긴다.
  · `미조회` 105칸은 **아무것도 넣지 않는다**(추정 금지) — 앱에서 빈칸(—)이 된다.
  · 이미 있는 칸은 건드리지 않는다(중복·금액 충돌이면 멈춘다). 기존 12월·1월 값은 그대로 둔다.
  · 호텔 538곳 · 아코르 SNU 43줄 · 출처 목록 · 패턴 정의 · 다른 40개 노선 · 기존 `noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)와 2027-02~06 `notes`(plain text — `**` 금지)를
    실제 데이터에서 다시 계산해 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jp26m.py --dry-run
    python3 tools/merge_flights_jp26m.py --note "..."
"""
import argparse
import collections
import csv
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-jp-new7'))
SUMMARY = os.path.join(SRC, '0-pus_jp_flights_2027_02_06_summary.md')
PART1 = os.path.join(SRC, '1-pus_jp_flights_2027_02_06_part1.md')
PART2 = os.path.join(SRC, '2-pus_jp_flights_2027_02_06_part2.md')
MATRIX = os.path.join(SRC, '3-pus_jp_flights_2027_02_06_matrix.csv')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
CODES = ('KMJ', 'KOJ', 'FSZ', 'MYJ', 'TAK', 'MMY', 'CTS')
CITY = {'KMJ': '구마모토', 'KOJ': '가고시마', 'FSZ': '시즈오카', 'MYJ': '마쓰야마',
        'TAK': '다카마쓰', 'MMY': '미야코지마', 'CTS': '삿포로'}
NAME2CODE = {v: k for k, v in CITY.items()}
WK = ('금~일', '토~월', '목~일', '금~월', '목~월')
DY = ('토~토', '일~일')
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4,
              '토~토': 0, '일~일': 0}
THU = tuple((datetime.date(2027, 2, 4) + datetime.timedelta(days=7 * i)).isoformat()
            for i in range(21))
MONTHS = ('2027-02', '2027-03', '2027-04', '2027-05', '2027-06')
STATUS = {'측정': 'deals', '0건': 'nosale', '요금미공개': 'nofare', '미조회': 'blank'}
EXPECT = {'deals': 523, 'nosale': 303, 'nofare': 98, 'blank': 105}
EXPECT_TOTAL = 6599            # 6,076 + 523
EXPECT_DAYTRIP = 318           # 275 + 43
EXPECT_HOLIDAY = 185           # 172 + 2/4 출발 13칸
EXPECT_BY_MONTH = {'2027-02': 921, '2027-03': 926, '2027-04': 461,
                   '2027-05': 423, '2027-06': 530}
EXPECT_H2 = {'weekend': 1501, 'day': 95}
ROUTE_DEALS = {'KMJ': 95, 'KOJ': 149, 'FSZ': 83, 'MYJ': 118,
               'TAK': 152, 'MMY': 69, 'CTS': 191}
# 원문(요약)이 말하는 노선별 기간 최저 — (금액, 출발일, 패턴)
EXPECT_LOW = {'KMJ': (476800, '2027-03-04', '목~월'), 'KOJ': (508800, '2027-03-04', '목~월'),
              'FSZ': (274400, '2027-02-04', '목~일'), 'MYJ': (271700, '2027-03-04', '목~월'),
              'TAK': (226400, '2027-03-18', '목~월'), 'MMY': (878800, '2027-02-11', '목~일'),
              'CTS': (374303, '2027-03-19', '금~일')}
# 노선별 상태(주말형 5패턴 / 당일치기) — 요약 md '노선별 특징'·'당일치기' 표와 같은 수
EXPECT_STATUS = {
    'KMJ': {'weekend': {'deals': 40, 'nosale': 0, 'nofare': 61, 'blank': 4},
            'day': {'deals': 3, 'nosale': 0, 'nofare': 0, 'blank': 39}},
    'KOJ': {'weekend': {'deals': 102, 'nosale': 0, 'nofare': 0, 'blank': 3},
            'day': {'deals': 2, 'nosale': 31, 'nofare': 0, 'blank': 9}},
    'FSZ': {'weekend': {'deals': 33, 'nosale': 68, 'nofare': 0, 'blank': 4},
            'day': {'deals': 0, 'nosale': 24, 'nofare': 0, 'blank': 18}},
    'MYJ': {'weekend': {'deals': 73, 'nosale': 7, 'nofare': 25, 'blank': 0},
            'day': {'deals': 0, 'nosale': 20, 'nofare': 11, 'blank': 11}},
    'TAK': {'weekend': {'deals': 103, 'nosale': 0, 'nofare': 0, 'blank': 2},
            'day': {'deals': 0, 'nosale': 33, 'nofare': 0, 'blank': 9}},
    'MMY': {'weekend': {'deals': 24, 'nosale': 81, 'nofare': 0, 'blank': 0},
            'day': {'deals': 0, 'nosale': 39, 'nofare': 0, 'blank': 3}},
    'CTS': {'weekend': {'deals': 105, 'nosale': 0, 'nofare': 0, 'blank': 0},
            'day': {'deals': 38, 'nosale': 0, 'nofare': 1, 'blank': 3}},
}
# 경유지 표기(원문) → 앱에 쓰는 짧은 이름
PLACE = (('인천', '인천'), ('후쿠오카', '후쿠오카'), ('나하', '오키나와'), ('도쿄', '도쿄'),
         ('간사이', '오사카'), ('타오위안', '타이베이'), ('서울', '서울'))

PERIOD = re.compile(r'^기간 최저 🔴 \*\*([\d.]+)만원\*\* · (\d{2}-\d{2})~(\d{2}-\d{2})'
                    r'\(([월화수목금토일]~[월화수목금토일])\) · (.+)$')
DIRECT = re.compile(r'^직항 최저 🔴 \*\*([\d.]+)만원\*\* \((.+?), (.+?), '
                    r'(\d{2}-\d{2})~(\d{2}-\d{2})\(([월화수목금토일]~[월화수목금토일])\)\)$')
LASTSALE = re.compile(r'^직항 요금이 잡히는 마지막 출발일: \*\*(\d{2}-\d{2})\*\*')
MHEAD = re.compile(r'^\*\*(\d+)월\*\*$')
TROW = re.compile(r'^\| ([월화수목금토일]~[월화수목금토일]) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|$')
TDATE = re.compile(r'^([\d.]+)만\*\* \((\d{2}-\d{2})~(\d{2}-\d{2})\)$')
DAYLINE = re.compile(r'^당일치기(?:: |\(([월화수목금토일]~[월화수목금토일])\) )')
DAYVAL = re.compile(r'^당일치기\(([월화수목금토일]~[월화수목금토일])\) 🔴 \*\*([\d.]+)만원\*\* · '
                    r'(\d{2}-\d{2})(?: \((\d)박\))? · (.+)$')
CNT = re.compile(r'(0건|미조회|요금 미공개)\s*(\d+)')


def won(text):
    """'🔴 **47.7만**' / '47.7만원' → 477000 (0.1만 단위 반올림 값)."""
    return round(float(text) * 10000)


def md_date(mm_dd):
    return '2027-' + mm_dd


def close(md_won, price):
    """md 는 0.1만(1,000원) 단위로 반올림돼 있다 — 500원 이내면 같은 값."""
    return abs(md_won - price) <= 500


def place_short(raw):
    out = []
    for part in _split_places(raw):
        hit = next((short for key, short in PLACE if key in part), None)
        if hit is None:
            raise SystemExit('경유지 표기를 해석하지 못했습니다: %r' % raw)
        out.append(hit)
    return '·'.join(out)


def _split_places(raw):
    return [p.strip() for p in raw.split(',') if p.strip()]


def deal_note(stops, places, dur):
    if stops == 0:
        return '직항 · %s' % dur
    return '경유 %d회 %s · %s' % (stops, places, dur)


# ---------------------------------------------------------------- CSV
def read_csv():
    """CSV 1,029줄 → {(code, date, pattern): {status, price, ...}} + 격자 검사."""
    rows = list(csv.DictReader(open(MATRIX, encoding='utf-8-sig')))
    cells = {}
    for r in rows:
        code = r['노선']
        if code not in CODES:
            raise SystemExit('예상 밖 노선: %s' % code)
        status = r['상태']
        if status not in STATUS:
            raise SystemExit('예상 밖 상태: %s' % status)
        date, pat = r['출발'], r['패턴']
        key = (code, date, pat)
        if key in cells:
            raise SystemExit('CSV 중복 칸: %s' % (key,))
        if CITY[code] != r['도시']:
            raise SystemExit('%s 도시 이름이 다릅니다: %s' % (code, r['도시']))
        d = datetime.date.fromisoformat(date)
        back = datetime.date.fromisoformat(r['도착'])
        if d.isoweekday() % 7 != WD[pat[0]]:
            raise SystemExit('%s %s 의 요일이 패턴과 다릅니다' % (key, date))
        if (back - d).days != PAT_NIGHTS[pat]:
            raise SystemExit('%s 박수가 패턴과 다릅니다' % (key,))
        thu = r['주(목요일)']
        if d != datetime.date.fromisoformat(thu) + datetime.timedelta(
                days=(WD[pat[0]] - WD['목']) % 7):
            raise SystemExit('%s 가 %s 주차 창 밖입니다' % (key, thu))
        cell = {'status': status, 'kind': STATUS[status], 'back': r['도착']}
        if status == '측정':
            price = int(r['최저가(원)'])
            if price <= 0:
                raise SystemExit('%s 금액이 0 이하입니다' % (key,))
            stops = int(r['경유횟수'])
            raw_via = r['경유지'].strip()
            if stops == 0:
                if raw_via:
                    raise SystemExit('%s 직항인데 경유지가 있습니다: %r' % (key, raw_via))
                places = ''
            else:
                if len(_split_places(raw_via)) != stops:
                    raise SystemExit('%s 경유 횟수와 경유지 수가 다릅니다: %s %r'
                                     % (key, stops, raw_via))
                places = place_short(raw_via)
            if not r['항공사'].strip() or not r['소요시간'].strip():
                raise SystemExit('%s 항공사·소요시간이 비었습니다' % (key,))
            cell.update({'price': price, 'airline': r['항공사'].strip(),
                         'stops': stops, 'places': places,
                         'dur': r['소요시간'].strip()})
            direct = int(r['직항최저(원)']) if r['직항최저(원)'].strip() else None
            if direct is not None:
                if stops == 0 and direct != price:
                    raise SystemExit('%s 직항 칸의 직항최저가 최저가와 다릅니다' % (key,))
                if stops and direct < price:
                    raise SystemExit('%s 직항최저가 최저가보다 쌉니다: %d < %d'
                                     % (key, direct, price))
                cell['direct'] = direct
        cells[key] = cell
    grid = {(c, (datetime.date.fromisoformat(t) + datetime.timedelta(
        days=(WD[p[0]] - WD['목']) % 7)).isoformat(), p)
        for c in CODES for t in THU for p in WK + DY}
    if set(cells) != grid:
        raise SystemExit('CSV 격자 %d칸 (기대 %d칸) 차이: %s'
                         % (len(cells), len(grid), sorted(set(cells) ^ grid)[:6]))
    return cells


def status_counts(cells, code=None, part=None, month=None):
    out = collections.Counter()
    for (c, date, pat), v in cells.items():
        if code and c != code:
            continue
        if part == 'weekend' and pat not in WK:
            continue
        if part == 'day' and pat not in DY:
            continue
        if month and date[:7] != month:
            continue
        out[v['status']] += 1
    return out


# ---------------------------------------------------------------- md 대조
def parse_parts():
    """part1·part2 의 절 머리·월별 5패턴 표·당일치기 줄을 모은다."""
    heads, tables, days = {}, collections.defaultdict(dict), collections.defaultdict(dict)
    for path in (PART1, PART2):
        code = month = None
        for raw in open(path, encoding='utf-8').read().splitlines():
            line = raw.strip()
            if line.startswith('## '):
                name = line[3:].strip()
                if name not in NAME2CODE:
                    raise SystemExit('예상 밖 절: %s' % line)
                code, month = NAME2CODE[name], None
                continue
            if line.startswith('# '):
                continue
            m = PERIOD.match(line)
            if m and code:
                low, d1, d2, pat, rest = m.groups()
                bits = [b.strip() for b in rest.split(' · ')]
                if len(bits) != 3:
                    raise SystemExit('기간 최저 줄 해석 실패: %s' % line)
                heads.setdefault(code, {})['period'] = {
                    'price': won(low), 'date': md_date(d1), 'back': md_date(d2),
                    'pattern': pat, 'airline': bits[0], 'via': bits[1], 'dur': bits[2]}
                continue
            m = DIRECT.match(line)
            if m and code:
                low, airline, dur, d1, d2, pat = m.groups()
                heads.setdefault(code, {})['direct'] = {
                    'price': won(low), 'airline': airline.strip(), 'dur': dur.strip(),
                    'date': md_date(d1), 'back': md_date(d2), 'pattern': pat}
                continue
            if code and line.startswith('직항편 없음'):
                heads.setdefault(code, {})['direct'] = None
                continue
            m = LASTSALE.match(line)
            if m and code:
                heads.setdefault(code, {})['lastSale'] = md_date(m.group(1))
                continue
            m = MHEAD.match(line)
            if m and code:
                month = '2027-%02d' % int(m.group(1))
                continue
            m = TROW.match(line)
            if m and code and month:
                pat, span, value, meta = (x.strip() for x in m.groups())
                if pat not in PAT_NIGHTS:
                    raise SystemExit('패턴 표기가 이상합니다: %s' % line)
                if value in ('—', '0건', '요금 미공개'):
                    tables[code][(month, pat)] = {'kind': value}
                    continue
                vm = re.match(r'^🔴 \*\*([\d.]+)만\*\*$', value)
                sm = re.match(r'^(\d{2}-\d{2})~(\d{2}-\d{2})$', span)
                if not vm or not sm:
                    raise SystemExit('표 값·기간 해석 실패: %s' % line)
                bits = [b.strip() for b in meta.split(' · ')]
                if len(bits) != 3:
                    raise SystemExit('표 비고 해석 실패: %s' % line)
                tables[code][(month, pat)] = {
                    'kind': 'price', 'price': won(vm.group(1)),
                    'date': md_date(sm.group(1)), 'back': md_date(sm.group(2)),
                    'airline': bits[0], 'via': bits[1], 'dur': bits[2]}
                continue
            if code and month and line.startswith('당일치기'):
                m = DAYVAL.match(line)
                if m:
                    pat, mb, dd, nights, rest = m.groups()
                    bits = [b.strip() for b in rest.split(' · ')]
                    if len(bits) != 3:
                        raise SystemExit('당일치기 줄 해석 실패: %s' % line)
                    days[code][month] = {'kind': 'price', 'pattern': pat,
                                         'price': won(mb), 'date': md_date(dd),
                                         'airline': bits[0], 'via': bits[1], 'dur': bits[2]}
                    continue
                counts = {k: int(n) for k, n in CNT.findall(line)}
                if '조회 응답 없음' in line:
                    days[code][month] = {'kind': 'blank', 'counts': counts}
                else:
                    days[code][month] = {'kind': 'none', 'counts': counts}
                continue
    return heads, tables, days


def parse_summary():
    """요약 md — 노선별 기간 최저·월별 최저·패턴별 최저·당일치기 표·특징 줄·합계 문장."""
    text = open(SUMMARY, encoding='utf-8').read()
    out = {'low': {}, 'month': {}, 'pattern': {}, 'daytrip': {}, 'feature': {}, 'text': text}
    month_cols = None          # 현재 읽는 월별 표의 열 → 월 매핑
    for line in text.splitlines():
        line = line.strip()
        head = [c.strip() for c in line.strip('|').split('|')] if line.startswith('|') else []
        if head and head[0] == '노선' and all(re.match(r'^\d+월$', h) for h in head[1:]):
            month_cols = ('2027-%02d' % int(h[:-1]) for h in head[1:])
            month_cols = tuple(month_cols)
            continue
        if head and head[0] in NAME2CODE and month_cols and len(head) == len(month_cols) + 1:
            code = NAME2CODE[head[0]]
            for mon, val in zip(month_cols, head[1:]):
                out['month'][(code, mon)] = val
            continue
        if not line.startswith('|'):
            month_cols = None
        m = re.match(r'^\| (.+?) \| 🔴 \*\*([\d.]+)만\*\* \((\d{2}-\d{2})~(\d{2}-\d{2})\) \| '
                     r'(.+?) \|$', line)
        if m and m.group(1) in NAME2CODE:
            name, v, d1, d2, meta = m.groups()
            out['low'][NAME2CODE[name]] = {
                'price': won(v), 'date': md_date(d1), 'back': md_date(d2),
                'airline': meta.split(' · ')[0].strip(),
                'via': meta.split(' · ')[1].strip()}
            continue
        m = re.match(r'^\| (.+?) \| 같은 날 왕복 상품 없음 \| (.+?) \|$', line)
        if m and m.group(1) in NAME2CODE:
            out['daytrip'][NAME2CODE[m.group(1)]] = {
                'kind': 'none',
                'counts': {k: int(n) for k, n in CNT.findall(m.group(2))}}
            continue
        m = re.match(r'^\| (.+?) \| 🔴 \*\*([\d.]+)만\*\* \((\d{2}-\d{2}) ([월화수목금토일]~'
                     r'[월화수목금토일])\) \| (.+?) \|$', line)
        if m and m.group(1) in NAME2CODE:
            name, v, dd, pat, meta = m.groups()
            bits = [b.strip() for b in meta.split(' · ')]
            out['daytrip'][NAME2CODE[name]] = {
                'kind': 'price', 'price': won(v), 'date': md_date(dd), 'pattern': pat,
                'airline': bits[0], 'via': bits[1], 'dur': bits[2],
                'cells': int(bits[3].replace('칸', '')) if len(bits) > 3 else None}
            continue
        m = re.match(r'^- \*\*(.+?)\*\*: (.+)$', line)
        if m and m.group(1) in NAME2CODE:
            body = m.group(2)
            out['feature'][NAME2CODE[m.group(1)]] = {
                k: int(n) for k, n in re.findall(r'(요금 미공개|0건|미조회) (\d+)칸', body)}
            continue
        m = re.match(r'^\| ([월화수목금토일]~[월화수목금토일]) \| (.+?) \| 🔴 \*\*([\d.]+)만\*\* '
                     r'\((\d{2}-\d{2})~(\d{2}-\d{2})\) \| (.+?) \|$', line)
        if m:
            pat, city, v, d1, d2, meta = m.groups()
            if city in NAME2CODE:
                out['pattern'][pat] = {'code': NAME2CODE[city], 'price': won(v),
                                       'date': md_date(d1), 'back': md_date(d2),
                                       'airline': meta.split(' · ')[0].strip(),
                                       'via': meta.split(' · ')[1].strip()}
            continue
    return out


def check(cells, heads, tables, days, summary):
    bad = []
    text = summary['text']
    # 1) 합계 문장
    for need in ('7개 노선 × 주말 5패턴 + 당일치기 = 1,029칸',
                 '1,029칸 중 **실측 523칸**, 요금 미공개 98칸, 판매편 없음(0건) 303칸, 미조회 105칸',
                 '2027년 2월 4일 ~ 6월 28일 (21주)'):
        if need not in text:
            bad.append('요약 md 문장(%s)을 찾지 못했습니다' % need)
    tot = status_counts(cells)
    got_tot = {'deals': tot.get('측정', 0), 'nosale': tot.get('0건', 0),
               'nofare': tot.get('요금미공개', 0), 'blank': tot.get('미조회', 0)}
    if got_tot != EXPECT:
        bad.append('상태 합계 %s (원문 %s)' % (got_tot, EXPECT))
    # 2) 노선별 상태 수(주말형/당일치기)
    for code in CODES:
        for part in ('weekend', 'day'):
            got = {k: v for k, v in status_counts(cells, code, part).items()}
            want = {'deals': 0, 'nosale': 0, 'nofare': 0, 'blank': 0}
            want.update(EXPECT_STATUS[code][part])
            gotn = {'deals': got.get('측정', 0), 'nosale': got.get('0건', 0),
                    'nofare': got.get('요금미공개', 0), 'blank': got.get('미조회', 0)}
            if gotn != want:
                bad.append('%s %s 상태 %s (원문 %s)' % (code, part, gotn, want))
    # 3) 절 머리 — 기간 최저·직항 최저·마지막 직항 판매일
    for code in CODES:
        h = heads.get(code) or {}
        p = h.get('period')
        if not p:
            bad.append('%s 절 머리의 기간 최저를 찾지 못했습니다' % code)
        else:
            want = EXPECT_LOW[code]
            low = min(v['price'] for (c, d, pat), v in cells.items()
                      if c == code and v['status'] == '측정')
            if low != want[0] or not close(p['price'], low):
                bad.append('%s 기간 최저 %d (CSV %d · 원문 %d)' % (code, p['price'], low, want[0]))
            place = cells.get((code, p['date'], p['pattern']))
            if not place or place['status'] != '측정' or not close(p['price'], place['price']):
                bad.append('%s 기간 최저 칸(%s %s)이 CSV 최저가와 다릅니다'
                           % (code, p['date'], p['pattern']))
                continue
            if not place['airline'].startswith(p['airline']):
                bad.append('%s 기간 최저 항공사 %r (CSV %r)' % (code, p['airline'],
                                                         place['airline']))
            if ('직항' in p['via']) != (place['stops'] == 0):
                bad.append('%s 기간 최저 직항/경유 표기가 다릅니다: %s' % (code, p['via']))
            if p['dur'] != place['dur']:
                bad.append('%s 기간 최저 소요 %s (CSV %s)' % (code, p['dur'], place['dur']))
        direct = h.get('direct')
        direct_cells = {(d, pat): v for (c, d, pat), v in cells.items()
                        if c == code and v['status'] == '측정' and v['stops'] == 0}
        if direct is None:
            if direct_cells:
                bad.append('%s 는 직항편 없음인데 CSV 에 직항 칸이 있습니다' % code)
        elif not direct_cells:
            bad.append('%s 직항 최저가 있는데 CSV 에 직항 칸이 없습니다' % code)
        else:
            low = min(v['price'] for v in direct_cells.values())
            if not close(direct['price'], low):
                bad.append('%s 직항 최저 %d (CSV %d)' % (code, direct['price'], low))
            hit = cells.get((code, direct['date'], direct['pattern']))
            if not hit or hit['stops'] != 0 or not close(direct['price'], hit['price']) \
                    or not hit['airline'].startswith(direct['airline']):
                bad.append('%s 직항 최저 칸(원문 %s %s)이 CSV 와 다릅니다'
                           % (code, direct['date'], direct['pattern']))
            elif direct['dur'] != hit['dur']:
                bad.append('%s 직항 최저 소요가 CSV 와 다릅니다' % code)
            last = h.get('lastSale')
            if not last:
                bad.append('%s 직항 마지막 판매일 줄을 찾지 못했습니다' % code)
            elif max(d for (d, _p) in direct_cells) != last:
                bad.append('%s 직항 마지막 판매일 %s (CSV %s)'
                           % (code, last, max(d for (d, _p) in direct_cells)))
    # 4) 월별 5패턴 표
    for code in CODES:
        if len(tables.get(code) or {}) != 5 * len(MONTHS):
            bad.append('%s 월별 표 %d칸 (기대 25칸)' % (code, len(tables.get(code) or {})))
        for month in MONTHS:
            for pat in WK:
                row = (tables.get(code) or {}).get((month, pat))
                if not row:
                    bad.append('%s %s %s 표 줄 없음' % (code, month, pat))
                    continue
                mine = {k: v for k, v in cells.items()
                        if k[0] == code and k[2] == pat and k[1][:7] == month}
                measured = {k: v for k, v in mine.items() if v['status'] == '측정'}
                kinds = {v['status'] for v in mine.values()}
                if row['kind'] == 'price':
                    if not measured:
                        bad.append('%s %s %s 표는 값인데 CSV 에 값이 없습니다'
                                   % (code, month, pat))
                        continue
                    low = min(measured.values(), key=lambda v: v['price'])
                    if not close(row['price'], low['price']):
                        bad.append('%s %s %s 표 최저 %d (CSV %d)'
                                   % (code, month, pat, row['price'], low['price']))
                    hit = [k for k, v in measured.items()
                           if close(row['price'], v['price']) and k[1] == row['date']]
                    if not hit:
                        bad.append('%s %s %s 표 출발일 %s 가 CSV 최저 칸과 다릅니다'
                                   % (code, month, pat, row['date']))
                        continue
                    v = measured[hit[0]]
                    if not v['airline'].startswith(row['airline']):
                        bad.append('%s %s %s 표 항공사 %r (CSV %r)'
                                   % (code, month, pat, row['airline'], v['airline']))
                    if ('직항' in row['via']) != (v['stops'] == 0):
                        bad.append('%s %s %s 표 직항/경유 표기 %r' % (code, month, pat, row['via']))
                    if row['dur'] != v['dur']:
                        bad.append('%s %s %s 표 소요 %s (CSV %s)'
                                   % (code, month, pat, row['dur'], v['dur']))
                elif row['kind'] == '요금 미공개':
                    if measured or '요금미공개' not in kinds:
                        bad.append('%s %s %s 표는 요금 미공개인데 CSV 상태 %s' % (
                            code, month, pat, sorted(kinds)))
                    if '0건' in kinds:
                        bad.append('%s %s %s 요금 미공개·0건이 섞였습니다' % (code, month, pat))
                elif row['kind'] == '0건':
                    if measured or '0건' not in kinds:
                        bad.append('%s %s %s 표는 0건인데 CSV 상태 %s' % (
                            code, month, pat, sorted(kinds)))
                else:
                    if measured or '0건' in kinds or '요금미공개' in kinds:
                        bad.append('%s %s %s 표는 —인데 CSV 상태 %s' % (
                            code, month, pat, sorted(kinds)))
    # 5) 월별 당일치기 줄
    for code in CODES:
        for month in MONTHS:
            row = (days.get(code) or {}).get(month)
            if not row:
                bad.append('%s %s 당일치기 줄 없음' % (code, month))
                continue
            mine = {k: v for k, v in cells.items()
                    if k[0] == code and k[2] in DY and k[1][:7] == month}
            cnt = collections.Counter(v['status'] for v in mine.values())
            measured = [(k, v) for k, v in mine.items() if v['status'] == '측정']
            if row['kind'] == 'price':
                if not measured:
                    bad.append('%s %s 당일치기 값인데 CSV 에 없습니다' % (code, month))
                    continue
                low = min(measured, key=lambda kv: kv[1]['price'])
                if not close(row['price'], low[1]['price']) or low[0][1] != row['date'] \
                        or low[0][2] != row['pattern']:
                    bad.append('%s %s 당일치기 최저 %s (CSV %s %s %s)'
                               % (code, month, (row['price'], row['date'], row['pattern']),
                                  (low[1]['price'], low[0][1], low[0][2])))
                if not low[1]['airline'].startswith(row['airline']):
                    bad.append('%s %s 당일치기 항공사 %r (CSV %r)'
                               % (code, month, row['airline'], low[1]['airline']))
                if row['dur'] != low[1]['dur']:
                    bad.append('%s %s 당일치기 소요 %s (CSV %s)'
                               % (code, month, row['dur'], low[1]['dur']))
                continue
            if measured:
                bad.append('%s %s 당일치기가 불가/빈칸인데 CSV 에 값 %d칸'
                           % (code, month, len(measured)))
            want = {'0건': 0, '미조회': 0, '요금 미공개': 0}
            want.update(row['counts'])
            got = {'0건': cnt.get('0건', 0), '미조회': cnt.get('미조회', 0),
                   '요금 미공개': cnt.get('요금미공개', 0)}
            for k in want:
                if got[k] != want[k]:
                    bad.append('%s %s 당일치기 %s %d칸 (원문 %d칸)'
                               % (code, month, k, got[k], want[k]))
    # 6) 요약 md 표
    for code in CODES:
        low = summary['low'].get(code)
        if not low:
            bad.append('요약 md 노선별 기간 최저에 %s 없음' % code)
        else:
            row = summary['low'][code]
            low = min(v['price'] for (c, d, pat), v in cells.items()
                      if c == code and v['status'] == '측정')
            if low != EXPECT_LOW[code][0] or not close(row['price'], low):
                bad.append('요약 %s 기간 최저 %s (CSV %d)' % (code, row, low))
            hits = [v for k, v in cells.items()
                    if k[0] == code and k[1] == row['date'] and v['status'] == '측정'
                    and close(row['price'], v['price'])]
            if not hits:
                bad.append('요약 %s 기간 최저 출발일 %s 가 CSV 최저가와 맞지 않습니다'
                           % (code, row['date']))
            else:
                if not hits[0]['airline'].startswith(row['airline']):
                    bad.append('요약 %s 기간 최저 항공사 %r (CSV %r)'
                               % (code, row['airline'], hits[0]['airline']))
                if ('직항' in row['via']) != (hits[0]['stops'] == 0):
                    bad.append('요약 %s 기간 최저 직항/경유 표기 %r' % (code, row['via']))
        # 월별 최저
        for month in MONTHS:
            val = (summary['month'].get((code, month)) or '').strip()
            mine = [v for (c, d, p), v in cells.items()
                    if c == code and d[:7] == month and p in WK and v['status'] == '측정']
            if not val:
                bad.append('요약 md 월별 최저에 %s %s 없음' % (code, month))
            elif val == '요금 미공개':
                if mine or '요금미공개' not in status_counts(cells, code, month=month):
                    bad.append('요약 %s %s 는 요금 미공개인데 CSV 에 값/상태가 다릅니다'
                               % (code, month))
            elif val == '—':
                if mine:
                    bad.append('요약 %s %s 는 —인데 CSV 에 값이 있습니다' % (code, month))
            else:
                vm = re.match(r'🔴 \*\*([\d.]+)만\*\* \((\d{2}-\d{2})~(\d{2}-\d{2})\)', val)
                if not vm:
                    bad.append('요약 %s %s 월별 최저 해석 실패: %r' % (code, month, val))
                    continue
                if not mine:
                    bad.append('요약 %s %s 월별 최저가 있는데 CSV 에 값이 없습니다'
                               % (code, month))
                    continue
                low = min(mine, key=lambda v: v['price'])
                if not close(won(vm.group(1)), low['price']):
                    bad.append('요약 %s %s 월별 최저 %s (CSV %d)'
                               % (code, month, vm.group(1), low['price']))
                if not any(close(won(vm.group(1)), v['price']) and d == md_date(vm.group(2))
                           for (c, d, p), v in cells.items()
                           if c == code and v['status'] == '측정'):
                    bad.append('요약 %s %s 월별 최저 출발일 %s 가 CSV 와 다릅니다'
                               % (code, month, vm.group(2)))
        # 노선별 특징(주말형 5패턴 상태 수)
        feat = summary['feature'].get(code)
        if feat is None:
            bad.append('요약 md 노선별 특징에 %s 없음' % code)
        else:
            cnt = status_counts(cells, code, 'weekend')
            want = {'요금 미공개': cnt.get('요금미공개', 0), '0건': cnt.get('0건', 0),
                    '미조회': cnt.get('미조회', 0)}
            for k, n in feat.items():
                if want[k] != n:
                    bad.append('요약 %s 특징 %s %d칸 (CSV %d칸)' % (code, k, n, want[k]))
        # 당일치기 표
        dt = summary['daytrip'].get(code)
        if not dt:
            bad.append('요약 md 당일치기 표에 %s 없음' % code)
        else:
            measured = [((c, d, p), v) for (c, d, p), v in cells.items()
                        if c == code and p in DY and v['status'] == '측정']
            if dt['kind'] == 'price':
                if not measured:
                    bad.append('요약 %s 당일치기 값인데 CSV 에 없습니다' % code)
                    continue
                low = min(measured, key=lambda kv: kv[1]['price'])
                if not close(dt['price'], low[1]['price']) or low[0][1] != dt['date'] \
                        or low[0][2] != dt['pattern']:
                    bad.append('요약 %s 당일치기 최저 %s (CSV %s)'
                               % (code, (dt['price'], dt['date'], dt['pattern']),
                                  (low[1]['price'], low[0][1], low[0][2])))
                if dt.get('cells') not in (None, len(measured)):
                    bad.append('요약 %s 당일치기 칸 수 %s (CSV %d)'
                               % (code, dt.get('cells'), len(measured)))
            else:
                if measured:
                    bad.append('요약 %s 당일치기는 불가인데 CSV 에 값이 있습니다' % code)
                cnt = status_counts(cells, code, 'day')
                want = {'0건': 0, '미조회': 0, '요금 미공개': 0}
                want.update(dt['counts'])
                got = {'0건': cnt.get('0건', 0), '미조회': cnt.get('미조회', 0),
                       '요금 미공개': cnt.get('요금미공개', 0)}
                for k in want:
                    if got[k] != want[k]:
                        bad.append('요약 %s 당일치기 %s %d칸 (원문 %d칸)'
                                   % (code, k, got[k], want[k]))
    # 7) 패턴별 최저(전 노선)
    for pat in WK:
        row = summary['pattern'].get(pat)
        if not row:
            bad.append('요약 md 패턴별 최저에 %s 없음' % pat)
            continue
        mine = [((c, d, p), v) for (c, d, p), v in cells.items()
                if p == pat and v['status'] == '측정']
        low = min(mine, key=lambda kv: kv[1]['price'])
        if low[0][0] != row['code'] or not close(row['price'], low[1]['price']) \
                or low[0][1] != row['date'] or low[0][2] != pat:
            bad.append('요약 %s 패턴 최저 %s (CSV %s %s %s)'
                       % (pat, row, low[0][0], low[1]['price'], low[0][1]))
    return bad


# ---------------------------------------------------------------- 병합
def month_note(fl, month):
    """그 달 일본 7개 노선 커버리지 — 실측·0건·요금 미공개·미조회를 데이터에서 센다(plain text)."""
    routes = {r['code']: r for r in fl['routes']}
    got, days = [], []
    for code in CODES:
        for d in routes[code]['deals']:
            if d['date'][:7] != month:
                continue
            row = (d['price'], d['date'], d['pattern'], code, d.get('airline', ''),
                   d.get('via'))
            (days if d['pattern'].split('~')[0] == d['pattern'].split('~')[1] else got).append(row)
    marks = [n for n in fl['noSale'] if n['code'] in CODES and n['date'][:7] == month]
    ns = sum(1 for n in marks if (n.get('status') or 'nosale') == 'nosale')
    nf = sum(1 for n in marks if n.get('status') == 'nofare')
    grid = sum(1 for (c, d, p) in grid_cells() if d[:7] == month)
    miss = grid - len(got) - len(days) - len(marks)
    body = ('일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)은 '
            '2027년 2~6월 21주 × 7패턴 1,029칸 가운데 이 달 %d칸을 조회해 실측 %d칸 · '
            '판매편 0건 %d칸 · 요금 미공개 %d칸 · 미조회 %d칸입니다.'
            % (grid, len(got) + len(days), ns, nf, miss))
    if not got:
        txt = body + ' 이 달은 주말형 값이 잡힌 칸이 없습니다.'
    else:
        per_route = collections.defaultdict(list)
        for g in got:
            per_route[g[3]].append(g)
        ranked = sorted((min(v), c) for c, v in per_route.items())
        lead = ranked[0][0]
        txt = body + ' 주말형 최저는 %s %d/%d~%d %s %s원(%s %s)' % (
            CITY[lead[3]], int(lead[1][5:7]), int(lead[1][8:10]), int(lead[1][8:10]) +
            PAT_NIGHTS[lead[2]], lead[2], format(lead[0], ','), lead[4],
            '직항' if lead[5] is False else '경유')
        rest = [r[0] for r in ranked[1:3]]
        if rest:
            txt += '이고 다음이 ' + ' · '.join(
                '%s %s원(%s)' % (CITY[r[3]], format(r[0], ','),
                               '직항' if r[5] is False else '경유') for r in rest)
        txt += '입니다.'
        silent = [CITY[c] for c in CODES if c not in per_route]
        if silent:
            txt += ' 주말형 값이 없는 노선은 %s입니다.' % '·'.join(silent)
    if days:
        low = min(days)
        txt += ' 당일치기 최저는 %s %d/%d %s %s원(%s %s)입니다.' % (
            CITY[low[3]], int(low[1][5:7]), int(low[1][8:10]), low[2], format(low[0], ','),
            low[4], '직항' if low[5] is False else '경유')
    return txt


def grid_cells():
    return {(c, (datetime.date.fromisoformat(t) + datetime.timedelta(
        days=(WD[p[0]] - WD['목']) % 7)).isoformat(), p)
        for c in CODES for t in THU for p in WK + DY}


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


def _join(a, b):
    a, b = (a or '').strip(), (b or '').strip()
    return (a + ' ' + b).strip() if a and b else (a or b)


DAYTRIP_NOTE = {
    'KMJ': '2027년 2~6월에는 3/7·3/13·3/14 세 날짜만 같은 날 왕복이 잡혔고(1,028,300원 · 대한항공·일본항공 '
           '도쿄 경유 총 7시간 30분 · 현지 체류 미확인), 4~6월은 조회 응답이 없습니다.',
    'KOJ': ' 2027년 2월에는 제주항공 직항이 2/26까지 판매되어 2/13 토~토 949,800원 · 2/20 토~토 '
           '992,000원 두 날짜만 같은 날 왕복이 잡혔습니다(직항 1시간 20분 · 체류 시간 미표시). '
           '3월 이후는 직항 판매가 끝나 0건 31칸 · 미조회 9칸입니다.',
    'FSZ': ' 2027년 2~6월 당일치기는 42칸 모두 판매편 0건(24칸)이거나 조회되지 않았습니다(미조회 18칸).',
    'MYJ': ' 2027년 2~6월에도 같은 날 왕복이 잡히지 않습니다(0건 20칸 · 요금 미공개 11칸 · 미조회 11칸).',
    'TAK': ' 2027년 2~6월 당일치기는 42칸 모두 판매편 0건(33칸)이거나 조회되지 않았습니다(미조회 9칸).',
    'MMY': ' 2027년 2~6월 당일치기도 0건 39칸 · 미조회 3칸으로 잡히지 않습니다.',
    'CTS': ' 2027년 2~6월은 42칸 가운데 38칸에서 같은 날 왕복이 잡혔고 최저는 3/6 토~토 438,600원'
           '(진에어 직항 2시간 20분) · 3/7 일~일 438,600원입니다. 4월 이후는 대한항공 인천 경유(5시간 25분~)로 '
           '59만~109만원입니다.',
}


def merge(master, cells):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in CODES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다(신설이 아니라 병합 대상)' % code)
    added, dup, conflicts = [], [], []
    for (code, date, pat), v in sorted(cells.items()):
        if v['kind'] != 'deals':
            continue
        have = next((d for d in routes[code]['deals']
                     if d['date'] == date and d['pattern'] == pat), None)
        if have is not None:
            if have.get('price') != v['price']:
                conflicts.append((code, date, pat, have.get('price'), v['price']))
            dup.append((code, date, pat))
            continue
        deal = {'date': date, 'back': v['back'], 'pattern': pat, 'price': v['price'],
                'airline': v['airline'], 'via': v['stops'] > 0,
                'note': deal_note(v['stops'], v['places'], v['dur'])}
        if v.get('direct') and v['direct'] > v['price']:
            deal['alt'] = v['direct']
        routes[code]['deals'].append(deal)
        added.append((code, date, pat, v['price']))
    for (code, date, pat), v in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if v['kind'] not in ('nosale', 'nofare'):
            continue
        if any(n['code'] == code and n['date'] == date and n['pattern'] == pat
               for n in fl['noSale']):
            conflicts.append((code, date, pat, 'noSale', v['kind']))
            continue
        if any(d['date'] == date and d['pattern'] == pat for d in routes[code]['deals']):
            conflicts.append((code, date, pat, 'deal', v['kind']))
            continue
        fl['noSale'].append({
            'code': code, 'date': date, 'back': v['back'], 'pattern': pat,
            'status': v['kind'],
            'note': ('검색 결과 0건(판매편 없음)' if v['kind'] == 'nosale'
                     else '운항편은 표시되나 요금 미게시(예약 불가)')})
    if conflicts:
        raise SystemExit('기존 값과 충돌합니다(확인 필요): %s' % conflicts[:8])
    if dup:
        raise SystemExit('이미 있는 칸이 있습니다: %s' % dup[:5])
    if len(added) != EXPECT['deals']:
        raise SystemExit('신규 값 %d칸 (기대 %d칸)' % (len(added), EXPECT['deals']))
    for code in CODES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))
        dt = routes[code]['daytrip']
        dt['note'] = _join(dt.get('note'), DAYTRIP_NOTE[code])
    # 가고시마는 12월·1월에는 당일치기가 안 됐지만 2027년 2월 두 날짜에 잡혔다 — 상태·요약을 고친다
    koj = routes['KOJ']['daytrip']
    koj['status'] = 'unk'
    koj['stay'] = ''
    koj['short'] = '2월 2일만 성립'
    koj['note'] = _join('2026년 12월·1월에는 부산–가고시마 직항이 검색되지 않아(서울 경유 총 4시간 20분~) '
                        '같은 날 왕복이 성립하지 않았습니다.', DAYTRIP_NOTE['KOJ'])
    routes['KOJ']['daytrip'] = koj


def main(argv):
    ap = argparse.ArgumentParser(description='일본 7개 노선 2027년 2~6월 1,029칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    cells = read_csv()
    heads, tables, days = parse_parts()
    summary = parse_summary()
    bad = check(cells, heads, tables, days, summary)
    print('  CSV 1,029칸 — 실측 %d · 0건 %d · 요금 미공개 %d · 미조회 %d'
          % tuple(status_counts(cells)[k] for k in ('측정', '0건', '요금미공개', '미조회')))
    for code in CODES:
        c = status_counts(cells, code)
        print('    %s %s' % (code, dict(c)))
    if bad:
        raise SystemExit('원문과 CSV 가 다릅니다:\n  - ' + '\n  - '.join(bad))

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}

    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    sources_before = json.dumps(master.get('sources'), ensure_ascii=False)
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    bw_before = json.dumps(fl['bookingWindow'], ensure_ascii=False, sort_keys=True)
    notes_before = {m: fl['notes'][m] for m in MONTHS}
    other_notes_before = {k: v for k, v in fl['notes'].items() if k not in MONTHS}
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    before_deals = {code: json.dumps(routes[code]['deals'], ensure_ascii=False)
                    for code in CODES}
    before_daytrip = {code: json.dumps(routes[code]['daytrip'], ensure_ascii=False)
                      for code in CODES}
    other_codes = set(routes) - set(CODES)
    before_other = json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                              ensure_ascii=False, sort_keys=True)

    merge(master, cells)
    counts, by_month = recount(fl)
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = counts['total']
    for month in MONTHS:
        fl['notes'][month] = (notes_before[month].rstrip() + ' ' + month_note(fl, month))
    fl['bookingWindow']['note'] = _join(
        fl['bookingWindow']['note'],
        ' 일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)의 부산 직항은 '
        '겨울 시즌(2027-02-26~03-26 노선별)까지만 판매 중이라 4월 이후 값은 대한항공·JAL 등 경유편입니다.')

    # ── 보존·건수 검증 ──
    if counts['total'] != EXPECT_TOTAL:
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], EXPECT_TOTAL))
    if counts['daytrip'] != EXPECT_DAYTRIP:
        raise SystemExit('당일치기 %d건 (기대 %d건)' % (counts['daytrip'], EXPECT_DAYTRIP))
    if counts['holiday'] != EXPECT_HOLIDAY:
        raise SystemExit('연휴 칸 %d건 (기대 %d건)' % (counts['holiday'], EXPECT_HOLIDAY))
    for m, want in EXPECT_BY_MONTH.items():
        if counts['byMonth'].get(m) != want:
            raise SystemExit('%s %s건 (기대 %d건)' % (m, counts['byMonth'].get(m), want))
    for code, want in ROUTE_DEALS.items():
        if len(routes[code]['deals']) != want:
            raise SystemExit('%s 딜 %d건 (기대 %d건)' % (code, len(routes[code]['deals']), want))
    h2 = collections.Counter()
    for r in fl['routes']:
        for d in r['deals']:
            if d['date'] >= '2027-06-01':
                h2['day' if d['pattern'].split('~')[0] == d['pattern'].split('~')[1]
                   else 'weekend'] += 1
    if dict(h2) != EXPECT_H2:
        raise SystemExit('6~11월 주말/당일 %s (기대 %s)' % (dict(h2), EXPECT_H2))
    marks = collections.Counter(n.get('status') or 'nosale' for n in fl['noSale'])
    for key, want in (('nosale', 191 + 303), ('nofare', 255 + 98), ('unopened', 376)):
        if marks[key] != want:
            raise SystemExit('%s %d칸 (기대 %d칸)' % (key, marks[key], want))
    jp_marks = [n for n in fl['noSale'] if n['code'] in CODES and '2027-02-01' <= n['date']]
    if len(jp_marks) != 303 + 98:
        raise SystemExit('일본 7노선 표시 칸 %d개 (기대 401개)' % len(jp_marks))

    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps(master.get('sources'), ensure_ascii=False) != sources_before:
        raise SystemExit('출처 목록이 바뀌었습니다.')
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다.')
    if json.dumps(fl['noSale'][:len(json.loads(nosale_before))], ensure_ascii=False) \
            != nosale_before:
        raise SystemExit('기존 noSale 순서/내용이 바뀌었습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다.')
    for code in CODES:
        old = json.loads(before_deals[code])
        now = routes[code]['deals'][:len(old)]
        if json.dumps(now, ensure_ascii=False) != json.dumps(old, ensure_ascii=False):
            raise SystemExit('%s 기존 딜이 사라지거나 바뀌었습니다.' % code)
    for code in CODES:
        if code == 'KOJ':
            continue
        old = json.loads(before_daytrip[code])
        now = dict(routes[code]['daytrip'])
        now.pop('note', None)
        old.pop('note', None)
        if json.dumps(now, ensure_ascii=False, sort_keys=True) != \
                json.dumps(old, ensure_ascii=False, sort_keys=True):
            raise SystemExit('%s 당일치기 요약(상태·체류·한줄)이 바뀌었습니다.' % code)
    if {k: v for k, v in fl['notes'].items() if k not in MONTHS} != other_notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다.')
    bw_now = json.loads(json.dumps(fl['bookingWindow'], ensure_ascii=False, sort_keys=True))
    bw_old = json.loads(bw_before)
    if {k: v for k, v in bw_now.items() if k != 'note'} != \
            {k: v for k, v in bw_old.items() if k != 'note'}:
        raise SystemExit('예약창 정보가 바뀌었습니다(주석 외).')
    if '**' in json.dumps({m: fl['notes'][m] for m in MONTHS}, ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다.')

    print('신규 %d칸 (실측 %d)' % (EXPECT['deals'], EXPECT['deals']))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, counts['total'], counts['total'] - counts['daytrip'],
        counts['daytrip']))
    print('월별: %s' % counts['byMonth'])
    print('월별 증가: %s' % {m: counts['byMonth'].get(m, 0) - before_by_month.get(m, 0)
                            for m in counts['byMonth']})
    print('표시: 0건 %d · 요금 미공개 %d · 미오픈 %d'
          % (marks['nosale'], marks['nofare'], marks['unopened']))
    for code in CODES:
        mine = routes[code]['deals']
        print('  %s %d건 최저 %s' % (code, len(mine),
                                    format(min(d['price'] for d in mine), ',')))

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        json.dump({m: fl['notes'][m] for m in MONTHS},
                  open(os.path.join(ROOT, 'data', '.jp26m_dry_notes.json'), 'w'),
                  ensure_ascii=False, indent=1)
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
