#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P2 4차 4곳(No.7 실측 · 2026-11-26) → data/app/tab11_ihg.json 병합

원자료: No.7(@no_7)이 전달한 `0-ihg_p2_batch4_4.json`
        (2026-11-26 공홈 직접 실측 · 2026-12-01~2027-11-30 365일)
        · HELMH 크라운 플라자 헬싱키 (핀란드 · 헬싱키 — 코드 HELMH 는 크라운 플라자,
          호텔 인디고 헬싱키(HELIN)는 P1에서 이미 들어와 있다)
        · ATHGR 크라운 플라자 아테네 시티 센트르 (그리스 · 아테네)
        · ISTBM 크라운 플라자 이스탄불 올드 시티 (튀르키예 · 이스탄불)
        · ISTOR 크라운 플라자 이스탄불 오르타쾨이 보스포루스 (튀르키예 · 이스탄불)

기존 tab11_ihg.json(244곳, i01~i244)은 값·순서·alsoIn 을 그대로 두고
뒤에 4곳을 i245~i248 로 붙여 248곳으로 만든다(유럽 67 → 71).

① 호텔럭스(tab1_vip.json 161곳) 전수 대조 — 코드·영문명·국문명·도시를 정규화해
맞는 호텔이 하나도 없으면 alsoIn 을 붙이지 않는다(IHG 공홈 단일 링크).
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', 'a03363f4-no71', 'pickle',
                   '2026-11-26-0729', 'received', '0-ihg_p2_batch4_4.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

