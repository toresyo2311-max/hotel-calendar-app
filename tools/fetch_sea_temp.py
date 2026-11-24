#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🌊 바다수온 탭 자료 수집 — 기상청 「전국 해수욕장 날씨 조회서비스」로 해수욕장 22곳의
최신 수온·파고·초단기예보와 최근 3일 수온 시계열을 모아 data/app/tab14_sea.json 을 만든다.

자료 출처
  · 기상청 전국 해수욕장 날씨 조회서비스(공공데이터포털)의 해수욕장별 관측·예보값이다.
    getTwBuoyBeach(수온) · getWhBuoyBeach(파고) · getUltraSrtFcstBeach(초단기예보 기온·하늘·강수).
  · 화면·자료·주석 어디에도 중간 유통 사이트 이름이나 주소를 쓰지 않는다.

자료 규칙
  · 받은 값만 쓴다. 관측이 비어 있는 시각은 null 로 두고 앞뒤 값으로 메우지 않는다.
  · 시계열은 2시간 간격(01·03·…·23시) 3일치 = 하루 12칸 × 3일 = 36칸(그저께·어제·오늘).
  · 응답 시각이 요청 시각과 1시간 이상 벌어지면 그 칸은 비운다(다른 시각 값을 끌어오지 않는다).

인증키(저장소에 평문 커밋 금지)
  · 환경변수 DATA_GO_KR_API_KEY → 인자 --key → 저장소 루트 .env 의 DATA_GO_KR_API_KEY 순서.
  · GitHub Actions 에서는 저장소 시크릿 DATA_GO_KR_API_KEY 를 환경변수로 받는다.

사용
  DATA_GO_KR_API_KEY=... python3 tools/fetch_sea_temp.py          # 수집 → data/app/tab14_sea.json
  python3 tools/fetch_sea_temp.py --full                          # 36칸 전부 다시 조회(기본은 빈칸·최근칸만)
  python3 tools/fetch_sea_temp.py --quiet
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'app', 'tab14_sea.json')
BASE = 'https://apis.data.go.kr/1360000/BeachInfoservice'
KST = dt.timezone(dt.timedelta(hours=9))
STEP_H = 2          # 시계열 간격(시간)
SLOTS_PER_DAY = 12  # 01·03·…·23시

# 수집 대상 22곳 — 부산 7곳을 앞에 두고(화면 상단 비교 카드) 그 뒤는 지역 순서(강원→경북→충남→전북→
# 전남→경남→제주). beach_num 은 기상청 전국 해수욕장 날씨 조회서비스의 해변코드다.
BEACHES = [
    # (id, name, short, region, beach_num)
    ('haeundae', '해운대해수욕장', '해운대', '부산', '304'),
    ('songjeong', '송정해수욕장', '송정', '부산', '305'),
    ('gwangalli', '광안리해수욕장', '광안리', '부산', '306'),
    ('imrang', '임랑해수욕장', '임랑', '부산', '307'),
    ('dadaepo', '다대포해수욕장', '다대포', '부산', '308'),
    ('ilgwang', '일광해수욕장', '일광', '부산', '309'),
    ('songdo', '송도해수욕장', '송도', '부산', '268'),
    ('gyeongpodae', '경포해수욕장', '경포대', '강원', '176'),
    ('naksan', '낙산해수욕장', '낙산', '강원', '262'),
    ('sokcho', '속초해수욕장', '속초', '강원', '201'),
    ('mangsang', '망상해수욕장', '망상', '강원', '198'),
    ('hajodae', '하조대해수욕장', '하조대', '강원', '249'),
    ('goraebul', '고래불해수욕장', '고래불', '경북', '288'),
    ('yeongildae', '영일대해수욕장', '영일대', '경북', '271'),
    ('daecheon', '대천해수욕장', '대천', '충남', '41'),
    ('manripo', '만리포해수욕장', '만리포', '충남', '70'),
    ('byeonsan', '변산해수욕장', '변산', '전북', '97'),
    ('manseongri', '만성리검은모래해수욕장', '만성리', '전남', '104'),
    ('hakdong', '학동흑진주몽돌해변', '학동', '경남', '322'),
    ('sangju', '상주은모래비치', '상주', '경남', '327'),
    ('jungmun', '중문·색달해수욕장', '중문', '제주', '347'),
    ('hyeopjae', '협재해수욕장', '협재', '제주', '346'),
]

