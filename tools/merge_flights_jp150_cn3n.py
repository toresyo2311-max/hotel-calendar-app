#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 항공 특가 **최종 3건**을 `data/master_db.json` 의 `flights` 에 한꺼번에 병합한다.

  1) 일본 신규 7개 노선 12월 **보완본(90 → 150칸 + 당일치기 실측)** — 5번 보고
     `data-sources/flights-jp-new7/부산출발-일본7노선-12월-보완.md`
     마쓰야마(MYJ)·다카마쓰(TAK)·미야코지마(MMY) 25칸 완결(각 +20칸) + 삿포로·시즈오카·가고시마·
     구마모토는 기존과 금액이 같아 중복 90칸 → **신규 60칸**. 당일치기 실측 4칸
     (삿포로 12/12 574,900원 · 구마모토 12/16 370,300원 · 시즈오카 12/9 305,800원 ·
     다카마쓰 12/24 795,000원)과 노선별 `daytrip` 메타(가능/짧음/불가)를 원문대로 다시 쓴다.
  2) 중국 G1 4개 노선(선양·다롄·광저우·샤먼) 2~6월 **금~월(3박) 84칸 완주본**
     `data-sources/flights-china-new8/부산출발-중국4노선-선양다롄광저우샤먼-2_6월-2박.md`
     누적 336/420칸 — 2박 168 + 목~일 84(기존 반영) + 금~월 84. 금~월 중 선양 2/5~8 1칸은
     기존이라 **신규 83칸**, 목~일·금~일·토~월 252칸은 중복.
  3) 중국 G2 4개 노선(연길·장가계·구이린·황산) 2~6월 **목~일(3박) 84칸 완주본**
     `data-sources/flights-china-new8/부산출발-중국4노선-연길장가계구이린황산-2_6월-금일.md`
     누적 252/420칸 — 금~일·토~월 값 148칸 + 0건 20칸(기존 반영) + 목~일 84칸 → **신규 84칸**.

읽는 곳: 세 원문의 부록 '병합용 줄'(일본은 `- 날짜 · 패턴 · 도시 · 금액원` 목록)과 실측표.
  · 일본 — `### 부산–삿포로(신치토세) (CTS) · 25칸 중 4칸 실측` 아래 `- 2026-12-03 · 목~일 · 삿포로 · 420,480원`
  · G1 — `- 2027-02-04 · 목~일 · PUS–XMN · 651,100원 · 이스타항공 · 직항 2h50`
  · G2 — `- 2027-03-27(토) · 토~월(2박) · PUS–TXN · 954,600원 · Air China · 경유(Beijing 22h 45m, 총 27h 30m)`
  · 0건 — `- 2027-03-20(토) · 토~월(2박) · PUS–TXN · 판매편 없음(0건)` → 기존 `noSale` 과 대조(신규 0칸)
  · 미조회 — 표의 `—`·`미측정` → 넣지 않고 gaps 로만 센다.

규칙:
  · 값(가격·날짜·소요시간)은 원문 그대로. 항공사·경유지 이름만 앱 표기(한국어)로 옮긴다.
  · 원문 표와 부록 줄을 **(노선·출발일·패턴) 단위 전수** 대조하고, 원문이 말하는 칸 수·노선별
    커버리지·최저/최고·평균·순위표를 파싱 결과와 맞춘다 — 하나라도 다르면 멈춘다.
  · 이미 있는 칸은 중복으로 넣지 않고, **기존 금액이 하나라도 달라지면 멈춘다**
    (기존 항공사·경유 표기는 그대로 보존).
  · 호텔 538곳 · 아코르 SNU 43줄 · 출처 목록 · 패턴 정의 · `noSale` · 다른 노선은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)와 2026-12 ~ 2027-06 `notes`(커버리지 문구)를 다시 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jp150_cn3n.py --dry-run
    python3 tools/merge_flights_jp150_cn3n.py
