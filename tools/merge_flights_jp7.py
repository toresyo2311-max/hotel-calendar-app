#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **일본 신규 7개 노선**(구마모토·가고시마·시즈오카·마쓰야마·다카마쓰·미야코지마·삿포로)
2026년 12월 1차 실측 90칸 md → `data/master_db.json` 의 `flights` 병합(노선 7개 신설).

읽는 곳:
  · `### 부산–삿포로(신치토세) (CTS) · 25칸 중 4칸 실측` 절 머리 — 노선 코드와 실측/전체 칸 수
  · 그 아래 `- 2026-12-03 · 목~일 · 삿포로(신치토세) · 420,480원` 줄(값) 과 `· 미실측` 줄(건너뜀)
  · `## 먼저 결론` — 노선별 12월 최저가·날짜(파싱 결과와 대조)
  · `## 노선별 실측 커버리지 (2026년 12월 · 25칸 기준)` — 노선별 실측 칸 수
  · `## 12월 최저가 순위 (실측분)` — 25줄(싼 순)을 파싱 결과의 상위 25칸과 대조

규칙:
  · 값은 원문 그대로. `미실측` 은 넣지 않는다(추정 금지) — 90칸만 적재한다.
  · 원문이 말하는 노선별 실측 칸 수(4·21·25·25·5·5·5 = 90)와 노선별 최저가·최저 날짜를
    파싱 결과와 **전수 대조**한다. 하나라도 다르면 멈춘다.
  · 이미 있는 노선·칸은 건드리지 않는다. 새 노선 7개만 신설한다.
  · 원문에 칸별 항공사·직항/경유가 없으므로 `via=null`·`src=가격표`로 적고 note 에 미확인을 밝힌다.
  · 호텔 538곳 · 아코르 · 기존 노선·`noSale`·다른 달 notes 는 **바이트 동일성**으로 보존 확인.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jp7.py /workspace/data-sources/flights-jp-new7/부산출발-일본7노선-12월-1차.md --dry-run
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
# 노선 코드 → (도시 이름, extra, 실측 칸 수, 전체 칸 수, 12월 최저가, 최저 출발일, 패턴, daytrip 메타)
ROUTES = {
    'KMJ': ('구마모토', '', 25, 25, 242800, '2026-12-03', '목~월', {
        'status': 'short', 'stay': '5~6시간',
        'note': '이스타항공 직항 11:55 → 13:25(1시간 30분) · 오후 출발이라 현지 체류가 5~6시간 수준 · '
                '당일치기 금액은 실측하지 않았습니다',
        'short': '직항 11:55 출발'}),
    'KOJ': ('가고시마', '직항 없음', 25, 25, 427000, '2026-12-18', '금~일', {
        'status': 'no', 'stay': '',
        'note': '부산–가고시마 직항이 검색되지 않음 — 서울 경유(대한항공, 총 4시간 20분~) 또는 '
                '마쓰야마 경유(에어부산+JAL, 총 4시간 40분)뿐이라 같은 날 왕복이 성립하지 않음',
        'short': '직항 없음·경유 4시간 20분↑'}),
    'FSZ': ('시즈오카', '', 21, 25, 276900, '2026-12-03', '목~월', {
        'status': 'unk', 'stay': '',
        'note': '에어부산 직항 09:05 → 10:45(1시간 40분)가 뜨는 날만 직항 · 직항이 없는 날은 서울·후쿠오카 '
                '경유(5시간 40분~)뿐 · 같은 날 귀국편 시각과 금액은 실측하지 않았습니다',
        'short': '당일치기 미확인'}),
    'MYJ': ('마쓰야마', '', 5, 25, 304400, '2026-12-04', '금~월', {
        'status': 'no', 'stay': '',
        'note': '에어부산 직항이 16:35 출발(17:40 도착) 하루 1편뿐이라 같은 날 귀국편으로 이어지지 않음 — '
                '직항으로는 당일치기가 사실상 불가',
        'short': '직항 16:35 출발 1편'}),
    'TAK': ('다카마쓰', '', 5, 25, 439800, '2026-12-17', '목~일', {
        'status': 'unk', 'stay': '',
        'note': '부산–다카마쓰 직항 유무부터 확인되지 않았습니다(경유 편 중심 14편 검색) · '
                '당일치기 금액은 실측하지 않았습니다',
        'short': '당일치기 미확인'}),
    'MMY': ('미야코지마', '', 5, 25, 317500, '2026-12-17', '목~일', {
        'status': 'unk', 'stay': '',
        'note': '진에어 직항 12:55 → 15:20(2시간 25분) · 직항이 없는 날은 서울 경유 68만원대 · '
                '같은 날 귀국편 시각과 금액은 실측하지 않았습니다',
        'short': '당일치기 미확인'}),
    'CTS': ('삿포로', '', 4, 25, 416500, '2026-12-05', '토~월', {
        'status': 'unk', 'stay': '',
        'note': '이스타항공 직항 14:30 → 17:00(2시간 30분) 외 오전 출발편(에어부산 09:00·트리니티 09:10)도 검색됨 · '
                '저녁 귀국편과의 조합·금액은 실측하지 않았습니다(날짜별 가격표가 열리지 않는 노선)',
        'short': '당일치기 미확인'}),
}
NEW_CELLS = 90
# 12/31 주의 금~일·토~월·금~월은 2027-01-01·01-02 출발이다(구마모토·가고시마·시즈오카 3칸씩)
NEW_BY_MONTH = {'2026-12': 81, '2027-01': 9}
TOTAL_CELLS = sum(v[3] for v in ROUTES.values())     # 175칸(7노선 × 5주 × 5패턴)

