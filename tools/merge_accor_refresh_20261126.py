#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 아코르 — 60~90일 구간(2027-01-25~02-24) 재실측 병합 (2026-11-26 04:00 스케줄).

입력  /workspace/work/accor_refresh_20261126/raw.json      (오늘 실측)
      /workspace/work/accor_refresh_20261125/raw.json      (전일 실측 — 상대 변화 기준)

값 기준 (계수 추정 없음)
  · ② 아코르 259곳 가운데 218곳은 전일(2026-11-25 04:00)에 창 전체를 이미 실측했고,
    국내 28곳은 회원 최저가 계열 365일 일일 갱신이 따로 돈다 → 오늘은 손대지 않는다.
  · 오늘 대상 13곳은 관측일이 2026-11-21~24 로 오래됐으면서 카드 안에 요율 계열이 섞여
    (저장값÷표시액 비율이 날짜별로 1.18/1.37처럼 갈림) 단일 계수 덮어쓰기로는 어제도 제외된 곳이다.
    이 카드들은 **날짜별 상대 변화**로 갱신한다:
        새 값 = 기존 값 × (오늘 표시액 ÷ 전일 표시액)
    각 칸의 기존 계열(요율 종류·세금 포함 여부)을 그대로 둔 채, 원천에서 그 날짜의 최저가가
    실제로 움직인 만큼만 옮긴다. 전일 표시액이 없거나 기존 값이 없는 칸은 건드리지 않는다.
  · 요금이 없는 날(미판매·매진)은 null 로 남긴다 — 추측·보간하지 않는다.
  · 표시 자릿수는 그 호텔의 기존 칸에 맞춘다.

사용법: python3 tools/merge_accor_refresh_20261126.py [--dry]
"""
import datetime
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
RAW = '/workspace/work/accor_refresh_20261126/raw.json'
PREV = '/workspace/work/accor_refresh_20261125/raw.json'
TARGETS = '/workspace/work/accor_refresh_20261126/targets.json'
NOTE = ' · 2027-01-25~02-24(60~90일) 구간은 2026-11-26 04:00 재실측(같은 API 기준·날짜별 전일 대비)'
NOTE_RE = re.compile(r' · \d{4}-\d{2}-\d{2}~\d{2}-\d{2}\(60~90일\) 구간은 [^·]*?재실측\([^)]*\)')
DRY = '--dry' in sys.argv

WS = datetime.date(2027, 1, 25)
WIN = [(WS + datetime.timedelta(days=i)).isoformat() for i in range(31)]
MIN_REL = 0.005          # 0.5% 안쪽은 환율·반올림 잔차로 보고 그대로 둔다
HOTEL_MED_GUARD = 0.12   # 호텔 중앙값이 ±12% 넘게 움직이면 요율 종류가 바뀐 것으로 보고 그 호텔은 건너뛴다


def amt(rec, d):
    if not rec:
        return None
    v = (rec.get('days') or {}).get(d)
    if v is None:
        v = (rec.get('near') or {}).get(d)
    return (v or {}).get('amt')


def digits_of(hotel):
    vals = [hotel['rates'].get(d) for d in WIN if hotel['rates'].get(d)]
    for step in (1000, 500, 250, 100, 10):
        if vals and all(v % step == 0 for v in vals):
            return step
    return 1


def main():
    raw = json.load(open(RAW, encoding='utf-8'))
    prev = json.load(open(PREV, encoding='utf-8'))
    targets = json.load(open(TARGETS, encoding='utf-8'))['hotels']
    master = json.load(open(MASTER, encoding='utf-8'))
    by_id = {h['id']: h for h in master['hotels']}

    report, skips, big_all = [], [], []
    for t in targets:
        hid = t['id']
        h = by_id[hid]
        cur, old_rec = raw.get(hid), prev.get(hid)
        if not cur:
            skips.append((hid, h['name'], t['zone'], '오늘 수집 자료 없음'))
            continue
        rels = []
        for d in WIN:
            a, p = amt(cur, d), amt(old_rec, d)
            if a and p:
                rels.append(a / p)
        if not rels:
            skips.append((hid, h['name'], t['zone'], '전일과 겹치는 날짜가 없어 상대 변화 산출 불가'))
            continue
        med_rel = statistics.median(rels)
        if abs(med_rel - 1) > HOTEL_MED_GUARD:
            skips.append((hid, h['name'], t['zone'],
                          '중앙 상대변화 %+.1f%% — 요율 종류가 바뀐 것으로 보여 건너뜀' % ((med_rel - 1) * 100)))
            continue

        step = digits_of(h)
        rates = h['rates']
        changed = same = to_null = nobase = noprev = 0
        cell_rels, big = [], []
        for d in WIN:
            a, p, old = amt(cur, d), amt(old_rec, d), rates.get(d)
            if not a:
                if old is not None:
                    to_null += 1
                    rates[d] = None
                    big.append((d, old, 'null'))
                continue
            if not p:
                noprev += 1
                continue
            if old is None:
                nobase += 1
                continue
            new = int(round(old * (a / p) / step)) * step
            if old and abs(new - old) <= old * MIN_REL:
                same += 1
                continue
            cell_rels.append(new / old)
            if old and (new / old <= 0.5 or new / old >= 1.5):
                big.append((d, old, new))
            rates[d] = new
            changed += 1
        src = NOTE_RE.sub('', h.get('source') or '')
        if NOTE not in src:
            h['source'] = src + NOTE
        report.append({'id': hid, 'name': h['name'], 'zone': t['zone'], 'group': t.get('group'),
                       'med_rel': med_rel, 'n': len(rels), 'step': step, 'changed': changed,
                       'same': same, 'null': to_null, 'nobase': nobase, 'noprev': noprev,
                       'big': big,
                       'cell_med': statistics.median(cell_rels) if cell_rels else None})
        if big:
            big_all.append((hid, h['name'], big))

    print('%-7s %-30s %-5s %-5s %6s %3s %5s %5s %5s %5s %6s  %s' % (
        'id', 'name', 'zone', 'group', '전일%', 'n', 'chg', 'same', 'null', 'nobase', '셀중앙', '50%+'))
    for r in sorted(report, key=lambda x: ({'stale': 0, 'hub': 1, 'check': 2}.get(x['group'], 9), x['id'])):
        print('%-7s %-30s %-5s %-5s %6.2f %3d %5d %5d %5d %5d %6s  %s' % (
            r['id'], r['name'][:30], r['zone'], r['group'], (r['med_rel'] - 1) * 100, r['n'],
            r['changed'], r['same'], r['null'], r['nobase'],
            '%+.1f%%' % ((r['cell_med'] - 1) * 100) if r['cell_med'] else '-',
            ' '.join('%s %s→%s' % b for b in r['big'][:2]) or '-'))
    tot = lambda k: sum(r[k] for r in report)
    print('합계 호텔 %d곳 · changed=%d same=%d null=%d nobase=%d noprev=%d' % (
        len(report), tot('changed'), tot('same'), tot('null'), tot('nobase'), tot('noprev')))
    print('\nSKIP %d곳' % len(skips))
    for hid, name, zone, why in skips:
        print('  %-7s %-30s %-5s %s' % (hid, name[:30], zone, why))
    if big_all:
        print('\n50% 이상 변동')
        for hid, name, big in big_all:
            print('  %s %s %s' % (hid, name[:24], big))

    if DRY:
        print('\n(dry — 저장하지 않음)')
        return
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
