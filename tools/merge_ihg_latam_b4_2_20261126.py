#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 4차 2곳(No.7 실측 · 2026-11-26) → data/app/tab11_ihg.json 병합

원자료: No.7(@no_7)이 전달한 `0-ihg_latam_batch4_2.json`
        (2026-11-26 공홈 직접 실측 · 2026-12-01~2027-11-30 365일)
        · LMAMI 크라운 플라자 리마 미라플로레스 (페루 · 리마)
        · PCYHA 인터컨티넨탈 미라마르 파나마 (파나마 · 파나마시티) — 파나마 첫 지점

기존 tab11_ihg.json(263곳, i01~i263)은 값·순서·alsoIn 을 그대로 두고
뒤에 2곳을 i264~i265 으로 붙여 265곳으로 만든다(북미·중남미 69 → 71).
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', 'a03363f4-no71', 'pickle',
                   '2026-11-26-1113', 'received', '0-ihg_latam_batch4_2.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def nulls(v):
    return [i for i, x in enumerate(v) if x is None]


def norm(s):
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 263, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30'], src['window']
    assert src['group'] == 'ihg-latam-batch4-2', src['group']
    assert src['generated_at'] == '2026-11-26'

    old_codes = {h['code'] for h in old}
    old_ids = {h['id'] for h in old}
    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 84328 and old_pts == 81186, (old_cash, old_pts)
    assert len([h for h in old if h['region'] == '북미·중남미']) == 69

    n = 263
    added = []
    for h in src['hotels']:
        assert h['code'] not in old_codes, ('이미 있는 코드', h['code'])
        n += 1
        rc = numeric(h['rates']['$v'])
        pc = numeric(h['points']['$v'])
        assert rc == h['cells']['rates'], (h['code'], rc, h['cells'])
        assert pc == h['cells']['points'], (h['code'], pc, h['cells'])
        assert len(h['rates']['$v']) == 365 and len(h['points']['$v']) == 365
        assert h['rates']['$d'] == h['points']['$d'] == '2026-12-01'
        note = h['note']
        assert '판단 필요' not in note, h['code']
        rec = {
            'id': 'i%02d' % n,
            'group': 'ihg',
            'code': h['code'],
            'brand': h['brand'],
            'brand_code': h['brand_code'],
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

    assert len(added) == 2
    assert [h['code'] for h in added] == ['LMAMI', 'PCYHA']
    assert [h['id'] for h in added] == ['i264', 'i265']
    assert [h['cells']['rates'] for h in added] == [344, 343]
    assert [h['cells']['points'] for h in added] == [342, 313]
    assert sum(h['cells']['rates'] for h in added) == 687
    assert sum(h['cells']['points'] for h in added) == 655
    assert len({h['id'] for h in added} | old_ids) == len(old) + len(added)
    assert {h['region'] for h in added} == {'북미·중남미'}
    assert [h['country'] for h in added] == ['페루', '파나마']
    assert [h['city'] for h in added] == ['리마', '파나마시티']
    assert [h['brand'] for h in added] == ['크라운 플라자', '인터컨티넨탈']
    assert [h['brand_code'] for h in added] == ['CP', 'IC']
    assert [h['brand_key'] for h in added] == ['CP', 'IC']
    assert [h['brand_path'] for h in added] == ['crowneplaza', 'intercontinental']
    for h in added:
        assert h['name'] and h['english'] and h['city']
        assert h['group'] == 'ihg'
        assert 'alsoIn' not in h

    by = {h['code']: h for h in added}
    W = list(range(344, 365))            # 2027-11-10~11-30 (예약창 밖 21일)

    # ── 특이사항(브리프 3)이 원자료·값에 실제로 반영됐는지 확인 ──────────
    # LMAMI — 현금 344일 / 포인트 342일 · 포인트 모드에 10% 서비스차지 별도
    mc, mcp = by['LMAMI']['rates']['$v'], by['LMAMI']['points']['$v']
    assert nulls(mc) == W
    assert nulls(mcp) == [0, 26] + W
    assert mc[0] == 246600 and mcp[0] is None
    assert min(v for v in mc if v) == 183300 and max(v for v in mc if v) == 358400
    assert min(v for v in mcp if v) == 20000 and max(v for v in mcp if v) == 40000
    assert mc[26] == 202800 and mcp[26] is None        # 2026-12-27 현금만 판매
    assert mc[344 - 1] == 306500 and mcp[344 - 1] == 32000   # 2027-11-09 마지막 값
    assert 'Excludes 10% Service Charge' in by['LMAMI']['note']
    assert 'Includes taxes and fees' in by['LMAMI']['note']
    assert '2026-12-01' in by['LMAMI']['note'] and '2026-12-27' in by['LMAMI']['note']

    # PCYHA — 현금 343일 / 포인트 313일 · 2026-12-26 달력 견적 vs 요금카드 최저가 차이
    pc, pcp = by['PCYHA']['rates']['$v'], by['PCYHA']['points']['$v']
    assert nulls(pc) == [10] + W
    assert len(nulls(pcp)) == 52
    assert nulls(pcp)[:5] == [10, 25, 28, 29, 30]
    assert pc[0] == 342900 and pcp[0] == 53000
    assert pc[10] is None and pcp[10] is None          # 2026-12-11 하루 공백
    assert pc[25] == 356400 and pcp[25] is None        # 2026-12-26 달력 견적
    assert min(v for v in pc if v) == 271100 and max(v for v in pc if v) == 799800
    assert min(v for v in pcp if v) == 39000 and max(v for v in pcp if v) == 86000
    assert pc[344 - 1] == 353400 and pcp[344 - 1] == 46000   # 2027-11-09 마지막 값
    assert '356,431' in by['PCYHA']['note'] and '383,994' in by['PCYHA']['note']
    assert '2.7만원' in by['PCYHA']['note'] or '27' in by['PCYHA']['note']
    assert 'Includes taxes and fees' in by['PCYHA']['note']
    assert '2026-12-11' in by['PCYHA']['note']

    # 두 곳 모두 마지막 값 있는 날이 2027-11-09 (예약창 밖 11-10~30)
    for h in added:
        for kind in ('rates', 'points'):
            v = h[kind]['$v']
            last = max(i for i, x in enumerate(v) if x is not None)
            assert last == 343, (h['code'], kind, last)

    # ── ① 호텔럭스 161곳 전수 대조(코드·영문명·국문명·도시) ──────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
    assert len(rows) == 161, len(rows)
    assert not any(k in cols for k in ('lat', 'lng', 'latitude', 'longitude')), cols
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
    city_hits = [(h['code'], h['city']) for h in added if h['city'] in lux_cities]
    assert not hits, hits
    assert not city_hits, city_hits
    print('① 호텔럭스 161곳 대조 — 코드·영문명·국문명·도시 겹침 0곳 · alsoIn 추가 0쌍')
    for h in added:
        e = norm(h['english'])
        near = [d['id'] for d in rows
                if e and (e[:8] in norm(d.get('english')) or norm(d.get('english'))[:8] in e)]
        print('   근사 후보(영문 앞 8자):', h['code'], near)

    # ── 기존 IHG 263곳 안에 같은 이름이 있는지(같은 도시는 리마 4곳 허용) ──
    for h in added:
        same_city = [(x['id'], x['code'], x['name']) for x in old if x['city'] == h['city']]
        print('   같은 도시 기존:', h['code'], h['city'], same_city)
        same_name = [x['id'] for x in old if norm(x['name']) == norm(h['name'])]
        assert not same_name, (h['code'], same_name)
    assert not [x for x in old if x['country'] == '파나마']
    print('   파나마 기존: 0곳 — 이 탭의 첫 지점 / 리마는 기존 3곳 + 신규 1곳 = 4곳')

    hotels = old + added
    assert len({h['id'] for h in hotels}) == len(hotels)
    assert len({h['code'] for h in hotels}) == len(hotels)
    base['hotels'] = hotels
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    assert cash == old_cash + 687, (cash, old_cash)
    assert pts == old_pts + 655, (pts, old_pts)
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
    assert len(na) == 71, len(na)
    assert co == {'미국': 52, '캐나다': 5, '멕시코': 6, '브라질': 1, '아르헨티나': 1,
                  '칠레': 1, '페루': 4, '파나마': 1}, co
    assert ci['리마'] == 4 and ci['파나마시티'] == 1
    assert ci['산티아고'] == 1 and ci['칸쿤'] == 2 and ci['멕시코시티'] == 4
    assert base['counts'] == {'hotels': 265, 'cells': 96725, 'cash': 85015, 'points': 81841}, \
        base['counts']
    assert sum(h['cells']['rates'] for h in na) == 23193
    assert sum(h['cells']['points'] for h in na) == 22637
    print('OK — 263→265곳 · 북미·중남미 69→71 · 96,725칸(현금 85,015 · 포인트 81,841)')


if __name__ == '__main__':
    main()
