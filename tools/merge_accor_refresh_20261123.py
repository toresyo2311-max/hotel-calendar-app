#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 아코르 — 60~90일 구간(2027-01-22~2027-02-21) 재실측 병합 (2026-11-23 04:00 스케줄).

입력  /workspace/work/accor_refresh_20261123/raw.json
      (collect.py 가 all.accor.com 이 쓰는 공식 GraphQL api.accor.com/bff/v1/graphql
       hotelOffers.calendar 로 8일 단위 조회. 1박·성인 2인·1객실·KRW·countryMarket KR)

값 기준
  · 달력 응답의 요금은 호텔별로 세금 포함/제외가 다르다. 같은 호텔·날짜의 bestOffer
    pricing.formattedTaxType 표본(창 안 4일: 01-23·02-02·02-06·02-16)에서 세율을 읽어
    세금 포함액으로 환산한다. 예: 중국 16.6% · 홍콩 13% · 마카오 15% · 한국 10% ·
    일본(페어몬트 도쿄)은 표기가 비어 있어 붙이지 않는다(사이트 표시가 = 세금 포함).
  · 이 19곳의 기존 ② 요금은 모두 1,000원 단위로 반올림돼 있어 같은 자릿수로 맞춘다.
  · 요금이 없는 날(미판매·매진·예약창 밖)은 null 로 남긴다 — 추측·보간하지 않는다.

하는 일
  · 대상 19곳의 rates 가운데 창 안 31칸만 새 실측값으로 바꾼다. 나머지 334칸은 건드리지 않는다.
  · source 문구 끝에 재실측 사실을 덧붙인다(앞머리 표지는 그대로 — 급락 알람의 산식 전환
    판정이 이 표지를 쓰므로 바꾸면 오탐이 난다).
사용법: python3 tools/merge_accor_refresh_20261123.py [--dry-run]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
RAW = '/workspace/work/accor_refresh_20261123/raw.json'
NOTE = ' · 2027-01-22~02-21(60~90일) 구간은 2026-11-23 04:00 재실측(같은 API 기준)'
DRY = '--dry-run' in sys.argv

# 세금 기준 — 호텔마다 지금 365일 칸이 어느 계열로 채워져 있는지 2026-11-23에 표본 확인했다
#   (창 밖 2027-03·05·08·10월 각 7일을 오늘 다시 읽어, 저장값이 '사이트 표시액'과 같은지
#    '표시액+표기 세금'과 같은지 다수결). 이 창은 그 호텔의 기존 계열과 같은 기준으로 쓴다.
#   INCL = 표시액 + 표기 세금(중국 16.6%) · PRETAX = 사이트 표시액 그대로.
INCL = {'aA5G7', 'aA7Z9', 'a8873', 'a8719'}


def rate_for(day, tax):
    """표본 4일의 세율 중 그 날짜에 가장 가까운 표본의 세율(없으면 None)."""
    best = None
    for ds, t in tax.items():
        if t.get('rate') is None:
            continue
        d = abs((__import__('datetime').date.fromisoformat(ds)
                 - __import__('datetime').date.fromisoformat(day)).days)
        if best is None or d < best[0]:
            best = (d, t['rate'])
    return best[1] if best else None


def main():
    raw = json.load(open(RAW, encoding='utf-8'))
    master = json.load(open(MASTER, encoding='utf-8'))
    ids = {h['id']: h for h in master['hotels']}
    report = []
    for hid, r in raw.items():
        h = ids.get(hid)
        if h is None:
            print('!! %s 없음' % hid)
            continue
        rates = h['rates']
        changed = same = newfill = noloss = 0
        big = []
        for day, v in sorted(r['days'].items()):
            if day not in rates:
                print('!! %s %s 창 밖' % (hid, day))
                continue
            amt = v.get('amt')
            old = rates.get(day)
            if not amt:
                if old is not None:
                    noloss += 1
                    big.append((day, old, None))
                rates[day] = None
                continue
            rt = rate_for(day, r['tax'])
            val = amt * (1 + rt) if (hid in INCL and rt is not None) else amt
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
        if NOTE not in (h.get('source') or ''):
            h['source'] = (h.get('source') or '') + NOTE
        report.append((hid, h['name'], changed, same, newfill, noloss, big))

    print('%-7s %-28s %5s %5s %5s %5s %s' % ('id', 'name', 'changed', 'same', 'new', 'null', '50%+'))
    for hid, name, c, s, n, z, big in report:
        print('%-7s %-28s %5d %5d %5d %5d %s' % (hid, name[:28], c, s, n, z,
                                                 ' '.join('%s %s→%s' % b for b in big) or '-'))
    tot = (sum(x[2] for x in report), sum(x[3] for x in report),
           sum(x[4] for x in report), sum(x[5] for x in report))
    print('합계 changed=%d same=%d newfill=%d null로바뀜=%d' % tot)
    if DRY:
        print('(dry-run — 저장하지 않음)')
        return
    with open(MASTER, 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('저장', MASTER)


if __name__ == '__main__':
    main()
