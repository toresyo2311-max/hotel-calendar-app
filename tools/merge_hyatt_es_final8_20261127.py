#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 스페인 3차 마지막 배치3 4 + 배치4 4 = 8곳 병합 (2026-11-27) 584 → 592곳

입력 (4번 @jin_4 · 2026-11-27 06:20~06:23 KST)
  · 배치3 4곳: bp022 · bp019 · asora · alten
      memory/clones/06130525-jin489/pickle/2026-11-27-0600/received/0-hyatt-es3-batch3.json
  · 배치4 4곳: svqth · alatg · drjtf · drepd
      memory/clones/06130525-jin489/pickle/2026-11-27-0600/received/0-hyatt-es3-batch4.json

■ 규칙
- 마스터(1-hyatt-global-master.json)의 8개 spiritCode 와 이름·카테고리·브랜드·WoH 참여를 배치본과 대조.
  카드 region 은 마스터 area 그대로 — 스페인 → 유럽.
- 기존 584곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·전수 대조 — 겹침 0쌍 확인.
- asora(AluaSoul Orotava Valley)는 성인2·2박(los=2) 조회가 2026-12-02~12-21 20일만 열리고 12-22 이후는
  soldOutHotel 이지만, 최소 7박(los=7)으로 다시 재면 307일이 표출된다. 두 조회가 겹치는 20일의 값이
  완전히 같아(12,000P SUPER_OFF_PEAK) 카드 points 는 12-21까지 2박 값, 12-22 이후 7박(los=7) 값으로
  채우고 note 에 「12-22 이후 최소 7박 기준(los=7)」을 명시한다. 보간은 하지 않는다(표시가 없는 날은 null).
- svqth(Thompson Seville)는 표준룸 어워드가 2026년 12월 15일에만 열려 있고 이후는 스위트만 표출된다.
  alatg 는 12-03 이후 최소 7박(los=7), drjtf 는 목~토 3박·연말 7박 최소숙박 기준 보완 실측이다.
  alten 은 0/365(los=2·7 및 공홈 달력 UI 미표출 확정).
- city·name 은 국문, brand 는 공홈(마스터) 브랜드 라벨, category 는 마스터 값(A0~A2 또는 정수).
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 8곳 모두 현금가를 호출하지 않았다.
- note 에는 마크다운 ** 별표와 긴 URL 을 쓰지 않고, 달력이 호텔 전체 미오픈으로 읽는 「개관 전」 문구도 쓰지 않는다.
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
D4 = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-27-0600/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START, END = '2026-12-01', '2027-11-30'
_d0, _d1 = date(2026, 12, 1), date(2027, 11, 30)
DATES = [(_d0 + timedelta(days=i)).isoformat() for i in range((_d1 - _d0).days + 1)]
assert len(DATES) == 365
FIRST_ID = 585

# (code, 국문명, 도시, 브랜드, 카테고리, 파일)
PLAN = [
    # ── 배치3 (테네리페 올인클루시브 — Bahia Principe / Alua) · 4번(@jin_4) 2026-11-27 06:30 KST
    ('bp022', '바이아 프린시페 익스플로어 판타지아', '테네리페', 'Bahia Principe Hotels & Resorts', 'A2', 'b3'),
    ('bp019', '바이아 프린시페 익스플로어 산 펠리페', '테네리페', 'Bahia Principe Hotels & Resorts', 'A0', 'b3'),
    ('asora', '알루아솔 오로타바 밸리', '테네리페', 'Alua Hotels & Resorts', 'A0', 'b3'),
    ('alten', '알루아 테네리페', '테네리페', 'Alua Hotels & Resorts', 'A0', 'b3'),
    # ── 배치4 (세비야 · 테네리페 · 란사로테) · 4번(@jin_4) 2026-11-27 06:30 KST
    ('svqth', '톰슨 세비야', '세비야', 'Thompson Hotels', '6', 'b4'),
    ('alatg', '알루아 아틀란티코 골프 리조트', '테네리페', 'Alua Hotels & Resorts', 'A0', 'b4'),
    ('drjtf', '하얏트 지바 하르딘 트로피칼 테네리페', '테네리페', 'Hyatt Ziva', 'A2', 'b4'),
    ('drepd', '그랜드 하얏트 란사로테 플라야 도라다 리조트', '란사로테', 'Grand Hyatt', 'A2', 'b4'),
]

