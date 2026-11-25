#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 유럽 스위스 5곳(취리히 · 클로텐 2 · 다보스 · 플림스, 365일 스탠다드 아워드 포인트) 병합 (2026-11-26)

입력  : memory/clones/a03363f4-no71/pickle/2026-11-26-0258/received/0-hyatt_eu_switzerland_5.json
        (meta: EU-Switzerland-5 · window 2026-12-01~2027-11-30 ·
         days_priced_total 1,487 · 2026-11-26 02:46~02:57 KST 실측)
        No.7(@no_7) 피클이 전달한 본.
대상  : data/app/tab10_hyatt.json  (hy01~hy327 → hy328~hy332, 총 332곳)

- 기존 327곳은 값·순서 그대로 보존
- 번들 스키마(spirit_code·name·brand·city·country·category·url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지
- city 는 원자료 표기(Davos · Flims · Kloten · Zurich)를 그대로 쓰고 국가는 note 에 적는다
- rates_official·rates_hlx 는 null(공홈 현금가·호럭 요금 이번 배치 없음)
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 후 겹치면 연결
  (① 탭에 스위스 지점이 없어 겹침 0곳 — 공홈 단일 링크)
- davub(Hotel Flüela Davos)는 겨울 한정 운영 호텔이라 12/1~10 시즌 사이(interseason) 휴관 공지가 있고
  어워드 재고가 2026-12-11~2027-03-13 구간에만 있으며 이후는 soldOutHotel 응답이다 —
  매진과 섞지 않고 note 에 적는다. note 는 순수 텍스트(** 등 마크다운 기호 없음).
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
    WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-0258/received/0-hyatt_eu_switzerland_5.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

CITY_ORDER = ['Zurich', 'Kloten', 'Davos', 'Flims']
COLLECTED = '2026-11-26 02:46~02:57 KST'
FIRST_ID = 328

NOTE = {
    'zurph': ('스탠다드 아워드 365일 실측(2026-11-26 02:46~02:57 KST · hyatt.com · 스위스 취리히) — '
              '포인트 363일 · 값 없는 2일(2026-12-01 · 2027-06-06, 그날 스탠다드룸 응답 없음)은 '
              '보간 없이 —입니다. 최저 35,000P(SUPER_OFF_PEAK 70일) ~ 최고 75,000P(SUPER_PEAK 9일 · '
              'PEAK 32일 · STANDARD 105일 · OFF_PEAK 147일). 공홈 현금가 미수집.'),
    'zrhzz': ('스탠다드 아워드 365일 실측(2026-11-26 02:46~02:57 KST · hyatt.com · 스위스 클로텐, '
              '취리히 공항 더 서클) — 포인트 362일 · 값 없는 3일(2027-01-14~16, 날짜 키 없음)은 '
              '보간 없이 —입니다. 최저 12,000P(SUPER_OFF_PEAK 70일) ~ 최고 20,000P(STANDARD 146일 · '
              'OFF_PEAK 146일). 공홈 현금가 미수집.'),
    'zrhrz': ('스탠다드 아워드 365일 실측(2026-11-26 02:46~02:57 KST · hyatt.com · 스위스 클로텐, '
              '취리히 공항 컨벤션 센터) — 포인트 348일 · 값 없는 17일(날짜 키 없음 10 · 그날 스탠다드룸 '
              '응답 없음 7)은 매진·예약창 밖·미오픈을 구분하지 않고 보간 없이 —입니다. '
              '최저 15,000P(SUPER_OFF_PEAK 67일) ~ 최고 25,000P(STANDARD 142일 · OFF_PEAK 139일). '
              '공홈 현금가 미수집.'),
    'davub': ('스탠다드 아워드 365일 실측(2026-11-26 02:46~02:57 KST · hyatt.com · 스위스 다보스) — '
              '포인트 75일 · 값 없는 290일(날짜 키 없음 288 · 그날 스탠다드룸 응답 없음 2)은 보간 없이 —입니다. '
              '이 호텔은 겨울 한정 운영으로, 예약 화면이 1박 어워드 재고를 2026-12-11~2027-03-13 구간에만 '
              '주고 나머지는 soldOutHotel 로 답합니다(2026-12-01~10 은 시즌 사이(interseason) 휴관 공지, '
              '2027-03-14 이후와 2027-06 · 2027-11 구간은 60일 창 재조회로 soldOutHotel 교차 확인). '
              '어워드 가능 구간 안에서도 2026-12-25~2027-01-01 · 2027-01-15~01-22 · 02-20 · 02-27 은 값이 '
              '없습니다. 최저 35,000P(SUPER_OFF_PEAK 5일) ~ 최고 65,000P(PEAK 11일 · STANDARD 34일 · '
              'OFF_PEAK 25일). 공홈 현금가 미수집.'),
    'achjd': ('스탠다드 아워드 365일 실측(2026-11-26 02:46~02:57 KST · hyatt.com · 스위스 플림스) — '
              '포인트 339일 · 값 없는 26일(날짜 키 없음 26)은 매진·예약창 밖·미오픈을 구분하지 않고 '
              '보간 없이 —입니다. 최저 15,000P(SUPER_OFF_PEAK 78일) ~ 최고 25,000P(STANDARD 60일 · '
              'OFF_PEAK 201일). 공홈 현금가 미수집.'),
}

SWISS_WORDS = ('switzerland', 'swiss', '스위스', 'zurich', 'zürich', '취리히', 'kloten', '클로텐',
               'davos', '다보스', 'flims', '플림스', 'geneva', '제네바', 'basel', '바젤',
               'lucerne', 'luzern', '루체른', 'bern', '베른', 'zermatt', '체르마트')


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
    assert len(before) == 327, len(before)
    assert before[-1]['id'] == 'hy327', before[-1]['id']

    bundle = json.load(open(BUNDLE, encoding='utf-8'))
    meta = bundle['meta']
    assert meta['hotels_total'] == 5 and meta['hotels_collected'] == 5
    assert meta['days_priced_total'] == 1487, meta['days_priced_total']
    assert meta['window'] == '2026-12-01~2027-11-30'
    assert meta['collected_at'] == COLLECTED
    assert meta['pending'] == []
    new = bundle['hotels']
    assert len(new) == 5, len(new)
    assert set(new) == {'davub', 'achjd', 'zrhzz', 'zrhrz', 'zurph'}, sorted(new)
    assert {c: new[c]['days_priced'] for c in new} == {
        'davub': 75, 'achjd': 339, 'zrhzz': 362, 'zrhrz': 348, 'zurph': 363}
    assert sum(new[c]['days_priced'] for c in new) == 1487

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

    # ① 탭에 스위스 지점이 있는지 먼저 확인 (도시·영문명·국문명·지역 전수)
    for r in vip_rows:
        blob = ' '.join(clean(r.get(k)) for k in ('city', 'name', 'english', 'region')).lower()
        assert not any(w in blob for w in SWISS_WORDS), ('① 에 스위스 지점이 있음', r.get('id'), r)

    exist_codes = {x['code']: x['id'] for x in before}
    exist_names = {norm(x['english']): x['id'] for x in before}
    exist_kr = {norm(x['name']): x['id'] for x in before}
    exist_ids = {x['id'] for x in before}

    ordered = []
    for city in CITY_ORDER:
        ordered += sorted([c for c, h in new.items() if clean(h['city']) == city],
                          key=lambda c: clean(new[c]['name']))
    assert len(ordered) == 5, ordered
    assert ordered == ['zurph', 'zrhzz', 'zrhrz', 'davub', 'achjd'], ordered

    added, city_stat = [], {}
    for i, code in enumerate(ordered):
        info = new[code]
        hid = 'hy%02d' % (FIRST_ID + i)
        assert hid not in exist_ids
        assert code not in exist_codes, 'duplicate code %s (%s)' % (code, exist_codes.get(code))
        n = norm(info['name'])
        assert n not in exist_names, 'duplicate name %s -> %s' % (info['name'], exist_names[n])
        assert n not in exist_kr

        pts = [info['points'].get(d) for d in DATES]
        assert len(pts) == 365
        assert sum(1 for v in pts if v is not None) == info['days_priced']
        assert all(v is None or isinstance(v, int) for v in pts)
        assert info['country'] == 'Switzerland'
        assert min(v for v in pts if v is not None) == info['min_points']
        assert max(v for v in pts if v is not None) == info['max_points']

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

    assert set(city_stat) == {'Zurich', 'Kloten', 'Davos', 'Flims'}, city_stat
    assert city_stat == {'Zurich': 1, 'Kloten': 2, 'Davos': 1, 'Flims': 1}, city_stat

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'

    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    cells = sum(len(h['points']['$v']) for h in tab['hotels'])
    priced = sum(1 for h in tab['hotels'] for v in h['points']['$v'] if v is not None)
    europe = [h['id'] for h in tab['hotels'] if h['region'] == '유럽']
    print('added', [(a['id'], a['code'], a['name'], a['city'], a['category']) for a in added])
    print('cities', city_stat)
    print('hotels', len(tab['hotels']), 'cells', cells, 'priced', priced)
    print('유럽', len(europe))
    print('신규 5곳 셀 1,825 가운데',
          sum(1 for h in added for v in h['points']['$v'] if v is not None), '칸')


if __name__ == '__main__':
    main()
