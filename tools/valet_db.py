#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🅿️ 발렛 탭 데이터 생성기 — `data/app/valet.json`.

국내 특급호텔의 호텔 발렛(발레파킹) 현장 조건과, 카드사가 공식 안내장에서
무료 발렛 대상 호텔로 밝힌 목록을 한 파일로 구조화한다.

원칙(2026-11-20 정밀 검수):
  · 카드별 대상 호텔은 **카드사·브랜드사 공식 안내장에 적힌 이름 그대로**만 넣는다.
    공식 목록을 확인하지 못한 카드는 호텔을 붙이지 않고 조건만 남긴다(가짜 매칭 금지).
  · 영수증 조건은 호텔 × 카드 단위로 나눈다.
      receipt_type = none      → 최소 결제 금액 조건 없음(영수증은 요청될 수 있음)
                     same_day  → 당일 호텔 이용 영수증 제시(금액 조건 없음)
                     amount    → 최소 결제 금액 이상 당일 영수증
  · 호텔 목록이 일부만 확인된 카드는 coverage_complete=False 로 두고 화면에서
    "확인 필요"로 보여 준다.

사용법(저장소 루트에서):
    python3 tools/valet_db.py build     # data/app/valet.json 생성
    python3 tools/valet_db.py check     # 이름·참조 정합성만 검사
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'app', 'valet.json')

BASIS_DATE = '2026-11-20'
BASIS = ('카드사·브랜드사 공식 발레파킹 안내장(2026-01-01~12-31 기준)의 대상 호텔·조건을 '
         '호텔 × 카드 단위로 옮긴 값입니다. 더 플라자 호텔 서울은 2026-09-30 영업을 종료해 '
         '목록에서 뺐습니다. 카드사·호텔 사정으로 바뀔 수 있어 방문 전 확인이 필요합니다.')

# ────────────────────────────────────────────────────────────────
# 호텔 — (id, 이름, 지역, 구·시, 주소, 호텔 발렛 요금 참고값, 앱 탭 참조)
#   주소는 카드사 공식 안내에 적힌 값만 넣었다. 요금은 호텔 공지 확인값(2026-11).
#   앱 탭 참조 = 이 앱 ①~④ 에 같은 호텔이 있으면 (탭, id).
# ────────────────────────────────────────────────────────────────
HOTELS = [
    # ── 서울 ──────────────────────────────────────────────
    ('s-grand-walkerhill', '그랜드 워커힐 서울', '서울', '광진구', '워커힐로 177', '28,000원', None),
    ('s-vista-walkerhill', '비스타 워커힐 서울', '서울', '광진구', '워커힐로 177', '28,000원', None),
    ('s-grand-hyatt', '그랜드 하얏트 서울', '서울', '용산구', '소월로 322', '30,000원', ('lux', 'h28')),
    ('s-park-hyatt', '파크 하얏트 서울', '서울', '강남구', '테헤란로 606', '22,000원(투숙) / 10,000원(3시간)', ('lux', 'h38')),
    ('s-parnas', '그랜드 인터컨티넨탈 서울 파르나스', '서울', '강남구', '테헤란로 521', None, ('lux', 'h27')),
    ('s-andaz', '안다즈 서울 강남', '서울', '강남구', '논현로 854', '40,000원', ('lux', 'h33')),
    ('s-novotel-gangnam', '노보텔 앰배서더 서울 강남', '서울', '강남구', '봉은사로 130', '30,000원', None),
    ('s-ac-gangnam', 'AC 호텔 바이 메리어트 서울 강남', '서울', '강남구', '테헤란로 25길 10', '투숙객 무료', None),
    ('s-oakwood', '오크우드 프리미어 코엑스 센터', '서울', '강남구', '테헤란로87길 46', None, None),
    ('s-glad-gangnam', '글래드 강남 코엑스 센터', '서울', '강남구', '테헤란로 610', None, None),
    ('s-glad-yeouido', '글래드 여의도', '서울', '영등포구', None, None, None),
    ('s-conrad', '콘래드 서울', '서울', '영등포구', '국제금융로 10', '29,000원', ('lux', 'h37')),
    ('s-fairmont', '페어몬트 앰배서더 서울', '서울', '영등포구', '여의대로 108', None, ('lux', 'h39')),
    ('s-mea', '메리어트 이그제큐티브 아파트먼트 서울', '서울', '영등포구', '여의대로 8', '30,000원(3시간)', ('marriott', 'k09')),
    ('s-cy-timesquare', '코트야드 바이 메리어트 서울 타임스퀘어', '서울', '영등포구', '영중로 15', '27,000원', None),
    ('s-cy-botanic', '코트야드 바이 메리어트 서울 보타닉 파크', '서울', '강서구', None, None, None),
    ('s-mayfield', '메이필드 호텔 서울', '서울', '강서구', '방화대로 94', '20,000원', None),
    ('s-swissgrand', '스위스 그랜드 호텔', '서울', '서대문구', '연희로 353', '20,000원', None),
    ('s-seoulgarden', '서울 가든 호텔', '서울', '마포구', '마포대로 58', '20,000원', None),
    ('s-naru', '호텔 나루 서울 엠갤러리', '서울', '마포구', '마포대로 8', '30,000원', None),
    ('s-dragoncity', '서울 드래곤 시티', '서울', '용산구', '청파로20길 95', '27,000원', None),
    ('s-gm-yongsan', '그랜드 머큐어 앰배서더 서울 용산', '서울', '용산구', '청파로20길 95', '27,000원', None),
    ('s-novotel-yongsan', '노보텔 앰배서더 서울 용산', '서울', '용산구', '청파로20길 95', '27,000원', None),
    ('s-novotel-suite', '노보텔 스위트 앰배서더 서울 용산', '서울', '용산구', '청파로20길 95', '27,000원', None),
    ('s-ibis-yongsan', '이비스 스타일 앰배서더 서울 용산', '서울', '용산구', '청파로20길 95', '27,000원', None),
    ('s-mondrian', '몬드리안 서울 이태원', '서울', '용산구', '장문로 23', '28,000원', None),
    ('s-shilla', '서울신라호텔', '서울', '중구', '동호로 249', None, ('lux', 'h29')),
    ('s-koreana', '코리아나 호텔', '서울', '중구', '세종대로 135', None, None),
    ('s-lotte-seoul', '롯데호텔 서울', '서울', '중구', '을지로 30', None, None),
    ('s-banyan', '반얀트리 클럽 앤 스파 서울', '서울', '중구', '장충단로 60', '3시간 무료(제휴카드)', None),
    ('s-lescape', '레스케이프 호텔', '서울', '중구', '퇴계로 67', '25,000원(3시간)', ('lux', 'h30')),
    ('s-ambassador-pullman', '앰배서더 서울 풀만', '서울', '중구', '동호로 287', '30,000원', None),
    ('s-pullman-eastpole', '풀만 앰배서더 서울 이스트폴', '서울', '광진구', None, None, None),
    ('s-novotel-dongdaemun', '노보텔 앰배서더 서울 동대문', '서울', '중구', '을지로 238', '20,000원 → 2026-12-01 25,000원', None),
    ('s-jw-dongdaemun', 'JW 메리어트 동대문 스퀘어 서울', '서울', '종로구', '청계천로 279', '27,000원', ('lux', 'h25')),
    ('s-four-seasons', '포시즌스 호텔 서울', '서울', '종로구', '새문안로 97', '30,000원', ('lux', 'h40')),
    ('s-jw-seoul', 'JW 메리어트 호텔 서울', '서울', '서초구', '신반포로 176', '35,000원(3시간)', ('lux', 'h26')),
    ('s-lemeridien', '르메르디앙 서울 명동', '서울', '중구', None, '25,000원(투숙)', ('marriott', 'k10')),
    ('s-moxy', '목시 서울 명동', '서울', '중구', None, '25,000원(투숙)', None),
    ('s-lotte-world', '롯데호텔 월드', '서울', '송파구', '올림픽로 240', None, None),
    ('s-signiel-seoul', '시그니엘 서울', '서울', '송파구', '올림픽로 300', None, ('lux', 'h32')),
    ('s-westin-chosun', '웨스틴 조선 서울', '서울', '중구', None, None, ('lux', 'h35')),
    ('s-josun-palace', '조선 팰리스 서울 강남', '서울', '강남구', None, None, ('lux', 'h36')),
    ('s-hilton-garden', '힐튼 가든 인 서울 강남', '서울', '강남구', None, None, None),
    ('s-millennium-hilton', '밀레니엄 힐튼 서울', '서울', '중구', None, None, None),
    ('s-imperial', '임피리얼 팰리스 서울', '서울', '강남구', None, '30,000원', None),
    ('s-acem', '아셈타워', '서울', '강남구', None, None, None),
    ('s-riviera', '호텔 리베라 청담', '서울', '강남구', None, None, None),
    # ── 부산 ──────────────────────────────────────────────
    ('b-paradise', '파라다이스 호텔 부산', '부산', '해운대구', '해운대해변로 296', '25,000원', ('lux', 'h01')),
    ('b-park-hyatt', '파크 하얏트 부산', '부산', '해운대구', '마린시티1로 51', '32,000원', ('lux', 'h02')),
    ('b-westin-chosun', '웨스틴 조선 부산', '부산', '해운대구', '동백로 67', '30,000원(1박)', ('marriott', 'k06')),
    ('b-grand-chosun', '그랜드 조선 부산', '부산', '해운대구', None, None, None),
    ('b-lotte', '롯데호텔 부산', '부산', '부산진구', '가야대로 772', None, None),
    ('b-novotel', '노보텔 앰배서더 부산 해운대', '부산', '해운대구', None, None, None),
    ('b-signiel', '시그니엘 부산', '부산', '해운대구', None, None, ('lux', 'h03')),
    ('b-nongshim', '호텔 농심', '부산', '동래구', None, None, None),
    # ── 제주 ──────────────────────────────────────────────
    ('j-lotte', '롯데호텔 제주', '제주', '서귀포시', '중문관광로72번길 35', None, None),
    ('j-jw', 'JW 메리어트 제주 리조트 & 스파', '제주', '서귀포시', None, '25,000원(입차 1회)', ('marriott', 'k03')),
    ('j-grand-chosun', '그랜드 조선 제주', '제주', '서귀포시', None, None, None),
    # ── 인천 ──────────────────────────────────────────────
    ('i-grand-hyatt', '그랜드 하얏트 인천', '인천', '중구', '영종해안남로 321번길 208', '35,000원(1박)', None),
    ('i-paradise-city', '파라다이스시티', '인천', '중구', None, None, None),
    ('i-inspire', '인스파이어 엔터테인먼트 리조트', '인천', '중구', None, '30,000원', None),
    # ── 경기 ──────────────────────────────────────────────
    ('g-sonocam', '소노캄 고양', '경기', '고양시', None, None, None),
    # ── 강원 ──────────────────────────────────────────────
    ('w-saintjohns', '세인트존스 호텔', '강원', '강릉시', None, '25,000~35,000원', None),
    # ── 경남 ──────────────────────────────────────────────
    ('n-gm-changwon', '그랜드 머큐어 앰배서더 창원', '경남', '창원시', '원이대로 332', None, None),
    # ── 경북 ──────────────────────────────────────────────
    ('p-hilton-gyeongju', '힐튼 경주', '경북', '경주시', '보문로 484-7', '20,000원', None),
    # ── 대구 ──────────────────────────────────────────────
    ('d-marriott', '대구 메리어트 호텔', '대구', '동구', '동부로26길 6', '27,000원', ('marriott', 'k07')),
    ('d-interburgo', '호텔 인터불고 대구', '대구', '수성구', '팔현길 212', '20,000원', None),
    ('d-grand', '대구 그랜드 호텔', '대구', '수성구', None, None, None),
    # ── 대전 ──────────────────────────────────────────────
    ('dj-onoma', '호텔 오노마 대전', '대전', '유성구', None, '28,000원', None),
    # ── 울산 ──────────────────────────────────────────────
    ('u-lotte', '롯데호텔 울산', '울산', '남구', '삼산로 282', None, None),
    # ── 전남 ──────────────────────────────────────────────
    ('y-sonocam', '소노캄 여수', '전남', '여수시', None, None, None),
    # ── 앱 ①~④ 에만 있는 국내 호텔(카드사 무료 발렛 안내에 이름이 없는 곳) ──
    ('s-westin-parnas', '웨스틴 서울 파르나스', '서울', '서울', None, None, ('lux', 'h34')),
    ('s-ryse', '라이즈 오토그래프 컬렉션 서울', '서울', '마포구', None, None, ('marriott', 'k08')),
    ('s-sofitel', '소피텔 앰배서더 서울', '서울', '송파구', None, None, ('lux', 'h31')),
]

