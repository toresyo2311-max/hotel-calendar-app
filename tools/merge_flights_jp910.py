#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 일본 신규 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)
**2027년 9~10월 9주 × 5패턴 315칸**을 `data/master_db.json` 의 `flights` 에 병합한다.

원본 7개(노선별 파일 구조가 서로 다르다):
  data-sources/flights-jp-new7/부산출발-일본7노선-{구마모토,가고시마,시즈오카,마쓰야마,
  다카마쓰,미야코지마,삿포로}-9_10월.md
  · 구마모토 — `| # | 09/02주 | 09-02(목) | 09-05(일) | 🟩 **₩396,491** | … | ✅ 최저가=직항 | 확정 |`
  · 가고시마·미야코지마 — `### 📆 09/02주` 아래 5열 표 `| 09-02(목)~09-05(일) (목~일, 3박) | … |`
  · 시즈오카 — 5열 표 `| S01 | 2027-09-02~09-05 (목~일) | 🚫 판매편 0건 | … |`
  · 마쓰야마 — `## 5. 📊 45칸 전체 요약표` 의 `| 1 | 2027-09-02~2027-09-05 | 목~일 | **659,401** | … |`
  · 다카마쓰 — `## 📋 45칸 전체 내역` 의 `- 🟨 09-02~05 (목~일, 3박) ₩828,677 — …` 줄
  · 삿포로 — 6열 표 `| 09-02~09-05 (목~일) | **₩391,120** | … | ₩391,120 — 직항이 최저가 | [S01] |`

