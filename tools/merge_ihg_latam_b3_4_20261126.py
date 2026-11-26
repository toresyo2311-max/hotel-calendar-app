#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 3차 4곳(No.7 실측 · 2026-11-26) → data/app/tab11_ihg.json 병합

원자료: No.7(@no_7)이 전달한 `0-ihg_latam_batch3_4.json`
        (2026-11-26 공홈 직접 실측 · 2026-12-01~2027-11-30 365일)
        · SCLHA 인터컨티넨탈 산티아고 (칠레 · 산티아고) — 칠레 첫 지점
        · LIMHA 인터컨티넨탈 레알 리마 미라플로레스 (페루 · 리마) — 페루 첫 지점
        · LIMMP 비네트 컬렉션 소우마 호텔 (페루 · 리마)
        · LIMMD 호텔 인디고 리마 미라플로레스 (페루 · 리마)

기존 tab11_ihg.json(259곳, i01~i259)은 값·순서·alsoIn 을 그대로 두고
뒤에 4곳을 i260~i263 으로 붙여 263곳으로 만든다(북미·중남미 65 → 69).
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', 'a03363f4-no71', 'pickle',
                   '2026-11-26-1051', 'received', '0-ihg_latam_batch3_4.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

# 원자료의 호텔 인디고 brand_code 는 IHG 공홈 코드(IN)가 아니라 브랜드 키 표기(INDIGO)라
# 이 탭의 기존 실측 관례(IN)로 맞춘다. 비네트 컬렉션은 기존 관례와 같은 VIGNETTE 다.
BRAND_CODE_FIX = {'INDIGO': 'IN'}


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
    assert len(old) == 259, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30'], src['window']
    assert src['group'] == 'ihg-latam-batch3-4', src['group']
    assert src['generated_at'] == '2026-11-26'

    old_codes = {h['code'] for h in old}
    old_ids = {h['id'] for h in old}
    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 82966 and old_pts == 79855, (old_cash, old_pts)
    assert len([h for h in old if h['region'] == '북미·중남미']) == 65

    n = 259
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
    assert [h['code'] for h in added] == ['SCLHA', 'LIMHA', 'LIMMP', 'LIMMD']
    assert [h['id'] for h in added] == ['i260', 'i261', 'i262', 'i263']
    assert [h['cells']['rates'] for h in added] == [332, 342, 344, 344]
    assert [h['cells']['points'] for h in added] == [326, 342, 344, 319]
    assert sum(h['cells']['rates'] for h in added) == 1362
    assert sum(h['cells']['points'] for h in added) == 1331
    assert len({h['id'] for h in added} | old_ids) == len(old) + len(added)
    assert {h['region'] for h in added} == {'북미·중남미'}
    assert {h['country'] for h in added} == {'칠레', '페루'}
    assert {h['city'] for h in added} == {'산티아고', '리마'}
    assert [h['brand_key'] for h in added] == ['IC', 'IC', 'VIGNETTE', 'INDIGO']
    assert [h['brand_code'] for h in added] == ['IC', 'IC', 'VIGNETTE', 'IN']
    assert [h['brand_path'] for h in added] == ['intercontinental', 'intercontinental',
                                                'vignettecollection', 'hotelindigo']
    assert [h['brand'] for h in added] == ['인터컨티넨탈', '인터컨티넨탈', '비네트 컬렉션', '호텔 인디고']
    for h in added:
        assert h['name'] and h['english'] and h['city']
        assert h['group'] == 'ihg'
        assert 'alsoIn' not in h

    by = {h['code']: h for h in added}
    W = list(range(344, 365))            # 2027-11-10~11-30 (예약창 밖 21일)

    # ── 특이사항(브리프 3)이 원자료·값에 실제로 반영됐는지 확인 ──────────
    # SCLHA — 칠레 IVA 19% 포함 세후가 · 부활절 주간 12일 현금·포인트 동시 매진
    sc, scp = by['SCLHA']['rates']['$v'], by['SCLHA']['points']['$v']
    assert nulls(sc) == [124, 125, 126, 131, 132, 133, 134, 135, 139, 140, 141, 142] + W
    assert nulls(scp) == [1, 2, 8, 14, 73] + [124, 125, 126, 131, 132, 133, 134, 135,
                                             139, 140, 141, 142] + [327] + W
    assert sc[0] == 242700 and scp[0] == 30000
    assert min(v for v in sc if v) == 154400 and max(v for v in sc if v) == 667800
    assert min(v for v in scp if v) == 21000 and max(v for v in scp if v) == 53000
    assert sc[1] == 667800 and scp[1] is None          # 2026-12-02 현금 최고 · 리워드 없음
    assert 'IVA 19%' in by['SCLHA']['note'] and 'No rooms available' in by['SCLHA']['note']

    # LIMHA — 10% 서비스차지 + 18% IGV 포함 세후가 · 현금·포인트 null 집합 동일
    lc, lcp = by['LIMHA']['rates']['$v'], by['LIMHA']['points']['$v']
    assert nulls(lc) == nulls(lcp) == [52, 53] + W
    assert lc[0] == 458800 and lcp[0] == 49000
    assert min(v for v in lc if v) == 321400 and max(v for v in lc if v) == 653500
    assert min(v for v in lcp if v) == 40000 and max(v for v in lcp if v) == 109000
    assert '10% Service Charge' in by['LIMHA']['note'] and 'IGV' in by['LIMHA']['note']

    # LIMMP — 날짜별 최저가에 Early Saver Member Exclusive(사전예약·환불불가)가 들어 있음
    mc, mcp = by['LIMMP']['rates']['$v'], by['LIMMP']['points']['$v']
    assert nulls(mc) == nulls(mcp) == W
    assert mc[0] == 320300 and mcp[0] == 54000
    assert min(v for v in mc if v) == 174500 and max(v for v in mc if v) == 447300
    assert min(v for v in mcp if v) == 25000 and max(v for v in mcp if v) == 57000
    assert 'Early Saver Member Exclusive' in by['LIMMP']['note']

    # LIMMD — 2026년 12월 현금 31일 전부 · 리워드는 19일만 (포인트만 비는 날 25일)
    dc, dcp = by['LIMMD']['rates']['$v'], by['LIMMD']['points']['$v']
    assert nulls(dc) == W
    assert len(nulls(dcp)) == 46
    assert len([x for x in nulls(dcp) if x not in set(W)]) == 25
    assert sum(1 for v in dcp[:31] if v is not None) == 19
    assert sum(1 for v in dc[:31] if v is not None) == 31
    assert dc[0] == 303500 and dcp[0] is None
    assert min(v for v in dc if v) == 207900 and max(v for v in dc if v) == 512400
    assert min(v for v in dcp if v) == 29000 and max(v for v in dcp if v) == 53000
    assert '2026년 12월은 현금이 31일 전부 판매되는 반면 리워드는 19일만' in by['LIMMD']['note']

    # 네 곳 모두 마지막 값 있는 날이 2027-11-09 (예약창 밖 11-10~30)
    for h in added:
        for kind in ('rates', 'points'):
            v = h[kind]['$v']
            last = max(i for i, x in enumerate(v) if x is not None)
            assert last == 343, (h['code'], kind, last)

    # ── ① 호텔럭스 161곳 전수 대조(코드·영문명·국문명·도시) ──────────────
    # ① 탭과 ⑤ 탭 모두 좌표 필드를 갖고 있지 않아(스키마에 lat/lng 없음) 좌표 대조는
    # 성립하지 않는다 — 코드·영문명·국문명·도시로 전수 대조하고, 같은 도시까지 본다.
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

    # ── 기존 IHG 259곳 안에 같은 도시·같은 이름이 있는지 ──────────────────
    for h in added:
        same_city = [(x['id'], x['code'], x['name']) for x in old if x['city'] == h['city']]
        print('   같은 도시 기존:', h['code'], h['city'], same_city)
        assert not same_city, (h['code'], same_city)
        same_name = [x['id'] for x in old if norm(x['name']) == norm(h['name'])]
        assert not same_name, (h['code'], same_name)
    assert not [x for x in old if x['country'] in ('칠레', '페루')]
    print('   칠레 · 페루 기존: 0곳 — 이 탭의 첫 지점')

    hotels = old + added
    assert len({h['id'] for h in hotels}) == len(hotels)
    assert len({h['code'] for h in hotels}) == len(hotels)
    base['hotels'] = hotels
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    assert cash == old_cash + 1362, (cash, old_cash)
    assert pts == old_pts + 1331, (pts, old_pts)
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
    assert len(na) == 69, len(na)
    assert co == {'미국': 52, '캐나다': 5, '멕시코': 6, '브라질': 1, '아르헨티나': 1,
                  '칠레': 1, '페루': 3}, co
    assert ci['산티아고'] == 1 and ci['리마'] == 3
    assert ci['칸쿤'] == 2 and ci['멕시코시티'] == 4 and ci['상파울루'] == 1
    assert base['counts'] == {'hotels': 263, 'cells': 95995, 'cash': 84328, 'points': 81186}, \
        base['counts']
    assert sum(h['cells']['rates'] for h in na) == 22506
    assert sum(h['cells']['points'] for h in na) == 21982
    print('OK — 259→263곳 · 북미·중남미 65→69 · 95,995칸(현금 84,328 · 포인트 81,186)')


if __name__ == '__main__':
    main()
