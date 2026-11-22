#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""매일 04:00 재수집분(내려받은 CSV 36개) → tools/partner_tab/raw/*.txt 갱신.

입력: /workspace/downloads/collect/{dep|arr}_{슬러그}_{PUS|ICN}.csv
      (조회 사이트 PRO 「전체 연도」 CSV 내보내기를 그대로 받은 것)
출력: tools/partner_tab/raw/{슬러그}_{dep|arr}_{PUS|ICN}.txt
      한 줄 = YYYY-MM-DD|최근확인|상대도시|이코|프이|비즈|퍼스트  (레코드 구분 ';')

규칙
- X Miles = 그 등급 최저 마일. X Direct Carriers 가 채워졌으면 직항(0), 아니면 1회 경유(1).
  (Direct Seats 는 좌석 0이면 비어 나와 직항 판정에 쓰지 않는다 — 화면 대조로 확인한 규칙)
- 국내선(김포·제주↔부산·인천)은 뺀다. 창(2026-11-22~2027-11-21) 밖 날짜도 뺀다.
- 그날 CSV 에 없는 (날짜,도시) 는 그대로 두지 않는다(팔린 좌석이 계속 남지 않게).
  다만 공항 홈페이지에서 직접 실측한 줄은 보존한다:
    flyingblue 부산 출발·도착의 옌타이(YNT)·난징(NKG), delta 부산의 난징(NKG)
- 추측·보간 없음. CSV 가 비었으면 빈 파일로 남긴다.
"""
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, 'raw')
COLLECT = '/workspace/downloads/collect'
APPDIR = os.path.join(ROOT, 'data', 'app')

SLUGS = ['flyingblue', 'smiles', 'virginatlantic', 'delta', 'united',
         'aeroplan', 'asiamiles', 'british', 'jal']
RAW_SLUG = {'virginatlantic': 'virgin'}          # 원자료 파일 접두는 virgin
CABINS = [('Economy', 3), ('Premium Economy', 4), ('Business', 5), ('First', 6)]
DOMESTIC = {'GMP', 'CJU', 'PUS', 'TAE', 'KWJ', 'CJJ', 'RSU', 'KUV', 'HIN', 'USN',
            'WJU', 'MPC', 'KPO', 'YNY', 'ICN', 'SEL'}
WIN_FROM, WIN_TO = '2026-11-22', '2027-11-21'
# 공항 홈페이지 실측분 보존: (슬러그, 코드, 방향, 도시)
PRESERVE = {('flyingblue', 'PUS', 'dep', 'YNT'), ('flyingblue', 'PUS', 'dep', 'NKG'),
            ('flyingblue', 'PUS', 'arr', 'YNT'), ('flyingblue', 'PUS', 'arr', 'NKG'),
            ('delta', 'PUS', 'dep', 'NKG'), ('delta', 'PUS', 'arr', 'NKG')}


def seen_text(hours):
    h = int(hours)
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
    txt = open(path, encoding='utf-8').read().strip()
    for rec in txt.split(';'):
        rec = rec.strip()
        if not rec:
            continue
        p = rec.split('|')
        if len(p) != 7:
            raise SystemExit('형식 불일치 %r (%s)' % (rec, path))
        out[(p[0], p[2])] = {'seen': p[1], 'cab': {i: v for i, v in enumerate(p[3:7], start=3) if v != '-'}}
    return out


def main(argv):
    only = set(a for a in argv if not a.startswith('-'))
    report = {}
    for code in ('PUS', 'ICN'):
        for direction in ('dep', 'arr'):
            for slug in SLUGS:
                key = '%s_%s_%s' % (direction, slug, code)
                if only and key not in only:
                    continue
                rslug = RAW_SLUG.get(slug, slug)
                path = os.path.join(RAW, '%s_%s_%s.txt' % (rslug, direction, code))
                old = parse_old(path)
                csv_path = os.path.join(COLLECT, '%s_%s_%s.csv' % (direction, slug, code))
                new = {}
                if os.path.exists(csv_path):
                    rows = list(csv.DictReader(open(csv_path, encoding='utf-8-sig')))
                    for r in rows:
                        if direction == 'dep':
                            org, dest = r['Origin Airport'], r['Destination Airport']
                        else:
                            org, dest = r['Destination Airport'], r['Origin Airport']
                        if org != code:
                            raise SystemExit('출발지 불일치 %s %s' % (csv_path, org))
                        date = r['Date']
                        if dest in DOMESTIC or not (WIN_FROM <= date <= WIN_TO):
                            continue
                        rec = new.setdefault((date, dest), {'seen_h': [], 'cab': {}})
                        try:
                            rec['seen_h'].append(int(r['Hours Ago']))
                        except (KeyError, ValueError):
                            pass
                        for name, idx in CABINS:
                            miles = (r.get(name + ' Miles') or '').strip()
                            if not miles:
                                continue
                            ds = (r.get(name + ' Direct Seats') or '').strip()
                            dc = (r.get(name + ' Direct Carriers') or '').strip()
                            direct = bool(dc) or (bool(ds) and ds != '0')
                            v = '%d-%s' % (0 if direct else 1, miles)
                            cur = rec['cab'].get(idx)
                            if cur is None or better(v, cur):
                                rec['cab'][idx] = v
                out = {}
                for (date, dest), rec in new.items():
                    if not rec['cab']:
                        continue
                    seen = seen_text(min(rec['seen_h'])) if rec['seen_h'] else '방금'
                    out[(date, dest)] = {'seen': seen, 'cab': dict(rec['cab'])}
                kept = 0
                for (date, dest), rec in old.items():
                    if (date, dest) in out:
                        continue
                    if (slug, code, direction, dest) in PRESERVE and rec['cab']:
                        out[(date, dest)] = rec
                        kept += 1
                lines = []
                for key2 in sorted(out):
                    o = out[key2]
                    vals = [o['cab'].get(i, '-') for i in (3, 4, 5, 6)]
                    lines.append('|'.join([key2[0], o['seen'], key2[1]] + vals))
                with open(path, 'w', encoding='utf-8') as fp:
                    fp.write(';'.join(lines))
                report[key] = {'csv_rows': len(rows) if os.path.exists(csv_path) else 0,
                               'old': len(old), 'kept': kept, 'out': len(lines),
                               'file': os.path.basename(path)}
                print('%-16s csv %6d · 기존 %5d · 공홈보존 %3d → %5d줄  %s'
                      % (key, report[key]['csv_rows'], len(old), kept, len(lines),
                         os.path.basename(path)))
    with open('/workspace/downloads/collect/_refresh_report.json', 'w', encoding='utf-8') as fp:
        json.dump(report, fp, ensure_ascii=False, indent=1)
    print('TOTAL 줄 %d' % sum(v['out'] for v in report.values()))


if __name__ == '__main__':
    main(sys.argv[1:])
