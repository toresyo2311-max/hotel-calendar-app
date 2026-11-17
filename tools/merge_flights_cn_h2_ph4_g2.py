#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 항공 특가 **추가 완본 3건**을 `data/master_db.json` 의 `flights` 에 한꺼번에 병합한다.

  1) 중국 신규 8개 노선(선양·다롄·광저우·샤먼·연길·장가계·구이린·황산)
     **2027년 7~11월 15주말 × 7패턴 840칸 + 미오픈 검증 16칸** — 3번 보고
     `data-sources/flights-china-new8-h2/` (요약 · part1 · part2 · 주말행렬 CSV)
     측정 465 / 요금 미공개 255 / 0건 120 + 10/15·11/12 금~일 미오픈 16칸(예약창 2027-10-13까지)
  2) 필리핀 4개 노선(세부·마닐라·보홀(팡라오)·클락) **2027년 2~6월 21주 × 5패턴 420칸** — 4번 보고
     `data-sources/flights-sea-new8/부산출발-필리핀4노선-세부마닐라보홀클락-2_6월.md`
     최저 세부 3/12~14 265,706원(에어부산 직항) · 4~6월은 LCC 하계 스케줄 미판매로 경유 위주
  3) 중국 G2 4개 노선(연길·장가계·구이린·황산) **2027년 2~6월 금~월(3박) 84칸** — 2번 보고
     `data-sources/flights-china-new8/부산출발-중국4노선-연길장가계구이린황산-2_6월.md`
     값 75칸 + 황산 판매편 0건 9칸 → 이 4개 노선 2~6월 **336/420칸**

읽는 곳:
  · 중국 7~11월 — 주말행렬 CSV(`노선,주말기준(금),패턴,출발,도착,상태,최저가(원),항공사,경유횟수,소요시간,경유지`)
    를 값의 원본으로 쓰고, part1·part2 의 월별 표(노선 × 7~10월 × 5패턴) + 당일치기 줄 + 노선별 기간 최저·
    특징(요금 미공개·0건 칸 수)과 **전수 대조**한다.
  · 필리핀 — `## 부산(PUS) ↔ 세부(CEB)` → `### 상세` 표 105줄(값의 원본) + `### 주차 × 패턴 최저가 달력`
    + 절 머리 요약(최저·최고·평균·직항 조합 수) + `### 가장 싼 10개 조합` + `### 주차별 4노선 통합 최저가`.
  · 중국 G2 — 부록 줄 `- 2027-02-05(금) · 금~월(3박) · PUS–YNJ · 932,000원 · … · 경유(Shanghai 13h 20m, 총18h 10m)`
    를 값의 원본으로 쓰고, 2절 표(21주 × 5패턴)와 대조한다. 이미 앱에 있는 금~일·토~월·목~일 336칸은
    **금액이 하나라도 달라지면 멈춘다**(같은 조사라 값이 같아야 한다).

규칙:
  · 값은 원문 그대로. 항공사·경유지 이름만 앱 표기(한국어)로 옮긴다.
  · `요금 미공개`(운항편은 있으나 요금 미게시) · `0건`(판매편 없음) · `미오픈`(예약창 밖)을 서로 구분해
    `noSale` 에 `status` 로 남긴다(nosal·nofare·unopened). 값이 있는 칸만 `deals` 로 들어간다.
  · 호텔 538곳 · 아코르 SNU 43줄 · 출처 목록 · 패턴 정의 · 기존 `noSale` · 대상 밖 노선은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)·`counts.routes`·`counts.deals` 와
    2027-02~06·07~11 `notes`(커버리지 문구), `bookingWindow` 를 다시 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_cn_h2_ph4_g2.py --dry-run
    python3 tools/merge_flights_cn_h2_ph4_g2.py --note "..."
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
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources'))
H2_SUM = os.path.join(SRC, 'flights-china-new8-h2', '0-pus_cn_flights_2027_07_11_summary.md')
H2_P1 = os.path.join(SRC, 'flights-china-new8-h2', '1-pus_cn_flights_2027_07_11_part1.md')
H2_P2 = os.path.join(SRC, 'flights-china-new8-h2', '2-pus_cn_flights_2027_07_11_part2.md')
H2_CSV = os.path.join(SRC, 'flights-china-new8-h2', '3-pus_cn_flights_2027_weekend_matrix.csv')
PH_MD = os.path.join(SRC, 'flights-sea-new8',
                     '부산출발-필리핀4노선-세부마닐라보홀클락-2_6월.md')
G2_MD = os.path.join(SRC, 'flights-china-new8',
                     '부산출발-중국4노선-연길장가계구이린황산-2_6월.md')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
CN8 = ('SHE', 'DLC', 'CAN', 'XMN', 'YNJ', 'DYG', 'KWL', 'TXN')
CN8_CITY = {'SHE': '선양', 'DLC': '다롄', 'CAN': '광저우', 'XMN': '샤먼',
            'YNJ': '연길', 'DYG': '장가계', 'KWL': '구이린', 'TXN': '황산',
            'CEB': '세부', 'MNL': '마닐라', 'TAG': '보홀(팡라오)', 'CRK': '클락'}
G1 = ('SHE', 'DLC', 'CAN', 'XMN')
G2 = ('YNJ', 'DYG', 'KWL', 'TXN')
PH4 = ('CEB', 'MNL', 'TAG', 'CRK')
PAT7 = ('목~일', '금~일', '토~월', '금~월', '목~월', '토~토', '일~일')
PAT5 = ('목~일', '금~일', '토~월', '금~월', '목~월')
# 주말행렬 CSV 의 '주말기준(금)' 15주(2027-07-02 ~ 2027-10-08) + 미오픈 검증 10-15·11-12
H2_WEEKENDS = ('2027-07-02', '2027-07-09', '2027-07-16', '2027-07-23', '2027-07-30',
               '2027-08-06', '2027-08-13', '2027-08-20', '2027-08-27',
               '2027-09-03', '2027-09-10', '2027-09-17', '2027-09-24',
               '2027-10-01', '2027-10-08')
H2_PROBE = ('2027-10-15', '2027-11-12')

AIRPORT = {'서울특별시의 인천국제공항': '인천', '홍콩의 홍콩 국제 공항': '홍콩', '서울특별시': '서울'}