"""
import argparse
import collections
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.join(os.path.dirname(ROOT), '..', 'data-sources')
SRC = os.path.normpath(SRC)
MD_JP = os.path.join(SRC, 'flights-jp-new7', '부산출발-일본7노선-12월-보완.md')
MD_G1 = os.path.join(SRC, 'flights-china-new8', '부산출발-중국4노선-선양다롄광저우샤먼-2_6월-2박.md')
MD_G2 = os.path.join(SRC, 'flights-china-new8', '부산출발-중국4노선-연길장가계구이린황산-2_6월-금일.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
JP_ROUTES = ('CTS', 'FSZ', 'KOJ', 'KMJ', 'MYJ', 'TAK', 'MMY')
G1_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN')
G2_ROUTES = ('YNJ', 'DYG', 'KWL', 'TXN')
PUS4 = ('SHE', 'DLC', 'CAN', 'XMN')
CITY_G1 = {'SHE': '선양', 'DLC': '다롄', 'CAN': '광저우', 'XMN': '샤먼'}

# 원문이 말하는 칸 수 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT_JP_CELLS = {'CTS': 4, 'FSZ': 21, 'KOJ': 25, 'KMJ': 25, 'MYJ': 25, 'TAK': 25, 'MMY': 25}
EXPECT_JP_DUP = {'CTS': 4, 'FSZ': 21, 'KOJ': 25, 'KMJ': 25, 'MYJ': 5, 'TAK': 5, 'MMY': 5}
EXPECT_JP_NEW = 60
EXPECT_JP_LOW = {'CTS': (416500, '2026-12-05', '토~월'), 'FSZ': (276900, '2026-12-03', '목~월'),
                 'KOJ': (427000, '2026-12-18', '금~일'), 'KMJ': (242800, '2026-12-03', '목~월'),
                 'MYJ': (274300, '2026-12-03', '목~월'), 'TAK': (259300, '2026-12-12', '토~월'),
                 'MMY': (317500, '2026-12-17', '목~일')}
# 당일치기 실측 — 원문 3절의 값 그대로(그 문자열이 원문에도 있는지 확인한다)
JP_DAYTRIP_DEALS = [
    # code, date, pattern, price, airline, via, note, 원문 확인용 문자열, alt(직항 조합)
    ('CTS', '2026-12-12', '토~토', 574900, None, None,
     '13:50 출국·늦은 귀국 조합의 표시 최저 — 09:00 출국+18:00 귀국이면 현지 약 6시간 30분 · '
     '12/26 같은 조건은 2,184,000원',
     '574,900원', 662100),
    ('KMJ', '2026-12-16', '수~수', 370300, '이스타항공', False,
     '직항 11:55→13:25 / 귀국 14:30→15:55 · 현지 1시간 5분 · 12/12는 1,026,200원(잔여 9석 미만)',
     '370,300원', 0),
    ('FSZ', '2026-12-09', '수~수', 305800, '에어부산', False,
     '직항 09:05→10:45 / 귀국 12:00→14:00 · 현지 1시간 15분 · 12/12는 453,500원',
     '305,800원', 0),
    ('TAK', '2026-12-24', '목~목', 795000, '에어부산', False,
     '직항 15:55→17:20 / 귀국 18:20→20:00 · 현지 1시간 · 직항이 없는 날은 경유 8시간 이상이라 성립하지 않음',
     '795,000원', 0),
]
# 노선별 daytrip 메타 — 원문 3절(당일치기) 결론 그대로
JP_DAYTRIP_META = {
    'CTS': {'status': 'ok', 'stay': '약 6시간 30분',
            'note': '09:00 출국 + 18:00 귀국 조합이면 현지 약 6시간 30분 — 7개 노선 중 당일치기가 실용적인 '
                    '유일한 노선 · 표시 최저 574,900원(2026-12-12, 13:50 출국·늦은 귀국 조합) · '
                    '직항 조합은 662,100원 · 연말은 12/26 2,184,000원까지 오르고 12/5~12/19 중 당일 왕복은 '
                    '12/12 하루입니다',
            'short': ''},
    'KMJ': {'status': 'short', 'stay': '1시간 5분',
            'note': '이스타항공 직항 11:55 → 13:25 · 귀국 직항 14:30 → 15:55 — 형식상 성립하나 현지 체류 '
                    '1시간 5분 · 표시 최저 370,300원(2026-12-16), 12/12는 1,026,200원(직항 1편·잔여 9석 미만) · '
                    '12/5~12/19 가운데 12/9만 항공편 없음',
            'short': '현지 1시간 5분'},
    'FSZ': {'status': 'short', 'stay': '1시간 15분',
            'note': '에어부산 직항 09:05 → 10:45 · 귀국 직항 12:00 → 14:00 — 직항이 뜨는 날만 성립(현지 체류 '
                    '1시간 15분) · 표시 최저 305,800원(2026-12-09), 12/12는 453,500원 · '
                    '12/5~12/19 중 7일만 성립',
            'short': '직항 있는 날만'},
    'TAK': {'status': 'short', 'stay': '1시간',
            'note': '에어부산 직항이 일부 날짜에만 운항(2026-12-24 15:55 → 17:20, 귀국 18:20 → 20:00) — '
                    '직항이 있는 날만 성립하고 현지 체류 1시간 · 표시 795,000원(2026-12-24) · 직항이 없는 날은 '
                    '경유 8시간 이상이라 12/17~12/31 중 4일만 성립',
            'short': '직항 4일만'},
    'MMY': {'status': 'no', 'stay': '',
            'note': '출국 직항(진에어 12:55 → 15:20)만 확인되고 조회일(2026-12-12)에 귀국 직항이 없음 — '
                    '같은 날 귀국은 서울 경유 총 5시간 40분~뿐 · 12/5~12/19 당일 왕복 조회는 전 날짜 '
                    '항공편 없음',
            'short': '귀국 직항 없음'},
    'MYJ': {'status': 'no', 'stay': '',
            'note': '에어부산 직항이 16:35 출발(17:40 도착) 하루 1편뿐이라 오전 출국·당일 귀국이 성립하지 않음 — '
                    '직항으로는 당일치기가 사실상 불가',
            'short': '직항 16:35 출발 1편'},
    'KOJ': {'status': 'no', 'stay': '',
            'note': '부산–가고시마 직항이 검색되지 않음 — 서울 경유(대한항공, 총 4시간 20분~) 또는 '
                    '마쓰야마 경유(에어부산+JAL, 총 4시간 40분)뿐이라 같은 날 왕복이 성립하지 않음',
            'short': '직항 없음·경유 4시간 20분↑'},
}

EXPECT_G1 = {'cells': 336, 'gaps': 84,
             'per': {'목~일': 84, '금~일': 84, '토~월': 84, '금~월': 84, '목~월': 0},
             'overall': (373100, 884000),      # 다롄 3/11~14 목~일 · 샤먼 2/6~8 토~월
             'fri': {'SHE': (538167, 713600, 463500), 'DLC': (466567, 607100, 373300),
                     'CAN': (545043, 775200, 501100), 'XMN': (555929, 758400, 464500)},
             'dup': 253, 'new': 83}
EXPECT_G2 = {'values': 232, 'nosale': 20, 'gaps': 168,
             'per': {'목~일': 84, '토~월': 77, '금~일': 71},
             'per_nosale': {'금~일': 13, '토~월': 7},
             'minmax': {'YNJ': (455700, 927100), 'DYG': (686700, 904100),
                        'KWL': (526600, 879900), 'TXN': (791900, 2588000)},
             'dup': 148, 'new': 84}
EXPECT_TOTAL = 3649
PREV_TOTAL = 3418


def load(mod, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, mod))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def num(pattern, text, name):
    m = re.search(pattern, text)
    if not m:
        raise SystemExit('요약 문장을 찾지 못했습니다: %s' % name)
    return int(m.group(1).replace(',', ''))


def check_jp(text, cells, heads, concl, cover, rank):
    """일본 보완본 — 원문이 말하는 칸 수·커버리지·최저가·순위표와 파싱 결과를 전수 대조."""
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
            bad.append('일본 %s 최저 %d (기대 %d)' % (code, min(prices), EXPECT_JP_LOW[code][0]))
        if concl.get(code) != EXPECT_JP_LOW[code]:
            bad.append('일본 %s 결론 %s (기대 %s)' % (code, concl.get(code), EXPECT_JP_LOW[code]))
        hit = next(d for d in cells[code] if d['price'] == min(prices))
        if (hit['date'], hit['pattern']) != EXPECT_JP_LOW[code][1:]:
            bad.append('일본 %s 최저 칸 %s %s (원문 %s %s)'
                       % (code, hit['date'], hit['pattern'], *EXPECT_JP_LOW[code][1:]))
    total = sum(len(v) for v in cells.values())
    if total != 150:
        bad.append('일본 값 %d칸 (기대 150칸)' % total)
    if '7개 노선 × 5주 × 5패턴 = 175칸 가운데 **150칸 실측(86%)**' not in text:
        bad.append('원문 완료 범위 문장(175칸 가운데 150칸)을 찾지 못했습니다')
    # 12월 최저가 순위 25줄 ↔ 계산값
    everything = sorted((d['price'], d['date'], d['pattern'], code)
                        for code, v in cells.items() for d in v)
    if len(rank) != 25:
        bad.append('일본 순위표 %d줄 (기대 25줄)' % len(rank))
    else:
        for (rd, rp, _city, price), (p2, d2, pat2, _c2) in zip(rank, everything[:25]):
            if (rd, rp, price) != (d2, pat2, p2):
                bad.append('일본 순위 줄 %s ↔ 계산 %s' % ((rd, rp, price), (d2, pat2, p2)))
    return bad


def check_jp_daytrip(text):
    bad = []
    for _c, _d, _p, _pr, _a, _v, _n, need, _alt in JP_DAYTRIP_DEALS:
        if need not in text:
            bad.append('일본 원문에 당일치기 값 %s 이 없습니다' % need)
    for need in ('662,100원', '2,184,000원', '1,026,200원', '453,500원'):
        if need not in text:
            bad.append('일본 원문에 당일치기 비교값 %s 이 없습니다' % need)
    if '실용적인 당일치기는 삿포로뿐' not in text:
        bad.append('일본 원문 3절 결론(삿포로만 실용적)을 찾지 못했습니다')
    for code in ('MMY', 'MYJ', 'KOJ'):
        if JP_DAYTRIP_META[code]['status'] != 'no':
            bad.append('일본 %s daytrip 이 불가가 아닙니다' % code)
    return bad


def check_g1(text, values, table):
    bad = []
    if len(values) != EXPECT_G1['cells']:
        bad.append('G1 값 %d칸 (기대 %d칸)' % (len(values), EXPECT_G1['cells']))
    per = collections.Counter(k[2] for k in values)
    for pat, want in EXPECT_G1['per'].items():
        if per.get(pat, 0) != want:
            bad.append('G1 %s %d칸 (기대 %d칸)' % (pat, per.get(pat, 0), want))
    if len(table) != 420:
        bad.append('G1 표 %d칸 (기대 420칸)' % len(table))
    gaps = [k for k, v in table.items() if v == '—']
    if len(gaps) != EXPECT_G1['gaps'] or {k[2] for k in gaps} != {'목~월'}:
        bad.append('G1 미조회 %d칸 (기대 목~월 %d칸)' % (len(gaps), EXPECT_G1['gaps']))
    mism = [(k, v['price'], table.get(k)) for k, v in values.items() if table.get(k) != v['price']]
    if mism:
        bad.append('G1 부록·표 불일치 %d건: %s' % (len(mism), mism[:5]))
    for key in gaps:
        if key in values:
            bad.append('G1 미조회 칸이 부록에는 값이 있습니다: %s' % (key,))
    grid = num(r'\| 전체 격자 \| \*\*([\d,]+)칸\*\*', text, 'G1 격자')
    done = num(r'\| 실측 완료 \| \*\*([\d,]+)칸\*\*', text, 'G1 실측')
    zero = num(r'\| 판매편 없음\(0건\) \| \*\*([\d,]+)칸\*\*', text, 'G1 0건')
    rest = num(r'\| 미조회 \| \*\*([\d,]+)칸\*\*', text, 'G1 미조회')
    if (grid, done, zero, rest) != (420, 336, 0, 84):
        bad.append('G1 요약 칸 수 %s (기대 420·336·0·84)' % ((grid, done, zero, rest),))
    prices = [d['price'] for d in values.values()]
    if (min(prices), max(prices)) != EXPECT_G1['overall']:
        bad.append('G1 전체 최저·최고 %s (기대 %s)' % ((min(prices), max(prices)), EXPECT_G1['overall']))
    for code, (avg, top, low) in EXPECT_G1['fri'].items():
        m = re.search(r'- \*\*%s 금~일\*\* 평균 ([\d,]+)원 · 최고 ([\d,]+)원[^·]*· 최저 ([\d,]+)원'
                      % CITY_G1[code], text)
        if not m:
            raise SystemExit('G1 5절 금~일 요약을 찾지 못했습니다: %s' % code)
        got = tuple(int(x.replace(',', '')) for x in m.groups())
        if got != (avg, top, low):
            bad.append('G1 %s 금~일 요약 %s (기대 %s)' % (code, got, (avg, top, low)))
        ps = [d['price'] for (c, _, p), d in values.items() if c == code and p == '금~일']
        if (round(sum(ps) / len(ps)), max(ps), min(ps)) != (avg, top, low):
            bad.append('G1 %s 금~일 계산 %s (요약 %s)'
                       % (code, (round(sum(ps) / len(ps)), max(ps), min(ps)), (avg, top, low)))
    return bad


def check_g2(text, values, nosale, gaps, table):
    bad = []
    if len(values) != EXPECT_G2['values']:
        bad.append('G2 값 %d칸 (기대 %d칸)' % (len(values), EXPECT_G2['values']))
    if len(nosale) != EXPECT_G2['nosale']:
        bad.append('G2 0건 %d칸 (기대 %d칸)' % (len(nosale), EXPECT_G2['nosale']))
    if len(gaps) != EXPECT_G2['gaps']:
        bad.append('G2 미조회 %d칸 (기대 %d칸)' % (len(gaps), EXPECT_G2['gaps']))
    per = collections.Counter(k[2] for k in values)
    for pat, want in EXPECT_G2['per'].items():
        if per.get(pat, 0) != want:
            bad.append('G2 %s 값 %d칸 (기대 %d칸)' % (pat, per.get(pat, 0), want))
    perns = collections.Counter(k[2] for k in nosale)
    if dict(perns) != EXPECT_G2['per_nosale']:
        bad.append('G2 0건 패턴별 %s (기대 %s)' % (dict(perns), EXPECT_G2['per_nosale']))
    if {k[2] for k in gaps} != {'금~월', '목~월'} or len(gaps) != 168:
        bad.append('G2 미조회 패턴이 금~월·목~월 168칸이 아닙니다')
    if len(table) != 420:
        bad.append('G2 표 %d칸 (기대 420칸)' % len(table))
    mism = []
    for k, v in values.items():
        if table.get(k) != v['price']:
            mism.append(('값', k, v['price'], table.get(k)))
    for k in nosale:
        if table.get(k) != 'NOSALE':
            mism.append(('0건', k, 'NOSALE', table.get(k)))
    if mism:
        bad.append('G2 부록·표 불일치 %d건: %s' % (len(mism), mism[:5]))
    for code in G2_ROUTES:
        got = sorted(k[1] for k in values if k[2] == '목~일' and k[0] == code)
        if len(got) != 21:
            bad.append('G2 %s 목~일 %d주 (기대 21주)' % (code, len(got)))
    if '4노선 × 21주 × 5패턴 = **420칸 중 252칸' not in text:
        bad.append('G2 커버리지 문장(420칸 중 252칸)을 찾지 못했습니다')
    for code, (low, top) in EXPECT_G2['minmax'].items():
        ps = [d['price'] for (c, _, _), d in values.items() if c == code]
        if (min(ps), max(ps)) != (low, top):
            bad.append('G2 %s 최저·최고 %s (기대 %s)' % (code, (min(ps), max(ps)), (low, top)))
    for code in G2_ROUTES:
        if not re.search(r'\| [^|]+ \(%s\) \| 63/105 \|' % code, text):
            bad.append('G2 1절 요약표(%s 63/105)를 찾지 못했습니다' % code)
    return bad


def merge(master, values_by_group):
    """(code, date, pattern) 단위로 새 칸만 더한다. 기존 칸은 금액이 같아야 한다."""
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    added, dup, conflicts = [], [], []
    for group in ('G1', 'G2', 'JP'):
        values = values_by_group[group]
        for (code, date, pattern), deal in sorted(values.items()):
            r = routes[code]
            have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
            if have is not None:
                if have.get('price') != deal['price']:
                    conflicts.append((group, code, date, pattern, have.get('price'), deal['price']))
                dup.append((group, code, date, pattern))
                continue
            r['deals'].append(deal)
            r['deals'].sort(key=lambda d: d['date'])     # 안정 정렬 — 같은 날 기존 순서 유지
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
    """그 달 중국 8개 노선 커버리지를 실제 데이터에서 세어 문장으로 만든다."""
    routes = {r['code']: r for r in fl['routes']}
    pats4 = ('금~일', '토~월', '목~일', '금~월')
    cnt = collections.Counter()
    for code in PUS4:
        for d in routes[code]['deals']:
            if d['date'][:7] == month and d['pattern'] in pats4:
                cnt[d['pattern']] += 1
    cnt3 = collections.Counter()
    for code in G2_ROUTES:
        for d in routes[code]['deals']:
            if d['date'][:7] == month and d['pattern'] in ('금~일', '토~월', '목~일'):
                cnt3[d['pattern']] += 1
    ns = sum(1 for n in fl['noSale'] if n['code'] == 'TXN' and n['date'][:7] == month)
    p4 = ' · '.join('%s %d' % (p, cnt[p]) for p in pats4 if cnt[p])
    p3 = ' · '.join('%s %d' % (p, cnt3[p]) for p in ('금~일', '토~월', '목~일') if cnt3[p])
    return (head +
            '중국 8개 노선은 2박(금~일·토~월)에 목~일(3박)·금~월(3박)까지 실측했습니다 — '
            '선양·다롄·광저우·샤먼 %d칸(%s), 연길·장가계·구이린·황산 %d칸(%s)%s입니다. '
            '중국 8개 노선의 목~월(4박) 84칸은 아직 미조회(—)입니다.'
            % (sum(cnt[p] for p in pats4), p4,
               sum(cnt3[p] for p in ('금~일', '토~월', '목~일')), p3,
               ('이고 황산 판매편 0건 %d칸' % ns) if ns else ''))


def notes_update(fl):
    fl['notes']['2026-12'] = (
        '신규 11개 노선 가운데 필리핀 4개(세부·마닐라·보홀(팡라오)·클락)와 동남아 4개(푸꾸옥·코타키나발루·'
        '쿠알라룸푸르·비엔티안)는 12월 5주 × 5패턴을 실측했습니다 — 동남아는 86칸이고, 비엔티안 12/3 '
        '목~일·목~월 2칸은 항공편은 표시되나 이코노미 판매 가격이 제공되지 않아 빈칸(—)입니다(0건 아님). '
        '일본 신규 7개 노선은 12월 5주 × 5패턴 175칸 가운데 **150칸(86%)**을 실측했습니다 — 마쓰야마·'
        '다카마쓰·미야코지마가 25칸으로 완결됐고(최저 마쓰야마 274,300 · 다카마쓰 259,300 · 미야코지마 '
        '317,500원), 구마모토 25 · 가고시마 25 · 시즈오카 21 · 삿포로 4칸입니다. 삿포로 21칸은 날짜별 '
        '가격표가 열리지 않아, 시즈오카 4칸은 표시 운임이 없는 날이라 미조회(—)입니다. 당일치기는 '
        '**삿포로만 실용적**(12/12 574,900원 · 현지 약 6시간 30분)이고 구마모토·시즈오카·다카마쓰는 현지 '
        '체류 1시간 안팎(370,300 · 305,800 · 795,000원), 마쓰야마·미야코지마·가고시마는 성립하지 않습니다.')
    fl['notes']['2027-01'] = (
        '신규 노선의 1월분입니다 — 필리핀 4개 노선 92칸(12/31 주의 1/1·1/2 출발 12칸 포함), 동남아 4개 '
        '노선 92칸(1/28 출발 목~월은 귀국 2027-02-01), 일본 7개 노선은 12/31 주의 1/1·1/2 출발 18칸'
        '(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마 3칸씩)만 실측했습니다. 일본 7개 노선의 '
        '나머지 1월 주차는 미조회(—)입니다.')
    fl['notes']['2027-02'] = month_note(
        fl, '2027-02',
        '기존 24개 노선은 2027년 2월 1~4주 × 5패턴 480칸을 전부 실측했습니다(1주차 설 연휴 120칸 포함, '
        '빈칸 0칸). ')
    fl['notes']['2027-03'] = month_note(
        fl, '2027-03',
        '기존 24개 노선은 3월 1주차(3/4~8) 5패턴 120칸을 전부 실측했습니다 — 전체 최저는 후쿠오카 3/4~8 '
        '목~월 243,200원(에어부산 직항), 최고는 발리 3/4~8 목~월 564,600원(베트남항공 호찌민 경유)입니다. ')
    fl['notes']['2027-04'] = month_note(fl, '2027-04', '')
    fl['notes']['2027-05'] = month_note(fl, '2027-05', '')
    fl['notes']['2027-06'] = month_note(fl, '2027-06', '')


def main(argv):
    ap = argparse.ArgumentParser(description='일본 150칸 보완 + 중국 3박 완주본 2건 → master_db.json flights 병합')
    ap.add_argument('--jp', default=MD_JP)
    ap.add_argument('--g1', default=MD_G1)
    ap.add_argument('--g2', default=MD_G2)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    jp7 = load('merge_flights_jp7.py', 'jp7')
    f8 = load('merge_flights_china_26m_final8.py', 'f8')

    tjp = open(args.jp, encoding='utf-8').read()
    t1 = open(args.g1, encoding='utf-8').read()
    t2 = open(args.g2, encoding='utf-8').read()

    cells, heads, concl, cover, rank = jp7.parse(tjp)
    jp_values = {(code, d['date'], d['pattern']): d for code, v in cells.items() for d in v}
    v1, _g1 = f8.parse_g1_appendix(t1)
    tab1, _s1 = f8.parse_g1_tables(t1)
    v2, ns2, g2 = f8.parse_g2_appendix(t2)
    tab2, _s2 = f8.parse_g2_tables(t2)

    bad = []
    bad += check_jp(tjp, cells, heads, concl, cover, rank)
    bad += check_jp_daytrip(tjp)
    bad += check_g1(t1, v1, tab1)
    bad += check_g2(t2, v2, ns2, g2, tab2)
    print('  일본 %d칸 · G1 %d칸(표 %d) · G2 값 %d + 0건 %d칸(표 %d, 미조회 %d)'
          % (sum(len(v) for v in cells.values()), len(v1), len(tab1), len(v2), len(ns2),
             len(tab2), len(g2)))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']

    # 0) 원문의 판매편 0건 칸은 이미 noSale 에 있어야 한다(이번 병합으로 새로 생기는 0건 없음)
    known_ns = {(n['code'], n['date'], n['pattern']) for n in fl['noSale']}
    missing_ns = sorted(k for k in ns2 if k not in known_ns)
    if missing_ns:
        raise SystemExit('G2 0건 칸이 master_db.noSale 에 없습니다: %s' % missing_ns)

    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    sources_before = json.dumps(master.get('sources'), ensure_ascii=False)
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    target_codes = set(JP_ROUTES) | set(G1_ROUTES) | set(G2_ROUTES)
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

    # 1) 본 데이터 병합
    added, dup = merge(master, {'G1': v1, 'G2': v2, 'JP': jp_values})
    by_group_add = collections.Counter(a[0] for a in added)
    by_group_dup = collections.Counter(d[0] for d in dup)
    if (by_group_dup['G1'], by_group_add['G1']) != (EXPECT_G1['dup'], EXPECT_G1['new']):
        raise SystemExit('G1 중복/신규 %d/%d (기대 %d/%d)'
                         % (by_group_dup['G1'], by_group_add['G1'], EXPECT_G1['dup'], EXPECT_G1['new']))
    if (by_group_dup['G2'], by_group_add['G2']) != (EXPECT_G2['dup'], EXPECT_G2['new']):
        raise SystemExit('G2 중복/신규 %d/%d (기대 %d/%d)'
                         % (by_group_dup['G2'], by_group_add['G2'], EXPECT_G2['dup'], EXPECT_G2['new']))
    if (by_group_dup['JP'], by_group_add['JP']) != (90, EXPECT_JP_NEW):
        raise SystemExit('일본 중복/신규 %d/%d (기대 90/%d)'
                         % (by_group_dup['JP'], by_group_add['JP'], EXPECT_JP_NEW))
    for code, want in EXPECT_JP_DUP.items():
        got = sum(1 for d in dup if d[0] == 'JP' and d[1] == code)
        if got != want:
            raise SystemExit('일본 %s 중복 %d칸 (기대 %d칸)' % (code, got, want))

    # 2) 당일치기 실측 4칸 + 노선별 daytrip 메타
    routes = {r['code']: r for r in fl['routes']}
    day_added = []
    for code, date, pattern, price, airline, via, note, _need, alt in JP_DAYTRIP_DEALS:
        r = routes[code]
        if any(d['date'] == date and d['pattern'] == pattern for d in r['deals']):
            raise SystemExit('%s %s %s 당일치기 칸이 이미 있습니다' % (code, date, pattern))
        if pattern.split('~')[0] != pattern.split('~')[1]:
            raise SystemExit('%s %s 는 0박 패턴이 아닙니다' % (code, pattern))
        deal = {'date': date, 'back': date, 'pattern': pattern, 'price': price}
        if airline:
            deal['airline'] = airline
        if via is not None:
            deal['via'] = via
        if alt:
            deal['alt'] = alt
        deal['note'] = note
        r['deals'].append(deal)
        r['deals'].sort(key=lambda d: d['date'])
        day_added.append((code, date, pattern, price))
    if len(day_added) != 4:
        raise SystemExit('당일치기 신규 %d칸 (기대 4칸)' % len(day_added))
    for code, meta in JP_DAYTRIP_META.items():
        routes[code]['daytrip'] = dict(meta)

    counts = recount(fl)
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = counts['total']

    # 3) 월별 notes 재작성
    notes_update(fl)

    # 4) 보존 검증
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

    # 5) 결과 보고
    print('신규 %d칸 (G1 %d · G2 %d · 일본 %d) + 당일치기 %d칸'
          % (len(added), by_group_add['G1'], by_group_add['G2'], by_group_add['JP'], len(day_added)))
    print('중복 %d칸 (G1 %d · G2 %d · 일본 %d)'
          % (len(dup), by_group_dup['G1'], by_group_dup['G2'], by_group_dup['JP']))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'], counts['daytrip']))
    print('월별: %s' % counts['byMonth'])
    print('월별 증가: %s' % {m: counts['byMonth'].get(m, 0) - before_by_month.get(m, 0)
                            for m in counts['byMonth']})
    print('노선별 건수: %s' % ', '.join(
        '%s %d' % (r['code'], len(r['deals'])) for r in fl['routes'] if r['code'] in target_codes))
    print('당일치기 메타: %s' % ', '.join('%s %s' % (c, routes[c]['daytrip']['status'])
                                        for c in JP_ROUTES))

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
