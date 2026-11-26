#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 호주 11 + 말레이시아 11 + 태국 9 + UAE 1차 5 = 36곳 병합 (2026-11-26)

입력
  · 4번(@jin_4) 호주 11 · 말레이시아 11 — 4개 배치
      memory/clones/06130525-jin489/pickle/2026-11-26-1741/received/0-hyatt-au-batch{A,B}.json
      memory/clones/06130525-jin489/pickle/2026-11-26-1741/received/0-hyatt-my-batch{A,B}.json
      (hyatt.com /explore-hotels/service/avail/days · STANDARD_ROOM · 성인1·1박)
  · 7번(@no_7) 태국 잔여 9곳 — 2개 배치
      memory/clones/a03363f4-no71/pickle/2026-11-26-1140/received/0-hyatt_thailand_batch{2_4,3_5}.json
      (hyatt.com 포인트 캘린더 · Standard Room · 1박)
  · 6번(@jin_6) UAE 1차 5곳 — 1개 배치
      memory/clones/146dd4d1-jin_6/pickle/2026-11-26-1741/received/0-hyatt-uae-batch1-5.json
      (hyatt.com 포인트 캘린더 · Standard Room · 성인2인·1실)
대상
  data/app/tab10_hyatt.json  377곳 → 413곳 (hy378~hy413)

■ 규칙
- 마스터(1-hyatt-global-master.json)에 36개 spiritCode 전부 등록돼 있고 이름·지역·카테고리·
  브랜드·woh 참여 여부가 배치본과 일치하는지 먼저 확인한다. 마스터 지역(area) 매핑은
  호주 오세아니아 / 말레이시아·태국 동남아 / UAE 중동·아프리카 → 카드 region '중동'.
- 기존 377곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건 확인.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 — ① 탭의 하얏트는
  시드니 파크 하얏트(h119 = hy34)와 방콕·다낭·나트랑 등이며, 이번 36곳은 이름이 겹치지 않아
  alsoIn 0쌍. 시드니 신규 2곳(Caption Central Sydney · Hyatt Regency Sydney)은 ① 탭의
  W·랭햄·샹그릴라·소피텔 2·인터컨티넨탈 2·카펠라·킴튼·파크 하얏트·포시즌스·풀러턴과 다른 호텔.
- city 는 국문(시드니·멜버른·캔버라·브리즈번·골드코스트 / 쿠알라룸푸르·코타키나발루·조호르바루·
  쿠안탄 / 방콕·사뭇쁘라깐·파타야·푸켓·후아힌·코사무이 / 아부다비·두바이), brand 는 공홈 브랜드 라벨,
  category 는 정수.
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 네 배치 모두 현금가 미수집(공홈 현금 캘린더 없음·차단).
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
D4 = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-26-1741/received')
D7 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-1140/received')
D6 = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-26-1741/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

FIRST_ID = 378

