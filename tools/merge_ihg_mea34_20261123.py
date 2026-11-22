#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중동 29 · 아프리카 5 = 34곳 → data/app/tab11_ihg.json 병합 (+ ① 호텔럭스 전수 대조)

원자료: 5번(@jin_5) 실측 `0-ihg-no5-34.json`
        (2026-11-23 06:44 KST · 2026-12-01~2027-11-30 365일 · 현금 10,820칸 · 포인트 10,820칸)

기존 tab11_ihg.json(아시아·오세아니아 72 + 유럽 41 + 북미·중남미 57 = 170곳, i01~i170)은
값·순서·alsoIn 을 그대로 두고 뒤에 34곳을 i171~i204로 붙여 204곳으로 만든다.

원자료의 rates/points 는 {YYYY-MM-DD: 값} 딕셔너리이므로 기존 `$d`/`$v` 압축열로 바꾼다:
  rates  = {'$d': '2026-12-01', '$v': [365개 …]}      (값 없는 칸은 null 그대로 — 보간 금지)
  points = {'$d': '2026-12-01', '$v': [365개 …]}
SHJVC(보코 샤르자)는 현금·포인트 0/0칸(365일 전부 null)로 그대로 두고 note 를 보존한다.

브랜드 표기 — 원자료의 brand 는 사이트 코드(IC·VOCO·CP…), brand_key 와 brand_code 가
뒤바뀐 행이 있어 브랜드 경로로 정규화한다(기존 표기: 한글 브랜드명 · qSHBrC 코드 · brand_key).
같이, 기존 170곳 가운데 브랜드 코드가 `VOCO`·`INDIGO`·`KIMPTON` 으로 남아 있던 15곳을
사이트 코드 `VO`·`IN`·`KI` 로 통일한다(예약 주소 qSHBrC 에 그대로 들어가는 값).

