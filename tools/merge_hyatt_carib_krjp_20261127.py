#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 카리브·중미 20곳 신규(613 → 633곳) + 한국 9 · 일본 11 = 20곳 90일 재실측
(2026-11-27)

A. 신규 20곳 — No.7(@no_7) · 2026-11-27 07:35~10:20 KST
  · memory/clones/a03363f4-no71/pickle/2026-11-27-0553/received/0-hyatt_carib_batch1_5.json
      (auaza · aruba · seaua — 아루바 3, liraz · sjozc — 코스타리카 2)
  · .../0-hyatt_carib_batch2_5.json  (sepcr · sjozp · sjoct 코스타리카 3, drcur · sucur 퀴라소 2)
  · .../0-hyatt_carib_batch3_5.json  (zocur 퀴라소 1, drrhm · mbjia · mbjif · grmbj 자메이카 몬테고베이 4)
  · .../0-hyatt_carib_batch4_5.json  (sesmb · bp014 · bp013 · bremb · sewmb 자메이카 5)
  (hyatt.com explore-hotels/avail/days · roomCategory=ROOM · STANDARD_ROOM · 성인2·1박 ·
   60일 창 6회 + 5일 창 1회 = 365일 · 재조회 창 추가)

B. 90일 재실측 — 5번(@jin_5) · 2026-11-27 07:30~ KST
  · memory/clones/f0ee2d96-jin_5/pickle/2026-11-27-0600/received/0-2026-11-27-hyatt-refresh-batch{1..4}-5.json
  points 의 앞 90일(2026-12-01~2027-02-28)만 새 실측값으로 교체.
  rates_official(현금가) 는 5번 파일에서 null(not_remeasured) 이므로 기존 11-22/23 세후 KRW 값을
  그대로 둔다 — 절대 덮어쓰지 않는다.

■ 규칙
- region 은 마스터(1-hyatt-global-master.json) area 그대로 — 20곳 전부 '중남미·카리브'.
  카드 도시는 국가를 앞에 붙여 적는다(같은 name 의 도시가 4개국에 흩어져 있어 오해를 막는다).
