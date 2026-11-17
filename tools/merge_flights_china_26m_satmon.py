#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 중국 4노선(연길·장가계·구이린·황산) **2027년 2~6월 토~월(2박) 21주 35칸**
(값 29 + 황산 판매편 0건 6) 조사 md → `data/master_db.json` 의 `flights` 병합.

앞선 두 병합(`merge_flights_china_pus4_26m_full.py`)이 넣은 금~일 84칸 + 연길 6/5 토~월 1칸은
그대로 두고, 이번 조사에서 새로 찬 **34칸**(값 28 + 황산 판매편 0건 6)만 더한다.
(연길 6/5 토~월은 이미 있으므로 중복 1칸)

사용법 (저장소 루트에서):
    python3 tools/merge_flights_china_26m_satmon.py \
        ../data-sources/flights-china-new8/부산출발-중국4노선-연길장가계구이린황산-2_6월-금일.md --dry-run

읽는 곳(부록 5절 '앱 병합용 줄' + 2절 노선별 실측표):
  · 값   — `- 2027-02-13(토) · 토~월(2박) · PUS–YNJ · 537,200원 · Air Busan · 직항(무경유, 총2h 40m)`
  · 0건  — `- 2027-02-06(토) · 토~월(2박) · PUS–TXN · 판매편 없음(0건)`
  · 미조회 — `- 2027-05-15(토) · 토~월(2박) · PUS–YNJ · 미측정`  → 넣지 않고 gaps 로만 센다

규칙:
  · 값(가격·날짜·소요시간)은 원문 그대로. 항공사·경유지 이름만 앱 표기(한국어)로 옮긴다.
  · 조회했으나 **판매편이 없던** 칸은 가격이 아니라 `flights.noSale` 로 넣는다(추정 금지).
  · 부록 줄과 2절 표를 **(노선·출발일·패턴) 단위 420칸 전수**로 대조한다 — 한 칸이라도 다르면 멈춘다.
    노선별 최저·최고가도 1절 요약표와 대조한다.
  · 이미 있는 칸은 **중복으로 넣지 않는다**(기존 건 보존). 기존 딜의 금액이 하나라도 달라지면 멈춘다.
  · 호텔 538곳 · 아코르 · 다른 28개 노선은 **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)와 2027년 2~5월 `notes`(커버리지 문구)를 다시 쓴다.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
ROUTE_ORDER = ('YNJ', 'DYG', 'KWL', 'TXN')
ROUTE_CITY = {'YNJ': '연길/옌지', 'DYG': '장가계', 'KWL': '구이린', 'TXN': '황산'}
# 원문이 말하는 칸 수 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT = {
    # 원문 전체(금~일 84칸 + 토~월 35칸 = 2~6월 21주 5패턴 420칸 중 조회분) — 전수 대조용
    'values': {'YNJ': 36, 'DYG': 28, 'KWL': 28, 'TXN': 8},
    'nosale': {'YNJ': 0, 'DYG': 0, 'KWL': 0, 'TXN': 19},
    'gaps': 301,
    'cells': 119,
    # 1절 요약표의 노선별 최저·최고(원)
    'minmax': {'YNJ': (455700, 927100), 'DYG': (691100, 904100),
               'KWL': (535200, 863700), 'TXN': (845000, 1035900)},
}
# 이번 병합 대상 — 토~월(2박)만. 금~일 84칸은 앞선 병합분과 금액이 같아야 한다(갱신 0건)
EXPECT_SAT_VALUES = {'YNJ': 15, 'DYG': 7, 'KWL': 7, 'TXN': 0}
EXPECT_SAT_NOSALE = {'YNJ': 0, 'DYG': 0, 'KWL': 0, 'TXN': 6}
EXPECT_FRI_VALUES = {'YNJ': 21, 'DYG': 21, 'KWL': 21, 'TXN': 8}   # 이미 들어간 금~일(값)
EXPECT_FRI_NOSALE = {'YNJ': 0, 'DYG': 0, 'KWL': 0, 'TXN': 13}    # 이미 들어간 금~일(0건)
# 21주(토요일 기준) — 2027년 2/6 ~ 6/26
WEEKS_SAT = ('2027-02-06', '2027-02-13', '2027-02-20', '2027-02-27',
             '2027-03-06', '2027-03-13', '2027-03-20', '2027-03-27',
             '2027-04-03', '2027-04-10', '2027-04-17', '2027-04-24',
             '2027-05-01', '2027-05-08', '2027-05-15', '2027-05-22', '2027-05-29',
             '2027-06-05', '2027-06-12', '2027-06-19', '2027-06-26')
