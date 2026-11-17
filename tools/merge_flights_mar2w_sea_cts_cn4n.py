#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 항공 특가 **추가 완본 4건**을 `data/master_db.json` 의 `flights` 에 한꺼번에 병합한다.

  1) 기존 24개 노선 **2027년 3월 2주차(3/11~15) 5패턴 120칸 완본** — 5번 보고
     `data-sources/flights-2027-03/부산출발-항공특가-2027년3월-2주차.md`
     최저 후쿠오카 3/11~15 238,100원(에어부산 직항) · 최고 발리(노선별 최저 기준 496,600원)
  2) 일본 신규 7개 노선 **2026년 12월 최종 완결본 171/175칸** — 5번 보고
     `data-sources/flights-jp-new7/부산출발-일본7노선-12월-완결.md`
     삿포로(CTS) 25/25 완결(+21칸) · 시즈오카 21/25 · 나머지 5개 노선 25/25
  3) 동남아 4개 노선(푸꾸옥·코타키나발루·쿠알라룸푸르·비엔티안) **2027년 2~6월 420/420칸** — 4번 보고
     `data-sources/flights-sea-new8/부산출발-동남아4노선-푸꾸옥코타쿠알라비엔티안-2_6월.md`
  4) 중국 G1 4개 노선(선양·다롄·광저우·샤먼) **2027년 2~6월 384/420칸 갱신본** — 2번 보고
     `data-sources/flights-china-new8/부산출발-중국4노선-선양다롄광저우샤먼-2_6월.md`
     기존 336칸(2박·3박) + 목~월(4박) 2/4~4/22 48칸 추가

읽는 곳:
  · 3월 2주차 — `### 부산–상하이 (PVG)` 절 머리 + `- 2027-03-12 · 금~일·2박 · PUS–PVG · 319,600원 · 춘추항공 · 직항 1시간55분(22:10-23:05)`
  · 일본 — `### 부산–삿포로(신치토세) (CTS) · 25칸 중 25칸 실측` 아래 `- 2026-12-03 · 목~일 · 삿포로(신치토세) · 420,480원`
  · 동남아 — `## 1. 부산 ↔ 푸꾸옥(PQC)` → `### 금~일(2박)` 표의 `| 02/05 (금) | 02/07 | **812,072** | 비엣젯항공 | 직항 | … |`
  · 중국 — 부록 A `- 2027-02-04 · 목~월 · PUS–SHE · 713,400원 · 중국동방항공(상하이항공 운항) · 경유(상하이 2h35, 총7h00)`

규칙:
  · 값은 원문 그대로. 항공사·경유지 이름만 앱 표기(한국어)로 옮긴다.
  · 원문이 말하는 칸 수·노선별 커버리지·최저/최고/평균·순위표·달력표를 파싱 결과와 **전수 대조**한다.
  · 이미 있는 칸은 중복으로 넣지 않고, **기존 금액이 하나라도 달라지면 멈춘다**
    (기존 항공사·경유 표기는 그대로 보존).
  · 호텔 538곳 · 아코르 SNU 43줄 · 출처 목록 · 패턴 정의 · `noSale` · 대상 밖 노선은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)와 2026-12 ~ 2027-06 `notes`(커버리지 문구)를 다시 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_mar2w_sea_cts_cn4n.py --dry-run
    python3 tools/merge_flights_mar2w_sea_cts_cn4n.py --note "..."
