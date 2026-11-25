#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 유럽 이탈리아 2차 피렌체 · 베네치아 · 사르데냐 3곳(365일 스탠다드 아워드 포인트) 병합 (2026-11-26)

입력  : memory/clones/a03363f4-no71/pickle/2026-11-26-0245/received/0-hyatt_eu_italy_batch2.json
        (meta: EU-Italy-Batch2-3 · window 2026-12-01~2027-11-30 ·
         days_priced_total 701 · 2026-11-26 03:05 KST 실측)
        No.7(@no_7) 피클이 전달한 본.
대상  : data/app/tab10_hyatt.json  (hy01~hy324 → hy325~hy327, 총 327곳)

- 기존 324곳은 값·순서 그대로 보존
- 번들 스키마(spirit_code·name·brand·city·state·country·category·url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지
- city 는 원자료 표기(Florence · Venice · Baja Sardinia (Arzachena))를 그대로 쓰고,
  국가·주는 note 에 적는다
- rates_official·rates_hlx 는 null(공홈 현금가·호럭 요금 이번 배치 없음)
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 후 겹치면 연결
  (① 탭에 이탈리아 지점이 없어 겹침 0곳 — 공홈 단일 링크)
- sardh(7Pines Resort Sardinia)는 시즌제 리조트(2027-04-15 재오픈 ~ 2027-10-24 운영)라
  휴관 기간 soldOutHotel 응답과 성수기(2027-06-09~09-15) 어워드 재고 없음이 겹쳐
  포인트가 74일뿐이다 — 매진/개관과 섞지 않고 note 에 적는다
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
    WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-0245/received/0-hyatt_eu_italy_batch2.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

CITY_ORDER = ['Florence', 'Venice', 'Baja Sardinia (Arzachena)']
COLLECTED = '2026-11-26 03:05 KST'
FIRST_ID = 325

NOTE = {
    'flrub': ('스탠다드 아워드 365일 실측(2026-11-26 03:05 KST · hyatt.com · 이탈리아 토스카나주 피렌체) — '
              '포인트 273일 · 값 없는 92일(날짜 키 없음 2 · 그날 스탠다드룸 응답 없음 90)은 매진·예약창 밖·'
              '미오픈을 구분하지 않고 보간 없이 —입니다. 최저 35,000P(SUPER_OFF_PEAK 50일) ~ '
              '최고 55,000P(STANDARD 125일). 공홈 현금가 미수집.'),
    'vcect': ('스탠다드 아워드 365일 실측(2026-11-26 03:05 KST · hyatt.com · 이탈리아 베네토주 베네치아) — '
              '포인트 354일 · 값 없는 11일(2026-12-01~02 · 12-10~11 · 2027-02-06 · 03-13 · 03-19 · 04-03 · '
              '05-22 · 06-14~15)은 매진·예약창 밖·미오픈을 구분하지 않고 보간 없이 —입니다. '
              '최저 12,000P(SUPER_OFF_PEAK 126일) ~ 최고 20,000P(STANDARD 145일). 공홈 현금가 미수집.'),
    'sardh': ('스탠다드 아워드 365일 실측(2026-11-26 03:05 KST · hyatt.com · 이탈리아 사르데냐주 '
              '바하 사르디니아(아르차케나)) — 포인트 74일 · 값 없는 291일은 보간 없이 —입니다. '
              '이 호텔은 시즌제 리조트로 2027-04-15 재오픈 ~ 2027-10-24까지만 운영합니다 — '
              '휴관 기간(2026-12-01~2027-04-14 · 2027-10-25~11-30)은 예약 화면이 soldOutHotel 로 답하고 '
              '1박 아워드 재고가 아예 없습니다. 운영 기간 안에서도 119일이 비어 있는데, '
              '그중 성수기 2027-06-09~09-15 99일은 1박 어워드 재고 없음(빈 오브젝트)으로 7일 창 재조회에서 '
              '다시 확인했고 나머지 20일(2027-04-23~24 · 04-26~27 · 05-04~07 · 05-28 · 06-01~07 · 09-25~28)은 '
              '그날 스탠다드룸 응답이 없던 날입니다. 최저 35,000P(2027-10-24 하루) ~ '
              '최고 55,000P(2027-04-15~10-23 STANDARD 68일). 공홈 현금가 미수집.'),
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
    assert len(before) == 324, len(before)
    assert before[-1]['id'] == 'hy324', before[-1]['id']

    bundle = json.load(open(BUNDLE, encoding='utf-8'))
    meta = bundle['meta']
    assert meta['hotels_total'] == 3 and meta['hotels_collected'] == 3
    assert meta['days_priced_total'] == 701, meta['days_priced_total']
    assert meta['window'] == '2026-12-01~2027-11-30'
    assert meta['collected_at'] == COLLECTED
    assert meta['pending'] == []
    new = bundle['hotels']
    assert len(new) == 3, len(new)
    assert set(new) == {'sardh', 'flrub', 'vcect'}, sorted(new)
    assert {c: new[c]['days_priced'] for c in new} == {'sardh': 74, 'flrub': 273, 'vcect': 354}
    assert sum(new[c]['days_priced'] for c in new) == 701

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

    # ① 탭에 이탈리아 지점이 있는지 먼저 확인 (도시·영문명·국문명 전수)
    italy_words = ('rome', 'roma', '로마', 'italy', 'italia', '이탈리아', 'milan', 'milano', '밀라노',
                   'venice', 'venezia', '베네치아', 'florence', 'firenze', '피렌체', 'sardinia', '사르데냐')
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
    assert ordered == ['flrub', 'vcect', 'sardh'], ordered

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
        assert info['country'] == 'Italy'

        # ① 호텔럭스 전수 대조 — 코드·영문명·국문명·도시
        hit_code = by_code.get(code.lower())
        hit_en = by_english.get(norm(info['name']))
        hit_kr = by_korean.get(norm(info['name']))
        hit_city = by_city.get(clean(info['city']))
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
            'links': {'official': info['url'], 'hlx': None},
            'promotion': None,
            'note': NOTE[code],
        }
        added.append(entry)
        city_stat[clean(info['city'])] = city_stat.get(clean(info['city']), 0) + 1

    assert set(city_stat) == {'Florence', 'Venice', 'Baja Sardinia (Arzachena)'}

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'

    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    cells = sum(len(h['points']['$v']) for h in tab['hotels'])
    priced = sum(1 for h in tab['hotels'] for v in h['points']['$v'] if v is not None)
    italy = [h['id'] for h in tab['hotels'] if h['region'] == '유럽'
             and (h['city'] in CITY_ORDER or h['city'] == 'Rome')]
    print('added', [(a['id'], a['code'], a['name']) for a in added])
    print('cities', city_stat)
    print('hotels', len(tab['hotels']), 'cells', cells, 'priced', priced)
    print('이탈리아', len(italy), italy)
    print('신규 3곳 셀 1,095 가운데',
          sum(1 for h in added for v in h['points']['$v'] if v is not None), '칸')


if __name__ == '__main__':
    main()