# 노선별 토~월 실측 출발일(값) — 원문 표의 `—`(미조회)와 같은 빈칸
EXPECT_SAT = {
    'YNJ': set(WEEKS_SAT) - {'2027-05-15', '2027-05-22', '2027-05-29',
                             '2027-06-12', '2027-06-19', '2027-06-26'},
    'DYG': set(WEEKS_SAT[:7]),
    'KWL': set(WEEKS_SAT[:7]),
    'TXN': set(),   # 값 0칸 — 조회한 6주는 모두 판매편 0건
}
# 황산 토~월 판매편 0건 — 2/6 ~ 3/13 6주(원문 4절 '조회한 주 전부 0건'), 3/20 이후는 미조회
TXN_NOSALE = ('2027-02-06', '2027-02-13', '2027-02-20', '2027-02-27',
              '2027-03-06', '2027-03-13')
# 앞선 병합에서 이미 들어간 2~6월 값(금~일 84칸 + 연길 6/5 토~월 1칸) — 이번 신규는 34칸
PREV_26M = {'YNJ': 22, 'DYG': 21, 'KWL': 21, 'TXN': 8}
NEW_VALUES = 28
NEW_NOSALE = 6
EXPECT_PREV_NOSALE = 46

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
]
AIRPORT_KO = [('Jeju City', '제주'), ('Hong Kong', '홍콩'), ('Seoul', '서울'),
              ('Beijing', '베이징'), ('Shanghai', '상하이'), ('Jeju', '제주'),
              ('Nanjing', '난징'), ('Guangzhou', '광저우')]

LINE_F2 = re.compile(r'^- (\d{4}-\d{2}-\d{2})\([월화수목금토일]\) · ([월화수목금토일]~[월화수목금토일])'
                     r'(?:\((\d)박\))? · PUS–([A-Z]{3}) · (.+)$')
TABLE_HEAD = re.compile(r'^### .*\(([A-Z]{3})\)$')
TABLE_ROW = re.compile(r'^\| (\d{2})/(\d{2}) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$')
TAB_COLS = {'목~일': 0, '금~일': 1, '토~월': 2, '금~월': 3, '목~월': 4}


# ---------------------------------------------------------------- 표기 변환
def timespan(text):
    """'13h 20m' → '13시간 20분', '2h' → '2시간' (원문 값은 그대로)."""
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


def norm_desc(desc):
    """원문 편구성 → {via, note}."""
    d = (desc or '').strip()
    m = re.fullmatch(r'경유\((.*)\)', d)
    if m:
        parts = [timespan(city_words(p.strip())) for p in m.group(1).split(',')]
        parts = [p for p in parts if p and p != '총']
        return {'via': True, 'note': '경유' + ('(%s)' % ', '.join(parts) if parts else '')}
    if d.startswith('경유'):
        return {'via': True, 'note': '경유'}
    if d.startswith('직항'):
        # '직항(무경유, 총2h 40m)' → '직항 2시간 40분'
        inner = re.search(r'\((.*)\)', d)
        if inner:
            body = [c.strip() for c in inner.group(1).split(',') if c.strip() != '무경유']
            body = [re.sub(r'^총\s*', '', timespan(city_words(c))) for c in body]
            if body:
                return {'via': False, 'note': '직항 ' + ', '.join(body)}
        return {'via': False, 'note': '직항'}
    return {'via': None, 'note': d or '직항/경유 미확인'}


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    nights = (WD[b] - WD[a]) % 7 or 7
    return (start + datetime.timedelta(days=nights)).isoformat()


