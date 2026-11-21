#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🌲 휴양림 탭 데이터(tab7_forest.json) 생성.

숲나들e(foresttrip.go.kr)의 월별 예약현황을 모아 둔 스냅샷(status.json·changes.json)을
이 앱이 쓰는 압축 구조($t/$r 표 + 71자 상태 문자열)로 옮긴다. 값은 하나도 만들지 않고
스냅샷에 있는 상태 코드만 그대로 옮긴다(추정·보간 없음).

    python3 tools/build_forest_data.py --src /path/to/snapshot_dir
    python3 tools/build_forest_data.py --src ... --check     # 쓰지 않고 규모만 확인

스냅샷 폴더에는 status.json(전체)·changes.json(직전 수집 대비 새로 빈 자리)이 있다.
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'app', 'tab7_forest.json')
REGION_ORDER = ['부산/경남', '대구/경북', '울산', '강원', '서울/인천/경기',
                '충북', '대전/충남', '전북', '전남/광주', '제주']

# 숲나들e 상태 코드 → 앱이 쓰는 문자(그대로 저장, 앱에서 해석)
STATUS = 'AFCPR'          # A 예약가능 / F 완료 / C 휴무 / P 추첨·우선예약 / R 공사·점검
DIGITS = '123456789'      # 대기 1~9


def group_of(kind, cls):
    """객실유형 묶음 — 필터가 6~9개로 끝나게 큰 갈래만 나눈다."""
    c = cls or ''
    if kind == '02':
        if '오토캠핑' in c:
            return '오토캠핑장'
        if '카라반' in c or '캐라반' in c:
            return '카라반'
        if '글램핑' in c:
            return '글램핑'
        if '데크' in c:
            return '야영데크'
        return '야영장'
    if '숲속의집' in c or '산속의집' in c:
        return '숲속의집'
    if '연립' in c:
        return '연립동'
    if '휴양관' in c or '수련' in c or '교육관' in c:
        return '휴양관'
    return '숙소 기타'


def open_text(pol):
    """예약 오픈 정책 값 → 사람이 읽는 문장. 값을 해석하지 않고 표기만 바꾼다."""
    if not pol:
        return None
    cyc, day, tm = pol.get('cycle'), str(pol.get('day') or ''), str(pol.get('time') or '')
    when = None
    if cyc == 'WEEK' and day.isdigit():
        when = '매주 ' + '일월화수목금토'[int(day) % 7] + '요일'
    elif cyc == 'MON' and day.isdigit():
        when = '매월 ' + day + '일'
    elif cyc == 'DAY' and day.isdigit():
        when = '매일'
    if not when or len(tm) != 4 or not tm.isdigit():
        return None
    return when + ' ' + tm[:2] + ':' + tm[2:] + ' 오픈'


def rate_of(booking, key):
    """월별 예약률 → 수집 기간 합산. 표본 10일 미만이면 표시하지 않는다(null)."""
    num = den = 0
    for m in (booking or {}).values():
        v = m.get(key) or [0, 0]
        num += v[0]
        den += v[1]
    if den < 10:
        return None
    return int(round(num * 100.0 / den))