REGION_ORDER = ['서울', '부산', '제주', '인천', '경기', '강원', '경남', '경북', '대구', '대전', '울산', '전남']

# ────────────────────────────────────────────────────────────────
# 공식 안내에 적힌 호텔 이름 → 이 앱의 호텔 id
#   (표기 차이만 흡수한다. 없는 호텔을 있는 것처럼 붙이지 않는다.)
# ────────────────────────────────────────────────────────────────
NAME_ALIAS = {
    # 신한카드 · 삼성카드 · KB · 현대 · 롯데 · 우리 표기
    '메이필드호텔': 's-mayfield', '메이필드 호텔': 's-mayfield', '메이필드': 's-mayfield',
    '스위스그랜드호텔': 's-swissgrand', '스위스 그랜드 호텔': 's-swissgrand',
    '서울가든호텔': 's-seoulgarden', '서울 가든 호텔': 's-seoulgarden', '서울 가든호텔': 's-seoulgarden',
    '베스트 웨스턴 프리미어 서울가든호텔': 's-seoulgarden',
    '베스트웨스턴프리미어 서울가든호텔': 's-seoulgarden',
    '서울 가든호텔&스위트': 's-seoulgarden',
    '호텔나루 서울 엠 갤러리': 's-naru', '호텔 나루 서울 엠갤러리': 's-naru',
    '호텔 나루 서울 엠 갤러리': 's-naru',
    '페어몬트앰배서더서울': 's-fairmont', '페어몬트 앰배서더 서울': 's-fairmont',
    '콘래드서울호텔': 's-conrad', '콘래드 서울': 's-conrad', '콘래드 서울 호텔': 's-conrad',
    '메리어트이그제큐티브아파트먼트서울': 's-mea',
    '메리어트 이그제큐티브 아파트먼트 서울': 's-mea',
    '메리어트 이그제큐티브 아파트먼트': 's-mea',
    '코트야드메리어트서울타임스퀘어': 's-cy-timesquare',
    '코트야드 바이 메리어트 서울 타임스퀘어': 's-cy-timesquare',
    '코트야드 메리어트 서울 타임스퀘어': 's-cy-timesquare',
    '코트야드 메리어트 서울 보타닉 파크 호텔': 's-cy-botanic',
    'JW메리어트동대문스퀘어': 's-jw-dongdaemun',
    'JW 메리어트 동대문 스퀘어 서울': 's-jw-dongdaemun',
    'JW 메리어트 동대문 스퀘어': 's-jw-dongdaemun',
    '포시즌스호텔서울': 's-four-seasons', '포시즌스 호텔 서울': 's-four-seasons',
    '코리아나호텔': 's-koreana', '코리아나 호텔': 's-koreana', '호텔 코리아나': 's-koreana',
    '롯데호텔서울(소공)': 's-lotte-seoul', '롯데호텔 서울': 's-lotte-seoul',
    '반얀트리클럽앤서울스파': 's-banyan', '반얀트리 클럽 앤 스파 서울': 's-banyan',
    '반얀트리 클럽앤스파 서울': 's-banyan', '반얀트리 클럽 & 스파 서울': 's-banyan',
    '반얀트리클럽앤스파': 's-banyan', '반얀트리클럽앤스파서울': 's-banyan',
    '반얀트리 클럽앤스파': 's-banyan',
    '노보텔앰배서더서울동대문': 's-novotel-dongdaemun',
    '노보텔 앰배서더 서울 동대문 호텔&레지던스': 's-novotel-dongdaemun',
    '노보텔 앰배서더 서울 동대문 호텔 & 레지던스': 's-novotel-dongdaemun',
    '노보텔 앰배서더 서울 동대문': 's-novotel-dongdaemun',
    '노보텔 앰배서더 동대문': 's-novotel-dongdaemun',
    '레스케이프호텔': 's-lescape', '레스케이프 호텔': 's-lescape',
    '서울신라호텔': 's-shilla', '서울 신라 호텔': 's-shilla', '서울신라': 's-shilla',
    '앰배서더서울풀만': 's-ambassador-pullman', '앰배서더 서울 풀만 호텔': 's-ambassador-pullman',
    '앰배서더 서울 풀만': 's-ambassador-pullman',
    '그랜드 앰배서더 서울': 's-ambassador-pullman',
    '그랜드 앰배서더 서울 풀만': 's-ambassador-pullman',
    '소피텔 앰배서더 서울': 's-sofitel',
    '소피텔 앰배서더 서울 호텔 앤 서비스드 레지던스': 's-sofitel',
    '소피텔 앰배서더 서울 호텔 & 서비스드 레지던스': 's-sofitel',
    '소피텔 앰배서더 서울 호텔&서비스드 레지던스': 's-sofitel',
    '그랜드 하얏트 서울': 's-grand-hyatt', '그랜드하얏트서울': 's-grand-hyatt',
    '그랜드하얏트 서울': 's-grand-hyatt',
    '몬드리안서울이태원': 's-mondrian', '몬드리안 서울 이태원': 's-mondrian',
    '서울드래곤시티': 's-dragoncity', '서울 드래곤 시티': 's-dragoncity',
    'JW메리어트호텔서울': 's-jw-seoul', 'JW 메리어트 호텔 서울': 's-jw-seoul',
    'JW메리어트 호텔 서울': 's-jw-seoul', 'JW 메리어트 동대문스퀘어 서울': 's-jw-dongdaemun',
    '그랜드인터컨티넨탈서울파르나스': 's-parnas',
    '그랜드 인터컨티넨탈 서울 파르나스': 's-parnas',
    '안다즈서울강남': 's-andaz', '안다즈 서울 강남': 's-andaz', '안다즈 강남': 's-andaz',
    '파크하얏트서울': 's-park-hyatt', '파크 하얏트 서울': 's-park-hyatt',
    '노보텔 앰배서더 서울 강남': 's-novotel-gangnam', '노보텔앰배서더 서울강남': 's-novotel-gangnam',
    '노보텔 앰배서더 강남': 's-novotel-gangnam', '노보텔앰배서더서울강남': 's-novotel-gangnam',
    '노보텔 앰버서더 서울 강남': 's-novotel-gangnam',
    '노보텔 앰배서더 서울 동대문 호텔': 's-novotel-dongdaemun',
    'AC호텔 바이메리어트 서울강남': 's-ac-gangnam', 'AC 호텔 바이 메리어트 서울 강남': 's-ac-gangnam',
    '오크우드프리미어코엑스센터': 's-oakwood', '오크우드 프리미어 코엑스 센터': 's-oakwood',
    '오크우드 프리미어 코엑스센터': 's-oakwood',
    '글래드강남코엑스센터': 's-glad-gangnam', '글래드 강남 코엑스 센터': 's-glad-gangnam',
    '글래드 강남 코엑스센터': 's-glad-gangnam', '글래드 강남 코엑스': 's-glad-gangnam',
    '글래드 여의도': 's-glad-yeouido',
    '그랜드워커힐서울': 's-grand-walkerhill', '그랜드 워커힐 서울': 's-grand-walkerhill',
    '그랜드워커힐 서울': 's-grand-walkerhill',
    '그랜드 워커힐 서울 호텔': 's-grand-walkerhill',
    '비스타워커힐서울': 's-vista-walkerhill', '비스타 워커힐 서울': 's-vista-walkerhill',
    '비스타 워커힐 서울 호텔': 's-vista-walkerhill',
    '롯데호텔월드': 's-lotte-world', '롯데호텔 월드': 's-lotte-world',
    '시그니엘서울': 's-signiel-seoul', '시그니엘 서울': 's-signiel-seoul',
    '아셈타워': 's-acem',
    '힐튼 가든 인 서울 강남': 's-hilton-garden', '힐튼가든 인 서울 강남': 's-hilton-garden',
    '힐튼 가든 인 서울 강남': 's-hilton-garden',
    '임피리얼 팰리스 서울': 's-imperial',
    '그랜드 머큐어 임피리얼 팰리스 서울': 's-imperial',
    '그랜드 머큐어 임피리얼 팰리스 서울 강남': 's-imperial',
    '르메르디앙 서울 명동': 's-lemeridien', '르메르디앙앤목시서울명동': 's-lemeridien',
    '르 메르디앙 & 목시 서울 명동': 's-lemeridien', '르메르디앙&목시 서울 명동': 's-lemeridien',
    '르메르디앙 & 목시 서울 명동': 's-lemeridien',
    '목시 서울 명동': 's-moxy',
    '노보텔 스위트 앰배서더 서울 용산': 's-novotel-suite',
    '노보텔 앰배서더 서울 용산': 's-novotel-yongsan',
    '노보텔 호텔&리조트 앰배서더 서울 용산': 's-novotel-yongsan',
    '이비스 스타일 앰배서더 서울 용산': 's-ibis-yongsan',
    '그랜드 머큐어 앰배서더 서울 용산': 's-gm-yongsan',
    '그랜드 머큐어 앰배서더 호텔 앤 레지던스 서울 용산': 's-gm-yongsan',
    '풀만 앰배서더 서울 이스트폴': 's-pullman-eastpole',
    '호텔 리베라 청담': 's-riviera', '호텔리베라 서울': 's-riviera',
    # 지방
    '그랜드 하얏트 인천 이스트타워': 'i-grand-hyatt', '그랜드 하얏트 인천': 'i-grand-hyatt',
    '그랜드 하얏트 인천 웨스트타워': 'i-grand-hyatt',
    '그랜드머큐어앰배서더창원': 'n-gm-changwon', '그랜드 머큐어 앰배서더 창원': 'n-gm-changwon',
    '대구메리어트호텔': 'd-marriott', '메리어트 대구': 'd-marriott',
    '대구 메리어트 호텔': 'd-marriott', '메리어트 대구': 'd-marriott',
    '대구 인터불고': 'd-interburgo', '호텔 인터불고 대구': 'd-interburgo',
    '호텔인터불고 대구': 'd-interburgo', '인터불고대구': 'd-interburgo',
    '대구 그랜드 호텔': 'd-grand',
    '힐튼 경주': 'p-hilton-gyeongju', '힐튼호텔 경주': 'p-hilton-gyeongju',
    '힐튼호텔경주': 'p-hilton-gyeongju', '힐튼 경주 호텔': 'p-hilton-gyeongju',
    '롯데호텔울산': 'u-lotte', '롯데호텔 울산': 'u-lotte',
    '롯데호텔부산': 'b-lotte', '롯데호텔 부산': 'b-lotte',
    '파라다이스호텔부산': 'b-paradise', '파라다이스 호텔 부산': 'b-paradise',
    '파라다이스호텔 부산': 'b-paradise',
    '웨스틴조선부산': 'b-westin-chosun', '웨스틴 조선 부산': 'b-westin-chosun',
    '파크하얏트부산호텔': 'b-park-hyatt', '파크 하얏트 부산': 'b-park-hyatt',
    '파크하얏트 부산': 'b-park-hyatt',
    '그랜드 조선 부산': 'b-grand-chosun', '그랜드조선부산': 'b-grand-chosun',
    '그랜드 조선 제주': 'j-grand-chosun',
    '롯데호텔제주': 'j-lotte', '롯데호텔 제주': 'j-lotte',
    'JW 메리어트 제주 리조트 & 스파': 'j-jw', 'JW메리어트 제주 리조트&스파': 'j-jw',
    '인스파이어 엔터테인먼트 리조트': 'i-inspire',
    '파라다이스시티 인천': 'i-paradise-city', '파라다이스시티': 'i-paradise-city',
    '호텔 오노마 대전 오토그래프 컬렉션': 'dj-onoma', '호텔 오노마': 'dj-onoma',
    '호텔오노마': 'dj-onoma', '호텔 오노마 대전': 'dj-onoma',
    '소노캄 고양': 'g-sonocam', '소노캄 여수': 'y-sonocam',
    '세인트존스 호텔': 'w-saintjohns',
    '호텔농심': 'b-nongshim',
}

