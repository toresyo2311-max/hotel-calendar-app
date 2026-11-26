#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 인도 2차 배치4 5 + 캐나다 2차 배치3 5 + 배치4 4 + 스페인 3차 배치1 5 + 배치2 5 = 24곳 병합
(2026-11-27) 560 → 584곳

입력
  · 6번(@jin_6) 인도 2차 배치4 5곳 (hydhy · hydph · hydzh · jaial · jairj)
      memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0554/received/0-hyatt-in2-batch4-5.json
      (포인트 캘린더 · Standard Room · 1박 · 성인2인·1실 · 56일 이하 7구간)
  · 7번(@no_7) 캐나다 2차 배치3 5곳 (torjd · torph · torrt · torza · torzt)
      memory/clones/a03363f4-no71/pickle/2026-11-27-0553/received/0-hyatt_ca2_batch3_5.json
  · 7번(@no_7) 캐나다 2차 배치4 4곳 (yxyzw · yqgzw · caaae · caaaf)
      memory/clones/a03363f4-no71/pickle/2026-11-27-0553/received/0-hyatt_ca2_batch4_4.json
      (avail/days · roomCategory=STANDARD_ROOM · 성인2·1박 · 60일 창 6 + 5일 창 1)
  · 4번(@jin_4) 스페인 3차 배치1 5곳 (aumap · alime · asmen · aufam · aulgp — 전부 0/365)
      memory/clones/06130525-jin489/pickle/2026-11-27-0542/received/0-hyatt-es3-batch1.json
  · 4번(@jin_4) 스페인 3차 배치2 5곳 (pmijc · agpub · aumed · audbl · seclz)
      memory/clones/06130525-jin489/pickle/2026-11-27-0542/received/0-hyatt-es3-batch2.json
      (스페인은 일반 호텔 los=1·성인1, 올인클루시브 los=2·성인2)

■ 규칙
- 마스터(1-hyatt-global-master.json)의 24개 spiritCode 와 이름·카테고리·브랜드·WoH 참여를 배치본과 대조.
  카드 region 은 마스터 area 그대로 — 인도 → 남아시아 / 캐나다 → 캐나다 / 스페인 → 유럽.
- 기존 560곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 — 겹침 0쌍 확인.
- caaae·caaaf(프린스앨버트 형제 호텔)는 WoH 미참여(category null)이고 공홈 예약 버튼이 「Coming Soon」인
  상태라 365일 0칸이다. 카드에는 그대로 싣고 사유를 note 에 적는다.
- 스페인 알루아 5곳(aumap·alime·asmen·aufam·aulgp)과 aumed·audbl 은 0/365 — 최소숙박·인원 아티팩트가
  아님을 los=7(·14)·좁은 창·공홈 UI 로 확인한 내용을 note 에 적는다.
- city·name 은 국문, brand 는 공홈(마스터) 브랜드 라벨, category 는 정수 또는 A0~A2 문자열(없으면 null).
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 24곳 모두 현금가 미수집.
- note 에는 마크다운 ** 별표와 긴 URL 을 쓰지 않고, 달력이 호텔 전체 미오픈 신호로 읽는 「개관 전」 문구도 쓰지 않는다.
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
D7 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0553/received')
D4 = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-27-0542/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START, END = '2026-12-01', '2027-11-30'
_d0, _d1 = date(2026, 12, 1), date(2027, 11, 30)
DATES = [(_d0 + timedelta(days=i)).isoformat() for i in range((_d1 - _d0).days + 1)]
assert len(DATES) == 365
FIRST_ID = 561

