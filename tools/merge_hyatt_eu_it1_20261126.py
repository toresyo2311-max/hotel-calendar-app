#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 유럽 이탈리아 1차 로마(Rome) 3곳(365일 스탠다드 아워드 포인트) 병합 (2026-11-26)

입력  : memory/clones/a03363f4-no71/pickle/2026-11-26-0234/received/0-hyatt_eu_italy_batch1.json
        (meta: EU-Italy-Batch1-3 · window 2026-12-01~2027-11-30 ·
         days_priced_total 990 · 2026-11-26 02:33 KST 실측)
        No.7(@no_7) 피클이 전달한 본.
대상  : data/app/tab10_hyatt.json  (hy01~hy321 → hy322~hy324, 총 324곳)

- 기존 321곳은 값·순서 그대로 보존
- 번들 스키마(spirit_code·name·brand·city·state·category·url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지
- city 는 원자료 표기(Rome)를 그대로 쓰고, 국가·주는 note 에 적는다(3곳 모두 이탈리아 라치오주 로마)
- rates_official·rates_hlx 는 null(공홈 현금가·호럭 요금 이번 배치 없음)
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 후 겹치면 연결
- romrt(Hyatt Regency Rome Central)는 2026년 12월 31일 전체가 **개관 전 예약 미오픈**
  ("Now accepting reservations for stays from January 1, 2027 and beyond")이라 매진과 구분해 note 에 적는다
"""
import copy
import json
import os
import re
import unicodedata
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
BUNDLE = os.path.join(
    WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-0234/received/0-hyatt_eu_italy_batch1.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

CITY_ORDER = ['Rome']
COUNTRY = '이탈리아'
STATE_KR = '라치오주'
CITY_KR = {'Rome': '로마'}
COLLECTED = '2026-11-26 02:33 KST'
FIRST_ID = 322

# 카드 메모 — 원자료의 null 성격(어떤 날이 왜 비었는지)을 호텔별로 적는다
NOTE = {
    'romrt': ('스탠다드 아워드 365일 실측(2026-11-26 02:33 KST · hyatt.com · 이탈리아 라치오주 로마) — '
              '포인트 293일 · 값 없는 72일은 보간 없이 —입니다. '
              '**2026년 12월 31일 전체는 매진이 아니라 개관 전 예약 미오픈**입니다 — 하얏트 공지 '
              '「Now accepting reservations for stays from January 1, 2027 and beyond」대로 '
              '2027-01-01부터 재고가 시작되므로 12월은 투숙 자체가 불가합니다(값을 채워 넣지 않았습니다). '
              '2027-01-01 이후 값 없는 41일(2027-03~06)은 그날 스탠다드룸 아워드 응답이 없던 날이고 '
              '매진·미오픈을 구분하지 않습니다. 최저 12,000P(SUPER_OFF_PEAK 56일) ~ '
              '최고 22,500P(2027-06-26~27 PEAK 2일). 공홈 현금가 미수집.'),
    'romjd': ('스탠다드 아워드 365일 실측(2026-11-26 02:33 KST · hyatt.com · 이탈리아 라치오주 로마) — '
              '포인트 339일 · 값 없는 26일(스탠다드룸 응답 없음 20 · 날짜 키 없음 6)은 매진·예약창 밖·'
              '미오픈을 구분하지 않고 보간 없이 —입니다. 값 없는 날은 2026-12-01~05 · 12-07~15 · '
              '12-23~25 · 12-28~2027-01-01(연말)과 2027-05-13 · 05-15 · 05-29 · 07-10입니다. '
              '최저 20,000P(SUPER_OFF_PEAK 61일) ~ 최고 35,000P(2027-06-11 · 06-26 · 06-27 PEAK 3일). '
              '공홈 현금가 미수집.'),
    'romth': ('스탠다드 아워드 365일 실측(2026-11-26 02:33 KST · hyatt.com · 이탈리아 라치오주 로마) — '
              '포인트 358일 · 값 없는 7일은 그날 오브젝트에 스탠다드룸이 없던 날(스위트만 있거나 빈 응답)로 '
              '매진·미오픈을 구분하지 않고 보간 없이 —입니다(2026-12-01 · 12-04 · 12-06~08 · '
              '2027-02-08~09). 최저 35,000P(SUPER_OFF_PEAK 67일) ~ 최고 65,000P(2027-06-11 · 06-26 · '
              '06-27 PEAK 3일). 공홈 현금가 미수집.'),
}


def clean(s):
    s = unicodedata.normalize('NFC', str(s or ''))
    s = ''.join(' ' if (ch.isspace() or unicodedata.category(ch) in ('Cf', 'Cc')) else ch for ch in s)
    return ' '.join(s.split())


def norm(s):
    s = unicodedata.normalize('NFKD', clean(s)).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 321, len(before)
    assert before[-1]['id'] == 'hy321', before[-1]['id']

    bundle = json.load(open(BUNDLE, encoding='utf-8'))
    meta = bundle['meta']
    assert meta['hotels_total'] == 3 and meta['hotels_collected'] == 3
    assert meta['days_priced_total'] == 990, meta['days_priced_total']
    assert meta['window'] == '2026-12-01~2027-11-30'
    assert meta['collected_at'] == COLLECTED
    assert meta['pending'] == []
    new = bundle['hotels']
    assert len(new) == 3, len(new)
    assert set(new) == {'romrt', 'romjd', 'romth'}, sorted(new)
    assert {c: new[c]['days_priced'] for c in new} == {'romrt': 293, 'romjd': 339, 'romth': 358}
    assert sum(new[c]['days_priced'] for c in new) == 990

    # ── ① 호텔럭스 대조용 색인 ──────────────────────────────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    vip_rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
    assert len(vip_rows) == 161, len(vip_rows)
    by_code, by_english, by_korean, by_city = {}, {}, {}, {}
    for r in vip_rows:
        if r.get('ref_id'):
            by_code[str(r['ref_id']).strip().lower()] = r
        if r.get('english'):
            by_english.setdefault(norm(r['english']), []).append(r)
        if r.get('name'):
            by_korean.setdefault(norm(r['name']), []).append(r)
        if r.get('city'):
            by_city.setdefault(clean(r['city']), []).append(r)

    # ① 탭에 이탈리아·로마 지점이 있는지 먼저 확인 (도시·영문명·국문명 전수)
    italy_words = ('rome', 'roma', '로마', 'italy', 'italia', '이탈리아', 'milan', 'milano', '밀라노',
                   'venice', 'venezia', '베네치아', 'florence', 'firenze', '피렌체')
    for r in vip_rows:
        blob = ' '.join(clean(r.get(k)) for k in ('city', 'name', 'english', 'region')).lower()
        assert not any(w in blob for w in italy_words), ('① 에 이탈리아 지점이 있음', r.get('id'), r)

    exist_codes = {x['code']: x['id'] for x in before}
    exist_names = {norm(x['english']): x['id'] for x in before}
    exist_kr = {norm(x['name']): x['id'] for x in before}
    exist_ids = {x['id'] for x in before}

    ordered = []
    for city in CITY_ORDER:
        ordered += sorted([c for c, h in new.items() if clean(h['city']) == city],
                          key=lambda c: clean(new[c]['name']))
    assert len(ordered) == 3, ordered
    assert ordered == ['romrt', 'romjd', 'romth'], ordered

    added, city_stat = [], {}
    for i, code in enumerate(ordered):
        info = new[code]
        hid = 'hy%02d' % (FIRST_ID + i)
        assert hid not in exist_ids
        assert code not in exist_codes, 'duplicate code %s (%s)' % (code, exist_codes.get(code))
        n = norm(info['name'])
        assert n not in exist_names, 'duplicate name %s -> %s' % (info['name'], exist_names[n])
        assert norm(info['name']) not in exist_kr

        pts = [info['points'].get(d) for d in DATES]
        assert len(pts) == 365
        assert sum(1 for v in pts if v is not None) == info['days_priced']
        assert all(v is None or isinstance(v, int) for v in pts)

        # ① 호텔럭스 전수 대조 — 코드·영문명·국문명·도시
        hit_code = by_code.get(code.lower())
        hit_en = by_english.get(norm(info['name']))
        hit_kr = by_korean.get(norm(info['name']))
        hit_city = by_city.get(clean(info['city']))
        # 도시가 같다는 것만으로는 연결하지 않는다(로마 지점이 ① 에 없음)
        assert hit_code is None and not hit_en and not hit_kr and not hit_city, \
            ('① 호텔럭스 겹침', code, hit_code, hit_en, hit_kr, hit_city)

        entry = {
            'id': hid,
            'group': 'hyatt',
            'code': info['spirit_code'],
            'region': '유럽',
            'city': clean(info['city']),
            'name': clean(info['name']),
            'english': clean(info['name']),
            'brand': clean(info['brand']),
            'category': info['category'],
            'vip_id': None,
            'alsoIn': None,
            'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None,
            'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % info['spirit_code'],
                      'hlx': None},
            'promotion': None,
            'note': NOTE[code],
        }
        added.append(entry)
        city_stat[clean(info['city'])] = city_stat.get(clean(info['city']), 0) + 1

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'

    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    cells = sum(len(h['points']['$v']) for h in tab['hotels'])
    priced = sum(1 for h in tab['hotels'] for v in h['points']['$v'] if v is not None)
    print('added', [(a['id'], a['code'], a['name']) for a in added])
    print('cities', city_stat)
    print('hotels', len(tab['hotels']), 'cells', cells, 'priced', priced)
    print('이탈리아 1차 3곳 = 1,095칸 가운데', sum(1 for h in added for v in h['points']['$v'] if v is not None), '칸')


if __name__ == '__main__':
    main()
