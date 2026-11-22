#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 서유럽·남유럽 P2 15곳 → data/app/tab11_ihg.json 병합

원자료: 3번(@jin_3) 실측 `0-ihg_eu_p2_no3_15.json`
        (2026-11-23 05:37 KST · 2026-12-01~2027-11-30 365일 · 현금 4,202칸 · 포인트 3,788칸)

기존 tab11_ihg.json(아시아·오세아니아 72 + 유럽 26 + 북미·중남미 27 = 125곳, i01~i125)은
값·순서·alsoIn 을 그대로 두고 뒤에 15곳을 i126~i140으로 붙인다
(이탈리아 5 · 영국 3 · 프랑스 3 · 스페인 2 · 포르투갈 2).

스키마는 기존과 똑같이 맞춘다:
  · brand      — 화면 태그·필터용 한글 브랜드명(자료의 'VIGNETTE'/'CP'/'VOCO'/'INDIGO'를 기존 표기로 정규화)
  · brand_code — 기존 표기(VIGNETTE · CP · VOCO · INDIGO). 자료의 PARPT 'LX'(브랜드 그룹 코드)는
                 같은 브랜드 경로(vignettecollection)의 기존 표기 'VIGNETTE' 로 맞춘다
  · rates/points — {$d, $v} 압축 열, 값 없는 칸은 null(보간 금지)
  · cells      — {"rates": n, "points": n}
  · note       — ROMVB(전일 null · 리브랜딩 공사) · LISPD(전일 null · 판매 재고 없음) ·
                 PARPT(2026-12~2027-03 판매 없음 · 전 기간 포인트 불가) 원자료 문구 그대로

① 호텔럭스(tab1_vip.json 161곳) 전수 대조 — 코드·영문명·국문명·도시를 정규화해 맞춰 본 결과
겹치는 호텔 0곳(① 탭은 서울·부산·도쿄·방콕·싱가포르·시드니·뉴욕 등이고 유럽 지점이 없다).
기존 9쌍(i01·i12·i13·i48·i54·i63·i65·i99·i100 ↔ h27·h61·h64·h15·h20·h115·h118·h122·h152)은 그대로 둔다.
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', '2e8f9e24-hanjinlee4', 'pickle',
                   '2026-11-23-0537', 'received', '0-ihg_eu_p2_no3_15.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

# 기존 125곳이 이미 이은 ① 호텔럭스 9쌍 — 이번 15곳은 겹침 0
KEEP_PAIRS = {
    'i01': 'h27', 'i12': 'h61', 'i13': 'h64', 'i48': 'h15', 'i54': 'h20',
    'i63': 'h115', 'i65': 'h118', 'i99': 'h122', 'i100': 'h152',
}