# ---------------------------------------------------------------- 파싱
def parse_appendix(text):
    """부록 줄 → (values, nosale, gaps). values=(code,date,pattern)→deal 딕셔너리."""
    values, nosale, gaps = {}, {}, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('- 20'):
            continue
        m = LINE_F2.match(line)
        if not m:
            raise SystemExit('부록 줄 형식이 예상과 다릅니다: %s' % line)
        date, pattern, nights, code, rest = m.groups()
        body = rest.strip()
        if body in ('미측정', '가격 미표시') or body.startswith('미측정'):
            gaps.append((code, date, pattern))
            continue
        if nights is not None:
            n = (WD[pattern[-1]] - WD[pattern[0]]) % 7 or 7
            if int(nights) != n:
                raise SystemExit('%s %s 박수 표기(%s박)가 패턴(%s)과 다릅니다' % (code, date, nights, pattern))
        if body == '판매편 없음(0건)':
            nosale[(code, date, pattern)] = {
                'code': code, 'date': date, 'back': back_date(date, pattern),
                'pattern': pattern, 'note': '검색 결과 0건(판매편 없음)'}
            continue
        fields = [f.strip() for f in body.split(' · ')]
        pm = re.fullmatch(r'([\d,]+)원', fields[0])
        if not pm:
            raise SystemExit('부록 금액을 읽지 못했습니다: %s' % line)
        info = norm_desc(' · '.join(fields[2:])) if len(fields) > 2 else norm_desc('')
        deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern,
                'price': int(pm.group(1).replace(',', ''))}
        airline = airline_ko(fields[1]) if len(fields) > 1 else ''
        if airline:
            deal['airline'] = airline
        else:
            deal['src'] = '가격표'
        for k in ('via', 'note'):
            if info.get(k) is not None:
                deal[k] = info[k]
        values[(code, date, pattern)] = deal
    return values, nosale, gaps


def parse_tables(text):
    """2절 노선별 실측표 → (code,date,pattern) → 가격 | 'NOSALE' | '—'.

    `537,200 **직항**` 처럼 강조 표기가 붙은 칸은 금액만 쓰고, 직항 표시는 따로 모아
    부록의 `via:false` 와 대조한다(원문 두 곳이 서로 다른 말을 하면 멈춘다).
    """
    out, code, straight = {}, None, set()
    for raw in text.splitlines():
        line = raw.strip()
        m = TABLE_HEAD.match(line)
        if m:
            code = m.group(1)
            continue
        if code is None:
            continue
        m = TABLE_ROW.match(line)
        if not m:
            continue
        mm, dd, *cells = m.groups()
        if len(cells) != 5:
            raise SystemExit('표 열이 5개가 아닙니다: %s' % line)
        thu = datetime.date(2027, int(mm), int(dd))
        if thu.isoweekday() != 4:
            raise SystemExit('표의 주 구분이 목요일이 아닙니다: %s' % line)
        for label, idx in TAB_COLS.items():
            cell = cells[idx].strip()
            date = (thu + datetime.timedelta(days=(WD[label[0]] - 4) % 7)).isoformat()
            if '**직항**' in cell:
                straight.add((code, date, label))
                cell = cell.replace('**직항**', '').strip()
            if cell == '—':
                out[(code, date, label)] = '—'
            elif cell == '0건':
                out[(code, date, label)] = 'NOSALE'
            elif re.fullmatch(r'[\d,]+', cell):
                out[(code, date, label)] = int(cell.replace(',', ''))
            else:
                raise SystemExit('표 칸 값을 읽지 못했습니다: %s' % line)
    return out, straight


