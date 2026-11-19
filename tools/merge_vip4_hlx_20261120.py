#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP 탭 배정 4곳 — 예약 사이트(hotel.hotelux.com) 상세 페이지 직접 조회 실측 병합.

사용법 (저장소 루트에서):
    python3 tools/merge_vip4_hlx_20261120.py --dry-run \
        h12=../work/hlx/h12_usd.json h13=../work/hlx/h13_usd.json ...
    python3 tools/merge_vip4_hlx_20261120.py h12=...

입력 JSON: {"2026-12-01": 768, "2026-12-02": null, ...}  (표시 통화 USD, 1박 세금 포함 최저)
 - null 은 그 날짜에 판매 객실이 없었다는 뜻(화면 "no room types available").
 - 90일(2026-12-01~2027-02-28) 전수여야 한다. 빠진 날짜가 있으면 아무것도 쓰지 않고 멈춘다.

규칙:
  · 2026-12-01~2027-02-28 구간만 새 실측값으로 바꾼다. 2027-03-01~2027-11-30 은 기존 값을 그대로 둔다.
  · USD → KRW: index.html `FX_TABLE` 의 USD 1 = ₩1,331.56 (2026-11-19 기준) 고정 환산, 100원 단위 반올림.
  · `vip` 플래그는 내리고(공개 요금), `source` 를 이번 수집 조건으로 교체한다.
  · 값은 고치기만 하고 counts·배포본은 건드리지 않는다 — 이어서
    `python3 tools/master_db.py refresh && python3 tools/master_db.py inject`.
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

WINDOW_START = '2026-12-01'
WINDOW_END = '2027-02-28'
KEEP_FROM = '2027-03-01'
FX_USD = 1331.56          # index.html FX_TABLE USD (2026-11-19)

TARGETS = {
    'h12': ('콘래드 도쿄', '5b35e43e04f832fae1e4d9ee'),
    'h13': ('페어몬트 도쿄', '682d2d40a92b2d2dbadf407e'),
    'h04': ('페어몬트 피스 호텔 온 더 번드', '5b50d91512bd3f60197e2d60'),
    'h05': ('푸동 샹그릴라 상하이', '5b5078036a8860a3024e0fd3'),
}

SRC = ('공개 요금 실측 · 2026-11-20 07:30~ KST 예약 사이트 호텔 상세 페이지 직접 조회'
       '(비로그인 · 성인 2인·1실·1박·세금 포함 표시가 "including tax & fees", '
       '%s %d일 전수. 객실 목록이 다 불러온 뒤 값이 안정될 때까지 확인). '
       '표시 통화 USD를 USD 1 = ₩1,331.56(2026-11-19 기준)로 환산해 100원 단위로 적었습니다. '
       '%s 은 2026-11-19 검색값을 그대로 두었습니다.')
SRC_EXTRA = {
    'h12': ' 기본 객실(King Room City)이 2027-01-17 은 매진, 2026-12-01·12-02 는 전 객실 판매 없음으로 —입니다.',
    'h13': ' 최저가 객실 일부는 아코르 멤버십(로열티) 번호가 필요한 요금이고, 각 객실의 최저 요금제'
           '(세이버·회원 요율)를 기준으로 그날 최저값을 적었습니다.',
    'h04': '',
    'h05': '',
}
SOURCES_ADD = ['2026-11-20_vip4-예약사이트-직접조회-실측.json']


def days(start, end):
    d = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    out = []
    while d <= e:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def krw(usd):
    return int(round(usd * FX_USD / 100.0)) * 100


def main(argv=None):
    ap = argparse.ArgumentParser(description='① VIP 4곳 예약 사이트 실측 병합')
    ap.add_argument('pairs', nargs='+', help='h12=path.json 형식')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--now', default=None)
    args = ap.parse_args(argv)

    master = json.load(open(MASTER, encoding='utf-8'))
    by_id = {h['id']: h for h in master['hotels']}
    need = days(WINDOW_START, WINDOW_END)

    stat = {}
    for pair in args.pairs:
        hid, _, spec = pair.partition('=')
        path, _, rng = spec.partition('@')
        w_start, w_end = (rng.split('/') + ['', ''])[:2] if rng else (WINDOW_START, WINDOW_END)
        if not (w_start and w_end):
            raise SystemExit('범위 표기가 이상합니다: %r' % rng)
        need_h = days(w_start, w_end)
        if hid not in TARGETS:
            raise SystemExit('%s 는 배정 4곳이 아닙니다' % hid)
        h = by_id.get(hid)
        if not h:
            raise SystemExit('%s 호텔이 master_db.json 에 없습니다' % hid)
        if h.get('ref_id') and h['ref_id'] != TARGETS[hid][1]:
            raise SystemExit('%s ref_id 가 다릅니다: %s' % (hid, h['ref_id']))
        raw = json.load(open(path, encoding='utf-8'))
        missing = [d for d in need_h if d not in raw]
        if missing:
            raise SystemExit('%s 날짜가 %d개 빠졌습니다: %s' % (hid, len(missing), missing[:5]))
        old = h.get('rates') or {}
        same = changed = na2v = v2na = 0
        for d in need_h:
            prev = old.get(d)
            usd = raw[d]
            val = None if usd is None else krw(usd)
            if prev == val:
                same += 1
            elif prev is None:
                na2v += 1
            elif val is None:
                v2na += 1
            else:
                changed += 1
            old[d] = val
        h['rates'] = dict(sorted(old.items()))
        if len(h['rates']) != 365:
            raise SystemExit('%s %s 칸이 %d개입니다 (365 여야 함)' % (hid, h['name'], len(h['rates'])))
        h['source'] = (SRC % ('%s~%s' % (w_start, w_end), len(need_h),
                              (datetime.date.fromisoformat(w_end)
                               + datetime.timedelta(days=1)).isoformat())
                       + SRC_EXTRA.get(hid, ''))
        h.pop('vip', None)
        nums = [v for v in (h['rates'][d] for d in need_h) if v]
        stat[hid] = dict(name=h['name'], range='%s~%s' % (w_start, w_end), cells=len(need_h),
                         same=same, changed=changed, na2v=na2v, v2na=v2na, na=len(need_h) - len(nums),
                         lo=min(nums), hi=max(nums), avg=round(sum(nums) / len(nums)))

    for hid in sorted(stat):
        s = stat[hid]
        print('  %s %-26s %s %3d칸 | 같음 %3d · 변경 %3d · NA→값 %2d · 값→NA %2d · NA(판매없음) %2d | '
              '최저 %s원 · 최고 %s원 · 평균 %s원'
              % (hid, s['name'], s['range'], s['cells'], s['same'], s['changed'], s['na2v'], s['v2na'],
                 s['na'], format(s['lo'], ','), format(s['hi'], ','), format(s['avg'], ',')))

    for name in SOURCES_ADD:
        if name not in master['sources']:
            master['sources'].append(name)
    line = (' / 2026-11-20 07:30~ KST ① VIP 4곳 중 %d곳 예약 사이트 직접 조회 실측 반영'
            '(2026-12-01~2027-02-28 90일, 2027-03-01 이후 기존 검색값 유지) — %s'
            % (len(stat), ', '.join(sorted(stat))))
    if line.strip() not in (master.get('extended') or ''):
        master['extended'] = (master.get('extended') or '') + line
    master['generated_at'] = args.now or datetime.datetime.now().astimezone().strftime(
        '%Y-%m-%dT%H:%M:%S%z')

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