- brand·category 는 마스터 값(Hyatt Partners · World of Hyatt 미참여인 grmbj 는 category null).
- points 는 {"$d":"2026-12-01","$v":[365개]}, 응답에 없는 날은 보간 없이 null.
- rates_official·rates_hlx 는 null(현금가 미수집) · links.official 은 공홈 예약 화면.
- note 에 마크다운 ** 별표, 긴 URL, 달력이 호텔 전체 미오픈 신호로 읽는 「개관 전」 문구를 쓰지 않는다.
- ① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0.
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
D7 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-27-0553/received')
D5 = os.path.join(WS, 'memory/clones/f0ee2d96-jin_5/pickle/2026-11-27-0600/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START, END = '2026-12-01', '2027-11-30'
_d0, _d1 = date(2026, 12, 1), date(2027, 11, 30)
DATES = [(_d0 + timedelta(days=i)).isoformat() for i in range((_d1 - _d0).days + 1)]
assert len(DATES) == 365
FIRST_ID = 614

CARIB = {
    'C1': '0-hyatt_carib_batch1_5.json',
    'C2': '0-hyatt_carib_batch2_5.json',
    'C3': '0-hyatt_carib_batch3_5.json',
    'C4': '0-hyatt_carib_batch4_5.json',
}
TIME = {
    'C1': '2026-11-27 07:40~08:55 KST',
    'C2': '2026-11-27 07:35~ KST',
    'C3': '2026-11-27 08:00~09:40 KST',
    'C4': '2026-11-27 08:25~10:20 KST',
}

# (code, 국문명, 카드 도시, 묶음)
PLAN = [
    # ── 아루바 3 · 코스타리카 2 — C1
    ('auaza', '하얏트 플레이스 아루바 에어포트', '아루바 오라녜스타트', 'C1'),
    ('aruba', '하얏트 리젠시 아루바 리조트 스파 앤 카지노', '아루바 팜비치', 'C1'),
    ('seaua', '시크릿츠 베이비 비치 아루바', '아루바 산니콜라스', 'C1'),
    ('liraz', '안다즈 페닌슐라 파파가요 리조트 코스타리카', '코스타리카 과나카스테', 'C1'),
    ('sjozc', '하얏트 플레이스 카리아리 컨벤션 센터', '코스타리카 에레디아', 'C1'),
    # ── 코스타리카 3 · 퀴라소 2 — C2
    ('sepcr', '시크릿츠 파파가요 코스타리카', '코스타리카 파파가요', 'C2'),
    ('sjozp', '하얏트 플레이스 산호세 피나레스', '코스타리카 산호세', 'C2'),
    ('sjoct', '하얏트 센트릭 산호세 에스카수', '코스타리카 산호세 에스카수', 'C2'),
    ('drcur', '드림스 쿠라사오 리조트 스파 앤 카지노', '쿠라사오 빌렘스타트', 'C2'),
    ('sucur', '선스케이프 쿠라사오 리조트 스파 앤 카지노', '쿠라사오 빌렘스타트', 'C2'),
    # ── 퀴라소 1 · 자메이카 몬테고베이 4 — C3
    ('zocur', '조에트리 쿠라사오 리조트 앤 스파', '쿠라사오 빌렘스타트', 'C3'),
    ('drrhm', '드림스 로즈홀 리조트 앤 스파', '자메이카 몬테고베이', 'C3'),
    ('mbjia', '하얏트 질라라 로즈홀', '자메이카 몬테고베이', 'C3'),
    ('mbjif', '하얏트 지바 로즈홀', '자메이카 몬테고베이', 'C3'),
    ('grmbj', '주얼 그랜드 몬테고베이', '자메이카 몬테고베이', 'C3'),
    # ── 자메이카 5 — C4
    ('sesmb', '시크릿츠 세인트제임스 몬테고베이', '자메이카 몬테고베이', 'C4'),
    ('bp014', '바이아 프린시페 이스케이프 러너웨이 베이', '자메이카 러너웨이베이', 'C4'),
    ('bp013', '바이아 프린시페 익스플로어 자메이카', '자메이카 러너웨이베이', 'C4'),
    ('bremb', '브레스리스 몬테고베이 리조트 앤 스파', '자메이카 세인트제임스', 'C4'),
    ('sewmb', '시크릿츠 와일드 오키드 몬테고베이', '자메이카 세인트제임스 몬테고베이', 'C4'),
]
REGION = '중남미·카리브'
PROVIDER = 'No.7(@no_7)'

# 호텔별 사실 — 7번 배치본 note 에서 확인한 내용만, 별표·URL·「개관 전」 없이.
FACTS = {
    'auaza': ('공항에서 가까운 하얏트 플레이스로 365일 전부 표출됐다(공백 0일). 무료 조식·공항 셔틀을 '
              '안내한다. 2026-12-30~2027-04-27 119일이 STANDARD(15,000P)로 이어지고, 최저 '
              '8,000P 구간은 2027-09-06~09-21 16일, 여름 비수기 2027-08-12~09-05 25일은 OFF_PEAK다.'),
    'aruba': ('팜비치 비치프런트 364실 리조트다. 150일 공백 가운데 111일은 날짜 오브젝트가 비었거나 '
              '표준룸 없이 스위트만(24일 — STANDARD_SUITE 56,000~76,000P · PREMIUM_SUITE '
              '70,000~90,000P) 표출된 날이고 39일은 응답에 날짜 키가 없다. 2027-02는 28일 전부 '
              '공백이고 2026-12 8일 · 2027-01 7일 · 2027-03 2일로 겨울~초봄에 몰리며, '
              '2027-05~11은 월 25~29일이 표출된다. 공백 150일을 7개 창으로 다시 조회해 같은 형태로 '
              '재현됐다(불일치 0).'),
    'seaua': ('성인전용 올인클루시브 304스위트다. 같은 응답에 3인 기준 STANDARD_ROOM_3'
              '(37,500/45,000/52,500P)가 266일 별도 표출되지만 수집 규칙대로 STANDARD_ROOM(2인)만 '
              '담았다. 공백 62일 가운데 42일은 PREMIUM_SUITE(55,000~80,000P)만 표출된 날이고 20일은 '
              '날짜 키가 없으며, 2026-12~2027-02에 52일이 몰려 있다. 호텔 단위 soldOutHotel 응답은 '
              '한 번도 없었고 2박(los=2) 창 2개로 교차확인해도 표준룸이 없던 날은 그대로여서 최소숙박 '
              '때문이 아니다. 공백 62일은 5개 창 재조회에서 전부 재현됐다.'),
    'liraz': ('과나카스테 페닌슐라 파파가요의 리조트로 일 12% 리조트피를 안내한다. 공백 60일 가운데 '
              '58일이 응답에 날짜 키가 없는 날이고 2일(2026-12-03 · 2027-01-08)은 날짜 오브젝트가 '
              '비었다. 연말(2026-12-19~21 · 12-25~31)과 2027-03 하순~04 중순(부활절 전후), '
              '2027-11-08~13에 공백이 몰린다. PEAK 65,000P는 연말·건기 성수 주말에 붙고, 최저 '
              '35,000P는 2027-10-03~10-20 18일과 8~9월 비수기에 길게 나타난다. 공백 60일은 5개 창 '
              '재조회에서 전부 재현됐다.'),
    'sjozc': ('에레디아 카리아리 컨벤션 센터 옆 호텔로 365일 전부 표출됐다. 2027-06-11~09-05이 '
              '87일 연속 OFF_PEAK(12,000P)로 가장 길고, STANDARD(15,000P)는 2026-12-22~12-31과 '
              '2~4월·11월 주중에 흩어져 있다. 무료 조식·24시간 피트니스·야외수영장을 안내한다.'),
    'sepcr': ('202실 성인전용 올인클루시브다. 공백 147일은 날짜 키가 없는 날 63일과 날짜 오브젝트에 '
              'CLUB_3 · STANDARD_SUITE · PREMIUM_SUITE만 있고 STANDARD_ROOM이 없는 날 84일로 '
              '나뉜다. ±2일 버퍼를 둔 6개 창으로 공백 147일 전부가 같은 형태로 재현됐고, 창에 함께 든 '
              '표출일 101일도 값·레벨이 모두 같았다(불일치 0). 가장 긴 공백은 2027-03-10~03-21 '
              '12일이다.'),
    'sjozp': ('1년의 84%가 OFF_PEAK(7,500P)로, 2027-06-11~09-05 87일과 2027-09-08~11-01 55일이 '
              '긴 OFF_PEAK 구간이다. 공백 5일(2026-12-01 · 12-02 · 12-07 · 12-09 · 12-10)은 모두 '
              '응답에 날짜 키가 없는 날이며, ±2일 버퍼 창으로 다시 조회해 같은 형태로 재현됐다.'),
    'sjoct': ('161실 부티크 호텔이다. 레벨 패턴이 같은 도시의 하얏트 플레이스 산호세 피나레스'
              '(sjozp)와 날짜까지 일치한다 — 연말 STANDARD, 1~6월 OFF_PEAK, 2026-12-20 · 2027-03-28 '
              '· 04-18만 SUPER_OFF_PEAK(8,000P)다. 같은 응답에 STANDARD_SUITE'
              '(16,000/20,000/23,000P)가 365일 함께 표출되지만 수집 규칙대로 STANDARD_ROOM만 담았다.'),
    'drcur': ('가족형 올인클루시브로, 365일 내내 응답에 STANDARD_ROOM 카테고리가 없어 값이 0일이다'
              '(날짜 키 없음 17일 · 날짜 오브젝트에 스위트·클럽만 있는 날 348일). 응답에 실린 객실 '
              '카테고리는 STANDARD_SUITE(27,000~37,000P) · STANDARD_ROOM_3(22,500~37,500P) · '
              'CLUB_3(29,500~44,500P) · PREMIUM_SUITE(30,000~40,000P) · '
              'STANDARD_SUITE_3(34,500~49,500P)이고 그 값은 원자료의 별도 파일에 보존돼 있다. 재조회 '
              '창 3개에서도 STANDARD_ROOM은 한 번도 나오지 않았다 — 로드 실패가 아니라 카테고리 구성 '
              '차이다.'),
    'sucur': ('가족형 올인클루시브로 2027-02-01부터 STANDARD_ROOM이 표출된다. 그 전인 '
              '2026-12-01~2027-01-31 62일은 CLUB(22,000~32,000P)만 있어 값이 없다. 공백 74일 '
              '가운데 19일이 날짜 키 없음, 55일이 스위트·클럽만 있는 날이며 2027-03-01~03-16 · '
              '03-30 · 04-03~04-04에도 짧게 비어 4개 창 재조회에서 모두 재현됐다. 2027-05-30~07-28 '
              '60일 창은 서비스가 빈 응답만 3회 돌려줘 30일 창 2개로 나눠 다시 쟀다(정상 표출).'),
    'zocur': ('빌렘스타트의 72스위트 부티크 올인클루시브로 공항에서 10분 거리, Dreams 쿠라사오와 '
              '골프카트로 연결된다. 공홈이 World of Hyatt 참여를 명시한다. 공백 50일(날짜 키 없음 '
              '31일 · 스위트만 표출 19일)은 3개 창 재조회에서 그대로 재현됐고, 가장 긴 공백은 '
              '2026-12-01~2027-01-04다. 공홈 지도·주소 블록이 비어 주소·전화는 확인하지 못했다.'),
    'drrhm': ('494실 올인클루시브로 365일 전부 호텔 단위 soldOutHotel 응답이라 값이 한 날도 없다. '
              '공홈 중요 공지가 이유를 밝힌다 — 허리케인 멜리사 영향으로 정상 운영을 중단했고 2027년 '
              '상반기 재개를 예상한다는 안내이며 직접 예약 취소는 1-855-752-9252로 받는다. 공지의 '
              '재개 시점과 달리 어워드 달력은 2027-11-30까지 재고가 열리지 않았다. 2박(los=2) 교차 '
              '확인과 재조회 2개 창에서도 soldOutHotel이 그대로여서 최소숙박 때문이 아니다.'),
    'mbjia': ('성인전용 올인클루시브 344실로 2027-07-01부터 STANDARD_ROOM이 열린다. '
              '2026-12-01~2027-06-30 212일은 호텔 단위 soldOutHotel(허리케인 멜리사 운영 중단, '
              '2027년 상반기 재개 예상 공지)이다. 같은 응답에 3인 기준 STANDARD_ROOM_3'
              '(52,500~82,500P)와 4인 기준 STANDARD_ROOM_4(70,000~110,000P)가 표출일 153일 내내 함께 '
              '있지만 수집 규칙대로 STANDARD_ROOM(2인)만 담았다. 2박 교차확인과 재조회 3개 창에서도 '
              '7월 이전 공백이 재현됐다.'),
    'mbjif': ('패밀리 올인클루시브로 365일 전부 호텔 단위 soldOutHotel라 값이 0일이다. 같은 로즈홀 '
              '단지의 자매 호텔 하얏트 질라라(mbjia)는 2027-07-01부터 어워드가 열리지만 지바는 '
              '2027-11-30까지 재고가 열리지 않았다. 두 호텔 모두 허리케인 멜리사 운영 중단·2027년 '
              '상반기 재개 예상 공지를 달고 있다. 2박 교차확인과 재조회 2개 창에서도 soldOutHotel이 '
              '그대로였다.'),
    'grmbj': ('World of Hyatt 미참여(Hyatt Partners) 호텔로 어워드 카테고리가 없고 365일 전부 호텔 단위 '
              'soldOutHotel 응답이라 값이 0일이다. 공홈 호텔 주소는 Hyatt 예약 페이지가 아니라 호텔 자체 '
              '사이트로 넘어가고, 그 페이지는 주소와 올인클루시브 운영만 안내할 뿐 World of Hyatt '
              '어워드·카테고리 안내가 없다 — 미참여 상태와 일치한다. 재조회 2개 창에서도 같은 응답이었다.'),
    'sesmb': ('성인전용 올인클루시브 전 객실 스위트다. 2026-12-01~2027-06-18 200일이 호텔 단위 '
              'soldOutHotel(허리케인 멜리사 운영 중단·2027년 상반기 재개 예상 공지)이고 '
              '2027-06-19부터 STANDARD_ROOM이 열린다. 같은 응답에 CLUB · CLUB_3 · '
              'STANDARD_ROOM_3가 병행 표출되지만 수집 규칙대로 STANDARD_ROOM만 담았다. 경계 창'
              '(2027-05-29~06-22)에서 06-18까지 공백·06-19부터 30,000P 표출이 그대로 재현됐고 2박 '
              '교차확인에서도 soldOutHotel이 유지됐다.'),
    'bp014': ('성인전용 올인클루시브로 옛 이름은 바이아 프린시페 럭셔리 러너웨이 베이다. 365일 전부 '
              'STANDARD_ROOM이 표출되고 응답에 다른 객실 카테고리가 아예 없으며 soldOutHotel도 한 번도 '
              '나오지 않았다. 2026-12~2027-03은 STANDARD(30,000P)가 대부분이고 2027-08 하순~10월에 '
              'SUPER_OFF_PEAK(20,000P)가 몰린다.'),
    'bp013': ('가족용 올인클루시브 647룸·워터파크로 포인트 그리드가 자매 호텔 바이아 프린시페 '
              '이스케이프 러너웨이 베이(bp014)와 같다. 2027-04-22 하루만 응답에 날짜 키가 없는데, '
              '±2일 버퍼 창과 2박 창으로 다시 열어도 그날만 빠져 그날의 표준룸 어워드 재고가 없는 것으로 '
              '확인했다(추정 없이 —).'),
    'bremb': ('성인전용 올인클루시브 150스위트로 공홈이 World of Hyatt 참여를 명시한다. '
              '2026-12-01~2027-03-30 120일은 호텔 단위 soldOutHotel(허리케인 멜리사 운영 중단)이고 '
              '2027-03-31부터 어워드가 열리는데, 그 뒤로도 금·토로 보이는 2일 블록이 36개 구간(76일) '
              '반복적으로 비어 2027-04-23~24 · 04-30~05-01 같은 주말 공백이 이어진다. 2박 창'
              '(2027-04-20~05-20)에서도 같은 날이 비어 최소숙박 조건 때문이 아니다.'),
    'sewmb': ('성인전용 올인클루시브로 어워드 응답에 STANDARD_ROOM이 한 번도 나오지 않아 값이 0일이다. '
              '2026-12-01~2027-06-18 200일은 호텔 단위 soldOutHotel(허리케인 멜리사 운영 중단, '
              '2026-06-19 재개 시점은 세인트제임스 자매 호텔과 같다)이고, 재고가 열리는 '
              '2027-06-19~11-30 165일은 표출 카테고리가 CLUB(34,000~44,000P) · CLUB_3 · '
              'PREMIUM_SUITE뿐이다. 경계 창과 2박 창 재조회에서도 같은 형태였다.'),
}

CASH = ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아'
        '(1박 단위 shop/rooms 화면에서만 표시) 미수집으로 두었습니다.')

