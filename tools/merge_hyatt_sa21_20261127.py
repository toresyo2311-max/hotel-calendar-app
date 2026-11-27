#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 남아시아 마지막 21곳(인도 15 · 몰디브 3 · 네팔 3) 병합
(2026-11-27) 592 → 613곳 · 남아시아 40 → 61곳

입력 — 모두 6번(@jin_6) · 2026-11-27 07:32~08:36 KST
  · memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0554/received/0-hyatt-sa-batch1-5.json
      (bdqzv · cokgh · cokrm · trvrt · cokrt — 인도 케랄라·구자라트 5곳)
  · .../0-hyatt-sa-batch2-5.json   (mumgh · mumct · pnqzp · pnqhy · punhr — 뭄바이·푸네 5곳)
  · .../0-hyatt-sa-batch3-5.json   (luhrl · jaizm · lkorl · kolct · kolka — 북·동인도 5곳)
  · .../0-hyatt-sa-batch4-6.json   (mldph · mldal · mldsm 몰디브 3 + bwazb · ktmzk · kathm 네팔 3)
  (hyatt.com 포인트 캘린더 · Standard Room · 1박 · 성인2인·1실 · 56일 이하 7구간 · 365일)

■ 규칙
- 마스터(1-hyatt-global-master.json)의 21개 spiritCode 와 이름·카테고리·브랜드·WoH 참여를 배치본과 대조.
  카드 region 은 마스터 area 그대로 — 21곳 전부 남아시아.