# ── 36곳 메타 ────────────────────────────────────────────────────────
# (code, 국문명, 도시, 브랜드, 카테고리, region, 배치시각/출처)
PLAN = [
    # ── 호주 11 (4번 · 오세아니아) — batchA 19:54 / batchB 19:56 KST
    ('canbe', '하얏트 호텔 캔버라 - 파크 하얏트 호텔', '캔버라', 'Park Hyatt', 3, '오세아니아', '19:54'),
    ('sydcp', '캡션 바이 하얏트 센트럴 시드니', '시드니', 'Caption by Hyatt', 3, '오세아니아', '19:54'),
    ('sydrs', '하얏트 리젠시 시드니', '시드니', 'Hyatt Regency', 4, '오세아니아', '19:54'),
    ('bnerb', '하얏트 리젠시 브리즈번', '브리즈번', 'Hyatt Regency', 3, '오세아니아', '19:54'),
    ('oolaz', '안다즈 골드코스트', '골드코스트', 'Andaz', 6, '오세아니아', '19:54'),
    ('melbo', '그랜드 하얏트 멜버른', '멜버른', 'Grand Hyatt', 4, '오세아니아', '19:56'),
    ('melct', '하얏트 센트릭 멜버른', '멜버른', 'Hyatt Centric', 3, '오세아니아', '19:56'),
    ('melxs', '하얏트 하우스 사우스 멜버른', '멜버른', 'Hyatt House', 3, '오세아니아', '19:56'),
    ('melzc', '하얏트 플레이스 멜버른 캐리비안 파크', '멜버른', 'Hyatt Place', 2, '오세아니아', '19:56'),
    ('melze', '하얏트 플레이스 멜버른 에센던 필즈', '멜버른', 'Hyatt Place', 2, '오세아니아', '19:56'),
    ('melsx', '더 스탠다드X 멜버른', '멜버른', 'The StandardX', 3, '오세아니아', '19:56'),
    # ── 말레이시아 11 (4번 · 동남아) — batchA 19:48 / batchB 20:02 KST
    ('jhbzj', '하얏트 플레이스 조호르바루 파라다임 몰', '조호르바루', 'Hyatt Place', 1, '동남아', '19:48'),
    ('bkict', '하얏트 센트릭 코타키나발루', '코타키나발루', 'Hyatt Centric', 2, '동남아', '19:48'),
    ('bkiki', '하얏트 리젠시 키나발루', '코타키나발루', 'Hyatt Regency', 1, '동남아', '19:48'),
    ('kuakt', '하얏트 리젠시 쿠안탄 리조트', '쿠안탄', 'Hyatt Regency', 2, '동남아', '20:02'),
    ('kulal', '알릴라 방사르 쿠알라룸푸르', '쿠알라룸푸르', 'Alila', 2, '동남아', '19:48'),
    ('kuagh', '그랜드 하얏트 쿠알라룸푸르', '쿠알라룸푸르', 'Grand Hyatt', 3, '동남아', '19:48'),
    ('kulct', '하얏트 센트릭 시티 센터 쿠알라룸푸르', '쿠알라룸푸르', 'Hyatt Centric', 1, '동남아', '20:02'),
    ('kulxk', '하얏트 하우스 쿠알라룸푸르 몬트키아라', '쿠알라룸푸르', 'Hyatt House', 1, '동남아', '20:02'),
    ('kulzk', '하얏트 플레이스 쿠알라룸푸르 부킷잘릴', '쿠알라룸푸르', 'Hyatt Place', 1, '동남아', '20:02'),
    ('kulrk', '하얏트 리젠시 쿠알라룸푸르 앳 KL 미드타운', '쿠알라룸푸르', 'Hyatt Regency', 2, '동남아', '20:02'),
    ('kulph', '파크 하얏트 쿠알라룸푸르', '쿠알라룸푸르', 'Park Hyatt', 5, '동남아', '20:02'),
    # ── 태국 9 (7번 · 동남아) — batch2 11:30~11:55 / batch3 12:00~12:45 KST
    ('bkksx', '쿠로 방콕 리버사이드', '방콕', 'Unscripted by Hyatt', 2, '동남아', 'TH2'),
    ('bkksb', '더 스탠다드 방콕 마하나콘', '방콕', 'The Standard', 4, '동남아', 'TH2'),
    ('bkkrb', '하얏트 리젠시 방콕 수완나품 공항', '사뭇쁘라깐', 'Hyatt Regency', 2, '동남아', 'TH2'),
    ('utpsp', '더 스탠다드 파타야 나좀티엔', '파타야', 'The Standard', 3, '동남아', 'TH2'),
    ('phuhr', '하얏트 리젠시 푸켓 리조트', '푸켓', 'Hyatt Regency', 4, '동남아', 'TH3'),
    ('huahi', '하얏트 리젠시 후아힌', '후아힌', 'Hyatt Regency', 3, '동남아', 'TH3'),
    ('hhqub', '더 바라이 후아힌', '후아힌', 'The Unbound Collection by Hyatt', 5, '동남아', 'TH3'),
    ('huash', '더 스탠다드 후아힌', '후아힌', 'The Standard', 3, '동남아', 'TH3'),
    ('usmrk', '하얏트 리젠시 코사무이', '코사무이', 'Hyatt Regency', 5, '동남아', 'TH3'),
    # ── UAE 1차 5 (6번 · 중동) — 20:00 KST
    ('abdcc', '안다즈 캐피털 게이트 아부다비', '아부다비', 'Andaz', 4, '중동', 'UAE'),
    ('auhgh', '그랜드 하얏트 아부다비 호텔 & 레지던스', '아부다비', 'Grand Hyatt', 4, '중동', 'UAE'),
    ('abuph', '파크 하얏트 아부다비 호텔 앤 빌라스', '아부다비', 'Park Hyatt', 6, '중동', 'UAE'),
    ('dxbct', '안다즈 두바이 더 팜', '두바이', 'Andaz', 5, '중동', 'UAE'),
    ('dxbgh', '그랜드 하얏트 두바이', '두바이', 'Grand Hyatt', 4, '중동', 'UAE'),
]

