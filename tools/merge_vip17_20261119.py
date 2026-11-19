#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP·FHR 핵심 17개 호텔 2026-11-19 재실측 CSV → `data/master_db.json` 병합.

사용법 (저장소 루트에서):
    python3 tools/merge_vip17_20261119.py \
        ../memory/clones/06130525-jin489/pickle/2026-11-19-2133/received/1-*.csv \
        ../memory/clones/06130525-jin489/pickle/2026-11-19-2133/received/3-*.csv \
        ../memory/clones/06130525-jin489/pickle/2026-11-19-2133/received/5-*.csv --dry-run
    python3 tools/merge_vip17_20261119.py ... (같은 인수에서 --dry-run 만 빼고)

읽는 CSV 형식(두 가지 헤더가 섞여 있다):
    일본·방콕:    날짜,호텔명,1박 세후 KRW,무료취소 여부,조회기준일
    다낭·나트랑:  날짜,호텔명,1박_세후_KRW,무료취소_여부,조회기준일
    값이 `NA`·`N/A`·빈칸이면 그 날짜는 요금 미표시(None)로 적는다.

규칙:
  · CSV 에 **있는 날짜만** 덮어쓴다. 방콕은 2026-12-01~2027-03-31 121일만 새로
    쟀으므로 2027-04-01~11-30 의 기존(2026-11-17) 값을 지우지 않는다.
  · 일본 6곳·다낭·나트랑 6곳은 365일 전수라 그 날짜의 기존 값을 새 실측값으로 바꾼다
    (새 값이 NA 면 미표시로 바꾼다 — 판매가 닫힌 날).
  · 호텔은 이름(영문 괄호 앞부분)으로 찾는다. 못 찾으면 아무것도 쓰지 않고 멈춘다.
  · `source` 문구를 이번 수집 조건으로 바꾸고, 17곳은 VIP 전용 요율이 아니라
    공개 검색 최저가이므로 `vip` 플래그를 내린다.
  · `sources` 에 원본 md 3건, `extended` 에 반영 이력을 한 줄 더한다.
  · 값은 고치기만 하고 counts·배포본은 건드리지 않는다 — 이어서
    `python3 tools/master_db.py refresh && python3 tools/master_db.py inject`.
