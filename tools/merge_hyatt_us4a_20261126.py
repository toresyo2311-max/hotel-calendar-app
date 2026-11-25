#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 미국 4차-A 덴버 9 · 샬럿 8 · 달라스 7 = 24곳(365일 아워드 포인트) 병합 (2026-11-26)

입력  : memory/clones/a03363f4-no71/pickle/2026-11-26-0132/received/0-hyatt-us-hub4a-points.json
        (meta: US-Hub4A-24 · window 2026-12-01~2027-11-30 · days_priced_total 8,659 · 2026-11-23 01:24 KST 실측)
        No.7(@no_7) 피클이 4번(@jin_4)에게서 인계받아 전달한 본.
대상  : data/app/tab10_hyatt.json  (hy01~hy275 → hy276~hy299, 총 299곳)

- 기존 275곳은 값·순서 그대로 보존(원본 객체 동일성 검사)
- 번들 스키마(spirit_code·name·brand·city·state·category·url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지(번들 verification 대로 매진·미오픈)
- rates_official·rates_hlx 는 null(공홈 현금가·호럭 요금 이번 배치 없음)
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시·영문명 토큰 전수 대조 후 겹치면
  vip_id/alsoIn/hlx_in/links.hlx/rates_hlx/promotion 연결
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
    WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-0132/received/0-hyatt-us-hub4a-points.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

# 도시 묶음 순서 — 덴버 → 샬럿 → 달라스
CITY_ORDER = ['Denver', 'Charlotte', 'Dallas']


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
    assert len(before) == 275, len(before)
    assert before[-1]['id'] == 'hy275', before[-1]['id']

    bundle = json.load(open(BUNDLE, encoding='utf-8'))
    meta = bundle['meta']
    assert meta['hotels_total'] == 24 and meta['hotels_collected'] == 24
    assert meta['days_priced_total'] == 8659
    new = bundle['hotels']
    assert len(new) == 24, len(new)

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

    exist_codes = {x['code']: x['id'] for x in before}
    exist_names = {norm(x['english']): x['id'] for x in before}
    exist_ids = {x['id'] for x in before}

    ordered = []
    for city in CITY_ORDER:
        ordered += sorted([c for c, h in new.items() if clean(h['city']) == city],
                          key=lambda c: clean(new[c]['name']))
    assert len(ordered) == 24, len(ordered)

    added, linked, city_stat = [], [], {}
    for i, code in enumerate(ordered):
        info = new[code]
        hid = 'hy%02d' % (276 + i)
        assert hid not in exist_ids
        assert code not in exist_codes, 'duplicate code %s (%s)' % (code, exist_codes.get(code))
        n = norm(info['name'])
        assert n not in exist_names, 'duplicate name %s -> %s' % (info['name'], exist_names[n])

        pts = [info['points'].get(d) for d in DATES]
        assert len(info['points']) == 365, (code, len(info['points']))
        priced = sum(1 for v in pts if v is not None)
        assert priced == info['days_priced'], (code, priced, info['days_priced'])

        # ① 호텔럭스 대조 — 코드 → 영문명 완전일치 → 국문명 완전일치
        hit = by_code.get(code.lower())
        how = 'code' if hit else ''
        if not hit:
            cand = by_english.get(n)
            if cand:
                hit, how = cand[0], 'english'
        if not hit:
            cand = by_korean.get(n)
            if cand:
                hit, how = cand[0], 'korean'

        city = clean(info['city'])
        if priced == 0:
            note = ('스탠다드 아워드 365일 실측(2026-11-23 01:24 KST · hyatt.com) — 365일 모두 값이 없습니다(0일). '
                    '재고 없음·예약창 밖·미조회를 구분하지 않음(NA). 공홈 현금가 미수집.')
        else:
            note = ('스탠다드 아워드 365일 실측(2026-11-23 01:24 KST · hyatt.com) — 포인트 %d일 · '
                    '값 없는 %d일은 재고 없음·예약창 밖·미조회를 구분하지 않음(NA). 공홈 현금가 미수집.'
                    % (priced, 365 - priced))

        cat = info.get('category')
        entry = {
            'id': hid,
            'group': 'hyatt',
            'code': code,
            'region': '미국',
            'city': city,
            'name': clean(info['name']),
            'english': clean(info['name']),
            'brand': clean(info['brand']) or None,
            'category': int(cat) if cat not in (None, '') else None,
            'vip_id': None,
            'alsoIn': None,
            'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None,
            'rates_hlx': None,
            'links': {'official': info['url'], 'hlx': None},
            'promotion': None,
            'note': note,
        }
        if not entry['brand']:
            raise SystemExit('brand 비어 있음: ' + code)
        if hit:
            assert hit['id'] not in {a['vip_id'] for a in added if a['vip_id']}
            entry['vip_id'] = hit['id']
            entry['alsoIn'] = hit['id']
            entry['hlx_in'] = True
            entry['links']['hlx'] = 'https://hotel.hotelux.com/hotelDetail/' + str(hit['ref_id'])
            entry['rates_hlx'] = hit.get('rates')
            entry['promotion'] = hit.get('promotion')
            entry['note'] += ' ① 호텔럭스 %s(%s)에 같은 호텔이 있어 호럭 요금·예약 링크를 연결했습니다.' % (
                hit['id'], hit.get('brand') or '')
            linked.append((hid, code, entry['english'], hit['id'], how))
        added.append(entry)
        city_stat[city] = city_stat.get(city, 0) + 1

    assert [h['id'] for h in added] == ['hy%02d' % i for i in range(276, 300)]
    assert len({h['code'] for h in added}) == 24

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'
    with open(TAB, 'w', encoding='utf-8') as f:
        json.dump(tab, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')

    print('기존 %d + 신규 %d = %d곳' % (len(before), len(added), len(tab['hotels'])))
    for h in added:
        print('  %s %-6s %-10s %-2s %-22s 포인트 %3d일  %s' % (
            h['id'], h['code'], h['city'], h['category'], h['brand'],
            sum(1 for v in h['points']['$v'] if v is not None), h['english']))
    print('도시별', city_stat)
    tot = len(added) * 365
    priced = sum(1 for a in added for v in a['points']['$v'] if v is not None)
    print('신규 셀 %d 중 값 %d · null %d (번들 %d)' % (tot, priced, tot - priced, meta['days_priced_total']))
    all_cells = sum(1 for a in tab['hotels'] for v in a['points']['$v'] if v is not None)
    print('④ 하얏트 %d곳 · %d칸 · 포인트 값 %d칸' % (len(tab['hotels']), len(tab['hotels']) * 365, all_cells))
    print('① 호텔럭스 겹침 %d곳 %s' % (len(linked), linked))
    for c, v in sorted(city_stat.items()):
        print('  %-10s %2d곳' % (c, v))


if __name__ == '__main__':
    main()
