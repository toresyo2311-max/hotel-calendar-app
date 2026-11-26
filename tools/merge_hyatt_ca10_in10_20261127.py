#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 캐나다 2차 10 + 인도 2차 10 = 20곳 병합 (2026-11-27) 540 → 560곳

입력 (모두 2026-12-01~2027-11-30 365칸)
  · 7번(@no_7) 캐나다 2차 배치1 5 (yulza · yyzzm · yulct · yulzm · ca101)
      memory/clones/a03363f4-no71/pickle/2026-11-27-0540/received/0-hyatt_ca2_batch1_5.json
  · 7번(@no_7) 캐나다 2차 배치2 5 (iagub · yowaz · yowzo · yqtxt · tordh)
      memory/clones/a03363f4-no71/pickle/2026-11-27-0540/received/0-hyatt_ca2_batch2_5.json
      (avail/days · STANDARD_ROOM · 성인2·1박 · 60일 창 6 + 5일 창 1)
  · 6번(@jin_6) 인도 2차 배치2 5 (in102 · stvzb · bhozb · chenn · cheph)
      memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0527/received/0-hyatt-in2-batch2-5.json
  · 6번(@jin_6) 인도 2차 배치3 5 (ixuza · dedzd · delrh · dhmrm · dedzh)
      memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0541/received/0-hyatt-in2-batch3-5.json
      (hyatt.com 포인트 캘린더 · Standard Room · 1박 · 성인2인·1실 · 56일 이하 7구간)

■ 규칙
- 마스터(1-hyatt-global-master.json)의 20개 spiritCode 와 이름·카테고리·브랜드·WoH 참여를 대조.
  카드 region 은 마스터 area 그대로 — 캐나다 → '캐나다' / 인도 → '남아시아'.
- 기존 540곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳.
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 네 배치 모두 현금가 미수집.
- 링크는 기존 카드와 같이 공홈 예약 화면 https://www.hyatt.com/shop/rooms/{code}.
- 몬트리올 도시명은 '몬트리올'(영문 Montreal)로 통일한다 — yulzm 원자료의 Montréal 포함.
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
CA_D = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0540/received')
IN2_D = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0527/received')
IN3_D = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0541/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

_d0, _d1 = date(2026, 12, 1), date(2027, 11, 30)
DATES = [(_d0 + timedelta(days=i)).isoformat() for i in range((_d1 - _d0).days + 1)]
assert len(DATES) == 365

FIRST_ID = 541