# ── 원문이 말하는 값 ────────────────────────────────────────────────────────────
EXPECT_H2 = {
    'cells': 840, 'measured': 465, 'nofare': 255, 'nosale': 120, 'unopened': 16,
    'weekends': 15, 'probe': 2,
    # '노선별 특징' — 요금 미공개·0건 칸 수
    'nofare_by_route': {'SHE': 30, 'DLC': 0, 'CAN': 15, 'XMN': 30,
                        'YNJ': 0, 'DYG': 60, 'KWL': 75, 'TXN': 45},
    'nosale_by_route': {'SHE': 0, 'DLC': 0, 'CAN': 0, 'XMN': 0,
                        'YNJ': 0, 'DYG': 30, 'KWL': 30, 'TXN': 60},
    # '노선별 기간 최저 (7월~10월 초)' — 요금 미공개는 None
    'route_low': {'SHE': 429800, 'DLC': 478700, 'CAN': 513000, 'XMN': 513000,
                  'YNJ': 645200, 'DYG': 2556800, 'KWL': None, 'TXN': None},
    # '패턴별 최저 (전 노선 통틀어)' — 5패턴
    'pat_low': {'금~일': ('DLC', 478700), '목~일': ('DLC', 478700), '토~월': ('DLC', 478700),
                '금~월': ('SHE', 429800), '목~월': ('DLC', 478700)},
    # 당일치기 실측 칸(토~토·일~일) — 노선별 최저
    'day_low': {'DLC': (479700, '2027-09-04'), 'YNJ': (809700, '2027-09-25'),
                'CAN': (899300, '2027-07-04')},
}
# 필리핀 4노선 2027년 2~6월 — 절 머리 요약(최저·최고·평균·최저가가 직항인 조합 수)
EXPECT_PH = {
    'CEB': {'low': 265706, 'high': 854100, 'avg': 545061, 'direct': 40},
    'MNL': {'low': 382487, 'high': 832873, 'avg': 472987, 'direct': 17},
    'TAG': {'low': 496224, 'high': 1264800, 'avg': 687911, 'direct': 20},
    'CRK': {'low': 409800, 'high': 924700, 'avg': 512019, 'direct': 0},
}
# 중국 G2 — 부록 4노선 × 105칸 = 420칸(값 307 · 0건 29 · 미측정 84), 금~월 84칸 중 값 75 · 0건 9
EXPECT_G2 = {
    'cells': 420, 'values': 307, 'nosale': 29, 'unmeasured': 84,
    'frimon_values': 75, 'frimon_nosale': 9,
    'route_low': {'YNJ': 455700, 'DYG': 686700, 'KWL': 526600, 'TXN': 791900},
}
PREV_TOTAL = 4258
EXPECT_TOTAL = 5218           # 신규 960칸(중국 7~11월 465 · 필리핀 420 · 중국 금~월 75)
EXPECT_NOSALE_TOTAL = 53 + 129     # 기존 53 + 중국 0건 120 + 황산 금~월 0건 9
EXPECT_NOFARE_TOTAL = 255
EXPECT_UNOPENED_TOTAL = 16

MONEY = re.compile(r'([\d,]+)')
ROUTE_HEAD = re.compile(r'^## (선양|다롄|광저우|샤먼|연길|장가계|구이린|황산)$')
MONTH_HEAD = re.compile(r'^\*\*(\d+)월\*\*$')
TBL_ROW = re.compile(r'^\| ([월화수목금토일]~[월화수목금토일]) \| ([^|]+?) \| (?:🔴 )?\*\*([\d,]+)\*\* \| (.+?) \|$')
TBL_NONE = re.compile(r'^\| ([월화수목금토일]~[월화수목금토일]) \| — \| 요금 미공개 \| — \|$')
DAY_LINE = re.compile(r'^당일치기: (?:🔴 \*\*([\d,]+)\*\* (\d{2}-\d{2}) · (.+)|(요금 미공개|0건))$')
PERIOD_LOW = re.compile(r'^기간 최저 🔴 \*\*([\d,]+)원\*\* · (\d{2}-\d{2})~(\d{2}-\d{2})\(([월화수목금토일]~[월화수목금토일])\) · (.+)$')
FEATURE = re.compile(r'^- \*\*(선양|다롄|광저우|샤먼|연길|장가계|구이린|황산)\*\*: (.+)$')
SUM_MIN_ROW = re.compile(r'^\| (선양|다롄|광저우|샤먼|연길|장가계|구이린|황산) \| (?:🔴 \*\*([\d,]+)\*\*|요금 미공개) \|')
PAT_LOW_ROW = re.compile(r'^\| ([월화수목금토일]~[월화수목금토일]) \| (선양|다롄|광저우|샤먼|연길|장가계|구이린|황산) \| 🔴 \*\*([\d,]+)\*\* \|')
PH_HEAD = re.compile(r'^## 부산\(PUS\) ↔ .*\(([A-Z]{3})\)$')
PH_ROW = re.compile(r'^\|\s*(\d+)\s*\|\s*(\d+)주\s*\|\s*([월화수목금토일]~[월화수목금토일])\((\d)박\)\s*\|'
                    r'\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d,]+)\s*\|'
                    r'\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|')
PH_CAL = re.compile(r'^\|\s*(\d+)주\s*\|(.+)\|\s*$')
PH_SUM = re.compile(r'^- 최저 \*\*₩([\d,]+)\*\* \((\d{4}-\d{2}-\d{2}) → (\d{4}-\d{2}-\d{2}), '
                    r'([^,]+), (.+?)\) · 최고 ₩([\d,]+) · 평균 ₩([\d,]+)$')
PH_DIRECT = re.compile(r'^- 최저가가 직항인 조합 (\d+)/105 · 경유가 최저가인 조합 (\d+)/105$')
PH_TOP = re.compile(r'^\| 부산 ↔ ([^|]+?)\s*\|\s*\*\*₩([\d,]+)\*\*\s*\|\s*(\d{4}-\d{2}-\d{2}) → '
                    r'(\d{4}-\d{2}-\d{2}) · ([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|')
PH_WEEK = re.compile(r'^\| (\d+)주 \| (\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2}) \| ([\d,]+) \| ([^|]+?) \|$')
PH_CHEAP = re.compile(r'^\| (\d+) \| (세부|마닐라|보홀\(팡라오\)|클락) \| (\d{4}-\d{2}-\d{2}) → '
                      r'(\d{4}-\d{2}-\d{2}) \| ([^(|]+)\((\d)박\) \| ([\d,]+) \| ([^|]+?) \| ([^|]+?) \|')
G2_LINE = re.compile(r'^- (\d{4}-\d{2}-\d{2})\(([월화수목금토일])\) · ([월화수목금토일]~[월화수목금토일])\((\d)박\) '
                     r'· PUS–([A-Z]{3}) · (.+)$')
G2_TBL_ROW = re.compile(r'^\| (\d{2})/(\d{2}) \|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|$')

# 부록 영문 항공사 → 앱 표기 (긴 이름부터)
AIR_EN = (
    ('China Eastern Airlines', '중국동방항공'), ('China Southern Airlines', '중국남방항공'),
    ('Shanghai Airlines', '상하이항공'), ('Hong Kong Express', '홍콩 익스프레스항공'),
    ('HK Express', '홍콩 익스프레스항공'),
    ('Spring Airlines', '춘추항공'), ('Juneyao Airlines', '주니야오항공'),
    ('Air China', '중국국제항공'), ('Korean Air', '대한항공'), ('Asiana Airlines', '아시아나항공'),
    ('Jeju Air', '제주항공'), ('Eastar Jet', '이스타항공'), ('Jin Air', '진에어'),
    ('Air Busan', '에어부산'), ('Tway Air', '티웨이항공'), ('Air Seoul', '에어서울'),
    ('Philippine Airlines', '필리핀항공'), ('Cathay Pacific', '캐세이퍼시픽항공'),
    ('VietJet Air', '비엣젯항공'), ('Xiamen Airlines', '샤먼항공'), ('Shenzhen Airlines', '선전항공'),
    ('Shandong Airlines', '산둥항공'), ('China Airlines', '중화항공'), ('EVA Air', '에바항공'),
)
CITY_EN = {'Seoul': '서울', 'Beijing': '베이징', 'Shanghai': '상하이', 'Hong Kong': '홍콩',
           'Jeju City': '제주', 'Jeju': '제주', 'Taipei': '타이베이', 'Xiamen': '샤먼',
           'Nanjing': '난징', 'Guangzhou': '광저우', 'Incheon': '인천', 'Qingdao': '칭다오'}


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def norm_money(text):
    return int(re.sub(r'[^\d]', '', text))


