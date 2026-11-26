#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 인도 10 + 스페인 15(말라가 2 · 마요르카 13) + 오만 3 + 요르단 2 = 30곳 병합
(2026-11-27) 485 → 515곳

입력 (모두 2026-12-01~2027-11-30 365칸)
  · 6번(@jin_6) 인도 배치3 5 + 배치4 5 = 10곳
      memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0448/received/0-hyatt-in-batch3-5.json
      memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0458/received/0-hyatt-in-batch4-5.json
      (hyatt.com 포인트 캘린더 · Standard Room · 1박 · 성인2인·1실 · 56일 이하 7구간)
  · 4번(@jin_4) 스페인 2차 배치2 5 · 배치3 5 · 배치4 5 = 15곳
      memory/clones/06130525-jin489/pickle/2026-11-27-0449/received/0-hyatt-es2-batch2.json
      memory/clones/06130525-jin489/pickle/2026-11-27-0453/received/0-hyatt-es2-batch3.json
      memory/clones/06130525-jin489/pickle/2026-11-27-0500/received/0-hyatt-es2-batch4.json
      (avail/days · STANDARD_ROOM · 성인2·2박 기준, 배치4는 60일 창 7개)
  · 7번(@no_7) 오만 3 + 요르단 2 = 5곳
      memory/clones/a03363f4-no71/pickle/2026-11-27-0449/received/0-hyatt_me_batch6_5.json
      (avail/days · STANDARD_ROOM · 성인2·1박 · 60일 창 6+5일 1)

■ 규칙
- 마스터(1-hyatt-global-master.json)의 30개 spiritCode 와 이름·카테고리·브랜드·WoH 참여를 배치본과 대조.
  카드 region 은 마스터 area 를 이 탭 표기로 나눠 적는다 — 인도 → 남아시아(마스터 area 그대로) /
  스페인 → 유럽 / 오만·요르단 → 중동(마스터는 '중동·아프리카').
- 기존 485곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조.
- category 는 마스터 값 그대로(A0/A1/A2/A3 문자열 또는 정수) — Alua·Secrets·Zoëtry 는 이미 A0/A1/A2
  문자열로 실려 있어 같은 표기를 쓴다. wllin 은 WoH 미참여라 category null.
- 지시대로 「개관 전」 문구는 쓰지 않는다 — 30곳 모두 영업 중이고, 0칸인 호텔은 사유(시즌 휴장 ·
  어워드 재고 미표시 · 현금 전용 · 판매 중단)를 카드 메모에 적는다.