HEAD = re.compile(r'^### 부산–(.+?) \(([A-Z]{3})\) · (\d+)칸 중 (\d+)칸 실측$')
CELL = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · '
                  r'.+? · (?:([\d,]+)원|(미실측))$')
CONCL = re.compile(r'^- \*\*(.+?)\(([A-Z]{3})\)\*\*: 12월 최저 ([\d,]+)원 — '
                   r'(\d{4}-\d{2}-\d{2}) 출발 (\S+)$', re.M)
COVER = re.compile(r'^- (.+?)\(([A-Z]{3})\) (\d+)/(\d+)$', re.M)
RANK = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · '
                  r'(.+?) · ([\d,]+)원$', re.M)


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    return (start + datetime.timedelta(days=(WD[b] - WD[a]) % 7)).isoformat()


def parse(text):
    cells, heads = {}, {}
    code = None
    for raw in text.splitlines():
        line = raw.strip()
        m = HEAD.match(line)
        if m:
            city, code, total, got = m.groups()
            if code not in ROUTES:
                raise SystemExit('예상 밖 노선: %s' % line)
            heads[code] = (city, int(total), int(got))
            continue
        if line.startswith('## ') or line.startswith('### '):
            code = None
            continue
        if code:
            m = CELL.match(line)
            if m:
                date, pat, price, miss = m.groups()
                if miss:
                    continue
                if any(d['date'] == date and d['pattern'] == pat for d in cells.get(code, [])):
                    raise SystemExit('%s %s %s 중복' % (code, date, pat))
                cells.setdefault(code, []).append({
                    'date': date, 'back': back_date(date, pat), 'pattern': pat,
                    'price': int(price.replace(',', '')), 'via': None, 'src': '가격표',
                    'note': '가격표 실측 · 항공사·직항/경유 미확인'})
    concl = {}
    for m in CONCL.finditer(text):
        name, code, price, date, pat = m.groups()
        concl[code] = (int(price.replace(',', '')), date, pat)
    cover = {m.group(2): (int(m.group(3)), int(m.group(4))) for m in COVER.finditer(text)}
    tail = text.split('## 12월 최저가 순위 (실측분)', 1)
    if len(tail) != 2:
        raise SystemExit('원문에서 12월 최저가 순위 절을 찾지 못했습니다')
    rank = [(m.group(1), m.group(2), m.group(3), int(m.group(4).replace(',', '')))
            for m in RANK.finditer(tail[1])]
    return cells, heads, concl, cover, rank


