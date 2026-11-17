#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **동남아 신규 4개 노선**(푸꾸옥·코타키나발루·쿠알라룸푸르·비엔티안)
2026.12~2027.01 9주 × 5패턴 **178칸**(비엔티안 2칸은 가격 미제공) md → `data/master_db.json` 병합.

읽는 곳:
  · `## 1. 부산 ↔ 푸꾸옥(PQC)` 절 머리 — 노선 코드
  · `기간 내 최저 **388,393원** / 최고 **662,826원** / 45칸 평균 **481,623원**`
  · `### 금~일 (2박)` 아래 표 — 값(출발·귀국·총액·항공사·직항/경유·편 시각·비고)의 원본
  · `### 달력형 요약(주차 × 패턴, 왕복 최저가)` — 주차×패턴 45칸(표와 전수 대조)
  · `**패턴별 요약**` — 패턴별 최저·평균·최고(파싱 결과와 대조)
  · `## 요약 — 4노선 최저가`·`## 부록 A. 당일치기(0박 1일) 검토` — 노선별 최저가·당일치기 판정

규칙:
  · 값은 원문 그대로. `—`(항공편은 있으나 이코노미 판매 가격 미제공)는 칸을 만들지 않고 빈칸으로 둔다
    (0건과 구분 — `noSale` 에도 넣지 않는다).
  · 원문이 말하는 칸 수(178)·노선별 칸 수(45·45·45·43)·주차별 45칸·노선별 최저/최고/평균·
    패턴별 최저/평균/최고를 파싱 결과와 **전수 대조**한다. 하나라도 다르면 멈춘다.
  · 이미 있는 노선·칸은 건드리지 않는다. 새 노선 4개만 신설한다.
  · 호텔 538곳 · 아코르 · 기존 43개 노선·`noSale`·다른 달 notes 는 **바이트 동일성**으로 보존 확인.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_sea4.py /workspace/data-sources/flights-sea-new8/부산출발-동남아4노선-푸꾸옥코타쿠알라비엔티안-12_1월.md --dry-run
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
WEEKS = ('2026-12-03', '2026-12-10', '2026-12-17', '2026-12-24', '2026-12-31',
         '2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
# 노선 코드 → (도시 이름, extra, 칸 수, 최저, 최고, 평균, daytrip 메타)
ROUTES = {
    'PQC': ('푸꾸옥', '', 45, 388393, 662826, 481623, {
        'status': 'ok', 'stay': '약 12시간 30분',
        'note': '비엣젯항공 직항 07:35 → 11:05(5시간 30분) · 같은 날 23:40 귀국편(부산 06:30+1 도착)으로 '
                '0박 왕복이 성립하나 귀국 도착이 새벽이라 실효는 낮음 · 당일치기 금액은 실측하지 않음',
        'short': ''}),
    'BKI': ('코타키나발루', '', 45, 377162, 749700, 486784, {
        'status': 'no', 'stay': '',
        'note': '에어부산 직항이 19:05 → 23:05 도착인데 귀국 직항은 00:05(다음 날) 출발이라 같은 날 왕복이 '
                '성립하지 않음 · 나머지 귀국편은 모두 경유이고 최단 13시간',
        'short': '직항 23:05 도착·귀국 00:05'}),
    'KUL': ('쿠알라룸푸르', '', 45, 570263, 1028900, 676059, {
        'status': 'ok', 'stay': '약 7시간',
        'note': '말레이항공 직항 10:40 → 16:40(7시간) 뒤 같은 날 23:55 경유 귀국편(대한항공, 부산 11:35+1 도착)이 '
                '있어 0박 왕복이 성립 — 다만 귀국편이 1회 경유 10시간 40분 · 당일치기 금액은 실측하지 않음',
        'short': ''}),
    'VTE': ('비엔티안', '직항 주 2회', 43, 577023, 790751, 659621, {
        'status': 'no', 'stay': '',
        'note': '직항(제주항공 21:00 → 00:25+1)이 자정 넘어 도착하고 귀국 직항(01:25)과 맞지 않음 · '
                '경유 최단 조합도 가는편 18:00 도착·귀국편 18:45 출발로 45분뿐이라 성립하지 않음',
        'short': '직항 심야 도착·45분 연결'}),
}
NEW_CELLS = 178
NEW_BY_MONTH = {'2026-12': 86, '2027-01': 92}
# 비엔티안 12/03 목~일·목~월 2칸은 '—'(항공편은 표시되나 이코노미 판매 가격 미제공)
MISSING = {('VTE', '2026-12-03', '목~일'), ('VTE', '2026-12-03', '목~월')}

HEAD = re.compile(r'^## \d\. 부산 ↔ (.+?)\(([A-Z]{3})\)$')
PAT_HEAD = re.compile(r'^### ([월화수목금토일]~[월화수목금토일]) \((\d)박\)$')
ROW = re.compile(r'^\| (\d{2})/(\d{2}) \(([월화수목금토일])\) \| (\d{2})/(\d{2}) \(([월화수목금토일])\)'
                 r'(?: ※)? '
                 r'\| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.*?) \|$')
CAL = re.compile(r'^\| (\d{2})/(\d{2}) 주 \(W\d+\) \|(.+)\|\s*$')
PSUM = re.compile(r'^\| ([월화수목금토일]~[월화수목금토일]) \((\d)박\) \| \*\*([\d,]+)원\*\* \| '
                  r'([\d,]+)원 \| ([\d,]+)원 \| (\d{2})/(\d{2})~(\d{2})/(\d{2}) \|$')
TOTAL = re.compile(r'^- 기간 내 최저 \*\*([\d,]+)원\*\* / 최고 \*\*([\d,]+)원\*\* / '
                   r'(\d+)칸 평균 \*\*([\d,]+)원\*\*$')
TOP = re.compile(r'^\| \*\*부산 ↔ (.+?)\(([A-Z]{3})\)\*\* \| \*\*([\d,]+)원\*\* \| '
                 r'(\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2})[^|]*\| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|')
DAY = re.compile(r'^\| 부산 ↔ (.+?)\(([A-Z]{3})\) \| \*\*(가능|불가)\*\* \|')


def year_of(mm):
    return 2026 if int(mm) == 12 else 2027


def full(mm, dd):
    return '%d-%02d-%02d' % (year_of(mm), int(mm), int(dd))


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def norm_money(text):
    return int(text.replace(',', '').replace('원', '').replace('*', '').strip())


def tidy(text):
    t = re.sub(r'(\d+)시간(\d+)분', r'\1시간 \2분', text)
    t = re.sub(r'총(\d)', r'총 \1', t)
    return t.strip()


def parse(text):
    cells, total, top, day, cal, psum = {}, {}, {}, {}, {}, {}
    code = pat = None
    for raw in text.splitlines():
        line = raw.strip()
        m = HEAD.match(line)
        if m:
            city, code = m.groups()
            if code not in ROUTES:
                raise SystemExit('예상 밖 노선: %s' % line)
            if city != ROUTES[code][0]:
                raise SystemExit('도시 이름이 다릅니다: %s' % line)
            cells[code], cal[code], psum[code] = [], {}, {}
            pat = None
            continue
        if line.startswith('## '):
            code = pat = None
            continue
        if code:
            m = PAT_HEAD.match(line)
            if m:
                label, nights = m.groups()
                if int(nights) != (WD[label[-1]] - WD[label[0]]) % 7:
                    raise SystemExit('박수 표기가 패턴과 다릅니다: %s' % line)
                pat = label
                continue
            if line.startswith('### '):
                pat = None
                continue
            m = ROW.match(line)
            if m and pat:
                (sm, sd, swd, em, ed, ewd, price, airline, via, going, ret,
                 memo) = m.groups()
                if WD[swd] != WD[pat[0]] or WD[ewd] != WD[pat[-1]]:
                    raise SystemExit('요일이 패턴과 다릅니다: %s' % line)
                date = full(sm, sd)
                back = back_date(date, pat)
                if back != full(em, ed):
                    raise SystemExit('귀국일이 패턴과 다릅니다: %s' % line)
                if price.strip() == '—':
                    if (code, date, pat) not in MISSING:
                        raise SystemExit('예상 밖 빈칸입니다: %s' % line)
                    continue
                if not re.fullmatch(r'\*\*[\d,]+\*\*', price.strip()):
                    raise SystemExit('금액 표기가 예상과 다릅니다: %s' % line)
                if via.strip() == '—':
                    raise SystemExit('직항/경유가 비어 있습니다: %s' % line)
                note = '%s %s · 오는편 %s' % (tidy(via), tidy(going), tidy(ret))
                if memo.strip() and memo.strip() != '—':
                    note += ' · ' + tidy(memo)
                deal = {'date': date, 'back': back, 'pattern': pat,
                        'price': norm_money(price), 'airline': airline.strip(),
                        'via': not via.strip().startswith('직항'), 'note': note}
                alt = re.search(r'직항 최저 ([\d,]+)원', memo)
                if alt:
                    deal['alt'] = norm_money(alt.group(1))
                if any(d['date'] == date and d['pattern'] == pat for d in cells[code]):
                    raise SystemExit('%s %s %s 중복' % (code, date, pat))
                cells[code].append(deal)
                continue
            m = CAL.match(line)
            if m:
                sm, sd, rest = m.groups()
                values = [v.strip().replace('*', '') for v in rest.split('|')]
                values = [v for v in values if v]
                if len(values) != 5:
                    raise SystemExit('달력 줄 칸 수가 5가 아닙니다: %s' % line)
                for label, val in zip(PATTERNS, values):
                    if val == '—':
                        continue
                    if not re.fullmatch(r'[\d,]+', val):
                        raise SystemExit('달력 값이 숫자가 아닙니다: %s' % line)
                    cal[code][(full(sm, sd), label)] = norm_money(val)
                continue
            m = PSUM.match(line)
            if m:
                label, _n, lo, avg, hi, sm, sd, _em, _ed = m.groups()
                psum[code][label] = (norm_money(lo), norm_money(avg), norm_money(hi),
                                     full(sm, sd))
                continue
            m = TOTAL.match(line)
            if m:
                total[code] = (norm_money(m.group(1)), norm_money(m.group(2)),
                               int(m.group(3)), norm_money(m.group(4)))
                continue
        m = TOP.match(line)
        if m:
            city, rc, price, d1, _d2, pat, airline, via = m.groups()
            top[rc] = (norm_money(price), d1, pat.split('(')[0].strip(),
                       airline.strip(), via.strip())
            continue
        m = DAY.match(line)
        if m:
            _city, rc, verdict = m.groups()
            day[rc] = verdict
    return cells, total, top, day, cal, psum


def checks(text, cells, total, top, day, cal, psum):
    bad = []
    if set(cells) != set(ROUTES):
        bad.append('노선 집합이 다릅니다: %s' % sorted(set(cells) ^ set(ROUTES)))
    if sum(len(v) for v in cells.values()) != NEW_CELLS:
        bad.append('값 %d칸 (기대 %d칸)' % (sum(len(v) for v in cells.values()), NEW_CELLS))
    for code, (city, _e, n, lo, hi, avg, dt) in ROUTES.items():
        deals = cells.get(code) or []
        if len(deals) != n:
            bad.append('%s %d칸 (원문 %d칸)' % (code, len(deals), n))
        prices = [d['price'] for d in deals]
        if min(prices) != lo or max(prices) != hi:
            bad.append('%s 최저·최고 %s (원문 %s)' % (code, (min(prices), max(prices)), (lo, hi)))
        # 원문은 비엔티안도 '45칸 평균'으로 적는다(값이 있는 43칸 기준 평균)
        if total.get(code) != (lo, hi, 45, avg):
            bad.append('%s 절 머리 %s (원문 %s)' % (code, total.get(code), (lo, hi, 45, avg)))
        mine = int(sum(prices) / len(prices))          # 원문 평균은 버림해 적는다
        if mine != avg:
            bad.append('%s 평균 %d원 (원문 %d원)' % (code, mine, avg))
        # 주차 × 패턴 달력 == 표
        for wi, thu in enumerate(WEEKS):
            for label in PATTERNS:
                out = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(WD[label[0]] - WD['목']) % 7)).isoformat()
                hit = [d for d in deals if d['date'] == out and d['pattern'] == label]
                key = (thu, label)
                if (code, out, label) in MISSING:
                    if hit or key in cal[code]:
                        bad.append('%s %s %s 는 빈칸이어야 합니다' % (code, out, label))
                    continue
                if not hit:
                    bad.append('%s %s %s 표에 없음' % (code, out, label))
                    continue
                if cal[code].get(key) != hit[0]['price']:
                    bad.append('%s %s %s 달력 %s ≠ 표 %d' % (code, out, label,
                                                           cal[code].get(key), hit[0]['price']))
        # 패턴별 요약
        for label in PATTERNS:
            ps = [d['price'] for d in deals if d['pattern'] == label]
            if not ps:
                continue
            want = psum.get(code, {}).get(label)
            got = (min(ps), int(sum(ps) / len(ps)), max(ps))
            if want is None:
                bad.append('%s %s 패턴 요약 없음' % (code, label))
            elif want[:3] != got:
                bad.append('%s %s 패턴 요약 %s (계산 %s)' % (code, label, want[:3], got))
            else:
                hit = [d for d in deals if d['pattern'] == label and d['price'] == want[0]]
                if want[3] not in {d['date'] for d in hit}:
                    bad.append('%s %s 최저 일정 %s (계산 %s)' % (code, label, want[3],
                                                            [d['date'] for d in hit]))
        # 당일치기 판정
        verdict = 'ok' if dt['status'] == 'ok' else 'no'
        if day.get(code) != ('가능' if verdict == 'ok' else '불가'):
            bad.append('%s 당일치기 판정 %s (부록 A %s)' % (code, verdict, day.get(code)))
        if not dt['note'] or (dt['status'] != 'ok' and not dt['short']):
            bad.append('%s daytrip 메타가 비었습니다' % code)
    # 요약 표 — 노선별 최저가·날짜
    if set(top) != set(ROUTES):
        bad.append('요약 표 노선 집합이 다릅니다: %s' % sorted(set(top) ^ set(ROUTES)))
    for code in ROUTES:
        if code not in top:
            continue
        price, date, pat, airline, via = top[code]
        lo = min(cells[code], key=lambda d: d['price'])
        if (lo['price'], lo['date']) != (price, date):
            bad.append('%s 요약 %s (계산 %s)' % (code, (price, date),
                                              (lo['price'], lo['date'])))
        if lo['pattern'] != pat:
            bad.append('%s 요약 패턴 %s (계산 %s)' % (code, pat, lo['pattern']))
        if not airline.startswith(lo['airline']):
            bad.append('%s 요약 항공사 %r (표 %r)' % (code, airline, lo['airline']))
    for phrase in ('4노선 × 5패턴 × 9주 = 180칸 · 전부 실제 조회(178칸 가격 확인, 2칸 가격 미표시)',
                   '푸꾸옥·쿠알라룸푸르는 성립하지만',
                   '코타키나발루·비엔티안은 시간 구조상 불가능하다'):
        if phrase not in text:
            bad.append('원문 문장을 찾지 못했습니다: %s' % phrase)
    return bad


