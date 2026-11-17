#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선 2027년 3월 1주차(3/4~8) 5패턴 120칸 완본** md
→ `data/master_db.json` 의 `flights` 병합(노선 신설 없음).

읽는 곳:
  · `### 부산–상하이 (PVG)` 절 머리 — 노선 코드
  · `- 2027-03-05 · 금~일·2박 · PUS–PVG · 338,000원 · 춘추항공 · 직항 1시간55분(22:10-23:05)`
    경유 칸은 뒤에 ` (직항 최저 647,400원)` 또는 ` (직항편 없음)` 이 붙는다
  · `## 한눈에` — 120조합 전수·전체 최저/최고·패턴 평균·경유 37칸·직항편 없음 10칸
  · `## 노선별 최저가 순위` — 24줄(노선별 5패턴 중 최저)

규칙:
  · 값은 원문 그대로. 120칸(24노선 × 5패턴) 전수와 노선별·패턴별 칸 수, 전체 최저·최고,
    패턴 평균, 경유 칸 수, 직항편 없음 칸 수, 노선별 최저가·날짜·패턴을 **전수 대조**한다.
  · 이미 있는 칸은 넣지 않고(중복 금지), 금액이 다른 기존 칸이 하나라도 있으면 멈춘다.
  · 호텔 538곳 · 아코르 · 다른 노선·`noSale`·다른 달 notes 는 **바이트 동일성**으로 보존 확인.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_mar1w.py /workspace/data-sources/flights-2027-03/부산출발-항공특가-2027년3월-1주차.md --dry-run
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
PATTERNS = ('금~일', '토~월', '목~일', '금~월', '목~월')
ROUTE_ORDER = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
               'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'TPE': '타이베이', 'HKG': '홍콩',
        'MFM': '마카오', 'PVG': '상하이', 'BKK': '방콕', 'DAD': '다낭', 'CXR': '나트랑',
        'NKG': '난징', 'SGN': '호찌민', 'SIN': '싱가포르', 'GUM': '괌', 'NGO': '나고야',
        'OKA': '오키나와', 'HGH': '항저우', 'TAO': '칭다오', 'HAN': '하노이', 'CNX': '치앙마이',
        'DPS': '발리', 'KHH': '가오슝', 'RMQ': '타이중', 'BJS': '베이징'}
# 원문이 말하는 값
EXPECT = {
    'cells': 120,
    'start': '2027-03-04',
    'overall': (243200, 564600),
    'avg': {'금~일': 378954, '토~월': 376512, '목~일': 381212, '금~월': 371529, '목~월': 375583},
    'via': 37,
    'no_direct': 10,
}
NEW_CELLS = 120
NEW_BY_MONTH = {'2027-03': 120}

HEAD = re.compile(r'^### 부산–(.+?) \(([A-Z]{3})\)$')
CELL = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일])·(\d)박 · '
                  r'PUS–([A-Z]{3}) · ([\d,]+)원 · ([^·]+?) · (.+)$')
RANK = re.compile(r'^- ([\d,]+)원 · (.+?)\(([A-Z]{3})\) · (\d{4}-\d{2}-\d{2}) '
                  r'[①②③④⑤] (\S+?)·(\d)박 · (.+)$', re.M)


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def tidy(desc):
    """'직항 1시간55분(22:10-23:05)' → '직항 1시간 55분(22:10-23:05)' · '경유(…, 총13시간5분)' 정리."""
    d = re.sub(r'(\d+)시간(\d+)분', r'\1시간 \2분', desc)
    d = re.sub(r'총(\d)', r'총 \1', d)
    d = re.sub(r'(\d)시간(?!\s?\d)', r'\1시간', d)
    return d.strip()


