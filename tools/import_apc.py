#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APC 무료숙박권(APC=진향/臻享) 관측값 → ② 중올플 10곳에 날짜별 상태 주입.

원본: /workspace/data-sources/apc/availability.json
      (수집기 fetch_apc.py · API 구조는 같은 폴더 API-구조.md)

사용법 (저장소 루트에서):
    python3 tools/import_apc.py --dry
    python3 tools/import_apc.py
    python3 tools/import_apc.py --now "2026-11-17T15:00:00+09:00"   # 신선도 기준 시각

규칙
  · 상태 3구분: 가능(a) / 불가(n) / 미확인(행 없음 또는 last_checked_at 72시간 경과)
  · 72시간 규칙은 예약 사이트가 화면에 쓰는 것과 같다(DISPLAY_RESULT_FRESHNESS_MS).
    빌드 시점에 걸러서 저장하고, index.html 이 열릴 때 한 번 더 같은 규칙을 적용한다
    (오래된 파일을 나중에 열면 자동으로 「미확인」이 된다).
  · participation_status 가 not_participating 인 호텔(AKI 홍콩·뫼벤픽 칭다오)은
    날짜별 상태 대신 「미참여」로 표시한다.
  · ③ 국내 아코르(Stay Plus) 탭 데이터는 건드리지 않는다(Accor 공홈 직접 조회값 유지).
"""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = '/workspace/data-sources/apc/availability.json'
REL = 'apc/availability.json'

WINDOW_START = '2026-12-01'
WINDOW_END = '2027-11-30'
FRESH_HOURS = 72

# ② 중올플 10곳 ← APC public_id (API-구조.md 5장 매칭표)
MAP = {
    'c6480': 'public-93e12d415300',   # 소피텔 마카오 앳 폰테 16
    'cB5L5': 'public-92925991f976',   # AKI 홍콩 - 엠갤러리
    'c9933': 'public-a5c8ed3d9ac4',   # 소피텔 상하이 홍차오
    'cB628': 'public-5fe02dd7ad96',   # 소피텔 베이징 센트럴
    'c6318': 'public-78f75c38e7eb',   # 소피텔 광저우 선리치
    'c5554': 'public-4cb0b52085d9',   # 소피텔 항저우 웨스트레이크
    'c6179': 'public-5a4c62ae5728',   # 소피텔 난징 갤럭시 쑤닝
    'cC7G9': 'public-e204f247119e',   # 뫼벤픽 칭다오 5·4광장
    'c6156': 'public-adfa93cabadd',   # 소피텔 레전드 피플스 그랜드 시안
    'cC2G5': 'public-7243cf9cec7c',   # 풀만 충칭 시위에
}

# checked_at 은 관측 서버 현지시각(중국 표준시 +08:00)의 naive 문자열이다.
CHECK_TZ = dt.timezone(dt.timedelta(hours=8))


def parse_checked(s):
    return dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=CHECK_TZ)


def build(now):
    with open(SRC, encoding='utf-8') as fp:
        data = json.load(fp)
    by_pid = {h['public_id']: h for h in data['hotels']}
    cutoff = now - dt.timedelta(hours=FRESH_HOURS)
    out = {}
    for hid, pid in MAP.items():
        h = by_pid.get(pid)
        if not h:
            raise SystemExit('APC JSON 에 %s 가 없습니다.' % pid)
        part = (h['participation'].get('zhenxiang') or {})
        status = part.get('status') or 'unknown'
        apc, apc_t = {}, {}
        stale = 0
        newest = None
        for month, block in h['months'].items():
            for date, bt in block['days'].items():
                if not (WINDOW_START <= date <= WINDOW_END):
                    continue
                a = bt.get('zhenxiang')
                if not a or a.get('status') not in ('available', 'no_room'):
                    continue
                ts = parse_checked(a['checked_at'])
                if newest is None or ts > newest:
                    newest = ts
                if ts < cutoff:
                    stale += 1
                    continue
                if status != 'participating':
                    continue   # 미참여 호텔은 날짜별 상태 대신 「미참여」로 표시
                apc[date] = 'a' if a['status'] == 'available' else 'n'
                apc_t[date] = ts.isoformat()
        out[hid] = {
            'participation': status,
            'required_nights': part.get('required_nights', 1),
            'public_id': pid,
            'city_key': h['city_key'],
            'stale_dropped': stale,
            'newest': newest.isoformat() if newest else None,
            'apc': dict(sorted(apc.items())),
            'apc_t': dict(sorted(apc_t.items())),
        }
    return data, out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--now', default=None)
    a = ap.parse_args(argv)
    with open(SRC, encoding='utf-8') as fp:
        gen = json.load(fp)['generated_at']
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.fromisoformat(gen).replace(
        tzinfo=dt.timezone(dt.timedelta(hours=9)))
    data, res = build(now)
    print('기준 시각 %s · 72시간 컷 %s' % (now.isoformat(), (now - dt.timedelta(hours=FRESH_HOURS)).isoformat()))
    print('%-7s %-28s %-18s %4s %4s %4s' % ('id', '호텔', '참여', '가능', '불가', '제외'))
    tot = {'a': 0, 'n': 0}
    for hid, r in res.items():
        na = sum(1 for v in r['apc'].values() if v == 'a')
        nn = sum(1 for v in r['apc'].values() if v == 'n')
        tot['a'] += na
        tot['n'] += nn
        print('%-7s %-28s %-18s %4d %4d %4d' % (hid, MAP_NAME.get(hid, ''), r['participation'], na, nn,
                                                r['stale_dropped']))
    print('\nAPC 가능 %d칸 · 불가 %d칸 (미참여 2곳은 날짜 상태 없음)' % (tot['a'], tot['n']))
    if a.dry:
        return 0

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import master_db  # noqa: E402

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    used = set()
    for h in master['hotels']:
        if h['id'] in res:
            r = res[h['id']]
            h['accor'] = {
                'participation': r['participation'],
                'required_nights': r['required_nights'],
                'public_id': r['public_id'],
                'city_key': r['city_key'],
                'source': '예약 캘린더 관측(%s) · %s' % (REL, data['source']),
                'generated_at': data['generated_at'],
                'newest_checked': r['newest'],
                'fresh_hours': FRESH_HOURS,
            }
            h['accor_apc'] = r['apc']
            h['accor_apc_t'] = r['apc_t']
            used.add(h['id'])
    missing = set(res) - used
    if missing:
        raise SystemExit('master_db.json 에 없는 호텔 id: %s' % missing)
    master['sources'] = [s for s in master.get('sources', []) if not s.startswith('apc/')]
    master['sources'] += [REL, 'APC/fetch_apc.py', 'apc/API-구조.md']
    st = master_db.stats_of(master, master['flights'])
    master['counts'] = {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na',
                                           'stayplus', 'routes', 'deals')}
    tag = '2026-11-17 15:00 KST ② 중올플 APC 무료숙박 가능일(APC 72시간 규칙) 반영'
    ext = master.get('extended') or ''
    if 'APC 무료숙박 가능일' not in ext:
        master['extended'] = (ext + ' / ' + tag).strip(' /')
    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    print('master_db.json 갱신 — ② 중올플 10곳 accor_apc 주입 완료')
    return 0


MAP_NAME = {}


def _names():
    try:
        with open(MASTER, encoding='utf-8') as fp:
            m = json.load(fp)
        for h in m['hotels']:
            if h['id'] in MAP:
                MAP_NAME[h['id']] = h['name']
    except FileNotFoundError:
        pass


if __name__ == '__main__':
    _names()
    sys.exit(main(sys.argv[1:]))
