#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **필리핀 신규 4개 노선**(세부·마닐라·보홀(팡라오)·클락) 2026.12~2027.01
9주 × 5패턴 45칸씩 180칸 md → `data/master_db.json` 의 `flights` 병합(노선 4개 신설).

읽는 곳:
  · `## 부산(PUS) ↔ 세부(CEB)` 절 머리 — 노선 코드
  · `- 최저 **₩399,713** (2026-12-12 → 2026-12-14, 토~월(2박), 진에어 직항) · 최고 … · 평균 …`
  · `- 최저가가 직항인 조합 45/45 · 경유가 최저가인 조합 0/45`
  · `### 주차 × 패턴 최저가 달력` 표 45칸(달력 값이 상세 표와 같은지 대조)
  · `### 상세 (성인 1인 왕복 총액)` 표 45줄 — 값(가격·날짜·항공사·직항/경유·편 시각)의 원본
  · `## 한눈에 보는 노선별 최저가` 표 — 노선별 최저가·날짜·항공사
  · `### 당일치기(0박 1일) 가능 여부` 표 — 노선별 불가 사유(daytrip 메타 note)

규칙:
  · 값은 원문 그대로. 원문이 말하는 칸 수(180)·노선별 45칸·주차별 45칸·노선별 최저/최고/평균·
    직항 최저 조합 수·주차별 통합 최저가를 파싱 결과와 **전수 대조**한다. 하나라도 다르면 멈춘다.
  · 이미 있는 노선·칸은 건드리지 않는다(중복 금지). 새 노선 4개만 신설한다.
  · 호텔 538곳 · 아코르 · 기존 32개 노선·`noSale`·다른 달 notes 는 **바이트 동일성**으로 보존 확인.
  · `counts`(total · byMonth · holiday · daytrip)·`counts.routes`·`counts.deals` 와
    새 노선의 `daytrip` 메타, 2026-12·2027-01 `notes`(커버리지 문구)를 다시 쓴다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_ph4.py ../data-sources/flights-sea-new8/부산출발-필리핀4노선-세부마닐라보홀클락-12_1월.md --dry-run
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
PATTERNS = ('목~일', '금~일', '토~월', '금~월', '목~월')
WEEKS = ('2026-12-03', '2026-12-10', '2026-12-17', '2026-12-24', '2026-12-31',
         '2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
# 노선 코드 → (도시 이름, 영문 표기, daytrip 메타)
ROUTES = {
    'CEB': ('세부', '', {
        'status': 'no', 'stay': '',
        'note': '부산 직항 최초 도착이 19:00 출발 22:25(진에어)이고 이후는 익일 00:40~00:45 · '
                '귀국 직항은 01:40 한 편뿐이라 같은 날 오전·낮 도착 후 귀국하는 구조가 없음',
        'short': '직항 심야 도착·귀국 01:40'}),
    'MNL': ('마닐라', '', {
        'status': 'no', 'stay': '',
        'note': '부산 직항은 20:40(23:45 도착)·21:30(익일 01:10) 야간 출발뿐 · '
                '오전 경유편(08:45 출발 16:35 도착)에 15:05 필리핀항공 귀국편을 붙이는 조합이 성립하지 않음 · '
                '0박 조회분은 모두 귀국편이 익일 오전 부산 도착',
        'short': '야간 출발·익일 귀국'}),
    'TAG': ('보홀(팡라오)', '', {
        'status': 'no', 'stay': '',
        'note': '출발·귀국 직항이 각 1일 1편(21:05 출발 / 01:45 새벽 귀국)뿐 · '
                '출발일=귀국일(0박) 조회 결과 판매편 0건(2027-01-13 조회)',
        'short': '직항 1일 1편·0박 0건'}),
    'CRK': ('클락', '직항 최저 비쌈', {
        'status': 'no', 'stay': '',
        'note': '출발·귀국 직항이 각 1일 1편(22:05 출발 01:00 도착 / 01:45 귀국)뿐이고 '
                '경유 최단 도착도 09:35 이후라 같은 날 귀국 연결이 성립하지 않음(0박 조회 0건)',
        'short': '직항 1일 1편·0박 0건'}),
}
CELLS_PER_ROUTE = 45
NEW_CELLS = 180
# 12/31 주는 목~일·목~월(12/31 출발)만 12월이고 금~일·토~월·금~월은 2027-01-01·02 출발이다
NEW_BY_MONTH = {'2026-12': 88, '2027-01': 92}

ROW = re.compile(r'^\|\s*(\d+)\s*\|\s*(\d)주\s*\|\s*([월화수목금토일]~[월화수목금토일])\((\d)박\)\s*\|'
                 r'\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d,]+)\s*\|'
                 r'\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|')
CAL_ROW = re.compile(r'^\|\s*(\d)주\s*\|(.+)\|\s*$')
SUM_LINE = re.compile(r'^- 최저 \*\*₩([\d,]+)\*\* \((\d{4}-\d{2}-\d{2}) → (\d{4}-\d{2}-\d{2}), '
                      r'([^,]+), (.+?)\) · 최고 ₩([\d,]+) · 평균 ₩([\d,]+)$')
DIRECT_LINE = re.compile(r'^- 최저가가 직항인 조합 (\d+)/45 · 경유가 최저가인 조합 (\d+)/45$')
TOP_ROW = re.compile(r'^\|\s*부산 ↔ ([^|]+?)\s*\|\s*\*\*₩([\d,]+)\*\*\s*\|\s*(\d{4}-\d{2}-\d{2}) → '
                     r'(\d{4}-\d{2}-\d{2}) \((.+?)\)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|')
WEEKLY_ROW = re.compile(r'^\| (\d)주 \| (\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2}) \| '
                        r'([\d,]+) \| ([^|]+?) \|$')


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def norm_money(text):
    return int(text.replace(',', ''))


def clean_note(text):
    """'₩918,800(진에어 3시간55분)' → '918,800원(진에어 3시간55분)'."""
    return re.sub(r'₩([\d,]+)', r'\1원', text)


def parse(text):
    """→ (routes{code: [deal]}, cal{code: {(week, pattern): price}}, summary{code: (…, …)})."""
    routes, cal, summary, top = {}, {}, {}, {}
    code = None
    for raw in text.splitlines():
        line = raw.rstrip()
        m = re.match(r'^## 부산\(PUS\) ↔ .*\(([A-Z]{3})\)$', line)
        if m:
            code = m.group(1)
            if code not in ROUTES:
                raise SystemExit('예상 밖 노선: %s' % line)
            routes[code] = []
            cal[code] = {}
            continue
        if line.startswith('## '):
            code = None
            continue
        if code:
            m = ROW.match(line)
            if m:
                (_n, week, pat, nights, date, back, price, airline, via, going,
                 ret, memo) = m.groups()
                if int(nights) != (WD[pat[-1]] - WD[pat[0]]) % 7:
                    raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
                if back_date(date, pat) != back:
                    raise SystemExit('귀국일이 패턴과 다릅니다: %s' % line)
                if via not in ('직항', '경유 1회'):
                    raise SystemExit('직항/경유 표기가 예상과 다릅니다: %r' % via)
                note = '%s %s · 오는편 %s' % (via, going, ret)
                if memo:
                    note += ' · ' + clean_note(memo)
                deal = {'date': date, 'back': back, 'pattern': pat,
                        'price': norm_money(price), 'airline': airline,
                        'via': via != '직항', 'note': note}
                alt = re.search(r'직항 최저 ([\d,]+)원', clean_note(memo)) if memo else None
                if alt:
                    deal['alt'] = norm_money(alt.group(1))
                if any(d['date'] == date and d['pattern'] == pat for d in routes[code]):
                    raise SystemExit('%s %s %s 중복' % (code, date, pat))
                routes[code].append(deal)
                continue
            m = CAL_ROW.match(line)
            if m:
                week = m.group(1)
                cells = [c.strip().strip('*').replace(',', '') for c in m.group(2).split('|')]
                cells = [c for c in cells if c]
                if len(cells) != 5:
                    raise SystemExit('달력 줄 칸 수가 5가 아닙니다: %s' % line)
                for pat, val in zip(PATTERNS, cells):
                    if not re.fullmatch(r'\d+', val):
                        raise SystemExit('달력 값이 숫자가 아닙니다: %s' % line)
                    cal[code][(week, pat)] = int(val)
                continue
            m = SUM_LINE.match(line)
            if m:
                summary.setdefault(code, {})['min'] = (
                    norm_money(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5))
                summary[code]['max'] = norm_money(m.group(6))
                summary[code]['avg'] = norm_money(m.group(7))
                continue
            m = DIRECT_LINE.match(line)
            if m:
                summary.setdefault(code, {})['via'] = (int(m.group(1)), int(m.group(2)))
                continue
        m = TOP_ROW.match(line)
        if m:
            city, price, d1, d2, pat, airline, via = m.groups()
            city = city.strip()
            code_top = next(c for c, (name, _e, _d) in ROUTES.items()
                            if name.replace(' ', '') == city.replace(' ', ''))
            pat = pat.split('(')[0]
            top[code_top] = (norm_money(price), d1, d2, pat, airline.strip(), via.strip())
    return routes, cal, summary, top


def checks(text, routes, cal, summary, top):
    bad = []
    if set(routes) != set(ROUTES):
        bad.append('노선 집합이 다릅니다: %s' % sorted(set(routes) ^ set(ROUTES)))
    total = sum(len(v) for v in routes.values())
    if total != NEW_CELLS:
        bad.append('값 %d칸 (기대 %d칸)' % (total, NEW_CELLS))

    for code, (city, _extra, _dt) in ROUTES.items():
        deals = routes.get(code) or []
        s = summary.get(code) or {}
        if len(deals) != CELLS_PER_ROUTE:
            bad.append('%s %d칸 (기대 %d칸)' % (code, len(deals), CELLS_PER_ROUTE))
        prices = [d['price'] for d in deals]
        lo, d1, d2, pat, who = s['min']
        if min(prices) != lo or s['max'] != max(prices):
            bad.append('%s 최저·최고 %s (원문 %s)' % (code, (min(prices), max(prices)),
                                                   (lo, s['max'])))
        avg = int(sum(prices) / len(prices))      # 원문은 평균을 버림해 적는다
        if avg != s['avg']:
            bad.append('%s 평균 %d원 (원문 %d원)' % (code, avg, s['avg']))
        via_cnt = sum(1 for d in deals if d['via'])
        if s['via'] != (len(deals) - via_cnt, via_cnt):
            bad.append('%s 직항·경유 최저 조합 %s (원문 %s)' % (code, (len(deals) - via_cnt, via_cnt),
                                                        s['via']))
        # 최저 칸의 날짜·패턴·항공사가 요약 문장과 같은지
        deal_min = next(d for d in deals if d['price'] == lo)
        if (deal_min['date'], deal_min['back']) != (d1, d2):
            bad.append('%s 최저 칸 날짜 %s (원문 %s → %s)' % (code, deal_min['date'], d1, d2))
        if deal_min['pattern'] != pat.split('(')[0]:
            bad.append('%s 최저 칸 패턴 %s (원문 %s)' % (code, deal_min['pattern'], pat))
        if not who.startswith(deal_min.get('airline') or ''):
            bad.append('%s 최저 칸 항공사 %r (원문 %r)' % (code, deal_min.get('airline'), who))
        # 달력 표 == 상세 표 (패턴마다 출발 요일이 다르다 — 목~일·목~월 목 / 금~일·금~월 금 / 토~월 토)
        for wi, thu in enumerate(WEEKS, 1):
            for pat5 in PATTERNS:
                key = (str(wi), pat5)
                if key not in cal.get(code, {}):
                    bad.append('%s 달력 %s주 %s 없음' % (code, wi, pat5))
                    continue
                out = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(WD[pat5[0]] - WD['목']) % 7)).isoformat()
                hit = [d for d in deals if d['date'] == out and d['pattern'] == pat5]
                if not hit:
                    bad.append('%s %s %s 상세 표에 없음' % (code, out, pat5))
                    continue
                if hit[0]['price'] != cal[code][key]:
                    bad.append('%s %s %s 달력 %d ≠ 상세 %d' % (code, out, pat5,
                                                             cal[code][key], hit[0]['price']))
        # 한눈에 표
        if code not in top:
            bad.append('%s 한눈에 표 없음' % code)
        else:
            price, t1, t2, tpat, tair, tvia = top[code]
            if price != lo or t1 != d1 or t2 != d2 or tpat != pat.split('(')[0]:
                bad.append('%s 한눈에 표 %s (요약 %s)' % (code, top[code], s['min']))

    overall = min((d['price'], c) for c, v in routes.items() for d in v)
    if overall != (333828, 'MNL'):
        bad.append('전체 최저 %s (원문 마닐라 333,828)' % (overall,))
    if '전체에서 가장 싼 조합은 **마닐라 2026-12-17' not in text:
        bad.append('원문 전체 최저 문장을 찾지 못했습니다')
    # 주차별 4노선 통합 최저가 표
    weekly = []
    for raw in text.splitlines():
        m = WEEKLY_ROW.match(raw.strip())
        if m:
            weekly.append(m.groups())
    if len(weekly) != 9:
        bad.append('주차별 통합 최저가 표 %d줄 (기대 9줄)' % len(weekly))
    for wk, a, b, val, who in weekly:
        thu = WEEKS[int(wk) - 1]
        if a != thu:
            bad.append('%s주 시작일 %s (기대 %s)' % (wk, a, thu))
        cells = [d for c, v in routes.items() for d in v if a <= d['date'] <= b]
        mine = min(cells, key=lambda d: d['price'])
        if mine['price'] != norm_money(val):
            bad.append('%s주 통합 최저 %d (원문 %s)' % (wk, mine['price'], val))
        if ROUTES[mine_code := next(c for c in ROUTES if any(
                d is mine for d in routes[c]))][0].split('(')[0] not in who:
            bad.append('%s주 통합 최저 노선 %s (원문 %s)' % (wk, mine_code, who))
        if mine['pattern'] not in who:
            bad.append('%s주 통합 최저 패턴 %s (원문 %s)' % (wk, mine['pattern'], who))
    # 당일치기 불가 표 4줄
    for code, (_city, _e, dt) in ROUTES.items():
        if dt['status'] != 'no' or not dt['note'] or not dt['short']:
            bad.append('%s daytrip 메타가 비었습니다' % code)
    if '4개 노선 모두 **당일치기 불가**' not in text:
        bad.append('원문 당일치기 불가 문장을 찾지 못했습니다')
    return bad


