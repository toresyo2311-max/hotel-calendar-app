#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""방금 내려받은 CSV 하나를 collect/{dep|arr}_{슬러그}_{PUS|ICN}.csv 로 옮긴다.

- 대상: /workspace/downloads/seats.aero *Export*.csv 중 아직 옮기지 않은 가장 최근 파일
- 확인: CSV 의 Mileage Program 값 == 슬러그, Origin/Destination Airport 중 한쪽 == 코드
  (프로그램 이름이 같아 파일명이 겹치므로, 값으로 확인한 뒤에만 옮긴다)
- 쓰임:  python3 tools/partner_tab/grab_csv.py {dep|arr} {슬러그} {PUS|ICN}
        → 옮긴 경로와 행 수·날짜 범위를 출력
"""
import csv
import glob
import os
import shutil
import sys

DL = '/workspace/downloads'
OUT = os.path.join(DL, 'collect')


def main(argv):
    direction, slug, code = argv[0], argv[1], argv[2]
    os.makedirs(OUT, exist_ok=True)
    cands = sorted(
        (os.path.getmtime(p), p) for p in glob.glob(os.path.join(DL, 'seats.aero*Export*.csv'))
        if not os.path.basename(p).startswith('_')
    )
    if not cands:
        raise SystemExit('CSV 없음')
    for _, path in reversed(cands):
        try:
            with open(path, encoding='utf-8-sig') as fp:
                rows = list(csv.DictReader(fp))
        except Exception:
            continue
        if not rows:
            continue
        progs = {r.get('Mileage Program') for r in rows}
        if progs != {slug}:
            continue
        if direction == 'dep':
            ok = {r['Origin Airport'] for r in rows} == {code}
        else:
            ok = {r['Destination Airport'] for r in rows} == {code}
        if not ok:
            continue
        dst = os.path.join(OUT, '%s_%s_%s.csv' % (direction, slug, code))
        shutil.move(path, dst)
        dates = [r['Date'] for r in rows]
        print('%s  rows %d  %s ~ %s' % (os.path.basename(dst), len(rows), min(dates), max(dates)))
        return
    raise SystemExit('맞는 CSV 없음: %s %s %s' % (direction, slug, code))


if __name__ == '__main__':
    main(sys.argv[1:])
