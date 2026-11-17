#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 24개 노선 **2027년 2월 1주차(설 연휴 2/4~8) 5패턴 120칸 완본** md
→ `data/master_db.json` 의 `flights` 병합.

앞선 조사(2026-11-17)로 이미 있던 **34칸**(목~일 24 · 오사카 나머지 4패턴 · 도쿄 금~일·토~월)은
그대로 두고, 이번 완본에서 새로 찬 **86칸**만 더한다. 후쿠오카는 4칸을 개별 조회로 다시 확인해
3칸 금액이 바뀌었다(392,400→364,100 / 400,000→401,500 / 465,400→467,050) — 원문 '조건·주의'에
적힌 그 3칸만 갱신하고, 그 밖의 기존 금액이 하나라도 다르면 멈춘다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_feb_w1.py \
        ../data-sources/flights-2027-02/부산출발-항공특가-2027년2월-1주차-완본.md --dry-run

읽는 곳(패턴별 5개 절의 줄 + '이번 주 가장 싼 10칸' + '노선별로 가장 싼 패턴' + '한눈에'):
  · 값 — `- 2027-02-04 · 목~일 3박 · 부산–후쿠오카(FUK) · 263,900원 · 에어부산 · 직항 1시간`
  · 경유 칸은 `경유(마닐라, 총 30시간20분) (직항 최저 693,000원)` 처럼 같은 날짜 직항 최저가를
    괄호로 붙였다 → note 뒤에 `※직항 최저 …` 로 옮기고 `alt` 에 숫자를 넣는다.

규칙:
  · 값(가격·날짜·소요시간)은 원문 그대로. 표기만 앱 표기로 옮긴다.
  · 원문이 말하는 칸 수(120)·노선별 5칸·패턴별 24칸·최저/최고·패턴 평균·경유 35칸·TOP10을
    파싱 결과와 **전수 대조**한다. 한 칸이라도 다르면 멈춘다.
  · 이미 있는 칸은 중복으로 넣지 않는다. 금액이 다르면 EXPECTED_UPDATES 에 적힌 3칸만 갱신한다.
  · 호텔 538곳 · 아코르 · 다른 8개 노선은 **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)와 2027년 2월 `notes`(커버리지 문구)를 다시 쓴다.
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
PATTERNS = ('목~일', '금~일', '토~월', '목~월', '금~월')
# 원문이 말하는 값 — 24개 노선 · 5패턴 · 120칸 · 경유 35칸
ROUTE_ORDER = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
               'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
EXPECT = {
    'cells': 120,
    # 패턴 → 출발일 (설 연휴 2/4 목 ~ 2/8 월)
    'starts': {'목~일': '2027-02-04', '금~일': '2027-02-05', '토~월': '2027-02-06',
               '목~월': '2027-02-04', '금~월': '2027-02-05'},
    'via': 35,
    'overall': (263900, 1028700),            # 최저 후쿠오카 2/4 목~일 · 최고 치앙마이 2/6 토~월
    'avg': {'목~일': 545600, '목~월': 565300, '금~일': 594500, '금~월': 614800, '토~월': 629100},
    'top10': (263900, 362300, 364100, 370700, 372600, 379300, 388700, 393200, 401500, 403700),
}
# 이미 있던 34칸 중 이번 개별 재조회로 금액이 바뀐 칸 — 원문 '조건·주의'에 적힌 3칸뿐이다
EXPECTED_UPDATES = {
    ('FUK', '2027-02-04', '목~월'): (392400, 364100),
    ('FUK', '2027-02-05', '금~일'): (400000, 401500),
    ('FUK', '2027-02-06', '토~월'): (465400, 467050),
}
PREV_CELLS, NEW_CELLS = 31, 86      # 금액이 같아 손대지 않는 칸 · 새로 더하는 칸 (31 + 3 + 86 = 120)
NEW_BY_MONTH = {'2027-02': 86}

LINE = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · (목~일|금~일|토~월|목~월|금~월) (\d)박 · '
                  r'부산–([^(]+)\(([A-Z]{3})\) · ([\d,]+)원 · (.+)$')
ROUTE_LINE = re.compile(r'^- 부산–([^(]+)\(([A-Z]{3})\) · 최저 (\d{4}-\d{2}-\d{2}) (\S+) '
                        r'([\d,]+)원\(([^)]*)\) · 최고 (\d{4}-\d{2}-\d{2}) (\S+) ([\d,]+)원$')


