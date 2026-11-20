#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP 페어몬트 도쿄(h13) — 예약 사이트(hotel.hotelux.com) 상세 페이지 직접 조회 실측 병합 (2027년 9~11월 마지막 분기판).

h13(페어몬트 도쿄)의 2027-09-01~2027-11-30 91일을 실측값으로 채워
2026-12-01~2027-11-30 365일을 완결한다. 2027-12-01 이후는 키를 남기지 않는다(달력 —).

사용법 (저장소 루트에서):
    python3 tools/merge_vip4_hlx_q4_20261120.py --dry-run h13=../work/hlx/h13_m9_11_usd.json@2027-09-01/2027-11-30

입력 JSON: {"2027-09-01": 791, ..., "2027-10-01": null, ...}
 - null 은 그 날짜에 판매 객실이 없었다는 뜻(화면 "There are no room types available for sale at this time").

규칙:
  · 지정 구간만 새 실측값으로 바꾼다(2026-12-01~2027-08-31 기존 실측 유지).
  · 구간 이후 rates 키는 남기지 않는다 → 화면 —(미실측).
  · USD → KRW: index.html `FX_TABLE` USD 1 = ₩1,331.56 (2026-11-19) 고정 환산, 100원 단위 반올림.
  · `source` 를 "2026-12-01~2027-11-30 365일 전수 실측" 형태로 교체하고,
    2027-10~11월 판매 없음 구간은 '예약 창 미개시 가능성 · 추후 재조회 대상'으로 구분해 적는다.
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

FX_USD = 1331.56
TARGETS = {
    'h12': ('콘래드 도쿄', '5b35e43e04f832fae1e4d9ee'),
    'h13': ('페어몬트 도쿄', '682d2d40a92b2d2dbadf407e'),
    'h04': ('페어몬트 피스 호텔 온 더 번드', '5b50d91512bd3f60197e2d60'),
    'h05': ('푸동 샹그릴라 상하이', '5b5078036a8860a3024e0fd3'),
}
SRC_EXTRA = {
    'h13': ' 2027-09-01~10-17 중 09-02(매진)를 뺀 46일은 요금이 있고 USD 841~1,986입니다'
           ' (09-01은 4개 객실만 남아 USD 1,743, 10-15·10-16은 기본 객실이 매진되어'
           ' Fairmont Gold 등급만 남아 USD 1,986).'
           ' 2027-10-18~11-30 44일은 화면에 "There are no room types available for sale at this time"만'
           ' 표시되어 —으로 두었습니다(예약 창 미개시 가능성 · 추후 재조회 대상).'
           ' 최저가 객실 일부는 아코르 멤버십(로열티) 번호가 필요한 요금이고,'
           ' 각 객실의 최저 요금제(세이버·회원 요율)를 기준으로 그날 최저값을 적었습니다.',
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
    ap = argparse.ArgumentParser()
    ap.add_argument('pairs', nargs='+', help='h12=path.json@YYYY-MM-DD/YYYY-MM-DD')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--now', default=None)
    ap.add_argument('--measured-start', default='2026-12-01', help='source 문구에 쓸 실측 시작일')
    ap.add_argument('--collected', default='2026-11-20 14:49~16:05 KST')
    args = ap.parse_args(argv)

    master = json.load(open(MASTER, encoding='utf-8'))
    by_id = {h['id']: h for h in master['hotels']}
    stat = {}

    for pair in args.pairs:
        hid, _, spec = pair.partition('=')
        path, _, rng = spec.partition('@')
        w_start, w_end = rng.split('/')
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
        dropped = [d for d in old if d > w_end]
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
        for d in dropped:
            del old[d]
        h['rates'] = dict(sorted(old.items()))
        n_cells = len(h['rates'])
        nums = [v for v in (h['rates'][d] for d in need_h) if v]
        h['source'] = (
            '공개 요금 실측 · %s 예약 사이트 호텔 상세 페이지 직접 조회'
            '(비로그인 · 성인 2인·1실·1박·세금 포함 표시가 "including tax & fees", '
            '2026-12-01~2027-11-30 365일 전수. 날짜마다 새로 불러와 화면 날짜 라벨을 대조하고, '
            '값과 객실 카드 수가 안정될 때까지 확인). '
            '표시 통화 USD를 USD 1 = ₩1,331.56(2026-11-19 기준)로 환산해 100원 단위로 적었습니다.'
            % args.collected
        ) + SRC_EXTRA.get(hid, '')
        h.pop('vip', None)
        stat[hid] = dict(name=h['name'], w='%s~%s' % (w_start, w_end), cells=len(need_h), total=n_cells,
                         same=same, changed=changed, na2v=na2v, v2na=v2na,
                         na=len(need_h) - len(nums), dropped=len(dropped),
                         lo=min(nums), hi=max(nums), avg=round(sum(nums) / len(nums)))

    for hid in sorted(stat):
        s = stat[hid]
        print('  %s %-26s %s %3d칸 | 같음 %3d · 변경 %3d · NA→값 %2d · 값→NA %2d · 판매없음 %2d | '
              '구간밖 삭제 %3d · 총 %3d칸 | 최저 %s원 · 최고 %s원 · 평균 %s원'
              % (hid, s['name'], s['w'], s['cells'], s['same'], s['changed'], s['na2v'], s['v2na'], s['na'],
                 s['dropped'], s['total'], format(s['lo'], ','), format(s['hi'], ','), format(s['avg'], ',')))

    for name in SOURCES_ADD:
        if name not in master['sources']:
            master['sources'].append(name)
    line = (' / 2026-11-20 14:49~16:05 KST ① VIP %d곳 중 페어몬트 도쿄(h13) 예약 사이트 직접 조회 실측 연장'
            '(2027-09-01~2027-11-30 91일 중 46일 요금·45일 판매 없음(10-18 이후 예약창 미개시 가능성), 2026-12-01~2027-11-30 365일 완결) — %s'
            % (len(stat), ', '.join(sorted(stat))))
    if line.strip() not in (master.get('extended') or ''):
        master['extended'] = (master.get('extended') or '') + line
    master['generated_at'] = args.now or datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')

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