def build(src):
    with open(os.path.join(src, 'status.json'), encoding='utf-8') as fp:
        st = json.load(fp)
    chg_path = os.path.join(src, 'changes.json')
    changes = []
    if os.path.exists(chg_path):
        with open(chg_path, encoding='utf-8') as fp:
            changes = json.load(fp).get('items') or []

    start = st['start']
    base = datetime.date(int(start[:4]), int(start[4:6]), int(start[6:]))
    days = int(st['days'])
    at = st.get('generatedAt') or ''
    try:
        kst = datetime.datetime.strptime(at, '%Y-%m-%dT%H:%M:%S.%fZ') + datetime.timedelta(hours=9)
        at_txt = kst.strftime('%Y-%m-%d %H:%M')
    except Exception:                     # noqa: BLE001 - 표기용이라 실패하면 원문
        at_txt = at

    forests = []
    f_idx, g_idx = {}, {}
    for f in st['forests']:
        goods = []
        for gi, g in enumerate(f.get('goods') or []):
            g_idx[(f['id'], g['id'])] = gi
            row = {
                'k': g.get('kind') or '01',
                'c': g.get('cls') or '',
                'g': group_of(g.get('kind'), g.get('cls')),
                'n': g.get('name') or '',
                'cap': g.get('cap'),
                'ar': g.get('area') or '',
                'f': g.get('flags') or '',
                'm': g.get('maxNights'),
                'p': g.get('pr') or [],
                's': g['s'],
            }
            goods.append(row)
        f_idx[f['id']] = len(forests)
        forests.append({
            'id': f['id'],
            'name': f['name'],
            'type': f.get('type') or '',
            'sido': f.get('sidoName') or '',
            'gug': f.get('sigungu') or '',
            'lat': f.get('lat'),
            'lng': f.get('lng'),
            'addr': f.get('addr') or '',
            'tel': f.get('tel') or '',
            'ci': f.get('checkin') or '',
            'co': f.get('checkout') or '',
            'op': open_text(f.get('policy')),
            'rw': rate_of(f.get('booking'), 'we'),
            'rd': rate_of(f.get('booking'), 'wd'),
            'goods': goods,
        })

    # 새로 빈 자리 — 마지막 수집에서 직전 수집 대비 완료·대기 → 예약가능으로 바뀐 칸만.
    # changes.json 에는 그 이전 수집분도 함께 남아 있으므로 마지막 수집 시각(at)과 같은 것만 고른다.
    new = [[0, 0]] * 0
    for it in changes:
        if at and it.get('at') != at:
            continue
        fi = f_idx.get(it.get('forest'))
        gi = g_idx.get((it.get('forest'), it.get('goods')))
        dt = it.get('date') or ''
        if fi is None or gi is None or len(dt) != 8:
            continue
        try:
            di = (datetime.date(int(dt[:4]), int(dt[4:6]), int(dt[6:])) - base).days
        except ValueError:
            continue
        if 0 <= di < days:
            new.append([fi, gi, di])

    # 권역은 부산·경남을 앞에 두고 나머지는 인구·접근성 순서(고정 목록), 없는 권역은 빼지 않는다
    sidos = []
    for s in REGION_ORDER:
        if any(f['sido'] == s for f in forests):
            sidos.append(s)
    for f in forests:
        if f['sido'] not in sidos:
            sidos.append(f['sido'])

    goods_n = sum(len(f['goods']) for f in forests)
    avail = sum(g['s'].count('A') for f in forests for g in f['goods'])
    return {
        'meta': {
            'at': at_txt,
            'start': '%s-%s-%s' % (start[:4], start[4:6], start[6:]),
            'days': days,
            'forests': len(forests),
            'goods': goods_n,
            'avail': avail,
            'new': len(new),
        },
        'sidos': sidos,
        'forests': forests,
        'new': new,
        'gt': ['k', 'c', 'g', 'n', 'cap', 'ar', 'f', 'm', 'p', 's'],
    }


def to_table(out):
    """goods 배열을 $t/$r 표로 바꿔 키 반복을 없앤다(앱의 hcDecode 가 되돌린다)."""
    cols = out.pop('gt')
    for f in out['forests']:
        f['goods'] = {'$t': cols, '$r': [[g[c] for c in cols] for g in f['goods']]}
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.environ.get('FOREST_SNAPSHOT', ''))
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    if not a.src:
        raise SystemExit('--src 또는 FOREST_SNAPSHOT 로 스냅샷 폴더를 지정하세요')
    data = to_table(build(a.src))
    body = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    m = data['meta']
    print('휴양림 %d곳 · 객실·사이트 %d · 예약가능 칸 %d · 새로 빈 자리 %d · 기간 %s +%d일 (수집 %s)'
          % (m['forests'], m['goods'], m['avail'], m['new'], m['start'], m['days'], m['at']))
    print('%s → %d bytes (%.2f MB)' % (a.out, len(body.encode('utf-8')), len(body.encode('utf-8')) / 1048576))
    if a.check:
        print('(--check: 쓰지 않았습니다)')
        return 0
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as fp:
        fp.write(body)
    print('저장 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
