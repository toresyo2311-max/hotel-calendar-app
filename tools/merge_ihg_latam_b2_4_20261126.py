#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 2차 4곳(No.7 실측 · 2026-11-26) → data/app/tab11_ihg.json 병합

원자료: No.7(@no_7)이 전달한 `0-ihg_latam_batch2_4.json`
        (2026-11-26 공홈 직접 실측 · 2026-12-01~2027-11-30 365일)
        · CUNHC 인터컨티넨탈 프레시덴테 칸쿤 리조트 (멕시코 · 칸쿤)
        · CUNCN 보코 칸쿤 소나 호텔레라 (멕시코 · 칸쿤)
        · SAOHA 인터컨티넨탈 상파울루 (브라질 · 상파울루) — 브라질 첫 지점
        · BUEHA 인터컨티넨탈 부에노스아이레스 (아르헨티나 · 부에노스아이레스) — 아르헨티나 첫 지점

기존 tab11_ihg.json(255곳, i01~i255)은 값·순서·alsoIn 을 그대로 두고
뒤에 4곳을 i256~i259 로 붙여 259곳으로 만든다(북미·중남미 61 → 65).
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', 'a03363f4-no71', 'pickle',
                   '2026-11-26-0957', 'received', '0-ihg_latam_batch2_4.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