# (code, 국문명, 도시, 브랜드, 카테고리, region, 묶음)
PLAN = [
    # ── 캐나다 2차 배치1 5곳 — 7번(@no_7) · 2026-11-27 05:4x~06:1x KST
    ('yulza', '하얏트 플레이스 몬트리올 에어포트', '도르발', 'Hyatt Place', 3, '캐나다', 'CA1'),
    ('yyzzm', '하얏트 플레이스 토론토 미시소가 센터', '미시소가', 'Hyatt Place', 2, '캐나다', 'CA1'),
    ('yulct', '하얏트 센트릭 몬트리올', '몬트리올', 'Hyatt Centric', 3, '캐나다', 'CA1'),
    ('yulzm', '하얏트 플레이스 몬트리올 다운타운', '몬트리올', 'Hyatt Place', 3, '캐나다', 'CA1'),
    ('ca101', '하얏트 리젠시 나이아가라 폴스 폴스뷰', '나이아가라 폴스', 'Hyatt Regency', 5, '캐나다', 'CA1'),
    # ── 캐나다 2차 배치2 5곳 — 7번(@no_7) · 2026-11-27 05:4x~06:1x KST
    ('iagub', '더 클레이필드', '나이아가라온더레이크', 'The Unbound Collection by Hyatt', 5, '캐나다', 'CA2'),
    ('yowaz', '안다즈 오타와 바이워드 마켓', '오타와', 'Andaz', 3, '캐나다', 'CA2'),
    ('yowzo', '하얏트 플레이스 오타와 웨스트', '오타와', 'Hyatt Place', 2, '캐나다', 'CA2'),
    ('yqtxt', '하얏트 하우스 선더베이', '선더베이', 'Hyatt House', 2, '캐나다', 'CA2'),
    ('tordh', '호텔 X 토론토', '토론토', 'Destination by Hyatt', 5, '캐나다', 'CA2'),
    # ── 인도 2차 배치2 5곳 — 6번(@jin_6) · 2026-11-27 05:11~05:24 KST
    ('in102', '하얏트 센트릭 화이트필드 벵갈루루', '방갈로르', 'Hyatt Centric', 2, '남아시아', 'IN2'),
    ('stvzb', '하얏트 플레이스 바루치', '바루치', 'Hyatt Place', 1, '남아시아', 'IN2'),
    ('bhozb', '하얏트 플레이스 보팔', '보팔', 'Hyatt Place', 1, '남아시아', 'IN2'),
    ('chenn', '하얏트 리젠시 첸나이', '첸나이', 'Hyatt Regency', 1, '남아시아', 'IN2'),
    ('cheph', '파크 하얏트 첸나이', '첸나이', 'Park Hyatt', 2, '남아시아', 'IN2'),
    # ── 인도 2차 배치3 5곳 — 6번(@jin_6) · 2026-11-27 05:2x~05:41 KST
    ('ixuza', '하얏트 플레이스 아우랑가바드 에어포트', '아우랑가바드', 'Hyatt Place', 1, '남아시아', 'IN3'),
    ('dedzd', '하얏트 센트릭 라지푸르 로드 데라둔', '데라둔', 'Hyatt Centric', 1, '남아시아', 'IN3'),
    ('delrh', '하얏트 리젠시 데라둔 리조트 앤 스파', '데라둔', 'Hyatt Regency', 3, '남아시아', 'IN3'),
    ('dhmrm', '하얏트 리젠시 다람살라 리조트', '다람살라', 'Hyatt Regency', 4, '남아시아', 'IN3'),
    ('dedzh', '하얏트 플레이스 하리드와르', '하리드와르', 'Hyatt Place', 1, '남아시아', 'IN3'),
]

PROVIDER = {'CA1': '7번(@no_7)', 'CA2': '7번(@no_7)', 'IN2': '6번(@jin_6)', 'IN3': '6번(@jin_6)'}
WHEN = {'CA1': '2026-11-27 05:40~06:10 KST', 'CA2': '2026-11-27 05:40~06:10 KST',
        'IN2': '2026-11-27 05:11~05:24 KST', 'IN3': '2026-11-27 05:25~05:41 KST'}

CASH = {
    'CA': ('현금 요금은 365일 전부 —입니다 — 이 엔드포인트는 어워드 포인트만 주고 현금가는 다른 '
           '경로라 미수집입니다(rate 는 표출일 전부 null). 호럭 요금도 미수집입니다.'),
    'IN': ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아(1박 단위 '
           'shop/rooms 화면에서만 표시) 현금가는 미수집입니다. 호럭 요금도 미수집입니다.'),
}

