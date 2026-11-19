#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **A조 12개 노선의 2027년 7월 잔여 3주(7/15~19 · 7/22~26 · 7/29~8/2)
5패턴 180칸** 가운데 빈칸 134칸 실측 + 재확인 1칸을 `data/master_db.json` 의 `flights` 에 병합한다.

원본 1개(5번 보고서 `0-2027-07-groupA-rest.csv` + `1-2027-07-groupA-rest.md`,
2026-11-19 21:07 ~ 2026-11-20 00:40 KST 실측) — 성인 1인 왕복 총액(유류·세금 포함, KRW).

  · 노선 12개: 후쿠오카·오사카·도쿄·타이베이·홍콩·마카오·상하이·방콕·다낭·나트랑·난징·호찌민
  · 칸 135줄(CSV): route, week, pattern, dep, ret, nights, price_krw, airline, direct_or_via,
    via_city, duration, times, status, note
  · 12노선 × 5패턴 × 3주 = 180칸 가운데 **134칸은 웹앱에 없던 빈칸**, 1칸(후쿠오카 7/30~8/1
    금~일)은 앱에 있던 447,100원을 다시 조회한 값(325,800원), 나머지 45칸은 앞선 가격표 조사분
    (편성 미확인 자리표시)이 그대로 있다. 0박 당일치기 2칸(후쿠오카 7/30 금~금 · 오사카 7/16 금~금)은
    이번 조사 범위 밖이라 손대지 않는다.

규칙:
  · `via` 는 그 칸 **최저가 편성**이 직항(`false`)·경유(`true`)인지로 적는다.
  · `note` 는 기존 앱 표기(`경유(서울 11시간 50분) · 총 16시간 45분 (21:15-13:00+1)`,
    `직항 2시간 15분 (09:20-11:35)`) 꼴로 적고, 공항 터미널(나리타·타오위안 T1 등) ·
    `잔여 9석 미만` · `최저가가 경유편` 을 덧붙인다.
  · 원본이 '직항 최저 …원'을 적어 준 칸은 `alt` 에 직항 금액을 넣는다(최저가가 경유일 때만).
  · 원본 CSV 의 실측 시각(`2026-11-19 21:08 KST 실측`)은 값이 아니라 조사 시각이므로 note 에 넣지 않는다.
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · ⑥ 땡처리 · 출처 목록 · 패턴 정의 · 다른 노선/기존 딜·`noSale` 은
    값 대조로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-07 `notes` 끝에 이번 병합
    문장을 덧붙인다(plain text — `**` 금지). `extended` 끝에 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_groupA_jul.py --dry-run
    python3 tools/merge_flights_groupA_jul.py