AU_CODES = [p[0] for p in PLAN[0:11]]
MY_CODES = [p[0] for p in PLAN[11:22]]
TH_CODES = [p[0] for p in PLAN[22:31]]
UAE_CODES = [p[0] for p in PLAN[31:36]]

BATCH_OF = {}
for c in AU_CODES:
    BATCH_OF[c] = '호주'
for c in MY_CODES:
    BATCH_OF[c] = '말레이시아'
for c in TH_CODES:
    BATCH_OF[c] = '태국'
for c in UAE_CODES:
    BATCH_OF[c] = 'UAE'

COUNTRY_KO = {'호주': '호주', '말레이시아': '말레이시아', '태국': '태국', 'UAE': '아랍에미리트(UAE)'}

CASH_NULL_AU = ('현금 요금은 365일 전부 —입니다 — 공홈 세후 KRW 현금은 미수집'
                '(2026-11-26 rate JSON 1회 조회가 빈 본문으로 차단돼 확정 불가).')
CASH_NULL_MY = ('현금 요금은 365일 전부 —입니다 — 공홈 세후 KRW 현금은 미수집'
                '(rooms/roomrates 엔드포인트가 404 로 미지원).')
CASH_NULL_TH = '현금 요금은 365일 전부 —입니다 — 태국 배치들도 공홈 세후 KRW 현금가는 미수집입니다.'
CASH_NULL_UAE = ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아'
                 '(1박 단위 shop/rooms 화면에서만 표시) 미수집으로 두었습니다.')

