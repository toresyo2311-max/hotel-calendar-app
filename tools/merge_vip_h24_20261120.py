#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP h24 아마노이(닌투언/판랑) — 예약 사이트 365일 실측 병합 (2026-11-20, 6번(@jin_6) 전달분).

입력: memory/clones/146dd4d1-jin_6/pickle/2026-11-20-1323/received/0-hotelux-h24.json
  rates: {"2026-12-01": 2232, ... } — 365일 키, 값은 그 날짜 최저 객실 1박 USD(세금·수수료 포함),
  null 은 1박 판매 불가(최소숙박 제한 · 예약 창 미오픈)로 추정·보간하지 않는다.

규칙
  · 기존 병합 도구와 같은 앱 고정 환율 USD 1 = ₩1,331.56 로 KRW 정수 반올림(int(round)) 변환.
  · null 119일은 null 그대로 유지하고, 365일 키를 모두 남긴다(2027-12 이후 키 없음).
  · `source` 를 실측 출처 문구로 교체, `extended`·`sources` 에 이번 병합을 덧붙인다.
  · 값은 고치기만 하고 counts·배포본은 건드리지 않는다 —
    이어서 `python3 tools/master_db.py refresh && python3 tools/master_db.py inject`.
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC_JSON = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-20-1323/received/'
            '0-hotelux-h24.json')

HID = 'h24'
REF_ID = '5b5055be74de201bce684ca4'
FX_USD = 1331.56
WINDOW_START = '2026-12-01'
WINDOW_END = '2027-11-30'

SRC = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 6번(@jin_6) 전달분. '
       '예약 사이트 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 USD 총액) '
       '2026-12-01~2027-11-30 365일 전수. 앱 고정 환율 USD 1 = ₩1,331.56 로 환산. '
       '요금 없는 날 119일은 빈칸이며 추정하지 않았습니다 — 2026-12-23~2027-01-04(13일)·'
       '2027-02-05~02-14(10일)·2027-03-26~03-29(4일)·2027-04-29~05-04(6일)는 최소 3박 조건, '
       '2027-09-06~11-30(86일)은 예약 창(요금 로드 한도) 미오픈으로 추후 재조회 대상입니다. '
       '실측 최저 1박 USD 1,539(2027-05-05~07-31 중 70일) · 최고 USD 3,720(2026-12-19).')
EXT_LINE = (' / 2026-11-20 ① VIP 예약 사이트 실측 병합 — h24 아마노이(닌투언/판랑) 365일 전수'
            '(6번(@jin_6) 전달, USD→₩, 판매 없음 119일 null)')
SOURCE_NAME = 'VIP 예약 사이트 실측 2026-11-20 — h24 아마노이 365일 (6번 전달)'


def days(a, b):
    d = datetime.date.fromisoformat(a)
    e = datetime.date.fromisoformat(b)
    out = []
    while d <= e:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(argv)

    master = json.load(open(MASTER, encoding='utf-8'))
    by_id = {h['id']: h for h in master['hotels']}
    h = by_id.get(HID)
    if not h:
        sys.exit('%s 가 master_db.json 에 없습니다' % HID)
    if h.get('ref_id') and h['ref_id'] != REF_ID:
        sys.exit('%s ref_id 가 다릅니다: %s' % (HID, h['ref_id']))

    raw = json.load(open(SRC_JSON, encoding='utf-8'))
    if raw.get('id') != HID:
        sys.exit('입력 파일 id 가 %s 가 아닙니다: %s' % (HID, raw.get('id')))
    need = days(WINDOW_START, WINDOW_END)
    missing = [d for d in need if d not in raw['rates']]
    if missing:
        sys.exit('날짜가 %d개 빠졌습니다: %s' % (len(missing), missing[:5]))

    old = h.get('rates') or {}
    rates = {}
    same = changed = na2v = v2na = na = 0
    for d in need:
        usd = raw['rates'][d]
        val = None if usd is None else int(round(usd * FX_USD))
        prev = old.get(d)
        if prev == val:
            same += 1
        elif prev is None:
            na2v += 1 if val is not None else 0
        elif val is None:
            v2na += 1
        else:
            changed += 1
        if val is None:
            na += 1
        rates[d] = val
    dropped = [d for d in old if d not in rates]
    h['rates'] = rates
    h['source'] = SRC

    for name in (SOURCE_NAME,):
        if name not in master['sources']:
            master['sources'].append(name)
    if EXT_LINE.strip() not in (master.get('extended') or ''):
        master['extended'] = (master.get('extended') or '') + EXT_LINE
    master['generated_at'] = datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')

    nums = [v for v in rates.values() if v]
    lo_d = min((d for d in rates if rates[d]), key=lambda d: rates[d])
    hi_d = max((d for d in rates if rates[d]), key=lambda d: rates[d])
    print('  %s %-18s %s~%s | 365일 중 값 %d · 판매없음 %d | 같음 %d · 변경 %d · NA→값 %d · 값→NA %d · '
          '구간밖 삭제 %d' % (HID, h.get('name'), WINDOW_START, WINDOW_END,
                             len(nums), na, same, changed, na2v, v2na, len(dropped)))
    print('  최저 %s원(%s) · 최고 %s원(%s) · 평균 %s원 · 총 %d칸'
          % (format(rates[lo_d], ','), lo_d, format(rates[hi_d], ','), hi_d,
             format(round(sum(nums) / len(nums)), ','), len(rates)))

    if args.dry_run:
        print('--dry-run — 파일을 쓰지 않았습니다.')
        return 0
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('master_db.json 갱신 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main())
