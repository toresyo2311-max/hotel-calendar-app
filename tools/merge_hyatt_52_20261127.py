#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 싱가포르·뉴질랜드·스페인 18 + UAE·필리핀·대만 15 + 사우디·튀르키예·모로코 19
= 52곳 병합 (2026-11-27) 413 → 465곳

입력
  · 4번(@jin_4) 싱가포르·뉴질랜드·스페인 18곳 — 4개 배치
      memory/clones/06130525-jin489/pickle/2026-11-26-1741/received/0-hyatt-sgnz-es-batch1.json
      memory/clones/06130525-jin489/pickle/2026-11-26-1741/received/0-hyatt-es-batch2~4.json
      (hyatt.com /explore-hotels/service/avail/days · STANDARD_ROOM · 성인1·1박)
  · 6번(@jin_6) UAE 8 · 필리핀 2 · 대만 5 = 15곳 — 3개 배치
      memory/clones/146dd4d1-jin_6/pickle/2026-11-26-1741/received/0-hyatt-uae-batch2-5.json
      memory/clones/146dd4d1-jin_6/pickle/2026-11-26-1741/received/0-hyatt-uae-ph-batch3-5.json
      memory/clones/146dd4d1-jin_6/pickle/2026-11-26-1741/received/0-hyatt-tw-batch4-5.json
      (hyatt.com 포인트 캘린더 · Standard Room · 1박 · 성인2인·1실)
  · 7번(@no_7) 사우디 9 · 튀르키예 6 · 모로코 4 = 19곳 — 4개 배치
      memory/clones/a03363f4-no71/pickle/2026-11-26-1140/received/0-hyatt_me_batch1~4_*.json
      (hyatt.com /explore-hotels/service/avail/days · roomCategory=ROOM · 성인2·1박)

■ 규칙
- 마스터(1-hyatt-global-master.json)에 52개 spiritCode 전부 등록돼 있고 이름·카테고리·브랜드가
  배치본과 일치하는지 먼저 확인한다. 카드 region 은 브리프대로
  싱가포르·필리핀 → 동남아 / 대만 → 중국·중화권 / 뉴질랜드 → 오세아니아 / 스페인·튀르키예 → 유럽 /
  UAE·사우디 → 중동 / 모로코 → 아프리카.
  (마스터 area 는 튀르키예·모로코를 '중동·아프리카'로 묶지만, ⑤ IHG 탭이 튀르키예를 유럽 · 모로코를
   아프리카로 적고 있어 같은 표기를 따른다.)
- 기존 413곳과 code·영문명(정규화)·국문명 중복 0건, 영문명 토큰 부분집합(같은 호텔 의심) 0건 확인.
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 — ① 탭의 하얏트는 안다즈
  싱가포르(h96 = 기존 hy32) 하나이고, 새 싱가포르 2곳(그랜드 하얏트 싱가포르 · 더 스탠다드
  싱가포르)은 ① 탭 36곳 어느 것과도 다른 호텔이라 alsoIn 0쌍.
- city·name 은 국문, brand 는 공홈 브랜드 라벨, category 는 정수(올인클루시브 A0/A1/A2 는 문자열,
  Miraval 은 마스터 category null 그대로 null).
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
D4 = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-26-1741/received')
D6 = os.path.join(WS, 'memory/clones/146dd4d1-jin_6/pickle/2026-11-26-1741/received')
D7 = os.path.join(WS, 'memory/clones/a03363f4-no71/pickle/2026-11-26-1140/received')
MASTER = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-22-2230/received/'
                          '1-hyatt-global-master.json')
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
assert len(DATES) == 365

FIRST_ID = 414