def parse(text):
    cells, heads = {}, {}
    code = None
    for raw in text.splitlines():
        line = raw.strip()
        m = HEAD.match(line)
        if m:
            city, code = m.groups()
            if code not in ROUTE_ORDER:
                raise SystemExit('예상 밖 노선: %s' % line)
            if city != CITY[code]:
                raise SystemExit('도시 이름이 다릅니다: %s (%s)' % (line, CITY[code]))
            heads[code] = city
            continue
        if line.startswith('## ') or line.startswith('### '):
            code = None
            continue
        if code:
            m = CELL.match(line)
            if m:
                date, pat, nights, rc, price, airline, desc = m.groups()
                if rc != code:
                    raise SystemExit('절과 노선 코드가 다릅니다: %s' % line)
                if int(nights) != (WD[pat[-1]] - WD[pat[0]]) % 7:
                    raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
                if date != EXPECT['start'] and date[8:] not in ('05', '06'):
                    raise SystemExit('3월 1주차 밖 출발일입니다: %s' % line)
                deal = {'date': date, 'back': back_date(date, pat), 'pattern': pat,
                        'price': int(price.replace(',', '')), 'airline': airline.strip()}
                tail = ''
                mo = re.search(r'\((.+)\)$', desc)
                body = desc
                if ' (직항 최저' in desc or ' (직항편 없음)' in desc:
                    body, tail = desc.rsplit(' (', 1)
                    tail = tail[:-1]
                body = tidy(body)
                deal['via'] = body.startswith('경유')
                if not (body.startswith('직항') or body.startswith('경유')):
                    raise SystemExit('직항/경유 표기가 아닙니다: %s' % line)
                note = body
                if tail:
                    note += ' · ' + tidy(tail)
                    mm = re.search(r'직항 최저 ([\d,]+)원', tail)
                    if mm:
                        deal['alt'] = int(mm.group(1).replace(',', ''))
                deal['note'] = note
                if any(d['date'] == date and d['pattern'] == pat for d in cells.get(code, [])):
                    raise SystemExit('%s %s %s 중복' % (code, date, pat))
                cells.setdefault(code, []).append(deal)
    rank = []
    for m in RANK.finditer(text):
        price, city, code, date, pat, nights, desc = m.groups()
        rank.append((int(price.replace(',', '')), code, date, pat, desc.strip()))
    return cells, heads, rank


def checks(text, cells, heads, rank):
    bad = []
    if set(cells) != set(ROUTE_ORDER):
        bad.append('노선 집합이 다릅니다: %s' % sorted(set(cells) ^ set(ROUTE_ORDER)))
    total = sum(len(v) for v in cells.values())
    if total != EXPECT['cells']:
        bad.append('값 %d칸 (기대 %d칸)' % (total, EXPECT['cells']))
    for code in ROUTE_ORDER:
        deals = cells.get(code) or []
        if len(deals) != 5:
            bad.append('%s %d칸 (기대 5칸)' % (code, len(deals)))
        if {d['pattern'] for d in deals} != set(PATTERNS):
            bad.append('%s 패턴 집합이 다릅니다: %s' % (code, sorted(d['pattern'] for d in deals)))
    per_pat = {p: sum(1 for v in cells.values() for d in v if d['pattern'] == p) for p in PATTERNS}
    for p in PATTERNS:
        if per_pat[p] != 24:
            bad.append('%s %d칸 (기대 24칸)' % (p, per_pat[p]))

    prices = [d['price'] for v in cells.values() for d in v]
    if (min(prices), max(prices)) != EXPECT['overall']:
        bad.append('전체 최저·최고 %s (원문 %s)' % ((min(prices), max(prices)), EXPECT['overall']))
    for p, want in EXPECT['avg'].items():
        ps = [d['price'] for v in cells.values() for d in v if d['pattern'] == p]
        mean = sum(ps) / len(ps)
        if int(round(mean)) != want:
            bad.append('%s 평균 %.1f원 (원문 %d원)' % (p, mean, want))
    via = sum(1 for v in cells.values() for d in v if d['via'])
    if via != EXPECT['via']:
        bad.append('경유 최저가 %d칸 (원문 %d칸)' % (via, EXPECT['via']))
    no_direct = sum(1 for v in cells.values() for d in v if '직항편 없음' in d['note'])
    if no_direct != EXPECT['no_direct']:
        bad.append('직항편 없음 %d칸 (원문 %d칸)' % (no_direct, EXPECT['no_direct']))

    # 노선별 최저가 순위 24줄
    if len(rank) != 24:
        bad.append('노선별 최저가 순위 %d줄 (기대 24줄)' % len(rank))
    if {r[1] for r in rank} != set(ROUTE_ORDER):
        bad.append('순위표 노선 집합이 다릅니다: %s' % sorted({r[1] for r in rank} ^ set(ROUTE_ORDER)))
    for price, code, date, pat, desc in rank:
        deals = cells.get(code) or []
        lo = min(deals, key=lambda d: d['price'])
        if lo['price'] != price or lo['date'] != date or lo['pattern'] != pat:
            bad.append('%s 순위표 %s (계산 %s)' % (code, (price, date, pat),
                                                (lo['price'], lo['date'], lo['pattern'])))
        if lo['airline'] not in desc:
            bad.append('%s 순위표 항공사 %r 가 본문 %r 과 다릅니다' % (code, desc, lo['airline']))
        if ('경유' in desc) != lo['via']:
            bad.append('%s 순위표 직항/경유 표기가 본문과 다릅니다: %s' % (code, desc))

    for phrase in ('24개 노선 × 5패턴 = 120조합 전수 실측 완료',
                   '빈칸이나 추정치는 없습니다',
                   '이 주차 전체 최저가는 후쿠오카 3/4~3/8 243,200원',
                   '가장 비싼 조합은 발리'):
        if phrase not in text:
            bad.append('원문 문장을 찾지 못했습니다: %s' % phrase)
    return bad