def merge(master, routes):
    fl = master['flights']
    have = {r['code'] for r in fl['routes']}
    dup = have & set(ROUTES)
    if dup:
        raise SystemExit('이미 있는 노선입니다: %s' % sorted(dup))
    for code, (city, extra, dt) in ROUTES.items():
        fl['routes'].append({
            'code': code, 'city': city, 'extra': extra,
            'deals': sorted(routes[code], key=lambda d: (d['date'], WD[d['pattern'][0]])),
            'daytrip': dict(dt),
        })
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
    return fl


def notes_update(fl):
    fl['notes']['2026-12'] = (
        '필리핀 신규 4개 노선(세부·마닐라·보홀(팡라오)·클락)은 12월 5주 × 5패턴 100칸 가운데 12/31 주의 '
        '금~일·토~월·금~월(1/1·1/2 출발)을 뺀 88칸을 실측했습니다(빈칸 0칸). 일본 신규 7개 노선은 12월 5주 × 5패턴 175칸 중 '
        '83칸만 실측했습니다 — 구마모토 23 · 가고시마 23 · 시즈오카 18 · 마쓰야마 5 · 다카마쓰 5 · '
        '미야코지마 5 · 삿포로 4칸이고 나머지는 미조회(—)입니다.')
    fl['notes']['2027-01'] = (
        '필리핀 신규 4개 노선은 1월 4주 × 5패턴 80칸 + 12/31 주의 1/1·1/2 출발 3패턴 12칸 = 92칸을 실측했습니다'
        '(1/28 출발 목~월은 귀국 2027-02-01). '
        '일본 신규 7개 노선은 1/1·1/2 출발 7칸(구마모토·가고시마 2칸씩, 시즈오카 3칸)만 실측했고 '
        '나머지 1월 주차는 미조회(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='필리핀 신규 4개 노선 180칸 md → master_db.json 병합')
    ap.add_argument('md')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    routes, cal, summary, top = parse(text)
    bad = checks(text, routes, cal, summary, top)
    print('  값 %d칸 · 노선 %d개 × 45칸 · 주차 %d주' % (
        sum(len(v) for v in routes.values()), len(routes), len(WEEKS)))
    for code in ROUTES:
        print('    %s %d칸 최저 %s원 ~ 최고 %s원' % (
            code, len(routes[code]), format(min(d['price'] for d in routes[code]), ','),
            format(max(d['price'] for d in routes[code]), ',')))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_total = fl['counts']['total']
    before_by_month = dict(fl['counts']['byMonth'])
    before_other = json.dumps(fl['routes'], ensure_ascii=False, sort_keys=True)
    before_nosale = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)
    before_notes = {k: v for k, v in fl['notes'].items() if k not in ('2026-12', '2027-01')}
    before_patterns = json.dumps(fl['patterns'], ensure_ascii=False)

    fl = merge(master, routes)
    notes_update(fl)

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
    after_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                             ensure_ascii=False, sort_keys=True)
    if after_other != before_other:
        raise SystemExit('기존 32개 노선 데이터가 바뀌었습니다.')
    if json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True) != before_nosale:
        raise SystemExit('판매편 0건 기록이 바뀌었습니다.')
    if {k: v for k, v in fl['notes'].items() if k not in ('2026-12', '2027-01')} != before_notes:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다.')
    if json.dumps(fl['patterns'], ensure_ascii=False) != before_patterns:
        raise SystemExit('패턴 정의가 바뀌었습니다.')

    print('신규 딜 %d건 · 노선 %d개 신설' % (sum(len(routes[c]) for c in ROUTES), len(ROUTES)))
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
