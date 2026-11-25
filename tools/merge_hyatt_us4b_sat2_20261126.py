#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 미국 4차-B 샌안토니오(San Antonio, TX) 2차(마지막) 4곳(365일 아워드 포인트) 병합 (2026-11-26)

입력  : memory/clones/a03363f4-no71/pickle/2026-11-26-0226/received/0-hyatt_us_sanantonio_batch2.json
        (meta: US-Hub4B-SanAntonio-Batch2-4 · window 2026-12-01~2027-11-30 ·
         days_priced_total 1112 · 2026-11-26 02:25 KST 실측)
        No.7(@no_7) 피클이 전달한 본.
대상  : data/app/tab10_hyatt.json  (hy01~hy317 → hy318~hy321, 총 321곳)

- 기존 317곳은 값·순서 그대로 보존
- 번들 스키마(spirit_code·name·brand·city·state·category·url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지
- city 는 원자료 표기(San Antonio)를 그대로 쓰고, 주(州) 구분은 note 에 적는다(4곳 모두 텍사스주)
- rates_official·rates_hlx 는 null(공홈 현금가·호럭 요금 이번 배치 없음)
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 후 겹치면 연결
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
    WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-0226/received/0-hyatt_us_sanantonio_batch2.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

CITY_ORDER = ['San Antonio']
STATE_KR = {'Texas': '텍사스주'}
CITY_KR = {'San Antonio': '샌안토니오'}
COLLECTED = '2026-11-26 02:25 KST'
FIRST_ID = 318

# sansh 는 2027-03-24~2027-11-30 270일이 soldOutHotel 장기 블록으로 재조회 확정된 케이스
EXTRA_NOTE = {
    'sansh': ('2027-03-24~11-30 270일은 60일 창 전체가 days:{} + responseInfo soldOutHotel 로 응답했고, '
              '블록 안 7일 창 11개 지점(2027-04-12~18 · 05-10~16 · 06-07~13 · 06-20~26 · 07-12~18 · '
              '08-10~16 · 08-22~28 · 09-07~13 · 10-05~11 · 11-10~16 · 11-24~30)을 재조회해도 같은 응답이어서 '
              '매진·미오픈으로 확정했습니다'),
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
    assert len(before) == 317, len(before)
    assert before[-1]['id'] == 'hy317', before[-1]['id']

    bundle = json.load(open(BUNDLE, encoding='utf-8'))
    meta = bundle['meta']
    assert meta['hotels_total'] == 4 and meta['hotels_collected'] == 4
    assert meta['days_priced_total'] == 1112, meta['days_priced_total']
    assert meta['window'] == '2026-12-01~2027-11-30'
    assert meta['collected_at'] == COLLECTED
    new = bundle['hotels']
    assert len(new) == 4, len(new)
    assert set(new) == {'sanhc', 'satrs', 'sansh', 'satth'}, sorted(new)
    nb = {c: h.get('null_breakdown') or {} for c, h in new.items()}

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
    exist_kr = {norm(x['name']): x['id'] for x in before}
    exist_ids = {x['id'] for x in before}

    ordered = []
    for city in CITY_ORDER:
        ordered += sorted([c for c, h in new.items() if clean(h['city']) == city],
                          key=lambda c: clean(new[c]['name']))
    assert len(ordered) == 4, ordered
    assert ordered == ['sanhc', 'satrs', 'sansh', 'satth'], ordered

    added, linked, city_stat = [], [], {}
    for i, code in enumerate(ordered):
        info = new[code]
        hid = 'hy%02d' % (FIRST_ID + i)
        assert hid not in exist_ids
        assert code not in exist_codes, 'duplicate code %s (%s)' % (code, exist_codes.get(code))
        n = norm(info['name'])
        assert n not in exist_names, 'duplicate name %s -> %s' % (info['name'], exist_names[n])

        pts = [info['points'].get(d) for d in DATES]
        assert len(info['points']) == 365, (code, len(info['points']))
        priced = sum(1 for v in pts if v is not None)
        assert priced == info['days_priced'], (code, priced, info['days_priced'])
        assert all(isinstance(v, int) for v in pts if v is not None), code
        assert min(v for v in pts if v is not None) == info['min_points'], code
        assert max(v for v in pts if v is not None) == info['max_points'], code

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
        state = clean(info.get('state'))
        nbk = nb.get(code) or {}
        if priced == 365:
            null_txt = '365일 전부 값이 있습니다'
        else:
            null_txt = '값 없는 %d일은 재고 없음·예약창 밖·미조회를 구분하지 않음(NA)' % (365 - priced)
        if nbk:
            parts = []
            if nbk.get('empty_day_object'):
                parts.append('스탠다드룸 응답 없음 %d일' % nbk['empty_day_object'])
            if nbk.get('no_key_in_response'):
                parts.append('날짜 키 없음 %d일' % nbk['no_key_in_response'])
            if parts:
                null_txt += ' [%s]' % ' · '.join(parts)
        if code in EXTRA_NOTE:
            null_txt += ' ' + EXTRA_NOTE[code]
        note = ('스탠다드 아워드 365일 실측(%s · hyatt.com) — %s %s · 포인트 %d일 · %s. 공홈 현금가 미수집.'
                % (COLLECTED, STATE_KR.get(state, state), CITY_KR.get(city, city), priced, null_txt))

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

    assert [h['id'] for h in added] == ['hy%02d' % i for i in range(FIRST_ID, FIRST_ID + 4)]
    assert len({h['code'] for h in added}) == 4
    assert [h['id'] for h in before] == [h['id'] for h in tab['hotels']]

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'
    with open(TAB, 'w', encoding='utf-8') as f:
        json.dump(tab, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')

    print('기존 %d + 신규 %d = %d곳' % (len(before), len(added), len(tab['hotels'])))
    for h in added:
        vals = [v for v in h['points']['$v'] if v is not None]
        print('  %s %-6s %-12s %-2s %-16s 포인트 %3d일 (%s~%s)  %s' % (
            h['id'], h['code'], h['city'], h['category'], h['brand'],
            len(vals), min(vals), max(vals), h['english']))
        print('     ', h['note'])
    print('도시별', city_stat)
    tot = len(added) * 365
    priced = sum(1 for a in added for v in a['points']['$v'] if v is not None)
    print('신규 셀 %d 중 값 %d · null %d (번들 %d)' % (tot, priced, tot - priced, meta['days_priced_total']))
    all_cells = sum(len(a['points']['$v']) for a in tab['hotels'])
    all_priced = sum(1 for a in tab['hotels'] for v in a['points']['$v'] if v is not None)
    print('④ 하얏트 %d곳 · %d칸 · 포인트 값 %d칸' % (len(tab['hotels']), all_cells, all_priced))
    print('미국 %d곳' % sum(1 for a in tab['hotels'] if a['region'] == '미국'))
    print('① 호텔럭스 겹침 %d곳 %s' % (len(linked), linked))
    from collections import Counter
    print('미국 도시 상위', Counter(a['city'] for a in tab['hotels'] if a['region'] == '미국').most_common())
    tx = [a for a in tab['hotels'] if a['region'] == '미국' and a['city'] in (
        'Austin', 'Houston', 'Dallas', 'San Antonio')]
    print('텍사스 %d곳' % len(tx), Counter(a['city'] for a in tx).most_common())


if __name__ == '__main__':
    main()