def merge(master, cells):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    added, same, conflicts = 0, 0, []
    for code in ROUTE_ORDER:
        r = routes[code]
        for deal in cells[code]:
            have = next((d for d in r['deals']
                         if d['date'] == deal['date'] and d['pattern'] == deal['pattern']), None)
            if have is not None:
                if have.get('price') == deal['price']:
                    same += 1
                    continue
                conflicts.append((code, deal['date'], deal['pattern'],
                                  have.get('price'), deal['price']))
                continue
            r['deals'].append(dict(deal))
            added += 1
        r['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))
    if conflicts:
        raise SystemExit('기존 금액과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts)

    alldeals = [d for r in fl['routes'] for d in r['deals']]
    by_month = {}
    for d in alldeals:
        by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    fl['counts'] = {
        'total': len(alldeals),
        'byMonth': {k: by_month[k] for k in sorted(by_month)},
        'holiday': sum(1 for d in alldeals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in alldeals if d['pattern'].split('~')[0] == d['pattern'].split('~')[1]),
    }
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = len(alldeals)
    return added, same


def notes_update(fl):
    fl['notes']['2027-03'] = (
        '기존 24개 노선은 3월 1주차(3/4~8) 5패턴 120칸을 전부 실측했습니다 — 전체 최저는 후쿠오카 '
        '3/4~8 목~월 243,200원(에어부산 직항), 최고는 발리 3/4~8 목~월 564,600원(베트남항공 호찌민 경유)이고 '
        '경유가 최저인 칸이 37칸(직항편 없음 10칸: 마카오 5 · 항저우 2 · 발리 3)입니다. '
        '중국 8개 노선은 3월 2박 260칸을 실측했습니다 — 선양·다롄·광저우·샤먼은 금~일·토~월·목~일 4주씩, '
        '연길·장가계·구이린·황산은 금~일·토~월 4주씩입니다(황산 금~일·토~월은 3/6~3/20 판매편이 없어 0건). '
        '선양·다롄·광저우·샤먼의 금~월·목~월과 연길·장가계·구이린·황산의 3·4박은 미조회(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 3월 1주차 24개 노선 120칸 md → master_db.json 병합')
    ap.add_argument('md')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    cells, heads, rank = parse(text)
    bad = checks(text, cells, heads, rank)
    print('  값 %d칸 · 노선 %d개 × 5패턴' % (sum(len(v) for v in cells.values()), len(cells)))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    before_routes = json.dumps([{'code': r['code'], 'city': r['city'], 'extra': r['extra'],
                                 'daytrip': r['daytrip']} for r in fl['routes']],
                               ensure_ascii=False, sort_keys=True)
    before_nosale = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_notes = {k: v for k, v in fl['notes'].items() if k != '2027-03'}
    before_deals = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False,
                                                                     sort_keys=True)
                    for r in fl['routes'] for d in r['deals']}

    added, same = merge(master, cells)
    notes_update(fl)

    if added != NEW_CELLS or same:
        raise SystemExit('신규 %d칸·중복 %d칸 (기대 신규 %d칸·중복 0칸)' % (added, same, NEW_CELLS))
    if fl['counts']['total'] != before_total + NEW_CELLS:
        raise SystemExit('총 건수 %d → %d (기대 +%d)' % (before_total, fl['counts']['total'], NEW_CELLS))
    for m, n in NEW_BY_MONTH.items():
        if fl['counts']['byMonth'][m] - before_by_month.get(m, 0) != n:
            raise SystemExit('%s 증가 %d칸 (기대 %d칸)'
                             % (m, fl['counts']['byMonth'][m] - before_by_month.get(m, 0), n))

    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    after_routes = json.dumps([{'code': r['code'], 'city': r['city'], 'extra': r['extra'],
                                'daytrip': r['daytrip']} for r in fl['routes']],
                              ensure_ascii=False, sort_keys=True)
    if after_routes != before_routes:
        raise SystemExit('노선 목록·daytrip 메타가 바뀌었습니다.')
    if json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True) != before_nosale:
        raise SystemExit('판매편 0건 기록이 바뀌었습니다.')
    if {k: v for k, v in fl['notes'].items() if k != '2027-03'} != before_notes:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다.')
    after_deals = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False,
                                                                   sort_keys=True)
                   for r in fl['routes'] for d in r['deals']}
    for key, blob in before_deals.items():
        if after_deals.get(key) != blob:
            raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % (key,))
    for r in fl['routes']:
        keys = [(d['date'], d['pattern']) for d in r['deals']]
        if len(keys) != len(set(keys)):
            raise SystemExit('%s (출발일·패턴) 중복' % r['code'])

    print('신규 딜 %d건 · 중복 0건' % added)
    print('총 %d건 → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, fl['counts']['total'],
        fl['counts']['total'] - fl['counts']['daytrip'], fl['counts']['daytrip']))
    print('월별: %s' % fl['counts']['byMonth'])

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