규칙:
  · 원본이 말하는 노선별 칸 수·최저·최고·직항 칸 수와 파싱 결과를 전수 대조한다. 하나라도 다르면 멈춘다.
  · 315칸은 **새 칸**이다(7개 노선의 2027년 9~10월에 이미 값·상태가 있으면 멈춘다 — 덮어쓰지 않는다).
  · 값이 없는 칸은 원본이 적은 그대로 세 갈래로 나눈다 —
    `nosale`(조회 결과 판매편 0건) · `nofare`(요금 미확인·미표시, 재조회 필요) ·
    `unopened`(예약창 밖 — 조회 자체가 열리지 않음/미측정). 추정·보간 없음.
  · 값은 원본 그대로(반올림 없음). 항공사·직항/경유·소요시간·경유지만 앱 표기로 옮긴다.
  · 제3자 조회 사이트 이름은 값·note·notes 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 다른 40개 노선 · 다른 달 `notes` · 기존 `noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(flights.total · byMonth · holiday · daytrip, 최상위 deals)와 2027-09·2027-10 `notes` 를 다시 쓴다.
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jp910.py --dry-run
    python3 tools/merge_flights_jp910.py
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
    'KMJ': '부산출발-일본7노선-구마모토-9_10월.md',
    'KOJ': '부산출발-일본7노선-가고시마-9_10월.md',
    'FSZ': '부산출발-일본7노선-시즈오카-9_10월.md',
    'MYJ': '부산출발-일본7노선-마쓰야마-9_10월.md',
    'TAK': '부산출발-일본7노선-다카마쓰-9_10월.md',
    'MMY': '부산출발-일본7노선-미야코지마-9_10월.md',
    'CTS': '부산출발-일본7노선-삿포로-9_10월.md',
}
ORDER = ('KMJ', 'KOJ', 'FSZ', 'MYJ', 'TAK', 'MMY', 'CTS')      # 원본 파일 순서
CITY = {'KMJ': '구마모토', 'KOJ': '가고시마', 'FSZ': '시즈오카', 'MYJ': '마쓰야마',
        'TAK': '다카마쓰', 'MMY': '미야코지마', 'CTS': '삿포로'}
WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
WK = ('목~일', '금~일', '토~월', '금~월', '목~월')            # 원본 표의 열 순서
PAT_ORDER = ('목~월', '목~일', '금~월', '금~일', '토~월')       # 앱의 같은 날짜 안 정렬(기존 데이터 다수)
WEEKS = tuple((datetime.date(2027, 9, 2) + datetime.timedelta(days=7 * i)).isoformat()
              for i in range(9))
NIGHTS = {p: (WD[p[-1]] - WD[p[0]]) % 7 for p in WK}
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '네이버',
          '구글', 'Google', '플라이트')

# 원본이 스스로 적은 노선별 집계 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
#              (값, 0건, 요금 미확인, 미오픈, 최저, 최고, 직항이 최저가인 칸)
EXPECT = {
    'KMJ': (23, 3, 4, 15, 393000, 1085031, 12),
    'KOJ': (30, 0, 0, 15, 599847, 995447, 0),
    'FSZ': (0, 30, 0, 15, None, None, 0),
    'MYJ': (30, 0, 0, 15, 635917, 816517, 0),
    'TAK': (30, 0, 0, 15, 770828, 1083174, 0),
    'MMY': (45, 0, 0, 0, 795900, 5743900, 0),
    'CTS': (32, 1, 0, 12, 374540, 1062100, 21),
}
# 주차별 최저(원본 '주차별 요약' · 주차별 도표) — KMJ·KOJ·MMY
EXPECT_WEEK_LOW = {
    'KMJ': (396491, 393000, 473875, 432500, 421290, 452500),
    'KOJ': (608718, 644167, 619321, 599847, 805255, 626443),
    'MMY': (1125000, 1121100, 1198800, 1139400, 1023100, 1021900, 898600, 795900, 1147200),
}
# 마쓰야마 원본 '출발일별 최저가' — 출발일별 가장 싼 패턴
EXPECT_MYJ_DAY = {
    '2027-09-02': 641675, '2027-09-03': 684076, '2027-09-04': 662079,
    '2027-09-09': 692868, '2027-09-10': 779279, '2027-09-11': 813680,
    '2027-09-16': 767437, '2027-09-17': 799859, '2027-09-18': 674897,
    '2027-09-23': 635917, '2027-09-24': 667728, '2027-09-25': 667728,
    '2027-09-30': 799683, '2027-10-01': 799918, '2027-10-02': 814915,
    '2027-10-07': 707358, '2027-10-08': 810503, '2027-10-09': 789597,
}
EXPECT_CELLS = 45 * 7
EXPECT_PRICED = sum(v[0] for v in EXPECT.values())      # 190
EXPECT_NOSALE = sum(v[1] for v in EXPECT.values())      # 34
EXPECT_NOFARE = sum(v[2] for v in EXPECT.values())      # 4
EXPECT_UNOPENED = sum(v[3] for v in EXPECT.values())    # 87

SRC_TAG = re.compile(r'\s*\[출처:[^\]]*\]\s*$')
EMOJI = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]')


def year_of(mmdd, anchor_year=2027):
    return int(mmdd[0:4]) if len(mmdd) >= 10 else anchor_year


def full_date(mmdd, dep=None):
    """'09-02' 또는 '2027-09-02' → '2027-09-02'. 연말 넘김은 dep 기준으로 판단."""
    if len(mmdd) == 10:
        return mmdd
    y = 2027
    if dep and mmdd[:2] < dep[5:7]:
        y = int(dep[:4]) + 1
    return '%04d-%s' % (y, mmdd)


def ret_date(dep_date, ret_txt):
    """'05' · '10-04' · '2027-10-04' → 귀국일. 출발일보다 앞선 날짜는 다음 달·다음 해로 넘긴다."""
    if len(ret_txt) == 2:
        d = datetime.date.fromisoformat(dep_date[:8] + ret_txt)
        if d < datetime.date.fromisoformat(dep_date):
            m = d.month + 1
            y = d.year + (1 if m > 12 else 0)
            m = 1 if m > 12 else m
            d = datetime.date(y, m, d.day)
        return d.isoformat()
    return full_date(ret_txt, dep_date)


def nights_of(pattern):
    if pattern not in NIGHTS:
        raise SystemExit('예상 밖 패턴: %s' % pattern)
    return NIGHTS[pattern]


def back_of(date, pattern):
    return (datetime.date.fromisoformat(date) +
            datetime.timedelta(days=nights_of(pattern))).isoformat()


def money(text):
    m = re.search(r'₩\s*([\d,]+)', text)
    if m:
        return int(m.group(1).replace(',', ''))
    m = re.match(r'^\s*\**\s*([\d,]{4,})\s*\**\s*$', text or '')
    return int(m.group(1).replace(',', '')) if m else None


def clean_line(text):
    t = EMOJI.sub('', text or '').replace('**', '').replace('⭐', '').replace('★', '').strip()
    t = re.sub(r'\s*전체\s*(최저|최고)\s*$', '', t).strip()
    t = SRC_TAG.sub('', t).strip()
    return re.sub(r'\s+', ' ', t)


def conv_ampm(text):
    """'오후 2:50→오후 1:40+1' → '14:50-13:40+1'."""
    def rep(m):
        half, hh, mi = m.group(1), int(m.group(2)), m.group(3)
        if half == '오후' and hh < 12:
            hh += 12
        if half == '오전' and hh == 12:
            hh = 0
        return '%02d:%s' % (hh, mi)
    t = re.sub(r'(오전|오후) (\d{1,2}):(\d{2})', rep, text)
    return t.replace('→', '-').strip()


def strip_times(text):
    t = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?(?:[–\-]\d{1,2}:\d{2}(?:\+\d)?)?', '', text)
    t = re.sub(r'\s*[,/]\s*$', '', t)
    return re.sub(r'\s+', ' ', t).strip(' ,·')


def norm_dur(text):
    """'8h5m'·'17시간05분'·'2시간 30분' → '8시간 5분' 꼴."""
    t = text.strip()
    m = re.match(r'^(\d+)h\s*(\d*)m?\b', t)
    if m:
        return '%s시간%s' % (int(m.group(1)),
                            (' %d분' % int(m.group(2))) if m.group(2) and int(m.group(2)) else '')
    m = re.match(r'^(\d+)시간\s*(\d*)\s*분?', t)
    if m:
        return '%s시간%s' % (int(m.group(1)),
                            (' %d분' % int(m.group(2))) if m.group(2) and int(m.group(2)) else '')
    m = re.match(r'^(\d+)\s*시간$', t)
    if m:
        return '%s시간' % int(m.group(1))
    return t


def clean_air(text):
    t = clean_line(text)
    t = t.replace('(LCC)', '').replace('(경유)', '')
    t = t.replace('일본 트랜스오션항공', '일본 트랜스오션항공')
    t = re.sub(r'\s+', ' ', t).strip(' ,·')
    t = re.sub(r'\s*,\s*', '+', t)
    return t


def rec(kind, **kw):
    out = {'kind': kind}
    out.update(kw)
    return out


# ── 노선별 파서 ──────────────────────────────────────────────────────────────
def parse_kmj(text):
    """`| # | 09/02주 | 09-02(목) | 09-05(일) | 🟩 **₩396,491** | 구성 | 직항 | 상태 |`"""
    cells = {}
    for line in text.splitlines():
        if not re.match(r'^\|\s*\d+\s*\|\s*\d\d/\d\d주\s*\|', line.strip()):
            continue
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) != 8:
            raise SystemExit('구마모토 표 열이 8개가 아닙니다: %s' % line)
        idx, week, dep, ret, price, detail, direct, status = c
        date = full_date(dep[:5])
        pattern = dep[6] + '~' + ret[6]
        if back_of(date, pattern) != full_date(ret[:5], date):
            raise SystemExit('귀국일이 패턴과 다릅니다: %s %s' % (line, back_of(date, pattern)))
        if '판매편 0건' in price:
            cells[(date, pattern)] = rec('nosale')
            continue
        if '미오픈' in price:
            cells[(date, pattern)] = rec('unopened')
            continue
        if '미확인' in price or '가격 미표시' in price:
            cells[(date, pattern)] = rec('nofare')
            continue
        p = money(price)
        if p is not None:
            d = clean_line(detail)
            self_tr = '자가환승' in d or '자가 환승' in d
            via = '경유' in d
            body = re.sub(r'자가\s*환승', '', d)
            body = re.sub(r'\(구글[^)]*\)|구글[^·]*', '', body)
            first = body.split(' · ')[0].strip()
            if not via:
                m = re.match(r'^(?P<air>.+?) 직항 (?P<dep>\d\d:\d\d)→(?P<arr>\d\d:\d\d)\s*·?\s*(?P<dur>.*)$',
                             first)
                if not m:
                    raise SystemExit('구마모토 직항 줄을 읽지 못했습니다: %s' % first)
                note = '직항 %s-%s' % (m.group('dep'), m.group('arr'))
                if m.group('dur'):
                    note += ' · ' + norm_dur(strip_times(m.group('dur')))
                air = clean_air(m.group('air'))
            else:
                m = re.match(r'^(?P<air>.+?) · (?P<n>\d회) 경유\((?P<via>[^)]*)\) · (?P<dur>[^·]+)', body)
                if not m:
                    raise SystemExit('구마모토 경유 줄을 읽지 못했습니다: %s' % body)
                air = clean_air(m.group('air'))
                note = '경유 %s(%s) · 총 %s' % (m.group('n'), m.group('via'), norm_dur(m.group('dur').strip()))
                if self_tr:
                    note += ' · 자가환승'
            cells[(date, pattern)] = rec('price', price=p, airline=air, via=via, note=note)
            continue
        raise SystemExit('구마모토 금액 칸을 읽지 못했습니다: %s' % price)
    return cells


