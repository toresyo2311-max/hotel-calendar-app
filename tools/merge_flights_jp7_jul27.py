#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 일본 신규 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)
**2027년 7월 5주 × 5패턴 175칸 완결본**을 `data/master_db.json` 의 `flights` 에 병합한다.

원본: `data-sources/flights-jp-new7/부산출발-일본7노선-7월-완결.md`
  · `### 부산–삿포로(신치토세) (CTS) · 25칸 중 25칸 실측 · 최저 695,800원` 절 머리 — 노선 코드·칸 수·최저
  · 그 아래 `- 2027-07-01 · 목~일 · 삿포로(신치토체) · 744,000원 · 이스타항공 · 직항 14:10-16:40 2시간30분` 줄(값)
  · `· [미확인/검증필요]` 줄은 값이 아니다 — 시즈오카 25칸이 여기에 해당한다.
  · `## 2027년 7월 달력`·`## 주차별 · 노선별 최저가 흐름`·`## 패턴 5종` 표 — 파싱 결과와 대조

규칙:
  · 원문이 말하는 175칸(7노선 × 5주 × 5패턴)과 노선별 실측(6개 노선 25칸 · 시즈오카 0칸)을 전수 대조한다.
    하나라도 다르면 멈춘다.
  · 값이 있는 150칸은 **새 칸**이다(2027년 7월 일본 7노선에 이미 값이 있으면 멈춘다 — 덮어쓰지 않는다).
  · 시즈오카 25칸은 원문이 "이용 가능한 항공편 없음"(네 구간 조회)으로 적은 그대로,
    값 대신 `noSale` 에 `status: unopened`(예약창 미오픈)로 적는다 — 추정·보간 없음.
  · 값은 원문 그대로(반올림 없음). 항공사 이름·직항/경유·소요시간만 앱 표기로 옮긴다.
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 다른 40개 노선 · 다른 달 `notes` · 나머지 `noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(flights.total · byMonth · holiday · daytrip, 최상위 deals)와 2027-07 `notes` 를 다시 쓴다.
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jp7_jul27.py --dry-run
    python3 tools/merge_flights_jp7_jul27.py
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
MD = os.path.normpath(os.path.join(
    ROOT, '..', '..', 'data-sources', 'flights-jp-new7', '부산출발-일본7노선-7월-완결.md'))

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
JP = ('CTS', 'FSZ', 'KOJ', 'KMJ', 'MYJ', 'TAK', 'MMY')          # 원문 절 순서
CITY = {'KMJ': '구마모토', 'KOJ': '가고시마', 'FSZ': '시즈오카', 'MYJ': '마쓰야마',
        'TAK': '다카마쓰', 'MMY': '미야코지마', 'CTS': '삿포로(신치토세)'}
CITY_MD = dict(CITY, **{'CTS': '삿포로(신치토세)'})
WK = ('목~일', '금~일', '토~월', '목~월', '금~월')
PAT_ORDER = ('목~월', '목~일', '금~월', '금~일', '토~월')
WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
              for i in range(5))

# 원문이 말하는 값 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT_HEAD = {'CTS': (25, 25, 695800), 'FSZ': (25, 0, None), 'KOJ': (25, 25, 549200),
               'KMJ': (25, 25, 483700), 'MYJ': (25, 25, 634000), 'TAK': (25, 25, 711300),
               'MMY': (25, 25, 626700)}
EXPECT_UNKNOWN = {'FSZ': 25}
# 원문 '먼저 결론' 의 노선별 최저
EXPECT_LOW = {'CTS': 695800, 'KOJ': 549200, 'KMJ': 483700,
              'MYJ': 634000, 'TAK': 711300, 'MMY': 626700}
# 원문 '주차별 · 노선별 최저가 흐름' (천원 단위 표기 → 원)
EXPECT_WEEK_ROUTE = {
    'KMJ': (746, 484, 725, 588, 834), 'KOJ': (549, 549, 599, 559, 569),
    'MYJ': (638, 634, 680, 637, 677), 'CTS': (696, 726, 751, 774, 782),
    'TAK': (711, 767, 1008, 748, 799), 'MMY': (839, 839, 769, 842, 627),
}
# 원문 '패턴 5종' 표 (노선 → 패턴 순서 WK 의 최저, 천원)
EXPECT_PATTERN = {
    'KMJ': (493, 625, 725, 484, 746), 'KOJ': (599, 625, 576, 549, 576),
    'MYJ': (677, 713, 657, 634, 664), 'CTS': (744, 737, 696, 703, 696),
    'TAK': (811, 782, 842, 740, 711), 'MMY': (842, 910, 627, 635, 839),
}
# 직항이 최저가인 칸 — 원문 요약은 '32칸(삿포로 17·구마모토 15)'이라고 적었지만
# 칸별 줄을 그대로 세면 삿포로 15 · 구마모토 15 = 30칸이다(원문 요약이 자기 표와 어긋난다).
# 집계는 칸별 값으로 하고, 요약의 32칸은 쓰지 않는다.
EXPECT_DIRECT = {'CTS': 15, 'KMJ': 15}
# 원문 '주차 실측 최저' (7/1 549,200 가고시마 … 7/29 569,000 가고시마)
EXPECT_WEEK_LOW = (549200, 483700, 598500, 559100, 569000)
EXPECT_TOTAL_CELLS = sum(v[0] for v in EXPECT_HEAD.values())        # 175
EXPECT_PRICED_TOTAL = sum(v[1] for v in EXPECT_HEAD.values())       # 150
EXPECT_UNOPENED_TOTAL = EXPECT_TOTAL_CELLS - EXPECT_PRICED_TOTAL    # 25

HEAD = re.compile(r'^### 부산–(.+?) \(([A-Z]{3})\) · (\d+)칸 중 (\d+)칸 실측 · 최저 (.+)$')
CELL = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · (.+?) · (.+)$')
SRC = re.compile(r'\s*\[출처:[^\]]*\]\s*$')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '네이버', '구글')


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def clean_detail(detail):
    det = (detail or '').strip()
    det = re.sub(r'\s*,\s*', ' · ', det)
    det = re.sub(r'(?<!\d)(\d+)시간(\d+)분', r'\1시간 \2분', det)
    det = re.sub(r'총\s*(\d)', r'총 \1', det)
    return det


def parse_cell(value):
    value = SRC.sub('', value).strip()
    if value in ('[미확인/검증필요]', '미확인/검증필요'):
        return {'kind': 'unknown'}
    if value.startswith('**항공편 없음**'):
        return {'kind': 'nosale'}
    m = re.match(r'^([\d,]+)원(?:\s*·\s*(.+))?$', value)
    if not m:
        raise SystemExit('금액 줄을 읽지 못했습니다: %s' % value)
    rec = {'kind': 'price', 'price': int(m.group(1).replace(',', '')),
           'carrier': None, 'via': None, 'detail': None}
    tail = m.group(2) or ''
    parts = [p.strip() for p in tail.split('·')] if tail else []
    if parts and parts[0] != '미확인':
        rec['carrier'] = parts[0]
        rec['detail'] = parts[1] if len(parts) > 1 else ''
        rec['via'] = (True if rec['detail'].startswith('경유')
                      else False if rec['detail'].startswith('직항') else None)
    return rec


def parse(text):
    cells, order, heads = {}, [], {}
    code = None
    for raw in text.splitlines():
        line = raw.strip()
        m = HEAD.match(line)
        if m:
            city, code, total, got, low = m.groups()
            if code not in JP:
                raise SystemExit('예상 밖 노선: %s' % line)
            if city != CITY_MD[code]:
                raise SystemExit('도시 이름이 다릅니다: %s (기대 %s)' % (city, CITY_MD[code]))
            low_n = None if not low.endswith('원') else int(low.replace(',', '').replace('원', ''))
            heads[code] = (city, int(total), int(got), low_n)
            order.append(code)
            continue
        if line.startswith('##') and not line.startswith('###'):
            code = None if not line.startswith('###') else code
            continue
        if line.startswith('#') and not line.startswith('###'):
            code = None
            continue
        if code:
            m = CELL.match(line)
            if not m:
                continue
            date, pat, city, value = m.groups()
            if pat not in WK:
                raise SystemExit('예상 밖 패턴: %s' % line)
            key = (date, pat)
            if key in cells.setdefault(code, {}):
                raise SystemExit('%s %s %s 중복' % (code, date, pat))
            rec = parse_cell(value)
            rec.update(date=date, pattern=pat)
            cells[code][key] = rec
    if tuple(order) != JP:
        raise SystemExit('노선 순서가 다릅니다: %s' % (order,))
    if sum(len(v) for v in cells.values()) != EXPECT_TOTAL_CELLS:
        raise SystemExit('전체 칸 %d (기대 %d)' % (sum(len(v) for v in cells.values()),
                                                  EXPECT_TOTAL_CELLS))
    for code in JP:
        mine = cells[code]
        total, priced_want, low_want = EXPECT_HEAD[code]
        if len(mine) != total:
            raise SystemExit('%s %d칸 (기대 %d칸)' % (code, len(mine), total))
        priced = {k for k, v in mine.items() if v['kind'] == 'price'}
        if len(priced) != priced_want:
            raise SystemExit('%s 실측 %d칸 (기대 %d칸)' % (code, len(priced), priced_want))
        if sum(1 for v in mine.values() if v['kind'] == 'unknown') != EXPECT_UNKNOWN.get(code, 0):
            raise SystemExit('%s 미확인 칸 수가 다릅니다' % code)
        if sum(1 for v in mine.values() if v['kind'] == 'nosale'):
            raise SystemExit('%s 에 항공편 없음 칸이 있습니다' % code)
        # 5주(목요일 기준) × 5패턴이 모두 있는지
        for thu in WEEKS:
            for pat in WK:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(WD[pat[0]] - 4) % 7)).isoformat()
                if (dt, pat) not in mine:
                    raise SystemExit('%s %s %s 칸이 없습니다' % (code, dt, pat))
        if heads[code][1] != total or heads[code][2] != priced_want:
            raise SystemExit('%s 절 머리 칸 수가 다릅니다: %s' % (code, heads[code]))
        if low_want is not None:
            low = min(v['price'] for v in mine.values() if v['kind'] == 'price')
            if low != low_want or low != heads[code][3]:
                raise SystemExit('%s 최저 %s (원문 %s)' % (code, low, low_want))
        elif priced_want:
            raise SystemExit('%s 최저 표기가 비었습니다' % code)
    # 원문 주차별·패턴별 표와 대조
    for code, want in EXPECT_WEEK_ROUTE.items():
        for i, thu in enumerate(WEEKS):
            vals = [v['price'] for (d, p), v in cells[code].items()
                    if (datetime.date.fromisoformat(d) -
                        datetime.date.fromisoformat(thu)).days // 7 == 0]
            got = (min(vals) + 500) // 1000
            if got != want[i]:
                raise SystemExit('%s %d주차 최저 %s천 (원문 %s천)' % (code, i + 1, got, want[i]))
    for code, want in EXPECT_PATTERN.items():
        for i, pat in enumerate(WK):
            vals = [v['price'] for (d, p), v in cells[code].items() if p == pat]
            got = (min(vals) + 500) // 1000
            if got != want[i]:
                raise SystemExit('%s %s 최저 %s천 (원문 %s천)' % (code, pat, got, want[i]))
    direct = {code: sum(1 for v in cells[code].values()
                        if v['kind'] == 'price' and v['via'] is False) for code in JP}
    if {c: n for c, n in direct.items() if n} != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %s (기대 %s)' % (direct, EXPECT_DIRECT))
    for i, thu in enumerate(WEEKS):
        best = min(v['price'] for code in JP for (d, p), v in cells[code].items()
                   if v['kind'] == 'price' and
                   (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(thu)).days // 7 == 0)
        if best != EXPECT_WEEK_LOW[i]:
            raise SystemExit('%d주차 전체 최저 %s (원문 %s)' % (i + 1, best, EXPECT_WEEK_LOW[i]))
    return cells


def make_deal(rec):
    deal = {'date': rec['date'], 'back': back_date(rec['date'], rec['pattern']),
            'pattern': rec['pattern'], 'price': rec['price']}
    if rec.get('carrier'):
        deal['airline'] = rec['carrier']
        deal['via'] = rec['via']
        deal['note'] = clean_detail(rec.get('detail'))
    else:
        deal['via'] = None
        deal['src'] = '가격표'
        deal['note'] = '가격표 실측 · 직항/경유 미확인'
    return deal


def sort_key(deal):
    return (deal['date'], PAT_ORDER.index(deal['pattern']) if deal['pattern'] in PAT_ORDER else 9)


def july_note(existing):
    extra = (
        ' 일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)은 2027년 7월 '
        '목요일 기준 5주 × 5패턴 175칸을 조회해 6개 노선 150칸이 값으로 찼고, 시즈오카 25칸은 네 구간'
        '(7/1~5·7/8~12·7/22~26·7/29~8/2) 조회 모두 "이용 가능한 항공편 없음"이라 예약창 미오픈으로 '
        '적었습니다(추정 없음). 이 달 최저는 구마모토 2027-07-08~07-12 목~월 483,700원(이스타항공 '
        '직항 12:30-13:50 · 1시간 20분)이고, 다음이 가고시마 7/1·7/8~7/12 목~월 549,200원'
        '(후쿠오카 경유 · 총 5시간 55분)입니다. 7/15~7/19는 일본 공휴일 해의 날 3연휴로 7월의 '
        '봉우리이고, 구마모토 4박이 1,598,500원(2주차 483,700원의 3.3배), 미야코지마 7/16~7/18 2박이 '
        '2,639,400원입니다. 칸별 값을 세면 직항이 최저가인 칸은 30칸으로 전부 구마모토(15)와 '
        '삿포로(15)이고(원문 요약의 32칸·삿포로 17칸은 같은 문서의 칸별 표와 어긋나 칸별 값을 썼습니다), '
        '구마모토 7/30~8/2 금~월 833,900원 한 칸은 항공사가 표시되지 않아 가격표 값만 적었습니다.'
    )
    return existing.rstrip() + extra


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ④ 항공 일본 7노선 2027년 7월 완결본 — 5주 × 5패턴 175칸(값 150 + 미오픈 25), '
        '최저 구마모토 7/8~7/12 483,700원(직항), 총 7,093→7,243건(주말형 6,775→6,925)'))
    args = ap.parse_args(argv)

    text = open(MD, encoding='utf-8').read()
    cells = parse(text)
    master = json.load(open(MASTER, encoding='utf-8'))
    merged = copy.deepcopy(master)
    routes = {r['code']: r for r in merged['flights']['routes']}
    old_routes = {r['code']: r for r in master['flights']['routes']}
    old_marks = master['flights']['noSale']

    added = collections.Counter()
    unopened = []
    for code in JP:
        r = routes[code]
        existing = {(d['date'], d['pattern']) for d in r['deals']}
        if any(s >= '2027-07-01' and s <= '2027-07-31' for s, _ in existing):
            raise SystemExit('%s 에 이미 2027년 7월 값이 있습니다 — 덮어쓰지 않습니다' % code)
        old_keys = {(n.get('code'), n.get('date'), n.get('pattern'))
                    for n in old_marks if n.get('code') == code
                    and '2027-07-01' <= n.get('date', '') <= '2027-07-31'}
        if old_keys:
            raise SystemExit('%s 에 이미 2027년 7월 상태 기록이 있습니다' % code)
        new = [make_deal(v) for v in cells[code].values() if v['kind'] == 'price']
        for deal in sorted(new, key=sort_key):
            pos = sum(1 for d in r['deals'] if d['date'] < deal['date'])
            r['deals'].insert(pos, deal)
        added[code] = len(new)
        for rec in cells[code].values():
            if rec['kind'] == 'unknown':
                unopened.append({'code': code, 'date': rec['date'],
                                 'back': back_date(rec['date'], rec['pattern']),
                                 'pattern': rec['pattern'], 'status': 'unopened',
                                 'note': '예약창 밖(항공사 스케줄 미개시) — 조회 결과 이용 가능한 항공편 0건'})

    if sum(added.values()) != EXPECT_PRICED_TOTAL:
        raise SystemExit('추가 칸 %d (기대 %d)' % (sum(added.values()), EXPECT_PRICED_TOTAL))
    if len(unopened) != EXPECT_UNOPENED_TOTAL:
        raise SystemExit('미오픈 칸 %d (기대 %d)' % (len(unopened), EXPECT_UNOPENED_TOTAL))
    merged['flights']['noSale'] = old_marks + sorted(
        unopened, key=lambda n: (n['code'], n['date'], n['pattern']))

    # ── 보존 확인 ──────────────────────────────────────────────
    for key in ('schema', 'version', 'window', 'built', 'voucherExpiry', 'sources', 'accor', 'hotels'):
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != \
                json.dumps(merged.get(key), ensure_ascii=False, sort_keys=True):
            raise SystemExit('%s 가 달라졌습니다' % key)
    new_routes = {r['code']: r for r in merged['flights']['routes']}
    if list(old_routes) != list(new_routes):
        raise SystemExit('노선 목록이 달라졌습니다')
    for code, old in old_routes.items():
        if code not in JP:
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
        if n not in old_marks and n not in unopened:
            raise SystemExit('noSale 에 예고 없는 기록이 생겼습니다: %s' % n)
    blob = json.dumps(merged, ensure_ascii=False)
    for word in BANNED:
        if word in json.dumps({'added': [d for c in JP for d in new_routes[c]['deals']
                                        if d['date'].startswith('2027-07')]}, ensure_ascii=False):
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
    if counts['total'] != old_counts['total'] + EXPECT_PRICED_TOTAL:
        raise SystemExit('총 건수 %s' % counts['total'])
    if counts['byMonth']['2027-07'] != old_counts['byMonth']['2027-07'] + EXPECT_PRICED_TOTAL:
        raise SystemExit('2027-07 건수 %s' % counts['byMonth']['2027-07'])
    if counts['holiday'] != old_counts['holiday'] or counts['daytrip'] != old_counts['daytrip']:
        raise SystemExit('연휴/당일치기 수가 달라졌습니다: %s vs %s' % (counts, old_counts))
    for m, n in old_counts['byMonth'].items():
        if m != '2027-07' and counts['byMonth'][m] != n:
            raise SystemExit('%s 건수가 달라졌습니다 (%s → %s)' % (m, n, counts['byMonth'][m]))
    merged['flights']['counts'] = counts
    merged['counts'] = dict(master['counts'])
    merged['counts']['deals'] = counts['total']

    # ── notes · extended ──────────────────────────────────────
    notes = dict(master['flights']['notes'])
    if '2027-07' not in notes:
        raise SystemExit('2027-07 notes 가 없습니다')
    note = july_note(notes['2027-07'])
    for word in BANNED:
        if word in note:
            raise SystemExit('note 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    merged['flights']['notes'] = notes
    merged['flights']['notes']['2027-07'] = note
    merged['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')
    for word in BANNED:
        if word in args.note:
            raise SystemExit('extended 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    print('노선별 추가:', dict(added), '합계', sum(added.values()))
    print('미오픈(시즈오카):', len(unopened))
    print('counts:', json.dumps(counts, ensure_ascii=False))
    print('최저 칸 예시:', [(c, d['date'], d['pattern'], d['price'], d.get('airline'))
                        for c in ('KMJ', 'KOJ', 'CTS')
                        for d in new_routes[c]['deals'] if d['date'].startswith('2027-07')][:3])
    print('note:', note[-320:])

    if args.dry_run:
        print('\n[dry-run] 파일은 쓰지 않았습니다.')
        return 0
    with open(MASTER, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('\n%s 를 다시 썼습니다.' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