# ---------------------------------------------------------------- 표기 변환
def norm_desc(desc):
    """원문 편구성 → {via, note, alt?}.

    '직항 1시간(07:30-08:30)'                        → 직항 · note '직항 1시간(07:30-08:30)'
    '경유(마닐라, 총 30시간20분) (직항 최저 693,000원)' → 경유 · note '경유(마닐라, 총 30시간20분) ※직항 최저 693,000원' · alt 693000
    """
    d = (desc or '').strip()
    alt, tail = None, ''
    if ') (' in d:                      # 경유 설명 뒤에 붙은 같은 날짜 직항 최저/사유
        head, rest = d.rsplit(') (', 1)
        head += ')'
        tail = rest[:-1] if rest.endswith(')') else rest
        d = head
    if d.startswith('경유'):
        info = {'via': True, 'note': d}
    elif d.startswith('직항'):
        info = {'via': False, 'note': d}
    else:
        raise SystemExit('경유/직항 표기가 아닙니다(원문 확인 필요): %r' % desc)
    if tail:
        info['note'] = info['note'] + ' ※' + tail
        m = re.search(r'직항 최저 ([\d,]+)원', tail)
        if m:
            alt = int(m.group(1).replace(',', ''))
    if alt:
        info['alt'] = alt
    return info


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    nights = (WD[b] - WD[a]) % 7 or 7
    return (start + datetime.timedelta(days=nights)).isoformat()


# ---------------------------------------------------------------- 파싱
def parse_cells(text):
    cells = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('- 2027-02'):
            continue
        m = LINE.match(line)
        if not m:
            raise SystemExit('줄 형식이 예상과 다릅니다: %s' % line)
        date, pattern, nights, city, code, price, desc = m.groups()
        if int(nights) != (WD[pattern[-1]] - WD[pattern[0]]) % 7:
            raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
        deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern,
                'price': int(price.replace(',', ''))}
        fields = [f.strip() for f in desc.split(' · ')]
        if not fields or not fields[0]:
            raise SystemExit('항공사가 없습니다: %s' % line)
        deal['airline'] = fields[0]
        deal.update(norm_desc(' · '.join(fields[1:])))
        key = (code, date, pattern)
        prev = cells.get(key)
        if prev is not None:
            # '이번 주 가장 싼 10칸' 목록과 본문이 같은 칸을 두 번 적는다 — 금액이 같아야 한다
            if prev['price'] != deal['price']:
                raise SystemExit('%s 금액이 본문과 목록에서 다릅니다: %s / %s'
                                 % (key, prev['price'], deal['price']))
            continue
        cells[key] = deal
    return cells


def parse_route_summary(text):
    """'노선별로 가장 싼 패턴' 절 → code → (최저일, 최저패턴, 최저가, 최고일, 최고패턴, 최고가)."""
    out = {}
    for raw in text.splitlines():
        m = ROUTE_LINE.match(raw.strip())
        if not m:
            continue
        city, code, d1, p1, lo, airline, d2, p2, hi = m.groups()
        out[code] = ((d1, p1, int(lo.replace(',', ''))), (d2, p2, int(hi.replace(',', ''))))
    return out


