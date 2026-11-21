#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑦ 마일리지(부산) — 보너스 좌석 수집본을 앱 자료로 옮기고, 전일 대비 차이를 낸다.

원칙
  · 원천(항공사 공개 보너스 좌석 현황)이 주지 않는 값은 만들지 않는다.
    → 좌석 수량 · 수수료 금액 · 기재 · 편명은 자료에 넣지 않는다.
  · 등급 배지만 옮긴다: E 일반석 보너스=1, P 프레스티지 보너스=2, U 프레스티지 승급=4, F 일등석=8
  · 조회하지 못한 날은 '미수집'으로 비워 두고, 원천 제공 범위(앞으로 360일) 밖은 '미제공'이다.

쓰는 법
  python3 tools/collect_mileage.py --build                 # 수집본들을 모아 앱 자료·스냅샷·차이 생성
  python3 tools/collect_mileage.py --build --quiet
  python3 tools/collect_mileage.py --status                # 지금 무엇이 있는지 요약
  python3 tools/collect_mileage.py --fetch --route NRT --month 2026-12
                                                           # 원천 직접 조회(차단되는 환경이면 그대로 알린다)

수집본 형식 (data/mileage/captures/<YYYY-MM-DD>.json)
  {"collectedAt":"2026-11-22T07:40:00+09:00",
   "observed":"2026-11-22 01:30",                  # 원천이 화면에 적어 둔 기준 시각
   "rows":[{"code":"NRT","dir":0,"month":"2026-12","cells":"1:7,2:7,3:1,..."}]}
  dir 0 = 부산(PUS)→현지, 1 = 현지→부산(PUS)
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_MILEAGE = os.path.join(ROOT, 'data', 'mileage')
CAPTURES = os.path.join(DATA_MILEAGE, 'captures')
SNAPSHOTS = os.path.join(DATA_MILEAGE, 'snapshots')
OUT = os.path.join(ROOT, 'data', 'app', 'tab8_mileage.json')

KST = datetime.timezone(datetime.timedelta(hours=9))
SOURCE_URL = 'https://www.koreanair.com/booking/book-and-manage/award-seat-availability'
CHART_URL = 'https://www.koreanair.com/contents/skypass/use-miles'

# 노선 — 부산/김해(PUS)를 드나드는 노선. region 은 공제표 구역 키.
ROUTES = [
    ('NRT', '도쿄/나리타', 'jp_cn_ne', 0),
    ('KIX', '오사카', 'jp_cn_ne', 1),
    ('FUK', '후쿠오카', 'jp_cn_ne', 1),
    ('NGO', '나고야', 'jp_cn_ne', 1),
    ('CTS', '삿포로', 'jp_cn_ne', 0),
    ('TPE', '타이베이', 'jp_cn_ne', 1),
    ('HKG', '홍콩', 'jp_cn_ne', 0),
    ('PVG', '상하이/푸둥', 'jp_cn_ne', 0),
    ('TAO', '칭다오', 'jp_cn_ne', 1),
    ('BKK', '방콕', 'sea_guam', 1),
    ('SIN', '싱가포르', 'sea_guam', 0),
    ('HAN', '하노이', 'sea_guam', 0),
    ('SGN', '호찌민', 'sea_guam', 0),
    ('DAD', '다낭', 'sea_guam', 0),
]
ROUTE_MAP = {code: (city, region, direct) for code, city, region, direct in ROUTES}

# 대한항공 스카이패스 공제표(편도, 마일). 공식 공제표 값 — 계산에만 쓴다.
# [구역키, 이름, 일반 평수기, 일반 성수기, 프레스티지 평수기, 프레스티지 성수기, 일등 평수기, 일등 성수기]
CHART = [
    ['kr', '국내선', 5000, 7500, 6000, 9000, None, None],
    ['jp_cn_ne', '일본·중국·동북아', 15000, 22500, 22500, 32500, 32500, 47500],
    ['sea_guam', '동남아·괌', 20000, 30000, 35000, 52500, 45000, 67500],
    ['sw_asia', '서남아', 25000, 37500, 45000, 67500, 57500, 87500],
    ['us_eu_me_oc', '미주·유럽·중동·대양주', 35000, 52500, 62500, 92500, 80000, 120000],
]
BIT = {'E': 1, 'P': 2, 'U': 4, 'F': 8}


def log(*a):
    print(*a, flush=True)


