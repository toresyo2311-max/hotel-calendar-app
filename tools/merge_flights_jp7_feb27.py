#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 일본 신규 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)
**2027년 2월 5패턴 140칸 보완본**을 `data/master_db.json` 의 `flights` 에 병합한다.

원본: `data-sources/flights-jp-new7/부산출발-일본7노선-2월-5번보완.md`
  · `### 부산–구마모토 (KMJ) · 20칸 중 20칸 실측 · 최저 280,600원` 절 머리 — 노선 코드·실측 칸 수·최저
  · 그 아래 `- 2027-02-04 · 목~일 · 구마모토 · 328,200원 · 이스타항공 · 직항 11:55-13:25` 줄(값)
  · `· 미확인` 줄은 값이 아니다 — 건너뛴다. `· **항공편 없음**(조회 결과 0건)` 줄은 판매편 0건.
  · `## 먼저 결론 — 노선별 2월 최저`·`## 2027년 2월 달력` — 파싱한 노선별·주차별 최저와 대조

규칙(기존 실측을 잃지 않는 방향으로만 보강):
  · 원문이 말하는 칸 수(7노선 × 4주 × 5패턴 = 140칸)와 노선별 실측 칸(20·20·20·20·12·14·20),
    판매편 0건 7칸(미야코지마 6 · 가고시마 1), 미확인 7칸(미야코지마 2 · 가고시마 5)을 전수 대조한다.
    하나라도 다르면 멈춘다.
  · **빈칸(값도 상태도 없던 칸)**: 새 값을 넣는다 — 7칸.
  · **판매편 0건이던 칸**: 새 값이 잡혔으면 그 값으로 바꾸고 `noSale` 기록을 지운다 — 7칸(미야코지마).
  · **이미 값이 있는 칸**: 새 값이 더 쌀 때만 갱신한다(더 비싼 새 값으로 덮어써 손실을 내지 않는다) — 73칸.
    새 값에 항공사·직항 표기가 없으면(가격표 값) 기존의 항공사·직항 표기를 잃으므로, 그 차이가
    **2만원 이상**일 때만 갈아끼운다(원문도 같은 날짜 조회 편차를 5천~3만원으로 적었다). 2만원 미만
    19칸은 기존의 항공사·직항 표기가 붙은 값을 그대로 둔다.
  · 새 값이 더 비싼 20칸과, 새 조회가 `미확인`/`항공편 없음`이던 14칸(기존 값 10칸 + 원래 빈칸 4칸)은
    기존 값을 지우지 않는다.
  · 값은 원문 그대로(반올림 없음). 항공사 이름·직항/경유·소요시간만 앱 표기로 옮긴다.
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 다른 40개 노선 · 다른 달 `notes` · 나머지 `noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(flights.total · byMonth · holiday · daytrip, 최상위 deals)와 2027-02 `notes` 를 다시 쓴다.
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jp7_feb27.py --dry-run
    python3 tools/merge_flights_jp7_feb27.py
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
    ROOT, '..', '..', 'data-sources', 'flights-jp-new7', '부산출발-일본7노선-2월-5번보완.md'))

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
JP = ('KMJ', 'TAK', 'MYJ', 'FSZ', 'MMY', 'KOJ', 'CTS')
CITY = {'KMJ': '구마모토', 'KOJ': '가고시마', 'FSZ': '시즈오카', 'MYJ': '마쓰야마',
        'TAK': '다카마쓰', 'MMY': '미야코지마(시모지시마)', 'CTS': '삿포로(신치토세)'}
WK = ('목~일', '금~일', '토~월', '목~월', '금~월')
PAT_ORDER = ('목~월', '목~일', '금~월', '금~일', '토~월')   # DB 안의 2월 칸 정렬 순서
WEEKS = tuple((datetime.date(2027, 2, 4) + datetime.timedelta(days=7 * i)).isoformat()
              for i in range(4))
MARGIN = 20000        # 항공사 표기가 없는 새 값이 기존을 갈아끼우려면 필요한 최소 차액

# 원문이 말하는 값 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT_CELLS = {'KMJ': 20, 'TAK': 20, 'MYJ': 20, 'FSZ': 20, 'MMY': 20, 'KOJ': 20, 'CTS': 20}
EXPECT_PRICED = {'KMJ': 20, 'TAK': 20, 'MYJ': 20, 'FSZ': 20, 'MMY': 12, 'KOJ': 14, 'CTS': 20}
EXPECT_NOSALE = {'MMY': 6, 'KOJ': 1}
EXPECT_UNKNOWN = {'MMY': 2, 'KOJ': 5}
EXPECT_LOW = {'KMJ': (280600, '2027-02-13', '토~월'), 'TAK': (229900, '2027-02-11', '목~월'),
              'MYJ': (284900, '2027-02-11', '목~월'), 'FSZ': (275100, '2027-02-04', '목~일'),
              'MMY': (385500, '2027-02-11', '목~일'), 'KOJ': (530300, '2027-02-19', '금~일'),
              'CTS': (433000, '2027-02-25', '목~월')}
EXPECT_WEEK_LOW = {'2027-02-04': (275100, 'FSZ'), '2027-02-11': (229900, 'TAK'),
                   '2027-02-18': (259200, 'TAK'), '2027-02-25': (376300, 'KMJ')}
# 병합 결과 — 손대는 칸 수
EXPECT_FILL = 7            # 빈칸 → 값
EXPECT_FROM_NOSALE = 7     # 판매편 0건 → 값
EXPECT_REPLACE = 73        # 더 싼 최신 실측으로 갱신
EXPECT_KEEP_SMALL = 19     # 더 싸지만 항공사 표기 없는 2만원 미만 차이 — 기존 유지
EXPECT_KEEP_HIGHER = 20    # 새 값이 더 비쌈 — 기존 유지
EXPECT_KEEP_NO_NEW = 10    # 새 조회 미확인/항공편 없음 — 기존 값 유지(나머지 4칸은 원래도 빈칸)
EXPECT_ADDED = EXPECT_FILL + EXPECT_FROM_NOSALE          # 14
EXPECT_DEALS_TOTAL = 523 + EXPECT_ADDED                  # 일본 7노선 2~6월 537칸
EXPECT_NOSALE_LEFT = 303 - EXPECT_FROM_NOSALE            # 296칸
EXPECT_BLANK_LEFT = 105 - EXPECT_FILL                    # 98칸
EXPECT_FEB_STATE = (144, 22, 8, 22)   # 2027-02 196칸 — 실측/0건/미공개/미조회
# 병합 뒤 일본 7노선 2027-02~06 — 노선 → (값 칸, 최저, 최고, 직항이 최저가인 칸)
EXPECT_JP26_AFTER = {
    'KMJ': (43, 280600, 1028300, 7), 'KOJ': (107, 508800, 1600600, 4),
    'FSZ': (35, 274400, 1421100, 11), 'MYJ': (73, 271700, 3074400, 35),
    'TAK': (105, 226400, 2322200, 14), 'MMY': (31, 385500, 2888100, 0),
    'CTS': (143, 374303, 1144600, 38)}
EXPECT_NEW_ROUTE_DEALS = {'KMJ': 95, 'KOJ': 152, 'FSZ': 85, 'MYJ': 118,
                          'TAK': 154, 'MMY': 76, 'CTS': 191}
EXPECT_TOP_DEALS = 6959 + EXPECT_ADDED                  # 6,973
EXPECT_FEB_MONTH_DEALS = 921 + EXPECT_ADDED              # 935
EXPECT_WEEKEND_DEALS = 6641 + EXPECT_ADDED               # 6,655

HEAD = re.compile(r'^### 부산–(.+?) \(([A-Z]{3})\) · (\d+)칸 중 (\d+)칸 실측 · 최저 ([\d,]+)원$')
CELL = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · (.+?) · (.+)$')
SRC = re.compile(r'\s*\[출처:[^\]]*\]\s*$')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '네이버', '구글')


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def clean_note(rec):
    if not rec.get('carrier'):
        return '가격표 실측 · 직항/경유 미확인'
    det = (rec.get('detail') or '').strip()
    det = re.sub(r'\s*,\s*', ' · ', det)
    det = re.sub(r'(\d+)시간(\d+)분', r'\1시간 \2분', det)
    det = re.sub(r'총\s*(\d)', r'총 \1', det)
    return det


def parse_cell(value):
    value = SRC.sub('', value)
    if value.startswith('**항공편 없음**'):
        return {'kind': 'nosale'}
    if value.startswith('미확인'):
        return {'kind': 'unknown'}
    m = re.match(r'^([\d,]+)원(?:\s*·\s*(.+))?$', value)
    if not m:
        raise SystemExit('금액 줄을 읽지 못했습니다: %s' % value)
    rec = {'kind': 'price', 'price': int(m.group(1).replace(',', '')),
           'carrier': None, 'via': None, 'detail': None}
    tail = m.group(2) or ''
    parts = [p.strip() for p in tail.split('·')] if tail else []
    if parts and parts[0] != '항공사 미확인(가격표 실측)':
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
            if code not in JP or CITY[code] != city:
                raise SystemExit('예상 밖 노선: %s' % line)
            heads[code] = (city, int(total), int(got), int(low.replace(',', '')))
            order.append(code)
            continue
        if line.startswith('#'):
            code = None
            continue
        if code:
            m = CELL.match(line)
            if not m:
                continue
            date, pat, _city, value = m.groups()
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
    for code in JP:
        mine = cells[code]
        if len(mine) != EXPECT_CELLS[code]:
            raise SystemExit('%s %d칸 (기대 %d칸)' % (code, len(mine), EXPECT_CELLS[code]))
        priced = {k for k, v in mine.items() if v['kind'] == 'price'}
        if len(priced) != EXPECT_PRICED[code]:
            raise SystemExit('%s 실측 %d칸 (기대 %d칸)' % (code, len(priced), EXPECT_PRICED[code]))
        if sum(1 for v in mine.values() if v['kind'] == 'nosale') != EXPECT_NOSALE.get(code, 0):
            raise SystemExit('%s 항공편 없음 칸 수가 다릅니다' % code)
        if sum(1 for v in mine.values() if v['kind'] == 'unknown') != EXPECT_UNKNOWN.get(code, 0):
            raise SystemExit('%s 미확인 칸 수가 다릅니다' % code)
        # 실측 칸은 4주(목요일 기준) 안에 있어야 한다
        for date, pat in priced:
            if (datetime.date.fromisoformat(date) -
                    datetime.date.fromisoformat(WEEKS[0])).days // 7 not in range(4):
                raise SystemExit('%s %s 가 2월 4주 밖입니다' % (code, date))
        low = min((v['price'], k) for k, v in mine.items() if v['kind'] == 'price')
        want = EXPECT_LOW[code]
        if (low[0], low[1][0], low[1][1]) != want:
            raise SystemExit('%s 최저 %s (원문 %s)' % (code, low, want))
        if heads[code][3] != want[0]:
            raise SystemExit('%s 절 머리 최저가가 다릅니다: %s' % (code, heads[code][3]))
        if heads[code][2] != EXPECT_PRICED[code]:
            raise SystemExit('%s 절 머리 실측 칸 수가 다릅니다' % code)
    # 주차별 최저 — 원문 달력 표와 대조
    for week, (want_price, want_code) in EXPECT_WEEK_LOW.items():
        best = None
        for code in JP:
            for pat in WK:
                dt = (datetime.date.fromisoformat(week) +
                      datetime.timedelta(days=(WD[pat[0]] - 4) % 7)).isoformat()
                rec = cells[code].get((dt, pat))
                if rec and rec['kind'] == 'price':
                    if best is None or rec['price'] < best[0]:
                        best = (rec['price'], code)
        if best != (want_price, want_code):
            raise SystemExit('%s 주차 최저 %s (원문 %s)' % (week, best, (want_price, want_code)))
    return cells


def plan(master, cells):
    routes = {r['code']: r for r in master['flights']['routes']}
    nosale = {(n.get('code'), n.get('date'), n.get('pattern')): n
              for n in master['flights']['noSale']}
    deals = {c: list(routes[c]['deals']) for c in JP}
    actions = {'fill': [], 'from_nosale': [], 'replace': [], 'keep_small': [],
               'keep_higher': [], 'keep_no_new': []}
    for code in JP:
        idx = {(d['date'], d['pattern']): i for i, d in enumerate(deals[code])}
        for key in sorted(cells[code]):
            rec = cells[code][key]
            i = idx.get(key)
            old = deals[code][i] if i is not None else None
            mark = nosale.get((code, key[0], key[1]))
            if rec['kind'] != 'price':
                if old:
                    actions['keep_no_new'].append((code, key, old['price'], rec['kind']))
                continue
            if old:
                if rec['price'] >= old['price']:
                    actions['keep_higher'].append((code, key, old['price'], rec['price']))
                elif rec['carrier'] or old['price'] - rec['price'] >= MARGIN:
                    actions['replace'].append((code, key, old['price'], rec['price'], rec['carrier']))
                else:
                    actions['keep_small'].append((code, key, old['price'], rec['price']))
            elif mark:
                actions['from_nosale'].append((code, key, None, rec['price'], rec['carrier']))
            else:
                actions['fill'].append((code, key, None, rec['price'], rec['carrier']))
    return deals, actions


def make_deal(rec, back):
    deal = {'date': rec['date'], 'back': back, 'pattern': rec['pattern'], 'price': rec['price']}
    if rec.get('carrier'):
        deal['airline'] = rec['carrier']
        deal['via'] = rec['via']
    else:
        deal['via'] = None
        deal['src'] = '가격표'
    deal['note'] = clean_note(rec)
    return deal


def sort_key(deal):
    return (deal['date'], PAT_ORDER.index(deal['pattern']) if deal['pattern'] in PAT_ORDER else 9)


def apply_plan(master, cells, deals, actions):
    merged = copy.deepcopy(master)
    routes = {r['code']: r for r in merged['flights']['routes']}
    by_route = {}
    for code in JP:
        lst = deals[code]
        idx = {(d['date'], d['pattern']): i for i, d in enumerate(lst)}
        for action in ('replace',):
            for c, key, _old, new, _carrier in actions[action]:
                if c != code:
                    continue
                i = idx[key]
                old = lst[i]
                lst[i] = make_deal(cells[code][key], old['back'])
        added = []
        for action in ('fill', 'from_nosale'):
            for c, key, _old, _new, _carrier in actions[action]:
                if c != code:
                    continue
                deal = make_deal(cells[code][key], back_date(key[0], key[1]))
                added.append(deal)
        for deal in sorted(added, key=sort_key):
            pos = 0
            for j, cur in enumerate(lst):
                if '2027-02-01' <= cur['date'] <= '2027-02-28' and sort_key(cur) < sort_key(deal):
                    pos = j + 1
            if pos == 0:
                raise SystemExit('%s %s 삽입 위치를 찾지 못했습니다' % (code, deal['date']))
            lst.insert(pos, deal)
        by_route[code] = lst
        routes[code]['deals'] = lst
    # 판매편 0건이던 칸 가운데 값이 잡힌 칸은 noSale 기록을 지운다
    filled = {(c, k[0], k[1]) for c, k, *_ in actions['from_nosale']}
    merged['flights']['noSale'] = [n for n in merged['flights']['noSale']
                                   if (n.get('code'), n.get('date'), n.get('pattern')) not in filled]
    return merged, by_route


def counts_of(master):
    routes = master['flights']['routes']
    deals = [d for r in routes for d in r['deals']]
    by_month = collections.Counter(d['date'][:7] for d in deals)
    return {
        'total': len(deals),
        'byMonth': {m: by_month.get(m, 0) for m in master['flights']['months']},
        'holiday': sum(1 for d in deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in deals if d['pattern'].split('~')[0] == d['pattern'].split('~')[-1]),
    }


def feb_state(master):
    """일본 7노선 2027-02 196칸(4주 × 7패턴) 상태 — (실측, 0건, 미공개, 미조회)."""
    routes = {r['code']: r for r in master['flights']['routes']}
    pats = WK + ('토~토', '일~일')
    grid = {(c, (datetime.date.fromisoformat(w) +
                 datetime.timedelta(days=(WD[p[0]] - 4) % 7)).isoformat(), p)
            for c in JP for w in WEEKS for p in pats}
    deals = {(c, d['date'], d['pattern']) for c in JP for d in routes[c]['deals']
             if '2027-02-01' <= d['date'] <= '2027-02-29'}
    marks = {(n.get('code'), n.get('date'), n.get('pattern')): (n.get('status') or 'nosale')
             for n in master['flights']['noSale'] if n.get('code') in JP}
    nosale = {k for k, st in marks.items() if st == 'nosale' and k in grid and k not in deals}
    nofare = {k for k, st in marks.items() if st == 'nofare' and k in grid and k not in deals}
    blank = grid - deals - nosale - nofare
    if deals & (nosale | nofare):
        raise SystemExit('2027-02 상태가 겹칩니다: %s' % sorted(deals & (nosale | nofare))[:4])
    return len(deals), len(nosale), len(nofare), len(blank)


def jp26_stats(master):
    routes = {r['code']: r for r in master['flights']['routes']}
    out = {}
    for code in JP:
        got = [d for d in routes[code]['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30']
        vals = [d['price'] for d in got]
        out[code] = (len(got), min(vals), max(vals),
                     sum(1 for d in got if d.get('via') is False))
    return out


def jp26_status(master):
    routes = {r['code']: r for r in master['flights']['routes']}
    pats = WK + ('토~토', '일~일')
    weeks = [(datetime.date(2027, 2, 4) + datetime.timedelta(days=7 * i)).isoformat()
             for i in range(21)]
    grid = {(c, (datetime.date.fromisoformat(w) +
                 datetime.timedelta(days=(WD[p[0]] - 4) % 7)).isoformat(), p)
            for c in JP for w in weeks for p in pats}
    deals = {(c, d['date'], d['pattern']) for c in JP for d in routes[c]['deals']
             if '2027-02-01' <= d['date'] <= '2027-06-30'}
    marks = {(n.get('code'), n.get('date'), n.get('pattern')): (n.get('status') or 'nosale')
             for n in master['flights']['noSale'] if n.get('code') in JP}
    out = {}
    for code in JP:
        for part, group in (('주말형', WK), ('당일치기', ('토~토', '일~일'))):
            mine = [k for k in grid if k[0] == code and k[2] in group]
            ns = {k for k in mine if marks.get(k) == 'nosale' and k not in deals}
            nf = {k for k in mine if marks.get(k) == 'nofare' and k not in deals}
            bl = set(mine) - deals - ns - nf
            out.setdefault(code, {})[part] = (len([k for k in mine if k in deals]),
                                              len(ns), len(nf), len(bl))
    return out


def feb_note(stats, state):
    deals, nosale, nofare, blank = state
    return (
        '일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)의 2027년 2월 4주 × 5패턴 '
        '140칸을 다시 조회해 보강했습니다 — 주말형 140칸이 값 136칸 + 항공편 없음 4칸으로 100% 찼습니다. '
        '빈칸이던 7칸(다카마쓰 2/5 금~월·금~일, 시즈오카 2/5 금~월·2/6 토~월, 가고시마 2/5 금~월·금~일·2/6 토~월)을 '
        '값으로 채우고, 판매편 0건이던 미야코지마 7칸에도 값이 잡혔습니다. 값이 있던 122칸 가운데 73칸은 새 조회가 '
        '더 싸서 갱신했습니다 — 구마모토 20칸이 서울 경유 52만~101만원에서 28만~72만원으로 '
        '내려갔고(그중 7칸은 이스타항공 직항으로 확인), 삿포로 2/25~3/1 목~월은 667,376원에서 '
        '433,000원(제주항공 직항)이 됐습니다. 더 비싼 새 값 20칸, '
        '차이가 2만원 미만이면서 새 값에 항공사 표기가 없는 19칸, 새 조회에서 값이 없던 14칸은 기존 값을 그대로 '
        '두었습니다(추정·삭제 없음). 이 달 196칸 기준으로는 실측 {}칸 · 판매편 0건 {}칸 · 요금 미공개 {}칸 · '
        '미조회 {}칸입니다. 주말형 최저는 다카마쓰 2/11~15 목~월 236,400원(에어부산 직항)이고 다음이 '
        '다카마쓰 2/13~15 토~월 246,400원 · 시즈오카 2/4~7 목~일 274,400원(에어부산 직항) · '
        '구마모토 2/13~15 토~월 280,600원(이스타항공 직항)입니다. 2월 1주차는 설 연휴(2/6~2/9)와 겹쳐 '
        '2박 조합이 2·3주차의 1.6~2.2배이고, 4주차는 구마모토 2/25~28 목~일 376,300원이 가장 쌉니다. '
        '당일치기 최저는 삿포로 2/28 일~일 630,600원(진에어 직항)입니다.'
        .format(deals, nosale, nofare, blank))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-18 KST ④ 항공 일본 7노선 2027년 2월 보완 — 2월 주말형 140칸 재조회로 빈칸 7칸 + '
        '판매편 0건 7칸을 값으로 채우고 더 싼 최신 실측 73칸 갱신(주말형 값 136 + 항공편 없음 4로 완결), '
        '총 6,959→6,973건(주말형 6,641→6,655)'))
    args = ap.parse_args(argv)

    text = open(MD, encoding='utf-8').read()
    cells = parse(text)
    master = json.load(open(MASTER, encoding='utf-8'))
    deals, actions = plan(master, cells)

    got = {k: len(v) for k, v in actions.items()}
    want = {'fill': EXPECT_FILL, 'from_nosale': EXPECT_FROM_NOSALE, 'replace': EXPECT_REPLACE,
            'keep_small': EXPECT_KEEP_SMALL, 'keep_higher': EXPECT_KEEP_HIGHER,
            'keep_no_new': EXPECT_KEEP_NO_NEW}
    if sum(got.values()) + 4 != 140:
        raise SystemExit('140칸이 아닙니다: %s' % got)
    print('계획:', json.dumps(got, ensure_ascii=False))
    if got != want:
        raise SystemExit('손대는 칸 수가 기대와 다릅니다: %s' % got)

    merged, by_route = apply_plan(master, cells, deals, actions)

    # ── 보존 확인 ──────────────────────────────────────────────
    for key in ('schema', 'version', 'window', 'built', 'voucherExpiry', 'sources',
                'accor', 'hotels'):
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != \
                json.dumps(merged.get(key), ensure_ascii=False, sort_keys=True):
            raise SystemExit('%s 가 달라졌습니다' % key)
    old_routes = {r['code']: r for r in master['flights']['routes']}
    new_routes = {r['code']: r for r in merged['flights']['routes']}
    if list(old_routes) != list(new_routes):
        raise SystemExit('노선 목록이 달라졌습니다')
    touched = {(c, k[0], k[1]) for c, k, *_ in
               (actions['replace'] + actions['fill'] + actions['from_nosale'])}
    for code, old in old_routes.items():
        if code in JP:
            continue
        if json.dumps(old, ensure_ascii=False, sort_keys=True) != \
                json.dumps(new_routes[code], ensure_ascii=False, sort_keys=True):
            raise SystemExit('%s 노선이 달라졌습니다' % code)
    for code in JP:
        before = {(d['date'], d['pattern']): d for d in old_routes[code]['deals']}
        after = {(d['date'], d['pattern']): d for d in new_routes[code]['deals']}
        for key, deal in before.items():
            if (code, key[0], key[1]) in touched:
                continue
            if after.get(key) != deal:
                raise SystemExit('%s %s 칸이 예고 없이 달라졌습니다' % (code, key))
        if len(after) != len(before) + len([1 for c, *_ in
                                            actions['fill'] + actions['from_nosale'] if c == code]):
            raise SystemExit('%s 칸 수가 맞지 않습니다' % code)
        for deal in new_routes[code]['deals']:
            if (code, deal['date'], deal['pattern']) in touched:
                for word in BANNED:
                    if word in json.dumps(deal, ensure_ascii=False):
                        raise SystemExit('%s %s 값에 제3자 사이트 이름이 들어갔습니다'
                                         % (code, deal['date']))
    old_marks = [n for n in master['flights']['noSale']]
    new_marks = [n for n in merged['flights']['noSale']]
    if len(new_marks) != len(old_marks) - EXPECT_FROM_NOSALE:
        raise SystemExit('noSale 기록 수가 맞지 않습니다')
    for n in new_marks:
        if n not in old_marks:
            raise SystemExit('noSale 에 새 기록이 생겼습니다: %s' % n)
    for n in old_marks:
        if n not in new_marks and (n.get('code'), n.get('date'), n.get('pattern')) not in \
                {(c, k[0], k[1]) for c, k, *_ in actions['from_nosale']}:
            raise SystemExit('noSale 기록이 예고 없이 지워졌습니다: %s' % n)

    # ── counts·stats ───────────────────────────────────────────
    counts = counts_of(merged)
    if counts['total'] != EXPECT_TOP_DEALS:
        raise SystemExit('총 건수 %s (기대 %s)' % (counts['total'], EXPECT_TOP_DEALS))
    if counts['byMonth']['2027-02'] != EXPECT_FEB_MONTH_DEALS:
        raise SystemExit('2027-02 건수 %s' % counts['byMonth']['2027-02'])
    if counts['holiday'] != 185:
        raise SystemExit('연휴 칸 %s (기대 185)' % counts['holiday'])
    if counts['daytrip'] != 318:
        raise SystemExit('당일치기 %s (기대 318)' % counts['daytrip'])
    merged['flights']['counts'] = counts
    merged['counts'] = dict(master['counts'])
    merged['counts']['deals'] = counts['total']

    stats = jp26_stats(merged)
    if stats != EXPECT_JP26_AFTER:
        raise SystemExit('일본 7노선 2~6월 통계가 다릅니다: %s' % stats)
    status = jp26_status(merged)
    state = feb_state(merged)
    if state != EXPECT_FEB_STATE:
        raise SystemExit('2027-02 상태 %s (기대 %s)' % (state, EXPECT_FEB_STATE))
    deals_sum = sum(v[0] for v in stats.values())
    ns_left = sum(p[1] for v in status.values() for p in v.values())
    nf_left = sum(p[2] for v in status.values() for p in v.values())
    bl_left = sum(p[3] for v in status.values() for p in v.values())
    if deals_sum != EXPECT_DEALS_TOTAL:
        raise SystemExit('일본 7노선 실측 합계 %d (기대 %d)' % (deals_sum, EXPECT_DEALS_TOTAL))
    if (ns_left, nf_left, bl_left) != (EXPECT_NOSALE_LEFT, 98, EXPECT_BLANK_LEFT):
        raise SystemExit('일본 7노선 상태 합계 %s' % ((ns_left, nf_left, bl_left),))
    for code, n in EXPECT_NEW_ROUTE_DEALS.items():
        got_n = len(new_routes[code]['deals'])
        if got_n != n:
            raise SystemExit('%s 딜 %d건 (기대 %d건)' % (code, got_n, n))

    merged['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')
    for word in BANNED:
        if word in args.note:
            raise SystemExit('extended 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    note = feb_note(stats, state)
    merged['flights']['notes'] = dict(master['flights']['notes'])
    merged['flights']['notes']['2027-02'] = note
    if not note.startswith('일본 7개 노선'):
        raise SystemExit('note 형식이 다릅니다')
    for word in BANNED:
        if word in note:
            raise SystemExit('note 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    print('2027-02 상태 (실측/0건/미공개/미조회):', state)
    print('일본 7노선 2~6월:', json.dumps(stats, ensure_ascii=False))
    print('주말형/당일치기 상태:', json.dumps(status, ensure_ascii=False))
    print('갱신 73칸 예시:', [(c, k[0], k[1], o, n) for c, k, o, n, _ in actions['replace'][:5]])
    print('빈칸→값:', [(c, k[0], k[1], n) for c, k, _o, n, _ in actions['fill']])
    print('0건→값:', [(c, k[0], k[1], n) for c, k, _o, n, _ in actions['from_nosale']])
    print('기존 유지(2만원 미만·항공사 미표기):',
          [(c, k[0], k[1], o, n) for c, k, o, n in actions['keep_small']])
    print('counts:', json.dumps(counts, ensure_ascii=False))
    print('note:', note)

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
