#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotel-calendar-app 통합 마스터 DB 도구.

`index.html` 안의 `const DB`(호텔 238곳 × 365일)와 `const FLIGHTS`(부산 출발 항공 특가)를
읽어 `data/master_db.json` 한 파일로 모으고, 그 파일이 라이브 앱과 정확히 같은지 검사한다.

사용법 (저장소 루트에서):
    python3 tools/master_db.py extract   # index.html -> data/master_db.json (전체 재생성)
    python3 tools/master_db.py verify    # master_db.json 이 index.html 과 일치하는지 검사
    python3 tools/master_db.py inject    # master_db.json -> index.html (DB·FLIGHTS 다시 채움)
    python3 tools/master_db.py stats     # 수록 범위·건수만 출력

`inject` 는 index.html 을 백업한 뒤 `const DB = ...` / `const FLIGHTS = ...` 두 구간만
바꾸고, 나머지 바이트는 그대로 둔다. 바꾼 뒤 스스로 `verify` 를 다시 돌려 실패하면 되돌린다.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

WINDOW_START = '2026-12-01'
WINDOW_END = '2027-11-30'

# 탭별 기대 호텔 수 — ② 중올플 289곳(참여 287 + 기존 미참여·자격없음 2) · ③ 아코르 25곳 · 총 538곳
EXPECT_TABS = {'lux': 162, 'china': 289, 'domestic': 25, 'marriott': 62}
EXPECT_HOTELS = sum(EXPECT_TABS.values())
# ② 중올플 APC — 참여 282 + 기존 2 = 284곳 · 12월 관측 창(12/1~18) 가능 210곳 · APC 칸 4,715
EXPECT_APC = {'hotels': 289, 'participating': 287, 'dec_available': 210,
              'cells': 4715, 'tiers': {1: 116, 2: 137, 3: 36},
              'cash_filled': 40, 'cash_empty': 249}

# ③ 아코르 · Stay Plus & SNU — 국내 4곳 + 한·중·일 페어몬트·소피텔 21곳(365일)
EXPECT_ACCOR3 = {
    'hotels': 25, 'new': 21,
    'priced': {'C1B5': 0, 'A7Z9': 124, 'A5G7': 263, '8167': 357, 'B6R8': 362},
    'snu_rows': 43, 'snu_cities': 8,
}
EXPECT_DOMESTIC_PROGRAM = {'dB220': (True, True), 'dB200': (True, False),
                           'dA3N6': (True, False), 'dC2G2': (True, False)}
# 출처 문구에 사이트 이름을 쓰지 않는다
FORBIDDEN = ('accorcards', 'ittaeda', 'roame', '트립닷컴')


def check_apc(db):
    """② 중올플 284곳 · 권역(tier) · APC 상태 검사."""
    problems = []
    china = [h for h in db['hotels'] if h.get('group') == 'china']
    if len(china) != EXPECT_APC['hotels']:
        problems.append('② 중올플 %d곳 (기대 %d곳)' % (len(china), EXPECT_APC['hotels']))
    part = [h for h in china if (h.get('accor') or {}).get('participation') == 'participating']
    if len(part) != EXPECT_APC['participating']:
        problems.append('② 참여 %d곳 (기대 %d곳)' % (len(part), EXPECT_APC['participating']))
    pids = [(h.get('accor') or {}).get('public_id') for h in china]
    if len(set(pids)) != len(pids) or None in pids:
        problems.append('② public_id 중복/누락')
    tiers = {}
    cells = dec_av = 0
    legacy_cash = 0
    fresh_none = 0
    for h in china:
        a = h.get('accor') or {}
        t = a.get('tier')
        tiers[t] = tiers.get(t, 0) + 1
        if t not in (1, 2, 3):
            problems.append('② %s 권역(tier) 없음/이상: %s' % (h['id'], t))
        if not a.get('tier_label') or not a.get('city_key'):
            problems.append('② %s 권역명/도시키 없음' % h['id'])
        if a.get('participation') == 'participating':
            obs = (a.get('dec') or {}).get('observed', 0)
            if not h.get('accor_apc') and obs:
                problems.append('② %s APC 날짜 상태 없음 (관측 %d일)' % (h['id'], obs))
            for d, v in (h.get('accor_apc') or {}).items():
                if v not in ('a', 'n') or not (WINDOW_START <= d <= WINDOW_END):
                    problems.append('② %s APC 값 이상 %s=%s' % (h['id'], d, v))
                    break
                if d not in (h.get('accor_apc_t') or {}):
                    problems.append('② %s APC 관측시각 누락 %s' % (h['id'], d))
                    break
                cells += 1
                if v == 'a' and d <= '2026-12-18':
                    dec_av += 1
            for k in ('dec', 'nov'):
                v = a.get(k)
                if not isinstance(v, dict) or 'available' not in v or 'observed' not in v:
                    problems.append('② %s %s 관측 요약 없음' % (h['id'], k))
        priced = sum(1 for v in (h.get('rates') or {}).values() if v is not None)
        if priced:
            legacy_cash += 1
            if priced < 100:
                # 우한(2027-04 이후 요금 이상 241일 제외)만 124일이다 — 더 줄면 요금이 유실된 것
                if h['name'] != '페어몬트 우한':
                    problems.append('② %s 현금 요금 %d일 (100일 미만)' % (h['id'], priced))
        else:
            fresh_none += 1
        for v in (h.get('rates') or {}).values():
            if v is not None and (not isinstance(v, int) or v <= 0):
                problems.append('② %s 요금이 양의 정수가 아님: %r' % (h['id'], v))
                break
            if isinstance(v, int) and v > 3_000_000:
                problems.append('② %s 에 비정상 고가(%s) — 이상값은 null 이어야 함' % (h['id'], v))
                break
        if len(h.get('rates') or {}) != 365:
            problems.append('② %s 날짜 칸 %d개' % (h['id'], len(h.get('rates') or {})))
    if tiers != EXPECT_APC['tiers']:
        problems.append('② 권역 분포 %s (기대 %s)' % (tiers, EXPECT_APC['tiers']))
    if cells != EXPECT_APC['cells']:
        problems.append('② APC 칸 %d (기대 %d)' % (cells, EXPECT_APC['cells']))
    dec_hotels = len({h['id'] for h in china
                      if any(v == 'a' and d <= '2026-12-18'
                             for d, v in (h.get('accor_apc') or {}).items())})
    if dec_hotels != EXPECT_APC['dec_available']:
        problems.append('② 12월 APC 가능 호텔 %d곳 (기대 %d곳)' % (dec_hotels, EXPECT_APC['dec_available']))
    if legacy_cash != EXPECT_APC['cash_filled']:
        problems.append('② 현금 요금 보유 호텔 %d곳 (기대 %d곳)' % (legacy_cash, EXPECT_APC['cash_filled']))
    if fresh_none != EXPECT_APC['cash_empty']:
        problems.append('② 현금 미수집 호텔 %d곳 (기대 %d곳)' % (fresh_none, EXPECT_APC['cash_empty']))
    return problems


def check_accor3(db):
    """③ 아코르 · Stay Plus & SNU — 21곳 365일 · 우한 이상값 제외 · alsoIn 양방향 · SNU 표."""
    problems = []
    dom = [h for h in db['hotels'] if h.get('group') == 'domestic']
    if len(dom) != EXPECT_ACCOR3['hotels']:
        problems.append('③ 아코르 %d곳 (기대 %d곳)' % (len(dom), EXPECT_ACCOR3['hotels']))
    ids = {h['id']: h for h in db['hotels']}
    new = [h for h in dom if h['id'].startswith('a')]
    if len(new) != EXPECT_ACCOR3['new']:
        problems.append('③ 신규 %d곳 (기대 %d곳)' % (len(new), EXPECT_ACCOR3['new']))
    for h in dom:
        rates = h.get('rates') or {}
        if len(rates) != 365:
            problems.append('③ %s 날짜 칸 %d개' % (h['id'], len(rates)))
        for v in rates.values():
            if v is not None and (not isinstance(v, int) or v <= 0):
                problems.append('③ %s 요금이 양의 정수가 아님: %r' % (h['id'], v))
                break
            if isinstance(v, int) and v > 3_000_000:
                problems.append('③ %s 에 비정상 고가(%s) — 이상값은 null 이어야 함' % (h['id'], v))
                break
        if h.get('alsoIn'):
            other = ids.get(h['alsoIn'])
            if other is None:
                problems.append('③ %s alsoIn %s 대상 없음' % (h['id'], h['alsoIn']))
            elif other.get('alsoIn') != h['id']:
                problems.append('③ %s ↔ %s alsoIn 이 한쪽만 있음' % (h['id'], h['alsoIn']))
    for code, n in EXPECT_ACCOR3['priced'].items():
        h = ids.get('a' + code)
        if not h:
            problems.append('③ %s 없음' % code)
            continue
        got = sum(1 for v in (h.get('rates') or {}).values() if v is not None)
        if got != n:
            problems.append('③ %s 요금 표시 %d일 (기대 %d일)' % (h['name'], got, n))
    for hid, (sp, snu) in EXPECT_DOMESTIC_PROGRAM.items():
        p = (ids.get(hid) or {}).get('program') or {}
        if p.get('stayplus') is not sp or p.get('snu') is not snu:
            problems.append('③ %s program %s (기대 stayplus=%s snu=%s)' % (hid, p, sp, snu))
    accor = db.get('accor') or {}
    program = accor.get('program') or {}
    if program.get('stayplusExpiry') != '2027-09-30' or program.get('snuExpiry') != '2027-12-31':
        problems.append('③ SNU/Stay Plus 만료일 %s' % program)
    rows = accor.get('rows') or []
    if len(rows) != EXPECT_ACCOR3['snu_rows']:
        problems.append('③ SNU 후보 %d줄 (기대 %d줄)' % (len(rows), EXPECT_ACCOR3['snu_rows']))
    cities = {r.get('city') for r in rows}
    if len(cities) != EXPECT_ACCOR3['snu_cities']:
        problems.append('③ SNU 도시 %d개 (기대 %d개: %s)' % (len(cities), EXPECT_ACCOR3['snu_cities'],
                                                        sorted(cities)))
    for r in rows:
        if not r.get('hotel') or not r.get('checkin'):
            problems.append('③ SNU 줄에 호텔/체크인 없음: %s' % r)
            continue
        if not (WINDOW_START <= r['checkin'] <= WINDOW_END):
            problems.append('③ SNU 체크인 창 밖: %s' % r)
        for k in ('snu', 'list', 'save'):
            if not isinstance(r.get(k), int) or r[k] <= 0:
                problems.append('③ SNU %s 값 이상: %s' % (k, r))
        if isinstance(r.get('snu'), int) and isinstance(r.get('list'), int) and r['list'] < r['snu']:
            problems.append('③ SNU 정가가 SNU 요금보다 쌈: %s' % r)
    return problems


def check_sources(text_blob):
    """출처 문구에 제3자 사이트 이름이 남아 있지 않은지 검사."""
    low = text_blob.lower()
    hits = [w for w in FORBIDDEN if w in low]
    return ['출처 문구에 금지된 사이트 이름: %s' % ', '.join(hits)] if hits else []


EXPECT_BRANDS = {'리츠칼튼': 24, '세인트레지스': 14, 'W': 10, 'JW 메리어트': 4,
                 '럭셔리 컬렉션': 2, '에디션': 2, '웨스틴': 2, '메리어트': 1,
                 '오토그래프 컬렉션': 1, '메리어트 이그제큐티브 아파트먼트': 1, '르메르디앙': 1}
# 한·일 원본 CSV 기대치(2026-11-17 수집) — 유실·중복 방지용 고정값
EXPECT_KJ = {'hotels': 22, 'cash': 6800, 'points': 6629}
# ① HoteLux 탭과 호텔이 겹치는 ⑤ 항목(요금 출처가 달라 둘 다 수록) — alsoIn 으로 교차 표시
EXPECT_OVERLAP = {'k01', 'k02', 'k04', 'k05', 'j01', 'j04', 'j10', 'j11', 'j12'}
# 원래부터 두 탭에 있던 중복(③ Stay Plus ↔ ① HoteLux) — 새 중복과 구분하기 위한 허용 목록
KNOWN_DUP = {('dB200', 'h39')}

