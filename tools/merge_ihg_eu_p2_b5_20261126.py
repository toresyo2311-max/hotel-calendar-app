#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P2 5차(마지막) 3곳(No.7 실측 · 2026-11-26) → data/app/tab11_ihg.json 병합

원자료: No.7(@no_7)이 전달한 `0-ihg_p2_batch5_3.json`
        (2026-11-26 공홈 직접 실측 · 2026-12-01~2027-11-30 365일)
        · NAVNC 크라운 플라자 카파도키아 네브셰히르 (튀르키예 · 카파도키아)
        · WAWFN 비네트 컬렉션 플라네 바르샤바 (폴란드 · 바르샤바 — WorldHotels 운영 중,
          IHG 채널 판매 미개시(2027년 통합 예정)라 현금·포인트 365일 전부 null)
        · REKRR 캔들우드 스위트 레이캬비크 (아이슬란드 · 레이캬비크 — 리워드 재고가 얇아
          포인트 163일만 값이 있음)

기존 tab11_ihg.json(248곳, i01~i248)은 값·순서·alsoIn 을 그대로 두고
뒤에 3곳을 i249~i251 로 붙여 251곳으로 만든다(유럽 71 → 74 · 18 → 20개국).

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
                   '2026-11-26-0805', 'received', '0-ihg_p2_batch5_3.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

BRAND_KO = {
    'IC': '인터컨티넨탈', 'VOCO': '보코', 'HIX': '홀리데이 인 익스프레스',
    'HI': '홀리데이 인', 'CP': '크라운 플라자', 'KIMPTON': '킴프턴',
    'INDIGO': '호텔 인디고', 'REGENT': '리젠트', 'VIGNETTE': '비네트 컬렉션',
    'CW': '캔들우드 스위트',
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
    assert len(old) == 248, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30'], src['window']
    assert src['group'] == 'ihg-p2-batch5-3', src['group']

    old_codes = {h['code'] for h in old}
    old_ids = {h['id'] for h in old}
    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 79682 and old_pts == 77151, (old_cash, old_pts)

    n = 248
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

    assert len(added) == 3
    assert [h['code'] for h in added] == ['NAVNC', 'WAWFN', 'REKRR']
    assert [h['id'] for h in added] == ['i249', 'i250', 'i251']
    assert [h['cells']['rates'] for h in added] == [339, 0, 342]
    assert [h['cells']['points'] for h in added] == [339, 0, 163]
    assert sum(h['cells']['rates'] for h in added) == 681
    assert sum(h['cells']['points'] for h in added) == 502
    assert len({h['id'] for h in added} | old_ids) == len(old) + len(added)
    assert {h['region'] for h in added} == {'유럽'}
    assert {h['country'] for h in added} == {'튀르키예', '폴란드', '아이슬란드'}
    assert {h['brand_key'] for h in added} == {'CP', 'VIGNETTE', 'CW'}
    assert {h['brand_path'] for h in added} == {'crowneplaza', 'vignettecollection', 'candlewood'}
    assert {h['city'] for h in added} == {'카파도키아', '바르샤바', '레이캬비크'}
    assert {h['brand'] for h in added} == {'크라운 플라자', '비네트 컬렉션', '캔들우드 스위트'}
    for h in added:
        assert h['name'] and h['english'] and h['city']
        assert h['group'] == 'ihg'

    by = {h['code']: h for h in added}
    # NAVNC — null 26일(2027-02-06 · 04-07 · 04-20 · 05-18 · 05-24~25 · 11-11~30)
    nav = by['NAVNC']['rates']['$v']
    navp = by['NAVNC']['points']['$v']
    nulls = [i for i, v in enumerate(nav) if v is None]
    assert len(nulls) == 26 and nulls[-1] == 364, len(nulls)
    assert [i for i, v in enumerate(navp) if v is None] == nulls
    assert nav[33] == 82600 and nav[53] == 390800, (nav[33], nav[53])
    assert nav[67] is None and nav[343] is not None, (nav[67], nav[343])
    # WAWFN — 판매 미개시: 365일 전부 null(0칸)
    assert by['WAWFN']['rates']['$v'] == [None] * 365
    assert by['WAWFN']['points']['$v'] == [None] * 365
    # REKRR — 현금 null 23일 · 포인트 null 202일(리워드 재고 얇음)
    rek = by['REKRR']['rates']['$v']
    rekp = by['REKRR']['points']['$v']
    assert len([i for i, v in enumerate(rek) if v is None]) == 23
    assert len([i for i, v in enumerate(rekp) if v is None]) == 202
    assert rek[30] is None and rek[344] is None and rekp[344] is None
    assert rekp[12] == 49000, rekp[12]

    # 원자료 note 주의문 — WAWFN 미개시 · REKRR 리워드 재고 · NAVNC 예약창
    assert 'WorldHotels' in by['WAWFN']['note'] and '2027년 예정' in by['WAWFN']['note']
    assert '포인트 163일' in by['REKRR']['note']
    assert 'Rooms cannot be booked this far in advance' in by['NAVNC']['note']

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
    print('   같은 국가 기존:', {c: [(x['id'], x['code'], x['city']) for x in old
                                    if x['country'] == c] for c in ('튀르키예', '폴란드', '아이슬란드')})

    hotels = old + added
    assert len({h['id'] for h in hotels}) == len(hotels)
    assert len({h['code'] for h in hotels}) == len(hotels)
    base['hotels'] = hotels
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    assert cash == old_cash + 681, (cash, old_cash)
    assert pts == old_pts + 502, (pts, old_pts)
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
    assert len(eu) == 74, len(eu)
    assert co['튀르키예'] == 5 and co['폴란드'] == 1 and co['아이슬란드'] == 1, co
    assert len(co) == 20, co
    assert base['counts'] == {'hotels': 251, 'cells': 91615, 'cash': 80363, 'points': 77653}, base['counts']
    assert sum(h['cells']['rates'] for h in eu) == 23089
    assert sum(h['cells']['points'] for h in eu) == 21787


if __name__ == '__main__':
    main()