def parse_grid5(text, code):
    """가고시마·미야코지마 — `| 09-02(목)~09-05(일) (목~일, 3박) | **₩651,568** | 편성 | 차선 | [S01] |`"""
    cells = {}
    head = re.compile(r'^\|\s*(\d\d-\d\d)\([월화수목금토일]\)~(\d\d-\d\d)\([월화수목금토일]\)'
                      r'\s*\(([^,]+),\s*\d+박\)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        dep, ret, pattern, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 4:
            raise SystemExit('%s 표 열이 5개가 아닙니다: %s' % (code, line))
        price, detail, _alt, _src = c
        date = full_date(dep)
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != full_date(ret, date):
            raise SystemExit('%s 귀국일이 패턴과 다릅니다: %s' % (code, line))
        p = money(price)
        if p is None:
            if '미오픈' in price or '🔒' in price or '미오픈' in detail or '🔒' in detail:
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('%s 금액 칸을 읽지 못했습니다: %s' % (code, price))
        d = clean_line(detail)
        m2 = re.match(r'^(?P<air>.+?) · (?P<n>\d회) 경유\((?P<via>.+?)\) · (?P<dur>[^·]+)(?: · (?P<time>.+))?$', d)
        if not m2:
            raise SystemExit('%s 편성을 읽지 못했습니다: %s' % (code, d))
        via = re.sub(r'\(([^()]*대기)\)', r' \1', m2.group('via')).strip()
        note = '경유 %s · %s · 총 %s' % (m2.group('n'), via, norm_dur(m2.group('dur').strip()))
        if m2.group('time'):
            note += ' · ' + conv_ampm(m2.group('time'))
        air = clean_air(m2.group('air'))
        if '자가 환승' in air or '자가환승' in air:
            air = re.sub(r'\s*\(?\s*자가\s*환승\s*\)?', '', air).strip()
            note += ' · 자가환승'
        cells[(date, pattern)] = rec('price', price=p, airline=air, via=True, note=note)
    return cells


def parse_fsz(text):
    """시즈오카 — `| S01 | 2027-09-02~09-05 (목~일) | 🚫 판매편 0건 | 문구 | [S01] |`"""
    cells = {}
    head = re.compile(r'^\|\s*S\d+\s*\|\s*2027-(\d\d-\d\d)~(\d\d-\d\d)\s*\(([^,|)]+)(?:,\s*\d+박)?\)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        dep, ret, pattern, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 3:
            raise SystemExit('시즈오카 표 열이 5개가 아닙니다: %s' % line)
        status = c[0]
        date = full_date('2027-' + dep)
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != full_date('2027-' + ret, date):
            raise SystemExit('시즈오카 귀국일이 패턴과 다릅니다: %s' % line)
        if '판매편 0건' in status:
            cells[(date, pattern)] = rec('nosale')
        elif '미오픈' in status:
            cells[(date, pattern)] = rec('unopened')
        else:
            raise SystemExit('시즈오카 상태를 읽지 못했습니다: %s' % status)
    return cells


def parse_myj(text):
    """마쓰야마 — `| 1 | 2027-09-02~2027-09-05 | 목~일 | **659,401** | 항공사 | 경유 | 소요 | 비고 |`"""
    cells = {}
    head = re.compile(r'^\|\s*\d+\s*\|\s*(2027-\d\d-\d\d)~(2027-\d\d-\d\d)\s*\|\s*([^|,]+?)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        date, ret, pattern, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 5:
            raise SystemExit('마쓰야마 표 열이 8개가 아닙니다: %s' % line)
        price, air, viainfo, dur, _memo = c
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != ret:
            raise SystemExit('마쓰야마 귀국일이 패턴과 다릅니다: %s' % line)
        p = money(price)
        if p is None:
            if '미오픈' in price:
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('마쓰야마 금액 칸을 읽지 못했습니다: %s' % price)
        parts = [x.strip() for x in clean_line(viainfo).split('·')]
        n = parts[0] if parts and parts[0].endswith('회') else ''
        self_tr = '자가환승' in parts
        via = '·'.join(x for x in parts[1:] if x and x != '자가환승')
        note = '경유 %s%s · 총 %s' % (n + ' ' if n else '', via, norm_dur(clean_line(dur)))
        if self_tr:
            note += ' · 자가환승'
        cells[(date, pattern)] = rec('price', price=p, airline=clean_air(air), via=True, note=note)
    return cells


def parse_tak(text):
    """다카마쓰 — `- 🟨 09-02~05 (목~일, 3박) ₩828,677 — 이스타항공+ANA, 1회 경유(나하) 4h10m 대기, 자가환승, 8h5m`"""
    cells = {}
    head = re.compile(r'^-\s*(\d\d-\d\d)~(\d\d(?:-\d\d)?)\s*\(([^,|]+),\s*\d+박\)\s*(.*)$')
    for line in text.splitlines():
        line = line.strip().replace('🟩', '').replace('🟨', '').replace('🟧', '') \
                   .replace('🟥', '').replace('⛔', '').strip()
        m = head.match(line)
        if not m:
            continue
        dep, ret, pattern, rest = m.groups()
        date = full_date(dep)
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != ret_date(date, ret):
            raise SystemExit('다카마쓰 귀국일이 패턴과 다릅니다: %s' % line)
        p = money(rest)
        if p is None:
            if '미오픈' in rest:
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('다카마쓰 금액 칸을 읽지 못했습니다: %s' % rest)
        detail = clean_line(rest.split('—', 1)[1] if '—' in rest else rest)
        detail = re.sub(r'\s*전체\s*(최저|최고)\s*$', '', detail).strip(' ,')
        parts = [x.strip() for x in detail.split(',') if x.strip()]
        air = clean_air(parts[0])
        m2 = re.search(r'(\d회) 경유\(([^)]*)\)', parts[1] if len(parts) > 1 else '')
        if not m2:
            raise SystemExit('다카마쓰 경유 정보를 읽지 못했습니다: %s' % detail)
        via = m2.group(2)
        m3 = re.search(r'(\d+h\s*\d*m?|\d+시간\s*\d*\s*분?)\s*대기', parts[1])
        if m3:
            via += ' ' + norm_dur(m3.group(1)) + ' 대기'
        dur = cabin = mixed = None
        self_tr = False
        for token in parts[1:]:
            token = token.strip()
            if re.match(r'^\d+h\s*\d*m?$', token) or re.match(r'^\d+시간', token):
                dur = norm_dur(token)
            elif '자가' in token and '환승' in token:
                self_tr = True
            elif '기내선반' in token:
                cabin = True
            elif '이코노미' in token or '퍼스트' in token:
                mixed = token
        if not dur:
            raise SystemExit('다카마쓰 소요시간을 읽지 못했습니다: %s' % detail)
        note = '경유 %s %s · 총 %s' % (m2.group(1), via, dur)
        if self_tr:
            note += ' · 자가환승'
        if cabin:
            note += ' · 기내 선반 별도'
        if mixed:
            note += ' · ' + mixed
        cells[(date, pattern)] = rec('price', price=p, airline=air, via=True, note=note)
    return cells


def parse_cts(text):
    """삿포로 — `| 09-02~09-05 (목~일) | **₩391,120** | 대표 편성 | 차선 | 직항 최저가 | [S01] |`"""
    cells = {}
    head = re.compile(r'^\|\s*(\d\d-\d\d)~(\d\d-\d\d)\s*\(([^,|]+)\)\s*\|(.*)$')
    for line in text.splitlines():
        m = head.match(line.strip())
        if not m:
            continue
        dep, ret, pattern, rest = m.groups()
        c = [x.strip() for x in rest.strip().strip('|').split('|')]
        if len(c) != 5:
            raise SystemExit('삿포로 표 열이 6개가 아닙니다: %s' % line)
        price, detail, _alt, directprice, _src = c
        date = full_date(dep)
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % pattern)
        if back_of(date, pattern) != full_date(ret, date):
            raise SystemExit('삿포로 귀국일이 패턴과 다릅니다: %s' % line)
        p = money(price)
        if p is None:
            if '판매가 없음' in price:
                cells[(date, pattern)] = rec('nosale')
                continue
            if '미오픈' in price:
                cells[(date, pattern)] = rec('unopened')
                continue
            raise SystemExit('삿포로 금액 칸을 읽지 못했습니다: %s' % price)
        d = clean_line(detail)
        self_tr = d.startswith('자가환승')
        body = re.sub(r'^자가환승\s*', '', d)
        m2 = re.match(r'^(?P<air>.+?) 직항 (?P<dep>\d\d:\d\d)–(?P<arr>\d\d:\d\d)'
                      r'(?: / 귀국 (?P<d2>\d\d:\d\d)–(?P<a2>\d\d:\d\d))?'
                      r'(?: \((?P<dur>[^)]*)\))?$', body)
        if m2:
            note = '직항 %s-%s' % (m2.group('dep'), m2.group('arr'))
            if m2.group('d2'):
                note = '직항 %s-%s · 귀국 %s-%s' % (m2.group('dep'), m2.group('arr'),
                                                  m2.group('d2'), m2.group('a2'))
            if m2.group('dur'):
                note += ' · ' + re.sub(r'\s*·\s*', ' · ', norm_dur(m2.group('dur')))
            via = False
            air = clean_air(m2.group('air'))
        else:
            m3 = re.match(r'^(?P<air>[^,]+),\s*(?P<rest>.*?)\s*\((?P<dur>[^)]*)\)$', body)
            if not m3:
                # '대한항공 ICN 경유(공항변경) 12:15–13:25+1 (25시간 10분)' 꼴
                m3 = re.match(r'^(?P<air>.+?) (?P<code>[A-Z]{3}) 경유(?P<sub>\([^)]*\))?'
                              r'[^(]*\((?P<dur>[^)]*)\)$', body)
                if m3:
                    rest = ('%s %s' % (m3.group('code'), m3.group('sub') or '')).strip()
                    note = '경유 %s · 총 %s' % (rest, norm_dur(m3.group('dur')))
                    air = clean_air(m3.group('air'))
                    r = rec('price', price=p, airline=air, via=True, note=note)
                    alt0 = money(directprice or '')
                    if alt0:
                        r['alt'] = alt0
                    cells[(date, pattern)] = r
                    continue
            if not m3:
                raise SystemExit('삿포로 편성을 읽지 못했습니다: %s' % body)
            via = True
            air = clean_air(m3.group('air'))
            rest = strip_times(m3.group('rest')).replace('경유', '').strip(' ,·')
            rest = re.sub(r'\s*\(\s*', ' (', rest)
            rest = re.sub(r'\s+', ' ', rest).strip()
            note = '경유 %s · 총 %s' % (rest or '경유', norm_dur(m3.group('dur')))
            if self_tr:
                note = '자가환승 · ' + note
        alt = money(directprice or '')
        r = rec('price', price=p, airline=air, via=via, note=note)
        if via and alt:
            r['alt'] = alt
        cells[(date, pattern)] = r
    return cells


PARSERS = {'KMJ': parse_kmj, 'KOJ': parse_grid5, 'FSZ': parse_fsz,
           'MYJ': parse_myj, 'TAK': parse_tak, 'MMY': parse_grid5, 'CTS': parse_cts}


def load(code):
    path = os.path.join(SRC, FILES[code])
    text = open(path, encoding='utf-8').read()
    cells = PARSERS[code](text, code) if code in ('KOJ', 'MMY') else PARSERS[code](text)
    # 격자 9주 × 5패턴이 모두 있는지
    for thu in WEEKS:
        for pat in WK:
            d = (datetime.date.fromisoformat(thu) + datetime.timedelta(days=WD[pat[0]] - 4)).isoformat()
            if (d, pat) not in cells:
                raise SystemExit('%s %s %s 칸이 없습니다' % (code, d, pat))
            if cells[(d, pat)]['kind'] == 'price':
                if cells[(d, pat)]['note'].find('  ') >= 0 or not cells[(d, pat)]['note']:
                    raise SystemExit('%s %s %s note 이상: %r' % (code, d, pat, cells[(d, pat)]['note']))
    priced, nosale, nofare, unopened = EXPECT[code][:4]
    got = collections.Counter(v['kind'] for v in cells.values())
    got = (got['price'], got['nosale'], got['nofare'], got['unopened'])
    if got != (priced, nosale, nofare, unopened):
        raise SystemExit('%s 칸 집계 %s (원본 %s)' % (code, got, (priced, nosale, nofare, unopened)))
    if len(cells) != 45:
        raise SystemExit('%s %d칸 (기대 45칸)' % (code, len(cells)))
    vals = [v['price'] for v in cells.values() if v['kind'] == 'price']
    if vals:
        lo, hi = EXPECT[code][4], EXPECT[code][5]
        if (min(vals), max(vals)) != (lo, hi):
            raise SystemExit('%s 최저·최고 %s (원본 %s)' % (code, (min(vals), max(vals)), (lo, hi)))
        direct = sum(1 for v in cells.values() if v['kind'] == 'price' and v['via'] is False)
        if direct != EXPECT[code][6]:
            raise SystemExit('%s 직항이 최저가인 칸 %d (원본 %d)' % (code, direct, EXPECT[code][6]))
    if code in EXPECT_WEEK_LOW:
        want = EXPECT_WEEK_LOW[code]
        for i, thu in enumerate(WEEKS[:len(want)]):
            ps = [v['price'] for (d, p), v in cells.items()
                  if p != '' and (datetime.date.fromisoformat(d) -
                                  datetime.date.fromisoformat(thu)).days // 7 == 0 and v['kind'] == 'price']
            if min(ps) != want[i]:
                raise SystemExit('%s %d주차 최저 %s (원본 %s)' % (code, i + 1, min(ps), want[i]))
    if code == 'MYJ':
        for d, want in EXPECT_MYJ_DAY.items():
            ps = [v['price'] for (dd, p), v in cells.items() if dd == d and v['kind'] == 'price']
            if min(ps) != want:
                raise SystemExit('마쓰야마 %s 최저 %s (원본 %s)' % (d, min(ps), want))
    for word in BANNED:
        blob = json.dumps({'c': [v for v in cells.values()]}, ensure_ascii=False)
        if word in blob:
            raise SystemExit('%s 값에 제3자 사이트 이름이 들어갔습니다: %s' % (code, word))
    return cells


MARK_NOTE = {
    ('KMJ', 'nosale'): '조회 결과 판매편 0건 — 해당 출발·귀국 조합 항공편 없음',
    ('KMJ', 'nofare'): '운항편은 표시되나 요금을 확인하지 못했습니다(화면 미표시·응답 정지) — 재조회 필요',
    ('FSZ', 'nosale'): '조회 결과 판매편 0건 — 2027년 하계 시즌 스케줄 미게시',
    ('CTS', 'nosale'): '판매 가격 미표시 — 항공편 1건만 뜨고 요금이 없음(재조회 필요)',
}


def mark_note(code, kind, rec_):
    if kind == 'nosale':
        return MARK_NOTE.get((code, 'nosale'), '조회 결과 판매편 0건 — 항공편 자체가 없음')
    if kind == 'nofare':
        return MARK_NOTE[('KMJ', 'nofare')]
    if code == 'FSZ':
        return '예약창 밖 — 2027년 하계 시즌 스케줄 미게시'
    if code == 'CTS':
        return '예약창 밖(2027-10-11 귀국까지 조회) — 10/14주 이후 일부는 미측정'
    return '예약창 밖 — 2027-10-11(귀국일) 이후 조회가 열려 있지 않음'


def make_deal(code, date, pattern, r):
    deal = {'date': date, 'back': back_of(date, pattern), 'pattern': pattern, 'price': r['price']}
    if r.get('airline'):
        deal['airline'] = r['airline']
    deal['via'] = r['via']
    deal['note'] = r['note']
    if r.get('alt'):
        deal['alt'] = r['alt']
    return deal


def sort_key(deal):
    return (deal['date'], PAT_ORDER.index(deal['pattern']) if deal['pattern'] in PAT_ORDER else 9)


def note_append(existing, extra):
    return (existing.rstrip() + ' ' + extra).strip()


def _low(cells, code, month):
    ps = [(d, p, v['price'], v['note']) for (d, p), v in cells[code].items()
          if d.startswith(month) and v['kind'] == 'price']
    if not ps:
        return None
    return min(ps, key=lambda x: x[2])


def build_notes(month, cells, master_note):
    """2027-09 · 2027-10 notes 뒤에 일본 7개 노선 9~10월 문단을 덧붙인다(값은 파싱 결과에서 센다)."""
    priced_all = sum(1 for code in ORDER for v in cells[code].values() if v['kind'] == 'price')
    marks_all = collections.Counter(v['kind'] for code in ORDER for v in cells[code].values()
                                    if v['kind'] != 'price')
    priced_m = sum(1 for code in ORDER for (d, p), v in cells[code].items()
                   if d.startswith(month) and v['kind'] == 'price')
    low = {code: _low(cells, code, month) for code in ORDER}
    late = {code: sum(1 for (d, p), v in cells[code].items()
                      if d >= '2027-10-14' and v['kind'] == 'price') for code in ORDER}

    def one(code, label=True):
        x = low[code]
        if not x:
            return None
        d, p, price, note = x
        return '%s %s %s %s원(%s)' % (CITY[code], d, p, format(price, ','), note) if label \
            else '%s %s %s %s원' % (CITY[code], d, p, format(price, ','))

    if month == '2027-09':
        extra = (
            ' 일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)은 2027년 9~10월 '
            '목요일 기준 9주 × 5패턴 315칸을 조회해 %d칸이 값으로 찼고, 판매편 0건 %d칸 · 요금 미확인 %d칸 · '
            '예약창 밖 %d칸입니다(추정 없음). 이 달(9월)은 %d칸이 값이고 노선별 최저는 %s 순입니다. '
            '시즈오카는 9~10월 30칸이 모두 판매편 0건이고(2027년 하계 시즌 스케줄 미게시) 10/14주 이후 15칸은 '
            '예약창 밖입니다. 9월의 봉우리는 09-16주(일본 실버위크 9/18~20)로 미야코지마 09-16 목~일 '
            '5,743,900원이고, 삿포로는 09/02주 374,717원 · 09/23주 374,540원으로 37만원대가 유지됩니다.'
            % (priced_all, marks_all['nosale'], marks_all['nofare'], marks_all['unopened'], priced_m,
               ' · '.join(x for x in (one(c, False) for c in ORDER) if x))
        )
    else:
        extra = (
            ' 일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)의 2027년 10월 '
            '몫입니다 — 이 달은 %d칸이 값이고, 노선별 최저는 %s 순입니다. 10/07주까지 구마모토·가고시마·'
            '마쓰야마·다카마쓰 19칸과 삿포로 4칸이 값으로 차고 시즈오카 5칸은 판매편 0건이며, 10/14주 이후는 '
            '예약창이 열려 있지 않아 미야코지마 %d칸과 삿포로 %d칸만 값이 있습니다. 개천절 연휴(10/1~4)는 '
            '삿포로 10-02~04 토~월 859,892원 · 10-01~04 금~월 890,677원으로 같은 주 9/30 출발 '
            '564,042원보다 20만~30만원 비쌉니다.'
            % (priced_m, ' · '.join(x for x in (one(c, False) for c in ORDER) if x),
               late['MMY'], late['CTS'])
        )
    return (master_note.rstrip() + extra).strip()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ④ 항공 일본 7노선 2027년 9~10월 — 9주 × 5패턴 315칸(값 190 · 판매편 0건 34 · '
        '요금 미확인 4 · 예약창 밖 87), 최저 삿포로 9/24~27 374,540원(직항), 총 7,417→7,607건'))
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
        if any('2027-09-01' <= s <= '2027-10-31' for s, _ in existing):
            raise SystemExit('%s 에 이미 2027년 9~10월 값이 있습니다 — 덮어쓰지 않습니다' % code)
        if any(n.get('code') == code and '2027-09-01' <= n.get('date', '') <= '2027-10-31'
               for n in old_marks):
            raise SystemExit('%s 에 이미 2027년 9~10월 상태 기록이 있습니다' % code)
        new = [make_deal(code, d, p, v) for (d, p), v in cells[code].items() if v['kind'] == 'price']
        for deal in sorted(new, key=sort_key):
            pos = sum(1 for x in r['deals'] if x['date'] < deal['date'])
            r['deals'].insert(pos, deal)
        added[code] = len(new)
        for (d, p), v in sorted(cells[code].items()):
            if v['kind'] == 'price':
                continue
            marks.append({'code': code, 'date': d, 'back': back_of(d, p), 'pattern': p,
                          'status': v['kind'], 'note': mark_note(code, v['kind'], v)})

    if sum(added.values()) != EXPECT_PRICED:
        raise SystemExit('추가 칸 %d (기대 %d)' % (sum(added.values()), EXPECT_PRICED))
    if collections.Counter(m['status'] for m in marks) != collections.Counter(
            {'nosale': EXPECT_NOSALE, 'nofare': EXPECT_NOFARE, 'unopened': EXPECT_UNOPENED}):
        raise SystemExit('상태 집계가 다릅니다: %s'
                         % collections.Counter(m['status'] for m in marks))
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
    for n in merged['flights']['noSale']:
        if n not in old_marks and n not in marks:
            raise SystemExit('noSale 에 예고 없는 기록이 생겼습니다: %s' % n)
    new_blob = json.dumps([d for c in ORDER for d in new_routes[c]['deals']
                           if '2027-09-01' <= d['date'] <= '2027-10-31'], ensure_ascii=False)
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
    if counts['byMonth']['2027-09'] + counts['byMonth']['2027-10'] != \
            old_counts['byMonth']['2027-09'] + old_counts['byMonth']['2027-10'] + EXPECT_PRICED:
        raise SystemExit('9~10월 건수 %s' % counts['byMonth'])
    if counts['holiday'] != old_counts['holiday'] or counts['daytrip'] != old_counts['daytrip']:
        raise SystemExit('연휴/당일치기 수가 달라졌습니다: %s vs %s' % (counts, old_counts))
    for m, n in old_counts['byMonth'].items():
        if m not in ('2027-09', '2027-10') and counts['byMonth'][m] != n:
            raise SystemExit('%s 건수가 달라졌습니다 (%s → %s)' % (m, n, counts['byMonth'][m]))
    merged['flights']['counts'] = counts
    merged['counts'] = dict(master['counts'])
    merged['counts']['deals'] = counts['total']

    # ── notes · extended ──────────────────────────────────────
    notes = dict(master['flights']['notes'])
    for month in ('2027-09', '2027-10'):
        if month not in notes:
            raise SystemExit('%s notes 가 없습니다' % month)
        note = build_notes(month, cells, notes[month])
        for word in BANNED:
            if word in note:
                raise SystemExit('note 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
        notes[month] = note
    merged['flights']['notes'] = notes
    bw = dict(master['flights']['bookingWindow'])
    bw['note'] = note_append(bw['note'], (
        '일본 7개 노선의 2027년 9~10월은 귀국일 2027-10-11까지만 조회가 열린 경우가 많아 '
        '10/14주 이후는 노선별로 값이 있거나 미오픈입니다(시즈오카는 9~10월 30칸이 시즌 스케줄 미게시로 판매편 0건).'))
    merged['flights']['bookingWindow'] = bw
    for word in BANNED:
        if word in args.note or word in bw['note']:
            raise SystemExit('note 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    merged['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')

    print('노선별 추가:', dict(added), '합계', sum(added.values()))
    print('상태:', dict(collections.Counter(m['status'] for m in marks)))
    print('counts:', json.dumps(counts, ensure_ascii=False))
    for code in ORDER:
        got = [d for d in new_routes[code]['deals'] if '2027-09-01' <= d['date'] <= '2027-10-31']
        if got:
            low = min(got, key=lambda d: d['price'])
            print('  %s %d칸 최저 %s %s %s %s' % (code, len(got), low['date'], low['pattern'],
                                                 low['price'], low['note']))
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
