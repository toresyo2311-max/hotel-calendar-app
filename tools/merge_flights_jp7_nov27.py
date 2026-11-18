#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 일본 신규 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)
**2027년 11월 4주 × 5패턴 140칸**을 `data/master_db.json` 의 `flights` 에 병합한다.

원본 7개(노선별 파일 구조가 서로 다르다):
  data-sources/flights-jp-new7/부산출발-일본7노선-{구마모토,가고시마,시즈오카,마쓰야마,
  다카마쓰,미야코지마,삿포로}-11월.md
  · 구마모토 — `| 1 | 11/04주 | 11-04(목) | 11-07(일) | 🟧 **₩629,400** | … | ❌ 없음 | 확정 | S01 |`
  · 가고시마 — `| 11-04(목)~11-07(일) (목~일, 3박) | **₩669,200** | 17 | 대한항공 · 인천 1회 경유(1시간 30분) · … | 차선 | [S01] |`
  · 미야코지마 — `| 11-04~11-07 (목~일, 3박) | **₩1,153,300** | 20개 | … 2회 경유 · 17시간 35분 · … | 차선 | [S01] |`
  · 삿포로 — `| S01 | 11-04~11-07 (목~일) | 3박 | 30 | **₩804,500** | 대한항공 07:55→12:50, 서울 1시간 경유, … | 없음 | 06:43:50 |` 줄
  · 다카마쓰 — `## 📋 20칸 전체 내역` 의 `- 🟥 1) 11-04~11-07 (목~일, 3박4일) ₩1,008,500 — 대한항공+JAL, 1회 경유(도쿄 7시간 5분), …`
  · 마쓰야마 — `## 5. 📋 20칸 한 장 요약` 의 `| 1 | 2027-11-04~11-07 | 목~일 | 3박4일 | **759,000** | 대한항공+JAL·경유 1회(…) | 24시간 15분 | 차선 …|`
  · 시즈오카 — `| S01 | 2027-11-04~11-07 (목~일) | 3박 | 🚫 판매편 0건 | … | ddate=… | [S01] |`

