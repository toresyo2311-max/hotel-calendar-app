#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑧ 외항사 마일 — seats.aero Partner API 수집기 (브라우저 크롤링 대체).

기존 길(탐험 화면 36개 CSV 내려받기 → grab_csv.py → refresh_from_csv.py)을 대신해,
공식 Partner API `GET /search`(Cached Search)로 9개 프로그램의 부산(PUS)·인천(ICN)
출발편·귀국편을 한 번에 받아 `tools/partner_tab/raw/*.txt` 를 다시 쓴다.

    python3 tools/partner_tab/fetch_seats_aero_api.py                # PUS·ICN 전부
    python3 tools/partner_tab/fetch_seats_aero_api.py --origins PUS   # 부산만
    python3 tools/partner_tab/fetch_seats_aero_api.py --dry-run       # 쓰지 않고 호출·건수만
    python3 tools/partner_tab/fetch_seats_aero_api.py --report /path/report.json

인증(보안)
- 키는 환경변수 `SEATS_AERO_API_KEY` 또는 `/workspace/.secrets/seats_aero_api_key`(권한 600)에서 읽는다.
  저장소·스크립트에는 키를 적지 않는다(공개 저장소).
- 일 1,000회 한도(UTC 자정 초기화). 응답 헤더 `X-RateLimit-Remaining` 을 그대로 세어 보고한다.

호출 구성(1회 전체 수집)
    GET /routes?source={9곳}                 → 9회  (프로그램별 노선표 → 목적지 후보)
    GET /destinations?origin_airport={PUS|ICN} → 2회  (비경유 도착지 후보)
    GET /search?origin_airport=…&destination_airport=…&sources={슬러그}
        = 9프로그램 × 2출발지 × 2방향 = 36회 + 페이지 넘김(1,000건 단위) 회수
    Program API 는 공항 단위 필터가 /search 에만 있어, 방향별로 목적지 목록을 붙여 부른다.

원자료 형식(기존과 동일)
    한 줄 = YYYY-MM-DD|최근확인|상대도시|이코|프이|비즈|퍼스트, 레코드 구분 ';'
    등급 값 = `직항편수-마일` (0 = 직항, 1 = 1회 이상 경유), 없으면 `-`
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, 'raw')
APPDIR = os.path.join(ROOT, 'data', 'app')
BASE = 'https://seats.aero/partnerapi'
KEY_FILE = '/workspace/.secrets/seats_aero_api_key'

# 프로그램 슬러그(API `source` 값) → 원자료 파일 접두
SOURCES = [
    ('flyingblue', 'flyingblue'),
    ('smiles', 'smiles'),
    ('virginatlantic', 'virgin'),
    ('delta', 'delta'),
    ('united', 'united'),
    ('aeroplan', 'aeroplan'),
    ('asiamiles', 'asiamiles'),
    ('british', 'british'),
    ('jal', 'jal'),
]
CABINS = [('Y', 3), ('W', 4), ('J', 5), ('F', 6)]
DOMESTIC = {'GMP', 'CJU', 'PUS', 'TAE', 'KWJ', 'CJJ', 'RSU', 'KUV', 'HIN', 'USN',
            'WJU', 'MPC', 'KPO', 'YNY', 'ICN', 'SEL'}
# 공항 홈페이지에서 직접 실측해 둔 줄 — API 결과가 0이어도 지우지 않는다.
PRESERVE = {('flyingblue', 'PUS', 'dep', 'YNT'), ('flyingblue', 'PUS', 'dep', 'NKG'),
            ('flyingblue', 'PUS', 'arr', 'YNT'), ('flyingblue', 'PUS', 'arr', 'NKG'),
            ('delta', 'PUS', 'dep', 'NKG'), ('delta', 'PUS', 'arr', 'NKG')}
ORIGIN_JSON = {'PUS': 'tab9_partner_mileage.json', 'ICN': 'tab9_partner_mileage_icn.json'}

CALLS = []          # {'path','params','status','rows'}
REMAIN = {'last': None, 'first': None, 'reset': None}