# 카드사 공식 목록에만 있고 이 앱의 호텔 목록에는 없는 이름은 여기서 걸러 낸다.
#   더 플라자 = 2026-09-30 영업 종료
DROP_NAMES = {'더플라자', '더 플라자', '더 플라자 호텔 서울'}

# ────────────────────────────────────────────────────────────────
# 영수증 조건 — (type, 최소 결제액)  type: none / same_day / amount
# ────────────────────────────────────────────────────────────────
def none():
    return ('none', 0)


def same_day():
    return ('same_day', 0)


def amt(n):
    return ('amount', n)


def label_of(typ, n):
    if typ == 'amount':
        man = n / 10000.0
        txt = ('%g' % man) + '만원↑ 영수증'
        return txt
    if typ == 'same_day':
        return '당일 영수증'
    return '금액 조건 없음'


# ────────────────────────────────────────────────────────────────
# 신한카드 — VISA 인피니트·시그니처 지역별 호텔 발레파킹 안내(2025-12-22~2026-12-31)
#   https://www.shinhancard.com/pconts/html/benefit/event/1231045_2239.html
#   인피니트(The Premier·PREMIER GOLD EDITION·The Ace): 월 5회(호텔별)/전월 30만원
#   시그니처(The BEST·The LADY BEST): 월 5회(호텔별)/30만원
#   시그니처(The BEST+·The BEST-F·메리어트 본보이 더 베스트): 월 5회(호텔통합)/30만원
#   호텔 목록은 계열 공통 44곳(서울 33 · 지방 11). 더 플라자는 영업 종료로 제외 → 43.
# ────────────────────────────────────────────────────────────────
SHINHAN_URL = 'https://www.shinhancard.com/pconts/html/benefit/event/1231045_2239.html'
SHINHAN_HOTELS = [
    '메이필드호텔', '스위스그랜드호텔', '서울가든호텔', '호텔나루 서울 엠 갤러리',
    '페어몬트앰배서더서울', '콘래드서울호텔', '메리어트이그제큐티브아파트먼트서울',
    '코트야드메리어트서울타임스퀘어', 'JW메리어트동대문스퀘어', '포시즌스호텔서울',
    '코리아나호텔', '롯데호텔서울(소공)', '반얀트리클럽앤서울스파', '노보텔앰배서더서울동대문',
    '더플라자', '레스케이프호텔', '서울신라호텔', '앰배서더서울풀만',
    '그랜드하얏트서울', '몬드리안서울이태원', '서울드래곤시티', 'JW메리어트호텔서울',
    '그랜드인터컨티넨탈서울파르나스', '안다즈서울강남', '파크하얏트서울',
    '노보텔 앰배서더 강남', 'AC호텔 바이메리어트 서울강남', '오크우드프리미어코엑스센터',
    '글래드강남코엑스센터', '그랜드워커힐서울', '비스타워커힐서울', '롯데호텔월드', '시그니엘서울',
    '그랜드 하얏트 인천 이스트타워', '그랜드머큐어앰배서더창원', '대구메리어트호텔',
    '대구 인터불고', '힐튼 경주', '롯데호텔울산', '롯데호텔부산', '파라다이스호텔부산',
    '웨스틴조선부산', '파크하얏트부산호텔', '롯데호텔제주',
]

# 신한카드 Mastercard Diamond(선택서비스 유형1 베스트급) — The BEST·The LADY BEST
#   월 5회(호텔별)/30만원. 서울 21 · 지방 4(더 플라자 제외 24)
SHINHAN_MC_DIAMOND = [
    'https://www.shinhancard.com/pconts/download/card/MO_26_00782_master_diamond_1_best.pdf',
    ['JW메리어트동대문스퀘어', 'JW메리어트호텔서울', '그랜드워커힐서울', '그랜드하얏트서울',
     '노보텔앰배서더서울강남', '노보텔앰배서더서울동대문', '더플라자', '레스케이프호텔',
     '메리어트이그제큐티브아파트먼트서울', '코리아나 호텔', '메이필드호텔', '몬드리안서울이태원',
     '비스타워커힐서울', '서울가든호텔', '서울드래곤시티', '서울신라호텔', '스위스그랜드호텔',
     '안다즈서울강남', '앰배서더서울풀만', '오크우드프리미어코엑스센터', '콘래드서울호텔',
     '그랜드머큐어앰배서더창원', '대구메리어트호텔', '파라다이스호텔부산', '그랜드조선부산'],
]

# 신한카드 Mastercard Platinum(유형2 클래식급) — The CLASSIC-L·Y·S·V·NEO
#   호텔통합 월 3회/30만원, JW 메리어트 서울 월 1회. 서울 16 · 지방 3
SHINHAN_MC_CLASSIC = [
    'https://www.shinhancard.com/pconts/download/card/MO_26_00789_master_platinum_2_classics.pdf',
    ['JW메리어트호텔서울', '그랜드워커힐서울', '그랜드하얏트서울', '노보텔앰배서더서울강남',
     '노보텔앰배서더서울동대문', '레스케이프호텔', '메리어트이그제큐티브아파트먼트서울',
     '코리아나 호텔', '메이필드호텔', '몬드리안서울이태원', '비스타워커힐서울', '서울가든호텔',
     '서울드래곤시티', '서울신라호텔', '스위스그랜드호텔', '앰배서더서울풀만',
     '그랜드머큐어앰배서더창원', '대구메리어트호텔', '그랜드조선부산'],
]

# 신한카드 UnionPay Platinum(유형1 클래식급) — The CLASSIC-Y·The LADY CLASSIC·The CLASSIC-Lite·The BEST-T
#   호텔통합 월 3회/30만원. 서울 9 · 지방 1
SHINHAN_UPI_CLASSIC = [
    'https://www.shinhancard.com/pconts/download/card/MO_26_00802_upi_platinum_1_classics_bestt.pdf',
    ['그랜드하얏트서울', '노보텔앰배서더서울강남', '노보텔앰배서더서울동대문', '르메르디앙앤목시서울명동',
     '몬드리안서울이태원', '반얀트리클럽앤스파서울', '스위스그랜드호텔', '코리아나호텔',
     '코트야드메리어트서울타임스퀘어', '대구메리어트호텔'],
]

# ────────────────────────────────────────────────────────────────
# 삼성카드 — 브랜드 서비스 안내장(2026-01-01~12-31)
# ────────────────────────────────────────────────────────────────
SAM_AMEX = 'https://static11.samsungcard.com/wcms/personal/files/24_AMEX_E_004.pdf'
SAM_VISA_I = 'https://static11.samsungcard.com/wcms/personal/files/VISA_I_001.pdf'
SAM_MASTER_W = 'https://static11.samsungcard.com/wcms/personal/files/MASTER_W_002.pdf'

SAM_AMEX_HOTELS = [   # 22곳 · 공항 통합 월 5회 · 전월 50만원
    '그랜드 워커힐 서울', '그랜드 하얏트 서울', '노보텔 앰배서더 강남', '노보텔 앰배서더 서울 동대문',
    '더 플라자', '르메르디앙 서울 명동', '메이필드 호텔', '반얀트리 클럽 앤 스파 서울',
    '베스트 웨스턴 프리미어 서울가든호텔', '비스타 워커힐 서울', '서울드래곤시티', '서울신라호텔',
    '아셈타워', '앰배서더 서울 풀만', '코트야드 메리어트 서울 타임스퀘어',
    '힐튼 가든 인 서울 강남', 'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울',
    '그랜드 조선 부산', '대구 메리어트 호텔', '파크 하얏트 부산', '호텔인터불고 대구',
]
SAM_VISA_HOTELS = [   # 30곳 · 호텔별 월 5회 · 3개월 월평균 30만원
    '그랜드 워커힐 서울', '그랜드 하얏트 서울', '글래드 강남 코엑스센터', '노보텔 앰배서더 강남',
    '노보텔 앰배서더 서울 동대문', '더 플라자', '메리어트 이그제큐티브 아파트먼트 서울',
    '반얀트리 클럽 앤 스파 서울', '베스트 웨스턴 프리미어 서울가든호텔', '비스타 워커힐 서울',
    '서울드래곤시티', '서울신라호텔', '스위스 그랜드 호텔', '앰배서더 서울 풀만',
    '오크우드 프리미어 코엑스 센터', '코리아나 호텔', '코트야드 메리어트 서울 보타닉 파크 호텔',
    '코트야드 메리어트 서울 타임스퀘어', '콘래드 서울', '파크 하얏트 서울', '호텔 리베라 청담',
    'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울',
    '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천', '대구 메리어트 호텔',
    '웨스틴 조선 부산', '파크 하얏트 부산', '호텔농심', '호텔인터불고 대구',
]
SAM_MASTER_HOTELS = [  # 25곳 · 공항 통합 월 5회 · 전월 50만원
    '그랜드 워커힐 서울', '그랜드 하얏트 서울', '노보텔 앰배서더 강남', '노보텔 앰배서더 서울 동대문',
    '더 플라자', '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔',
    '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울', '서울가든호텔', '서울드래곤시티',
    '서울신라호텔', '스위스 그랜드 호텔', '앰배서더 서울 풀만', '오크우드 프리미어 코엑스 센터',
    '코트야드 메리어트 서울 타임스퀘어', '콘래드 서울', '파크 하얏트 서울',
    '코트야드 메리어트 서울 보타닉 파크 호텔', 'JW 메리어트 호텔 서울',
    '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천', '파크 하얏트 부산',
    '호텔농심', '호텔인터불고 대구',
]

