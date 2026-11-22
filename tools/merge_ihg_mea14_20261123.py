#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중동 7 · 아프리카 7 = 14곳 → data/app/tab11_ihg.json 병합 (+ ① 호텔럭스 전수 대조)

원자료: 5번(@jin_5) 실측 `0-ihg-no5-48.json` (2026-11-23 07:43 KST)
        중동·아프리카 48곳 완결본 — 2026-12-01~2027-11-30 365일
        현금 14,926칸 · 포인트 14,830칸 (48 × 365 = 17,520칸)

앞선 `merge_ihg_mea34_20261123.py`(z109)로 들어간 34곳은 값·순서·alsoIn 을 그대로 두고,
아직 없는 순수 신규 14곳만 i205~i218 로 이어 붙여 204 → 218곳으로 만든다.
신규 14곳: 현금 4,106칸 · 포인트 4,010칸 (중동 7 · 아프리카 7)

특이사항(원자료 그대로 + note 에 사유 보존):
  · JRSHA 인터컨티넨탈 예루살렘 — IHG 공홈 OPENING SOON, 2027-05-15 개관.
    그날부터 현금 99일만 값이 있고 포인트는 전 기간 없음.
  · CROHC 인터컨티넨탈 시티스타 카이로 — 달력 셀 값은 세금·수수료 포함 표시값 그대로.
  · ACCRA 홀리데이 인 아크라 에어포트 — 전 기간(365일) 재고 없음, 현금·포인트 0/0칸.