def checks(text, cells, heads, concl, cover, rank):
    bad = []
    if set(cells) != set(ROUTES):
        bad.append('노선 집합이 다릅니다: %s' % sorted(set(cells) ^ set(ROUTES)))
    if sum(len(v) for v in cells.values()) != NEW_CELLS:
        bad.append('값 %d칸 (기대 %d칸)' % (sum(len(v) for v in cells.values()), NEW_CELLS))
    for code, (city, extra, got, total, lo, lo_date, lo_pat, _dt) in ROUTES.items():
        deals = cells.get(code) or []
        if len(deals) != got:
            bad.append('%s %d칸 (원문 %d칸)' % (code, len(deals), got))
        head = heads.get(code) or ('', 0, 0)
        if head[1:] != (total, got) or not head[0].startswith(city):
            bad.append('%s 절 머리 %s (기대 %s %s칸 중 %s칸)' % (code, heads.get(code), city, total, got))
        if cover.get(code) != (got, total):
            bad.append('%s 커버리지 %s (기대 %d/%d)' % (code, cover.get(code), got, total))
        prices = [d['price'] for d in deals]
        if min(prices) != lo:
            bad.append('%s 최저 %d (원문 %d)' % (code, min(prices), lo))
        if concl.get(code) != (lo, lo_date, lo_pat):
            bad.append('%s 결론 %s (기대 %s)' % (code, concl.get(code), (lo, lo_date, lo_pat)))
        hit = next(d for d in deals if d['price'] == lo)
        if (hit['date'], hit['pattern']) != (lo_date, lo_pat):
            bad.append('%s 최저 칸 %s %s (원문 %s %s)'
                       % (code, hit['date'], hit['pattern'], lo_date, lo_pat))
    if len(rank) != 25:
        bad.append('12월 최저가 순위 %d줄 (기대 25줄)' % len(rank))
    dec = [d for v in cells.values() for d in v if d['date'].startswith('2026-12')]
    if len(dec) != NEW_BY_MONTH['2026-12']:
        bad.append('12월 값 %d칸 (기대 %d칸)' % (len(dec), NEW_BY_MONTH['2026-12']))
    everything = sorted(((d['price'], d['date'], d['pattern'], ROUTES[c][0])
                         for c, v in cells.items() for d in v))
    if [r[3] for r in rank] != [r[0] for r in everything[:25]]:
        bad.append('순위 25줄 금액이 계산값과 다릅니다')
    else:
        for (d1, p1, city1, price1), (price2, d2, p2, city2) in zip(rank, everything[:25]):
            if (d1, p1, price1) != (d2, p2, price2) or not city1.startswith(city2):
                bad.append('순위 줄 %s (계산 %s)' % ((d1, p1, price1, city1),
                                                 (d2, p2, price2, city2)))
    if '7개 노선 × 5주 × 5패턴 = %d칸 가운데 **%d칸 실측' % (TOTAL_CELLS, NEW_CELLS) not in text:
        bad.append('원문 완료 범위 문장을 찾지 못했습니다')
    for code, (_c, _e, _g, _t, _lo, _d, _p, dt) in ROUTES.items():
        if dt['status'] not in ('ok', 'short', 'no', 'unk') or not dt['note'] or not dt['short']:
            bad.append('%s daytrip 메타가 비었습니다' % code)
    return bad


def merge(master, cells):
    fl = master['flights']
    have = {r['code'] for r in fl['routes']}
    dup = have & set(ROUTES)
    if dup:
        raise SystemExit('이미 있는 노선입니다: %s' % sorted(dup))
    for code, (city, extra, _got, _total, _lo, _d, _p, dt) in ROUTES.items():
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
        '필리핀 신규 4개 노선(세부·마닐라·보홀(팡라오)·클락)은 12월 5주 × 5패턴 가운데 12/31 주의 '
        '금~일·토~월·금~월(1/1·1/2 출발)을 뺀 88칸을 실측했습니다(빈칸 0칸). 일본 신규 7개 노선은 '
        '12월 5주 × 5패턴 175칸 중 81칸만 실측했습니다 — 구마모토 22 · 가고시마 22 · 시즈오카 18 · '
        '마쓰야마 5 · 다카마쓰 5 · 미야코지마 5 · 삿포로 4칸이고 나머지는 미조회(—)입니다.')
    fl['notes']['2027-01'] = (
        '필리핀 신규 4개 노선은 1월 4주 × 5패턴 80칸 + 12/31 주의 1/1·1/2 출발 3패턴 12칸 = 92칸을 '
        '실측했습니다(1/28 출발 목~월은 귀국 2027-02-01). 일본 신규 7개 노선은 12/31 주의 1/1·1/2 출발 '
        '9칸(구마모토·가고시마·시즈오카 3칸씩)만 실측했고 나머지 1월 주차는 미조회(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='일본 신규 7개 노선 12월 1차 90칸 md → master_db.json 병합')
    ap.add_argument('md')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    cells, heads, concl, cover, rank = parse(text)
    bad = checks(text, cells, heads, concl, cover, rank)
    print('  값 %d칸 / %d칸 · 노선 %d개' % (sum(len(v) for v in cells.values()), TOTAL_CELLS,
                                        len(cells)))
    for code in ROUTES:
        print('    %s %d/%d칸 최저 %s원' % (code, len(cells[code]), ROUTES[code][3],
                                         format(min(d['price'] for d in cells[code]), ',')))
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
    if json.dumps(fl['patterns'], ensure_ascii=False) != before_patterns:
        raise SystemExit('패턴 정의가 바뀌었습니다.')

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