def api_key():
    k = os.environ.get('SEATS_AERO_API_KEY', '').strip()
    if k:
        return k
    if os.path.exists(KEY_FILE):
        return open(KEY_FILE, encoding='utf-8').read().strip()
    raise SystemExit('API 키가 없습니다 — 환경변수 SEATS_AERO_API_KEY 또는 %s' % KEY_FILE)


KEY = None


def api(path, params, tries=4):
    """GET /partnerapi{path} → (json, headers). 429·5xx 는 잠깐 쉬고 다시."""
    global KEY
    if KEY is None:
        KEY = api_key()
    qs = urllib.parse.urlencode(params, safe=',')
    url = '%s%s%s' % (BASE, path, ('?' + qs) if qs else '')
    delay = 3
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={'Partner-Authorization': KEY,
                                                   'Accept': 'application/json',
                                                   'User-Agent': 'hotel-calendar-app/partner-tab'})
        try:
            with urllib.request.urlopen(req, timeout=120) as fp:
                body = fp.read()
                hdr = dict(fp.headers)
            rem = hdr.get('X-RateLimit-Remaining') or hdr.get('x-ratelimit-remaining')
            if rem is not None:
                rem = int(rem)
                if REMAIN['first'] is None:
                    REMAIN['first'] = rem
                REMAIN['last'] = rem
                REMAIN['reset'] = hdr.get('X-RateLimit-Reset') or hdr.get('x-ratelimit-reset')
            data = json.loads(body.decode('utf-8'))
            CALLS.append({'path': path, 'params': params, 'status': 200,
                          'rows': len(data.get('data', [])) if isinstance(data, dict) else
                                  (len(data) if isinstance(data, list) else 0),
                          'remaining': rem})
            return data, hdr
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')[:300]
            CALLS.append({'path': path, 'params': params, 'status': e.code,
                          'rows': 0, 'error': msg})
            if e.code in (429, 500, 502, 503, 504):
                print('  ! HTTP %d — %ds 뒤 재시도 (%s)' % (e.code, delay, msg[:120]),
                      file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            raise SystemExit('API 오류 HTTP %d: %s\n%s' % (e.code, url[:200], msg))
        except (urllib.error.URLError, TimeoutError) as e:
            CALLS.append({'path': path, 'params': params, 'status': 0, 'rows': 0,
                          'error': str(e)})
            print('  ! 연결 실패 — %ds 뒤 재시도 (%s)' % (delay, e), file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    raise SystemExit('API 호출이 계속 실패했습니다: %s' % path)


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
    for rec in open(path, encoding='utf-8').read().strip().split(';'):
        rec = rec.strip()
        if not rec:
            continue
        p = rec.split('|')
        if len(p) != 7:
            raise SystemExit('형식 불일치 %r (%s)' % (rec, path))
        out[(p[0], p[2])] = {'seen': p[1],
                             'cab': {i: v for i, v in enumerate(p[3:7], start=3) if v != '-'}}
    return out


def existing_dests(code):
    """지금 원자료·JSON에 있는 상대 도시(놓치지 않게 후보에 넣는다)."""
    dep, arr = set(), set()
    for api_slug, raw_slug in SOURCES:
        for d, side in (('dep', dep), ('arr', arr)):
            for f in sorted(os.listdir(RAW)):
                if f.startswith('%s_%s_%s' % (raw_slug, d, code)) and f.endswith('.txt'):
                    for rec in open(os.path.join(RAW, f), encoding='utf-8').read().split(';'):
                        p = rec.strip().split('|')
                        if len(p) == 7:
                            side.add(p[2])
    j = os.path.join(APPDIR, ORIGIN_JSON[code])
    if os.path.exists(j):
        data = json.load(open(j, encoding='utf-8'))
        for r in data.get('rows', []):
            (dep if r[8] == 0 else arr).add(r[3])
    return dep, arr


ROUTE_CACHE = {}


def routes_of(api_slug):
    if api_slug not in ROUTE_CACHE:
        routes, _h = api('/routes', {'source': api_slug})
        ROUTE_CACHE[api_slug] = routes if isinstance(routes, list) else []
    return ROUTE_CACHE[api_slug]


def dest_candidates(origin):
    """방향별 목적지 후보 — /routes(9곳 합집합) + /destinations + 기존 자료."""
    out_dep, out_arr = existing_dests(origin)
    for api_slug, _ in SOURCES:
        routes = routes_of(api_slug)
        for r in routes:
            if r.get('OriginAirport') == origin:
                out_dep.add(r.get('DestinationAirport'))
            if r.get('DestinationAirport') == origin:
                out_arr.add(r.get('OriginAirport'))
    for which, side in (('origin_airport', out_dep), ('destination_airport', out_arr)):
        d, _h = api('/destinations', {which: origin})
        for x in (d.get('destinations') or []):
            if x.get('airport'):
                side.add(x['airport'])
    for s in (out_dep, out_arr):
        s.discard(None)
        s.difference_update(DOMESTIC)
    return sorted(out_dep), sorted(out_arr)


def pull(origin, direction, api_slug, raw_slug, dests, win_from, win_to, stat):
    """한 (출발지·방향·프로그램) 자료를 /search 로 끝까지 받아 raw 줄로 만든다."""
    if not dests:
        return {}
    if direction == 'dep':
        base = {'origin_airport': origin, 'destination_airport': ','.join(dests)}
    else:
        base = {'origin_airport': ','.join(dests), 'destination_airport': origin}
    base.update({'sources': api_slug, 'start_date': win_from, 'end_date': win_to,
                 'take': 1000, 'include_filtered': 'true'})
    rows = {}
    skip = 0
    cursor = None
    pages = 0
    while True:
        params = dict(base)
        if cursor is not None:
            params['cursor'] = cursor
        if skip:
            params['skip'] = skip
        data, _h = api('/search', params)
        batch = data.get('data') or []
        pages += 1
        cursor = data.get('cursor', cursor)
        for r in batch:
            route = r.get('Route') or {}
            if direction == 'dep':
                org, dest = route.get('OriginAirport'), route.get('DestinationAirport')
            else:
                org, dest = route.get('DestinationAirport'), route.get('OriginAirport')
            if org != origin or not dest or dest in DOMESTIC:
                continue
            date = r.get('Date') or ''
            if not (win_from <= date <= win_to):
                continue
            cab = {}
            for letter, idx in CABINS:
                if not r.get(letter + 'Available'):
                    continue
                cost = str(r.get(letter + 'MileageCost') or '').strip()
                if not cost or cost in ('0', 'None'):
                    continue
                direct = bool(r.get(letter + 'Direct'))
                v = '%d-%s' % (0 if direct else 1, cost)
                cur = cab.get(idx)
                if cur is None or better(v, cur):
                    cab[idx] = v
            if not cab:
                continue
            seen = None
            up = r.get('UpdatedAt')
            if up:
                try:
                    t = datetime.datetime.fromisoformat(up.replace('Z', '+00:00'))
                    hrs = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 3600.0
                    seen = max(0, int(hrs))
                except ValueError:
                    pass
            k = (date, dest)
            prev = rows.get(k)
            if prev is None:
                rows[k] = {'seen_h': seen, 'cab': cab}
            else:
                if seen is not None and (prev['seen_h'] is None or seen < prev['seen_h']):
                    prev['seen_h'] = seen
                for i, v in cab.items():
                    cur = prev['cab'].get(i)
                    if cur is None or better(v, cur):
                        prev['cab'][i] = v
        if not data.get('hasMore'):
            break
        if not batch:
            break
        skip += len(batch)
        if pages > 400:
            print('  ! 페이지 상한(400) 도달 — %s %s 중단' % (origin, api_slug), file=sys.stderr)
            break
    stat[api_slug] = stat.get(api_slug, {'rows': 0, 'pages': 0})
    stat[api_slug]['rows'] += len(rows)
    stat[api_slug]['pages'] += pages
    return rows


def write_raw(path, rows, origin, direction, api_slug, kept):
    lines = []
    merged = dict(rows)
    for k, v in kept.items():
        if k not in merged:
            merged[k] = v
    for k in sorted(merged):
        o = merged[k]
        cab = o['cab']
        seen = o.get('seen') or (seen_text(o['seen_h']) if o.get('seen_h') is not None else '방금')
        lines.append('|'.join([k[0], seen, k[1]] + [cab.get(i, '-') for i in (3, 4, 5, 6)]))
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(';'.join(lines))
    return len(lines)


def main(argv):
    only_origins = ['PUS', 'ICN']
    only_sources = None
    dry = '--dry-run' in argv
    report_path = None
    for i, a in enumerate(argv):
        if a == '--origins':
            only_origins = [x.strip().upper() for x in argv[i + 1].split(',')]
        elif a == '--sources':
            only_sources = [x.strip() for x in argv[i + 1].split(',')]
        elif a == '--report':
            report_path = argv[i + 1]

    started = time.time()
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    win_from = now.date().isoformat()
    win_to = (now.date() + datetime.timedelta(days=364)).isoformat()
    print('수집 창 %s ~ %s · 프로그램 %d곳 · 출발지 %s'
          % (win_from, win_to, len(SOURCES), ','.join(only_origins)))

    summary = {'startedAt': now.isoformat(timespec='seconds'), 'window': [win_from, win_to],
               'origins': {}}
    for origin in only_origins:
        dep_c, arr_c = dest_candidates(origin)
        print('%s 후보 도시 — 출발 %d · 도착 %d' % (origin, len(dep_c), len(arr_c)))
        summary['origins'][origin] = {'destCandidates': {'dep': len(dep_c), 'arr': len(arr_c)},
                                      'programs': {}}
        for api_slug, raw_slug in SOURCES:
            if only_sources and api_slug not in only_sources:
                continue
            for direction, dests in (('dep', dep_c), ('arr', arr_c)):
                path = os.path.join(RAW, '%s_%s_%s.txt' % (raw_slug, direction, origin))
                old = parse_old(path)
                kept = {}
                if not dry:
                    for k, v in old.items():
                        if (api_slug, origin, direction, k[1]) in PRESERVE and v['cab']:
                            kept[k] = v
                stat = {}
                rows = pull(origin, direction, api_slug, raw_slug, dests, win_from, win_to, stat)
                if dry:
                    n = len(rows) + len(kept)
                    print('  %-14s %s %s  %5d줄 (API %d · 공홈보존 %d) · 페이지 %d'
                          % (api_slug, origin, direction, n, len(rows), len(kept),
                             stat.get(api_slug, {}).get('pages', 0)))
                else:
                    n = write_raw(path, rows, origin, direction, api_slug, kept)
                    print('  %-14s %s %s  %5d줄 (API %d · 공홈보존 %d → 기존 %d) · 페이지 %d'
                          % (api_slug, origin, direction, n, len(rows), len(kept), len(old),
                             stat.get(api_slug, {}).get('pages', 0)))
                summary['origins'][origin]['programs'].setdefault(api_slug, {})[direction] = {
                    'rows': n, 'apiRows': len(rows), 'preserved': len(kept),
                    'prev': len(old), 'pages': stat.get(api_slug, {}).get('pages', 0)}

    ok = [c for c in CALLS if c['status'] == 200]
    err = [c for c in CALLS if c['status'] != 200]
    summary['calls'] = {'total': len(CALLS), 'ok': len(ok), 'errors': len(err),
                        'searchPages': len([c for c in CALLS if c['path'] == '/search']),
                        'rateLimitFirst': REMAIN['first'], 'rateLimitLast': REMAIN['last'],
                        'rateLimitReset': REMAIN['reset'],
                        'elapsedSec': round(time.time() - started, 1),
                        'failures': [c for c in err]}
    print('\nAPI 호출 %d회(정상 %d · 실패 %d) · 남은 한도 %s → %s · %.1f초'
          % (len(CALLS), len(ok), len(err), REMAIN['first'], REMAIN['last'],
             time.time() - started))
    if report_path:
        os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as fp:
            json.dump(summary, fp, ensure_ascii=False, indent=1)
        print('보고서 → %s' % report_path)
    return 1 if err else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