# ────────────────────────────────────────────────────────────────
# 현대카드
# ────────────────────────────────────────────────────────────────
HY_PREMIUM = 'https://www.hyundaicard.com/cpu/ug/CPUUG3001_02.hc'
HY_AMEX_PLAT = 'https://www.hyundaicard.com/ct_pbb/html/amexMR_hotelValet_pl.html'
HY_AMEX_GREEN = 'https://www.hyundaicard.com/ct_pbb/html/amexMR_hotelValet_gr_ed2.html'
HY_PLATINUM_EV = 'https://www.hyundaicard.com/cpb/ev/CPBEV0101_06.hc?bnftWebEvntCd=GGE383'

# 프리미엄 카드 발레파킹 서비스 안내(2026년 기준, 공지 26.11.02)
#   R = the Red 계열 · G = the Green 계열 · P = the Pink 계열 · O = the Orange
#   S = Summit · M = MX Black Edition2
HY_RED_HOTELS = [   # R 27곳
    'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '그랜드 워커힐 서울',
    '그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남', '르메르디앙 & 목시 서울 명동',
    '레스케이프 호텔', '메이필드 호텔', '몬드리안 서울 이태원', '반얀트리 클럽 앤 스파 서울',
    '비스타 워커힐 서울', '서울 신라 호텔', '소피텔 앰배서더 서울 호텔 앤 서비스드 레지던스',
    '스위스 그랜드 호텔', '안다즈 서울 강남', '앰배서더 서울 풀만', '콘래드 서울',
    '포시즌스 호텔 서울', '인스파이어 엔터테인먼트 리조트', '파라다이스시티 인천',
    '메리어트 대구', '호텔 오노마 대전 오토그래프 컬렉션', '그랜드 조선 부산',
    '파라다이스호텔 부산', '파크 하얏트 부산', '롯데호텔 울산', 'JW 메리어트 제주 리조트 & 스파',
    '롯데호텔 제주',
]
HY_GREEN_HOTELS = [  # G 13곳
    '그랜드 워커힐 서울', '노보텔 앰배서더 서울 강남', '르메르디앙 & 목시 서울 명동',
    '레스케이프 호텔', '몬드리안 서울 이태원', '비스타 워커힐 서울',
    '소피텔 앰배서더 서울 호텔 앤 서비스드 레지던스', '안다즈 서울 강남', '앰배서더 서울 풀만',
    '인스파이어 엔터테인먼트 리조트', '파라다이스호텔 부산', '파크 하얏트 부산',
    'JW 메리어트 제주 리조트 & 스파',
]
# 아멕스 The Platinum Card(현대) — 39곳 · 공항·호텔 통합 월 5회 · 전월 50만원
HY_AMEX_PLAT_HOTELS = [
    'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '그랜드 워커힐 서울',
    '그랜드 인터컨티넨탈 서울 파르나스', '그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남',
    '노보텔 앰배서더 서울 동대문', '페어몬트 앰배서더 서울', '호텔 나루 서울 엠갤러리',
    '르메르디앙 서울 명동', '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔',
    '몬드리안 서울 이태원', '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울', '서울 가든 호텔',
    '서울드래곤시티', '서울 신라 호텔', '아셈타워', '안다즈 서울 강남', '앰배서더 서울 풀만 호텔',
    '오크우드 프리미어 코엑스 센터', '코트야드 메리어트 서울 타임스퀘어', '콘래드 서울 호텔',
    '파크 하얏트 서울', '포시즌스 호텔 서울', '힐튼 가든 인 서울 강남',
    '소피텔 앰배서더 서울 호텔 & 서비스드 레지던스', '그랜드 하얏트 인천', '소노캄 고양',
    '메리어트 대구', '호텔인터불고 대구', '호텔오노마', '힐튼호텔 경주', '그랜드 조선 부산',
    '웨스틴 조선 부산', '파크하얏트 부산', '소노캄 여수', '그랜드 조선 제주',
]
# 아멕스 Green Card Edition2(현대) — 36곳 · 공항·호텔 통합 월 5회 · 전월 50만원
HY_AMEX_GREEN_HOTELS = [
    'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '그랜드 워커힐 서울',
    '그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문',
    '페어몬트 앰배서더 서울', '호텔 나루 서울 엠갤러리', '르메르디앙 서울 명동',
    '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔', '몬드리안 서울 이태원',
    '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울', '서울 가든 호텔', '서울드래곤시티',
    '서울 신라 호텔', '아셈타워', '안다즈 서울 강남', '앰배서더 서울 풀만 호텔',
    '코트야드 메리어트 서울 타임스퀘어', '콘래드 서울 호텔', '파크 하얏트 서울',
    '포시즌스 호텔 서울', '힐튼 가든 인 서울 강남',
    '소피텔 앰배서더 서울 호텔 & 서비스드 레지던스', '그랜드 하얏트 인천', '소노캄 고양',
    '메리어트 대구', '호텔인터불고 대구', '호텔오노마', '힐튼호텔 경주', '그랜드 조선 부산',
    '파크하얏트 부산', '소노캄 여수', '그랜드 조선 제주',
]
# 플래티넘카드 발레파킹서비스 안내(2026년 기준) — 대상점별 월 3회
HY_VISA_PLAT_HOTELS = [   # Visa 22곳
    'JW 메리어트 동대문 스퀘어 서울', '그랜드 워커힐 서울', '그랜드 하얏트 서울',
    '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문 호텔 & 레지던스', '더 플라자',
    '메리어트 이그제큐티브 아파트먼트 서울', '반얀트리 클럽앤스파 서울', '비스타 워커힐 서울',
    '스위스 그랜드 호텔', '앰배서더 서울 풀만 호텔', '호텔 나루 서울 엠갤러리',
    '소피텔 앰배서더 서울 호텔 & 서비스드 레지던스', '호텔 코리아나', '글래드 강남 코엑스',
    'AC 호텔 바이 메리어트 서울 강남', '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천',
    '대구 메리어트 호텔', '파크 하얏트 부산', '호텔 인터불고 대구', '힐튼 경주',
]
HY_MASTER_PLAT_HOTELS = [  # Mastercard 21곳
    'JW 메리어트 호텔 서울', '그랜드 워커힐 서울', '그랜드 하얏트 서울',
    '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문 호텔 & 레지던스', '더 플라자',
    '레스케이프 호텔', '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔',
    '몬드리안 서울 이태원', '반얀트리 클럽앤스파 서울', '비스타 워커힐 서울', '서울신라호텔',
    '스위스 그랜드 호텔', '앰배서더 서울 풀만 호텔', '파크 하얏트 서울',
    '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천', '대구 메리어트 호텔',
    '파크 하얏트 부산', '파라다이스 호텔 부산',
]
HY_UPI_PLAT_HOTELS = [    # UnionPay 16곳
    'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '그랜드 워커힐 서울',
    '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문 호텔 & 레지던스', '더 플라자',
    '레스케이프 호텔', '르 메르디앙 & 목시 서울 명동', '메리어트 이그제큐티브 아파트먼트 서울',
    '반얀트리 클럽앤스파 서울', '비스타 워커힐 서울', '서울신라호텔', '스위스 그랜드 호텔',
    '소피텔 앰배서더 서울 호텔 & 서비스드 레지던스', '대구 메리어트 호텔', '웨스틴 조선 부산',
]

# ────────────────────────────────────────────────────────────────
# 롯데카드 — 국제브랜드 선택서비스 안내장(2026)
# ────────────────────────────────────────────────────────────────
LOTTE_VISA_PLAT = 'https://image.lottecard.co.kr/webapp/file/VISA_PLATINUM_04_260514.pdf'
LOTTE_AMEX_PE = 'https://image.lottecard.co.kr/webapp/mobile/images/card/detail/13_33.AMEX_PLATINUM_ELITE_03_260514OL.pdf'
LOTTE_AMEX_PLAT = 'http://image.lottecard.co.kr/webapp/file/AMERICAN_EXPRESS_PLATINUM_02_260514.pdf'
LOTTE_UPI = 'https://image.lottecard.co.kr/UploadFiles/cardProvisionPath/2017-B00022_20260519_10020.pdf'

