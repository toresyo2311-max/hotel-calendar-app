#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🅿️ 발렛 탭 데이터 생성기 — `data/app/valet.json`.

국내 특급호텔의 호텔 발렛(발레파킹) 현장 조건과, 카드사가 공식 안내장에서
무료 발렛 대상 호텔로 밝힌 목록을 한 파일로 구조화한다.

  · 카드 조건의 1차 출처는 카드사 공식 안내(공지·상품설명서 PDF).
  · 호텔 목록이 공식 안내에서 확인된 카드는 basis='official',
    카드사 안내장을 2차 자료에서 확인한 카드는 basis='secondary' 로 남긴다.
  · 호텔 목록이 일부만 확인된 카드는 coverage_complete=False 로 두고,
    화면에서는 그 카드로 "불가"라고 단정하지 않고 "확인 필요"로 보여 준다.

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
BASIS = ('카드사 공식 발레파킹 안내(2026-01-01~12-31 기준, 일부 2025-12-22~2026-12-31)와 '
         '호텔 공지 확인값. 카드사·호텔 사정으로 바뀔 수 있어 방문 전 확인이 필요합니다. '
         '더 플라자 호텔 서울은 2026-09-30 영업을 종료해 목록에서 뺐습니다.')

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
    # ── 부산 ──────────────────────────────────────────────
    ('b-paradise', '파라다이스 호텔 부산', '부산', '해운대구', '해운대해변로 296', '25,000원', ('lux', 'h01')),
    ('b-park-hyatt', '파크 하얏트 부산', '부산', '해운대구', '마린시티1로 51', '32,000원', ('lux', 'h02')),
    ('b-westin-chosun', '웨스틴 조선 부산', '부산', '해운대구', '동백로 67', '30,000원(1박)', ('marriott', 'k06')),
    ('b-grand-chosun', '그랜드 조선 부산', '부산', '해운대구', None, None, None),
    ('b-lotte', '롯데호텔 부산', '부산', '부산진구', '가야대로 772', None, None),
    ('b-novotel', '노보텔 앰배서더 부산 해운대', '부산', '해운대구', None, None, None),
    ('b-signiel', '시그니엘 부산', '부산', '해운대구', None, None, ('lux', 'h03')),
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

# ────────────────────────────────────────────────────────────────
# 카드 — 공식 안내 기준
#   limit/prev/hours 는 카드 공통 조건, receipt 는 기본 현장 조건.
#   overrides[호텔 id] 로 호텔별 예외(최소 결제액·주차시간·월 횟수)를 덮어쓴다.
# ────────────────────────────────────────────────────────────────
SHINHAN_URL = 'https://www.shinhancard.com/pconts/html/benefit/event/1231045_2239.html'
SAMSUNG_AMEX = 'https://static11.samsungcard.com/wcms/personal/files/24_AMEX_E_004.pdf'
SAMSUNG_VISA_I = 'https://static11.samsungcard.com/wcms/personal/files/VISA_I_001.pdf'
SAMSUNG_MASTER_W = 'https://static11.samsungcard.com/wcms/personal/files/MASTER_W_002.pdf'
HYUNDAI_RED = 'https://www.hyundaicard.com/TRDM/cms_content/ycag12208.html'
HYUNDAI_GREEN2 = 'https://www.hyundaicard.com/ct_pbb/html/amexMR_hotelValet_gr_ed2.html'
HYUNDAI_PLAT = ('https://www.hyundaicard.com/cpb/ev/CPBEV0101_06.hc?bnftWebEvntCd=GGE383')
LOTTE_VISA_PLAT = 'https://image.lottecard.co.kr/webapp/file/VISA_PLATINUM_04_260514.pdf'
LOTTE_AMEX_PE = 'https://image.lottecard.co.kr/webapp/mobile/images/card/detail/13_33.AMEX_PLATINUM_ELITE_03_260514OL.pdf'
LOTTE_AMEX_PLAT = 'http://image.lottecard.co.kr/webapp/file/AMERICAN_EXPRESS_PLATINUM_02_260514.pdf'
LOTTE_UNIONPAY = 'https://image.lottecard.co.kr/UploadFiles/cardProvisionPath/2017-B00022_20260519_10020.pdf'
KB_GAON = 'https://card.kbcard.com/CRD/DVIEW/HCAMCXPRICAC0076?cooperationcode=09152&mainCC=a'
HANA_JADE = 'https://www.hanacard.co.kr/OPI42000000D.web?CD_PD_SEQ=17870'
BC_MASTER = 'https://www.bccard.com/app/card/ContentsLinkActn.do?pgm_id=vip0024'
NH_GUIDE = 'https://card.nonghyup.com/file/ebank/form/pdf/serviceGuide_BCPlatinum_221101.pdf'
WOORI_INF = 'https://cardandkey.com/card/woori-all-infinite/'

SHINHAN_LIST = [
    '메이필드 호텔 서울', '스위스 그랜드 호텔', '서울 가든 호텔', '호텔 나루 서울 엠갤러리',
    '페어몬트 앰배서더 서울', '콘래드 서울', '메리어트 이그제큐티브 아파트먼트 서울',
    '코트야드 바이 메리어트 서울 타임스퀘어', 'JW 메리어트 동대문 스퀘어 서울', '포시즌스 호텔 서울',
    '코리아나 호텔', '롯데호텔 서울', '반얀트리 클럽 앤 스파 서울', '노보텔 앰배서더 서울 동대문',
    '레스케이프 호텔', '서울신라호텔', '앰배서더 서울 풀만', '그랜드 하얏트 서울',
    '몬드리안 서울 이태원', '서울 드래곤 시티', 'JW 메리어트 호텔 서울', '그랜드 인터컨티넨탈 서울 파르나스',
    '안다즈 서울 강남', '파크 하얏트 서울', '노보텔 앰배서더 서울 강남',
    'AC 호텔 바이 메리어트 서울 강남', '오크우드 프리미어 코엑스 센터', '글래드 강남 코엑스 센터',
    '그랜드 워커힐 서울', '비스타 워커힐 서울', '롯데호텔 월드', '시그니엘 서울',
    '그랜드 하얏트 인천', '그랜드 머큐어 앰배서더 창원', '대구 메리어트 호텔', '호텔 인터불고 대구',
    '힐튼 경주', '롯데호텔 울산', '롯데호텔 부산', '파라다이스 호텔 부산', '웨스틴 조선 부산',
    '파크 하얏트 부산', '롯데호텔 제주',
]

