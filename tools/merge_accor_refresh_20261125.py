#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 아코르 — 60~90일 구간(2027-01-24~2027-02-23) 재실측 병합 (2026-11-25 04:00 스케줄).

입력  /workspace/work/accor_refresh_20261125/raw.json
      (collect.py 가 all.accor.com 이 쓰는 공식 GraphQL api.accor.com/bff/v1/graphql
       hotelOffers.calendar 로 창 안 31일 + 창 밖 이웃 14일을 8일 단위 조회.
       1박·성인 2인·1객실·KRW·countryMarket KR)

값 기준 (호텔별 계수 = 지금 365일 칸이 어느 요율·세금 계열로 채워져 있는지 실측으로 판정)
  · 창 안·밖에서 겹치는 날들의 `저장값 ÷ API 표시액` 비율을 모아 **중앙값**을 그 호텔의 계수로 쓴다.
    (중국 13곳처럼 표시액 그대로인 호텔은 1.000, 태국처럼 세금 포함으로 저장된 호텔은 1.18 등)
  · 비율의 중앙절대편차(MAD)가 3%를 넘으면 계열이 섞인 카드로 보고 **건드리지 않는다**(SKIP).
  · 국내(kr) 30곳은 저장값이 회원가·다른 요율 계열이라 공개 API 값으로 대체하면 추정이 된다.
    계수가 1.000 로 확인된 카드만 직접 대조로 갱신하고 나머지는 SKIP 한다.
  · 요금이 없는 날(미판매·매진)은 null 로 남긴다 — 추측·보간하지 않는다.
  · 표시 자릿수는 그 호텔의 기존 칸에 맞춘다(정확값 198곳 · 1,000원 단위 47곳 등).