LOTTE_VISA_HOTELS = [
    '그랜드 워커힐 서울', '그랜드 하얏트 서울', '글래드 강남 코엑스센터', '노보텔 앰배서더 서울 강남',
    '호텔 나루 서울 엠갤러리', '노보텔 앰배서더 서울 동대문 호텔 & 레지던스', '더 플라자',
    '몬드리안 서울 이태원', '레스케이프 호텔', '르 메르디앙 & 목시 서울 명동',
    '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔', '반얀트리 클럽 앤 스파 서울',
    '서울가든호텔', 'AC 호텔 바이 메리어트 서울 강남', '비스타 워커힐 서울', '서울 드래곤 시티',
    '스위스 그랜드 호텔', '호텔 코리아나', '오크우드 프리미어 코엑스 센터',
    '앰배서더 서울 풀만 호텔', '콘래드 서울', 'JW 메리어트 동대문 스퀘어 서울',
    '소피텔 앰배서더 서울 호텔 & 서비스드 레지던스', '안다즈 서울 강남',
    '그랜드 조선 부산', '파크하얏트 부산', '대구 메리어트 호텔', '호텔 인터불고 대구',
    '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천', '인스파이어 엔터테인먼트 리조트',
    '소노캄 고양', '소노캄 여수', '세인트존스 호텔',
]
LOTTE_AMEX_PE_HOTELS = [
    '서울 신라 호텔', '메리어트 이그제큐티브 아파트먼트 서울', '그랜드 하얏트 서울',
    '비스타 워커힐 서울', '그랜드 워커힐 서울', '반얀트리 클럽 앤 스파 서울', '르메르디앙 서울 명동',
    'JW메리어트 호텔 서울', '노보텔 앰배서더 서울 강남', '메이필드 호텔', '힐튼 가든 인 서울 강남',
    'AC 호텔 바이 메리어트 서울 강남', '앰배서더 서울 풀만 호텔', '안다즈 서울 강남',
    '서울 가든 호텔', '몬드리안 서울 이태원', '호텔 나루 서울 엠갤러리', '글래드 여의도',
    'JW 메리어트 동대문 스퀘어 서울', '서울드래곤시티', '노보텔 앰배서더 서울 동대문',
    '파크 하얏트 서울', '더 플라자 호텔 서울', '아셈타워', '포시즌스 호텔 서울',
    '코트야드 메리어트 서울 타임스퀘어', '호텔 인터불고 대구', '파크하얏트 부산',
    '소노캄 고양', '소노캄 여수', '힐튼호텔 경주', '그랜드 하얏트 인천', '호텔오노마',
    '대구 메리어트 호텔',
]
LOTTE_AMEX_PLAT_HOTELS = [
    '서울 신라 호텔', '메리어트 이그제큐티브 아파트먼트 서울', '그랜드 하얏트 서울',
    '비스타 워커힐 서울', '그랜드 워커힐 서울', '반얀트리 클럽 앤 스파 서울', '르메르디앙 서울 명동',
    'JW메리어트 호텔 서울', '노보텔 앰배서더 서울 강남', '메이필드 호텔', '힐튼 가든 인 서울 강남',
    'AC 호텔 바이 메리어트 서울 강남', '앰배서더 서울 풀만 호텔', '안다즈 서울 강남',
    '서울 가든 호텔', '몬드리안 서울 이태원', '호텔 나루 서울 엠갤러리', '글래드 여의도',
    'JW 메리어트 동대문 스퀘어 서울', '서울드래곤시티', '노보텔 앰배서더 서울 동대문',
    '파크 하얏트 서울', '호텔 인터불고 대구', '파크하얏트 부산', '소노캄 고양', '소노캄 여수',
    '힐튼호텔 경주', '그랜드 하얏트 인천', '호텔오노마',
]
LOTTE_UPI_HOTELS = [
    '그랜드 머큐어 앰배서더 호텔 앤 레지던스 서울 용산', '그랜드 워커힐 서울 호텔',
    '노보텔 스위트 앰배서더 서울 용산', '노보텔 호텔&리조트 앰배서더 서울 용산',
    '그랜드 하얏트 서울', '노보텔 앰배서더 서울 동대문 호텔 & 레지던스', '더 플라자',
    '레스케이프 호텔', '소피텔 앰배서더 서울 호텔 & 서비스드 레지던스',
    '메리어트 이그제큐티브 아파트먼트', '글래드 강남 코엑스 센터', '몬드리안 서울 이태원',
    '반얀트리 클럽 & 스파 서울', '비스타 워커힐 서울 호텔', '호텔 나루 서울 엠갤러리',
    '앰배서더 서울 풀만 호텔', '스위스 그랜드 호텔', '호텔 코리아나',
    '오크우드 프리미어 코엑스센터', '이비스 스타일 앰배서더 서울 용산',
    '코트야드 메리어트 서울 타임스퀘어', '콘래드 서울', '노보텔 앰버서더 서울 강남',
    'JW 메리어트 동대문스퀘어 서울', '파크 하얏트 서울', '웨스틴 조선 부산',
    '호텔 오노마 대전 오토그래프 컬렉션', '메리어트 대구', 'JW 메리어트 제주 리조트 & 스파',
]

# ────────────────────────────────────────────────────────────────
# KB국민카드 — VISA Platinum 서비스 안내(2026-01-01~12-31)
#   대상카드: 플래티늄(쿠폰형)·가온플래티늄·플래티늄 S. 호텔별 월 3회.
#   가온플래티늄만 전월 30만원, 쿠폰형·S는 별도 이용 조건 없음.
# ────────────────────────────────────────────────────────────────
KB_VISA_URL = 'https://m.kbcard.com/BON/DVIEW/MBCMCXHIAWEC0060'
KB_VISA_HOTELS = [
    '그랜드 워커힐 서울', '그랜드 하얏트 서울', '글래드 강남 코엑스센터',
    '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문 호텔', '더 플라자',
    '레스케이프 호텔', '르 메르디앙 & 목시 서울 명동', '메리어트 이그제큐티브 아파트먼트 서울',
    '메이필드 호텔', '몬드리안 서울 이태원', '반얀트리 클럽앤스파', '서울가든호텔',
    '비스타 워커힐 서울', '서울 드래곤 시티', '소피텔 앰배서더 서울', '스위스 그랜드 호텔',
    '안다즈 서울 강남', '앰배서더 서울 풀만 호텔', '오크우드 프리미어 코엑스 센터', '콘래드 서울',
    '호텔 나루 서울 엠갤러리', '호텔 코리아나', 'AC 호텔 바이 메리어트 서울 강남',
    'JW 메리어트 동대문 스퀘어 서울', '그랜드 머큐어 임피리얼 팰리스 서울',
    '그랜드 조선 부산', '파크 하얏트 부산', '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천',
    '대구 메리어트 호텔', '세인트존스 호텔', '소노캄 고양', '소노캄 여수',
    '인스파이어 엔터테인먼트 리조트', '호텔 오노마 대전 오토그래프 컬렉션', '호텔 인터불고 대구',
    '힐튼 경주', 'JW 메리어트 제주 리조트 & 스파',
]

# ────────────────────────────────────────────────────────────────
# 우리카드 — 국제브랜드 선택서비스 안내장 VISA Infinite 유형3(2026-01-01~12-31)
#   ALL 우리카드 Infinite: 공항 통합 월 3회/연 10회 · 전월 국내외 50만원
# ────────────────────────────────────────────────────────────────
WOORI_URL = 'https://pc.wooricard.com/dcpc/yh1/cct/cct11/prdntc/H1CCT211S09.do'
WOORI_HOTELS = [
    '그랜드 머큐어 임피리얼 팰리스 서울', '그랜드워커힐 서울', '그랜드하얏트 서울',
    '글래드강남코엑스센터', '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문 호텔&레지던스',
    '더 플라자', '레스케이프 호텔', '르메르디앙&목시 서울 명동',
    '메리어트이그제큐티브아파트먼트서울', '메이필드 호텔', '몬드리안 서울 이태원',
    '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울', '서울가든호텔', '서울 드래곤 시티',
    '서울신라호텔', '소피텔 앰배서더 서울 호텔&서비스드 레지던스', '스위스 그랜드 호텔',
    '안다즈 서울 강남', '앰배서더 서울 풀만 호텔', '오크우드 프리미어 코엑스 센터',
    '코트야드 바이 메리어트 서울 타임스퀘어', '콘래드 서울', '파크 하얏트 서울',
    '포시즌스 호텔 서울', '호텔 나루 서울 엠갤러리', '호텔 코리아나',
    'AC 호텔 바이 메리어트 서울 강남', 'JW 메리어트 동대문 스퀘어 서울',
    'JW 메리어트 호텔 서울', '페어몬트 앰배서더 서울', '풀만 앰배서더 서울 이스트폴',
    '그랜드 조선 부산', '웨스틴 조선 부산', '파크 하얏트 부산', '그랜드 머큐어 앰배서더 창원',
    '그랜드 하얏트 인천', '대구 메리어트 호텔', '세인트존스 호텔', '소노캄 고양', '소노캄 여수',
    '인스파이어 엔터테인먼트 리조트', '호텔 오노마 대전 오토그래프 컬렉션',
    '호텔 인터불고 대구', '힐튼 경주', 'JW 메리어트 제주 리조트 & 스파',
]

