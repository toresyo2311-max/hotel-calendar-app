#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🌊 바다수온 탭 자료 수집 — 해수욕장 10곳의 최신 수온·파고와 최근 3일 수온 시계열을 모아
data/app/tab14_sea.json 을 만든다.

자료 출처
  · 해양수산부 국립해양조사원이 해수욕장 인근 해양관측 지점에서 관측한 실측값(수온·파고)이다.
    공공데이터포털이 배포하는 「해수욕장 정보」와 같은 원자료이며, 이 탭은 관측 지점 코드로
    최신값과 2시간 간격 시계열을 받아 쓴다.
  · 화면·자료·주석 어디에도 중간 유통 사이트 이름을 쓰지 않는다. 출처 표기는
    「국립해양조사원 해양관측 자료」 하나로 통일한다(한진님 지시).

자료 규칙
  · 받은 값만 쓴다. 관측이 비어 있는 시각은 null 로 두고 앞뒤 값으로 메우지 않는다.
  · 시계열은 2시간 간격(01·03·…·23시) 3일치 = 하루 12칸 × 3일 = 36칸이다.
    시간축은 원자료의 오늘 시간별 관측값과 대조해 확인한다(어긋나면 --strict 없이도 경고를 남긴다).
  · 최신 관측 시각은 원자료 표기(YY-MM-DD HH:MM)를 KST 로 읽어 ISO 로 적는다.

사용
  python3 tools/fetch_sea_temp.py            # 수집 → data/app/tab14_sea.json
  python3 tools/fetch_sea_temp.py --raw-dir data-sources/sea/raw   # 원자료도 함께 보관
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'app', 'tab14_sea.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0 Safari/537.36')
KST = dt.timezone(dt.timedelta(hours=9))

# 관측 지점 코드 — 국립해양조사원 해수욕장 관측 지점. 부산 3곳을 앞에 둔다(화면 상단 비교용).
BEACHES = [
    ('haeundae', '해운대해수욕장', '해운대', '부산', 'TW_0062'),
    ('songjeong', '송정해수욕장', '송정', '부산', 'TW_0090'),
    ('imrang', '임랑해수욕장', '임랑', '부산', 'TW_0092'),
    ('daecheon', '대천해수욕장', '대천', '충남', 'TW_0069'),
    ('jungmun', '중문해수욕장', '중문', '제주', 'TW_0075'),
    ('gyeongpodae', '경포대해수욕장', '경포대', '강원', 'TW_0089'),
    ('naksan', '낙산해수욕장', '낙산', '강원', 'TW_0091'),
    ('sokcho', '속초해수욕장', '속초', '강원', 'TW_0093'),
    ('mangsang', '망상해수욕장', '망상', '강원', 'TW_0094'),
    ('goraebul', '고래불해수욕장', '고래불', '경북', 'TW_0095'),
]

# 관측 지점 조회 엔드포인트 — 지점 코드로 최신값·3일 시계열·오늘 시간별값을 돌려준다.
BEACH_OBS_API = 'https://www.swimvirus.com/api/badaTemp'


def http_json(url, tries=3, timeout=40):
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA, 'Accept': 'application/json',
                'Accept-Language': 'ko-KR,ko;q=0.9'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            last = exc
            time.sleep(1.2 * (n + 1))
    raise RuntimeError('%s 를 읽지 못했습니다: %r' % (url, last))


