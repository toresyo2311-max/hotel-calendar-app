#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 스페인 마드리드 2차 배치1 5 + 인도 1차 배치1·2 10 + 모로코·카타르 5차 5 = 20곳 병합
(2026-11-27) 465 → 485곳

입력
  · 4번(@jin_4) 스페인 마드리드 5곳
      memory/clones/06130525-jin489/pickle/2026-11-27-0422/received/0-hyatt-es2-batch1.json
      (hyatt.com /explore-hotels/service/avail/days · STANDARD_ROOM · 성인1·1박 · 20일 창 타일링)
  · 6번(@jin_6) 인도 배치1 5 + 배치2 5 = 10곳
      memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0420/received/0-hyatt-in-batch1-5.json
      memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0436/received/0-hyatt-in-batch2-5.json
      (hyatt.com 포인트 캘린더 · Standard Room · 1박 · 성인2인·1실 · 56일 이하 7구간)
  · 7번(@no_7) 모로코 1 + 카타르 4 = 5곳
      memory/clones/a03363f4-no71/pickle/2026-11-27-0405/received/0-hyatt_me_batch5_5.json
      (hyatt.com /explore-hotels/service/avail/days · STANDARD_ROOM · 성인2·1박 · 60일 창 6+5일 1)

■ 규칙
- 마스터(1-hyatt-global-master.json)의 20개 spiritCode 와 이름·카테고리·브랜드·WoH 참여를 배치본과 대조.
  카드 region 은 마스터 area 를 이 탭 표기로 나눠 적는다 — 스페인 → 유럽 / 인도 → 남아시아(마스터 area
  그대로, 이 탭 첫 남아시아 지점) / 모로코 → 아프리카 / 카타르 → 중동.
- 기존 465곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 — ① 탭 161곳은 부산·상하이·
  후쿠오카·오사카·도쿄·방콕·다낭·나트랑·서울·싱가포르·시드니·뉴욕 12개 도시뿐이라 마드리드·델리·
  도하·타가주트 지점이 없어 겹침 0쌍(alsoIn·hlx_in 없음).
- bp023(바이아 프린시페 이스케이프 코랄 플라야)과 vgazv(하얏트 플레이스 비자야와다)는 WoH 미참여로
  0/365 · category null 이다. 카드에는 그대로 싣고, 미참여 사유는 note 에 적는다. 두 곳의 빈칸은
  「개관 전」이 아니라 미참여·공홈 판매 미개시이므로 note 에 그 문구를 쓰지 않는다(달력이 그 문구를
  호텔 전체 미오픈 신호로 읽는다).