# ────────────────────────────────────────────────────────────────
# 카드 정의
#   cond: {공식 호텔 이름: (type, 금액)}  — 없으면 기본(금액 조건 없음)
#   hours: {호텔 이름: (표기, 시간)}       — 없으면 카드 기본
#   limit: {호텔 이름: (표기, 횟수)}       — 없으면 카드 기본
# ────────────────────────────────────────────────────────────────
CARDS = [
    # ── 신한카드 ───────────────────────────────────────────────
    dict(id='sh-visa-infinite', issuer='신한카드',
         name='신한카드 The ACE · The Premier (Visa Infinite)',
         network='Visa Infinite', tier='인피니트', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 2~3시간', hours_n=3,
         note='VISA 인피니트 계열(The Premier·PREMIER GOLD EDITION·The Ace) 공통 안내. '
              '실물 카드 제시 · 호텔 객실·식음(연회장 제외) 이용 본인 한정.',
         airport='공항 발레파킹은 별도 안내',
         url=SHINHAN_URL, basis='official', complete=True, hotels=SHINHAN_HOTELS),
    dict(id='sh-visa-best', issuer='신한카드',
         name='신한카드 The BEST · The LADY BEST (Visa Signature)',
         network='Visa Signature', tier='시그니처', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 2~3시간', hours_n=3,
         note='The BEST(연회비 20만원 기본/21만원 항공형)·The LADY BEST는 호텔별 월 5회. '
              'The BEST+·The BEST-F·메리어트 본보이 더 베스트는 호텔통합이라 따로 표기합니다.',
         airport='공항 발레파킹은 별도 안내',
         url=SHINHAN_URL, basis='official', complete=True, hotels=SHINHAN_HOTELS),
    dict(id='sh-visa-bestplus', issuer='신한카드',
         name='신한카드 The BEST+ · The BEST-F (Visa Signature)',
         network='Visa Signature', tier='시그니처', limit_label='월 5회(호텔통합)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 2~3시간', hours_n=3,
         note='The BEST+·The BEST-F는 참여 호텔 전체 합산 월 5회(The BEST의 호텔별 5회와 다름).',
         airport='공항 발레파킹은 별도 안내',
         url=SHINHAN_URL, basis='official', complete=True, hotels=SHINHAN_HOTELS),
    dict(id='sh-marriott-bonvoy', issuer='신한카드',
         name='메리어트 본보이 더 베스트 신한카드 (Visa Signature)',
         network='Visa Signature', tier='시그니처', limit_label='월 5회(호텔통합)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 2~3시간', hours_n=3,
         note='신한 VISA 시그니처 계열 안내의 대상카드로 명시(연회비 26만 7천원). '
              'The BEST+·The BEST-F와 같은 호텔통합 월 5회입니다.',
         airport='공항 발레파킹은 별도 안내',
         url=SHINHAN_URL, basis='official', complete=True, hotels=SHINHAN_HOTELS),
    dict(id='sh-master-diamond', issuer='신한카드',
         name='신한카드 The BEST · The LADY BEST (Mastercard Diamond)',
         network='Mastercard Diamond', tier='다이아몬드', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 2~3시간', hours_n=3,
         note='Mastercard Diamond 선택서비스 유형1(베스트급) 안내장 기준. 공항라운지 연 3회·'
              '공항발레파킹 월 3회도 같은 안내장에 있습니다.',
         airport='공항 발레파킹 월 3회(별도)',
         url=SHINHAN_MC_DIAMOND[0], basis='official', complete=True, hotels=SHINHAN_MC_DIAMOND[1]),
    dict(id='sh-mc-classic', issuer='신한카드',
         name='신한카드 The CLASSIC-L·Y·S·V·NEO (Mastercard Platinum)',
         network='Mastercard Platinum', tier='플래티넘', limit_label='월 3회(호텔통합)', limit_n=3,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 2~3시간', hours_n=3,
         note='Mastercard Platinum 선택서비스 유형2(클래식급) 안내장 기준. 참여 호텔 전체 합산 월 3회, '
              'JW 메리어트 서울은 월 1회. UnionPay 브랜드 발급분은 대상 호텔이 10곳으로 다릅니다.',
         airport='공항 발레파킹 월 3회(별도)·공항라운지 연 2회',
         url=SHINHAN_MC_CLASSIC[0], basis='official', complete=True,
         hotels=SHINHAN_MC_CLASSIC[1],
         limit={'JW메리어트호텔서울': ('월 1회', 1)}),
    dict(id='sh-upi-classic', issuer='신한카드',
         name='신한카드 The CLASSIC-Y·LADY CLASSIC (UnionPay Platinum)',
         network='UnionPay Platinum', tier='플래티넘', limit_label='월 3회(호텔통합)', limit_n=3,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 2~3시간', hours_n=3,
         note='UnionPay Platinum 선택서비스 유형1(클래식급) 안내장 기준 — The CLASSIC-Y·'
              'The LADY CLASSIC·The CLASSIC-Lite·The BEST-T 공통 10곳.',
         airport='공항 발레파킹 월 3회(별도)·공항라운지 연 2회',
         url=SHINHAN_UPI_CLASSIC[0], basis='official', complete=True,
         hotels=SHINHAN_UPI_CLASSIC[1]),

    # ── 삼성카드 ───────────────────────────────────────────────
    dict(id='sam-amex-platinum', issuer='삼성카드',
         name='삼성 American Express PLATINUM ELITE',
         network='Amex Platinum Elite', tier='플래티넘 엘리트',
         limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='공항 발레파킹과 통합 월 5회. 대상 호텔 22곳(안내장 표기).',
         airport='공항 통합 월 5회',
         url=SAM_AMEX, basis='official', complete=True, hotels=SAM_AMEX_HOTELS,
         cond={'JW 메리어트 호텔 서울': amt(30000)}),
    dict(id='sam-visa-infinite', issuer='삼성카드',
         name='삼성 THE O (Visa Infinite)',
         network='Visa Infinite', tier='인피니트', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='3개월 평균 30만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         note='THE O 카드의 VISA 인피니트 선택서비스 — 호텔별 월 5회, 직전 3개월 월평균 30만원. '
              '대상 호텔 30곳(안내장 표기).',
         airport='공항 발레파킹 별도(인천·김포 월 5회)',
         url=SAM_VISA_I, basis='official', complete=True, hotels=SAM_VISA_HOTELS,
         cond={'JW 메리어트 호텔 서울': amt(30000), '코리아나 호텔': amt(25000),
               '파크 하얏트 서울': amt(20000)}),
    dict(id='sam-master-world', issuer='삼성카드',
         name='삼성 THE O V2 (Mastercard World)',
         network='Mastercard World', tier='월드', limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='THE O V2(아시아나) Mastercard World 선택서비스 — 인천공항 발레파킹과 통합 월 5회. '
              '대상 호텔 25곳(안내장 표기).',
         airport='공항 통합 월 5회',
         url=SAM_MASTER_W, basis='official', complete=True, hotels=SAM_MASTER_HOTELS,
         cond={'JW 메리어트 호텔 서울': amt(30000), '파크 하얏트 서울': amt(20000)}),

    # ── 현대카드 ───────────────────────────────────────────────
    dict(id='hy-the-red', issuer='현대카드',
         name='현대카드 the Red 계열 (the Red·the Red Stripe·Ed4·Ed5)',
         network='현대카드 전용', tier='the Red', limit_label='월 10회(공항·호텔 통합)', limit_n=10,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='the Red·the Red Stripe Edition2는 공항·호텔 통합 월 10회, the Red Stripe·'
              'the Red Edition4·5는 공항·호텔 각각 월 5회. 실물 카드 필수·본인 탑승 차량.',
         airport='the Red·Red Stripe Ed2 = 통합 월 10회',
         url=HY_PREMIUM, basis='official', complete=True, hotels=HY_RED_HOTELS),
    dict(id='hy-green', issuer='현대카드',
         name='현대카드 the Green·the Pink 계열 (G·P)',
         network='Visa·Mastercard', tier='the Green', limit_label='월 5회(공항·호텔 각각)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='the Green·the Green Edition2·3·4 공통(G). 호텔 월 5회·공항 월 5회를 각각 씁니다. '
              '상품 페이지에는 그랜드 워커힐·비스타 워커힐·소피텔 3곳만 적혀 있어, 계열 공지 13곳과 차이가 있습니다.',
         airport='호텔·공항 각각 월 5회',
         url=HY_PREMIUM, basis='official', complete=True, hotels=HY_GREEN_HOTELS),
    dict(id='hy-amex-platinum', issuer='현대카드',
         name='American Express The Platinum Card (현대)',
         network='Amex Platinum', tier='플래티넘', limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='본인·가족 합산, 공항 발렛과 통합 월 5회. 대상점별 최소 결제액이 따로 있습니다.',
         airport='공항 통합 월 5회',
         url=HY_AMEX_PLAT, basis='official', complete=True, hotels=HY_AMEX_PLAT_HOTELS,
         cond={'JW 메리어트 호텔 서울': amt(50000), '몬드리안 서울 이태원': amt(25000),
               '포시즌스 호텔 서울': amt(30000), '파크 하얏트 서울': amt(20000),
               '그랜드 인터컨티넨탈 서울 파르나스': same_day()},
         hours={'힐튼 가든 인 서울 강남': ('1일 4시간', 4)}),
    dict(id='hy-amex-green', issuer='현대카드',
         name='현대 American Express Green Card Edition2',
         network='Amex Green', tier='그린', limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='본인·가족 합산, 공항 발렛과 통합 월 5회. 대상점별 최소 결제액이 따로 있습니다.',
         airport='공항 통합 월 5회',
         url=HY_AMEX_GREEN, basis='official', complete=True, hotels=HY_AMEX_GREEN_HOTELS,
         cond={'JW 메리어트 호텔 서울': amt(50000), '몬드리안 서울 이태원': amt(25000),
               '포시즌스 호텔 서울': amt(30000), '파크 하얏트 서울': amt(20000)},
         hours={'힐튼 가든 인 서울 강남': ('1일 4시간', 4)}),
    dict(id='hy-visa-plat', issuer='현대카드',
         name='현대카드 M2·M3 Platinum (Visa)',
         network='Visa Platinum', tier='플래티넘', limit_label='월 3회(대상점별)', limit_n=3,
         prev_label='전월 30만~50만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         note='플래티넘카드 발레파킹서비스 안내(2026) Visa 대상점. 전월 50만원(MX Black·M2·M3 BOOST 등) '
              '또는 30만원(M3·T3·H3·R3·M2 Platinum 등) 카드별 기준.',
         airport='공항 통합 월 3회',
         url=HY_PLATINUM_EV, basis='official', complete=True, hotels=HY_VISA_PLAT_HOTELS),
    dict(id='hy-master-plat', issuer='현대카드',
         name='현대카드 M2·M3 Platinum (Mastercard)',
         network='Mastercard Platinum', tier='플래티넘', limit_label='월 3회(대상점별)', limit_n=3,
         prev_label='전월 30만~50만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         note='플래티넘카드 발레파킹서비스 안내(2026) Mastercard 대상점.',
         airport='공항 통합 월 3회',
         url=HY_PLATINUM_EV, basis='official', complete=True, hotels=HY_MASTER_PLAT_HOTELS),
    dict(id='hy-unionpay-plat', issuer='현대카드',
         name='현대카드 M2·M3 Platinum (UnionPay)',
         network='UnionPay Platinum', tier='플래티넘', limit_label='월 3회(대상점별)', limit_n=3,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='플래티넘카드 발레파킹서비스 안내(2026) UnionPay 대상점. JW 메리어트 서울은 월 1회 한도.',
         airport='공항 통합 월 3회',
         url=HY_PLATINUM_EV, basis='official', complete=True, hotels=HY_UPI_PLAT_HOTELS,
         limit={'JW 메리어트 호텔 서울': ('월 1회', 1)}),

    # ── 롯데카드 ───────────────────────────────────────────────
    dict(id='lotte-visa-plat', issuer='롯데카드',
         name='롯데카드 디지로카 Monaco (Visa Platinum)',
         network='Visa Platinum', tier='플래티넘', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='본인+가족 합산 · 실물 카드 제시. 대상 호텔 35곳(안내장 표기).',
         airport='공항 발레파킹 별도',
         url=LOTTE_VISA_PLAT, basis='official', complete=True, hotels=LOTTE_VISA_HOTELS,
         cond={'그랜드 하얏트 서울': same_day(), '호텔 나루 서울 엠갤러리': same_day(),
               '몬드리안 서울 이태원': amt(25000), '레스케이프 호텔': amt(30000),
               '호텔 코리아나': amt(25000), '오크우드 프리미어 코엑스 센터': same_day(),
               'JW 메리어트 동대문 스퀘어 서울': same_day(),
               '그랜드 조선 부산': same_day(), '세인트존스 호텔': same_day()}),
    dict(id='lotte-amex-pe', issuer='롯데카드',
         name='롯데백화점 Flex (Amex Platinum Elite)',
         network='Amex Platinum Elite', tier='플래티넘 엘리트',
         limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='본인+가족 합산. 대상 호텔 34곳(안내장 표기).',
         airport='공항 발레파킹 별도',
         url=LOTTE_AMEX_PE, basis='official', complete=True, hotels=LOTTE_AMEX_PE_HOTELS,
         cond={'JW메리어트 호텔 서울': amt(50000), '몬드리안 서울 이태원': amt(25000),
               '파크 하얏트 서울': amt(20000), '포시즌스 호텔 서울': amt(30000)},
         hours={'힐튼 가든 인 서울 강남': ('1일 4시간', 4),
                'AC 호텔 바이 메리어트 서울 강남': ('1일 4시간', 4)}),
    dict(id='lotte-amex-plat', issuer='롯데카드',
         name='롯데 샤롯데 플래티넘 스타 (Amex Platinum)',
         network='Amex Platinum', tier='플래티넘', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='JW 메리어트 서울은 월 1회. 대상 호텔 29곳(안내장 표기).',
         airport='공항 발레파킹 별도',
         url=LOTTE_AMEX_PLAT, basis='official', complete=True, hotels=LOTTE_AMEX_PLAT_HOTELS,
         cond={'JW메리어트 호텔 서울': amt(50000), '몬드리안 서울 이태원': amt(25000),
               '파크 하얏트 서울': amt(20000)},
         hours={'힐튼 가든 인 서울 강남': ('1일 4시간', 4),
                'AC 호텔 바이 메리어트 서울 강남': ('1일 4시간', 4)},
         limit={'JW메리어트 호텔 서울': ('월 1회', 1)}),
    dict(id='lotte-unionpay-diamond', issuer='롯데카드',
         name='롯데 위버스카이 (UnionPay Diamond)',
         network='UnionPay Diamond', tier='다이아몬드', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 10만원', prev_n=100000, hours_label='1일 3시간', hours_n=3,
         note='본인+가족 합산. 그랜드·비스타 워커힐은 통합 운영. 대상 호텔 29곳(안내장 표기).',
         airport='공항 발레파킹 별도',
         url=LOTTE_UPI, basis='official', complete=True, hotels=LOTTE_UPI_HOTELS,
         cond={'그랜드 하얏트 서울': same_day(), '레스케이프 호텔': amt(30000),
               '몬드리안 서울 이태원': amt(25000), '호텔 나루 서울 엠갤러리': same_day(),
               '호텔 코리아나': amt(25000), '오크우드 프리미어 코엑스센터': same_day(),
               'JW 메리어트 동대문스퀘어 서울': same_day(), '파크 하얏트 서울': amt(20000),
               '웨스틴 조선 부산': same_day()}),

    # ── KB국민카드 ─────────────────────────────────────────────
    dict(id='kb-visa-plat', issuer='KB국민카드',
         name='KB국민 플래티늄 (Visa)',
         network='Visa Platinum', tier='플래티넘', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='가온 30만원 / 쿠폰형 조건 없음', prev_n=300000,
         hours_label='1일 3시간', hours_n=3,
         note='대상카드: 플래티늄(쿠폰형)·가온플래티늄·플래티늄 S. 쿠폰형·S는 별도 이용 조건이 없고 '
              '가온플래티늄만 전월 30만원. 호텔별 금액 기준이 붙은 곳이 있습니다.',
         airport='공항 발레파킹 월 3회(별도)',
         url=KB_VISA_URL, basis='official', complete=True, hotels=KB_VISA_HOTELS,
         cond={'레스케이프 호텔': amt(30000), '몬드리안 서울 이태원': amt(25000),
               '호텔 코리아나': amt(25000),
               '그랜드 머큐어 임피리얼 팰리스 서울': amt(20000),
               '오크우드 프리미어 코엑스 센터': same_day(),
               '그랜드 하얏트 서울': same_day(), '앰배서더 서울 풀만 호텔': same_day(),
               '노보텔 앰배서더 서울 강남': same_day(),
               '메리어트 이그제큐티브 아파트먼트 서울': same_day(),
               'JW 메리어트 동대문 스퀘어 서울': same_day()}),

    # ── 우리카드 ───────────────────────────────────────────────
    dict(id='woori-all-infinite', issuer='우리카드',
         name='ALL 우리카드 Infinite',
         network='Visa Infinite', tier='인피니트', limit_label='월 3회(공항 통합)', limit_n=3,
         prev_label='전월 국내외 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         note='VISA 선택서비스(유형3). 공항 발레파킹과 통합 월 3회·연 10회, 연 단위 2026-12-31까지. '
              '국내 발급 Visa Infinite 본인 회원 · 실물 카드. 대상 호텔 47곳(안내장 표기).',
         airport='공항 통합 월 3회·연 10회',
         url=WOORI_URL, basis='official', complete=True, hotels=WOORI_HOTELS,
         cond={'그랜드 머큐어 임피리얼 팰리스 서울': amt(20000),
               '그랜드하얏트 서울': same_day(), '레스케이프 호텔': amt(30000),
               '몬드리안 서울 이태원': amt(25000), '오크우드 프리미어 코엑스 센터': same_day(),
               '앰배서더 서울 풀만 호텔': same_day(), '파크 하얏트 서울': amt(20000),
               '포시즌스 호텔 서울': amt(30000), '호텔 나루 서울 엠갤러리': same_day(),
               '호텔 코리아나': amt(25000), 'JW 메리어트 동대문 스퀘어 서울': same_day(),
               'JW 메리어트 호텔 서울': amt(50000), '페어몬트 앰배서더 서울': amt(30000),
               '그랜드 조선 부산': same_day(), '웨스틴 조선 부산': same_day(),
               '세인트존스 호텔': same_day()}),

    # ── 조건만 확인된 카드(공식 안내에서 대상 호텔 목록은 확인하지 못함) ──
    dict(id='hana-jade-first', issuer='하나카드',
         name='하나카드 JADE First Centum (Visa Infinite)',
         network='Visa Infinite', tier='인피니트', limit_label='월 8회(공항 통합)·연 60회', limit_n=8,
         prev_label='하나카드 안내 확인', prev_n=0, hours_label='1일 3시간', hours_n=3,
         note='하나카드 상품 페이지에 VISA Infinite 특급호텔 발레파킹 월 8회·연 60회로 표기. '
              '대상 호텔 목록은 공식 안내에서 확인하지 못해 호텔을 붙이지 않았습니다.',
         airport='공항 통합 월 8회·연 60회',
         url='https://www.hanacard.co.kr/OPI42000000D.web?CD_PD_SEQ=17870',
         basis='official-condition', complete=False, hotels=[]),
    dict(id='bc-diamond', issuer='BC카드',
         name='BC Diamond (회원사 공통)',
         network='Mastercard Diamond', tier='다이아몬드', limit_label='월 3회(공항 통합)', limit_n=3,
         prev_label='조건 없음', prev_n=0, hours_label='1일 3시간', hours_n=3,
         note='BC카드 VIP 안내의 Diamond 선택서비스 기준. 호텔 목록은 확인된 공식 안내가 '
              '2015년판이라 지금 대상점으로 쓰지 않았습니다(호텔 미표기).',
         airport='공항 통합 월 3회',
         url='https://www.bccard.com/app/card/ContentsLinkActn.do?pgm_id=vip0024',
         basis='secondary', complete=False, hotels=[]),
    dict(id='nh-wi-terra', issuer='NH농협카드',
         name='NH 위 테라카드 (Visa Signature)',
         network='Visa Signature', tier='시그니처', limit_label='월 5회(호텔 통합)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         note='NH농협 안내 기준 월 5회·전월 30만원. 대상 호텔 목록을 공식 안내에서 확인하지 못해 '
              '호텔을 붙이지 않았습니다.',
         airport='공항 발레파킹 별도',
         url='https://card.nonghyup.com/file/ebank/form/pdf/serviceGuide_BCPlatinum_221101.pdf',
         basis='secondary', complete=False, hotels=[]),
]