- 기존 592곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 — 겹침 0쌍.
- city·name 은 국문, brand 는 공홈(마스터) 브랜드 라벨, category 는 정수.
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 21곳 모두 현금가 미수집.
- note 에 마크다운 ** 별표·긴 URL·달력이 호텔 전체 미오픈 신호로 읽는 「개관 전」 문구를 쓰지 않는다.
- 링크는 기존 카드와 같이 공홈 예약 화면 https://www.hyatt.com/shop/rooms/{code}.
"""

import collections
import copy
import json
import os
import re
import unicodedata
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
D6 = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0554/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START, END = '2026-12-01', '2027-11-30'
_d0, _d1 = date(2026, 12, 1), date(2027, 11, 30)
DATES = [(_d0 + timedelta(days=i)).isoformat() for i in range((_d1 - _d0).days + 1)]
assert len(DATES) == 365
FIRST_ID = 593

FILES = {
    'IN1': '0-hyatt-sa-batch1-5.json',
    'IN2': '0-hyatt-sa-batch2-5.json',
    'IN3': '0-hyatt-sa-batch3-5.json',
    'SA4': '0-hyatt-sa-batch4-6.json',
}

# (code, 국문명, 도시, 브랜드, 카테고리, region, 묶음)
PLAN = [
    # ── 인도 1차(케랄라·구자라트) 5곳 — 6번(@jin_6) · 2026-11-27 07:32~07:44 KST
    ('bdqzv', '하얏트 플레이스 바도다라', '바도다라', 'Hyatt Place', 1, '남아시아', 'IN1'),
    ('cokgh', '그랜드 하얏트 코치 볼가티', '코치', 'Grand Hyatt', 2, '남아시아', 'IN1'),
    ('cokrm', '하얏트 리젠시 코치 말라야투르', '코치', 'Hyatt Regency', 1, '남아시아', 'IN1'),
    ('trvrt', '하얏트 리젠시 티루바난타푸람', '티루바난타푸람', 'Hyatt Regency', 1, '남아시아', 'IN1'),
    ('cokrt', '하얏트 리젠시 트리수르', '트리수르', 'Hyatt Regency', 1, '남아시아', 'IN1'),
    # ── 인도 2차(뭄바이·푸네) 5곳 — 2026-11-27 07:45~07:58 KST
    ('mumgh', '그랜드 하얏트 뭄바이 호텔 앤 레지던스', '뭄바이', 'Grand Hyatt', 3, '남아시아', 'IN2'),
    ('mumct', '하얏트 센트릭 주후 뭄바이', '뭄바이', 'Hyatt Centric', 2, '남아시아', 'IN2'),
    ('pnqzp', '하얏트 플레이스 푸네 힌자와디', '푸네', 'Hyatt Place', 1, '남아시아', 'IN2'),
    ('pnqhy', '하얏트 푸네', '푸네', 'Hyatt Hotels', 1, '남아시아', 'IN2'),
    ('punhr', '하얏트 리젠시 푸네 앤 레지던스', '푸네', 'Hyatt Regency', 1, '남아시아', 'IN2'),
    # ── 인도 3차(북·동인도) 5곳 — 2026-11-27 07:59~08:11 KST
    ('luhrl', '하얏트 리젠시 루디아나', '루디아나', 'Hyatt Regency', 1, '남아시아', 'IN3'),
    ('jaizm', '하얏트 플레이스 자이푸르 말비야 나가르', '자이푸르', 'Hyatt Place', 1, '남아시아', 'IN3'),
    ('lkorl', '하얏트 리젠시 러크나우', '러크나우', 'Hyatt Regency', 1, '남아시아', 'IN3'),
    ('kolct', '하얏트 센트릭 발리군지 콜카타', '콜카타', 'Hyatt Centric', 1, '남아시아', 'IN3'),
    ('kolka', '하얏트 리젠시 콜카타', '콜카타', 'Hyatt Regency', 1, '남아시아', 'IN3'),
    # ── 몰디브 3곳 — 2026-11-27 08:14~08:27 KST
    ('mldph', '파크 하얏트 몰디브 하다하', '가푸 알리푸 아톨', 'Park Hyatt', 7, '남아시아', 'SA4'),
    ('mldal', '알릴라 코타이파루 몰디브', '라 아톨', 'Alila', 7, '남아시아', 'SA4'),
    ('mldsm', '더 스탠다드 몰디브', '라 아톨', 'The Standard', 6, '남아시아', 'SA4'),
    # ── 네팔 3곳 — 2026-11-27 08:14~08:27 KST
    ('bwazb', '하얏트 플레이스 부트왈', '부트왈', 'Hyatt Place', 1, '남아시아', 'SA4'),
    ('ktmzk', '하얏트 센트릭 소알티모데 카트만두', '카트만두', 'Hyatt Centric', 1, '남아시아', 'SA4'),
    ('kathm', '하얏트 리젠시 카트만두', '카트만두', 'Hyatt Regency', 1, '남아시아', 'SA4'),
]

COUNTRY_KO = {'IN1': '인도', 'IN2': '인도', 'IN3': '인도', 'SA4': None}  # SA4 는 호텔별
TIME = {
    'IN1': '2026-11-27 07:32~07:44 KST',
    'IN2': '2026-11-27 07:45~07:58 KST',
    'IN3': '2026-11-27 07:59~08:11 KST',
    'SA4': '2026-11-27 08:14~08:27 KST',
}
PROVIDER = '6번(@jin_6)'

CASH = ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아'
        '(1박 단위 shop/rooms 화면에서만 표시) 미수집으로 두었습니다.')

# 호텔별 보강 — 배치본 note 에 이미 있는 사실은 되풀이하지 않고, 그 호텔 note 에 없는
# 같은 수요 달력 공유 사실(이번 병합에서 365일 등급을 직접 대조해 확인)만 적는다.
EXTRA = {
    'pnqzp': ('푸네 3곳(이 호텔 · 하얏트 푸네 · 하얏트 리젠시 푸네 앤 레지던스)이 값이 겹치는 날 '
              '100% 동일한 포인트 달력을 쓴다 — 브랜드가 Place·Hyatt·Regency로 달라도 하나의 푸네 '
              '수요 달력이다.'),
    'pnqhy': ('푸네 3곳이 값이 겹치는 날 100% 동일한 포인트 달력을 쓴다(하얏트 플레이스 푸네 '
              '힌자와디와 326일 · 하얏트 리젠시 푸네 앤 레지던스와 334일).'),
    'kolct': ('같은 콜카타의 하얏트 리젠시 콜카타(<code>kolka</code>)와 값이 겹치는 330일이 전부 '
              '동일한 포인트 달력을 쓴다 — 브랜드(Centric·Regency)와 성급(5성·4.5성)이 달라도 하나의 '
              '콜카타 수요 달력이다.'),
    'mldph': ('몰디브 3곳이 하나의 수요 달력을 공유한다 — 알릴라 코타이파루 몰디브와 값이 겹치는 '
              '312일이 전부 동일(둘 다 Cat7)하고, 더 스탠다드 몰디브(Cat6)는 같은 날짜에 '
              '5,000·10,000·15,000P 낮은 밴드로 같은 등급 전환을 따른다.'),
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
    hotels, country = {}, {}
    for grp, name in FILES.items():
        d = json.load(open(os.path.join(D6, name), encoding='utf-8'))
        assert d['window'] == {'start': START, 'end': END, 'days': 365}
        for h in d['hotels']:
            assert h['code'] not in hotels, h['code']
            hotels[h['code']] = h
            country[h['code']] = h['country']
    assert len(hotels) == 21, len(hotels)
    return hotels, country


def pts_of(h):
    raw = h.get('points') or {}
    if isinstance(raw, list):
        raw = dict(raw)
    return [raw.get(d) for d in DATES]


def dist_text(pts):
    cnt = collections.Counter(v for v in pts if v is not None)
    return ' · '.join('%sP %d일' % ('{:,}'.format(v), n)
                      for v, n in sorted(cnt.items(), key=lambda kv: (-kv[1], -kv[0])))


COUNTRY_NAME = {'India': '인도', 'Maldives': '몰디브', 'Nepal': '네팔'}


def head(grp, city, country, priced):
    return ('하얏트 공홈 포인트 캘린더(explore-hotels/rate-calendar · Standard Room · 1박 · '
            '성인2인·1실)와 그 데이터 원천(avail/days · roomCategory=STANDARD_ROOM · los=1)을 '
            '56일 이하 7구간으로 나눠 2026-12-01~2027-11-30 365칸을 실측했다'
            '(%s · %s · %s · %s).' % (TIME[grp], PROVIDER, city, COUNTRY_NAME[country]))


def body_from_source(info):
    """배치본 note 의 사실을 그대로 살리되 머리·카테고리·분포와 중복되는 문장, 별표, 긴 URL 은 걷어낸다."""
    n = clean(info.get('note') or '').replace('**', '')
    i = n.find('실측했다.')
    if i > 0:
        n = n[i + len('실측했다.'):].strip()
    a = n.find('값은 캘린더 화면이 쓰는')
    if a >= 0:
        b = n.find('포인트 어워드 없음).', a)
        if b > 0:
            n = (n[:a] + n[b + len('포인트 어워드 없음).'):]).strip()
    a = n.find('공홈 표시 어워드 카테고리')
    if a >= 0:
        b = n.find('일치).', a)
        if b > 0:
            n = (n[:a] + n[b + len('일치).'):]).strip()
    n = re.sub(r'유효 \d+일 / null \d+일\([^)]*\)\s*(—\s*)?', '', n)
    n = re.sub(r'분포: [^.]*\.', '', n)
    n = re.sub(r'https?://\S+', '', n)
    return ' '.join(n.split())


def build_note(grp, code, city, country, cat, info, pts, priced):
    bits = [head(grp, city, country, priced),
            '공홈 표시 어워드 카테고리는 %s이고 값이 있는 날은 %d일이다.' % (cat, priced)]
    if priced:
        bits.append('분포: %s.' % dist_text(pts))
    bits.append(body_from_source(info))
    bits.append(EXTRA.get(code, ''))
    bits.append(CASH)
    bits.append('%s이 실측해 보낸 본입니다.' % PROVIDER)
    note = ' '.join(x for x in bits if x)
    note = ' '.join(note.split())
    assert '**' not in note, code
    assert '개관 전' not in note, code
    assert 'http' not in note, code
    assert len(note) < 4000, (code, len(note))
    return note


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 592, len(before)
    assert before[-1]['id'] == 'hy592', before[-1]['id']

    hotels, country = load()
    assert set(hotels) == {p[0] for p in PLAN}, sorted(set(hotels) ^ {p[0] for p in PLAN})

    # ── 공홈 마스터 대조 ─────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    for code, kr, city, brand, cat, region, grp in PLAN:
        m, h = byc[code], hotels[code]
        assert norm(m['name']) == norm(h['name']), (code, m['name'], h['name'])
        assert m['area'] == '남아시아', (code, m['area'])
        assert str(m['category']) == str(h['category']) == str(cat), (code, m['category'], h['category'], cat)
        assert clean(brand) == clean(m['brand']), (code, brand, m['brand'])
        assert clean(h['brand']) == clean(m['brand']), (code, h['brand'], m['brand'])
        assert m['woh_participating'] is True, code
        print('%-6s %-5s Cat %-2s %s (%s · %s)' % (code, COUNTRY_NAME[country[code]], m['category'],
                                                    m['name'], city, grp))

    # ── 기존 592곳 중복 확인 ─────────────────────────────────────────
    exist_codes = {x['code']: x['id'] for x in before}
    exist_names, exist_kr, exist_city = {}, {}, collections.defaultdict(list)
    for x in before:
        exist_names.setdefault(norm(x['english']), []).append(x['id'])
        exist_kr.setdefault(norm_ko(x['name']), []).append(x['id'])
        exist_city[clean(x['city'])].append((x['id'], x['english']))
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
    print('기존 592곳 대조 — code·영문명·국문명 중복 0건')

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
    print('① 호텔럭스 161곳 대조 — 겹침 0곳 (① 탭 도시 %d개)' % len({clean(r.get('city')) for r in rows}))

    added = []
    for i, (code, kr, city, brand, cat, region, grp) in enumerate(PLAN):
        hid = 'hy%d' % (FIRST_ID + i)
        info = hotels[code]
        pts = pts_of(info)
        assert len(pts) == 365
        assert all(v is None or (isinstance(v, int) and v > 0) for v in pts)
        priced = sum(1 for v in pts if v is not None)
        note = build_note(grp, code, city, country[code], cat, info, pts, priced)
        added.append({
            'id': hid, 'group': 'hyatt', 'code': code, 'region': region, 'city': city,
            'name': kr, 'english': clean(byc[code]['name']), 'brand': brand, 'category': cat,
            'vip_id': None, 'alsoIn': None, 'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None, 'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % code, 'hlx': None},
            'promotion': None, 'note': note,
        })
        print('%s %-6s %-10s %-38s Cat %-2s %3d일 note %d자' %
              (hid, code, city, kr, cat, priced, len(note)))

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-27'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n')

    hs = tab['hotels']
    cells = sum(len(h['points']['$v']) for h in hs)
    priced = sum(1 for h in hs for v in h['points']['$v'] if v is not None)
    reg = collections.Counter(h['region'] for h in hs)
    print('hotels', len(hs), 'cells', cells, 'priced', priced, dict(reg))
    assert len(hs) == 613 and cells == 613 * 365 == 223745
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['남아시아'] == 61
    assert reg['미국'] == 209 and reg['유럽'] == 146 and reg['동남아'] == 61 and reg['일본'] == 23
    assert reg['중국·중화권'] == 15 and reg['오세아니아'] == 14 and reg['한국'] == 9
    assert reg['중동'] == 31 and reg['아프리카'] == 5 and reg['캐나다'] == 39
    assert priced == 178352 + 7285, priced
    print("EXPECT_HYATT = {'hotels': %d, 'cells': %d, 'priced': %d}" % (len(hs), cells, priced))


if __name__ == '__main__':
    main()