def dur_ko(text):
    """'13h 20m' → '13시간 20분', '2h' → '2시간', '5시간 50분' 그대로."""
    t = text.strip()
    t = re.sub(r'(\d+)h\s*(\d+)m', r'\1시간 \2분', t)
    t = re.sub(r'(\d+)h\b', r'\1시간', t)
    return t


def air_ko(text):
    """부록의 영문 항공사 나열 → 앱 표기('대한항공+중국남방항공')."""
    rest = text.strip()
    names = []
    while rest:
        for en, ko in AIR_EN:
            if rest.startswith(en):
                if ko not in names:
                    names.append(ko)
                rest = rest[len(en):].strip(' ,')
                break
        else:
            raise SystemExit('모르는 항공사 표기: %r' % text)
    return '+'.join(names)


def route_ko(text):
    """부록의 경유 상세 → 앱 표기('경유(서울 7시간 40분, 총 11시간 15분)')."""
    m = re.match(r'^(직항|경유)\((.*)\)$', text.strip())
    if not m:
        raise SystemExit('경유 표기가 아닙니다: %r' % text)
    kind, body = m.groups()
    parts = [p.strip() for p in body.split(',')]
    out = []
    for p in parts:
        if p.startswith('총'):
            out.append('총 ' + dur_ko(p[1:]).lstrip())
        elif p in CITY_EN:
            out.append(CITY_EN[p])
        elif re.match(r'^[A-Z][a-z]+( [A-Z][a-z]+)* \d+h', p):
            city, dur = p.rsplit(' ', 1)
            out.append('%s %s' % (CITY_EN.get(city, city), dur_ko(dur)))
        else:
            out.append(dur_ko(p))
    return '%s(%s)' % (kind, ', '.join(out))


# ── 1) 중국 8노선 2027년 7~11월 주말행렬 ────────────────────────────────────────
def parse_h2_csv(path):
    deals, marks, counts = {}, [], collections.Counter()
    with open(path, encoding='utf-8-sig', newline='') as fp:
        for row in csv.DictReader(fp):
            code = row['노선'].strip()
            if code not in CN8:
                raise SystemExit('예상 밖 노선: %s' % row)
            wk, pat = row['주말기준(금)'].strip(), row['패턴'].strip()
            date, back, status = row['출발'].strip(), row['도착'].strip(), row['상태'].strip()
            if pat not in PAT7:
                raise SystemExit('예상 밖 패턴: %s' % row)
            if back_date(date, pat) != back:
                raise SystemExit('귀국일이 패턴과 다릅니다: %s' % row)
            if date <= '2027-06-30' or date > '2027-11-30':
                raise SystemExit('2027년 7~11월 밖 출발일입니다: %s' % row)
            if status == '미오픈':
                if wk not in H2_PROBE or pat != '금~일':
                    raise SystemExit('예상 밖 미오픈 칸: %s' % row)
                marks.append({'code': code, 'date': date, 'back': back, 'pattern': pat,
                              'status': 'unopened',
                              'note': '예약창 밖(2027-10-13까지) — 항공사 스케줄 미개시'})
                counts['unopened'] += 1
                continue
            if wk not in H2_WEEKENDS:
                raise SystemExit('예상 밖 주말 기준일: %s' % row)
            if status == '요금미공개':
                marks.append({'code': code, 'date': date, 'back': back, 'pattern': pat,
                              'status': 'nofare',
                              'note': '운항편은 표시되나 요금 미게시(예약 불가)'})
                counts['nofare'] += 1
                continue
            if status == '0건':
                marks.append({'code': code, 'date': date, 'back': back, 'pattern': pat,
                              'status': 'nosale', 'note': '검색 결과 0건(판매편 없음)'})
                counts['nosale'] += 1
                continue
            if status != '측정':
                raise SystemExit('예상 밖 상태: %s' % row)
            price = norm_money(row['최저가(원)'])
            if price <= 0 or not row['항공사'].strip():
                raise SystemExit('측정 칸에 값/항공사가 없습니다: %s' % row)
            stops = int(row['경유횟수'] or 0)
            place = row['경유지'].strip()
            dur = dur_ko(row['소요시간'])
            if stops == 0:
                note = '직항(총 %s)' % dur
            elif stops == 1:
                note = '경유(%s, 총 %s)' % (AIRPORT.get(place, place), dur)
            else:
                note = '경유(%d회, 총 %s)' % (stops, dur)
            airline = '+'.join(a.strip() for a in row['항공사'].split(','))
            key = (code, date, pat)
            if key in deals:
                raise SystemExit('%s %s %s 중복' % key)
            deals[key] = {'date': date, 'back': back, 'pattern': pat, 'price': price,
                          'airline': airline, 'via': stops > 0, 'note': note}
            counts['measured'] += 1
    return deals, marks, counts


def parse_h2_parts(summary_path, *paths):
    """part1·part2 의 월별 표·당일치기 줄·노선 특징 + 요약표 → 검증용 기대값."""
    monthly, dayminus, features, period, sum_low, pat_low = {}, {}, {}, {}, {}, {}
    t_sum = open(summary_path, encoding='utf-8').read()
    for m in re.finditer(r'^\| (선양|다롄|광저우|샤먼|연길|장가계|구이린|황산) \| '
                         r'(?:🔴 \*\*([\d,]+)\*\*|(요금 미공개))', t_sum, re.M):
        name, price, none = m.groups()
        c = {v: k for k, v in CN8_CITY.items()}[name]
        if c not in sum_low:            # '노선별 기간 최저' 표가 '월별 최저' 표보다 먼저 온다
            sum_low[c] = norm_money(price) if price else None
    for m in re.finditer(r'^\| ([월화수목금토일]~[월화수목금토일]) \| '
                         r'(선양|다롄|광저우|샤먼|연길|장가계|구이린|황산) \| 🔴 \*\*([\d,]+)\*\*',
                         t_sum, re.M):
        pat, name, price = m.groups()
        pat_low[pat] = ({v: k for k, v in CN8_CITY.items()}[name], norm_money(price))
    for path in paths:
        code = month = None
        for raw in open(path, encoding='utf-8'):
            line = raw.strip()
            m = ROUTE_HEAD.match(line)
            if m:
                code, month = {v: k for k, v in CN8_CITY.items()}[m.group(1)], None
                continue
            if line.startswith('## '):
                code = month = None
                continue
            m = MONTH_HEAD.match(line)
            if m and code:
                month = int(m.group(1))
                continue
            m = PERIOD_LOW.match(line)
            if m and code and month is None:
                period[code] = (norm_money(m.group(1)), m.group(2), m.group(3), m.group(4))
                continue
            m = FEATURE.match(line)
            if m:
                name, body = m.groups()
                c = {v: k for k, v in CN8_CITY.items()}[name]
                nf = re.search(r'요금 미공개 (\d+)칸', body)
                ns = re.search(r'0건 (\d+)칸', body)
                features[c] = (int(nf.group(1)) if nf else 0, int(ns.group(1)) if ns else 0)
                continue
            if code and month:
                m = TBL_ROW.match(line)
                if m:
                    pat, span, price, desc = m.groups()
                    monthly[(code, month, pat)] = (norm_money(price), span, desc)
                    continue
                m = TBL_NONE.match(line)
                if m:
                    monthly[(code, month, m.group(1))] = None
                    continue
                m = DAY_LINE.match(line)
                if m:
                    if m.group(4):
                        dayminus[(code, month)] = ('none', m.group(4))
                    else:
                        dayminus[(code, month)] = (norm_money(m.group(1)), m.group(2), m.group(3))
                    continue
    return monthly, dayminus, features, period, sum_low, pat_low


