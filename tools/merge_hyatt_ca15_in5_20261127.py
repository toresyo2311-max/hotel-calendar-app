#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 캐나다 20 + 인도 2차 5 = 25곳 병합 (2026-11-27) 515 → 540곳

입력 (모두 2026-12-01~2027-11-30 365칸)
  · 7번(@no_7) 캐나다 1차 5 (yycza · calrc · yegzw · yvrzb · ykazk)
      memory/clones/a03363f4-no71/pickle/2026-11-27-0508/received/0-hyatt_ca_batch1_5.json
  · 7번(@no_7) 캐나다 2차 5 (ylwzk · ylwub · yxszp · yvrrv · yvrph)
      memory/clones/a03363f4-no71/pickle/2026-11-27-0505/received/0-hyatt_ca_batch2_5.json
  · 7번(@no_7) 캐나다 3차 5 (ywgct · ywgxw · yqmzm · yyzzb · yyzxh)
      memory/clones/a03363f4-no71/pickle/2026-11-27-0517/received/0-hyatt_ca_batch3_5.json
      (avail/days · STANDARD_ROOM · 성인2·1박 · 60일 창 6 + 5일 창 1)
  · 7번(@no_7) 캐나다 4차(마지막) 5 (yyzzh · caaab · yyzjd · yyzxa · yyzza)
      memory/clones/a03363f4-no71/pickle/2026-11-27-0520/received/0-hyatt_ca_batch4_5.json
      (avail/days · STANDARD_ROOM · 성인2·1박 · 60일 창 6 + 5일 창 1)
  · 6번(@jin_6) 인도 2차 배치1 5 (atqhy · blrch · blrhy · hbxzh · blrcb)
      memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0511/received/0-hyatt-in2-batch1-5.json
      (hyatt.com 포인트 캘린더 · Standard Room · 1박 · 성인2인·1실 · 56일 이하 7구간)

■ 규칙
- 마스터(1-hyatt-global-master.json)의 20개 spiritCode 와 이름·카테고리·브랜드·WoH 참여를 대조.
  카드 region 은 마스터 area 를 그대로 쓴다 — 캐나다 → '캐나다'(마스터도 캐나다 별도 area,
  이 탭 첫 캐나다 지점) / 인도 → '남아시아'.
- 기존 515곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조.
- category 는 마스터 값 그대로(정수 또는 null). ykazk·ywgct·yyzxh 는 WoH 미참여라 null.
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 네 배치 모두 현금가 미수집.
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
CA1 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0508/received')
CA2 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0505/received')
CA3 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0517/received')
CA4 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0520/received')
IN2 = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0511/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START, END = '2026-12-01', '2027-11-30'
_d0, _d1 = date(2026, 12, 1), date(2027, 11, 30)
DATES = [(_d0 + timedelta(days=i)).isoformat() for i in range((_d1 - _d0).days + 1)]
assert len(DATES) == 365

FIRST_ID = 516

