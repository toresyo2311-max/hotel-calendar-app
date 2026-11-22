#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 한국 신규 30곳 병합 (62곳 → 92곳 · 한국 40곳).

입력: memory/clones/f0ee2d96-jin_5/pickle/2026-11-23-0131/received/0-2026-11-22-marriott-kr-31.json
      (marriott.com 요금 캘린더 + 아워드 포인트 캘린더 365일 · 2026-12-01~2027-11-30 · 2026-11-22 조회)
대상: data/master_db.json (정본) — 기존 62곳(m01~m40 중국 · k01~k10 한국 · j01~j12 일본)은 그대로 두고
      k10 뒤에 k11~k40 으로 30곳을 넣는다. 배포본(data/app/tab4_marriott.json · index.html 집계값)은
      이 스크립트 뒤에 `python3 tools/master_db.py inject` 로 쓴다.

· SELAK(더 플라자 서울, 2026-09-30 영업 종료 · 2029년 재개관 목표)는 넣지 않는다 — bundle 에서 status=closed.
· 도시 표기: SELNH(인천 영종도) → 인천, SELGA(경기 군포) → 경기, SELAY·SELPN(성남 판교) → 판교.
· rates·points 는 365일 날짜 맵 그대로(KRW 정수 · null 은 보간하지 않음).
· ① 호텔럭스(tab1_vip.json 161곳)와 코드·국문명·영문명을 전수 대조해 겹치는 2곳
  (SELLM → h30 레스케이프 호텔 명동 · SELWG → h34 웨스틴 서울 파르나스)만 alsoIn 으로 잇는다.
