#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 아코르 — 60~90일 구간(2027-01-23~2027-02-22) 재실측 병합 (2026-11-24 04:00 스케줄).

입력  /workspace/work/accor_refresh_20261124/raw.json
      (collect.py 가 all.accor.com 이 쓰는 공식 GraphQL api.accor.com/bff/v1/graphql
       hotelOffers.calendar 로 8일 단위 조회. 1박·성인 2인·1객실·KRW·countryMarket KR)

값 기준 (호텔별로 지금 365일 칸이 어느 계열로 채워져 있는지 창 밖·창 안 표본으로 판정)
  · pre  — 사이트 표시액 그대로 (표시액은 세금 별도)
  · svc  — 표시액 + 10% 서비스료 (중국 호텔 다수가 이 계열로 저장돼 있다: 표본 50~59/59 일치)
  · incl — 표시액 + 표기 세금 (중국 16.6% · 홍콩 13%)
  판정 근거는 basis.json(votes) 이고, 창 바로 바깥 날짜(01-17~22·02-23~28)의 계열까지 대조해
  달력이 창 경계에서 단차 없이 이어지도록 골랐다.
  · 요금이 없는 날(미판매·매진)은 null 로 남긴다 — 추측·보간하지 않는다.
  · 판정이 서지 않는 카드는 건드리지 않는다(SKIP).

사용법: python3 tools/merge_accor_refresh_20261124.py [--dry-run]
"""
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
RAW = '/workspace/work/accor_refresh_20261124/raw.json'
NOTE = ' · 2027-01-23~02-22(60~90일) 구간은 2026-11-24 04:00 재실측(같은 API 기준)'
NOTE_RE = re.compile(r' · \d{4}-\d{2}-\d{2}~\d{2}-\d{2}\(60~90일\) 구간은 [^·]*?재실측\(같은 API 기준\)')
DRY = '--dry-run' in sys.argv

# 계열 판정 — collect 2026-11-24 04:00 · 표본 59일(창 안 31 + 창 밖 28) + 창 바깥 이웃 14일
BASIS = {
    # 사이트 표시액 그대로 (표본 다수가 1.00)
    'pre': ['c6318', 'cC1H8', 'cC4Q5', 'ap004', 'ap023', 'ap076', 'c6156', 'cC037',
            'ap127', 'cC2G5', 'ap078', 'c5554', 'ap102'],
    # 표시액 + 10% 서비스료
    'svc': ['ap016', 'c6179', 'ap056', 'ap086', 'cC7G9', 'ap067', 'ap131'],
    # 표시액 + 표기 세금
    'incl': ['cC3N7', 'ap025'],
}
# 건드리지 않는 카드 — 이유는 보고에 적는다
SKIP = {
    'cB628': '365일 값이 중올플 요금달력(다른 플랫폼) 기준으로 공식 API 표시액보다 7%쯤 낮다 — 계열 판정 불가',
    'c9933': 'all.accor.com 이 연중 UNAVAILABLE — API 로는 요금을 못 읽는다(중올플 값 유지)',
}


def days():
    d0 = datetime.date(2027, 1, 23)
    return [(d0 + datetime.timedelta(days=i)).isoformat() for i in range(31)]


def main():
    raw = json.load(open(RAW, encoding='utf-8'))
    master = json.load(open(MASTER, encoding='utf-8'))
    by_id = {h['id']: h for h in master['hotels']}
    win = days()

    def rate_for(day, tax):
        best = None
        for ds, t in tax.items():
            if t.get('rate') is None:
                continue
            d = abs((datetime.date.fromisoformat(ds) - datetime.date.fromisoformat(day)).days)
            if best is None or d < best[0]:
                best = (d, t['rate'])
        return None if best is None else best[1]

    report = []
    for mode, ids in BASIS.items():
        for hid in ids:
            r = raw.get(hid)
            h = by_id.get(hid)
            if not r or not h:
                print('!! %s 자료 없음' % hid)
                continue
            rates = h['rates']
            changed = same = newfill = to_null = 0
            big = []
            for day in win:
                v = r['days'].get(day) or {}
                amt = v.get('amt')
                old = rates.get(day)
                if not amt:
                    if old is not None:
                        to_null += 1
                        big.append((day, old, 'null'))
                    rates[day] = None
                    continue
                if mode == 'pre':
                    val = amt
                elif mode == 'svc':
                    val = amt * 1.10
                else:
                    rt = rate_for(day, r['tax'])
                    if rt is None:
                        print('!! %s %s 세율 없음' % (hid, day))
                        continue
                    val = amt * (1 + rt)
                new = int(round(val / 1000.0)) * 1000
                if old is None:
                    newfill += 1
                elif old != new:
                    changed += 1
                    if old and (new / old <= 0.5 or new / old >= 1.5):
                        big.append((day, old, new))
                else:
                    same += 1
                rates[day] = new
            src = NOTE_RE.sub('', h.get('source') or '')
            if NOTE not in src:
                h['source'] = src + NOTE
            report.append((mode, hid, h['name'], changed, same, newfill, to_null, big))

    print('%-4s %-7s %-26s %5s %5s %5s %5s %s' % ('mode', 'id', 'name', 'chg', 'same', 'new', 'null', '50%+'))
    tot = [0, 0, 0, 0]
    for mode, hid, name, c, s, n, z, big in sorted(report, key=lambda x: -x[3]):
        print('%-4s %-7s %-26s %5d %5d %5d %5d %s' % (mode, hid, name[:24], c, s, n, z,
                                                       ' '.join('%s %s→%s' % b for b in big) or '-'))
        tot = [tot[0] + c, tot[1] + s, tot[2] + n, tot[3] + z]
    print('합계 changed=%d same=%d newfill=%d null로바뀜=%d · 호텔 %d곳' % (tot[0], tot[1], tot[2], tot[3], len(report)))
    for hid, why in SKIP.items():
        print('skip %s %s — %s' % (hid, by_id[hid]['name'] if hid in by_id else '', why))
    if DRY:
        print('(dry-run — 저장하지 않음)')
        return
    with open(MASTER, 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('저장', MASTER)


if __name__ == '__main__':
    main()