# (code, 국문명, 도시, 브랜드, 카테고리, region, 묶음)
PLAN = [
    # ── 캐나다 1차 5곳 — 7번(@no_7) · 2026-11-27 04:51~05:07 KST
    ('yycza', '하얏트 플레이스 캘거리 에어포트', '캘거리', 'Hyatt Place', 2, '캐나다', 'CA1'),
    ('calrc', '하얏트 리젠시 캘거리', '캘거리', 'Hyatt Regency', 3, '캐나다', 'CA1'),
    ('yegzw', '하얏트 플레이스 에드먼턴 웨스트', '에드먼턴', 'Hyatt Place', 2, '캐나다', 'CA1'),
    ('yvrzb', '하얏트 플레이스 밴쿠버 메트로타운', '버너비', 'Hyatt Place', 4, '캐나다', 'CA1'),
    ('ykazk', '하얏트 플레이스 캠룹스', '캠룹스', 'Hyatt Place', None, '캐나다', 'CA1'),
    # ── 캐나다 2차 5곳 — 7번(@no_7) · 2026-11-27 04:52~05:04 KST
    ('ylwzk', '하얏트 플레이스 켈로나', '켈로나', 'Hyatt Place', 2, '캐나다', 'CA2'),
    ('ylwub', '스피릿 리지', '오소요스', 'The Unbound Collection by Hyatt', 4, '캐나다', 'CA2'),
    ('yxszp', '하얏트 플레이스 프린스 조지', '프린스 조지', 'Hyatt Place', 1, '캐나다', 'CA2'),
    ('yvrrv', '하얏트 리젠시 밴쿠버', '밴쿠버', 'Hyatt Regency', 5, '캐나다', 'CA2'),
    ('yvrph', '하얏트 밴쿠버 다운타운 알베르니', '밴쿠버', 'Hyatt Hotels', 7, '캐나다', 'CA2'),
    # ── 캐나다 3차 5곳 — 7번(@no_7) · 2026-11-27 05:05~05:16 KST
    ('ywgct', '하얏트 센트릭 다운타운 위니펙', '위니펙', 'Hyatt Centric', None, '캐나다', 'CA3'),
    ('ywgxw', '하얏트 하우스 위니펙 사우스 아울렛 컬렉션', '위니펙', 'Hyatt House', 2, '캐나다', 'CA3'),
    ('yqmzm', '하얏트 플레이스 멍크턴 다운타운', '멍크턴', 'Hyatt Place', 2, '캐나다', 'CA3'),
    ('yyzzb', '하얏트 플레이스 토론토 브램턴', '브램턴', 'Hyatt Place', 2, '캐나다', 'CA3'),
    ('yyzxh', '하얏트 하우스 해밀턴 맥마스터 이노베이션 파크', '해밀턴', 'Hyatt House', None, '캐나다', 'CA3'),
    # ── 캐나다 4차(마지막) 5곳 — 7번(@no_7) · 2026-11-27 05:09~05:19 KST
    ('yyzzh', '하얏트 플레이스 해밀턴 맥마스터 이노베이션 파크', '해밀턴', 'Hyatt Place', None, '캐나다', 'CA4'),
    ('caaab', '하얏트 셀렉트 킹스턴', '킹스턴', 'Hyatt Select', 2, '캐나다', 'CA4'),
    ('yyzjd', '더 월퍼 호텔', '키치너', 'JdV by Hyatt', 3, '캐나다', 'CA4'),
    ('yyzxa', '하얏트 하우스 미시소가 에어포트 코퍼레이트 센터', '미시소가', 'Hyatt House', 2, '캐나다', 'CA4'),
    ('yyzza', '하얏트 플레이스 미시소가 에어포트 코퍼레이트 센터', '미시소가', 'Hyatt Place', 2, '캐나다', 'CA4'),
    # ── 인도 2차 배치1 5곳 — 6번(@jin_6) · 2026-11-27 05:01~05:10 KST
    ('atqhy', '하얏트 리젠시 암리차르 호텔 앤 스파', '암리차르', 'Hyatt Regency', 1, '남아시아', 'IN2'),
    ('blrch', '하얏트 센트릭 헤발 벵갈루루', '방갈로르', 'Hyatt Centric', 2, '남아시아', 'IN2'),
    ('blrhy', '하얏트 센트릭 엠지 로드 방갈로르', '방갈로르', 'Hyatt Centric', 2, '남아시아', 'IN2'),
    ('hbxzh', '하얏트 플레이스 함피', '함피', 'Hyatt Place', 1, '남아시아', 'IN2'),
    ('blrcb', '하얏트 센트릭 벵갈루루 에어포트', '방갈로르', 'Hyatt Centric', 2, '남아시아', 'IN2'),
]

PROVIDER = {'CA1': '7번(@no_7)', 'CA2': '7번(@no_7)', 'CA3': '7번(@no_7)', 'CA4': '7번(@no_7)',
            'IN2': '6번(@jin_6)'}
WHEN = {'CA1': '2026-11-27 04:51~05:07 KST', 'CA2': '2026-11-27 04:52~05:04 KST',
        'CA3': '2026-11-27 05:05~05:16 KST', 'CA4': '2026-11-27 05:09~05:19 KST',
        'IN2': '2026-11-27 05:01~05:10 KST'}

CASH = {
    'CA': ('현금 요금은 365일 전부 —입니다 — 이 엔드포인트는 어워드 포인트만 주고 현금가는 다른 '
           '경로라 미수집입니다(rate 는 표출일 전부 null). 호럭 요금도 미수집입니다.'),
    'IN': ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아(1박 단위 '
           'shop/rooms 화면에서만 표시) 현금가는 미수집이고, 위에 적은 현금 금액은 같은 날짜대의 공홈 '
           '1박 검색에서 확인한 참고값입니다. 호럭 요금도 미수집입니다.'),
}

