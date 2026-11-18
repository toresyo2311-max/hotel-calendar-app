#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 일본 신규 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)
**2027년 8월 4주 × 5패턴 140칸**을 `data/master_db.json` 의 `flights` 에 병합한다.

원본: `data-sources/flights-jp-new7/부산출발-일본7노선-8월-완결.md`
  · `### 부산–삿포로(신치토세) (CTS) · 20칸 중 20칸 실측 · 최저 573,300원` 절 머리 — 노선 코드·칸 수·최저
  · 그 아래 `- 2027-08-05 · 목~일 · 삿포로(신치토se) · 927,700원 · 이스타항공+JAL · 경유 후쿠오카 총7시간30분 08:55-16:25` 줄(값)
  · 시즈오카 20칸은 `· [미오픈/NA] · 항공편 없음(0건)` — 값이 아니라 예약창 밖(미오픈)이다.
  · `## 주차별 · 노선별 최저가 흐름` 표(4주 × 7노선) · `## 패턴 5종` 표(5패턴 × 6노선) — 파싱 결과와 대조

규칙:
  · 원본이 말하는 140칸(7노선 × 4주 × 5패턴)과 노선별 실측(6개 노선 20칸 · 시즈오카 0칸)을 전수 대조한다.
    하나라도 다르면 멈춘다.
  · 값이 있는 120칸은 **새 칸**이다(2027년 8월 일본 7개 노선에 이미 값·상태가 있으면 멈춘다 — 덮어쓰지 않는다).
  · 시즈오카 20칸은 원본이 "이용 가능한 항공편 없음"(세 구간 조회)으로 적은 그대로,
    값 대신 `noSale` 에 `status: unopened`(예약창 미오픈)로 적는다 — 추정·보간 없음.
  · 값은 원본 그대로(반올림 없음). 항공사·직항/경유·소요시간·경유지만 앱 표기로 옮긴다.
  · 제3자 조회 사이트 이름은 값·note·notes 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 다른 40개 노선 · 다른 달 `notes` · 기존 `noSale` 은
    **바이트 동일성**으로 보존을 확인한다.
  · `counts`(flights.total · byMonth · holiday · daytrip, 최상위 deals)와 2027-08 `notes` 를 다시 쓴다.
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jp_aug27.py --dry-run
    python3 tools/merge_flights_jp_aug27.py
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
MD = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-jp-new7',
                                   '부산출발-일본7노선-8월-완결.md'))

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
JP = ('CTS', 'FSZ', 'KOJ', 'KMJ', 'MYJ', 'TAK', 'MMY')          # 원본 절 순서
CITY = {'KMJ': '구마모토', 'KOJ': '가고시마', 'FSZ': '시즈오카', 'MYJ': '마쓰야마',
        'TAK': '다카마쓰', 'MMY': '미야코지마', 'CTS': '삿포로'}
CITY_MD = {'CTS': '삿포로(신치토세)', 'FSZ': '시즈오카', 'KOJ': '가고시마', 'KMJ': '구마모토',
           'MYJ': '마쓰야마', 'TAK': '다카마쓰', 'MMY': '미야코지마'}
WK = ('목~일', '금~일', '토~월', '목~월', '금~월')
PAT_ORDER = ('목~월', '목~일', '금~월', '금~일', '토~월')
WEEKS = tuple((datetime.date(2027, 8, 5) + datetime.timedelta(days=7 * i)).isoformat()
              for i in range(4))
NIGHTS = {p: (WD[p[-1]] - WD[p[0]]) % 7 for p in WK}
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '네이버',
          '구글', 'Google', '플라이트')
SRC_TAG = re.compile(r'\s*\[출처:[^\]]*\]\s*$')

