#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 한·일 핵심 20곳 90일(2026-12-01~2027-02-28) 재실측 병합 — 2026-11-28.

입력: 4번(@jin_4) 피클이 2026-11-27 보낸 4개 배치
  memory/clones/06130525-jin489/pickle/2026-11-27-0600/received/0-ihg-refresh-batch1.json
  .../1-ihg-refresh-batch2.json  .../0-ihg-refresh-batch3.json  .../0-ihg-refresh-batch4.json
  (i01~i20 · 각 90일 · 세후 KRW 현금 + 리워드 포인트 · 하루 = {cash_krw, points})

원칙
  · 2026-12-01~2027-02-28 90칸만 새 값으로 덮는다. 2027-03-01 이후는 2026-11-22 값 그대로.
  · 새 배치가 null 이면 그 날은 미판매/매진으로 보고 null 로 둔다(보간 금지).
  · 오탐은 덮지 않는다 — i07(인터컨티넨탈 알펜시아) 2027-01-09 현금 2,500,000원은
    앞뒤 같은 주 토요일 231,000~391,000원과 6.4배 차이라 달력 오독으로 보고 기존 값(391,000)을 남긴다.
"""
import json
import os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAB = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
REC = '/workspace/memory/clones/06130525-jin489/pickle/2026-11-27-0600/received/'
FILES = ['0-ihg-refresh-batch1.json', '1-ihg-refresh-batch2.json',
         '0-ihg-refresh-batch3.json', '0-ihg-refresh-batch4.json']
START, END = '2026-12-01', '2027-02-28'

# 오탐으로 판정해 덮지 않는 칸 (id, 날짜) → 사유
KEEP = {('i07', '2027-01-09'): '현금 2,500,000원(주변 토요일 231,000~391,000원의 6.4배) — 달력 오독 의심'}


def days_of(start, end):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while d0 <= d1:
        out.append(d0.isoformat())
        d0 += timedelta(days=1)
    return out


def arr_to_map(blk):
    if not blk:
        return {}
    d0 = date.fromisoformat(blk['$d'])
    return {(d0 + timedelta(days=i)).isoformat(): v for i, v in enumerate(blk['$v'])}


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    hotels = {h['id']: h for h in tab['hotels']}
    new = {}
    for f in FILES:
        for h in json.load(open(REC + f, encoding='utf-8'))['hotels']:
            new[h['id']] = h

    WIN = days_of(START, END)
    stat = {'hotels': 0, 'cash_set': 0, 'cash_chg': 0, 'cash_null': 0, 'pts_set': 0,
            'pts_chg': 0, 'pts_null': 0, 'kept': [], 'missing': []}
    for hid in sorted(new):
        h = hotels.get(hid)
        if not h:
            stat['missing'].append(hid)
            continue
        nd = new[hid]['days']
        old_c = arr_to_map(h['rates'])
        old_p = arr_to_map(h['points'])
        d0 = date.fromisoformat(h['rates']['$d'])
        cv = list(h['rates']['$v'])
        pv = list(h['points']['$v'])
        for d in WIN:
            ok = (date.fromisoformat(d) - d0).days
            if not (0 <= ok < len(cv)):
                continue
            cell = nd.get(d) or {}
            c, p = cell.get('cash_krw'), cell.get('points')
            if (hid, d) in KEEP and c is not None:
                # 현금만 기존 값 유지(오탐), 포인트는 새 값 반영
                stat['kept'].append((hid, d, c, old_c.get(d)))
                cv[ok] = old_c.get(d)
                if p is not None:
                    if old_p.get(d) is None:
                        stat['pts_set'] += 1
                    elif old_p.get(d) != p:
                        stat['pts_chg'] += 1
                    pv[ok] = p
                elif old_p.get(d) is not None:
                    stat['pts_null'] += 1
                    pv[ok] = None
                continue
            if c is not None:
                if old_c.get(d) is None:
                    stat['cash_set'] += 1
                elif old_c.get(d) != c:
                    stat['cash_chg'] += 1
                cv[ok] = c
            else:
                if old_c.get(d) is not None:
                    stat['cash_null'] += 1
                cv[ok] = None
            if p is not None:
                if old_p.get(d) is None:
                    stat['pts_set'] += 1
                elif old_p.get(d) != p:
                    stat['pts_chg'] += 1
                pv[ok] = p
            else:
                if old_p.get(d) is not None:
                    stat['pts_null'] += 1
                pv[ok] = None
        h['rates']['$v'] = cv
        h['points']['$v'] = pv
        h['cells'] = {'rates': sum(1 for v in cv if v is not None),
                      'points': sum(1 for v in pv if v is not None)}
        note = h.get('note') or ''
        add = ('2026-12-01~2027-02-28 90일 현금·포인트는 2026-11-27 4번(@jin_4) 재실측값으로 갱신했다'
               '(2026-11-28 병합 · 세후 KRW · 리워드 재고 없는 날 null). 2027-03-01 이후는 2026-11-22 값 그대로.')
        if '4번(@jin_4) 재실측' not in note:
            h['note'] = (note.rstrip() + ' ' + add).strip()
        stat['hotels'] += 1

    tab['generated_at'] = '2026-11-28'
    hs = tab['hotels']
    cells = sum(len((h.get('rates') or {}).get('$v') or []) for h in hs)
    cash = sum(1 for h in hs for v in ((h.get('rates') or {}).get('$v') or []) if v is not None)
    pts = sum(1 for h in hs for v in ((h.get('points') or {}).get('$v') or []) if v is not None)
    tab['counts'] = {'hotels': len(hs), 'cells': cells, 'cash': cash, 'points': pts}

    with open(TAB, 'w', encoding='utf-8') as f:
        json.dump(tab, f, ensure_ascii=False, separators=(',', ':'))
    print(json.dumps(stat, ensure_ascii=False, indent=1))
    print('counts', tab['counts'])


if __name__ == '__main__':
    main()
