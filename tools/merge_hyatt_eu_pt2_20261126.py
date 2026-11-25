#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 유럽 포르투갈 2차 3곳(마데이라 · 알가르브) 병합 (2026-11-26)

입력  : memory/clones/a03363f4-no71/pickle/2026-11-26-0404/received/0-hyatt_eu_portugal_batch2.json
        (EU-Portugal-Batch2-3 · 1,063칸 · 2026-11-26 03:45~04:10 KST · window 2026-12-01~2027-11-30)
        No.7(@no_7) 피클이 전달한 본.
대상  : data/app/tab10_hyatt.json  (hy01~hy344 → hy345~hy347, 총 347곳)

- 기존 344곳은 값·순서 그대로 보존
- 번들 스키마(spirit_code·name·brand·city·state·country·category·url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지
- city 는 원자료 표기(Madeira · Olhos de Água, Albufeira · Vilamoura)를 그대로 쓰고 국가는 note 에 적는다
- rates_official·rates_hlx 는 null(공홈 현금가·호럭 요금 이번 배치 없음)
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 후 겹치면 연결
  (① 탭에 포르투갈 지점이 없어 겹침 0곳 — 공홈 단일 링크)
- dremp 카테고리는 팀 배포 스키마 기준 A1 유지(hyatt.com 예약 화면은 Award Category B 표기 — note 에 적음).
  note 는 순수 텍스트(** 등 마크다운 기호 없음).
"""
import copy
import json
import os
import re
import unicodedata
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
RECEIVED = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-0404/received')
BUNDLE = '0-hyatt_eu_portugal_batch2.json'
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

CODES = ('dremp', 'faodh', 'faorq')
CITY_ORDER = ['Madeira', 'Olhos de Água, Albufeira', 'Vilamoura']
FIRST_ID = 345

NOTE = {
    'dremp': ('스탠다드 아워드 365일 실측(2026-11-26 03:45~04:10 KST · hyatt.com · 포르투갈 마데이라) — '
              '포인트 364일 · 값 없는 1일(2026-12-31, 응답에 날짜 키 자체가 없음 — 60일 창과 '
              '2026-12-29~2027-01-02 좁은 창 두 번 모두 키가 없었고 앞뒤 12-30 · 01-01은 25,000P '
              'STANDARD 실측)은 보간 없이 —입니다. 60일 창 하나(2027-03-31~05-29)는 서버가 '
              'soldOutHotel · 빈 응답 · 504로 계속 실패해 2027-03-31~04-30 · 05-01~05-19 등 6개 창으로 '
              '나눠 다시 받았고, 그 가운데 2027-05-01~05-04는 첫 기록이 soldOutHotel였으나 좁은 창 '
              '재조회에서 20,000P OFF_PEAK로 정정했습니다(같은 날짜 실제 예약 페이지 Use Points 화면에도 '
              'Standard Room Free Night 20,000 Points/Night 표시). 최저 15,000P(SUPER_OFF_PEAK 111일) ~ '
              '최고 25,000P(STANDARD 25일 · OFF_PEAK 228일). 연중 운영으로 시즌 휴관 공지가 없습니다. '
              '카테고리는 팀 배포 스키마 기준 A1이며 hyatt.com 예약 화면은 Award Category B로 '
              '표시합니다. 공홈 현금가 미수집.'),
    'faodh': ('스탠다드 아워드 365일 실측(2026-11-26 03:45~04:10 KST · hyatt.com · 포르투갈 알부페이라 '
              '올루스 드 아구아) — 포인트 365일 전부 · 값 없는 날 없음. 시즌 경계가 뚜렷합니다: '
              '2027-01-01~02-26 20,000P · 02-27~06-17 25,000P · 06-18~08-29 30,000P · '
              '08-30~11-14 25,000P · 11-15~11-28 20,000P · 11-29~11-30 25,000P. 최저 '
              '20,000P(SUPER_OFF_PEAK 71일) ~ 최고 30,000P(STANDARD 73일 · OFF_PEAK 221일). '
              '브랜드는 Destination by Hyatt · 카테고리 6입니다. 값이 다 있는 곳이라 재조회는 표본 2개 '
              '창(2026-12-15~12-20 · 2027-06-16~06-22)으로 값·레벨 일치만 확인했습니다(불일치 0). '
              '공홈 현금가 미수집.'),
    'faorq': ('스탠다드 아워드 365일 실측(2026-11-26 03:45~04:10 KST · hyatt.com · 포르투갈 빌라모우라) — '
              '포인트 334일 · 값 없는 31일(날짜 키 없음 11 · 그날 응답 오브젝트는 있으나 스탠다드룸 없음 '
              '20)은 보간 없이 —입니다. 빈 날 대부분은 STANDARD_SUITE(20,000P)만 게시되고 스탠다드룸이 '
              '없는 날이라 호텔은 영업 중이고 스탠다드룸 어워드 재고만 없는 상태입니다(2027-03-12는 빈 '
              '응답). 31일 전부를 ±2일 좁은 창 10개로 재조회해 그대로 재현했고 주변 실측일의 값·레벨도 '
              '일치했습니다(최종 불일치 0). 최저 8,000P(SUPER_OFF_PEAK 70일) ~ 최고 '
              '15,000P(STANDARD 73일 · OFF_PEAK 191일). 카테고리 3. 공홈 현금가 미수집.'),
}

PORTUGAL_WORDS = ('portugal', '포르투갈', 'lisbon', 'lisboa', '리스본', 'porto', '포르투',
                  'algarve', '알가르베', 'madeira', '마데이라', 'vilamoura', '빌라모우라',
                  'albufeira', '알부페이라', 'olhos', 'comporta', 'sintra', '신트라', 'faro', '파루')


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
    assert len(before) == 344, len(before)
    assert before[-1]['id'] == 'hy344', before[-1]['id']

    bundle = json.load(open(os.path.join(RECEIVED, BUNDLE), encoding='utf-8'))
    meta = bundle['meta']
    assert meta['group'] == 'EU-Portugal-Batch2-3', meta['group']
    assert meta['days_priced_total'] == 1063, meta['days_priced_total']
    assert meta['window'] == '2026-12-01~2027-11-30'
    assert meta['hotels_collected'] == meta['hotels_total'] == 3
    assert meta['pending'] == []
    assert set(bundle['hotels']) == set(CODES), sorted(bundle['hotels'])
    new = bundle['hotels']

    assert {c: new[c]['days_priced'] for c in CODES} == {
        'dremp': 364, 'faodh': 365, 'faorq': 334}
    assert {c: new[c]['days_null'] for c in CODES} == {
        'dremp': 1, 'faodh': 0, 'faorq': 31}

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

    # ① 탭에 포르투갈 지점이 있는지 먼저 확인 (도시·영문명·국문명·지역 전수)
    for r in vip_rows:
        blob = ' '.join(clean(r.get(k)) for k in ('city', 'name', 'english', 'region')).lower()
        assert not any(w in blob for w in PORTUGAL_WORDS), ('① 에 포르투갈 지점이 있음', r.get('id'), r)

    exist_codes = {x['code']: x['id'] for x in before}
    exist_names = {norm(x['english']): x['id'] for x in before}
    exist_kr = {norm(x['name']): x['id'] for x in before}
    exist_ids = {x['id'] for x in before}

    ordered = []
    for city in CITY_ORDER:
        ordered += sorted([c for c, h in new.items() if clean(h['city']) == city],
                          key=lambda c: clean(new[c]['name']))
    assert len(ordered) == 3, ordered
    assert ordered == ['dremp', 'faodh', 'faorq'], ordered

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
        assert sum(1 for v in pts if v is not None) == info['days_priced'], code
        assert all(v is None or isinstance(v, int) for v in pts)
        assert info['country'] == 'Portugal', info['country']
        if info['days_priced']:
            assert min(v for v in pts if v is not None) == info['min_points'], code
            assert max(v for v in pts if v is not None) == info['max_points'], code
        else:
            assert info['min_points'] is None and info['max_points'] is None
        assert NOTE[code].count('**') == 0

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

    assert set(city_stat) == set(CITY_ORDER), city_stat
    assert city_stat == {'Madeira': 1, 'Olhos de Água, Albufeira': 1, 'Vilamoura': 1}, city_stat

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'

    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    cells = sum(len(h['points']['$v']) for h in tab['hotels'])
    priced = sum(1 for h in tab['hotels'] for v in h['points']['$v'] if v is not None)
    europe = [h['id'] for h in tab['hotels'] if h['region'] == '유럽']
    portugal = [h['city'] for h in tab['hotels'] if h['region'] == '유럽'
                and h['city'] in ('Lisbon', 'Madeira', 'Olhos de Água, Albufeira', 'Vilamoura')]
    print('added', [(a['id'], a['code'], a['name'], a['city'], a['category']) for a in added])
    print('cities', city_stat, '포르투갈', len(portugal))
    print('hotels', len(tab['hotels']), 'cells', cells, 'priced', priced)
    print('유럽', len(europe))
    print('신규 3곳 셀 1,095 가운데',
          sum(1 for h in added for v in h['points']['$v'] if v is not None), '칸')


if __name__ == '__main__':
    main()