def parse_obs_time(s):
    """원자료 표기(YY-MM-DD HH:MM)를 KST ISO 로. 두 자리 연도는 2000년대로 읽는다."""
    s = (s or '').strip()
    for fmt in ('%y-%m-%d %H:%M', '%Y-%m-%d %H:%M'):
        try:
            return dt.datetime.strptime(s, fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    raise RuntimeError('관측 시각을 읽지 못했습니다: %r' % s)


def build(code, payload):
    """원자료 하나를 탭 항목으로 바꾼다. 없는 값은 null 로 남긴다."""
    latest = payload.get('latest') or {}
    series3 = payload.get('suonDataSet') or []
    if not latest or len(series3) != 3:
        raise RuntimeError('%s: 최신값이나 3일 시계열이 없습니다' % code)

    when = parse_obs_time(latest.get('waterRecordTime'))
    today = when.date()
    days = [(today - dt.timedelta(days=2 - i)).isoformat() for i in range(3)]

    series, missing = [], 0
    for di, block in enumerate(series3):
        vals = (block or {}).get('values') or []
        for i in range(12):
            hour = 1 + 2 * i
            at = '%sT%02d:00' % (days[di], hour)
            v = vals[i] if i < len(vals) else None
            if v is None:
                missing += 1
                series.append([at, None])
            else:
                series.append([at, round(float(v), 2)])

    # 오늘 시간별 관측값으로 2시간 간격 시간축을 확인한다(값이 어긋나면 경고만 남기고 받은 값을 쓴다)
    warn = []
    hourly = {}
    for it in (payload.get('rawTodayItems') or []):
        try:
            t = parse_obs_time(it.get('obsrvnDt'))
            if t.date() == today and it.get('wtem') is not None:
                hourly[t.hour] = float(it['wtem'])
        except RuntimeError:
            continue
    mism = 0
    for at, v in series[24:]:
        h = int(at[11:13])
        if v is not None and h in hourly and abs(v - hourly[h]) > 0.06:
            mism += 1
    if mism:
        warn.append('%s: 오늘 시간별값과 %d칸 어긋남' % (code, mism))

    wv = latest.get('waterPago')
    return {
        'code': code,
        'name': (latest.get('waterName') or '').strip() or code,
        'short': '',
        'region': '',
        'latest': {
            't': when.strftime('%Y-%m-%dT%H:%M'),
            'wt': None if latest.get('waterTemp') is None else round(float(latest['waterTemp']), 2),
            'wv': None if wv is None else round(float(wv), 1),
        },
        'series': series,
    }, missing, warn


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw-dir', default='')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)

    out, warns, total_missing = [], [], 0
    for bid, name, short, region, code in BEACHES:
        payload = http_json(BEACH_OBS_API + '?obsCode=' + code)
        row, missing, w = build(code, payload)
        row['id'], row['short'], row['region'] = bid, short, region
        row['name'] = row['name'] if row['name'].endswith('해수욕장') else name
        out.append(row)
        total_missing += missing
        warns.extend(w)

        if args.raw_dir:
            day = (row['latest']['t'] or '')[:10] or dt.datetime.now(KST).date().isoformat()
            d = os.path.join(ROOT, args.raw_dir, day) if not os.path.isabs(args.raw_dir) \
                else os.path.join(args.raw_dir, day)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, code + '.json'), 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
        time.sleep(0.4)

    first = out[0]['series']
    days = [first[0][0][:10], first[12][0][:10], first[24][0][:10]]
    doc = {
        'schema': 1,
        'generated': dt.datetime.now(KST).replace(microsecond=0).isoformat(),
        'basis': ('국립해양조사원 해양관측 자료 — 해수욕장 인근 관측 지점의 실측 수온(℃)·파고(m). '
                  '수온 시계열은 2시간 간격 최근 3일(그저께·어제·오늘). 관측이 없는 시각은 비웁니다(추정 없음).'),
        'days': days,
        'counts': {'beaches': len(out), 'busan': sum(1 for r in out if r['region'] == '부산'),
                   'points': sum(len(r['series']) for r in out), 'missing': total_missing},
        'beaches': out,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')

    if not args.quiet:
        print('🌊 바다수온 — %d곳 · %d칸(빈칸 %d) · %s' % (len(out), doc['counts']['points'],
                                                     total_missing, os.path.relpath(OUT, ROOT)))
        print('   %-12s %-4s %8s %6s  %s' % ('해수욕장', '지역', '수온', '파고', '관측 시각'))
        for r in out:
            lt = r['latest']
            print('   %-12s %-4s %7s℃ %5sm  %s'
                  % (r['short'], r['region'],
                     '—' if lt['wt'] is None else ('%.2f' % lt['wt']),
                     '—' if lt['wv'] is None else ('%.1f' % lt['wv']),
                     lt['t'].replace('T', ' ')))
        for w in warns:
            print('   ! ' + w)
    return 0


if __name__ == '__main__':
    sys.exit(main())