# ④ 항공 — 47개 노선(기존 24 + 중국 신규 8 + 필리핀 신규 4 + 일본 신규 7 + 동남아 신규 4)
# · 2026년 12월 ~ 2027년 11월(12개월) · 당일치기(0박) 패턴
EXPECT_FLIGHTS = 47
# 중국 신규 8노선 — 노선 코드 → (도시 이름, 딜 건수). 12~1월 완본(9주 × 5패턴 180칸) +
# 연길·장가계·구이린·황산의 2027년 2~6월 금~일(2박) 71칸 + 연길 6/5 토~월 1칸(2026-11-18 반영)
# + 선양·다롄·광저우·샤먼의 2027년 2~6월 2박 168칸 완주본(금~일 84 + 토~월 84, 2026-11-18 반영)
# + 연길·장가계·구이린 2027년 2~6월 토~월 28칸(2026-11-18 반영, 황산 토~월은 값 0칸·0건 6칸)
# + 2026-11-18 완주본 2건 — 선양·다롄·광저우·샤먼 목~일 84칸 + 선양 금~월 1칸,
#   연길·장가계·구이린·황산 토~월 48칸(황산 3/20 토~월은 판매편 0건으로 정정)
# + 2026-11-18 3박 완주본 2건 — 선양·다롄·광저우·샤먼 2027년 2~6월 금~월 84칸(선양 2/5는 기존이라
#   신규 83칸), 연길·장가계·구이린·황산 2027년 2~6월 목~일 84칸(황산 포함 0건 없음)
# + 2026-11-18 G1 갱신본 — 선양·다롄·광저우·샤먼 2027년 2~6월 목~월(4박) 48칸(2/4~4/22 12주, 4/29 이후 미조회)
# + 2026-11-18 중국 8개 노선 2027년 7~11월 15주말 × 7패턴(측정 465 · 요금 465칸) —
#   SHE +75 · DLC +105 · CAN +90 · XMN +75 · YNJ +105 · DYG +15 · KWL +0 · TXN +0
# + 2026-11-18 G1 완결본 — 선양·다롄·광저우·샤먼 2027년 2~6월 목~월(4박) 4/29~6/24 9주 36칸을 더해 420/420칸(100%)
#   SHE +9 · DLC +9 · CAN +9 · XMN +9
# + 2026-11-18 일본 7노선 2027년 1월 완결본 140칸(값 138 · 항공편 없음 2) + 당일치기 21칸
#   KMJ +26 · TAK +23 · MYJ +20 · FSZ +28 · MMY +20 · CTS +22 · KOJ +20
EXPECT_NEW_ROUTES = {'SHE': ('선양', 226), 'DLC': ('다롄', 256), 'CAN': ('광저우', 241), 'XMN': ('샤먼', 226),
                     'YNJ': ('연길', 256), 'DYG': ('장가계', 166), 'KWL': ('구이린', 150), 'TXN': ('황산', 87)}
# 2026-11-18 신규 15노선 — 노선 코드 → (도시 이름, 딜 건수).
# 필리핀 4노선(4번)은 2026.12~2027.01 9주 × 5패턴 45칸씩 180칸 완본(판매편 0건 없음),
# 동남아 4노선(4번)은 같은 기간 178칸(비엔티안 12/3 목~일·목~월 2칸은 가격 미제공),
# 일본 7노선(5번)은 2026년 12월 완결본 171칸(175칸 중 — 삿포로 25칸 완결 + 시즈오카 21 · 나머지 25씩)
#   + 당일치기 실측 4칸(삿포로·구마모토·시즈오카·다카마쓰) = 175칸. 미실측은 시즈오카 4칸(표시 운임 없음).
# 동남아 4노선(4번)은 2026.12~2027.01 178칸 + 2027년 2~6월 21주 × 5패턴 420칸(푸꾸옥·코타키나발루·
#   쿠알라룸푸르 150칸씩 · 비엔티안 148칸 — 12/3 목~일·목~월 2칸 가격 미제공).
# 필리핀 4노선은 2026-11-18 2027년 2~6월 21주 × 5패턴 105칸을 더해 150칸이 됐고,
# 같은 날 저녁 2027년 7~11월 1차 실측(실측 126칸)을 더해 세부 162 · 마닐라 207 · 보홀 152 · 클락 205칸이다.
EXPECT_NEW_ROUTES2 = {'CEB': ('세부', 162), 'MNL': ('마닐라', 207), 'TAG': ('보홀(팡라오)', 152),
                      'CRK': ('클락', 205), 'PQC': ('푸꾸옥', 205), 'BKI': ('코타키나발루', 205),
                      'KUL': ('쿠알라룸푸르', 205), 'VTE': ('비엔티안', 203),
                      'KMJ': ('구마모토', 95), 'KOJ': ('가고시마', 149),
                      'FSZ': ('시즈오카', 83), 'MYJ': ('마쓰야마', 118), 'TAK': ('다카마쓰', 152),
                      'MMY': ('미야코지마', 69), 'CTS': ('삿포로', 191)}
# 일본 7노선 당일치기 실측 4칸(0박) — 노선 → (출발일, 금액). 나머지 노선은 당일치기 칸이 없다.
EXPECT_JP_DAYTRIP = {'CTS': ('2026-12-12', 574900), 'KMJ': ('2026-12-16', 370300),
                     'FSZ': ('2026-12-09', 305800), 'TAK': ('2026-12-24', 795000)}
# 일본 7노선의 1월 칸 — 2026-11-18 1월 완결본(4주 × 5패턴 140칸) + 당일치기 실측
#   = 기존 12/31 주 3칸 + 주말형 값/항공편 없음 + 당일치기(KMJ 6 · TAK 4 · FSZ 9 · CTS 2)
EXPECT_JP_JAN = {'CTS': 25, 'FSZ': 31, 'KOJ': 23, 'KMJ': 29, 'MYJ': 23, 'TAK': 26, 'MMY': 23}
# 일본 7노선 1월 주말형 5패턴 — 값 138칸 + 항공편 없음 2칸(다카마쓰 1/30 토~월 · 시즈오카 1/15 금~월)
EXPECT_JP_JAN_NOFLIGHT = {('TAK', '2027-01-30', '토~월'), ('FSZ', '2027-01-15', '금~월')}
EXPECT_JP_JAN_DAYTRIP = {'CTS': 2, 'FSZ': 9, 'KMJ': 6, 'TAK': 4}
# 2026-11-18 — 일본 7개 노선 2027년 2~6월 21주 × 7패턴 1,029칸 (실측 523 · 0건 303 · 요금 미공개 98 · 미조회 105)
# 노선 → (실측 칸, 최저, 최고, 직항이 최저가인 칸). 2027-02-01~06-30 구간만 센다.
JP26 = ('KMJ', 'KOJ', 'FSZ', 'MYJ', 'TAK', 'MMY', 'CTS')
JP26_WEEKS = tuple((datetime.date(2027, 2, 4) + datetime.timedelta(days=7 * i)).isoformat()
                   for i in range(21))
JP26_WK = ('금~일', '토~월', '목~일', '금~월', '목~월')
JP26_DAY = ('토~토', '일~일')
JP26_PATS = JP26_WK + JP26_DAY
EXPECT_JP26 = {'KMJ': (43, 476800, 1028300, 0), 'KOJ': (104, 508800, 1600600, 7),
               'FSZ': (33, 274400, 1746600, 13), 'MYJ': (73, 271700, 3074400, 35),
               'TAK': (103, 226400, 2322200, 14), 'MMY': (24, 878800, 1093600, 0),
               'CTS': (143, 374303, 1144600, 47)}
# 노선 → {'주말형': (실측, 0건, 요금 미공개, 미조회), '당일치기': (...)} — 원문 노선별 특징·당일치기 표
EXPECT_JP26_STATUS = {
    'KMJ': {'주말형': (40, 0, 61, 4), '당일치기': (3, 0, 0, 39)},
    'KOJ': {'주말형': (102, 0, 0, 3), '당일치기': (2, 31, 0, 9)},
    'FSZ': {'주말형': (33, 68, 0, 4), '당일치기': (0, 24, 0, 18)},
    'MYJ': {'주말형': (73, 7, 25, 0), '당일치기': (0, 20, 11, 11)},
    'TAK': {'주말형': (103, 0, 0, 2), '당일치기': (0, 33, 0, 9)},
    'MMY': {'주말형': (24, 81, 0, 0), '당일치기': (0, 39, 0, 3)},
    'CTS': {'주말형': (105, 0, 0, 0), '당일치기': (38, 0, 1, 3)},
}
EXPECT_JP26_CELLS = len(JP26) * len(JP26_WEEKS) * len(JP26_PATS)      # 1,029칸
EXPECT_JP26_DEALS = 523
EXPECT_JP26_NOSALE = 303
EXPECT_JP26_NOFARE = 98
EXPECT_JP26_BLANK = 105
# 이 달 실측 칸 수(출발일 기준) — 요약 md 와 같은 값
EXPECT_JP26_BY_MONTH = {'2027-02': 130, '2027-03': 135, '2027-04': 84,
                        '2027-05': 91, '2027-06': 83}
# 중국 G1(선양·다롄·광저우·샤먼) 2027년 2~6월 21주 × 5패턴 420칸(100%) — 노선별 최저·최고(원)
EXPECT_PUS4_FULL = {'SHE': (417700, 759800), 'DLC': (317400, 663000),
                    'CAN': (500700, 821600), 'XMN': (462400, 884000)}
# 중국 G2(연길·장가계·구이린·황산) 2027년 2~6월 21주 × 5패턴 420칸 완결 —
# 노선 → (값 칸, 최저, 최고). 황산은 판매편 0건 36칸을 떼고 값 69칸이다.
EXPECT_G2_FULL = {'YNJ': (105, 455700, 932000), 'DYG': (105, 686700, 904100),
                  'KWL': (105, 525900, 879900), 'TXN': (69, 783500, 2588000)}
EXPECT_PH4 = ('CEB', 'MNL', 'TAG', 'CRK')
EXPECT_SEA4 = ('PQC', 'BKI', 'KUL', 'VTE')
# 비엔티안 12/3 목~일·목~월은 항공편은 표시되나 이코노미 판매 가격이 없어 빈칸(0건 아님)
EXPECT_SEA4_MISSING = {('VTE', '2026-12-03', '목~일'), ('VTE', '2026-12-03', '목~월')}
# 2027년 3월 1주차(3/4~8) 기존 24개 노선 × 5패턴 120칸 완본(2026-11-18 5번 보고서)
EXPECT_MAR_W1_START = '2027-03-04'
# 2027년 3월 2주차(3/11~15) 기존 24개 노선 × 5패턴 120칸 완본(2026-11-18 5번 보고서)
EXPECT_MAR_W2_START = '2027-03-11'
# 3·4주차(3/18~22 · 3/25~29) 120칸씩 — 2026-11-18 추가 도착분. 1~4주차로 3월 480칸 완결.
EXPECT_MAR_W3_START = '2027-03-18'
EXPECT_MAR_W4_START = '2027-03-25'
EXPECT_MAR_W3_OVERALL = (245600, 553000)   # 최저 후쿠오카 3/20 토~월 · 최고 도쿄 3/18 목~일
EXPECT_MAR_W4_OVERALL = (278400, 701200)   # 최저 상하이 3/26 금~월 · 최고 치앙마이 3/26 금~월
EXPECT_MAR_W3_AVG = {'금~일': 396646, '토~월': 372962, '목~일': 394392,
                     '금~월': 380479, '목~월': 372646}
EXPECT_MAR_W4_AVG = {'금~일': 462850, '토~월': 474225, '목~일': 456408,
                     '금~월': 473550, '목~월': 468962}
EXPECT_MAR_W2_OVERALL = (238100, 519900)   # 최저 후쿠오카 3/11~15 목~월 · 최고 싱가포르 3/13~15 토~월
# (원문 '가장 비싼 노선'은 노선별 최저 기준으로 발리 496,600원이고, 칸 하나의 최고가는 싱가포르 519,900원)
# 2027년 3월 2주차 패턴 평균(원문 '한눈에') — 값이 통째로 밀리면 여기서 걸린다
EXPECT_MAR_W2_AVG = {'금~일': 388200, '토~월': 376275, '목~일': 392467, '금~월': 372612, '목~월': 374129}
EXPECT_MAR_W1_ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR',
                        'NKG', 'SGN', 'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX',
                        'DPS', 'KHH', 'RMQ', 'BJS')      # = EXPECT_JAN_ALL 과 같은 24개 노선
