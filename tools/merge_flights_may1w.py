#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선의 2027년 5월 1주차(4/29~5/3) 5패턴 120칸** 실측을
`data/master_db.json` 의 `flights` 에 병합한다.

원본 1개(`data-sources/flights-2027-05/부산출발-항공특가-2027년5월-1주차.md`,
2026-11-19 06:20~07:50 KST 실측):
  노선별 절 `### 부산–상하이 (PVG)` 아래 불릿 5줄씩 —
  `- 4/30(금) → 5/2(일) · ①금~일·2박 · **603,500원** · 중국남방항공 · 경유(선양 2시간30분, 총7시간20분, 11:20-17:40) · 직항 최저 637,000원(대한항공 1시간55분 08:35-09:30), 9석 미만 [출처: …]`

규칙:
  · 120칸 모두 `routes[].deals` 로 넣는다(`price` = 원문 금액 그대로, 반올림 없음).
    빈칸·추정 없음 — 원문이 120칸 전부 값을 적었다(미오픈·판매편 0건·요금 미공개 0칸).
  · `via` 는 그 칸 **최저가 편성**이 직항인지(`false`) 경유인지(`true`)로 적는다(원문 120칸 전부 명시).
  · `alt` 는 원문의 '직항 최저가'가 숫자로 있고 최저가보다 비쌀 때만 넣는다(21칸).
  · 이미 있는 칸은 건드리지 않는다(중복이면 멈춘다). 기존 24개 노선의 4/29~5/3 칸은 0칸이다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 패턴 정의 · 다른 노선·기존 딜·`noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-04 `notes` 의
    '4월 5주차는 아직 수신 전' 문장을 이번 실측 문장으로 바꾸며, 2027-05 `notes` 앞머리에
    5/1 출발 24칸 문장을 넣는다(plain text — `**` 금지).
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_may1w.py --dry-run
    python3 tools/merge_flights_may1w.py
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
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-2027-05'))
FILE = '부산출발-항공특가-2027년5월-1주차.md'

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
          'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'NGO': '나고야',
        'OKA': '오키나와', 'GUM': '괌', 'PVG': '상하이', 'BJS': '베이징', 'NKG': '난징',
        'HGH': '항저우', 'TAO': '칭다오', 'TPE': '타이베이', 'HKG': '홍콩', 'KHH': '가오슝',
        'RMQ': '타이중', 'MFM': '마카오', 'BKK': '방콕', 'CNX': '치앙마이', 'DAD': '다낭',
        'CXR': '나트랑', 'HAN': '하노이', 'SGN': '호찌민', 'SIN': '싱가포르', 'DPS': '발리'}
MONTH_APR, MONTH_MAY = '2027-04', '2027-05'
WEEK_START = '2027-04-29'
WEEK_END = '2027-05-03'
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver')

# 원본이 스스로 적은 값 — 파싱이 조용히 빠뜨리거나 바꾸지 않았는지 대조한다
EXPECT_CELLS = 120
EXPECT_OVERALL = (325800, 1067400)      # 호찌민 4/29~5/2 목~일 / 오키나와 4/30~5/3 금~월
EXPECT_AVG = {'금~일': 627483, '토~월': 676333, '목~일': 556558,
              '금~월': 661925, '목~월': 582871}
EXPECT_DIRECT = 44                       # 직항이 최저가인 칸 (경유 76)
EXPECT_ALTS = 21                         # '직항 최저'를 함께 적은 칸
# 노선 → (그 주 안에서의 최저, 최고) — 원문 가격 매트릭스 표와 같은 값
EXPECT_ROUTE = {
    'PVG': (403400, 610200), 'FUK': (412100, 655200), 'KIX': (611500, 813200),
    'TYO': (637900, 809800), 'BKK': (514600, 619300), 'DAD': (327300, 529200),
    'CXR': (375500, 566100), 'TPE': (401200, 446800), 'HKG': (520600, 597900),
    'MFM': (685700, 797200), 'NKG': (600900, 685700), 'SGN': (325800, 385100),
    'SIN': (548800, 655200), 'GUM': (682600, 867400), 'NGO': (745700, 982300),
    'OKA': (534500, 1067400), 'HGH': (670400, 771200), 'TAO': (501900, 543500),
    'HAN': (385900, 561500), 'CNX': (699000, 957500), 'DPS': (505300, 799300),
    'KHH': (709700, 841500), 'RMQ': (745100, 978700), 'BJS': (450600, 527600),
}
# 원문이 콕 집어 적은 칸(전체 최저·최고, 패턴별 최저)
EXPECT_LOW = {('SGN', '2027-04-29', '목~일'): 325800,
              ('DAD', '2027-04-30', '금~일'): 327300,
              ('OKA', '2027-04-30', '금~월'): 1067400,
              ('PVG', '2027-05-01', '토~월'): 403400,
              ('TAO', '2027-04-29', '목~월'): 501900}
# 최저가가 경유일 때 함께 적은 직항 최저가
EXPECT_ALT = {('PVG', '2027-04-30', '금~일'): 637000,
              ('SIN', '2027-04-29', '목~일'): 744600,
              ('TAO', '2027-04-29', '목~월'): 853600,
              ('BJS', '2027-04-29', '목~일'): 511100,
              ('CXR', '2027-04-29', '목~일'): None}   # 이 칸은 직항이 최저가
EXPECT_TOTAL = 8000 + EXPECT_CELLS
EXPECT_BY_MONTH = {MONTH_APR: 941 + 96, MONTH_MAY: 663 + 24}
EXPECT_DAYTRIP = 318
# 원문이 '9석 미만'으로 적은 칸은 15칸이다(원문 요약 문장은 8개 노선 13칸이라 적었으나
# 같은 문장이 나열한 칸은 9개 노선 15칸 — 값은 나열된 15칸을 그대로 따랐다).
EXPECT_SEATS = 15


def read():
    return open(os.path.join(SRC, FILE), encoding='utf-8').read()


def won(text):
    m = re.search(r'([\d,]+)', text)
    return int(m.group(1).replace(',', '')) if m else None


def dur(text):
    """'4시간55분' / '1시간 10분' → '4시간 55분'."""
    m = re.match(r'^(?:\ucd9c발\s*)?(\d+)\s*시간\s*(\d+)?\s*분?$', text.strip())
    if not m:
        return text.strip()
    return '%d시간 %s분' % (int(m.group(1)), m.group(2) or '0')


def short_dur(text):
    """'66분' → '1시간 06분' 없이 그대로 두되, 분이 0이면 'N시간'."""
    m = re.match(r'^(\d+)시간\s*(\d*)분?$', text.strip())
    if not m:
        return text.strip()
    mins = m.group(2)
    if mins in ('', '0'):
        return '%s시간' % m.group(1)
    return '%s시간 %02d분' % (m.group(1), int(mins))


def parse():
    text = read()
    cells, code, bad = {}, None, []
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r'^###\s*부산[–-]\S+\s*\(([A-Z]{3})\)\s*$', line)
        if m:
            code = m.group(1)
            if code not in ROUTES:
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        m = re.match(r'^-\s*(?P<m1>\d+)/(?P<d1>\d+)\((?P<w1>[월화수목금토일])\)\s*→\s*'
                     r'(?P<m2>\d+)/(?P<d2>\d+)\((?P<w2>[월화수목금토일])\)\s*·\s*(?P<rest>.+)$',
                     line)
        if not m:
            continue
        if code is None:
            raise SystemExit('노선 없이 표 행: %s' % line[:60])
        rest = re.sub(r'\s*\[출처:[^\]]*\]', '', m.group('rest')).strip()
        parts = [p.strip() for p in rest.split(' · ')]
        pm = re.match(r'^[①②③④⑤]\s*(?P<pat>[월화수목금토일]~[월화수목금토일])'
                      r'\s*·\s*(?P<n>\d)박$', parts[0])
        if not pm:
            bad.append(line[:70])
            continue
        pat, nights = pm.group('pat'), int(pm.group('n'))
        if PAT_NIGHTS[pat] != nights:
            raise SystemExit('%s 박수 %d (패턴 %d박)' % (pat, nights, PAT_NIGHTS[pat]))
        date = datetime.date(2027, int(m.group('m1')), int(m.group('d1')))
        back = datetime.date(2027, int(m.group('m2')), int(m.group('d2')))
        if WD[m.group('w1')] != (date.weekday() + 1) % 7:
            raise SystemExit('%s 요일 불일치 (%s)' % (date, m.group('w1')))
        if WD[m.group('w2')] != (back.weekday() + 1) % 7:
            raise SystemExit('%s 귀국 요일 불일치' % back)
        if (back - date).days != nights:
            raise SystemExit('%s~%s 가 %d박이 아닙니다' % (date, back, nights))
        price = won(parts[1])
        airline = parts[2]
        leg, remarks = parts[3], parts[4:]
        note, alt, via = build_note(leg, remarks)
        key = (code, date.isoformat(), pat)
        if key in cells:
            raise SystemExit('중복 칸 %s' % (key,))
        cells[key] = dict(code=code, date=date.isoformat(), pattern=pat, price=price,
                          airline=airline, via=via, alt=alt, note=note)
    if bad:
        raise SystemExit('불릿 형식을 읽지 못한 줄: %s' % bad[:3])
    return cells


def build_note(leg, remarks):
    """편성 문장 + 비고 → (note, alt, via)."""
    alt = None
    if leg.startswith('직항'):
        via = False
        dm = re.search(r'^(직항)\s*(\d+시간\s*\d*분?)', leg)
        note = '직항' + (' ' + short_dur(dm.group(2)) if dm else '')
        tm = re.search(r'\(([^)]*)\)\s*$', leg)
        if tm:
            note += '(%s)' % tm.group(1).replace('→', '-')
    elif leg.startswith('경유'):
        via = True
        m = re.match(r'^경유\s*(?P<n>\d?)\s*회?\s*\((?P<inner>[^)]*)\)\s*$', leg)
        if not m:
            raise SystemExit('경유 문장을 읽지 못했습니다: %r' % leg)
        inner = [x.strip() for x in m.group('inner').split(',')]
        stop = inner[0]
        sm = re.match(r'^(?P<hub>[^\s]+)(?:\s+(?P<lay>\d+시간\s*\d*분?))?$', stop)
        hub = sm.group('hub') if sm else stop
        cnt = m.group('n') or '1'
        note = '경유 %s회(%s)' % (cnt, hub)
        if sm and sm.group('lay'):
            note += ' · 환승 %s' % short_dur(sm.group('lay'))
        tot = next((x for x in inner if x.startswith('총')), None)
        if tot:
            note += ' · 총 %s' % short_dur(re.sub(r'^총\s*', '', tot))
        times = next((x for x in inner if re.match(r'^\d\d:\d\d', x)), None)
        if times:
            note += ' (%s)' % times.replace('→', '-')
    else:
        raise SystemExit('편성 문장이 직항/경유로 시작하지 않습니다: %r' % leg)

    for r in remarks:
        r = r.strip()
        if r.startswith('직항 최저'):
            alt = won(re.search(r'직항 최저\s*([\d,]+)', r).group(0))
            am = re.search(r'\(([^)\s]+)', r)
            note += ' · 직항 최저 %s원%s' % (
                format(alt, ','), '(%s)' % am.group(1) if am else '')
        elif '직항 운임 미표시' in r:
            note += ' · 직항 가격 미표시'
        elif '직항 없음' in r:
            note += ' · 직항편 없음'
        if '9석 미만' in r:
            note += ' · 잔여 9석 미만'
    return note, alt, via


def check(cells):
    if len(cells) != EXPECT_CELLS:
        raise SystemExit('%d칸 (기대 %d칸)' % (len(cells), EXPECT_CELLS))
    if {k[0] for k in cells} != set(ROUTES):
        raise SystemExit('노선이 24개가 아닙니다: %s' % sorted({k[0] for k in cells}))
    want = set()
    for code in ROUTES:
        for pat in PAT_NIGHTS:
            d = (datetime.date.fromisoformat(WEEK_START) +
                 datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
            want.add((code, d, pat))
    if set(cells) != want:
        raise SystemExit('칸 집합이 24노선 × 5패턴과 다릅니다: %s'
                         % sorted(set(cells) ^ want)[:6])
    ps = [c['price'] for c in cells.values()]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('최저·최고 %s (원문 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    for pat, want_avg in EXPECT_AVG.items():
        v = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if len(v) != 24:
            raise SystemExit('%s %d칸 (기대 24칸)' % (pat, len(v)))
        if abs(sum(v) / len(v) - want_avg) > 1:
            raise SystemExit('%s 평균 %.1f (원문 %d)' % (pat, sum(v) / len(v), want_avg))
    direct = sum(1 for c in cells.values() if c['via'] is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (원문 %d)' % (direct, EXPECT_DIRECT))
    if sum(1 for c in cells.values() if c['alt']) != EXPECT_ALTS:
        raise SystemExit('직항 최저를 함께 적은 칸 %d (원문 %d)'
                         % (sum(1 for c in cells.values() if c['alt']), EXPECT_ALTS))
    seats = sum(1 for c in cells.values() if '잔여 9석 미만' in c['note'])
    if seats != EXPECT_SEATS:
        raise SystemExit('9석 미만 칸 %d (원문 나열 %d)' % (seats, EXPECT_SEATS))
    for code, (lo, hi) in EXPECT_ROUTE.items():
        v = [c['price'] for k, c in cells.items() if k[0] == code]
        if len(v) != 5:
            raise SystemExit('%s %d칸 (기대 5칸)' % (code, len(v)))
        if (min(v), max(v)) != (lo, hi):
            raise SystemExit('%s 최저·최고 %s (원문 %s)' % (code, (min(v), max(v)), (lo, hi)))
    # 원문 '노선별 최저가 순위' 목록의 24줄도 맞는지
    rank = re.findall(r'^- ([\d,]+)원 · ([^(]+)\(([A-Z]{3})\) · ([^·]+)·', read(), re.M)
    got_rank = {code: int(p.replace(',', '')) for p, _, code, _ in rank}
    if got_rank:
        want_rank = {code: min(c['price'] for k, c in cells.items() if k[0] == code)
                     for code in ROUTES}
        if got_rank != want_rank:
            raise SystemExit('노선별 최저 순위 표와 다릅니다: %s'
                             % {k: (got_rank.get(k), want_rank.get(k))
                                for k in ROUTES if got_rank.get(k) != want_rank.get(k)})
    for key, price in EXPECT_LOW.items():
        if cells[key]['price'] != price:
            raise SystemExit('%s %s (원문 %d)' % (key, cells[key]['price'], price))
    for key, alt in EXPECT_ALT.items():
        if cells[key]['alt'] != alt:
            raise SystemExit('%s 직항 최저 %s (원문 %s)' % (key, cells[key]['alt'], alt))
    for k, c in cells.items():
        if c['alt'] is not None and c['alt'] <= c['price']:
            raise SystemExit('%s 직항 최저가가 최저가 이하입니다: %s <= %s'
                             % (k, c['alt'], c['price']))
        if c['price'] <= 0:
            raise SystemExit('%s 가격이 양의 정수가 아닙니다' % (k,))
        if not c['airline'] or not c['note']:
            raise SystemExit('%s 항공사/note 비어 있음' % (k,))
        if '**' in c['note'] or '[' in c['note'] or '출처' in c['note']:
            raise SystemExit('%s note 에 마크업이 있습니다: %r' % (k, c['note']))
        for word in BANNED:
            if word in c['note'] or word in c['airline']:
                raise SystemExit('%s 값에 제3자 사이트 이름(%s)이 있습니다' % (k, word))
    return cells


def recount(fl):
    all_deals = [d for r in fl['routes'] for d in r['deals']]
    by_month = collections.Counter(d['date'][:7] for d in all_deals)
    fl['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month.get(k, 0) for k in fl['months']},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals
                       if d['pattern'].split('~')[0] == d['pattern'].split('~')[-1]),
    }
    return fl['counts']


def _viaword(d):
    return '직항' if d.get('via') is False else ('경유' if d.get('via') else '편성 미확인')


def span(d):
    return '%d/%d~%d/%d' % (int(d['date'][5:7]), int(d['date'][8:10]),
                            int(d['back'][5:7]), int(d['back'][8:10]))


def week_note(rows, label):
    lo = min(rows, key=lambda d: d['price'])
    hi = max(rows, key=lambda d: d['price'])
    agg = collections.defaultdict(list)
    for d in rows:
        agg[d['pattern']].append(d['price'])
    avg = ' < '.join('{} {}원'.format(p, format(round(sum(v) / len(v)), ','))
                     for p, v in sorted(agg.items(), key=lambda kv: sum(kv[1]) / len(kv[1])))
    direct = sum(1 for d in rows if d.get('via') is False)
    unk = sum(1 for d in rows if d.get('via') is None)
    ties_lo = sum(1 for d in rows if d['price'] == lo['price'])
    ties_hi = sum(1 for d in rows if d['price'] == hi['price'])
    return (label + ' 최저는 ' + CITY[lo['code']] + ' ' + span(lo) + ' ' + lo['pattern'] + ' '
            + format(lo['price'], ',') + '원(' + (lo['airline'] or '항공사 미확인') + ' '
            + _viaword(lo) + (' · 같은 금액 %d칸' % ties_lo if ties_lo > 1 else '')
            + ')이고, 최고는 ' + CITY[hi['code']] + ' ' + span(hi) + ' ' + hi['pattern'] + ' '
            + format(hi['price'], ',') + '원(' + (hi['airline'] or '항공사 미확인') + ' '
            + _viaword(hi) + (' · 같은 금액 %d칸' % ties_hi if ties_hi > 1 else '')
            + ')입니다. 직항이 최저가인 칸 ' + str(direct) + ' · 경유 '
            + str(len(rows) - direct - unk)
            + (' · 편성 미확인 ' + str(unk) if unk else '') + '칸이고, 패턴 평균은 '
            + avg + ' 순입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 5월 1주(4/29~5/3) 120칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ④ 항공 기존 24개 노선 2027년 5월 1주차(4/29~5/3) '
        '5패턴 120칸 완결 — 최저 호찌민 4/29~5/2 목~일 325,800원(직항), '
        '직항이 최저가인 칸 44, 총 8,000→8,120건'))
    args = ap.parse_args(argv)

    cells = check(parse())
    print('파싱 %d칸 — 최저 %s · 최고 %s · 직항이 최저인 칸 %d · 경유 %d · 직항 최저 병기 %d'
          % (len(cells), format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ','),
             sum(1 for c in cells.values() if c['via'] is False),
             sum(1 for c in cells.values() if c['via'] is True),
             sum(1 for c in cells.values() if c['alt'])))
    for k in sorted(cells)[:3]:
        print('  예:', k, cells[k])

    master = json.load(open(MASTER, encoding='utf-8'))
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다' % code)

    before = {k: json.dumps(master.get(k), ensure_ascii=False, sort_keys=True)
              for k in ('hotels', 'accor', 'sources', 'window', 'built', 'voucherExpiry',
                        'schema', 'version')}
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    notes_before = {k: v for k, v in fl['notes'].items() if k not in (MONTH_APR, MONTH_MAY)}
    before_deals = {c: json.dumps(routes[c]['deals'], ensure_ascii=False) for c in ROUTES}
    before_daytrip = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_apr = fl['counts']['byMonth'][MONTH_APR]
    before_may = fl['counts']['byMonth'][MONTH_MAY]
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])

    # 기존 24개 노선의 이 주 칸은 0칸이어야 한다(다른 노선의 같은 주 칸은 그대로 둔다)
    clash = [(c, d['date'], d['pattern']) for c in ROUTES for d in routes[c]['deals']
             if WEEK_START <= d['date'] <= WEEK_END]
    if clash:
        raise SystemExit('기존 24개 노선에 이 주 칸이 이미 있습니다: %s' % clash[:4])

    added = []
    for (code, date, pat), v in sorted(cells.items()):
        deal = collections.OrderedDict()
        deal['date'] = date
        deal['back'] = (datetime.date.fromisoformat(date) +
                        datetime.timedelta(days=PAT_NIGHTS[pat])).isoformat()
        deal['pattern'] = pat
        deal['price'] = v['price']
        deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt']:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        routes[code]['deals'].append(json.loads(json.dumps(deal)))
        added.append((code, date, pat))
        for word in BANNED:
            if word in json.dumps(deal, ensure_ascii=False):
                raise SystemExit('%s %s 값에 제3자 사이트 이름이 있습니다' % (code, date))
    if len(added) != EXPECT_CELLS:
        raise SystemExit('신규 %d칸 (기대 %d칸)' % (len(added), EXPECT_CELLS))
    for code in ROUTES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))

    counts = recount(fl)
    if counts['total'] != EXPECT_TOTAL:
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], EXPECT_TOTAL))
    for m, want in EXPECT_BY_MONTH.items():
        if counts['byMonth'][m] != want:
            raise SystemExit('%s %d건 (기대 %d건)' % (m, counts['byMonth'][m], want))
    if counts['daytrip'] != EXPECT_DAYTRIP:
        raise SystemExit('당일치기 %d건 (기대 %d건)' % (counts['daytrip'], EXPECT_DAYTRIP))
    if counts['holiday'] != 185:
        raise SystemExit('연휴 칸 %d건 (기대 185)' % counts['holiday'])

    rows = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if WEEK_START <= d['date'] <= WEEK_END]
    if len(rows) != EXPECT_CELLS:
        raise SystemExit('이 주 칸 %d칸 (기대 %d칸)' % (len(rows), EXPECT_CELLS))

    # ── 2027-04 notes: '4월 5주차는 아직 수신 전' 문장을 이번 실측 문장으로 바꾼다
    old_sent = ('4월 5주차(4/29~5/3)는 아직 수신 전이라 24개 노선의 그 주 칸은 빈칸(—)입니다.')
    if fl['notes'][MONTH_APR].count(old_sent) != 1:
        raise SystemExit('2027-04 notes 의 4월 5주차 문장이 예상과 다릅니다: %r'
                         % fl['notes'][MONTH_APR][-160:])
    jp = [d['price'] for d in rows if d['code'] in ('FUK', 'KIX', 'TYO', 'NGO', 'OKA')]
    vn = [d['price'] for d in rows if d['code'] in ('SGN', 'DAD', 'CXR', 'HAN')]
    week_sent = ('4월 5주차(4/29~5/3)도 24개 노선 5패턴 120칸을 전부 실측했습니다(빈칸·추정 0칸). '
                 + week_note(rows, '이 주(4/29~5/3)')
                 + ' 앱의 주차 선택은 목요일 기준이라 이 주가 4월 5주(4/29~5/5)로 표시되고, '
                   '5/1 토요일 출발은 5월 달력에도 들어옵니다. '
                   '이 주는 일본 골든위크(4/29 쇼와의 날·5/3 헌법기념일)와 겹쳐 일본 5개 노선이 '
                 + '%s~%s원이고, 베트남 4개 노선은 %s~%s원입니다. 9석 미만으로 표시된 칸은 '
                 % (format(min(jp), ','), format(max(jp), ','),
                    format(min(vn), ','), format(max(vn), ','))
                 + '%d칸이니 예약을 미루면 다시 확인해야 합니다.'
                 % sum(1 for d in rows if '잔여 9석 미만' in d.get('note', '')))
    fl['notes'][MONTH_APR] = fl['notes'][MONTH_APR].replace(old_sent, week_sent)

    # ── 2027-05 notes: 5/1 출발 24칸이 이 달에 들어오는 것을 앞머리에 적는다
    if not fl['notes'][MONTH_MAY].startswith('기존 24개 노선은 2027년 5월 3~4주차'):
        raise SystemExit('2027-05 notes 의 첫 문장이 예상과 다릅니다: %r'
                         % fl['notes'][MONTH_MAY][:40])
    may1 = sorted((d for d in rows if d['date'] == '2027-05-01'), key=lambda d: d['price'])
    fl['notes'][MONTH_MAY] = (
        '2027년 5월 1주차(4/29~5/3) 24개 노선 5패턴 120칸도 전부 실측했습니다 — 이 주는 앱에서 '
        '4월 5주(4/29~5/5)로 표시되고, 그중 5/1 토~월 24칸이 이 달 달력에 들어옵니다(최저 '
        + ' · '.join('%s %s원' % (CITY[d['code']], format(d['price'], ','))
                    for d in may1[:3]) + '). '
        + fl['notes'][MONTH_MAY])

    # ── 보존 확인
    for key, old in before.items():
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != old:
            raise SystemExit('%s 가 바뀌었습니다' % key)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('noSale 이 바뀌었습니다')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다')
    for code in ROUTES:
        old = json.loads(before_deals[code])
        cur = routes[code]['deals']
        if len(cur) != len(old) + 5:
            raise SystemExit('%s 딜 %d건 (기존 %d + 5)' % (code, len(cur), len(old)))
        have = {(d['date'], d['pattern']): d for d in cur}
        if len(have) != len(cur):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for o in old:
            got = have.get((o['date'], o['pattern']))
            if json.dumps(got, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(o, ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 기존 딜이 바뀌었습니다: %s %s' % (code, o['date'], o['pattern']))
        keys = [(d['date'], WD[d['pattern'][0]]) for d in cur]
        if keys != sorted(keys):
            raise SystemExit('%s 딜 정렬이 깨졌습니다' % code)
        if json.dumps(routes[code]['daytrip'], ensure_ascii=False) != before_daytrip[code]:
            raise SystemExit('%s 당일치기 요약이 바뀌었습니다' % code)
    if {k: v for k, v in fl['notes'].items() if k not in (MONTH_APR, MONTH_MAY)} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')
    for word in BANNED:
        if word in json.dumps(fl['notes'], ensure_ascii=False):
            raise SystemExit('notes 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    master['extended'] = (before_extended + ' / ' + args.note).strip(' /')

    print('신규 %d칸 · 총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (len(added), before_total, counts['total'],
             counts['total'] - counts['daytrip'], counts['daytrip']))
    print('2027-04 %d → %d건 · 2027-05 %d → %d건'
          % (before_apr, counts['byMonth'][MONTH_APR], before_may, counts['byMonth'][MONTH_MAY]))
    print('notes[2027-04] 새 문장:', week_sent[:300])
    print('notes[2027-05] 앞부분:', fl['notes'][MONTH_MAY][:300])

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        return 0
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('저장: %s' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
