#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선의 2027년 4월 4주차(4/22~26) 5패턴 120칸** 실측을
`data/master_db.json` 의 `flights` 에 병합한다. 이로써 2027년 4월 1~4주차 480/480칸이 완결된다.

원본: `data-sources/flights-2027-04/부산출발-항공특가-2027년4월-4주차.md`
  · `## 5. 날짜·패턴별 최저가 — 24개 노선 120칸 전수` 절 120줄(노선 24 × 5패턴)
    `- 2027-04-23 · ① 금~일·2박 · PUS–PVG · 417,600원 · 중국남방항공 · 경유(선양 2시간30분, 총7시간20분) 11:20-17:40 · 직항 최저 481,600(대한항공 …)`
  · `## 4. 노선별 최저가 순위` 24줄 — 금액·패턴을 파싱 결과의 노선별 최소값과 대조
  · `### 노선별 4주 추이` 24줄 — 4주차 열의 노선별 최저를 대조
  · `## 2` 패턴표(패턴별 최저·최고)와 패턴별 평균표, `## 3` 한눈에(전체 최저·최고·직항/경유 칸 수)

규칙:
  · 120칸 모두 `routes[].deals` 로 넣는다(값은 원문 그대로, 반올림 없음). 빈칸·추정 없음.
  · 이미 있는 칸은 건드리지 않는다(중복이면 멈춘다) — 4월 1~3주차 360칸은 그대로 둔다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 패턴 정의 · 다른 노선·기존 딜·`noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip, 최상위 deals)를 다시 세고, 2027-04 `notes` 의
    '4주차는 미수신' 문장을 실측 결과로 바꾼다(plain text — `**` 금지).
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_apr4w.py --dry-run
    python3 tools/merge_flights_apr4w.py
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
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-2027-04'))
MD = os.path.join(SRC, '부산출발-항공특가-2027년4월-4주차.md')

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
CODE_BY_CITY = {v: k for k, v in CITY.items()}
THU = '2027-04-22'
MONTH = '2027-04'
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '네이버', '구글')

# 원문이 말하는 값 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT_CELLS = 120
EXPECT_MIN = 256200
EXPECT_MAX = 737300
EXPECT_DIRECT = 62
EXPECT_VIA = 58
EXPECT_AVG = {'금~일': 465354, '토~월': 460329, '목~일': 470496, '금~월': 460012, '목~월': 474450}
EXPECT_PAT_RANGE = {'금~일': (265800, 737300), '토~월': (282400, 730300),
                    '목~일': (278900, 732100), '금~월': (256200, 730900),
                    '목~월': (269200, 731300)}
EXPECT_TOTAL = 6973 + EXPECT_CELLS          # 7,093
EXPECT_BY_MONTH_APR = 821 + EXPECT_CELLS    # 941
EXPECT_DAYTRIP = 318

BUL = re.compile(r'^- (?P<date>\d{4}-\d{2}-\d{2}) · [①②③④⑤]? ?(?P<pat>[월화수목금토일]~'
                 r'[월화수목금토일])·(?P<nights>\d)박 · PUS–(?P<code>[A-Z]{3}) · '
                 r'(?P<price>[\d,]+)원 · (?P<air>.+?) · (?P<rest>.+)$')
RANK = re.compile(r'^- (?P<price>[\d,]+)원 · .+?\((?P<code>[A-Z]{3})\) · '
                  r'\d{4}-\d{2}-\d{2}\([월화수목금토일]\) (?P<pat>[월화수목금토일]~'
                  r'[월화수목금토일])·(?P<nights>\d)박 · ')
TRAIL = re.compile(r'^│ (?P<city>.+?)\s*│ (?P<w1>[\d,]+) │ (?P<w2>[\d,]+) │ (?P<w3>[\d,]+) │ '
                   r'(?P<w4>[\d,]+) │')
SRC = re.compile(r'\s*\[출처:[^\]]*\]\s*$')
DUR = re.compile(r'(\d+)시간(\d*)분?')
MAIN_DIRECT = re.compile(r'^직항 (?P<dur>\d+시간(?:\d+분)?) (?P<time>\d{2}:\d{2}-\d{2}:\d{2}(?:\+\d)?)'
                         r'(?: \((?P<extra>[^()]*)\))?$')
MAIN_VIA = re.compile(r'^경유\((?P<inner>[^()]*)\) (?P<time>\d{2}:\d{2}-\d{2}:\d{2}(?:\+\d)?)'
                      r'(?: (?P<extra>\([^()]*\)|[A-Z]{3}(?: [A-Z]\d)?))?$')
ALT = re.compile(r'^직항 최저 ([\d,]+)(?:\((?P<detail>.*)\))?$')


def won(text):
    return int(text.replace(',', ''))


def norm_dur(text):
    text = DUR.sub(lambda m: '%s시간 %s분' % (m.group(1), m.group(2) or '0'), text)
    text = re.sub(r'(\d+)시간 0분', r'\1시간', text)
    text = re.sub(r'총\s*(\d+)시간', r'총 \1시간', text)
    text = re.sub(r'\s*,\s*', ', ', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def parse_main(main):
    """'직항 1시간10분 14:50-16:00' / '경유(홍콩 8시간15분, 총13시간35분) 07:45-20:20' → via·note."""
    m = MAIN_DIRECT.match(main)
    if m:
        extra = (', ' + m.group('extra').strip()) if m.group('extra') else ''
        return False, '직항 %s(%s%s)' % (norm_dur(m.group('dur')), m.group('time'), extra)
    m = MAIN_VIA.match(main)
    if not m:
        raise SystemExit('운항 표기를 읽지 못했습니다: %r' % main)
    inner = norm_dur(m.group('inner'))
    has_layover = bool(re.search(r'[가-힣A-Za-z]+ ?\d+시간', m.group('inner')))
    bits = []
    if not has_layover:
        bits.append(m.group('time'))
    if m.group('extra'):
        bits.append(m.group('extra').strip().strip('()'))
    return True, '경유(%s)' % ', '.join([inner] + [norm_dur(b) for b in bits])


def parse_tails(rest_parts):
    """'직항 최저 481,600(대한항공 1시간55분 08:35-09:30)' 등 꼬리 → (note 꼬리들, alt)."""
    tails, alt = [], None
    for part in rest_parts:
        for seg in [s.strip() for s in part.split(';') if s.strip()]:
            if re.match(r'^검색 \d+건$', seg):
                continue
            m = ALT.match(seg)
            if m:
                price = won(m.group(1))
                detail = m.group('detail')
                if alt is None:
                    alt = price
                tails.append('직항 최저 %s원%s'
                             % (format(price, ','), '(%s)' % norm_dur(detail) if detail else ''))
                continue
            m = re.match(r'^대안 ([\d,]+)(?:\((?P<detail>.*)\))?$', seg)
            if m:
                detail = m.group('detail')
                tails.append('대안 %s원%s' % (format(won(m.group(1)), ','),
                                              '(%s)' % norm_dur(detail) if detail else ''))
                continue
            if seg.startswith('직항 운임 없음') or seg.startswith('직항 없음'):
                extra = re.search(r'\((.*)\)$', seg)
                tails.append('직항편 없음' + ('(%s)' % extra.group(1) if extra else ''))
                continue
            if re.match(r'^\d차 조회 \d+건 → 재조회 성공$', seg):
                tails.append('1차 조회 0건 → 재조회 성공' if seg.startswith('1차')
                             else seg)
                continue
            raise SystemExit('꼬리 표기를 읽지 못했습니다: %r' % seg)
    return tails, alt


def parse(text):
    cells = {}
    for raw in text.splitlines():
        line = SRC.sub('', raw.rstrip())
        m = BUL.match(line)
        if not m:
            continue
        date, pat = m.group('date'), m.group('pat')
        nights, code = int(m.group('nights')), m.group('code')
        if code not in ROUTES:
            raise SystemExit('알 수 없는 노선 %s' % code)
        if pat not in PAT_NIGHTS:
            raise SystemExit('주말형 밖 패턴 %s' % pat)
        if PAT_NIGHTS[pat] != nights:
            raise SystemExit('%s 박수 %d (패턴은 %d박)' % (pat, nights, PAT_NIGHTS[pat]))
        want = (datetime.date.fromisoformat(THU) +
                datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
        if date != want:
            raise SystemExit('%s/%s 출발일 %s (기대 %s)' % (code, pat, date, want))
        parts = [p.strip() for p in m.group('rest').split(' · ')]
        via, note = parse_main(parts[0])
        tails, alt = parse_tails(parts[1:])
        if alt is not None and alt < won(m.group('price')):
            raise SystemExit('%s %s %s 직항 최저가가 최저값보다 쌉니다' % (code, date, pat))
        if via != (alt is None) and alt is not None and not via:
            raise SystemExit('%s %s %s 직항인데 직항 최저가 꼬리가 붙었습니다' % (code, date, pat))
        price = won(m.group('price'))
        key = (code, date, pat)
        if key in cells:
            raise SystemExit('중복 칸 %s' % (key,))
        cells[key] = {'date': date, 'pattern': pat, 'price': price,
                      'airline': m.group('air').strip(),
                      'back': (datetime.date.fromisoformat(date) +
                               datetime.timedelta(days=nights)).isoformat(),
                      'via': via, 'alt': alt,
                      'note': note + (' · ' + ' · '.join(tails) if tails else '')}
    ranks = {}
    for raw in text.splitlines():
        m = RANK.match(raw.strip())
        if m:
            ranks[m.group('code')] = (won(m.group('price')), m.group('pat'))
    trend = {}
    for raw in text.splitlines():
        m = TRAIL.match(raw.strip())
        if m and m.group('city').strip() in CODE_BY_CITY:
            trend[CODE_BY_CITY[m.group('city').strip()]] = won(m.group('w4'))
    return cells, ranks, trend


def check(cells, ranks, trend):
    if len(cells) != EXPECT_CELLS:
        raise SystemExit('%d칸 (기대 %d칸)' % (len(cells), EXPECT_CELLS))
    if {k[0] for k in cells} != set(ROUTES):
        raise SystemExit('노선이 24개가 아닙니다: %s' % sorted({k[0] for k in cells}))
    per_pat = collections.Counter(k[2] for k in cells)
    if set(per_pat) != set(WK) or any(v != 24 for v in per_pat.values()):
        raise SystemExit('패턴별 칸 수 %s' % dict(per_pat))
    prices = [c['price'] for c in cells.values()]
    if (min(prices), max(prices)) != (EXPECT_MIN, EXPECT_MAX):
        raise SystemExit('최저·최고 %s (원문 %s)' % ((min(prices), max(prices)),
                                                 (EXPECT_MIN, EXPECT_MAX)))
    direct = sum(1 for c in cells.values() if not c['via'])
    if (direct, len(prices) - direct) != (EXPECT_DIRECT, EXPECT_VIA):
        raise SystemExit('직항 %d·경유 %d (원문 %d·%d)'
                         % (direct, len(prices) - direct, EXPECT_DIRECT, EXPECT_VIA))
    for pat, want in EXPECT_AVG.items():
        ps = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if abs(sum(ps) / len(ps) - want) > 1:
            raise SystemExit('%s 평균 %.1f (원문 %d)' % (pat, sum(ps) / len(ps), want))
    for pat, (lo, hi) in EXPECT_PAT_RANGE.items():
        ps = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if (min(ps), max(ps)) != (lo, hi):
            raise SystemExit('%s 최저·최고 %s (원문 %s)' % (pat, (min(ps), max(ps)), (lo, hi)))
    if len(ranks) != 24 or len(trend) != 24:
        raise SystemExit('노선별 표가 24줄이 아닙니다(순위 %d · 추이 %d)' % (len(ranks), len(trend)))
    per_route = collections.defaultdict(list)
    for (code, _d, pat), c in cells.items():
        per_route[code].append((c['price'], pat))
    for code, (price, pat) in ranks.items():
        lo = min(p for p, _ in per_route[code])
        if price != lo or pat not in {pt for p, pt in per_route[code] if p == lo}:
            raise SystemExit('%s 순위 %s/%s (파싱 %d/%s)'
                             % (code, price, pat, lo, sorted({pt for p, pt in per_route[code] if p == lo})))
    for code, price in trend.items():
        if price != min(p for p, _ in per_route[code]):
            raise SystemExit('%s 4주 추이 %d (파싱 %d)' % (code, price, min(p for p, _ in per_route[code])))


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


def week_note(rows):
    lo = min(rows, key=lambda d: d['price'])
    hi = max(rows, key=lambda d: d['price'])
    agg = collections.defaultdict(list)
    for d in rows:
        agg[d['pattern']].append(d['price'])
    avg = ' < '.join('{} {}원'.format(p, format(round(sum(v) / len(v)), ','))
                     for p, v in sorted(agg.items(), key=lambda kv: sum(kv[1]) / len(kv[1])))
    direct = sum(1 for d in rows if d.get('via') is False)
    return ('4월 4주차(4/22~26) 5패턴 120칸도 실측해 1~4주차 480칸(100%)이 됐습니다 — 이 주 최저는 '
            '{} {}/{}~{}/{} {} {}원({} {}), 최고는 {} {}/{}~{}/{} {} {}원({})이고, 직항이 최저가인 칸 '
            '{} · 경유 {}칸, 패턴 평균은 {} 순입니다. 4월 5주차(4/29~5/3)는 아직 수신 전이라 24개 '
            '노선의 그 주 칸은 빈칸(—)입니다.'
            .format(CITY[lo['code']], int(lo['date'][5:7]), int(lo['date'][8:10]),
                    int(lo['back'][5:7]), int(lo['back'][8:10]), lo['pattern'],
                    format(lo['price'], ','), lo.get('airline', ''),
                    '직항' if lo.get('via') is False else '경유',
                    CITY[hi['code']], int(hi['date'][5:7]), int(hi['date'][8:10]),
                    int(hi['back'][5:7]), int(hi['back'][8:10]), hi['pattern'],
                    format(hi['price'], ','), hi.get('airline', ''),
                    direct, len(rows) - direct, avg))


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 4월 4주차 120칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-18~19 KST ④ 항공 기존 24개 노선 2027년 4월 4주차(4/22~26) 5패턴 120칸 완결 — '
        '최저 타이베이 4/23~26 금~월 256,200원(타이거항공 직항), 직항 62·경유 58칸, '
        '4월 1~4주차 480/480칸(100%), 총 6,973→7,093건'))
    args = ap.parse_args(argv)

    if not os.path.isfile(MD):
        raise SystemExit('원본이 없습니다: %s' % MD)
    text = open(MD, encoding='utf-8').read()
    cells, ranks, trend = parse(text)
    check(cells, ranks, trend)
    print('파싱 120칸 — 직항 %d · 경유 %d · 최저 %s · 최고 %s'
          % (sum(1 for c in cells.values() if not c['via']),
             sum(1 for c in cells.values() if c['via']),
             format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ',')))

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
    notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    before_deals = {c: json.dumps(routes[c]['deals'], ensure_ascii=False) for c in ROUTES}
    before_daytrip = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_apr = fl['counts']['byMonth'][MONTH]
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])

    added = []
    for (code, date, pat), v in sorted(cells.items()):
        if any(d['date'] == date and d['pattern'] == pat for d in routes[code]['deals']):
            raise SystemExit('이미 있는 칸입니다: %s %s %s' % (code, date, pat))
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
    if counts['byMonth'][MONTH] != EXPECT_BY_MONTH_APR:
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH], EXPECT_BY_MONTH_APR))
    if counts['daytrip'] != EXPECT_DAYTRIP:
        raise SystemExit('당일치기 %d건 (기대 %d건)' % (counts['daytrip'], EXPECT_DAYTRIP))
    if counts['holiday'] != 185:
        raise SystemExit('연휴 칸 %d건 (기대 185)' % counts['holiday'])

    week_rows = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
                 for d in r['deals'] if '2027-04-22' <= d['date'] <= '2027-04-26'
                 and d['pattern'] in WK]
    if len(week_rows) != EXPECT_CELLS:
        raise SystemExit('4주차 칸 %d (기대 %d)' % (len(week_rows), EXPECT_CELLS))
    old_sentence = ('4월 4주차(4/22~26)와 5주차(4/29~5/3)는 아직 조회하지 않아 24개 노선의 '
                    '그 주 칸은 빈칸(—)입니다.')
    if old_sentence not in fl['notes'][MONTH]:
        raise SystemExit('2027-04 notes 에서 4주차 미수신 문장을 찾지 못했습니다')
    fl['notes'][MONTH] = fl['notes'][MONTH].replace(old_sentence, week_note(week_rows))

    # 보존 확인
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
        if len(cur) != len(old) + len(WK):
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
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')
    for word in BANNED:
        if word in json.dumps({k: fl['notes'][k] for k in fl['notes']}, ensure_ascii=False):
            raise SystemExit('notes 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    master['extended'] = (before_extended + ' / ' + args.note).strip(' /')

    print('신규 %d칸 · 총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (len(added), before_total, counts['total'],
             counts['total'] - counts['daytrip'], counts['daytrip']))
    print('2027-04 %d → %d건' % (before_apr, counts['byMonth'][MONTH]))
    print('notes[2027-04] 꼬리:', fl['notes'][MONTH][-330:])

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