① 호텔럭스(tab1_vip.json 161곳) 전수 대조 — 코드·영문명·국문명·도시. ① 탭 도시는
뉴욕·싱가포르·도쿄·서울·시드니·방콕·상하이·다낭·나트랑·부산·후쿠오카·오사카 뿐이라
이번 34곳(중동 29 · 아프리카 5)과 겹치는 곳은 0곳일 것으로 보나 이름·코드로 전수 확인한다.
"""
import json
import os
import re
import unicodedata
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', 'b61af69f-leehanjin7', 'pickle',
                   '2026-11-23-0646', 'received', '0-ihg-no5-34.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
DAYS = [START + timedelta(days=i) for i in range(365)]
KEYS = [d.isoformat() for d in DAYS]

# 브랜드 경로 → (한글 브랜드명, qSHBrC 코드, brand_key)
BRAND = {
    'intercontinental': ('인터컨티넨탈', 'IC', 'IC'),
    'voco': ('보코', 'VO', 'VOCO'),
    'crowneplaza': ('크라운 플라자', 'CP', 'CP'),
    'vignettecollection': ('비네트 컬렉션', 'VIGNETTE', 'VIGNETTE'),
    'kimptonhotels': ('킴프턴', 'KI', 'KIMPTON'),
    'hotelindigo': ('호텔 인디고', 'IN', 'INDIGO'),
    'holidayinn': ('홀리데이 인', 'HI', 'HI'),
    'holidayinnexpress': ('홀리데이 인 익스프레스', 'HX', 'HIX'),
    'evenhotels': ('이븐 호텔', 'VN', 'EVEN'),
    'regent': ('리젠트', 'REGENT', 'REGENT'),
}

# 기존 9쌍 — 이번 34곳은 겹침 0
KEEP_PAIRS = {
    'i01': 'h27', 'i12': 'h61', 'i13': 'h64', 'i48': 'h15', 'i54': 'h20',
    'i63': 'h115', 'i65': 'h118', 'i99': 'h122', 'i100': 'h152',
}

EXPECT_ORDER = ['DXBHB', 'DXBPL', 'DXBMA', 'DXBBP', 'DXBSZ', 'DUBFC', 'AUHHA', 'AUHYI',
                'RKTHA', 'SHJVC', 'DOHHA', 'DOHWB', 'DOHDH', 'DOHCP', 'RUHHA', 'RUHKA',
                'RUHSD', 'RUHRP', 'JEDHA', 'JEDVC', 'QCAHD', 'QCAKS', 'KWIHC', 'KWIKF',
                'MSCHA', 'AMMHA', 'TLVHA', 'BEYHA', 'BAHHA', 'CROHA', 'CPTTB', 'JNBHC',
                'NBOFN', 'MRUMA']


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def norm(s):
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def compress(d):
    """{YYYY-MM-DD: 값} → {'$d': 첫날, '$v': [365개]} (날짜 순서 고정 · 없는 날은 null)"""
    assert list(d.keys()) == KEYS, (len(d), list(d.keys())[:2])
    return {'$d': KEYS[0], '$v': [d[k] for k in KEYS]}


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 170, len(old)
    assert base['window'] == ['2026-12-01', '2027-11-30'] and base['days'] == 365
    assert src['window']['start'] == '2026-12-01' and src['window']['end'] == '2027-11-30'
    assert src['window']['days'] == 365 and src['currency'] == 'KRW'
    assert src['summary'] == {'targets_total': 48, 'p1_total': 24, 'measured': 34,
                              'pending': 14, 'cash_cells': 10820, 'points_cells': 10820}, src['summary']
    assert len(src['hotels']) == 34
    assert src['pending_measurement'] and len(src['pending_measurement']) == 14

    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 54701 and old_pts == 52443, (old_cash, old_pts)
    old_alsoin = {h['id']: h.get('alsoIn') for h in old if h.get('alsoIn')}
    assert old_alsoin == KEEP_PAIRS, old_alsoin
    assert [h['id'] for h in old][0] == 'i01' and [h['id'] for h in old][-1] == 'i170'

    old_codes = {h['code'] for h in old}
    old_en = {norm(h['english']): h['id'] for h in old}
    old_ko = {norm(h['name']): h['id'] for h in old}

    n = len(old)
    added = []
    for h in src['hotels']:
        n += 1
        path = h['brand_path']
        assert path in BRAND, (h['code'], path)
        brand, bcode, bkey = BRAND[path]
        assert h['code'] not in old_codes, h['code']
        assert norm(h['english']) not in old_en, (h['english'], old_en.get(norm(h['english'])))
        assert norm(h['name']) not in old_ko, (h['name'], old_ko.get(norm(h['name'])))
        assert h['region'] in ('중동', '아프리카'), h['region']
        assert h['group'] == 'IHG' and h['priority'] in (1, 2)
        rates = compress(h['rates'])
        points = compress(h['points'])
        rc = numeric(rates['$v'])
        pc = numeric(points['$v'])
        assert rc == h['cells']['cash'] and pc == h['cells']['points'], (h['code'], rc, pc, h['cells'])
        assert (h.get('note') or ''), h['code']
        added.append({
            'id': 'i%02d' % n,
            'group': 'ihg',
            'code': h['code'],
            'brand': brand,
            'brand_code': bcode,
            'brand_key': bkey,
            'brand_path': path,
            'region': h['region'],
            'city': h['city'],
            'country': h['country'],
            'name': h['name'],
            'english': h['english'],
            'rates': rates,
            'points': points,
            'note': h['note'],
            'source': h.get('source') or '',
            'cells': {'rates': rc, 'points': pc},
        })

    assert len(added) == 34
    assert added[0]['id'] == 'i171' and added[-1]['id'] == 'i204'
    assert [x['code'] for x in added] == EXPECT_ORDER, [x['code'] for x in added]
    assert sum(h['cells']['rates'] for h in added) == 10820
    assert sum(h['cells']['points'] for h in added) == 10820
    assert sum(1 for h in added if h['region'] == '중동') == 29
    assert sum(1 for h in added if h['region'] == '아프리카') == 5
    assert sum(1 for h in added if h['region'] == '중동' and h['country'] == '아랍에미리트') == 10
    assert sum(1 for h in added if h['country'] == '사우디아라비아') == 8
    assert [x['id'] for x in added if x['code'] == 'SHJVC'] == ['i180']

    # SHJVC — 현금·포인트 0/0칸 · note 보존
    shj = [x for x in added if x['code'] == 'SHJVC'][0]
    assert shj['cells'] == {'rates': 0, 'points': 0}
    assert all(v is None for v in shj['rates']['$v']) and all(v is None for v in shj['points']['$v'])
    assert shj['note'].startswith('www.ihg.com 비로그인 실측')

    # ── 기존 170곳 브랜드 표기 통일 — VOCO→VO · INDIGO→IN · KIMPTON→KI (brand_code 만)
    fixed = []
    for h in old:
        bc = h['brand_code']
        if bc in ('VOCO', 'INDIGO', 'KIMPTON'):
            h['brand_code'] = BRAND[h['brand_path']][1]
            fixed.append((h['id'], h['code'], bc, h['brand_code']))
    assert len(fixed) == 21, fixed
    assert len([f for f in fixed if f[2] == 'VOCO']) == 5
    assert len([f for f in fixed if f[2] == 'INDIGO']) == 6
    assert len([f for f in fixed if f[2] == 'KIMPTON']) == 10

    hotels = old + added
    base['hotels'] = hotels
    base['generated_at'] = '2026-11-23'
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    assert cash == old_cash + 10820 == 65521, cash
    assert pts == old_pts + 10820 == 63263, pts
    assert base['counts']['cells'] == 204 * 365 == 74460
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))

    regions = {}
    countries = {}
    for h in hotels:
        regions[h['region']] = regions.get(h['region'], 0) + 1
    for h in added:
        countries[(h['region'], h['country'])] = countries.get((h['region'], h['country']), 0) + 1
    asia = sum(v for k, v in regions.items() if k not in ('유럽', '북미·중남미', '중동', '아프리카'))
    print('tab11 hotels %d (신규 %d) · 아시아·오세아니아 %d · 유럽 %d · 북미·중남미 %d · 중동 %d · 아프리카 %d'
          % (len(hotels), len(added), asia, regions.get('유럽'), regions.get('북미·중남미'),
             regions.get('중동'), regions.get('아프리카')))
    print('cells %d · cash %d · points %d (신규 현금 %d · 포인트 %d)'
          % (base['counts']['cells'], cash, pts, 10820, 10820))
    print('브랜드 코드 통일 %d곳: %s' % (len(fixed), fixed))
    print('신규 국가:', dict(sorted(countries.items(), key=lambda kv: -kv[1])))

    # ── ① 호텔럭스 161곳 전수 대조 — 코드·영문명·국문명·도시 ─────────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
    assert len(rows) == 161, len(rows)
    lux_by_en, lux_by_ko, lux_ids, lux_cities = {}, {}, set(), {}
    for d in rows:
        lux_by_en.setdefault(norm(d.get('english')), []).append(d['id'])
        lux_by_ko.setdefault(norm(d.get('name')), []).append(d['id'])
        lux_ids.add(str(d.get('id') or '').upper())
        lux_cities.setdefault(d.get('city'), []).append(d['id'])
    hits = []
    for h in added:
        for why, got in (('code', h['code'].upper() if h['code'].upper() in lux_ids else None),
                         ('en', (lux_by_en.get(norm(h['english'])) or [None])[0]),
                         ('ko', (lux_by_ko.get(norm(h['name'])) or [None])[0])):
            if got:
                hits.append((h['id'], h['code'], h['name'], got, why))
    print('① 호텔럭스 겹침(신규 34곳):', hits if hits else '없음')
    assert not hits, hits
    print('① 탭 도시:', {k: len(v) for k, v in sorted(lux_cities.items(), key=lambda kv: -len(kv[1]))})
    print('신규 34곳 도시가 ① 탭에 있는지:',
          {c: (c in lux_cities) for c in sorted({h['city'] for h in added})})
    assert not [c for c in {h['city'] for h in added} if c in lux_cities]

    lux_ai = {d['id']: d.get('alsoIn') for d in rows}
    for ihg_id, lux_id in KEEP_PAIRS.items():
        assert lux_ai[lux_id] == ihg_id, (lux_id, lux_ai[lux_id])
    print('기존 alsoIn 9쌍 양방향 유지 · alsoIn 총 %d쌍(신규 0쌍)'
          % len([h for h in hotels if h.get('alsoIn')]))


if __name__ == '__main__':
    main()