# 90일 재실측에서 확인된 사실 — 5번(@jin_5) 보고서의 호텔별 기록만.
REFRESH_FACTS = {
    'busph': '90일이 기존 11-22/23 값과 한 칸도 다르지 않았다(수집 기준·통화·세금 기준이 같다는 교차 확인).',
    'selph': '2026년 12월은 스탠다드룸 어워드가 대부분 소진돼 스위트만 남았고(12-01~12-31 · 01-01·01-02 · '
             '01-06~01-11 없음), 2027-02부터 값이 이어진다.',
    'selrs': '2026-12-08 하루만 값이 사라졌고 나머지 89일은 기존 값 그대로다.',
    'selaz': '2026-12~2027-01 스탠다드룸 어워드가 소진돼(2026-12-01~2027-01-31 60일 없음) 2027-02부터 '
             '값이 있다.',
    'inche': '기존에 비어 있던 5일이 21,000P로 새로 표출됐다(그랜드 하얏트 인천은 CLUB 아워드 기준).',
    'cjugh': '2026년 연말과 2027-01 초에 소진이 몰려 12-16 · 12-19 · 12-24~26 · 01-04 · 01-07~01-09는 '
             'CLUB 아워드만 남았다.',
    'fukgh': '2026-12-05와 2027-01-11 두 날만 값이 없고 나머지 88일은 기존과 같다(12-05는 CLUB 26,000P만).',
    'tyoph': '2026년 12월 초·연말연시와 2027-01-11에 소진이 몰려 17일이 비었다.',
    'tyogh': '2026-12-08 · 12-14 · 12-15 세 날이 CLUB 아워드만 남아 기존 값이 사라졌다.',
    'tyoaz': '2026년 12월 초·연말과 2027-01 중순·02 중순에 소진이 몰렸다.',
    'tyoct': '2026년 12월 초와 연말에 소진이 몰려 12-25 · 12-26 · 12-30은 PREMIUM_SUITE만 남았다.',
    'tyoty': '2026-12-01~12-21 21일이 연속으로 스탠다드룸 어워드 없이 CLUB만 남았고, 2027-02에는 값이 '
             '고르게 열렸다.',
    'itmph': '10회 조회 모두 호텔 단위 soldOutHotel 응답이라 90일 전부 값이 없다(공홈 현금은 정상 판매).',
    'kyoto': '2026-12-31 하루만 값이 없고 나머지 89일은 기존 값과 완전히 일치한다.',
    'osacp': '2026년 연말 12-31~2027-01-01에만 연속으로 값이 비었다.',
    'okaro': '90일이 기존 값과 완전히 일치한다(12-04 · 12-05는 CLUB만, 12-31은 날짜 키 없음).',
    'kraaa': '2026년 연말 12-25~2027-01-02에 소진이 몰렸다(12-17 · 12-20 · 01-01 · 01-02 · 01-10 없음).',
    'buszy': '2027년 1월은 01-05 · 01-18 · 01-29 세 날만 값이 있고, 12월에도 절반이 비어 있다.',
    'selzp': '90일이 기존 값과 완전히 일치한다(12-05 · 12-24~26 · 12-31 · 01-01만 비어 있음).',
    'tyocp': '2026년 12월 중순과 2027년 1월 초·중순에 값이 비었다.',
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


def dist_text(pts):
    cnt = collections.Counter(v for v in pts if v is not None)
    return ' · '.join('%sP %d일' % ('{:,}'.format(v), n)
                      for v, n in sorted(cnt.items(), key=lambda kv: (-kv[1], -kv[0])))


def load_carib():
    hotels = {}
    for grp, name in CARIB.items():
        d = json.load(open(os.path.join(D7, name), encoding='utf-8'))
        for code, h in d['hotels'].items():
            assert code not in hotels, code
            hotels[code] = h
    assert len(hotels) == 20, len(hotels)
    return hotels


def build_note(code, grp, city, cat, pts, priced):
    head = ('하얏트 공홈 포인트 캘린더(explore-hotels/avail/days · Standard Room · 1박 · '
            '성인2인·1실)를 60일 창 6회 + 5일 창 1회로 나눠 2026-12-01~2027-11-30 365칸을 '
            '실측했다(%s · %s · %s).' % (TIME[grp], PROVIDER, city))
    if cat is None:
        catline = '공홈 표시 어워드 카테고리가 없는 호텔(World of Hyatt 미참여)이고 값이 있는 날은 %d일이다.' % priced
    else:
        catline = '공홈 표시 어워드 카테고리는 %s이고 값이 있는 날은 %d일이다.' % (cat, priced)
    bits = [head, catline]
    if priced:
        bits.append('분포: %s.' % dist_text(pts))
    bits += [FACTS[code], CASH, '%s이 실측해 보낸 본입니다.' % PROVIDER]
    note = ' '.join(bits)
    note = ' '.join(note.split())
    assert '**' not in note, code
    assert '개관 전' not in note, code
    assert 'http' not in note, code
    assert len(note) < 1400, (code, len(note))
    return note


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 613, len(before)
    assert before[-1]['id'] == 'hy613', before[-1]['id']

    carib = load_carib()
    assert set(carib) == {p[0] for p in PLAN}, sorted(set(carib) ^ {p[0] for p in PLAN})

    # ── 공홈 마스터 대조 ─────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    for code, kr, city, grp in PLAN:
        m, h = byc[code], carib[code]
        assert norm(m['name']) == norm(h['name']), (code, m['name'], h['name'])
        assert m['area'] == REGION, (code, m['area'])
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert norm(m['brand']) == norm(h['brand']), (code, m['brand'], h['brand'])
        print('%-6s %-4s Cat %-4s %-46s (%s · %s)' % (
            code, m['country'], m['category'], m['name'], city, grp))
    assert byc['grmbj']['woh_participating'] is False
    assert all(byc[p[0]]['woh_participating'] is True for p in PLAN if p[0] != 'grmbj')

    # ── 기존 613곳 중복 확인 ─────────────────────────────────────────
    exist_codes = {x['code']: x['id'] for x in before}
    exist_en, exist_ko = {}, {}
    exist_tokens = {x['id']: set(norm(x['english']).split()) for x in before}
    for x in before:
        exist_en.setdefault(norm(x['english']), []).append(x['id'])
        exist_ko.setdefault(norm_ko(x['name']), []).append(x['id'])
    seen_en, seen_ko = {}, {}
    for code, kr, city, grp in PLAN:
        h = carib[code]
        assert code not in exist_codes, ('code dup', code)
        assert not exist_en.get(norm(h['name'])), ('english dup', code)
        assert not exist_ko.get(norm_ko(kr)), ('korean dup', code, kr)
        assert norm(h['name']) not in seen_en, ('batch english dup', code)
        assert norm_ko(kr) not in seen_ko, ('batch korean dup', code)
        seen_en[norm(h['name'])] = code
        seen_ko[norm_ko(kr)] = code
        toks = set(norm(h['name']).split())
        for hid, et in exist_tokens.items():
            assert not toks <= et, ('same hotel?', code, hid, et)
    print('기존 613곳 대조 — code·영문명·국문명 중복 0건')

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
    for code, kr, city, grp in PLAN:
        h = carib[code]
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
    for i, (code, kr, city, grp) in enumerate(PLAN):
        hid = 'hy%d' % (FIRST_ID + i)
        info = carib[code]
        pts = [info['points'].get(d) for d in DATES]
        assert len(pts) == 365
        assert all(v is None or (isinstance(v, int) and v > 0) for v in pts)
        priced = sum(1 for v in pts if v is not None)
        assert priced == info['days_priced'], (code, priced, info['days_priced'])
        m = byc[code]
        cat = m['category']
        cat = None if cat is None else (int(cat) if str(cat).isdigit() else str(cat))
        note = build_note(code, grp, city, cat, pts, priced)
        added.append({
            'id': hid, 'group': 'hyatt', 'code': code, 'region': REGION, 'city': city,
            'name': kr, 'english': clean(m['name']), 'brand': clean(m['brand']), 'category': cat,
            'vip_id': None, 'alsoIn': None, 'hlx_in': False,
            'points': {'$d': DATES[0], '$v': pts},
            'rates_official': None, 'rates_hlx': None,
            'links': {'official': 'https://www.hyatt.com/shop/rooms/%s' % code, 'hlx': None},
            'promotion': None, 'note': note,
        })
        print('%s %-6s %-26s %-46s Cat %-4s %3d일 note %d자' % (
            hid, code, city, kr, cat, priced, len(note)))

    tab['hotels'] = before + added

    # ══ B. 한국 9 · 일본 11 = 20곳 90일 재실측 ═══════════════════════
    REFRESH_FILES = ['0-2026-11-27-hyatt-refresh-batch1-5.json',
                     '0-2026-11-27-hyatt-refresh-batch2-5.json',
                     '0-2026-11-27-hyatt-refresh-batch3-5.json',
                     '0-2026-11-27-hyatt-refresh-batch4-5.json']
    by_code = {h['code']: h for h in tab['hotels']}
    done = []
    for name in REFRESH_FILES:
        d = json.load(open(os.path.join(D5, name), encoding='utf-8'))
        assert d['window'] == [START, '2027-02-28'] and d['nights'] == 90, name
        for h in d['hotels']:
            code = h['code']
            tgt = by_code[code]
            assert h['rates_official'] is None, code
            assert h['rates_official_status'] == 'not_remeasured', code
            assert h['points']['$d'] == START and len(h['points']['$v']) == 90, code
            old = tgt['points']['$v']
            assert len(old) == 365, code
            cash_before = copy.deepcopy(tgt.get('rates_official'))
            new90 = h['points']['$v']
            assert all(v is None or (isinstance(v, int) and v > 0) for v in new90), code

            def rng(vals):
                xs = [v for v in vals if v is not None]
                return '%s~%sP' % ('{:,}'.format(min(xs)), '{:,}'.format(max(xs))) if xs else '값 없음'
            tgt['points']['$v'] = new90 + old[90:]
            assert tgt['points']['$d'] == START
            assert tgt['get' if False else 'points']['$v'][90:] == old[90:]
            # 현금가·호럭·프로모션·링크는 손대지 않는다
            assert tgt.get('rates_official') == cash_before, code
            priced = sum(1 for v in new90 if v is not None)
            changed = sum(1 for a, b in zip(old[:90], new90) if a != b)
            line = ('포인트 2026-12-01~2027-02-28 90일은 2026-11-27에 다시 쟀습니다'
                    '(5번(@jin_5) · 값 %d/90일 · 범위 %s · 기존 11-22/23 값과 다른 날 %d일). %s'
                    ' 2027-03-01 이후 포인트와 현금가는 2026-11-22/23 실측값 그대로입니다.'
                    % (priced, rng(new90), changed, REFRESH_FACTS[code]))
            tgt['note'] = (clean(tgt.get('note')) + ' ' + line).strip() if tgt.get('note') else line
            done.append((code, priced, changed))
            print('%-6s 90일 값 %2d일 · 변동 %2d칸 · %s' % (code, priced, changed, rng(new90)))
    assert len(done) == 20, len(done)
    assert len({c for c, _, _ in done}) == 20

    tab['generated_at'] = '2026-11-27'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n')

    hs = tab['hotels']
    cells = sum(len(h['points']['$v']) for h in hs)
    priced = sum(1 for h in hs for v in h['points']['$v'] if v is not None)
    reg = collections.Counter(h['region'] for h in hs)
    print('hotels', len(hs), 'cells', cells, 'priced', priced)
    print(dict(reg))
    assert len(hs) == 633 and cells == 633 * 365 == 231045
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg[REGION] == 20
    assert reg['한국'] == 9 and reg['일본'] == 23 and reg['미국'] == 209 and reg['유럽'] == 146
    assert reg['동남아'] == 61 and reg['남아시아'] == 61 and reg['캐나다'] == 39
    assert reg['중동'] == 31 and reg['중화권' if False else '중국·중화권'] == 15
    assert reg['오세아니아'] == 14 and reg['아프리카'] == 5
    print("EXPECT_HYATT = {'hotels': %d, 'cells': %d, 'priced': %d}" % (len(hs), cells, priced))


if __name__ == '__main__':
    main()
