#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 태국 1차 방콕 4곳(365일 스탠다드 아워드 포인트) 병합 (2026-11-26)

입력  : memory/clones/a03363f4-no71/pickle/2026-11-26-1127/received/0-hyatt_thailand_batch1_4.json
        (meta: Thailand-Bangkok-1 · window 2026-12-01~2027-11-30 ·
         days_priced_total 1383 · collected_at 2026-11-26 11:20~11:55 KST)
        No.7(@no_7) 피클이 전달한 본.
대상  : data/app/tab10_hyatt.json  (347곳 → 350곳)

■ 이번 배치의 특이점 — bangh 는 기존 hy28(bkkgh)과 같은 호텔이다
- 탭에는 이미 hy28 "그랜드 하얏트 에라완 방콕"(code bkkgh)이 있었고, 2026-11-22 수집 때
  365일 전부 soldOutHotel · shop/rooms/bkkgh Error 로 포인트가 한 칸도 없었다.
- 이번 실측은 같은 호텔의 실제 spiritCode 인 bangh 로 받아 361일 어워드가 확인됐다
  (hyatt.com 공식 URL .../grand-hyatt-erawan-bangkok/bangh · ±2일 창 재조회 불일치 0).
- 그래서 새 카드를 하나 더 붙여 같은 호텔이 두 장이 되지 않도록, hy28 의 코드를
  bkkgh → bangh 로 바로잡고 이번 값·note 를 채운다(id·순서·alsoIn 그대로).
  신규 추가는 bkkaz · bkkzk · bkkzs 3곳(hy348~hy350)이다. 347 → 350곳.