def summary_checks(text, cells, routes):
    bad = []
    if len(cells) != EXPECT['cells']:
        bad.append('값 %d칸 (기대 %d칸)' % (len(cells), EXPECT['cells']))
    per_route = {}
    per_pat = {}
    for (code, date, pattern), d in cells.items():
        per_route[code] = per_route.get(code, 0) + 1
        per_pat[pattern] = per_pat.get(pattern, 0) + 1
        if EXPECT['starts'][pattern] != date:
            bad.append('%s %s 출발일이 %s (기대 %s)' % (code, pattern, date, EXPECT['starts'][pattern]))
    if set(per_route) != set(ROUTE_ORDER):
        bad.append('노선 집합이 다릅니다: %s' % sorted(set(per_route) ^ set(ROUTE_ORDER)))
    for code in ROUTE_ORDER:
        if per_route.get(code) != 5:
            bad.append('%s %d칸 (기대 5칸)' % (code, per_route.get(code)))
    for pat in PATTERNS:
        if per_pat.get(pat) != 24:
            bad.append('%s %d칸 (기대 24칸)' % (pat, per_pat.get(pat)))

    prices = [d['price'] for d in cells.values()]
    if (min(prices), max(prices)) != EXPECT['overall']:
        bad.append('전체 최저·최고 %s (기대 %s)' % ((min(prices), max(prices)), EXPECT['overall']))
    for pat, want in EXPECT['avg'].items():
        ps = [d['price'] for (_, _, p), d in cells.items() if p == pat]
        gc = int(round(sum(ps) / len(ps), -2))       # 원문은 백원 단위로 반올림해 적는다
        if gc != want:
            bad.append('%s 평균 %d원 (기대 %d원)' % (pat, gc, want))
    via = sum(1 for d in cells.values() if d.get('via'))
    if via != EXPECT['via']:
        bad.append('경유 최저가 %d칸 (기대 %d칸)' % (via, EXPECT['via']))

    # '이번 주 가장 싼 10칸' — 값과 목록을 대조
    ten = [int(x.replace(',', '')) for x in re.findall(
        r'^- 2027-02-\d\d · (?:목~일|금~일|토~월|목~월|금~월) \d박 · 부산–[^(]+\([A-Z]{3}\) · ([\d,]+)원',
        text, re.M)]
    cheapest = [p for p in sorted(prices)[:10]]
    if ten[:10] != list(EXPECT['top10']):
        bad.append('원문 TOP10 %s (기대 %s)' % (ten[:10], list(EXPECT['top10'])))
    if cheapest != list(EXPECT['top10']):
        bad.append('계산한 10칸 %s (원문 TOP10 과 다름)' % cheapest)

    # '노선별로 가장 싼 패턴' 표 — 노선마다 최저·최고
    if set(routes) != set(ROUTE_ORDER):
        bad.append('노선 요약 표 %d개 노선 (기대 24개)' % len(routes))
    for code in ROUTE_ORDER:
        rows = [(p, d['price']) for (c, _, p), d in cells.items() if c == code]
        if code not in routes:
            bad.append('%s 노선 요약 없음' % code)
            continue
        (d1, p1, lo), (d2, p2, hi) = routes[code]
        gmin = min(rows, key=lambda x: x[1])
        gmax = max(rows, key=lambda x: x[1])
        if lo != gmin[1] or hi != gmax[1]:
            bad.append('%s 최저·최고 %s (원문 %s)' % (code, (gmin[1], gmax[1]), (lo, hi)))
        # 동점이면 원문이 어느 패턴을 적었든 값만 맞으면 된다(난징 507,700·510,500)
        if cells.get((code, d1, p1), {}).get('price') != lo or \
                cells.get((code, d2, p2), {}).get('price') != hi:
            bad.append('%s 요약 날짜·패턴 칸이 본문과 다릅니다: %s %s / %s %s'
                       % (code, d1, p1, d2, p2))
    return bad


# ---------------------------------------------------------------- 병합
def merge(master, cells):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTE_ORDER:
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)

    added, same, updated, conflicts = [], [], [], []
    for (code, date, pattern), deal in sorted(cells.items()):
        r = routes[code]
        have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
        if have is not None:
            if have.get('price') == deal['price']:
                same.append((code, date, pattern))
                continue
            expect = EXPECTED_UPDATES.get((code, date, pattern))
            if expect is None:
                conflicts.append((code, date, pattern, have.get('price'), deal['price']))
                continue
            if expect != (have.get('price'), deal['price']):
                conflicts.append((code, date, pattern, have.get('price'), deal['price']))
                continue
            for k in ('price', 'airline', 'via', 'note', 'alt'):
                if k in deal:
                    have[k] = deal[k]
                else:
                    have.pop(k, None)
            have.pop('src', None)          # 운임 캘린더 값 → 개별 조회값으로 교체
            updated.append((code, date, pattern, expect[0], expect[1]))
            continue
        r['deals'].append(dict(deal))
        added.append((code, date, pattern, deal['price']))
    if conflicts:
        raise SystemExit('기존 금액과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts)

    for code in ROUTE_ORDER:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))

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
    return added, same, updated


