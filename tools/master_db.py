#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotel-calendar-app 통합 마스터 DB 도구.

`index.html` 안의 `const DB`(호텔 176곳 × 365일)와 `const FLIGHTS`(부산 출발 항공 특가)를
읽어 `data/master_db.json` 한 파일로 모으고, 그 파일이 라이브 앱과 정확히 같은지 검사한다.

사용법 (저장소 루트에서):
    python3 tools/master_db.py extract   # index.html -> data/master_db.json (전체 재생성)
    python3 tools/master_db.py verify    # master_db.json 이 index.html 과 일치하는지 검사
    python3 tools/master_db.py inject    # master_db.json -> index.html (DB·FLIGHTS 다시 채움)
    python3 tools/master_db.py stats     # 수록 범위·건수만 출력

`inject` 는 index.html 을 백업한 뒤 `const DB = ...` / `const FLIGHTS = ...` 두 구간만
바꾸고, 나머지 바이트는 그대로 둔다. 바꾼 뒤 스스로 `verify` 를 다시 돌려 실패하면 되돌린다.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

WINDOW_START = '2026-12-01'
WINDOW_END = '2027-11-30'


# ---------------------------------------------------------------- 추출 / 주입

def _read(path):
    with open(path, encoding='utf-8') as fp:
        return fp.read()


def find_literal(src, name):
    """`const NAME = <json>` 의 (시작, 끝) 오프셋을 중괄호 짝으로 찾는다."""
    m = re.search(r'\bconst\s+' + re.escape(name) + r'\s*=\s*', src)
    if not m:
        raise SystemExit('index.html 에서 const %s 를 찾지 못했습니다.' % name)
    i = m.end()
    while i < len(src) and src[i] not in '{[':
        i += 1
    opener = src[i]
    closer = '}' if opener == '{' else ']'
    depth, in_str, esc, j = 0, False, False, i
    while j < len(src):
        c = src[j]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return i, j + 1
        j += 1
    raise SystemExit('const %s 의 JSON 이 닫히지 않았습니다.' % name)


def read_index(path=INDEX):
    src = _read(path)
    a, b = find_literal(src, 'DB')
    db = json.loads(src[a:b])
    c, d = find_literal(src, 'FLIGHTS')
    flights = json.loads(src[c:d])
    return src, db, flights, (a, b), (c, d)


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


# ---------------------------------------------------------------- 통계

def stats_of(db, flights):
    hotels = db['hotels']
    cells = sum(len(h.get('rates') or {}) for h in hotels)
    priced = sum(1 for h in hotels for v in (h.get('rates') or {}).values() if v is not None)
    stayplus = sum(len(h.get('stayplus2') or {}) + len(h.get('stayplus3') or {}) for h in hotels)
    tabs = {}
    for h in hotels:
        tabs[h.get('group')] = tabs.get(h.get('group'), 0) + 1
    routes = flights.get('routes') or []
    deals = sum(len(r.get('deals') or []) for r in routes)
    dates = set()
    for h in hotels:
        dates.update((h.get('rates') or {}).keys())
    return {
        'hotels': len(hotels),
        'tabs': tabs,
        'cells': cells,
        'priced': priced,
        'na': cells - priced,
        'stayplus': stayplus,
        'routes': len(routes),
        'deals': deals,
        'priced_per_hotel': {h['id']: sum(1 for v in (h.get('rates') or {}).values() if v is not None)
                             for h in hotels},
        'cells_per_hotel': {h['id']: len(h.get('rates') or {}) for h in hotels},
        'dates': len(dates),
        'date_min': min(dates) if dates else None,
        'date_max': max(dates) if dates else None,
    }


# ---------------------------------------------------------------- extract

