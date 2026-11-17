#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 중국 4노선(**연길 YNJ · 장가계 DYG · 구이린 KWL · 황산 TXN**) 12~1월 **완본**(180칸) →
`data/master_db.json` 의 `flights` 병합 (기존 부분 조사분을 중복 없이 채운다).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_china_full4.py \
        ../data-sources/flights-china-new8/부산출발-중국4노선-연길장가계구이린황산-12_1월-완본.md --dry-run

읽는 곳:
  · 부록 — `- 2026-12-03(목) · 목~일(3박) · PUS–YNJ · 304,800원 · Jeju Air · 경유(Seoul 7h40, 총11h15)`
  · 부록 0건 — `- 2026-12-05(토) · 토~월(2박) · PUS–TXN · 판매편 없음(0건)`
  · 4절 당일치기 표 (익일 귀국이 없어 0박이 안 되는 노선 판정)

규칙:
  · 값(가격·날짜·소요시간)은 원문 그대로. 항공사·경유지 이름만 앱 표기(한국어)로 옮긴다.
  · 조회했으나 **판매편이 없던** 칸은 가격이 아니라 `flights.noSale` 로 넣는다(추정 금지).
  · 이미 있는 (노선·출발일·패턴) 칸은 **중복으로 넣지 않는다**. 금액이 다르면 완본값으로 갱신하고 그 내역을 보고한다.
  · 기존 호텔 538곳 · 다른 항공 노선 · 당일치기 딜은 1건도 건드리지 않는다(병합 뒤 바이트 비교로 확인).
  · `counts`(total · byMonth · holiday · daytrip)만 다시 센다. 호텔 지표는 그대로 둔다.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge_flights_china_new8 as base   # 파서·표기 변환·날짜 계산을 그대로 쓴다

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

WITHIN = ('YNJ', 'DYG', 'KWL', 'TXN')          # 완본이 도착한 4노선
WEEKEND = ('목~일', '금~일', '토~월', '금~월', '목~월')
# 원문이 말하는 칸 수 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT = {
    'YNJ': {'values': 45, 'nosale': 0},
    'DYG': {'values': 45, 'nosale': 0},
    'KWL': {'values': 45, 'nosale': 0},
    'TXN': {'values': 18, 'nosale': 27},
}
EXPECT_DAYTRIP = {('YNJ', '2026-12-05', '토~토'): 495100,
                  ('DYG', '2026-12-05', '토~토'): 793000}
EXPECT_DAYTRIP_NOSALE = {('KWL', '2026-12-05', '토~토'), ('TXN', '2026-12-05', '토~토')}
EXPECT_NOSALE_TOTAL = 29          # 4절 당일치기 불가 2 + 부록 0건 27


def merge(master, weekend, daytrip, nosale):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in WITHIN:
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)

    added, updated, same, conflicts = [], [], [], []
    for (code, date, pattern), deal in sorted(weekend.items()):
        r = routes[code]
        have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
        if have is None:
            r['deals'].append(deal)
            added.append((code, date, pattern, deal['price']))
            continue
        if have == deal:
            same.append((code, date, pattern))
            continue
        if have.get('price') == deal.get('price') and have.get('back') == deal.get('back'):
            # 금액·귀국일이 같은데 표기만 다르면 기존 줄을 그대로 둔다(이력 보존)
            same.append((code, date, pattern))
            continue
        conflicts.append((code, date, pattern, have.get('price'), deal.get('price')))
        have.update(deal)            # 완본의 최신 실측가가 우선
        updated.append((code, date, pattern, deal['price']))

    for (code, date, pattern), deal in sorted(daytrip.items()):
        r = routes[code]
        have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
        want = EXPECT_DAYTRIP.get((code, date, pattern))
        if want is not None and deal['price'] != want:
            raise SystemExit('당일치기 금액 불일치 %s %s: 부록 %s원 / 기대 %s원'
                             % (code, pattern, deal['price'], want))
        if have is None:
            r['deals'].append(deal)
            added.append((code, date, pattern, deal['price']))
        else:
            same.append((code, date, pattern))

    for r in fl['routes']:
        r['deals'].sort(key=lambda d: (d['date'], base.WD[d['pattern'][0]]))

    known = {(n['code'], n['date'], n['pattern']) for n in fl['noSale']}
    deal_keys = {(r['code'], d['date'], d['pattern']) for r in fl['routes'] for d in r['deals']}
    new_nosale = []
    for key, entry in sorted(nosale.items()):
        if key in known:
            continue
        if key in deal_keys:
            raise SystemExit('판매편 0건 칸이 실측 딜과 겹칩니다: %s' % (key,))
        fl['noSale'].append(entry)
        new_nosale.append(key)
    fl['noSale'].sort(key=lambda n: (n['date'], n['code']))

    all_deals = [d for r in fl['routes'] for d in r['deals']]
    by_month = {}
    for d in all_deals:
        by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    fl['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month[k] for k in sorted(by_month)},
        'holiday': sum(1 for d in all_deals if d['date'] in base.HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals if d['pattern'].split('~')[0] == d['pattern'].split('~')[1]),
    }
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = len(all_deals)
    return added, updated, same, conflicts, new_nosale


