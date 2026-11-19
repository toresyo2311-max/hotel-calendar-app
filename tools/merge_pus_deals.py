#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑥ 땡처리 · 부산 출발 — 수집본(JSON)을 앱에 병합한다.

    python3 tools/merge_pus_deals.py <수집본.json> [<수집본2.json> ...]          # 드라이런
    python3 tools/merge_pus_deals.py <수집본.json> --write                      # 반영 + verify

수집본 형식은 data-sources/flights-ttang/README.md 참고. 파일은
`{"observedAt":..,"window":..,"deals":[...]}` 또는 상품 배열만 있어도 된다.

병합 규칙
  · 같은 상품 키(`code`+`out`+`back`+`airline`)는 **더 싼 값**으로 갱신한다(같으면 새 값).
  · 새 키는 그대로 추가한다. 삭제는 하지 않는다.
  · `window` 는 합집합, `observedAt` 은 더 늦은 값, `coverage`/`coverageOk` 는 새 파일이 주면 덮어쓴다.
  · 병합 결과가 `tools/master_db.py` 의 `check_ttang` 을 통과하지 못하면 아무것도 쓰지 않는다.
"""
import argparse
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')


def load_tool():
    spec = importlib.util.spec_from_file_location('master_db', os.path.join(ROOT, 'tools', 'master_db.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_block(path):
    with open(path, encoding='utf-8') as fp:
        data = json.load(fp)
    if isinstance(data, list):
        return {'deals': data}
    if not isinstance(data, dict):
        raise SystemExit('%s: JSON 객체나 배열이 아닙니다' % path)
    data.setdefault('deals', [])
    return data


def deal_key(d):
    """같은 항공편 = 도착공항+출발일+귀국일+항공사. 공급사(채널)가 달라도 한 줄로 합친다."""
    return (d.get('code'), d.get('out'), d.get('back'), d.get('airline'))


def main(argv):
    ap = argparse.ArgumentParser(description='⑥ 땡처리 수집본 병합')
    ap.add_argument('files', nargs='+')
    ap.add_argument('--write', action='store_true', help='master_db.json·index.html 에 반영')
    ap.add_argument('--now', default=None, help='extract 시각 기록(기본: 지금)')
    args = ap.parse_args(argv)

    md = load_tool()
    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    cur = master.get('ttang') or {'deals': []}
    deals = [dict(d) for d in (cur.get('deals') or [])]
    index = {deal_key(d): i for i, d in enumerate(deals)}
    win = dict(cur.get('window') or {'start': md.TTANG_WINDOW[0], 'end': md.TTANG_WINDOW[1], 'basis': '출발일'})
    chans = {c.get('key'): dict(c) for c in (cur.get('channels') or [])}
    observed = cur.get('observedAt') or ''
    coverage, coverage_ok = cur.get('coverage'), cur.get('coverageOk')

    added = updated = same = 0
    seq = len(deals)
    for path in args.files:
        block = read_block(path)
        seen_in_file = set()
        for d in block.get('deals') or []:
            d = dict(d)
            seq += 1
            if not d.get('id'):
                d['id'] = 'A%03d' % seq
            if d.get('days') is None and d.get('out') and d.get('back'):
                import datetime
                o = datetime.date.fromisoformat(d['out'])
                b = datetime.date.fromisoformat(d['back'])
                d['days'] = (b - o).days + 1
            k = deal_key(d)
            if k in seen_in_file:
                print('  ! 같은 파일 안 중복 키, 뒤 값 사용: %s' % (k,))
            seen_in_file.add(k)
            if k in index:
                old = deals[index[k]]
                if d.get('price', 10 ** 9) <= old.get('price', 10 ** 9):
                    d['id'] = old.get('id') or d['id']
                    deals[index[k]] = old = d
                    updated += 1
                else:
                    same += 1
            else:
                index[k] = len(deals)
                deals.append(d)
                added += 1
        w = block.get('window') or {}
        if w.get('start'):
            win['start'] = min(win.get('start') or w['start'], w['start'])
        if w.get('end'):
            win['end'] = max(win.get('end') or w['end'], w['end'])
        for c in block.get('channels') or []:
            if c.get('key'):
                chans[c['key']] = dict(c)
        if block.get('observedAt') and block['observedAt'] > observed:
            observed = block['observedAt']
        if block.get('coverage'):
            coverage = block['coverage']
        if 'coverageOk' in block:
            coverage_ok = bool(block['coverageOk'])

    merged = {
        'schema': cur.get('schema') or md.TTANG_SCHEMA,
        'observedAt': observed or '—',
        'window': win,
        'channels': [chans[k] for k in sorted(chans)],
        'deals': deals,
    }
    # 병합 뒤 id 는 한 번 더 매긴다(여러 수집본의 id 가 서로 겹치지 않게)
    deals.sort(key=lambda d: (d.get('price') or 0, str(d.get('out'))))
    for i, d in enumerate(deals, 1):
        d['id'] = 'P%04d' % i
    if coverage:
        merged['coverage'] = coverage
    if coverage_ok is not None:
        merged['coverageOk'] = coverage_ok

    problems = md.check_ttang(merged)
    print('신규 %d건 · 갱신 %d건 · 그대로 %d건 → 합계 %d건 (노선 %d개)' % (
        added, updated, same, len(deals), len({d.get('code') for d in deals})))
    if problems:
        print('검증 실패 — 쓰지 않았습니다.')
        for p in problems:
            print('  - ' + p)
        return 1
    print('check_ttang 통과')
    if not args.write:
        print('(드라이런 — --write 로 반영)')
        return 0

    master['ttang'] = merged
    st = md.stats_of({'hotels': master['hotels'], 'accor': master.get('accor')},
                     master['flights'], merged)
    master['counts'] = {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na', 'stayplus',
                                           'routes', 'deals', 'snu', 'pus_deals', 'pus_routes')}
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('master_db.json 갱신 (⑥ %d건)' % st['pus_deals'])

    ns = argparse.Namespace(now=args.now, command='inject')
    if md.cmd_inject(ns) != 0:
        return 1
    return md.cmd_verify(ns)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