- points 는 {"$d":"2026-12-01","$v":[365개]}, null 은 보간 없이 유지.
- rates_official·rates_hlx 는 null — 세 배치 모두 현금가 미수집(cash_note 참조).
- 링크는 기존 카드와 같이 공홈 예약 화면 https://www.hyatt.com/shop/rooms/{code}.
"""

import collections
import copy
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
D6A = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0448/received')
D6B = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-27-0458/received')
D4A = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-27-0449/received')
D4B = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-27-0453/received')
D4C = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-27-0500/received')
D7 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0449/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START, END = '2026-12-01', '2027-11-30'
from datetime import date, timedelta
_d0, _d1 = date(2026, 12, 1), date(2027, 11, 30)
DATES = [(_d0 + timedelta(days=i)).isoformat() for i in range((_d1 - _d0).days + 1)]
assert len(DATES) == 365

FIRST_ID = 486

# (code, 국문명, 도시, 브랜드, 카테고리, region, 묶음)
PLAN = [
    # ── 인도 배치3 5곳 — 6번(@jin_6) · 2026-11-27 04:37~04:48 KST
    ('delaa', '하얏트 델리 레지던스 에어로시티', '뉴델리', 'Hyatt Hotels', 2, '남아시아', 'IN3'),
    ('delrd', '하얏트 리젠시 델리', '뉴델리', 'Hyatt Regency', 2, '남아시아', 'IN3'),
    ('goagh', '그랜드 하얏트 고아', '고아', 'Grand Hyatt', 4, '남아시아', 'IN3'),
    ('goajd', '로닐 고아', '고아', 'JdV by Hyatt', 2, '남아시아', 'IN3'),
    ('goazc', '하얏트 센트릭 칸돌림 고아', '고아', 'Hyatt Centric', 2, '남아시아', 'IN3'),
    # ── 인도 배치4 5곳 — 6번(@jin_6) · 2026-11-27 04:49~04:57 KST
    ('goazg', '하얏트 플레이스 고아 칸돌림', '고아', 'Hyatt Place', 2, '남아시아', 'IN4'),
    ('goial', '알릴라 디와 고아', '고아', 'Alila', 3, '남아시아', 'IN4'),
    ('amdhy', '하얏트 아메다바드', '아메다바드', 'Hyatt Hotels', 1, '남아시아', 'IN4'),
    ('amdzv', '하얏트 플레이스 비탈라푸르', '아메다바드', 'Hyatt Place', 1, '남아시아', 'IN4'),
    ('amdhr', '하얏트 리젠시 아메다바드', '아메다바드', 'Hyatt Regency', 1, '남아시아', 'IN4'),
    # ── 스페인 2차 배치2 5곳 — 4번(@jin_4) · 2026-11-27 05:10 KST
    ('auctp', '알루아선 코스타 파크', '말라가', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES2'),
    ('aulgr', '알루아선 라고 로호', '말라가', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES2'),
    ('alboc', '알루아 보카치오', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES2'),
    ('drcam', '알루아 칼비아', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES2'),
    ('alcdm', '알루아 그란 캄프 데 마르', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES2'),
    # ── 스페인 2차 배치3 5곳(마요르카) — 4번(@jin_4) · 2026-11-27 05:00 KST
    ('alleo', '알루아 레오', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES3'),
    ('wllin', '알루아 린다 마요르카', '마요르카', 'Alua Hotels & Resorts', None, '유럽', 'ES3'),
    ('alroc', '알루아 스위트 라스 로카스', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES3'),
    ('ascar', '알루아솔 캐롤라이나', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES3'),
    ('asmal', '알루아솔 마요르카 리조트', '마요르카', 'Alua Hotels & Resorts', 'A1', '유럽', 'ES3'),
    # ── 스페인 2차 배치4 5곳(마요르카) — 4번(@jin_4) · 2026-11-27 05:15 KST
    ('aspmi', '알루아솔 팔마', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES4'),
    ('aucan', '알루아선 칼라 안테나', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES4'),
    ('aucnp', '알루아선 컨티넨탈 파크', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES4'),
    ('zoehm', '조에트리 마요르카', '마요르카', 'Zoëtry', 'A2', '유럽', 'ES4'),
    ('secvm', '시크릿츠 마요르카 비야밀', '마요르카', 'Secrets', 'A3', '유럽', 'ES4'),
    # ── 오만 3 + 요르단 2 — 7번(@no_7) · 2026-11-27 04:40~04:50 KST
    ('mctal', '알릴라 자발 아크다르', '알 자발 알 아크다르', 'Alila', 7, '중동', 'ME6'),
    ('musca', '그랜드 하얏트 무스카트', '무스카트', 'Grand Hyatt', 2, '중동', 'ME6'),
    ('sllal', '알릴라 히누 베이', '살랄라', 'Alila', 5, '중동', 'ME6'),
    ('ammgh', '그랜드 하얏트 암만', '암만', 'Grand Hyatt', 1, '중동', 'ME6'),
    ('aqjra', '하얏트 리젠시 아카바 아일라', '아카바', 'Hyatt Regency', 3, '중동', 'ME6'),
]

COUNTRY_KO = {'IN3': '인도', 'IN4': '인도', 'ES2': '스페인', 'ES3': '스페인', 'ES4': '스페인',
              'ME6': '오만'}
PROVIDER = {'IN3': '6번(@jin_6)', 'IN4': '6번(@jin_6)', 'ES2': '4번(@jin_4)',
            'ES3': '4번(@jin_4)', 'ES4': '4번(@jin_4)', 'ME6': '7번(@no_7)'}
CASH = {
    'IN': ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아(1박 단위 '
           'shop/rooms 화면에서만 표시) 현금가는 미수집이고, 위에 적은 현금 금액은 같은 날짜대의 공홈 '
           '1박 검색에서 확인한 참고값입니다. 호럭 요금도 미수집입니다.'),
    'ES': ('현금 요금은 365일 전부 —입니다 — 지시대로 현금(rooms/roomrates) 호출을 하지 않아'
           ' 미수집으로 두었고, 위에 적은 현금 금액은 공홈 검색 화면에 표시된 참고값입니다. '
           '호럭 요금도 미수집입니다.'),
}
# 공홈 캘린더·검색 화면에 표시된 어워드 카테고리 글자(배치본이 확인한 값, 기본 A)
DISPLAY = {'zoehm': 'C', 'secvm': 'D'}
CASH['ME'] = ('현금 요금은 365일 전부 —입니다 — 이 엔드포인트는 어워드 포인트만 주고 현금가는 다른 '
              '경로라 미수집입니다. 호럭 요금도 미수집입니다.')

# 호텔별 보강 — 배치본 note 에 있는 사실만 옮겨 적는다
EXTRA = {
    'delaa': ('365일 전부 null — 7구간 모두 days:{} + responseInfo:soldOutHotel 이었고, los 1·3·7·14 와 '
              'STANDARD_SUITE 조회도 어워드가 없었다. 같은 기간 현금 객실은 정상 판매(2026-12-10 1박 '
              '원베드룸 아파트먼트 ₩338,907~ · 2027-02-05 ₩402,852~)이고, Use Points 필터 1박 조회는 '
              "'No Available Rooms', 검색 카드는 'Hotel Not Available'이어서 휴관·미개관이 아니라 이 "
              '레지던스 호텔이 포인트·프리나이트 어워드 재고를 열지 않는 상태다. 같은 계열 안다즈 '
              '델리(delaz)는 스탠다드룸 어워드가 정상으로 열린다.'),
    'delrd': ('분포: 7,500P 280일 · 10,000P 45일 · 6,000P 16일 · 12,000P 2일(2027-02-10~11 PEAK) · '
              'null 22일. 2026-12월 캘린더 29칸과 전수 대조해 일치했다(12-01·03~05·08~12·17~19·21 '
              '값 없음). null 22일은 그 1박 스탠다드룸 포인트 어워드가 없는 날이고(CLUB·SUITE 대체 '
              '어워드도 없음), 호텔은 정상 영업 중이다(2027-02-05 1박 현금 ₩481,493~).'),
    'goagh': ('분포: 20,000P 145일 · 15,000P 164일 · 12,000P 14일 · null 42일. 12-25~31 연말 성수기 '
              '7일 연속 공백인데 같은 2026-12-26~27 1박 현금이 ₩480,748~로 정상 판매 중이어서 휴관이 '
              '아니라 재고 미개방이다. 12-05는 캘린더 칸이 비었으나 shop/rooms 포인트 조회에서 '
              '프리나이트 어워드 20,000P 가 예약 가능해 API 값을 채택했다(goazc 12-28과 같은 성격).'),
    'goajd': ('분포: 10,000P 176일 · 7,500P 171일 · 6,000P 14일 · null 4일(2026-12-04·12-10~12). '
              '2026-12월 캘린더 29칸과 전수 대조해 일치했고, 2026-12-26~27 1박 현금 ₩250,998~로 '
              '정상 판매 중이다.'),
    'goazc': ('분포: 10,000P 175일 · 7,500P 171일 · 6,000P 14일 · null 5일(2026-12-09~10·12-24·'
              '12-26·12-31). 12-28은 캘린더 칸·패널이 값 없음이었지만 shop/rooms 포인트 조회에서 '
              '10,000P 프리나이트 어워드가 예약 가능해 API 값을 채택했다. 같은 고아의 로닐 고아'
              '(goajd)와 계절 곡선이 같다. 2026-12-26~27 1박 현금 ₩262,197~.'),
    'goazg': ('분포: 10,000P 170일 · 7,500P 171일 · 6,000P 14일 · null 10일(2026-12-02·12-11~12·'
              '12-18·12-24~25·12-28~30, 2027-01-01). 12-02는 1박 화면에서 체크아웃 셀이라 avail/days '
              '를 2026-12-02~12-04 로 다시 조회해 날짜 키가 없음을 확인했다.'),
    'goial': ('창 전체에서 5일(2026-12-06·07·10·11·25, 각 15,000P Standard)만 어워드가 열려 있고 '
              '나머지 360일은 null 이다. 2026-12월·2027-06월 캘린더 화면도 같은 결과였고, 2027-02-10 '
              "1박 'Use Points' 조회에서 스탠다드룸 프리나이트는 없으나 'Diwa Club Suite' 스위트 "
              '포인트 업그레이드(₩581,315 + 6,000P/Night)가 판매 중이어서 그 시점은 휴관이 아니었다 — '
              '스탠다드 어워드 미개방이고, 우기철 휴관 여부는 사이트가 밝히지 않아 단정하지 않았다.'),
    'amdhy': ('분포: 4,500P 220일 · 3,000P 14일 · 6,000P 12일 · null 119일. null 은 2026-12-02~05'
              '(4일)와 2026-12-07~2027-03-31(115일 연속) 두 구간으로, 2027-02월 캘린더도 전칸 값 '
              "없음·'No Rooms Available'이었다. 같은 2027-02-10 1박 현금은 ₩301,943~로 정상 판매 "
              '중이어서 휴관이 아니라 포인트 재고 미개방이다.'),
    'amdzv': ('365일 전부 값이 있고 null 0일이다(4,500P 307일 · 6,000P 44일 · 3,000P 14일). '
              '2027-02-10 1박 현금 ₩112,372~로 정상 판매 중이다.'),
    'amdhr': ('분포: 4,500P 189일 · 3,000P 14일 · 6,000P 13일 · null 149일. null 은 세 성격이다 — '
              '(1) 2026-12-02~05·12-10~12·12-15~19 와 2027-01-08~02-28(52일)은 그 1박 스탠다드룸 '
              '어워드가 없는 날(같은 2027-02-10 현금 ₩286,535~로 정상 판매 → 휴관 아님), '
              '(2) 2027-09-07~11-30(85일)은 responseInfo:soldOutHotel 로 현금 검색도 '
              "'Hotel Not Available'인 유일한 판매 중단 블록(같은 날짜의 하얏트 아메다바드 · "
              '하얏트 플레이스 비탈라푸르는 정상 노출), (3) 어느 null 날짜에도 CLUB·SUITE 대체 '
              '어워드는 없었다.'),
    'auctp': ('분포: 15,000P(Off-peak) · 20,000P(Standard) · 25,000P(Super-peak) 의 A0 그리드다. '
              '2026-12-01~2027-02-28 과 2027-10-31~11-30 은 2박·성인2 조회가 전부 soldOutHotel 이고 '
              '3월 1일부터 값이 나와 10월 30일이 마지막 날이어서 동계 휴장(시즌 운영)으로 판단했다'
              '(02-24~28·10-31~11-04·11-25~30 좁은 창 재조회도 동일). 2027-07-15~07-20 은 2박 창에 '
              '키가 없어(최소숙박 7박 구간) los=7 재조회값 20,000 을 썼다.'),
    'aulgr': ('동계·봄은 12,000P(Super-off-peak) 위주로 값이 있으나 날짜 블록이 끊겨 있고(2박·7박 '
              '모두 없는 구간), 하계·추계는 어워드 재고 자체가 없다. 2027-04-30 이후 전 구간이 2박 '
              "조회 soldOutHotel 이고 공홈 검색(포인트 필터)도 '선택한 날짜에는 포인트 요금 이용 "
              '불가\'(현금 ₩267,102/박 판매)여서 하계는 현금 전용이다.'),
    'alboc': ('전 기간 2박·성인2 조회가 soldOutHotel 이다(겨울 12월·2월·3~4월·5월·7월(2박·7박)·9월·'
              '10월 표본 모두 동일). 공홈 검색(포인트 필터)에서 현금 ₩248,744/박은 판매되지만 '
              "\'선택한 날짜에는 포인트 요금 이용 불가\'여서 현금 전용 · 어워드 재고 미표시 상태다 — "
              '영업 중인 호텔이고 휴장이 아니다.'),
    'drcam': ('전 기간 2박·성인2 조회가 soldOutHotel 이고 공홈 포인트 캘린더 UI 도 \'이용 가능한 '
              '객실 없음\'·\'--\'다. 공홈 검색(2027-09-10~09-17 포인트 필터)에서 이 호텔은 '
              "\'Unavailable\'(현금도 미표시)로, 온라인 판매 자체가 열리지 않는 상태다."),
    'alcdm': ('전 기간 2박·성인2 조회가 soldOutHotel 이고 공홈 포인트 캘린더 UI 도 \'이용 가능한 '
              "객실 없음\'이다. 공홈 검색(2027-07-10 · 2027-09-10~09-17)에서도 'Unavailable(이용 "
              '가능 여부는 호텔 웹사이트를 참조하세요)\'로 온라인 판매가 표시되지 않는다.'),
    'alleo': ('numAdults=2·los=2 20일 창 19개(365일 전량)가 전부 days:{} + soldOutHotel 이고, '
              'los=7·los=3·성인1·roomCategory 미지정 조회도 모두 같은 응답이었다. 공홈 포인트 '
              "캘린더도 1박·2박 모두 11월 셀 전부 값 없음·합계 '--'·예약 버튼 비활성, 2027년 7월은 "
              '월 버튼 전체 비활성이었다.'),
    'wllin': ('공홈 UI 에는 \'4 (24)\'만 표시되고 어워드 카테고리 라벨 자체가 없다. '
              'numAdults=2·los=2 20일 창 19개가 전부 soldOutHotel '
              "이고 공홈 UI 도 '이용 가능한 객실 없음'·11월~5월 버튼 전부 비활성이다. 영업 중인 "
              '호텔이며 미오픈·휴관이 아니다.'),
    'alroc': ('numAdults=2·los=2 20일 창 19개가 전부 soldOutHotel 이고, 공홈 UI 도 \'어워드 '
              "카테고리 A\'(4성 169리뷰)·'이용 가능한 객실 없음'·월 버튼 전부 비활성이다."),
    'ascar': ('numAdults=2·los=2 20일 창 19개가 전부 soldOutHotel 이고, 공홈 UI 는 셀 전부 '
              "공백('11월 27일: --')이며 2027년 7월을 누르면 포인트 캘린더 로드 오류 모달이 떴다."),
    'asmal': ('numAdults=2·los=2 20일 창 19개가 전부 soldOutHotel 이고, 공홈 UI 는 첫 접속에서 '
              '포인트 캘린더 로드 오류 모달이 뜨고 재접속하면 헤더 공백 + \'이용 가능한 객실 '
              '없음\' + 월 버튼 전부 비활성이었다(마스터 Cat A1).'),
    'aspmi': ('60일 창 7개가 전부 soldOutHotel 이고 20·30일 창·los=7·roomCategory=ROOM 교차 조회도 '
              '같았다. 같은 파라미터로 secvm 은 전 시즌 값이 정상 반환돼 파라미터 오류가 아니며, '
              '가짜 코드(qqqqq)도 같은 soldOutHotel 을 돌려주므로 공홈 포인트 캘린더·검색에서 호텔명·'
              "Award Category 표기를 따로 확인해 코드 유효를 확인했다. 공홈 2박2인 캘린더도 "
              "'No Rooms Available' — 성인전용 비치프런트 호텔로 영업 중이며 어워드·현금 재고가 "
              '공홈에 표시되지 않는다.'),
    'aucan': ('60일 창 7개 + los=7 30일 프로브가 모두 soldOutHotel 이고 공홈 2박2인 캘린더도 '
              "'No Rooms Available' — 올인클루시브로 영업 중이나 어워드·현금 재고가 공홈에 "
              '표시되지 않는다.'),
    'aucnp': ('60일 창 7개 + los=7 30일 프로브가 모두 soldOutHotel 이고 공홈 2박2인 캘린더도 '
              "'No Rooms Available' — 플라야 데 무로의 올인클루시브로 영업 중이나 어워드·현금 "
              '재고가 공홈에 표시되지 않는다.'),
    'zoehm': ('60일 창 7개 + los=7 30일 프로브가 모두 soldOutHotel 이고 공홈 검색 Points 필터는 '
              "'Point rates unavailable'이다 — 2027년 7월 현금 판매(₩509,539/박)가 확인돼 영업 중이며 "
              '어워드 재고만 표시되지 않는다.'),
    'secvm': ('2027-03-19~10-30 시즌 운영이라 222일만 값이 있고 나머지 143일은 null 이다. '
              'STANDARD_ROOM 4단 그리드 25,000(Super-off-peak) · 30,000(Off-peak) · '
              '35,000(Standard) · 45,000(Peak) 가 전 기간 일관되고(레벨 이탈 0건), 2027-07-13 은 '
              '45,000P(2박째 35,000)였다. 2027-04-20~04-23 은 스탠다드룸 미표시(CLUB 39,000 · '
              'SUITE 48,000 만)다. 공홈 표기가 마스터 카테고리와 달라 카드 카테고리는 마스터 값(A3)을 '
              '쓰고 공홈 표기를 여기에 남긴다.'),
    'mctal': ('362일 표출·3일 공백(2026-12-02~04). STANDARD_ROOM 은 SUPER_OFF_PEAK 25,000(79일) · '
              'OFF_PEAK 30,000(242일) · STANDARD 35,000(41일) 3단계만 1년 내내 표시되고 PEAK·'
              'SUPER_PEAK 은 나오지 않았다. 공백 3일은 PREMIUM_SUITE(55,000)만 있는 '
              'empty_day_object 로, 앞뒤 표출일을 포함한 좁은 창 재조회에서도 같은 형태로 재현됐다.'),
    'musca': ('362일 표출·3일 공백(2026-12-03~05). 6,000 · 7,500 · 10,000 3단계(P&SP 없음)이고 '
              '공백 3일은 날짜 키 자체가 없는 no_key_in_response 로 재조회에서도 같았다. 같은 오만 '
              '권역인 알릴라 자발 아크다르(mctal)와 레벨 날짜 구성이 완전히 같다.'),
    'sllal': ('365일 전부 표출(null 0일). 15,000 · 20,000 · 25,000 3단계이고 최고 구간이 '
              '2027-08-02~09-02(살랄 카레프·몬순 시즌)다.'),
    'ammgh': ('365일 전부 표출(null 0일). 3,000(2일) · 4,500(315일) · 6,000(48일)로 1년의 86%가 '
              'OFF_PEAK 단일가이고 PEAK·SUPER_PEAK 은 없다.'),
    'aqjra': ('365일 전부 표출(null 0일). 8,000 · 12,000 · 15,000 3단계이고 2027-01-02~03-02 '
              '60일 연속 SUPER_OFF_PEAK 다. 이 배치에서 시즌 전환이 가장 잦아 2027-03~11 은 '
              '3~10일 단위로 레벨이 바뀐다.'),
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

    for path, name, tag, keys in (
            (D6A, '0-hyatt-in-batch3-5.json', 'IN3', 'list'),
            (D6B, '0-hyatt-in-batch4-5.json', 'IN4', 'list')):
        d = json.load(open(os.path.join(path, name), encoding='utf-8'))
        assert d['window'] == {'start': '2026-12-01', 'end': '2027-11-30', 'days': 365}
        for h in d['hotels']:
            add(h['code'], dict(h, _tag=tag, _file=name), tag)
    for path, name, tag in (
            (D4A, '0-hyatt-es2-batch2.json', 'ES2'),
            (D4B, '0-hyatt-es2-batch3.json', 'ES3'),
            (D4C, '0-hyatt-es2-batch4.json', 'ES4'),
            (D7, '0-hyatt_me_batch6_5.json', 'ME6')):
        d = json.load(open(os.path.join(path, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30', (name, d['meta']['window'])
        for code, h in d['hotels'].items():
            add(code, dict(h, _tag=tag, _file=name), tag)
    assert len(hotels) == 30, len(hotels)
    return hotels


def pts_of(h):
    raw = h.get('points') or {}
    if isinstance(raw, list):
        raw = dict(raw)
    return [raw.get(d) for d in DATES]


def head(tag, code, city, cat, priced):
    cat_txt = 'null' if cat is None else str(cat)
    if tag in ('IN3', 'IN4'):
        s = ('하얏트 공홈 포인트 캘린더(explore-hotels/rate-calendar · Standard Room · 1박 · 성인2인·'
             '1실)로 2026-12-01~2027-11-30 365칸을 실측했다(2026-11-27 04:37~04:57 KST · '
             '6번(@jin_6) · %s · 인도). 값은 캘린더 화면의 데이터 원천인 공홈 avail/days 응답'
             '(roomCategory=STANDARD_ROOM·los=1)에서 날짜별 STANDARD_ROOM pointsValue 를 읽었고, '
             '조회는 56일 이하 7구간(총 35회)으로 나눠 정상 응답한 범위만 기록했다. 공홈 표시 '
             '어워드 카테고리 %s이고 값이 있는 날은 %d일이다.' % (city, cat_txt, priced))
        return s
    if tag in ('ES2', 'ES3', 'ES4'):
        if tag == 'ES2':
            s = ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory='
                 'STANDARD_ROOM · 성인2·2박 기준, 2박 불가 구간은 7박 재조회 · 20일 이하 창 타일링)으로 '
                 '2026-12-01~2027-11-30 365칸을 실측했다(2026-11-27 05:10 KST · 4번(@jin_4) · %s · '
                 '스페인). Alua 올인클루시브는 1박·1인 판매를 하지 않아 (성인1·1박) 조회는 호텔 전체를 '
                 'soldOutHotel 로 돌려주고, (성인2·2박)으로 조회해야 정상 값이 나온다(auctp 2027-07-10 '
                 '20,000P — 공홈 객실 페이지와 일치).' % city)
        elif tag == 'ES3':
            s = ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory='
                 'STANDARD_ROOM · 성인2·2박 고정 · 20일 창 19개로 365일 전량)으로 실측했다'
                 '(2026-11-27 05:00 KST · 4번(@jin_4) · %s · 스페인). (성인2·2박) 말고 los=3·7·'
                 '성인1·roomCategory 미지정 조회도 전부 soldOutHotel 이어서 최소숙박·인원 파라미터 '
                 '아티팩트가 아니라 어워드 재고 자체가 공홈에 표시되지 않는 상태로 판정했다.' % city)
        else:
            s = ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory='
                 'STANDARD_ROOM · 성인2·2박 · 60일 창 7개(마지막 5일) 타일링) + 공홈 포인트 캘린더·'
                 '검색(Points 필터) 대조로 2026-12-01~2027-11-30 365칸을 실측했다(2026-11-27 05:15 '
                 'KST · 4번(@jin_4) · %s · 스페인).' % city)
        if cat is None:
            s += (' 공홈에 어워드 카테고리 라벨이 없어 카테고리는 null(월드 오브 하얏트 미참여)이고 '
                  '값이 있는 날은 %d일이다.' % priced)
        else:
            s += ' 공홈 표시 어워드 카테고리 %s · 마스터 표기 %s이고 값이 있는 날은 %d일이다.' % (
                DISPLAY.get(code, 'A'), cat_txt, priced)
        return s
    s = ('하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM · '
         '성인2·1박)을 60일 창 6회 + 5일 창 1회로 나눠 2026-12-01~2027-11-30 365칸을 실측했다'
         '(2026-11-27 04:40~04:50 KST · 7번(@no_7) · %s · 오만·요르단). 창은 모두 실제 페이지 로드로 '
         '응답 JSON 을 받아 파싱했고, null 구간은 앞뒤 표출일을 포함한 좁은 창 2개로 다시 조회해 '
         '값·레벨 불일치 0건을 확인했다. 공홈 표시 어워드 카테고리 %s이고 값이 있는 날은 %d일이다.'
         % (city, cat_txt, priced))
    return s


def build_note(tag, code, city, cat, priced):
    facts = [head(tag, code, city, cat, priced), EXTRA[code]]
    cash = CASH[tag[:2]]
    if '₩' not in ' '.join(facts):
        for clause in ('위에 적은 현금 금액은 공홈 검색 화면에 표시된 참고값입니다. ',
                       '위에 적은 현금 금액은 같은 날짜대의 공홈 1박 검색에서 확인한 참고값입니다. '):
            cash = cash.replace(clause, '')
    bits = facts + [cash, '%s이 실측해 보낸 본입니다.' % PROVIDER[tag]]
    note = ' '.join(note_bit for note_bit in bits if note_bit)
    note = ' '.join(note.split())
    assert '개관 전' not in note, code
    return note


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 485, len(before)
    assert before[-1]['id'] == 'hy485', before[-1]['id']

    hotels = load()
    assert set(hotels) == {p[0] for p in PLAN}, sorted(set(hotels) ^ {p[0] for p in PLAN})

    # ── 공홈 마스터 대조 ─────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    AREA_OK = {'유럽': '유럽', '남아시아': '남아시아', '중동': '중동·아프리카'}
    for code, kr, city, brand, cat, region, tag in PLAN:
        m, h = byc[code], hotels[code]
        assert norm(m['name']) == norm(h['name']), (code, m['name'], h['name'])
        assert m['area'] == AREA_OK[region], (code, m['area'], region)
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert str(cat) == str(h['category']), (code, cat, h['category'])
        assert clean(h['brand']) == clean(brand) == clean(m['brand']), (code, h['brand'], brand, m['brand'])
        assert m['woh_participating'] is (cat is not None), (code, m['woh_participating'], cat)
        print('%-6s %-6s Cat %-4s WoH %-5s %s' % (code, region, m['category'],
                                                   m['woh_participating'], m['name']))

    # ── 기존 485곳 중복 확인 ─────────────────────────────────────────
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
    print('기존 485곳 대조 — code·영문명·국문명 중복 0건')

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
    print('① 호텔럭스 161곳 대조 — 겹침 0곳 · ① 탭 도시 %d개' % len({clean(r.get('city')) for r in rows}))

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
        print('%s %-6s %-5s %-8s %-30s Cat %-4s %3d일' %
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
    assert len(hs) == 515 and cells == 515 * 365, (len(hs), cells)
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['유럽'] == 128 and reg['남아시아'] == 20 and reg['중동'] == 31 and reg['아프리카'] == 5
    assert reg['미국'] == 209 and reg['동남아'] == 61 and reg['일본'] == 23
    assert reg['중국·중화권'] == 15 and reg['오세아니아'] == 14 and reg['한국'] == 9
    assert priced == 152594 + 4957, priced
    print('EXPECT_HYATT = {\'hotels\': %d, \'cells\': %d, \'priced\': %d}' % (len(hs), cells, priced))


if __name__ == '__main__':
    main()