사용법: python3 tools/merge_accor_refresh_20261125.py [--dry]
"""
import datetime
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
RAW = '/workspace/work/accor_refresh_20261125/raw.json'
TARGETS = '/workspace/work/accor_refresh_20261125/targets.json'
NOTE = ' · 2027-01-24~02-23(60~90일) 구간은 2026-11-25 04:00 재실측(같은 API 기준)'
import re
NOTE_RE = re.compile(r' · \d{4}-\d{2}-\d{2}~\d{2}-\d{2}\(60~90일\) 구간은 [^·]*?재실측\(같은 API 기준\)')
DRY = '--dry' in sys.argv

WS = datetime.date(2027, 1, 24)
WIN = [(WS + datetime.timedelta(days=i)).isoformat() for i in range(31)]
NEAR = ([(datetime.date(2027, 1, 17) + datetime.timedelta(days=i)).isoformat() for i in range(7)] +
        [(datetime.date(2027, 2, 24) + datetime.timedelta(days=i)).isoformat() for i in range(7)])

MAD_MAX = 0.03
N_MIN = 20
# 재실측 값이 기존 칸과 0.5% 안쪽이면 그대로 둔다 — 환율 환산 잔차(±0.3%)를 '변동'으로 남기지 않는다.
MIN_REL = 0.005
KR_FACTOR_TOL = 0.005
FIXED_SKIP = {
    'c9933': 'all.accor.com 연중 UNAVAILABLE — 이번 조회도 31일 전부 요금 없음(기존 값 유지)',
    'dC3E6': '이번 조회에서 31일 중 30일 요금 없음 — 계열 판정 불가·전면 매진으로 단정하지 않는다(기존 값 유지)',
}


def factor_of(hotel, rec):
    ratios = []
    for days, src in ((WIN, rec['days']), (NEAR, rec['near'])):
        for d in days:
            amt = (src.get(d) or {}).get('amt')
            old = hotel['rates'].get(d)
            if amt and old:
                ratios.append(old / amt)
    if not ratios:
        return None, None, 0
    med = statistics.median(ratios)
    mad = statistics.median([abs(x - med) for x in ratios]) / med
    return med, mad, len(ratios)


def digits_of(hotel):
    vals = [hotel['rates'].get(d) for d in WIN if hotel['rates'].get(d)]
    for step in (1000, 500, 250, 100, 10):
        if vals and all(v % step == 0 for v in vals):
            return step
    return 1


def main():
    raw = json.load(open(RAW, encoding='utf-8'))
    targets = json.load(open(TARGETS, encoding='utf-8'))['hotels']
    master = json.load(open(MASTER, encoding='utf-8'))
    by_id = {h['id']: h for h in master['hotels']}

    report, skips, big_all = [], [], []
    for t in targets:
        hid = t['id']
        h = by_id[hid]
        rec = raw.get(hid)
        if not rec:
            skips.append((hid, h['name'], t['zone'], '수집 자료 없음'))
            continue
        if hid in FIXED_SKIP:
            skips.append((hid, h['name'], t['zone'], FIXED_SKIP[hid]))
            continue
        fac, mad, n = factor_of(h, rec)
        if fac is None:
            skips.append((hid, h['name'], t['zone'], '겹치는 날이 없어 계열 판정 불가'))
            continue
        if n < N_MIN or mad > MAD_MAX:
            skips.append((hid, h['name'], t['zone'],
                          '계열 불안정(겹침 %d일 · MAD %.1f%% · 중앙값 %.3f)' % (n, mad * 100, fac)))
            continue
        if t['zone'] == 'kr':
            # 2026-11-25 04:00 국내 아코르 일일 갱신(tools/merge_accor_daily_20261125.py)이 30곳 365일을
            #   이미 회원 최저가로 다시 채웠다 — 같은 날 같은 구간을 공개 API 계수로 덮지 않는다.
            skips.append((hid, h['name'], t['zone'],
                          '국내는 같은 날 04:00 일일 갱신에서 365일 전량 재조회됨(회원 최저가 계열)'))
            continue

        step = digits_of(h)
        rates = h['rates']
        changed = same = newfill = to_null = 0
        big = []
        for d in WIN:
            amt = (rec['days'].get(d) or {}).get('amt')
            old = rates.get(d)
            if not amt:
                if old is not None:
                    to_null += 1
                    big.append((d, old, 'null'))
                rates[d] = None
                continue
            new = int(round(amt * fac / step)) * step
            if old is not None and abs(new - old) <= old * MIN_REL:
                same += 1
                continue
            if old is None:
                newfill += 1
            elif old != new:
                changed += 1
                if old and (new / old <= 0.5 or new / old >= 1.5):
                    big.append((d, old, new))
            else:
                same += 1
            rates[d] = new
        src = NOTE_RE.sub('', h.get('source') or '')
        if NOTE not in src:
            h['source'] = src + NOTE
        report.append({'id': hid, 'name': h['name'], 'zone': t['zone'], 'fac': fac, 'mad': mad,
                       'n': n, 'step': step, 'changed': changed, 'same': same,
                       'new': newfill, 'null': to_null, 'big': big})
        if big:
            big_all.append((hid, h['name'], big))

    order = {'cn': 0, 'sea': 1, 'kr': 2, 'etc': 3}
    print('%-7s %-26s %-4s %6s %6s %5s %5s %5s %5s  %s' % (
        'id', 'name', 'zone', '계수', 'MAD', 'chg', 'same', 'new', 'null', '50%+'))
    for r in sorted(report, key=lambda x: (order.get(x['zone'], 9), -x['changed'])):
        print('%-7s %-26s %-4s %6.3f %5.1f%% %5d %5d %5d %5d  %s' % (
            r['id'], r['name'][:26], r['zone'], r['fac'], r['mad'] * 100,
            r['changed'], r['same'], r['new'], r['null'],
            ' '.join('%s %s→%s' % b for b in r['big'][:3]) or '-'))
    tot = lambda k: sum(r[k] for r in report)
    print('합계 호텔 %d곳 · changed=%d same=%d newfill=%d null=%d' % (
        len(report), tot('changed'), tot('same'), tot('new'), tot('null')))
    byz = {}
    for r in report:
        z = byz.setdefault(r['zone'], [0, 0, 0, 0])
        z[0] += 1
        z[1] += r['changed']
        z[2] += r['new']
        z[3] += r['null']
    print('지역별', {k: '호텔 %d · 변경 %d · 새값 %d · null %d' % tuple(v) for k, v in byz.items()})
    print('\nSKIP %d곳' % len(skips))
    for hid, name, zone, why in skips:
        print('  %-7s %-26s %-4s %s' % (hid, name[:26], zone, why))
    if big_all:
        print('\n50%% 이상 변동')
        for hid, name, big in big_all:
            print('  %s %s %s' % (hid, name[:24], big))

    if DRY:
        print('\n(dry — 저장하지 않음)')
        return
    # 집계값(칸·요금 있음·없음)은 마스터 DB 안에도 적혀 verify 가 대조한다 — 함께 갱신한다.
    cnt = master.setdefault('counts', {})
    cells = sum(len(h.get('rates') or {}) for h in master['hotels'])
    priced = sum(1 for h in master['hotels'] for v in (h.get('rates') or {}).values() if v is not None)
    before = (cnt.get('cells'), cnt.get('priced'), cnt.get('na'))
    cnt['cells'] = cells
    cnt['priced'] = priced
    cnt['na'] = cells - priced
    print('집계 갱신 cells/priced/na %s → %s' % (before, (cells, priced, cells - priced)))
    with open(MASTER, 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('\n저장', MASTER)


if __name__ == '__main__':
    main()