SKY = {'1': '맑음', '3': '구름많음', '4': '흐림'}
PTY = {'0': '강수 없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기', '5': '빗방울',
       '6': '빗방울·눈날림', '7': '눈날림'}


def load_key(explicit=''):
    """환경변수 → 인자 → 저장소 .env 순서로 인증키를 찾는다(코드에 키를 적지 않는다)."""
    if explicit:
        return explicit.strip()
    for var in ('DATA_GO_KR_API_KEY', 'DATA_GO_KR_SERVICE_KEY'):
        v = os.environ.get(var, '').strip()
        if v:
            return v
    env = os.path.join(ROOT, '.env')
    if os.path.exists(env):
        with open(env, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('DATA_GO_KR_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise SystemExit('인증키가 없습니다 — DATA_GO_KR_API_KEY 환경변수나 --key 로 넘겨 주세요.')


def api(key, path, rows=10, tries=3, timeout=25, **params):
    q = '&'.join('%s=%s' % (k, v) for k, v in params.items())
    url = '%s/%s?serviceKey=%s&numOfRows=%s&pageNo=1&dataType=JSON&%s' % (
        BASE, path, key, rows, q)
    last = None
    for n in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                d = json.loads(r.read().decode('utf-8'))
            body = d['response']['body']
            items = (body.get('items') or {}).get('item') or []
            if isinstance(items, dict):
                items = [items]
            return items
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError) as exc:
            last = exc
            time.sleep(0.8 * (n + 1))
    raise RuntimeError('%s 호출 실패: %r' % (path, last))


def num(v):
    """'16.2' → 16.2. 빈 값·'-'·':' 은 None."""
    s = ('' if v is None else str(v)).strip()
    if s in ('', '-', ':', 'null', 'None'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_tw(key, code, when):
    """when(KST) 시각의 수온. 응답 시각이 1시간 넘게 벌어지면 None."""
    items = api(key, 'getTwBuoyBeach', beach_num=code, searchTime=when.strftime('%Y%m%d%H%M'))
    if not items:
        return None, None
    it = items[0]
    v = num(it.get('tw'))
    tm = (it.get('tm') or '').strip()
    if v is None or not tm:
        return None, tm or None
    try:
        got = dt.datetime.strptime(tm, '%Y%m%d%H%M').replace(tzinfo=KST)
    except ValueError:
        return None, tm
    if abs((got - when).total_seconds()) > 3600:
        return None, tm
    return round(v, 2), tm


def fetch_wh(key, code, when):
    """when(KST) 시각의 파고."""
    items = api(key, 'getWhBuoyBeach', beach_num=code, searchTime=when.strftime('%Y%m%d%H'))
    if not items:
        return None, None
    it = items[0]
    v = num(it.get('wh'))
    tm = (it.get('tm') or '').strip()
    if v is None or not tm:
        return None, tm or None
    try:
        got = dt.datetime.strptime(tm, '%Y%m%d%H%M').replace(tzinfo=KST)
    except ValueError:
        return None, tm
    if abs((got - when).total_seconds()) > 3600:
        return None, tm
    return round(v, 1), tm


def fetch_ultra(key, code, now):
    """초단기예보 — 가장 가까운 예보 시각의 기온·하늘·강수·습도·풍속."""
    base = now - dt.timedelta(minutes=45)
    base = base.replace(minute=30, second=0, microsecond=0)
    items = []
    for i in range(4):                      # 발표 전이면 한 시간씩 앞으로 물러난다
        b = base - dt.timedelta(hours=i)
        try:
            items = api(key, 'getUltraSrtFcstBeach', rows=120, beach_num=code,
                        base_date=b.strftime('%Y%m%d'), base_time=b.strftime('%H%M'))
        except RuntimeError:
            items = []
        if items:
            break
        time.sleep(0.3)
    if not items:
        return None
    groups = {}
    for it in items:
        g = '%s %s' % (it.get('fcstDate') or '', it.get('fcstTime') or '')
        groups.setdefault(g, {})[it.get('category')] = it.get('fcstValue')
    if not groups:
        return None
    gk = sorted(groups)[0]
    c = groups[gk]
    fd, ft = gk.split(' ', 1)
    when = '%s-%s-%sT%s:%s' % (fd[0:4], fd[4:6], fd[6:8], ft[0:2], ft[2:4]) if fd and ft else None
    out = {
        't': when,
        'temp': num(c.get('T1H')),
        'sky': SKY.get(str(c.get('SKY') or '').strip()),
        'pty': PTY.get(str(c.get('PTY') or '').strip()),
        'reh': num(c.get('REH')),
        'wsd': num(c.get('WSD')),
    }
    if all(out[k] is None for k in ('temp', 'sky', 'pty', 'reh', 'wsd')):
        return None
    return out


def slots_for(now):
    """그저께·어제·오늘의 01·03·…·23시 36칸."""
    days = [(now.date() - dt.timedelta(days=2 - i)).isoformat() for i in range(3)]
    out = []
    for d in days:
        for i in range(SLOTS_PER_DAY):
            hh = 1 + STEP_H * i
            out.append(dt.datetime.strptime('%s %02d' % (d, hh), '%Y-%m-%d %H'
                                            ).replace(tzinfo=KST))
    return out, days


def load_cache():
    """이전 tab14_sea.json 의 시계열 — 지난 칸은 다시 부르지 않는다(호출 한도 절약)."""
    if not os.path.exists(OUT):
        return {}
    try:
        with open(OUT, encoding='utf-8') as f:
            doc = json.load(f)
    except (ValueError, OSError):
        return {}
    cache = {}
    for b in doc.get('beaches') or []:
        code = str(b.get('code') or '')
        for p in b.get('series') or []:
            if isinstance(p, list) and len(p) == 2 and p[1] is not None:
                cache[(code, p[0])] = p[1]
    return cache


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', default='')
    ap.add_argument('--beaches', default='', help='쉼표로 해변코드나 id 를 골라 받는다(검증용)')
    ap.add_argument('--full', action='store_true', help='36칸을 전부 다시 조회한다')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)

    key = load_key(args.key)
    now = dt.datetime.now(KST).replace(microsecond=0)
    slots, days = slots_for(now)
    cache = {} if args.full else load_cache()

    picks = [s.strip() for s in args.beaches.split(',') if s.strip()]
    targets = [b for b in BEACHES if not picks or b[4] in picks or b[0] in picks]
    fresh_after = now - dt.timedelta(hours=3)   # 최근 3시간 칸은 값이 더 올라올 수 있어 다시 본다

    def work(beach):
        bid, name, short, region, code = beach
        row = {'id': bid, 'code': code, 'name': name, 'short': short, 'region': region}
        # --- 최신 수온·파고
        tw, tm = fetch_tw(key, code, now.replace(second=0))
        wh, _ = fetch_wh(key, code, now)
        row['latest'] = {
            't': ('%s-%s-%sT%s:%s' % (tm[0:4], tm[4:6], tm[6:8], tm[8:10], tm[10:12])) if tm else None,
            'wt': tw, 'wv': wh,
        }
        # --- 3일 시계열(수온) — 빈칸·최근칸만 조회
        series, missing = [], 0
        for s in slots:
            iso = s.strftime('%Y-%m-%dT%H:%M')
            v = None
            if s <= now:
                cached = cache.get((code, iso))
                if cached is not None and s < fresh_after:
                    v = cached
                else:
                    v, _tm = fetch_tw(key, code, s)
                    if v is None and cached is not None:
                        v = cached                      # 이미 받아 둔 값은 지우지 않는다
            if v is None:
                missing += 1
            series.append([iso, v])
        row['series'] = series
        # --- 초단기예보
        row['forecast'] = fetch_ultra(key, code, now)
        return row, missing

    rows, warns, missing_total = [], [], 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for row, missing in ex.map(work, targets):
            rows.append(row)
            missing_total += missing
            if row['latest']['wt'] is None:
                warns.append("%s: 최신 수온 없음" % row['short'])
            if row['latest']['wv'] is None:
                warns.append("%s: 최신 파고 없음" % row['short'])

    if not rows:
        raise SystemExit('받은 해수욕장이 없습니다.')

    first = rows[0]['series']
    # 캐시에 있던 다른 해수욕장(부분 실행)은 기존 자료를 그대로 살린다
    if picks:
        try:
            with open(OUT, encoding='utf-8') as f:
                old = json.load(f)
            kept = [b for b in (old.get('beaches') or [])
                    if str(b.get('code')) not in {r['code'] for r in rows}]
            if kept:
                rows = kept + rows
                rows.sort(key=lambda r: next((i for i, b in enumerate(BEACHES)
                                              if b[4] == str(r['code'])), 99))
        except (OSError, ValueError):
            pass

    regions = {}
    for r in rows:
        regions[r['region']] = regions.get(r['region'], 0) + 1
    doc = {
        'schema': 2,
        'generated': now.isoformat(),
        'source': '기상청 전국 해수욕장 날씨 조회서비스',
        'basis': ('기상청 전국 해수욕장 날씨 조회서비스 — 해수욕장별 최신 수온(℃)·파고(m)와 초단기예보(기온·하늘·강수), '
                  '수온 2시간 간격 최근 3일(그저께·어제·오늘) 시계열. 값이 없는 칸은 비웁니다(추정·보간 없음).'),
        'days': days,
        'counts': {'beaches': len(rows), 'busan': regions.get('부산', 0),
                   'regions': regions, 'points': sum(len(r['series']) for r in rows),
                   'missing': missing_total},
        'beaches': rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # 값이 하나도 안 바뀌었으면 파일을 그대로 둔다(생성 시각만 바뀤 재커밋을 막는다).
    old = None
    try:
        with open(OUT, encoding='utf-8') as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = None
    if old:
        a = {k: v for k, v in old.items() if k != 'generated'}
        b = {k: v for k, v in doc.items() if k != 'generated'}
        if a == b:
            if not args.quiet:
                print('🌊 바다수온 — 바뀐 값 없음(자료 그대로) · %s' % os.path.relpath(OUT, ROOT))
            return 0
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    os.replace(tmp, OUT)
    _ = first

    if not args.quiet:
        print('🌊 바다수온 — %d곳 · %d칸(빈칸 %d) · %s' % (len(rows), doc['counts']['points'],
                                                     missing_total, os.path.relpath(OUT, ROOT)))
        print('   %-8s %-4s %8s %6s %9s  %s' % ('해수욕장', '지역', '수온', '파고', '기온', '관측'))
        for r in rows:
            lt, fc = r['latest'], r['forecast'] or {}
            print('   %-8s %-4s %7s℃ %5sm %8s℃  %s'
                  % (r['short'], r['region'],
                     '—' if lt['wt'] is None else ('%.2f' % lt['wt']),
                     '—' if lt['wv'] is None else ('%.1f' % lt['wv']),
                     '—' if fc.get('temp') is None else ('%.1f' % fc['temp']),
                     (lt['t'] or '—').replace('T', ' ')))
        for w in warns:
            print('   ! ' + w)
    return 0


if __name__ == '__main__':
    sys.exit(main())