# ── 52곳 메타 ─────────────────────────────────────────────────────────
# (code, 국문명, 도시, 브랜드, 카테고리, region, 묶음)
PLAN = [
    # ── 싱가포르 2 · 뉴질랜드 1 · 스페인 15 = 18 (4번 · batch1 20:31 / batch2 20:29 / batch3 20:39 / batch4 20:31~20:50 KST)
    ('sinrs', '그랜드 하얏트 싱가포르', '싱가포르', 'Grand Hyatt', 6, '동남아', 'SG'),
    ('sinss', '더 스탠다드 싱가포르', '싱가포르', 'The Standard', 4, '동남아', 'SG'),
    ('aklph', '파크 하얏트 오클랜드', '오클랜드', 'Park Hyatt', 6, '오세아니아', 'NZ'),
    ('bp021', '바이아 프린시페 이스케이프 테네리페', '테네리페', 'Bahia Principe Hotels & Resorts', 'A1', '유럽', 'ES'),
    ('pmidh', '사레나 데 무로 리조트 마요르카', '마요르카', 'Destination by Hyatt', 6, '유럽', 'ES'),
    ('algtr', '알루아 골프 트리니다드', '알메리아', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('bcnub', '그랜드 하얏트 바르셀로나', '바르셀로나', 'Grand Hyatt', 5, '유럽', 'ES'),
    ('bcnrb', '하얏트 리젠시 바르셀로나 타워', '바르셀로나', 'Hyatt Regency', 4, '유럽', 'ES'),
    ('alcma', '알루아 칼라스 데 마요르카 리조트', '마요르카', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('rmugh', '그랜드 하얏트 라 망가 클럽 골프 & 스파', '카르타헤나', 'Grand Hyatt', 4, '유럽', 'ES'),
    ('ascoa', '알루아솔 코스타 아데헤', '테네리페', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('bp020', '바이아 프린시페 익스플로어 코스타 아데헤', '테네리페', 'Bahia Principe Hotels & Resorts', 'A1', '유럽', 'ES'),
    ('secbr', '시크릿츠 바이아 레알 리조트 & 스파', '푸에르테벤투라', 'Secrets', 'A2', '유럽', 'ES'),
    ('ibzdh', '7파인스 리조트 이비자', '이비자', 'Destination by Hyatt', 7, '유럽', 'ES'),
    ('ibzsi', '더 스탠다드 이비자', '이비자', 'The Standard', 7, '유럽', 'ES'),
    ('asibz', '알루아솔 이비자', '이비자', 'Alua Hotels & Resorts', 'A1', '유럽', 'ES'),
    ('alsfu', '알루아 스위트 푸에르테벤투라', '푸에르테벤투라', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    ('alvfu', '알루아빌리지 푸에르테벤투라', '푸에르테벤투라', 'Alua Hotels & Resorts', 'A0', '유럽', 'ES'),
    # ── UAE 8 · 필리핀 2 · 대만 5 = 15 (6번 · batch2 20:30 / batch3 21:40 / batch4 21:02 KST)
    ('dxbcl', '하얏트 센트릭 주메이라 두바이', '두바이', 'Hyatt Centric', 4, '중동', 'UAE'),
    ('dxbzd', '하얏트 플레이스 두바이 알 리가', '두바이', 'Hyatt Place', 1, '중동', 'UAE'),
    ('dxbzb', '하얏트 플레이스 두바이 바니야스 스퀘어', '두바이', 'Hyatt Place', 1, '중동', 'UAE'),
    ('dxbza', '하얏트 플레이스 두바이 주메이라', '두바이', 'Hyatt Place', 2, '중동', 'UAE'),
    ('dxbzm', '하얏트 플레이스 두바이 와슬 디스트릭트', '두바이', 'Hyatt Place', 1, '중동', 'UAE'),
    ('dxbrd', '하얏트 리젠시 두바이', '두바이', 'Hyatt Regency', 2, '중동', 'UAE'),
    ('dxbhc', '하얏트 리젠시 두바이 크릭 하이츠', '두바이', 'Hyatt Regency', 2, '중동', 'UAE'),
    ('dxbph', '파크 하얏트 두바이', '두바이', 'Park Hyatt', 6, '중동', 'UAE'),
    ('mangh', '그랜드 하얏트 마닐라', '마닐라', 'Grand Hyatt', 3, '동남아', 'PH'),
    ('mnlhy', '하얏트 리젠시 마닐라 시티 오브 드림스', '마닐라', 'Hyatt Regency', 3, '동남아', 'PH'),
    ('hsujd', '에피소드 신주', '신주', 'JdV by Hyatt', 2, '중국·중화권', 'TW'),
    ('tpezn', '하얏트 플레이스 신베이 신좡', '신베이', 'Hyatt Place', 1, '중국·중화권', 'TW'),
    ('tpejd', '에피소드 다안 타이베이', '타이베이', 'JdV by Hyatt', 3, '중국·중화권', 'TW'),
    ('tsact', '하얏트 센트릭 이스트 타이베이', '타이베이', 'Hyatt Centric', 3, '중국·중화권', 'TW'),
    ('tpera', '하얏트 리젠시 타오위안 국제공항', '타오위안', 'Hyatt Regency', 2, '중국·중화권', 'TW'),
    # ── 사우디 9 · 튀르키예 6 · 모로코 4 = 19 (7번 · batch1 20:14~20:30 / batch2 20:31~20:42 / batch3 20:45~21:35 / batch4 21:00~21:15 KST)
    ('dmmgh', '그랜드 하얏트 알 코바르 호텔 & 레지던스', '알 코바르', 'Grand Hyatt', 3, '중동', 'SA'),
    ('ulhza', '하얏트 플레이스 알울라', '알울라', 'Hyatt Place', 3, '중동', 'SA'),
    ('jedxr', '하얏트 하우스 제다 사리 스트리트', '제다', 'Hyatt House', 2, '중동', 'SA'),
    ('jedph', '파크 하얏트 제다 – 마리나, 클럽 앤 스파', '제다', 'Park Hyatt', 6, '중동', 'SA'),
    ('jedhr', '자발 오마르 하얏트 리젠시 메카', '메카', 'Hyatt Regency', 5, '중동', 'SA'),
    ('ruhzs', '하얏트 플레이스 리야드 알 술라이마니아', '리야드', 'Hyatt Place', 3, '중동', 'SA'),
    ('ruhhr', '하얏트 리젠시 리야드 올라야', '리야드', 'Hyatt Regency', 5, '중동', 'SA'),
    ('rsigh', '그랜드 하얏트 더 레드 씨', '슈라섬', 'Grand Hyatt', 6, '중동', 'SA'),
    ('rsiob', '미라발 더 레드 씨', '우믈루지', 'Miraval', None, '중동', 'SA'),
    ('adbri', '그랜드 하얏트 이즈미르 이스티네파크', '이즈미르', 'Grand Hyatt', 2, '유럽', 'TR'),
    ('istxg', '하얏트 하우스 게브제', '게브제', 'Hyatt House', 1, '유럽', 'TR'),
    ('istan', '그랜드 하얏트 이스탄불', '이스탄불', 'Grand Hyatt', 4, '유럽', 'TR'),
    ('istct', '하얏트 센트릭 레벤트 이스탄불', '이스탄불', 'Hyatt Centric', 3, '유럽', 'TR'),
    ('isthr', '하얏트 리젠시 이스탄불 아타쾨이', '이스탄불', 'Hyatt Regency', 3, '유럽', 'TR'),
    ('istph', '파크 하얏트 이스탄불 – 마치카 팔라스', '이스탄불', 'Park Hyatt', 6, '유럽', 'TR'),
    ('agazt', '하얏트 플레이스 타가주트 베이', '아가디르', 'Hyatt Place', 2, '아프리카', 'MA'),
    ('casab', '하얏트 리젠시 카사블랑카', '카사블랑카', 'Hyatt Regency', 3, '아프리카', 'MA'),
    ('cmn01', '하얏트 리젠시 마자간', '엘자디다', 'Hyatt Regency', 3, '아프리카', 'MA'),
    ('marph', '파크 하얏트 마라케시', '마라케시', 'Park Hyatt', 7, '아프리카', 'MA'),
]

GROUP_OF = {p[0]: p[6] for p in PLAN}
COUNTRY_KO = {'SG': '싱가포르', 'NZ': '뉴질랜드', 'ES': '스페인', 'UAE': '아랍에미리트(UAE)',
              'PH': '필리핀', 'TW': '대만', 'SA': '사우디아라비아', 'TR': '튀르키예', 'MA': '모로코'}
PROVIDER = {'SG': '4번(@jin_4)', 'NZ': '4번(@jin_4)', 'ES': '4번(@jin_4)',
            'UAE': '6번(@jin_6)', 'PH': '6번(@jin_6)', 'TW': '6번(@jin_6)',
            'SA': '7번(@no_7)', 'TR': '7번(@no_7)', 'MA': '7번(@no_7)'}

# 4번 배치별 조회 시각 · 조회 창 방식
TIME4 = {'sinrs': '20:31', 'sinss': '20:31', 'aklph': '20:31', 'bp021': '20:31', 'pmidh': '20:31',
         'algtr': '20:29', 'bcnub': '20:29', 'bcnrb': '20:29', 'alcma': '20:29', 'rmugh': '20:29',
         'ascoa': '20:39', 'bp020': '20:39', 'secbr': '20:39', 'ibzdh': '20:39',
         'ibzsi': '20:31~20:50', 'asibz': '20:31~20:50', 'alsfu': '20:31~20:50', 'alvfu': '20:31~20:50'}
WIN4 = {'sinrs': '60일 창 6회+5일 창 1회', 'sinss': '60일 창 6회+5일 창 1회', 'aklph': '60일 창 6회+5일 창 1회',
        'bp021': '60일 창 6회+5일 창 1회', 'pmidh': '60일 창 6회+5일 창 1회',
        'algtr': '20일 이하 창 타일링', 'bcnub': '20일 이하 창 타일링', 'bcnrb': '20일 이하 창 타일링',
        'alcma': '20일 이하 창 타일링', 'rmugh': '20일 이하 창 타일링',
        'ascoa': '60일 창 6회+5일 창 1회', 'bp020': '60일 창 6회+5일 창 1회', 'secbr': '60일 창 6회+5일 창 1회',
        'ibzdh': '60일 창 6회+5일 창 1회',
        'ibzsi': '20일 이하 창 타일링', 'asibz': '시즌별 3~20일 샘플 창', 'alsfu': '시즌별 3~20일 샘플 창',
        'alvfu': '시즌별 3~20일 샘플 창'}

CASH4 = ('현금 요금은 365일 전부 —입니다 — 공홈 세후 KRW 현금은 미수집입니다'
         '(rooms/roomrates 엔드포인트가 404·429로 차단).')
CASH6 = ('현금 요금은 365일 전부 —입니다 — hyatt.com 은 월 단위 현금 캘린더를 제공하지 않아'
         '(1박 단위 shop/rooms 화면에서만 표시, 세금·봉사료 별도) 미수집으로 두었습니다.')

# 4번 18곳 — 배치본에 호텔별 note 가 없어 검증 기록(meta.verification·declared_no_data_ranges)으로 적는다.
WHY4 = {
    'sinrs': '365일 전부 값이 있습니다(결번 0일).',
    'sinss': ('값 없는 5일은 모두 응답에 날짜 키가 없는 날(no_key_in_response)로, 매진·1박 포인트 '
              '어워드 미개방이 섞여 있어 보간 없이 —로 두었습니다 — 결번 2026-12-05 · 12-17 · '
              '12-19~20 · 2027-11-27.'),
    'aklph': ('값 없는 5일은 응답에 날짜 키가 없는 날(no_key_in_response)입니다 — 결번 2026-12-30~31 · '
              '2027-01-31 · 02-03~04.'),
    'bp021': '365일 전부 값이 있습니다(결번 0일).',
    'pmidh': ('시즌 운영 리조트라 2026-12-01~2027-04-23(144일)은 시즌 개시 전, '
              '2027-10-25~11-30(37일)은 시즌 종료로 7일·6일 창 재조회에서도 응답이 없었고, 한여름 '
              '2027-06-16~09-22(99일)는 스탠다드룸 어워드 없이 스위트만 표출된 날(empty_day_object)입니다. '
              '2027-02-10~15 창은 days:{} + responseInfo=soldOutHotel로 겨울 휴장이 확인됐습니다. 실제 값이 '
              '있는 구간은 2027-04-24~06-15와 2027-09-23~10-24입니다.'),
    'algtr': ('전 기간 어워드가 표출되지 않았습니다 — 2026-11-28(익일)·12-01~02·12-10~12(los=2 포함)·'
              '2027-01-15·03-15·04-15·06-10(los=7 포함)·07-15 단일·2일 창 재조회가 모두 soldOutHotel이었고 '
              'roomCategory 미지정·성인2 조회도 같았습니다. 공홈 포인트 캘린더도 「이용 가능한 객실 없음」·'
              '「--」입니다(같은 Alua 브랜드의 알루아솔 이비자도 같은 상태이나, 알루아솔 코스타 아데헤는 '
              '234일 표출돼 브랜드 전체 문제는 아닙니다).'),
    'bcnub': ('2027-03-29까지 값이 있고, 2027-03-30~11-30(246일)은 단일·2일 창 '
              '재조회에서도 days:{} + responseInfo=soldOutHotel라 요금·어워드 재고가 적재되지 않았습니다'
              '(미오픈으로 판단, 보간 없이 —). 그 밖의 짧은 결번(2026-12-02~03 · 12-05 · 2027-01-11~13 · '
              '01-26~28 · 02-01~04 · 02-28~03-03 · 03-15~17)은 30일 창이 통째로 실패해 5일·2일 창으로 '
              '쪼개 확인한 결과입니다.'),
    'bcnrb': ('값 없는 61칸은 대부분 1~5일짜리 짧은 결번입니다(2026-12-01~02 · 12-04~05 · 12-31 · '
              '2027-01-18~20 · 02-01~04 · 02-28~03-04 · 03-14~17 등 24개 구간) — 30일 이상 창이 '
              'soldOutHotel로 실패하는 구간이 있어 20일 이하 창으로 타일링하고 빈 구간은 5일·2일 창으로 '
              '재확인했습니다.'),
    'alcma': ('전 기간 어워드가 표출되지 않았습니다 — 2026-12-15·2027-02-15·05-15·06-10·07-15·11-15 '
              '단일·2일 창 재조회가 모두 soldOutHotel이고 공홈 포인트 캘린더도 값을 표시하지 않습니다.'),
    'rmugh': ('값 없는 27칸 가운데 23칸은 날짜 키는 있으나 스탠다드룸이 없는 날(empty_day_object · 상위 '
              '객실만 표출), 4칸은 날짜 키가 없는 날(no_key_in_response)입니다 — 결번 2026-12-04~07 · '
              '2027-01-21~23 · 01-25~27 · 03-12~13 · 05-19~22 등 짧은 구간입니다.'),
    'ascoa': ('포인트 234일입니다 — 2026-12-01~2027-04-10(131일)이 비어 있습니다(시즌 개시 전, 12월 창 '
              '재조회에서도 날짜 키 없음). 이 기간에는 스탠다드룸 대신 CLUB(18,000/21,000/26,000P)만 '
              '열려 있는 날이 많습니다.'),
    'bp020': '365일 전부 값이 있습니다(결번 0일).',
    'secbr': ('전 기간 어워드가 표출되지 않았습니다 — 2027-08-10~14 5일 창을 포함한 전 구간 재조회가 '
              'responseInfo=soldOutHotel로 같았고(창 크기 문제 아님), 공홈 포인트 캘린더는 전 월 '
              '「이용 가능한 객실 없음」이며 어워드 카테고리를 C로 표기합니다.'),
    'ibzdh': ('포인트 164일 — 시즌제 리조트라 2026-12-01~2027-04-29(150일)는 시즌 개시 전, '
              '2027-10-17~11-30(45일)은 시즌 종료로 응답이 없습니다(마지막 표출일 2027-10-16). 5~6월의 '
              '2일짜리 결번(05-27~28 · 06-09~10 · 06-23~24)은 좁은 창 재조회에서도 같았습니다.'),
    'ibzsi': ('포인트 309일 — 2027-10-14가 마지막 표출일이고 2027-10-15~11-30(47일)은 5·3·2일 창과 성인2 '
              '조회에서도 soldOutHotel이라 시즌 종료(동절기 휴장)로 보입니다(같은 시각 하얏트 리젠시 '
              '바르셀로나 타워는 2027-12-05·06 정상 응답이라 예약 호라이즌 한계가 아닙니다). 2026-12-23 · '
              '12-26 · 12-30 · 2027-01-01 등 단일 결번은 연말 성수기 미개방입니다.'),
    'asibz': ('전 기간 어워드가 표출되지 않았습니다 — 3~20일 창 7개(겨울·봄·초여름·성수기·가을)가 모두 '
              '{days:{}, responseInfo:soldOutHotel}이고 roomCategory 미지정·성인2 조회도 같습니다. 공홈 '
              '포인트 캘린더는 월 그리드가 뜨지 않고 「이용 가능한 객실 없음」 비활성 버튼이며 어워드 '
              '카테고리를 B로 표기합니다.'),
    'alsfu': ('전 기간 어워드가 표출되지 않았습니다 — 겨울·봄·성수기(los=7 포함)·가을·연말 7개 창이 모두 '
              'soldOutHotel이고 공홈 포인트 캘린더도 값을 표시하지 않습니다.'),
    'alvfu': ('전 기간 어워드가 표출되지 않았습니다 — 겨울·봄·성수기·가을·연말 6개 창이 모두 '
              'soldOutHotel이고 공홈 포인트 캘린더도 값을 표시하지 않습니다.'),
}

# 7번 보고분에서 온 특이사항 보강
EXTRA = {
    'rsiob': '카드에는 Cat 을 적지 않았습니다(마스터·공홈 모두 카테고리 등급 null).',
    'marph': '공홈 1박 화면에 본관 풀(수영장) 임시 휴장 안내 배너가 있었습니다.',
    'ulhza': '카드에는 실측값 그대로 0칸으로 싣고, 개관 후 재실측이 필요합니다.',
    'cmn01': '카드에는 실측값 그대로 0칸으로 싣고, 개관 후 재실측이 필요합니다.',
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
    hotels, src = {}, {}
    for name in ('0-hyatt-sgnz-es-batch1.json', '0-hyatt-es-batch2.json',
                 '0-hyatt-es-batch3.json', '0-hyatt-es-batch4.json'):
        d = json.load(open(os.path.join(D4, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30', d['meta']['window']
        for code, h in d['hotels'].items():
            assert code not in hotels, code
            hotels[code] = h
            src[code] = ('4', name)
    for name in ('0-hyatt-uae-batch2-5.json', '0-hyatt-uae-ph-batch3-5.json',
                 '0-hyatt-tw-batch4-5.json'):
        d = json.load(open(os.path.join(D6, name), encoding='utf-8'))
        assert d['window'] == {'start': '2026-12-01', 'end': '2027-11-30', 'days': 365}, d['window']
        for h in d['hotels']:
            assert h['code'] not in hotels, h['code']
            hotels[h['code']] = h
            src[h['code']] = ('6', name)
    for name in ('0-hyatt_me_batch1_5.json', '0-hyatt_me_batch2_4.json',
                 '0-hyatt_me_batch3_5.json', '0-hyatt_me_batch4_5.json'):
        d = json.load(open(os.path.join(D7, name), encoding='utf-8'))
        assert d['meta']['window'] == '2026-12-01~2027-11-30', d['meta']['window']
        for code, h in d['hotels'].items():
            assert code not in hotels, code
            hotels[code] = h
            src[code] = ('7', name)
    assert len(hotels) == 52, len(hotels)
    return hotels, src


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


def dist_text(pts, info=None):
    cnt = collections.Counter(v for v in pts if v is not None)
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
        tag = val2lv.get(v, '')
        out.append('%sP%s %d일' % ('{:,}'.format(v), (' ' + tag) if tag else '', n))
    return ' · '.join(out)


def note4(code, kr, city, brand, cat, info):
    pts = pts_of(info)
    priced = sum(1 for v in pts if v is not None)
    cat_txt = 'A0' if cat == 'A0' else str(cat)
    dist = dist_text(pts, info)
    head = ('스탠다드 아워드 365일 실측(2026-11-26 %s KST · hyatt.com · %s %s) — 하얏트 공홈 어워드 응답'
            '(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM · 성인1·1박 · %s)으로 '
            '365칸을 받았고, 공홈 표시 어워드 카테고리는 %s입니다. 포인트 %d일. %s%s %s %s'
            % (TIME4[code], COUNTRY_KO[GROUP_OF[code]], city, WIN4[code], cat_txt, priced,
               WHY4[code], (' 분포: %s.' % dist) if dist else '',
               CASH4, '4번(@jin_4)이 실측해 보낸 본입니다.'))
    return ' '.join(head.split())


NOTE_FIX = {
    # 달력이 note 의 「개관 전」을 호텔 전체 '미오픈' 신호로 읽어, 값이 있는 날까지 미오픈으로 칠한다.
    # 값이 있는 호텔은 그 문구를 빼고, 빈 구간을 날짜 범위 + 「판매 없음」으로 적어 그 구간만 표시되게 한다.
    'dxbph': (
        ('즉 이 호텔의 null 121칸은 1박 미개방이 아니라 **개관 전(휴관)**이다.',
         '즉 이 호텔의 null 121칸은 1박 미개방이 아니라 **휴관**입니다(2026년 5월부터 장기 리노베이션, '
         '공홈 예상 재개관 2027년 1분기). 2026-12-01~2027-03-31(121일)은 휴관으로 판매 없음입니다.'),
    ),
    'adbri': (
        ('개관 전 호텔이 아니며', '신규 개관 호텔이 아니며'),
    ),
    'rsiob': (
        ('개관 전이 아니라 운영 중이다', '미개관이 아니라 운영 중이다'),
    ),
    'tsact': (
        ('**2026-11-26 현재 개관 전(예약 접수 시작) 호텔**이다.',
         '**2026-11-26 현재 예약을 받기 시작한 신규 호텔**이다(2027-02-15부터 투숙).'),
        ('null 156칸 = 2026-12-01~2027-02-28(개관 전, 90일)',
         'null 156칸 = 2026-12-01~2027-02-28(투숙 개시 전, 90일)은 판매 없음이고'),
    ),
}


def note_src(code, city, brand, cat, info, cash, provider):
    src = clean(info.get('note') or '')
    for a, bb in NOTE_FIX.get(code, ()):
        assert a in src, (code, a[:40])
        src = src.replace(a, bb)
    bits = [src, EXTRA.get(code, '')]
    tail = '%s %s' % (cash, provider + '이 실측해 보낸 본입니다.')
    out = ' '.join(x for x in bits + [tail] if x)
    return ' '.join(out.split())


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    before = copy.deepcopy(tab['hotels'])
    assert len(before) == 413, len(before)
    assert before[-1]['id'] == 'hy413', before[-1]['id']

    hotels, src = load_bundles()
    assert set(hotels) == {p[0] for p in PLAN}, sorted(set(hotels) ^ {p[0] for p in PLAN})

    # ── 공홈 마스터 대조 ────────────────────────────────────────────
    master = json.load(open(MASTER, encoding='utf-8'))
    byc = {m['code']: m for m in master['hotels']}
    AREA_OK = {'동남아': '동남아', '오세아니아': '오세아니아', '유럽': ('유럽', '중동·아프리카'),
               '중국·중화권': '중국·중화권', '중동': '중동·아프리카', '아프리카': '중동·아프리카'}
    for code, kr, city, brand, cat, region, grp in PLAN:
        m = byc[code]
        h = hotels[code]
        assert norm(m['name']) == norm(h['name']), (code, m['name'], h['name'])
        area_ok = AREA_OK[region]
        assert m['area'] in (area_ok if isinstance(area_ok, tuple) else (area_ok,)), \
            (code, m['area'], region)
        assert str(m['category']) == str(h['category']), (code, m['category'], h['category'])
        assert str(cat) == str(h['category']), (code, cat, h['category'])
        assert clean(h['brand']) == clean(brand) == clean(m['brand']), (code, h['brand'], brand, m['brand'])
        if code == 'rsiob':
            assert m['woh_participating'] is False and cat is None
        else:
            assert m['woh_participating'] is True, code

    # ── 기존 413곳 중복 확인 ────────────────────────────────────────
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
        assert not exist_names.get(norm(h['name'])), ('english dup', code, h['name'], exist_names.get(norm(h['name'])))
        assert not exist_kr.get(norm_ko(kr)), ('korean dup', code, kr, exist_kr.get(norm_ko(kr)))
        assert norm(h['name']) not in seen_en, ('batch english dup', code, seen_en.get(norm(h['name'])))
        assert norm_ko(kr) not in seen_kr, ('batch korean dup', code, seen_kr.get(norm_ko(kr)))
        seen_en[norm(h['name'])] = code
        seen_kr[norm_ko(kr)] = code
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
    for code, kr, city, brand, cat, region, grp in PLAN:
        h = hotels[code]
        if norm(h['name']) in by_eng:
            overlaps.append(('english', code, by_eng[norm(h['name'])]))
        if norm_ko(kr) in by_kr:
            overlaps.append(('korean', code, by_kr[norm_ko(kr)]))
        toks = set(norm(h['name']).split())
        for rid, r in [(r['id'], r) for r in rows]:
            et = set(norm(r.get('english') or '').split())
            if et and toks <= et:
                overlaps.append(('same hotel?', code, rid, r.get('english')))
    assert not overlaps, overlaps
    print('① 호텔럭스 161곳 대조 — 겹침 0곳')
    print('① 탭 도시:', {k: len(v) for k, v in by_city.items()})

    added = []
    for i, (code, kr, city, brand, cat, region, grp) in enumerate(PLAN):
        hid = 'hy%d' % (FIRST_ID + i)
        info = hotels[code]
        pts = pts_of(info)
        assert len(pts) == 365
        priced = sum(1 for v in pts if v is not None)
        assert all(v is None or (isinstance(v, int) and v > 0) for v in pts)
        if 'days_priced' in info:
            assert priced == info['days_priced'], (code, priced, info['days_priced'])

        if src[code][0] == '4':
            note = note4(code, kr, city, brand, cat, info)
        elif src[code][0] == '6':
            note = note_src(code, city, brand, cat, info, CASH6, '6번(@jin_6)')
        else:
            note = note_src(code, city, brand, cat, info, CASH6, '7번(@no_7)')

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
            'note': note,
        }
        added.append(entry)
        print('%s %-6s %-6s %-8s %-30s Cat %-3s %3d일  %s'
              % (hid, code, region, city, kr, '-' if cat is None else cat, priced, src[code][0]))

    tab['hotels'] = before + added
    tab['generated_at'] = '2026-11-27'
    raw = json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(raw)

    hs = tab['hotels']
    cells = sum(len(h['points']['$v']) for h in hs)
    priced = sum(1 for h in hs for v in h['points']['$v'] if v is not None)
    reg = collections.Counter(h['region'] for h in hs)
    print('hotels', len(hs), 'cells', cells, 'priced', priced, dict(reg))
    assert len(hs) == 465 and cells == 465 * 365
    assert len({h['id'] for h in hs}) == len(hs)
    assert len({h['code'] for h in hs}) == len(hs)
    assert reg['유럽'] == 108 and reg['동남아'] == 61 and reg['오세아니아'] == 14
    assert reg['중국·중화권'] == 15 and reg['중동'] == 22 and reg['아프리카'] == 4
    assert priced == 147415, priced
    assert all(len(h['points']['$v']) == 365 for h in hs)


if __name__ == '__main__':
    main()