# 2027년 4월 1~3주차(4/1~5 · 4/8~12 · 4/15~19) 기존 24개 노선 × 5패턴 120칸씩(2026-11-18 5번 보고서 3건).
# 4월 4주차(4/22~26)는 아직 미수신이라 이 세 주만 검사하고, 24개 노선에는 4주차 값이 없어야 한다.
APR_WEEKS = (
    ('1주차', '2027-04-01', '2027-04-05', (299100, 2133000), 47,
     {'금~월': 524404, '목~일': 531117, '금~일': 534188, '토~월': 538488, '목~월': 578008}),
    ('2주차', '2027-04-08', '2027-04-12', (299100, 864500), 49,
     {'금~월': 486233, '토~월': 490192, '금~일': 491042, '목~월': 499771, '목~일': 500958}),
    ('3주차', '2027-04-15', '2027-04-19', (299000, 923000), 45,
     {'토~월': 490858, '금~월': 492833, '목~월': 493988, '목~일': 497004, '금~일': 506588}),
)
EXPECT_APR_TOTAL = 360
EXPECT_APR_LOW = {('PVG', '2027-04-03', '토~월'): 299100,
                  ('PVG', '2027-04-10', '토~월'): 299100,
                  ('PVG', '2027-04-17', '토~월'): 299000}
