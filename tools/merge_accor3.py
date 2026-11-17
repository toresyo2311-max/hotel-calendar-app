#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""아코르 12개월 조사 3건을 master_db.json 에 병합한다.

입력 (워크스페이스 기준):
  1) data-sources/accor-stayplus-snu/accor_stayplus_snu_12m_report.md  — SNU·Stay Plus 인사이트(표를 코드에 옮겨 적음)
  2) data-sources/accor-fairmont-sofitel/calendar_1~3.md               — 한·중·일 페어몬트·소피텔 21곳 × 365일
  3) data-sources/accor-allplus-china-30/calendar.md                    — 부산 출발 중올플 30곳 × 365일

하는 일
  · ② 중올플: 이미 있는 25곳에 365일 현금 요금을 채우고, 새 호텔 5곳을 편입한다.
  · ③ 아코르: 한·중·일 페어몬트·소피텔 21곳을 365일 달력과 함께 넣고, 겹치는 호텔은 alsoIn 으로 양방향 연결한다.
  · DB.accor 에 SNU·Stay Plus 2박 후보(도시·호텔·체크인·SNU·정가·절감)를 넣는다.
  · 우한의 비정상 요금(1박 2.33억 원)과 만실·미오픈은 가격이 아니라 null(NA)로 둔다.