def main(argv):
    ap = argparse.ArgumentParser(description='중국 4노선 12~1월 완본 md → master_db.json flights 병합')
    ap.add_argument('md', help='완본 파일(연길·장가계·구이린·황산 180칸)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    w, d, ns, gaps = base.parse_second(text)

    # 1) 원문 칸 수와 파싱 결과가 정확히 맞는지
    per = {}
    for code, date, pattern in w:
        per.setdefault(code, {'values': 0, 'nosale': 0})['values'] += 1
    for code, date, pattern in ns:
        if (code, date, pattern) in EXPECT_DAYTRIP_NOSALE:
            continue           # 0박 불가 2칸은 부록 0건 27칸과 별개
        per.setdefault(code, {'values': 0, 'nosale': 0})['nosale'] += 1
    bad = []
    for code in WITHIN:
        got = per.get(code, {'values': 0, 'nosale': 0})
        if got != EXPECT[code]:
            bad.append('%s 값 %d/0건 %d (기대 %d/%d)' % (code, got['values'], got['nosale'],
                                                       EXPECT[code]['values'], EXPECT[code]['nosale']))
    if len(w) != 153 or len(d) != 2 or len(ns) != EXPECT_NOSALE_TOTAL:
        bad.append('전체 값 %d + 당일치기 %d / 0건 %d (기대 153 + 2 / %d)'
                   % (len(w), len(d), len(ns), EXPECT_NOSALE_TOTAL))
    if gaps:
        bad.append('미측정 줄 %d개 — 완본에는 없어야 합니다' % len(gaps))
    for code in WITHIN:
        pats = {p for (c, _, p) in list(w) + list(ns) if c == code}
        missing = set(WEEKEND) - pats
        if missing:
            bad.append('%s 패턴 누락: %s' % (code, sorted(missing)))
    for code in WITHIN:
        weeks = set()
        for (c, date, _) in list(w) + list(ns):
            if c != code:
                continue
            # 주 구분은 그 주 목요일 — 목요일(ISO 4)까지의 일수를 빼서 주 시작(목)을 구한다
            d0 = datetime.date.fromisoformat(date)
            thu = d0 - datetime.timedelta(days=(d0.isoweekday() - 4) % 7)
            weeks.add(thu.isoformat())
            weeks.add(thu.isoformat())
        if len(weeks) != 9:
            bad.append('%s 주 수 %d (기대 9): %s' % (code, len(weeks), sorted(weeks)))
    print('  값 %d칸 + 당일치기 %d칸 + 판매편 0건 %d칸 = %d칸' % (len(w), len(d), len(ns), len(w) + len(d) + len(ns)))
    print('  노선별: %s' % ', '.join('%s %d/%d' % (c, per[c]['values'], per[c]['nosale']) for c in WITHIN))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_total = master['flights']['counts']['total']
    before_nosale = len(master['flights']['noSale'])
    before_other = json.dumps([r for r in master['flights']['routes'] if r['code'] not in WITHIN],
                              ensure_ascii=False, sort_keys=True)
    before_within = {(r['code'], dz['date'], dz['pattern']): dz
                     for r in master['flights']['routes'] if r['code'] in WITHIN for dz in r['deals']}

    added, updated, same, conflicts, new_nosale = merge(master, w, d, ns)

    # 2) 보존 검증 — 호텔·아코르·다른 노선은 한 바이트도 바뀌면 안 된다
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps([r for r in master['flights']['routes'] if r['code'] not in WITHIN],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 항공 노선 데이터가 바뀌었습니다.')
    for r in master['flights']['routes']:
        if r['code'] not in WITHIN:
            continue
        keys = [(dz['date'], dz['pattern']) for dz in r['deals']]
        if len(keys) != len(set(keys)):
            raise SystemExit('%s (출발일·패턴) 중복' % r['code'])
    # 기존 87칸은 그대로 남아 있어야 한다(삭제 금지)
    after_within = {(r['code'], dz['date'], dz['pattern']): dz
                    for r in master['flights']['routes'] if r['code'] in WITHIN for dz in r['deals']}
    lost = [k for k in before_within if k not in after_within]
    if lost:
        raise SystemExit('기존 딜이 사라졌습니다: %s' % lost)

    print('기존 4노선 딜 %d건 중 그대로 %d건 · 신규 %d건 · 갱신 %d건(금액 차이 %d)'
          % (len(before_within), len(same), len(added), len(updated), len(conflicts)))
    for c in conflicts:
        print('  ! 금액 갱신 %s %s %s: %s → %s원' % c)
    print('신규 판매편 0건 %d건 → noSale %d건' % (len(new_nosale), len(master['flights']['noSale'])))
    print('총 %d건 → %d건 · 주말형 %d · 당일치기 %d' % (
        before_total, master['flights']['counts']['total'],
        master['flights']['counts']['total'] - master['flights']['counts']['daytrip'],
        master['flights']['counts']['daytrip']))
    print('월별: %s' % master['flights']['counts']['byMonth'])
    print('4노선 건수: %s' % ', '.join(
        '%s %d' % (r['code'], len(r['deals'])) for r in master['flights']['routes'] if r['code'] in WITHIN))

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
