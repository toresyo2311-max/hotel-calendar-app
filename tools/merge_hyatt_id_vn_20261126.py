#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 동남아 2·3차 인도네시아 14곳 + 베트남 13곳(총 27곳) 병합 (2026-11-26)

입력
  · 4번(@jin_4) 인도네시아 14곳 — 3개 배치
      memory/clones/06130525-jin489/pickle/2026-11-26-1741/received/0-hyatt-indonesia-batch{1,2,3}.json
      (hyatt.com /explore-hotels/service/avail/days · STANDARD_ROOM 포인트 365일)
  · 6번(@jin_6) 베트남 13곳 — 3개 배치
      memory/clones/146dd4d1-jin_6/pickle/2026-11-26-1741/received/0-hyatt-vietnam-batch{1-4,2-4,3-5}.json
      (hyatt.com 포인트 캘린더 · Standard Room 365일)
대상
  data/app/tab10_hyatt.json  350곳 → 377곳 (hy351~hy377)

■ 규칙
- 마스터(1-hyatt-global-master.json)에 27개 spiritCode 전부 등록돼 있고 이름·도시·카테고리·
  woh 참여 여부가 배치본과 일치하는지 먼저 확인한다.
- 기존 350곳과 code·영문명 중복 0건 확인(서드파티 코드 중복 없음).
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 — ① 탭 지점은
  뉴욕·싱가포르·도쿄·서울·시드니·방콕·상하이·다낭·나트랑·부산·후쿠오카·오사카뿐이고
  인도네시아·호찌민·하노이·하이퐁·하롱·푸꾸옥·나트랑(신규분)·껀터 지점이 없어 겹침 0곳.
- city 는 국문(발리·자카르타·족자카르타·수라카르타·마카사르·라부안바조 / 호찌민·다낭·하노이·
  하이퐁·하롱·나트랑·투이호아·푸꾸옥·껀터), brand 는 공홈 브랜드 라벨, category 는 정수
  (미개관 hanct·크루즈 dpaal 은 None).
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 두 배치 모두 현금가 미수집(공홈 현금 캘린더 없음·
  rate JSON 차단·세금 포함 표기 없음).
