#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 유럽 4개 배치 총 12곳(이탈리아 밀라노 2 · 그리스 7 · 포르투갈 3) 병합 (2026-11-26)

입력  : memory/clones/a03363f4-no71/pickle/2026-11-26-0258/received/
        0-hyatt_eu_milan_2.json        (EU-Italy-Milan-2 · 690칸 · 03:00~03:15 KST)
        0-hyatt_eu_greece_batch1.json  (EU-Greece-Batch1-4 · 683칸 · 03:05~03:25 KST)
        0-hyatt_eu_greece_batch2.json  (EU-Greece-Batch2-3 · 356칸 · 03:30~04:05 KST)
        0-hyatt_eu_portugal_batch1.json(EU-Portugal-Batch1-3 · 630칸 · 03:40~04:20 KST)
        (window 2026-12-01~2027-11-30 · 12 × 365 = 4,380칸 가운데 2,359칸)
        No.7(@no_7) 피클이 전달한 본.
대상  : data/app/tab10_hyatt.json  (hy01~hy332 → hy333~hy344, 총 344곳)

- 기존 332곳은 값·순서 그대로 보존
- 번들 스키마(spirit_code·name·brand·city·state·country·category·url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지
- city 는 원자료 표기(Milan · Athens · Thessaloniki · Halkidiki · Paros · Corfu · Santorini ·
  Zakynthos · Lisbon)를 그대로 쓰고 국가·주는 note 에 적는다
- rates_official·rates_hlx 는 null(공홈 현금가·호럭 요금 이번 배치 없음)
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 후 겹치면 연결
  (① 탭에 이탈리아·그리스·포르투갈 지점이 없어 겹침 0곳 — 공홈 단일 링크)
- 시즌제·미판매 6곳(zoeha·pasdh·drcfu·jtrub·aszak·lissl)은 매진과 섞지 않고 사유를 note 에 적는다.
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
RECEIVED = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-0258/received')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

BATCHES = [
    ('0-hyatt_eu_milan_2.json', 690, ('mxpct', 'milph')),
    ('0-hyatt_eu_greece_batch1.json', 683, ('athgh', 'zoeha', 'pasdh', 'drcfu')),
    ('0-hyatt_eu_greece_batch2.json', 356, ('thess', 'jtrub', 'aszak')),
    ('0-hyatt_eu_portugal_batch1.json', 630, ('lisaz', 'lishr', 'lissl')),
]

CITY_ORDER = ['Milan', 'Athens', 'Thessaloniki', 'Halkidiki', 'Paros',
              'Corfu', 'Santorini', 'Zakynthos', 'Lisbon']
FIRST_ID = 333

NOTE = {
    'mxpct': ('스탠다드 아워드 365일 실측(2026-11-26 03:00~03:15 KST · hyatt.com · 이탈리아 '
              '롬바르디아주 밀라노) — 포인트 354일 · 값 없는 11일(날짜 키 없음 5 · 그날 스탠다드룸 '
              '응답 없음 6: 2026-12-02 · 12-04 · 12-17 · 2027-02-02~02-03 · 02-17~02-18 · '
              '09-02~09-05)은 매진·예약창 밖·미오픈을 구분하지 않고 보간 없이 —입니다. '
              '최저 15,000P(SUPER_OFF_PEAK 26일) ~ 최고 35,000P(SUPER_PEAK 26일 · PEAK 41일 · '
              'STANDARD 87일 · OFF_PEAK 174일). 연중 운영으로 시즌 휴관 공지가 없습니다. '
              '공홈 현금가 미수집.'),
    'milph': ('스탠다드 아워드 365일 실측(2026-11-26 03:00~03:15 KST · hyatt.com · 이탈리아 '
              '롬바르디아주 밀라노) — 포인트 336일 · 값 없는 29일(날짜 키 없음 21 · 그날 스탠다드룸 '
              '응답 없음 8: 2027-01-15~01-17 · 02-23~02-27 · 04-12~04-17 · 06-18~06-21 · '
              '09-02~09-05 · 09-20~09-24 · 09-27~09-28 — 그 8일은 PREMIUM_SUITE만 응답해 '
              '스탠다드룸 어워드 매진)은 보간 없이 —입니다. 최저 35,000P(SUPER_OFF_PEAK 23일) ~ '
              '최고 75,000P(SUPER_PEAK 19일 · PEAK 36일 · STANDARD 83일 · OFF_PEAK 175일). '
              '연중 운영으로 시즌 휴관 공지가 없습니다. 공홈 현금가 미수집.'),
    'athgh': ('스탠다드 아워드 365일 실측(2026-11-26 03:05~03:25 KST · hyatt.com · 그리스 아티키주 '
              '아테네) — 포인트 351일 · 값 없는 14일(날짜 키 없음 4: 2027-02-01~02-04 · 그날 '
              '스탠다드룸 응답 없음 10: 2026-12-04 · 2027-01-25~01-27 · 02-19 · 03-12~03-13 · '
              '03-15 · 09-14 · 10-20 — 그 10일은 STANDARD_SUITE만 응답해 스탠다드룸 어워드 매진)은 '
              '보간 없이 —입니다. 최저 12,000P(SUPER_OFF_PEAK 90일) ~ 최고 20,000P(STANDARD 113일 · '
              'OFF_PEAK 148일). 연중 운영입니다. 공홈 현금가 미수집.'),
    'thess': ('스탠다드 아워드 365일 실측(2026-11-26 03:30~04:05 KST · hyatt.com · 그리스 '
              '테살로니키) — 포인트 356일 · 값 없는 9일(날짜 키 없음 8: 2026-12-19 · '
              '12-31~2027-01-01 · 2027-02-14 · 03-11~03-12 · 06-18~06-19 · 그날 스탠다드룸 '
              '응답 없음 1: 2027-02-11)은 보간 없이 —입니다. 최저 8,000P(SUPER_OFF_PEAK 235일) ~ '
              '최고 15,000P(STANDARD 84일 · OFF_PEAK 37일). 연중 운영입니다. 공홈 현금가 미수집.'),
    'zoeha': ('스탠다드 아워드 365일 실측(2026-11-26 03:05~03:25 KST · hyatt.com · 그리스 '
              '할키디키) — 포인트 172일 · 값 없는 193일(날짜 키 없음 193)은 보간 없이 —입니다. '
              '이 호텔은 시즌제 리조트로 2027-04-29 개관 ~ 2027-10-17 폐관까지만 운영합니다 — '
              '휴관 기간(2026-12-01~2027-04-28 149일 · 2027-10-18~11-30 44일)은 예약 화면이 '
              'soldOutHotel 로 답하고 1박 어워드 재고가 없습니다(개관·폐관 경계 창 재조회로 확인). '
              '최저 20,000P(SUPER_OFF_PEAK 49일) ~ 최고 30,000P(STANDARD 86일 · OFF_PEAK 37일). '
              '공홈 현금가 미수집.'),
    'pasdh': ('스탠다드 아워드 365일 실측(2026-11-26 03:05~03:25 KST · hyatt.com · 그리스 파로스) — '
              '포인트 160일 · 값 없는 205일(날짜 키 없음 205)은 보간 없이 —입니다. 이 호텔은 시즌제 '
              '리조트로 2027-05-10 재개관 ~ 2027-10-16 폐관까지만 운영합니다 — 휴관 기간'
              '(2026-12-01~2027-05-09 160일 · 2027-10-17~11-30 45일)은 예약 화면이 soldOutHotel 로 '
              '답합니다. 호텔 페이지 공지도 겨울철 휴관과 2027년 5월 10일 재개관을 알려 API 개관일과 '
              '일치합니다. 최저 20,000P(SUPER_OFF_PEAK 5일) ~ 최고 30,000P(STANDARD 150일 · '
              'OFF_PEAK 5일). 공홈 현금가 미수집.'),
    'drcfu': ('스탠다드 아워드 365일 실측(2026-11-26 03:05~03:25 KST · hyatt.com · 그리스 코르푸) — '
              '포인트 0일 · 365일 모두 값이 없습니다(보간 없음). 겨울 휴관 기간'
              '(2026-12-01~2027-04-24 145일 · 2027-10-31~11-30 31일 = 176일)은 예약 화면이 '
              'soldOutHotel 로 답하고, 운영 기간(2027-04-25~2027-10-30 189일)에도 STANDARD_ROOM 이 '
              '한 번도 없이 PREMIUM_SUITE·PREMIUM_SUITE_3(스위트)만 응답합니다(예: 2027-07-10~12 '
              'PREMIUM_SUITE 50,000P · PREMIUM_SUITE_3 65,000P). 이 호텔은 스탠다드룸이 아니라 '
              '스위트 등급으로만 어워드가 열려 있어 이 창에는 스탠다드 아워드 포인트가 없습니다. '
              '카테고리는 올인클루시브 A2 입니다. 공홈 현금가 미수집.'),
    'jtrub': ('스탠다드 아워드 365일 실측(2026-11-26 03:30~04:05 KST · hyatt.com · 그리스 산토리니) — '
              '포인트 0일 · 365일 모두 값이 없습니다(보간 없음). 날짜 키가 있는 구간은 '
              '2027-05-01~2027-10-31(184일)뿐이고 그 184일은 모두 빈 오브젝트이며 나머지 181일은 '
              '날짜 키 자체가 없습니다(soldOutHotel). 시즌(2027-05-01~10-31) 중 실제 예약 페이지를 '
              'Use Points 로 열면 스탠다드룸 어워드 없이 스위트 Points Plus Cash 만 나오고'
              '(예: STANDARD_SUITE 22,500P+€450 · PREMIUM_SUITE 25,000P+€495, 2박), 현금 객실은 '
              '정상 판매 중입니다 — 영업 중이나 이 창에 스탠다드룸 포인트 어워드가 없습니다. '
              '공홈 현금가 미수집.'),
    'aszak': ('스탠다드 아워드 365일 실측(2026-11-26 03:30~04:05 KST · hyatt.com · 그리스 자킨토스) — '
              '포인트 0일 · 365일 모두 날짜 키 없이 soldOutHotel 응답입니다(보간 없음). 호텔 페이지에 '
              '휴관 공지가 없고 2027-07-05~07 실제 예약 페이지에서 현금 객실이 판매(€229~314)되며, '
              'Use Points 모드에서는 Hyatt 화면이 이 기간에 포인트·프리나이트 어워드가 없다고 '
              '안내합니다 — 영업 중이나 이 창에 포인트·프리나이트 어워드 재고가 없습니다. '
              '카테고리는 A0(올인클루시브)입니다. 공홈 현금가 미수집.'),
    'lisaz': ('스탠다드 아워드 365일 실측(2026-11-26 03:40~04:20 KST · hyatt.com · 포르투갈 리스본) — '
              '포인트 346일 · 값 없는 19일(날짜 키 없음 5 · 그날 스탠다드룸 응답 없음 14: '
              '2027-03-22~03-23 · 04-05 · 04-12 · 05-04 · 05-25~05-29 · 06-05~06-10 · 09-05 · '
              '09-27 · 10-04)은 보간 없이 —입니다. 스위트만 있는 날은 STANDARD_SUITE 포인트가 '
              '응답하므로 스탠다드룸 어워드만 없는 날입니다(예: 2027-03-22~23 STANDARD_SUITE '
              '40,000P). 최저 20,000P(SUPER_OFF_PEAK 93일) ~ 최고 30,000P(STANDARD 76일 · '
              'OFF_PEAK 177일). 공홈 현금가 미수집.'),
    'lishr': ('스탠다드 아워드 365일 실측(2026-11-26 03:40~04:20 KST · hyatt.com · 포르투갈 리스본) — '
              '포인트 284일 · 값 없는 81일(날짜 키 없음 22 · 그날 스탠다드룸 응답 없음 59)은 보간 '
              '없이 —입니다. 결번이 흩어져 13개 창으로 다시 조회했고, 빈 날에도 PREMIUM_SUITE·'
              'STANDARD_SUITE 포인트는 응답해 호텔은 정상 영업 중이고 스탠다드룸 어워드 재고만 없는 '
              '날입니다(예: 2026-12-19~24 · 2027-03-22~30). 최저 15,000P(SUPER_OFF_PEAK 70일) ~ '
              '최고 25,000P(STANDARD 69일 · OFF_PEAK 145일). 공홈 현금가 미수집.'),
    'lissl': ('스탠다드 아워드 365일 실측(2026-11-26 03:40~04:20 KST · hyatt.com · 포르투갈 리스본) — '
              '포인트 0일 · 365일 모두 날짜 키 없이 soldOutHotel 응답입니다(보간 없음). World of '
              'Hyatt 에 아직 참여하지 않는 호텔(woh_participating=false)이라 포인트·프리나이트 '
              '어워드를 판매하지 않습니다 — 호텔 페이지 공지가 곧 개관하며 World of Hyatt 에 '
              '참여하지 않는다고 밝히고 있습니다. 예약 페이지에서 현금 객실은 €342~415 로 판매 중이고 '
              'Use Points 로는 포인트·프리나이트 어워드가 없다는 안내만 나옵니다. 개관일 표기가 '
              '페이지마다 달라(공지 팝업 2027-04-30부터 · 예약 페이지 상단 2026-12-01부터) 확정하지 '
              '않았고, 어느 쪽이든 이 창에는 어워드 재고가 없습니다. 원본에 카테고리가 없습니다. '
              '공홈 현금가 미수집.'),
}

ITALY_WORDS = ('italy', 'italia', '이탈리아', 'milan', 'milano', '밀라노', 'rome', 'roma', '로마',
               'florence', 'firenze', '피렌체', 'venice', 'venezia', '베네치아', 'sardinia', '사르데냐')
GREECE_WORDS = ('greece', 'hellas', '그리스', 'athens', 'αθηνα', '아테네', 'thessaloniki', '테살로니키',
                'halkidiki', '할키디키', 'paros', '파로스', 'corfu', 'kerkyra', '코르푸',
                'santorini', '산토리니', 'zakynthos', '자킨토스', 'crete', '크레타', 'mykonos', '미코노스',
                'rhodes', '로도스')
PORTUGAL_WORDS = ('portugal', '포르투갈', 'lisbon', 'lisboa', '리스본', 'porto', '포르투',
                  'algarve', '알가르베', 'comporta', 'sintra', '신트라')


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
    assert len(before) == 332, len(before)
    assert before[-1]['id'] == 'hy332', before[-1]['id']

    new, collected = {}, {}
    total = 0
    for fname, want, codes in BATCHES:
        bundle = json.load(open(os.path.join(RECEIVED, fname), encoding='utf-8'))
        meta = bundle['meta']
        assert meta['days_priced_total'] == want, (fname, meta['days_priced_total'])
        assert meta['window'] == '2026-12-01~2027-11-30'
        assert meta['hotels_collected'] == meta['hotels_total'] == len(codes)
        assert meta['pending'] == []
        assert set(bundle['hotels']) == set(codes), (fname, sorted(bundle['hotels']))
        for c in codes:
            assert c not in new, c
            new[c] = bundle['hotels'][c]
            collected[c] = meta['collected_at']
        total += want
    assert len(new) == 12, len(new)
    assert total == 2359, total
    assert {c: new[c]['days_priced'] for c in new} == {
        'mxpct': 354, 'milph': 336, 'athgh': 351, 'zoeha': 172, 'pasdh': 160, 'drcfu': 0,
        'thess': 356, 'jtrub': 0, 'aszak': 0, 'lisaz': 346, 'lishr': 284, 'lissl': 0}
    assert {c: new[c]['days_null'] for c in new} == {
        'mxpct': 11, 'milph': 29, 'athgh': 14, 'zoeha': 193, 'pasdh': 205, 'drcfu': 365,
        'thess': 9, 'jtrub': 365, 'aszak': 365, 'lisaz': 19, 'lishr': 81, 'lissl': 365}

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

    # ① 탭에 이탈리아·그리스·포르투갈 지점이 있는지 먼저 확인 (도시·영문명·국문명·지역 전수)
    for r in vip_rows:
        blob = ' '.join(clean(r.get(k)) for k in ('city', 'name', 'english', 'region')).lower()
        for words in (ITALY_WORDS, GREECE_WORDS, PORTUGAL_WORDS):
            assert not any(w in blob for w in words), ('① 에 해당 지점이 있음', r.get('id'), r)

    exist_codes = {x['code']: x['id'] for x in before}
    exist_names = {norm(x['english']): x['id'] for x in before}
    exist_kr = {norm(x['name']): x['id'] for x in before}
    exist_ids = {x['id'] for x in before}

    ordered = []
    for city in CITY_ORDER:
        ordered += sorted([c for c, h in new.items() if clean(h['city']) == city],
                          key=lambda c: clean(new[c]['name']))
    assert len(ordered) == 12, ordered
    assert ordered == ['mxpct', 'milph', 'athgh', 'thess', 'zoeha', 'pasdh',
                       'drcfu', 'jtrub', 'aszak', 'lisaz', 'lishr', 'lissl'], ordered

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
        assert info['country'] in ('Italy', 'Greece', 'Portugal'), info['country']
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
    assert city_stat == {'Milan': 2, 'Athens': 1, 'Thessaloniki': 1, 'Halkidiki': 1, 'Paros': 1,
                         'Corfu': 1, 'Santorini': 1, 'Zakynthos': 1, 'Lisbon': 3}, city_stat

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'

    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    cells = sum(len(h['points']['$v']) for h in tab['hotels'])
    priced = sum(1 for h in tab['hotels'] for v in h['points']['$v'] if v is not None)
    europe = [h['id'] for h in tab['hotels'] if h['region'] == '유럽']
    greece = [h['city'] for h in added if h['city'] in ('Athens', 'Thessaloniki', 'Halkidiki',
                                                        'Paros', 'Corfu', 'Santorini', 'Zakynthos')]
    print('added', [(a['id'], a['code'], a['name'], a['city'], a['category']) for a in added])
    print('cities', city_stat, '그리스', len(greece))
    print('hotels', len(tab['hotels']), 'cells', cells, 'priced', priced)
    print('유럽', len(europe))
    print('신규 12곳 셀 4,380 가운데',
          sum(1 for h in added for v in h['points']['$v'] if v is not None), '칸')


if __name__ == '__main__':
    main()
