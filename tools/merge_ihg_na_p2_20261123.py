#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 북미·중남미 P2 30곳 → data/app/tab11_ihg.json 병합 (+ ① 호텔럭스 전수 대조)

원자료: 6번(@jin_6) 실측 `0-ihg-global-no6-p2-30.json`
        (2026-11-23 06:19 KST · 2026-12-01~2027-11-30 365일 · 현금 9,833칸 · 포인트 9,778칸)

원자료 상단 `source` 문자열이 "No.6 P1 27곳"으로 오기돼 있으나 이 파일은 **P2 30곳**이다
(hotels 30 · counts.cells 21,900 = 30 × 365 로 확인). 30곳의 호텔별 `source`·`note` 는
원자료 문구를 그대로 옮긴다(Amenity Fee · CAD 전환 · 1박 판매 제한 등 주의문 보존).

기존 tab11_ihg.json(아시아·오세아니아 72 + 유럽 41 + 북미·중남미 27 = 140곳, i01~i140)은
값·순서·alsoIn 을 그대로 두고 뒤에 30곳을 i141~i170으로 붙인다
(미국 26 — 뉴욕 3 · 마이애미 3 · 로스앤젤레스 2 · 샌프란시스코 2 · 샌디에이고 2 · 시카고 2 ·
 올랜도 2 · 라스베이거스 2 · 워싱턴DC 2 · 덴버 2 · 뉴올리언스 2 · 보스턴 · 시애틀 /
 캐나다 4 — 토론토 · 밴쿠버 2 · 몬트리올).

스키마는 기존과 똑같이 맞춘다:
  · brand      — 화면 태그·필터용 한글 브랜드명(자료의 '인디고'→'호텔 인디고', '이븐'→'이븐 호텔')
  · brand_code — 예약 주소(qSHBrC)에 들어가는 사이트 브랜드 코드
                 (자료의 brand_code/brand_key 표기가 행마다 뒤바뀌어 있어 브랜드 경로로 정규화:
                  KI · IN · CP · HI · HX · VO · VIGNETTE · VN)
  · brand_key  — 기존 표기(KIMPTON · INDIGO · CP · HI · HIX · VOCO · VIGNETTE · EVEN)
  · rates/points — {$d, $v} 압축 열, 값 없는 칸은 null(보간 금지)
  · cells      — {"rates": n, "points": n}

① 호텔럭스(tab1_vip.json 161곳) 전수 대조 — 코드·영문명·국문명·도시를 정규화해 맞춘 결과
겹치는 호텔 0곳(① 탭 161곳은 뉴욕 41 · 싱가포르 36 · 도쿄 35 · 서울 16 · 시드니 12 · 방콕 5 ·
상하이 4 · 다낭 3 · 나트랑 3 · 부산 2 · 후쿠오카 2 · 오사카 2 로, 이번 30곳의 도시 가운데 뉴욕
말고는 ① 탭에 지점이 없고 뉴욕 3곳도 ① 탭 뉴욕 41곳과 이름·코드가 모두 다르다). 기존 9쌍은 그대로 둔다.
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', 'b61af69f-leehanjin7', 'pickle',
                   '2026-11-23-0619', 'received', '0-ihg-global-no6-p2-30.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

# 브랜드 경로 → (한글 브랜드명, qSHBrC 코드, brand_key) — 기존 140곳 표기에 맞춘다
BRAND = {
    'kimptonhotels': ('킴프턴', 'KI', 'KIMPTON'),
    'hotelindigo': ('호텔 인디고', 'IN', 'INDIGO'),
    'crowneplaza': ('크라운 플라자', 'CP', 'CP'),
    'holidayinn': ('홀리데이 인', 'HI', 'HI'),
    'holidayinnexpress': ('홀리데이 인 익스프레스', 'HX', 'HIX'),
    'vignettecollection': ('비네트 컬렉션', 'VIGNETTE', 'VIGNETTE'),
    'voco': ('보코', 'VO', 'VOCO'),
    'evenhotels': ('이븐 호텔', 'VN', 'EVEN'),
}

# 기존 9쌍 — 이번 30곳은 겹침 0
KEEP_PAIRS = {
    'i01': 'h27', 'i12': 'h61', 'i13': 'h64', 'i48': 'h15', 'i54': 'h20',
    'i63': 'h115', 'i65': 'h118', 'i99': 'h122', 'i100': 'h152',
}