# ────────────────────────────────────────────────────────────────
# 한진님 보유 카드 58장 — 원문 그대로 보존한다(임의 삭제·확정 금지).
#   (순번, 발급사, 카드명, 유형, 발렛 연결 카드 id 또는 None, 상태 메모, 혜택 메모)
#   valet 상태는 아래 네 가지로만 나눈다.
#     eligible = 카드사 공식 안내에서 호텔 발렛 확인 → 발렛 카드 id 연결
#     unknown  = 발렛 여부를 확인하지 못함(체크·선불·법인 다수)
#     none     = 공식 상품 안내에 호텔 발렛이 없음이 확인됨
# ────────────────────────────────────────────────────────────────
MY_CARDS = [
    (1, 'IBK기업은행', '참! 좋은 kt wiz 카드', '신용', None, '중복 가능(23번 체크판과 카드명 같음)', None),
    (2, 'BNK부산은행', '부자되세요 홈쇼핑카드', '신용', None, None, None),
    (3, '하나카드', 'MG+ Blue 하나카드', '신용', None, None, None),
    (4, 'NH농협카드', '라이언 치즈 체크카드', '체크', None, None, None),
    (5, '롯데카드', 'SKYPASS 롯데 플래티넘 체크카드', '체크', None,
     '발렛 없음 — 공식 상품 페이지에 호텔·공항 발렛 선택서비스가 없고 공항 라운지 연 2회만 확인된다(2026-05-29 신규 발급 중단, 기존 회원은 유효기간까지 사용).',
     dict(benefit='대한항공 1,500원당 1마일 · 공항 라운지 연 2회(전월 50만원)',
          prev='전월 50만원(라운지)', limit='라운지 연 2회', exclude='지방세·아파트관리비·현금서비스·카드론 등')),
    (6, 'KB국민카드', '홈플러스 KB국민카드', '신용', None, None, None),
    (7, 'BC·신한카드', 'BC 부자되세요 홈쇼핑 신한카드', '신용', None, None, None),
    (8, 'BC·iM뱅크', '동아-대구은행 대한항공 마일리지 카드 후보', '신용', None, '상품명 미확정(후보)', None),
    (9, 'KB국민카드', '노리2 체크카드(KB Pay)', '체크', None, None, None),
    (10, '신한카드', 'The CLASSIC-Y', '신용', 'sh-mc-classic',
     'Mastercard 플래티넘 공식 안내장 기준 호텔통합 월 3회·전월 30만원, 대상 19곳(JW 메리어트 서울 월 1회) — UnionPay 발급분은 대상 10곳(sh-upi-classic)으로 다르니 카드 앞면 브랜드를 확인하세요.',
     dict(benefit='호텔 발렛 통합 월 3회 · 공항 발레파킹 월 3회 · 1일 2~3시간 무료주차', prev='전월 30만원',
          limit='월 3회(호텔 통합)', exclude='현금서비스·카드론·수수료·이자·거래 취소')),
    (11, 'IBK기업은행', 'K-패스', '신용', None, None, None),
    (12, '하나카드', 'L.PAY 하나 체크카드', '체크', None, None, None),
    (13, 'iM뱅크', '대구단디 체크카드', '체크', None, None, None),
    (14, '케이뱅크', 'ONE 체크카드(K-패스)', '체크', None, None, None),
    (15, 'KB국민카드', '아시아나 KB국민 플래티넘카드', '신용', 'kb-visa-plat',
     'KB 플래티늄(쿠폰형) 프로그램 — 호텔별 월 3회, 쿠폰형은 전월 실적 조건 없음(가온플래티늄만 30만원). 아래 목록은 VISA 브랜드 공식 39곳이며 MASTER 브랜드로 발급된 카드는 대상점이 달라 KB(1599-4300) 확인이 필요합니다.',
     dict(benefit='호텔별 월 3회 발렛 · 공항 발레파킹 월 3회 · 1일 3시간 무료주차',
          prev='쿠폰형 조건 없음 / 가온 30만원', limit='월 3회(호텔별)',
          exclude='세금·공과금·등록금·상품권·관리비·수수료·이자')),
    (16, 'KB국민카드', 'KB 틴업 체크카드(티니핑)', '체크', None, None, None),
    (17, '우리카드', 'ALL 우리카드 Infinite', '신용', 'woori-all-infinite',
     'VISA 선택서비스(유형3) — 공항 통합 월 3회·연 10회, 전월 국내외 50만원. 공식 대상 호텔 47곳(더 플라자 영업 종료로 화면에는 46곳).',
     dict(benefit='공항 발렛 + 호텔 발렛 통합 월 3회/연 10회 · 1일 3시간 무료주차',
          prev='전월 국내외 50만원', limit='월 3회·연 10회(공항 통합)',
          exclude='현금서비스·카드론·연회비·수수료·이자')),
    (18, 'BNK부산은행', '동백전 체크카드', '체크', None, None, None),
    (19, '삼성카드', 'iD SIMPLE', '신용', None, None, None),
    (20, 'NH농협카드', '올바른 NEW HAVE(원이) 체크카드', '체크', None, '중복 가능(27번 올바른 NEW HAVE와 유사)', None),
    (21, 'BC바로', 'GOAT BC 바로카드', '신용', None, None, None),
    (22, '롯데카드', 'SKYPASS 롯데카드', '신용', None,
     '호텔 발렛 확인 필요 — 롯데카드 공식 발렛 안내(디지로카 Monaco·샤롯데·위버스카이)에 이 상품명이 없어 임의 확정하지 않았다.', None),
    (23, 'IBK기업은행', '참! 좋은 kt wiz 카드', '체크', None, '중복 가능(01번 신용판과 카드명 같음)', None),
    (24, '현대카드', 'the Green', '신용', 'hy-green',
     '현대카드 프리미엄 발레파킹 안내(2026-11-02, 계열 G) — 공항·호텔 각각 월 5회, 전월 50만원, 대상 13곳. 상품 페이지에는 그랜드·비스타 워커힐·소피텔 3곳만 적혀 있습니다.',
     dict(benefit='공항·호텔 발렛 각각 월 5회 · 1일 3시간 · 실물 카드 필수', prev='전월 50만원',
          limit='월 5회(공항·호텔 각각)', exclude='카드론·현금서비스·연회비·수수료·이자')),
    (25, '우리카드', '우리 ONE 체크카드(국제ATM)', '체크', None, None, None),
    (26, 'iM뱅크', '스카이패스카드(세부판본 미확정)', '신용', None, '세부판본 미확정', None),
    (27, 'NH농협카드', '올바른 NEW HAVE 체크카드', '체크', None, '중복 가능(20번 원이 체크카드와 유사)', None),
    (28, '확인 필요', 'CJ카드(패스-신)', '미확인', None, '발급사·유형 미확인 · 상품명 미확정', None),
    (29, 'KB국민카드', '트래블러스 체크카드', '체크', None, None, None),
    (30, 'BNK부산은행', '스카이패스카드 후보', '신용', None, '상품명 미확정(후보)', None),
    (31, '케이뱅크', '교통 전용(ONE K-패스)', '교통전용', None, '유형: 교통전용', None),
    (32, 'KB국민카드', '포인트리 체크카드', '체크', None, None, None),
    (33, '하나카드', '트래블로그 체크카드(구형 후보)', '체크', None, '중복 가능(35번과 같은 상품 후보) · 구형 여부 미확정', None),
    (34, '삼성카드', '전우사랑 패밀리 삼성카드', '신용', None, None, None),
    (35, '하나카드', '트래블로그 체크카드(구형 후보)', '체크', None, '중복 가능(33번과 같은 상품 후보) · 구형 여부 미확정', None),
    (36, '하나카드', '네이버페이 머니 하나 체크카드', '체크', None, None, None),
    (37, '삼성카드', '삼성증권 CMA+ 애니패스 체크카드', '체크', None, None, None),
    (38, 'KB국민카드', '금융포인트리카드', '신용', None, None, None),
    (39, '삼성카드', '신세계 삼성지엔미포인트 체크카드', '체크', None, None, None),
    (40, '현대백화점', '현대백화점카드(그린 디자인)', '전용', None, '전용카드(백화점 멤버십)', None),
    (41, 'BNK부산은행', '아시아나클럽카드', '신용', None, None, None),
    (42, '현대카드', 'American Express The Platinum Card', '신용', 'hy-amex-platinum',
     '아멕스 호텔 발레파킹 안내(2026) — 공항 통합 월 5회·전월 50만원, 대상 39곳. JW 메리어트 서울 5만원·포시즌스 3만원·몬드리안 2.5만원·파크 하얏트 서울 2만원 이상 결제 조건.',
     dict(benefit='공항·호텔 발렛 통합 월 5회 · 1일 3시간 · 실물 카드 필수', prev='전월 50만원',
          limit='월 5회(공항 통합)', exclude='카드론·현금서비스·연회비·수수료·이자')),
    (43, 'IBK기업은행', 'IBK 스카이패스카드 후보', '신용', None, '상품명 미확정(후보)', None),
    (44, '토스뱅크', '토스뱅크 체크카드', '체크', None, None, None),
    (45, '하나카드', '인터파크 투어 스카이패스 카드', '신용', None, None, None),
    (46, 'KB국민카드', 'Liiv Mate 카드', '신용', None, None, None),
    (47, '신한카드', '메리어트 본보이 더 베스트', '신용', 'sh-marriott-bonvoy',
     '신한 VISA 시그니처 공식 안내의 대상카드(연회비 26만 7천원) — 호텔통합 월 5회·전월 30만원. The BEST(호텔별)나 The BEST+와 다른 카드로 따로 표기했습니다.',
     dict(benefit='호텔 발렛 통합 월 5회 · 1일 2~3시간 무료주차', prev='전월 30만원',
          limit='월 5회(호텔통합)', exclude='현금서비스·카드론·수수료·이자·거래 취소')),
    (48, '신한카드', 'Always On', '신용', None, None, None),
    (49, '신한카드', 'Deep On 체크', '체크', None, None, None),
    (50, '우리카드', '그린카드(전국형)', '유형 미확인', None, '유형 미확인', None),
    (51, '우리카드', '카드의정석 UniMile CHECK', '체크', None, None, None),
    (52, '신한카드', 'Air SKYPASS 법인카드', '법인', None, '법인카드', None),
    (53, '삼성카드', '삼성 스카이패스 법인카드', '법인', None, '법인카드', None),
    (54, '다날', '배터리카드', '선불', None, '선불카드', None),
    (55, '코나', '코나 럭키더블', '선불', None, '선불카드', None),
    (56, 'OK캐쉬백', 'OK카드', '선불', None, '선불카드', None),
    (57, '모빌', '모빌카드', '선불', None, '선불카드', None),
    (58, '웰컴', '웰컴페이카드', '선불', None, '선불카드', None),
]

