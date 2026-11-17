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

# ④ 항공 — 32개 노선(기존 24 + 중국 신규 8) · 2026년 12월 ~ 2027년 11월 (12개월) · 당일치기(0박) 패턴
EXPECT_FLIGHTS = 32
# 중국 신규 8노선 — 노선 코드 → (도시 이름, 딜 건수). 12~1월 완본(9주 × 5패턴 180칸) +
# 연길·장가계·구이린·황산의 2027년 2~6월 금~일(2박) 58칸(2026-11-18 반영)
EXPECT_NEW_ROUTES = {'SHE': ('선양', 46), 'DLC': ('다롄', 46), 'CAN': ('광저우', 46), 'XMN': ('샤먼', 46),
                     'YNJ': ('연길', 63), 'DYG': ('장가계', 63), 'KWL': ('구이린', 61), 'TXN': ('황산', 26)}
# 완본이 도착한 8노선 — 9주(목요일 기준) × 5패턴 45칸씩, 값 333 + 판매편 0건 27 = 360칸
EXPECT_FULL_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN', 'YNJ', 'DYG', 'KWL', 'TXN')
EXPECT_FULL_WEEKS = ('2026-12-03', '2026-12-10', '2026-12-17', '2026-12-24', '2026-12-31',
                     '2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
# 2026-11-18 추가 — 연길·장가계·구이린·황산 2027년 2~5월 금~일(2박) 실측 주(금요일)
EXPECT_26M_WEEKS = ('2027-02-05', '2027-02-12', '2027-02-19', '2027-02-26',
                    '2027-03-05', '2027-03-12', '2027-03-19', '2027-03-26',
                    '2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23', '2027-04-30',
                    '2027-05-07', '2027-05-14', '2027-05-21', '2027-05-28')
# 노선별로 채워진 금~일 칸 수(값) — 구이린은 5/28 미조회, 황산은 4/2~5/21 판매편 0건
EXPECT_26M = {'YNJ': 17, 'DYG': 17, 'KWL': 16, 'TXN': 8}
# 노선별 금~일 실측 출발일(값) — 날짜가 밀리거나 바뀌면 여기서 걸린다
_W26M = EXPECT_26M_WEEKS
EXPECT_26M_DATES = {'YNJ': set(_W26M), 'DYG': set(_W26M),
                    'KWL': set(_W26M) - {'2027-05-28'},
                    'TXN': set(_W26M) - {'2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23',
                                          '2027-04-30', '2027-05-07', '2027-05-14', '2027-05-21',
                                          '2027-05-28'}}
EXPECT_MONTHS = ('2026-12', '2027-01', '2027-02', '2027-03', '2027-04', '2027-05',
                 '2027-06', '2027-07', '2027-08', '2027-09', '2027-10', '2027-11')
EXPECT_FIRST_WEEK, EXPECT_LAST_WEEK = '2026-12-03', '2027-11-25'
# 2026.12~2027.02 고정 기준(1,638건 + 중국 신규 8노선 177건 + 중국 4노선 완본 162칸 + 2027년 2~5월 금~일 58칸)
EXPECT_OLD_BY_MONTH = {'2026-12': 783, '2027-01': 797, '2027-02': 413,
                       '2027-03': 16, '2027-04': 15, '2027-05': 11}
# 2027.06~11 반영분(3개 원본: 260 + 73 + 53 = 386건)
EXPECT_H2_BY_MONTH = {'2027-06': 131, '2027-07': 129, '2027-08': 47,
                      '2027-09': 35, '2027-10': 43, '2027-11': 1}
EXPECT_H2 = {'weekend': 373, 'day': 13, 'total': 386}
EXPECT_NOSALE = {('FUK', '2027-11-12'), ('TYO', '2027-11-12'),
                 ('TYO', '2027-11-16'), ('FUK', '2027-11-20'),
                 ('KWL', '2026-12-05'), ('TXN', '2026-12-05')}   # 중국 2건: 같은 날 복편 0편
# 2026-11-18 황산 완본 — 토~월·금~월·목~월 9주 27칸은 조회 결과 판매편 0건(가격 아님)
EXPECT_NOSALE_TXN = {('TXN', d) for d in (
    '2026-12-05', '2026-12-04', '2026-12-03', '2026-12-12', '2026-12-11', '2026-12-10',
    '2026-12-19', '2026-12-18', '2026-12-17', '2026-12-26', '2026-12-25', '2026-12-24',
    '2027-01-02', '2027-01-01', '2026-12-31', '2027-01-09', '2027-01-08', '2027-01-07',
    '2027-01-16', '2027-01-15', '2027-01-14', '2027-01-23', '2027-01-22', '2027-01-21',
    '2027-01-30', '2027-01-29', '2027-01-28')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN
# 2026-11-18 황산 2027년 4/2~5/21 금~일 8주 연속 판매편 0건(값 아님)
EXPECT_NOSALE_TXN_26M = {('TXN', d) for d in (
    '2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23',
    '2027-04-30', '2027-05-07', '2027-05-14', '2027-05-21')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M
EXPECT_BOOKING_END = '2027-11-14'
EXPECT_JAN_WEEKS = ('2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
# 1월 4주 × 5패턴 전수 노선 — 기존 24개 노선(중국 신규 8노선은 연길만 전수, 나머지는 부분 조사)
EXPECT_JAN_ALL = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
                  'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
EXPECT_WEEKEND = ('목~일', '금~일', '토~월', '목~월', '금~월')
EXPECT_DAY = ('목~목', '금~금', '토~토', '일~일', '월~월')
EXPECT_DAYTRIP_MIN = 170
FL_WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}


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
        if not meta or meta.get('status') not in ('ok', 'short', 'no'):
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
            problems.append('%s 2027년 2~5월 금~일 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(dates), sorted(got ^ dates)[:6]))
    ns_dates = {x['date'] for x in (flights.get('noSale') or []) if x.get('code') == 'TXN'
                and '2027-04-01' <= x.get('date', '') <= '2027-06-30'}
    if ns_dates != {d for (_, d) in EXPECT_NOSALE_TXN_26M}:
        problems.append('황산 2027년 4~5월 금~일 판매편 0건 %d칸 (기대 8칸): %s'
                        % (len(ns_dates), sorted(ns_dates)))
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

    # 조회했으나 판매편이 없던 칸(가격 아님) — deals 와 분리 보관
    codes = {r['code'] for r in routes}
    nosale = flights.get('noSale') or []
    got_ns = {(n.get('code'), n.get('date')) for n in nosale}
    if got_ns != EXPECT_NOSALE:
        problems.append('noSale %s (기대 %s)' % (sorted(got_ns), sorted(EXPECT_NOSALE)))
    for n in nosale:
        if n.get('code') not in codes or not (WINDOW_START <= n.get('date', '') <= WINDOW_END):
            problems.append('noSale 이상: %s' % (n,))
        if 'price' in n:
            problems.append('noSale 에 가격이 들어 있음(추정 금지): %s' % (n,))
        key = (n.get('code'), n.get('date'), n.get('pattern'))
        if key in deal_keys:
            problems.append('noSale 가 실측 딜과 겹침: %s' % (key,))

    notes = flights.get('notes') or {}
    for m in notes:
        if m not in EXPECT_MONTHS:
            problems.append('notes 의 월 %s 이상' % m)
    bw = flights.get('bookingWindow') or {}
    if bw.get('end') != EXPECT_BOOKING_END:
        problems.append('bookingWindow.end %r (기대 %s)' % (bw.get('end'), EXPECT_BOOKING_END))
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