BRAND_KO = {
    'IC': '인터컨티넨탈', 'VOCO': '보코', 'HIX': '홀리데이 인 익스프레스',
    'HI': '홀리데이 인', 'CP': '크라운 플라자', 'KIMPTON': '킴프턴',
    'INDIGO': '호텔 인디고', 'REGENT': '리젠트', 'VIGNETTE': '비네트 컬렉션',
}
BRAND_KEY_FIX = {'KI': 'KIMPTON', 'IN': 'INDIGO', 'HIX': 'HIX'}


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def norm(s):
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 244, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30'], src['window']
    assert src['group'] == 'ihg-p2-batch4-4', src['group']

    old_codes = {h['code'] for h in old}
    old_ids = {h['id'] for h in old}
    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 78315 and old_pts == 75783, (old_cash, old_pts)

    n = 244
    added = []
    for h in src['hotels']:
        assert h['code'] not in old_codes, ('이미 있는 코드', h['code'])
        n += 1
        brand = BRAND_KO.get(h['brand']) or BRAND_KO.get(h['brand_code']) or h['brand']
        bkey = BRAND_KEY_FIX.get(h['brand_key'], h['brand_key'])
        rc = numeric(h['rates']['$v'])
        pc = numeric(h['points']['$v'])
        assert rc == h['cells']['rates'], (h['code'], rc, h['cells'])
        assert pc == h['cells']['points'], (h['code'], pc, h['cells'])
        assert len(h['rates']['$v']) == 365 and len(h['points']['$v']) == 365
        assert h['rates']['$d'] == h['points']['$d'] == '2026-12-01'
        rec = {
            'id': 'i%02d' % n,
            'group': 'ihg',
            'code': h['code'],
            'brand': brand,
            'brand_code': h['brand_code'],
            'brand_key': bkey,
            'brand_path': h['brand_path'],
            'region': h['region'],
            'city': h['city'],
            'country': h['country'],
            'name': h['name'],
            'english': h['english'],
            'rates': h['rates'],
            'points': h['points'],
            'note': h['note'],
            'source': h['source'],
            'cells': {'rates': rc, 'points': pc},
        }
        added.append(rec)

    assert len(added) == 4
    assert [h['code'] for h in added] == ['HELMH', 'ATHGR', 'ISTBM', 'ISTOR']
    assert [h['id'] for h in added] == ['i245', 'i246', 'i247', 'i248']
    assert [h['cells']['rates'] for h in added] == [340, 337, 345, 345]
    assert [h['cells']['points'] for h in added] == [339, 339, 345, 345]
    assert sum(h['cells']['rates'] for h in added) == 1367
    assert sum(h['cells']['points'] for h in added) == 1368
    assert len({h['id'] for h in added} | old_ids) == len(old) + len(added)
    assert {h['region'] for h in added} == {'유럽'}
    assert {h['country'] for h in added} == {'핀란드', '그리스', '튀르키예'}
    assert {h['brand_key'] for h in added} == {'CP'}
    assert {h['brand_path'] for h in added} == {'crowneplaza'}
    assert {h['city'] for h in added} == {'헬싱키', '아테네', '이스탄불'}
    for h in added:
        assert h['name'] and h['english'] and h['city']
        assert h['group'] == 'ihg'

    by = {h['code']: h for h in added}
    # 값이 있는 마지막 날 — 헬싱키 2027-11-09, 나머지 세 곳 2027-11-10(그 뒤는 예약창 미오픈)
    assert by['HELMH']['rates']['$v'][343] == 194400 and by['HELMH']['rates']['$v'][344] is None
    for code in ('ATHGR', 'ISTBM', 'ISTOR'):
        assert by[code]['rates']['$v'][344] is not None, code
        assert all(v is None for v in by[code]['rates']['$v'][345:]), code
        assert all(v is None for v in by[code]['points']['$v'][345:]), code
    assert all(v is None for v in by['HELMH']['rates']['$v'][344:])
    assert all(v is None for v in by['HELMH']['points']['$v'][344:])

    # 원자료 note 주의문 — ATHGR 4 EUR 어메니티 피 별도 · HELMH 코드/브랜드 정정 · ISTOR 예약창
    assert 'Excludes 4 EUR Amenity Fee per night' in by['ATHGR']['note']
    assert '4 EUR(약 6,600원) 어메니티피' in by['ATHGR']['note']
    assert 'Crowne Plaza Helsinki - Hesperia' in by['HELMH']['note']
    assert 'HELIN(호텔 인디고 헬싱키 블레바르디, g063)' in by['HELMH']['note']
    assert 'Rooms cannot be booked this far in advance' in by['ISTOR']['note']
    assert 'p-disabled' in by['ISTBM']['note']

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
    assert not hits, hits
    print('① 호텔럭스 161곳 대조 — 겹침 0곳 · alsoIn 추가 0쌍')
    print('   ① 탭 도시:', ' · '.join(sorted(c for c in lux_cities if c)))
    for h in added:
        if h['city'] in lux_cities:
            print('   주의 — 새 호텔 도시가 ① 탭 도시와 같음:', h['code'], h['city'])
    for h in added:
        e = norm(h['english'])
        near = [d['id'] for d in rows
                if e and (e[:6] in norm(d.get('english')) or norm(d.get('english'))[:6] in e)]
        print('   근사 후보(영문 앞 6자):', h['code'], near)

    # ── 같은 도시의 기존 IHG 호텔(중복 코드만 아니면 별개 호텔) ──────────
    for h in added:
        same_city = [(x['id'], x['code'], x['name']) for x in old if x['city'] == h['city']]
        print('   같은 도시 기존:', h['code'], h['city'], same_city)

    hotels = old + added
    assert len({h['id'] for h in hotels}) == len(hotels)
    assert len({h['code'] for h in hotels}) == len(hotels)
    base['hotels'] = hotels
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    assert cash == old_cash + 1367, (cash, old_cash)
    assert pts == old_pts + 1368, (pts, old_pts)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    base['generated_at'] = '2026-11-26'
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))

    eu = [h for h in hotels if h['region'] == '유럽']
    co = {}
    for h in eu:
        co[h['country']] = co.get(h['country'], 0) + 1
    print('tab11 hotels %d (신규 %d · 유럽 %d) · cells %d · cash %d · points %d'
          % (len(hotels), len(added), len(eu), base['counts']['cells'], cash, pts))
    print('유럽 국가:', ' · '.join('%s %d' % (k, v) for k, v in sorted(co.items(), key=lambda x: -x[1])))
    print('유럽 칸: %d · 현금 %d · 포인트 %d'
          % (len(eu) * 365, sum(h['cells']['rates'] for h in eu),
             sum(h['cells']['points'] for h in eu)))
    print('신규 ids %s ~ %s' % (added[0]['id'], added[-1]['id']))
    assert len(eu) == 71, len(eu)
    assert co['핀란드'] == 2 and co['그리스'] == 2 and co['튀르키예'] == 4, co
    assert len(co) == 18, co
    assert base['counts'] == {'hotels': 248, 'cells': 90520, 'cash': 79682, 'points': 77151}, base['counts']
    assert sum(h['cells']['rates'] for h in eu) == 22408
    assert sum(h['cells']['points'] for h in eu) == 21285


if __name__ == '__main__':
    main()