def merge(master, cells):
    fl = master['flights']
    have = {r['code'] for r in fl['routes']}
    dup = have & set(ROUTES)
    if dup:
        raise SystemExit('이미 있는 노선입니다: %s' % sorted(dup))
    for code, (city, extra, _n, _lo, _hi, _avg, dt) in ROUTES.items():
        fl['routes'].append({
            'code': code, 'city': city, 'extra': extra,
            'deals': sorted(cells[code], key=lambda d: (d['date'], WD[d['pattern'][0]])),
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


def notes_update(fl):
    fl['notes']['2026-12'] = (
        '신규 11개 노선 가운데 필리핀 4개(세부·마닐라·보홀(팡라오)·클락)와 동남아 4개'
        '(푸꾸옥·코타키나발루·쿠알라룸푸르·비엔티안)는 12월 5주 × 5패턴을 실측했습니다 — 동남아는 86칸이고, '
        '비엔티안 12/3 목~일·목~월 2칸은 항공편은 표시되나 이코노미 판매 가격이 제공되지 않아 빈칸(—)입니다'
        '(0건 아님). 일본 신규 7개 노선은 12월 5주 × 5패턴 175칸 중 81칸만 실측했습니다 — '
        '구마모토 22 · 가고시마 22 · 시즈오카 18 · 마쓰야마 5 · 다카마쓰 5 · 미야코지마 5 · 삿포로 4칸이고 '
        '나머지는 미조회(—)입니다.')
    fl['notes']['2027-01'] = (
        '신규 노선의 1월분입니다 — 필리핀 4개 노선 92칸(12/31 주의 1/1·1/2 출발 12칸 포함), '
        '동남아 4개 노선 92칸(1/28 출발 목~월은 귀국 2027-02-01), 일본 7개 노선은 12/31 주의 1/1·1/2 출발 '
        '9칸(구마모토·가고시마·시즈오카 3칸씩)만 실측했습니다. 일본 7개 노선의 나머지 1월 주차는 미조회(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='동남아 신규 4개 노선 178칸 md → master_db.json 병합')
    ap.add_argument('md')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    cells, total, top, day, cal, psum = parse(text)
    bad = checks(text, cells, total, top, day, cal, psum)
    print('  값 %d칸 · 노선 %d개 (%s)' % (
        sum(len(v) for v in cells.values()), len(cells),
        ', '.join('%s %d' % (c, len(cells[c])) for c in ROUTES)))
    for code in ROUTES:
        print('    %s 최저 %s원 ~ 최고 %s원' % (
            code, format(min(d['price'] for d in cells[code]), ','),
            format(max(d['price'] for d in cells[code]), ',')))
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

    merge(master, cells)
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
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('기존 노선 데이터가 바뀌었습니다.')
    if json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True) != before_nosale:
        raise SystemExit('판매편 0건 기록이 바뀌었습니다.')
    if {k: v for k, v in fl['notes'].items() if k not in ('2026-12', '2027-01')} != before_notes:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다.')

    print('신규 딜 %d건 · 노선 %d개 신설' % (NEW_CELLS, len(ROUTES)))
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