# 원자료의 CUNCN brand_code 는 IHG 공홈 코드가 아니라 브랜드 키 표기(VOCO)라
# 이 탭의 기존 실측 관례(VO)로 맞춘다.
BRAND_CODE_FIX = {'VOCO': 'VO'}


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def norm(s):
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 255, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30'], src['window']
    assert src['group'] == 'ihg-latam-batch2-4', src['group']
    assert src['generated_at'] == '2026-11-26'

    old_codes = {h['code'] for h in old}
    old_ids = {h['id'] for h in old}
    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 81720 and old_pts == 78878, (old_cash, old_pts)

    n = 255
    added = []
    for h in src['hotels']:
        assert h['code'] not in old_codes, ('이미 있는 코드', h['code'])
        n += 1
        bcode = BRAND_CODE_FIX.get(h['brand_code'], h['brand_code'])
        rc = numeric(h['rates']['$v'])
        pc = numeric(h['points']['$v'])
        assert rc == h['cells']['rates'], (h['code'], rc, h['cells'])
        assert pc == h['cells']['points'], (h['code'], pc, h['cells'])
        assert len(h['rates']['$v']) == 365 and len(h['points']['$v']) == 365
        assert h['rates']['$d'] == h['points']['$d'] == '2026-12-01'
        note = h['note']
        # 병합자 판단 대기 같은 미정 표기가 남아 있지 않은지 확인 — 남기지 않는다.
        assert '판단 필요' not in note, h['code']
        rec = {
            'id': 'i%02d' % n,
            'group': 'ihg',
            'code': h['code'],
            'brand': h['brand'],
            'brand_code': bcode,
            'brand_key': h['brand_key'],
            'brand_path': h['brand_path'],
            'region': h['region'],
            'city': h['city'],
            'country': h['country'],
            'name': h['name'],
            'english': h['english'],
            'rates': h['rates'],
            'points': h['points'],
            'note': note,
            'source': h['source'],
            'cells': {'rates': rc, 'points': pc},
        }
        added.append(rec)

    assert len(added) == 4
    assert [h['code'] for h in added] == ['CUNHC', 'CUNCN', 'SAOHA', 'BUEHA']
    assert [h['id'] for h in added] == ['i256', 'i257', 'i258', 'i259']
    assert [h['cells']['rates'] for h in added] == [336, 268, 344, 298]
    assert [h['cells']['points'] for h in added] == [336, 0, 343, 298]
    assert sum(h['cells']['rates'] for h in added) == 1246
    assert sum(h['cells']['points'] for h in added) == 977
    assert len({h['id'] for h in added} | old_ids) == len(old) + len(added)
    assert {h['region'] for h in added} == {'북미·중남미'}
    assert {h['country'] for h in added} == {'멕시코', '브라질', '아르헨티나'}
    assert {h['city'] for h in added} == {'칸쿤', '상파울루', '부에노스아이레스'}
    assert {h['brand_key'] for h in added} == {'IC', 'VOCO'}
    assert {h['brand_code'] for h in added} == {'IC', 'VO'}
    assert {h['brand_path'] for h in added} == {'intercontinental', 'voco'}
    assert {h['brand'] for h in added} == {'인터컨티넨탈', '보코'}
    for h in added:
        assert h['name'] and h['english'] and h['city']
        assert h['group'] == 'ihg'
        assert 'alsoIn' not in h

    by = {h['code']: h for h in added}
    W = list(range(344, 365))            # 2027-11-10~11-30 (예약창 밖 21일)

    # ── 특이사항(브리프 3)이 원자료·값에 실제로 반영됐는지 확인 ──────────
    # CUNHC — 12 USD/박 Amenity Fee 별도(세후가 미포함) · 연말 8일 + 예약창 21일 null
    hc, hcp = by['CUNHC']['rates']['$v'], by['CUNHC']['points']['$v']
    assert [i for i, v in enumerate(hc) if v is None] == [22, 23, 27, 28, 29, 30, 31, 32] + W
    assert [i for i, v in enumerate(hcp) if v is None] == [i for i, v in enumerate(hc) if v is None]
    assert hc[25] == 1200000 and hc[26] == 1300000, (hc[25], hc[26])      # 12-26 · 12-27
    assert hcp[25] == 120000 and hcp[26] == 120000
    assert '12 USD Amenity Fee per night' in by['CUNHC']['note']
    assert 'Amenity' in by['CUNHC']['note']

    # CUNCN — 리브랜딩 개관 초기 · 현금은 2027-02-15부터 268일 단일가 259,600원 · 포인트 0일
    nc, ncp = by['CUNCN']['rates']['$v'], by['CUNCN']['points']['$v']
    assert all(v is None for v in ncp), 'CUNCN 포인트는 전 기간 null 이어야 한다'
    assert all(v is None for v in nc[:76]) and all(v is None for v in nc[344:])
    assert all(v == 259600 for v in nc[76:344]), sorted({v for v in nc[76:344]})
    assert '259,600' in by['CUNCN']['note'] and '포인트 0일' in by['CUNCN']['note']
    assert '리브랜딩' in by['CUNCN']['note'] and '개관 초기' in by['CUNCN']['note']

    # SAOHA — 전면 리노베이션(로비·레스토랑·풀 임시 휴업) 공지 · 포인트만 없는 날 1일(2026-12-02)
    sc, scp = by['SAOHA']['rates']['$v'], by['SAOHA']['points']['$v']
    assert [i for i, v in enumerate(sc) if v is None] == W
    assert [i for i, v in enumerate(scp) if v is None] == [1] + W
    assert sc[0] == 407100 and scp[0] == 79000
    assert '전면 리노베이션' in by['SAOHA']['note']
    assert 'lobby, restaurants, and pool are temporarily closed' in by['SAOHA']['note']
    assert '진행 중 전면 리노베이션' in by['SAOHA']['note']

    # BUEHA — 1.5 USD/인/박 Amenity Fee 별도 · 현금·포인트 null 집합 동일
    bc, bcp = by['BUEHA']['rates']['$v'], by['BUEHA']['points']['$v']
    assert [i for i, v in enumerate(bc) if v is None] == [i for i, v in enumerate(bcp) if v is None]
    assert len([i for i, v in enumerate(bc) if v is None]) == 67
    assert bc[0] == 432000 and bcp[0] == 59000
    assert '1.5 USD Amenity Fee per guest per night' in by['BUEHA']['note']

    # ── ① 호텔럭스 161곳 전수 대조(코드·영문명·국문명·도시) ──────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
    assert len(rows) == 161, len(rows)
    lux_keys = {}
    for d in rows:
        for k in ('english', 'name'):
            v = norm(d.get(k))
            if v:
                lux_keys.setdefault(v, []).append(d['id'])
        c = norm(d.get('code'))
        if c:
            lux_keys.setdefault('code:' + c, []).append(d['id'])
    lux_cities = {d.get('city') for d in rows}
    hits = []
    for h in added:
        for key in (norm(h['english']), norm(h['name']), 'code:' + norm(h['code'])):
            if key in lux_keys:
                hits.append((h['code'], key, lux_keys[key]))
    # 도시 단위까지 본다 — 같은 도시에 ① 지점이 있으면 이름이 달라도 사람이 헷갈릴 수 있다.
    city_hits = [(h['code'], h['city']) for h in added if h['city'] in lux_cities]
    assert not hits, hits
    assert not city_hits, city_hits
    print('① 호텔럭스 161곳 대조 — 코드·영문명·국문명·도시 겹침 0곳 · alsoIn 추가 0쌍')
    for h in added:
        e = norm(h['english'])
        near = [d['id'] for d in rows
                if e and (e[:8] in norm(d.get('english')) or norm(d.get('english'))[:8] in e)]
        print('   근사 후보(영문 앞 8자):', h['code'], near)

    # ── 기존 IHG 255곳 안에 같은 도시·같은 이름이 있는지 ──────────────────
    for h in added:
        same_city = [(x['id'], x['code'], x['name']) for x in old if x['city'] == h['city']]
        print('   같은 도시 기존:', h['code'], h['city'], same_city)
        assert not same_city, (h['code'], same_city)
        same_name = [x['id'] for x in old if norm(x['name']) == norm(h['name'])]
        assert not same_name, (h['code'], same_name)
    assert not [x for x in old if x['country'] in ('브라질', '아르헨티나')]
    print('   브라질 · 아르헨티나 기존: 0곳 — 이 탭의 첫 지점')
    print('   기존 멕시코:', [(x['id'], x['code'], x['city']) for x in old if x['country'] == '멕시코'])

    hotels = old + added
    assert len({h['id'] for h in hotels}) == len(hotels)
    assert len({h['code'] for h in hotels}) == len(hotels)
    base['hotels'] = hotels
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    assert cash == old_cash + 1246, (cash, old_cash)
    assert pts == old_pts + 977, (pts, old_pts)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    base['generated_at'] = '2026-11-26'
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))

    na = [h for h in hotels if h['region'] == '북미·중남미']
    co = {}
    for h in na:
        co[h['country']] = co.get(h['country'], 0) + 1
    ci = {}
    for h in na:
        ci[h['city']] = ci.get(h['city'], 0) + 1
    print('tab11 hotels %d (신규 %d · 북미·중남미 %d)' % (len(hotels), len(added), len(na)))
    print('북미·중남미 국가:', co)
    print('북미·중남미 도시:', ci)
    print('북미·중남미 칸: %d · 현금 %d · 포인트 %d'
          % (len(na) * 365, sum(h['cells']['rates'] for h in na),
             sum(h['cells']['points'] for h in na)))
    print('신규 ids %s ~ %s' % (added[0]['id'], added[-1]['id']))
    print('전체 칸 %d · 현금 %d · 포인트 %d' % (len(hotels) * 365, cash, pts))
    assert len(na) == 65, len(na)
    assert co == {'미국': 52, '캐나다': 5, '멕시코': 6, '브라질': 1, '아르헨티나': 1}, co
    assert ci['칸쿤'] == 2 and ci['멕시코시티'] == 4 and ci['상파울루'] == 1 and ci['부에노스아이레스'] == 1
    assert base['counts'] == {'hotels': 259, 'cells': 94535, 'cash': 82966, 'points': 79855}, \
        base['counts']
    assert sum(h['cells']['rates'] for h in na) == 21144
    assert sum(h['cells']['points'] for h in na) == 20651
    print('OK — 255→259곳 · 북미·중남미 61→65 · 94,535칸(현금 82,966 · 포인트 79,855)')


if __name__ == '__main__':
    main()