# 호텔별 보강 — 배치본 note 에 있는 사실만 옮겨 적는다
EXTRA = {
    'yycza': ('STANDARD_ROOM 5단계가 모두 표출된다 — SUPER_OFF_PEAK 6,000(70일) · OFF_PEAK '
              '7,500(218일) · STANDARD 10,000(65일) · PEAK 12,000(4일: 2027-07-04 · 07-08~10) · '
              'SUPER_PEAK 15,000(5일: 2027-07-02~03 · 07-05~07). 공백 3일(2027-05-21~22 · 06-09)은 '
              '날짜 키 자체가 없는 no_key_in_response 로, 2027-05-19~25 · 06-07~11 두 창 재조회에서 '
              '같은 형태로 재현됐다(창에 함께 든 표출일 9일 값·레벨 동일).'),
    'calrc': ('이 배치에서 공백이 가장 많다 — 79일이 모두 empty_day_object(날짜 키는 있으나 '
              'STANDARD_ROOM 없음)로 빈 {} 46일 · 다른 객실 카테고리(CLUB · STANDARD_SUITE · '
              'PREMIUM_SUITE)만 있는 날 32일이고, 2027-03-10 하루만 날짜 키가 없다. 공백이 요일·연속 '
              '구간에 몰리지 않고 1년 내내 흩어져 있으며 가장 긴 공백은 2027-06-26~07-05(10일)이고 '
              '4일짜리 공백이 2027-02-06~09 · 05-31~06-03 · 06-20~23 · 07-12~15 네 번 있다. '
              'STANDARD_ROOM 은 SUPER_OFF_PEAK 8,000(76일) · OFF_PEAK 12,000(148일) · STANDARD '
              '15,000(57일) · PEAK 17,500(2일) · SUPER_PEAK 20,000(3일) 5단계다.'),
    'yegzw': ('STANDARD_ROOM 은 OFF_PEAK 7,500(335일) · STANDARD 10,000(25일) · PEAK 12,000(2일: '
              '2027-07-16~17) 3단계만 표출되고 SUPER_OFF_PEAK·SUPER_PEAK 은 1년 내내 한 번도 나오지 '
              '않는다(1년의 92%가 OFF_PEAK 단일가). 공백 3일(2027-05-28~30)은 날짜 키가 없는 '
              'no_key_in_response 로 2027-05-26~06-01 창 재조회에서 같은 형태로 재현됐다.'),
    'yvrzb': ('STANDARD_ROOM 은 SUPER_OFF_PEAK 12,000(46일) · OFF_PEAK 15,000(133일) · STANDARD '
              '20,000(181일) 3단계만 표출되고 PEAK·SUPER_PEAK 은 없다. 2027-04-24~05-15(22일)와 '
              '2027-05-17~10-02(139일)가 STANDARD 로 봄~여름 성수기 대부분이 최고 레벨이다. 공백 '
              '5일(2026-12-01 · 12-05 · 12-12 · 12-19 · 12-25)은 모두 날짜 키가 없는 '
              'no_key_in_response 로 2026-11-29~12-27 창 재조회에서 같은 형태로 재현됐다.'),
    'ykazk': ('공홈 호텔 페이지(/hyatt-place/en-US/ykazk-hyatt-place-kamloops)의 예약 버튼이 '
              '「Coming Soon」[disabled]로 개관 전·예약 불가 상태이고(주소 1270 Rogers Way, '
              'Kamloops, BC V1S 1N5), 7개 창 모두 응답 본문이 {"days":{},"responseInfo":'
              '"soldOutHotel"} 41바이트로 완전히 같아 날짜별 데이터가 없다. 카테고리도 인계 목록·'
              '페이지 모두 표기가 없어 null(월드 오브 하얏트 미참여)이다. 추정·보간 없음.'),
    'ylwzk': ('365일 전부 표출(공백 0일)되어 재조회 대상 null 이 없다. STANDARD_ROOM 5단계가 1년 '
              '내내 표출된다 — SUPER_OFF_PEAK 6,000(208일) · OFF_PEAK 7,500(52일) · STANDARD '
              '10,000(87일) · PEAK 12,000(16일) · SUPER_PEAK 15,000(2일: 2027-07-31~08-01). 최장 '
              '단일 구간은 SUPER_OFF_PEAK 2027-01-01~04-02(92일)다.'),
    'ylwub': ('STANDARD_ROOM 은 SUPER_OFF_PEAK 12,000(191일) · OFF_PEAK 15,000(17일) · STANDARD '
              '20,000(10일) 3단계뿐이고 STANDARD 는 2026-12-22~12-31 연말 10일에만 나온다. 공백 '
              '147일은 모두 날짜 키가 없는 no_key_in_response 로 2027-05-11~10-02 145일 연속과 '
              '2027-04-03 · 04-10 각 1일이며, 2027-05-30~07-28 · 07-29~09-26 두 창은 응답 '
              'top-level 에 responseInfo=soldOutHotel 이 붙어 그 120일이 페이지 자체 매진으로 '
              '응답했다(4개 창 재조회에서 147일 공백과 표출일 218일 값이 모두 동일).'),
    'yxszp': ('STANDARD_ROOM 은 SUPER_OFF_PEAK 3,000(69일) · OFF_PEAK 4,500(217일) · STANDARD '
              '6,000(74일) 3단계뿐이고 1년의 60%가 OFF_PEAK 다. 공백 5일(2027-01-18~20 · 03-21 · '
              '03-25)은 날짜 키가 없는 no_key_in_response 로 ±2일 버퍼 창 재조회에서 같은 형태로 '
              '재현됐다.'),
    'yvrrv': ('STANDARD_ROOM 은 SUPER_OFF_PEAK 15,000(42일) · OFF_PEAK 20,000(117일) · STANDARD '
              '25,000(149일) 3단계뿐이고 도심 상업호텔이라 STANDARD 비중이 가장 크다(최장 '
              '2027-07-03~08-04 33일 · 08-22~09-14 24일). 공백 57일은 26개 구간으로 짧게 흩어져 '
              '있고(최장 2027-05-31~06-05 6일) empty_day_object 12일 · no_key_in_response 45일이다.'),
    'yvrph': ('STANDARD_ROOM 은 SUPER_OFF_PEAK 25,000(16일) · OFF_PEAK 30,000(70일) · STANDARD '
              '35,000(168일) 3단계뿐이다. 공백이 가장 많은 111일(empty_day_object 94 · '
              'no_key_in_response 17)이고, 가장 큰 공백은 2027-01-15~03-31 76일 연속(그중 74일이 '
              '빈 {}, 2027-03-03~04 는 날짜 키 없음)이며 2026-12-01~12-20 에도 13일이 비어 있다. '
              '표출일은 2026-12-22~12-31 연말 10일이 최고 구간이고 2027-08-22~10-02(42일) · '
              '06-27~07-26(30일)이 연속 STANDARD 다.'),
    'ywgct': ('365일 중 238일이 공백이고 첫 표출일이 2027-07-27 이다 — 2026-12-01~2027-07-26 중 '
              '180일은 응답이 {"days":{},"responseInfo":"soldOutHotel"} 뿐인 호텔 단위 매진 '
              '응답이고 58일은 날짜 키가 없었다. 2027-07-27 이전은 예약 미개방으로 어워드 '
              '인벤토리가 없고 이 날부터 표출이 시작된다. 표출 127일은 SUPER_OFF_PEAK 8,000(24일) '
              '· OFF_PEAK 12,000(76일) · STANDARD 15,000(27일) 3단계다. 호텔 페이지(325 Broadway, '
              'Winnipeg, 140실)에 「Booking Notice」 배너가 붙어 있고 카테고리 표기가 없어 '
              'null(월드 오브 하얏트 미참여)이다.'),
    'ywgxw': ('STANDARD_ROOM 은 SUPER_OFF_PEAK 6,000(71일) · OFF_PEAK 7,500(180일) · STANDARD '
              '10,000(109일) 3단계뿐이고 최장 STANDARD 구간은 2027-06-30~07-28(29일)이다. 공백 '
              '5일은 2026-12-03(날짜 키 없음)과 빈 오브젝트 4일(2026-12-08 · 12-11 · 12-15 · '
              '2027-02-12 로 12-08·12-15 는 스위트만, 12-11·02-12 는 빈 {})이다. STANDARD_SUITE'
              '(11,000~15,000) · PREMIUM_SUITE(13,000~17,000)도 함께 표출됐으나 채택값은 '
              'STANDARD_ROOM 만이다.'),
    'yqmzm': ('STANDARD_ROOM 만 3단계(SUPER_OFF_PEAK 6,000 67일 · OFF_PERK 7,500 126일 · STANDARD '
              '10,000 159일)로 표출된다. 공백 13일은 모두 날짜 키가 없는 no_key_in_response 로 6개 '
              '구간(2026-12-05 · 12-12 · 2027-02-14 각 1일, 2027-05-26~29 4일, 07-09~10 2일, '
              '08-26~29 4일)에 흩어져 있다. 여름 성수기 STANDARD 가 2027-07-29~08-25(28일) · '
              '09-02~09-19(18일)로 길게 이어진다.'),
    'yyzzb': ('365일 전부 표출(공백 0일)되어 재조회 대상 null 이 없다. STANDARD_ROOM 3단계'
              '(SUPER_OFF_PEAK 6,000 34일 · OFF_PEAK 7,500 175일 · STANDARD 10,000 156일)이고 '
              'PEAK·SUPER_PEAK 은 없다. 공항권 출장 수요가 커 주중 STANDARD·주말 OFF_PEAK 교차가 '
              '잦고 최장 STANDARD 구간은 2027-07-29~08-28(31일)이다.'),
    'yyzxh': ('365일 전부 어워드 표출이 없다 — 7개 창 가운데 6개 창(305일)이 {"days":{},'
              '"responseInfo":"soldOutHotel"} 뿐인 호텔 단위 매진 응답이고, 2027-09-27~11-25 창도 '
              '53일이 카테고리 없는 빈 {} · 7일이 날짜 키 없음이다. 호텔 페이지(180 Longwood Road '
              'South, Hamilton, 84실)에 「Booking Notice」 배너가 붙어 개관 준비·미판매 상태로 '
              '보이나 이 엔드포인트만으로는 매진과 미개방을 구분할 수 없어 응답 형태 그대로 '
              '기록했다. 카테고리 표기가 없어 null(월드 오브 하얏트 미참여)이다.'),
    'yyzzh': ('7개 창 모두 응답 본문이 {"days":{},"responseInfo":"soldOutHotel"}(41바이트)로 날짜 키가 '
              '하나도 없고, 재조회 7개 창에서도 365일 전부 같은 응답이 재현됐다. 호텔 페이지(180 '
              'Longwood Road South, Hamilton, ON L8P 0A1) 상단 「Booking Notice」는 「Now accepting '
              'reservations for stays from September 29, 2027 and beyond.」라 2027-09-29부터 숙박 '
              '예약을 받는 개관 예정 호텔이다 — 다만 그 개시일 이후(2027-09-29~11-30 63일)를 포함한 '
              '창에서도 어워드는 호텔 단위 soldOutHotel 로만 돌아와, 현금 예약 개시일과 어워드 '
              '인벤토리 로드는 별개임을 보여준다. 카테고리 표기가 없어 null(월드 오브 하얏트 '
              '미참여)이다. 추정·보간 없음.'),
    'caaab': ('364일 표출·1일 공백. STANDARD_ROOM 은 SUPER_OFF_PEAK 6,000(34일) · OFF_PEAK 7,500(175일) '
              '· STANDARD 10,000(155일) 3단계뿐이고 PEAK·SUPER_PEAK 은 없다. 여름 성수기 '
              '2027-06-30~08-28(60일 연속)과 연말 2026-12-22~12-31(10일)이 최고가 구간이다. 공백 '
              '1일은 2027-06-05 로 응답에 날짜 키가 없는 no_key_in_response 이며 ±2일 버퍼 창 '
              '(2027-06-03~07) 재조회에서 같은 형태로 재현됐다. Hyatt Select 는 신설 브랜드로 '
              '/hyatt-select/en-US/caaab-hyatt-select-kingston 페이지가 정상으로 열린다.'),
    'yyzjd': ('360일 표출·5일 공백. STANDARD_ROOM 은 SUPER_OFF_PEAK 8,000(45일) · OFF_PEAK 12,000(275일) '
              '· STANDARD 15,000(40일) 3단계뿐이고 1년의 76%가 OFF_PEAK 다. STANDARD 는 연말 '
              '2026-12-22~12-31(10일)을 비롯해 2027-04-16~17 · 05-21~22 같은 1~2일 블록으로 '
              '흩어져 있다. 공백 5일(2026-12-08 · 2027-02-07 · 05-06 · 08-13~14)은 모두 날짜 키가 '
              '없는 no_key_in_response 로 각 날짜 ±2일 창 4개 재조회에서 같은 형태로 재현됐다. '
              'STANDARD_SUITE(342일) · PREMIUM_SUITE(320일)도 함께 표출됐으나 채택값은 '
              'STANDARD_ROOM 만이다.'),
    'yyzxa': ('365일 전부 표출(공백 0일). STANDARD_ROOM 은 SUPER_OFF_PEAK 6,000(80일) · OFF_PEAK '
              '7,500(157일) · STANDARD 10,000(125일) · PEAK 12,000(3일: 2027-03-01 · 09-03~04) '
              '4단계이고 SUPER_PEAK 은 없다. 겨울 비수기 SUPER_OFF_PEAK 가 2027-01-10~02-27 '
              '(49일 연속), STANDARD 는 2027-06-07~07-02(26일) · 08-31~09-23(24일)로 길다. '
              'STANDARD_SUITE(356일)도 함께 표출됐으나 채택값은 STANDARD_ROOM 만이고, 같은 단지 '
              '자매 호텔 yyzza(Hyatt Place)와 365일 값·레벨이 전부 동일했다(불일치 0일).'),
    'yyzza': ('365일 전부 표출(공백 0일). STANDARD_ROOM 은 SUPER_OFF_PEAK 6,000(80일) · OFF_PEAK '
              '7,500(157일) · STANDARD 10,000(125일) · PEAK 12,000(3일: 2027-03-01 · 09-03~04) '
              '4단계이고 SUPER_PEAK 은 없다. 겨울 비수기 SUPER_OFF_PEAK 가 2027-01-10~02-27 '
              '(49일 연속), STANDARD 는 2027-06-07~07-02(26일) · 08-31~09-23(24일)로 길다. '
              'STANDARD_ROOM 단일 카테고리만 표출됐고, 같은 단지 자매 호텔 yyzxa(Hyatt House)와 '
              '365일 값·레벨이 전부 동일했다(불일치 0일 · 주소도 5100 Satellite Drive 로 같고 '
              '우편번호만 L4W 5A1/5B6).'),
    'atqhy': ('분포: 4,500P 275일 · 6,000P 55일 · 3,000P 28일 · null 7일. 4,500P(Standard)가 '
              '기본이고 6,000P(Peak)는 연말 2026-12-18~2027-01-02 와 2027-10~11 주말, '
              '3,000P(Off-peak)는 우기철 2027-05~07 에 몰린다. null 7일은 2027-02-02~03 · '
              '02-12~13 · 03-03~05 세 블록이고 모두 응답에 날짜 키가 없으며 CLUB·SUITE 대체 객실 '
              '어워드도 없었다 — 그 1박 스탠다드룸 어워드가 없는 날이다. 2026-12월 · 2027-02월 '
              '캘린더와 전 칸 대조해 일치했다.'),
    'blrch': ('분포: 7,500P 204일 · 10,000P 117일 · null 44일. 2027-02~03월은 금~일만 어워드를 '
              '열고 평일은 닫는 주 단위 개방 패턴이라 null 44일의 대부분이 평일 블록'
              '(2027-02-01~04 · 02-08~12 · 02-15~18 · 02-22~25 · 03-01~05 · 03-08~11 · '
              '03-15~18 · 03-22~25)에 집중된다. 2026-12월 · 2027-02월 캘린더와 전 칸 대조해 '
              '일치했고, 같은 달 주말에는 어워드가 정상 개방돼 휴관·판매중단이 아님을 확인했다.'),
    'blrhy': ('분포: 7,500P 192일 · 10,000P 134일 · null 39일. null 은 2026-12-01~04 · 12-08~09 · '
              '12-15~16 · 12-31 · 2027-01-26~27 과 2027-02-01~28 전일(28일)이다. 2027-02-05~06 '
              '1박 포인트 조회는 「No Available Rooms」였지만 같은 날짜 현금 뷰는 6실 최저 '
              '₩430,900(멤버 레이트)로 정상 판매 중이어서 휴관이 아닌 어워드 재고 미개방이다. '
              '2026-12-02 는 좁혀 재조회에서 soldOutHotel 응답이 왔지만 같은 날 현금 ₩290,835 로 '
              '판매 중이었다 — soldOutHotel 이 호텔 전체 판매중단을 뜻하지 않는 사례로, 그 날의 '
              'null 은 그 1박 스탠다드룸 어워드가 없는 날이다.'),
    'hbxzh': ('분포: 4,500P 292일 · 6,000P 43일 · 3,000P 7일 · 7,500P 2일(2026-12-26~27, 카테고리 '
              '상단보다 한 단계 높은 값) · null 21일. null 은 2026-12-03~04 · 12-11~12 · '
              '12-16~19 와 2027-01-25~02-06 13일 연속이고, 2027-02-01~02 포인트 조회는 「No '
              'Available Rooms」였으나 같은 날짜 현금 뷰는 4실 최저 ₩244,615(멤버)로 정상 판매 '
              '중이어서 휴관이 아닌 어워드 재고 미개방이다. 2026-12월 · 2027-01월 캘린더와 전 칸 '
              '대조해 일치했다.'),
    'blrcb': ('365일 전부 값이 있고 null 0일이다 — 7,500P 212일 · 10,000P 150일 · 12,000P '
              '3일(2027-02-08~10, 카테고리 상단 10,000P 보다 높은 피크 값). 10,000P(Standard)가 '
              '2026-12월 연말과 2027년 주중에 기본으로 깔리고 7,500P(Off-peak)는 주말 중심이다. '
              '2026-12월 캘린더와 전 칸 대조해 일치했다.'),
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
    hotels = {}

    def add(code, h, tag):
        assert code not in hotels, code
        hotels[code] = h

    for path, name, tag in (
            (CA1, '0-hyatt_ca_batch1_5.json', 'CA1'),
            (CA2, '0-hyatt_ca_batch2_5.json', 'CA2'),
            (CA3, '0-hyatt_ca_batch3_5.json', 'CA3'),
            (CA4, '0-hyatt_ca_batch4_5.json', 'CA4')):
        d = json.load(open(os.path.join(path, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30', (name, d['meta']['window'])
        for code, h in d['hotels'].items():
            add(code, dict(h, _tag=tag, _file=name), tag)
    d = json.load(open(os.path.join(IN2, '0-hyatt-in2-batch1-5.json'), encoding='utf-8'))
    assert d['window'] == {'start': '2026-12-01', 'end': '2027-11-30', 'days': 365}
    for h in d['hotels']:
        add(h['code'], dict(h, _tag='IN2', _file='0-hyatt-in2-batch1-5.json'), 'IN2')
    assert len(hotels) == 25, len(hotels)
    return hotels


def pts_of(h):
    raw = h.get('points') or {}
    if isinstance(raw, list):
        raw = dict(raw)
    return [raw.get(d) for d in DATES]


def head(tag, code, city, cat, priced):
    cat_txt = 'null' if cat is None else str(cat)
    if tag == 'IN2':
        return ('하얏트 공홈 포인트 캘린더(explore-hotels/rate-calendar · Standard Room · 1박 · '
                '성인2인·1실)로 2026-12-01~2027-11-30 365칸을 실측했다(%s · 6번(@jin_6) · %s · '
                '인도). 값은 캘린더 화면의 데이터 원천인 공홈 avail/days 응답'
                '(roomCategory=STANDARD_ROOM·los=1)에서 날짜별 STANDARD_ROOM pointsValue 를 '
                '읽었고, 조회는 56일 이하 7구간(총 35회)으로 나눠 정상 응답한 범위만 기록했다. '
                '공홈 표시 어워드 카테고리 %s이고 값이 있는 날은 %d일이다.'
                % (WHEN[tag], city, cat_txt, priced))
    return ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory='
            'STANDARD_ROOM · 성인2·1박)을 60일 창 6회 + 5일 창 1회로 나눠 2026-12-01~'
            '2027-11-30 365칸을 실측했다(%s · 7번(@no_7) · %s · 캐나다). 창은 모두 실제 페이지 '
            '로드로 응답 JSON 을 받아 파싱했고, null 구간은 앞뒤 표출일을 포함한 좁은 창으로 다시 '
            '조회해 값·레벨 불일치 0건을 확인했다. 공홈 표시 어워드 카테고리 %s이고 값이 있는 날은 '
            '%d일이다.' % (WHEN[tag], city, cat_txt, priced))


def build_note(tag, code, city, cat, priced):
    facts = [head(tag, code, city, cat, priced), EXTRA[code]]
    cash = CASH[tag[:2]]
    if '₩' not in ' '.join(facts):
        for clause in ('위에 적은 현금 금액은 같은 날짜대의 공홈 1박 검색에서 확인한 참고값입니다. ',):
            cash = cash.replace(clause, '')
    bits = facts + [cash, '%s이 실측해 보낸 본입니다.' % PROVIDER[tag]]
    note = ' '.join(bit for bit in bits if bit)
    note = ' '.join(note.split())
    # 개관 전 표기는 공홈이 Coming Soon 으로 밝힌 ykazk 에만 쓴다
    if code != 'ykazk':
        assert 'Coming Soon' not in note, code
    return note


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 515, len(before)
    assert before[-1]['id'] == 'hy515', before[-1]['id']

    hotels = load()
    assert set(hotels) == {p[0] for p in PLAN}, sorted(set(hotels) ^ {p[0] for p in PLAN})

    # ── 공홈 마스터 대조 ─────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    for code, kr, city, brand, cat, region, tag in PLAN:
        m, h = byc[code], hotels[code]
        assert norm(m['name']) == norm(h['name']), (code, m['name'], h['name'])
        assert m['area'] == region, (code, m['area'], region)
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert str(cat) == str(h['category']), (code, cat, h['category'])
        assert clean(h['brand']) == clean(brand) == clean(m['brand']), (code, h['brand'], brand, m['brand'])
        assert m['woh_participating'] is (cat is not None), (code, m['woh_participating'], cat)
        print('%-6s %-6s Cat %-4s WoH %-5s %s' % (code, region, m['category'],
                                                   m['woh_participating'], m['name']))

    # ── 기존 515곳 중복 확인 ─────────────────────────────────────────
    exist_codes = {x['code']: x['id'] for x in before}
    exist_names, exist_kr = {}, {}
    for x in before:
        exist_names.setdefault(norm(x['english']), []).append(x['id'])
        exist_kr.setdefault(norm_ko(x['name']), []).append(x['id'])
    exist_tokens = {x['id']: (set(norm(x['english']).split()), x['english']) for x in before}
    seen_en, seen_kr = {}, {}
    for code, kr, city, brand, cat, region, tag in PLAN:
        h = hotels[code]
        assert code not in exist_codes, ('code dup', code, exist_codes.get(code))
        assert not exist_names.get(norm(h['name'])), ('english dup', code, h['name'])
        assert not exist_kr.get(norm_ko(kr)), ('korean dup', code, kr, exist_kr.get(norm_ko(kr)))
        assert norm(h['name']) not in seen_en, ('batch english dup', code)
        assert norm_ko(kr) not in seen_kr, ('batch korean dup', code)
        seen_en[norm(h['name'])] = code
        seen_kr[norm_ko(kr)] = code
        toks = set(norm(h['name']).split())
        for hid, (et, en) in exist_tokens.items():
            assert not toks <= et, ('same hotel?', code, hid, en)
    print('기존 515곳 대조 — code·영문명·국문명 중복 0건')

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
    for code, kr, city, brand, cat, region, tag in PLAN:
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
    for i, (code, kr, city, brand, cat, region, tag) in enumerate(PLAN):
        hid = 'hy%d' % (FIRST_ID + i)
        info = hotels[code]
        pts = pts_of(info)
        assert len(pts) == 365
        assert all(v is None or (isinstance(v, int) and v > 0) for v in pts), code
        priced = sum(1 for v in pts if v is not None)
        if 'days_priced' in info:
            assert priced == info['days_priced'], (code, priced, info['days_priced'])
        note = build_note(tag, code, city, cat, priced)
        added.append({
            'id': hid, 'group': 'hyatt', 'code': code, 'region': region, 'city': city,
            'name': kr, 'english': clean(info['name']), 'brand': brand, 'category': cat,
            'vip_id': None, 'alsoIn': None, 'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None, 'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % code, 'hlx': None},
            'promotion': str(info.get('promotion')) if info.get('promotion') else None,
            'note': note,
        })
        print('%s %-6s %-5s %-8s %-32s Cat %-4s %3d일' %
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
    assert len(hs) == 540 and cells == 540 * 365, (len(hs), cells)
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['캐나다'] == 20 and reg['남아시아'] == 25 and reg['중동'] == 31 and reg['아프리카'] == 5
    assert reg['미국'] == 209 and reg['유럽'] == 128 and reg['동남아'] == 61 and reg['일본'] == 23
    assert reg['중국·중화권'] == 15 and reg['오세아니아'] == 14 and reg['한국'] == 9
    assert priced == 157551 + 7247, priced
    print('EXPECT_HYATT = {\'hotels\': %d, \'cells\': %d, \'priced\': %d}' % (len(hs), cells, priced))


if __name__ == '__main__':
    main()
