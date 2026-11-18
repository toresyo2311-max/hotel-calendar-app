#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선의 2027년 4월 1~3주차(4/1~5 · 4/8~12 · 4/15~19)
5패턴 360칸** 실측을 `data/master_db.json` 의 `flights` 에 병합한다.

원본: `data-sources/flights-2027-04/`
  · `부산출발-항공특가-2027년4월-1주차.md` — 4/1~5, 120줄
  · `부산출발-항공특가-2027년4월-2주차.md` — 4/8~12, 120줄
  · `부산출발-항공특가-2027년4월-3주차.md` — 4/15~19, 120줄

값의 원본은 각 md 의 '날짜·패턴별 최저가' 절 120줄(노선 24 × 5패턴)이다. 병합 전에 원문의 요약과
전수 대조한다:
  · '한눈에'의 주차 최저·최고·직항/경유 칸 수·패턴별 평균
  · '노선별 최저가 순위' 24줄의 금액과 파싱 결과의 노선별 최소값
  · 노선 24개 × 5패턴 = 120칸, 출발일이 그 주 목(4/1·4/8·4/15)에서 패턴만큼 이동한 날인지

규칙:
  · 360칸 모두 `routes[].deals` 로 넣는다(값은 원문 그대로, 반올림 없음). 빈칸·추정 없음.
  · 이미 있는 칸은 건드리지 않는다(중복·금액 충돌이면 멈춘다).
  · 호텔 538곳 · 아코르 SNU 43줄 · 출처 목록 · 패턴 정의 · 다른 노선·기존 딜·`noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)와 2027-04 `notes`(plain text — `**` 금지)를
    실제 데이터에서 다시 계산해 쓴다.
  · 4월 4주차(4/22~26)는 아직 미수신이라 손대지 않는다(빈칸 유지).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_apr13w.py --dry-run
    python3 tools/merge_flights_apr13w.py --note "..."
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-2027-04'))
WEEK_FILES = (
    ('부산출발-항공특가-2027년4월-1주차.md', '2027-04-01'),
    ('부산출발-항공특가-2027년4월-2주차.md', '2027-04-08'),
    ('부산출발-항공특가-2027년4월-3주차.md', '2027-04-15'),
)

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
WK = ('금~일', '토~월', '목~일', '금~월', '목~월')
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
          'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'TPE': '타이베이', 'HKG': '홍콩',
        'MFM': '마카오', 'PVG': '상하이', 'BKK': '방콕', 'DAD': '다낭', 'CXR': '나트랑',
        'NKG': '난징', 'SGN': '호찌민', 'SIN': '싱가포르', 'GUM': '괌', 'NGO': '나고야',
        'OKA': '오키나와', 'HGH': '항저우', 'TAO': '칭다오', 'HAN': '하노이', 'CNX': '치앙마이',
        'DPS': '발리', 'KHH': '가오슝', 'RMQ': '타이중', 'BJS': '베이징'}
MONTH = '2027-04'
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')

# 원문 '한눈에'가 말하는 주차별 값 — 파싱 결과와 대조한다
EXPECT = {
    '2027-04-01': {'min': 299100, 'max': 2133000, 'direct': 47, 'via': 73,
                   'avg': {'금~월': 524404, '목~일': 531117, '금~일': 534188,
                           '토~월': 538488, '목~월': 578008}},
    '2027-04-08': {'min': 299100, 'max': 864500, 'direct': 49, 'via': 71,
                   'avg': {'금~월': 486233, '토~월': 490192, '금~일': 491042,
                           '목~월': 499771, '목~일': 500958}},
    '2027-04-15': {'min': 299000, 'max': 923000, 'direct': 45, 'via': 75,
                   'avg': {'토~월': 490858, '금~월': 492833, '목~월': 493988,
                           '목~일': 497004, '금~일': 506588}},
}
EXPECT_CELLS = 360
EXPECT_TOTAL = 6599 + 360          # 6,959
EXPECT_BY_MONTH_APR = 461 + 360    # 821
EXPECT_DAYTRIP = 318

BUL = re.compile(r'^- (?P<date>\d{4}-\d{2}-\d{2}) · (?P<pat>[월화수목금토일]~[월화수목금토일])'
                 r'·(?P<nights>\d)박 · PUS–(?P<code>[A-Z]{3}) · (?P<price>[\d,]+)원 · '
                 r'(?P<air>.+?) · (?P<rest>(?:직항|경유).*)$')
RANK = re.compile(r'^- (?P<price>[\d,]+)원 · .+?\((?P<code>[A-Z]{3})\) · .*?'
                  r'(?P<pat>[월화수목금토일]~[월화수목금토일])\s*·?\s*(?P<nights>\d)박 · ')
VIA = re.compile(r'^경유( 2회)?\((?P<inner>[^()]*)\)')
VIA2 = re.compile(r'^(경유2회)\((?P<inner>[^()]*)\)')
DIRECT = re.compile(r'^직항 (?P<dur>[^()]+)\((?P<time>[^()]*)\)')
BARE_TIME = re.compile(r'^\s*(\d{2}:\d{2}-\d{2}:\d{2}(?:[+-]\d)?)(,\s*[A-Z]{3})?')
ALT = re.compile(r'\(직항 최저 (?P<price>[\d,]+)원?(?:\((?P<detail>[^()]*)\))?\)')
ALTX = re.compile(r'\(직항 최저 (?P<price>[\d,]+)원?\)')
NOSALE_TAIL = ('(직항 운임 미표시)', '(직항 운임 없음)', '(직항 운임 미표시(직항편 우선 \'-\'))',
               '(직항 운임 미표시, 잔여 고가 운임만 남음)')
MACAU = '(부산–마카오 직항 없음)'
ALT2 = re.compile(r'— 대안 (?P<price>[\d,]+)원(?:\((?P<detail>[^()]*)\))?')
SEATS = re.compile(r'\((\d+)석 미만\)$')
DUR = re.compile(r'(\d+)시간(\d+)분')


def norm_dur(text):
    """'1시간55분' → '1시간 55분', '총9시간50분' → '총 9시간 50분' (앱 표기와 맞춤)."""
    text = DUR.sub(r'\1시간 \2분', text)
    text = re.sub(r'총\s*(\d+)시간', r'총 \1시간', text)
    text = re.sub(r'(\d+)시간\s*(\d+)분', r'\1시간 \2분', text)
    text = re.sub(r'\s+,', ',', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def won(text):
    return int(text.replace(',', ''))


def split_note(rest):
    """원문의 '직항 …' / '경유…' 표기 + 꼬리 주석을 앱 표기 note·via·alt 로 바꾼다."""
    rest = rest.strip()
    alt = None
    tails = []
    # 꼬리 주석은 문자열 뒤에서부터 떼어 낸다
    for _ in range(4):
        m = ALT.search(rest)
        if m and m.end() == len(rest):
            alt = (won(m.group('price')), m.group('detail'))
            rest = rest[:m.start()].strip()
            continue
        m = ALT2.search(rest)
        if m and m.end() == len(rest):
            detail = m.group('detail')
            tails.insert(0, '대안 %s원%s' % (format(won(m.group('price')), ','),
                                            '(%s)' % norm_dur(detail) if detail else ''))
            rest = rest[:m.start()].strip()
            continue
        hit = [t for t in NOSALE_TAIL if rest.endswith(t)]
        if hit:
            if '잔여 고가 운임' in hit[0]:
                tails.insert(0, '잔여 고가 운임만 남음')
            rest = rest[:-len(hit[0])].strip()
            continue
        m = SEATS.search(rest)
        if m and m.end() == len(rest):
            tails.insert(0, '잔여 %s석 미만' % m.group(1))
            rest = rest[:m.start()].strip()
            continue
        if rest.endswith(MACAU):
            tails.insert(0, '직항편 없음')
            rest = rest[:-len(MACAU)].strip()
            continue
        break
    if rest.startswith('직항'):
        m = DIRECT.match(rest)
        if not m:
            raise ValueError('직항 표기 해석 실패: %r' % rest)
        if rest[m.end():].strip():
            raise ValueError('직항 꼬리 해석 실패: %r' % rest)
        note = '직항 %s(%s)' % (norm_dur(m.group('dur')), m.group('time').strip())
        via = False
    else:
        m = VIA2.match(rest) or VIA.match(rest)
        if not m:
            raise ValueError('경유 표기 해석 실패: %r' % rest)
        inner = m.group('inner')
        head = '경유2회' if (m.group(0).startswith('경유2회') or (m.lastindex and m.group(1))) \
            else '경유'
        rest2 = rest[m.end():].strip()
        mt = BARE_TIME.match(rest2)
        if mt:
            inner = inner + ', ' + mt.group(1) + (mt.group(2) or '')
            rest2 = rest2[mt.end():].strip()
        if rest2:
            raise ValueError('경유 꼬리 해석 실패: %r (rest2=%r)' % (rest, rest2))
        note = '%s(%s)' % (head, norm_dur(inner))
        via = True
    if alt is not None and alt[1]:
        tails.append('직항 최저 %s원(%s)' % (format(alt[0], ','), norm_dur(alt[1])))
    elif alt is not None:
        tails.append('직항 최저 %s원' % format(alt[0], ','))
    if tails:
        note += ' · ' + ' · '.join(tails)
    return {'via': via, 'alt': alt[0] if alt else None, 'note': note}


def parse_week(path, thu):
    """한 주차 md → {(code, date, pattern): {...}} + 원문 '한눈에' 확인용 통계."""
    text = open(path, encoding='utf-8').read().split('\n')
    cells = {}
    for line in text:
        m = BUL.match(line.rstrip())
        if not m:
            continue
        date, pat, nights, code = m.group('date'), m.group('pat'), int(m.group('nights')), m.group('code')
        if code not in ROUTES:
            raise SystemExit('%s 알 수 없는 노선 %s' % (os.path.basename(path), code))
        if pat not in PAT_NIGHTS:
            raise SystemExit('%s 주말형 밖 패턴 %s' % (os.path.basename(path), pat))
        if PAT_NIGHTS[pat] != nights:
            raise SystemExit('%s %s 박수 %d (패턴은 %d박)' % (os.path.basename(path), pat, nights,
                                                          PAT_NIGHTS[pat]))
        want = (datetime.date.fromisoformat(thu) +
                datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
        if date != want:
            raise SystemExit('%s %s/%s 출발일 %s (기대 %s)' % (os.path.basename(path), code, pat,
                                                            date, want))
        info = split_note(m.group('rest'))
        price = won(m.group('price'))
        if info['alt'] is not None and info['alt'] < price:
            raise SystemExit('%s %s %s %s 직항 최저가가 최저값보다 쌉니다(%s < %s)'
                             % (os.path.basename(path), code, date, pat, info['alt'], price))
        key = (code, date, pat)
        if key in cells:
            raise SystemExit('%s 중복 칸 %s' % (os.path.basename(path), key))
        cells[key] = {'date': date, 'pattern': pat, 'price': price,
                      'airline': m.group('air').strip(),
                      'back': (datetime.date.fromisoformat(date) +
                               datetime.timedelta(days=nights)).isoformat(),
                      'via': info['via'], 'note': info['note'], 'alt': info['alt']}
    ranks = {}
    for line in text:
        m = RANK.match(line.rstrip())
        if m:
            ranks[m.group('code')] = (won(m.group('price')), m.group('pat'))
    return cells, ranks


def check_week(name, thu, cells, ranks):
    want = EXPECT[thu]
    if len(cells) != 120:
        raise SystemExit('%s %d칸 (기대 120칸)' % (name, len(cells)))
    if {k[0] for k in cells} != set(ROUTES):
        raise SystemExit('%s 노선이 24개가 아닙니다: %s' % (name, sorted({k[0] for k in cells})))
    per_pat = collections.Counter(k[2] for k in cells)
    if set(per_pat) != set(WK) or any(v != 24 for v in per_pat.values()):
        raise SystemExit('%s 패턴별 칸 수 %s (기대 5패턴 × 24칸)' % (name, dict(per_pat)))
    prices = [c['price'] for c in cells.values()]
    if min(prices) != want['min'] or max(prices) != want['max']:
        raise SystemExit('%s 최저·최고 %s (원문 %s)'
                         % (name, (min(prices), max(prices)), (want['min'], want['max'])))
    direct = sum(1 for c in cells.values() if not c['via'])
    if direct != want['direct'] or len(prices) - direct != want['via']:
        raise SystemExit('%s 직항 %d·경유 %d (원문 %d·%d)'
                         % (name, direct, len(prices) - direct, want['direct'], want['via']))
    for pat, avg in want['avg'].items():
        ps = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if round(sum(ps) / len(ps)) != avg:
            raise SystemExit('%s %s 평균 %d (원문 %d)' % (name, pat, round(sum(ps) / len(ps)), avg))
    if len(ranks) != 24:
        raise SystemExit('%s 노선별 최저가 순위 %d줄 (기대 24줄)' % (name, len(ranks)))
    per_route = collections.defaultdict(list)
    for (code, _d, _p), c in cells.items():
        per_route[code].append((c['price'], c['pattern']))
    for code, (price, pat) in ranks.items():
        lo = min(pr for pr, _ in per_route[code])
        if price != lo:
            raise SystemExit('%s %s 순위 금액 %d (파싱 최저 %d)' % (name, code, price, lo))
        pats_at_min = {pt for pr, pt in per_route[code] if pr == lo}
        if pat not in pats_at_min:
            raise SystemExit('%s %s 순위 패턴 %s (파싱 최저 패턴 %s)'
                             % (name, code, pat, sorted(pats_at_min)))


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


def week_stats(fl):
    routes = {r['code']: r for r in fl['routes']}
    out = {}
    for start in ('2027-04-01', '2027-04-08', '2027-04-15'):
        end = (datetime.date.fromisoformat(start) + datetime.timedelta(days=4)).isoformat()
        rows = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
                for d in r['deals'] if start <= d['date'] <= end and d['pattern'] in WK]
        out[start] = rows
    return routes, out


def mmdd(date):
    return '%d/%d' % (int(date[5:7]), int(date[8:10]))


def note_text(fl):
    routes, weeks = week_stats(fl)
    head = ('기존 24개 노선은 2027년 4월 1~3주차(4/1~5 · 4/8~12 · 4/15~19) 5패턴 360칸을 '
            '전부 실측했습니다(빈칸·추정 0칸).')
    lo_txt, hi_txt, avg_txt, dir_txt = [], [], [], []
    for start in ('2027-04-01', '2027-04-08', '2027-04-15'):
        rows = weeks[start]
        lo = min(rows, key=lambda d: d['price'])
        hi = max(rows, key=lambda d: d['price'])
        lo_txt.append('%s주차 %s %s~%s %s %s원(%s %s)' % (
            {'2027-04-01': '1', '2027-04-08': '2', '2027-04-15': '3'}[start],
            CITY[lo['code']], mmdd(lo['date']), mmdd(lo['back']), lo['pattern'],
            format(lo['price'], ','), lo.get('airline', ''), '직항' if lo.get('via') is False else '경유'))
        hi_txt.append('%s주차 %s %s~%s %s %s원(%s)' % (
            {'2027-04-01': '1', '2027-04-08': '2', '2027-04-15': '3'}[start],
            CITY[hi['code']], mmdd(hi['date']), mmdd(hi['back']), hi['pattern'],
            format(hi['price'], ','), hi.get('airline', '')))
        agg = collections.defaultdict(list)
        for d in rows:
            agg[d['pattern']].append(d['price'])
        avg_txt.append('%s주차 ' % {'2027-04-01': '1', '2027-04-08': '2', '2027-04-15': '3'}[start] +
                       ' < '.join('%s %s원' % (p, format(round(sum(v) / len(v)), ','))
                                  for p, v in sorted(agg.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))))
        dir_txt.append('%s주차 %d칸' % (
            {'2027-04-01': '1', '2027-04-08': '2', '2027-04-15': '3'}[start],
            sum(1 for d in rows if d.get('via') is False)))
    return (head + ' 주차별 최저는 ' + ', '.join(lo_txt) + '이고, 최고는 ' + ', '.join(hi_txt) +
            '입니다. 직항이 최저가인 칸은 ' + ' · '.join(dir_txt) + '이고, 패턴 평균은 ' +
            ', '.join(avg_txt) + ' 순입니다. 4월 4주차(4/22~26)는 아직 조회하지 않아 빈칸(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 4월 1~3주차 360칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    cells = {}
    for name, thu in WEEK_FILES:
        path = os.path.join(SRC, name)
        if not os.path.isfile(path):
            raise SystemExit('원본이 없습니다: %s' % path)
        got, ranks = parse_week(path, thu)
        check_week(name, thu, got, ranks)
        for key, v in got.items():
            if key in cells:
                raise SystemExit('주차 간 중복 칸 %s' % (key,))
            cells[key] = v
        print('%s — %d칸 (직항 %d · 경유 %d) 최저 %s' % (
            name, len(got), sum(1 for c in got.values() if not c['via']),
            sum(1 for c in got.values() if c['via']),
            format(min(c['price'] for c in got.values()), ',')))
    if len(cells) != EXPECT_CELLS:
        raise SystemExit('합계 %d칸 (기대 %d칸)' % (len(cells), EXPECT_CELLS))

    master = json.loads(open(MASTER, encoding='utf-8').read())
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다(신설이 아니라 병합 대상)' % code)

    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    sources_before = json.dumps(master.get('sources'), ensure_ascii=False)
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    other_notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    before_deals = {c: json.dumps(routes[c]['deals'], ensure_ascii=False) for c in ROUTES}
    before_daytrip = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    before_extended = master.get('extended', '')
    other_codes = [r['code'] for r in fl['routes'] if r['code'] not in ROUTES]
    before_other = json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                              ensure_ascii=False, sort_keys=True)

    added = []
    for (code, date, pat), v in sorted(cells.items()):
        have = next((d for d in routes[code]['deals']
                     if d['date'] == date and d['pattern'] == pat), None)
        if have is not None:
            raise SystemExit('이미 있는 칸입니다: %s %s %s (%s)' % (code, date, pat, have.get('price')))
        deal = collections.OrderedDict()
        deal['date'] = date
        deal['back'] = v['back']
        deal['pattern'] = pat
        deal['price'] = v['price']
        deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt']:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        routes[code]['deals'].append(json.loads(json.dumps(deal)))
        added.append((code, date, pat))
    if len(added) != EXPECT_CELLS:
        raise SystemExit('신규 %d칸 (기대 %d칸)' % (len(added), EXPECT_CELLS))
    for code in ROUTES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))

    counts, by_month = recount(fl)
    if counts['total'] != EXPECT_TOTAL:
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], EXPECT_TOTAL))
    if by_month.get(MONTH) != EXPECT_BY_MONTH_APR:
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, by_month.get(MONTH), EXPECT_BY_MONTH_APR))
    if counts['daytrip'] != EXPECT_DAYTRIP:
        raise SystemExit('당일치기 %d건 (기대 %d건)' % (counts['daytrip'], EXPECT_DAYTRIP))
    old = fl['notes'][MONTH]
    fl['notes'][MONTH] = note_text(fl) + ' ' + old

    # 보존 확인
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps(master.get('sources'), ensure_ascii=False) != sources_before:
        raise SystemExit('출처 목록이 바뀌었습니다.')
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다.')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('noSale 순서/내용이 바뀌었습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] in other_codes],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다.')
    for code in ROUTES:
        old = json.loads(before_deals[code])
        cur = routes[code]['deals']
        if len(cur) != len(old) + len(WK) * len(WEEK_FILES):
            raise SystemExit('%s 딜 %d건 (기존 %d + %d 이어야 함)'
                             % (code, len(cur), len(old), len(WK) * len(WEEK_FILES)))
        have = {(d['date'], d['pattern']): d for d in cur}
        if len(have) != len(cur):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for o in old:
            got = have.get((o['date'], o['pattern']))
            if json.dumps(got, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(o, ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 기존 딜이 사라지거나 바뀌었습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
        keys = [(d['date'], WD[d['pattern'][0]]) for d in cur]
        if keys != sorted(keys):
            raise SystemExit('%s 딜 정렬이 깨졌습니다.' % code)
        if json.dumps(routes[code]['daytrip'], ensure_ascii=False) != before_daytrip[code]:
            raise SystemExit('%s 당일치기 요약이 바뀌었습니다.' % code)
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != other_notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다.')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다.')

    print('신규 %d칸' % len(added))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, counts['total'], counts['total'] - counts['daytrip'], counts['daytrip']))
    print('월별 증가: %s' % {m: counts['byMonth'].get(m, 0) - before_by_month.get(m, 0)
                            for m in counts['byMonth']})
    print('2027-04 %d → %d건' % (before_by_month.get(MONTH), counts['byMonth'][MONTH]))
    _, weeks = week_stats(fl)
    for start, rows in weeks.items():
        print('  %s 주 %d칸 최저 %s 최고 %s' % (
            start, len(rows), format(min(d['price'] for d in rows), ','),
            format(max(d['price'] for d in rows), ',')))

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        print('--- notes[2027-04] ---')
        print(fl['notes'][MONTH])
        return 0
    if args.note:
        master['extended'] = (before_extended + ' / ' + args.note).strip(' /')
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('저장: %s' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