"""
import argparse
import collections
import csv
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
CSV_DEFAULT = os.path.normpath(os.path.join(
    ROOT, '..', 'memory', 'clones', 'f0ee2d96-jin_5', 'pickle', '2026-11-19-2200',
    'received', '0-2027-07-groupA-rest.csv'))

WD = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}   # datetime.weekday()
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN')
CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'TPE': '타이베이', 'HKG': '홍콩',
        'MFM': '마카오', 'PVG': '상하이', 'BKK': '방콕', 'DAD': '다낭', 'CXR': '나트랑',
        'NKG': '난징', 'SGN': '호찌민'}
MONTH = '2027-07'
GRID_START, GRID_END = '2027-07-15', '2027-07-31'
WEEK_THU = ('2027-07-15', '2027-07-22', '2027-07-29')
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver', '아고다', '부킹', '호텔스컴바인', '마이리얼트립', '야놀자', '여기어때')
TERMINALS = ('나리타', '타오위안 T1', '푸동 T1', '루커우 T1', '루커우 T2',
             '깜라인 T2', '떤선녓 T2', '떤선녓 T3')

# 원본 보고서(1-2027-07-groupA-rest.md)의 집계 — 파서가 같은 숫자를 내는지 대조한다
EXPECT_CELLS = 135
EXPECT_NEW = 134
EXPECT_REPLACED = 1
EXPECT_GRID = 180
EXPECT_PLACEHOLDER = 46        # 병합 전 이 세 주에 남아 있던 가격표 자리표시(5패턴)
EXPECT_LEFT = 45               # 병합 뒤 남는 자리표시(교체 1칸)
EXPECT_OVERALL = (300500, 913300)
EXPECT_SUM = 76340300
EXPECT_PAT_SUM = {'금~일': 16638800, '토~월': 12810700, '목~일': 17032600,
                  '금~월': 13704500, '목~월': 16153700}
EXPECT_PAT_CELLS = {'금~일': 30, '토~월': 22, '목~일': 30, '금~월': 24, '목~월': 29}
EXPECT_DIRECT = 60
EXPECT_ALT = 6
EXPECT_THIN = 5
# 노선: (칸수, 최저, 최고, 평균(내림), 최저가가 직항인 칸)
EXPECT_ROUTE = {
    'FUK': (11, 300500, 398400, 333018, 11), 'KIX': (11, 479000, 592000, 557027, 7),
    'TYO': (10, 482200, 587400, 543610, 9), 'TPE': (7, 408500, 534600, 497428, 7),
    'HKG': (9, 396900, 505100, 468966, 9), 'MFM': (13, 700100, 913300, 802153, 0),
    'PVG': (14, 359800, 552100, 475550, 9), 'BKK': (14, 429000, 681200, 569471, 0),
    'DAD': (14, 493800, 712300, 605435, 0), 'CXR': (9, 516800, 743800, 644177, 8),
    'NKG': (13, 508000, 661500, 584023, 0), 'SGN': (10, 484400, 720800, 648670, 0),
}


def norm_dur(text):
    """'9시간 5분' → '9시간 05분', '1시간' → '1시간', '50분' → '50분'."""
    text = text.strip()
    m = re.fullmatch(r'(\d+)\s*시간(?:\s*(\d+)\s*분)?', text)
    if m:
        return m.group(1) + '시간' + ((' ' + m.group(2).rjust(2, '0') + '분')
                                     if m.group(2) else '')
    m = re.fullmatch(r'(\d+)\s*분', text)
    if m:
        return m.group(1).rjust(2, '0') + '분'
    raise SystemExit('소요시간 형식 이상: %r' % text)


def build_note(row):
    """CSV 한 줄 → (note, via, alt, thin)."""
    kind = row['direct_or_via']
    times = row['times'].strip()
    dur = row['duration'].strip()
    alt = thin = None
    extras = []
    if kind == '직항':
        note = '직항 ' + norm_dur(dur) + ' (' + times + ')'
        via = False
    elif kind == '경유':
        via = True
        body = dur.split('·')[0].strip()             # '총 6시간(환승 1시간)·도착 13:00' 대응
        m = re.fullmatch(r'총\s*(.+?)(?:\((.*)\))?', body)
        if not m:
            raise SystemExit('경유 소요시간을 읽지 못했습니다: %r' % dur)
        total, inner = m.group(1).strip(), (m.group(2) or '').strip()
        lay = hopdur = ''
        if inner.startswith('환승'):
            lay = norm_dur(inner[2:])
        elif inner:
            hm = re.fullmatch(r'(\S+)\s*(.+)', inner)
            if not hm:
                raise SystemExit('환승 문장을 읽지 못했습니다: %r' % inner)
            lay, hopdur = hm.group(1), norm_dur(hm.group(2))
        hops = [h.strip() for h in row['via_city'].replace('(2회)', '').split('·') if h.strip()]
        hops = [h.replace('(인천)', '').replace('호찌민시', '호찌민') for h in hops]
        if hopdur:                      # '제주 14시간 40분' — 도시는 hops[0], 환승 시간만 붙인다
            if len(hops) != 1 or hops[0] != lay.replace('호찌민시', '호찌민'):
                raise SystemExit('경유지-환승 표기가 어긋납니다: %r / %r' % (row['via_city'], inner))
            lay, hopdur = hopdur, ''
        if not hops:
            raise SystemExit('경유지가 없습니다: %r' % row)
        # 앱이 note 의 '환승 N시간' 을 읽어 장시간 경유 배지(12h+ · 20h+)를 계산하므로
        # 구 표기(`경유 1회(서울) · 환승 3시간 20분 · 총 6시간 10분 (…)`)를 쓴다.
        note = '경유 %d회(%s)' % (len(hops), '·'.join(hops))
        if lay:
            note += ' · 환승 ' + lay
        note += ' · 총 ' + norm_dur(total) + ' (' + times + ')'
    else:
        raise SystemExit('편성 표기를 읽지 못했습니다: %r' % kind)

    pieces = [p.strip() for p in row['note'].split(' · ')]
    head = pieces[0]
    if re.match(r'^2026-11-(?:19|20) \d\d:\d\d KST (재확인 )?실측', head):
        pieces = pieces[1:]
        amt = re.search(r'앱 기입력 ([\d,]+)원 → 재실측 ([\d,]+)원', head)
        if amt:
            old, new = (int(x.replace(',', '')) for x in amt.groups())
            if new != int(row['price_krw']):
                raise SystemExit('재확인 칸의 새 금액이 CSV 와 다릅니다: %s %s'
                                 % (row['dep'], row['note']))
            if old != 447100:
                raise SystemExit('재확인 칸의 앱 기입력 금액이 다릅니다: %s' % row['note'])
    else:
        raise SystemExit('실측 시각 표기를 읽지 못했습니다: %r' % head)

    for p in pieces:
        if p in TERMINALS:
            extras.append(p)
        elif p == '홍콩익스프레스 운항':
            extras.append(p)
        elif p == '잔여 9석 미만':
            thin = True
        elif p.startswith('직항 최저 '):
            got = re.search(r'([\d,]+)원', p)
            if not got:
                raise SystemExit('직항 최저 금액을 읽지 못했습니다: %r' % p)
            alt = int(got.group(1).replace(',', ''))
        elif p == '직항 최저':
            pass                      # 최저가 자체가 직항인 칸 — 병기할 직항 금액 없음
        elif p == '최저가가 경유편':
            extras.append(p)
        else:
            raise SystemExit('%s 처리하지 못한 비고: %r' % (row['dep'], p))

    if via and alt is not None and alt <= int(row['price_krw']):
        raise SystemExit('%s 직항 금액이 최저가보다 싸거나 같습니다' % row['dep'])
    if not via and alt is not None:
        raise SystemExit('%s 직항인데 직항 금액이 붙었습니다' % row['dep'])
    if alt is not None:
        extras.append('직항 금액 ' + format(alt, ',') + '원')
    if thin:
        extras.append('잔여 9석 미만')
    if extras:
        note += ' · ' + ' · '.join(extras)
    return note, via, alt, bool(thin)


def parse(path):
    if not os.path.isfile(path):
        raise SystemExit('원본 CSV 가 없습니다: %s' % path)
    cells = {}
    with open(path, encoding='utf-8-sig', newline='') as fp:
        for row in csv.DictReader(fp):
            if row['status'] != '값':
                raise SystemExit('%s 상태가 값이 아닙니다: %r' % (row['dep'], row['status']))
            code = row['route'].strip()
            if code not in ROUTES:
                raise SystemExit('알 수 없는 노선 %s' % code)
            pat = row['pattern'].strip()
            if pat not in PAT_NIGHTS:
                raise SystemExit('%s 알 수 없는 패턴 %r' % (code, pat))
            date = datetime.date.fromisoformat(row['dep'])
            back = datetime.date.fromisoformat(row['ret'])
            nights = int(row['nights'])
            if PAT_NIGHTS[pat] != nights:
                raise SystemExit('%s %s 박수 불일치: %s' % (code, row['dep'], row['nights']))
            if (back - date).days != nights:
                raise SystemExit('%s 출발·귀국 간격이 박수와 다릅니다: %s' % (code, row))
            if WD[pat[0]] != date.weekday() or WD[pat[-1]] != back.weekday():
                raise SystemExit('%s 요일 불일치: %s %s' % (code, row['dep'], pat))
            if not (GRID_START <= row['dep'] <= GRID_END):
                raise SystemExit('%s 출발일이 이번 범위 밖: %s' % (code, row['dep']))
            price = int(row['price_krw'])
            if price <= 0:
                raise SystemExit('%s 금액이 양의 정수가 아닙니다' % code)
            note, via, alt, thin = build_note(row)
            if '**' in note or '[' in note or '출처' in note:
                raise SystemExit('%s note 에 마크업이 있습니다: %r' % (code, note))
            if via and '총' not in note:
                raise SystemExit('%s 경유 칸에 총 소요시간이 없습니다: %r' % (code, note))
            if not via and '직항' not in note:
                raise SystemExit('%s 직항 칸 note 이상: %r' % (code, note))
            for word in BANNED:
                if word in note or word in row['airline']:
                    raise SystemExit('%s 값에 제3자 사이트 이름(%s)이 있습니다' % (code, word))
            key = (code, row['dep'], pat)
            if key in cells:
                raise SystemExit('중복 칸 %s %s %s' % key)
            cells[key] = dict(code=code, date=row['dep'], back=row['ret'], pattern=pat,
                              price=price, airline=row['airline'].strip() or None, via=via,
                              alt=alt, thin=thin, note=note)
    return cells


def check(cells):
    if len(cells) != EXPECT_CELLS:
        raise SystemExit('%d칸 (기대 %d칸)' % (len(cells), EXPECT_CELLS))
    codes = {k[0] for k in cells}
    if codes != set(ROUTES):
        raise SystemExit('노선이 12개가 아닙니다: %s' % sorted(codes))
    ps = [c['price'] for c in cells.values()]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('최저·최고 %s (원문 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    if sum(ps) != EXPECT_SUM:
        raise SystemExit('금액 합 %d (원문 %d)' % (sum(ps), EXPECT_SUM))
    for pat, want in EXPECT_PAT_SUM.items():
        v = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if len(v) != EXPECT_PAT_CELLS[pat]:
            raise SystemExit('%s %d칸 (원문 %d칸)' % (pat, len(v), EXPECT_PAT_CELLS[pat]))
        if sum(v) != want:
            raise SystemExit('%s 합 %d (원문 %d)' % (pat, sum(v), want))
    direct = sum(1 for c in cells.values() if c['via'] is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (원문 %d)' % (direct, EXPECT_DIRECT))
    if sum(1 for c in cells.values() if c['alt']) != EXPECT_ALT:
        raise SystemExit('직항 금액 병기 %d칸 (원문 %d칸)'
                         % (sum(1 for c in cells.values() if c['alt']), EXPECT_ALT))
    if sum(1 for c in cells.values() if c['thin']) != EXPECT_THIN:
        raise SystemExit('잔여 9석 미만 %d칸 (원문 %d칸)'
                         % (sum(1 for c in cells.values() if c['thin']), EXPECT_THIN))
    for code in ROUTES:
        v = [c for k, c in cells.items() if k[0] == code]
        prices = [c['price'] for c in v]
        got = (len(v), min(prices), max(prices), sum(prices) // len(prices),
               sum(1 for c in v if c['via'] is False))
        if got != EXPECT_ROUTE[code]:
            raise SystemExit('%s 집계 %s (원문 %s)' % (code, got, EXPECT_ROUTE[code]))
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


def span(d):
    return '%d/%d~%d/%d' % (int(d['date'][5:7]), int(d['date'][8:10]),
                            int(d['back'][5:7]), int(d['back'][8:10]))


def main(argv):
    ap = argparse.ArgumentParser(description='A조 12노선 2027년 7월 3~5주 180칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--csv', default=CSV_DEFAULT)
    ap.add_argument('--note', default=None)
    args = ap.parse_args(argv)

    cells = check(parse(args.csv))
    print('파싱 %d칸 — 최저 %s · 최고 %s · 직항이 최저인 칸 %d · 경유 %d · 잔여 9석 미만 %d · 직항 금액 병기 %d'
          % (len(cells), format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ','),
             sum(1 for c in cells.values() if c['via'] is False),
             sum(1 for c in cells.values() if c['via'] is True),
             sum(1 for c in cells.values() if c['thin']),
             sum(1 for c in cells.values() if c['alt'])))

    master = json.load(open(MASTER, encoding='utf-8'))
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다' % code)

    frozen = {k: json.dumps(master.get(k), ensure_ascii=False, sort_keys=True)
              for k in ('hotels', 'accor', 'sources', 'window', 'built', 'voucherExpiry',
                        'schema', 'version', 'ttang')}
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    deals_before = {c: json.loads(json.dumps(routes[c]['deals'])) for c in ROUTES}
    daytrip_before = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    other_before = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_jul = fl['counts']['byMonth'][MONTH]
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])
    before_weeks = json.dumps(fl['weeks'], ensure_ascii=False)

    # 이 세 주에 남아 있는 기존 칸 — 5패턴은 앞선 가격표 자리표시(편성 미확인), 0박은 범위 밖
    placeholders, skipped, unexpected = {}, [], []
    for code in ROUTES:
        for d in routes[code]['deals']:
            if not (GRID_START <= d['date'] <= '2027-08-02'):
                continue
            if d['pattern'] not in PAT_NIGHTS:
                skipped.append((code, d['date'], d['pattern']))
                continue
            if d.get('src') != '가격표' or d.get('note') != '가격표 실측 · 직항/경유 미확인':
                unexpected.append((code, d, 'note'))
                continue
            placeholders[(code, d['date'], d['pattern'])] = d
    if unexpected:
        raise SystemExit('이 범위에 예상 밖의 기존 칸: %s'
                         % [(c, d['date'], d['pattern']) for c, d, _ in unexpected])
    if len(placeholders) != EXPECT_PLACEHOLDER:
        raise SystemExit('자리표시 칸 %d개 (기대 %d개): %s'
                         % (len(placeholders), EXPECT_PLACEHOLDER, sorted(placeholders)))
    replaced_keys = set(cells) & set(placeholders)
    if len(replaced_keys) != EXPECT_REPLACED:
        raise SystemExit('교체할 칸 %d개 (기대 %d개): %s'
                         % (len(replaced_keys), EXPECT_REPLACED, sorted(replaced_keys)))
    new_keys = set(cells) - replaced_keys
    if len(new_keys) != EXPECT_NEW:
        raise SystemExit('새 칸 %d개 (기대 %d개)' % (len(new_keys), EXPECT_NEW))
    print('자리표시 %d칸 가운데 %d칸 교체 · 새 칸 %d칸 추가 · 0박 칸 %d개는 그대로: %s'
          % (len(placeholders), len(replaced_keys), len(new_keys), len(skipped),
             [(c, d) for c, d, p in skipped]))

    def make(v, pattern):
        deal = collections.OrderedDict()
        deal['date'] = v['date']
        deal['back'] = v['back']
        deal['pattern'] = pattern
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt']:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        return json.loads(json.dumps(deal))

    replaced = []
    for key in sorted(replaced_keys):
        code, date, pat = key
        old = placeholders[key]
        deals = routes[code]['deals']
        idx = next(i for i, d in enumerate(deals) if (d['date'], d['pattern']) == (date, pat))
        deals[idx] = make(cells[key], pat)
        replaced.append((code, date, pat, old['price'], cells[key]['price']))

    added = []
    for key in sorted(new_keys):
        code, date, pat = key
        routes[code]['deals'].append(make(cells[key], pat))
        added.append(key)
    for code in ROUTES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))
        for d in routes[code]['deals']:
            for word in BANNED:
                if word in json.dumps(d, ensure_ascii=False):
                    raise SystemExit('%s %s 값에 제3자 사이트 이름(%s)이 있습니다'
                                     % (code, d['date'], word))

    counts = recount(fl)
    if counts['total'] != before_total + len(added):
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], before_total + len(added)))
    if counts['byMonth'][MONTH] != before_jul + len(added):
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                 before_jul + len(added)))

    grid = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if GRID_START <= d['date'] <= GRID_END
            and d['pattern'] in PAT_NIGHTS]
    if len(grid) != EXPECT_GRID:
        raise SystemExit('이 세 주 5패턴 칸 %d칸 (기대 %d칸)' % (len(grid), EXPECT_GRID))
    measured = [d for d in grid if d.get('via') is not None]
    if len(measured) != EXPECT_CELLS:
        raise SystemExit('실측 칸 %d칸 (기대 %d칸)' % (len(measured), EXPECT_CELLS))
    left = [d for d in grid if d.get('via') is None]
    if len(left) != EXPECT_LEFT:
        raise SystemExit('남은 자리표시 칸 %d칸 (기대 %d칸)' % (len(left), EXPECT_LEFT))

    lo = min(measured, key=lambda d: d['price'])
    hi = max(measured, key=lambda d: d['price'])
    pats = collections.defaultdict(list)
    for d in measured:
        pats[d['pattern']].append(d['price'])
    pat_avg = sorted(((p, sum(v) // len(v)) for p, v in pats.items()), key=lambda kv: kv[1])
    direct = sum(1 for d in measured if d.get('via') is False)
    thin = sum(1 for d in measured if '잔여 9석 미만' in (d.get('note') or ''))
    alt = sum(1 for d in measured if d.get('alt'))
    avg = sum(d['price'] for d in measured) // len(measured)
    nodirect = [c for c in ROUTES
                if not any(d.get('via') is False for d in measured if d['code'] == c)]
    withalt = sorted({d['code'] for d in measured if d.get('alt')})

    month_sent = (
        '2027년 7월 3~5주차(7/15~19 · 7/22~26 · 7/29~8/2)는 부산 출발 12개 노선(후쿠오카·오사카·도쿄·'
        '타이베이·홍콩·마카오·상하이·방콕·다낭·나트랑·난징·호찌민) 5패턴 180칸이 모두 값으로 찼습니다 — '
        '이번에 빈칸 134칸을 실측하고, 앱에 이미 있던 후쿠오카 7/30~8/1 금~일 447,100원은 다시 조회해 '
        '325,800원으로 바꿨습니다. 이 세 주 최저는 후쿠오카 7/22~26 목~월 '
        + format(lo['price'], ',') + '원(' + (lo['airline'] or '항공사 미확인') + ' 직항 1시간, 18:00-19:00)이고, '
        '최고는 마카오 7/23~25 금~일 ' + format(hi['price'], ',') + '원(' + (hi['airline'] or '항공사 미확인')
        + ', 서울 11시간 50분 환승 · 총 16시간 45분)입니다. 이번 실측 135칸 평균은 '
        + format(avg, ',') + '원이고 패턴 평균은 '
        + ' < '.join(CITY and ('%s %s원' % (p, format(v, ','))) for p, v in pat_avg)
        + ' 순입니다. 최저가가 직항인 칸은 ' + str(direct) + '칸이고, '
        + '·'.join(CITY[c] for c in nodirect)
        + ' ' + str(len(nodirect)) + '개 노선은 실측분 모두 최저가가 경유입니다. '
        + ('·'.join(CITY[c] for c in withalt) + ' ' + str(alt)
           + '칸은 직항이 있어도 최저가가 경유라 직항 금액을 함께 적었습니다. ' if alt else '')
        + '잔여 9석 미만으로 표시된 칸은 ' + str(thin) + '칸입니다. '
        '남은 45칸은 앞선 가격표 조사분(편성 미확인)이 그대로 있고, 0박 당일치기 2칸'
        '(후쿠오카 7/30 · 오사카 7/16)은 이번 조사 범위 밖입니다.')
    if '**' in month_sent:
        raise SystemExit('notes 문장에 마크다운 별표가 있습니다')
    for word in BANNED:
        if word in month_sent:
            raise SystemExit('notes 문장에 제3자 사이트 이름(%s)이 있습니다' % word)
    fl['notes'][MONTH] = fl['notes'][MONTH].rstrip() + ' ' + month_sent

    for key, old in frozen.items():
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != old:
            raise SystemExit('%s 가 바뀌었습니다' % key)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다')
    if json.dumps(fl['weeks'], ensure_ascii=False) != before_weeks:
        raise SystemExit('주차 정의가 바뀌었습니다')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('noSale 이 바뀌었습니다')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != other_before:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다')
    for code in ROUTES:
        old = deals_before[code]
        cur = routes[code]['deals']
        want = len(old) + sum(1 for k in new_keys if k[0] == code)
        if len(cur) != want:
            raise SystemExit('%s 딜 %d건 (기존 %d + 이번 %d)' % (code, len(cur), len(old),
                                                              want - len(old)))
        have = {(d['date'], d['pattern']): d for d in cur}
        if len(have) != len(cur):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for o in old:
            got = have.get((o['date'], o['pattern']))
            if got is None:
                raise SystemExit('%s 기존 딜이 사라졌습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
            if (code, o['date'], o['pattern']) in replaced_keys:
                continue
            if json.dumps(got, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(o, ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 기존 딜이 바뀌었습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
        keys = [(d['date'], WD[d['pattern'][0]]) for d in cur]
        if keys != sorted(keys):
            raise SystemExit('%s 딜 정렬이 깨졌습니다' % code)
        if json.dumps(routes[code]['daytrip'], ensure_ascii=False) != daytrip_before[code]:
            raise SystemExit('%s 당일치기 요약이 바뀌었습니다' % code)
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')
    for word in BANNED:
        if word in json.dumps(fl['notes'], ensure_ascii=False):
            raise SystemExit('notes 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    note = args.note or (
        '2026-11-19 KST ⑤ 항공 부산 출발 A조 12개 노선 2027년 7월 3~5주차'
        '(7/15~19 · 7/22~26 · 7/29~8/2) 5패턴 180칸 완결 — 빈칸 134칸 실측 + '
        '재확인 1칸(후쿠오카 7/30~8/1 447,100→325,800원), 최저 후쿠오카 7/22~26 목~월 '
        '300,500원(트리니티항공 직항), 직항이 최저가인 칸 60, 가격표 자리표시 1칸 교체, '
        '총 %s→%s건' % (format(before_total, ','), format(counts['total'], ',')))
    master['extended'] = (before_extended + ' / ' + note).strip(' /')

    print('교체 %d칸(%s → %s원) · 신규 %d칸' % (len(replaced),
                                              format(replaced[0][3], ','),
                                              format(replaced[0][4], ','), len(added)))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'],
             counts['daytrip']))
    print('2027-07 %d → %d건' % (before_jul, counts['byMonth'][MONTH]))
    print('notes[2027-07] 새 문장:', month_sent)
    print('extended 추가:', note)

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