def cmd_extract(args):
    src, db, flights, _, _ = read_index()
    commit = os.environ.get('MASTER_DB_COMMIT', '')
    if not commit:
        try:
            import subprocess
            commit = subprocess.check_output(['git', '-C', ROOT, 'rev-parse', '--short', 'HEAD'],
                                             text=True).strip()
        except Exception:
            commit = 'unknown'
    st = stats_of(db, flights)
    master = {
        'schema': 'hotel-calendar-app/master-db',
        'version': 1,
        'generated_at': args.now,
        'source': {'file': 'index.html', 'commit': commit, 'tool': 'tools/master_db.py extract'},
        'window': {'start': WINDOW_START, 'end': WINDOW_END, 'days': 365},
        'built': db.get('built'),
        'voucherExpiry': db.get('voucherExpiry'),
        'extended': db.get('extended'),
        'counts': {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na', 'stayplus', 'routes', 'deals')},
        'sources': db.get('sources') or [],
        'hotels': db['hotels'],
        'flights': flights,
    }
    os.makedirs(os.path.dirname(MASTER), exist_ok=True)
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('wrote %s' % os.path.relpath(MASTER, ROOT))
    print('  hotels %(hotels)d  cells %(cells)d  priced %(priced)d  na %(na)d' % st)
    print('  stayplus %(stayplus)d  routes %(routes)d  deals %(deals)d' % st)
    print('  date window %s ~ %s (%d days)' % (st['date_min'], st['date_max'], st['dates']))
    return 0


# ---------------------------------------------------------------- verify

def project(master):
    """master_db.json -> index.html 의 `const DB` / `const FLIGHTS` 에 들어가야 할 값."""
    db = {
        'hotels': master['hotels'],
        'sources': master['sources'],
        'built': master['built'],
        'voucherExpiry': master['voucherExpiry'],
        'extended': master['extended'],
    }
    return db, master['flights']


def cmd_verify(args, quiet=False):
    master = json.loads(_read(MASTER))
    _, db, flights, _, _ = read_index()
    problems = []

    mdb, mfl = project(master)
    if compact(mdb) != compact(db):
        # 어느 부분이 다른지 좁혀서 알려준다
        if list(mdb.keys()) != list(db.keys()):
            problems.append('DB key 순서/구성 다름: %s vs %s' % (list(mdb.keys()), list(db.keys())))
        if mdb['hotels'] != db['hotels']:
            for a, b in zip(mdb['hotels'], db['hotels']):
                if a != b:
                    problems.append('hotel %s 내용 다름' % a.get('id'))
                    break
            else:
                problems.append('hotel 개수 다름: %d vs %d' % (len(mdb['hotels']), len(db['hotels'])))
        for k in ('sources', 'built', 'voucherExpiry', 'extended'):
            if mdb[k] != db[k]:
                problems.append('DB.%s 다름' % k)
    if compact(mfl) != compact(flights):
        problems.append('FLIGHTS 내용 다름')

    st = stats_of(db, flights)
    expect = master.get('counts') or {}
    for k in ('hotels', 'tabs', 'cells', 'priced', 'na', 'stayplus', 'routes', 'deals'):
        if k in expect and expect[k] != st[k]:
            problems.append('counts.%s 불일치: master=%s index=%s' % (k, expect[k], st[k]))
    if st['date_min'] != WINDOW_START or st['date_max'] != WINDOW_END or st['dates'] != 365:
        problems.append('날짜 창 이상: %s ~ %s (%d일)' % (st['date_min'], st['date_max'], st['dates']))
    for hid, n in st['cells_per_hotel'].items():
        if n != 365:
            problems.append('%s 날짜 칸 %d개 (365 이어야 함)' % (hid, n))

    if problems:
        print('VERIFY FAIL')
        for p in problems:
            print('  - ' + p)
        return 1
    if not quiet:
        print('VERIFY OK — master_db.json == index.html')
        print('  hotels %(hotels)d  tabs %(tabs)s' % st)
        print('  cells %(cells)d  priced %(priced)d  na %(na)d  stayplus %(stayplus)d' % st)
        print('  routes {routes}  deals {deals}  window {date_min}~{date_max}'.format(**st))
    return 0


# ---------------------------------------------------------------- inject

def cmd_inject(args):
    if cmd_verify(args, quiet=True) != 0:
        print('master_db.json 이 이미 index.html 과 다릅니다 — verify 로 차이를 먼저 확인하세요.')
        print('(다른 데이터를 넣으려면 수정한 뒤 inject 하는 것이 맞습니다. 계속 진행합니다.)')
    master = json.loads(_read(MASTER))
    mdb, mfl = project(master)
    src, db, flights, span_db, span_fl = read_index()

    if compact(db) == compact(mdb) and compact(flights) == compact(mfl):
        print('index.html 이 이미 master_db.json 과 같습니다 — 바꾸지 않았습니다.')
        return 0

    new = src
    # 뒤쪽(FLIGHTS)부터 바꿔야 앞쪽 오프셋이 흔들리지 않는다
    new = new[:span_fl[0]] + compact(mfl) + new[span_fl[1]:]
    new = new[:span_db[0]] + compact(mdb) + new[span_db[1]:]

    backup = INDEX + '.bak'
    shutil.copy2(INDEX, backup)
    with open(INDEX, 'w', encoding='utf-8') as fp:
        fp.write(new)
    if cmd_verify(args, quiet=True) != 0:
        shutil.copy2(backup, INDEX)
        print('검증 실패 — index.html 을 백업으로 되돌렸습니다.')
        return 1
    os.remove(backup)
    print('index.html 갱신 완료 (DB %d호텔, FLIGHTS %d노선)' % (len(mdb['hotels']), len(mfl.get('routes') or [])))
    return 0


# ---------------------------------------------------------------- stats

def cmd_stats(args):
    _, db, flights, _, _ = read_index()
    st = stats_of(db, flights)
    print('index.html 기준')
    print('  hotels  %d  %s' % (st['hotels'], st['tabs']))
    print('  cells   %d  (priced %d / NA %d)' % (st['cells'], st['priced'], st['na']))
    print('  stayplus %d건' % st['stayplus'])
    print('  flights %d노선 %d건' % (st['routes'], st['deals']))
    print('  window  %s ~ %s (%d일)' % (st['date_min'], st['date_max'], st['dates']))
    print()
    print('호텔별 요금 표기 칸수')
    for h in db['hotels']:
        print('  %-7s %-34s %3d/365' % (h['id'], h['name'], st['priced_per_hotel'][h['id']]))
    return 0


def main(argv):
    import argparse
    import datetime
    p = argparse.ArgumentParser(description='hotel-calendar-app 통합 마스터 DB 도구')
    p.add_argument('command', choices=['extract', 'verify', 'inject', 'stats'])
    p.add_argument('--now', default=datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z'),
                   help='extract 시 기록할 생성 시각')
    args = p.parse_args(argv)
    return {'extract': cmd_extract, 'verify': cmd_verify,
            'inject': cmd_inject, 'stats': cmd_stats}[args.command](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
