#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P1 2차(마지막) 3곳(No.7 실측 · 2026-11-26) → data/app/tab11_ihg.json 병합

원자료: No.7(@no_7)이 전달한 `0-ihg_p1_batch2_3.json`
        (2026-11-26 공홈 직접 실측 · 2026-12-01~2027-11-30 365일)
        · 아테네 1(ATHHA 인터컨티넨탈 아테나이움 아테네 · 그리스)
        · 이스탄불 2(ISTHA 인터컨티넨탈 이스탄불 / ISTKI 비네트 컬렉션 뤼니옹 한 이스탄불 · 튀르키예)
        → P1 14곳(1차 8 + 2차 3 + 마지막 3) 완결

기존 tab11_ihg.json(229곳, i01~i229)은 값·순서·alsoIn 을 그대로 두고
뒤에 3곳을 i230~i232 로 붙여 232곳으로 만든다(유럽 52 → 55).

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
                   '2026-11-26-0511', 'received', '0-ihg_p1_batch2_3.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

BRAND_KO = {
    'IC': '인터컨티넨탈', 'VOCO': '보코', 'HIX': '홀리데이 인 익스프레스',
    'HI': '홀리데이 인', 'CP': '크라운 플라자', 'KIMPTON': '킴프턴',
    'INDIGO': '호텔 인디고', 'REGENT': '리젠트', 'VIGNETTE': '비네트 컬렉션',
    '인터컨티넨탈': '인터컨티넨탈', '킴프턴': '킴프턴', '킴튼': '킴프턴', '보코': '보코',
    '리젠트': '리젠트', '인디고': '호텔 인디고', '호텔 인디고': '호텔 인디고',
    '홀리데이 인 익스프레스': '홀리데이 인 익스프레스', '홀리데이 인': '홀리데이 인',
    '크라운 플라자': '크라운 플라자', '비네트 컬렉션': '비네트 컬렉션',
}
BRAND_KEY_FIX = {'KI': 'KIMPTON', 'IN': 'INDIGO'}
BRAND_PATH_FIX = {}   # 원자료 brand_path 가 기존 표기와 이미 같다


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def norm(s):
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 229, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30'], src['window']
    assert src['group'] == 'ihg-p1-batch2-3', src['group']

    old_codes = {h['code'] for h in old}
    old_ids = {h['id'] for h in old}
    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)

    n = 229
    added = []
    for h in src['hotels']:
        assert h['code'] not in old_codes, ('이미 있는 코드', h['code'])
        n += 1
        brand = BRAND_KO.get(h['brand']) or BRAND_KO.get(h['brand_code']) or h['brand']
        bkey = BRAND_KEY_FIX.get(h['brand_key'], h['brand_key'])
        bpath = BRAND_PATH_FIX.get(h['brand_path'], h['brand_path'])
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
            'brand_path': bpath,
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
    assert [h['code'] for h in added] == ['ATHHA', 'ISTHA', 'ISTKI']
    assert [h['id'] for h in added] == ['i230', 'i231', 'i232']
    assert [h['cells']['rates'] for h in added] == [343, 344, 344]
    assert [h['cells']['points'] for h in added] == [344, 342, 315]
    assert sum(h['cells']['rates'] for h in added) == 1031
    assert sum(h['cells']['points'] for h in added) == 1001
    assert len({h['id'] for h in added} | old_ids) == len(old) + len(added)
    assert {h['region'] for h in added} == {'유럽'}
    assert {h['country'] for h in added} == {'그리스', '튀르키예'}
    assert {h['brand_key'] for h in added} == {'IC', 'VIGNETTE'}

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

    hotels = old + added
    assert len({h['id'] for h in hotels}) == len(hotels)
    assert len({h['code'] for h in hotels}) == len(hotels)
    base['hotels'] = hotels
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    assert cash == old_cash + 1031, (cash, old_cash)
    assert pts == old_pts + 1001, (pts, old_pts)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))

    eu = [h for h in hotels if h['region'] == '유럽']
    co = {}
    for h in eu:
        co[h['country']] = co.get(h['country'], 0) + 1
    print('tab11 hotels %d (신규 %d · 유럽 %d) · cells %d · cash %d · points %d'
          % (len(hotels), len(added), len(eu), base['counts']['cells'], cash, pts))
    print('유럽 국가:', ' · '.join('%s %d' % (k, v) for k, v in sorted(co.items(), key=lambda x: -x[1])))
    print('신규 ids %s ~ %s' % (added[0]['id'], added[-1]['id']))
    assert len(eu) == 55, len(eu)
    assert base['counts']['cells'] == 84680, base['counts']


if __name__ == '__main__':
    main()