"""
import argparse
import csv
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
WINDOW_START = '2026-12-01'
WINDOW_END = '2027-11-30'

# 2026-11-19 수집분 묶음 — source 문구와 반영 이력
JAPAN = ('h08', 'h09', 'h10', 'h11', 'h12', 'h13')
BANGKOK = ('h14', 'h15', 'h16', 'h17', 'h18')
VIETNAM = ('h19', 'h20', 'h21', 'h22', 'h23', 'h24')
ALL17 = JAPAN + BANGKOK + VIETNAM

SRC_JAPAN = ('검색 요금 · 2026-11-19 21:13~21:35 KST Google 호텔 가격 달력 실측'
             '(성인 2인·1실·1박·세금 포함 표시가, 2026-12-01~2027-11-30 365일 전수). '
             '취소 조건은 날짜별로 구분되지 않는 그날 전체 최저가이고, '
             '화면 달력 셀이 이보다 낮은 날이 있어 이 값은 그날 최저가의 상한입니다.')
SRC_JAPAN_EXTRA = {
    'h08': ' 일부 날짜(2027-03-21·23 등)는 화면이 최대 약 23% 낮게 표시됩니다.',
    'h13': ' 이 호텔은 화면의 1박 특가를 놓쳐 실제 최저가보다 최대 약 9% 높습니다.',
}
SRC_BANGKOK = ('검색 요금 · 2026-11-19 21:10~22:15 KST 화면 가격 달력 실측'
               '(성인 2인·1실·1박·세금 포함 표시가, 2026-12-01~2027-03-31 121일). '
               '취소 가능 요금만 켠 화면에서 읽었고 요금별 취소 규정은 날짜별 미확인, '
               '달력이 3유효숫자로 반올림된 표시가라 실제 예약 총액은 더 높을 수 있습니다. '
               '2027-04-01~11-30 은 2026-11-17 조사값을 그대로 두었습니다.')
SRC_VIETNAM = ('검색 요금 · 2026-11-19 21:00~23:30 KST Google 호텔 가격 달력 3회 조회 최빈값'
               '(성인 2인·1실·1박·세금 포함, 2026-12-01~2027-11-30 365일 전수). '
               '취소 조건을 걸러내지 않은 그날 최저가이고, 반복 조회에서 5% 넘게 갈린 날짜가 '
               '호텔별 0~6일 있어 그 날은 값이 달라질 수 있습니다.')
SRC_VIETNAM_EXTRA = {
    'h20': ' 2027-03-13 6,216,188원은 화면 달력에서도 같은 값으로 확인된 실측이지만 '
           '전후 날짜(03-12 1.58M·03-14 1.01M) 대비 이례적입니다.',
}

SOURCES_ADD = [
    '2026-11-19_vip-fhr-일본-6개호텔.md',
    '2026-11-19_vip-fhr-방콕-5개호텔.md',
    '2026-11-19_vip-fhr-다낭나트랑-6개호텔.md',
]
EXTENDED_ADD = (' / 2026-11-19 21:13~23:30 KST ① VIP·FHR 17곳 재실측 반영 — 일본 6(365일) · '
                '다낭·나트랑 6(365일) · 방콕 5(2026-12-01~2027-03-31 121일, 2027-04 이후 기존 유지)')


def load_master():
    with open(MASTER, encoding='utf-8') as fp:
        return json.load(fp)


def ko_name(cell):
    """`그랜드 하얏트 후쿠오카 (Grand Hyatt Fukuoka)` → `그랜드 하얏트 후쿠오카`."""
    s = cell.split(' (')[0].strip()
    return ' '.join(s.split())


def read_csv(path):
    """{호텔명: {날짜: 금액 or None}} — 헤더 이름이 두 가지라 열 위치로 읽는다."""
    with open(path, encoding='utf-8-sig', newline='') as fp:
        rows = list(csv.reader(fp))
    if not rows:
        raise SystemExit('%s 가 비어 있습니다' % path)
    head = [h.strip() for h in rows[0]]
    if len(head) < 4 or head[0] != '날짜' or head[1] != '호텔명':
        raise SystemExit('%s 헤더가 예상과 다릅니다: %r' % (path, head))
    price_col = head[2]
    if price_col not in ('1박 세후 KRW', '1박_세후_KRW'):
        raise SystemExit('%s 금액 열 이름이 예상과 다릅니다: %r' % (path, price_col))
    out = {}
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        day, raw = r[0].strip(), r[2].strip()
        if not (WINDOW_START <= day <= WINDOW_END):
            raise SystemExit('%s 날짜가 창(%s~%s) 밖입니다: %r'
                             % (path, WINDOW_START, WINDOW_END, day))
        if raw in ('', 'NA', 'N/A', '-'):
            val = None
        else:
            val = int(raw.replace(',', '').replace('₩', '').replace(' ', ''))
            if val <= 0:
                raise SystemExit('%s %s 값이 0 이하입니다: %r' % (path, day, raw))
        key = ko_name(r[1])
        bucket = out.setdefault(key, {})
        if day in bucket:
            raise SystemExit('%s %s %s 날짜가 중복입니다' % (path, key, day))
        bucket[day] = val
    return out


def check_contiguous(name, series):
    days = sorted(series)
    if not days:
        raise SystemExit('%s 날짜가 없습니다' % name)
    d = datetime.date.fromisoformat(days[0])
    end = datetime.date.fromisoformat(days[-1])
    if (end - d).days + 1 != len(days):
        raise SystemExit('%s 날짜가 연속이 아닙니다 (%s~%s, %d칸)'
                         % (name, days[0], days[-1], len(days)))


def main(argv=None):
    ap = argparse.ArgumentParser(description='① VIP·FHR 17개 호텔 2026-11-19 재실측 병합')
    ap.add_argument('csvs', nargs='+', help='받은 CSV 경로(일본·방콕·다낭나트랑)')
    ap.add_argument('--dry-run', action='store_true', help='파일을 쓰지 않고 결과만 출력')
    ap.add_argument('--now', default=None, help='generated_at 에 적을 시각(기본 지금)')
    args = ap.parse_args(argv)

    master = load_master()
    by_name = {}
    for h in master['hotels']:
        by_name.setdefault(ko_name(h['name']), h)

    parsed = {}
    for path in args.csvs:
        got = read_csv(path)
        for name, series in got.items():
            check_contiguous(name, series)
            if name in parsed:
                raise SystemExit('%s 가 두 파일에 있습니다' % name)
            parsed[name] = series

    total_cells = sum(len(v) for v in parsed.values())
    print('읽은 호텔 %d곳 · %d칸 (파일 %d개)' % (len(parsed), total_cells, len(args.csvs)))
    if len(parsed) != len(ALL17):
        raise SystemExit('호텔이 %d곳입니다 (기대 %d곳)' % (len(parsed), len(ALL17)))

    stat = {}
    for name, series in sorted(parsed.items()):
        h = by_name.get(name)
        if not h:
            raise SystemExit('master_db.json 에서 호텔을 찾지 못했습니다: %r' % name)
        if h['id'] not in ALL17:
            raise SystemExit('%s 는 이번 병합 대상 17곳이 아닙니다' % h['id'])
        old = h.get('rates') or {}
        same = changed = na2v = v2na = 0
        for day, val in series.items():
            prev = old.get(day)
            if prev == val:
                same += 1
            elif prev is None and val is not None:
                na2v += 1
            elif prev is not None and val is None:
                v2na += 1
            else:
                changed += 1
            old[day] = val
        h['rates'] = dict(sorted(old.items()))
        if len(h['rates']) != 365:
            raise SystemExit('%s %s 날짜 칸이 %d개입니다 (365 여야 함)'
                             % (h['id'], h['name'], len(h['rates'])))
        group = '일본' if h['id'] in JAPAN else ('방콕' if h['id'] in BANGKOK else '다낭·나트랑')
        if h['id'] in JAPAN:
            h['source'] = SRC_JAPAN + SRC_JAPAN_EXTRA.get(h['id'], '')
        elif h['id'] in BANGKOK:
            h['source'] = SRC_BANGKOK
        else:
            h['source'] = SRC_VIETNAM + SRC_VIETNAM_EXTRA.get(h['id'], '')
        h.pop('vip', None)
        stat[h['id']] = dict(name=h['name'], group=group, cells=len(series), same=same,
                             changed=changed, na2v=na2v, v2na=v2na,
                             first=min(series), last=max(series),
                             na=sum(1 for v in series.values() if v is None))

    for hid in sorted(stat):
        s = stat[hid]
        print('  %s %-28s %-9s %3d칸 %s~%s | 같음 %3d · 변경 %3d · NA→값 %d · 값→NA %d · NA %d'
              % (hid, s['name'], s['group'], s['cells'], s['first'], s['last'],
                 s['same'], s['changed'], s['na2v'], s['v2na'], s['na']))

    for name in SOURCES_ADD:
        if name not in master['sources']:
            master['sources'].append(name)
    if EXTENDED_ADD.strip() not in (master.get('extended') or ''):
        master['extended'] = (master.get('extended') or '') + EXTENDED_ADD
    master['generated_at'] = args.now or datetime.datetime.now().astimezone().strftime(
        '%Y-%m-%dT%H:%M:%S%z')

    print('합계 — 변경 %d · NA→값 %d · 값→NA %d · 나머지 %d칸은 같은 값'
          % (sum(s['changed'] for s in stat.values()),
             sum(s['na2v'] for s in stat.values()),
             sum(s['v2na'] for s in stat.values()),
             sum(s['same'] for s in stat.values())))
    if args.dry_run:
        print('--dry-run — 파일을 쓰지 않았습니다.')
        return 0
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('wrote %s' % os.path.relpath(MASTER, ROOT))
    print('다음: python3 tools/master_db.py refresh && python3 tools/master_db.py inject && '
          'python3 tools/master_db.py verify')
    return 0


if __name__ == '__main__':
    sys.exit(main())