# 호텔별 보강 — 배치본 note 의 사실만 옮겨 적는다
EXTRA = {
    'yulza': ('Hyatt Place Montreal Airport(카테고리 3)는 359일 표출·6일 공백. STANDARD_ROOM 은 '
              'SUPER_OFF_PEAK 8,000(32일) · OFF_PEAK 12,000(247일) · STANDARD 15,000(76일) · '
              'SUPER_PEAK 20,000(4일: 2027-06-10~13) 4단계다. 공백 6일(2027-05-20~23 · 07-30~31)은 '
              '모두 날짜 키가 없는 no_key_in_response 이고 ±2일 버퍼 창 2개 재조회에서 같은 형태로 '
              '재현됐다(함께 든 표출일 7일 값·레벨 동일). 몬트리올 트뤼도 공항(YUL) 입구의 신규 '
              '호텔로 주소 690 Michel Jasmin Avenue, Dorval, QC H9P 1C5 이고 24시간 무료 공항 셔틀 '
              '안내가 있으며 예약 개시 전 안내 배너(Booking Notice)는 붙어 있지 않았다.'),
    'yyzzm': ('Hyatt Place Toronto/Mississauga Centre(카테고리 2)는 362일 표출·3일 공백. '
              'SUPER_OFF_PEAK 6,000(78일) · OFF_PEAK 7,500(156일) · STANDARD 10,000(125일) · '
              'PEAK 12,000(3일: 2027-03-01 · 09-03~04) 4단계다. 공백 3일(2026-12-08 · '
              '2027-02-09~10)은 no_key_in_response 이고 ±2일 창 2개 재조회에서 전부 재현됐다'
              '(함께 든 표출일 8일 값 동일). 주소 5787 Hurontario St, Mississauga, ON L4Z 2H7.'),
    'yulct': ('Hyatt Centric Montreal(카테고리 3)은 324일 표출·41일 공백으로 이번 캐나다 10곳 '
              '가운데 표출률이 가장 낮다. SUPER_OFF_PEAK 8,000(13일) · OFF_PEAK 12,000(236일) · '
              'STANDARD 15,000(69일) · PEAK 17,500(2일: 2027-07-30~31) · SUPER_PEAK 20,000(4일: '
              '2027-06-10~13) 5단계다. 공백은 2026-12월 19일 · 2027-01월 12일과 여름 주말'
              '(05-20~23 · 06-15 · 06-25 · 08-01 · 08-14)에 몰려 있고 전부 no_key_in_response 이며 '
              '재조회 5개 창에서 불일치 0건이다 — 여름 주말과 겨울 단기 구간의 어워드 인벤토리가 '
              '하루 단위로 끊긴다. 올드몬트리올 부티크로 주소 621 Notre-Dame St. East.'),
    'yulzm': ('Hyatt Place Montreal - Downtown(카테고리 3)은 340일 표출·25일 공백. '
              'SUPER_OFF_PEAK 8,000(31일) · OFF_PEAK 12,000(244일) · STANDARD 15,000(61일) · '
              'SUPER_PEAK 20,000(4일: 2027-06-10~13) 4단계다. 공백 25일이 여름 금·토 주말에 주 '
              '1~2일씩 끊기는 패턴이고 전부 no_key_in_response 로 재조회 4개 창 불일치 0건이다. '
              '주소 1415 rue Saint-Hubert, Montréal(베리-UQAM 메트로역 2분). 원자료의 도시 표기 '
              'Montréal 은 카드에서 Montreal(몬트리올)로 통일했다.'),
    'ca101': ('Hyatt Regency Niagara Falls Fallsview(카테고리 5)는 365일 전부 표출(공백 0일)되어 '
              '재조회 대상 null 이 없다. SUPER_OFF_PEAK 15,000(178일) · OFF_PEAK 20,000(84일) · '
              'STANDARD 25,000(103일) 3단계뿐이고 PEAK 이상은 없다. 여름 2027-06-21~07-28(38일 '
              '연속)과 연말 2026-12-22~12-31 이 최고가 구간이고, 겨울 2026-12-01~12-21 · '
              '2027-01-01~02-11 · 02-14~03-31 은 대부분 SUPER_OFF_PEAK 다. 나이아가라 폭포 뷰 '
              '42층 리젠시(6700 Fallsview Blvd).'),
    'iagub': ('The Clayfield(카테고리 5 · The Unbound Collection by Hyatt)는 352일 표출·13일 공백. '
              'SUPER_OFF_PEAK 15,000(178일) · OFF_PEAK 20,000(84일) · STANDARD 25,000(90일) '
              '3단계뿐이다. 공백 13일은 5월 말~9월 초에 주 단위로 흩어진 no_key_in_response 이며 '
              '±2일 창 3개 재조회에서 13일 전부 재현됐다(함께 든 표출일 66일 값·레벨 동일). '
              'STANDARD_SUITE(27,000~37,000) · PREMIUM_SUITE(30,000~40,000)도 함께 표출됐으나 '
              '채택값은 STANDARD_ROOM 만이다. 나이아가라온더레이크의 부티크(18 Clayfield Commons)로 '
              '2026-11-27 정상 영업 중이고 예약 개시 전 안내 배너는 없었다.'),
    'yowaz': ('Andaz Ottawa ByWard Market(카테고리 3)은 361일 표출·4일 공백. SUPER_OFF_PEAK '
              '8,000(32일) · OFF_PEAK 12,000(246일) · STANDARD 15,000(83일) 3단계뿐이고 1년의 68%가 '
              'OFF_PEAK 다. 공백 4일은 모두 empty_day_object 로 2026-12-07~09 는 날짜 오브젝트에 '
              '스위트만 있고 2027-04-07 은 빈 {} 이며 재조회 2창에서 재현됐다. STANDARD_SUITE'
              '(16,000~23,000) · PREMIUM_SUITE(18,000~25,000)도 함께 표출됐다. 주소 325 Dalhousie '
              'Street, Ottawa.'),
    'yowzo': ('Hyatt Place Ottawa - West(카테고리 2)는 353일 표출·12일 공백. SUPER_OFF_PEAK '
              '6,000(29일) · OFF_PEAK 7,500(242일) · STANDARD 10,000(82일) 3단계뿐이고 '
              'STANDARD_ROOM 단일 카테고리다. 공백 12일은 모두 no_key_in_response 이고 ±2일 창 5개 '
              '재조회에서 전부 재현됐다. 주소 300 Moodie Drive, Ottawa(페이지 본문은 도시를 Nepean '
              '으로 적고 있다).'),
    'yqtxt': ('Hyatt House Thunder Bay(카테고리 2)는 365일 전부 표출(공백 0일). SUPER_OFF_PEAK '
              '6,000(72일) · OFF_PEAK 7,500(182일) · STANDARD 10,000(111일) 3단계뿐이고 레벨이 '
              '1~5일 단위로 촘촘히 교차해 최장 구간도 15일이다. STANDARD_SUITE(11,000~15,000)가 '
              '대부분의 날에 함께 표출됐다. 주소 1165 Oliver Road, Thunder Bay(리뷰 37건 4.6/5 — '
              '영업 중 확인).'),
    'tordh': ('Hotel X Toronto(카테고리 5 · Destination by Hyatt)는 335일 표출·30일 공백. '
              'SUPER_OFF_PEAK 15,000(78일) · OFF_PEAK 20,000(147일) · STANDARD 25,000(107일) · '
              'PEAK 30,000(3일: 2027-03-01 · 09-03~04) 4단계이고 SUPER_PEAK 은 없다. 공백 30일은 '
              'empty_day_object 16일(대부분 스탠다드 스위트만 있는 날)과 no_key_in_response 14일로 '
              '나뉘며 ±2일 창 9개 재조회에서 전부 재현됐다. STANDARD_SUITE(27,000~42,000)도 함께 '
              '표출됐다. 주소 111 Princes\' Blvd, Toronto.'),
    'in102': ('**365일 전부 값이 있고 null 0일**(7,500~12,000P). 분포 7,500P 212일 · 10,000P '
              '150일 · 12,000P 3일. 금·토·일 7,500P(Off-peak) · 월~목 10,000P(Standard)가 '
              '기본이고 12,000P 는 2027-02-08~10 사흘에만 붙는다(카테고리 상단 10,000P 보다 한 '
              '단계 높은 값). 2026-12월 캘린더 전 칸과 API 값이 일치했고 12-01 패널도 '
              '「Points for this stay 10,000」·Book Now 활성이었다.'),
    'stvzb': ('유효 362일 · null 3일(3,000~6,000P). 분포 6,000P 164일 · 3,000P 107일 · 4,500P '
              '91일. 토·일 3,000P · 금 4,500P · 화~목 6,000P 의 요일 밴드가 1년 내내 유지된다. '
              'null 3일(2026-12-01~02 · 12-09) 가운데 12-09 는 1박 shop/rooms 에서 포인트·현금 '
              '모두 「Hotel Not Available」로 그 날짜에 호텔 자체가 팔리지 않는 상태였고(같은 '
              '화면의 인근 하얏트 플레이스 바도다라는 6,000P 정상 노출) 12-02 는 1박 뷰의 '
              'checkout 셀이다. 2026-12월 캘린더와 전 칸 일치.'),
    'bhozb': ('유효 355일 · null 10일(3,000~6,000P). 분포 4,500P 294일 · 6,000P 44일 · 3,000P '
              '17일. null 10일은 2026-12-01 · 12-03~05 · 12-10~12 · 12-17~19 네 블록으로 모두 '
              '12월에만 있고, 12-10~11 은 1박 포인트 뷰가 「Hotel Not Available」이었다(신규 개관 '
              '호텔로 재고 미적재로 보이나 공홈은 사유를 밝히지 않는다). 2026-12월 캘린더와 전 칸 '
              '일치.'),
    'chenn': ('유효 324일 · null 41일(3,000~6,000P). 분포 4,500P 181일 · 3,000P 74일 · 6,000P '
              '69일, 6,000P(Peak)가 2027-07-10~08-22 44일 연속이다. null 41일은 12개 블록이고 '
              '그중 30일은 STANDARD_ROOM 대신 CLUB/SUITE 어워드만 있는 날이다(2027-02-09~10 은 '
              '클럽 포인트 어워드 6,500P 만 열림) — 호텔은 정상 판매 중이고 스탠다드룸 포인트 '
              '어워드만 닫힌 상태다. 2026-12-24 는 캘린더 칸이 비었으나 shop/rooms 에서 「Free '
              'Night Award 6,000 Points/Night」가 활성으로 예약 가능해 API 값을 채택했다(배치 3의 '
              'goazc·goagh 와 같은 유형).'),
    'cheph': ('유효 350일 · null 15일(6,000~12,000P). 분포 7,500P 286일 · 10,000P 42일 · 6,000P '
              '21일 · 12,000P 1일(2027-01-31 — 카테고리 상단 10,000P 보다 높은 값). 2027-03-23~'
              '09-20 은 7,500P 가 6개월 가까이 이어진다. null 15일은 2026-12-01 · 12-03 · '
              '2027-02-01~04 · 02-17~18 · 09-21~24 · 09-28~30 여섯 블록이며, 2027-02-02~03 은 '
              'Suites 의 파크 스위트(₩444,900 + 6,000P 업그레이드)만 열려 있었다 — 호텔은 판매 '
              '중이고 스탠다드룸 포인트 어워드만 닫힌 상태다. 2026-12월 캘린더와 전 칸 일치.'),
    'ixuza': ('유효 349일 · null 16일(3,000~6,000P). 분포 6,000P 159일 · 4,500P 157일 · 3,000P '
              '33일. 2027-06-06~07-08 은 3,000P 33일 연속(우기 최저가)이고 2027-11 은 29일이 '
              '6,000P 다. null 16일은 전부 2026-12~2027-02 초 10개 블록에 몰려 있고 2027-03 '
              '이후는 0일 — 대표일 2026-12-01 1박 조회는 포인트 뷰 「No Available Rooms」였지만 '
              '같은 화면에서 현금(₩113,369~)은 판매 중이라 호텔은 정상 영업이고 그 1박 스탠다드룸 '
              '포인트 어워드만 닫힌 상태다. 공홈 도시 표기는 개칭명 Chhatrapati Sambhajinagar'
              '(2022년 아우랑가바드에서 개칭)이고 호텔명은 「아우랑가바드 에어포트」를 그대로 쓰므로 '
              '카드 도시는 알아보기 쉬운 아우랑가바드로 적었다.'),
    'dedzd': ('유효 362일 · null 3일(3,000~6,000P). 분포 4,500P 185일 · 6,000P 132일 · 3,000P '
              '45일이고 3,000P 는 2027-01-03~07 과 2027-07-21~09-23 우기 주중에 몰린다. null '
              '3일은 2026-12-02 와 2027-03-27~28 — 12-02 는 avail/days 를 12-02~12-03 으로 좁혀 '
              '재조회해 빈 객체임을 확인했고(같은 응답의 12-03 은 6,000P) 03-27·28 은 캘린더 '
              '그리드에서도 값이 비어 있었다. 2026-12월·2027-03월 그리드 전 칸과 API 가 일치.'),
    'delrh': ('유효 278일 · null 87일(8,000~15,000P)로 이번 인도 10곳 가운데 값이 가장 적다. 분포 '
              '12,000P 159일 · 15,000P 74일 · 8,000P 45일. null 87일은 28개 블록으로 2027-07-12 '
              '까지만 있고 그 뒤 창 끝까지는 0일이며 2027-05-13~25(13일) · 2027-02-25~03-04(8일) '
              '같은 긴 블록이 있다. 2026-12월·2027-06월 그리드에서 같은 날이 비어 있어 렌더 누락이 '
              '아닌 실제 미개방임을 확인했고, 대표일 2027-06-10 · 2027-02-09 1박 교차 확인에서는 '
              '공홈이 「Hotel Not Available」로 현금가도 노출하지 않았다 — 어워드만 닫힌 것이 '
              '아니라 그 날짜에 호텔이 팔리지 않는 상태다(공홈은 사유를 밝히지 않는다).'),
    'dhmrm': ('유효 355일 · null 10일(12,000~20,000P). 분포 15,000P 166일 · 12,000P 111일 · '
              '20,000P 78일. 2027-09-15~11-30 은 15,000P 77일 연속이고 2027-08 은 31일 전부 '
              '12,000P 다. null 10일은 2026-12-02~04 · 2027-01-25~26 · 03-14~16 · 04-22~23 네 '
              '블록이며, 2026-12-03 1박 조회는 Suites 만 열려(레젠시 스위트 24,000P · 프리미엄 '
              '27,000P 활성) 호텔은 판매 중이고 스탠다드룸 포인트 어워드만 닫힌 상태였다. '
              '2026-12월 그리드 전 칸 일치.'),
    'dedzh': ('유효 360일 · null 5일(3,000~6,000P). 분포 4,500P 181일 · 6,000P 134일 · 3,000P '
              '45일. 같은 주(우타라칸드) Cat1 호텔 dedzd 와 365일 중 357일 값이 완전히 같아 같은 '
              '피크/오프피크 달력을 쓰는 것으로 보이나 null 위치가 달라 각각 별도 응답임은 '
              '확인했다. null 5일은 2026-12-01 · 12-09~10 · 12-14 · 12-19 로 전부 12월이고 '
              '12-01 은 avail/days 를 12-01~12-02 로 좁힌 재조회에서 날짜 키 자체가 없음을 '
              '확인했다(같은 응답의 12-02 는 4,500P). 2026-12월 그리드 전 칸 일치.'),
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

    def add(code, h):
        assert code not in hotels, code
        hotels[code] = h

    for name in ('0-hyatt_ca2_batch1_5.json', '0-hyatt_ca2_batch2_5.json'):
        d = json.load(open(os.path.join(CA_D, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30', (name, d['meta']['window'])
        for code, h in d['hotels'].items():
            add(code, h)
    for path, name in ((IN2_D, '0-hyatt-in2-batch2-5.json'), (IN3_D, '0-hyatt-in2-batch3-5.json')):
        d = json.load(open(os.path.join(path, name), encoding='utf-8'))
        assert d['window'] == {'start': '2026-12-01', 'end': '2027-11-30', 'days': 365}
        for h in d['hotels']:
            add(h['code'], h)
    assert len(hotels) == 20, len(hotels)
    return hotels


def pts_of(h):
    raw = h.get('points') or {}
    if isinstance(raw, list):
        raw = dict(raw)
    return [raw.get(d) for d in DATES]


def head(tag, city, cat, priced):
    cat_txt = 'null' if cat is None else str(cat)
    if tag.startswith('IN'):
        return ('하얏트 공홈 포인트 캘린더(explore-hotels/rate-calendar · Standard Room · 1박 · '
                '성인2인·1실)로 2026-12-01~2027-11-30 365칸을 실측했다(%s · 6번(@jin_6) · %s · '
                '인도). 값은 캘린더 화면의 데이터 원천인 공홈 avail/days 응답(roomCategory='
                'STANDARD_ROOM·los=1)에서 날짜별 STANDARD_ROOM pointsValue 를 읽었고, 조회는 56일 '
                '이하 7구간(총 35회)으로 나눠 정상 응답한 범위만 기록했다. 공홈 표시 어워드 '
                '카테고리 %s이고 값이 있는 날은 %d일이다.' % (WHEN[tag], city, cat_txt, priced))
    return ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory='
            'STANDARD_ROOM · 성인2·1박)을 60일 창 6회 + 5일 창 1회로 나눠 2026-12-01~2027-11-30 '
            '365칸을 실측했다(%s · 7번(@no_7) · %s · 캐나다). 창은 모두 실제 페이지 로드로 응답 '
            'JSON 을 받아 파싱했고, null 구간은 앞뒤 표출일을 포함한 좁은 창으로 다시 조회해 '
            '값·레벨 불일치 0건을 확인했다. 공홈 표시 어워드 카테고리 %s이고 값이 있는 날은 '
            '%d일이다.' % (WHEN[tag], city, cat_txt, priced))


def build_note(tag, code, city, cat, priced):
    bits = [head(tag, city, cat, priced), EXTRA[code], CASH[tag[:2]],
            '%s이 실측해 보낸 본입니다.' % PROVIDER[tag]]
    note = ' '.join(note for note in bits if note)
    note = ' '.join(note.split())
    # 「개관 전」은 달력 UI 가 호텔 전체 미오픈 신호로 읽으므로 이 20곳에는 쓰지 않는다
    assert '개관 전' not in note, code
    return note


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 540, len(before)
    assert before[-1]['id'] == 'hy540', before[-1]['id']

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
        assert m['woh_participating'] is (cat is not None), (code, 'WoH', m['woh_participating'], cat)
        print('%-6s %-6s Cat %-4s WoH %-5s %s' % (code, region, m['category'],
                                                   m['woh_participating'], m['name']))

    # ── 기존 540곳 중복 확인 ─────────────────────────────────────────
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
    print('기존 540곳 대조 — code·영문명·국문명 중복 0건')

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
    online = sum(1 for h in added for v in h['points']['$v'] if v is not None)
    print('hotels', len(hs), 'cells', cells, 'priced', priced, dict(reg))
    assert len(hs) == 560 and cells == 560 * 365, (len(hs), cells)
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['캐나다'] == 30 and reg['남아시아'] == 35 and reg['중동'] == 31 and reg['아프리카'] == 5
    assert reg['미국'] == 209 and reg['유럽'] == 128 and reg['동남아'] == 61 and reg['일본'] == 23
    assert reg['중국·중화권'] == 15 and reg['오세아니아'] == 14 and reg['한국'] == 9
    assert online == 6976, online
    assert priced == 164798 + 6976, priced
    print('EXPECT_HYATT = {\'hotels\': %d, \'cells\': %d, \'priced\': %d}' % (len(hs), cells, priced))


if __name__ == '__main__':
    main()
