#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""귀국편(→PUS / →ICN) PRO 전체 연도 CSV 실측값 → tools/partner_tab/raw 파이프 포맷.

- 입력: downloads/arr_{슬러그}_{PUS|ICN}.csv (2026-11-22 실측, PRO 「전체 연도」 내보내기)
- 규칙(출발편과 동일, 화면 대조로 확인):
    X Miles = 그 등급 최저 마일. X Direct Seats 가 채워져 있으면 그 최저가 직항(0),
    비어 있으면 1회 경유(1).
- 귀국편의 '도시'는 CSV의 Origin Airport(출발 도시)다. 도착지 PUS/ICN 은 고정.
- 국내선(김포 GMP·제주 CJU 등)은 뺀다.
- 같은 (날짜, 도시)에 여러 레코드가 있으면 등급별 최저 마일·직항 우선으로 한 줄로 정리.
- 출력: tools/partner_tab/raw/{슬러그}_arr_{PUS|ICN}.txt (한 줄 = 날짜|최근확인|도시|이코|프이|비즈|퍼스트)
- 추측·보간 없음: 원천에 없는 (날짜,도시,등급)은 기록하지 않는다. 0건 프로그램은 빈 파일로 남긴다.
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, 'raw')
DL = os.environ.get('PARTNER_CSV_DIR', '/workspace/downloads')   # 내려받은 CSV 폴더
CABINS = [('Economy', 3), ('Premium Economy', 4), ('Business', 5), ('First', 6)]
DOMESTIC = {'GMP', 'CJU', 'PUS', 'TAE', 'KWJ', 'CJJ', 'RSU', 'KUV', 'HIN', 'USN',
            'WJU', 'MPC', 'KPO', 'YNY', 'ICN', 'SEL'}
WIN_FROM, WIN_TO = '2026-11-22', '2027-11-21'
SLUGS = ['flyingblue', 'smiles', 'virgin', 'delta', 'united', 'aeroplan',
         'asiamiles', 'british', 'jal']


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


def main():
    summary = {}
    for code in ('PUS', 'ICN'):
        for slug in SLUGS:
            path = os.path.join(DL, 'arr_%s_%s.csv' % (slug, code))
            out = os.path.join(RAW, '%s_arr_%s.txt' % (slug, code))
            if not os.path.exists(path):
                raise SystemExit('CSV 없음: %s' % path)
            rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
            merged, skipped_dom, skipped_win = {}, 0, 0
            for r in rows:
                city = r['Origin Airport']
                date = r['Date']
                if city in DOMESTIC:
                    skipped_dom += 1
                    continue
                if not (WIN_FROM <= date <= WIN_TO):
                    skipped_win += 1
                    continue
                rec = merged.setdefault(date + '|' + city, {'seen_h': [], 'cab': {}})
                try:
                    rec['seen_h'].append(int(r['Hours Ago']))
                except (KeyError, ValueError):
                    pass
                for name, idx in CABINS:
                    miles = (r.get(name + ' Miles') or '').strip()
                    if not miles:
                        continue
                    # 직항 판정 = 'Direct Carriers' 가 채워졌는가.
                    #   Direct Seats 는 좌석 수가 0이면 비어 나오므로(아시아마일즈처럼 좌석 수를
                    #   아예 안 주는 프로그램) 그것만 보면 직항을 경유로 잘못 적는다.
                    ds = (r.get(name + ' Direct Seats') or '').strip()
                    dc = (r.get(name + ' Direct Carriers') or '').strip()
                    direct = bool(dc) or (bool(ds) and ds != '0')
                    v = '%d-%s' % (0 if direct else 1, miles)
                    cur = rec['cab'].get(idx)
                    if cur is None or better(v, cur):
                        rec['cab'][idx] = v
            lines = []
            for key in sorted(merged):
                date, city = key.split('|')
                rec = merged[key]
                if not rec['cab']:
                    continue
                seen = seen_text(min(rec['seen_h'])) if rec['seen_h'] else '방금'
                vals = [rec['cab'].get(i, '-') for i in (3, 4, 5, 6)]
                lines.append('|'.join([date, seen, city] + vals))
            with open(out, 'w', encoding='utf-8') as fp:
                fp.write(';'.join(lines))
            summary['%s_%s' % (slug, code)] = (len(rows), len(lines), skipped_dom, skipped_win)
            print('%-3s %-11s csv %6d행 · 국내선제외 %4d · 창밖 %2d → %5d줄  %s'
                  % (code, slug, len(rows), skipped_dom, skipped_win, len(lines),
                     os.path.basename(out)))
    tot = sum(v[1] for v in summary.values())
    print('TOTAL 줄 %d · 프로그램 %d/%d' % (tot, len([v for v in summary.values() if v[1]]), len(summary)))


if __name__ == '__main__':
    main()
