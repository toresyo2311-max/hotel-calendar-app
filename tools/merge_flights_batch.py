#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 항공 특가 md(5패턴 실측 보고서)를 `data/master_db.json` 의 `flights` 에 병합한다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_batch.py ../부산출발-항공특가-12월잔여-보완2차.md --dry-run
    python3 tools/merge_flights_batch.py ../부산출발-항공특가-12월잔여-보완2차.md

규칙:
  · 보고서의 `- 날짜 · 패턴 · PUS–코드 · 금액원 · 항공사 …` 줄만 읽는다. 추정값은 만들지 않는다.
  · 같은 (노선, 출발일, 패턴) 이 이미 있으면 **기존 건을 그대로 둔다**(완본의 항공사·직항 정보 보존).
    기존 건에 항공사가 비어 있고 새 보고서에 있으면 그 항목만 채운다.
  · '가격 미표시' 줄은 넣지 않고 gaps 로 보고한다.
  · 노선·주차·패턴 목록(`routes`/`weeks`/`patterns`)은 그대로 두고 `counts` 만 다시 센다.
    counts.holiday 는 기존 정의(2026-12-25 · 2027-02-04 출발 건수)를 그대로 따른다.
  · 호텔 데이터(`hotels`)는 읽기만 하고 절대 건드리지 않는다.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

PAT_ORDER = ['목~일', '금~일', '토~월', '목~월', '금~월',
             '일~수', '일~목', '월~수']  # 앱의 5패턴 뒤에 보조 창구를 붙인다
WD = {'월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6, '일': 0}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')

LINE = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · (\S+~\S+) · PUS–([A-Z]{3}) · (.+)$')
ROUTE = re.compile(r'^## 부산–(.+?) \(([A-Z]{3})\)')


def parse_md(path):
    """보고서 md → (deals, gaps). deals 는 (code, deal dict) 목록."""
    with open(path, encoding='utf-8') as fp:
        text = fp.read()
    deals, gaps, code = [], [], None
    for raw in text.splitlines():
        m = ROUTE.match(raw.strip())
        if m:
            code = m.group(2)
            continue
        m = LINE.match(raw.strip())
        if not m:
            continue
        date, pattern, rcode, rest = m.groups()
        if '가격 미표시' in rest:
            gaps.append((rcode, date, pattern, rest))
            continue
        fields = [f.strip() for f in rest.split(' · ')]
        pm = re.match(r'([\d,]+)원', fields[0])
        if not pm:
            gaps.append((rcode, date, pattern, rest))
            continue
        price = int(pm.group(1).replace(',', ''))
        info = fields[1] if len(fields) > 1 else ''

        deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern, 'price': price}
        if info == '항공사 미확인(가격표 실측)':
            deal['src'] = '가격표'
            deal['via'] = None
            deal['note'] = '직항/경유 미확인'
        elif info:
            airline, _, tail = info.partition(' ')
            deal['airline'] = airline
            alt = re.search(r'/ 직항 (\S+) ([\d,]+)$', tail)
            if alt:
                deal['alt'] = int(alt.group(2).replace(',', ''))
                deal['note'] = '%s ※직항 %s원(%s)' % (
                    clean(tail[:alt.start()]), alt.group(2), alt.group(1))
            else:
                deal['note'] = clean(tail)
            deal['via'] = '경유' in info
            if not deal['note']:
                deal.pop('note')
        else:
            deal['src'] = '가격표'
            deal['via'] = None
            deal['note'] = '직항/경유 미확인'
        deals.append((rcode, deal))
    return deals, gaps


def clean(tail):
    """'경유(난징 13h, 총18h) 직항없음' → '경유(난징 13h, 총18h)' (직항 여부는 via 필드가 갖는다)."""
    t = tail.strip()
    t = re.sub(r'\s*직항\s*없음$', '', t)
    t = re.sub(r'\s*부산\s*직항\s*없음$', '', t)
    return t.strip()


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다 (패턴 %s)' % (date, a, pattern))
    nights = (WD[b] - WD[a]) % 7 or 7
    return (start + datetime.timedelta(days=nights)).isoformat()


def rank(pattern):
    return PAT_ORDER.index(pattern) if pattern in PAT_ORDER else len(PAT_ORDER)


def merge(master, deals, gaps):
    routes = {r['code']: r for r in master['flights']['routes']}
    added, filled, skipped = [], [], []
    for code, deal in deals:
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)
        r = routes[code]
        same = [d for d in r['deals'] if d['date'] == deal['date'] and d['pattern'] == deal['pattern']]
        if same:
            old = same[0]
            changed = False
            if not old.get('airline') and deal.get('airline'):
                old['airline'] = deal['airline']
                changed = True
            if old.get('via') is None and deal.get('via') is not None:
                old['via'] = deal['via']
                changed = True
            if old.get('note') in (None, '', '직항/경유 미확인') and deal.get('note') and deal['note'] != '직항/경유 미확인':
                old['note'] = deal['note']
                changed = True
            if changed:
                filled.append((code, deal['date'], deal['pattern']))
            else:
                skipped.append((code, deal['date'], deal['pattern'], old['price'], deal['price']))
            continue
        r['deals'].append(deal)
        added.append((code, deal['date'], deal['pattern'], deal['price']))

    for r in master['flights']['routes']:
        r['deals'].sort(key=lambda d: (d['date'], rank(d['pattern'])))

    all_deals = [d for r in master['flights']['routes'] for d in r['deals']]
    by_month = {}
    for d in all_deals:
        by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    master['flights']['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month[k] for k in sorted(by_month)},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
    }
    return added, filled, skipped, gaps


def main(argv):
    ap = argparse.ArgumentParser(description='항공 특가 md → master_db.json flights 병합')
    ap.add_argument('md')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='', help='DB.extended 에 덧붙일 한 줄')
    args = ap.parse_args(argv)

    deals, gaps = parse_md(args.md)
    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    before = len(master['flights']['routes']), master['flights']['counts']['total']
    added, filled, skipped, gaps = merge(master, deals, gaps)

    print('파싱 %d건 (가격 미표시 %d건)' % (len(deals), len(gaps)))
    print('신규 %d건 · 기존 유지 %d건 · 항목 보강 %d건' % (len(added), len(skipped), len(filled)))
    print('총 건수 %d → %d' % (before[1], master['flights']['counts']['total']))
    for a in added:
        print('  + %s %s %s %s원' % a)
    for f in filled:
        print('  ~ %s %s %s (항공사/직항 보강)' % f)
    for s in skipped:
        print('  = %s %s %s 기존 %s원 / 보고서 %s원' % s)
    for g in gaps:
        print('  - %s %s %s 가격 미표시: %s' % g)

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