"""
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
SRC = os.path.join(WS, 'memory/clones/f0ee2d96-jin_5/pickle/2026-11-23-0131/received/'
                       '0-2026-11-22-marriott-kr-31.json')
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

sys.path.insert(0, os.path.join(ROOT, 'tools'))
import master_db as M  # noqa: E402  (stats_of 재사용 — counts 를 손으로 적지 않는다)

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

# 표시 순서 — 서울 → 경기 → 판교 → 인천 → 수원 → 대전 → 부산 → 제주
ORDER = [
    'SELAG', 'SELAL', 'SELCS', 'SELCY', 'SELFD', 'SELFI', 'SELFG', 'SELFP',
    'SELFU', 'SELLM', 'SELMO', 'SELMX', 'SELOX', 'SELSN', 'SELTX', 'SELWG',
    'SELGA', 'SELAY', 'SELPN', 'SELGI', 'SELNH', 'SELCW', 'SELFO',
    'CJJAK', 'CJJCY', 'CJJPY', 'PUSFB', 'PUSFI', 'CJUMJ', 'CJUSI',
]
CITY_FIX = {'SELNH': '인천', 'SELGA': '경기', 'SELAY': '판교', 'SELPN': '판교'}
# ① 호텔럭스(tab1_vip.json)와 겹치는 2곳 — alsoIn 대상 id
HLX = {'SELLM': 'h30', 'SELWG': 'h34'}
SOURCE_TEXT = ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · 2026-11-22 조회 / '
               '아워드 포인트 캘린더(2026-11-22 기준) · 5번 계정 실측 marriott-kr-31 365일')


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def clean_note(t):
    """조사 메모에서 내부 파일 이름·지시문만 걷어낸다(사실은 그대로)."""
    t = t.replace('**', '').replace('\\"', '"')
    t = t.replace(' — No.2 병합 시 참고.', '')
    t = t.replace('No.2 병합 시 참고.', '')
    t = t.replace(' — targets.json의 city=서울과 실제 소재지가 다름', '')
    t = t.replace('targets.json의 ', '이전 조사 목록의 ')
    t = t.replace('targets.json', '이전 조사 목록')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def main():
    master = json.load(open(MASTER, encoding='utf-8'))
    hotels = master['hotels']
    mar = [h for h in hotels if h.get('group') == 'marriott']
    assert len(mar) == 62, len(mar)
    exist_codes = {h.get('code') for h in mar}
    exist_names = {norm(h.get('english')): h['id'] for h in mar}
    exist_kr = {h.get('name'): h['id'] for h in mar}

    bundle = json.load(open(SRC, encoding='utf-8'))
    src = {h['code']: h for h in bundle['hotels']}
    assert len(src) == 31, len(src)
    closed = [c for c, h in src.items() if h.get('status') == 'closed']
    assert closed == ['SELAK'], closed          # 더 플라자 서울 — 영업 종료라 넣지 않는다
    assert bundle.get('pending_measurement') == [], bundle.get('pending_measurement')
    assert sorted(ORDER) == sorted(c for c in src if c not in closed), \
        (set(ORDER) ^ set(c for c in src if c not in closed))

    # ① 호텔럭스 161곳 전수 대조 — 코드가 없으므로 영문명·국문명으로 본다
    tab1 = json.load(open(os.path.join(ROOT, 'data', 'app', 'tab1_vip.json'), encoding='utf-8'))
    cols = tab1['hotels']['$t']
    vip = [dict(zip(cols, r)) for r in tab1['hotels']['$r']]
    vip_en = {}
    for r in vip:
        vip_en.setdefault(norm(r.get('english')), []).append(r)
    found = {}
    for code in ORDER:
        h = src[code]
        hit = vip_en.get(norm(h['english'])) or [
            r for r in vip if r.get('name') == h['name']]
        if hit:
            found[code] = hit[0]['id']
    assert found == HLX, '① 호텔럭스 대조 결과가 기대와 다름: %s' % found

    new_rows = []
    for i, code in enumerate(ORDER):
        h = src[code]
        hid = 'k%02d' % (11 + i)
        assert code not in exist_codes, '이미 있는 코드 %s' % code
        n = norm(h['english'])
        assert n not in exist_names, '이미 있는 영문명 %s → %s' % (h['english'], exist_names.get(n))
        assert h['name'] not in exist_kr, '이미 있는 국문명 %s' % h['name']
        exist_names[n] = hid
        exist_kr[h['name']] = hid
        exist_codes.add(code)
        assert h.get('region') == '한국', h.get('region')
        assert sorted(h['rates']) == DATES and sorted(h['points']) == DATES, code

        rates = {d: (None if h['rates'].get(d) is None else int(h['rates'][d])) for d in DATES}
        pts = {d: (None if h['points'].get(d) is None else int(h['points'][d])) for d in DATES}
        for v in rates.values():
            assert v is None or (isinstance(v, int) and 0 < v < 10_000_000), (code, v)
        for v in pts.values():
            assert v is None or (isinstance(v, int) and 0 < v < 1_000_000), (code, v)
        cash = sum(1 for v in rates.values() if v is not None)
        pdays = sum(1 for v in pts.values() if v is not None)

        city = CITY_FIX.get(code, h['city'])
        head = code if code not in CITY_FIX else '%s (도시 칸 「%s」 — 호텔명은 서울)' % (code, city)
        note = '%s · 현금 %d일/365 · 아워드 포인트 %d일/365 · %s' % (
            head, cash, pdays, clean_note(h['note']))

        row = {
            'id': hid,
            'group': 'marriott',
            'brand': h['brand'],
            'city': city,
            'region': '한국',
            'name': h['name'],
            'english': h['english'],
            'promotion': '아워드 포인트 캘린더(2026-11-22 기준) · 포인트 %d일 확보' % pdays,
            'source': SOURCE_TEXT,
            'code': code,
            'rates': rates,
            'points': pts,
            'note': note,
        }
        if code in HLX:
            row['alsoIn'] = HLX[code]
            row['alsoInLabel'] = '① VIP 요금 탭에도 수록'
        new_rows.append(row)

    # k10 바로 뒤에 끼워 넣는다 — 한국 블록이 40곳으로 이어진다
    at = max(i for i, h in enumerate(hotels) if h['id'] == 'k10') + 1
    hotels[at:at] = new_rows

    if 'marriott-kr30 2026-11-22 (한국 30곳 · 5번 실측 marriott-kr-31)' not in master['sources']:
        master['sources'].append('marriott-kr30 2026-11-22 (한국 30곳 · 5번 실측 marriott-kr-31)')

    line = ('2026-11-23 KST ③ 메리어트 한국 30곳 병합(62→92곳 · 한국 40 · 일본 12 · 중국 40) — '
            '2026-11-22 marriott.com 요금 캘린더 세전 KRW + 아워드 포인트 365일 실측(5번 계정 marriott-kr-31), '
            'SELAK(더 플라자 서울 · 2026-09-30 영업 종료)은 제외. 인천 영종도·경기 군포·성남 판교 4곳은 '
            '도시 칸을 실제 소재지(인천·경기·판교)로 바로잡고, ① 호텔럭스와 겹치는 2곳 '
            '(레스케이프 서울 명동 · 웨스틴 서울 파르나스)은 alsoIn 으로 이었습니다.')
    if '한국 30곳 병합(62→92곳' not in master.get('extended', ''):
        master['extended'] = (master.get('extended') or '') + ' / ' + line

    st = M.stats_of({'hotels': hotels, 'accor': master.get('accor')},
                    master['flights'], master.get('ttang'))
    master['counts'] = {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na', 'stayplus',
                                           'routes', 'deals', 'snu', 'pus_deals', 'pus_routes',
                                           'redhot_hotels', 'redhot_cells')}

    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')

    brands = {}
    for h in hotels:
        if h.get('group') == 'marriott':
            brands[h['brand']] = brands.get(h['brand'], 0) + 1
    cash = sum(1 for h in new_rows for v in h['rates'].values() if v is not None)
    pts = sum(1 for h in new_rows for v in h['points'].values() if v is not None)
    print('메리어트 %d곳 · 전체 %d곳 · cells %d · priced %d · na %d' % (
        len(mar) + len(new_rows), st['hotels'], st['cells'], st['priced'], st['na']))
    print('신규 30곳 — 현금 %d칸 · 포인트 %d칸 / %d칸(30×365)' % (cash, pts, 30 * 365))
    print('브랜드:', json.dumps(dict(sorted(brands.items(), key=lambda x: -x[1])), ensure_ascii=False))


if __name__ == '__main__':
    main()