CARDS = [
    dict(id='sh-visa-infinite', issuer='신한카드', name='신한카드 The ACE · The Premier',
         network='Visa Infinite', tier='인피니트', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='실물 카드 제시 · 호텔 객실·식음(연회장 제외) 이용 본인 한정',
         url=SHINHAN_URL, basis='official', complete=True, hotels=SHINHAN_LIST,
         overrides={'s-koreana': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-banyan': {'hours_label': '1일 3시간', 'hours_n': 3}}),
    dict(id='sh-visa-signature', issuer='신한카드', name='신한카드 The BEST · The BEST+',
         network='Visa Signature', tier='시그니처', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='The BEST+·The ACE BLUE LABEL은 호텔 통합 월 5회',
         url=SHINHAN_URL, basis='official', complete=True, hotels=SHINHAN_LIST,
         overrides={'s-koreana': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000}}),
    dict(id='sh-master-diamond', issuer='신한카드', name='신한카드 The BEST (Mastercard)',
         network='Mastercard Diamond', tier='다이아몬드', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='마스터카드 다이아몬드 계열 안내 기준',
         url='https://www.shinhancard.com/pconts/download/card/MO_26_00782_master_diamond_1_best.pdf',
         basis='official', complete=True,
         hotels=['JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '그랜드 워커힐 서울',
                 '그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문',
                 '더 플라자', '레스케이프 호텔', '메리어트 이그제큐티브 아파트먼트 서울', '코리아나 호텔',
                 '메이필드 호텔 서울', '몬드리안 서울 이태원', '비스타 워커힐 서울', '서울 가든 호텔',
                 '서울 드래곤 시티', '서울신라호텔', '스위스 그랜드 호텔', '안다즈 서울 강남',
                 '앰배서더 서울 풀만', '오크우드 프리미어 코엑스 센터', '콘래드 서울',
                 '그랜드 머큐어 앰배서더 창원', '대구 메리어트 호텔', '파라다이스 호텔 부산',
                 '그랜드 조선 부산']),
    dict(id='sam-amex-platinum', issuer='삼성카드', name='삼성 American Express PLATINUM ELITE',
         network='Amex Platinum Elite', tier='플래티넘 엘리트', limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='공항 발렛과 통합 월 5회',
         url=SAMSUNG_AMEX, basis='official', complete=True,
         hotels=['그랜드 워커힐 서울', '그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남',
                 '노보텔 앰배서더 서울 동대문', '더 플라자', '르메르디앙 서울 명동', '메이필드 호텔 서울',
                 '반얀트리 클럽 앤 스파 서울', '서울 가든 호텔', '비스타 워커힐 서울', '서울 드래곤 시티',
                 '서울신라호텔', '아셈타워', '앰배서더 서울 풀만', '코트야드 바이 메리어트 서울 타임스퀘어',
                 '힐튼 가든 인 서울 강남', 'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울',
                 '그랜드 조선 부산', '대구 메리어트 호텔', '파크 하얏트 부산', '호텔 인터불고 대구'],
         overrides={'s-jw-seoul': {'receipt': '식음 3만원↑', 'receipt_min': 30000}}),
    dict(id='sam-visa-infinite', issuer='삼성카드', name='삼성 THE O (Visa Infinite)',
         network='Visa Infinite', tier='인피니트', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='3개월 평균 30만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='호텔별 월 5회 · 3개월 월평균 이용금액 기준',
         url=SAMSUNG_VISA_I, basis='official', complete=True,
         hotels=['그랜드 워커힐 서울', '그랜드 하얏트 서울', '글래드 강남 코엑스 센터',
                 '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문', '더 플라자',
                 '메리어트 이그제큐티브 아파트먼트 서울', '반얀트리 클럽 앤 스파 서울', '서울 가든 호텔',
                 '비스타 워커힐 서울', '서울 드래곤 시티', '서울신라호텔', '스위스 그랜드 호텔',
                 '앰배서더 서울 풀만', '오크우드 프리미어 코엑스 센터', '코리아나 호텔',
                 '코트야드 바이 메리어트 서울 보타닉 파크', '코트야드 바이 메리어트 서울 타임스퀘어',
                 '콘래드 서울', '파크 하얏트 서울', '호텔 리베라 청담', 'JW 메리어트 동대문 스퀘어 서울',
                 'JW 메리어트 호텔 서울', '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천',
                 '대구 메리어트 호텔', '웨스틴 조선 부산', '파크 하얏트 부산', '힐튼 경주',
                 '호텔 인터불고 대구'],
         overrides={'s-jw-seoul': {'receipt': '식음 3만원↑', 'receipt_min': 30000},
                    's-koreana': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-park-hyatt': {'receipt': '식음 2만원↑', 'receipt_min': 20000}}),
    dict(id='sam-master-world', issuer='삼성카드', name='삼성 THE O V2 (Mastercard World)',
         network='Mastercard World', tier='월드', limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='인천공항 발렛과 통합 월 5회',
         url=SAMSUNG_MASTER_W, basis='official', complete=True,
         hotels=['그랜드 워커힐 서울', '그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남',
                 '노보텔 앰배서더 서울 동대문', '더 플라자', '메리어트 이그제큐티브 아파트먼트 서울',
                 '메이필드 호텔 서울', '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울', '서울 가든 호텔',
                 '서울 드래곤 시티', '서울신라호텔', '스위스 그랜드 호텔', '앰배서더 서울 풀만',
                 '오크우드 프리미어 코엑스 센터', '코트야드 바이 메리어트 서울 타임스퀘어', '콘래드 서울',
                 '파크 하얏트 서울', '코트야드 바이 메리어트 서울 보타닉 파크', 'JW 메리어트 호텔 서울',
                 '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천', '파크 하얏트 부산', '힐튼 경주',
                 '호텔 인터불고 대구'],
         overrides={'s-jw-seoul': {'receipt': '식음 3만원↑', 'receipt_min': 30000},
                    's-park-hyatt': {'receipt': '식음 2만원↑', 'receipt_min': 20000}}),
    dict(id='hy-the-red', issuer='현대카드', name='현대카드 the Red',
         network='현대카드 전용', tier='the Red', limit_label='월 5회(호텔별)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='실물 카드 필수(앱·가상카드 불가) · 본인 탑승 차량',
         url=HYUNDAI_RED, basis='official', complete=True,
         hotels=['그랜드 워커힐 서울', '그랜드 하얏트 서울', '더 플라자', '밀레니엄 힐튼 서울',
                 '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울', '소피텔 앰배서더 서울',
                 '스위스 그랜드 호텔', '안다즈 서울 강남', '임피리얼 팰리스 서울', '콘래드 서울',
                 '포시즌스 호텔 서울', '서울신라호텔', 'JW 메리어트 호텔 서울', '앰배서더 서울 풀만',
                 '메이필드 호텔 서울', '노보텔 앰배서더 서울 강남', '파라다이스시티',
                 '그랜드 조선 부산', '파라다이스 호텔 부산', '파크 하얏트 부산', '호텔 인터불고 대구',
                 '대구 메리어트 호텔', '대구 그랜드 호텔', '호텔 오노마 대전', '롯데호텔 울산',
                 '롯데호텔 제주'],
         overrides={'s-jw-seoul': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000}}),
    dict(id='hy-amex-green', issuer='현대카드', name='현대 American Express Green Edition2',
         network='Amex Green', tier='그린', limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인·가족 합산 · 공항 발렛과 통합 월 5회',
         url=HYUNDAI_GREEN2, basis='official', complete=True,
         hotels=['JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '그랜드 워커힐 서울',
                 '그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문',
                 '페어몬트 앰배서더 서울', '호텔 나루 서울 엠갤러리', '르메르디앙 서울 명동',
                 '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔 서울', '몬드리안 서울 이태원',
                 '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울', '서울 가든 호텔', '서울 드래곤 시티',
                 '서울신라호텔', '아셈타워', '안다즈 서울 강남', '앰배서더 서울 풀만',
                 '코트야드 바이 메리어트 서울 타임스퀘어', '콘래드 서울', '파크 하얏트 서울',
                 '포시즌스 호텔 서울', '힐튼 가든 인 서울 강남', '소피텔 앰배서더 서울',
                 '그랜드 하얏트 인천', '소노캄 고양', '대구 메리어트 호텔', '호텔 인터불고 대구',
                 '호텔 오노마 대전', '힐튼 경주', '그랜드 조선 부산', '파크 하얏트 부산',
                 '소노캄 여수', '그랜드 조선 제주'],
         overrides={'s-jw-seoul': {'receipt': '식음 5만원↑', 'receipt_min': 50000},
                    's-mondrian': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-four-seasons': {'receipt': '식음 3만원↑', 'receipt_min': 30000},
                    's-park-hyatt': {'receipt': '식음 2만원↑', 'receipt_min': 20000},
                    's-hilton-garden': {'hours_label': '1일 4시간', 'hours_n': 4}}),
    dict(id='hy-visa-plat', issuer='현대카드', name='현대카드 M2·M3 Platinum (Visa)',
         network='Visa Platinum', tier='플래티넘', limit_label='월 3회(대상점별)', limit_n=3,
         prev_label='전월 30만/50만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인+가족 합산 · 카드 등급에 따라 전월 실적 기준이 다름',
         url=HYUNDAI_PLAT, basis='official', complete=True,
         hotels=['JW 메리어트 동대문 스퀘어 서울', '그랜드 워커힐 서울', '그랜드 하얏트 서울',
                 '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문', '더 플라자',
                 '메리어트 이그제큐티브 아파트먼트 서울', '반얀트리 클럽 앤 스파 서울',
                 '비스타 워커힐 서울', '스위스 그랜드 호텔', '앰배서더 서울 풀만', '호텔 나루 서울 엠갤러리',
                 '소피텔 앰배서더 서울', '코리아나 호텔', '글래드 강남 코엑스 센터',
                 'AC 호텔 바이 메리어트 서울 강남', '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천',
                 '대구 메리어트 호텔', '파크 하얏트 부산', '호텔 인터불고 대구', '힐튼 경주'],
         overrides={'s-jw-seoul': {'limit_label': '월 1회', 'limit_n': 1}}),
    dict(id='hy-master-plat', issuer='현대카드', name='현대카드 M2·M3 Platinum (Mastercard)',
         network='Mastercard Platinum', tier='플래티넘', limit_label='월 3회(대상점별)', limit_n=3,
         prev_label='전월 30만/50만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인+가족 합산 · 카드 등급에 따라 전월 실적 기준이 다름',
         url=HYUNDAI_PLAT, basis='official', complete=True,
         hotels=['JW 메리어트 호텔 서울', '그랜드 워커힐 서울', '그랜드 하얏트 서울',
                 '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문', '더 플라자',
                 '레스케이프 호텔', '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔 서울',
                 '몬드리안 서울 이태원', '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울',
                 '서울신라호텔', '스위스 그랜드 호텔', '파크 하얏트 서울', '그랜드 머큐어 앰배서더 창원',
                 '그랜드 하얏트 인천', '대구 메리어트 호텔', '파크 하얏트 부산', '파라다이스 호텔 부산'],
         overrides={'s-jw-seoul': {'limit_label': '월 1회', 'limit_n': 1}}),
    dict(id='hy-unionpay-plat', issuer='현대카드', name='현대카드 M2·M3 Platinum (UnionPay)',
         network='UnionPay Platinum', tier='플래티넘', limit_label='월 3회(대상점별)', limit_n=3,
         prev_label='전월 30만/50만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인+가족 합산',
         url=HYUNDAI_PLAT, basis='official', complete=True,
         hotels=['JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '그랜드 워커힐 서울',
                 '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문', '더 플라자',
                 '레스케이프 호텔', '르메르디앙 서울 명동', '목시 서울 명동',
                 '메리어트 이그제큐티브 아파트먼트 서울', '반얀트리 클럽 앤 스파 서울',
                 '비스타 워커힐 서울', '서울신라호텔', '스위스 그랜드 호텔', '소피텔 앰배서더 서울',
                 '그랜드 머큐어 앰배서더 창원', '대구 메리어트 호텔', '웨스틴 조선 부산',
                 '파크 하얏트 부산'],
         overrides={'s-jw-seoul': {'limit_label': '월 1회', 'limit_n': 1}}),
    dict(id='lotte-visa-plat', issuer='롯데카드', name='롯데카드 디지로카 Monaco (Visa Platinum)',
         network='Visa Platinum', tier='플래티넘', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인+가족 합산 · 실물 카드 제시',
         url=LOTTE_VISA_PLAT, basis='official', complete=True,
         hotels=['그랜드 워커힐 서울', '그랜드 하얏트 서울', '글래드 강남 코엑스 센터',
                 '노보텔 앰배서더 서울 강남', '호텔 나루 서울 엠갤러리', '노보텔 앰배서더 서울 동대문',
                 '더 플라자', '몬드리안 서울 이태원', '레스케이프 호텔', '르메르디앙 서울 명동',
                 '목시 서울 명동', '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔 서울',
                 '반얀트리 클럽 앤 스파 서울', '서울 가든 호텔', 'AC 호텔 바이 메리어트 서울 강남',
                 '비스타 워커힐 서울', '서울 드래곤 시티', '스위스 그랜드 호텔', '코리아나 호텔',
                 '오크우드 프리미어 코엑스 센터', '앰배서더 서울 풀만', '콘래드 서울',
                 'JW 메리어트 동대문 스퀘어 서울', '소피텔 앰배서더 서울', '안다즈 서울 강남',
                 '그랜드 조선 부산', '파크 하얏트 부산', '대구 메리어트 호텔', '호텔 인터불고 대구',
                 '그랜드 머큐어 앰배서더 창원', '그랜드 하얏트 인천', '인스파이어 엔터테인먼트 리조트',
                 '소노캄 고양', '소노캄 여수', '세인트존스 호텔'],
         overrides={'s-grand-hyatt': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    's-naru': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    's-mondrian': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-lescape': {'receipt': '식음 3만원↑', 'receipt_min': 30000},
                    's-koreana': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-jw-dongdaemun': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    's-oakwood': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    'b-grand-chosun': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    'w-saintjohns': {'receipt': '당일 영수증 필수', 'receipt_min': 1}}),
    dict(id='lotte-amex-pe', issuer='롯데카드', name='롯데백화점 Flex (Amex Platinum Elite)',
         network='Amex Platinum Elite', tier='플래티넘 엘리트', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인+가족 합산',
         url=LOTTE_AMEX_PE, basis='official', complete=True,
         hotels=['서울신라호텔', '메리어트 이그제큐티브 아파트먼트 서울', '그랜드 하얏트 서울',
                 '비스타 워커힐 서울', '그랜드 워커힐 서울', '반얀트리 클럽 앤 스파 서울',
                 '르메르디앙 서울 명동', 'JW 메리어트 호텔 서울', '노보텔 앰배서더 서울 강남',
                 '메이필드 호텔 서울', '힐튼 가든 인 서울 강남', 'AC 호텔 바이 메리어트 서울 강남',
                 '앰배서더 서울 풀만', '안다즈 서울 강남', '서울 가든 호텔', '몬드리안 서울 이태원',
                 '호텔 나루 서울 엠갤러리', '글래드 여의도', 'JW 메리어트 동대문 스퀘어 서울',
                 '서울 드래곤 시티', '노보텔 앰배서더 서울 동대문', '파크 하얏트 서울', '더 플라자',
                 '아셈타워', '포시즌스 호텔 서울', '코트야드 바이 메리어트 서울 타임스퀘어',
                 '호텔 인터불고 대구', '파크 하얏트 부산', '소노캄 고양', '소노캄 여수', '힐튼 경주',
                 '그랜드 하얏트 인천', '호텔 오노마 대전', '대구 메리어트 호텔'],
         overrides={'s-jw-seoul': {'receipt': '식음 5만원↑', 'receipt_min': 50000},
                    's-mondrian': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-park-hyatt': {'receipt': '식음 2만원↑', 'receipt_min': 20000},
                    's-four-seasons': {'receipt': '식음 3만원↑', 'receipt_min': 30000},
                    's-hilton-garden': {'hours_label': '1일 4시간', 'hours_n': 4},
                    's-ac-gangnam': {'hours_label': '1일 4시간', 'hours_n': 4}}),
    dict(id='lotte-amex-plat', issuer='롯데카드', name='롯데 샤롯데 플래티넘 스타 (Amex Platinum)',
         network='Amex Platinum', tier='플래티넘', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='JW 메리어트 호텔 서울은 월 1회',
         url=LOTTE_AMEX_PLAT, basis='official', complete=True,
         hotels=['서울신라호텔', '메리어트 이그제큐티브 아파트먼트 서울', '그랜드 하얏트 서울',
                 '비스타 워커힐 서울', '그랜드 워커힐 서울', '반얀트리 클럽 앤 스파 서울',
                 '르메르디앙 서울 명동', 'JW 메리어트 호텔 서울', '노보텔 앰배서더 서울 강남',
                 '메이필드 호텔 서울', '힐튼 가든 인 서울 강남', 'AC 호텔 바이 메리어트 서울 강남',
                 '앰배서더 서울 풀만', '안다즈 서울 강남', '서울 가든 호텔', '몬드리안 서울 이태원',
                 '호텔 나루 서울 엠갤러리', '글래드 여의도', 'JW 메리어트 동대문 스퀘어 서울',
                 '서울 드래곤 시티', '노보텔 앰배서더 서울 동대문', '파크 하얏트 서울',
                 '호텔 인터불고 대구', '파크 하얏트 부산', '소노캄 고양', '소노캄 여수', '힐튼 경주',
                 '그랜드 하얏트 인천', '호텔 오노마 대전'],
         overrides={'s-jw-seoul': {'receipt': '식음 5만원↑', 'receipt_min': 50000, 'limit_label': '월 1회', 'limit_n': 1},
                    's-mondrian': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-park-hyatt': {'receipt': '식음 2만원↑', 'receipt_min': 20000},
                    's-hilton-garden': {'hours_label': '1일 4시간', 'hours_n': 4},
                    's-ac-gangnam': {'hours_label': '1일 4시간', 'hours_n': 4}}),
    dict(id='lotte-unionpay-diamond', issuer='롯데카드', name='롯데 위버스카이 (UnionPay Diamond)',
         network='UnionPay Diamond', tier='다이아몬드', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 10만원', prev_n=100000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인+가족 합산',
         url=LOTTE_UNIONPAY, basis='official', complete=True,
         hotels=['그랜드 머큐어 앰배서더 서울 용산', '그랜드 워커힐 서울', '노보텔 스위트 앰배서더 서울 용산',
                 '노보텔 앰배서더 서울 용산', '그랜드 하얏트 서울', '노보텔 앰배서더 서울 동대문',
                 '더 플라자', '레스케이프 호텔', '소피텔 앰배서더 서울',
                 '메리어트 이그제큐티브 아파트먼트 서울', '글래드 강남 코엑스 센터',
                 '몬드리안 서울 이태원', '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울',
                 '호텔 나루 서울 엠갤러리', '앰배서더 서울 풀만', '스위스 그랜드 호텔', '코리아나 호텔',
                 '오크우드 프리미어 코엑스 센터', '이비스 스타일 앰배서더 서울 용산',
                 '코트야드 바이 메리어트 서울 타임스퀘어', '콘래드 서울', '노보텔 앰배서더 서울 강남',
                 'JW 메리어트 동대문 스퀘어 서울', '파크 하얏트 서울', '웨스틴 조선 부산',
                 '호텔 오노마 대전', '대구 메리어트 호텔', 'JW 메리어트 제주 리조트 & 스파'],
         overrides={'s-lescape': {'receipt': '식음 3만원↑', 'receipt_min': 30000},
                    's-mondrian': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-koreana': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-oakwood': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    's-naru': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    's-jw-dongdaemun': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    's-park-hyatt': {'receipt': '식음 2만원↑', 'receipt_min': 20000},
                    's-grand-hyatt': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    'b-westin-chosun': {'receipt': '당일 영수증 필수', 'receipt_min': 1}}),
    dict(id='hy-amex-platinum', issuer='현대카드', name='American Express The Platinum Card (현대)',
         network='Amex Platinum', tier='플래티넘', limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인·가족 합산 · 공항 발렛과 통합 월 5회 · 실물 카드 제시',
         url='https://www.hyundaicard.com/ct_pbb/html/amexMR_hotelValet_pl.html',
         basis='official', complete=True,
         hotels=['JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '그랜드 워커힐 서울',
                 '그랜드 인터컨티넨탈 서울 파르나스', '그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남',
                 '노보텔 앰배서더 서울 동대문', '페어몬트 앰배서더 서울', '호텔 나루 서울 엠갤러리',
                 '르메르디앙 서울 명동', '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔 서울',
                 '몬드리안 서울 이태원', '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울',
                 '서울 가든 호텔', '서울 드래곤 시티', '서울신라호텔', '아셈타워', '안다즈 서울 강남',
                 '앰배서더 서울 풀만', '오크우드 프리미어 코엑스 센터',
                 '코트야드 바이 메리어트 서울 타임스퀘어', '콘래드 서울', '파크 하얏트 서울',
                 '포시즌스 호텔 서울', '힐튼 가든 인 서울 강남', '소피텔 앰배서더 서울',
                 '그랜드 하얏트 인천', '소노캄 고양', '대구 메리어트 호텔', '호텔 인터불고 대구',
                 '호텔 오노마 대전', '힐튼 경주', '그랜드 조선 부산', '웨스틴 조선 부산',
                 '파크 하얏트 부산', '소노캄 여수', '그랜드 조선 제주'],
         overrides={'s-jw-seoul': {'receipt': '식음 5만원↑', 'receipt_min': 50000},
                    's-mondrian': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-four-seasons': {'receipt': '식음 3만원↑', 'receipt_min': 30000},
                    's-park-hyatt': {'receipt': '식음 2만원↑', 'receipt_min': 20000},
                    's-hilton-garden': {'hours_label': '1일 4시간', 'hours_n': 4}}),
    dict(id='hy-the-green', issuer='현대카드', name='현대카드 the Green',
         network='Visa Signature', tier='그린', limit_label='월 5회(공항 통합)', limit_n=5,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='상품 페이지 기준 3곳 — 계열 공지로는 13곳(방문 전 확인)',
         url='https://www.hyundaicard.com/docfiles/resources/gpcc/mo/html_eng/MOCAR_TGE3.html',
         basis='official', complete=False,
         hotels=['그랜드 워커힐 서울', '비스타 워커힐 서울', '소피텔 앰배서더 서울']),
    dict(id='sh-classic-y', issuer='신한카드', name='신한카드 The CLASSIC-Y',
         network='Visa·Master·UnionPay Platinum', tier='플래티넘', limit_label='월 3회(호텔 통합)', limit_n=3,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 2~3시간', hours_n=3,
         receipt='객실·F&B 필수', note='브랜드(Visa·Master·UnionPay)별 대상 호텔이 달라 카드사 안내 확인 필요',
         url='https://www.shinhancard.com/pconts/download/card/MO_26_00802_upi_platinum_1_classics_bestt.pdf',
         basis='official', complete=False,
         hotels=['그랜드 하얏트 서울', '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문',
                 '르메르디앙 서울 명동', '목시 서울 명동', '몬드리안 서울 이태원',
                 '반얀트리 클럽 앤 스파 서울', '스위스 그랜드 호텔', '코리아나 호텔',
                 '코트야드 바이 메리어트 서울 타임스퀘어', '대구 메리어트 호텔']),
    dict(id='kb-visa-plat', issuer='KB국민카드', name='KB국민 플래티늄 (Visa)',
         network='Visa Platinum', tier='플래티넘', limit_label='월 3회(호텔별)', limit_n=3,
         prev_label='전월 30만원(가온)', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='본인+가족 합산 · 실물 카드 제시 · 쿠폰형 플래티늄S는 실적 조건 없음',
         url='https://m.kbcard.com/BON/DVIEW/MBCMCXHIAWEC0060', basis='official', complete=True,
         hotels=['그랜드 워커힐 서울', '그랜드 하얏트 서울', '글래드 강남 코엑스 센터',
                 '노보텔 앰배서더 서울 강남', '노보텔 앰배서더 서울 동대문', '더 플라자',
                 '레스케이프 호텔', '르메르디앙 서울 명동', '목시 서울 명동',
                 '메리어트 이그제큐티브 아파트먼트 서울', '메이필드 호텔 서울', '몬드리안 서울 이태원',
                 '반얀트리 클럽 앤 스파 서울', '서울 가든 호텔', '비스타 워커힐 서울',
                 '서울 드래곤 시티', '소피텔 앰배서더 서울', '스위스 그랜드 호텔', '안다즈 서울 강남',
                 '앰배서더 서울 풀만', '오크우드 프리미어 코엑스 센터', '콘래드 서울',
                 '호텔 나루 서울 엠갤러리', '코리아나 호텔', 'AC 호텔 바이 메리어트 서울 강남',
                 'JW 메리어트 동대문 스퀘어 서울', '그랜드 머큐어 임피리얼 팰리스 서울 강남',
                 '그랜드 조선 부산', '파크 하얏트 부산', '그랜드 머큐어 앰배서더 창원',
                 '그랜드 하얏트 인천', '대구 메리어트 호텔', '세인트존스 호텔', '소노캄 고양',
                 '소노캄 여수', '인스파이어 엔터테인먼트 리조트', '호텔 오노마 대전',
                 '호텔 인터불고 대구', '힐튼 경주', 'JW 메리어트 제주 리조트 & 스파'],
         overrides={'s-lescape': {'receipt': '식음 3만원↑', 'receipt_min': 30000},
                    's-mondrian': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-koreana': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-imperial': {'receipt': '식음 2만원↑', 'receipt_min': 20000},
                    's-novotel-gangnam': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    's-mea': {'receipt': '당일 영수증 필수', 'receipt_min': 1},
                    's-oakwood': {'receipt': '당일 영수증 필수', 'receipt_min': 1}}),
    dict(id='hana-jade-first', issuer='하나카드', name='하나카드 JADE First Centum',
         network='Visa Infinite', tier='인피니트', limit_label='월 8회(호텔 통합)', limit_n=8,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간(일부 호텔)', hours_n=3,
         receipt='객실·F&B 필수', note='호텔 통합 월 8회 · 주차요금은 호텔별로 다름',
         url=HANA_JADE, basis='secondary', complete=True,
         hotels=['JW 메리어트 제주 리조트 & 스파', '그랜드 머큐어 앰배서더 서울 용산',
                 '그랜드 머큐어 앰배서더 창원', '그랜드 머큐어 앰배서더 서울 용산',
                 '노보텔 스위트 앰배서더 서울 용산', '노보텔 앰배서더 서울 강남',
                 '노보텔 앰배서더 서울 동대문', '노보텔 앰배서더 서울 용산', '몬드리안 서울 이태원',
                 '서울 드래곤 시티', '소피텔 앰배서더 서울', '앰배서더 서울 풀만',
                 '이비스 스타일 앰배서더 서울 용산', '호텔 나루 서울 엠갤러리', '콘래드 서울',
                 '힐튼 경주', 'AC 호텔 바이 메리어트 서울 강남', 'JW 메리어트 동대문 스퀘어 서울',
                 'JW 메리어트 호텔 서울', '대구 메리어트 호텔', '레스케이프 호텔',
                 '르메르디앙 서울 명동', '메리어트 이그제큐티브 아파트먼트 서울', '목시 서울 명동',
                 '웨스틴 조선 부산', '코트야드 바이 메리어트 서울 타임스퀘어', '호텔 오노마 대전',
                 '그랜드 하얏트 서울', '그랜드 하얏트 인천', '안다즈 서울 강남', '파크 하얏트 부산',
                 '파크 하얏트 서울', '서울신라호텔', '그랜드 워커힐 서울', '그랜드 조선 부산',
                 '글래드 강남 코엑스 센터', '메이필드 호텔 서울', '반얀트리 클럽 앤 스파 서울',
                 '비스타 워커힐 서울', '서울 가든 호텔', '세인트존스 호텔', '소노캄 고양',
                 '소노캄 여수', '스위스 그랜드 호텔', '오크우드 프리미어 코엑스 센터',
                 '인스파이어 엔터테인먼트 리조트', '코리아나 호텔', '포시즌스 호텔 서울',
                 '호텔 인터불고 대구']),
    dict(id='woori-all-infinite', issuer='우리카드', name='ALL 우리카드 Infinite',
         network='Visa Infinite', tier='인피니트', limit_label='월 3회(공항 통합)', limit_n=3,
         prev_label='전월 50만원', prev_n=500000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='공항 발렛과 통합 월 3회·연 10회',
         url=WOORI_INF, basis='secondary', complete=False,
         hotels=['JW 메리어트 제주 리조트 & 스파', '그랜드 머큐어 앰배서더 서울 용산',
                 '그랜드 머큐어 앰배서더 창원', '그랜드 머큐어 앰배서더 서울 용산',
                 '노보텔 스위트 앰배서더 서울 용산', '노보텔 앰배서더 서울 강남',
                 '노보텔 앰배서더 서울 동대문', '노보텔 앰배서더 서울 용산', '몬드리안 서울 이태원',
                 '서울 드래곤 시티', '소피텔 앰배서더 서울', '앰배서더 서울 풀만',
                 '이비스 스타일 앰배서더 서울 용산', '페어몬트 앰배서더 서울', '호텔 나루 서울 엠갤러리',
                 '콘래드 서울', '힐튼 경주', 'AC 호텔 바이 메리어트 서울 강남',
                 'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '대구 메리어트 호텔',
                 '레스케이프 호텔', '르메르디앙 서울 명동', '메리어트 이그제큐티브 아파트먼트 서울',
                 '목시 서울 명동', '코트야드 바이 메리어트 서울 타임스퀘어', '호텔 오노마 대전',
                 '그랜드 하얏트 서울', '그랜드 하얏트 인천', '파크 하얏트 부산', '파크 하얏트 서울',
                 '서울신라호텔', '그랜드 워커힐 서울', '그랜드 조선 부산', '글래드 강남 코엑스 센터',
                 '메이필드 호텔 서울', '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울',
                 '서울 가든 호텔', '세인트존스 호텔', '소노캄 고양', '소노캄 여수',
                 '스위스 그랜드 호텔', '오크우드 프리미어 코엑스 센터', '인스파이어 엔터테인먼트 리조트',
                 '코리아나 호텔', '호텔 인터불고 대구', '파라다이스 호텔 부산', '파라다이스시티'],
         overrides={'s-fairmont': {'receipt': '식음 3만원↑', 'receipt_min': 30000}}),
    dict(id='bc-diamond', issuer='BC카드', name='BC Diamond (회원사 공통)',
         network='Mastercard Diamond', tier='다이아몬드', limit_label='월 3회(공항 통합)', limit_n=3,
         prev_label='조건 없음', prev_n=0, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='국내 호텔·인천공항 통합 월 3회 · 전월 실적 조건 없음',
         url=BC_MASTER, basis='secondary', complete=True,
         hotels=['JW 메리어트 제주 리조트 & 스파', '그랜드 머큐어 앰배서더 서울 용산',
                 '그랜드 머큐어 앰배서더 창원', '그랜드 머큐어 임피리얼 팰리스 서울 강남',
                 '노보텔 스위트 앰배서더 서울 용산', '노보텔 앰배서더 서울 강남',
                 '노보텔 앰배서더 서울 동대문', '노보텔 앰배서더 서울 용산', '몬드리안 서울 이태원',
                 '서울 드래곤 시티', '앰배서더 서울 풀만', '이비스 스타일 앰배서더 서울 용산',
                 '호텔 나루 서울 엠갤러리', '콘래드 서울', '힐튼 경주', 'JW 메리어트 동대문 스퀘어 서울',
                 'JW 메리어트 호텔 서울', '대구 메리어트 호텔', '레스케이프 호텔',
                 '르메르디앙 서울 명동', '메리어트 이그제큐티브 아파트먼트 서울', '목시 서울 명동',
                 '코트야드 바이 메리어트 서울 타임스퀘어', '호텔 오노마 대전', '그랜드 하얏트 서울',
                 '그랜드 하얏트 인천', '파크 하얏트 부산', '파크 하얏트 서울', '서울신라호텔',
                 '그랜드 워커힐 서울', '그랜드 조선 부산', '글래드 강남 코엑스 센터',
                 '메이필드 호텔 서울', '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울',
                 '서울 가든 호텔', '세인트존스 호텔', '소노캄 고양', '소노캄 여수',
                 '스위스 그랜드 호텔', '오크우드 프리미어 코엑스 센터', '인스파이어 엔터테인먼트 리조트',
                 '코리아나 호텔', '호텔 인터불고 대구', '파라다이스 호텔 부산'],
         overrides={'s-jw-seoul': {'receipt': '식음 5만원↑', 'receipt_min': 50000},
                    's-mondrian': {'receipt': '식음 2.5만원↑', 'receipt_min': 25000},
                    's-millennium-hilton': {'receipt': '식음 2만원↑', 'receipt_min': 20000}}),
    dict(id='nh-wi-terra', issuer='NH농협카드', name='NH 위 테라카드',
         network='Visa Signature', tier='시그니처', limit_label='월 5회(호텔 통합)', limit_n=5,
         prev_label='전월 30만원', prev_n=300000, hours_label='1일 3시간', hours_n=3,
         receipt='객실·F&B 필수', note='호텔 통합 일 1회·월 5회·연 10회',
         url=NH_GUIDE, basis='secondary', complete=True,
         hotels=['그랜드 머큐어 앰배서더 서울 용산', '그랜드 머큐어 앰배서더 창원',
                 '노보텔 스위트 앰배서더 서울 용산', '노보텔 앰배서더 서울 강남',
                 '노보텔 앰배서더 서울 동대문', '노보텔 앰배서더 서울 용산', '몬드리안 서울 이태원',
                 '서울 드래곤 시티', '소피텔 앰배서더 서울', '앰배서더 서울 풀만',
                 '이비스 스타일 앰배서더 서울 용산', '페어몬트 앰배서더 서울', '호텔 나루 서울 엠갤러리',
                 '콘래드 서울', '힐튼 경주', 'AC 호텔 바이 메리어트 서울 강남',
                 'JW 메리어트 동대문 스퀘어 서울', 'JW 메리어트 호텔 서울', '대구 메리어트 호텔',
                 '레스케이프 호텔', '메리어트 이그제큐티브 아파트먼트 서울', '웨스틴 조선 부산',
                 '코트야드 바이 메리어트 서울 타임스퀘어', '그랜드 하얏트 서울', '그랜드 하얏트 인천',
                 '안다즈 서울 강남', '파크 하얏트 부산', '파크 하얏트 서울', '서울신라호텔',
                 '그랜드 워커힐 서울', '그랜드 조선 부산', '글래드 강남 코엑스 센터',
                 '메이필드 호텔 서울', '반얀트리 클럽 앤 스파 서울', '비스타 워커힐 서울',
                 '서울 가든 호텔', '소노캄 고양', '소노캄 여수', '스위스 그랜드 호텔',
                 '인스파이어 엔터테인먼트 리조트', '코리아나 호텔', '포시즌스 호텔 서울',
                 '호텔 인터불고 대구'],
         overrides={'s-jw-seoul': {'receipt': '식음 5만원↑', 'receipt_min': 50000}}),
]

# 카드 목록에 없는 이름(더 플라자: 2026-09-30 영업 종료) — 데이터에서 제외한다
DROP_NAMES = {'더 플라자', '호텔 리베라 청담', '그랜드 머큐어 임피리얼 팰리스 서울 강남', '그랜드 머큐어 앰배서더 서울 용산'}
# 위 DROP 안에서 실제 호텔이 있는 이름은 살린다(임피리얼 = 별도 호텔로 수록)
KEEP_NAMES = {'그랜드 머큐어 앰배서더 서울 용산'}

NAME_ALIAS = {
    '임피리얼 팰리스 서울': 's-imperial',
    '그랜드 머큐어 임피리얼 팰리스 서울 강남': 's-imperial',
    '그랜드 머큐어 앰배서더 서울 용산': 's-gm-yongsan',
    '베스트 웨스턴 프리미어 서울가든호텔': 's-seoulgarden',
    '서울가든호텔': 's-seoulgarden',
    '그랜드 앰배서더 서울 풀만': 's-ambassador-pullman',
    '그랜드 앰배서더 서울': 's-ambassador-pullman',
    '호텔 신라': 's-shilla',
}

REGION_ORDER = ['서울', '부산', '제주', '인천', '경기', '강원', '경남', '경북', '대구', '대전', '울산', '전남']

# ────────────────────────────────────────────────────────────────
# 한진님 보유 카드 58장 — 원문 그대로 보존한다(임의 삭제·확정 금지).
#   (순번, 발급사, 카드명, 유형, 발렛 연결 카드 id 또는 None, 상태 메모)
#   valet 상태는 아래 세 가지로만 나눈다.
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
    (10, '신한카드', 'The CLASSIC-Y', '신용', 'sh-classic-y',
     '호텔 통합 월 3회 발렛 확인 — 브랜드(Visa·Master·UnionPay)별 대상 호텔이 달라 방문 전 카드사 안내 확인 필요.',
     dict(benefit='호텔 발렛 통합 월 3회 · 1일 2~3시간 무료주차', prev='전월 30만원',
          limit='월 3회(호텔 통합)', exclude='현금서비스·카드론·수수료·이자·거래 취소')),
    (11, 'IBK기업은행', 'K-패스', '신용', None, None, None),
    (12, '하나카드', 'L.PAY 하나 체크카드', '체크', None, None, None),
    (13, 'iM뱅크', '대구단디 체크카드', '체크', None, None, None),
    (14, '케이뱅크', 'ONE 체크카드(K-패스)', '체크', None, None, None),
    (15, 'KB국민카드', '아시아나 KB국민 플래티넘카드', '신용', 'kb-visa-plat',
     'KB국민 플래티늄(Visa) 프로그램으로 호텔별 월 3회 발렛 확인.',
     dict(benefit='호텔별 월 3회 발렛 · 1일 3시간 무료주차', prev='전월 30만원(가온 기준)',
          limit='월 3회(호텔별)', exclude='세금·공과금·등록금·상품권·관리비·수수료·이자')),
    (16, 'KB국민카드', 'KB 틴업 체크카드(티니핑)', '체크', None, None, None),
    (17, '우리카드', 'ALL 우리카드 Infinite', '신용', 'woori-all-infinite', None,
     dict(benefit='공항 발렛 + 호텔 발렛 통합 월 3회/연 10회 · 1일 3시간 무료주차',
          prev='전월 50만원', limit='월 3회·연 10회(공항 통합)', exclude='현금서비스·카드론·연회비·수수료·이자')),
    (18, 'BNK부산은행', '동백전 체크카드', '체크', None, None, None),
    (19, '삼성카드', 'iD SIMPLE', '신용', None, None, None),
    (20, 'NH농협카드', '올바른 NEW HAVE(원이) 체크카드', '체크', None, '중복 가능(27번 올바른 NEW HAVE와 유사)', None),
    (21, 'BC바로', 'GOAT BC 바로카드', '신용', None, None, None),
    (22, '롯데카드', 'SKYPASS 롯데카드', '신용', None,
     '호텔 발렛 확인 필요 — 롯데카드 공식 발렛 안내(디지로카 Monaco·샤롯데·위버스카이)에 이 상품명이 없어 임의 확정하지 않았다.', None),
    (23, 'IBK기업은행', '참! 좋은 kt wiz 카드', '체크', None, '중복 가능(01번 신용판과 카드명 같음)', None),
    (24, '현대카드', 'the Green', '신용', 'hy-the-green',
     '상품 페이지에 발렛 3곳(그랜드 워커힐·비스타 워커힐·소피텔) 명시 — 계열 공지로는 13곳이라 3곳 밖은 확인 필요.',
     dict(benefit='공항·호텔 발렛 통합 월 5회 · 1일 3시간 · 실물 카드 필수', prev='전월 50만원',
          limit='월 5회(공항·호텔 통합)', exclude='카드론·현금서비스·연회비·수수료·이자')),
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
    (42, '현대카드', 'American Express The Platinum Card', '신용', 'hy-amex-platinum', None,
     dict(benefit='공항·호텔 발렛 통합 월 5회 · 1일 3시간 · 실물 카드 필수', prev='전월 50만원',
          limit='월 5회(공항 통합)', exclude='카드론·현금서비스·연회비·수수료·이자')),
    (43, 'IBK기업은행', 'IBK 스카이패스카드 후보', '신용', None, '상품명 미확정(후보)', None),
    (44, '토스뱅크', '토스뱅크 체크카드', '체크', None, None, None),
    (45, '하나카드', '인터파크 투어 스카이패스 카드', '신용', None, None, None),
    (46, 'KB국민카드', 'Liiv Mate 카드', '신용', None, None, None),
    (47, '신한카드', '메리어트 본보이 더 베스트', '신용', 'sh-visa-signature',
     '신한 VISA 시그니처 계열 공통 안내(월 5회·호텔별) 적용.',
     dict(benefit='호텔별 월 5회 발렛 · 1일 3시간 무료주차', prev='전월 30만원',
          limit='월 5회(호텔별)', exclude='현금서비스·카드론·수수료·이자·거래 취소')),
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
        for nm in c['hotels']:
            if nm in DROP_NAMES and nm not in KEEP_NAMES:
                continue   # 더 플라자(2026-09-30 영업 종료) 등 — 화면에 넣지 않는다
            hid = NAME_ALIAS.get(nm)
            if hid is None:
                h = by_name.get(nm)
                hid = h[0] if h else None
            if hid is None:
                problems.append('%s: 모르는 호텔 이름 %r' % (c['id'], nm))
                continue
            if hid in ids:
                continue
            ids.append(hid)
        card = {k: c[k] for k in ('id', 'issuer', 'name', 'network', 'tier', 'limit_label', 'limit_n',
                                  'prev_label', 'prev_n', 'hours_label', 'hours_n', 'receipt', 'note',
                                  'url', 'basis', 'complete')}
        card['official_url'] = card.pop('url')
        card['coverage_complete'] = card.pop('complete')
        card['hotel_count'] = len(ids)
        cards_out.append(card)
        for hid in ids:
            h = hindex[hid]
            o = {'card': c['id'], 'receipt_req': c.get('receipt', '객실·F&B 필수'),
                 'receipt_min': 0, 'parking_hours': c['hours_label'], 'hours_n': c['hours_n'],
                 'monthly_limit': c['limit_label'], 'limit_n': c['limit_n'],
                 'prev_spend': c['prev_label'], 'prev_n': c['prev_n'],
                 'official_url': c['url']}
            ov = (c.get('overrides') or {}).get(hid) or {}
            for k, v in ov.items():
                if k == 'receipt':
                    o['receipt_req'] = v
                elif k == 'receipt_min':
                    o['receipt_min'] = v
                elif k == 'hours_label':
                    o['parking_hours'] = v
                elif k == 'hours_n':
                    o['hours_n'] = v
                elif k == 'limit_label':
                    o['monthly_limit'] = v
                elif k == 'limit_n':
                    o['limit_n'] = v
                elif k == 'prev_spend':
                    o['prev_spend'] = v
            h['offers'].append(o)

    for h in hotels:
        h['app_hotel_ref'] = {'tab': h['app_ref'][0], 'id': h['app_ref'][1]} if h['app_ref'] else None
        h.pop('app_ref')
        h['card_count'] = len(h['offers'])
        h['no_receipt'] = any(o['receipt_req'] == '객실·F&B 필수' and o['receipt_min'] == 0
                              for o in h['offers'])

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
                            my_cards_valet=len([c for c in my_cards if c['valet'] == 'eligible'])))
    return data, problems


def main():
    cmds = set(sys.argv[1:]) or {'build'}
    data, problems = build()
    if 'check' in cmds or problems:
        if problems:
            print('문제 %d건' % len(problems))
            for p in problems:
                print('  - ' + p)
        else:
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
