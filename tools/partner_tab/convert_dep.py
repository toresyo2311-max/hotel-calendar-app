#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PRO 전체 연도 CSV 실측값 → tools/partner_tab/raw 파이프 포맷 병합.

- CSV: PRO "전체 연도" 내보내기(2026-11-22 실측, downloads/)
- 규칙(화면 대조로 확인): X Miles = 그 등급 최저 마일. X Direct Seats 가 채워져 있으면
  그 최저가가 직항(0), 비어 있으면 1회 경유(1). Direct Miles 열은 항상 비어 있음(미사용).
- 병합: CSV가 (날짜,도착) 조합을 갖고 있으면 그 등급 값으로 완전 교체(최신 실측),
  CSV에 없는 조합은 기존 raw 값 유지 → flyingblue PUS 공홈 실측 YNT 행은 그대로 보존.
- 같은 (날짜,도착)에 여러 레코드가 있으면 등급별 최저 마일·직항 우선으로 한 레코드로 정리.
- 날짜는 전부 YYYY-MM-DD 전체 형식으로 정규화해 기록(2027-11 월 구분이 필요해서).
"""
import csv
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, 'raw')
DL = os.environ.get('PARTNER_CSV_DIR', '/workspace/downloads')   # 내려받은 CSV 폴더

CSV_KEY = {
    'flyingblue': 'Air France_KLM Flying Blue',
    'smiles': 'GOL Smiles',
    'virgin': 'Virgin Atlantic',
    'delta': 'Delta SkyMiles',
    'united': 'United MileagePlus',
    'aeroplan': 'Air Canada Aeroplan',
    'asiamiles': 'Cathay Pacific Asia Miles',
    'british': 'British Airways Club',
    'jal': 'JAL Mileage Bank',
}
CABINS = [('Economy', 3), ('Premium Economy', 4), ('Business', 5), ('First', 6)]
DOMESTIC = {'GMP', 'CJU', 'PUS', 'TAE', 'KWJ', 'CJJ', 'RSU', 'KUV', 'HIN', 'USN',
            'WJU', 'MPC', 'KPO', 'YNY', 'ICN', 'SEL'}
WIN_FROM, WIN_TO = '2026-11-22', '2027-11-21'   # 대상 1년 창 밖(과거 잔여 레코드 등)은 제외


def seen_text(hours):
    h = int(hours)
    if h <= 0:
        return '방금'
    if h < 24:
        return '%d시간 전' % h
    return '%d일 전' % (h // 24)


def full_mmdd(s):
    """기존 MM-DD(또는 YYYY-MM-DD) → YYYY-MM-DD 정규화(빌더와 같은 해 규칙)."""
    if len(s) == 10 and s[4] == '-':
        return s
    mm, dd = s.split('-')
    year = 2026 if int(mm) >= 11 else 2027
    return '%d-%s-%s' % (year, mm, dd)


def parse_old(path):
    out = []
    with open(path, encoding='utf-8') as fp:
        txt = fp.read()
    for rec in txt.replace('\n', ';').split(';'):
        rec = rec.strip()
        if not rec:
            continue
        parts = rec.split('|')
        if len(parts) != 7:
            raise SystemExit('형식 불일치 %r (%s)' % (rec, path))
        out.append(parts)
    return out


def better(new, cur):
    """'n-miles' 비교: 마일 최저, 같으면 직항 우선."""
    ns, nm = new.split('-')
    cs, cm = cur.split('-')
    return (int(nm), int(ns)) < (int(cm), int(cs))


def load_csv(slug, org):
    key = CSV_KEY[slug]
    cands = []
    for p in glob.glob(os.path.join(DL, 'seats.aero %s Export*.csv' % key)):
        rows = [r for r in csv.DictReader(open(p, encoding='utf-8-sig'))
                if r.get('Origin Airport') == org]
        if rows:
            cands.append((len(rows), p, rows))
    if not cands:
        return []
    cands.sort()
    return cands[-1][2]


def csv_records(rows):
    """CSV 행 → {(date,dest): {'seen_h':[..],'cab':{idx:'n-miles'}}} (등급별 최저·직항 우선)."""
    merged = {}
    for r in rows:
        date, dest = r['Date'], r['Destination Airport']
        if not (WIN_FROM <= r['Date'] <= WIN_TO):
            continue
        if dest in DOMESTIC:
            continue
        rec = merged.setdefault(date + '|' + dest, {'seen_h': [], 'cab': {}})
        try:
            rec['seen_h'].append(int(r['Hours Ago']))
        except (KeyError, ValueError):
            pass
        for name, idx in CABINS:
            miles = (r.get(name + ' Miles') or '').strip()
            if not miles:
                continue
            # 직항 판정 = 'Direct Carriers' 가 채워졌는가(Direct Seats 는 좌석 0이면 비어 나온다)
            ds = (r.get(name + ' Direct Seats') or '').strip()
            dc = (r.get(name + ' Direct Carriers') or '').strip()
            direct = bool(dc) or (bool(ds) and ds != '0')
            v = '%d-%s' % (0 if direct else 1, miles)
            cur = rec['cab'].get(idx)
            if cur is None or better(v, cur):
                rec['cab'][idx] = v
    return merged


def main():
    total = {}
    for org in ('PUS', 'ICN'):
        print('==== %s ====' % org)
        for slug in CSV_KEY:
            rows = load_csv(slug, org)
            new = csv_records(rows)
            old = {}
            old_files = sorted(glob.glob(os.path.join(RAW, '%s_dep_%s*.txt' % (slug, org))))
            for f in old_files:
                for rec in parse_old(f):
                    date, seen, dest = full_mmdd(rec[0]), rec[1], rec[2]
                    if dest in DOMESTIC:
                        continue
                    e = old.setdefault((date, dest), {'seen': seen, 'cab': {}})
                    for i, v in enumerate(rec[3:7], start=3):
                        if v != '-':
                            e['cab'].setdefault(i, v)
            out = {}
            for (date, dest), e in old.items():      # 기존 값(예: 공홈 YNT) 유지
                out[(date, dest)] = {'seen': e['seen'], 'cab': dict(e['cab'])}
            n_upd = 0
            for key, rec in new.items():             # CSV 최신 실측으로 완전 교체
                date, dest = key.split('|')
                out[(date, dest)] = {'seen': None, 'cab': dict(rec['cab'])}
                n_upd += 1
            lines = []
            for (date, dest) in sorted(out):
                o = out[(date, dest)]
                if not o['cab']:
                    continue                          # 등급 값이 하나도 없으면 기록하지 않음
                seen = o['seen'] or '방금'
                vals = [o['cab'].get(i, '-') for i in (3, 4, 5, 6)]
                lines.append('|'.join([date, seen, dest] + vals))
            path = os.path.join(RAW, '%s_dep_%s.txt' % (slug, org))
            with open(path, 'w', encoding='utf-8') as fp:
                fp.write(';'.join(lines))
            total[slug + '_' + org] = len(lines)
            print('%-11s csv %5d행 · 기존 %4d조합 · 병합 %5d행(CSV교체 %4d) → %s'
                  % (slug, len(rows), len(old), len(lines), n_upd, os.path.basename(path)))
            for f in old_files:
                if os.path.abspath(f) != os.path.abspath(path):
                    os.remove(f)
                    print('   DEL', os.path.basename(f))
    print('TOTAL', total)


if __name__ == '__main__':
    main()
