#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 아코르 — 60~90일 구간(2027-01-27~02-26) 재실측 병합 (2026-11-28 04:00 스케줄).

입력  /workspace/work/accor_refresh_20261128/raw.json      (오늘 실측)
      /workspace/work/accor_refresh_20261127/raw.json      (전일 실측 — 24시간 전, 있는 호텔)
      /workspace/work/accor_refresh_20261126/raw.json      (그 전 실측 — 48시간 전)

값 기준
  · 오늘 대상 230곳은 창(01-26~02-25)에 요금이 있는 ② 아코르 가운데 국내 28곳(회원 최저가
    계열 365일 일일 갱신이 따로 돎)과 c9933(중올플 md 계열)을 뺀 전부다. 204곳은 11-25 이후,
    26곳은 11-26 이후 처음 읽는다.
  · 각 칸은 그 칸의 기존 계열(요율 종류·세금 포함 여부)을 그대로 두고, 원천이 그 날짜에 실제로
    움직인 만큼만 옮긴다:
        새 값 = 기존 값 × (오늘 표시액 ÷ 전일 표시액)
    전일 원본은 11-26 raw 를 먼저 쓰고, 없으면 11-25 raw(2일 전)를 쓴다.
  · 전일 표시액이 없는 칸은 그 호텔의 계열 계수(기존값÷전일 표시액 중앙값)로 옮긴다 —
    계열이 고를 때(계열 MAD 2% 이내)만.
  · 기존 값이 빈 칸에 오늘 요금이 있으면 같은 계열 계수로 채운다(계열이 고를 때만).
  · 요금이 없는 날(미판매·매진)은 null 로 남긴다 — 추측·보간하지 않는다. 단 그 날짜를 읽은
    호출이 실패한 덩어리면 값을 건드리지 않는다.
  · 호텔 중앙 상대변화가 ±15%를 넘을 때는 요율 종류가 바뀐 것으로 보고 건너뛴다. 다만 계열이
    아주 고르고(계열 MAD 2% 이내) 요율 코드가 전 날짜 같으면 원천의 일괄 요금 개정으로 보고
    반영하되 '요율 일괄 변동'으로 따로 표시한다.
  · 표시 자릿수는 그 호텔의 기존 칸에 맞춘다.