# ---------------------------------------------------------------- 병합
def merge(master, values, nosale):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTE_ORDER:
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
    fl['notes']['2027-02'] = ('중국 8개 노선의 2027년 2월 2박을 실측했습니다 — 선양·다롄·광저우·샤먼은 '
                              '금~일·토~월 4주씩, 연길·장가계·구이린·황산은 금~일 4주와 토~월 4주'
                              '(황산은 2/6~2/27 토~월 판매편이 없어 0건)입니다. 3·4박과 다른 노선은 미조회(—)입니다.')
    fl['notes']['2027-03'] = ('중국 8개 노선의 2027년 3월 2박을 실측했습니다 — 선양·다롄·광저우·샤먼은 '
                              '금~일·토~월 4주씩, 연길·장가계·구이린은 금~일 4주와 토~월 3주(3/6~3/20), '
                              '황산은 금~일 3주와 토~월 2주(3/6·3/13, 모두 0건)입니다. '
                              '3/27 토~월과 3·4박, 다른 노선은 미조회(—)입니다.')
    fl['notes']['2027-04'] = ('선양·다롄·광저우·샤먼 4개 노선의 금~일 5주·토~월 4주를, 연길은 금~일·토~월 '
                              '4주씩을, 장가계·구이린·황산은 금~일(2박)을 실측했습니다'
                              '(황산은 4/2~4/30 판매편이 없어 0건). 3·4박과 다른 노선은 미조회(—)입니다.')
    fl['notes']['2027-05'] = ('중국 8개 노선의 2027년 5월 2박을 실측했습니다 — 선양·다롄·광저우·샤먼은 '
                              '금~일 4주·토~월 5주(5/29 포함), 연길은 금~일 5주와 토~월 2주(5/1·5/8), '
                              '장가계·구이린·황산은 금~일 5주입니다(황산은 5/7~5/28 판매편이 없어 0건). '
                              '3·4박과 다른 노선은 미조회(—)입니다.')
    fl['notes']['2027-06'] = ('중국 8개 노선의 2027년 6월 2박을 실측했습니다 — 선양·다롄·광저우·샤먼은 '
                              '금~일·토~월 4주씩(32칸), 연길·장가계·구이린·황산은 금~일 4주와 연길 6/5 토~월 1칸입니다'
                              '(황산은 6월 네 주 모두 판매편이 없어 0건). 3·4박과 다른 노선은 미조회(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='중국 4노선 2027년 2~6월 토~월 35칸 md → master_db.json flights 병합')
    ap.add_argument('md')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    values, nosale, gaps = parse_appendix(text)
    table, straight = parse_tables(text)

    # 1) 원문 칸 수와 파싱 결과
    per = {c: {'values': 0, 'nosale': 0} for c in ROUTE_ORDER}
    for code, _, _ in values:
        per[code]['values'] += 1
    for code, _, _ in nosale:
        per[code]['nosale'] += 1
    bad = []
    for code in ROUTE_ORDER:
        want = {'values': EXPECT['values'][code], 'nosale': EXPECT['nosale'][code]}
        if per[code] != want:
            bad.append('%s 값 %d/0건 %d (기대 %d/%d)' % (code, per[code]['values'], per[code]['nosale'],
                                                     want['values'], want['nosale']))
    pats = {p for (_, _, p) in list(values) + list(nosale)}
    if pats != {'금~일', '토~월'}:
        bad.append('금~일·토~월 이외 패턴이 섞였습니다: %s' % sorted(pats))
    if len(values) != sum(EXPECT['values'].values()):
        bad.append('값 %d칸 (기대 %d칸)' % (len(values), sum(EXPECT['values'].values())))
    if len(values) + len(nosale) != EXPECT['cells']:
        bad.append('값+0건 %d칸 (기대 %d칸)' % (len(values) + len(nosale), EXPECT['cells']))
    if len(gaps) != EXPECT['gaps']:
        bad.append('미측정 줄 %d개 (기대 %d개)' % (len(gaps), EXPECT['gaps']))
    for code in ROUTE_ORDER:
        prices = [d['price'] for (c, _, _), d in values.items() if c == code]
        got = (min(prices), max(prices)) if prices else None
        if got != EXPECT['minmax'][code]:
            bad.append('%s 최저·최고 %s (요약표 기대 %s)' % (code, got, EXPECT['minmax'][code]))
    # 이번 병합 대상(토~월)만 따로 센다 — 금~일 84칸은 앞선 병합분과 금액이 같아야 한다(갱신 0건)
    sat_values = {k: v for k, v in values.items() if k[2] == '토~월'}
    sat_nosale = {k: v for k, v in nosale.items() if k[2] == '토~월'}
    fri_values = {k: v for k, v in values.items() if k[2] == '금~일'}
    fri_nosale = {k: v for k, v in nosale.items() if k[2] == '금~일'}
    for name, group, want in (('토~월 값', sat_values, EXPECT_SAT_VALUES),
                              ('토~월 0건', sat_nosale, EXPECT_SAT_NOSALE),
                              ('금~일 값', fri_values, EXPECT_FRI_VALUES),
                              ('금~일 0건', fri_nosale, EXPECT_FRI_NOSALE)):
        got = {c: sum(1 for k in group if k[0] == c) for c in ROUTE_ORDER}
        if got != want:
            bad.append('%s 노선별 %s (기대 %s)' % (name, got, want))
    # 노선별 토~월 실측 출발일 집합 — 미조회 주가 원문 표와 같은지
    for code in ROUTE_ORDER:
        got = {dt for (c, dt, _) in sat_values if c == code}
        if got != EXPECT_SAT[code]:
            bad.append('%s 토~월 값 %d칸 (기대 %d칸) 차이: %s'
                       % (code, len(got), len(EXPECT_SAT[code]), sorted(got ^ EXPECT_SAT[code])))
    if {d for (c, d, _) in sat_nosale if c == 'TXN'} != set(TXN_NOSALE):
        bad.append('황산 토~월 0건 날짜가 2/6~3/13 6주와 다릅니다')
    if {c for (c, _, _) in sat_nosale} - {'TXN'}:
        bad.append('황산 밖 노선에 토~월 판매편 0건 칸이 있습니다')

    # 2) 부록 ↔ 2절 표 전수 대조 (4노선 × 21주 × 5패턴 = 420칸)
    mismatch = []
    if len(table) != 420:
        bad.append('표 칸 %d개 (기대 420개)' % len(table))
    for (code, date, pat), got in sorted(table.items()):
        key = (code, date, pat)
        if key in values:
            if got != values[key]['price']:
                mismatch.append('%s 부록 %s / 표 %s' % (key, values[key]['price'], got))
        elif key in nosale:
            if got != 'NOSALE':
                mismatch.append('%s 0건인데 표는 %s' % (code + ' ' + date, got))
        elif got != '—':
            mismatch.append('%s 부록 미측정인데 표는 %s' % (key, got))
    got_straight = {k for k, d in values.items() if d.get('via') is False}
    if straight != got_straight:
        mismatch.append('직항 표시가 표 %s / 부록 %s 로 다릅니다' % (sorted(straight), sorted(got_straight)))
    extra = [k for k in list(values) + list(nosale) if k not in table]
    if extra:
        mismatch.append('표에 없는 부록 칸: %s' % extra[:5])
    if mismatch:
        bad.append('부록·표 불일치 %d건: %s' % (len(mismatch), mismatch[:6]))
    print('  원문 전체: 값 %d칸 + 판매편 0건 %d칸 = %d칸 · 미측정 %d칸 · 표 대조 %d칸'
          % (len(values), len(nosale), len(values) + len(nosale), len(gaps), len(table)))
    print('  노선별(전체): %s' % ', '.join('%s %d/%d' % (c, per[c]['values'], per[c]['nosale'])
                                       for c in ROUTE_ORDER))
    print('  이번 병합(토~월): 값 %d칸 + 0건 %d칸 = %d칸 · 노선별 %s'
          % (len(sat_values), len(sat_nosale), len(sat_values) + len(sat_nosale),
             {c: sum(1 for k in sat_values if k[0] == c) for c in ROUTE_ORDER}))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    before_total = fl['counts']['total']
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTE_ORDER],
                              ensure_ascii=False, sort_keys=True)
    before_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False, sort_keys=True)
                     for r in fl['routes'] if r['code'] in ROUTE_ORDER for d in r['deals']}
    before_nosale = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_nosale_total = len(fl['noSale'])
    before_by_month = dict(fl['counts']['byMonth'])
    before_26m = sum(1 for r in fl['routes'] if r['code'] in ROUTE_ORDER
                     for d in r['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30')
    before_26m_other = [(r['code'], d['date'], d['pattern']) for r in fl['routes'] if r['code'] in ROUTE_ORDER
                        for d in r['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30'
                        and d['pattern'] != '금~일']

    # 금~일 84칸은 앞선 병합분 그대로여야 한다 — 한 칸이라도 없거나 금액이 다르면 멈춘다
    routes_now = {r['code']: r for r in fl['routes']}
    fri_bad = []
    for (code, date, pat), deal in sorted(fri_values.items()):
        have = next((d for d in routes_now[code]['deals'] if d['date'] == date and d['pattern'] == pat), None)
        if have is None:
            fri_bad.append('%s %s %s 없음' % (code, date, pat))
        elif have.get('price') != deal['price']:
            fri_bad.append('%s %s %s 기존 %s / 원문 %s' % (code, date, pat, have.get('price'), deal['price']))
    known_ns = {(n['code'], n['date'], n['pattern']) for n in fl['noSale']}
    fri_bad += ['%s %s %s 0건 기록 없음' % k for k in sorted(fri_nosale) if k not in known_ns]
    if fri_bad:
        raise SystemExit('금~일 84칸이 기존 병합분과 다릅니다: %s' % fri_bad[:6])

    added, dup, new_nosale = merge(master, sat_values, sat_nosale)
    notes_update(fl)

    # 3) 이번 조사가 정확히 34칸(값 28 + 0건 6)만 더했는지 — 중복은 연길 6/5 토~월 1칸뿐
    if len(dup) != 1 or dup[0] != ('YNJ', '2027-06-05', '토~월'):
        raise SystemExit('기존 칸과 겹친 것이 연길 6/5 토~월 1칸이 아닙니다: %s' % dup)
    if len(added) != NEW_VALUES:
        raise SystemExit('신규 값 %d칸 (기대 %d칸): %s' % (len(added), NEW_VALUES, added))
    if len(new_nosale) != NEW_NOSALE:
        raise SystemExit('신규 0건 %d칸 (기대 %d칸): %s' % (len(new_nosale), NEW_NOSALE, new_nosale))
    if before_26m != sum(PREV_26M.values()):
        raise SystemExit('기존 2~6월 값 칸 수가 %d칸입니다 (기대 %d칸)' % (before_26m, sum(PREV_26M.values())))
    if before_26m_other != [('YNJ', '2027-06-05', '토~월')]:
        raise SystemExit('기존 2~6월 금~일 밖 칸이 연길 6/5 토~월 1칸이 아닙니다: %s' % before_26m_other)
    if before_nosale_total != EXPECT_PREV_NOSALE:
        raise SystemExit('기존 판매편 0건 기록이 %d건입니다 (기대 %d건)' % (before_nosale_total, EXPECT_PREV_NOSALE))

    # 4) 보존 검증 — 호텔·아코르·다른 노선·기존 딜은 한 바이트도 바뀌면 안 된다
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTE_ORDER],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 항공 노선 데이터가 바뀌었습니다.')
    after_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False, sort_keys=True)
                    for r in fl['routes'] if r['code'] in ROUTE_ORDER for d in r['deals']}
    lost = [k for k in before_within if before_within[k] != after_within.get(k)]
    if lost:
        raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % lost[:5])
    old_ns = {tuple(sorted(n.items())) for n in json.loads(before_nosale)}
    if not old_ns <= {tuple(sorted(n.items())) for n in fl['noSale']}:
        raise SystemExit('기존 판매편 0건 기록이 바뀌었습니다.')
    for r in fl['routes']:
        if r['code'] in ROUTE_ORDER:
            keys = [(d['date'], d['pattern']) for d in r['deals']]
            if len(keys) != len(set(keys)):
                raise SystemExit('%s (출발일·패턴) 중복' % r['code'])
    # 월별 증가가 이번 조사분(2월 12 · 3월 10 · 4월 4 · 5월 2)과 같은지
    expect_add = {'2027-02': 12, '2027-03': 10, '2027-04': 4, '2027-05': 2}
    for m, n in expect_add.items():
        got = fl['counts']['byMonth'].get(m, 0) - before_by_month.get(m, 0)
        if got != n:
            raise SystemExit('%s 증가 %d칸 (기대 %d칸)' % (m, got, n))

    print('신규 딜 %d건(중복 %d건) · 신규 0건 %d건 → noSale %d건'
          % (len(added), len(dup), len(new_nosale), len(fl['noSale'])))
    print('총 %d건 → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, fl['counts']['total'],
        fl['counts']['total'] - fl['counts']['daytrip'], fl['counts']['daytrip']))
    print('월별: %s' % fl['counts']['byMonth'])
    print('4노선 건수: %s' % ', '.join(
        '%s %d' % (r['code'], len(r['deals'])) for r in fl['routes'] if r['code'] in ROUTE_ORDER))
    for a in added:
        print('  + %s %s %s %s원' % a)

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