# 브랜드 경로 → 기존 표기(한글 브랜드명 · 브랜드 코드 · brand_key)
BRAND = {
    'vignettecollection': ('비네트 컬렉션', 'VIGNETTE', 'VIGNETTE'),
    'crowneplaza': ('크라운 플라자', 'CP', 'CP'),
    'voco': ('보코', 'VOCO', 'VOCO'),
    'hotelindigo': ('호텔 인디고', 'INDIGO', 'INDIGO'),
}


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
    assert len(old) == 125, len(old)
    assert src['days'] == 365 and src['window'] == '2026-12-01~2027-11-30'
    assert src['counts'] == {'hotels': 15, 'cash_cells': 4202, 'point_cells': 3788}, src['counts']

    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)
    assert old_cash == 40666 and old_pts == 38877, (old_cash, old_pts)
    old_alsoin = {h['id']: h.get('alsoIn') for h in old}
    assert all(old_alsoin[k] == v for k, v in KEEP_PAIRS.items())

    old_codes = {h['code'] for h in old}
    old_en = {norm(h['english']) for h in old}
    old_ko = {norm(h['name']) for h in old}

    n = len(old)
    added = []
    for h in src['hotels']:
        n += 1
        path = h['brand_path']
        assert path in BRAND, (h['code'], path)
        brand, bcode, bkey = BRAND[path]
        assert h['code'] not in old_codes, h['code']
        assert norm(h['english']) not in old_en, h['english']
        assert norm(h['name']) not in old_ko, h['name']
        assert h['region'] == '유럽', h['region']
        assert h['rates']['$d'] == '2026-12-01' and h['points']['$d'] == '2026-12-01'
        assert len(h['rates']['$v']) == 365 and len(h['points']['$v']) == 365
        rc = numeric(h['rates']['$v'])
        pc = numeric(h['points']['$v'])
        assert rc == h['cells']['cash'] and pc == h['cells']['points'], (h['code'], rc, pc, h['cells'])
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
            'note': h.get('note') or '',
            'source': h.get('source') or '',
            'cells': {'rates': rc, 'points': pc},
        }
        added.append(rec)

    assert len(added) == 15
    assert added[0]['id'] == 'i126' and added[-1]['id'] == 'i140'
    assert [x['code'] for x in added] == [
        'LONHR', 'LONKC', 'EDITE', 'PARPT', 'PARGM', 'NCEAN', 'ROMVB', 'ROMSG',
        'ROMSP', 'MILFE', 'VCEVM', 'BCNIN', 'MADCR', 'LISPD', 'OPOCC']
    assert sum(h['cells']['rates'] for h in added) == 4202
    assert sum(h['cells']['points'] for h in added) == 3788
    # 원자료 특이사항 — note 가 빈 곳 없이 그대로 실렸는지
    notes = {x['code']: x['note'] for x in added}
    assert '리브랜딩' in notes['ROMVB'] and '전일 null' in notes['ROMVB']
    assert '전일 null' in notes['LISPD']
    assert '124' not in notes['PARPT'] and '2026-12~2027-03' in notes['PARPT'] and '포인트' in notes['PARPT']

    hotels = old + added
    base['hotels'] = hotels
    base['generated_at'] = '2026-11-23'
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    assert cash == old_cash + 4202, (cash, old_cash)
    assert pts == old_pts + 3788, (pts, old_pts)
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))
    print('tab11 hotels %d (신규 %d) · 유럽 %d · cells %d · cash %d · points %d'
          % (len(hotels), len(added), sum(1 for h in hotels if h['region'] == '유럽'),
             base['counts']['cells'], cash, pts))

    # ── ① 호텔럭스 161곳 전수 대조 — 코드·영문명·국문명·도시 ─────────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
    lux_by_en, lux_by_ko, lux_by_code, lux_cities = {}, {}, {}, set()
    for d in rows:
        lux_by_en.setdefault(norm(d.get('english')), []).append(d['id'])
        lux_by_ko.setdefault(norm(d.get('name')), []).append(d['id'])
        lux_by_code[str(d.get('id') or '').upper()] = d['id']
        lux_cities.add(norm(d.get('city')))
    hits = []
    for h in hotels:
        for why, got in (('code', lux_by_code.get(h['code'].upper())),
                         ('en', (lux_by_en.get(norm(h['english'])) or [None])[0]),
                         ('ko', (lux_by_ko.get(norm(h['name'])) or [None])[0])):
            if got and h.get('alsoIn') != got:
                hits.append((h['id'], h['code'], h['name'], got, why))
    print('① 호텔럭스 겹침(아직 연결 안 된 곳):', hits if hits else '없음')
    assert not hits, hits
    # 이미 이어진 9쌍 밖에 같은 호텔이 또 있는지 — 연결된 짝과 대조
    linked = {(h['id'], h['alsoIn']) for h in hotels if h.get('alsoIn')}
    print('alsoIn 연결 %d쌍: %s' % (len(linked), sorted(linked)))
    print('신규 15곳 도시가 ① 탭 도시에 있는지:',
          {h['city']: norm(h['city']) in lux_cities for h in added})

    # 기존 9쌍이 양방향으로 그대로인지
    lux_ai = {d['id']: d.get('alsoIn') for d in rows}
    for ihg_id, lux_id in KEEP_PAIRS.items():
        assert lux_ai[lux_id] == ihg_id, (lux_id, lux_ai[lux_id])
    print('기존 alsoIn 9쌍 양방향 유지 확인')


if __name__ == '__main__':
    main()