# 원본이 스스로 적은 노선별 집계 — (값, 예약창 밖, 최저, 최고, 직항이 최저가인 칸)
EXPECT = {
    'CTS': (20, 0, 573300, 928700, 16),
    'FSZ': (0, 20, None, None, 0),
    'KOJ': (20, 0, 589100, 2358600, 0),
    'KMJ': (20, 0, 738100, 2110300, 11),
    'MYJ': (20, 0, 627800, 868100, 0),
    'TAK': (20, 0, 712900, 1304000, 0),
    'MMY': (20, 0, 603800, 2605000, 0),
}
# 원본 '주차별 · 노선별 최저가 흐름' (천원) — 4주
EXPECT_WEEK = {
    'CTS': (927, 873, 574, 573), 'KOJ': (706, 814, 589, 595),
    'MYJ': (677, 752, 628, 677), 'TAK': (914, 984, 713, 994),
    'KMJ': (988, 880, 778, 738), 'MMY': (1288, 804, 604, 799),
}
# 원본 '패턴 5종' 표 (천원) — WK 순서
EXPECT_PAT = {
    'CTS': (601, 600, 574, 573, 574), 'KOJ': (599, 635, 589, 595, 619),
    'MYJ': (677, 717, 665, 628, 667), 'TAK': (1008, 783, 741, 984, 713),
    'KMJ': (866, 1049, 899, 744, 738), 'MMY': (825, 815, 604, 624, 799),
}
# 원본이 콕 집어 적은 칸(봉우리·최저) — 날짜가 밀리면 여기서 걸린다
EXPECT_CELL = {
    ('CTS', '2027-08-26', '목~월'): 573300,
    ('CTS', '2027-08-21', '토~월'): 573900,
    ('KOJ', '2027-08-21', '토~월'): 589100,
    ('KOJ', '2027-08-14', '토~월'): 2358600,
    ('KMJ', '2027-08-27', '금~월'): 738100,
    ('KMJ', '2027-08-13', '금~월'): 2110300,
    ('MYJ', '2027-08-19', '목~월'): 627800,
    ('TAK', '2027-08-20', '금~월'): 712900,
    ('MMY', '2027-08-21', '토~월'): 603800,
    ('MMY', '2027-08-13', '금~일'): 2605000,
}
EXPECT_TOTAL = 140
EXPECT_PRICED = sum(v[0] for v in EXPECT.values())        # 120
EXPECT_UNOPENED = sum(v[1] for v in EXPECT.values())      # 20

HEAD = re.compile(r'^### 부산–(.+?) \(([A-Z]{3})\) · (\d+)칸 중 (\d+)칸 실측 · 최저 (.+)$')
HEAD_NO_LOW = re.compile(r'^### 부산–(.+?) \(([A-Z]{3})\) · (\d+)칸 중 (\d+)칸 실측 · .*$')
CELL = re.compile(r'^- (2027-\d\d-\d\d) · ([월화수목금토일]~[월화수목금토일]) · (.+?) · (.+)$')


def back_of(date, pattern):
    return (datetime.date.fromisoformat(date) + datetime.timedelta(days=NIGHTS[pattern])).isoformat()


def norm_dur(text):
    t = text.strip()
    m = re.match(r'^(\d+)시간\s*(\d*)\s*분?$', t)
    if m:
        return '%s시간%s' % (int(m.group(1)),
                            (' %d분' % int(m.group(2))) if m.group(2) and int(m.group(2)) else '')
    m = re.match(r'^(\d+)\s*시간$', t)
    return '%s시간' % int(m.group(1)) if m else t


def norm_times(text):
    t = text.strip()
    m = re.match(r'^(\d\d:\d\d)-\+(\d) (\d\d:\d\d)$', t)
    if m:
        return '%s-%s+%s' % (m.group(1), m.group(3), m.group(2))
    return t


def clean(text):
    return re.sub(r'\s+', ' ', SRC_TAG.sub('', text or '')).strip()


def parse_cell(value, airline, detail):
    """'- 2027-08-05 · 목~일 · 삿포로 · 927,700원 · 이스타항공+JAL · 경유 후쿠오카 총7시간30분 08:55-16:25'"""
    if value in ('[미오픈/NA]', '미오픈/NA') or '미오픈' in value:
        return {'kind': 'unopened'}
    m = re.match(r'^([\d,]+)원$', value)
    if not m:
        raise SystemExit('금액 칸을 읽지 못했습니다: %r' % value)
    price = int(m.group(1).replace(',', ''))
    air = re.sub(r'\(LCC\)', '', clean(airline)).replace(', ', '+')
    d = clean(detail)
    direct = d.startswith('직항')
    if direct:
        m2 = re.match(r'^직항 (?P<dur>[^ ]+) (?P<times>.+)$', d)
        if not m2:
            raise SystemExit('직항 편성을 읽지 못했습니다: %s' % d)
        note = '직항 %s · %s' % (norm_times(m2.group('times')), norm_dur(m2.group('dur')))
    else:
        m2 = re.match(r'^경유 (?P<via>.+?) 총(?P<dur>[^ ]+) (?P<times>.+)$', d)
        if not m2:
            raise SystemExit('경유 편성을 읽지 못했습니다: %s' % d)
        note = '경유 %s · 총 %s · %s' % (m2.group('via'), norm_dur(m2.group('dur')),
                                        norm_times(m2.group('times')))
    return {'kind': 'price', 'price': price, 'airline': air, 'via': not direct, 'note': note}