CASH = ('현금 요금은 365일 전부 —입니다 — 지시대로 현금(rooms/roomrates) 호출을 하지 않아 '
        '미수집으로 두었습니다.')
PROVIDER = '4번(@jin_4)이 실측해 보낸 본입니다.'

# 호텔별 측정 기준 (배치본 points_basis 기준)
BASIS = {
    'bp022': '성인2·2박(los=2) 고정 · 20일 이하 창 19개',
    'bp019': '성인2·2박(los=2) 고정 · 20일 이하 창 19개',
    'asora': '성인2·2박(los=2) 20일 + 12-22 이후 최소 7박(los=7) 보완 · 20일 이하 창 19개씩',
    'alten': '성인2·2박(los=2) 고정 · 20일 이하 창 19개 + 성인1·1박·los=7 교차',
    'svqth': '성인1·1박(los=1) · 20일 창 19개 + 좁은 창 재확인',
    'alatg': '성인2·2박(los=2) 2일 + 12-03 이후 최소 7박(los=7) · 20일 이하 창',
    'drjtf': '성인2·2박(los=2) + 목~토 체크인 3박(los=3) + 연말 7박(los=7) 보완 · 20일 이하 창',
    'drepd': '성인2·2박(los=2) 고정 · 20일 이하 창 19개',
}
TIME = '2026-11-27 06:30 KST'