def check_h2(text_all, deals, marks, counts, monthly, dayminus, features, period, sum_low, pat_low):
    bad = []
    if dict(counts) != {'measured': EXPECT_H2['measured'], 'nofare': EXPECT_H2['nofare'],
                        'nosale': EXPECT_H2['nosale'], 'unopened': EXPECT_H2['unopened']}:
        bad.append('중국 7~11월 집계 %s (원문 465/255/120/16)' % dict(counts))
    if '8개 노선 × 15주말 × 7패턴 = 840칸을 전부 조회했고(측정 465 / 요금 미공개 255 / 0건 120)' \
            not in text_all:
        bad.append('중국 7~11월 완료 문장(840칸·465/255/120)을 찾지 못했습니다')
    if '2027년 10월 13일까지 열림' not in text_all:
        bad.append('예약창(2027-10-13) 문장을 찾지 못했습니다')
    # 주말별 56칸(8노선 × 7패턴), 미오픈 주말은 8칸
    cells = set(deals) | {(m['code'], m['date'], m['pattern']) for m in marks}
    for wk in H2_WEEKENDS:
        thu = (datetime.date.fromisoformat(wk) - datetime.timedelta(days=1))
        want = {(code, (thu + datetime.timedelta(days=(WD[p[0]] - WD['목']) % 7)).isoformat(), p)
                for code in CN8 for p in PAT7}
        got = cells & want
        if len(got) != 56:
            bad.append('중국 %s주 %d칸 (56칸이어야 함) 빠진 칸 %s'
                       % (wk, len(got), sorted(want - got)[:3]))
    for m in marks:
        if m['status'] == 'unopened' and (m['date'] not in ('2027-10-15', '2027-11-12')):
            bad.append('미오픈 칸 날짜 이상: %s' % (m,))
    for code, want in EXPECT_H2['nofare_by_route'].items():
        got = sum(1 for m in marks if m['code'] == code and m['status'] == 'nofare')
        if got != want:
            bad.append('중국 %s 요금 미공개 %d칸 (원문 %d칸)' % (code, got, want))
    for code, want in EXPECT_H2['nosale_by_route'].items():
        got = sum(1 for m in marks if m['code'] == code and m['status'] == 'nosale')
        if got != want:
            bad.append('중국 %s 판매편 0건 %d칸 (원문 %d칸)' % (code, got, want))
    # 노선별 기간 최저(7월~10월 초) — 요금 미공개 노선은 값이 없어야 한다
    for code, want in EXPECT_H2['route_low'].items():
        ps = [d['price'] for (c, _d, _p), d in deals.items() if c == code]
        got = min(ps) if ps else None
        if got != want:
            bad.append('중국 %s 기간 최저 %s (원문 %s)' % (code, got, want))
        if sum_low.get(code) != want:
            bad.append('중국 %s 요약표 최저 %s (원문 %s)' % (code, sum_low.get(code), want))
    # 패턴별 최저(전 노선)
    for pat, want in EXPECT_H2['pat_low'].items():
        ps = [(d['price'], c) for (c, _d, p), d in deals.items() if p == pat]
        got = min(ps)
        if got != (want[1], want[0]):
            bad.append('중국 %s 패턴 최저 %s (원문 %s)' % (pat, got, want))
        if pat_low.get(pat) != want:
            bad.append('중국 %s 요약 패턴 최저 %s (원문 %s)' % (pat, pat_low.get(pat), want))
    # 당일치기 노선별 최저
    for code, (want_price, want_date) in EXPECT_H2['day_low'].items():
        ps = [(d['price'], d['date']) for (c, _d, p), d in deals.items()
              if c == code and p in ('토~토', '일~일')]
        if min(ps) != (want_price, want_date):
            bad.append('중국 %s 당일치기 최저 %s (원문 %s)' % (code, min(ps), (want_price, want_date)))
    # 노선 특징(요금 미공개·0건 칸 수)
    for code, want in features.items():
        if want != (EXPECT_H2['nofare_by_route'][code], EXPECT_H2['nosale_by_route'][code]):
            bad.append('중국 %s 특징 %s (원문 %s)' % (code, want,
                   (EXPECT_H2['nofare_by_route'][code], EXPECT_H2['nosale_by_route'][code])))
    # 월별 표(노선 × 월 × 패턴) ↔ CSV
    for (code, month, pat), want in monthly.items():
        ps = [(d['price'], d['date']) for (c, date, p), d in deals.items()
              if c == code and p == pat and int(date[5:7]) == month]
        if want is None:
            if ps:
                bad.append('중국 %s %d월 %s 요금 미공개인데 값이 있음: %s' % (code, month, pat, ps[:2]))
            continue
        if not ps:
            bad.append('중국 %s %d월 %s 표에 %d원인데 CSV에 값이 없음' % (code, month, pat, want[0]))
            continue
        if min(ps)[0] != want[0]:
            bad.append('중국 %s %d월 %s 최저 %d (원문 %d)' % (code, month, pat, min(ps)[0], want[0]))
        if min(ps)[1][5:] != want[1][:5]:
            bad.append('중국 %s %d월 %s 최저 출발일 %s (원문 %s)'
                       % (code, month, pat, min(ps)[1][5:], want[1][:5]))
    # 당일치기 월별 최저
    for (code, month), want in dayminus.items():
        ps = [(d['price'], d['date']) for (c, date, p), d in deals.items()
              if c == code and p in ('토~토', '일~일') and int(date[5:7]) == month]
        if want[0] == 'none':
            if want[1] == '요금 미공개':
                nf = [m for m in marks if m['code'] == code and m['status'] == 'nofare'
                      and m['pattern'] in ('토~토', '일~일') and int(m['date'][5:7]) == month]
                if ps or not nf:
                    bad.append('중국 %s %d월 당일치기 미공개인데 값 %d칸·미공개 %d칸'
                               % (code, month, len(ps), len(nf)))
            elif want[1] == '0건':
                ns = [m for m in marks if m['code'] == code and m['status'] == 'nosale'
                      and m['pattern'] in ('토~토', '일~일') and int(m['date'][5:7]) == month]
                if ps or not ns:
                    bad.append('중국 %s %d월 당일치기 0건인데 값 %d칸·0건 %d칸'
                               % (code, month, len(ps), len(ns)))
            continue
        if not ps or min(ps)[0] != want[0]:
            bad.append('중국 %s %d월 당일치기 최저 %s (원문 %s)'
                       % (code, month, min(ps) if ps else None, want[0]))
        elif min(ps)[1][5:] != want[1]:
            bad.append('중국 %s %d월 당일치기 최저일 %s (원문 %s)'
                       % (code, month, min(ps)[1][5:], want[1]))
    return bad


# ── 2) 필리핀 4노선 2027년 2~6월 ───────────────────────────────────────────────
def ph_city(code):
    return {'CEB': '세부', 'MNL': '마닐라', 'TAG': '보홀(팡라오)', 'CRK': '클락'}[code]