def parse(text):
    cells, heads, order = {}, {}, []
    code = None
    for raw in text.splitlines():
        line = raw.strip()
        m = HEAD.match(line)
        if not m:
            m2 = HEAD_NO_LOW.match(line)
            if m2:
                city, code, total, got = m2.groups()
                low = '—'
                m = m2
        if m:
            city, code, total, got, low = (m.groups() if len(m.groups()) == 5
                                           else tuple(m.groups()) + ('—',))
            if code not in JP:
                raise SystemExit('예상 밖 노선: %s' % line)
            if city != CITY_MD[code]:
                raise SystemExit('도시 이름이 다릅니다: %s (기대 %s)' % (city, CITY_MD[code]))
            low_n = None if not low.endswith('원') else int(low.replace(',', '').replace('원', ''))
            heads[code] = (int(total), int(got), low_n)
            order.append(code)
            continue
        if line.startswith('##') or (line.startswith('#') and not line.startswith('###')):
            code = None
            continue
        if not code:
            continue
        m = CELL.match(line)
        if not m:
            continue
        date, pattern, city, rest = m.groups()
        if pattern not in WK:
            raise SystemExit('예상 밖 패턴: %s' % line)
        if city != CITY_MD[code]:
            raise SystemExit('%s 줄의 도시가 다릅니다: %s' % (code, line))
        parts = [x.strip() for x in rest.split(' · ')]
        value = parts[0]
        airline = parts[1] if len(parts) > 1 else ''
        detail = ' · '.join(parts[2:]) if len(parts) > 2 else ''
        rec = parse_cell(value, airline, detail)
        rec.update(date=date, pattern=pattern)
        key = (date, pattern)
        if key in cells.setdefault(code, {}):
            raise SystemExit('%s %s %s 중복' % (code, date, pattern))
        cells[code][key] = rec
    if tuple(order) != JP:
        raise SystemExit('노선 순서가 다릅니다: %s' % (order,))
    for code in JP:
        mine = cells[code]
        total, got, low = heads[code]
        if total != 20 or len(mine) != 20:
            raise SystemExit('%s %d칸 (기대 20칸)' % (code, len(mine)))
        priced = [v for v in mine.values() if v['kind'] == 'price']
        unopened = [v for v in mine.values() if v['kind'] == 'unopened']
        if (len(priced), len(unopened)) != (got, 20 - got):
            raise SystemExit('%s 값 %d · 미오픈 %d (원본 %d / %d)'
                             % (code, len(priced), len(unopened), got, 20 - got))
        if (len(priced), len(unopened)) != EXPECT[code][:2]:
            raise SystemExit('%s 집계 %s (원본 %s)' % (code, (len(priced), len(unopened)),
                                                       EXPECT[code][:2]))
        if priced:
            vals = [v['price'] for v in priced]
            if (min(vals), max(vals)) != EXPECT[code][2:4]:
                raise SystemExit('%s 최저·최고 %s (원본 %s)'
                                 % (code, (min(vals), max(vals)), EXPECT[code][2:4]))
            if low is not None and min(vals) != low:
                raise SystemExit('%s 절 머리 최저 %s (파싱 %s)' % (code, low, min(vals)))
            direct = sum(1 for v in priced if v['via'] is False)
            if direct != EXPECT[code][4]:
                raise SystemExit('%s 직항이 최저가인 칸 %d (원본 %d)' % (code, direct, EXPECT[code][4]))
        for thu in WEEKS:
            for pat in WK:
                dt = (datetime.date.fromisoformat(thu) + datetime.timedelta(days=WD[pat[0]] - 4)).isoformat()
                if (dt, pat) not in mine:
                    raise SystemExit('%s %s %s 칸이 없습니다' % (code, dt, pat))
        if code in EXPECT_WEEK:
            for i, thu in enumerate(WEEKS):
                ps = [v['price'] for (d, p), v in mine.items()
                      if v['kind'] == 'price'
                      and (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(thu)).days // 7 == 0]
                got_k = (min(ps) + 500) // 1000 if ps else None
                if got_k != EXPECT_WEEK[code][i]:
                    raise SystemExit('%s %d주차 최저 %s천 (원본 %s천)'
                                     % (code, i + 1, got_k, EXPECT_WEEK[code][i]))
        if code in EXPECT_PAT:
            for i, pat in enumerate(WK):
                ps = [v['price'] for (d, p), v in mine.items()
                      if p == pat and v['kind'] == 'price']
                got_k = (min(ps) + 500) // 1000 if ps else None
                if got_k != EXPECT_PAT[code][i]:
                    raise SystemExit('%s %s 최저 %s천 (원본 %s천)'
                                     % (code, pat, got_k, EXPECT_PAT[code][i]))
    for (code, date, pat), want in EXPECT_CELL.items():
        hit = cells[code].get((date, pat))
        if not hit or hit.get('price') != want:
            raise SystemExit('칸 %s %s %s 가 %s원이 아닙니다 (%s)' % (code, date, pat, want, hit))
    total = sum(len(v) for v in cells.values())
    if total != EXPECT_TOTAL:
        raise SystemExit('전체 %d칸 (기대 %d칸)' % (total, EXPECT_TOTAL))
    for word in BANNED:
        if word in json.dumps({c: list(v.values()) for c, v in cells.items()},
                              ensure_ascii=False):
            raise SystemExit('값에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    return cells


def make_deal(rec):
    deal = {'date': rec['date'], 'back': back_of(rec['date'], rec['pattern']),
            'pattern': rec['pattern'], 'price': rec['price']}
    if rec.get('airline'):
        deal['airline'] = rec['airline']
    deal['via'] = rec['via']
    deal['note'] = rec['note']
    return deal


def sort_key(deal):
    return (deal['date'], PAT_ORDER.index(deal['pattern']) if deal['pattern'] in PAT_ORDER else 9)


def august_note(existing, cells):
    priced = sum(1 for c in JP for v in cells[c].values() if v['kind'] == 'price')
    unopened = sum(1 for c in JP for v in cells[c].values() if v['kind'] == 'unopened')
    lows = {}
    for c in JP:
        ps = [(v['price'], v['date'], v['pattern'], v['note'], v['via'])
              for v in cells[c].values() if v['kind'] == 'price']
        if ps:
            lows[c] = min(ps)
    seq = sorted(((v[0], c) for c, v in lows.items()))
    text = ' · '.join('%s %s %s %s원(%s)' % (CITY[c], lows[c][1], lows[c][2],
                                            format(lows[c][0], ','), lows[c][3]) for _p, c in seq)
    extra = (
        ' 일본 7개 노선(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)은 2027년 8월 '
        '목요일 기준 4주 × 5패턴 140칸을 조회해 %d칸이 값으로 차고 시즈오카 %d칸은 항공편 0건으로 '
        '예약창 밖(미오픈)입니다(추정 없음). 노선별 최저는 %s 순이고, 8/13~16 오봉 주간이 봉우리입니다 — '
        '가고시마 8/14~16 토~월 2,358,600원(베이징·도쿄 2회 경유) · 미야코지마 8/13~15 금~일 2,605,000원 · '
        '구마모토 8/13~16 금~월 2,110,300원으로, 오봉이 끝난 8/19 이후와 3~4배 차이가 납니다. '
        '최저가가 직항인 칸은 27칸으로 전부 삿포로(16)와 구마모토(11)이고, 가고시마·마쓰야마·다카마쓰·'
        '미야코지마는 부산 직항이 없어 최저가가 모두 경유입니다.'
        % (priced, unopened, text)
    )
    for word in BANNED:
        if word in extra:
            raise SystemExit('note 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    return (existing.rstrip() + extra).strip()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ④ 항공 일본 7노선 2027년 8월 — 4주 × 5패턴 140칸(값 120 + 시즈오카 미오픈 20), '
        '최저 삿포로 8/26~30 573,300원(직항), 총 7,607→7,727건'))
    args = ap.parse_args(argv)

    cells = parse(open(MD, encoding='utf-8').read())
    master = json.load(open(MASTER, encoding='utf-8'))
    merged = copy.deepcopy(master)
    routes = {r['code']: r for r in merged['flights']['routes']}
    old_routes = {r['code']: r for r in master['flights']['routes']}
    old_marks = master['flights']['noSale']

    added = collections.Counter()
    marks = []
    for code in JP:
        r = routes[code]
        existing = {(d['date'], d['pattern']) for d in r['deals']}
        if any(s[:7] == '2027-08' for s, _ in existing):
            raise SystemExit('%s 에 이미 2027년 8월 값이 있습니다 — 덮어쓰지 않습니다' % code)
        if any(n.get('code') == code and n.get('date', '')[:7] == '2027-08' for n in old_marks):
            raise SystemExit('%s 에 이미 2027년 8월 상태 기록이 있습니다' % code)
        new = [make_deal(v) for v in cells[code].values() if v['kind'] == 'price']
        for deal in sorted(new, key=sort_key):
            pos = sum(1 for x in r['deals'] if x['date'] < deal['date'])
            r['deals'].insert(pos, deal)
        added[code] = len(new)
        for (d, p), v in sorted(cells[code].items()):
            if v['kind'] != 'unopened':
                continue
            marks.append({'code': code, 'date': d, 'back': back_of(d, p), 'pattern': p,
                          'status': 'unopened',
                          'note': '예약창 밖(2027년 하계 시즌 스케줄 미게시) — 조회 결과 이용 가능한 항공편 0건'})
    if sum(added.values()) != EXPECT_PRICED:
        raise SystemExit('추가 칸 %d (기대 %d)' % (sum(added.values()), EXPECT_PRICED))
    if len(marks) != EXPECT_UNOPENED:
        raise SystemExit('미오픈 칸 %d (기대 %d)' % (len(marks), EXPECT_UNOPENED))
    merged['flights']['noSale'] = old_marks + sorted(
        marks, key=lambda n: (n['code'], n['date'], PAT_ORDER.index(n['pattern'])))

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
            raise SystemExit('%s 칸 수가 맞지 않습니다 (%d → %d)' % (code, len(before), len(after)))
    for n in merged['flights']['noSale']:
        if n not in old_marks and n not in marks:
            raise SystemExit('noSale 에 예고 없는 기록이 생겼습니다: %s' % n)
    blob = json.dumps([d for c in JP for d in new_routes[c]['deals']
                       if d['date'][:7] == '2027-08'], ensure_ascii=False) + \
        json.dumps(marks, ensure_ascii=False)
    for word in BANNED:
        if word in blob:
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
    if counts['byMonth']['2027-08'] != old_counts['byMonth']['2027-08'] + EXPECT_PRICED:
        raise SystemExit('2027-08 건수 %s' % counts['byMonth']['2027-08'])
    if counts['holiday'] != old_counts['holiday'] or counts['daytrip'] != old_counts['daytrip']:
        raise SystemExit('연휴/당일치기 수가 달라졌습니다')
    for m, n in old_counts['byMonth'].items():
        if m != '2027-08' and counts['byMonth'][m] != n:
            raise SystemExit('%s 건수가 달라졌습니다 (%s → %s)' % (m, n, counts['byMonth'][m]))
    merged['flights']['counts'] = counts
    merged['counts'] = dict(master['counts'])
    merged['counts']['deals'] = counts['total']

    # ── notes · extended ──────────────────────────────────────
    notes = dict(master['flights']['notes'])
    if '2027-08' not in notes:
        raise SystemExit('2027-08 notes 가 없습니다')
    notes['2027-08'] = august_note(notes['2027-08'], cells)
    merged['flights']['notes'] = notes
    for word in BANNED:
        if word in args.note:
            raise SystemExit('extended 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    merged['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')

    print('노선별 추가:', dict(added), '합계', sum(added.values()))
    print('미오픈(시즈오카):', len(marks))
    print('counts:', json.dumps(counts, ensure_ascii=False))
    print('note tail:', notes['2027-08'][-420:])
    if args.dry_run:
        print('\n[dry-run] 파일은 쓰지 않았습니다.')
        for code in JP:
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
