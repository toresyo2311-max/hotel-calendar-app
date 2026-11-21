#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑦ 마일리지(부산) — 팀원 수집본 여러 개를 정본 수집본 하나로 합친다.

수집은 팀이 나눠 하므로 파일마다 스키마가 조금씩 다르다(필드명·메모 문구·범위 표기).
이 스크립트는 (노선, 방향, 탑승월) 한 칸을 기준으로 겹친 칸을 하나로 모으고,
뒤에 준 파일이 이기게 한다. 원천이 주지 않은 값은 만들지 않는다.

쓰는 법
  python3 tools/merge_mileage.py \\
      --src data/mileage/captures/2026-11-22.json \\
      --src work/mileage_no3_supplement.json \\
      --src memory/clones/.../0-ke-award-no4-merged.json \\
      --src memory/clones/.../0-ke-pus-mileage-no5.json \\
      --out data/mileage/captures/2026-11-22.json

  --src 는 준 순서대로 우선한다(뒤가 최신). --out 을 생략하면 표준출력으로 합친 JSON 만 낸다.
"""
import argparse
import json
import os
import sys

ROUTES = ['NRT', 'KIX', 'FUK', 'NGO', 'CTS', 'TPE', 'HKG', 'PVG', 'TAO',
          'BKK', 'SIN', 'HAN', 'SGN', 'DAD']
MONTHS = ['%d-%02d' % (y, m) for y in (2026, 2027) for m in range(1, 13)]
MONTHS = [m for m in MONTHS if '2026-12' <= m <= '2027-11']
WINDOW_END = '2027-11-16'          # 오늘(2026-11-22) + 359일 — 원천 제공 범위의 끝

NOTE_ALIASES = (
    ('직항 미운항', '원천 조회 불가'),
    ('제공 범위 밖', '17~30일 원천 미제공'),
)


def norm_note(text):
    text = ' '.join(str(text or '').split())
    if not text:
        return ''
    for needle, fixed in NOTE_ALIASES:
        if needle in text:
            return fixed
    return text


def clean_cells(month, spec, warn):
    """'1:7,2:7' → '1:7,2:7' (2027-11 은 16일까지만 — 그 뒤는 원천 제공 범위 밖)."""
    out = []
    for part in str(spec or '').split(','):
        part = part.strip()
        if not part:
            continue
        day, _, val = part.partition(':')
        day, val = int(day), int(val)
        date = '%s-%02d' % (month, day)
        if date > WINDOW_END:
            warn.append('%s 은 원천 제공 범위 밖 — 버립니다' % date)
            continue
        out.append('%d:%d' % (day, val))
    return ','.join(out)


def read_rows(path, warn):
    with open(path, encoding='utf-8') as fp:
        doc = json.load(fp)
    rows = {}
    for row in doc.get('rows') or []:
        code = str(row.get('code') or '').strip().upper()
        month = str(row.get('month') or '').strip()
        direction = int(row.get('dir') or 0)
        if code not in ROUTES:
            warn.append('%s: 모르는 노선 %r — 건너뜁니다' % (path, code))
            continue
        if month not in MONTHS:
            warn.append('%s: 탑승월 %r 이 12개월 창 밖 — 건너뜁니다' % (path, month))
            continue
        note = norm_note(row.get('note'))
        cells = clean_cells(month, row.get('cells'), warn)
        if not cells and not note:
            warn.append('%s: %s %s %s 칸에 값도 메모도 없음 — 건너뜁니다'
                        % (path, code, direction, month))
            continue
        key = (code, direction, month)
        if key in rows:
            warn.append('%s: %s %s %s 가 파일 안에서 겹칩니다 — 뒤 행이 이깁니다'
                        % (path, code, direction, month))
        rows[key] = {'code': code, 'dir': direction, 'month': month,
                     'cells': cells, 'note': note}
    meta = {k: doc.get(k) for k in ('observed', 'collectedAt', 'source', 'sourceAsOf') if doc.get(k)}
    return rows, meta


def main(argv):
    ap = argparse.ArgumentParser(description='⑦ 마일리지 수집본 병합')
    ap.add_argument('--src', action='append', required=True, help='수집본 경로(뒤에 준 것이 최신)')
    ap.add_argument('--out', help='합친 수집본을 쓸 경로(생략하면 표준출력)')
    ap.add_argument('--observed', help='원천 기준 시각(기본: 마지막 파일 값)')
    ap.add_argument('--collected-at', help='수집 시각(기본: 마지막 파일 값)')
    args = ap.parse_args(argv)

    warn = []
    merged = {}
    metas = []
    for path in args.src:
        rows, meta = read_rows(path, warn)
        added = len([k for k in rows if k not in merged])
        merged.update(rows)                    # 뒤 파일이 이긴다
        metas.append({'file': os.path.basename(path), 'path': path, 'rows': len(rows),
                      'new': added, 'overlap': len(rows) - added, 'meta': meta})
        print('  %-46s rows %3d · 새 칸 %3d · 겹쳐 덮음 %2d'
              % (os.path.basename(path), len(rows), added, len(rows) - added), file=sys.stderr)

    out_rows = []
    for code in ROUTES:
        for direction in (0, 1):
            for month in MONTHS:
                row = merged.get((code, direction, month))
                if row is None:
                    continue
                item = {'code': code, 'dir': direction, 'month': month}
                if row['cells']:
                    item['cells'] = row['cells']
                if row['note']:
                    item['note'] = row['note']
                out_rows.append(item)

    target = len(ROUTES) * 2 * len(MONTHS)
    missing = [(c, d, m) for c in ROUTES for d in (0, 1) for m in MONTHS
               if (c, d, m) not in merged]
    notes = sum(1 for r in out_rows if r.get('note'))
    cells = sum(1 for r in out_rows if r.get('cells'))

    last = metas[-1]['meta'] if metas else {}
    doc = {
        'collectedAt': args.collected_at or last.get('collectedAt') or '',
        'observed': args.observed or '2026-11-22 01:30',
        'mergedFrom': metas,
        'rows': out_rows,
    }
    blob = json.dumps(doc, ensure_ascii=False, indent=1) + '\n'
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        tmp = args.out + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fp:
            fp.write(blob)
        os.replace(tmp, args.out)
    else:
        sys.stdout.write(blob)

    print('합침 — 칸 %d/%d (값 %d · 메모 %d) · 빠진 칸 %d'
          % (len(out_rows), target, cells, notes, len(missing)), file=sys.stderr)
    for shame in warn[:40]:
        print('  ! %s' % shame, file=sys.stderr)
    if len(warn) > 40:
        print('  ! 그 밖에 %d건' % (len(warn) - 40), file=sys.stderr)
    if missing:
        print('  ! 빠진 칸: %s' % ', '.join('%s/%d/%s' % m for m in missing[:20]), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