- 링크는 기존 동남아 카드와 같이 공홈 예약 화면 https://www.hyatt.com/shop/rooms/{code}.
"""

import copy
import json
import os
import re
import unicodedata
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
ID_DIR = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-26-1741/received')
VN_DIR = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-26-1741/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

FIRST_ID = 351

# ── 27곳 메타(국문명·도시·브랜드·카테고리·배치 시각) ─────────────────────
# (code, 국문명, 도시, 브랜드, 카테고리, 배치시각)
PLAN = [
    # 인도네시아 14 — batch1(18:01 KST) 5 · batch2(17:57) 5 · batch3(17:53) 4
    ('jakgh', '그랜드 하얏트 자카르타', '자카르타', 'Grand Hyatt', 3, '18:01'),
    ('cgkph', '파크 하얏트 자카르타', '자카르타', 'Park Hyatt', 3, '18:01'),
    ('cgkub', '케라톤 앳 더 플라자', '자카르타', 'The Unbound Collection by Hyatt', 5, '18:01'),
    ('balgh', '그랜드 하얏트 발리', '발리', 'Grand Hyatt', 3, '18:01'),
    ('dpsbl', '하얏트 리젠시 발리', '발리', 'Hyatt Regency', 3, '17:57'),
    ('dpsau', '알릴라 우붓', '발리', 'Alila', 4, '17:57'),
    ('dpsas', '알릴라 스미냑', '발리', 'Alila', 6, '17:57'),
    ('dpsat', '클레오 스미냑', '발리', 'JdV by Hyatt', 2, '17:57'),
    ('dpsav', '알릴라 빌라스 울루와투', '발리', 'Alila', 8, '17:57'),
    ('dpsak', '알릴라 망기스', '발리', 'Alila', 2, '18:01'),
    ('yogya', '하얏트 리젠시 족자카르타', '족자카르타', 'Hyatt Regency', 1, '17:53'),
    ('socal', '알릴라 솔로', '수라카르타', 'Alila', 1, '17:53'),
    ('upgzm', '하얏트 플레이스 마카사르', '마카사르', 'Hyatt Place', 1, '17:53'),
    ('dpaal', '알릴라 푸르나마', '라부안바조', 'Alila', None, '17:53'),
    # 베트남 13 — batch1(18:05) 4 · batch2(18:25) 4 · batch3(19:35) 5
    ('saiph', '파크 하얏트 사이공', '호찌민', 'Park Hyatt', 5, '19:35'),
    ('vn100', '윙크 사이공 센터', '호찌민', 'Unscripted by Hyatt', 1, '19:35'),
    ('vn101', '윙크 다낭 센터', '다낭', 'Unscripted by Hyatt', 1, '18:05'),
    ('vn102', '윙크 다낭 리버사이드', '다낭', 'Unscripted by Hyatt', 1, '18:05'),
    ('vn106', '윙크 하노이 웨스트레이크', '하노이', 'Unscripted by Hyatt', 1, '18:25'),
    ('hanct', '하얏트 센트릭 하노이 센터', '하노이', 'Hyatt Centric', None, '18:25'),
    ('vn105', '윙크 하이퐁 센터', '하이퐁', 'Unscripted by Hyatt', 1, '18:25'),
    ('vdorh', '하얏트 리젠시 하롱베이', '하롱', 'Hyatt Regency', 2, '18:25'),
    ('vdozh', '하얏트 플레이스 하롱베이 바이차이', '하롱', 'Hyatt Place', 1, '19:35'),
    ('cxrrn', '하얏트 리젠시 나트랑', '나트랑', 'Hyatt Regency', 3, '19:35'),
    ('vn103', '윙크 투이호아 비치', '투이호아', 'Unscripted by Hyatt', 1, '18:05'),
    ('pqcph', '파크 하얏트 푸꾸옥', '푸꾸옥', 'Park Hyatt', 7, '19:35'),
    ('vn104', '윙크 껀터 센터', '껀터', 'Unscripted by Hyatt', 1, '18:05'),
]

ID_CODES = [p[0] for p in PLAN[:14]]
VN_CODES = [p[0] for p in PLAN[14:]]

# ── 인도네시아 카드 메모 ────────────────────────────────────────────────
CASH_NULL = '현금 요금은 365일 전부 null — 공홈 현금가 미수집(공홈 현금 캘린더 없음·세금 포함 표기 없음).'
NYEPI = ('2027-03-07~03-08 두 날은 발리 전역이 녜피(Nyepi · 침묵의 날)로 판매가 없습니다'
         '(공홈 고지문 「2027년 3월 8일 출발은 발리의 침묵의 날로 이용이 불가합니다」 · '
         '발리 5곳 모두 같은 두 날짜가 응답에서 빠짐 · 좁은 창 재조회 동일).')

NOTE_ID = {
    'jakgh': '스탠다드 아워드 365일 실측(2026-11-26 18:01 KST · hyatt.com · 인도네시아 자카르타) — '
             '포인트 364일 · 값 없는 1일(2026-12-31)은 응답에 날짜 키가 없는 날(no_key_in_response)로 '
             '매진·어워드 미개방 구분이 안 돼 보간 없이 —입니다(좁은 창 재조회 동일). '
             '12,000P OFF_PEAK 256일 · 15,000P STANDARD 70일 · 8,000P SUPER_OFF_PEAK 38일 순입니다. '
             '카테고리 3(Grand Hyatt). ' + CASH_NULL,
    'cgkph': '스탠다드 아워드 365일 실측(2026-11-26 18:01 KST · hyatt.com · 인도네시아 자카르타) — '
             '포인트 364일 · 값 없는 1일(2026-12-01)은 응답에 날짜 키가 없는 날(no_key_in_response)로 '
             '보간 없이 —입니다(좁은 창 재조회 동일). 12,000P OFF_PEAK 255일 · 15,000P STANDARD 71일 · '
             '8,000P SUPER_OFF_PEAK 38일 순입니다. 카테고리 3(Park Hyatt). ' + CASH_NULL,
    'cgkub': '스탠다드 아워드 365일 실측(2026-11-26 18:01 KST · hyatt.com · 인도네시아 자카르타) — '
             '포인트 364일 · 값 없는 1일(2026-12-31)은 응답에 날짜 키가 없는 날(no_key_in_response)로 '
             '보간 없이 —입니다(좁은 창 재조회 동일). 20,000P OFF_PEAK 256일 · 25,000P STANDARD 70일 · '
             '15,000P SUPER_OFF_PEAK 38일 순입니다. 카테고리 5(Unbound Collection · 케라톤 앳 더 플라자). '
             + CASH_NULL,
    'balgh': '스탠다드 아워드 365일 실측(2026-11-26 18:01 KST · hyatt.com · 인도네시아 발리 누사두아) — '
             '포인트 168일 · 값 없는 197일 가운데 191일은 날짜 키는 있으나 그날 응답에 스탠다드룸이 없고 '
             '스위트 등 상위 등급만 표시된 날(empty_day_object), 6일은 응답에 날짜 키가 없는 날'
             '(no_key_in_response)입니다. 스탠다드룸 어워드가 긴 구간 비어 있어(2026-12-02~12-25 · '
             '12-28~2027-01-24 · 2027-03-01~31 · 04-02~16 · 05-01~22 · 06-21~07-15 등) 보간 없이 '
             '—입니다(2027-06-04~05·07·09 는 CLUB 만 표출 확인 · 좁은 창 재조회 동일). '
             '12,000P OFF_PEAK 106일 · 15,000P STANDARD 58일 · 8,000P SUPER_OFF_PEAK 4일 순입니다. '
             '카테고리 3(Grand Hyatt). ' + CASH_NULL,
    'dpsbl': '스탠다드 아워드 365일 실측(2026-11-26 17:57 KST · hyatt.com · 인도네시아 발리 사누르) — '
             '포인트 316일 · 값 없는 49일은 날짜 키는 있으나 스탠다드룸이 없는 날 45일(empty_day_object)과 '
             '날짜 키가 없는 날 4일(no_key_in_response)로, 매진·어워드 미개방 구분이 안 돼 보간 없이 '
             '—입니다(±1~2일 좁은 창 16개 재조회 동일). ' + NYEPI +
             ' 12,000P OFF_PEAK 214일 · 15,000P STANDARD 86일 · 8,000P SUPER_OFF_PEAK 16일 순입니다. '
             '카테고리 3(Hyatt Regency). ' + CASH_NULL,
    'dpsau': '스탠다드 아워드 365일 실측(2026-11-26 17:57 KST · hyatt.com · 인도네시아 발리 우붓) — '
             '포인트 360일 · 값 없는 5일(2027-03-07~03-08 · 04-13~04-15)은 모두 응답에 날짜 키가 없는 날'
             '(no_key_in_response)로 보간 없이 —입니다(좁은 창 재조회 동일). 03-07~08 은 녜피(침묵의 날) '
             '휴장입니다. 20,000P STANDARD 166일 · 15,000P OFF_PEAK 139일 · 12,000P SUPER_OFF_PEAK 55일 '
             '순입니다. 카테고리 4(Alila). ' + CASH_NULL,
    'dpsas': '스탠다드 아워드 365일 실측(2026-11-26 17:57 KST · hyatt.com · 인도네시아 발리 스미냑) — '
             '포인트 354일 · 값 없는 11일(2026-12-02~03 · 12-08~09 · 12-25 · 12-30~2027-01-01 · '
             '2027-03-07~08 · 2027-08-15)은 날짜 키 없음 6일과 날짜 키는 있으나 스탠다드룸이 없는 날 5일로, '
             '보간 없이 —입니다(좁은 창 재조회 동일). 2027-08-15 는 스탠다드 스위트 40,000P · 프리미엄 '
             '스위트 45,000P 만 표출돼 스탠다드룸 어워드만 소진된 것이 확인됐습니다. 03-07~08 은 녜피 휴장. '
             '25,000P OFF_PEAK 250일 · 30,000P STANDARD 35일 · 20,000P SUPER_OFF_PEAK 69일 순입니다. '
             '카테고리 6(Alila). ' + CASH_NULL,
    'dpsat': '스탠다드 아워드 365일 실측(2026-11-26 17:57 KST · hyatt.com · 인도네시아 발리 스미냑) — '
             '포인트 355일 · 값 없는 10일(2026-12-20~22 · 12-26 · 2027-01-01 · 01-04~05 · 03-07~08 · '
             '07-06)은 전부 응답에 날짜 키가 없는 날(no_key_in_response)로 보간 없이 —입니다'
             '(좁은 창 재조회 동일). 03-07~08 은 녜피 휴장. 7,500P OFF_PEAK 248일 · 10,000P STANDARD '
             '36일 · 6,000P SUPER_OFF_PEAK 71일 순입니다. 카테고리 2(JdV by Hyatt · 클레오 스미냑). '
             + CASH_NULL,
    'dpsav': '스탠다드 아워드 365일 실측(2026-11-26 17:57 KST · hyatt.com · 인도네시아 발리 울루와투) — '
             '포인트 339일 · 값 없는 26일은 전부 응답에 날짜 키가 없는 날(no_key_in_response)로 '
             '(2026-12-01·03~04 · 12-23 · 12-30~2027-01-01 · 2027-01-20 · 03-07~08 · 04-24~25 · '
             '05-08~09 · 05-21~22 · 05-26~28 · 07-09~10 · 07-30~08-01 · 09-17~18) 보간 없이 —입니다'
             '(좁은 창 재조회 동일). 03-07~08 은 녜피 휴장. 45,000P OFF_PEAK 146일 · 55,000P STANDARD '
             '133일 · 35,000P SUPER_OFF_PEAK 60일 순입니다. 카테고리 8(Alila Villas). ' + CASH_NULL,
    'dpsak': '스탠다드 아워드 365일 실측(2026-11-26 18:01 KST · hyatt.com · 인도네시아 발리 카랑아셈) — '
             '포인트 337일 · 값 없는 28일은 날짜 키 없음 12일과 날짜 키는 있으나 스탠다드룸이 없는 날 16일로 '
             '(2026-12-08 · 12-12 · 12-14 · 12-17 · 12-20~21 · 12-24 · 2027-01-01 · 01-26~27 · '
             '02-08~09 · 03-07~08 · 03-12~13 · 03-15~17 · 05-01~02 · 05-25~26 · 06-25~27 · 07-02~03) '
             '보간 없이 —입니다(좁은 창 재조회 동일). 03-07~08 은 녜피 휴장. 7,500P OFF_PEAK 231일 · '
             '10,000P STANDARD 37일 · 6,000P SUPER_OFF_PEAK 69일 순입니다. 카테고리 2(Alila Manggis · '
             '발리 동부 망기스). ' + CASH_NULL,
    'yogya': '스탠다드 아워드 365일 실측(2026-11-26 17:53 KST · hyatt.com · 인도네시아 족자카르타) — '
             '포인트 346일 · 값 없는 19일(2026-12-19 · 12-24~26 · 12-30~31 · 2027-01-21 · '
             '2027-07-08~13 · 07-15~20)은 날짜 키 없음 7일과 스탠다드룸이 없는 날 12일로, 보간 없이 '
             '—입니다(좁은 창 재조회 동일 · 7월 중순 13일은 연속 결번). '
             '4,500P OFF_PEAK 251일 · 6,000P STANDARD 50일 · 3,000P SUPER_OFF_PEAK 45일 순입니다. '
             '카테고리 1(Hyatt Regency). ' + CASH_NULL,
    'socal': '스탠다드 아워드 365일 실측(2026-11-26 17:53 KST · hyatt.com · 인도네시아 수라카르타) — '
             '포인트 364일 · 값 없는 1일(2026-12-31)은 날짜 키는 있으나 스탠다드룸이 없는 날'
             '(empty_day_object)로 보간 없이 —입니다(앞뒤 12-30·01-01 은 6,000P STANDARD 확인). '
             '4,500P OFF_PEAK 252일 · 6,000P STANDARD 47일 · 3,000P SUPER_OFF_PEAK 65일 순입니다. '
             '카테고리 1(Alila Solo). ' + CASH_NULL,
    'upgzm': '스탠다드 아워드 365일 실측(2026-11-26 17:53 KST · hyatt.com · 인도네시아 마카사르) — '
             '포인트 365일 전부 값이 있습니다(결번 0일). 4,500P OFF_PEAK 271일 · 6,000P STANDARD 65일 · '
             '3,000P SUPER_OFF_PEAK 28일 · 9,000P SUPER_PEAK 1일(2026-12-31) 순입니다. '
             '카테고리 1(Hyatt Place). ' + CASH_NULL,
    'dpaal': '알릴라 푸르나마는 46m 프리니시(Phinisi) 라이브어보드로 스위트·전세 단위 판매이며 World of '
             'Hyatt 어워드 대상이 아닙니다(공홈 마스터 카테고리 없음 · woh 참여 false). hyatt.com 어워드 '
             '일자별 응답이 4개 창(2026-12-01~2027-01-14 · 2027-05-30~07-13 · 2027-06-01~06-30 los=3 · '
             '2027-10-12~11-25) 모두 「soldOutHotel」 을 돌려줘 포인트는 365일 전부 null(0칸)입니다. '
             '카테고리 없음(어워드 미참여). ' + CASH_NULL,
}

VN_PREFIX = {
    '18:05': '스탠다드 아워드 365일 실측(2026-11-26 18:05 KST · hyatt.com · 베트남',
    '18:25': '스탠다드 아워드 365일 실측(2026-11-26 18:25 KST · hyatt.com · 베트남',
    '19:35': '스탠다드 아워드 365일 실측(2026-11-26 19:35 KST · hyatt.com · 베트남',
}
VN_CITY_KR = {
    'saiph': '호찌민', 'vn100': '호찌민', 'vn101': '다낭', 'vn102': '다낭', 'vn106': '하노이',
    'hanct': '하노이', 'vn105': '하이퐁', 'vdorh': '하롱', 'vdozh': '하롱', 'cxrrn': '나트랑',
    'vn103': '투이호아', 'pqcph': '푸꾸옥', 'vn104': '껀터',
}
# 베트남 원본 메모에 덧붙일 우리 표기 정정·보충
VN_EXTRA = {
    'vn103': ' ※ 공홈 마스터의 도시 표기는 「Dak Lak」 이고 2025년 푸옌성이 닥락성으로 통합돼 주소도 '
             '닥락성으로 적히지만, 실제 소재지는 투이호아시(1 Dien Bien Phu, Ward 7, Tuy Hoa)라 '
             '카드 도시를 투이호아로 적었습니다.',
    'vdozh': ' ※ 공홈 마스터의 도시 표기는 「Quang Ninh」 이지만 실제 소재지가 하롱베이 바이차이'
             '(꽝닌성 하롱시)라 카드 도시를 하롱으로 적었습니다.',
    'vdorh': ' ※ 공홈 마스터의 도시 표기는 「Ha Long」 이라 카드 도시를 하롱으로 적었습니다.',
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
    for name in ('0-hyatt-indonesia-batch1.json', '0-hyatt-indonesia-batch2.json',
                 '0-hyatt-indonesia-batch3.json'):
        d = json.load(open(os.path.join(ID_DIR, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30'
        for code, h in d['hotels'].items():
            assert code not in hotels, code
            hotels[code] = h
    for name in ('0-hyatt-vietnam-batch1-4.json', '0-hyatt-vietnam-batch2-4.json',
                 '0-hyatt-vietnam-batch3-5.json'):
        d = json.load(open(os.path.join(VN_DIR, name), encoding='utf-8'))
        assert d['window'] == {'start': '2026-12-01', 'end': '2027-11-30', 'days': 365}, d['window']
        for h in d['hotels']:
            assert h['code'] not in hotels, h['code']
            hotels[h['code']] = h
    assert len(hotels) == 27, len(hotels)
    return hotels


def pts_of(h):
    """배치본의 points(날짜 dict) → 365칸 리스트. 없으면 0칸."""
    raw = h.get('points') or {}
    return [raw.get(d) for d in DATES]


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 350, len(before)
    assert before[-1]['id'] == 'hy350', before[-1]['id']

    hotels = load_bundles()
    assert set(hotels) == set(ID_CODES) | set(VN_CODES), sorted(hotels)

    # ── 공홈 마스터 대조 ────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    for code, kr, city, brand, cat, _ in PLAN:
        m = byc[code]
        h = hotels[code]
        assert norm(m['name']) == norm(h['name']), (code, m['name'], h['name'])
        assert m['area'] == '동남아', (code, m['area'])
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert str(cat) == str(h['category']), (code, cat, h['category'])
        assert clean(h['brand']) == clean(brand) == clean(m['brand']), (code, h['brand'], brand, m['brand'])
        if code in ('hanct', 'dpaal'):
            assert m['woh_participating'] is False, code
        else:
            assert m['woh_participating'] is True, code

    # ── 기존 350곳 중복 확인 ────────────────────────────────────────
    exist_codes = {x['code']: x['id'] for x in before}
    exist_names = {}
    for x in before:
        exist_names.setdefault(norm(x['english']), []).append(x['id'])
    exist_kr = {}
    for x in before:
        exist_kr.setdefault(norm_ko(x['name']), []).append(x['id'])
    exist_tokens = {x['id']: set(norm(x['english']).split()) for x in before}
    for code, kr, city, brand, cat, _ in PLAN:
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
    for code, kr, city, brand, cat, _ in PLAN:
        h = hotels[code]
        if norm(h['name']) in by_eng:
            overlaps.append(('english', code, by_eng[norm(h['name'])]))
        if norm_ko(kr) in by_kr:
            overlaps.append(('korean', code, by_kr[norm_ko(kr)]))
    assert not overlaps, overlaps
    # ① 탭 지점이 있는 도시와 겹치는 후보(나트랑 3곳이 유일) — 이름으로 겹침 0 재확인
    print('① 호텔럭스 도시:', {k: v for k, v in by_city.items() if k in ('다낭', '나트랑')})
    for code in ('cxrrn',):
        assert norm(hotels[code]['name']) != 'six senses ninh van bay'
    print('① 호텔럭스 161곳 대조 — 겹침 0곳')

    added = []
    for i, (code, kr, city, brand, cat, tm) in enumerate(PLAN):
        hid = 'hy%d' % (FIRST_ID + i)
        info = hotels[code]
        pts = pts_of(info)
        assert len(pts) == 365
        priced = sum(1 for v in pts if v is not None)
        assert all(v is None or isinstance(v, int) for v in pts)

        if code in ID_CODES:
            note = NOTE_ID[code]
        else:
            note = '%s %s) — %s%s' % (VN_PREFIX[tm], VN_CITY_KR[code],
                                      clean(info.get('note') or '').rstrip(), VN_EXTRA.get(code, ''))
        entry = {
            'id': hid,
            'group': 'hyatt',
            'code': code,
            'region': '동남아',
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
            'note': note,
        }
        added.append(entry)
        print('%s %-6s %-30s %-8s Cat %-4s %3d일' % (hid, code, kr, city, cat, priced))

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-26'
    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    hs = tab['hotels']
    cells = sum(len(h['points']['$v']) for h in hs)
    priced = sum(1 for h in hs for v in h['points']['$v'] if v is not None)
    sea = [h for h in hs if h['region'] == '동남아']
    print('hotels', len(hs), 'cells', cells, 'priced', priced, '동남아', len(sea))
    assert len(hs) == 377 and cells == 377 * 365
    assert len(sea) == 37
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)


if __name__ == '__main__':
    main()