"""
import argparse
import collections
import datetime
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources'))
MD_MAR2 = os.path.join(SRC, 'flights-2027-03', '부산출발-항공특가-2027년3월-2주차.md')
MD_JP = os.path.join(SRC, 'flights-jp-new7', '부산출발-일본7노선-12월-완결.md')
MD_SEA = os.path.join(SRC, 'flights-sea-new8', '부산출발-동남아4노선-푸꾸옥코타쿠알라비엔티안-2_6월.md')
MD_CN = os.path.join(SRC, 'flights-china-new8', '부산출발-중국4노선-선양다롄광저우샤먼-2_6월.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
PATTERNS = ('금~일', '토~월', '목~일', '금~월', '목~월')
JP_ROUTES = ('CTS', 'FSZ', 'KOJ', 'KMJ', 'MYJ', 'TAK', 'MMY')
SEA_ROUTES = ('PQC', 'BKI', 'KUL', 'VTE')
G1_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN')
MAR2_ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR',
               'NKG', 'SGN', 'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX',
               'DPS', 'KHH', 'RMQ', 'BJS')
MAR2_CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'TPE': '타이베이', 'HKG': '홍콩',
             'MFM': '마카오', 'PVG': '상하이', 'BKK': '방콕', 'DAD': '다낭', 'CXR': '나트랑',
             'NKG': '난징', 'SGN': '호찌민', 'SIN': '싱가포르', 'GUM': '괌', 'NGO': '나고야',
             'OKA': '오키나와', 'HGH': '항저우', 'TAO': '칭다오', 'HAN': '하노이', 'CNX': '치앙마이',
             'DPS': '발리', 'KHH': '가오슝', 'RMQ': '타이중', 'BJS': '베이징'}
SEA_CITY = {'PQC': '푸꾸옥', 'BKI': '코타키나발루', 'KUL': '쿠알라룸푸르', 'VTE': '비엔티안'}

# ── 원문이 말하는 값 ────────────────────────────────────────────────────────────
# 3월 2주차: 24노선 × 5패턴 120칸, 패턴 평균·경유 칸 수·노선별 최저가 순위 24줄
EXPECT_MAR2 = {
    'cells': 120,
    'overall': (238100, 519900),          # 후쿠오카 3/11~15 목~월 · 싱가포르 3/13~15 토~월
    'route_low_max': 496600,              # 원문 '가장 비싼 노선'은 노선별 최저 기준 — 발리 496,600원
    'most_expensive_route': ('DPS', 496600),
    'avg': {'금~일': 388200, '토~월': 376275, '목~일': 392467, '금~월': 372612, '목~월': 374129},
    'via': 34,                            # 최저가가 경유인 조합 34 · 직항 86
    'route_low': {                        # 노선별 5패턴 중 최저(원문 '## 노선별 최저가 순위' 24줄)
        'FUK': (238100, '2027-03-11', '목~월'), 'DAD': (278100, '2027-03-12', '금~월'),
        'PVG': (280300, '2027-03-12', '금~월'), 'TAO': (286300, '2027-03-11', '목~일'),
        'HAN': (304200, '2027-03-13', '토~월'), 'TPE': (307100, '2027-03-12', '금~일'),
        'HKG': (315800, '2027-03-11', '목~월'), 'BJS': (323000, '2027-03-13', '토~월'),
        'NGO': (323400, '2027-03-11', '목~월'), 'CXR': (326900, '2027-03-13', '토~월'),
        'HGH': (334000, '2027-03-13', '토~월'), 'KIX': (339600, '2027-03-11', '목~월'),
        'TYO': (374300, '2027-03-11', '목~월'), 'CNX': (376400, '2027-03-12', '금~월'),
        'KHH': (388600, '2027-03-12', '금~월'), 'GUM': (390000, '2027-03-12', '금~일'),
        'NKG': (395200, '2027-03-11', '목~일'), 'SGN': (395600, '2027-03-12', '금~월'),
        'RMQ': (407900, '2027-03-13', '토~월'), 'BKK': (426700, '2027-03-12', '금~일'),
        'OKA': (430700, '2027-03-11', '목~월'), 'MFM': (438200, '2027-03-12', '금~일'),
        'SIN': (484300, '2027-03-12', '금~일'), 'DPS': (496600, '2027-03-12', '금~일'),
    },
}
# 일본 완결본: 175칸 중 171칸(삿포로 25 · 시즈오카 21 · 나머지 25씩)
EXPECT_JP_CELLS = {'CTS': 25, 'FSZ': 21, 'KOJ': 25, 'KMJ': 25, 'MYJ': 25, 'TAK': 25, 'MMY': 25}
EXPECT_JP_LOW = {                         # '## 먼저 결론' 7줄
    'CTS': (367800, '2026-12-10', '목~월'), 'FSZ': (276900, '2026-12-03', '목~월'),
    'KOJ': (427000, '2026-12-18', '금~일'), 'KMJ': (242800, '2026-12-03', '목~월'),
    'MYJ': (274300, '2026-12-03', '목~월'), 'TAK': (259300, '2026-12-12', '토~월'),
    'MMY': (317500, '2026-12-17', '목~일'),
}
EXPECT_JP_DUP = {'CTS': 4, 'FSZ': 21, 'KOJ': 25, 'KMJ': 25, 'MYJ': 25, 'TAK': 25, 'MMY': 25}
EXPECT_JP_NEW = 21
# 동남아 2~6월: 4노선 × 21주 × 5패턴 420칸 — 노선별 최저·평균·최고와 직항 최저, 패턴·월 요약
EXPECT_SEA = {
    'cells': 420,
    'per_route': {
        'PQC': {'low': 292051, 'avg': 430469, 'high': 1162801, 'direct': 292051,
                'direct_n': 73, 'via_n': 32},
        'BKI': {'low': 414100, 'avg': 537049, 'high': 948800, 'direct': 414100,
                'direct_n': 9, 'via_n': 96},
        'KUL': {'low': 411136, 'avg': 488882, 'high': 877016, 'direct': 936200,
                'direct_n': 0, 'via_n': 105},
        'VTE': {'low': 478218, 'avg': 621214, 'high': 944678, 'direct': 1095800,
                'direct_n': 0, 'via_n': 105},
    },
    'overall_low': 292051,
}
# 중국 G1 갱신본: 420칸 표 · 값 384칸 · 미조회 36칸(목~월 4/29 이후 9주)
EXPECT_CN = {
    'values': 384, 'gaps': 36, 'cells': 420,
    'per_pat': {'목~일': 84, '금~일': 84, '토~월': 84, '금~월': 84, '목~월': 48},
    'overall': (317400, 884000),          # 다롄 3/4~8 목~월 · 샤먼 2/6~8 토~월
    'fri': {'SHE': (538167, 713600, 463500), 'DLC': (466567, 607100, 373300),
            'CAN': (545043, 775200, 501100), 'XMN': (555929, 758400, 464500)},
    'dup': 336, 'new': 48,
}
PREV_TOTAL = 3649
EXPECT_TOTAL = 4258

MONEY = re.compile(r'([\d,]+)원')
HEAD24 = re.compile(r'^### 부산–(.+?) \(([A-Z]{3})\)$')
CELL24 = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일])·(\d)박 · '
                    r'PUS–([A-Z]{3}) · ([\d,]+)원 · ([^·]+?) · (.+)$')
RANK24 = re.compile(r'^- ([\d,]+)원 · (.+?)\(([A-Z]{3})\) · (\d{4}-\d{2}-\d{2}) '
                    r'(\S+?)·(\d)박 · (.+)$', re.M)
SEA_HEAD = re.compile(r'^## \d\. 부산 ↔ (.+?)\(([A-Z]{3})\)$')
SEA_PAT = re.compile(r'^### ([월화수목금토일]~[월화수목금토일])\s*\((\d)박\)$')
SEA_ROW = re.compile(r'^\| (\d{2})/(\d{2}) \(([월화수목금토일])\) \| (\d{2})/(\d{2}) \| '
                     r'\*\*([\d,]+)\*\* \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \| '
                     r'([^|]*?) \|$')
SEA_CAL = re.compile(r'^\| (\d{2})/(\d{2}) 주 \(W\d+\) \|(.+)\|\s*$')
SEA_PATSUM = re.compile(r'^\| ([월화수목금토일]~[월화수목금토일])\((\d)박\) \| \*\*([\d,]+)원\*\* \| '
                        r'([\d,]+)원 \| ([\d,]+)원 \| (\d{2})/(\d{2})~(\d{2})/(\d{2}) \|$')
SEA_MONSUM = re.compile(r'^\| 2027년 (\d+)월 \| \*\*([\d,]+)원\*\* \| ([\d,]+)원 \| (\d{2})/(\d{2})~'
                        r'(\d{2})/(\d{2}) · ([월화수목금토일]~[월화수목금토일])\((\d)박\) \|$')


def load(mod, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, mod))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def tidy(text):
    d = re.sub(r'(\d+)시간(\d+)분', r'\1시간 \2분', text)
    d = re.sub(r'총(\d)', r'총 \1', d)
    d = re.sub(r'(\d+)h(\d{2})', r'\1시간 \2분', d)
    d = re.sub(r'(\d+)h(?!\d)', r'\1시간', d)
    return d.strip()


def norm_money(text):
    return int(re.sub(r'[^\d]', '', text))


# ── 1) 3월 2주차 ───────────────────────────────────────────────────────────────
def parse_mar2(text):
    cells, heads, rank = {}, {}, []
    code = None
    for raw in text.splitlines():
        line = raw.strip()
        m = HEAD24.match(line)
        if m:
            city, code = m.groups()
            if code not in MAR2_ROUTES:
                raise SystemExit('예상 밖 노선: %s' % line)
            if city != MAR2_CITY[code]:
                raise SystemExit('도시 이름이 다릅니다: %s (%s)' % (line, MAR2_CITY[code]))
            if code in heads:
                raise SystemExit('같은 노선 절이 두 번 있습니다: %s' % code)
            heads[code] = city
            continue
        if line.startswith('## ') or line.startswith('### '):
            code = None
            continue
        if code:
            m = CELL24.match(line)
            if not m:
                continue
            date, pat, nights, rc, price, airline, desc = m.groups()
            if rc != code:
                raise SystemExit('절과 노선 코드가 다릅니다: %s' % line)
            if int(nights) != (WD[pat[-1]] - WD[pat[0]]) % 7:
                raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
            back = back_date(date, pat)
            if not ('2027-03-11' <= date <= '2027-03-15') or not ('2027-03-11' <= back <= '2027-03-16'):
                raise SystemExit('3월 2주차 밖 일정입니다: %s' % line)
            body, tail = desc, ''
            if ' (직항 최저' in desc or ' (직항편 없음)' in desc:
                body, tail = desc.rsplit(' (', 1)
                tail = tail[:-1]
            body = tidy(body)
            if not (body.startswith('직항') or body.startswith('경유')):
                raise SystemExit('직항/경유 표기가 아닙니다: %s' % line)
            note = body
            alt = 0
            if tail:
                mm = re.search(r'직항 최저 ([\d,]+)원?', tail)
                if mm:
                    alt = norm_money(mm.group(1))
                    note += ' · 직항 최저 %s원' % format(alt, ',')
                elif '직항편 없음' in tail:
                    note += ' · 직항편 없음'
                else:
                    note += ' · ' + tidy(tail)
            deal = {'date': date, 'back': back, 'pattern': pat, 'price': norm_money(price),
                    'airline': airline.strip(), 'via': body.startswith('경유'), 'note': note}
            if alt:
                deal['alt'] = alt
            if any(d['date'] == date and d['pattern'] == pat for d in cells.get(code, [])):
                raise SystemExit('%s %s %s 중복' % (code, date, pat))
            cells.setdefault(code, []).append(deal)
    for m in RANK24.finditer(text):
        price, city, code, date, pat, nights, desc = m.groups()
        rank.append((norm_money(price), code, date, pat, int(nights), desc.strip()))
    return cells, heads, rank


def check_mar2(text, cells, heads, rank):
    bad = []
    if set(cells) != set(MAR2_ROUTES):
        bad.append('3월 2주차 노선 집합이 다릅니다: %s' % sorted(set(cells) ^ set(MAR2_ROUTES)))
    total = sum(len(v) for v in cells.values())
    if total != EXPECT_MAR2['cells']:
        bad.append('3월 2주차 값 %d칸 (원문 %d칸)' % (total, EXPECT_MAR2['cells']))
    for code in MAR2_ROUTES:
        deals = cells.get(code) or []
        if len(deals) != 5:
            bad.append('%s %d칸 (5칸이어야 함)' % (code, len(deals)))
        if {d['pattern'] for d in deals} != set(PATTERNS):
            bad.append('%s 패턴 집합이 다릅니다: %s' % (code, sorted(d['pattern'] for d in deals)))
        for d in deals:
            if d['date'][8:] not in ('11', '12', '13'):
                bad.append('%s 출발일 %s 가 3/11~13 밖입니다' % (code, d['date']))
    all_deals = [d for v in cells.values() for d in v]
    prices = [d['price'] for d in all_deals]
    if (min(prices), max(prices)) != EXPECT_MAR2['overall']:
        bad.append('3월 2주차 최저·최고 %s (원문 %s)' % ((min(prices), max(prices)), EXPECT_MAR2['overall']))
    lows = {c: min(d['price'] for d in v) for c, v in cells.items()}
    if max(lows.values()) != EXPECT_MAR2['route_low_max']:
        bad.append('3월 2주차 노선별 최저의 최고 %d (원문 %d)'
                   % (max(lows.values()), EXPECT_MAR2['route_low_max']))
    worst = max(lows, key=lambda c: lows[c])
    if (worst, lows[worst]) != EXPECT_MAR2['most_expensive_route']:
        bad.append('3월 2주차 가장 비싼 노선 %s %d (원문 %s)'
                   % (worst, lows[worst], EXPECT_MAR2['most_expensive_route']))
    for pat, want in EXPECT_MAR2['avg'].items():
        ps = [d['price'] for d in all_deals if d['pattern'] == pat]
        got = round(sum(ps) / len(ps))
        if got != want:
            bad.append('3월 2주차 %s 평균 %d (원문 %d)' % (pat, got, want))
    via_n = sum(1 for d in all_deals if d['via'])
    if via_n != EXPECT_MAR2['via']:
        bad.append('3월 2주차 경유 최저 %d칸 (원문 %d칸)' % (via_n, EXPECT_MAR2['via']))
    if len(rank) != 24:
        bad.append('3월 2주차 노선별 순위 %d줄 (원문 24줄)' % len(rank))
    else:
        for price, code, date, pat, nights, _desc in rank:
            want = EXPECT_MAR2['route_low'][code]
            if (price, date, pat) != want:
                bad.append('3월 2주차 순위 %s %s (원문 %s)' % (code, (price, date, pat), want))
            low = min(cells[code], key=lambda d: d['price'])
            if (low['price'], low['date'], low['pattern']) != want:
                bad.append('3월 2주차 %s 계산 최저 %s (원문 %s)'
                           % (code, (low['price'], low['date'], low['pattern']), want))
            if nights != 0 and nights != (WD[pat[-1]] - WD[pat[0]]) % 7:
                bad.append('3월 2주차 순위 박수 %s %s' % (code, nights))
    if '**24개 노선 × 5패턴 = 120조합 전수 실측 완료.**' not in text:
        bad.append('3월 2주차 완료 문장(120조합 전수)을 찾지 못했습니다')
    if '**직항이 최저가로 잡힌 조합은 86개, 경유가 최저가로 잡힌 조합은 34개**' not in text:
        bad.append('3월 2주차 직항·경유 문장(86/34)을 찾지 못했습니다')
    return bad


# ── 2) 일본 완결본 ─────────────────────────────────────────────────────────────
def check_jp(text, cells, heads, concl, cover, rank):
    bad = []
    if set(cells) != set(JP_ROUTES):
        bad.append('일본 노선 집합이 다릅니다: %s' % sorted(set(cells) ^ set(JP_ROUTES)))
    for code, want in EXPECT_JP_CELLS.items():
        got = len(cells.get(code) or [])
        if got != want:
            bad.append('일본 %s %d칸 (원문 %d칸)' % (code, got, want))
        if heads.get(code, (None, 0, 0))[1:] != (25, want):
            bad.append('일본 %s 절 머리 %s (기대 25칸 중 %d칸)' % (code, heads.get(code), want))
        if cover.get(code) != (want, 25):
            bad.append('일본 %s 커버리지 %s (기대 %d/25)' % (code, cover.get(code), want))
        prices = [d['price'] for d in cells[code]]
        if min(prices) != EXPECT_JP_LOW[code][0]:
            bad.append('일본 %s 최저 %d (원문 %d)' % (code, min(prices), EXPECT_JP_LOW[code][0]))
        if concl.get(code) != EXPECT_JP_LOW[code]:
            bad.append('일본 %s 결론 %s (원문 %s)' % (code, concl.get(code), EXPECT_JP_LOW[code]))
        hit = next(d for d in cells[code] if d['price'] == min(prices))
        if (hit['date'], hit['pattern']) != EXPECT_JP_LOW[code][1:]:
            bad.append('일본 %s 최저 칸 %s %s (원문 %s %s)'
                       % (code, hit['date'], hit['pattern'], *EXPECT_JP_LOW[code][1:]))
    total = sum(len(v) for v in cells.values())
    if total != 171:
        bad.append('일본 값 %d칸 (원문 171칸)' % total)
    if '7개 노선 × 5주 × 5패턴 = 175칸 가운데 **171칸 실측(98%)**' not in text:
        bad.append('일본 완료 범위 문장(175칸 가운데 171칸)을 찾지 못했습니다')
    if '삿포로(CTS) 25/25' not in text:
        bad.append('일본 삿포로 25/25 문장을 찾지 못했습니다')
    everything = sorted((d['price'], d['date'], d['pattern'], code)
                        for code, v in cells.items() for d in v)
    if len(rank) != 25:
        bad.append('일본 순위표 %d줄 (원문 25줄)' % len(rank))
    else:
        for (rd, rp, _city, price), (p2, d2, pat2, _c2) in zip(rank, everything[:25]):
            if (rd, rp, price) != (d2, pat2, p2):
                bad.append('일본 순위 줄 %s ↔ 계산 %s' % ((rd, rp, price), (d2, pat2, p2)))
    # 삿포로 읽기 절의 연말 비교값(원문에 있는 숫자)
    for need in ('367,800원', '636,500원', '953,600원', '1,040,400원'):
        if need not in text:
            bad.append('일본 원문에 삿포로 값 %s 이 없습니다' % need)
    return bad


# ── 3) 동남아 2~6월 ────────────────────────────────────────────────────────────
def sea_full(mm, dd):
    return '2027-%02d-%02d' % (int(mm), int(dd))


def parse_sea(text):
    cells, cal, psum, msum, heads = {}, {}, {}, {}, {}
    code = pat = None
    for raw in text.splitlines():
        line = raw.strip()
        m = SEA_HEAD.match(line)
        if m:
            city, code = m.groups()
            if code not in SEA_ROUTES:
                raise SystemExit('예상 밖 노선: %s' % line)
            if city != SEA_CITY[code]:
                raise SystemExit('도시 이름이 다릅니다: %s' % line)
            cells[code], cal[code], psum[code], msum[code] = [], {}, {}, {}
            pat = None
            continue
        if line.startswith('## '):
            code = pat = None
            continue
        if code:
            m = SEA_PAT.match(line)
            if m:
                label, nights = m.groups()
                if int(nights) != (WD[label[-1]] - WD[label[0]]) % 7:
                    raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
                pat = label
                continue
            if line.startswith('#'):
                pat = None
                continue
            m = SEA_ROW.match(line)
            if m and pat:
                sm, sd, swd, em, ed, price, airline, via, going, ret, memo = m.groups()
                if WD[swd] != WD[pat[0]]:
                    raise SystemExit('출발 요일이 패턴과 다릅니다: %s' % line)
                date = sea_full(sm, sd)
                if date[5:7] not in ('02', '03', '04', '05', '06'):
                    raise SystemExit('2~6월 밖 출발일입니다: %s' % line)
                back = back_date(date, pat)
                if back != sea_full(em, ed):
                    raise SystemExit('귀국일이 패턴과 다릅니다: %s' % line)
                note = '%s %s · 오는편 %s' % (tidy(via), tidy(going), tidy(ret))
                if memo.strip() and memo.strip() != '—':
                    note += ' · ' + tidy(memo)
                deal = {'date': date, 'back': back, 'pattern': pat, 'price': norm_money(price),
                        'airline': airline.strip(), 'via': not via.strip().startswith('직항'),
                        'note': note}
                am = re.search(r'직항 최저 ([\d,]+)원', memo)
                if am:
                    deal['alt'] = norm_money(am.group(1))
                if any(d['date'] == date and d['pattern'] == pat for d in cells[code]):
                    raise SystemExit('%s %s %s 중복' % (code, date, pat))
                cells[code].append(deal)
                continue
            m = SEA_CAL.match(line)
            if m:
                sm, sd, rest = m.groups()
                values = [v.strip().replace('*', '') for v in rest.split('|')]
                values = [v for v in values if v]
                if len(values) != 5:
                    raise SystemExit('달력 줄 칸 수가 5가 아닙니다: %s' % line)
                thu = sea_full(sm, sd)
                if WD['목'] != datetime.date.fromisoformat(thu).isoweekday() % 7:
                    raise SystemExit('달력 줄이 목요일 주가 아닙니다: %s' % line)
                for label, val in zip(PATTERNS, values):
                    if val == '—':
                        continue
                    if not re.fullmatch(r'[\d,]+', val):
                        raise SystemExit('달력 값이 숫자가 아닙니다: %s' % line)
                    dt = (datetime.date.fromisoformat(thu) +
                          datetime.timedelta(days=(WD[label[0]] - WD['목']) % 7)).isoformat()
                    cal[code][(dt, label)] = norm_money(val)
                continue
            m = SEA_PATSUM.match(line)
            if m:
                label, _n, lo, avg, hi, sm, sd, em, ed = m.groups()
                psum[code][label] = (norm_money(lo), norm_money(avg), norm_money(hi),
                                     sea_full(sm, sd))
                continue
            m = SEA_MONSUM.match(line)
            if m:
                mm, lo, avg, sm, sd, em, ed, label, _n = m.groups()
                msum[code]['2027-%02d' % int(mm)] = (norm_money(lo), norm_money(avg),
                                                    sea_full(sm, sd), label)
                continue
    return cells, cal, psum, msum


def check_sea(text, cells, cal, psum, msum):
    bad = []
    if set(cells) != set(SEA_ROUTES):
        bad.append('동남아 노선 집합이 다릅니다: %s' % sorted(set(cells) ^ set(SEA_ROUTES)))
    total = sum(len(v) for v in cells.values())
    if total != EXPECT_SEA['cells']:
        bad.append('동남아 값 %d칸 (원문 %d칸)' % (total, EXPECT_SEA['cells']))
    for code in SEA_ROUTES:
        deals = cells[code]
        if len(deals) != 105:
            bad.append('동남아 %s %d칸 (105칸이어야 함)' % (code, len(deals)))
        per = collections.Counter(d['pattern'] for d in deals)
        for p in PATTERNS:
            if per.get(p) != 21:
                bad.append('동남아 %s %s %d칸 (21칸이어야 함)' % (code, p, per.get(p)))
        ps = [d['price'] for d in deals]
        want = EXPECT_SEA['per_route'][code]
        if (min(ps), round(sum(ps) / len(ps)), max(ps)) != (want['low'], want['avg'], want['high']):
            bad.append('동남아 %s 최저·평균·최고 %s (원문 %s)'
                       % (code, (min(ps), round(sum(ps) / len(ps)), max(ps)),
                          (want['low'], want['avg'], want['high'])))
        direct = [d['price'] for d in deals if d['via'] is False]
        direct_min = direct + [d['alt'] for d in deals if d.get('alt')]
        if (min(direct_min) if direct_min else None) != want['direct']:
            bad.append('동남아 %s 직항 최저 %s (원문 %d)'
                       % (code, (min(direct_min) if direct_min else None), want['direct']))
        if (len(direct), len(deals) - len(direct)) != (want['direct_n'], want['via_n']):
            bad.append('동남아 %s 직항/경유 %d/%d칸 (원문 %d/%d)'
                       % (code, len(direct), len(deals) - len(direct),
                          want['direct_n'], want['via_n']))
        # 달력형 요약 ↔ 패턴별 표
        if len(cal[code]) != 105:
            bad.append('동남아 %s 달력 %d칸 (105칸이어야 함)' % (code, len(cal[code])))
        mism = [(k, cal[code].get(k), d['price']) for d in deals
                for k in [(d['date'], d['pattern'])] if cal[code].get(k) != d['price']]
        if mism:
            bad.append('동남아 %s 달력·표 불일치 %d건: %s' % (code, len(mism), mism[:4]))
        # 패턴별 요약
        for p, (lo, avg, hi, low_date) in psum[code].items():
            sp = [d['price'] for d in deals if d['pattern'] == p]
            if (min(sp), round(sum(sp) / len(sp)), max(sp)) != (lo, avg, hi):
                bad.append('동남아 %s %s 요약 %s (계산 %s)'
                           % (code, p, (lo, avg, hi), (min(sp), round(sum(sp) / len(sp)), max(sp))))
            if not any(d['pattern'] == p and d['price'] == lo and d['date'] == low_date
                       for d in deals):
                bad.append('동남아 %s %s 최저 일정 %s (원문 %s)' % (code, p, low_date, low_date))
        # 월별 요약
        for mm, (lo, avg, low_date, low_pat) in msum[code].items():
            dp = [d for d in deals if d['date'][:7] == mm]
            sp = [d['price'] for d in dp]
            if (min(sp), round(sum(sp) / len(sp))) != (lo, avg):
                bad.append('동남아 %s %s 월 요약 %s (계산 %s)'
                           % (code, mm, (lo, avg), (min(sp), round(sum(sp) / len(sp)))))
            if not any(d['price'] == lo and d['date'] == low_date and d['pattern'] == low_pat
                       for d in dp):
                bad.append('동남아 %s %s 월 최저 일정 %s %s (원문 %s %s)'
                           % (code, mm, low_date, low_pat, low_date, low_pat))
    # 원문 머리 문장 — 칸 수·노선 요약표
    if '4노선 × 5패턴 × 21주 = 420칸 · 420칸 전부 실제 조회·가격 확인' not in text:
        bad.append('동남아 420칸 완본 문장을 찾지 못했습니다')
    overall = min(d['price'] for v in cells.values() for d in v)
    if overall != EXPECT_SEA['overall_low']:
        bad.append('동남아 전체 최저 %d (원문 %d)' % (overall, EXPECT_SEA['overall_low']))
    return bad


# ── 4) 중국 G1 갱신본 ──────────────────────────────────────────────────────────
def check_cn(text, values, table):
    bad = []
    if len(values) != EXPECT_CN['values']:
        bad.append('중국 값 %d칸 (원문 %d칸)' % (len(values), EXPECT_CN['values']))
    per = collections.Counter(k[2] for k in values)
    if dict(per) != EXPECT_CN['per_pat']:
        bad.append('중국 패턴별 %s (원문 %s)' % (dict(per), EXPECT_CN['per_pat']))
    if len(table) != EXPECT_CN['cells']:
        bad.append('중국 표 %d칸 (원문 420칸)' % len(table))
    gaps = [k for k, v in table.items() if v == '—']
    if len(gaps) != EXPECT_CN['gaps'] or {k[2] for k in gaps} != {'목~월'}:
        bad.append('중국 미조회 %d칸 (원문 목~월 %d칸)' % (len(gaps), EXPECT_CN['gaps']))
    mism = [(k, v['price'], table.get(k)) for k, v in values.items() if table.get(k) != v['price']]
    if mism:
        bad.append('중국 부록·표 불일치 %d건: %s' % (len(mism), mism[:5]))
    for key in gaps:
        if key in values:
            bad.append('중국 미조회 칸이 부록에는 값이 있습니다: %s' % (key,))
    m = re.search(r'\| 실측 완료 \| \*\*([\d,]+)칸\*\*', text)
    n = re.search(r'\| 미조회 \| \*\*([\d,]+)칸\*\*', text)
    z = re.search(r'\| 판매편 없음\(0건\) \| \*\*([\d,]+)칸\*\*', text)
    if not m or not n or not z:
        bad.append('중국 1절 실측 현황 표를 찾지 못했습니다')
    elif (norm_money(m.group(1)), norm_money(n.group(1)), norm_money(z.group(1))) != (384, 36, 0):
        bad.append('중국 실측 현황 %s (원문 384·36·0)'
                   % (norm_money(m.group(1)), norm_money(n.group(1)), norm_money(z.group(1))))
    prices = [d['price'] for d in values.values()]
    if (min(prices), max(prices)) != EXPECT_CN['overall']:
        bad.append('중국 전체 최저·최고 %s (원문 %s)' % ((min(prices), max(prices)), EXPECT_CN['overall']))
    for code, (avg, top, low) in EXPECT_CN['fri'].items():
        mm = re.search(r'- \*\*(선양|다롄|광저우|샤먼) 금~일\*\* 평균 ([\d,]+)원 · 최고 ([\d,]+)원[^·]*· '
                       r'최저 ([\d,]+)원', text)
        ps = [d['price'] for (c, _, p), d in values.items() if c == code and p == '금~일']
        if (round(sum(ps) / len(ps)), max(ps), min(ps)) != (avg, top, low):
            bad.append('중국 %s 금~일 계산 %s (원문 %s)'
                       % (code, (round(sum(ps) / len(ps)), max(ps), min(ps)), (avg, top, low)))
    return bad


def merge(master, values_by_group):
    """(code, date, pattern) 단위로 새 칸만 더한다. 기존 칸은 금액이 같아야 한다."""
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    added, dup, conflicts = [], [], []
    for group in ('MAR2', 'JP', 'SEA', 'CN'):
        for (code, date, pattern), deal in sorted(values_by_group[group].items()):
            r = routes[code]
            have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
            if have is not None:
                if have.get('price') != deal['price']:
                    conflicts.append((group, code, date, pattern, have.get('price'), deal['price']))
                dup.append((group, code, date, pattern))
                continue
            r['deals'].append(deal)
            r['deals'].sort(key=lambda d: d['date'])
            added.append((group, code, date, pattern, deal['price']))
    if conflicts:
        raise SystemExit('기존 금액과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts)
    return added, dup


def recount(fl):
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
    return fl['counts']


def month_note(fl, month, head):
    """그 달의 중국 8노선·동남아 4노선 커버리지를 실제 데이터에서 세어 문장으로 만든다."""
    routes = {r['code']: r for r in fl['routes']}
    pats4 = ('금~일', '토~월', '목~일', '금~월')
    cnt = collections.Counter()
    for code in G1_ROUTES:
        for d in routes[code]['deals']:
            if d['date'][:7] == month and d['pattern'] in pats4:
                cnt[d['pattern']] += 1
    g1_4n = sum(1 for code in G1_ROUTES for d in routes[code]['deals']
                if d['date'][:7] == month and d['pattern'] == '목~월')
    cnt3 = collections.Counter()
    for code in ('YNJ', 'DYG', 'KWL', 'TXN'):
        for d in routes[code]['deals']:
            if d['date'][:7] == month and d['pattern'] in ('금~일', '토~월', '목~일'):
                cnt3[d['pattern']] += 1
    ns = sum(1 for n in fl['noSale'] if n['code'] == 'TXN' and n['date'][:7] == month)
    sea = sum(1 for code in SEA_ROUTES for d in routes[code]['deals'] if d['date'][:7] == month)
    sea_lo = min((d['price'], d['date'], d['pattern'], code)
                 for code in SEA_ROUTES for d in routes[code]['deals']
                 if d['date'][:7] == month) if sea else None
    p4 = ' · '.join('%s %d' % (p, cnt[p]) for p in pats4 if cnt[p])
    p3 = ' · '.join('%s %d' % (p, cnt3[p]) for p in ('금~일', '토~월', '목~일') if cnt3[p])
    txt = (head +
           '중국 8개 노선은 2박(금~일·토~월)에 목~일(3박)·금~월(3박)까지 실측했습니다 — '
           '선양·다롄·광저우·샤먼 %d칸(%s), 연길·장가계·구이린·황산 %d칸(%s)%s입니다. '
           % (sum(cnt[p] for p in pats4), p4,
              sum(cnt3[p] for p in ('금~일', '토~월', '목~일')), p3,
              ('이고 황산 판매편 0건 %d칸' % ns) if ns else ''))
    txt += ('선양·다롄·광저우·샤먼의 목~월(4박)은 2/4~4/22 12주만 실측했습니다' if g1_4n else
            '선양·다롄·광저우·샤먼의 목~월(4박)은 아직 미조회(—)입니다')
    if g1_4n:
        txt += '(%s %d칸)이고 4/29 이후 9주는 미조회(—)입니다. ' % (month, g1_4n)
    else:
        txt += '. '
    if sea:
        txt += ('동남아 4개 노선은 2027년 2~6월 21주 × 5패턴 420칸을 전부 실측했습니다 — %s %d칸이고 '
                '이 달 최저는 %s %s %s %s원입니다.' %
                (month, sea, sea_lo[3], sea_lo[1], sea_lo[2], format(sea_lo[0], ',')))
    return txt


def notes_update(fl):
    routes = {r['code']: r for r in fl['routes']}
    cts = routes['CTS']
    dec = [d for d in cts['deals'] if d['date'].startswith('2026-12') and '~' in d['pattern']
           and d['pattern'].split('~')[0] != d['pattern'].split('~')[1]]
    fl['notes']['2026-12'] = (
        '신규 11개 노선 가운데 필리핀 4개(세부·마닐라·보홀(팡라오)·클락)와 동남아 4개(푸꾸옥·코타키나발루·'
        '쿠알라룸푸르·비엔티안)는 12월 5주 × 5패턴을 실측했습니다 — 동남아는 86칸이고, 비엔티안 12/3 '
        '목~일·목~월 2칸은 항공편은 표시되나 이코노미 판매 가격이 제공되지 않아 빈칸(—)입니다(0건 아님). '
        '일본 신규 7개 노선은 12월 5주 × 5패턴 175칸 가운데 171칸(98%)을 실측했습니다 — 삿포로 25칸까지 '
        '완결됐고(최저 12/10 목~월 367,800원 진에어 직항, 연말은 12/24 목~일 953,600원 vs 12/24 목~월 '
        '636,500원으로 귀국일 하루 차이가 32만원), 시즈오카 21칸(표시 운임이 없는 4칸은 미조회), '
        '가고시마·구마모토·마쓰야마·다카마쓰·미야코지마는 25칸 완결입니다. 당일치기는 삿포로만 '
        '실용적(12/12 574,900원 · 현지 약 6시간 30분)이고 구마모토·시즈오카·다카마쓰는 현지 체류 1시간 '
        '안팎(370,300 · 305,800 · 795,000원), 마쓰야마·미야코지마·가고시마는 성립하지 않습니다.')
    fl['notes']['2027-01'] = (
        '신규 노선의 1월분입니다 — 필리핀 4개 노선 92칸(12/31 주의 1/1·1/2 출발 12칸 포함), 동남아 4개 '
        '노선 92칸(1/28 출발 목~월은 귀국 2027-02-01), 일본 7개 노선은 12/31 주의 1/1·1/2 출발 21칸'
        '(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마 3칸씩 + 삿포로 3칸)만 실측했습니다. '
        '일본 7개 노선의 나머지 1월 주차는 미조회(—)입니다.')
    fl['notes']['2027-02'] = month_note(
        fl, '2027-02',
        '기존 24개 노선은 2027년 2월 1~4주 × 5패턴 480칸을 전부 실측했습니다(1주차 설 연휴 120칸 포함, '
        '빈칸 0칸). ')
    fl['notes']['2027-03'] = month_note(
        fl, '2027-03',
        '기존 24개 노선은 3월 1주차(3/4~8)와 2주차(3/11~15) 5패턴 240칸을 전부 실측했습니다 — '
        '1주차 최저는 후쿠오카 3/4~8 목~월 243,200원(에어부산 직항), 2주차 최저는 후쿠오카 3/11~15 '
        '목~월 238,100원(에어부산 직항), 2주차 최고는 발리 3/11~15 목~월 503,700원(베트남항공 호찌민 '
        '경유)입니다. ')
    fl['notes']['2027-04'] = month_note(fl, '2027-04', '')
    fl['notes']['2027-05'] = month_note(fl, '2027-05', '')
    fl['notes']['2027-06'] = month_note(fl, '2027-06', '')
    fl['notes']['2027-06'] = (fl['notes']['2027-06'].rstrip() +
        ' 기존 24개 노선은 6~11월 조사분 가운데 6월 131칸(주말형 124 · 당일치기 7)이 함께 들어 있습니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='3월 2주차 + 일본 12월 완결 + 동남아 2~6월 + 중국 G1 4박 → flights 병합')
    ap.add_argument('--mar2', default=MD_MAR2)
    ap.add_argument('--jp', default=MD_JP)
    ap.add_argument('--sea', default=MD_SEA)
    ap.add_argument('--cn', default=MD_CN)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    jp7 = load('merge_flights_jp7.py', 'jp7')
    f8 = load('merge_flights_china_26m_final8.py', 'f8')

    t24 = open(args.mar2, encoding='utf-8').read()
    tjp = open(args.jp, encoding='utf-8').read()
    tsea = open(args.sea, encoding='utf-8').read()
    tcn = open(args.cn, encoding='utf-8').read()

    c24, h24, rank24 = parse_mar2(t24)
    cjp, hjp, concl, cover, rankjp = jp7.parse(tjp)
    csea, cal, psum, msum = parse_sea(tsea)
    vcn, gaps_cn = f8.parse_g1_appendix(tcn)
    tabcn, _seen = f8.parse_g1_tables(tcn)

    bad = []
    bad += check_mar2(t24, c24, h24, rank24)
    bad += check_jp(tjp, cjp, hjp, concl, cover, rankjp)
    bad += check_sea(tsea, csea, cal, psum, msum)
    bad += check_cn(tcn, vcn, tabcn)
    print('  3월 2주차 %d칸(노선 %d) · 일본 %d칸 · 동남아 %d칸 · 중국 값 %d칸(표 %d, 미조회 %d)'
          % (sum(len(v) for v in c24.values()), len(c24),
             sum(len(v) for v in cjp.values()), sum(len(v) for v in csea.values()),
             len(vcn), len(tabcn), len(gaps_cn)))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    v24 = {(c, d['date'], d['pattern']): d for c, v in c24.items() for d in v}
    vjp = {(c, d['date'], d['pattern']): d for c, v in cjp.items() for d in v}
    vsea = {(c, d['date'], d['pattern']): d for c, v in csea.items() for d in v}

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']

    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    sources_before = json.dumps(master.get('sources'), ensure_ascii=False)
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    target_codes = set(MAR2_ROUTES) | set(JP_ROUTES) | set(SEA_ROUTES) | set(G1_ROUTES)
    other_codes = set(r['code'] for r in fl['routes']) - target_codes
    before_other = json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                              ensure_ascii=False, sort_keys=True)
    edited_notes = ('2026-12', '2027-01', '2027-02', '2027-03', '2027-04', '2027-05', '2027-06')
    before_notes_other = {k: v for k, v in fl['notes'].items() if k not in edited_notes}
    before_within = {}
    for r in fl['routes']:
        if r['code'] in target_codes:
            for d in r['deals']:
                before_within[(r['code'], d['date'], d['pattern'])] = json.dumps(
                    d, ensure_ascii=False, sort_keys=True)

    added, dup = merge(master, {'MAR2': v24, 'JP': vjp, 'SEA': vsea, 'CN': vcn})
    by_add = collections.Counter(a[0] for a in added)
    by_dup = collections.Counter(d[0] for d in dup)
    want = {'MAR2': (0, 120), 'JP': (150, EXPECT_JP_NEW), 'SEA': (0, 420), 'CN': (336, 48)}
    for g, (dw, aw) in want.items():
        if (by_dup[g], by_add[g]) != (dw, aw):
            raise SystemExit('%s 중복/신규 %d/%d (기대 %d/%d)'
                             % (g, by_dup[g], by_add[g], dw, aw))
    for code, want_dup in EXPECT_JP_DUP.items():
        got = sum(1 for d in dup if d[0] == 'JP' and d[1] == code)
        if got != want_dup:
            raise SystemExit('일본 %s 중복 %d칸 (기대 %d칸)' % (code, got, want_dup))

    counts = recount(fl)
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = counts['total']
    notes_update(fl)

    # 보존 검증
    if counts['total'] != EXPECT_TOTAL:
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], EXPECT_TOTAL))
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps(master.get('sources'), ensure_ascii=False) != sources_before:
        raise SystemExit('출처 목록이 바뀌었습니다.')
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다.')
    if json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True) != nosale_before:
        raise SystemExit('판매편 0건 기록이 바뀌었습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다.')
    if {k: v for k, v in fl['notes'].items() if k not in edited_notes} != before_notes_other:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다.')
    after_within = {}
    for r in fl['routes']:
        if r['code'] in target_codes:
            for d in r['deals']:
                after_within[(r['code'], d['date'], d['pattern'])] = json.dumps(
                    d, ensure_ascii=False, sort_keys=True)
    lost = [k for k, v in before_within.items() if after_within.get(k) != v]
    if lost:
        raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % lost[:5])
    for r in fl['routes']:
        keys = [(d['date'], d['pattern']) for d in r['deals']]
        if len(keys) != len(set(keys)):
            raise SystemExit('%s (출발일·패턴) 중복' % r['code'])

    print('신규 %d칸 (3월 2주차 %d · 일본 %d · 동남아 %d · 중국 %d)'
          % (len(added), by_add['MAR2'], by_add['JP'], by_add['SEA'], by_add['CN']))
    print('중복 %d칸 (일본 %d · 중국 %d)' % (len(dup), by_dup['JP'], by_dup['CN']))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'], counts['daytrip']))
    print('월별: %s' % counts['byMonth'])
    print('월별 증가: %s' % {m: counts['byMonth'].get(m, 0) - before_by_month.get(m, 0)
                            for m in counts['byMonth']})
    print('노선별 건수: %s' % ', '.join(
        '%s %d' % (r['code'], len(r['deals'])) for r in fl['routes'] if r['code'] in target_codes))
    print('holiday %d · daytrip %d' % (counts['holiday'], counts['daytrip']))

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        return 0
    if args.note:
        master['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
    os.replace(tmp, MASTER)
    print('저장: %s' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