def parse_ph(text):
    deals, cal, summary, top, weeks, cheap = {}, {}, {}, {}, [], []
    code = None
    for raw in text.splitlines():
        line = raw.strip()
        m = PH_HEAD.match(line)
        if m:
            code = m.group(1)
            if code not in PH4:
                raise SystemExit('예상 밖 노선: %s' % line)
            cal[code] = {}
            continue
        if line.startswith('## '):
            code = None
            continue
        if code:
            m = PH_ROW.match(line)
            if m:
                (_n, week, pat, nights, date, back, price, airline, via,
                 going, ret, memo) = m.groups()
                if int(nights) != (WD[pat[-1]] - WD[pat[0]]) % 7:
                    raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
                if back_date(date, pat) != back:
                    raise SystemExit('귀국일이 패턴과 다릅니다: %s' % line)
                if via not in ('직항', '경유 1회'):
                    raise SystemExit('직항/경유 표기가 예상과 다릅니다: %r' % via)
                note = '%s %s · 오는편 %s' % (via, going, ret)
                if memo:
                    note += ' · ' + memo.replace('₩', '')
                deal = {'date': date, 'back': back, 'pattern': pat,
                        'price': norm_money(price), 'airline': airline,
                        'via': via != '직항', 'note': note}
                alt = re.search(r'직항 최저 ([\d,]+)원', memo)
                if alt:
                    deal['alt'] = norm_money(alt.group(1))
                key = (code, date, pat)
                if key in deals:
                    raise SystemExit('%s %s %s 중복' % key)
                deals[key] = deal
                continue
            m = PH_CAL.match(line)
            if m:
                week = int(m.group(1))
                vals = [v.strip().strip('*').replace(',', '') for v in m.group(2).split('|')]
                vals = [v for v in vals if v]
                if len(vals) != 5:
                    raise SystemExit('달력 줄 칸 수가 5가 아닙니다: %s' % line)
                if not all(re.fullmatch(r'\d+', v) for v in vals):
                    raise SystemExit('달력 값이 숫자가 아닙니다: %s' % line)
                cal[code][week] = [int(v) for v in vals]
                continue
            m = PH_SUM.match(line)
            if m:
                summary[code] = {'low': norm_money(m.group(1)),
                                 'dates': (m.group(2), m.group(3)),
                                 'pat': m.group(4), 'who': m.group(5),
                                 'high': norm_money(m.group(6)),
                                 'avg': norm_money(m.group(7))}
                continue
            m = PH_DIRECT.match(line)
            if m:
                summary.setdefault(code, {})['direct'] = int(m.group(1))
                continue
        m = PH_TOP.match(line)
        if m:
            city, price, d1, d2, span, pat, airline, via = m.groups()
            c = next(k for k in PH4 if ph_city(k) == city.strip())
            top[c] = (norm_money(price), d1, d2, pat.strip(), airline.strip(), via.strip())
            continue
        m = PH_WEEK.match(line)
        if m:
            weeks.append((int(m.group(1)), m.group(2), m.group(3), norm_money(m.group(4)),
                          m.group(5).strip()))
            continue
        m = PH_CHEAP.match(line)
        if m:
            cheap.append((int(m.group(1)), m.group(2), m.group(3), m.group(4),
                          m.group(5).strip() + '(' + m.group(6) + '박)', norm_money(m.group(7)),
                          m.group(8).strip(), m.group(9).strip()))
    return deals, cal, summary, top, weeks, cheap