# 호텔별 보강 — 배치본에 있는 사실만, 달력 표시에 영향 없는 문장으로 적는다
EXTRA = {
    'bp022': ('값이 없는 11일은 2026-12-21~12-26(6일)과 2026-12-31~2027-01-04(5일) 두 블록이고 모두 '
              '응답에 날짜 키가 없는 날(no_key_in_response)이라 soldOutHotel 은 0일입니다. A2 그리드대로 '
              '20,000 SUPER_OFF_PEAK 73일 · 25,000 OFF_PEAK 110일 · 30,000 STANDARD 171일 세 단계로 '
              '표출됐습니다.'),
    'bp019': ('값이 없는 212일은 2026-12-05~12-07 · 2026-12-19~2027-01-09 · 2027-01-15~01-20 · '
              '01-27~01-30 · 02-08~02-17 · 03-03~03-06 · 03-16~03-24 · 2027-06-30~11-30(154일) 여덟 '
              '블록이고, 165일이 soldOutHotel · 47일이 응답에 날짜 키 없음입니다. 2027-06-30 이후는 '
              'los=7·성인1·1박 교차 조회에서도 열리지 않았고 공홈 검색(2027-07-10~07-17 · 2인 1실)이 '
              '「Hotel Not Available」이어서 어워드 재고 미표출로 보이며, 휴장 표시는 없습니다.'),
    'asora': ('2026-12-02~12-21 20일은 성인2·2박(los=2) 조회 값이고, 12-22 이후는 2박 조회가 '
              'soldOutHotel 로 막혀 최소 7박(los=7) 기준으로 다시 잰 값입니다 — 두 조회가 겹치는 20일의 '
              '값·레벨은 완전히 같았습니다(12,000P SUPER_OFF_PEAK). 7박 기준으로도 2027-04-01~04-22 는 '
              '표준룸 없이 CLUB 등 상위 객실만, 2027-10-26~11-30 은 표시가 없습니다. 2박 예약 가능 '
              '여부는 확인하지 못했고, 12-22 이후 값은 7박 기준이라는 점을 함께 봐 주세요.'),
    'alten': ('성인2·2박 20일 창 19개가 전부 soldOutHotel 이고, 성인1·1박(2027-07-01~07-20) · los=7 네 창 '
              '교차 조회도 같았습니다. 공홈 포인트 캘린더를 2박·2인으로 열면 객실타입 버튼이 '
              '「No Rooms Available」로 비활성이고 2026-11~2027-12 월 버튼이 전면 비활성이라 달력 화면으로도 '
              '확정했으며, 같은 시점 같은 절차로 조회한 다른 3곳(bp022·bp019·asora)은 정상 응답해 조회 절차 '
              '문제가 아닙니다.'),
    'svqth': ('표준룸 어워드는 2026년 12월의 15일에만(12-03~12-19 격일 패턴과 12-23) 20,000P '
              'SUPER_OFF_PEAK 로 열려 있고, 12-24 이후 342일은 표준룸 표시가 없습니다. 같은 응답에 '
              '스위트(STANDARD_SUITE)는 연중 대부분 표출돼 35,000P(12월 초) · 40,000P(2027-02-03~04) · '
              '45,000~50,000P(2027-06 · 11월 말)이고, 표준룸이 없을 때 실질 최저 어워드는 스위트 '
              '45,000~50,000P 입니다. 성인2·2박(2027-05-10~05-20)과 7박(2027-06-01~06-15) 재조회에서도 '
              '표준룸은 열리지 않아 최소숙박 조건 때문이 아닙니다.'),
    'alatg': ('성인2·2박 조회는 2026-12-03~2027-11-30 전 구간 soldOutHotel 이지만 최소 7박(los=7)으로 '
              '조회하면 12-03~2027-10-25 가 정상 표출됩니다 — 2026-12-01~02 이틀만 2박으로 잡히고, '
              '12-03 이후는 최소 7박 기준(los=7)입니다. 2026-12-24~12-30 은 14박(los=14)으로도 '
              '미표출(연말 매진)이고, 2027-10-26~11-30 은 2박·7박·14박 모두 표시가 없습니다'
              '(시즌 휴장 또는 어워드 미개방).'),
    'drjtf': ('목~토 체크인은 3박(los=3), 2026-12-26~2027-01-04 연말은 7박(los=7) 최소숙박 기준으로 '
              '보완 실측했습니다 — 성인2·2박 조회는 2026-12-01 하루만 잡히고 3박 조회가 주말 체크인을, '
              '7박 조회가 연말을 채웁니다. 2026-12-02~12-06 은 어떤 기준으로도 미표출이고, '
              '2027-10-30~11-30 은 3박·7박 모두 표시가 없습니다(시즌 휴장 또는 어워드 미개방).'),
    'drepd': ('365일 중 364일이 표출되고 2026-12-02 하루만 표준룸 없이 스위트(STANDARD_SUITE)만 있는 '
              '응답입니다. 모든 20일 창이 20개 날짜 키를 돌려줘 응답 절단이 없었고, 최소숙박 조건 없이 '
              '2박 조회만으로 1년이 채워졌습니다.'),
}


def clean(s):
    s = unicodedata.normalize('NFC', str(s or ''))
    s = ''.join(' ' if (ch.isspace() or unicodedata.category(ch) in ('Cf', 'Cc')) else ch for ch in s)
    return ' '.join(s.split())


def norm(s):
    s = unicodedata.normalize('NFKD', clean(s)).lower()
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def norm_ko(s):
    s = unicodedata.normalize('NFC', clean(s)).lower()
    return re.sub(r'[\s\W_]+', '', s)