사용법: python3 tools/merge_accor_refresh_20261128.py [--dry]
"""
import collections
import datetime
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
BASE = '/workspace/work/accor_refresh_20261128'
RAW = os.path.join(BASE, 'raw.json')
PREVS = ['/workspace/work/accor_refresh_20261127/raw.json',
         '/workspace/work/accor_refresh_20261126/raw.json']
TARGETS = os.path.join(BASE, 'targets.json')
NOTE = ' · 2027-01-27~02-26(60~90일) 구간은 2026-11-28 04:00 재실측(같은 API 기준·날짜별 전일 대비)'
NOTE_RE = re.compile(r' · \d{4}-\d{2}-\d{2}~\d{2}-\d{2}\(60~90일\) 구간은 [^·]*?재실측\([^)]*\)')
DRY = '--dry' in sys.argv

WS = datetime.date(2027, 1, 27)
WIN = [(WS + datetime.timedelta(days=i)).isoformat() for i in range(31)]
MIN_REL = 0.005          # 0.5% 안쪽은 환율·반올림 잔차로 보고 그대로 둔다
HOTEL_MED_GUARD = 0.15   # 호텔 중앙 상대변화 ±15% 초과 → 요율 종류 변경 의심
SERIES_MAD = 0.02        # 계열 계수(기존값÷전일 표시액) 흩어짐 허용치


def amt(rec, d):
    if not rec:
        return None
    v = (rec.get('days') or {}).get(d)
    if v is None:
        v = (rec.get('near') or {}).get(d)
    return (v or {}).get('amt')


def rate_of(rec, d):
    if not rec:
        return None
    v = (rec.get('days') or {}).get(d)
    if v is None:
        v = (rec.get('near') or {}).get(d)
    return (v or {}).get('rate')


def digits_of(hotel):
    vals = [hotel['rates'].get(d) for d in WIN if hotel['rates'].get(d)]
    for step in (1000, 500, 250, 100, 10):
        if vals and all(v % step == 0 for v in vals):
            return step
    return 1


def main():
    raw = json.load(open(RAW, encoding='utf-8'))
    prev = {}
    for p in reversed(PREVS):          # 11-25 먼저 → 11-26 이 덮는다
        if os.path.exists(p):
            prev.update(json.load(open(p, encoding='utf-8')))
    targets = json.load(open(TARGETS, encoding='utf-8'))['hotels']
    master = json.load(open(MASTER, encoding='utf-8'))
    by_id = {h['id']: h for h in master['hotels']}

    report, skips, big_all = [], [], []
    for t in targets:
        hid = t['id']
        h = by_id.get(hid)
        if h is None:
            skips.append((hid, t['name'], t['zone'], '마스터에 없는 호텔'))
            continue
        cur, old_rec = raw.get(hid), prev.get(hid)
        if not cur:
            skips.append((hid, h['name'], t['zone'], '오늘 수집 자료 없음'))
            continue
        chunks = cur.get('chunks') or {}

        def chunk_ok(d):
            if not chunks:
                return True
            wk = [k for k in chunks if k <= d]
            return bool(wk) and chunks[max(wk)] == 'ok'

        rates = h.get('rates') or {}
        rels, coefs = [], []
        for d in WIN:
            a, p, old = amt(cur, d), amt(old_rec, d), rates.get(d)
            if a and p:
                rels.append(a / p)
                if old:
                    coefs.append(old / p)
        if not rels:
            skips.append((hid, h['name'], t['zone'], '전일과 겹치는 날짜가 없어 상대 변화 산출 불가'))
            continue
        med_rel = statistics.median(rels)
        coef = statistics.median(coefs) if coefs else None
        coef_mad = (statistics.median([abs(c - coef) for c in coefs]) / coef) if coef else None
        codes_today = collections.Counter(rate_of(cur, d) for d in WIN).most_common(1)[0][0]
        codes_prev = collections.Counter(rate_of(old_rec, d) for d in WIN).most_common(1)[0][0]
        bulk_move = False
        if abs(med_rel - 1) > HOTEL_MED_GUARD:
            clean = coef_mad is not None and coef_mad < SERIES_MAD and codes_today == codes_prev
            if not clean:
                skips.append((hid, h['name'], t['zone'],
                              '중앙 상대변화 %+.1f%% · 계열 MAD %s · 요율코드 %s→%s — 요율 종류가 바뀐 것으로 보여 건너뜀'
                              % ((med_rel - 1) * 100,
                                 '%.3f' % coef_mad if coef_mad is not None else '-',
                                 codes_prev, codes_today)))
                continue
            bulk_move = True

        step = digits_of(h)
        changed = same = to_null = nobase = noprev = guarded = 0
        cell_rels, big = [], []
        for d in WIN:
            a, p, old = amt(cur, d), amt(old_rec, d), rates.get(d)
            if not a:
                if old is not None:
                    if chunk_ok(d):
                        to_null += 1
                        rates[d] = None
                        big.append((d, old, 'null'))
                    else:
                        guarded += 1
                continue
            if old is None:
                if coef is not None and coef_mad is not None and coef_mad < SERIES_MAD:
                    rates[d] = int(round(a * coef / step)) * step
                    nobase += 1
                continue
            if p:
                new = int(round(old * (a / p) / step)) * step
            elif coef is not None and coef_mad is not None and coef_mad < SERIES_MAD:
                noprev += 1
                new = int(round(a * coef / step)) * step
            else:
                noprev += 1
                continue
            if new == old or abs(new - old) <= old * MIN_REL:
                same += 1
                continue
            cell_rels.append(new / old)
            if new / old <= 0.5 or new / old >= 1.5:
                big.append((d, old, new))
            rates[d] = new
            changed += 1
        src = NOTE_RE.sub('', h.get('source') or '')
        if NOTE not in src:
            h['source'] = src + NOTE
        report.append({'id': hid, 'name': h['name'], 'zone': t['zone'], 'group': t.get('group'),
                       'med_rel': med_rel, 'n': len(rels), 'step': step, 'changed': changed,
                       'same': same, 'null': to_null, 'nobase': nobase, 'noprev': noprev,
                       'guarded': guarded, 'coef_mad': coef_mad, 'bulk': bulk_move, 'big': big,
                       'cell_med': statistics.median(cell_rels) if cell_rels else None})
        if big:
            big_all.append((hid, h['name'], big))

    hdr = '%-7s %-30s %-5s %-6s %7s %3s %5s %5s %5s %5s %6s  %s'
    print(hdr % ('id', 'name', 'zone', 'group', '전일%', 'n', 'chg', 'same', 'null', 'new', '셀중앙', '50%+'))
    for r in sorted(report, key=lambda x: ({'old48h': 0, 'yday': 1}.get(x['group'], 9), x['id'])):
        print('%-7s %-30s %-5s %-6s %7s %3d %5d %5d %5d %5d %6s  %s' % (
            r['id'], r['name'][:30], r['zone'], r['group'] + ('*' if r['bulk'] else ''),
            '%+.2f' % ((r['med_rel'] - 1) * 100) if r['med_rel'] is not None else '-',
            r['n'], r['changed'], r['same'], r['null'], r['nobase'],
            '%+.1f%%' % ((r['cell_med'] - 1) * 100) if r['cell_med'] else '-',
            ' '.join('%s %s→%s' % b for b in r['big'][:2]) or '-'))
    tot = lambda k: sum(r[k] for r in report)
    print('합계 호텔 {}곳 · changed={} same={} null={} new={} noprev={} guarded={}'.format(
        len(report), tot('changed'), tot('same'), tot('null'), tot('nobase'), tot('noprev'), tot('guarded')))
    print('\nSKIP {}곳'.format(len(skips)))
    for hid, name, zone, why in skips:
        print('  %-7s %-30s %-5s %s' % (hid, name[:30], zone, why))
    if big_all:
        print('\n50퍼센트 이상 변동 {}곳'.format(len(big_all)))
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
