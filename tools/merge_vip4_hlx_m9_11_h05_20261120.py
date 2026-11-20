#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP h05 푸동 샹그릴라 상하이 — 예약 사이트 호텔 상세 페이지 직접 조회 실측 병합 (2027년 9~11월 분기판 · 365일 완결).

h05 의 2027-09-01~2027-11-30 91일을 실측 결과로 채워
2026-12-01~2027-11-30 365칸을 완결한다.

사용법 (저장소 루트에서):
    python3 tools/merge_vip4_hlx_m9_11_h05_20261120.py --dry-run h05=../work/hlx/h05_m9_11_usd.json@2027-09-01/2027-11-30
    python3 tools/merge_vip4_hlx_m9_11_h05_20261120.py --collected '2026-11-20 19:32~20:5x KST' h05=...

입력 JSON: {"2027-09-01": 200, ...}  (표시 통화 USD, 1박 세금 포함 최저)
 - null 은 그 날짜에 판매 객실이 없었다는 뜻(화면 "There are no room types available for sale at this time").

규칙:
  · 지정 구간만 새 실측값으로 바꾼다(2026-12-01~2027-08-31 기존 실측 274칸 유지).
  · 실측한 날짜는 값이 null 이어도 키를 남긴다 → 달력 칸 수 365칸(요금 미표시 = null).
  · USD → KRW: index.html `FX_TABLE` USD 1 = ₩1,331.56 (2026-11-19) 고정 환산, 100원 단위 반올림.
  · `source` 를 "2026-12-01~2027-11-30 365일 실측 완결" 형태로 교체하고,
    2027-10-18 이후(44일) 판매 객실 없음은 "10-18 이후 판매 객실 없음(예약 창 미개시 가능성 · 추후 재조회 대상)"으로 구분 표기한다.
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
    'h05': ('푸동 샹그릴라 상하이', '5b5078036a8860a3024e0fd3'),
}
SRC_EXTRA = {
    'h05': ' 2027-09-01~2027-10-17 47일은 판매 요금이 있었고(객실 21종),'
           ' 2027-10-18~2027-11-30 44일은 판매 객실이 없었습니다 — 10-18 이후 판매 객실 없음(예약 창 미개시 가능성 · 추후 재조회 대상).'
           ' 요금이 있던 47일의 최저는 2027-10-04~10-07 157달러, 최고는 2027-10-03 220달러였습니다.'
           ' 같은 날 2027-10-17은 200달러로 지금도 판매 중이었습니다.'
           ' 2027-01-11~01-14·01-17~01-19 는 기본 객실(리버윙 디럭스)이 매진되어 상위 등급부터'
           ' 최저가가 잡혀 300달러대까지 올라갑니다(그 날짜들만 객실 종류가 15~16종).',
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
    ap.add_argument('pairs', nargs='+', help='h05=path.json@YYYY-MM-DD/YYYY-MM-DD')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--now', default=None)
    ap.add_argument('--measured-start', default='2026-12-01', help='source 문구에 쓸 실측 시작일')
    ap.add_argument('--collected', default='2026-11-20 19:34~20:13 KST')
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
            raise SystemExit('%s 는 이 스크립트 배정 호텔이 아닙니다' % hid)
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
            '%s~%s %d일 전수. 날짜마다 새로 불러와 화면 날짜 라벨을 대조하고, '
            '값과 객실 카드 수가 안정될 때까지 확인). '
            '표시 통화 USD를 USD 1 = ₩1,331.56(2026-11-19 기준)로 환산해 100원 단위로 적었습니다. '
            '%s~%s 실측 완결(%d칸 · 요금 %d일 · 판매 객실 없음 %d일).'
            % (args.collected, args.measured_start, w_end,
               len(days(args.measured_start, w_end)), args.measured_start, w_end,
               len(days(args.measured_start, w_end)),
               len([v for v in h['rates'].values() if v]),
               len([v for v in h['rates'].values() if not v]))
        ) + SRC_EXTRA.get(hid, '')
        h.pop('vip', None)
        stat[hid] = dict(name=h['name'], w='%s~%s' % (w_start, w_end), cells=len(need_h), total=n_cells,
                         same=same, changed=changed, na2v=na2v, v2na=v2na,
                         na=len(need_h) - len(nums), dropped=len(dropped),
                         lo=min(nums) if nums else None, hi=max(nums) if nums else None,
                         avg=round(sum(nums) / len(nums)) if nums else None)

    for hid in sorted(stat):
        s = stat[hid]
        print('  %s %-26s %s %3d칸 | 같음 %3d · 변경 %3d · NA→값 %2d · 값→NA %2d · 판매없음 %2d | '
              '구간밖 삭제 %3d · 총 %3d칸 | 최저 %s원 · 최고 %s원 · 평균 %s원'
              % (hid, s['name'], s['w'], s['cells'], s['same'], s['changed'], s['na2v'], s['v2na'], s['na'],
                 s['dropped'], s['total'],
                 format(s['lo'], ',') if s['lo'] else '-',
                 format(s['hi'], ',') if s['hi'] else '-',
                 format(s['avg'], ',') if s['avg'] else '-'))

    for name in SOURCES_ADD:
        if name not in master['sources']:
            master['sources'].append(name)
    line = (' / 2026-11-20 19:34~20:13 KST ① VIP 푸동 샹그릴라 상하이(h05) 예약 사이트 직접 조회 실측 연장'
            '(2027-09-01~2027-10-17 47일 요금 있음(객실 21종 · USD 157~220) · 2027-10-18~2027-11-30 44일 판매 객실 없음'
            '(예약 창 미개시 가능성 · 추후 재조회 대상), 2026-12-01~2027-11-30 365칸 완결 — 요금 321일 · 판매 없음 44일) — %s'
            % ', '.join(sorted(stat)))
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
