#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 한국 3곳 — 2027-02-01~02-25(65~89일 뒤) 현금·아워드 재실측 병합 (2026-11-28).

원자료: work/mr_daily_1128/out/{SELJW,SELAG,SELCY}.json
  marriott.com /search/availabilityCalendar.mi (비로그인 · 성인2인 1실 1박 · KRW · 세금·수수료 별도)
정본(data/master_db.json)의 rates/points 날짜 사전만 갈아 끼우고, index.html·탭 JSON은 master_db.py inject 로 맞춘다.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
OUT = '/workspace/work/mr_daily_1128/out'
CODES = ['SELJW', 'SELAG', 'SELCY']
STAMP = '2026-11-28'


def main():
    m = json.load(open(MASTER, encoding='utf-8'))
    by_code = {h.get('code'): h for h in m['hotels']}
    stat = []
    for code in CODES:
        new = json.load(open(os.path.join(OUT, code + '.json'), encoding='utf-8'))
        h = by_code[code]
        ch = {'cash': 0, 'cash_new': 0, 'pts': 0, 'pts_new': 0}
        for d, v in new['cash'].items():
            if d in h['rates']:
                if h['rates'][d] is None:
                    ch['cash_new'] += 1
                elif h['rates'][d] != v:
                    ch['cash'] += 1
                h['rates'][d] = v
        for d, v in new['points'].items():
            if d in h['points']:
                if h['points'][d] is None:
                    ch['pts_new'] += 1
                elif h['points'][d] != v:
                    ch['pts'] += 1
                h['points'][d] = v
        note = h.get('note') or ''
        add = ('2027-02-01~02-25(65~89일 뒤) 25일 현금·포인트는 2026-11-28 04:5x KST 공홈 요금 달력'
               '(/search/availabilityCalendar.mi · 세금·수수료 별도 KRW · 성인2인 1실 1박)에서 다시 쟀다.')
        if '2027-02-01~02-25' not in note:
            h['note'] = (note.rstrip() + ' ' + add).strip()
        src = h.get('source') or ''
        if '2026-11-28' not in src:
            h['source'] = src.rstrip() + ' · 2027-02-01~02-25(25일) 2026-11-28 재조회'
        stat.append((code, h['name'], len(new['cash']), len(new['points']), ch))
    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(m, fp, ensure_ascii=False, indent=1)
    for s in stat:
        print(s)


if __name__ == '__main__':
    main()