EXPECT_APR_4W = ('2027-04-22', '2027-04-26')   # 미수신 — 24개 노선에 값이 있으면 실패
# 완본이 도착한 8노선 — 9주(목요일 기준) × 5패턴 45칸씩, 값 333 + 판매편 0건 27 = 360칸
EXPECT_FULL_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN', 'YNJ', 'DYG', 'KWL', 'TXN')
EXPECT_FULL_WEEKS = ('2026-12-03', '2026-12-10', '2026-12-17', '2026-12-24', '2026-12-31',
                     '2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
# 2026-11-18 추가 — 연길·장가계·구이린·황산 2027년 2~6월 금~일(2박) 21주 실측 주(금요일)
EXPECT_26M_WEEKS = ('2027-02-05', '2027-02-12', '2027-02-19', '2027-02-26',
                    '2027-03-05', '2027-03-12', '2027-03-19', '2027-03-26',
                    '2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23', '2027-04-30',
                    '2027-05-07', '2027-05-14', '2027-05-21', '2027-05-28',
                    '2027-06-04', '2027-06-11', '2027-06-18', '2027-06-25')
# 노선별로 채워진 금~일 칸 수(값) — 21주 전수, 황산은 4/2~6/25 13주가 판매편 0건
EXPECT_26M = {'YNJ': 21, 'DYG': 21, 'KWL': 21, 'TXN': 8}
# 노선별 금~일 실측 출발일(값) — 날짜가 밀리거나 바뀌면 여기서 걸린다
_W26M = EXPECT_26M_WEEKS
EXPECT_26M_DATES = {'YNJ': set(_W26M), 'DYG': set(_W26M), 'KWL': set(_W26M),
                    'TXN': set(_W26M) - {'2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23',
                                          '2027-04-30', '2027-05-07', '2027-05-14', '2027-05-21',
                                          '2027-05-28', '2027-06-04', '2027-06-11', '2027-06-18',
                                          '2027-06-25'}}
# 2026-11-18 추가 — 연길·장가계·구이린·황산 2027년 2~6월 토~월(2박) 실측 출발일(값)
_W26M_SAT = ('2027-02-06', '2027-02-13', '2027-02-20', '2027-02-27',
             '2027-03-06', '2027-03-13', '2027-03-20', '2027-03-27',
             '2027-04-03', '2027-04-10', '2027-04-17', '2027-04-24',
             '2027-05-01', '2027-05-08', '2027-05-15', '2027-05-22', '2027-05-29',
             '2027-06-05', '2027-06-12', '2027-06-19', '2027-06-26')
# 토~월 21주 84칸 완성(2026-11-18 완주본) — 연길·장가계·구이린은 21주 전부 값,
# 황산은 3/27~6/26 14주만 값이고 2/6~3/20 7주는 판매편 0건
EXPECT_26M_SAT = {
    'YNJ': set(_W26M_SAT),
    'DYG': set(_W26M_SAT),
    'KWL': set(_W26M_SAT),
    'TXN': set(_W26M_SAT) - set(_W26M_SAT[:7]),
}
ROUTE_ORDER_26M = ('YNJ', 'DYG', 'KWL', 'TXN')
# 2026-11-18 추가 — 선양·다롄·광저우·샤먼 2027년 2~5월 2박(금~일·토~월) 실측 출발일
_PUS4_FRI = ('2027-02-05', '2027-02-12', '2027-02-19', '2027-02-26',
             '2027-03-05', '2027-03-12', '2027-03-19', '2027-03-26',
             '2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23', '2027-04-30',
             '2027-05-07', '2027-05-14', '2027-05-21', '2027-05-28',
             '2027-06-04', '2027-06-11', '2027-06-18', '2027-06-25')
_PUS4_SAT = ('2027-02-06', '2027-02-13', '2027-02-20', '2027-02-27',
             '2027-03-06', '2027-03-13', '2027-03-20', '2027-03-27',
             '2027-04-03', '2027-04-10', '2027-04-17', '2027-04-24',
             '2027-05-01', '2027-05-08', '2027-05-15', '2027-05-22', '2027-05-29',
             '2027-06-05', '2027-06-12', '2027-06-19', '2027-06-26')
_PUS4_THU = ('2027-02-04', '2027-02-11', '2027-02-18', '2027-02-25',
             '2027-03-04', '2027-03-11', '2027-03-18', '2027-03-25',
             '2027-04-01', '2027-04-08', '2027-04-15', '2027-04-22', '2027-04-29',
             '2027-05-06', '2027-05-13', '2027-05-20', '2027-05-27',
             '2027-06-03', '2027-06-10', '2027-06-17', '2027-06-24')
# 2026-11-18 완주본 — 4노선 × 21주 2박 168칸(금~일·토~월, 100%) + 목~일(3박) 84칸 + 금~월(3박) 84칸 100%.
# 목~월(4박)은 G1 갱신본에서 2/4~4/22 12주 48칸(4/29 이후 9주는 미조회).
_PUS4_4N = _PUS4_THU      # 2026-11-18 G1 완결본으로 목~월 4박도 21주 전부 실측(420/420칸)
EXPECT_PUS4_2N = {
    'SHE': {'목~일': set(_PUS4_THU), '금~일': set(_PUS4_FRI), '토~월': set(_PUS4_SAT),
            '금~월': set(_PUS4_FRI), '목~월': set(_PUS4_4N)},
    'DLC': {'목~일': set(_PUS4_THU), '금~일': set(_PUS4_FRI), '토~월': set(_PUS4_SAT),
            '금~월': set(_PUS4_FRI), '목~월': set(_PUS4_4N)},
    'CAN': {'목~일': set(_PUS4_THU), '금~일': set(_PUS4_FRI), '토~월': set(_PUS4_SAT),
            '금~월': set(_PUS4_FRI), '목~월': set(_PUS4_4N)},
    'XMN': {'목~일': set(_PUS4_THU), '금~일': set(_PUS4_FRI), '토~월': set(_PUS4_SAT),
            '금~월': set(_PUS4_FRI), '목~월': set(_PUS4_4N)},
}
# 2026-11-18 동남아 4노선 2027년 2~6월 21주 × 5패턴 420칸 완본 — 월별 칸 수
EXPECT_SEA_26M_BY_MONTH = {'2027-02': 80, '2027-03': 80, '2027-04': 96,
                           '2027-05': 84, '2027-06': 80}
# 2026-11-18 연길·장가계·구이린·황산 2027년 2~6월 목~일(3박) 21주 84칸 완주 — 4노선 모두 값
EXPECT_26M_THU = {code: set(_PUS4_THU) for code in ('YNJ', 'DYG', 'KWL', 'TXN')}
EXPECT_MONTHS = ('2026-12', '2027-01', '2027-02', '2027-03', '2027-04', '2027-05',
                 '2027-06', '2027-07', '2027-08', '2027-09', '2027-10', '2027-11')
EXPECT_FIRST_WEEK, EXPECT_LAST_WEEK = '2026-12-03', '2027-11-25'
# 2026.12~2027.02 고정 기준(1,638건 + 중국 신규 8노선 177건 + 중국 4노선 완본 162칸 + 2027년 2~6월 2박 287칸)
# 2027-02~05는 2026-11-18 선양·다롄·광저우·샤먼 2박 131칸 + 연길·장가계·구이린·황산 토~월 28칸을 더한 값
# 2027-02는 2026-11-18 2월 1주차(설 연휴 2/4~8) 5패턴 86칸을 더한 값(457 + 86 = 543)
# 2027-02~05는 2026-11-18 2박·목~일·금~월 완주본까지 더한 값(2월 591 · 3월 229 · 4월 127 · 5월 116)
# 2026-12·2027-01·2027-03은 2026-11-18 필리핀 4노선 180칸 + 일본 7노선 90칸 + 3월 1주차 120칸
# + 동남아 4노선 178칸을 더한 값(12월 783+88+81+86=1,038 · 1월 797+92+9+92=990 · 3월 77+120=197)
# 2026-11-18 마지막 4건 반영 — 일본 12월 완결 +18(삿포로)·+3(1월), 3월 2주차 +120,
# 동남아 2~6월 420칸(2월 80·3월 80·4월 96·5월 84·6월 80), 중국 G1 목~월 48칸(2~4월 16씩)
# 2026-11-18 마지막 3건 — 필리핀 4노선 2~6월 420칸(2월 80·3월 80·4월 96·5월 84·6월 80)과
# 중국 G2 금~월 84칸(2월 16·3월 16·4월 20·5월 16·6월 16)을 더한 값
# 2026-11-18 마지막 2건 — 중국 G2 목~월 84칸(값 77: 2월 12·3월 13·4월 20·5월 16·6월 16)과
# 3월 3·4주차 240칸을 더한 값(2월 779→791 · 3월 538→791 · 4월 357→377 · 5월 316→332)
EXPECT_OLD_BY_MONTH = {'2026-12': 1111, '2027-01': 1161, '2027-02': 921,
                       '2027-03': 926, '2027-04': 821, '2027-05': 423}
# 2026-12·2027-01은 2026-11-18 일본 보완본(12월 +51칸·당일치기 4칸 · 1월 +9칸)과 중국 3박 완주본을 더한 값
# 2027.06~11 반영분(3개 원본: 260 + 73 + 53 = 386건)
# 2027-06은 2026-11-18 동남아 4노선 2~6월 420칸 가운데 6월 80칸을 더한 값(239+80)
# 2027-06은 필리핀 6월 80칸 + G2 금~월 6월 16칸을 더한 값(319 + 96)
# 2027-07~10은 2026-11-18 중국 8개 노선 2027년 7~11월 측정 465칸(7월 152 · 8월 127 · 9월 135 · 10월 51)
# 2027-07~09는 2026-11-18 필리핀 4개 노선 7~11월 실측(7월 64 · 8월 40 · 9월 22)을 더한 값
EXPECT_H2_BY_MONTH = {'2027-06': 530, '2027-07': 445, '2027-08': 294,
                      '2027-09': 232, '2027-10': 94, '2027-11': 1}
EXPECT_H2 = {'weekend': 1501, 'day': 95, 'total': 1596}   # 주말형 1,425+76 · 당일치기 88+7(일본 7노선 2027년 6월)
EXPECT_NOSALE = {('FUK', '2027-11-12'), ('TYO', '2027-11-12'),
                 ('TYO', '2027-11-16'), ('FUK', '2027-11-20'),
                 ('KWL', '2026-12-05'), ('TXN', '2026-12-05'),   # 중국 2건: 같은 날 복편 0편
                 ('TAK', '2027-01-30'), ('FSZ', '2027-01-15')}   # 일본 1월: 가격표에도 항공편 없음
# 2026-11-18 황산 완본 — 토~월·금~월·목~월 9주 27칸은 조회 결과 판매편 0건(가격 아님)
EXPECT_NOSALE_TXN = {('TXN', d) for d in (
    '2026-12-05', '2026-12-04', '2026-12-03', '2026-12-12', '2026-12-11', '2026-12-10',
    '2026-12-19', '2026-12-18', '2026-12-17', '2026-12-26', '2026-12-25', '2026-12-24',
    '2027-01-02', '2027-01-01', '2026-12-31', '2027-01-09', '2027-01-08', '2027-01-07',
    '2027-01-16', '2027-01-15', '2027-01-14', '2027-01-23', '2027-01-22', '2027-01-21',
    '2027-01-30', '2027-01-29', '2027-01-28')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN
# 2026-11-18 황산 2027년 4/2~6/25 금~일 13주 연속 판매편 0건(값 아님)
EXPECT_NOSALE_TXN_26M = {('TXN', d) for d in (
    '2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23',
    '2027-04-30', '2027-05-07', '2027-05-14', '2027-05-21', '2027-05-28',
    '2027-06-04', '2027-06-11', '2027-06-18', '2027-06-25')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M
# 2026-11-18 황산 2027년 2/6~3/20 토~월 7주 판매편 0건(값 아님, 3/27~6/26 14주는 정상 판매)
EXPECT_NOSALE_TXN_26M_SAT = {('TXN', d) for d in (
    '2027-02-06', '2027-02-13', '2027-02-20', '2027-02-27', '2027-03-06', '2027-03-13',
    '2027-03-20')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M_SAT
# 2026-11-18 중국 G2 4노선 2027년 2~6월 금~월(3박) — 황산은 2/5·2/12·2/19·2/26·3/5·3/12·3/19·4/2·4/30
# 9칸이 판매편 0건(2회 재조회 확인)이고 나머지 12칸은 값이다. 연길·장가계·구이린은 21칸 모두 값.
EXPECT_NOSALE_TXN_26M_FRIMON = {('TXN', d) for d in (
    '2027-02-05', '2027-02-12', '2027-02-19', '2027-02-26',
    '2027-03-05', '2027-03-12', '2027-03-19', '2027-04-02', '2027-04-30')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M_FRIMON
# 2026-11-18 G2 완결본 — 황산 목~월(4박) 2/4~3/18 7주가 판매편 0건(3/25부터 값).
EXPECT_NOSALE_TXN_26M_THUMON = {('TXN', d) for d in (
    '2027-02-04', '2027-02-11', '2027-02-18', '2027-02-25',
    '2027-03-04', '2027-03-11', '2027-03-18')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M_THUMON
EXPECT_BOOKING_END = '2027-11-14'
EXPECT_BOOKING_SEA4 = '2027-09-14'      # 동남아 4노선(푸꾸옥·코타키나발루·쿠알라룸푸르·비엔티안) 판매창
EXPECT_BOOKING_PH4 = '2027-10-14'       # 필리핀 4노선(세부·마닐라·보홀·클락) 판매창
EXPECT_JAN_WEEKS = ('2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
# 1월 4주 × 5패턴 전수 노선 — 기존 24개 노선(중국 신규 8노선은 연길만 전수, 나머지는 부분 조사)
EXPECT_JAN_ALL = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
                  'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
# 2026-11-18 2월 1주차(설 연휴 2/4~8) — 기존 24개 노선 × 5패턴 120칸 완결(목 2/4 · 금 2/5 · 토 2/6 출발)
EXPECT_FEB_W1_START = '2027-02-04'
EXPECT_FEB_W1_ROUTES = EXPECT_JAN_ALL
EXPECT_WEEKEND = ('목~일', '금~일', '토~월', '목~월', '금~월')
EXPECT_DAY = ('목~목', '금~금', '토~토', '일~일', '월~월')
EXPECT_DAYTRIP_MIN = 310
FL_WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}

# ── 2026-11-18 중국 8개 노선 2027년 7~11월 (15주말 × 7패턴) ────────────────────────
# `noSale` 은 세 가지를 `status` 로 구분한다 — nosale(조회 결과 판매편 없음) ·
# nofare(운항편은 표시되나 요금 미게시) · unopened(예약창 밖, 항공사 스케줄 미개시).
H2_WEEKENDS = ('2027-07-02', '2027-07-09', '2027-07-16', '2027-07-23', '2027-07-30',
               '2027-08-06', '2027-08-13', '2027-08-20', '2027-08-27',
               '2027-09-03', '2027-09-10', '2027-09-17', '2027-09-24',
               '2027-10-01', '2027-10-08')
H2_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN', 'YNJ', 'DYG', 'KWL', 'TXN')
# 원문 '노선별 특징' 의 요금 미공개·0건 칸 수(패턴)
H2_NOFARE_PATS = {'SHE': ('토~토', '일~일'), 'CAN': ('토~토',), 'XMN': ('토~토', '일~일'),
                  'DYG': ('금~일', '토~월', '금~월', '목~월'), 'KWL': tuple(EXPECT_WEEKEND),
                  'TXN': ('목~일', '토~월', '목~월')}
H2_NOSALE_PATS = {'DYG': ('토~토', '일~일'), 'KWL': ('토~토', '일~일'),
                  'TXN': ('토~토', '일~일', '금~일', '금~월')}
H2_PROBE_DATES = ('2027-10-15', '2027-11-12')     # 예약창(2027-10-13) 밖 확인용 금~일 조회
EXPECT_NOFARE_TOTAL = sum(len(v) * len(H2_WEEKENDS) for v in H2_NOFARE_PATS.values())
EXPECT_UNOPENED_CHINA = len(H2_ROUTES) * len(H2_PROBE_DATES)

# ── 2026-11-18 동남아 4개 노선 2027년 7~11월 (22주 × 5패턴 = 440칸) ─────────────
# 4노선 모두 마지막 판매일이 2027-09-14라 07-01~09-09 주 11주 220칸만 실측값이고,
# 09-16~11-25 주 11주 220칸은 미오픈(unopened)이다.
SEA4 = ('PQC', 'BKI', 'KUL', 'VTE')
SEA_H2_WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
                     for i in range(22))
SEA_H2_MEASURED = SEA_H2_WEEKS[:11]
SEA_H2_UNOPENED = SEA_H2_WEEKS[11:]
# 노선 → (실측 칸, 최저, 최고, 평균) — 원문 표와 절 머리 요약
EXPECT_SEA_H2 = {'PQC': (55, 423616, 780500, 624246), 'BKI': (55, 425000, 851200, 712273),
                 'KUL': (55, 411136, 436617, 421792), 'VTE': (55, 417896, 1365374, 608394)}
EXPECT_UNOPENED_SEA = len(SEA4) * len(SEA_H2_UNOPENED) * len(EXPECT_WEEKEND)

# ── 2026-11-18 필리핀 4개 노선 2027년 7~11월 (22주 × 5패턴 = 440칸) ──────────────
# 예약창 상한이 2027-10-14라 16주차(10/14 목 시작)~22주차 7주 140칸은 미오픈이고,
# 실측은 126칸(마닐라 57 · 클락 55 · 세부 12 · 보홀 2), 나머지 174칸은 미조회(—)다.
PH4_LAST_SALE = '2027-10-14'
PH4_H2_WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
                     for i in range(22))
# 노선 → (실측 칸, 최저, 최고, 최저가가 직항인 칸 수)
EXPECT_PH4_H2 = {'CEB': (12, 453652, 803600, 0), 'MNL': (57, 406456, 766600, 2),
                 'TAG': (2, 553300, 565669, 0), 'CRK': (55, 409800, 765300, 0)}
EXPECT_PH4_H2_MISSING = {'CEB': 63, 'MNL': 18, 'TAG': 73, 'CRK': 20}   # 미조회 174칸
EXPECT_PH4_H2_LOW = {('MNL', '2027-08-06', '금~일'): 406456,
                     ('CEB', '2027-07-01', '목~월'): 453652,
                     ('TAG', '2027-07-02', '금~일'): 553300,
                     ('CRK', '2027-09-03', '금~월'): 409800}
EXPECT_UNOPENED_PH4 = len(EXPECT_PH4) * len([w for w in PH4_H2_WEEKS if w >= PH4_LAST_SALE]) \
    * len(EXPECT_WEEKEND)
EXPECT_UNOPENED_TOTAL = EXPECT_UNOPENED_CHINA + EXPECT_UNOPENED_SEA + EXPECT_UNOPENED_PH4


def _h2_keys(pats_by_route):
    out = set()
    for code, pats in pats_by_route.items():
        for pat in pats:
            for fri in H2_WEEKENDS:
                thu = datetime.date.fromisoformat(fri) - datetime.timedelta(days=1)
                d = thu + datetime.timedelta(days=(FL_WD[pat[0]] - FL_WD['목']) % 7)
                out.add((code, d.isoformat(), pat))
    return out


EXPECT_NOSALE_H2 = _h2_keys(H2_NOSALE_PATS)
EXPECT_NOSALE_ALL = {(c, d) for (c, d) in EXPECT_NOSALE} | {
    (c, d) for (c, d, _p) in EXPECT_NOSALE_H2}
# 2026-11-18 중국 G2 4노선 2027년 2~6월 금~월(3박) 21주 — 21 금요일
_G2_FRIMON = tuple((datetime.date(2027, 2, 5) + datetime.timedelta(days=7 * i)).isoformat()
                   for i in range(21))


def _fl_nights(label):
    m = re.match(r'^([월화수목금토일])~([월화수목금토일])$', str(label))
    if not m:
        return None
    return (FL_WD[m.group(2)] - FL_WD[m.group(1)]) % 7


def check_flights(flights):
    """④ 항공 데이터 검사 — 노선 수·패턴·12개월 창·주차 연속성·1월 전수·당일치기·가격 유효성."""
    import datetime
    problems = []
    routes = flights.get('routes') or []
    if len(routes) != EXPECT_FLIGHTS:
        problems.append('항공 노선 %d개 (기대 %d개)' % (len(routes), EXPECT_FLIGHTS))
    pats = {p['label']: p for p in flights.get('patterns') or []}
    for label in EXPECT_WEEKEND:
        p = pats.get(label)
        if not p or not p.get('nights'):
            problems.append('주말형 패턴 %s 없음/박수 0' % label)
    for label in EXPECT_DAY:
        p = pats.get(label)
        if not p:
            problems.append('당일치기 패턴 %s 없음' % label)
        elif p.get('nights') != 0:
            problems.append('당일치기 패턴 %s 박수 %s (0이어야 함)' % (label, p.get('nights')))

    # 월·월 이동이 2026-12 ~ 2027-11 1년을 덮는지
    months = flights.get('months') or []
    if tuple(months) != EXPECT_MONTHS:
        problems.append('months %s (기대 2026-12~2027-11 12개)' % (months,))
    weeks = flights.get('weeks') or []
    if not weeks:
        problems.append('weeks 없음')
    else:
        if weeks[0].get('thu') != EXPECT_FIRST_WEEK or weeks[-1].get('thu') != EXPECT_LAST_WEEK:
            problems.append('weeks 범위 %s ~ %s (기대 %s ~ %s)' % (
                weeks[0].get('thu'), weeks[-1].get('thu'), EXPECT_FIRST_WEEK, EXPECT_LAST_WEEK))
        prev = None
        for w in weeks:
            if w.get('month') not in EXPECT_MONTHS:
                problems.append('week %s 의 month %s 이상' % (w.get('thu'), w.get('month')))
            if w.get('end') != (datetime.date.fromisoformat(w['thu']) +
                                datetime.timedelta(days=6)).isoformat():
                problems.append('week %s span 끝 %s 이상' % (w.get('thu'), w.get('end')))
            if prev is not None and (datetime.date.fromisoformat(w['thu']) -
                                     datetime.date.fromisoformat(prev)).days != 7:
                problems.append('week %s 가 이전 주 %s 와 7일 간격이 아님' % (w['thu'], prev))
            prev = w['thu']

    by_month = {}
    day_total = 0
    h2 = {'weekend': 0, 'day': 0}
    deal_keys = set()
    for r in routes:
        keys = {(d['date'], d['pattern']) for d in r['deals']}
        if len(keys) != len(r['deals']):
            problems.append('%s (노선·출발일·패턴) 중복' % r['code'])
        for thu in EXPECT_JAN_WEEKS:
            if r['code'] not in EXPECT_JAN_ALL:
                continue
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt, label) not in keys:
                    problems.append('1월 미실측 %s %s %s' % (r['code'], dt, label))
        if r['code'] in EXPECT_FEB_W1_ROUTES:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(EXPECT_FEB_W1_START) +
                      datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt, label) not in keys:
                    problems.append('2월 1주차 미실측 %s %s %s' % (r['code'], dt, label))
        if r['code'] in EXPECT_MAR_W1_ROUTES:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(EXPECT_MAR_W1_START) +
                      datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt, label) not in keys:
                    problems.append('3월 1주차 미실측 %s %s %s' % (r['code'], dt, label))
                dt2 = (datetime.date.fromisoformat(EXPECT_MAR_W2_START) +
                       datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt2, label) not in keys:
                    problems.append('3월 2주차 미실측 %s %s %s' % (r['code'], dt2, label))
                dt3 = (datetime.date.fromisoformat(EXPECT_MAR_W3_START) +
                       datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt3, label) not in keys:
                    problems.append('3월 3주차 미실측 %s %s %s' % (r['code'], dt3, label))
                dt4 = (datetime.date.fromisoformat(EXPECT_MAR_W4_START) +
                       datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt4, label) not in keys:
                    problems.append('3월 4주차 미실측 %s %s %s' % (r['code'], dt4, label))
        for d in r['deals']:
            tag = '%s %s %s' % (r['code'], d.get('date'), d.get('pattern'))
            if not (WINDOW_START <= d['date'] <= WINDOW_END):
                problems.append('%s 날짜 창 밖' % tag)
                break
            n = _fl_nights(d['pattern'])
            if n is None:
                problems.append('%s 패턴 형식 이상' % tag)
                break
            if not isinstance(d.get('price'), int) or d['price'] <= 0:
                problems.append('%s 가격이 양의 정수가 아님(추정·0원 금지): %r' % (tag, d.get('price')))
                break
            if d.get('back') != (datetime.date.fromisoformat(d['date']) +
                                 datetime.timedelta(days=n)).isoformat():
                problems.append('%s 귀국일 %s 가 %d박과 맞지 않음' % (tag, d.get('back'), n))
                break
            by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
            deal_keys.add((r['code'], d['date'], d['pattern']))
            if d['date'] >= '2027-06-01':
                h2['day' if n == 0 else 'weekend'] += 1
            if n == 0:
                day_total += 1
        meta = r.get('daytrip')
        if not meta or meta.get('status') not in ('ok', 'short', 'no', 'unk'):
            problems.append('%s daytrip 메타 없음/이상' % r['code'])
    if day_total < EXPECT_DAYTRIP_MIN:
        problems.append('당일치기 %d건 (기대 %d건 이상)' % (day_total, EXPECT_DAYTRIP_MIN))

    # 중국 신규 8노선: 노선 이름·건수가 원본 보고서와 같은지(조용한 누락·중복 방지)
    new_routes = {c: (city, n) for c, (city, n) in EXPECT_NEW_ROUTES.items()}
    by_code = {r['code']: r for r in routes}
    for code, (city, n) in new_routes.items():
        r = by_code.get(code)
        if not r:
            problems.append('중국 신규 노선 %s 없음' % code)
            continue
        if r.get('city') != city:
            problems.append('노선 %s 도시 이름 %r (기대 %s)' % (code, r.get('city'), city))
        if len(r['deals']) != n:
            problems.append('노선 %s 딜 %d건 (기대 %d건)' % (code, len(r['deals']), n))

    # 2026-11-18 신규 11노선(필리핀 4 · 일본 7) — 도시 이름·건수가 원본 보고서와 같은지
    for code, (city, n) in EXPECT_NEW_ROUTES2.items():
        r = by_code.get(code)
        if not r:
            problems.append('신규 노선 %s 없음' % code)
            continue
        if r.get('city') != city:
            problems.append('신규 노선 %s 도시 이름 %r (기대 %s)' % (code, r.get('city'), city))
        if len(r['deals']) != n:
            problems.append('신규 노선 %s 딜 %d건 (기대 %d건)' % (code, len(r['deals']), n))

    # 필리핀 4노선 완본 — 9주 × 5패턴 45칸이 값으로 채워졌는지(180/180, 0건 없음)
    for code in EXPECT_PH4:
        r = by_code.get(code)
        if not r:
            continue
        keys = {(d['date'], d['pattern']) for d in r['deals']}
        for thu in EXPECT_FULL_WEEKS:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                if (dt, label) not in keys:
                    problems.append('필리핀 완본 미채움 %s %s %s' % (code, dt, label))

    # 동남아 4노선 — 9주 × 5패턴 가운데 비엔티안 2칸만 빈칸(나머지는 값)
    for code in EXPECT_SEA4:
        r = by_code.get(code)
        if not r:
            continue
        keys = {(d['date'], d['pattern']) for d in r['deals']}
        for thu in EXPECT_FULL_WEEKS:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                if (code, dt, label) in EXPECT_SEA4_MISSING:
                    if (dt, label) in keys:
                        problems.append('동남아 빈칸이어야 할 칸에 값이 있음 %s %s %s'
                                        % (code, dt, label))
                    continue
                if (dt, label) not in keys:
                    problems.append('동남아 완본 미채움 %s %s %s' % (code, dt, label))

    # 중국 4노선 완본 — 9주 × 5패턴 45칸이 모두 '값' 또는 '판매편 0건'으로 채워졌는지(180/180)
    no_sale_keys = {(n.get('code'), n.get('date'), n.get('pattern')) for n in (flights.get('noSale') or [])}
    for code in EXPECT_FULL_ROUTES:
        r = by_code.get(code)
        if not r:
            continue
        keys = {(d['date'], d['pattern']) for d in r['deals']}
        for thu in EXPECT_FULL_WEEKS:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                if (dt, label) not in keys and (code, dt, label) not in no_sale_keys:
                    problems.append('중국 완본 미채움 %s %s %s' % (code, dt, label))
        cells = sum(1 for thu in EXPECT_FULL_WEEKS for label in EXPECT_WEEKEND
                    if (code, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat(), label)
                    in no_sale_keys)
        if code == 'TXN' and cells != 27:
            problems.append('황산 판매편 0건 %d칸 (기대 27칸)' % cells)
        if code != 'TXN' and cells:
            problems.append('%s 판매편 0건 %d칸 (기대 0칸)' % (code, cells))
    # 2027년 3월 2주차 — 24노선 × 5패턴 120칸의 최저·최고와 패턴 평균
    mar2 = [d for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES for d in r['deals']
            if '2027-03-11' <= d['date'] <= '2027-03-13']
    if len(mar2) != 120:
        problems.append('3월 2주차 %d칸 (기대 120칸)' % len(mar2))
    else:
        prices = [d['price'] for d in mar2]
        if (min(prices), max(prices)) != EXPECT_MAR_W2_OVERALL:
            problems.append('3월 2주차 최저·최고 %s (기대 %s)'
                            % ((min(prices), max(prices)), EXPECT_MAR_W2_OVERALL))
        for label, want in EXPECT_MAR_W2_AVG.items():
            ps = [d['price'] for d in mar2 if d['pattern'] == label]
            if round(sum(ps) / len(ps)) != want:
                problems.append('3월 2주차 %s 평균 %d (기대 %d)'
                                % (label, round(sum(ps) / len(ps)), want))
    # 2027년 3월 3·4주차 — 120칸씩, 최저·최고와 패턴 평균
    for label_w, start, end, overall, avg in (
            ('3주차', EXPECT_MAR_W3_START, '2027-03-22', EXPECT_MAR_W3_OVERALL, EXPECT_MAR_W3_AVG),
            ('4주차', EXPECT_MAR_W4_START, '2027-03-29', EXPECT_MAR_W4_OVERALL, EXPECT_MAR_W4_AVG)):
        rows = [d for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES for d in r['deals']
                if start <= d['date'] <= end]
        if len(rows) != 120:
            problems.append('3월 %s %d칸 (기대 120칸)' % (label_w, len(rows)))
            continue
        prices = [d['price'] for d in rows]
        if (min(prices), max(prices)) != overall:
            problems.append('3월 %s 최저·최고 %s (기대 %s)'
                            % (label_w, (min(prices), max(prices)), overall))
        for pat, want in avg.items():
            ps = [d['price'] for d in rows if d['pattern'] == pat]
            if round(sum(ps) / len(ps)) != want:
                problems.append('3월 %s %s 평균 %d (기대 %d)'
                                % (label_w, pat, round(sum(ps) / len(ps)), want))
    # 동남아 4노선 2027년 2~6월 420칸 — 월별 칸 수
    for m, want in EXPECT_SEA_26M_BY_MONTH.items():
        got = sum(1 for r in routes if r['code'] in EXPECT_SEA4 for d in r['deals']
                  if d['date'][:7] == m and '2027-02-01' <= d['date'] <= '2027-06-30')
        if got != want:
            problems.append('동남아 %s 2027년 2~6월 %d칸 (기대 %d칸)' % (m, got, want))
    # 2027년 4월 1~3주차 — 120칸씩(노선 24 × 5패턴). 최저·최고·직항 칸 수·패턴 평균이 원문과 같은지
    apr_cells = 0
    for label_w, start, end, overall, direct_want, avg in APR_WEEKS:
        rows = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
                for d in r['deals'] if start <= d['date'] <= end and d['pattern'] in EXPECT_WEEKEND]
        if len(rows) != 120:
            problems.append('4월 %s %d칸 (기대 120칸)' % (label_w, len(rows)))
            continue
        apr_cells += len(rows)
        prices = [d['price'] for d in rows]
        if (min(prices), max(prices)) != overall:
            problems.append('4월 %s 최저·최고 %s (기대 %s)'
                            % (label_w, (min(prices), max(prices)), overall))
        direct = sum(1 for d in rows if d.get('via') is False)
        if direct != direct_want:
            problems.append('4월 %s 직항 %d칸 (기대 %d칸)' % (label_w, direct, direct_want))
        for pat, want in avg.items():
            ps = [d['price'] for d in rows if d['pattern'] == pat]
            if len(ps) != 24:
                problems.append('4월 %s %s %d칸 (기대 24칸)' % (label_w, pat, len(ps)))
            elif round(sum(ps) / len(ps)) != want:
                problems.append('4월 %s %s 평균 %d (기대 %d)'
                                % (label_w, pat, round(sum(ps) / len(ps)), want))
    if apr_cells != EXPECT_APR_TOTAL:
        problems.append('4월 1~3주차 %d칸 (기대 %d칸)' % (apr_cells, EXPECT_APR_TOTAL))
    for (code, date, pat), price in EXPECT_APR_LOW.items():
        r = by_code.get(code)
        got = next((d['price'] for d in (r['deals'] if r else [])
                    if d['date'] == date and d['pattern'] == pat), None)
        if got != price:
            problems.append('4월 주차 최저 %s %s %s %s (기대 %d)'
                            % (code, date, pat, got, price))
    stray = [d for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES for d in r['deals']
             if EXPECT_APR_4W[0] <= d['date'] <= EXPECT_APR_4W[1]]
    if stray:
        problems.append('4월 4주차(미수신)인데 24개 노선에 값이 있습니다: %s'
                        % [(d['date'], d['pattern']) for d in stray[:4]])
    for m, n in EXPECT_OLD_BY_MONTH.items():
        if by_month.get(m) != n:
            problems.append('%s 기존 건 %s (기대 %d — 손실/변형)' % (m, by_month.get(m), n))

    # 2027년 2~6월 금~일 실측 — 노선별 출발일 집합과 0건 칸이 원본과 같은지
    for code, dates in EXPECT_26M_DATES.items():
        r = by_code.get(code)
        if not r:
            continue
        got = {d['date'] for d in r['deals']
               if d['pattern'] == '금~일' and '2027-02-01' <= d['date'] <= '2027-06-30'}
        if got != dates:
            problems.append('%s 2027년 2~6월 금~일 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(dates), sorted(got ^ dates)[:6]))
        if EXPECT_26M.get(code) is not None and len(got) != EXPECT_26M[code]:
            problems.append('%s 2027년 2~6월 금~일 %d칸 (기대 %d칸)' % (code, len(got), EXPECT_26M[code]))
    ns_dates = {x['date'] for x in (flights.get('noSale') or []) if x.get('code') == 'TXN'
                and '2027-04-01' <= x.get('date', '') <= '2027-06-30'}
    if ns_dates != {d for (_, d) in EXPECT_NOSALE_TXN_26M}:
        problems.append('황산 2027년 4~6월 금~일 판매편 0건 %d칸 (기대 13칸): %s'
                        % (len(ns_dates), sorted(ns_dates)))
    got_sat = {(r['code'], d['date'], d['pattern']) for r in routes
               if r['code'] in ROUTE_ORDER_26M for d in r['deals']
               if '2027-02-01' <= d['date'] <= '2027-06-30'
               and d['pattern'] not in EXPECT_WEEKEND}
    if got_sat:
        problems.append('4노선 2027년 2~6월에 주말형 5패턴 밖 패턴이 있습니다: %s'
                        % sorted(got_sat)[:6])
    # 2026-11-18 G2 완결본 — 4노선 × 21주 × 5패턴 420칸(값 384 + 판매편 0건 36)이 다 찼는지.
    # 목~월(4박)은 이번에 채운 축으로, 황산 7주만 0건이다.
    for code in ROUTE_ORDER_26M:
        r = by_code.get(code)
        if not r:
            continue
        filled = {(d['date'], d['pattern']) for d in r['deals']}
        filled |= {(n.get('date'), n.get('pattern')) for n in (flights.get('noSale') or [])
                   if n.get('code') == code and '2027-02-01' <= n.get('date', '') <= '2027-06-30'}
        missing = []
        for thu in _PUS4_THU:
            for pat in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[pat[0]] - FL_WD['목']) % 7)).isoformat()
                if (dt, pat) not in filled:
                    missing.append('%s %s' % (dt, pat))
        if missing:
            problems.append('G2 %s 2027년 2~6월 빈칸 %d개: %s'
                            % (code, len(missing), missing[:4]))
        ps = [d['price'] for d in r['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30']
        want = EXPECT_G2_FULL[code]
        if len(ps) != want[0]:
            problems.append('G2 %s 2027년 2~6월 값 %d칸 (기대 %d칸)' % (code, len(ps), want[0]))
        elif (min(ps), max(ps)) != want[1:]:
            problems.append('G2 %s 2027년 2~6월 최저·최고 %s (기대 %s)'
                            % (code, (min(ps), max(ps)), want[1:]))
    # 2026-11-18 G2 — 2027년 2~6월 금~월(3박) 21주. 연길·장가계·구이린은 21칸 값,
    # 황산은 9칸이 판매편 0건이고 나머지 12칸이 값이다.
    for code in ROUTE_ORDER_26M:
        r = by_code.get(code)
        if not r:
            continue
        got = {d['date'] for d in r['deals']
               if d['pattern'] == '금~월' and '2027-02-01' <= d['date'] <= '2027-06-30'}
        want = set(_G2_FRIMON)
        if code == 'TXN':
            want -= {d for (c, d) in EXPECT_NOSALE_TXN_26M_FRIMON}
        if got != want:
            problems.append('%s 2027년 2~6월 금~월 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(want), sorted(got ^ want)[:6]))
    # 2027년 2~6월 목~일(3박) 84칸 완주 — 4노선 × 21주 전부 값(0건 없음)
    for code, dates in EXPECT_26M_THU.items():
        r = by_code.get(code)
        if not r:
            continue
        got = {d['date'] for d in r['deals']
               if d['pattern'] == '목~일' and '2027-02-01' <= d['date'] <= '2027-06-30'}
        if got != dates:
            problems.append('%s 2027년 2~6월 목~일 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(dates), sorted(got ^ dates)[:6]))
    # 2027년 2~6월 토~월(2박) — 노선별 실측 출발일 집합과 황산 0건 6주가 원본과 같은지
    for code in ROUTE_ORDER_26M:
        r = by_code.get(code)
        if not r:
            continue
        got = {d['date'] for d in r['deals']
               if d['pattern'] == '토~월' and '2027-02-01' <= d['date'] <= '2027-06-30'}
        want = EXPECT_26M_SAT[code]
        if got != want:
            problems.append('%s 2027년 2~6월 토~월 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(want), sorted(got ^ want)[:6]))
    ns_sat = {(n.get('code'), n.get('date')) for n in (flights.get('noSale') or [])
              if n.get('pattern') == '토~월' and '2027-02-01' <= n.get('date', '') <= '2027-06-30'
              and n.get('code') in ROUTE_ORDER_26M}
    if ns_sat != EXPECT_NOSALE_TXN_26M_SAT:
        problems.append('4노선 2027년 2~6월 토~월 판매편 0건 %d칸 (기대 6칸): %s'
                        % (len(ns_sat), sorted(ns_sat)))
    # 선양·다롄·광저우·샤먼 2027년 2~5월 2박 — 노선·패턴별 출발일 집합
    for code, pats in EXPECT_PUS4_2N.items():
        r = by_code.get(code)
        if not r:
            continue
        for pat, dates in pats.items():
            got = {d['date'] for d in r['deals']
                   if d['pattern'] == pat and '2027-02-01' <= d['date'] <= '2027-06-30'}
            if got != dates:
                problems.append('%s 2027년 2~6월 %s %d칸 (기대 %d칸) 차이: %s'
                                % (code, pat, len(got), len(dates), sorted(got ^ dates)[:6]))
    # 일본 7노선 — 2026년 12월 보완본(150칸)과 당일치기, 2026-11-18 1월 완결본 140칸(값 138 + 항공편 없음 2)까지
    for code in ('CTS', 'FSZ', 'KOJ', 'KMJ', 'MYJ', 'TAK', 'MMY'):
        r = by_code.get(code)
        if not r:
            continue
        dec = [d for d in r['deals'] if d['date'].startswith('2026-12')]
        jan = [d for d in r['deals'] if d['date'].startswith('2027-01')]
        day = [d for d in dec if _fl_nights(d['pattern']) == 0]
        want = EXPECT_JP_DAYTRIP.get(code)
        if want:
            if len(day) != 1 or (day[0]['date'], day[0]['price']) != want:
                problems.append('일본 %s 당일치기 %s (기대 %s)'
                                % (code, [(d['date'], d['price']) for d in day], want))
        elif day:
            problems.append('일본 %s 당일치기 칸이 있음(불가 노선): %s' % (code, day[:2]))
        if len(jan) != EXPECT_JP_JAN[code]:
            problems.append('일본 %s 1월 %d칸 (기대 %d칸 — 12/31 주 3칸 + 1월 완결본)'
                            % (code, len(jan), EXPECT_JP_JAN[code]))
        jan_day = [d for d in jan if _fl_nights(d['pattern']) == 0]
        if len(jan_day) != EXPECT_JP_JAN_DAYTRIP.get(code, 0):
            problems.append('일본 %s 1월 당일치기 %d칸 (기대 %d칸)'
                            % (code, len(jan_day), EXPECT_JP_JAN_DAYTRIP.get(code, 0)))
        # 1월 4주 × 5패턴은 값 또는 '항공편 없음'으로 다 차 있어야 한다(140칸 완결)
        got_keys = {(d['date'], d['pattern']) for d in jan if _fl_nights(d['pattern']) > 0}
        for thu in EXPECT_JAN_WEEKS:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt, label) not in got_keys and (code, dt, label) not in set(EXPECT_JP_JAN_NOFLIGHT):
                    problems.append('일본 1월 미실측 %s %s %s' % (code, dt, label))
    # 중국 G1(선양·다롄·광저우·샤먼) 2027년 2~6월 21주 × 5패턴 420칸(100%) — 노선별 최저·최고
    for code, (lo, hi) in EXPECT_PUS4_FULL.items():
        r = by_code.get(code)
        if not r:
            continue
        ps = [d['price'] for d in r['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30']
        if len(ps) != 105:
            problems.append('G1 %s 2027년 2~6월 %d칸 (기대 105칸)' % (code, len(ps)))
        elif (min(ps), max(ps)) != (lo, hi):
            problems.append('G1 %s 2027년 2~6월 최저·최고 %s (기대 %s)'
                            % (code, (min(ps), max(ps)), (lo, hi)))
    for m, n in EXPECT_H2_BY_MONTH.items():
        if by_month.get(m) != n:
            problems.append('%s 6~11월 건 %s (기대 %d)' % (m, by_month.get(m), n))
    if h2 != {'weekend': EXPECT_H2['weekend'], 'day': EXPECT_H2['day']}:
        problems.append('6~11월 주말/당일 %s (기대 %s)' % (h2, EXPECT_H2))

    c = flights.get('counts') or {}
    if c.get('daytrip') != day_total:
        problems.append('counts.daytrip %s (실제 %d)' % (c.get('daytrip'), day_total))
    if c.get('total') != sum(len(r['deals']) for r in routes):
        problems.append('counts.total %s (실제 %d)' % (c.get('total'), sum(len(r['deals']) for r in routes)))
    if c.get('byMonth') != {k: by_month[k] for k in sorted(by_month)}:
        problems.append('counts.byMonth 불일치: %s vs %s' % (c.get('byMonth'), by_month))

    # 조회했으나 값이 없는 칸(가격 아님) — deals 와 분리 보관.
    # status: nosale(판매편 없음, 기존 기록은 status 없음) · nofare(요금 미게시) · unopened(예약창 밖)
    codes = {r['code'] for r in routes}
    marks = flights.get('noSale') or []
    nosale = [n for n in marks if (n.get('status') or 'nosale') == 'nosale']
    nofare = [n for n in marks if n.get('status') == 'nofare']
    unopened = [n for n in marks if n.get('status') == 'unopened']
    other = [n for n in marks if n.get('status') not in (None, 'nosale', 'nofare', 'unopened')]
    if other:
        problems.append('noSale 의 status 가 이상합니다: %s' % (other[:3],))
    def _jp26_mark(n):
        """일본 7개 노선 2027년 2~6월 칸인가 — 이 구간은 아래 일본 전수 검사에서 따로 본다."""
        return (n.get('code') in JP26 and n.get('pattern') in JP26_PATS
                and '2027-02-01' <= n.get('date', '') <= '2027-06-30')
    got_ns = {(n.get('code'), n.get('date')) for n in nosale if not _jp26_mark(n)}
    if got_ns != EXPECT_NOSALE_ALL:
        problems.append('noSale %d칸 (기대 %d칸) 차이: %s'
                        % (len(got_ns), len(EXPECT_NOSALE_ALL),
                           sorted(got_ns ^ EXPECT_NOSALE_ALL)[:8]))
    got_h2 = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale
              if n.get('date', '') >= '2027-07-01' and n.get('code') in H2_ROUTES}
    if got_h2 != EXPECT_NOSALE_H2:
        problems.append('2027년 7~11월 판매편 0건 %d칸 (기대 %d칸) 차이: %s'
                        % (len(got_h2), len(EXPECT_NOSALE_H2), sorted(got_h2 ^ EXPECT_NOSALE_H2)[:6]))
    got_fr = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale
              if n.get('pattern') == '금~월' and '2027-02-01' <= n.get('date', '') <= '2027-06-30'
              and n.get('code') in ROUTE_ORDER_26M}
    if got_fr != {(c, d, '금~월') for (c, d) in EXPECT_NOSALE_TXN_26M_FRIMON}:
        problems.append('2027년 2~6월 금~월 판매편 0건 %d칸 (기대 %d칸): %s'
                        % (len(got_fr), len(EXPECT_NOSALE_TXN_26M_FRIMON), sorted(got_fr)[:6]))
    for n in marks:
        if n.get('code') not in codes or not (WINDOW_START <= n.get('date', '') <= WINDOW_END):
            problems.append('noSale 이상: %s' % (n,))
        if 'price' in n:
            problems.append('noSale 에 가격이 들어 있음(추정 금지): %s' % (n,))
        key = (n.get('code'), n.get('date'), n.get('pattern'))
        if key in deal_keys:
            problems.append('noSale 가 실측 딜과 겹침: %s' % (key,))
    # 요금 미공개(운항편은 표시되나 요금 미게시) — 2027년 7~11월 255칸 (일본 7노선 2~6월은 아래에서 따로)
    nofare_h2 = [n for n in nofare if not _jp26_mark(n)]
    if len(nofare_h2) != EXPECT_NOFARE_TOTAL:
        problems.append('요금 미공개 %d칸 (기대 %d칸)' % (len(nofare_h2), EXPECT_NOFARE_TOTAL))
    got_nf = {(n.get('code'), n.get('pattern')) for n in nofare_h2}
    want_nf = {(c, p) for c, pats in H2_NOFARE_PATS.items() for p in pats}
    if got_nf != want_nf:
        problems.append('요금 미공개 (노선·패턴) 이상: %s' % sorted(got_nf ^ want_nf))
    if {(n.get('code'), n.get('date'), n.get('pattern')) for n in nofare_h2} != _h2_keys(H2_NOFARE_PATS):
        problems.append('요금 미공개 칸(출발일)이 원문과 다릅니다.')
    # 미오픈(예약창 밖) — 중국 8노선 × 10/15·11/12 금~일 16칸 + 동남아 4노선 09-16 주 이후 11주 220칸
    if len(unopened) != EXPECT_UNOPENED_TOTAL:
        problems.append('미오픈 %d칸 (기대 %d칸)' % (len(unopened), EXPECT_UNOPENED_TOTAL))
    want_up = {(c, d, '금~일') for c in H2_ROUTES for d in H2_PROBE_DATES}
    want_up |= {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for c in SEA4 for thu in SEA_H2_UNOPENED for p in EXPECT_WEEKEND}
    want_up |= {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for c in EXPECT_PH4 for thu in PH4_H2_WEEKS if thu >= PH4_LAST_SALE
                for p in EXPECT_WEEKEND}
    if {(n.get('code'), n.get('date'), n.get('pattern')) for n in unopened} != want_up:
        problems.append('미오픈 칸이 원문(중국 16칸 + 동남아 220칸 + 필리핀 140칸)과 다릅니다.')

    # 일본 7개 노선 2027년 2~6월 — 21주 × 7패턴 1,029칸 전수(값 523 + 0건 303 + 미공개 98 + 빈칸 105)
    jp_grid = {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
               for c in JP26 for thu in JP26_WEEKS for p in JP26_PATS}
    jp_deals = {(r['code'], d['date'], d['pattern'])
                for r in routes if r['code'] in JP26 for d in r['deals']
                if '2027-02-01' <= d['date'] <= '2027-06-30'}
    jp_ns = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale if _jp26_mark(n)}
    jp_nf = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nofare if _jp26_mark(n)}
    jp_blank = jp_grid - jp_deals - jp_ns - jp_nf
    if len(jp_grid) != EXPECT_JP26_CELLS:
        problems.append('일본 7노선 2027년 2~6월 격자 %d칸 (기대 %d칸)'
                        % (len(jp_grid), EXPECT_JP26_CELLS))
    if len(jp_deals) != EXPECT_JP26_DEALS:
        problems.append('일본 7노선 2027년 2~6월 실측 %d칸 (기대 %d칸)'
                        % (len(jp_deals), EXPECT_JP26_DEALS))
    if len(jp_ns) != EXPECT_JP26_NOSALE:
        problems.append('일본 7노선 2027년 2~6월 판매편 0건 %d칸 (기대 %d칸)'
                        % (len(jp_ns), EXPECT_JP26_NOSALE))
    if len(jp_nf) != EXPECT_JP26_NOFARE:
        problems.append('일본 7노선 2027년 2~6월 요금 미공개 %d칸 (기대 %d칸)'
                        % (len(jp_nf), EXPECT_JP26_NOFARE))
    if len(jp_blank) != EXPECT_JP26_BLANK:
        problems.append('일본 7노선 2027년 2~6월 미조회 %d칸 (기대 %d칸)'
                        % (len(jp_blank), EXPECT_JP26_BLANK))
    if jp_deals & (jp_ns | jp_nf) or jp_ns & jp_nf:
        problems.append('일본 7노선 2027년 2~6월 상태가 겹칩니다: %s'
                        % sorted((jp_deals & (jp_ns | jp_nf)) | (jp_ns & jp_nf))[:4])
    for code in JP26:
        for part, pats in (('주말형', JP26_WK), ('당일치기', JP26_DAY)):
            mine = [k for k in jp_grid if k[0] == code and k[2] in pats]
            got = (len([k for k in mine if k in jp_deals]),
                   len([k for k in mine if k in jp_ns]),
                   len([k for k in mine if k in jp_nf]),
                   len([k for k in mine if k in jp_blank]))
            want = EXPECT_JP26_STATUS[code][part]
            if got != want:
                problems.append('일본 %s %s (실측·0건·미공개·미조회) %s (기대 %s)'
                                % (code, part, got, want))
        r = by_code.get(code)
        got_p = [d for d in r['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30']
        n, low, high, direct = EXPECT_JP26[code]
        if len(got_p) != n:
            problems.append('일본 %s 2027년 2~6월 값 %d칸 (기대 %d칸)' % (code, len(got_p), n))
            continue
        vals = [d['price'] for d in got_p]
        if (min(vals), max(vals)) != (low, high):
            problems.append('일본 %s 2027년 2~6월 최저·최고 %s (기대 %s)'
                            % (code, (min(vals), max(vals)), (low, high)))
        if sum(1 for d in got_p if d.get('via') is False) != direct:
            problems.append('일본 %s 2027년 2~6월 직항이 최저가인 칸 %d (기대 %d)'
                            % (code, sum(1 for d in got_p if d.get('via') is False), direct))
    for m, want in EXPECT_JP26_BY_MONTH.items():
        got = sum(1 for c, d, p in jp_deals if d[:7] == m)
        if got != want:
            problems.append('일본 7노선 %s 실측 %d칸 (기대 %d칸)' % (m, got, want))
    if '일본 7개 노선' not in (flights.get('notes', {}).get('2027-02') or ''):
        problems.append('2027-02 notes 에 일본 7개 노선 커버리지가 없습니다.')

    # 필리핀 4노선 2027년 7~11월 — 실측 126칸 + 미오픈 140칸 + 미조회 174칸(빈칸)
    ph4_grid = {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for c in EXPECT_PH4 for thu in PH4_H2_WEEKS for p in EXPECT_WEEKEND}
    ph4_deals = {(r['code'], d['date'], d['pattern']) for r in routes
                 if r['code'] in EXPECT_PH4 for d in r['deals']
                 if '2027-07-01' <= d['date'] <= '2027-11-29'}
    ph4_up = {(c, d, p) for (c, d, p) in want_up if c in EXPECT_PH4}
    if len(ph4_grid) != len(EXPECT_PH4) * len(PH4_H2_WEEKS) * len(EXPECT_WEEKEND):
        problems.append('필리핀 7~11월 격자 %d칸 (440칸이어야 함)' % len(ph4_grid))
    if ph4_deals & ph4_up:
        problems.append('필리핀 7~11월 실측 칸이 미오픈 칸과 겹칩니다: %s'
                        % sorted(ph4_deals & ph4_up)[:4])
    for code, (n, low, high, direct) in EXPECT_PH4_H2.items():
        r = by_code.get(code)
        if not r:
            problems.append('필리핀 노선 %s 없음' % code)
            continue
        got = [d for d in r['deals'] if '2027-07-01' <= d['date'] <= '2027-11-29']
        if len(got) != n:
            problems.append('필리핀 %s 2027년 7~11월 실측 %d칸 (기대 %d칸)'
                            % (code, len(got), n))
            continue
        vals = [d['price'] for d in got]
        if (min(vals), max(vals)) != (low, high):
            problems.append('필리핀 %s 2027년 7~11월 최저·최고 %s (기대 %s)'
                            % (code, (min(vals), max(vals)), (low, high)))
        if sum(1 for d in got if d.get('via') is False) != direct:
            problems.append('필리핀 %s 2027년 7~11월 직항이 최저가인 칸 %d (기대 %d)'
                            % (code, sum(1 for d in got if d.get('via') is False), direct))
        missing = {k for k in ph4_grid if k[0] == code} - ph4_deals - ph4_up
        if len(missing) != EXPECT_PH4_H2_MISSING[code]:
            problems.append('필리핀 %s 2027년 7~11월 미조회 %d칸 (기대 %d칸)'
                            % (code, len(missing), EXPECT_PH4_H2_MISSING[code]))
    for key, price in EXPECT_PH4_H2_LOW.items():
        r = by_code.get(key[0])
        hit = next((d for d in (r['deals'] if r else [])
                    if d['date'] == key[1] and d['pattern'] == key[2]), None)
        if not hit or hit['price'] != price:
            problems.append('필리핀 7~11월 최저 칸 %s (%s원)이 없습니다' % (key, price))

    # 동남아 4노선 2027년 7~11월 — 11주 × 5패턴 220칸 실측(최저/최고/평균), 09-16 주 이후는 미오픈
    for code, (n, low, high, avg) in EXPECT_SEA_H2.items():
        r = by_code.get(code)
        if not r:
            problems.append('동남아 노선 %s 없음' % code)
            continue
        got = {(d['date'], d['pattern']): d for d in r['deals']
               if '2027-07-01' <= d['date'] <= '2027-11-29'}
        want = {((datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for thu in SEA_H2_MEASURED for p in EXPECT_WEEKEND}
        if set(got) != want:
            problems.append('%s 2027년 7~11월 실측 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(want), sorted(set(got) ^ want)[:6]))
        vals = [d['price'] for d in got.values()]
        if len(vals) == n and (min(vals), max(vals), round(sum(vals) / len(vals))) != (low, high, avg):
            problems.append('%s 2027년 7~11월 최저/최고/평균 %s (기대 %s)'
                            % (code, (min(vals), max(vals), round(sum(vals) / len(vals))),
                               (low, high, avg)))
    # 동남아 4노선 실측 칸의 월별 분포(7월 100 · 8월 80 · 9월 40)
    for m, want_n in (('2027-07', 100), ('2027-08', 80), ('2027-09', 40)):
        got_n = sum(1 for r in routes if r['code'] in SEA4 for d in r['deals']
                    if d['date'][:7] == m)
        if got_n != want_n:
            problems.append('동남아 %s 실측 %d칸 (기대 %d칸)' % (m, got_n, want_n))

    notes = flights.get('notes') or {}
    for m in notes:
        if m not in EXPECT_MONTHS:
            problems.append('notes 의 월 %s 이상' % m)
    bw = flights.get('bookingWindow') or {}
    if bw.get('end') != EXPECT_BOOKING_END:
        problems.append('bookingWindow.end %r (기대 %s)' % (bw.get('end'), EXPECT_BOOKING_END))
    if bw.get('sea4End') != EXPECT_BOOKING_SEA4:
        problems.append('bookingWindow.sea4End %r (기대 %s)' % (bw.get('sea4End'),
                                                              EXPECT_BOOKING_SEA4))
    if bw.get('ph4End') != EXPECT_BOOKING_PH4:
        problems.append('bookingWindow.ph4End %r (기대 %s)' % (bw.get('ph4End'),
                                                              EXPECT_BOOKING_PH4))
    return problems


# ---------------------------------------------------------------- 추출 / 주입

def _read(path):
    with open(path, encoding='utf-8') as fp:
        return fp.read()


def find_literal(src, name):
    """`const NAME = <json>` 의 (시작, 끝) 오프셋을 중괄호 짝으로 찾는다."""
    m = re.search(r'\bconst\s+' + re.escape(name) + r'\s*=\s*', src)
    if not m:
        raise SystemExit('index.html 에서 const %s 를 찾지 못했습니다.' % name)
    i = m.end()
    while i < len(src) and src[i] not in '{[':
        i += 1
    opener = src[i]
    closer = '}' if opener == '{' else ']'
    depth, in_str, esc, j = 0, False, False, i
    while j < len(src):
        c = src[j]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return i, j + 1
        j += 1
    raise SystemExit('const %s 의 JSON 이 닫히지 않았습니다.' % name)


def read_index(path=INDEX):
    src = _read(path)
    a, b = find_literal(src, 'DB')
    db = json.loads(src[a:b])
    c, d = find_literal(src, 'FLIGHTS')
    flights = json.loads(src[c:d])
    return src, db, flights, (a, b), (c, d)


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


# ---------------------------------------------------------------- 통계

def stats_of(db, flights):
    hotels = db['hotels']
    cells = sum(len(h.get('rates') or {}) for h in hotels)
    priced = sum(1 for h in hotels for v in (h.get('rates') or {}).values() if v is not None)
    stayplus = sum(len(h.get('stayplus2') or {}) + len(h.get('stayplus3') or {}) for h in hotels)
    tabs = {}
    for h in hotels:
        tabs[h.get('group')] = tabs.get(h.get('group'), 0) + 1
    routes = flights.get('routes') or []
    deals = sum(len(r.get('deals') or []) for r in routes)
    dates = set()
    for h in hotels:
        dates.update((h.get('rates') or {}).keys())
    return {
        'hotels': len(hotels),
        'tabs': tabs,
        'snu': len(((db.get('accor') or {}).get('rows')) or []),
        'cells': cells,
        'priced': priced,
        'na': cells - priced,
        'stayplus': stayplus,
        'routes': len(routes),
        'deals': deals,
        'priced_per_hotel': {h['id']: sum(1 for v in (h.get('rates') or {}).values() if v is not None)
                             for h in hotels},
        'cells_per_hotel': {h['id']: len(h.get('rates') or {}) for h in hotels},
        'dates': len(dates),
        'date_min': min(dates) if dates else None,
        'date_max': max(dates) if dates else None,
    }


# ---------------------------------------------------------------- extract

def cmd_extract(args):
    src, db, flights, _, _ = read_index()
    commit = os.environ.get('MASTER_DB_COMMIT', '')
    if not commit:
        try:
            import subprocess
            commit = subprocess.check_output(['git', '-C', ROOT, 'rev-parse', '--short', 'HEAD'],
                                             text=True).strip()
        except Exception:
            commit = 'unknown'
    st = stats_of(db, flights)
    master = {
        'schema': 'hotel-calendar-app/master-db',
        'version': 1,
        'generated_at': args.now,
        'source': {'file': 'index.html', 'commit': commit, 'tool': 'tools/master_db.py extract'},
        'window': {'start': WINDOW_START, 'end': WINDOW_END, 'days': 365},
        'built': db.get('built'),
        'voucherExpiry': db.get('voucherExpiry'),
        'extended': db.get('extended'),
        'counts': {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na', 'stayplus',
                                      'routes', 'deals', 'snu')},
        'sources': db.get('sources') or [],
        'hotels': db['hotels'],
        'flights': flights,
        'accor': db.get('accor'),
    }
    os.makedirs(os.path.dirname(MASTER), exist_ok=True)
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('wrote %s' % os.path.relpath(MASTER, ROOT))
    print('  hotels %(hotels)d  cells %(cells)d  priced %(priced)d  na %(na)d' % st)
    print('  stayplus %(stayplus)d  routes %(routes)d  deals %(deals)d' % st)
    print('  date window %s ~ %s (%d days)' % (st['date_min'], st['date_max'], st['dates']))
    return 0


# ---------------------------------------------------------------- verify

def project(master):
    """master_db.json -> index.html 의 `const DB` / `const FLIGHTS` 에 들어가야 할 값."""
    db = {
        'hotels': master['hotels'],
        'sources': master['sources'],
        'built': master['built'],
        'voucherExpiry': master['voucherExpiry'],
        'extended': master['extended'],
        'accor': master.get('accor'),
    }
    return db, master['flights']


def check_tabs(db):
    """탭별 호텔 수와 ⑤ 메리어트 40곳의 브랜드 구성을 검사한다."""
    problems = []
    tabs = {}
    for h in db['hotels']:
        tabs[h.get('group')] = tabs.get(h.get('group'), 0) + 1
    for tab, n in EXPECT_TABS.items():
        if tabs.get(tab) != n:
            problems.append('tabs.%s %s곳 (기대 %d곳)' % (tab, tabs.get(tab), n))
    extra = {k: v for k, v in tabs.items() if k not in EXPECT_TABS}
    if extra:
        problems.append('알 수 없는 탭: %s' % extra)
    if len(db['hotels']) != EXPECT_HOTELS:
        problems.append('호텔 합계 %d곳 (기대 %d곳 = 162 + 284 + 4 + 62)' % (len(db['hotels']), EXPECT_HOTELS))
    brands = {}
    ids = set()
    for h in db['hotels']:
        if h['id'] in ids:
            problems.append('호텔 id 중복: %s' % h['id'])
        ids.add(h['id'])
        if h.get('group') == 'marriott':
            brands[h.get('brand')] = brands.get(h.get('brand'), 0) + 1
            for k in ('brand', 'city', 'name', 'source'):
                if not h.get(k):
                    problems.append('메리어트 호텔 %s 에 %s 없음' % (h['id'], k))
    if brands != EXPECT_BRANDS:
        problems.append('메리어트 브랜드 구성 %s (기대 %s)' % (brands, EXPECT_BRANDS))

    # ⑤ 한·일 22곳: 현금·포인트 칸 수와 교차 참조
    kj = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'][0] in 'kj']
    cash = sum(1 for h in kj for v in (h.get('rates') or {}).values() if v is not None)
    pts = sum(1 for h in kj for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(kj) != EXPECT_KJ['hotels'] or cash != EXPECT_KJ['cash'] or pts != EXPECT_KJ['points']:
        problems.append('한·일 22곳 수치 %s (기대 %s)' % (
            {'hotels': len(kj), 'cash': cash, 'points': pts}, EXPECT_KJ))
    for h in kj:
        if not h.get('points') and h['id'] != 'k09':
            problems.append('%s 포인트 칸 없음' % h['id'])
        if h['id'] in EXPECT_OVERLAP and not h.get('alsoIn'):
            problems.append('%s 는 ① 탭과 겹치므로 alsoIn 필요' % h['id'])
    # 같은 호텔이 두 탭에 조용히 중복되지 않았는지(교차 참조 없는 이름 중복 금지)
    seen = {}
    for h in db['hotels']:
        key = (h.get('english') or h['name']).strip().lower()
        prev = seen.get(key)
        if prev and prev != h['id'] and not (h.get('alsoIn') or
                                             ('%s' % prev, h['id']) in KNOWN_DUP or
                                             (h['id'], prev) in KNOWN_DUP):
            problems.append('호텔 중복: %s ↔ %s (%s)' % (prev, h['id'], key))
        seen.setdefault(key, h['id'])
    problems.extend(check_apc(db))
    problems.extend(check_accor3(db))
    return problems


def cmd_verify(args, quiet=False):
    master = json.loads(_read(MASTER))
    src, db, flights, _, _ = read_index()
    problems = []

    mdb, mfl = project(master)
    if compact(mdb) != compact(db):
        # 어느 부분이 다른지 좁혀서 알려준다
        if list(mdb.keys()) != list(db.keys()):
            problems.append('DB key 순서/구성 다름: %s vs %s' % (list(mdb.keys()), list(db.keys())))
        if mdb['hotels'] != db['hotels']:
            for a, b in zip(mdb['hotels'], db['hotels']):
                if a != b:
                    problems.append('hotel %s 내용 다름' % a.get('id'))
                    break
            else:
                problems.append('hotel 개수 다름: %d vs %d' % (len(mdb['hotels']), len(db['hotels'])))
        for k in ('sources', 'built', 'voucherExpiry', 'extended', 'accor'):
            if mdb.get(k) != db.get(k):
                problems.append('DB.%s 다름' % k)
    if compact(mfl) != compact(flights):
        problems.append('FLIGHTS 내용 다름')

    st = stats_of(db, flights)
    expect = master.get('counts') or {}
    for k in ('hotels', 'tabs', 'cells', 'priced', 'na', 'stayplus', 'routes', 'deals', 'snu'):
        if k in expect and expect[k] != st[k]:
            problems.append('counts.%s 불일치: master=%s index=%s' % (k, expect[k], st[k]))
    if st['date_min'] != WINDOW_START or st['date_max'] != WINDOW_END or st['dates'] != 365:
        problems.append('날짜 창 이상: %s ~ %s (%d일)' % (st['date_min'], st['date_max'], st['dates']))
    for hid, n in st['cells_per_hotel'].items():
        if n != 365:
            problems.append('%s 날짜 칸 %d개 (365 이어야 함)' % (hid, n))

    # 탭 구성 검사 (①~④ 기존 데이터가 손상되지 않았는지 포함)
    problems.extend(check_tabs(db))
    problems.extend(check_sources(src))
    problems.extend(check_sources(_read(MASTER)))
    problems.extend(check_flights(flights))

    if problems:
        print('VERIFY FAIL')
        for p in problems:
            print('  - ' + p)
        return 1
    if not quiet:
        print('VERIFY OK — master_db.json == index.html')
        print('  hotels %(hotels)d  tabs %(tabs)s' % st)
        print('  cells %(cells)d  priced %(priced)d  na %(na)d  stayplus %(stayplus)d' % st)
        print('  routes {routes}  deals {deals}  window {date_min}~{date_max}'.format(**st))
        print('  flights 당일치기 %d건 · 패턴 %d종' % (flights['counts'].get('daytrip', 0),
                                                   len(flights['patterns'])))
    return 0


# ---------------------------------------------------------------- inject

def cmd_inject(args):
    if cmd_verify(args, quiet=True) != 0:
        print('master_db.json 이 이미 index.html 과 다릅니다 — verify 로 차이를 먼저 확인하세요.')
        print('(다른 데이터를 넣으려면 수정한 뒤 inject 하는 것이 맞습니다. 계속 진행합니다.)')
    master = json.loads(_read(MASTER))
    mdb, mfl = project(master)
    src, db, flights, span_db, span_fl = read_index()

    if compact(db) == compact(mdb) and compact(flights) == compact(mfl):
        print('index.html 이 이미 master_db.json 과 같습니다 — 바꾸지 않았습니다.')
        return 0

    new = src
    # 뒤쪽(FLIGHTS)부터 바꿔야 앞쪽 오프셋이 흔들리지 않는다
    new = new[:span_fl[0]] + compact(mfl) + new[span_fl[1]:]
    new = new[:span_db[0]] + compact(mdb) + new[span_db[1]:]

    backup = INDEX + '.bak'
    shutil.copy2(INDEX, backup)
    with open(INDEX, 'w', encoding='utf-8') as fp:
        fp.write(new)
    if cmd_verify(args, quiet=True) != 0:
        shutil.copy2(backup, INDEX)
        print('검증 실패 — index.html 을 백업으로 되돌렸습니다.')
        return 1
    os.remove(backup)
    print('index.html 갱신 완료 (DB %d호텔, FLIGHTS %d노선)' % (len(mdb['hotels']), len(mfl.get('routes') or [])))
    return 0


# ---------------------------------------------------------------- stats

def cmd_refresh(args):
    """호텔·항공을 병합한 뒤 master_db.json 의 counts 만 다시 센다(데이터는 건드리지 않음)."""
    master = json.loads(_read(MASTER))
    st = stats_of(master, master['flights'])
    master['counts'] = {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na',
                                           'stayplus', 'routes', 'deals', 'snu')}
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('counts refreshed: %s' % json.dumps(master['counts'], ensure_ascii=False))
    return 0


def cmd_stats(args):
    _, db, flights, _, _ = read_index()
    st = stats_of(db, flights)
    print('index.html 기준')
    print('  hotels  %d  %s' % (st['hotels'], st['tabs']))
    print('  cells   %d  (priced %d / NA %d)' % (st['cells'], st['priced'], st['na']))
    print('  stayplus %d건 · SNU 후보 %d줄' % (st['stayplus'], st['snu']))
    print('  flights %d노선 %d건' % (st['routes'], st['deals']))
    print('  window  %s ~ %s (%d일)' % (st['date_min'], st['date_max'], st['dates']))
    print()
    print('호텔별 요금 표기 칸수')
    for h in db['hotels']:
        print('  %-7s %-34s %3d/365' % (h['id'], h['name'], st['priced_per_hotel'][h['id']]))
    return 0


def main(argv):
    import argparse
    import datetime
    p = argparse.ArgumentParser(description='hotel-calendar-app 통합 마스터 DB 도구')
    p.add_argument('command', choices=['extract', 'verify', 'inject', 'refresh', 'stats'])
    p.add_argument('--now', default=datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z'),
                   help='extract 시 기록할 생성 시각')
    args = p.parse_args(argv)
    return {'extract': cmd_extract, 'verify': cmd_verify, 'inject': cmd_inject,
            'refresh': cmd_refresh, 'stats': cmd_stats}[args.command](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