def load():
    hotels, src = {}, {}
    for name, tag in (('0-hyatt-es3-batch3.json', 'b3'), ('0-hyatt-es3-batch4.json', 'b4')):
        d = json.load(open(os.path.join(D4, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30'
        for code, h in d['hotels'].items():
            hotels[code] = h
            src[code] = (tag, name)
    assert len(hotels) == 8, len(hotels)
    return hotels, src


def pts_of(h):
    """표준룸 365칸. asora 는 2박 값이 없으면 7박(los=7) 값으로 채운다(겹치는 날은 값 일치 확인)."""
    raw = h.get('points') or {}
    if isinstance(raw, list):
        raw = dict(raw)
    vals = [raw.get(d) for d in DATES]
    if h.get('points_los7'):
        p7 = h['points_los7']
        alt = [p7.get(d) for d in DATES]
        for i, d in enumerate(DATES):
            if vals[i] is not None and alt[i] is not None:
                assert vals[i] == alt[i], ('los2/los7 값 불일치', h['spirit_code'], d, vals[i], alt[i])
            if vals[i] is None:
                vals[i] = alt[i]
    return vals


def blocks(dates):
    out = []
    for d in dates:
        if out and (date.fromisoformat(d) - date.fromisoformat(out[-1][1])).days == 1:
            out[-1][1] = d
        else:
            out.append([d, d])
    res = []
    for a, b in out:
        if a == b:
            res.append(a)
        else:
            n = (date.fromisoformat(b) - date.fromisoformat(a)).days + 1
            res.append('%s~%s(%d일)' % (a, b, n))
    return res


def dist_text(pts):
    cnt = collections.Counter(v for v in pts if v is not None)
    return ' · '.join('%sP %d일' % ('{:,}'.format(v), n)
                      for v, n in sorted(cnt.items(), key=lambda kv: (-kv[1], -kv[0])))


def cat_sentence(cat, priced):
    cat_txt = 'null' if cat is None else ('%s' % cat)
    if cat is None:
        return ('공홈에 어워드 카테고리 표시가 없어 카테고리는 null(월드 오브 하얏트 미참여)이고 값이 있는 '
                '날은 %d일이다.' % priced)
    if str(cat).startswith('A'):
        disp = {'A0': 'A', 'A1': 'B', 'A2': 'C'}.get(str(cat), str(cat))
        return ('공홈 표시 어워드 카테고리는 %s · 마스터 표기 %s이고 값이 있는 날은 %d일이다.'
                % (disp, cat_txt, priced))
    return '공홈 표시 어워드 카테고리는 %s이고 값이 있는 날은 %d일이다.' % (cat_txt, priced)


def head(code, city, priced):
    return ('하얏트 공홈 어워드 응답(avail/days · roomCategory=STANDARD_ROOM · %s)으로 '
            '2026-12-01~2027-11-30 365칸을 실측했다(%s · 4번(@jin_4) · %s · 스페인).'
            % (BASIS[code], TIME, city))


def build_note(code, city, cat, pts, priced):
    bits = [head(code, city, priced), cat_sentence(cat, priced)]
    if priced:
        bits.append('분포: %s.' % dist_text(pts))
    bits.append(EXTRA.get(code, ''))
    bits.append(CASH)
    bits.append(PROVIDER)
    note = ' '.join(x for x in bits if x)
    note = ' '.join(note.split())
    assert '**' not in note, code
    assert '개관 전' not in note, code
    assert 'http' not in note, code
    assert len(note) < 3000, (code, len(note))
    return note


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 584, len(before)
    assert before[-1]['id'] == 'hy584', before[-1]['id']

    hotels, src = load()
    assert set(hotels) == {p[0] for p in PLAN}, sorted(set(hotels) ^ {p[0] for p in PLAN})

    # ── 공홈 마스터 대조 ─────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    for code, kr, city, brand, cat, tag in PLAN:
        m, h = byc[code], hotels[code]
        assert norm(m['name']) in (norm(h['name']), norm(h['name'].split(',')[0])), \
            (code, m['name'], h['name'])
        assert m['area'] == '유럽', (code, m['area'])
        assert m['country_code'] == 'ES', (code, m['country_code'])
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert str(cat) == str(h['category']), (code, cat, h['category'])
        assert clean(brand) == clean(m['brand']), (code, brand, m['brand'])
        assert m['woh_participating'] is True, (code, m['woh_participating'])
        print('%-6s Cat %-3s %-34s %s' % (code, m['category'], m['name'], city))

    # ── 기존 584곳 중복 확인 ─────────────────────────────────────────
    exist_codes = {x['code']: x['id'] for x in before}
    exist_names, exist_kr = {}, {}
    for x in before:
        exist_names.setdefault(norm(x['english']), []).append(x['id'])
        exist_kr.setdefault(norm_ko(x['name']), []).append(x['id'])
    exist_tokens = {x['id']: set(norm(x['english']).split()) for x in before}
    seen_en, seen_kr = {}, {}
    for code, kr, city, brand, cat, tag in PLAN:
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
    print('기존 584곳 대조 — code·영문명·국문명 중복 0건')

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
    for code, kr, city, brand, cat, tag in PLAN:
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
    print('① 호텔럭스 161곳 대조 — 겹침 0곳')

    added = []
    for i, (code, kr, city, brand, cat, tag) in enumerate(PLAN):
        hid = 'hy%d' % (FIRST_ID + i)
        info = hotels[code]
        pts = pts_of(info)
        assert len(pts) == 365
        assert all(v is None or (isinstance(v, int) and v > 0) for v in pts)
        priced = sum(1 for v in pts if v is not None)
        if code != 'asora':
            assert priced == info['days_priced'], (code, priced, info['days_priced'])
        else:
            assert priced == info['days_priced_los7'] == 307, (priced, info.get('days_priced_los7'))
            assert info['days_priced'] == 20
        if code == 'alten':
            assert priced == 0
        note = build_note(code, city, cat, pts, priced)
        added.append({
            'id': hid, 'group': 'hyatt', 'code': code, 'region': '유럽', 'city': city,
            'name': kr, 'english': clean(byc[code]['name']), 'brand': brand, 'category': cat,
            'vip_id': None, 'alsoIn': None, 'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None, 'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % code, 'hlx': None},
            'promotion': None, 'note': note,
        })
        nulls = [DATES[j] for j, v in enumerate(pts) if v is None]
        print('%s %-6s %-6s %-20s %-26s Cat %-3s %3d일 결번 %3d note %4d자' %
              (hid, code, city, kr, byc[code]['name'], cat, priced, len(nulls), len(note)))
        if len(nulls) <= 30:
            print('      결번:', blocks(nulls))

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-27'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n')

    hs = tab['hotels']
    cells = sum(len(h['points']['$v']) for h in hs)
    priced = sum(1 for h in hs for v in h['points']['$v'] if v is not None)
    reg = collections.Counter(h['region'] for h in hs)
    es = [h for h in hs if byc[h['code']]['country_code'] == 'ES']
    print('hotels', len(hs), 'cells', cells, 'priced', priced, dict(reg))
    assert len(hs) == 592 and cells == 592 * 365 == 216080
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['유럽'] == 146 and reg['미국'] == 209 and reg['동남아'] == 61
    assert reg['남아시아'] == 40 and reg['캐나다'] == 39 and reg['중동'] == 31
    assert reg['일본'] == 23 and reg['중국·중화권'] == 15 and reg['오세아니아'] == 14
    assert reg['한국'] == 9 and reg['아프리카'] == 5
    assert len(es) == 53, len(es)
    assert priced == 176513 + 1839, priced
    new = [h for h in hs if int(h['id'][2:]) >= FIRST_ID]
    newp = sum(1 for h in new for v in h['points']['$v'] if v is not None)
    print('신규 8곳 — %d × 365 = %d칸 가운데 %d칸(%.1f%%)' % (len(new), len(new) * 365, newp,
                                                            100.0 * newp / (len(new) * 365)))
    print("EXPECT_HYATT = {'hotels': %d, 'cells': %d, 'priced': %d}" % (len(hs), cells, priced))


if __name__ == '__main__':
    main()