- city·name 은 국문, brand 는 공홈 브랜드 라벨, category 는 정수(없으면 null).
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 세 배치 모두 현금가 미수집.
- 링크는 기존 카드와 같이 공홈 예약 화면 https://www.hyatt.com/shop/rooms/{code}.
"""

import collections
import copy
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
D4 = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-27-0422/received')
D6A = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0420/received')
D6B = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0436/received')
D7 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0405/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START, END = '2026-12-01', '2027-11-30'
from datetime import date, timedelta
_d0, _d1 = date(2026, 12, 1), date(2027, 11, 30)
DATES = [(_d0 + timedelta(days=i)).isoformat() for i in range((_d1 - _d0).days + 1)]
assert len(DATES) == 365

FIRST_ID = 466

# (code, 국문명, 도시, 브랜드, 카테고리, region, 묶음)
PLAN = [
    # ── 스페인 마드리드 2차 배치1 5곳 — 4번(@jin_4) · 2026-11-27 04:21 KST
    ('madct', '하얏트 센트릭 그란 비아 마드리드', '마드리드', 'Hyatt Centric', 6, '유럽', 'ES'),
    ('madrm', '하얏트 리젠시 헤스페리아 마드리드', '마드리드', 'Hyatt Regency', 5, '유럽', 'ES'),
    ('madra', '하얏트 리젠시 마드리드 레지던스', '마드리드', 'Hyatt Regency', 6, '유럽', 'ES'),
    ('madrp', '톰슨 마드리드', '마드리드', 'Thompson Hotels', 6, '유럽', 'ES'),
    ('bp023', '바이아 프린시페 이스케이프 코랄 플라야', '마갈루프', 'Bahia Principe Hotels & Resorts', None, '유럽', 'ES'),
    # ── 인도 1차 배치1 5곳 — 6번(@jin_6) · 2026-11-27 04:20 KST
    ('vgazv', '하얏트 플레이스 비자야와다', '비자야와다', 'Hyatt Place', None, '남아시아', 'IN'),
    ('gayzb', '하얏트 플레이스 보드가야', '보드가야', 'Hyatt Place', 1, '남아시아', 'IN'),
    ('ixcct', '하얏트 센트릭 섹터 17 찬디가르', '찬디가르', 'Hyatt Centric', 1, '남아시아', 'IN'),
    ('ixchr', '하얏트 리젠시 찬디가르', '찬디가르', 'Hyatt Regency', 2, '남아시아', 'IN'),
    ('rprhy', '하얏트 라이푸르', '라이푸르', 'Hyatt Hotels', 1, '남아시아', 'IN'),
    # ── 인도 1차 배치2 5곳 — 6번(@jin_6) · 2026-11-27 04:31 KST
    ('grggh', '그랜드 하얏트 구르가온', '구르가온', 'Grand Hyatt', 2, '남아시아', 'IN'),
    ('delrg', '하얏트 리젠시 구르가온', '구르가온', 'Hyatt Regency', 1, '남아시아', 'IN'),
    ('delzo', '하얏트 플레이스 구루그람 우디오그 비하르', '구루그람', 'Hyatt Place', 1, '남아시아', 'IN'),
    ('delaz', '안다즈 델리', '뉴델리', 'Andaz', 2, '남아시아', 'IN'),
    ('delct', '하얏트 센트릭 자낙푸리 뉴델리', '뉴델리', 'Hyatt Centric', 1, '남아시아', 'IN'),
    # ── 모로코 1 + 카타르 4 — 7번(@no_7) · 2026-11-26 21:18~21:30 KST
    ('agart', '하얏트 리젠시 타가주트', '타가주트', 'Hyatt Regency', 3, '아프리카', 'MA'),
    ('dohaz', '안다즈 도하', '도하', 'Andaz', 3, '중동', 'QA'),
    ('dohgh', '그랜드 하얏트 도하 호텔 & 빌라스', '도하', 'Grand Hyatt', 4, '중동', 'QA'),
    ('dohrd', '하얏트 리젠시 오릭스 도하', '도하', 'Hyatt Regency', 1, '중동', 'QA'),
    ('dohph', '파크 하얏트 도하', '도하', 'Park Hyatt', 4, '중동', 'QA'),
]

COUNTRY_KO = {'ES': '스페인', 'IN': '인도', 'MA': '모로코', 'QA': '카타르'}
PROVIDER = {'ES': '4번(@jin_4)', 'IN': '6번(@jin_6)', 'MA': '7번(@no_7)', 'QA': '7번(@no_7)'}

CASH = {
    'ES': ('공홈 현금가·호럭 요금은 365일 전부 —입니다 — 지시대로 현금(rooms/roomrates) 호출을 하지 않아'
           ' 미수집으로 두었습니다.'),
    'IN': ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아(1박 단위 '
           'shop/rooms 화면에서만 표시) 미수집으로 두었습니다.'),
    'MA': ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아(1박 단위 '
           'shop/rooms 화면에서만 표시, 세금·봉사료 별도) 미수집으로 두었습니다.'),
}
CASH['QA'] = CASH['MA']

# 호텔별 보강 — 배치본 note 에 없는, 이번 병합에서 새로 확인한 사실만 적는다
EXTRA = {
    'madct': ('좁은 5일 창 재조회(2027-01-10~01-14)에서 5일 모두 20,000P SUPER_OFF_PEAK로 저장값이 '
              '일치했다.'),
    'madrm': ('공홈 포인트 캘린더 2027-03도 \'No Rooms Available\'로 같았다. 수집된 표본(13일)만으로 '
              '휴관인지 1박 재고 미개방인지는 구분하지 않았다.'),
    'madra': ('좁은 5일 창 재조회(2027-08-01~08-05)에서 08-01~04 20,000 · 08-05 25,000으로 저장값이 '
              '일치했다.'),
    'madrp': ('좁은 5일 창 재조회(2026-12-01~12-05)에서 12-01~03 25,000 · 12-04 30,000 · 12-05는 '
              '스탠다드룸 없이 프리미엄 스위트 50,000만 표출돼 저장값과 일치했다.'),
    'delzo': ('도시 표기는 원자료의 Gurugram(구루그람)을 그대로 살렸다 — 구르가온(Gurgaon)과 같은 델리 '
              '수도권 도시의 공식 개칭명이고, 호텔명도 공홈 표기 「하얏트 플레이스 구루그람 우디오그 '
              '비하르」를 따랐다.'),
    'agart': ('같은 타가주트 해안의 기존 카드 「하얏트 플레이스 타가주트 베이」(<code>agazt</code> · '
              'hy462 · 도시 아가디르)와는 다른 호텔이다.'),
}


def clean(s):
    s = unicodedata.normalize('NFC', str(s or ''))
    s = ''.join(' ' if (ch.isspace() or unicodedata.category(ch) in ('Cf', 'Cc')) else ch for ch in s)
    return ' '.join(s.split())


def norm(s):
    s = unicodedata.normalize('NFKD', clean(s)).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def norm_ko(s):
    s = unicodedata.normalize('NFC', clean(s)).lower()
    return re.sub(r'[\s\W_]+', '', s)


def load():
    hotels, src = {}, {}
    d = json.load(open(os.path.join(D4, '0-hyatt-es2-batch1.json'), encoding='utf-8'))
    assert d['meta']['window'] == '2026-12-01~2027-11-30'
    for code, h in d['hotels'].items():
        hotels[code] = h
        src[code] = ('ES', '0-hyatt-es2-batch1.json')
    for path, name in ((D6A, '0-hyatt-in-batch1-5.json'), (D6B, '0-hyatt-in-batch2-5.json')):
        d = json.load(open(os.path.join(path, name), encoding='utf-8'))
        assert d['window'] == {'start': '2026-12-01', 'end': '2027-11-30', 'days': 365}
        for h in d['hotels']:
            assert h['code'] not in hotels
            hotels[h['code']] = h
            src[h['code']] = ('IN', name)
    d = json.load(open(os.path.join(D7, '0-hyatt_me_batch5_5.json'), encoding='utf-8'))
    assert d['meta']['window'] == '2026-12-01~2027-11-30'
    for code, h in d['hotels'].items():
        hotels[code] = h
        src[code] = ('MA' if h['country'] == 'Morocco' else 'QA', '0-hyatt_me_batch5_5.json')
    assert len(hotels) == 20, len(hotels)
    return hotels, src


def pts_of(h):
    raw = h.get('points') or {}
    if isinstance(raw, list):
        raw = dict(raw)
    return [raw.get(d) for d in DATES]


def dist_text(pts):
    cnt = collections.Counter(v for v in pts if v is not None)
    return ' · '.join('%sP %d일' % ('{:,}'.format(v), n) for v, n in sorted(cnt.items(), key=lambda kv: (-kv[1], -kv[0])))


def head(grp, code, city, cat, info, priced):
    cat_txt = 'null' if cat is None else str(cat)
    if grp == 'ES':
        s = ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM · '
             '성인1인·1박)을 20일 창 19회로 타일링해 2026-12-01~2027-11-30 365칸을 실측했다'
             '(2026-11-27 04:21 KST · %s(%s) · %s). 공홈 표시 어워드 카테고리는 %s이고 값이 있는 날은 '
             '%d일이다.' % (PROVIDER[grp], city, COUNTRY_KO[grp], cat_txt, priced))
        if cat is None:
            s = ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM · '
                 '성인1인·1박)을 20일 창 19회로 타일링해 2026-12-01~2027-11-30 365칸을 실측했다'
                 '(2026-11-27 04:21 KST · 4번(@jin_4) · %s). 공홈에 어워드 카테고리가 없어 카테고리는 null, '
                 '값이 있는 날은 %d일이다.' % (COUNTRY_KO[grp], priced))
    elif grp == 'IN':
        s = ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM · '
             '1박 · 성인2인·1실)을 56일 이하 7구간으로 나눠 2026-12-01~2027-11-30 365칸을 실측했다'
             '(2026-11-27 04:00~04:31 KST · %s · %s · %s). 한 달치 캘린더 셀 표시와 전수 대조해 일치를 '
             '확인했다. ' % (PROVIDER[grp], city, COUNTRY_KO[grp]))
        s += ('공홈에 어워드 카테고리가 없어(VoH 미참여) 카테고리는 null, 값이 있는 날은 %d일이다.' % priced
              if cat is None else
              '공홈 표시 어워드 카테고리는 %s이고 값이 있는 날은 %d일이다.' % (cat_txt, priced))
    else:
        s = ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM · '
             '1박 · 성인2인·1실)을 60일 창 6회+5일 창 1회로 2026-12-01~2027-11-30 365칸을 실측했다'
             '(2026-11-26 21:18~21:30 KST · %s(%s) · 7번(@no_7)). 이 배치의 null 31일 전 구간을 ±2일 버퍼 '
             '창 6개로 다시 조회해 표출일 26일의 값·레벨 불일치 0건을 확인했다. 공홈 표시 어워드 카테고리는 '
             '%s이고 값이 있는 날은 %d일이다.' % (COUNTRY_KO[grp], city, cat_txt, priced))
    return s


def build_note(grp, code, city, cat, info, priced, pts):
    src_note = clean(info.get('note') or '')
    bits = [head(grp, code, city, cat, info, priced)]
    if cat is None and grp != 'ES':
        pass
    if grp == 'ES' and cat is not None:
        bits.append('분포: %s.' % dist_text(pts))
    bits.append(src_note)
    bits.append(EXTRA.get(code, ''))
    bits.append(CASH[grp])
    bits.append('%s이 실측해 보낸 본입니다.' % PROVIDER[grp])
    note = ' '.join(x for x in bits if x)
    note = ' '.join(note.split())
    assert '개관 전' not in note, code
    return note


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 465, len(before)
    assert before[-1]['id'] == 'hy465', before[-1]['id']

    hotels, src = load()
    assert set(hotels) == {p[0] for p in PLAN}, sorted(set(hotels) ^ {p[0] for p in PLAN})

    # ── 공홈 마스터 대조 ─────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    AREA_OK = {'유럽': '유럽', '남아시아': '남아시아', '아프리카': '중동·아프리카',
               '중동': '중동·아프리카'}
    for code, kr, city, brand, cat, region, grp in PLAN:
        m, h = byc[code], hotels[code]
        assert norm(m['name']) == norm(h['name']), (code, m['name'], h['name'])
        assert m['area'] == AREA_OK[region], (code, m['area'], region)
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert str(cat) == str(h['category']), (code, cat, h['category'])
        assert clean(h['brand']) == clean(brand) == clean(m['brand']), (code, h['brand'], brand, m['brand'])
        assert m['woh_participating'] is (cat is not None) or code in ('bp023', 'vgazv'), code
        if code in ('bp023', 'vgazv'):
            assert m['woh_participating'] is False and cat is None and m['category'] is None
        print('%-6s %-6s Cat %-4s WoH %-5s %s' % (code, region, m['category'], m['woh_participating'], m['name']))

    # ── 기존 465곳 중복 확인 ─────────────────────────────────────────
    exist_codes = {x['code']: x['id'] for x in before}
    exist_names, exist_kr = {}, {}
    for x in before:
        exist_names.setdefault(norm(x['english']), []).append(x['id'])
        exist_kr.setdefault(norm_ko(x['name']), []).append(x['id'])
    exist_tokens = {x['id']: set(norm(x['english']).split()) for x in before}
    seen_en, seen_kr = {}, {}
    for code, kr, city, brand, cat, region, grp in PLAN:
        h = hotels[code]
        assert code not in exist_codes, ('code dup', code, exist_codes.get(code))
        assert not exist_names.get(norm(h['name'])), ('english dup', code, h['name'])
        assert not exist_kr.get(norm_ko(kr)), ('korean dup', code, kr, exist_kr.get(norm_ko(kr)))
        assert norm(h['name']) not in seen_en, ('batch english dup', code)
        assert norm_ko(kr) not in seen_kr, ('batch korean dup', code)
        seen_en[norm(h['name'])] = code
        seen_kr[norm_ko(kr)] = code
        toks = set(norm(h['name']).split())
        for hid, et in exist_tokens.items():
            assert not toks <= et, ('same hotel?', code, hid, et)
    print('기존 465곳 대조 — code·영문명·국문명 중복 0건')

    # ── ① 호텔럭스 161곳 전수 대조 ──────────────────────────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
    assert len(rows) == 161, len(rows)
    by_eng, by_kr = {}, {}
    for r in rows:
        if r.get('english'):
            by_eng.setdefault(norm(r['english']), []).append(r['id'])
        if r.get('name'):
            by_kr.setdefault(norm_ko(r['name']), []).append(r['id'])
    overlaps = []
    for code, kr, city, brand, cat, region, grp in PLAN:
        h = hotels[code]
        if norm(h['name']) in by_eng:
            overlaps.append(('english', code, by_eng[norm(h['name'])]))
        if norm_ko(kr) in by_kr:
            overlaps.append(('korean', code, by_kr[norm_ko(kr)]))
        toks = set(norm(h['name']).split())
        for r in rows:
            et = set(norm(r.get('english') or '').split())
            if et and toks <= et:
                overlaps.append(('same hotel?', code, r['id'], r.get('english')))
    assert not overlaps, overlaps
    print('① 호텔럭스 161곳 대조 — 겹침 0곳 · ① 탭 도시 %d개(마드리드·델리·도하·타가주트 없음)'
          % len({clean(r.get('city')) for r in rows}))

    added = []
    for i, (code, kr, city, brand, cat, region, grp) in enumerate(PLAN):
        hid = 'hy%d' % (FIRST_ID + i)
        info = hotels[code]
        pts = pts_of(info)
        assert len(pts) == 365
        assert all(v is None or (isinstance(v, int) and v > 0) for v in pts)
        priced = sum(1 for v in pts if v is not None)
        if 'days_priced' in info:
            assert priced == info['days_priced'], (code, priced, info['days_priced'])
        note = build_note(grp, code, city, cat, info, priced, pts)
        added.append({
            'id': hid, 'group': 'hyatt', 'code': code, 'region': region, 'city': city,
            'name': kr, 'english': clean(info['name']), 'brand': brand, 'category': cat,
            'vip_id': None, 'alsoIn': None, 'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None, 'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % code, 'hlx': None},
            'promotion': None, 'note': note,
        })
        print('%s %-6s %-5s %-6s %-34s Cat %-4s %3d일' %
              (hid, code, region, city, kr, '-' if cat is None else cat, priced))

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-27'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n')

    hs = tab['hotels']
    cells = sum(len(h['points']['$v']) for h in hs)
    priced = sum(1 for h in hs for v in h['points']['$v'] if v is not None)
    reg = collections.Counter(h['region'] for h in hs)
    print('hotels', len(hs), 'cells', cells, 'priced', priced, dict(reg))
    assert len(hs) == 485 and cells == 485 * 365
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['유럽'] == 113 and reg['남아시아'] == 10 and reg['중동'] == 26 and reg['아프리카'] == 5
    assert reg['미국'] == 209 and reg['동남아'] == 61 and reg['일본'] == 23
    assert reg['중국·중화권'] == 15 and reg['오세아니아'] == 14 and reg['한국'] == 9
    assert priced == 147415 + 5179, priced
    print('EXPECT_HYATT = {\'hotels\': %d, \'cells\': %d, \'priced\': %d}' % (len(hs), cells, priced))


if __name__ == '__main__':
    main()
