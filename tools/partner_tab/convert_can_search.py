#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""광저우(CAN) ↔ 부산(PUS) — 검색 화면 CSV → 원자료(부산 탭) 반영.

왜 따로 있나
  매일 04:00 재수집은 조회 사이트의 **탐험(Explore) 화면** `/departing/PUS` ·
  `/arriving/PUS` 「전체 연도」 CSV 를 쓴다. 그 화면은 (프로그램 × 공항)마다 미리
  잡아 둔 노선표를 훑기 때문에, **부산↔광저우처럼 직항이 없는 짝은 아예 목록에 없다**
  (2026-11-23 확인: 9개 프로그램 부산 출발·도착 화면 모두 CAN 0줄, CAN 출발·도착
  화면도 PUS 0줄). 대신 **검색 화면**은 두 공항을 직접 받아 경유 itinerary 까지
  찾아 주므로, 그 CSV 를 받아 이 스크립트로 CAN 줄만 골라 넣는다.

입력: /workspace/downloads/collect_can/*.csv
      조회 사이트 검색 화면의 「. CSV」 내보내기(탐험 CSV 와 같은 열 구성)
      파일 이름 규칙: {dep|arr}_CAN_PUS_{중심 날짜}_p{±일수}.csv  (이름은 참고용)
출력: tools/partner_tab/raw/{슬러그}_{dep|arr}_PUS_can.txt
      한 줄 = YYYY-MM-DD|최근확인|CAN|이코|프이|비즈|퍼스트
      **파일 이름이 {슬러그}_{dir}_PUS_can.txt** 라서 build_partner_tab.py 의
      glob(`{슬러그}_{dir}_PUS*.txt`)에 함께 걸리고, 매일 갱신이 다시 쓰는
      `{슬러그}_{dir}_PUS.txt` 와는 다른 파일이라 지워지지 않는다.

  python3 tools/partner_tab/convert_can_search.py           # 반영
  python3 tools/partner_tab/convert_can_search.py --check   # 쓰지 않고 집계만
"""
import csv
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
SRC = '/workspace/downloads/collect_can'

SLUGS = ['flyingblue', 'smiles', 'virginatlantic', 'delta', 'united',
         'aeroplan', 'asiamiles', 'british', 'jal']
RAW_SLUG = {'virginatlantic': 'virgin'}
CABINS = [('Economy', 3), ('Premium Economy', 4), ('Business', 5), ('First', 6)]
WIN_FROM, WIN_TO = '2026-11-22', '2027-11-21'


def seen_text(hours):
    try:
        h = int(hours)
    except (TypeError, ValueError):
        return '방금'
    if h <= 0:
        return '방금'
    if h < 24:
        return '%d시간 전' % h
    return '%d일 전' % (h // 24)


def better(new, cur):
    ns, nm = new.split('-')
    cs, cm = cur.split('-')
    return (int(nm), int(ns)) < (int(cm), int(cs))


def parse_old(path):
    out = {}
    if not os.path.exists(path):
        return out
    for rec in open(path, encoding='utf-8').read().split(';'):
        rec = rec.strip()
        if not rec:
            continue
        p = rec.split('|')
        if len(p) != 7:
            raise SystemExit('형식 불일치 %r (%s)' % (rec, path))
        out[(p[0], p[2])] = {'seen': p[1],
                             'cab': {i: v for i, v in enumerate(p[3:7], start=3) if v != '-'}}
    return out


def main(argv):
    check = '--check' in argv
    files = sorted(glob.glob(os.path.join(SRC, '*.csv')))
    if not files:
        raise SystemExit('CSV 없음: %s' % SRC)
    # (슬러그, 방향) → {(날짜, 'CAN'): {'seen_h': [], 'cab': {}}}
    got = {}
    scans = []
    for path in files:
        rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
        keep = 0
        for r in rows:
            org = (r.get('Origin Airport') or '').strip()
            dst = (r.get('Destination Airport') or '').strip()
            if {org, dst} != {'PUS', 'CAN'}:
                continue
            direction = 'dep' if org == 'PUS' else 'arr'
            slug = (r.get('Mileage Program') or '').strip()
            if slug not in SLUGS:
                continue                     # 탭이 다루는 9개 프로그램만
            date = (r.get('Date') or '').strip()
            if not (WIN_FROM <= date <= WIN_TO):
                continue
            rec = got.setdefault((slug, direction), {}).setdefault(
                (date, 'CAN'), {'seen_h': [], 'cab': {}})
            try:
                rec['seen_h'].append(int(r['Hours Ago']))
            except (KeyError, ValueError):
                pass
            for name, idx in CABINS:
                miles = (r.get(name + ' Miles') or '').strip()
                if not miles or miles == '0':
                    continue
                ds = (r.get(name + ' Direct Seats') or '').strip()
                dc = (r.get(name + ' Direct Carriers') or '').strip()
                direct = bool(dc) or (bool(ds) and ds != '0')
                v = '%d-%s' % (0 if direct else 1, miles)
                cur = rec['cab'].get(idx)
                if cur is None or better(v, cur):
                    rec['cab'][idx] = v
            keep += 1
        scans.append((os.path.basename(path), len(rows), keep))

    total_new = 0
    for (slug, direction), rows in sorted(got.items()):
        rslug = RAW_SLUG.get(slug, slug)
        path = os.path.join(RAW, '%s_%s_PUS_can.txt' % (rslug, direction))
        old = parse_old(path)
        merged = dict(old)
        added = 0
        for key, rec in rows.items():
            if not rec['cab']:
                continue
            seen = seen_text(min(rec['seen_h'])) if rec['seen_h'] else '방금'
            prev = merged.get(key)
            cab = dict(rec['cab'])
            if prev:
                for i, v in prev['cab'].items():
                    cur = cab.get(i)
                    if cur is None or better(v, cur):
                        cab[i] = v
            else:
                added += 1
            merged[key] = {'seen': seen, 'cab': cab}
        lines = []
        for key in sorted(merged):
            o = merged[key]
            vals = [o['cab'].get(i, '-') for i in (3, 4, 5, 6)]
            lines.append('|'.join([key[0], o['seen'], key[1]] + vals))
        dates = sorted(k[0] for k in merged)
        print('%-14s %-3s  CSV %4d → 파일 %4d줄 (신규 %3d)  %s~%s  %s'
              % (rslug, direction, len(rows), len(lines), added,
                 dates[0], dates[-1], os.path.basename(path)))
        total_new += added
        if not check:
            with open(path, 'w', encoding='utf-8') as fp:
                fp.write(';'.join(lines))
    print('── CSV %d개' % len(scans))
    for name, n, keep in scans:
        print('   %-40s %5d행 중 부산↔광저우 %4d행' % (name, n, keep))
    print('TOTAL 신규 %d줄%s' % (total_new, ' (--check: 쓰지 않음)' if check else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
