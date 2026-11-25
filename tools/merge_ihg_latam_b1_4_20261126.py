#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 1차 4곳(No.7 실측 · 2026-11-26) → data/app/tab11_ihg.json 병합

원자료: No.7(@no_7)이 전달한 `0-ihg_latam_batch1_4.json`
        (2026-11-26 공홈 직접 실측 · 2026-12-01~2027-11-30 365일)
        · MEXHA 인터컨티넨탈 프레시덴테 멕시코시티 (멕시코 · 멕시코시티)
        · MEXMC 인터컨티넨탈 프레시덴테 미야나 (멕시코 · 멕시코시티)
        · MEXKM 킴프턴 엘 카스텔라르 폴랑코 (멕시코 · 멕시코시티)
        · MEXVC 보코 시우다드 데 멕시코 레포르마 (멕시코 · 멕시코시티)

기존 tab11_ihg.json(251곳, i01~i251)은 값·순서·alsoIn 을 그대로 두고
뒤에 4곳을 i252~i255 로 붙여 255곳으로 만든다(북미·중남미 57 → 61 · 멕시코 첫 지점).

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
                   '2026-11-26-0846', 'received', '0-ihg_latam_batch1_4.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

# 원자료 brand_code 는 IHG 공홈 코드가 아니라 브랜드 키 표기(KIMPTON·VOCO)라
# 이 탭의 기존 실측 관례(KI · VO)로 맞춘다.
BRAND_CODE_FIX = {'KIMPTON': 'KI', 'VOCO': 'VO'}


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def norm(s):
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 251, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30'], src['window']
    assert src['group'] == 'ihg-latam-batch1-4', src['group']

    old_codes = {h['code'] for h in old}
    old_ids = {h['id'] for h in old}
    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 80363 and old_pts == 77653, (old_cash, old_pts)

    n = 251
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
        if h['code'] == 'MEXKM':
            # 원자료는 병합자 판단 대기 문구를 남겼다 — 이 탭은 REKRR 과 같은 관례로
            # 달력 표출값을 그대로 두므로 판단 대기 표기를 걷고 관례를 밝힌다.
            assert '(No.2 판단 필요)' in note
            note = note.replace(
                '(No.2 판단 필요)',
                '(이 탭은 REKRR 과 같은 관례로 달력에 표시된 값을 그대로 유지합니다 — 주의문 참고)')
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
    assert [h['code'] for h in added] == ['MEXHA', 'MEXMC', 'MEXKM', 'MEXVC']
    assert [h['id'] for h in added] == ['i252', 'i253', 'i254', 'i255']
    assert [h['cells']['rates'] for h in added] == [334, 335, 344, 344]
    assert [h['cells']['points'] for h in added] == [334, 335, 296, 260]
    assert sum(h['cells']['rates'] for h in added) == 1357
    assert sum(h['cells']['points'] for h in added) == 1225
    assert len({h['id'] for h in added} | old_ids) == len(old) + len(added)
    assert {h['region'] for h in added} == {'북미·중남미'}
    assert {h['country'] for h in added} == {'멕시코'}
    assert {h['city'] for h in added} == {'멕시코시티'}
    assert {h['brand_key'] for h in added} == {'IC', 'KIMPTON', 'VOCO'}
    assert {h['brand_code'] for h in added} == {'IC', 'KI', 'VO'}
    assert {h['brand_path'] for h in added} == {'intercontinental', 'kimptonhotels', 'voco'}
    assert {h['brand'] for h in added} == {'인터컨티넨탈', '킴프턴', '보코'}
    for h in added:
        assert h['name'] and h['english'] and h['city']
        assert h['group'] == 'ihg'

    by = {h['code']: h for h in added}

    # ── 특이사항(브리프 3)이 원자료·값에 실제로 반영됐는지 확인 ──────────
    # MEXHA — 2026-12-03 · 2027-01-27 은 스탠더드 매진으로 클럽·스위트만 남아
    #           포인트가 통상 상한(120,000)을 넘는다.
    ha, hap = by['MEXHA']['rates']['$v'], by['MEXHA']['points']['$v']
    assert ha[2] == 1500000 and hap[2] == 241000, (ha[2], hap[2])          # 2026-12-03
    assert ha[57] == 1500000 and hap[57] == 278000, (ha[57], hap[57])      # 2027-01-27
    assert '241,000' in by['MEXHA']['note'] and '278,000' in by['MEXHA']['note']
    assert '클럽/스위트' in by['MEXHA']['note']
    # 2026-12-02 · 2026-12-31 매진, 2027-10-24~10-31(죽은자의 날) · 11-10~30(예약창) null
    assert [i for i, v in enumerate(ha) if v is None] == \
        [1, 30] + list(range(327, 335)) + list(range(344, 365))
    assert [i for i, v in enumerate(hap) if v is None] == \
        [i for i, v in enumerate(ha) if v is None]
    assert '죽은자의 날' in by['MEXHA']['note']

    # MEXMC — 2027-10-24~11-01(죽은자의 날 연휴) 매진 · 11-02 1.8M 급등
    mc = by['MEXMC']['rates']['$v']
    assert mc[336] == 1800000, mc[336]                                   # 2027-11-02
    assert [i for i, v in enumerate(mc) if v is None] == \
        list(range(327, 336)) + list(range(344, 365))

    # MEXKM — 12-01·12-02 달력 셀 77.4K·82.5K 는 Points & Cash 최저 포인트분
    km, kmp = by['MEXKM']['rates']['$v'], by['MEXKM']['points']['$v']
    assert kmp[0] == 77400 and kmp[1] == 82500
    assert '82,450' in by['MEXKM']['note'] and '97,000' in by['MEXKM']['note']
    assert '77,350' in by['MEXKM']['note'] and '91,000' in by['MEXKM']['note']
    assert 'Points & Cash' in by['MEXKM']['note']
    assert '(No.2 판단 필요)' not in by['MEXKM']['note']
    assert [i for i, v in enumerate(km) if v is None] == list(range(344, 365))
    assert len([i for i, v in enumerate(kmp) if v is None]) == 69

    # MEXVC — 2026년 12월 리워드 재고가 5일(12-06 · 12-13 · 12-16 · 12-23 · 12-30)만
    vc, vcp = by['MEXVC']['rates']['$v'], by['MEXVC']['points']['$v']
    dec = [i for i in range(31) if vcp[i] is not None]
    assert dec == [5, 12, 15, 22, 29], dec
    assert len([i for i, v in enumerate(vcp) if v is None]) == 105
    assert [i for i, v in enumerate(vc) if v is None] == list(range(344, 365))
    assert '2026년 12월은 31일 중 5일' in by['MEXVC']['note']
    assert '중남미 배치에서 가장 얇다' in by['MEXVC']['note']

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
                if e and (e[:8] in norm(d.get('english')) or norm(d.get('english'))[:8] in e)]
        print('   근사 후보(영문 앞 8자):', h['code'], near)

    # ── 기존 IHG 255곳 안에 같은 도시·같은 국가가 있는지 ──────────────────
    for h in added:
        same_city = [(x['id'], x['code'], x['name']) for x in old if x['city'] == h['city']]
        print('   같은 도시 기존:', h['code'], h['city'], same_city)
        assert not same_city
    assert not [x for x in old if x['country'] == '멕시코']
    print('   같은 국가(멕시코) 기존: 0곳 — 이 탭의 첫 멕시코 지점')

    hotels = old + added
    assert len({h['id'] for h in hotels}) == len(hotels)
    assert len({h['code'] for h in hotels}) == len(hotels)
    base['hotels'] = hotels
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    assert cash == old_cash + 1357, (cash, old_cash)
    assert pts == old_pts + 1225, (pts, old_pts)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    base['generated_at'] = '2026-11-26'
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))

    na = [h for h in hotels if h['region'] == '북미·중남미']
    co = {}
    for h in na:
        co[h['country']] = co.get(h['country'], 0) + 1
    print('tab11 hotels %d (신규 %d · 북미·중남미 %d)' % (len(hotels), len(added), len(na)))
    print('북미·중남미 국가:', co)
    print('북미·중남미 칸: %d · 현금 %d · 포인트 %d'
          % (len(na) * 365, sum(h['cells']['rates'] for h in na),
             sum(h['cells']['points'] for h in na)))
    print('신규 ids %s ~ %s' % (added[0]['id'], added[-1]['id']))
    assert len(na) == 61, len(na)
    assert co == {'미국': 52, '캐나다': 5, '멕시코': 4}, co
    assert base['counts'] == {'hotels': 255, 'cells': 93075, 'cash': 81720, 'points': 78878}, \
        base['counts']
    assert sum(h['cells']['rates'] for h in na) == 19898
    assert sum(h['cells']['points'] for h in na) == 19674


if __name__ == '__main__':
    main()