NO_VALET_TYPES = {'체크', '선불', '법인', '교통전용', '전용'}


def build():
    by_name = {h[1]: h for h in HOTELS}
    hotels = []
    for hid, name, region, district, addr, fee, ref in HOTELS:
        hotels.append(dict(id=hid, name=name, region=region, district=district,
                           address=addr, fee=fee, app_ref=ref, offers=[]))
    hindex = {h['id']: h for h in hotels}
    cards_out = []
    problems = []

    for c in CARDS:
        ids = []
        seen = set()
        for nm in c['hotels']:
            if nm in DROP_NAMES:
                continue
            hid = NAME_ALIAS.get(nm) or (by_name.get(nm) or (None,))[0]
            if hid is None:
                problems.append('%s: 모르는 호텔 이름 %r' % (c['id'], nm))
                continue
            if hid in seen:
                problems.append('%s: 중복 호텔 %r' % (c['id'], nm))
                continue
            seen.add(hid)
            ids.append(hid)
            # '르메르디앙 & 목시 서울 명동'처럼 두 호텔을 묶어 적은 이름은 두 곳 모두에 붙인다
            if '목시' in nm:
                for extra in ('s-moxy', 's-lemeridien'):
                    if extra not in seen:
                        seen.add(extra)
                        ids.append(extra)
        card = {k: c[k] for k in ('id', 'issuer', 'name', 'network', 'tier', 'limit_label', 'limit_n',
                                  'prev_label', 'prev_n', 'hours_label', 'hours_n', 'note',
                                  'airport', 'url', 'basis', 'complete')}
        card['official_url'] = card.pop('url')
        card['coverage_complete'] = card.pop('complete')
        card['hotel_count'] = len(ids)
        cards_out.append(card)

        cond = c.get('cond') or {}
        hours = c.get('hours') or {}
        limit = c.get('limit') or {}
        cond_by_id = {}
        for nm, spec in cond.items():
            hid = NAME_ALIAS.get(nm) or (by_name.get(nm) or (None,))[0]
            if hid is None:
                problems.append('%s: 조건의 호텔 이름 %r' % (c['id'], nm))
                continue
            cond_by_id[hid] = spec
        hours_by_id = {}
        for nm, spec in hours.items():
            hid = NAME_ALIAS.get(nm) or (by_name.get(nm) or (None,))[0]
            if hid is None:
                problems.append('%s: 주차시간의 호텔 이름 %r' % (c['id'], nm))
                continue
            hours_by_id[hid] = spec
        limit_by_id = {}
        for nm, spec in limit.items():
            hid = NAME_ALIAS.get(nm) or (by_name.get(nm) or (None,))[0]
            if hid is None:
                problems.append('%s: 횟수의 호텔 이름 %r' % (c['id'], nm))
                continue
            limit_by_id[hid] = spec

        for hid in ids:
            typ, amount = cond_by_id.get(hid, ('none', 0))
            hl, hn = hours_by_id.get(hid, (c['hours_label'], c['hours_n']))
            ll, ln = limit_by_id.get(hid, (c['limit_label'], c['limit_n']))
            hindex[hid]['offers'].append({
                'card': c['id'],
                'receipt_type': typ,
                'receipt_min': amount,
                'receipt_req': label_of(typ, amount),
                'parking_hours': hl, 'hours_n': hn,
                'monthly_limit': ll, 'limit_n': ln,
                'prev_spend': c['prev_label'], 'prev_n': c['prev_n'],
                'official_url': c['url']})

    for h in hotels:
        h['app_hotel_ref'] = {'tab': h['app_ref'][0], 'id': h['app_ref'][1]} if h['app_ref'] else None
        h.pop('app_ref')
        h['card_count'] = len(h['offers'])
        # 금액 조건이 없는 카드가 하나라도 있으면 '금액 조건 없음' 필터에 잡힌다
        h['no_min'] = any(o['receipt_type'] == 'none' for o in h['offers'])
        h['no_receipt'] = h['no_min']

    # 보유 카드 58장 — 발렛 연결
    card_ids = {c['id'] for c in cards_out}
    my_cards = []
    for seq, issuer, name, typ, vcard, note, memo in MY_CARDS:
        if vcard and vcard not in card_ids:
            problems.append('myCards %d: 모르는 발렛 카드 id %r' % (seq, vcard))
        valet = 'eligible' if vcard else ('none' if typ in NO_VALET_TYPES else 'unknown')
        if note and '발렛 없음' in note:
            valet = 'none'
        item = dict(seq=seq, issuer=issuer, name=name, type=typ, valet=valet, valet_card=vcard,
                    status_note=note, benefit=(memo or {}).get('benefit'),
                    prev_spend=(memo or {}).get('prev'), limit=(memo or {}).get('limit'),
                    exclude=(memo or {}).get('exclude'))
        my_cards.append(item)

    data = dict(schema='teambusan.valet.v1', generated=BASIS_DATE, basis=BASIS,
                region_order=REGION_ORDER, cards=cards_out, hotels=hotels, myCards=my_cards,
                counts=dict(hotels=len(hotels), cards=len(cards_out),
                            offers=sum(len(h['offers']) for h in hotels),
                            with_card=len([h for h in hotels if h['offers']]),
                            app_linked=len([h for h in hotels if h['app_hotel_ref']]),
                            my_cards=len(my_cards),
                            my_cards_valet=len([c for c in my_cards if c['valet'] == 'eligible']),
                            no_min=len([h for h in hotels if h['no_min']])))
    return data, problems


def main():
    cmds = set(sys.argv[1:]) or {'build'}
    data, problems = build()
    if problems:
        print('문제 %d건' % len(problems))
        for p in problems:
            print('  - ' + p)
    if 'check' in cmds or problems:
        if not problems:
            print('이름·참조 정합성 OK — 호텔 %d곳 · 카드 %d종 · 항목 %d개'
                  % (data['counts']['hotels'], data['counts']['cards'], data['counts']['offers']))
        if problems:
            return 1
    if 'build' in cmds:
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n')
        print('저장 %s (%.1f KB)' % (os.path.relpath(OUT, ROOT), os.path.getsize(OUT) / 1024.0))
        print(data['counts'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