EXPECT_ORDER = ['NYCAA', 'NYCOS', 'NYCTT', 'LAXWP', 'LAXWM', 'SFOFW', 'SFOSH', 'SANIS',
                'SANCP', 'CHIWP', 'CHISH', 'MIAPA', 'MIANI', 'MIASS', 'MCOOA', 'MCOPP',
                'LASTA', 'LASRR', 'WDCRG', 'WASVC', 'BOSFS', 'SEADT', 'YYZBS', 'YVRDT',
                'YVRBW', 'YULCA', 'MSYPS', 'MSYRL', 'DENDM', 'DENWS']


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def norm(s):
    """코드·이름 대조용 정규화 — 소문자, 한글/영문/숫자만 남긴다."""
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 140, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30']
    # 원자료 상단 source 는 "No.6 P1 27곳" 오기 — 실제는 P2 30곳(건수로 확인하고 문구는 쓰지 않는다)
    assert src['counts'] == {'hotels': 30, 'cells': 21900, 'cash': 9833, 'points': 9778}, src['counts']
    assert 'P1 27' in src['source'], src['source']

    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 44868 and old_pts == 42665, (old_cash, old_pts)
    old_alsoin = {h['id']: h.get('alsoIn') for h in old if h.get('alsoIn')}
    assert old_alsoin == KEEP_PAIRS, old_alsoin
    old_ids = [h['id'] for h in old]
    assert old_ids[0] == 'i01' and old_ids[-1] == 'i140'

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
        assert h['region'] == '북미·중남미', h['region']
        assert h['country'] in ('미국', '캐나다'), h['country']
        assert h['rates']['$d'] == '2026-12-01' and h['points']['$d'] == '2026-12-01'
        assert len(h['rates']['$v']) == 365 and len(h['points']['$v']) == 365
        rc = numeric(h['rates']['$v'])
        pc = numeric(h['points']['$v'])
        assert rc == h['cells']['rates'] and pc == h['cells']['points'], (h['code'], rc, pc, h['cells'])
        assert (h.get('note') or ''), h['code']          # 호텔별 주의문 보존(빈 곳 없음)
        rec = {
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
            'rates': h['rates'],
            'points': h['points'],
            'note': h['note'],
            'source': h.get('source') or '',
            'cells': {'rates': rc, 'points': pc},
        }
        added.append(rec)

    assert len(added) == 30
    assert added[0]['id'] == 'i141' and added[-1]['id'] == 'i170'
    assert [x['code'] for x in added] == EXPECT_ORDER, [x['code'] for x in added]
    assert sum(h['cells']['rates'] for h in added) == 9833
    assert sum(h['cells']['points'] for h in added) == 9778
    assert sum(1 for h in added if h['country'] == '미국') == 26
    assert sum(1 for h in added if h['country'] == '캐나다') == 4
    assert [x['id'] for x in added if x['code'] == 'YULCA'] == ['i166']

    # 원자료 특이사항이 note 에 그대로 실렸는지
    notes = {x['code']: x['note'] for x in added}
    assert '36 USD Amenity Fee' in notes['NYCOS']
    assert '2027-09-01' in notes['MSYPS'] and '판매' in notes['MSYPS']
    assert '최소숙박 2박' in notes['YULCA']
    assert 'CAD' in notes['YVRDT'] and 'CAD' in notes['YVRBW'] and 'CAD' in notes['YULCA']
    assert '2박' in notes['YULCA']

    hotels = old + added
    base['hotels'] = hotels
    base['generated_at'] = '2026-11-23'
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    assert cash == old_cash + 9833 == 54701, cash
    assert pts == old_pts + 9778 == 52443, pts
    assert base['counts']['cells'] == 170 * 365 == 62050
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))

    regions = {}
    cities = {}
    brands = {}
    for h in hotels:
        regions[h['region']] = regions.get(h['region'], 0) + 1
        cities[h['city']] = cities.get(h['city'], 0) + 1
        brands[h['brand']] = brands.get(h['brand'], 0) + 1
    asia = len(hotels) - regions.get('유럽', 0) - regions.get('북미·중남미', 0)
    print('tab11 hotels %d (신규 %d) · 아시아·오세아니아 %d · 유럽 %d · 북미·중남미 %d'
          % (len(hotels), len(added), asia, regions.get('유럽'), regions.get('북미·중남미')))
    print('cells %d · cash %d · points %d (신규 현금 %d · 포인트 %d)'
          % (base['counts']['cells'], cash, pts, 9833, 9778))
    print('브랜드:', dict(sorted(brands.items(), key=lambda kv: -kv[1])))
    print('북미·중남미 도시:', dict(sorted(cities.items(), key=lambda kv: -kv[1])))

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
    print('① 호텔럭스 겹침(신규 30곳):', hits if hits else '없음')
    assert not hits, hits
    print('① 탭 도시 구성:', {k: len(v) for k, v in sorted(lux_cities.items(), key=lambda kv: -len(kv[1]))})
    print('신규 30곳 도시가 ① 탭에 있는지:',
          {c: (c in lux_cities) for c in sorted({h['city'] for h in added})})
    # 뉴욕만 ① 탭에 있고, 그 3곳은 ① 뉴욕 41곳 어느 것과도 이름이 다르다
    assert [c for c in {h['city'] for h in added} if c in lux_cities] == ['뉴욕']

    # 기존 9쌍이 양방향으로 그대로인지
    lux_ai = {d['id']: d.get('alsoIn') for d in rows}
    for ihg_id, lux_id in KEEP_PAIRS.items():
        assert lux_ai[lux_id] == ihg_id, (lux_id, lux_ai[lux_id])
    print('기존 alsoIn 9쌍 양방향 유지 확인 · alsoIn 총 %d쌍(신규 0쌍)'
          % len([h for h in hotels if h.get('alsoIn')]))


if __name__ == '__main__':
    main()