규칙:
  · 원본이 말하는 노선별 칸 수·최저·최고·직항 칸 수와 파싱 결과를 전수 대조한다. 하나라도 다르면 멈춘다.
    값을 가진 33칸은 **칸별 금액까지** 원본 표와 대조한다(EXPECT_CELL).
  · 140칸은 **새 칸**이다(7개 노선의 2027년 11월에 이미 값·상태가 있으면 멈춘다 — 덮어쓰지 않는다).
  · 값이 없는 107칸은 원본이 적은 그대로 두 갈래로 나눈다 —
    `unopened`(예약창 밖 — 조회 결과 이용 가능한 항공편 0건) 87칸,
    `nosale`(조회 결과 판매편 0건 — 시즈오카 2027-28 겨울 시즌 스케줄 미게시) 20칸. 추정·보간 없음.
  · 값은 원본 그대로(반올림 없음). 항공사·직항/경유·소요시간·경유지만 앱 표기로 옮긴다.
  · 제3자 조회 사이트 이름은 값·note·notes 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 다른 40개 노선 · 다른 달 `notes` · 기존 `noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(flights.total · byMonth · holiday · daytrip, 최상위 deals)와 2027-11 `notes` 를 다시 쓴다.
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jp7_nov27.py --dry-run
    python3 tools/merge_flights_jp7_nov27.py
"""
import argparse
import collections
import copy
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-jp-new7'))
FILES = {
    'KMJ': '부산출발-일본7노선-구마모토-11월.md',
    'KOJ': '부산출발-일본7노선-가고시마-11월.md',
    'FSZ': '부산출발-일본7노선-시즈오카-11월.md',
    'MYJ': '부산출발-일본7노선-마쓰야마-11월.md',
    'TAK': '부산출발-일본7노선-다카마쓰-11월.md',
    'MMY': '부산출발-일본7노선-미야코지마-11월.md',
    'CTS': '부산출발-일본7노선-삿포로-11월.md',
}
ORDER = ('KMJ', 'KOJ', 'FSZ', 'MYJ', 'TAK', 'MMY', 'CTS')     # 브리프 파일 순서
CITY = {'KMJ': '구마모토', 'KOJ': '가고시마', 'FSZ': '시즈오카', 'MYJ': '마쓰야마',
        'TAK': '다카마쓰', 'MMY': '미야코지마', 'CTS': '삿포로'}
WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
WK = ('목~일', '금~일', '토~월', '금~월', '목~월')
PAT_ORDER = ('목~월', '목~일', '금~월', '금~일', '토~월')
WEEKS = tuple('2027-11-%02d' % d for d in (4, 11, 18, 25))
NIGHTS = {p: (WD[p[-1]] - WD[p[0]]) % 7 for p in WK}
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '네이버',
          '구글', 'Google', '플라이트')

# 원본이 스스로 적은 노선별 집계 — (값, 판매편 0건, 예약창 밖, 최저, 최고, 직항이 최저가인 칸)
EXPECT = {
    'KMJ': (5, 0, 15, 558700, 644100, 0),
    'KOJ': (5, 0, 15, 567700, 703400, 0),
    'FSZ': (0, 20, 0, None, None, 0),
    'MYJ': (5, 0, 15, 759000, 800700, 0),
    'TAK': (6, 0, 14, 757200, 1284100, 0),
    'MMY': (5, 0, 15, 1151900, 1304000, 0),
    'CTS': (7, 0, 13, 746600, 1313000, 0),
}
# 값을 가진 33칸 — 원본 표의 칸별 금액 전수
EXPECT_CELL = {
    ('KMJ', '2027-11-04', '목~일'): 629400, ('KMJ', '2027-11-05', '금~일'): 644100,
    ('KMJ', '2027-11-06', '토~월'): 582100, ('KMJ', '2027-11-05', '금~월'): 582100,
    ('KMJ', '2027-11-04', '목~월'): 558700,
    ('KOJ', '2027-11-04', '목~일'): 669200, ('KOJ', '2027-11-05', '금~일'): 703400,
    ('KOJ', '2027-11-06', '토~월'): 618400, ('KOJ', '2027-11-05', '금~월'): 618400,
    ('KOJ', '2027-11-04', '목~월'): 567700,
    ('MYJ', '2027-11-04', '목~일'): 759000, ('MYJ', '2027-11-05', '금~일'): 798500,
    ('MYJ', '2027-11-06', '토~월'): 787200, ('MYJ', '2027-11-05', '금~월'): 787300,
    ('MYJ', '2027-11-04', '목~월'): 800700,
    ('TAK', '2027-11-04', '목~일'): 1008500, ('TAK', '2027-11-05', '금~일'): 830400,
    ('TAK', '2027-11-06', '토~월'): 1008500, ('TAK', '2027-11-05', '금~월'): 800500,
    ('TAK', '2027-11-04', '목~월'): 757200, ('TAK', '2027-11-11', '목~일'): 1284100,
    ('MMY', '2027-11-04', '목~일'): 1153300, ('MMY', '2027-11-05', '금~일'): 1151900,
    ('MMY', '2027-11-06', '토~월'): 1285000, ('MMY', '2027-11-05', '금~월'): 1304000,
    ('MMY', '2027-11-04', '목~월'): 1304000,
    ('CTS', '2027-11-04', '목~일'): 804500, ('CTS', '2027-11-05', '금~일'): 792400,
    ('CTS', '2027-11-06', '토~월'): 758600, ('CTS', '2027-11-05', '금~월'): 746600,
    ('CTS', '2027-11-04', '목~월'): 758400,
    ('CTS', '2027-11-11', '목~일'): 1313000, ('CTS', '2027-11-12', '금~일'): 1313000,
}
# 원본 '요일 패턴별' 표 — 11/04주 5칸(노선별)
EXPECT_PAT_W1 = {
    'KMJ': (629400, 644100, 582100, 582100, 558700),
    'KOJ': (669200, 703400, 618400, 618400, 567700),
    'MYJ': (759000, 798500, 787200, 787300, 800700),
    'TAK': (1008500, 830400, 1008500, 800500, 757200),
    'MMY': (1153300, 1151900, 1285000, 1304000, 1304000),
    'CTS': (804500, 792400, 758600, 746600, 758400),
}
EXPECT_CELLS = 140
EXPECT_PRICED = sum(v[0] for v in EXPECT.values())        # 33
EXPECT_NOSALE = sum(v[1] for v in EXPECT.values())        # 20
EXPECT_UNOPENED = sum(v[2] for v in EXPECT.values())      # 87

EMOJI = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]')
SRC_TAG = re.compile(r'\s*\[출처:[^\]]*\]\s*$')


def back_of(date, pattern):
    if pattern not in NIGHTS:
        raise SystemExit('예상 밖 패턴: %s' % pattern)
    return (datetime.date.fromisoformat(date) +
            datetime.timedelta(days=NIGHTS[pattern])).isoformat()


def money(text):
    m = re.search(r'₩\s*([\d,]+)', text or '')
    if m:
        return int(m.group(1).replace(',', ''))
    m = re.match(r'^\s*\**\s*([\d,]{4,})\s*\**\s*$', text or '')
    return int(m.group(1).replace(',', '')) if m else None


def norm_dur(text):
    t = (text or '').strip()
    m = re.match(r'^(?:총\s*)?(\d+)\s*시간\s*(\d*)\s*분?', t)
    if m:
        return '%s시간%s' % (int(m.group(1)),
                            (' %d분' % int(m.group(2))) if m.group(2) and int(m.group(2)) else '')
    m = re.match(r'^(?:총\s*)?(\d+)\s*시간$', t)
    return '%s시간' % int(m.group(1)) if m else t


def norm_times(text):
    t = re.sub(r'\s*[A-Z]{3}\s*', ' ', (text or '').strip())
    t = re.sub(r'\s+', ' ', t).strip()
    t = t.replace('→', '-').replace('–', '-')
    t = re.sub(r'\s*-\s*', '-', t)
    return t


def clean(text):
    t = EMOJI.sub('', text or '').replace('**', '')
    t = SRC_TAG.sub('', t).strip()
    return re.sub(r'\s+', ' ', t).strip()


def air_join(text):
    t = clean(text).strip(' ,·')
    t = re.sub(r'\s*,\s*', '+', t)
    return re.sub(r'\s+', ' ', t)


def rec(kind, **kw):
    out = {'kind': kind}
    out.update(kw)
    return out


# ── 노선별 파서 ──────────────────────────────────────────────────────────────
def parse_kmj(text):
    """`| 1 | 11/04주 | 11-04(목) | 11-07(일) | 🟧 **₩629,400** | 구성 · 경유 · 시간 · 총 소요 | ❌ 없음 | 확정 | S01 |`"""
    cells = {}
    head = re.compile(r'^\|\s*\d+\s*\|\s*\d\d/\d\d주\s*\|\s*(\d\d-\d\d)\(([월화수목금토일])\)'
                      r'\s*\|\s*(\d\d-\d\d)\(([월화수목금토일])\)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        dep, dw, ret, rw, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 5:
            raise SystemExit('구마모토 표 열이 9개가 아닙니다: %s' % line)
        price, detail, _direct, _status, _src = c
        date = '2027-' + dep
        pattern = dw + '~' + rw
        if back_of(date, pattern) != '2027-' + ret:
            raise SystemExit('구마모토 귀국일이 패턴과 다릅니다: %s' % line)
        if (date, pattern) in cells:
            raise SystemExit('구마모토 %s %s 중복' % (date, pattern))
        p = money(price)
        if p is None:
            if '미오픈' in price:
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('구마모토 금액 칸을 읽지 못했습니다: %s' % price)
        parts = [clean(x) for x in detail.split(' · ') if clean(x)]
        if len(parts) != 4:
            raise SystemExit('구마모토 편성을 읽지 못했습니다: %s' % detail)
        m2 = re.match(r'^(?P<via>.+?) (?P<n>\d)회 경유$', parts[1])
        if not m2:
            raise SystemExit('구마모토 경유 정보를 읽지 못했습니다: %s' % parts[1])
        note = '경유 %s회 · %s · 총 %s · %s' % (m2.group('n'), m2.group('via'),
                                             norm_dur(parts[3]), norm_times(parts[2]))
        cells[(date, pattern)] = rec('price', price=p, airline=air_join(parts[0]),
                                     via=True, note=note)
    return cells


def parse_koj(text):
    """`| 11-04(목)~11-07(일) (목~일, 3박) | **₩669,200** | 17 | 대한항공 · 인천 1회 경유(1시간 30분) · 4시간 20분 · 12:00→16:20 | 차선 | [S01] |`"""
    cells = {}
    head = re.compile(r'^\|\s*(\d\d-\d\d)\([월화수목금토일]\)~(\d\d-\d\d)\([월화수목금토일]\)'
                      r'\s*\(([^,]+),\s*\d+박\)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        dep, ret, pattern, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 5:
            raise SystemExit('가고시마 표 열이 6개가 아닙니다: %s' % line)
        price, _flights, detail, _alt, _src = c
        date = '2027-' + dep
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != '2027-' + ret:
            raise SystemExit('가고시마 귀국일이 패턴과 다릅니다: %s' % line)
        if (date, pattern) in cells:
            raise SystemExit('가고시마 %s %s 중복' % (date, pattern))
        p = money(price)
        if p is None:
            if '미오픈' in ' '.join(c) or price.strip() in ('—', '-', ''):
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('가고시마 금액 칸을 읽지 못했습니다: %s' % price)
        parts = [clean(x) for x in detail.split(' · ') if clean(x)]
        if len(parts) != 4:
            raise SystemExit('가고시마 편성을 읽지 못했습니다: %s' % detail)
        m2 = re.match(r'^(?P<via>.+?) (?P<n>\d)회 경유\((?P<wait>[^)]+)\)$', parts[1])
        if not m2:
            raise SystemExit('가고시마 경유 정보를 읽지 못했습니다: %s' % parts[1])
        note = '경유 %s회 · %s %s · 총 %s · %s' % (m2.group('n'), m2.group('via'),
                                                m2.group('wait'), norm_dur(parts[2]),
                                                norm_times(parts[3]))
        cells[(date, pattern)] = rec('price', price=p, airline=air_join(parts[0]),
                                     via=True, note=note)
    return cells


def parse_mmy(text):
    """`| 11-04~11-07 (목~일, 3박) | **₩1,153,300** | 20개 | 항공사, … · 2회 경유 · 17시간 35분 · 18:55 PUS → 12:30+1 MMY | 차선 | [S01] |`"""
    cells = {}
    head = re.compile(r'^\|\s*(\d\d-\d\d)~(\d\d-\d\d)\s*\(([^,]+),\s*\d+박\)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        dep, ret, pattern, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 5:
            raise SystemExit('미야코지마 표 열이 6개가 아닙니다: %s' % line)
        price, _flights, detail, _alt, _src = c
        date = '2027-' + dep
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != '2027-' + ret:
            raise SystemExit('미야코지마 귀국일이 패턴과 다릅니다: %s' % line)
        if (date, pattern) in cells:
            raise SystemExit('미야코지마 %s %s 중복' % (date, pattern))
        p = money(price)
        if p is None:
            if '미오픈' in price or '미오픈' in detail:
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('미야코지마 금액 칸을 읽지 못했습니다: %s' % price)
        parts = [clean(x) for x in detail.split(' · ') if clean(x)]
        if len(parts) != 4:
            raise SystemExit('미야코지마 편성을 읽지 못했습니다: %s' % detail)
        m2 = re.match(r'^(?P<via>.+?) (?P<n>\d)회 경유$', parts[1])
        if not m2:
            raise SystemExit('미야코지마 경유 정보를 읽지 못했습니다: %s' % parts[1])
        note = '경유 %s회 · %s · 총 %s · %s' % (m2.group('n'), m2.group('via'),
                                             norm_dur(parts[2]), norm_times(parts[3]))
        cells[(date, pattern)] = rec('price', price=p, airline=air_join(parts[0]),
                                     via=True, note=note)
    return cells


def parse_fsz(text):
    """`| S01 | 2027-11-04~11-07 (목~일) | 3박 | 🚫 판매편 0건 | 문구 | ddate=… | [S01] |`"""
    cells = {}
    head = re.compile(r'^\|\s*S\d+\s*\|\s*2027-(\d\d-\d\d)~(\d\d-\d\d)\s*\(([^,|)]+)'
                      r'(?:,\s*\d+박)?\)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        dep, ret, pattern, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 5:
            raise SystemExit('시즈오카 표 열이 7개가 아닙니다: %s' % line)
        status = c[1]
        date = '2027-' + dep
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != '2027-' + ret:
            raise SystemExit('시즈오카 귀국일이 패턴과 다릅니다: %s' % line)
        if (date, pattern) in cells:
            raise SystemExit('시즈오카 %s %s 중복' % (date, pattern))
        if '판매편 0건' in status:
            cells[(date, pattern)] = rec('nosale')
        elif '미오픈' in status:
            cells[(date, pattern)] = rec('unopened')
        else:
            raise SystemExit('시즈오카 상태를 읽지 못했습니다: %s' % status)
    return cells


def parse_myj(text):
    """`| 1 | 2027-11-04~11-07 | 목~일 | 3박4일 | **759,000** | 대한항공+JAL·경유 1회(도쿄 자가환승·나리타→하네다 공항 이동) | 24시간 15분 | 차선 771,100원 |`"""
    cells = {}
    head = re.compile(r'^\|\s*(\d+)\s*\|\s*(2027-\d\d-\d\d)~(?:2027-)?(\d\d-\d\d)\s*\|'
                      r'\s*([^|,]+?)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        idx, date, ret, pattern, rest = m.groups()
        if int(idx) > 20:
            continue
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 5:
            raise SystemExit('마쓰야마 표 열이 8개가 아닙니다: %s' % line)
        _nights, price, viainfo, dur, _memo = c
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != '2027-' + ret:
            raise SystemExit('마쓰야마 귀국일이 패턴과 다릅니다: %s' % line)
        if (date, pattern) in cells:
            raise SystemExit('마쓰야마 %s %s 중복' % (date, pattern))
        p = money(price)
        if p is None:
            if '미오픈' in price:
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('마쓰야마 금액 칸을 읽지 못했습니다: %s' % price)
        info = clean(viainfo)
        air, _, kon = info.partition('·')
        m2 = re.match(r'^경유 (?P<n>\d)회\((?P<via>.+)\)$', kon.strip())
        if not m2:
            raise SystemExit('마쓰야마 경유 정보를 읽지 못했습니다: %s' % info)
        note = '경유 %s회 · %s · 총 %s' % (m2.group('n'), m2.group('via'), norm_dur(dur))
        cells[(date, pattern)] = rec('price', price=p, airline=air_join(air),
                                     via=True, note=note)
    return cells


def parse_tak(text):
    """`- 🟥 1) 11-04~11-07 (목~일, 3박4일) ₩1,008,500 — 대한항공+JAL, 1회 경유(도쿄 7시간 5분), 09:25→20:00, 총 10시간 35분, 위탁 23kg`"""
    cells = {}
    head = re.compile(r'^-\s*(\d+)\)\s*(\d\d-\d\d)~(\d\d-\d\d)\s*\(([^,]+),\s*\d+박\d+일\)'
                      r'\s*(.*)$')
    for line in text.splitlines():
        s = EMOJI.sub('', line.strip()).strip()
        m = head.match(s)
        if not m:
            continue
        idx, dep, ret, pattern, rest = m.groups()
        if int(idx) > 20:
            continue
        date = '2027-' + dep
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != '2027-' + ret:
            raise SystemExit('다카마쓰 귀국일이 패턴과 다릅니다: %s' % line)
        if (date, pattern) in cells:
            raise SystemExit('다카마쓰 %s %s 중복' % (date, pattern))
        p = money(rest)
        if p is None:
            if '미오픈' in rest:
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('다카마쓰 금액 칸을 읽지 못했습니다: %s' % rest)
        detail = clean(rest.split('—', 1)[1] if '—' in rest else rest)
        parts = [x.strip() for x in detail.split(',') if x.strip()]
        air = air_join(parts[0])
        m2 = re.match(r'^(?P<n>\d)회 경유\((?P<via>.+)\)$', parts[1])
        if not m2:
            raise SystemExit('다카마쓰 경유 정보를 읽지 못했습니다: %s' % detail)
        times = next((x for x in parts[2:] if re.match(r'^\d\d:\d\d', x)), None)
        dur = next((x for x in parts[2:] if re.match(r'^(총\s*)?\d+\s*시간', x)), None)
        if not times or not dur:
            raise SystemExit('다카마쓰 소요·시간을 읽지 못했습니다: %s' % detail)
        note = '경유 %s회 · %s · 총 %s · %s' % (m2.group('n'), m2.group('via'),
                                             norm_dur(dur), norm_times(times))
        for token in parts[2:]:
            if '석 미만' in token or '편뿐' in token:
                note += ' · ' + token
        cells[(date, pattern)] = rec('price', price=p, airline=air, via=True, note=note)
    return cells


def parse_cts(text):
    """`| S01 | 11-04~11-07 (목~일) | 3박 | 30 | **₩804,500** | 대한항공 07:55→12:50, 서울 1시간 경유, 4시간 55분, 위탁 23kg | 없음 | 06:43:50 | [S01] |`"""
    cells = {}
    head = re.compile(r'^\|\s*S\d+\s*\|\s*(\d\d-\d\d)~(\d\d-\d\d)\s*\(([^,|)]+)(?:,\s*\d+박)?\)'
                      r'\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        dep, ret, pattern, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) < 5:
            raise SystemExit('삿포로 표 열이 모자랍니다: %s' % line)
        date = '2027-' + dep
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != '2027-' + ret:
            raise SystemExit('삿포로 귀국일이 패턴과 다릅니다: %s' % line)
        if (date, pattern) in cells:
            raise SystemExit('삿포로 %s %s 중복' % (date, pattern))
        price = c[2]
        detail = c[3] if len(c) >= 6 else ''
        p = money(price)
        if p is None:
            if '미오픈' in ' '.join(c) or price.strip() in ('—', '-', ''):
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('삿포로 금액 칸을 읽지 못했습니다: %s' % price)
        if not detail:
            raise SystemExit('삿포로 편성이 없습니다: %s' % line)
        parts = [x.strip() for x in detail.split(',') if x.strip()]
        m2 = re.match(r'^(?P<air>.+?)\s*(?P<dep>\d\d:\d\d)→(?P<arr>\d\d:\d\d\+?\d?)$', parts[0])
        if not m2:
            raise SystemExit('삿포로 항공사·시간을 읽지 못했습니다: %s' % parts[0])
        m3 = re.match(r'^(?P<via>.+?) (?P<wait>.*?)경유$', parts[1])
        if not m3:
            raise SystemExit('삿포로 경유 정보를 읽지 못했습니다: %s' % parts[1])
        dur = next((x for x in parts[2:] if re.match(r'^\d+\s*시간', x)), None)
        if not dur:
            raise SystemExit('삿포로 소요시간을 읽지 못했습니다: %s' % detail)
        via = (m3.group('via') + ' ' + m3.group('wait')).strip()
        note = '경유 1회 · %s · 총 %s · %s' % (via, norm_dur(dur),
                                             norm_times('%s→%s' % (m2.group('dep'),
                                                                   m2.group('arr'))))
        cells[(date, pattern)] = rec('price', price=p, airline=air_join(m2.group('air')),
                                     via=True, note=note)
    return cells


PARSERS = {'KMJ': parse_kmj, 'KOJ': parse_koj, 'FSZ': parse_fsz,
           'MYJ': parse_myj, 'TAK': parse_tak, 'MMY': parse_mmy, 'CTS': parse_cts}

MARK_UNOPENED = {
    'KMJ': '예약창 밖(귀국일 2027-11-13까지 판매) — 조회 결과 이용 가능한 항공편 0건',
    'KOJ': '예약창 밖(귀국 2027-11-08까지 왕복 판매·11-11 이후 왕복 운임 미출시) — 조회 결과 이용 가능한 항공편 0건',
    'MYJ': '예약창 밖(귀국일 2027-11-11까지 판매) — 조회 결과 이용 가능한 항공편 0건',
    'TAK': '예약창 밖(귀국일 2027-11-14까지 판매) — 조회 결과 0개 항공편',
    'MMY': '예약창 밖(출발 2027-11-08·귀국 11-11까지 왕복 판매) — 조회 결과 이용 가능한 항공편 0건',
    'CTS': '예약창 밖(2027-11-14 이후 0건) — 조회 결과 이용 가능한 항공편 0건',
}
MARK_NOSALE = {'FSZ': '조회 결과 판매편 0건 — 2027-28 겨울 시즌 스케줄 미게시'}


def load(code):
    path = os.path.join(SRC, FILES[code])
    cells = PARSERS[code](open(path, encoding='utf-8').read())
    for thu in WEEKS:
        for pat in WK:
            d = (datetime.date.fromisoformat(thu) +
                 datetime.timedelta(days=WD[pat[0]] - 4)).isoformat()
            if (d, pat) not in cells:
                raise SystemExit('%s %s %s 칸이 없습니다' % (code, d, pat))
    if len(cells) != 20:
        raise SystemExit('%s %d칸 (기대 20칸)' % (code, len(cells)))
    got = collections.Counter(v['kind'] for v in cells.values())
    want = EXPECT[code][:3]
    if (got['price'], got['nosale'], got['unopened']) != want:
        raise SystemExit('%s 칸 집계 (값 %d · 0건 %d · 미오픈 %d) — 원본 %s'
                         % (code, got['price'], got['nosale'], got['unopened'], want))
    priced = {k: v['price'] for k, v in cells.items() if v['kind'] == 'price'}
    want_cells = {k[1:]: p for k, p in EXPECT_CELL.items() if k[0] == code}
    if priced != want_cells:
        raise SystemExit('%s 칸별 금액이 원본과 다릅니다: %s'
                         % (code, sorted((k, priced.get(k), want_cells.get(k))
                                         for k in set(priced) | set(want_cells)
                                         if priced.get(k) != want_cells.get(k))[:4]))
    vals = list(priced.values())
    if vals:
        lo, hi = EXPECT[code][3], EXPECT[code][4]
        if (min(vals), max(vals)) != (lo, hi):
            raise SystemExit('%s 최저·최고 %s (원본 %s)' % (code, (min(vals), max(vals)), (lo, hi)))
        direct = sum(1 for v in cells.values() if v['kind'] == 'price' and v['via'] is False)
        if direct != EXPECT[code][5]:
            raise SystemExit('%s 직항이 최저가인 칸 %d (원본 %d)' % (code, direct, EXPECT[code][5]))
    for i, pat in enumerate(WK):
        d = (datetime.date.fromisoformat(WEEKS[0]) +
             datetime.timedelta(days=WD[pat[0]] - 4)).isoformat()
        hit = cells.get((d, pat))
        want_p = EXPECT_PAT_W1.get(code, (None,) * 5)[i]
        if want_p is not None and (not hit or hit.get('price') != want_p):
            raise SystemExit('%s 11/04주 %s %s (원본 %s)' % (code, pat, hit, want_p))
    blob = json.dumps(list(cells.values()), ensure_ascii=False)
    for word in BANNED:
        if word in blob:
            raise SystemExit('%s 값에 제3자 사이트 이름이 들어갔습니다: %s' % (code, word))
    return cells


def make_deal(date, pattern, r):
    deal = {'date': date, 'back': back_of(date, pattern), 'pattern': pattern, 'price': r['price']}
    if r.get('airline'):
        deal['airline'] = r['airline']
    deal['via'] = r['via']
    deal['note'] = r['note']
    return deal


def sort_key(deal):
    return (deal['date'], PAT_ORDER.index(deal['pattern']) if deal['pattern'] in PAT_ORDER else 9)


def nov_note(existing, cells):
    priced = sum(1 for c in ORDER for v in cells[c].values() if v['kind'] == 'price')
    unopened = sum(1 for c in ORDER for v in cells[c].values() if v['kind'] == 'unopened')
    nosale = sum(1 for c in ORDER for v in cells[c].values() if v['kind'] == 'nosale')
    lows = {}
    for c in ORDER:
        ps = [(v['price'], d, p, v['note']) for (d, p), v in cells[c].items()
              if v['kind'] == 'price']
        if ps:
            lows[c] = min(ps)
    seq = sorted((lows[c][0], c) for c in lows)
    text = ' · '.join('%s %s~%s %s %s원(%s)' % (CITY[c], lows[c][1], back_of(lows[c][1], lows[c][2]),
                                               lows[c][2], format(lows[c][0], ','), lows[c][3])
                      for _p, c in seq)
    extra = (
        ' 일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)의 2027년 11월 '
        '몫입니다 — 목요일 기준 4주 × 5패턴 140칸 가운데 %d칸이 값이고, 예약창 밖(미오픈) %d칸 · '
        '판매편 0건 %d칸입니다(추정·보간 없음). 노선별 최저는 %s 순입니다. 11/04주만 판매가 열려 있고 '
        '삿포로·다카마쓰는 11/11주 목~일(1,313,000원 · 1,284,100원)까지 값이 있으며 나머지 주차는 '
        '노선마다 판매 상한이 달라(구마모토 귀국 11-13 · 마쓰야마 귀국 11-11 · 가고시마 11/04주까지) '
        '미오픈입니다. 최저가가 직항인 칸은 0칸입니다 — 부산–일본 7개 노선의 2027년 11월 직항은 '
        '겨울 시즌 스케줄이 아직 열리지 않아 값이 나온 33칸이 모두 경유이고, 구마모토·가고시마·'
        '마쓰야마·다카마쓰·미야코지마·삿포로 모두 서울·도쿄·오키나와 등을 거칩니다. 시즈오카는 '
        '20칸 전부 판매편 0건입니다(2027-28 겨울 시즌 스케줄 미게시 — 2026-27 겨울은 2026-11-18~'
        '2027-02-28 운항).'
        % (priced, unopened, nosale, text)
    )
    for word in BANNED:
        if word in extra:
            raise SystemExit('note 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    return (existing.rstrip() + extra).strip()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ④ 항공 일본 7노선 2027년 11월 — 4주 × 5패턴 140칸(값 33 · 미오픈 87 · '
        '시즈오카 판매편 0건 20), 최저 구마모토 11/4~8 558,700원(서울 1회 경유), 총 7,727→7,760건'))
    args = ap.parse_args(argv)

    cells = {code: load(code) for code in ORDER}
    master = json.load(open(MASTER, encoding='utf-8'))
    merged = copy.deepcopy(master)
    routes = {r['code']: r for r in merged['flights']['routes']}
    old_routes = {r['code']: r for r in master['flights']['routes']}
    old_marks = master['flights']['noSale']

    added = collections.Counter()
    marks = []
    for code in ORDER:
        r = routes[code]
        existing = {(d['date'], d['pattern']) for d in r['deals']}
        if any(s[:7] == '2027-11' for s, _ in existing):
            raise SystemExit('%s 에 이미 2027년 11월 값이 있습니다 — 덮어쓰지 않습니다' % code)
        if any(n.get('code') == code and n.get('date', '')[:7] == '2027-11' for n in old_marks):
            raise SystemExit('%s 에 이미 2027년 11월 상태 기록이 있습니다' % code)
        new = [make_deal(d, p, v) for (d, p), v in cells[code].items() if v['kind'] == 'price']
        for deal in sorted(new, key=sort_key):
            pos = sum(1 for x in r['deals'] if x['date'] < deal['date'])
            r['deals'].insert(pos, deal)
        added[code] = len(new)
        for (d, p), v in sorted(cells[code].items()):
            if v['kind'] == 'price':
                continue
            note = MARK_UNOPENED[code] if v['kind'] == 'unopened' else MARK_NOSALE[code]
            marks.append({'code': code, 'date': d, 'back': back_of(d, p), 'pattern': p,
                          'status': v['kind'], 'note': note})

    if sum(added.values()) != EXPECT_PRICED:
        raise SystemExit('추가 칸 %d (기대 %d)' % (sum(added.values()), EXPECT_PRICED))
    got_marks = collections.Counter(m['status'] for m in marks)
    if got_marks != collections.Counter({'unopened': EXPECT_UNOPENED, 'nosale': EXPECT_NOSALE}):
        raise SystemExit('상태 집계가 다릅니다: %s' % got_marks)
    merged['flights']['noSale'] = old_marks + sorted(
        marks, key=lambda n: (n['code'], n['date'], PAT_ORDER.index(n['pattern'])
                              if n['pattern'] in PAT_ORDER else 9))

    # ── 보존 확인 ──────────────────────────────────────────────
    for key in ('schema', 'version', 'generated_at', 'source', 'window', 'built',
                'voucherExpiry', 'sources', 'accor', 'hotels'):
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != \
                json.dumps(merged.get(key), ensure_ascii=False, sort_keys=True):
            raise SystemExit('%s 가 달라졌습니다' % key)
    new_routes = {r['code']: r for r in merged['flights']['routes']}
    if list(old_routes) != list(new_routes):
        raise SystemExit('노선 목록이 달라졌습니다')
    for code, old in old_routes.items():
        if code not in ORDER:
            if json.dumps(old, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(new_routes[code], ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 노선이 달라졌습니다' % code)
            continue
        if {k: v for k, v in old.items() if k != 'deals'} != \
                {k: v for k, v in new_routes[code].items() if k != 'deals'}:
            raise SystemExit('%s 노선 메타가 달라졌습니다' % code)
        before = {(d['date'], d['pattern']): d for d in old['deals']}
        after = {(d['date'], d['pattern']): d for d in new_routes[code]['deals']}
        if not set(before) <= set(after):
            raise SystemExit('%s 기존 칸이 사라졌습니다' % code)
        for k, deal in before.items():
            if after[k] != deal:
                raise SystemExit('%s %s 칸이 예고 없이 달라졌습니다' % (code, k))
        if len(after) != len(before) + added[code]:
            raise SystemExit('%s 칸 수가 맞지 않습니다 (%d → %d)'
                             % (code, len(before), len(after)))
        if [d['date'] for d in new_routes[code]['deals']] != \
                sorted(d['date'] for d in new_routes[code]['deals']):
            raise SystemExit('%s 날짜 정렬이 깨졌습니다' % code)
    for n in merged['flights']['noSale']:
        if n not in old_marks and n not in marks:
            raise SystemExit('noSale 에 예고 없는 기록이 생겼습니다: %s' % n)
    new_blob = json.dumps([d for c in ORDER for d in new_routes[c]['deals']
                           if d['date'][:7] == '2027-11'], ensure_ascii=False)
    new_blob += json.dumps(marks, ensure_ascii=False)
    for word in BANNED:
        if word in new_blob:
            raise SystemExit('새 값에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    # ── counts ────────────────────────────────────────────────
    deals = [d for r in merged['flights']['routes'] for d in r['deals']]
    by_month = collections.Counter(d['date'][:7] for d in deals)
    old_counts = master['flights']['counts']
    counts = {
        'total': len(deals),
        'byMonth': {m: by_month.get(m, 0) for m in merged['flights']['months']},
        'holiday': sum(1 for d in deals if d['date'] in ('2026-12-25', '2027-02-04')),
        'daytrip': sum(1 for d in deals if d['pattern'].split('~')[0] == d['pattern'].split('~')[-1]),
    }
    if counts['total'] != old_counts['total'] + EXPECT_PRICED:
        raise SystemExit('총 건수 %s' % counts['total'])
    if counts['byMonth']['2027-11'] != old_counts['byMonth']['2027-11'] + EXPECT_PRICED:
        raise SystemExit('2027-11 건수 %s' % counts['byMonth']['2027-11'])
    if counts['holiday'] != old_counts['holiday'] or counts['daytrip'] != old_counts['daytrip']:
        raise SystemExit('연휴/당일치기 수가 달라졌습니다: %s vs %s' % (counts, old_counts))
    for m, n in old_counts['byMonth'].items():
        if m != '2027-11' and counts['byMonth'][m] != n:
            raise SystemExit('%s 건수가 달라졌습니다 (%s → %s)' % (m, n, counts['byMonth'][m]))
    merged['flights']['counts'] = counts
    merged['counts'] = dict(master['counts'])
    merged['counts']['deals'] = counts['total']

    # ── notes · extended ──────────────────────────────────────
    notes = dict(master['flights']['notes'])
    if '2027-11' not in notes:
        raise SystemExit('2027-11 notes 가 없습니다')
    notes['2027-11'] = nov_note(notes['2027-11'], cells)
    merged['flights']['notes'] = notes
    bw = dict(master['flights']['bookingWindow'])
    extra_bw = (
        ' 일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)의 2027년 11월은 '
        '삿포로·다카마쓰가 귀국 2027-11-14까지, 구마모토는 귀국 11-13까지, 마쓰야마는 귀국 11-11까지, '
        '가고시마는 11/04주까지만 왕복 운임이 열려 있어 2~4주차가 대부분 미오픈이고, 시즈오카는 '
        '2027-28 겨울 시즌 스케줄 미게시로 20칸 전부 판매편 0건입니다.')
    bw['note'] = (bw['note'].rstrip() + extra_bw).strip()
    merged['flights']['bookingWindow'] = bw
    for word in BANNED:
        if word in args.note or word in bw['note']:
            raise SystemExit('note 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    merged['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')

    print('노선별 추가:', dict(added), '합계', sum(added.values()))
    print('상태:', dict(got_marks))
    print('counts:', json.dumps(counts, ensure_ascii=False))
    for code in ORDER:
        got = [d for d in new_routes[code]['deals'] if d['date'][:7] == '2027-11']
        if got:
            low = min(got, key=lambda d: d['price'])
            print('  %s %d칸 최저 %s %s %s %s' % (code, len(got), low['date'], low['pattern'],
                                                 low['price'], low['note']))
    print('notes tail:', notes['2027-11'][-480:])
    if args.dry_run:
        print('\n[dry-run] 파일은 쓰지 않았습니다.')
        for code in ORDER:
            print('\n--- %s' % code)
            for (d, p), v in sorted(cells[code].items(),
                                    key=lambda kv: (kv[0][0], PAT_ORDER.index(kv[0][1]))):
                print('  %s %s %s' % (d, p, json.dumps(v, ensure_ascii=False)))
        return 0
    with open(MASTER, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('\n%s 를 다시 썼습니다.' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