# 배치본에 호텔별 note 가 있는 경우(태국·UAE) 그대로 쓰고, 우리 표기 보정만 덧붙인다.
EXTRA_NOTE = {
    'bkkrb': ' ※ 공홈 마스터의 도시 표기는 「Samut Prakan」 이고 실제 소재지도 사뭇쁘라깐주'
             '(방콕 수완나품 공항)라 카드 도시를 사뭇쁘라깐으로 적었습니다.',
    'kuakt': ' ※ 공홈 마스터의 도시 표기는 「Pahang」 이지만 실제 소재지는 쿠안탄'
             '(하얏트 리젠시 쿠안탄 리조트 · 파항주 쿠안탄)이라 카드 도시를 쿠안탄으로 적었습니다.',
    'oolaz': ' 공홈에서 이미 판매·포인트 예약이 열려 있는 호텔(카테고리 6)이며 「예정 호텔」이 아닙니다.',
    'melsx': ' The StandardX 브랜드의 신규 카드로, 365일 가운데 364일에 어워드가 표출됩니다.',
    'sydcp': ' 2026-12-06~12-12(7일)는 7박·2박 창으로 다시 조회해도 days:{} + responseInfo=soldOutHotel'
             ' 로 매진이 확인됐습니다(최소숙박 파라미터 문제 아님).',
    'sydrs': ' 2026-12-02·12-03은 응답에 CLUB(21,000P)·SUITE(24,000P)만 표출돼 스탠다드룸 어워드만'
             ' 소진된 날이고, 2026-12-01은 CLUB·SUITE도 없이 비어 있었습니다.',
    'jhbzj': ' 2026-12-11~12-20(10일)이 연속 결번입니다.',
    'bkict': ' 2027-02-04~02-10(7일)이 연속 결번입니다.',
    'kulct': ' 2026-12~2027-03 결번이 2~4일 단위로 몰려 있고(연말연시·2월 중순 성수), 2027-03 이후는'
             ' 결번이 없습니다.',
    'kulph': ' 2027-03-11~03-14(4일)가 연속 결번입니다.',
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


def load_bundles():
    hotels = {}
    meta = {}
    for name in ('0-hyatt-au-batchA.json', '0-hyatt-au-batchB.json',
                 '0-hyatt-my-batchA.json', '0-hyatt-my-batchB.json'):
        d = json.load(open(os.path.join(D4, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30'
        for code, h in d['hotels'].items():
            assert code not in hotels, code
            hotels[code] = h
            meta[code] = d['meta']
    for name in ('0-hyatt_thailand_batch2_4.json', '0-hyatt_thailand_batch3_5.json'):
        d = json.load(open(os.path.join(D7, name), encoding='utf-8'))
        w = d.get('window') or d['meta'].get('window')
        assert w == '2026-12-01~2027-11-30', w
        for code, h in d['hotels'].items():
            assert code not in hotels, code
            hotels[code] = h
            meta[code] = d['meta']
    d = json.load(open(os.path.join(D6, '0-hyatt-uae-batch1-5.json'), encoding='utf-8'))
    assert d['window'] == {'start': '2026-12-01', 'end': '2027-11-30', 'days': 365}, d['window']
    for h in d['hotels']:
        assert h['code'] not in hotels, h['code']
        hotels[h['code']] = h
        meta[h['code']] = d
    assert len(hotels) == 36, len(hotels)
    return hotels, meta


def pts_of(h):
    raw = h.get('points') or {}
    if isinstance(raw, list):
        raw = dict(raw)
    return [raw.get(d) for d in DATES]


def runs_of(pts):
    out, cur = [], []
    for d, v in zip(DATES, pts):
        if v is None:
            cur.append(d)
        else:
            if cur:
                out.append((cur[0], cur[-1], len(cur)))
                cur = []
    if cur:
        out.append((cur[0], cur[-1], len(cur)))
    return out


def fmt_run(r):
    a, b, n = r
    if a == b:
        return '%s(1일)' % a
    if a[:7] == b[:7]:
        return '%s~%s(%d일)' % (a[5:], b[5:], n)
    return '%s~%s(%d일)' % (a, b, n)


LEVEL_KO = collections.OrderedDict((
    ('SUPER_OFF_PEAK', 'SUPER_OFF_PEAK'), ('OFF_PEAK', 'OFF_PEAK'), ('STANDARD', 'STANDARD'),
    ('PEAK', 'PEAK'), ('SUPER_PEAK', 'SUPER_PEAK')))


def dist_text(pts, info=None):
    cnt = collections.Counter(v for v in pts if v is not None)
    # 값 → 레벨(같은 값이 여러 레벨에 걸리면 가장 많이 나온 레벨)
    val2lv = {}
    lv = info.get('levels') if isinstance(info, dict) else None
    if isinstance(lv, dict):
        pairs = collections.Counter()
        for d, name in lv.items():
            v = (info.get('points') or {}).get(d)
            if v is not None:
                pairs[(v, name)] += 1
        agg = collections.defaultdict(collections.Counter)
        for (v, name), n in pairs.items():
            agg[v][name] += n
        for v, c in agg.items():
            val2lv[v] = c.most_common(1)[0][0]
    out = []
    for v, n in sorted(cnt.items(), key=lambda kv: (-kv[1], -kv[0])):
        tag = LEVEL_KO.get(val2lv.get(v, ''), '')
        out.append('%sP%s %d일' % ('{:,}'.format(v), (' ' + tag) if tag else '', n))
    return ' · '.join(out)


def note_au_my(code, kr, city, brand, cat, time, info, bmeta):
    pts = pts_of(info)
    priced = sum(1 for v in pts if v is not None)
    nb = dict(info.get('null_breakdown') or {})
    nkey = nb.get('no_key_in_response', 0)
    nobj = sum(v for k, v in nb.items() if k != 'no_key_in_response')
    runs = runs_of(pts)
    rtxt = ' · '.join(fmt_run(r) for r in runs[:6])
    if len(runs) > 6:
        rtxt += ' 등'
    if nkey and nobj:
        why = ('값 없는 %d일 가운데 %d일은 응답에 날짜 키가 없는 날(no_key_in_response), '
               '%d일은 날짜 키는 있으나 그날 스탠다드룸이 없는 날(empty_day_object · 상위 객실만 표출)입니다 — '
               '매진·어워드 미개방·최소숙박 미충족이 섞여 이 엔드포인트로는 구분되지 않아 보간 없이 —로 두었습니다.'
               % (365 - priced, nkey, nobj))
    elif nkey:
        why = ('값 없는 %d일은 모두 응답에 날짜 키가 없는 날(no_key_in_response)로, '
               '매진·어워드 미개방·최소숙박 미충족이 섞여 구분되지 않아 보간 없이 —로 두었습니다.' % (365 - priced))
    elif nobj:
        why = ('값 없는 %d일은 날짜 키는 있으나 스탠다드룸이 없는 날(empty_day_object · 상위 객실만 표출)로 '
               '보간 없이 —로 두었습니다.' % (365 - priced))
    else:
        why = '365일 전부 값이 있습니다(결번 0일).'
    if runs:
        why += ' 결번 구간: %s.' % rtxt

    country = COUNTRY_KO[BATCH_OF[code]]
    cash = CASH_NULL_AU if BATCH_OF[code] == '호주' else CASH_NULL_MY
    sent = ('스탠다드 아워드 365일 실측(2026-11-26 %s KST · hyatt.com · %s %s) — '
            '하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM · '
            '성인1·1박 · 60일 창 6회+5일 창 1회)으로 365칸을 받았고, 공홈 표시 어워드 카테고리 %d입니다. '
            '포인트 %d일. %s 분포: %s. %s %s %s'
            % (time, country, city, cat, priced, why, dist_text(pts, info),
               EXTRA_NOTE.get(code, '').strip(), cash, '4번(@jin_4)이 실측해 보낸 본입니다.'))
    return ' '.join(sent.split())


def note_from_source(code, city, brand, cat, info, sess_note, cash):
    """태국·UAE — 배치본 note 를 그대로 살리고 우리 머리말·현금 미수집 문구를 붙인다."""
    src = clean(info.get('note') or '')
    extra = EXTRA_NOTE.get(code, '').strip()
    body = ' '.join(x for x in (sess_note, src, extra) if x)
    tail = ('공홈 표시 어워드 카테고리 %d(%s · %s). %s %s'
            % (cat, brand, city, cash, '7번(@no_7)이 실측해 보낸 본입니다.' if code in TH_CODES
               else '6번(@jin_6)이 실측해 보낸 본입니다.'))
    return body + ' ' + tail


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 377, len(before)
    assert before[-1]['id'] == 'hy377', before[-1]['id']

    hotels, meta = load_bundles()
    assert set(hotels) == {p[0] for p in PLAN}, sorted(hotels)

    # ── 공홈 마스터 대조 ────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    AREA_OK = {'오세아니아': '오세아니아', '동남아': '동남아', '중동': '중동·아프리카'}
    for code, kr, city, brand, cat, region, _ in PLAN:
        m = byc[code]
        h = hotels[code]
        assert norm(m['name']) == norm(h['name']), (code, m['name'], h['name'])
        assert m['area'] == AREA_OK[region], (code, m['area'], region)
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert str(cat) == str(h['category']), (code, cat, h['category'])
        assert clean(h['brand']) == clean(brand) == clean(m['brand']), (code, h['brand'], brand, m['brand'])
        assert m['woh_participating'] is True, code

    # ── 기존 377곳 중복 확인 ────────────────────────────────────────
    exist_codes = {x['code']: x['id'] for x in before}
    exist_names, exist_kr = {}, {}
    for x in before:
        exist_names.setdefault(norm(x['english']), []).append(x['id'])
        exist_kr.setdefault(norm_ko(x['name']), []).append(x['id'])
    exist_tokens = {x['id']: set(norm(x['english']).split()) for x in before}
    for code, kr, city, brand, cat, region, _ in PLAN:
        h = hotels[code]
        assert code not in exist_codes, ('code dup', code, exist_codes.get(code))
        assert not exist_names.get(norm(h['name'])), ('english dup', code, h['name'])
        assert not exist_kr.get(norm_ko(kr)), ('korean dup', code, kr)
        toks = set(norm(h['name']).split())
        for hid, et in exist_tokens.items():
            assert not toks <= et, ('same hotel?', code, hid, et)

    # ── ① 호텔럭스 161곳 전수 대조 ──────────────────────────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
    assert len(rows) == 161, len(rows)
    by_eng, by_kr, by_city = {}, {}, {}
    for r in rows:
        if r.get('english'):
            by_eng.setdefault(norm(r['english']), []).append(r['id'])
        if r.get('name'):
            by_kr.setdefault(norm_ko(r['name']), []).append(r['id'])
        by_city.setdefault(clean(r.get('city')), []).append(r['id'])
    overlaps = []
    for code, kr, city, brand, cat, region, _ in PLAN:
        h = hotels[code]
        if norm(h['name']) in by_eng:
            overlaps.append(('english', code, by_eng[norm(h['name'])]))
        if norm_ko(kr) in by_kr:
            overlaps.append(('korean', code, by_kr[norm_ko(kr)]))
    assert not overlaps, overlaps
    # ① 탭이 있는 도시와 겹치는 곳은 이름으로 겹침 0 재확인
    print('① 호텔럭스 도시:', {k: v for k, v in by_city.items()
                                if k in ('시드니', '멜버른', '방콕', '두바이', '쿠알라룸푸르',
                                         '아부다비', '푸켓', '후아힌', '코사무이', '파타야')})
    assert '시드니' in by_city and '방콕' in by_city
    print('① 호텔럭스 161곳 대조 — 겹침 0곳')

    added = []
    for i, (code, kr, city, brand, cat, region, tm) in enumerate(PLAN):
        hid = 'hy%d' % (FIRST_ID + i)
        info = hotels[code]
        pts = pts_of(info)
        assert len(pts) == 365
        priced = sum(1 for v in pts if v is not None)
        assert all(v is None or (isinstance(v, int) and v > 0) for v in pts)
        assert priced == info.get('days_priced', priced), (code, priced, info.get('days_priced'))

        if code in AU_CODES or code in MY_CODES:
            bmeta = meta[code]
            note = note_au_my(code, kr, city, brand, cat, tm, info, bmeta)
        elif code in TH_CODES:
            stamp = '2026-11-26 11:30~12:45 KST' if tm == 'TH3' else '2026-11-26 11:30~11:55 KST'
            head = ('스탠다드 아워드 365일 실측(%s · hyatt.com · 태국 %s) — 하얏트 공홈 포인트 캘린더'
                    '(Standard Room · 1박 · 성인2인·1실)로 365칸 전수 실측.' % (stamp, city))
            note = note_from_source(code, city, brand, cat, info, head, CASH_NULL_TH)
        else:
            head = ('스탠다드 아워드 365일 실측(2026-11-26 20:00 KST · hyatt.com · UAE %s) —' % city)
            note = note_from_source(code, city, brand, cat, info, head, CASH_NULL_UAE)

        entry = {
            'id': hid,
            'group': 'hyatt',
            'code': code,
            'region': region,
            'city': city,
            'name': kr,
            'english': clean(info['name']),
            'brand': brand,
            'category': cat,
            'vip_id': None,
            'alsoIn': None,
            'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None,
            'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % code, 'hlx': None},
            'promotion': None,
            'note': ' '.join(note.split()),
        }
        added.append(entry)
        print('%s %-6s %-4s %-14s %-38s Cat %-2s %3d일' % (hid, code, region, city, kr, cat, priced))

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'
    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    hs = tab['hotels']
    cells = sum(len(h['points']['$v']) for h in hs)
    priced = sum(1 for h in hs for v in h['points']['$v'] if v is not None)
    reg = collections.Counter(h['region'] for h in hs)
    print('hotels', len(hs), 'cells', cells, 'priced', priced, dict(reg))
    assert len(hs) == 413 and cells == 413 * 365
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['오세아니아'] == 13 and reg['동남아'] == 57 and reg['중동'] == 5, dict(reg)
    assert priced == 133796, priced


if __name__ == '__main__':
    main()