# (code, 국문명, 도시, 브랜드, 카테고리, region, 묶음)
PLAN = [
    # ── 인도 2차 배치4 5곳 — 6번(@jin_6) · 2026-11-27 05:43~05:53 KST
    ('hydhy', '하얏트 하이데라바드 가치보울리', '하이데라바드', 'Hyatt Hotels', 2, '남아시아', 'IN'),
    ('hydph', '파크 하얏트 하이데라바드', '하이데라바드', 'Park Hyatt', 2, '남아시아', 'IN'),
    ('hydzh', '하얏트 플레이스 하이데라바드 반자라 힐스', '하이데라바드', 'Hyatt Place', 1, '남아시아', 'IN'),
    ('jaial', '알릴라 포트 비샹가르', '자이푸르', 'Alila', 5, '남아시아', 'IN'),
    ('jairj', '하얏트 리젠시 자이푸르 만사로바르', '자이푸르', 'Hyatt Regency', 2, '남아시아', 'IN'),
    # ── 캐나다 2차 배치3 5곳(토론토) — 7번(@no_7) · 2026-11-27 05:40~05:55 KST
    ('torjd', '더 앤도어 하우스', '토론토', 'JdV by Hyatt', 4, '캐나다', 'CA'),
    ('torph', '파크 하얏트 토론토', '토론토', 'Park Hyatt', 6, '캐나다', 'CA'),
    ('torrt', '하얏트 리젠시 토론토', '토론토', 'Hyatt Regency', 4, '캐나다', 'CA'),
    ('torza', '하얏트 플레이스 토론토 에어포트', '토론토', 'Hyatt Place', 2, '캐나다', 'CA'),
    ('torzt', 'TOOR 호텔', '토론토', 'JdV by Hyatt', 4, '캐나다', 'CA'),
    # ── 캐나다 2차 배치4 4곳 — 7번(@no_7) · 2026-11-27 05:41~05:52 KST
    ('yxyzw', '하얏트 플레이스 화이트호스', '화이트호스', 'Hyatt Place', 3, '캐나다', 'CA'),
    ('yqgzw', '하얏트 플레이스 윈저', '윈저', 'Hyatt Place', 2, '캐나다', 'CA'),
    ('caaae', '하얏트 스튜디오 프린스앨버트', '프린스앨버트', 'Hyatt Studios', None, '캐나다', 'CA'),
    ('caaaf', '하얏트 셀렉트 프린스앨버트', '프린스앨버트', 'Hyatt Select', None, '캐나다', 'CA'),
    # ── 스페인 3차 배치1 5곳(알루아) — 4번(@jin_4) · 2026-11-27 KST
    ('aumap', '알루아선 마르베야 파크', '마르베야', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('alime', '알루아 일라 데 메노르카', '메노르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('asmen', '알루아솔 메노르카', '메노르카', 'Alua Hotels & Resorts', 'A1', '유럽', 'ES'),
    ('aufam', '알루아선 파르 메노르카', '메노르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('aulgp', '알루아선 라고 파크', '메노르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    # ── 스페인 3차 배치2 5곳 — 4번(@jin_4) · 2026-11-27 06:40 KST
    ('pmijc', '린드너 호텔 마요르카 포르탈스 노우스', '마요르카', 'JdV by Hyatt', 4, '유럽', 'ES'),
    ('agpub', '라 잠브라 리조트', '미하스-마르베야', 'The Unbound Collection by Hyatt', 5, '유럽', 'ES'),
    ('aumed', '알루아선 메디테라네오', '메노르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('audbl', '알루아선 도블레마르', '무르시아', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('seclz', '시크릿츠 란사로테 리조트 앤 스파', '란사로테', 'Secrets', 'A2', '유럽', 'ES'),
]

COUNTRY_KO = {'IN': '인도', 'CA': '캐나다', 'ES': '스페인'}
PROVIDER = {'IN': '6번(@jin_6)', 'CA': '7번(@no_7)', 'ES': '4번(@jin_4)'}
CASH = {
    'IN': ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아(1박 단위 '
           'shop/rooms 화면에서만 표시) 미수집으로 두었습니다.'),
    'CA': ('현금 요금은 365일 전부 —입니다 — 이 엔드포인트는 어워드 포인트만 주고 현금가는 다른 경로라 '
           '미수집입니다.'),
    'ES': ('현금 요금은 365일 전부 —입니다 — 지시대로 현금(rooms/roomrates) 호출을 하지 않아 미수집으로 '
           '두었습니다.'),
}

# 호텔별 보강 — 배치본에 있는 사실만, 달력 표시에 영향 없는 문장으로 적는다
EXTRA = {
    # ── 인도
    'hydhy': ('공백 32일은 2026-12~2027-03 초의 10개 블록에 몰려 있고, 2026-12-01 1박 shop/rooms 에는 '
              'Suites(2)만 열려 있었다 — 스탠다드룸 포인트 어워드만 닫힌 날이며 같은 날 현금 '
              '₩223,686 은 정상 판매였다.'),
    'hydph': ('2026-12-04 은 공홈 검색이 「Hotel Not Available」로 그 날짜에 호텔 자체가 팔리지 않는 '
              '상태였고, 2027-01-27~28 은 스탠다드룸 없이 스위트 어워드(15,000~17,000P)만 열린 날이다. '
              'hydzh 와는 365일 중 353일 등급이 같다.'),
    'hydzh': ('공백 8일은 2026-12-01~04 · 12-06~08 · 2027-07-08 세 블록이다. 2026-12-02~03 은 '
              'soldOutHotel 응답이었지만 2026-12-04 검색에서 같은 호텔이 현금 ₩356,094 로 정상 판매 '
              '중이었고, 2027-07-08 은 앞뒤가 모두 4,500P 인 하루 공백이다.'),
    'jaial': ('rate-calendar 객실 선택자에 Standard Room 이 없고 Premium Suite 만 있는 호텔이라 '
              '2026-12-01~2027-03-14 104일 연속을 포함한 114일이 비어 있고, 2026-12-01 1박에는 '
              'Suites(6)와 Tented Suite 40,000P 가 열려 있었다. 2027-11-22 은 35,000P·11-23~25 는 '
              '30,000P(연말 피크)다.'),
    'jairj': ('공백 13일은 2026-12-04 · 12-12 · 12-16~17 · 12-28 · 12-31 · 2027-01-03 · 01-09 · '
              '01-18 · 01-28~30 · 02-18 로 연말·신정 연휴의 단일·연속 블록이고, 2026-12-04 1박 검색은 '
              '「Hotel Not Available」로 현금·포인트 모두 팔지 않았다.'),
    # ── 캐나다
    'torjd': ('공백 4일은 날짜 키 없음 3일(2026-12-01·02·07)과 PREMIUM_SUITE 만 있는 2026-12-03 이고, '
              '같은 기간 STANDARD_SUITE 21,000~31,500P · PREMIUM_SUITE 24,000~34,500P 도 함께 '
              '표출됐다(수집 필드는 STANDARD_ROOM).'),
    'torph': ('공백 46일이 이 배치에서 가장 많고(날짜 키 없음 36 · 빈 오브젝트 7 · 스위트만 3), '
              'STANDARD_SUITE 35,000~50,000P · PREMIUM_SUITE 40,000~55,000P 도 함께 표출됐다.'),
    'torrt': ('공백 17일 가운데 7일은 2027-09-09~15 연속 미표출이고, STANDARD_SUITE '
              '21,000~31,500P 도 함께 표출됐다.'),
    'torza': ('스탠다드룸 단일 카테고리만 표출되고(스위트 카테고리 없음) 공백은 2027-04-10 하루뿐이다. '
              '공홈 본문은 이 호텔을 신규 호텔로 소개하지만 예약은 정상 진행 중이다(24시간 무료 공항 '
              '셔틀·196실).'),
    'torzt': ('공백 18일 가운데 2027-05-16~21 이 6일 연속이고, STANDARD_SUITE 21,000~31,500P 도 함께 '
              '표출됐다. 공홈이 신규 부티크 호텔로 소개하지만 예약은 정상 진행 중이다.'),
    'yxyzw': ('겨울(2026-12~2027-03)은 SUPER_OFF_PEAK 과 OFF_PEAK 가 번갈아 나오고 여름 이후에는 '
              'OFF_PEAK 가 길게 이어지며, 공백 16일은 모두 날짜 키 없음(no_key_in_response)으로 ±2일 '
              '버퍼 창 8개에서 재현됐다. 공홈 페이지가 정상 열리고 2025-10 리뷰가 게시된 영업 중 호텔이다.'),
    'yqgzw': ('OFF_PEAK 7,500 이 272일로 가장 많고, 공백 6일은 모두 날짜 키 없음으로 ±2일 버퍼 창 3개에서 '
              '재현됐다. 공홈 페이지가 정상 열리고 실내 수영장·무료 주차를 안내하는 영업 중 호텔이다.'),
    'caaae': ('7개 창 모두 응답이 days 가 빈 객체인 soldOutHotel(41바이트)이고, 공홈 예약 버튼이 '
              '「Coming Soon」으로 비활성이라 예약을 받지 않는 상태다(전화·이메일 게시 없음). 같은 주소의 '
              '자매 호텔 하얏트 셀렉트 프린스앨버트를 companion hotel 로 안내한다.'),
    'caaaf': ('7개 창 모두 응답이 days 가 빈 객체인 soldOutHotel(41바이트)이고, 공홈 예약 버튼이 '
              '「Coming Soon」으로 비활성이라 예약을 받지 않는 상태다(전화·이메일 게시 없음). 같은 주소의 '
              '하얏트 스튜디오 프린스앨버트와 서로 companion hotel 로 안내한다.'),
    # ── 스페인
    'aumap': ('20일 창 19개와 2027-07-10~07-20 · 2027-04-01~04-14 los=7 재조회가 모두 soldOutHotel 이었고, '
              '공홈 객실페이지(2027-07-10~07-17 7박·2인·포인트 사용)도 「이 호텔은 해당 날짜에 포인트나 '
              '어워드로 예약을 받지 않습니다」였다.'),
    'alime': ('20일 창 19개와 2027-08-01~08-14 los=7 재조회가 모두 soldOutHotel 이었고, 공홈 객실페이지'
              '(7박·2인·포인트 사용)도 포인트·어워드 예약 불가를 표시했다.'),
    'asmen': ('20일 창 19개와 2027-08-01~08-14 los=7 재조회가 모두 soldOutHotel 이었고, 공홈 포인트 '
              '캘린더(2박·2인)에 객실구분 버튼·일자 셀이 없었다 — 같은 조건의 대조군 알루아선 코스타 '
              '파크는 20,000P 일자 셀을 표시했다.'),
    'aufam': ('20일 창 19개(겹침 재확인 포함 21창)와 2027-08-01~08-14 los=7 재조회가 모두 soldOutHotel '
              '이었고, 공홈 포인트 캘린더(2박·2인)에도 표시가 없었다.'),
    'aulgp': ('20일 창 19개와 2027-08-01~08-14 los=7·los=14·4일 좁은 창(2027-08-08~08-11) 재조회가 모두 '
              'soldOutHotel 이었고, 공홈 포인트 캘린더에 객실구분 버튼·일자 셀이 없으며 「이용 가능한 '
              '객실 없음」이었다.'),
    'pmijc': ('값이 없는 74일은 날짜 키 없음 60일과 스탠다드룸 없이 스위트만 있는 14일이고, 최장 공백은 '
              '2027-05-15~05-31(17일)이다. 2027-07-15~07-25 를 성인2·2박·상위 객실 포함'
              '(roomCategory=ROOM)으로 다시 조회해도 빈 응답이어서 여름 공백은 최소숙박 조건이 아니다. '
              '2027-11-26~11-30 에는 STANDARD_SUITE 21,000P(스탠다드룸 12,000P 의 1.75배)도 함께 표출됐다.'),
    'agpub': ('표준룸 어워드는 2026-12-17·12-21 두 날(15,000P)에만 표출되고 2027년은 전부 비어 있다. 같은 '
              '호텔의 SIGN 스위트는 2027-09-27~09-29 37,000P · 09-30~10-30 32,000P · 10-31~11-30 '
              '27,000P 로 실측돼 표준룸 어워드를 기다리는 접근보다 SIGN 기준이 실질 최저다. 공홈은 현금과 '
              'Points+Cash 로 팔고 있어(2027-07-10 SIGN 현금 €623.70+세금 · 18,500P+€539) 표준 포인트 '
              '어워드만 열리지 않은 상태다 — 현금 값은 저장하지 않았다.'),
    'aumed': ('20일 창 19개가 모두 soldOutHotel 이고 2027-04-22~04-26 5일 창과 04-22~04-29 los=7 재조회도 '
              '같았다. 공홈 객실페이지는 2027-07-10~07-17 에 포인트·프리나이트 어워드 이용 불가를 명시해 '
              '하계에는 영업 중이고 포인트만 미판매이며, 2027-01-10~01-17 현금 검색에서 메노르카 15개 '
              '호텔이 모두 Unavailable 이라 동계 휴장 정황이다.'),
    'audbl': ('20일 창 19개가 모두 soldOutHotel 이고 2027-06-05~06-09 5일 창과 06-05~06-12 los=7 재조회도 '
              '같았다. 공홈 객실페이지는 2027-07-10~07-17 에 포인트·프리나이트 어워드 이용 불가를 '
              '명시했고, 2027-01-10~01-17 현금 검색에서도 Unavailable 이었다.'),
    'seclz': ('값이 없는 14일은 스탠다드룸 없이 다른 객실만 있는 응답이고(2026-12-02~05 · 12-08~12 · '
              '12-22~24 · 2027-06-01~02), STANDARD_ROOM·STANDARD_SUITE·PREMIUM_SUITE·CLUB 이 함께 '
              '표출되는 호텔에서 이번 실행은 STANDARD_ROOM 만 365일 수집했다. 2027-11-30 은 재조회가 '
              '아닌 단일 판독이지만 응답에 20,000P 로 명시돼 있었다.'),
}

# 스페인 호텔별 측정 기준 문구
ES_BASIS = {
    'aumap': '성인2·2박(los=2) 고정 · 20일 이하 창 19개 + 겹침 재확인',
    'alime': '성인2·2박(los=2) 고정 · 20일 이하 창 19개 + 겹침 재확인',
    'asmen': '성인2·2박(los=2) 고정 · 20일 이하 창 19개 + 겹침 재확인',
    'aufam': '성인2·2박(los=2) 고정 · 20일 이하 창 19개',
    'aulgp': '성인2·2박(los=2) 고정 · 20일 이하 창 19개',
    'pmijc': '성인1·1박 · 20일 이하 창 타일링',
    'agpub': '성인1·1박 · 20일 이하 창 타일링',
    'aumed': '성인2·2박(los=2) 고정 · 20일 이하 창 19개',
    'audbl': '성인2·2박(los=2) 고정 · 20일 이하 창 19개',
    'seclz': '성인2·2박(los=2) 고정 · 20일 이하 창 20개',
}
ES_TIME = {
    'aumap': '2026-11-27 KST', 'alime': '2026-11-27 KST', 'asmen': '2026-11-27 KST',
    'aufam': '2026-11-27 KST', 'aulgp': '2026-11-27 KST',
    'pmijc': '2026-11-27 06:40 KST', 'agpub': '2026-11-27 06:40 KST',
    'aumed': '2026-11-27 06:40 KST', 'audbl': '2026-11-27 06:40 KST',
    'seclz': '2026-11-27 06:40 KST',
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
    d = json.load(open(os.path.join(D6, '0-hyatt-in2-batch4-5.json'), encoding='utf-8'))
    assert d['window'] == {'start': START, 'end': END, 'days': 365}
    for h in d['hotels']:
        hotels[h['code']] = h
        src[h['code']] = ('IN', '0-hyatt-in2-batch4-5.json')
    for name in ('0-hyatt_ca2_batch3_5.json', '0-hyatt_ca2_batch4_4.json'):
        d = json.load(open(os.path.join(D7, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30'
        for code, h in d['hotels'].items():
            hotels[code] = h
            src[code] = ('CA', name)
    for name in ('0-hyatt-es3-batch1.json', '0-hyatt-es3-batch2.json'):
        d = json.load(open(os.path.join(D4, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30'
        for code, h in d['hotels'].items():
            hotels[code] = h
            src[code] = ('ES', name)
    assert len(hotels) == 24, len(hotels)
    return hotels, src


def pts_of(h):
    raw = h.get('points') or {}
    if isinstance(raw, list):
        raw = dict(raw)
    return [raw.get(d) for d in DATES]


def blocks(dates):
    """연속 날짜 묶음 → ['2026-12-01~12-03(3일)', '2027-05-01']"""
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


def cat_sentence(grp, cat, priced):
    cat_txt = 'null' if cat is None else ('%s' % cat)
    if cat is None:
        return ('공홈에 어워드 카테고리 표시가 없어 카테고리는 null(월드 오브 하얏트 미참여)이고 값이 있는 '
                '날은 %d일이다.' % priced)
    if grp == 'ES' and str(cat).startswith('A'):
        disp = {'A0': 'A', 'A1': 'B', 'A2': 'C'}.get(str(cat), str(cat))
        return ('공홈 표시 어워드 카테고리는 %s · 마스터 표기 %s이고 값이 있는 날은 %d일이다.'
                % (disp, cat_txt, priced))
    return '공홈 표시 어워드 카테고리는 %s이고 값이 있는 날은 %d일이다.' % (cat_txt, priced)


def head(grp, code, city, priced):
    if grp == 'IN':
        return ('하얏트 공홈 포인트 캘린더(explore-hotels/rate-calendar · Standard Room · 1박 · '
                '성인2인·1실)와 그 데이터 원천(avail/days · roomCategory=STANDARD_ROOM · los=1)을 '
                '56일 이하 7구간으로 나눠 2026-12-01~2027-11-30 365칸을 실측했다'
                '(2026-11-27 05:43~05:53 KST · 6번(@jin_6) · %s · 인도).' % city)
    if grp == 'CA':
        return ('하얏트 공홈 어워드 응답(avail/days · roomCategory=STANDARD_ROOM · 성인2·1박)을 60일 창 '
                '6회 + 5일 창 1회로 나눠 2026-12-01~2027-11-30 365칸을 실측했다'
                '(2026-11-27 05:40~05:52 KST · 7번(@no_7) · %s · 캐나다).' % city)
    return ('하얏트 공홈 어워드 응답(avail/days · roomCategory=STANDARD_ROOM · %s)으로 '
            '2026-12-01~2027-11-30 365칸을 실측했다(%s · 4번(@jin_4) · %s · 스페인).'
            % (ES_BASIS[code], ES_TIME[code], city))


def body_from_source(grp, info):
    """배치본 note 의 사실을 그대로 살리되, 머리·카테고리·분포 문장과 중복되는 부분,
    별표, 긴 URL 은 걷어낸다."""
    n = clean(info.get('note') or '').replace('**', '')
    if grp == 'IN':
        # 1) 머리와 같은 수집 방법 문장
        i = n.find('실측했다.')
        if i > 0:
            n = n[i + len('실측했다.'):].strip()
        # 2) 데이터 원천·구간 설명(머리에 이미 있음)
        a = n.find('값은 캘린더 화면이 쓰는')
        if a >= 0:
            b = n.find('포인트 어워드 없음).', a)
            if b > 0:
                n = (n[:a] + n[b + len('포인트 어워드 없음).'):]).strip()
        # 3) 공홈 표시 카테고리 문장(카드 문장에 이미 있음)
        a = n.find('공홈 표시 어워드 카테고리')
        if a >= 0:
            b = n.find('일치).', a)
            if b > 0:
                n = (n[:a] + n[b + len('일치).'):]).strip()
        # 4) 유효일/null 요약과 분포(카드 문장·분포 문장에 이미 있음)
        n = re.sub(r'유효 \d+일 / null \d+일\([^)]*\)\.', '', n)
        n = re.sub(r'분포: [^.]*\.', '', n)
    n = re.sub(r'https?://\S+', '', n)
    return ' '.join(n.split())


def build_note(grp, code, city, cat, info, pts, priced):
    bits = [head(grp, code, city, priced), cat_sentence(grp, cat, priced)]
    if priced:
        bits.append('분포: %s.' % dist_text(pts))
    if grp == 'IN':
        bits.append(body_from_source('IN', info))
    if grp == 'CA' and cat is None:
        bits.append('365일 전부 어워드 표출이 없다.')
    if grp != 'IN':
        bits.append(EXTRA.get(code, ''))
    bits.append(CASH[grp])
    bits.append('%s이 실측해 보낸 본입니다.' % PROVIDER[grp])
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
    assert len(before) == 560, len(before)
    assert before[-1]['id'] == 'hy560', before[-1]['id']

    hotels, src = load()
    assert set(hotels) == {p[0] for p in PLAN}, sorted(set(hotels) ^ {p[0] for p in PLAN})

    # ── 공홈 마스터 대조 ─────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    AREA_OK = {'유럽': '유럽', '남아시아': '남아시아', '캐나다': '캐나다'}
    for code, kr, city, brand, cat, region, grp in PLAN:
        m, h = byc[code], hotels[code]
        # 배치본이 「La Zambra Resort, Mijas-Marbella」처럼 도시를 덧붙인 경우 마스터 이름을 정본으로 쓴다
        assert norm(m['name']) in (norm(h['name']), norm(h['name'].split(',')[0])), \
            (code, m['name'], h['name'])
        assert m['area'] == AREA_OK[region], (code, m['area'], region)
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert str(cat) == str(h['category']), (code, cat, h['category'])
        assert clean(brand) == clean(m['brand']), (code, brand, m['brand'])
        if clean(h['brand']) != clean(m['brand']):
            print('  브랜드 표기 차이 %s — 배치본 %r → 마스터 %r' % (code, h['brand'], m['brand']))
        assert m['woh_participating'] is (cat is not None), (code, m['woh_participating'])
        print('%-6s %-6s Cat %-4s WoH %-5s %s' % (code, region, m['category'], m['woh_participating'], m['name']))

    # ── 기존 560곳 중복 확인 ─────────────────────────────────────────
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
    print('기존 560곳 대조 — code·영문명·국문명 중복 0건')

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
    print('① 호텔럭스 161곳 대조 — 겹침 0곳')

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
        if info.get('woh_participating') is False:
            assert cat is None and priced == 0
        note = build_note(grp, code, city, cat, info, pts, priced)
        added.append({
            'id': hid, 'group': 'hyatt', 'code': code, 'region': region, 'city': city,
            'name': kr, 'english': clean(byc[code]['name']), 'brand': brand, 'category': cat,
            'vip_id': None, 'alsoIn': None, 'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None, 'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % code, 'hlx': None},
            'promotion': None, 'note': note,
        })
        print('%s %-6s %-5s %-8s %-36s Cat %-4s %3d일 note %d자' %
              (hid, code, region, city, kr, '-' if cat is None else cat, priced, len(note)))

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-27'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n')

    hs = tab['hotels']
    cells = sum(len(h['points']['$v']) for h in hs)
    priced = sum(1 for h in hs for v in h['points']['$v'] if v is not None)
    reg = collections.Counter(h['region'] for h in hs)
    print('hotels', len(hs), 'cells', cells, 'priced', priced, dict(reg))
    assert len(hs) == 584 and cells == 584 * 365 == 213160
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['남아시아'] == 40 and reg['캐나다'] == 39 and reg['유럽'] == 138
    assert reg['미국'] == 209 and reg['동남아'] == 61 and reg['일본'] == 23
    assert reg['중국·중화권'] == 15 and reg['오세아니아'] == 14 and reg['한국'] == 9
    assert reg['중동'] == 31 and reg['아프리카'] == 5
    assert priced == 171774 + 4739, priced
    print("EXPECT_HYATT = {'hotels': %d, 'cells': %d, 'priced': %d}" % (len(hs), cells, priced))


if __name__ == '__main__':
    main()
