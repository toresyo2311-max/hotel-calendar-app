#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ 항공특가(부산) 갱신본을 ⑥ 항공 탭 창 안 칸에 병합한다(2026-11-29).

    python3 tools/merge_tab5_update_20261129.py <갱신본.json> [--write]

규칙
  · 노선 코드는 앱 노선 코드로 옮긴다(NRT → TYO — 앱은 도쿄를 TYO 한 노선으로 본다).
  · 앱 창(2026-12-01 ~ 2027-11-30) 밖 출발일은 넣지 않는다(11/29~30 출발분 제외).
  · 같은 (노선·출발일·패턴) 칸이 있으면 값·직항 여부·항공사·비고를 오늘 실측값으로 바꾼다.
  · 없는 칸은 새로 넣는다(건수 증가). 삭제는 하지 않는다.
  · 패턴의 박수와 귀국일이 어긋나는 칸은 넣지 않고 따로 보고한다.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
WINDOW = ('2026-12-01', '2027-11-30')
FL_WD = {'월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6, '일': 7}
CODE_ALIAS = {'NRT': 'TYO'}          # 앱은 도쿄를 TYO 한 노선으로 둔다


def fl_nights(label):
    m = re.match(r'^([월화수목금토일])~([월화수목금토일])$', str(label))
    if not m:
        return None
    return (FL_WD[m.group(2)] - FL_WD[m.group(1)]) % 7


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args(argv)

    up = json.load(open(args.file, encoding='utf-8'))
    master = json.load(open(MASTER, encoding='utf-8'))
    flights = master['flights']
    by_code = {r['code']: r for r in flights['routes']}

    added = replaced = same = 0
    skipped_out = skipped_bad = 0
    ups, downs = [], []
    new_cells = {}
    missing_route = set()
    detail = []

    for r in up.get('routes') or []:
        code = CODE_ALIAS.get(r.get('code'), r.get('code'))
        route = by_code.get(code)
        if not route:
            missing_route.add(r.get('code'))
            continue
        index = {(d['date'], d['pattern']): d for d in route['deals']}
        for d in r.get('deals') or []:
            date = d.get('date')
            label = d.get('pattern')
            nights = fl_nights(label)
            if nights is None:
                skipped_bad += 1
                detail.append('패턴 형식: %s %s' % (code, label))
                continue
            back = (datetime.date.fromisoformat(date) + datetime.timedelta(days=nights)).isoformat()
            if d.get('back') and d['back'] != back:
                skipped_bad += 1
                detail.append('귀국일 불일치: %s %s %s %s(계산 %s)'
                              % (code, date, label, d['back'], back))
                continue
            if not (WINDOW[0] <= date <= WINDOW[1]):
                skipped_out += 1
                continue
            if not isinstance(d.get('price'), int) or d['price'] <= 0:
                skipped_bad += 1
                detail.append('가격 이상: %s %s %s %r' % (code, date, label, d.get('price')))
                continue
            cell = {
                'date': date,
                'back': back,
                'pattern': label,
                'price': d['price'],
                'via': d.get('via'),
                'note': d.get('note') or '',
            }
            if d.get('airline'):
                cell['airline'] = d['airline']
            if d.get('src'):
                cell['src'] = d['src']
            old = index.get((date, label))
            if old is None:
                route['deals'].append(cell)
                index[(date, label)] = cell
                added += 1
                new_cells[code] = new_cells.get(code, 0) + 1
                continue
            if old.get('price') == cell['price']:
                same += 1
            elif cell['price'] < (old.get('price') or 0):
                downs.append((old['price'], cell['price'], code, date, label, old.get('airline'), cell.get('airline')))
                replaced += 1
            else:
                ups.append((old['price'], cell['price'], code, date, label, old.get('airline'), cell.get('airline')))
                replaced += 1
            old.update(cell)

    total = sum(len(r['deals']) for r in flights['routes'])
    daytrip = sum(1 for r in flights['routes'] for d in r['deals'] if fl_nights(d['pattern']) == 0)
    by_month = {}
    for r in flights['routes']:
        for d in r['deals']:
            by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    print('새 칸 %d · 값 교체 %d(내림 %d · 오름 %d) · 같음 %d · 창 밖 %d · 형식 이상 %d'
          % (added, replaced, len(downs), len(ups), same, skipped_out, skipped_bad))
    print('노선별 새 칸:', dict(sorted(new_cells.items())))
    for x in detail[:10]:
        print('  !', x)
    if missing_route:
        print('  ! 앱에 없는 노선:', sorted(missing_route))
    print('총 %d건 → %d건 · 당일치기 %d · byMonth %s'
          % (flights['counts'].get('total'), total, daytrip, dict(sorted(by_month.items()))))
    print('내림 상위:', sorted((b - a, a, b, c, dt, lb) for a, b, c, dt, lb, *_ in downs)[:5])
    print('오름 상위:', sorted(((b - a), a, b, c, dt, lb) for a, b, c, dt, lb, *_ in ups)[-5:])

    if not args.write:
        print('(드라이런 — --write 로 반영)')
        return 0

    flights['counts']['total'] = total
    flights['counts']['daytrip'] = daytrip
    flights['counts']['byMonth'] = dict(sorted(by_month.items()))
    if len(flights['counts'].get('byMonth') or {}) != 12:
        print('! byMonth 가 12개월이 아닙니다:', flights['counts']['byMonth'])
        return 1
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('master_db.json 갱신 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