def read_json(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def write_json(path, obj, compact=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        if compact:
            fp.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
        else:
            json.dump(obj, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, path)


def parse_cells(month, spec):
    """'1:7,2:7,3:1' → {'2026-12-01': 7, ...}  — 값은 0~15(비트)만 받는다."""
    out = {}
    for part in str(spec or '').split(','):
        part = part.strip()
        if not part:
            continue
        day, _, val = part.partition(':')
        day = int(day)
        val = int(val)
        if not 1 <= day <= 31:
            raise SystemExit('%s: 날짜 %r 가 1~31 밖입니다' % (month, day))
        if val & ~31:
            raise SystemExit('%s %d일: 등급 비트 %r 가 0~31 밖입니다' % (month, day, val))
        out['%s-%02d' % (month, day)] = val
    return out


def load_captures():
    """수집본 파일들을 날짜 순으로 읽어 (파일, 자료) 목록으로."""
    if not os.path.isdir(CAPTURES):
        return []
    files = sorted(f for f in os.listdir(CAPTURES)
                   if f.endswith('.json') and f[:4].isdigit())
    out = []
    for name in files:
        path = os.path.join(CAPTURES, name)
        try:
            out.append((name[:-5], read_json(path)))
        except Exception as exc:                  # noqa: BLE001
            log('  ! %s 읽지 못함: %s' % (name, exc))
    return out


def flatten(caps):
    """수집본들 → ({(code, dir, date): (bit, 관측일)}, {(code, dir, month): 메모}) · 나중 파일이 이긴다."""
    cells = {}
    notes = {}
    for stamp, cap in caps:
        for row in cap.get('rows') or []:
            code = row.get('code')
            if code not in ROUTE_MAP:
                log('  ! 모르는 노선 %r — 건너뜁니다' % code)
                continue
            direction = int(row.get('dir') or 0)
            month = row.get('month') or ''
            if len(month) != 7:
                log('  ! %s: 탑승월 %r 형식이 아닙니다' % (code, month))
                continue
            if row.get('note'):
                notes[(code, direction, month)] = row['note']
                continue
            for date, bit in parse_cells(month, row.get('cells')).items():
                cells[(code, direction, date)] = (bit, stamp)
    return cells, notes


def snapshot_of(stamp, cells):
    return {'stamp': stamp, 'cells': {'%s|%d|%s' % k: v[0] for k, v in cells.items()}}


def diff_of(prev, cur):
    """이전 스냅샷 대비 새로 열린 칸(new)·사라진 칸(gone)."""
    new, gone = [], []
    p = (prev or {}).get('cells') or {}
    for key, bit in cur.items():
        code, direction, date = key.split('|')
        before = p.get(key, 0)
        added = bit & ~before
        removed = before & ~bit
        for name, val, bucket in (('E', 1, added), ('P', 2, added), ('U', 4, added),
                                  ('E', 1, removed), ('P', 2, removed), ('U', 4, removed)):
            if val & bucket:
                row = [code, int(direction), date, BIT[name]]
                (new if bucket is added else gone).append(row)
    new.sort(key=lambda r: (r[2], r[0]))
    gone.sort(key=lambda r: (r[2], r[0]))
    return new, gone


def months_range(caps):
    m = set()
    for _stamp, cap in caps:
        for row in cap.get('rows') or []:
            if row.get('month'):
                m.add(row['month'])
    return sorted(m)


def build(args):
    today = datetime.datetime.now(KST)
    stamp_today = today.strftime('%Y-%m-%d')
    caps = load_captures()
    if not caps:
        raise SystemExit('수집본이 없습니다 — %s 에 먼저 수집본을 두세요.' % CAPTURES)

    cells, notes = flatten(caps)
    stamps = sorted({s for s, _ in caps})
    latest = stamps[-1]
    cur_cap = [c for s, c in caps if s == latest][-1]

    # 스냅샷 저장(오늘 기준) + 직전 스냅샷과 비교
    os.makedirs(SNAPSHOTS, exist_ok=True)
    cur_snap = snapshot_of(latest, cells)
    prev_snap = None
    prev_files = sorted(f for f in os.listdir(SNAPSHOTS) if f.endswith('.json') and f[:-5] < latest)
    if prev_files:
        prev_snap = read_json(os.path.join(SNAPSHOTS, prev_files[-1]))
    write_json(os.path.join(SNAPSHOTS, latest + '.json'), cur_snap)
    if prev_snap is None:
        new, gone = [], []          # 첫 수집 — 비교할 이전 스냅샷이 없다(전부 '새 좌석'으로 세지 않는다)
    else:
        new, gone = diff_of(prev_snap, cur_snap['cells'])

    # 앱 자료
    rows = []
    per_route_dir = {}
    miss_dates = 0
    window_end = (today.date() + datetime.timedelta(days=359)).isoformat()
    months = months_range(caps)
    for (code, direction, date), (bit, _stamp) in sorted(cells.items(), key=lambda kv: (kv[0][2], kv[0][0])):
        rows.append([code, direction, date, bit])
        per_route_dir[(code, direction)] = per_route_dir.get((code, direction), 0) + 1
    open_cells = sum(1 for r in rows if r[3] and not (r[3] & 16))   # 16 = 운항편 없음(좌석 아님)
    for month in months:
        y, m = int(month[:4]), int(month[5:7])
        last = (datetime.date(y + (m == 12), 1 if m == 12 else m + 1, 1) - datetime.timedelta(days=1)).day
        for code, _city, _region, _direct in ROUTES:
            for direction in (0, 1):
                if (code, direction, month) in notes:
                    continue                     # 원천이 조회를 거절한 달 — 미수집으로 세지 않고 따로 적는다
                for day in range(1, last + 1):
                    date = '%s-%02d' % (month, day)
                    if date > window_end:
                        continue
                    if (code, direction, date) not in cells:
                        miss_dates += 1

    payload = {
        'schema': 'mileage/1',
        'observedAt': cur_cap.get('observed') or '',
        'observedLabel': (cur_cap.get('observed') or '').strip() or latest,
        'collectedAt': cur_cap.get('collectedAt') or today.isoformat(),
        'sourceLabel': '대한항공 공개 보너스 좌석 현황',
        'sourceUrl': SOURCE_URL,
        'chartUrl': CHART_URL,
        'windowEnd': window_end,
        'windowNote': '앞으로 360일',
        'months': months,
        'today': stamp_today,
        'routes': [{'code': c, 'city': city, 'region': region, 'direct': direct}
                   for c, city, region, direct in ROUTES],
        'cells': rows,
        'chart': CHART,
        'monthNotes': [[k[0], k[1], k[2], v] for k, v in sorted(notes.items(), key=lambda kv: (kv[0][2], kv[0][0]))],
        'coverage': [{'code': c, 'months': sorted({k[2][:7] for k in cells if k[0] == c and k[1] == 0}),
                      'noted': sorted({k[2] for k in notes if k[0] == c and k[1] == 0})}
                     for c, _city, _region, _direct in ROUTES],
        'newSeats': new,
        'goneSeats': gone,
        'hasPrev': bool(prev_snap),
        'prevLabel': (prev_snap or {}).get('stamp') or '',
        'counts': {
            'routes': sum(1 for c in ROUTES if any(k[0] == c[0] for k in cells)),
            'routeDirs': len(per_route_dir),
            'cells': len(rows),
            'open': open_cells,
            'newToday': len(new),
            'goneToday': len(gone),
            'miss': miss_dates,
            'noted': len(notes),
            'months': len(months),
        },
    }
    write_json(OUT, payload)
    if not args.quiet:
        c = payload['counts']
        log('노선 %d · 수집칸 %d(좌석 있음 %d) · 새로 열림 %d · 사라짐 %d · 미수집 %d · 원천 조회 불가 %d달'
            % (c['routes'], c['cells'], c['open'], c['newToday'], c['goneToday'], c['miss'], c['noted']))
        log('탑승월 %s ~ %s · 원천 기준 %s · 수집 %s'
            % (months[0] if months else '-', months[-1] if months else '-',
               payload['observedLabel'], latest))
        log('→ %s' % os.path.relpath(OUT, ROOT))
        log('→ %s' % os.path.relpath(os.path.join(SNAPSHOTS, latest + '.json'), ROOT))
    return 0


def status(args):
    caps = load_captures()
    if not caps:
        log('수집본 없음 (%s)' % CAPTURES)
        return 0
    cells = flatten(caps)
    log('수집본 %d개 · 칸 %d개 · 노선 %s'
        % (len(caps), len(cells), ', '.join(sorted({k[0] for k in cells}))))
    for stamp, cap in caps:
        log('  %s · row %d · 원천 기준 %s'
            % (stamp, len(cap.get('rows') or []), cap.get('observed') or '-'))
    return 0


def fetch(args):
    """원천 직접 조회 — 이 환경(데이터센터 IP)에서는 항공사가 막는 경우가 많다.

    막히면 그 사실을 그대로 알리고, 값을 지어내지 않는다. 브라우저로 본 화면을
    수집본에 옮겨 적는 편이 현재로선 확실하다(docs 참조).
    """
    body = json.dumps({'depAirportCode': args.route, 'arrAirportCode': 'PUS' if args.dir else args.route,
                       'month': args.month.replace('-', '')}).encode()
    req = urllib.request.Request(
        'https://www.koreanair.com/api/hmp/bonusSeatView/bonusSeatView', data=body,
        headers={'Content-Type': 'application/json',
                 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                               '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                 'Referer': SOURCE_URL, 'Accept-Language': 'ko-KR,ko;q=0.9'})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read().decode('utf-8', 'replace')
        log('응답 %d bytes' % len(data))
        log(data[:500])
    except urllib.error.HTTPError as exc:
        log('원천이 거절했습니다 — HTTP %s (%s). 값을 만들지 않고 멈춥니다.' % (exc.code, exc.reason))
        return 2
    except Exception as exc:                      # noqa: BLE001
        log('원천에 닿지 못했습니다 — %r. 값을 만들지 않고 멈춥니다.' % (exc,))
        return 2
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description='⑦ 마일리지(부산) 수집본 → 앱 자료')
    ap.add_argument('--build', action='store_true', help='수집본을 모아 앱 자료·스냅샷·차이 생성')
    ap.add_argument('--status', action='store_true', help='지금 있는 수집본 요약')
    ap.add_argument('--fetch', action='store_true', help='원천 직접 조회(차단되면 그대로 알림)')
    ap.add_argument('--route', default='NRT')
    ap.add_argument('--dir', type=int, default=0)
    ap.add_argument('--month', default='2026-12')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)
    if args.fetch:
        return fetch(args)
    if args.status:
        return status(args)
    return build(args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