def check_ph(text, deals, cal, summary, top, weeks, cheap):
    bad = []
    if {c for (c, _d, _p) in deals} != set(PH4):
        bad.append('필리핀 노선 집합이 다릅니다')
    for code in PH4:
        mine = {k: v for k, v in deals.items() if k[0] == code}
        if len(mine) != 105:
            bad.append('필리핀 %s %d칸 (105칸이어야 함)' % (code, len(mine)))
        per = collections.Counter(d['pattern'] for d in mine.values())
        for p in PAT5:
            if per.get(p) != 21:
                bad.append('필리핀 %s %s %d칸 (21칸이어야 함)' % (code, p, per.get(p)))
        prices = [d['price'] for d in mine.values()]
        want = EXPECT_PH[code]
        s = summary.get(code) or {}
        if min(prices) != want['low'] or max(prices) != want['high']:
            bad.append('필리핀 %s 최저·최고 %s (원문 %s)'
                       % (code, (min(prices), max(prices)), (want['low'], want['high'])))
        avg_floor = int(sum(prices) / len(prices))
        avg_round = round(sum(prices) / len(prices))
        if s.get('avg') not in (avg_floor, avg_round):
            bad.append('필리핀 %s 평균 %d/%d (원문 %d)'
                       % (code, avg_floor, avg_round, s.get('avg')))
        direct_min = [d['price'] for d in mine.values() if d['via'] is False]
        direct_min += [d['alt'] for d in mine.values() if d.get('alt')]
        n_direct = sum(1 for d in mine.values() if d['via'] is False)
        if n_direct != want['direct']:
            bad.append('필리핀 %s 직항 최저 조합 %d (원문 %d)' % (code, n_direct, want['direct']))
        low = next(d for d in mine.values() if d['price'] == min(prices))
        if not any((d['date'], d['back']) == s.get('dates') and d['price'] == min(prices)
                   for d in mine.values()):
            bad.append('필리핀 %s 최저 칸 날짜 %s (원문 %s)'
                       % (code, (low['date'], low['back']), s.get('dates')))
        if not s.get('who', '').startswith(low['airline']):
            bad.append('필리핀 %s 최저 칸 항공사 %r (원문 %r)' % (code, low['airline'], s.get('who')))
        # 달력(21주 × 5패턴) ↔ 상세
        if len(cal.get(code) or {}) != 21:
            bad.append('필리핀 %s 달력 %d줄 (21줄이어야 함)' % (code, len(cal.get(code) or {})))
        for week in range(1, 22):
            thu = (datetime.date.fromisoformat('2027-02-04') +
                   datetime.timedelta(days=7 * (week - 1))).isoformat()
            for i, pat in enumerate(PAT5):
                out = (datetime.date.fromisoformat(thu) +
                       datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
                hit = mine.get((code, out, pat))
                got = (cal.get(code) or {}).get(week, [None] * 5)[i]
                if not hit:
                    bad.append('필리핀 %s %d주 %s 상세 표에 없음(%s)' % (code, week, pat, out))
                elif hit['price'] != got:
                    bad.append('필리핀 %s %d주 %s 달력 %s ≠ 상세 %s'
                               % (code, week, pat, got, hit['price']))
        # 한눈에 표
        t = top.get(code)
        if not t or t[0] != want['low']:
            bad.append('필리핀 %s 한눈에 표 %s (요약 %s)' % (code, t, s.get('low')))
    # 주차별 4노선 통합 최저
    if len(weeks) != 21:
        bad.append('필리핀 주차별 표 %d줄 (21줄이어야 함)' % len(weeks))
    for (n, d1, d2, price, who) in weeks:
        cand = [(d['price'], c, d['pattern']) for (c, d, p), d in deals.items()
                if d1 <= d['date'] <= d2]
        if not cand or min(cand)[0] != price:
            bad.append('필리핀 %d주 통합 최저 %s (원문 %d)' % (n, min(cand) if cand else None, price))
    # 가장 싼 10개 조합
    everything = sorted((d['price'], c, d['date'], d['back'], d['pattern'], d['airline'], d['via'])
                        for (c, _x, _p), d in deals.items())
    if len(cheap) != 10:
        bad.append('필리핀 싼 조합 표 %d줄 (10줄이어야 함)' % len(cheap))
    else:
        for i, row in enumerate(cheap):
            got = everything[i]
            if (row[5], ph_city(got[1]), got[2], got[3]) != (got[0], ph_city(got[1]), got[2], got[3]):
                bad.append('필리핀 싼 조합 %d위 %s (계산 %s)' % (i + 1, row, got))
            if row[6] and not got[5].startswith(row[6]):
                bad.append('필리핀 싼 조합 %d위 항공사 %s (계산 %s)' % (i + 1, row[6], got[5]))
    if '420개 날짜 조합(4노선 × 21주 × 5패턴) 전체에서 가장 싼 조합' not in text:
        bad.append('필리핀 420조합 문장을 찾지 못했습니다')
    if min(d['price'] for d in deals.values()) != 265706:
        bad.append('필리핀 전체 최저 %d (원문 265,706)'
                   % min(d['price'] for d in deals.values()))
    return bad


# ── 3) 중국 G2 2027년 2~6월 금~월 ──────────────────────────────────────────────
def parse_g2(text):
    rows, table = {}, {}
    code = in_table = None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r'^#{2,3} (?:부산–)?[^(]*\(([A-Z]{3})\)', line)
        if m:
            code = m.group(1)
            if code not in G2:
                raise SystemExit('예상 밖 노선: %s' % line)
            in_table = False
            continue
        if line.startswith('## '):
            code = in_table = None
            continue
        if code:
            m = G2_LINE.match(line)
            if m:
                date, wd, pat, nights, rc, rest = m.groups()
                if rc != code:
                    raise SystemExit('절과 노선 코드가 다릅니다: %s' % line)
                if wd != pat[0]:
                    raise SystemExit('출발 요일이 패턴과 다릅니다: %s' % line)
                if int(nights) != (WD[pat[-1]] - WD[pat[0]]) % 7:
                    raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
                if rest.strip() == '미측정':
                    rows[(code, date, pat)] = None
                    continue
                if rest.strip() == '판매편 없음(0건)':
                    rows[(code, date, pat)] = 'zero'
                    continue
                m2 = re.match(r'^([\d,]+)원 · (.+) · ((?:직항|경유)\(.+\))$', rest.strip())
                if not m2:
                    raise SystemExit('부록 줄 형식이 아닙니다: %s' % line)
                rows[(code, date, pat)] = (norm_money(m2.group(1)), air_ko(m2.group(2)),
                                           route_ko(m2.group(3)))
                continue
            m = G2_TBL_ROW.match(line)
            if m:
                in_table = True
                mm, dd = int(m.group(1)), int(m.group(2))
                thu = datetime.date(2027, mm, dd)
                if thu.isoweekday() != 4:
                    raise SystemExit('표의 주 시작일이 목요일이 아닙니다: %s' % line)
                vals = [v.strip() for v in m.groups()[2:]]
                for pat, val in zip(PAT5, vals):
                    out = (thu + datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
                    if val in ('—', ''):
                        table[(code, out, pat)] = None
                    elif val == '0건':
                        table[(code, out, pat)] = 'zero'
                    else:
                        v = val.replace('**', '').replace(' 직항', '').replace(',', '')
                        if not re.fullmatch(r'\d+', v):
                            raise SystemExit('표 값이 숫자가 아닙니다: %s' % line)
                        table[(code, out, pat)] = int(v)
                continue
    return rows, table


def check_g2(text, rows, table):
    bad = []
    if len(rows) != EXPECT_G2['cells']:
        bad.append('G2 부록 %d칸 (원문 420칸)' % len(rows))
    vals = {k: v for k, v in rows.items() if isinstance(v, tuple)}
    zeros = [k for k, v in rows.items() if v == 'zero']
    unmeas = [k for k, v in rows.items() if v is None]
    if (len(vals), len(zeros), len(unmeas)) != (EXPECT_G2['values'], EXPECT_G2['nosale'],
                                                EXPECT_G2['unmeasured']):
        bad.append('G2 값/0건/미측정 %d/%d/%d (원문 %d/%d/%d)'
                   % (len(vals), len(zeros), len(unmeas), EXPECT_G2['values'],
                      EXPECT_G2['nosale'], EXPECT_G2['unmeasured']))
    if {k for k in unmeas if k[2] != '목~월'}:
        bad.append('G2 미측정 칸이 목~월이 아닙니다')
    if len(table) != EXPECT_G2['cells']:
        bad.append('G2 표 %d칸 (원문 420칸)' % len(table))
    mism = [(k, vals[k][0], table[k]) for k in vals if table.get(k) != vals[k][0]]
    if mism:
        bad.append('G2 부록·표 불일치 %d건: %s' % (len(mism), mism[:4]))
    for k in zeros:
        if table.get(k) != 'zero':
            bad.append('G2 0건 칸이 표와 다릅니다: %s' % (k,))
    frimon = [k for k in vals if k[2] == '금~월']
    fz = [k for k in zeros if k[2] == '금~월']
    if (len(frimon), len(fz)) != (EXPECT_G2['frimon_values'], EXPECT_G2['frimon_nosale']):
        bad.append('G2 금~월 값 %d칸·0건 %d칸 (원문 %d·%d)'
                   % (len(frimon), len(fz), EXPECT_G2['frimon_values'], EXPECT_G2['frimon_nosale']))
    for code, want in EXPECT_G2['route_low'].items():
        ps = [v[0] for k, v in vals.items() if k[0] == code]
        if min(ps) != want:
            bad.append('G2 %s 최저 %d (원문 %d)' % (code, min(ps), want))
    for need, want in (('84/105', None), ('420칸 중 336칸(80%) 조회 완료', None)):
        if need not in text:
            bad.append('G2 원문 문장(%s)을 찾지 못했습니다' % need)
    return bad


# ── 4) 병합 ────────────────────────────────────────────────────────────────────
def merge(master, deals_by_group, marks_by_group):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    added, dup, conflicts = [], [], []
    for group in ('H2', 'PH', 'G2'):
        for (code, date, pattern), deal in sorted(deals_by_group[group].items()):
            r = routes[code]
            have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
            if have is not None:
                if have.get('price') != deal['price']:
                    conflicts.append((group, code, date, pattern, have.get('price'), deal['price']))
                dup.append((group, code, date, pattern))
                continue
            if any(n['code'] == code and n['date'] == date and n['pattern'] == pattern
                   for n in fl['noSale']):
                conflicts.append((group, code, date, pattern, 'noSale', deal['price']))
                continue
            r['deals'].append(deal)
            added.append((group, code, date, pattern, deal['price']))
    for group in ('H2', 'PH', 'G2'):
        for (code, date, pattern), mark in sorted(marks_by_group[group].items(),
                                                  key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
            if any(d['date'] == date and d['pattern'] == pattern for d in routes[code]['deals']):
                conflicts.append((group, code, date, pattern, 'deal', mark['status']))
                continue
            if any(n['code'] == code and n['date'] == date and n['pattern'] == pattern
                   for n in fl['noSale']):
                conflicts.append((group, code, date, pattern, 'noSale', mark['status']))
                continue
            fl['noSale'].append(mark)
            added.append((group, code, date, pattern, mark['status']))
    if conflicts:
        raise SystemExit('기존 값과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts[:8])
    touched = {a[1] for a in added}
    for r in fl['routes']:
        if r['code'] in touched:      # 새 칸을 넣은 노선만 출발일 순으로 다시 정렬
            r['deals'].sort(key=lambda d: (d['date'], d['pattern']))
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
    return fl['counts'], by_month


def marks_of(fl, month, status=None, codes=None):
    return [n for n in fl['noSale']
            if n['date'].startswith(month) and (status is None or n.get('status') == status)
            and (codes is None or n['code'] in codes)]


def month_note(fl, month, head):
    """그 달의 중국 8노선·필리핀 4노선·동남아 4노선 커버리지를 실제 데이터에서 세어 문장으로 만든다."""
    routes = {r['code']: r for r in fl['routes']}
    pats4 = ('금~일', '토~월', '목~일', '금~월')
    cnt = collections.Counter()
    for code in G1:
        for d in routes[code]['deals']:
            if d['date'][:7] == month and d['pattern'] in pats4:
                cnt[d['pattern']] += 1
    g1_4n = sum(1 for code in G1 for d in routes[code]['deals']
                if d['date'][:7] == month and d['pattern'] == '목~월')
    cnt3 = collections.Counter()
    for code in G2:
        for d in routes[code]['deals']:
            if d['date'][:7] == month and d['pattern'] in pats4:
                cnt3[d['pattern']] += 1
    ns = sum(1 for n in fl['noSale'] if n['code'] == 'TXN' and n['date'][:7] == month
             and (n.get('status') or 'nosale') == 'nosale')
    p4 = ' · '.join('%s %d' % (p, cnt[p]) for p in pats4 if cnt[p])
    p3 = ' · '.join('%s %d' % (p, cnt3[p]) for p in pats4 if cnt3[p])
    txt = (head +
           '중국 8개 노선은 2박(금~일·토~월)에 목~일·금~월(3박)까지 21주를 조사해 이 달 '
           '선양·다롄·광저우·샤먼 %d칸(%s), 연길·장가계·구이린·황산 %d칸(%s)%s입니다. '
           % (sum(cnt[p] for p in pats4), p4, sum(cnt3[p] for p in pats4), p3,
              ('이고 황산 판매편 0건 %d칸' % ns) if ns else ''))
    txt += ('선양·다롄·광저우·샤먼의 목~월(4박)은 2/4~4/22 12주만 실측했습니다' if g1_4n else
            '선양·다롄·광저우·샤먼의 목~월(4박)은 아직 미조회(—)입니다')
    if g1_4n:
        txt += '(%s %d칸)이고 4/29 이후 9주는 미조회(—)이며, ' % (month, g1_4n)
    else:
        txt += '. '
    txt += '연길·장가계·구이린·황산의 목~월(4박)도 미조회(—)입니다. '
    ph = [(d['price'], d['date'], d['pattern'], code) for code in PH4
          for d in routes[code]['deals'] if d['date'][:7] == month]
    if ph:
        low = min(ph)
        txt += ('필리핀 4개 노선은 2027년 2~6월 21주 × 5패턴 420칸을 전부 실측했습니다 — %s %d칸이고 '
                '이 달 최저는 %s %s %s %s원입니다. '
                % (month, len(ph), CN8_CITY.get(low[3], low[3]), low[1], low[2],
                   format(low[0], ',')))
    sea = [d['price'] for code in ('PQC', 'BKI', 'KUL', 'VTE')
           for d in routes[code]['deals'] if d['date'][:7] == month]
    if sea:
        low = min((d['price'], d['date'], d['pattern'], code) for code in ('PQC', 'BKI', 'KUL', 'VTE')
                  for d in routes[code]['deals'] if d['date'][:7] == month)
        txt += ('동남아 4개 노선은 2027년 2~6월 21주 × 5패턴 420칸을 전부 실측했습니다 — %s %d칸이고 '
                '이 달 최저는 %s %s %s %s원입니다.'
                % (month, len(sea), low[3], low[1], low[2], format(low[0], ',')))
    return txt.rstrip()


def h2_month_note(fl, month):
    """2027년 7~11월 중국 8노선 커버리지 — 측정/요금 미공개/0건/미오픈을 나눠 적는다."""
    routes = {r['code']: r for r in fl['routes']}
    m = [(d['price'], d['date'], d['pattern'], code) for code in CN8
         for d in routes[code]['deals'] if d['date'][:7] == month]
    nf = marks_of(fl, month, 'nofare', CN8)
    ns = marks_of(fl, month, 'nosale', CN8)
    up = marks_of(fl, month, 'unopened', CN8)
    parts = []
    if m:
        low = min(m)
        parts.append('%s %s %s %s원(%s)' % (CN8_CITY[low[3]], low[1], low[2],
                                           format(low[0], ','), routes[low[3]]['deals'] and
                                           next(d for d in routes[low[3]]['deals']
                                                if d['date'] == low[1] and d['pattern'] == low[2]
                                                ).get('airline', '')))
    head = ('중국 신규 8개 노선(선양·다롄·광저우·샤먼·연길·장가계·구이린·황산)의 2027년 %s월 조사분입니다 — '
            '측정 %d칸 · 요금 미공개 %d칸 · 판매편 0건 %d칸%s = %d칸입니다. '
            % (int(month[5:]), len(m), len(nf), len(ns),
               (' · 미오픈 %d칸' % len(up)) if up else '', len(m) + len(nf) + len(ns) + len(up)))
    txt = head
    if parts:
        txt += '이 달 최저는 ' + parts[0] + '입니다. '
    if len(nf) or len(ns):
        txt += ('요금 미공개는 운항편은 표시되나 요금이 게시되지 않은 칸(예약 불가)이고, 판매편 0건은 '
                '조회 결과 항공편 자체가 없는 칸입니다. ')
    if len(ns):
        txt += '판매편 0건이 있는 노선은 %s입니다. ' % '·'.join(
            sorted({CN8_CITY[n['code']] for n in ns}))
    if len(nf):
        txt += '요금 미공개가 있는 노선은 %s입니다. ' % '·'.join(
            sorted({CN8_CITY[n['code']] for n in nf}))
    return txt.rstrip()


def notes_update(fl):
    routes = {r['code']: r for r in fl['routes']}
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
    for month in ('2027-07', '2027-08', '2027-09'):
        fl['notes'][month] = h2_month_note(fl, month)
    fl['notes']['2027-10'] = h2_month_note(fl, '2027-10') + (
        ' 기존 24개 노선은 예약창이 2027-11-14까지이고 10월은 첫 주말(10/1~3)과 10/8~10·'
        '10/15~17·10/29~31 일부만 실측했습니다.')
    fl['notes']['2027-11'] = h2_month_note(fl, '2027-11') + (
        ' 중국 8개 노선의 예약창은 2027-10-13 출발분까지라 10월 14일 이후와 11월 전체가 미오픈이고, '
        '11/12 금~일을 같은 조건으로 조회해 항공사 스케줄 미개시 응답을 확인했습니다. 기존 24개 노선은 '
        '예약창이 2027-11-14까지이며 11/5~7 후쿠오카 1칸만 실측됐습니다.')
    fl['bookingWindow']['note'] = ('2027-11-14 이후 출발일은 날짜 선택이 되지 않습니다(조회 시점 기준). '
                                   '중국 신규 8개 노선(선양·다롄·광저우·샤먼·연길·장가계·구이린·황산)은 '
                                   '2027-10-13 출발분까지만 열려 있고 10/14 이후·11월은 미오픈입니다.')
    fl['bookingWindow']['chinaNew8End'] = '2027-10-13'


def main(argv):
    ap = argparse.ArgumentParser(description='중국 7~11월 8노선 + 필리핀 2~6월 + 중국 G2 금~월 → flights 병합')
    ap.add_argument('--csv', default=H2_CSV)
    ap.add_argument('--summary', default=H2_SUM)
    ap.add_argument('--ph', default=PH_MD)
    ap.add_argument('--g2', default=G2_MD)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    t_sum = open(args.summary, encoding='utf-8').read()
    t_p1 = open(H2_P1, encoding='utf-8').read()
    t_p2 = open(H2_P2, encoding='utf-8').read()
    t_ph = open(args.ph, encoding='utf-8').read()
    t_g2 = open(args.g2, encoding='utf-8').read()

    h2_deals, h2_marks, h2_counts = parse_h2_csv(args.csv)
    monthly, dayminus, features, period, sum_low, pat_low = parse_h2_parts(args.summary, H2_P1, H2_P2)
    ph_deals, ph_cal, ph_sum, ph_top, ph_weeks, ph_cheap = parse_ph(t_ph)
    g2_rows, g2_table = parse_g2(t_g2)

    bad = []
    bad += check_h2(t_sum + t_p1 + t_p2, h2_deals, h2_marks, h2_counts, monthly, dayminus,
                    features, period, sum_low, pat_low)
    bad += check_ph(t_ph, ph_deals, ph_cal, ph_sum, ph_top, ph_weeks, ph_cheap)
    bad += check_g2(t_g2, g2_rows, g2_table)
    print('  중국 7~11월 %d칸(측정) · 미공개 %d · 0건 %d · 미오픈 %d / 필리핀 %d칸 / G2 금~월 %d칸'
          % (len(h2_deals), h2_counts['nofare'], h2_counts['nosale'], h2_counts['unopened'],
             len(ph_deals), sum(1 for k in g2_rows if k[2] == '금~월')))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    # G2: 금~월만 새로 넣는다(이미 있는 336칸은 금액이 같아야 한다)
    g2_deals, g2_marks = {}, {}
    for key, val in g2_rows.items():
        if key[2] != '금~월':
            continue
        code, date, pat = key
        back = back_date(date, pat)
        if val == 'zero':
            g2_marks[key] = {'code': code, 'date': date, 'back': back, 'pattern': pat,
                             'status': 'nosale', 'note': '검색 결과 0건(판매편 없음)'}
        elif val is None:
            raise SystemExit('G2 금~월 미측정 칸이 있습니다: %s' % (key,))
        else:
            g2_deals[key] = {'date': date, 'back': back, 'pattern': pat, 'price': val[0],
                             'airline': val[1], 'via': not val[2].startswith('직항'),
                             'note': val[2]}

    h2_marks_by_key = {(m['code'], m['date'], m['pattern']): m for m in h2_marks}

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']

    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    sources_before = json.dumps(master.get('sources'), ensure_ascii=False)
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    bw_before = json.dumps({k: v for k, v in fl['bookingWindow'].items()
                            if k not in ('note', 'chinaNew8End')},
                           ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    target = set(CN8) | set(PH4)
    other_codes = set(r['code'] for r in fl['routes']) - target
    before_other = json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                              ensure_ascii=False, sort_keys=True)
    before_within = {}
    for r in fl['routes']:
        if r['code'] in target:
            for d in r['deals']:
                before_within[(r['code'], d['date'], d['pattern'])] = json.dumps(
                    d, ensure_ascii=False, sort_keys=True)
    before_marks = {(n['code'], n['date'], n['pattern']): json.dumps(n, ensure_ascii=False,
                                                                    sort_keys=True)
                    for n in fl['noSale']}

    added, dup = merge(master, {'H2': h2_deals, 'PH': ph_deals, 'G2': g2_deals},
                       {'H2': h2_marks_by_key, 'PH': {}, 'G2': g2_marks})
    by_add = collections.Counter(a[0] for a in added)
    if by_add['H2'] != 840 + 16:
        raise SystemExit('중국 7~11월 신규 %d칸 (기대 856칸 — 값 465 + 표시 391)' % by_add['H2'])
    if by_add['PH'] != 420:
        raise SystemExit('필리핀 신규 %d칸 (기대 420칸)' % by_add['PH'])
    if by_add['G2'] != 84:
        raise SystemExit('G2 신규 %d칸 (기대 84칸)' % by_add['G2'])
    if dup:
        raise SystemExit('중복 칸이 있습니다: %s' % dup[:5])

    counts, by_month = recount(fl)
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = counts['total']
    notes_update(fl)

    # ── 보존·건수 검증 ──
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
    if json.dumps({k: v for k, v in fl['bookingWindow'].items()
                   if k not in ('note', 'chinaNew8End')},
                  ensure_ascii=False, sort_keys=True) != bw_before:
        raise SystemExit('예약창 정보가 바뀌었습니다(주석 외).')
    if fl['bookingWindow'].get('chinaNew8End') != '2027-10-13':
        raise SystemExit('중국 8노선 예약창(2027-10-13)이 기록되지 않았습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다.')
    after_within = {}
    for r in fl['routes']:
        if r['code'] in target:
            for d in r['deals']:
                after_within[(r['code'], d['date'], d['pattern'])] = json.dumps(
                    d, ensure_ascii=False, sort_keys=True)
    lost = [k for k, v in before_within.items() if after_within.get(k) != v]
    if lost:
        raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % lost[:5])
    for k, v in before_marks.items():
        now = next((n for n in fl['noSale']
                    if (n['code'], n['date'], n['pattern']) == k), None)
        if now is None or json.dumps(now, ensure_ascii=False, sort_keys=True) != v:
            raise SystemExit('기존 판매편 0건 기록이 바뀌었습니다: %s' % (k,))
    if json.dumps(fl['noSale'][:len(before_marks)], ensure_ascii=False) != nosale_before:
        raise SystemExit('기존 noSale 순서/내용이 바뀌었습니다.')
    for r in fl['routes']:
        keys = [(d['date'], d['pattern']) for d in r['deals']]
        if len(keys) != len(set(keys)):
            raise SystemExit('%s (출발일·패턴) 중복' % r['code'])
    stat = collections.Counter(n.get('status') or 'nosale' for n in fl['noSale'])
    if stat['nosale'] != EXPECT_NOSALE_TOTAL:
        raise SystemExit('판매편 0건 %d칸 (기대 %d칸)' % (stat['nosale'], EXPECT_NOSALE_TOTAL))
    if stat['nofare'] != EXPECT_NOFARE_TOTAL:
        raise SystemExit('요금 미공개 %d칸 (기대 %d칸)' % (stat['nofare'], EXPECT_NOFARE_TOTAL))
    if stat['unopened'] != EXPECT_UNOPENED_TOTAL:
        raise SystemExit('미오픈 %d칸 (기대 %d칸)' % (stat['unopened'], EXPECT_UNOPENED_TOTAL))
    if len(fl['noSale']) != EXPECT_NOSALE_TOTAL + EXPECT_NOFARE_TOTAL + EXPECT_UNOPENED_TOTAL:
        raise SystemExit('noSale 목록 %d줄 (기대 %d줄)' % (
            len(fl['noSale']), EXPECT_NOSALE_TOTAL + EXPECT_NOFARE_TOTAL + EXPECT_UNOPENED_TOTAL))

    print('신규 %d칸 (중국 7~11월 %d · 필리핀 %d · G2 금~월 %d)'
          % (len(added), by_add['H2'], by_add['PH'], by_add['G2']))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'], counts['daytrip']))
    print('월별: %s' % counts['byMonth'])
    print('월별 증가: %s' % {m: counts['byMonth'].get(m, 0) - before_by_month.get(m, 0)
                            for m in counts['byMonth']})
    print('표시: 판매편 0건 %d · 요금 미공개 %d · 미오픈 %d'
          % (stat['nosale'], stat['nofare'], stat['unopened']))
    print('노선별 건수: %s' % ', '.join(
        '%s %d' % (r['code'], len(r['deals'])) for r in fl['routes'] if r['code'] in target))
    print('holiday %d · daytrip %d' % (counts['holiday'], counts['daytrip']))

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        json.dump(fl, open(os.path.join(ROOT, 'data', '.h2_dry_flights.json'), 'w'),
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