def notes_update(fl):
    fl['notes']['2027-02'] = (
        '기존 24개 노선은 2027년 2월 1~4주 × 5패턴 480칸을 전부 실측했습니다(1주차 설 연휴 120칸 포함, '
        '빈칸 0칸). 중국 8개 노선은 2박(금~일·토~월) 4주씩을 실측했습니다 — 선양·다롄·광저우·샤먼 64칸, '
        '연길·장가계·구이린·황산은 금~일 32칸 + 토~월 32칸(황산은 2/6~2/27 토~월 판매편이 없어 0건)입니다. '
        '중국 8개 노선의 3·4박은 미조회(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='부산 출발 24개 노선 2027년 2월 1주차 5패턴 120칸 md → master_db.json 병합')
    ap.add_argument('md')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    cells = parse_cells(text)
    routes = parse_route_summary(text)

    bad = summary_checks(text, cells, routes)
    print('  값 %d칸 · 노선 %d개 × 5패턴 · 패턴별 %s · 경유 %d칸'
          % (len(cells), len({c for c, _, _ in cells}),
             {p: sum(1 for k in cells if k[2] == p) for p in PATTERNS},
             sum(1 for d in cells.values() if d.get('via'))))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_total = fl['counts']['total']
    before_holiday = fl['counts']['holiday']
    before_by_month = dict(fl['counts']['byMonth'])
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTE_ORDER],
                              ensure_ascii=False, sort_keys=True)
    before_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False, sort_keys=True)
                     for r in fl['routes'] if r['code'] in ROUTE_ORDER for d in r['deals']}
    before_nosale = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_notes = {k: v for k, v in fl['notes'].items() if k != '2027-02'}

    added, same, updated = merge(master, cells)
    notes_update(fl)

    if len(same) != PREV_CELLS:
        raise SystemExit('금액이 같아 그대로 둔 칸 %d개 (기대 %d개)' % (len(same), PREV_CELLS))
    if len(updated) != len(EXPECTED_UPDATES):
        raise SystemExit('갱신 %d칸 (기대 %d칸): %s' % (len(updated), len(EXPECTED_UPDATES), updated))
    if len(added) != NEW_CELLS:
        raise SystemExit('신규 %d칸 (기대 %d칸): %s' % (len(added), NEW_CELLS, added))
    after_by_month = fl['counts']['byMonth']
    for m, n in NEW_BY_MONTH.items():
        if after_by_month.get(m, 0) - before_by_month.get(m, 0) != n:
            raise SystemExit('%s 증가 %d칸 (기대 %d칸)'
                             % (m, after_by_month.get(m, 0) - before_by_month.get(m, 0), n))
    if fl['counts']['total'] != before_total + NEW_CELLS:
        raise SystemExit('총 건수 %d → %d (기대 +%d)' % (before_total, fl['counts']['total'], NEW_CELLS))
    if fl['counts']['holiday'] != before_holiday + 22:
        raise SystemExit('연휴(2/4 출발) 칸 %d → %d (기대 +22)' % (before_holiday, fl['counts']['holiday']))

    # 보존 검증 — 호텔·아코르·다른 8개 노선·기존 0건 기록은 한 바이트도 바뀌면 안 된다
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTE_ORDER],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 항공 노선 데이터가 바뀌었습니다.')
    after_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False, sort_keys=True)
                    for r in fl['routes'] if r['code'] in ROUTE_ORDER for d in r['deals']}
    for key, blob in before_within.items():
        if key in EXPECTED_UPDATES:
            continue
        if after_within.get(key) != blob:
            raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % (key,))
    for key, (old, new) in EXPECTED_UPDATES.items():
        if after_within.get(key) is None:
            raise SystemExit('갱신 대상 딜이 없습니다: %s' % (key,))
        after = json.loads(after_within[key])
        if after.get('price') != new or json.loads(before_within[key]).get('price') != old:
            raise SystemExit('%s 갱신 금액이 다릅니다: %s' % (key, after.get('price')))
    if json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True) != before_nosale:
        raise SystemExit('판매편 0건 기록이 바뀌었습니다.')
    if {k: v for k, v in fl['notes'].items() if k != '2027-02'} != before_notes:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다.')
    for r in fl['routes']:
        if r['code'] in ROUTE_ORDER:
            keys = [(d['date'], d['pattern']) for d in r['deals']]
            if len(keys) != len(set(keys)):
                raise SystemExit('%s (출발일·패턴) 중복' % r['code'])

    print('신규 딜 %d건 · 갱신 %d건 · 그대로 %d건' % (len(added), len(updated), len(same)))
    print('총 %d건 → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, fl['counts']['total'],
        fl['counts']['total'] - fl['counts']['daytrip'], fl['counts']['daytrip']))
    print('월별: %s' % fl['counts']['byMonth'])
    for u in updated:
        print('  ~ %s %s %s %s원 → %s원' % u)
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