브랜드 표기 — 원자료의 brand_path 를 기존 표기(한글 브랜드명 · qSHBrC 코드 · brand_key)로 정규화.
① 호텔럭스(tab1_vip.json 161곳) 전수 대조 — 코드·영문명·국문명·도시.
"""
import json
import os
import re
import unicodedata
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', 'b61af69f-leehanjin7', 'pickle',
                   '2026-11-23-0744', 'received', '0-ihg-no5-48.json')
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

# 기존 9쌍 — 이번 14곳은 겹침 0
KEEP_PAIRS = {
    'i01': 'h27', 'i12': 'h61', 'i13': 'h64', 'i48': 'h15', 'i54': 'h20',
    'i63': 'h115', 'i65': 'h118', 'i99': 'h122', 'i100': 'h152',
}

EXPECT_ORDER = ['MSCHC', 'MCTAL', 'AMMHB', 'TLVIL', 'JRSHA', 'BEYLE', 'MNABA',
                'CROHC', 'CAISZ', 'CPTST', 'JNBHI', 'NBOIR', 'ACCRA', 'DARDS']

# 특이사항 — 원자료 note 뒤에 사유를 덧붙여 보존한다
EXTRA_NOTE = {
    'JRSHA': ' IHG 공홈 OPENING SOON — 2027-05-15 개관, 그날부터 2027-11-06까지 현금 99일만 값이 있고 포인트는 전 기간 없습니다.',
    'CROHC': ' 달력 셀 값은 세금·수수료 포함 표시값 그대로입니다.',
    'ACCRA': ' 전 기간(365일) 재고 없음 — 현금·포인트 0칸입니다.',
}


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
    assert len(old) == 204, len(old)
    assert base['window'] == ['2026-12-01', '2027-11-30'] and base['days'] == 365
    assert src['window']['start'] == '2026-12-01' and src['window']['end'] == '2027-11-30'
    assert src['window']['days'] == 365 and src['currency'] == 'KRW'
    assert src['summary'] == {'targets_total': 48, 'p1_total': 24, 'measured': 48,
                              'pending': 0, 'cash_cells': 14926, 'points_cells': 14830}, src['summary']
    assert len(src['hotels']) == 48
    assert not (src.get('pending_measurement') or [])

    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 65521 and old_pts == 63263, (old_cash, old_pts)
    old_alsoin = {h['id']: h.get('alsoIn') for h in old if h.get('alsoIn')}
    assert old_alsoin == KEEP_PAIRS, old_alsoin
    assert [h['id'] for h in old][0] == 'i01' and [h['id'] for h in old][-1] == 'i204'

    old_codes = {h['code'] for h in old}
    old_en = {norm(h['english']): h['id'] for h in old}
    old_ko = {norm(h['name']): h['id'] for h in old}

    # 앞선 34곳은 같은 원자료 안에서 값이 그대로여야 한다
    same34 = [h for h in src['hotels'] if h['code'] in old_codes]
    assert len(same34) == 34, len(same34)
    for h in same34:
        cur = [x for x in old if x['code'] == h['code']][0]
        assert cur['cells'] == {'rates': h['cells']['cash'], 'points': h['cells']['points']}, \
            (h['code'], cur['cells'], h['cells'])

    n = len(old)
    added = []
    for h in src['hotels']:
        if h['code'] in old_codes:
            continue
        n += 1
        path = h['brand_path']
        assert path in BRAND, (h['code'], path)
        brand, bcode, bkey = BRAND[path]
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
        note = h['note'] + EXTRA_NOTE.get(h['code'], '')
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
            'note': note,
            'source': h.get('source') or '',
            'cells': {'rates': rc, 'points': pc},
        })

    assert len(added) == 14, len(added)
    assert added[0]['id'] == 'i205' and added[-1]['id'] == 'i218'
    assert [x['code'] for x in added] == EXPECT_ORDER, [x['code'] for x in added]
    assert sum(h['cells']['rates'] for h in added) == 4106
    assert sum(h['cells']['points'] for h in added) == 4010
    assert sum(1 for h in added if h['region'] == '중동') == 7
    assert sum(1 for h in added if h['region'] == '아프리카') == 7

    # JRSHA — 2027-05-15 개관, 현금 99일(2027-05-15~2027-11-06 중 값 있는 날) · 포인트 0일
    jrs = [x for x in added if x['code'] == 'JRSHA'][0]
    rv = jrs['rates']['$v']
    assert jrs['cells'] == {'rates': 99, 'points': 0}, jrs['cells']
    assert all(v is None for v in rv[:jrs['rates']['$v'].index(next(v for v in rv if v is not None))])
    first = KEYS[rv.index(next(v for v in rv if v is not None))]
    assert first == '2027-05-15', first
    assert all(v is None for v in jrs['points']['$v'])
    assert 'OPENING SOON' in jrs['note']

    # CROHC — 세금·수수료 포함 표시값 그대로
    cro = [x for x in added if x['code'] == 'CROHC'][0]
    assert cro['cells'] == {'rates': 335, 'points': 335}
    assert '세금·수수료 포함' in cro['note']

    # ACCRA — 전 기간 재고 없음 0/0칸
    acc = [x for x in added if x['code'] == 'ACCRA'][0]
    assert acc['cells'] == {'rates': 0, 'points': 0}
    assert all(v is None for v in acc['rates']['$v']) and all(v is None for v in acc['points']['$v'])
    assert '재고 없음' in acc['note']

    hotels = old + added
    base['hotels'] = hotels
    base['generated_at'] = '2026-11-23'
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    assert cash == old_cash + 4106 == 69627, cash
    assert pts == old_pts + 4010 == 67273, pts
    assert base['counts']['cells'] == 218 * 365 == 79570
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))

    regions = {}
    for h in hotels:
        regions[h['region']] = regions.get(h['region'], 0) + 1
    asia = sum(v for k, v in regions.items() if k not in ('유럽', '북미·중남미', '중동', '아프리카'))
    print('tab11 hotels %d (신규 %d) · 아시아·오세아니아 %d · 유럽 %d · 북미·중남미 %d · 중동 %d · 아프리카 %d'
          % (len(hotels), len(added), asia, regions.get('유럽'), regions.get('북미·중남미'),
             regions.get('중동'), regions.get('아프리카')))
    print('cells %d · cash %d · points %d (신규 현금 %d · 포인트 %d)'
          % (base['counts']['cells'], cash, pts, 4106, 4010))
    me = {}
    af = {}
    for h in hotels:
        if h['region'] == '중동':
            me[h['country']] = me.get(h['country'], 0) + 1
        elif h['region'] == '아프리카':
            af[h['country']] = af.get(h['country'], 0) + 1
    print('중동 국가:', dict(sorted(me.items(), key=lambda kv: -kv[1])), '합', sum(me.values()))
    print('아프리카 국가:', dict(sorted(af.items(), key=lambda kv: -kv[1])), '합', sum(af.values()))

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
    print('① 호텔럭스 겹침(신규 14곳):', hits if hits else '없음')
    assert not hits, hits
    print('신규 14곳 도시가 ① 탭에 있는지:',
          {c: (c in lux_cities) for c in sorted({h['city'] for h in added})})
    assert not [c for c in {h['city'] for h in added} if c in lux_cities]

    lux_ai = {d['id']: d.get('alsoIn') for d in rows}
    for ihg_id, lux_id in KEEP_PAIRS.items():
        assert lux_ai[lux_id] == ihg_id, (lux_id, lux_ai[lux_id])
    print('기존 alsoIn 9쌍 양방향 유지 · alsoIn 총 %d쌍(신규 0쌍)'
          % len([h for h in hotels if h.get('alsoIn')]))


if __name__ == '__main__':
    main()