- 번들 스키마(spirit_code·name·brand·city·state·country·category·url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지
- 동남아 기존 카드와 같이 city 는 국문 「방콕」, brand 는 「하얏트」, name 은 국문·english 는 영문
- rates_official·rates_hlx 는 null(이 엔드포인트는 어워드 포인트만 제공 · rate 전 일 null)
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 후 겹치면 연결
  (① 탭 방콕 5곳은 페어몬트·킴튼·월도프·만다린·카펠라로 하얏트가 없어 겹침 0곳 — 공홈 단일 링크)
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
    WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-1127/received/0-hyatt_thailand_batch1_4.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

COLLECTED = '2026-11-26 11:20~11:55 KST'
FIRST_ID = 348

KR_NAME = {
    'bkkaz': '안다즈 원 방콕',
    'bangh': '그랜드 하얏트 에라완 방콕',
    'bkkzk': '하얏트 플레이스 방콕 수쿰윗 1',
    'bkkzs': '하얏트 플레이스 방콕 수쿰윗 24',
}

NOTE = {
    'bkkaz': (
        '스탠다드 아워드 365일 실측(2026-11-26 11:20~11:55 KST · hyatt.com · 태국 방콕) — '
        '포인트 360일 · 값 없는 5일(2026-12-03 · 12-05 · 12-06 · 12-09 · 12-20)은 그날 응답에 '
        '표준룸·스탠다드 스위트 오브젝트가 모두 비어 있는 날(어워드 미표출: 매진·미개방 구분 불가)이고 '
        '±2일 좁은 창 재조회에서도 같아 보간 없이 —입니다. 20,000P OFF_PEAK 299일 · 25,000P STANDARD '
        '57일 · 35,000P SUPER_PEAK 2일(2026-12-30~31) · 30,000P PEAK 1일(2026-12-29) · '
        '15,000P SUPER_OFF_PEAK 1일 순입니다. 카테고리 5(Andaz). 현금 요금(STANDARD_ROOM.rate)은 '
        '365일 전부 null — 이 엔드포인트가 어워드 포인트만 주므로 공홈 현금가는 미수집입니다.'),
    'bangh': (
        '스탠다드 아워드 365일 실측(2026-11-26 11:20~11:55 KST · hyatt.com · 태국 방콕) — '
        '포인트 361일 · 값 없는 4일(2026-12-02 · 2027-01-05~01-07)은 보간 없이 —입니다'
        '(2026-12-02 · 2027-01-07 은 응답에 날짜 키가 없고, 2027-01-05~01-06 은 그날 표준룸 '
        '오브젝트가 비어 있음 · 좁은 창 재조회에서 동일). 12,000P OFF_PEAK 302일 · 15,000P STANDARD '
        '55일 · 20,000P SUPER_PEAK 2일(2026-12-30~31) · 17,500P PEAK 1일(2026-12-29) · '
        '8,000P SUPER_OFF_PEAK 1일 순입니다. 카테고리 3(Grand Hyatt). '
        '※ 코드 정정: 이 카드는 2026-11-22 수집 때 master 목록의 bkkgh 로 들어와 365일 전부 '
        'soldOutHotel(shop/rooms/bkkgh 도 Error)이었는데, 같은 호텔의 실제 spiritCode 는 bangh 이고 '
        '이번 실측에서 361일 어워드가 확인됐습니다(hyatt.com 공식 URL .../grand-hyatt-erawan-bangkok/bangh). '
        '같은 호텔이 두 장이 되지 않도록 이 카드의 코드를 bkkgh → bangh 로 바로잡고 값을 채웠습니다. '
        '이전 note 의 「2026-05~2027 2Q 리노베이션」 정황은 bkkgh 의 soldOutHotel 응답만 보고 적은 '
        '추정이며, bangh 실측에서는 12개월 가운데 361일이 예약 가능합니다. 현금 요금은 365일 전부 '
        'null — 공홈 현금가 미수집.'),
    'bkkzk': (
        '스탠다드 아워드 365일 실측(2026-11-26 11:20~11:55 KST · hyatt.com · 태국 방콕) — '
        '포인트 338일 · 값 없는 27일은 전부 응답에 날짜 키가 없는 날(no_key_in_response)로 '
        '2026-12-01~04 · 12-09~13 · 12-25~2027-01-01 8일 연속 · 2027-01-15~16 · 01-18~19 · '
        '01-27~31 · 02-12 에 몰려 있고, 매진인지 어워드 미개방인지는 이 엔드포인트로 구분되지 않아 '
        '보간 없이 —입니다(좁은 창 재조회 동일). 4,500P OFF_PEAK 285일 · 6,000P STANDARD 52일 · '
        '3,000P SUPER_OFF_PEAK 1일 순입니다. 카테고리 1(Hyatt Place). 현금 요금은 365일 전부 null — '
        '공홈 현금가 미수집.'),
    'bkkzs': (
        '스탠다드 아워드 365일 실측(2026-11-26 11:20~11:55 KST · hyatt.com · 태국 방콕) — '
        '포인트 324일 · 값 없는 41일은 전부 응답에 날짜 키가 없는 날(no_key_in_response)로 '
        '2026-12-24~2027-01-02 10일 연속 · 2026-12-13~18 · 2027-02-08~14 · 02-16~19 등에 몰려 있고 '
        '매진·어워드 미개방 구분이 안 돼 보간 없이 —입니다(좁은 창 재조회 동일). 4,500P OFF_PEAK '
        '297일 · 6,000P STANDARD 25일 · 3,000P SUPER_OFF_PEAK 2일 순입니다. 카테고리 1(Hyatt Place). '
        '현금 요금은 365일 전부 null — 공홈 현금가 미수집.'),
}

ORDER = ['bkkaz', 'bkkzk', 'bkkzs']   # bangh 는 기존 hy28 자리에서 정정


def clean(s):
    s = unicodedata.normalize('NFC', str(s or ''))
    s = ''.join(' ' if (ch.isspace() or unicodedata.category(ch) in ('Cf', 'Cc')) else ch for ch in s)
    return ' '.join(s.split())


def norm(s):
    s = unicodedata.normalize('NFKD', clean(s)).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def norm_ko(s):
    """국문 이름 비교용 — 한글을 지우지 않는다(norm 은 라틴·숫자만 남겨 한글이 전부 ''가 됨)."""
    s = unicodedata.normalize('NFC', clean(s)).lower()
    return re.sub(r'[\s\W_]+', '', s)


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 347, len(before)
    assert before[-1]['id'] == 'hy347', before[-1]['id']

    bundle = json.load(open(BUNDLE, encoding='utf-8'))
    meta = bundle['meta']
    assert meta['group'] == 'Thailand-Bangkok-1', meta['group']
    assert meta['hotels_total'] == 4 and meta['hotels_collected'] == 4
    assert meta['days_priced_total'] == 1383, meta['days_priced_total']
    assert meta['days_total'] == 1460
    assert meta['window'] == '2026-12-01~2027-11-30'
    assert meta['collected_at'] == COLLECTED, meta['collected_at']
    assert meta['pending'] == []
    new = bundle['hotels']
    assert set(new) == {'bkkaz', 'bangh', 'bkkzk', 'bkkzs'}, sorted(new)
    assert {c: new[c]['days_priced'] for c in new} == {
        'bkkaz': 360, 'bangh': 361, 'bkkzk': 338, 'bkkzs': 324}
    assert sum(new[c]['days_priced'] for c in new) == 1383

    # ── ① 호텔럭스 대조용 색인 ──────────────────────────────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    vip_rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
    assert len(vip_rows) == 161, len(vip_rows)
    by_code, by_english, by_korean = {}, {}, {}
    for r in vip_rows:
        if r.get('ref_id'):
            by_code[str(r['ref_id']).strip().lower()] = r
        if r.get('english'):
            by_english.setdefault(norm(r['english']), []).append(r)
        if r.get('name'):
            by_korean.setdefault(norm_ko(r['name']), []).append(r)

    # ① 탭 방콕 5곳은 하얏트가 아님을 먼저 확인 (도시 단위 비교)
    bkk_vip = [r for r in vip_rows if clean(r.get('city')) == '방콕']
    assert len(bkk_vip) == 5, [r.get('name') for r in bkk_vip]
    assert not any('hyatt' in clean(r.get('english')).lower() or '하얏트' in clean(r.get('name'))
                   for r in bkk_vip), bkk_vip

    exist_codes = {x['code']: x['id'] for x in before}
    exist_names = {}
    for x in before:
        exist_names.setdefault(norm(x['english']), []).append(x['id'])
    exist_kr = {}
    for x in before:
        exist_kr.setdefault(norm_ko(x['name']), []).append(x['id'])
    exist_ids = {x['id'] for x in before}

    # ── hy28(bkkgh) → bangh 코드 정정 ──────────────────────────────
    old = None
    for x in before:
        if x['id'] == 'hy28':
            old = x
    assert old is not None
    assert old['code'] == 'bkkgh', old['code']
    assert old['english'] == 'Grand Hyatt Erawan Bangkok', old['english']
    assert old['name'] == '그랜드 하얏트 에라완 방콕', old['name']
    assert old['category'] == 3, old['category']
    assert old['region'] == '동남아' and old['city'] == '방콕'
    assert old['vip_id'] is None and old['alsoIn'] is None and old['hlx_in'] is False
    assert all(v is None for v in old['points']['$v']), 'hy28 에 이미 값이 있음'
    assert 'bkkgh' not in exist_codes or exist_codes['bkkgh'] == 'hy28'
    assert 'bangh' not in exist_codes, exist_codes.get('bangh')

    info = new['bangh']
    assert info['country'] == 'Thailand' and info['city'] == 'Bangkok'
    assert info['category'] == '3'
    assert norm(info['name']) == norm(old['english'])
    pts = [info['points'].get(d) for d in DATES]
    assert len(pts) == 365 and sum(1 for v in pts if v is not None) == 361

    # ① 대조 — 코드·영문명·국문명
    for code in new:
        h = new[code]
        assert by_code.get(code.lower()) is None, ('① 코드 겹침', code, by_code.get(code.lower()))
        assert not by_english.get(norm(h['name'])), ('① 영문명 겹침', code, by_english.get(norm(h['name'])))
        assert not by_korean.get(norm_ko(KR_NAME[code])), ('① 국문명 겹침', code,
                                                         by_korean.get(norm_ko(KR_NAME[code])))

    old['code'] = 'bangh'
    old['points'] = {'$d': DATES[0], '$v': pts}
    old['links'] = {'official': 'https://www.hyatt.com/shop/rooms/bangh', 'hlx': None}
    old['note'] = NOTE['bangh']

    # ── 신규 3곳 ────────────────────────────────────────────────────
    added = []
    for i, code in enumerate(ORDER):
        info = new[code]
        hid = 'hy%02d' % (FIRST_ID + i)
        assert hid not in exist_ids, hid
        assert code not in exist_codes, 'duplicate code %s' % code
        assert norm(info['name']) not in exist_names, ('duplicate english', info['name'])
        assert norm_ko(KR_NAME[code]) not in exist_kr, ('duplicate korean', KR_NAME[code])
        assert info['country'] == 'Thailand' and info['city'] == 'Bangkok'
        pts = [info['points'].get(d) for d in DATES]
        assert len(pts) == 365
        assert sum(1 for v in pts if v is not None) == info['days_priced']
        assert all(v is None or isinstance(v, int) for v in pts)
        assert info['category'] in ('1', '2', '3', '4', '5', '6', '7', '8')

        entry = {
            'id': hid,
            'group': 'hyatt',
            'code': code,
            'region': '동남아',
            'city': '방콕',
            'name': KR_NAME[code],
            'english': clean(info['name']),
            'brand': '하얏트',
            'category': int(info['category']),
            'vip_id': None,
            'alsoIn': None,
            'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None,
            'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % code, 'hlx': None},
            'promotion': None,
            'note': NOTE[code],
        }
        added.append(entry)

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'

    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    cells = sum(len(h['points']['$v']) for h in tab['hotels'])
    priced = sum(1 for h in tab['hotels'] for v in h['points']['$v'] if v is not None)
    sea = [h for h in tab['hotels'] if h['region'] == '동남아']
    bkk = [h['code'] for h in sea if h['city'] == '방콕']
    print('added', [(a['id'], a['code'], a['name']) for a in added])
    print('corrected hy28 bkkgh →', [x for x in tab['hotels'] if x['id'] == 'hy28'][0]['code'],
          'priced', sum(1 for v in [x for x in tab['hotels'] if x['id'] == 'hy28'][0]['points']['$v']
                        if v is not None))
    print('hotels', len(tab['hotels']), 'cells', cells, 'priced', priced)
    print('동남아', len(sea), [h['code'] for h in sea])
    print('방콕', len(bkk), bkk)
    assert len(tab['hotels']) == 350
    assert len(sea) == 10 and len(bkk) == 6


if __name__ == '__main__':
    main()