사용법: python3 tools/merge_accor3.py [--dry-run]
"""
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
WS = os.path.dirname(os.path.dirname(ROOT))
DS = os.path.join(WS, 'data-sources')

SRC_FM = [os.path.join(DS, 'accor-fairmont-sofitel', 'calendar_%d.md' % i) for i in (1, 2, 3)]
SRC_CN = os.path.join(DS, 'accor-allplus-china-30', 'calendar.md')

WINDOW_START, WINDOW_END = '2026-12-01', '2027-11-30'
SRC_FM_TEXT = ('한·중·일 페어몬트·소피텔 21곳 12개월 조사(2026-11-17) · '
               '아코르 공식 API 회원 최저가 1박(세금 포함) · 365일')
SRC_CN_TEXT = ('아코르 공식 API 회원 최저가 1박(세금 포함) · 365일 조회(2026-11-17~18)')

# ② 중올플 30곳 → 기존 호텔 id (조사 원문 이름과 화면 이름이 달라 손으로 맞춘 표)
CN_TO_EXISTING = {
    'A7Z9': None,       # 페어몬트 우한 — ②에 없음(신규)
    'B953': 'ap063',    # 페어몬트 샤먼
    'B851': 'ap142',    # 페어몬트 싼야 하이탕베이
    'B9G8': 'ap052',    # 소피텔 상하이 북와이탄 = 화면 '소피텔 상하이 베이쓰탄'(Sofitel Shanghai North Bund)
    '5949': 'ap075',    # 소피텔 시안 인민광장
    '2197': 'ap176',    # 소피텔 정저우 인터내셔널
    '8873': 'ap241',    # 소피텔 구이양 헌터
    '8529': 'ap200',    # 소피텔 쿤밍
    '6824': 'ap088',    # 소피텔 하얼빈
    'B733': 'ap101',    # 소피텔 항저우 잉관
    '8719': 'ap216',    # 소피텔 포산
    '7970': 'ap224',    # 소피텔 하이커우
    '8167': 'ap140',    # 소피텔 싼야 리만 = 화면 '소피텔 싼야 리먼 리조트'
    'B8Y3': 'ap125',    # 소피텔 슝안 = 화면 '소피텔 바오딩 슝안'
    '7598': 'ap056',    # 풀만 상하이 징안
    '7025': 'ap025',    # 풀만 베이징 사우스
    'B2H2': 'ap131',    # 풀만 선전 노스
    '7934': 'ap076',    # 풀만 장자제
    'C4Q5': None,       # 풀만 다롄 — 신규
    'C037': None,       # 풀만 옌타이 센터 — 신규
    'A5A1': 'ap023',    # 스위소텔 베이징 홍콩·마카오 센터
    'C496': 'ap004',    # 스위소텔 광저우
    'B9L8': 'ap067',    # 스위소텔 선양
    'B9N9': 'ap127',    # M갤러리 선전 패션 타운
    'C3A2': 'ap078',    # M갤러리 청두 파이낸셜 시티
    'C1H8': None,       # 밍 호텔 난징 - 엠갤러리 — 신규
    'A4A4': 'ap102',    # M갤러리 더 실버리 홍콩
    'C3N7': None,       # 뫼벤픽 상하이 인민광장 — 신규
    '6684': 'ap016',    # 그랜드 머큐어 베이징 센트럴
    'B0Y3': 'ap086',    # 노보텔 칭다오 뉴호프
}
# ③에 들어가는 21곳 → (② 또는 ① 호텔 id, 없으면 None)
FM_TO_EXISTING = {
    'B6R8': 'h13',      # 페어몬트 도쿄 — ① HoteLux 탭
    'A5G7': 'h04',      # 페어몬트 피스 호텔 상하이 — ① HoteLux 탭
    'A7Z9': 'cA7Z9',    # 페어몬트 우한 — 이번에 ②에 새로 들어간다
    'B953': 'ap063',
    'B851': 'ap142',
    'C1B5': None,       # 페어몬트 다롄(개관 전)
    'B9G8': 'ap052',
    '5949': 'ap075',
    'B733': 'ap101',
    'C3B5': 'ap190',    # 소피텔 창저우 하이테크지구
    'C4U2': 'ap237',    # 소피텔 후저우 안지
    'B8Y3': 'ap125',
    '2197': 'ap176',
    '9567': 'ap251',    # 소피텔 시닝
    '8873': 'ap241',
    '8529': 'ap200',
    '8102': 'ap118',    # 소피텔 롄윈강 쑤닝
    '6824': 'ap088',
    '8719': 'ap216',
    '7970': 'ap224',
    '8167': 'ap140',
}
# ③ 탭 표시 순서 (일본 1 → 중국 페어몬트 5 → 중국 소피텔 15)
FM_ORDER = ['B6R8', 'A5G7', 'A7Z9', 'B953', 'B851', 'C1B5',
            'B9G8', '5949', 'B733', 'C3B5', 'C4U2', 'B8Y3', '2197', '9567',
            '8873', '8529', '8102', '6824', '8719', '7970', '8167']
FM_NAME_CLEAN = {'C1B5': '페어몬트 다롄'}
FM_ENGLISH = {'C1B5': 'Fairmont Dalian', 'A5G7': 'Fairmont Peace Hotel on the Bund',
              'B6R8': 'Fairmont Tokyo'}
FM_CITY = {'C1B5': '다롄'}
CN_ENGLISH = {'A7Z9': 'Fairmont Wuhan', 'C4Q5': 'Pullman Dalian', 'C037': 'Pullman Yantai Center',
              'C1H8': 'The Ming Hotel Nanjing - MGallery', 'C3N7': 'Movenpick Shanghai People\'s Square'}
CN_CITY_KEY = {'다롄': 'cn-dalian', '옌타이': 'cn-yantai'}

# ③ 호텔별 안내(요금 이상·판매 중단·개관 전)
FM_NOTE = {
    'A7Z9': '요금 이상 241일(2027-04-04~11-30) 제외 — 호텔이 등록한 요율이 비정상(1박 2억 3,330만 원)이라 가격으로 쓰지 않음',
    'A5G7': '2027-08-21~11-30(102일) 판매 없음 — 래플스 전환 예정 구간',
    '8167': '2027-09-30~10-07(8일) 판매 없음 — 국경절 구간 요율 미개시',
    'B6R8': '2026-12-31·2027-01-01·2027-06-13 판매 없음 — 연말 12/23~30은 연중 최고가',
    'C1B5': '개관 전 — 365일 전부 요금 미노출(아코르에 Opening Soon 으로만 등록)',
    'B953': '2026-12-01~03만 195.7만 원 — 남은 객실이 고가 객실뿐인 특수 구간',
}
CN_NOTE = {
    'A7Z9': FM_NOTE['A7Z9'],
    'B953': FM_NOTE['B953'],
    '8167': FM_NOTE['8167'],
}

# ─────────────────── SNU·Stay Plus 인사이트 (원문 표를 옮겨 적음) ───────────────────
# (도시, 호텔, 코드, 체크인, SNU 2박, 정가, 원문에 적힌 절감)
SNU_ROWS = [
    ('서울', '소피텔 앰배서더 서울', 'B220', '2027-01-08', 941500, 1324000, 420800),
    ('서울', '소피텔 앰배서더 서울', 'B220', '2027-01-27', 712000, 1094500, 420800),
    ('서울', '소피텔 앰배서더 서울', 'B220', '2027-02-05', 941500, 1324000, 420800),
    ('서울', '소피텔 앰배서더 서울', 'B220', '2027-03-05', 1037100, 1419600, 420800),
    ('서울', '소피텔 앰배서더 서울', 'B220', '2027-06-04', 1018000, 1400500, 382500),
    ('서울', '소피텔 앰배서더 서울', 'B220', '2027-09-03', 807600, 1190100, 420800),
    ('창원', '그랜드 머큐어 앰배서더 창원', None, '2026-12-11', 338300, 652800, 346000),
    ('도쿄', '페어몬트 도쿄', 'B6R8', '2027-03-05', 3024500, 4035500, None),
    ('도쿄', '풀만 도쿄 타마치', 'B137', '2027-03-05', 1343000, 1869400, None),
    ('오사카', '스위소텔 난카이 오사카', None, '2027-03-05', 524300, 812000, 287700),
    ('방콕', '풀만 방콕 호텔 G', None, '2027-03-05', 176800, 348800, None),
    ('방콕', '뫼벤픽 수쿰빗 15', None, '2027-03-05', 188300, 352100, None),
    ('방콕', '그랜드 머큐어 아트리움', None, '2027-03-05', 197600, 401100, None),
    ('방콕', '뫼벤픽 BDMS 웰니스', None, '2027-03-05', 279600, 436000, None),
    ('방콕', 'VIE 호텔 MGallery', None, '2027-03-05', 376700, 472300, None),
    ('방콕', '풀만 방콕 킹파워', None, '2027-03-05', 403200, 517200, None),
    ('방콕', 'SO/ 방콕', None, '2027-03-05', 473500, 710300, None),
    ('방콕', '소피텔 방콕 수쿰빗', None, '2027-03-05', 492000, 910100, 492100),
    ('방콕', '페어몬트 방콕 수쿰빗', None, '2027-03-05', 673900, 1147000, 556900),
    ('다낭', '그랜드 머큐어 다낭', None, '2027-03-05', 157000, 376100, None),
    ('다낭', '풀만 다낭 비치 리조트', None, '2027-03-05', 427400, 863200, 503300),
    ('싱가포르', '그랜드 머큐어 로지', None, '2027-03-05', 374100, 610400, None),
    ('싱가포르', '풀만 힐스트리트', None, '2027-03-05', 422800, 764800, None),
    ('싱가포르', '스위소텔 스탬포드', None, '2027-03-05', 641300, 720600, None),
    ('싱가포르', '페어몬트 싱가포르', None, '2027-03-05', 650100, 720600, None),
    ('싱가포르', '몬드리안 듀크슨', None, '2027-03-05', 664500, 1295600, None),
    ('싱가포르', '소피텔 센토사', None, '2027-03-05', 677700, 899100, None),
    ('싱가포르', '풀만 오차드', None, '2027-03-05', 700200, 1499600, 958500),
    ('싱가포르', '소피텔 시티센터', None, '2027-03-05', 985800, 1318000, None),
    ('상하이', '풀만 창수 리먼', None, '2027-03-05', 135900, 259900, None),
    ('상하이', '풀만 쑤저우 중후이', None, '2027-03-05', 147700, 319200, None),
    ('상하이', '풀만 칭푸 엑설런스', None, '2027-03-05', 180700, 498700, None),
    ('상하이', '그랜드 머큐어 홍차오', None, '2027-03-05', 189500, 450200, None),
    ('상하이', '소피텔 상하이 홍차오', None, '2027-03-05', 203400, 617700, 483100),
    ('상하이', '풀만 쑤저우 타이창', None, '2027-03-05', 251500, 488300, None),
    ('상하이', '풀만 상하이 쉬후이', None, '2027-03-05', 266500, 674700, None),
    ('상하이', '풀만 자싱 핑후', None, '2027-03-05', 282200, 559900, None),
    ('상하이', '풀만 상하이 징안', None, '2027-03-05', 295100, 502600, None),
    ('상하이', '풀만 저우좡', None, '2027-03-05', 300100, 420200, None),
    ('상하이', '스위소텔 그랜드 상하이', None, '2027-03-05', 332500, 1011900, 792200),
    ('상하이', '소피텔 상하이 북와이탄', None, '2027-03-05', 370700, 767600, 462900),
    ('상하이', '풀만 상하이 센트럴', None, '2027-03-05', 377300, 497300, None),
    ('상하이', '페어몬트 피스 호텔 상하이', 'A5G7', '2027-03-05', 1200500, 1995900, 927400),
]
SNU_KIND = {'서울': '국내 주말 창(7개) 중 SNU 열린 6개', '창원': '국내 확인 창 1개',
            '도쿄': '2027-03-05(금) 2박 창', '오사카': '2027-03-05(금) 2박 창',
            '방콕': '2027-03-05(금) 2박 창', '다낭': '2027-03-05(금) 2박 창',
            '싱가포르': '2027-03-05(금) 2박 창', '상하이': '2027-03-05(금) 2박 창'}


# ───────────────────────────── 파싱 ─────────────────────────────

def _cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def _parse_cell(c):
    """'7일 110.4만' / '31일 ❌' / '4일 ⚠️' / '1일 🟡🔴 **23.8만**' → (day, price|None, flag)"""
    m = re.match(r'^(\d{1,2})일\s*(.*)$', c)
    if not m:
        return None
    day = int(m.group(1))
    rest = m.group(2)
    flag = ''
    if '이상' in rest or '⚠️' in rest:
        flag = 'anomaly'
    elif '❌' in rest:
        flag = 'closed'
    price = None
    pm = re.search(r'([\d.]+)\s*만', rest)
    if pm:
        price = int(round(float(pm.group(1)) * 10000))
        if not flag:
            flag = 'ok'
    elif not flag:
        flag = 'blank'
    return (day, price, flag)


def parse_calendar(path, kind):
    text = open(path, encoding='utf-8').read()
    out = {}
    for block in re.split(r'\n(?=## )', text):
        head = block.split('\n', 1)[0]
        if not head.startswith('## '):
            continue
        title = re.sub(r'^[\U0001F1E6-\U0001F1FF\s]+', '', head[3:]).strip()
        if kind == 'fairmont':
            name = re.sub(r'\(개관 예정\)\s*$', '', title).strip()
            cm = re.search(r'`([0-9A-Z]{4,6})`\s*·\s*([^\s·]+)\s*·', block)
            if not cm:
                raise SystemExit('호텔 코드를 찾지 못했습니다: %s' % title)
            code, city = cm.group(1), cm.group(2)
        else:
            m = re.match(r'^\d+\.\s*(.*?)\s*·\s*([^\s(]+)\s*\(([0-9A-Z]{4,6})\)', title)
            if not m:
                raise SystemExit('호텔 줄을 읽지 못했습니다: %s' % title)
            name, city, code = m.group(1), m.group(2), m.group(3)
        rates, flags = {}, {}
        year = month = None
        for line in block.split('\n'):
            mm = re.match(r'^###\s*(?:📅\s*)?(\d{4})년\s*(\d{1,2})월', line)
            if mm:
                year, month = int(mm.group(1)), int(mm.group(2))
                continue
            if not line.strip().startswith('|') or year is None or '---' in line:
                continue
            for c in _cells(line):
                p = _parse_cell(c)
                if not p:
                    continue
                day, price, flag = p
                try:
                    dt = datetime.date(year, month, day).isoformat()
                except ValueError:
                    continue
                rates[dt] = price
                flags[dt] = flag
        full = {}
        d0 = datetime.date.fromisoformat(WINDOW_START)
        for i in range(365):
            k = (d0 + datetime.timedelta(days=i)).isoformat()
            full[k] = rates.get(k)
        out[code] = {'name': name, 'city': city, 'rates': full,
                     'flags': flags, 'raw_days': len(rates)}
        # 다롄(개관 전)은 달력 표 자체가 없다 — 365일 전부 null 이 정상
        if len(rates) not in (0, 365):
            raise SystemExit('%s 날짜 칸 %d일 (0 또는 365 이어야 함)' % (code, len(rates)))
    return out


def totals(rates):
    v = [x for x in rates.values() if x is not None]
    return len(v), (min(v) if v else None), (max(v) if v else None)


# ───────────────────────────── 병합 ─────────────────────────────

def main(argv):
    dry = '--dry-run' in argv
    fm = {}
    for p in SRC_FM:
        fm.update(parse_calendar(p, 'fairmont'))
    cn = parse_calendar(SRC_CN, 'china30')
    if len(fm) != 21 or len(cn) != 30:
        raise SystemExit('호텔 수가 원본과 다릅니다: fairmont %d / china %d' % (len(fm), len(cn)))

    # 같은 호텔을 두 조사가 다르게 적었으면 멈춘다(값 덮어쓰기 방지)
    for code, row in cn.items():
        if code in fm:
            diff = [k for k in fm[code]['rates'] if fm[code]['rates'][k] != row['rates'][k]]
            if diff:
                raise SystemExit('%s: 두 조사 값이 %d일 다릅니다 — 어느 쪽을 쓸지 정해야 합니다' % (code, len(diff)))

    m = json.load(open(MASTER, encoding='utf-8'))
    hotels = m['hotels']
    before = len(hotels)
    by_id = {h['id']: h for h in hotels}
    china = [h for h in hotels if h.get('group') == 'china']
    cn_before = len(china)
    tabs_before = {h.get('group') for h in hotels}

    code_of = {}
    for h in china:
        code_of[h['id']] = h.get('code')

    # ---- ② 중올플: 기존 호텔에 365일 현금 요금 채우기 ----
    filled = 0
    for code, target in CN_TO_EXISTING.items():
        if target is None:
            continue
        h = by_id.get(target)
        if h is None or h.get('group') != 'china':
            raise SystemExit('② 호텔 %s 를 찾지 못했습니다' % target)
        row = cn[code]
        h['rates'] = dict(row['rates'])
        h['source'] = SRC_CN_TEXT
        if code in CN_NOTE:
            h['note'] = CN_NOTE[code]
        if code == 'C3A2':
            # ② APC 목록에는 '개관 예정'으로 있었지만 이번 조회에서 365일 요금이 나왔다
            h['name'] = 'M갤러리 청두 파이낸셜 시티'
            h['english'] = 'Financial City Hotel Chengdu-MGallery Collection'
            h['note'] = ('② APC 목록에는 개관 예정으로 등록돼 있었지만 2026-11-17~18 조회에서 '
                         '365일 요금이 확인돼 판매 중입니다.')
        closed = sum(1 for v in row['flags'].values() if v == 'closed')
        if closed and 'note' not in h:
            h['note'] = '판매 없음 %d일(만실·판매중단)' % closed
        filled += 1

    # ---- ② 중올플: 새 호텔 5곳 편입 ----
    new_cn = []
    tier_label = {}
    for h in china:
        a = h.get('accor') or {}
        if a.get('tier'):
            tier_label[a['tier']] = a.get('tier_label')
    city_key = {}
    for h in china:
        a = h.get('accor') or {}
        if a.get('city_key'):
            city_key.setdefault(h['city'], a['city_key'])
    for code, target in CN_TO_EXISTING.items():
        if target is not None:
            continue
        row = cn[code]
        tier = 2 if row['city'] in ('우한', '다롄', '옌타이') else 1
        key = CN_CITY_KEY.get(row['city']) or city_key.get(row['city']) or ('cn-' + code.lower())
        new = {
            'id': 'c' + code,
            'group': 'china',
            'city': row['city'],
            'name': row['name'],
            'english': CN_ENGLISH.get(code, ''),
            'brand': '',
            'promotion': '중올플 무료숙박권 대상 후보 — 실제 쿼터 별도 확인',
            'rates': dict(row['rates']),
            'source': SRC_CN_TEXT + ' / APC 관측(무료숙박 가능일) 미수록',
            'code': code,
            'note': (CN_NOTE.get(code, '') + (' · ' if CN_NOTE.get(code) else '')
                     + '무료숙박 가능일(APC) 관측은 이 호텔에 없습니다'),
            'accor': {
                'participation': 'participating',
                'required_nights': 1,
                'public_id': 'code-' + code,
                'tier': tier,
                'tier_label': tier_label.get(tier, ''),
                'city_key': key,
                'dec': {'available': 0, 'observed': 0},
                'nov': {'available': 0, 'observed': 0},
                'newest_checked': None,
                'fresh_hours': 72,
                'source': 'APC 관측 미수록 — 현금 요금만 수집',
            },
            'accor_apc': {},
            'accor_apc_t': {},
        }
        new_cn.append(new)
    # brand 는 이름 앞부분으로 채운다(② 다른 호텔과 같은 방식)
    brand_word = {'페어몬트': '페어몬트', '풀만': '풀만', '뫼벤픽': '뫼벤픽'}
    for h in new_cn:
        for k, v in brand_word.items():
            if h['name'].startswith(k):
                h['brand'] = v
        if '엠갤러리' in h['name']:
            h['brand'] = '엠갤러리'
    idx = max(i for i, h in enumerate(hotels) if h.get('group') == 'china') + 1
    hotels[idx:idx] = new_cn
    by_id = {h['id']: h for h in hotels}   # 신규 ② 호텔까지 반영해 ③ alsoIn 연결에 쓴다

    # ---- ③ 아코르: 21곳 편입 ----
    domestic = [h for h in hotels if h.get('group') == 'domestic']
    dom_before = len(domestic)
    new_dom = []
    for code in FM_ORDER:
        row = fm[code]
        target = FM_TO_EXISTING[code]
        base = by_id.get(target) if target else None
        name = FM_NAME_CLEAN.get(code) or (base['name'] if base else row['name'])
        english = FM_ENGLISH.get(code) or (base.get('english') if base else '')
        city = FM_CITY.get(code) or (base['city'] if base else row['city'])
        brand = '페어몬트' if '페어몬트' in name else '소피텔'
        note = FM_NOTE.get(code, '')
        if base and base['name'] != row['name']:
            note = ('조사 원문 표기: %s' % row['name']) + (' · ' + note if note else '')
        new = {
            'id': 'a' + code,
            'group': 'domestic',
            'city': city,
            'region': '일본' if code == 'B6R8' else '중국',
            'name': name,
            'english': english,
            'brand': brand,
            'code': code,
            'promotion': ('SNU·Stay Plus 참여 — ' + ('개관 전(요금 미노출)' if code == 'C1B5'
                                                     else 'Stay Plus는 2027-09-30까지')),
            'note': note,
            'rates': dict(row['rates']),
            'source': SRC_FM_TEXT,
            'program': {'stayplus': True, 'snu': True},
        }
        if base:
            new['alsoIn'] = base['id']
            base['alsoIn'] = new['id']
        new_dom.append(new)
    idx = max(i for i, h in enumerate(hotels) if h.get('group') == 'domestic') + 1
    hotels[idx:idx] = new_dom

    # ---- 기존 ③ 4곳: 지역·프로그램 표시 ----
    prog = {
        'dB220': {'stayplus': True, 'snu': True,
                  'snuNote': 'SNU 2박 6창 가능 — 71.2만(1/27)~103.7만(3/5)·12/4만 미노출'},
        'dB200': {'stayplus': True, 'snu': False,
                  'snuNote': 'SNU 7창 전부 미노출 — Stay Plus는 평일 2박 위주'},
        'dA3N6': {'stayplus': True, 'snu': False, 'snuBrand': False,
                  'snuNote': '머큐어는 SNU 참여 브랜드가 아님'},
        'dC2G2': {'stayplus': True, 'snu': False, 'snuBrand': False,
                  'snuNote': '이비스는 SNU 참여 브랜드가 아님'},
    }
    for h in hotels:
        if h['id'] in prog:
            h['region'] = '한국'
            h['program'] = prog[h['id']]
    # ① 탭과 겹치는 서울 2곳도 양방향 연결(소피텔 서울 ↔ h31, 페어몬트 서울 ↔ h39)
    for a, b in (('dB220', 'h31'), ('dB200', 'h39')):
        by_id[a]['alsoIn'] = b
        by_id[b]['alsoIn'] = a

    # ---- DB.accor (SNU·Stay Plus 인사이트) ----
    rows = []
    for city, hotel, code, checkin, snu, lst, stated in SNU_ROWS:
        r = {'city': city, 'hotel': hotel, 'checkin': checkin, 'snu': snu, 'list': lst}
        if code:
            r['code'] = code
        if stated is not None:
            r['save'] = stated
            r['saveGiven'] = True
        else:
            r['save'] = lst - snu
            r['saveGiven'] = False
        rows.append(r)
    rows.sort(key=lambda r: (-r['save'], r['city'], r['hotel']))
    accor = {
        'program': {
            'checked': '2026-11-17 16:30~17:10 KST',
            'stayplusExpiry': '2027-09-30',
            'snuExpiry': '2027-12-31',
            'snuCards': 2,
            'stayplusNights': 2,
            'snuWindow': '도시별 2027-03-05(금)~07 2박 창 · 서울은 7개 창',
            'snuRule': 'SNU 1장 = 1박 스위트 확정 · Stay Plus 1장 = 2박 중 1박 무료(가장 비싼 밤)',
            'snuBrands': '참여: 페어몬트·소피텔·소피텔 레전드·풀만·스위소텔·뫼벤픽·그랜드 머큐어·MGallery·SO/ · 미참여: 머큐어·노보텔·이비스',
            'note': 'SNU 요금은 세금 별도 2박 합계 · 절감은 원문 표기값(없는 줄은 정가−SNU 계산)',
        },
        'kinds': SNU_KIND,
        'rows': rows,
    }
    m['accor'] = accor
    m['sources'] = list(dict.fromkeys(list(m.get('sources') or []) + [
        'accor_stayplus_snu_12m_report.md',
        'accor-fairmont-sofitel/summary.md · calendar_1~3.md',
        'accor-allplus-china-30/summary.md · calendar.md',
    ]))
    m['generated_at'] = datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')
    m['built'] = '2026-11-17'
    m['extended'] = (m.get('extended') or '') + \
        ' / 2026-11-18 KST 아코르 12개월 조사 3건(SNU·Stay Plus 21곳 365일 · 중올플 30곳 365일) 반영'

    # ---- 건수 ----
    tabs = {}
    for h in hotels:
        tabs[h.get('group')] = tabs.get(h.get('group'), 0) + 1
    cells = sum(len(h.get('rates') or {}) for h in hotels)
    priced = sum(1 for h in hotels for v in (h.get('rates') or {}).values() if v is not None)
    stayplus = sum(len(h.get('stayplus2') or {}) + len(h.get('stayplus3') or {}) for h in hotels)
    m['counts'] = {
        'hotels': len(hotels), 'tabs': tabs, 'cells': cells, 'priced': priced,
        'na': cells - priced, 'stayplus': stayplus,
        'routes': len(m['flights']['routes']),
        'deals': sum(len(r['deals']) for r in m['flights']['routes']),
        'snu': len(rows),
    }

    # ---- 검사 ----
    problems = []
    if tabs.get('lux') != 162 or tabs.get('marriott') != 62:
        problems.append('①·⑤ 호텔 수가 변했습니다: %s' % tabs)
    if tabs.get('china') != cn_before + len(new_cn):
        problems.append('② 호텔 수 %d (기대 %d)' % (tabs.get('china'), cn_before + len(new_cn)))
    if tabs.get('domestic') != dom_before + len(new_dom):
        problems.append('③ 호텔 수 %d (기대 %d)' % (tabs.get('domestic'), dom_before + len(new_dom)))
    if len(hotels) != before + len(new_cn) + len(new_dom):
        problems.append('호텔 합계 %d (기대 %d)' % (len(hotels), before + len(new_cn) + len(new_dom)))
    for h in hotels:
        r = h.get('rates') or {}
        if len(r) != 365:
            problems.append('%s 날짜 칸 %d' % (h['id'], len(r)))
        if any(isinstance(v, int) and v > 3_000_000 for v in r.values()) and h['id'] in (
                ['a' + c for c in FM_ORDER] + ['c' + c for c, t in CN_TO_EXISTING.items() if t is None]
                + [t for c, t in CN_TO_EXISTING.items() if t]):
            problems.append('%s 에 비정상 고가가 남아 있습니다' % h['id'])
    if problems:
        print('MERGE FAIL')
        for p in problems:
            print('  - ' + p)
        return 1

    print('② 중올플: 기존 %d곳 요금 채움 · 신규 %d곳 → 총 %d곳' % (filled, len(new_cn), tabs['china']))
    print('③ 아코르: 기존 %d곳 + 신규 %d곳 → 총 %d곳' % (dom_before, len(new_dom), tabs['domestic']))
    print('   SNU 후보 %d줄 (도시 %d개)' % (len(rows), len({r['city'] for r in rows})))
    print('   호텔 %d곳 · 칸 %d · 요금 %d · NA %d' % (len(hotels), cells, priced, cells - priced))
    for h in new_cn:
        n, mn, mx = totals(h['rates'])
        print('   + ② %-8s %-22s 요금 %3d일 최저 %s' % (h['id'], h['name'], n, mn))
    for h in new_dom:
        n, mn, mx = totals(h['rates'])
        print('   + ③ %-8s %-22s 요금 %3d일 최저 %s' % (h['id'], h['name'], n, mn))
    if dry:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        return 0
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(m, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('wrote %s' % os.path.relpath(MASTER, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
