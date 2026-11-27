#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotel-calendar-app 통합 마스터 DB 도구.

데이터는 두 층으로 나뉜다.

  · `data/master_db.json` — 병합 도구(merge_*.py)가 고치는 **정본**. 호텔 811곳 × 365일 ·
    항공 47개 노선 · ⑥ 땡처리 상품을 한 파일에 담는다(바뀌지 않음).
  · `data/app/*.json` — 앱이 탭에 들어갈 때 `fetch` 로 받는 **탭별 배포본**(지연 로딩).
      tab1_vip.json(①) · tab2_accor.json(② 아코르 + SNU rows)
      tab4_marriott.json(③) · tab5_flights.json(④) · tab6_ttang.json(⑤)
  · `index.html` — 화면 코드 + 집계값만. `const DB` 에는 호텔이 없고(`hotels: []`),
    출처·기준일·갱신 이력·counts 만 둔다. `const FLIGHTS` / `const TTANG` 은 빈 골격이며
    실제 값은 tab5/tab6 JSON 이 채운다.

사용법 (저장소 루트에서):
    python3 tools/master_db.py extract   # data/app/*.json -> data/master_db.json (전체 재생성)
    python3 tools/master_db.py verify    # master_db.json == data/app/*.json + index.html 집계값
    python3 tools/master_db.py inject    # master_db.json -> data/app/*.json + index.html 집계값
    python3 tools/master_db.py parts     # master_db.json -> data/app/*.json 만 (index.html 그대로)
    python3 tools/master_db.py stats     # 수록 범위·건수만 출력
    python3 tools/master_db.py snapshot  # 오늘(KST) 스냅샷을 data/history/ 에 누적 + 에러가 알람

`inject` 는 index.html 과 data/app/*.json 을 백업한 뒤 `const DB` 집계 블록과 탭별 JSON 만
다시 쓰고, 나머지 바이트는 그대로 둔다. 바꾼 뒤 스스로 `verify` 를 다시 돌려 실패하면 되돌린다.
"""
import datetime
import decimal
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

# 탭별 지연 로딩 배포본 — index.html 은 이 파일들을 fetch 해서 화면을 그린다
APP_DIR = os.path.join(ROOT, 'data', 'app')
# 2026-11-22 — ② 중올플(china)과 ③ 아코르(domestic)를 「② 아코르」 한 탭으로 합쳤다.
#   배포본도 tab2_accor.json 하나이고, 옛 tab2_china.json·tab3_accor.json 은 쓰지 않는다.
PART_TABS = (('lux', 'tab1_vip.json'), ('accor', 'tab2_accor.json'),
             ('marriott', 'tab4_marriott.json'))
PART_FLIGHTS = 'tab5_flights.json'
PART_TTANG = 'tab6_ttang.json'
PART_MILEAGE = 'tab8_mileage.json'      # ⑥ 마일리지(부산) — 호텔 묶음이 아니라 별도 검사
PART_ORDER = [tab for tab, _ in PART_TABS]
PART_ADDRESS = dict(PART_TABS)

WINDOW_START = '2026-12-01'
WINDOW_END = '2027-11-30'

# 탭별 기대 호텔 수 — ① 호텔럭스 161곳 · ② 아코르 536곳 · ③ 메리어트 197곳 · 총 894곳
#   ② 아코르 = 중국(APC) 291(중올플 289 + 아코르 카드 가운데 중국 2) + 국내 30 + 동남아 196
#   + 기타 해외 19.  중올플 289 + 아코르 265 = 554 가운데 같은 호텔 18곳을 한 카드로 합친 수다.
#   ③ 메리어트 = 중국·홍콩·마카오 40 + 한국 40 + 일본 12. 2026-11-23에 한국 30곳(k11~k40)을 더했다
#   (5번 실측 marriott-kr-31 · SELAK 더 플라자 서울은 2026-09-30 영업 종료라 제외).
#   2026-11-23에 싱가포르 8곳(m41~m48)을 더해 100곳이 됐다 — 동남아 8(싱가포르).
#   2026-11-23에 싱가포르 중반 7곳(m49~m55)을 더해 107곳이 됐다 — 동남아 15(싱가포르).
#   2026-11-23에 싱가포르 마지막 7곳(m56~m62)을 더해 114곳이 됐다 — 동남아 22(싱가포르 완결).
#   2026-11-23에 오세아니아 1차 23곳(m63~m85)을 더해 137곳이 됐다 — 오세아니아 23(호주 12 · 멜버른 8 ·
#   골드코스트 3 · 피지 3 · 오클랜드 2 · 포트모르즈비 2 · 보라보라 2 · 괌 1 · 아피아 1).
#   2026-11-23에 일본 1차 30곳(m86~m115)을 더해 167곳이 됐다 — 일본 42(기존 12 + 신규 30: 교토 14 ·
#   고베 5 · 나고야 3 · 가고시마 2 · 가나자와 2 · 나가사키 2 · 가루이자와 1 · 구마모토 1).
#   2026-11-23에 일본 2차 30곳(m168~m197)을 더해 197곳이 됐다 — 일본 72(기존 42 + 도쿄 15 · 나고야 7 ·
#   나라 2 · 니세코 2 · 마쓰모토 2 · 닛코 1 · 루스쓰 1).
#   2026-11-23에 오세아니아 2차 14곳(m198~m211)을 더해 211곳이 됐다 — 오세아니아 37(기존 23 + 호주 14:
#   멜버른 3 · 브리즈번 5 · 골드코스트 1 · 시드니 5).
#   2026-11-23에 일본 3차 30곳(m212~m241) · 4차 29곳(m242~m270)을 더해 270곳이 됐다 — 일본 131(기존 72 +
#   오사카 24 · 삿포로 6 · 오키나와 5 · 요코하마 4 · 오카야마 3 · 이바라키 3 · 마쓰모토 2 · 시즈오카 2 ·
#   후쿠오카 2 · 히로시마 2 · 모리오카 1 · 센다이 1 · 야마구치 1 · 이키 1 · 하코네 1 · 하코다테 1).
#   이로써 5번이 실측한 일본 미수록 119곳(1차 30 + 2차 30 + 3차 30 + 4차 29)이 모두 반영됐다.
#   2026-11-24에 오세아니아 2차 잔여 10곳(m271~m280)과 대만 1차 4곳(m281~m284)을 더해 284곳이 됐다 —
#   오세아니아 47(1차 23 + 2차 24: 멜버른 11 · 브리즈번 5 · 시드니 6 · 골드코스트 4 · 퍼스 5 · 다윈 1 ·
#   애들레이드 1 · 캔버라 1 · 호바트 1 · 포트더글라스 1) · 대만 4(가오슝 3 · 린커우 1).
#   2026-11-24에 대만 2차 4곳(m285~m288)을 더해 288곳이 됐다 — 대만 8(가오슝 3 · 린커우 1 ·
#   신주 1 · 이란 1 · 자오시 1 · 타오위안 1). 누적 8곳 원본 가운데 앞 4곳은 m281~m284 로 이미
#   실려 있어 뒤 4곳만 더했다(중복 없음).
#   2026-11-24에 대만 3차 3곳(m289~m291)을 더해 291곳이 됐다 — 대만 11(가오슝 3 · 린커우 1 ·
#   신주 1 · 이란 1 · 자오시 1 · 타오위안 2 · 타이둥 1 · 타이베이 1). 누적 11곳 원본 가운데 앞 8곳은
#   m281~m288 로 이미 실려 있어 뒤 3곳만 더했다(중복 없음).
#   2026-11-24에 대만 4차 4곳(m292~m295)을 더해 295곳이 됐다 — 대만 15(가오슝 3 · 린커우 1 ·
#   신주 1 · 이란 1 · 자오시 1 · 타오위안 2 · 타이둥 1 · 타이베이 5). 누적 15곳 원본 가운데 앞 11곳은
#   m281~m291 로 이미 실려 있어 뒤 4곳만 더했다(중복 없음).
#   2026-11-24에 대만 5차 4곳(m296~m299)을 더해 299곳이 됐다 — 대만 19(가오슝 3 · 린커우 1 ·
#   신주 1 · 이란 1 · 자오시 1 · 타오위안 2 · 타이둥 1 · 타이베이 9). 누적 19곳 원본 가운데 신규 4곳이
#   파일 13~16번(중간)에 있어 위치로 자르지 않고 **기존 정본에 없는 코드 4개만** 골라 더했다(중복 0건).
#   2026-11-24에 대만 6차 4곳(m300~m303)을 더해 303곳이 됐다 — 대만 23(가오슝 3 · 린커우 1 ·
#   신주 1 · 이란 1 · 자오시 1 · 타오위안 2 · 타이둥 1 · 타이베이 13). 누적 23곳 원본 가운데 신규 4곳이
#   파일 17·18·20·23번에 흩어져 있어 위치로 자르지 않고 코드로 걸러 더했다(중복 0건).
#   이로써 ① 161 + ② 536 + ③ 303 = **통합 1,000곳**이 됐다.
#   2026-11-24에 대만 7차 4곳(m304~m307)을 더해 307곳이 됐다 — 대만 27(가오슝 3 · 린커우 1 ·
#   신주 1 · 이란 1 · 자오시 1 · 타오위안 2 · 타이둥 1 · 타이베이 15 · 타이중 2). 누적 27곳 원본
#   가운데 신규 4곳이 파일 24~27번(끝)에 있어 코드로 걸러 더했다(중복 0건).
#   이로써 ① 161 + ② 536 + ③ 307 = **통합 1,004곳**이 됐다.
#   2026-11-24에 대만 8차 1곳(m308)을 더해 308곳이 됐다 — 대만 28(가오슝 3 · 린커우 1 · 신주 1 ·
#   이란 1 · 자오시 1 · 타오위안 2 · 타이둥 1 · 타이베이 15 · 타이중 3). 누적 28곳 원본 가운데
#   신규는 파일 28번(끝) RMQTL 알로프트 타이중 1곳뿐이라 코드로 걸러 더했다(중복 0건).
#   이로써 ① 161 + ② 536 + ③ 308 = **통합 1,005곳**이 됐다.
#   2026-11-25 베트남 1차 4곳(CXRJW·CXRWI·VCASI·VCALM)을 더해 ③ 312 · **통합 1,009곳**.
#   2026-11-25 베트남 2차 4곳(CXRHT·NHASI·CXRNP·DADMR)을 더해 ③ 316 · 베트남 8 · **통합 1,013곳**.
#   2026-11-25 베트남 5차 4곳(PQCSR·PQCFI·HANJW·HANBN)을 더해 ③ 328 · 베트남 20 · **통합 1,025곳**.
#   2026-11-25 베트남 6차 4곳(HANHS·HANSW·HANHP·HANLP)을 더해 ③ 332 · 베트남 24 · **통합 1,029곳**.
#   2026-11-26 베트남 7차 4곳(HPHSI·DADHA·DADMC·SGNJS)을 더해 ③ 336 · 베트남 28 · **통합 1,033곳**.
#   2026-11-26 베트남 8차 4곳(SGNJT·SGNBS·SGNBR·SGNMD)을 더해 ③ 340 · 베트남 32 · **통합 1,037곳**.
#   2026-11-26 베트남 9차(마지막) 3곳(SGNSI·SGNAK·SGNFI)을 더해 ③ 343 · 베트남 35 · **통합 1,040곳**
#   — 베트남 35곳(1~9차) 전량 반영.
EXPECT_TABS = {'lux': 161, 'accor': 536, 'marriott': 343}
EXPECT_HOTELS = sum(EXPECT_TABS.values())
# ④ 하얏트는 ①②③ 마스터 밖의 별도 정본(data/app/tab10_hyatt.json)이다 — 병합할 때마다 곳수·칸수가
#   줄지 않았는지 확인한다(2026-11-26 미국 4차-A 24곳 → 299곳, 4차-B 1차 스코츠데일 5곳 → 304곳,
#   4차-B 2차 스코츠데일 2 · 포틀랜드 3 = 5곳 → 309곳, 4차-B 3차(마지막) 포틀랜드 4곳 → 313곳,
#   4차-B 샌안토니오 1차 4곳 → 317곳, 4차-B 샌안토니오 2차(마지막) 4곳 → 321곳,
#   4차-B 유럽 3차(이탈리아 1차) 로마 3곳 → 324곳 · 118,260칸 · 값 105,760칸 — 117,165칸 · 값 104,770칸에서
#   이탈리아 1차 3곳(1,095칸 · 값 990칸)을 더한 수, 유럽 4차(이탈리아 2차) 피렌체 · 베네치아 · 사르데냐
#   3곳 → 327곳 · 119,355칸 · 값 106,461칸 — 이탈리아 2차 3곳(1,095칸 · 값 701칸)을 더한 수,
#   유럽 5차(스위스 1차) 취리히 · 클로텐 2 · 다보스 · 플림스 5곳 → 332곳 · 121,180칸 · 값 107,948칸,
#   유럽 6차 이탈리아 밀라노 2 · 그리스 7 · 포르투갈 리스본 3 = 12곳 → 344곳 · 125,560칸 · 값 110,307칸,
#   유럽 7차(포르투갈 2차) 마데이라 · 알부페이라 · 빌라모우라 3곳 → 347곳 · 126,655칸 · 값 111,370칸,
#   동남아 1차(태국 방콕) bkkaz · bkkzk · bkkzs 3곳 신규 + hy28 코드 정정(bkkgh → bangh · 361칸 채움)
#   → 350곳 · 127,750칸 · 값 112,753칸 — 3곳(1,095칸)을 더하고 hy28 의 빈 365칸 가운데 361칸을 채운 수
#   · 방콕 6곳 · 동남아 10곳),
#   동남아 2·3차(인도네시아 14 · 베트남 13 = 27곳) → 377곳 · 137,605칸 · 값 121,145칸 —
#   27곳(9,855칸 · 값 8,392칸)을 더한 수 · 인도네시아 15곳(발리 8) · 베트남 14곳 ·
#   동남아 37곳 · 아·태 81곳. 알릴라 푸르나마(프리니시 라이브어보드)와 하얏트 센트릭
#   하노이 센터(미개관)는 어워드 대상이 아니어서 0칸이지만 카드로는 싣는다(기존 0칸 관례).
#   호주 11 · 말레이시아 11 · 태국 9 · UAE 5 = 36곳(13,140칸 · 값 12,651칸) → 413곳 ·
#   150,745칸 · 값 133,796칸 — 오세아니아 13곳 · 동남아 57곳(태국 16 · 말레이시아 11) ·
#   중동 5곳(아부다비 3 · 두바이 2) · 아·태 112곳. UAE 는 마스터 area 가 '중동·아프리카'지만
#   카드 region 은 '중동'으로 나눠 적는다(IHG 탭과 같은 표기).
#   싱가포르·뉴질랜드·스페인 18 · UAE 8 · 필리핀 2 · 대만 5 · 사우디 9 · 튀르키예 6 · 모로코 4 = 52곳
#   (18,980칸 · 값 13,619칸) → 465곳 · 169,725칸 · 값 147,415칸 — 동남아 61곳(싱가포르 3 · 필리핀 2) ·
#   오세아니아 14곳(오클랜드) · 중화권 15곳(대만 5) · 중동 22곳(두바이 10 · 아부다비 3 · 사우디 9) ·
#   아프리카 4곳(모로코) · 유럽 108곳(스페인 15 · 튀르키예 6) · 아·태 122곳. 마스터 area 는 튀르키예 ·
#   모로코를 '중동·아프리카'로 묶지만 카드 region 은 브리프대로 튀르키예를 '유럽', 모로코를 '아프리카'로
#   나눠 적는다(⑤ IHG 탭과 같은 표기). 알울라 하얏트 플레이스 · 하얏트 리젠시 마자간은 개관 전이라
#   0칸이지만 카드로는 싣는다(기존 0칸 관례 — 알릴라 푸르나마 · 하얏트 센트릭 하노이 센터와 같다).
#   2026-11-27 스페인 마드리드 2차 배치1 5 · 인도 1차 배치1·2 10 · 모로코·카타르 5차 5 = 20곳
#   (7,300칸 · 값 5,179칸) → 485곳 · 177,025칸 · 값 152,594칸 — 유럽 108→113(스페인 15→20) ·
#   중동 22→26(카타르 4 — 도하) · 아프리카 4→5(모로코 타가주트) · 남아시아 0→10(인도 — 델리 2 ·
#   구르가온 3 · 찬디가르 2 · 라이푸르 · 보드가야 · 비자야와다) · 아·태 122 그대로(남아시아는 따로 셈).
#   마스터 area 는 모로코·카타르를 '중동·아프리카'로 묶지만 카드 region 은 브리프대로 모로코
#   '아프리카' · 카타르 '중동'으로 나눠 적는다(⑤ IHG 탭과 같은 표기). bp023(바이아 프린시페 이스케이프
#   코랄 플라야)과 vgazv(하얏트 플레이스 비자야와다)는 월드 오브 하얏트 미참여라 0칸 · category null
#   이지만 카드로는 싣는다(기존 0칸 관례).
#   2026-11-27 인도 배치3·4 10 + 스페인 2차 배치2·3·4 15(말라가 2 · 마요르카 13) + 오만 3 · 요르단 2
#   = 30곳(10,950칸 · 값 4,957칸) → 515곳 · 187,975칸 · 값 157,551칸 — 유럽 113→128(스페인 20→35 ·
#   마요르카 2→15 · 말라가 첫 지점) · 중동 26→31(오만 3 · 요르단 2 첫 지점) · 남아시아 10→20
#   (인도 — 델리 4 · 고아 5 · 아메다바드 3 · 구르가온 3 · 찬디가르 2 · 라이푸르 · 보드가야 ·
#   비자야와다). 오만·요르단은 마스터 area 가 '중동·아프리카'라 카드 region '중동'으로 나눠 적는다.
#   wllin(알루아 린다 마요르카)은 월드 오브 하얏트 미참여라 0칸 · category null 이지만 카드로 싣는다
#   (bp023 · vgazv 와 같은 관례 — 영업 중이라 '개관 전' 표기를 쓰지 않는다).
#   2026-11-27 캐나다 1~4차 20(ca 15 + ca4 5) + 인도 2차 배치1 5 = 25곳(9,125칸 · 값 7,247칸) →
#   540곳 · 197,100칸 · 값 164,798칸 — 캐나다 0→**20**(이 탭 첫 캐나다 권역 · 캘거리 2 · 위니펙 2 ·
#   밴쿠버 2 · 해밀턴 2 · 미시소가 2 · 에드먼턴 · 버너비 · 캠룹스 · 켈로나 · 오소요스 · 프린스 조지 ·
#   멍크턴 · 브램턴 · 킹스턴 · 키치너) · 남아시아 20→**25**(인도 — 방갈로르 3 · 암리차르 · 함피).
#   캐나다는 마스터 area 가 '캐나다'라 미국(209)과 따로 권역을 두었다(IHG 탭의 '북미·중남미' 묶음과 달리
#   이 탭은 국가·권역을 따로 적는 표기). ykazk(Coming Soon) · yyzxh · yyzzh 는 0칸 · category null 이고
#   WoH 미참여다(yyzzh 는 Booking Notice 상 2027-09-29 개관 예정). yyzzh 와 yyzxh, yyzxa 와 yyzza 는
#   같은 주소 단지의 서로 다른 호텔(Hyatt Place / Hyatt House)이라 각각 카드로 싣는다.
#   2026-11-27 캐나다 2차 배치1·2 10 + 인도 2차 배치2·3 10 = 20곳(7,300칸 · 값 6,976칸) →
#   560곳 · 204,400칸 · 값 171,774칸 — 캐나다 20→**30**(몬트리올 2 · 도르발 · 미시소가 +1 · 나이아가라
#   폴스 · 나이아가라온더레이크 · 오타와 2 · 선더베이 · 토론토) · 남아시아 25→**35**(인도 — 방갈로르 +1 ·
#   첸나이 2 · 바루치 · 보팔 · 아우랑가바드 · 데라둔 2 · 다람살라 · 하리드와르).
#   몬트리올 도시명은 원자료의 Montréal 을 Montreal(몬트리올)로 통일했고, 아우랑가바드는 공홈 도시 개칭명
#   Chhatrapati Sambhajinagar 의 옛 이름을 카드 도시로 썼다(호텔명은 「아우랑가바드 에어포트」).
#   같은 날 스페인 1차 6곳(algtr · alcma · asibz · alsfu · alvfu · secbr) 카드 메모의 0칸 사유를
#   성인2·2박(los=2 · 20일 창 19개) · los=7 · 공홈 캘린더 UI 교차검증 결과로 정정했다 — 최소숙박·인원
#   조건이 아니라 **실제 어워드 재고 미표출**. 값·곳수 변화 없음.
#   2026-11-27 ④ 하얏트 인도 2차 5(하이데라바드 3 · 자이푸르 2) · 캐나다 2차 9(토론토 5 · 화이트호스 ·
#   윈저 · 프린스앨버트 2) · 스페인 3차 10(마르베야 · 메노르카 5 · 마요르카 2 · 미하스-마르베야 ·
#   무르시아 · 란사로테) = 24곳을 더해 560→584곳 · 204,400→213,160칸 · 171,774→176,513칸.
#   프린스앨버트 2곳은 「Coming Soon」 · WoH 미참여로 0칸(카테고리 null), 알루아 7곳은 성인2·2박 기준
#   미표출로 0칸, 라 잠브라 리조트는 표준룸 어워드 2일이다.
#   2026-11-27 ④ 하얏트 스페인 3차 마지막 8곳(테네리페 6 — 바이아 프린시페 익스플로어 판타지아·산 펠리페,
#   알루아솔 오로타바 밸리·알루아 테네리페·알루아 아틀란티코 골프 리조트·하얏트 지바 하르딘 트로피칼
#   테네리페, 세비야 톰슨 세비야, 란사로테 그랜드 하얏트)을 더해 584→592곳 · 213,160→216,080칸 ·
#   176,513→178,352칸. 알루아솔 오로타바 밸리 307일은 12-22 이후 최소 7박(los=7) 기준,
#   알루아 테네리페는 0/365일, 톰슨 세비야 표준룸 어워드는 12월 15일뿐이다.
#   2026-11-27 ④ 하얏트 남아시아 마지막 21곳(인도 15 — 바도다라·코치 2·티루바난타푸람·트리수르·
#   뭄바이 2·푸네 3·루디아나·자이푸르·러크나우·콜카타 2, 몰디브 3, 네팔 3)을 더해 592→613곳 ·
#   216,080→223,745칸 · 178,352→185,637칸. 남아시아 40→61곳(인도 55 · 몰디브 3 · 네팔 3).
#   2026-11-27 ④ 하얏트 카리브·중미 20곳(아루바 3 — 오라녜스타트 하얏트 플레이스 · 팜비치 하얏트 리젠시 ·
#   산니콜라스 시크릿츠 베이비 비치, 코스타리카 5 — 과나카스테 안다즈 · 에레디아 하얏트 플레이스 ·
#   파파가요 시크릿츠 · 산호세 하얏트 플레이스 · 산호세 에스카수 하얏트 센트릭, 쿠라사오 3 — 빌렘스타트
#   드림스·선스케이프·조에트리, 자메이카 9 — 몬테고베이 드림스 로즈홀·질라라·지바·주얼 그랜드·
#   시크릿츠 세인트제임스, 러너웨이베이 바이아 프린시페 2, 세인트제임스 브레스리스·시크릿츠 와일드
#   오키드)을 더해 613→633곳 · 223,745→231,045칸. 카리브·중미 20곳의 값 4,318칸 가운데 그랜드
#   하얏트·안다즈·시크릿츠·드림스·질라라·지바·주얼 그랜드·브레스리스·와일드 오키드는 허리케인
#   멜리사 운영 중단과 WoH 미참여로 0~215일이다. 같은 커밋에서 5번(@jin_5)의 한·일 20곳
#   90일(2026-12-01~2027-02-28) 재실측을 앞 90일 구간에만 반영해 값 있는 칸이 185,637→189,938칸
#   (신규 4,318 − 90일 재실측 순감 17)이 되었다. 현금가는 11-22/23 세후 KRW 그대로다.
EXPECT_HYATT = {'hotels': 633, 'cells': 231045, 'priced': 189938}
# ⑤ IHG도 ①②③ 마스터 밖의 별도 정본(data/app/tab11_ihg.json)이다 — 병합할 때마다 곳수·칸수·값 있는
#   칸이 줄지 않았는지, id·code 가 겹치지 않는지 확인한다.
#   2026-11-26 유럽 P1 8곳(218→226곳 · 현금 2,628 + 포인트 2,559칸)에 이어
#   2026-11-26 유럽 P1 1차 3곳(BUDKM · GVAHA · HELIN)을 더해 229곳 · 유럽 52 —
#   1,095칸(현금 1,007 · 포인트 985)을 더한 수.
#   2026-11-26 유럽 P1 2차 마지막 3곳(ATHHA · ISTHA · ISTKI = 그리스 1 · 튀르키예 2)을 더해
#   232곳 · 유럽 55 — 1,095칸(현금 1,031 · 포인트 1,001)을 더한 수 · 232 × 365 = 84,680칸.
#   2026-11-26 유럽 P2 1차 4곳(AMSPC · BRUZM · BERCC · MUCHB)을 더해 236곳 · 유럽 59 —
#   1,460칸(현금 1,331 · 포인트 1,330)을 더한 수 · 236 × 365 = 86,140칸.
#   2026-11-26 유럽 P2 2차 4곳(MUCLB · VIENR · PRGNP · BUDVH = 독일 · 오스트리아 · 체코 · 헝가리)을
#   더해 240곳 · 유럽 63 — 1,460칸(현금 1,342 · 포인트 1,276)을 더한 수 · 240 × 365 = 87,600칸.
#   2026-11-26 유럽 P2 3차 4곳(ZRHHA · GVACP · RKECP · STOKT = 스위스 2 · 덴마크 1 · 스웨덴 1)을
#   더해 244곳 · 유럽 67 — 1,460칸(현금 1,349 · 포인트 1,359)을 더한 수 · 244 × 365 = 89,060칸.
#   덴마크 · 스웨덴은 ⑤ IHG 유럽의 첫 지점이라 유럽이 18개국이 됐다(제네바 2 · 취리히 1).
#   2026-11-26 유럽 P2 4차 4곳(HELMH · ATHGR · ISTBM · ISTOR = 핀란드 1 · 그리스 1 · 튀르키예 2)을
#   더해 248곳 · 유럽 71 — 1,460칸(현금 1,367 · 포인트 1,368)을 더한 수 · 248 × 365 = 90,520칸.
#   핀란드 · 그리스 · 튀르키예는 이미 지점이 있어 유럽은 18개국 그대로다(헬싱키 2 · 아테네 2 ·
#   이스탄불 4). HELMH 는 크라운 플라자 헬싱키 - 헤스페리아이고 호텔 인디고 헬싱키(HELIN)와 다른 호텔.
#   2026-11-26 유럽 P2 5차(마지막) 3곳(NAVNC · WAWFN · REKRR = 튀르키예 · 폴란드 · 아이슬란드)을
#   더해 251곳 · 유럽 74 — 1,095칸(현금 681 · 포인트 502)을 더한 수 · 251 × 365 = 91,615칸.
#   폴란드 · 아이슬란드는 ⑤ IHG 유럽의 첫 지점이라 유럽이 20개국이 됐다. 튀르키예는
#   5곳(카파도키아 1 + 이스탄불 4)이 됐다. WAWFN 은 WorldHotels 운영 중 · IHG 채널 판매 미개시
#   (2027년 통합 예정)로 현금·포인트 365일 전부 null(0칸) — 기존 미판매 호텔(ROMAA·ROMVB·LISPD ·
#   ACCRA 등)과 같은 관례이고 check_ihg 는 0칸을 결측으로 보지 않는다(NO_POINT_CODES 는 ③ 메리어트
#   전용 목록이라 ⑤ 에는 등록하지 않는다). REKRR 은 리워드 재고가 얇아 포인트가 163일뿐이다.
#   2026-11-26 중남미 1차 4곳(MEXHA · MEXMC · MEXKM · MEXVC = 멕시코시티 4)을 더해 255곳 ·
#   북미·중남미 61 — 1,460칸(현금 1,357 · 포인트 1,225)을 더한 수 · 255 × 365 = 93,075칸.
#   멕시코는 ⑤ IHG 의 첫 지점(미국 52 · 캐나다 5 · 멕시코 4). MEXHA 는 2026-12-03 · 2027-01-27
#   스탠더드 매진으로 클럽·스위트만 남아 포인트가 241,000 · 278,000(통상 상한 120,000 초과)이고,
#   MEXKM 은 2026-12-01 · 12-02 달력 포인트 77,400 · 82,500 이 Points & Cash 최저 포인트분
#   (전액 포인트 91,000 · 97,000)이라 REKRR 과 같은 관례로 달력 표출값을 그대로 둔다.
#   MEXVC 는 2026년 12월 리워드 재고가 5일(12-06 · 12-13 · 12-16 · 12-23 · 12-30)뿐이다.
#   2026-11-26 중남미 2차 4곳(CUNHC · CUNCN · SAOHA · BUEHA = 칸쿤 2 · 상파울루 · 부에노스아이레스)을
#   더해 259곳 · 북미·중남미 65 — 1,460칸(현금 1,246 · 포인트 977)을 더한 수 · 259 × 365 = 94,535칸.
#   브라질 · 아르헨티나는 ⑤ IHG 의 첫 지점(미국 52 · 캐나다 5 · 멕시코 6 · 브라질 1 · 아르헨티나 1).
#   CUNHC 는 1박 12 USD Amenity Fee 별도(세후가 미포함)이고, CUNCN 은 옛 Real Inn 칸쿤을 voco 로
#   리브랜딩한 개관 초기 호텔이라 현금이 2027-02-15부터 268일 단일가(259,600원)만 열리고 리워드
#   포인트는 365일 전부 null(0칸)이다 — check_ihg 는 0칸을 결측으로 보지 않는다.
#   SAOHA 는 전면 리노베이션(로비·레스토랑·풀 임시 휴업) 공지, BUEHA 는 1인 1박 1.5 USD Amenity
#   Fee 별도다. ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조해 겹침 0곳(alsoIn 9쌍 그대로).
#   2026-11-26 중남미 3차 4곳(SCLHA · LIMHA · LIMMP · LIMMD = 산티아고 1 · 리마 3)을 더해 263곳 ·
#   북미·중남미 69 — 1,460칸(현금 1,362 · 포인트 1,331)을 더한 수 · 263 × 365 = 95,995칸.
#   칠레 · 페루는 ⑤ IHG 의 첫 지점(미국 52 · 캐나다 5 · 멕시코 6 · 브라질 1 · 아르헨티나 1 · 칠레 1 · 페루 3).
#   SCLHA 는 칠레 IVA 19% 포함 세후가이고 2027-04-04~06 · 04-11~15 · 04-19~22 12일이 현금·포인트 동시
#   매진(부활절 주간) · 2026-12-02 등 6일은 리워드만 없음, LIMHA 는 10% 서비스차지 + 18% IGV 포함이고
#   현금·포인트 null 집합이 같다. LIMMP 는 날짜별 최저가에 Early Saver Member Exclusive(환불불가 ·
#   29일 전 예약 · 회원 전용)가 들어 있고, LIMMD 는 2026년 12월 현금 31일 전부 판매에 리워드는 19일만
#   열려 포인트 319일(포인트만 비는 날 25일)이다 — check_ihg 는 0칸을 결측으로 보지 않는다.
#   네 곳 모두 마지막 값 있는 날이 2027-11-09(2027-11-10~30 예약창 밖)이다. ① 호텔럭스 161곳과
#   코드·영문명·국문명·도시를 전수 대조해 겹침 0곳(alsoIn 9쌍 그대로 · ①·⑤ 모두 좌표 필드 없음).
#   2026-11-26 중남미 4차(마지막) 2곳(LMAMI · PCYHA = 리마 1 · 파나마시티 1)을 더해 265곳 ·
#   북미·중남미 71 — 730칸(현금 687 · 포인트 655)을 더한 수 · 265 × 365 = 96,725칸. 이로써
#   중남미 14곳(멕시코시티 4 · 칸쿤 2 · 상파울루 1 · 부에노스아이레스 1 · 산티아고 1 · 리마 4 ·
#   파나마시티 1)이 전량 완결됐다. 파나마는 ⑤ IHG 의 첫 지점(미국 52 · 캐나다 5 · 멕시코 6 ·
#   브라질 1 · 아르헨티나 1 · 칠레 1 · 페루 4 · 파나마 1)이고 리마는 4곳이 됐다.
#   LMAMI(크라운 플라자)는 현금 344일 · 포인트 342일 — 2026-12-01 · 12-27 두 날은 리워드만 없고
#   현금 표시가는 세금·수수료 포함이나 포인트 모드 요금카드에 「Excludes 10% Service Charge.」가
#   병기돼 포인트 숙박에는 10% 서비스차지가 따로 붙는다. PCYHA(인터컨티넨탈)는 현금 343일 ·
#   포인트 313일 — 2026-12-11 이 현금·포인트 함께 빈 하루, 포인트만 비는 날 30일이고,
#   2026-12-26 은 달력 견적가 356,431원과 요금카드 최저 383,994원이 2만7,400원 다른 날이다
#   (달력 = 날짜별 최저 견적 · 요금카드 = Best Available 목록, 값은 달력 표시값 그대로).
#   두 곳 모두 마지막 값 있는 날이 2027-11-09(2027-11-10~30 예약창 밖)이다. ① 호텔럭스 161곳과
#   코드·영문명·국문명·도시를 전수 대조해 겹침 0곳(alsoIn 9쌍 그대로 · ①·⑤ 모두 좌표 필드 없음).
EXPECT_IHG = {'hotels': 265, 'cells': 96725, 'cash': 85015, 'points': 81841}
# ② 아코르 가운데 중올플 APC 카드 — 참여 287 + 기존 미참여·자격없음 2 = 289곳
#   12월 관측 창(12/1~18) 가능 210곳 · APC 칸 4,715 · 권역 116/137/36
#   현금 요금 보유 44곳(기존 40 + 통합하며 아코르 카드의 365일 요금이 붙은 4곳) · 미수집 245곳
EXPECT_APC = {'hotels': 289, 'participating': 287, 'dec_available': 211,
              # 2026-11-24 새벽 재관측 — 참여 287곳의 12/1~12/18 을 다시 관측했다(칸 수는 4,784 그대로,
              # 12월 가능 호텔 210→211곳, 가능→불가 27 · 불가→가능 41)
              'cells': 4784, 'tiers': {1: 116, 2: 137, 3: 36},
              'cash_filled': 44, 'cash_empty': 245}

# ② 아코르(통합) · Stay Plus & SNU — 536곳 · 지역 칩 4가지
#   2026-11-22 — ② 중올플 289곳과 ③ 아코르 265곳을 합쳤다(같은 호텔 18곳은 한 카드).
#   지역(zone): cn 중국(APC) 291 · kr 국내 30 · sea 동남아 196 · etc 기타 해외 19.
#   Red Hot Rooms 32곳 가운데 18곳은 365일 요금 없이 레드핫 시작가(`redhotRates`)만 있다.
EXPECT_ACCOR = {
    'hotels': 536,
    'zones': {'cn': 291, 'kr': 30, 'sea': 196, 'etc': 19},
    # Red Hot Rooms — 2026-11-22 오퍼 목록 32건 · 참여 호텔 32곳(기존 14 + 신규 18) · 창 안 날짜 1,909칸
    'redhot': {'offers': 32, 'hotels': 32, 'cells': 1909},
    'priced': {'C1B5': 0, 'A7Z9': 124, 'A5G7': 263, '8167': 357, 'B6R8': 362},
    'snu_rows': 43, 'snu_cities': 8,
    # SNU 참여 상태 — 2026-11-22 아코르 공식 「참여 호텔」 목록과 전수 대조한 결과
    'snu_counts': {'participating': 184, 'hotelExcluded': 30, 'brandExcluded': 320, 'unverified': 2},
    # 통합하며 중국 카드가 사라진 18곳 — 사라진 id 는 data/id_alias_accor.json 의 매핑대로 남은 카드로 간다
    'merged': {'ap052': 'aB9G8', 'ap063': 'aB953', 'ap075': 'a5949', 'ap088': 'a6824',
               'ap101': 'aB733', 'ap118': 'a8102', 'ap125': 'aB8Y3', 'ap140': 'a8167',
               'ap142': 'aB851', 'ap176': 'a2197', 'ap190': 'aC3B5', 'ap200': 'a8529',
               'ap216': 'a8719', 'ap224': 'a7970', 'ap237': 'aC4U2', 'ap241': 'a8873',
               'ap251': 'a9567', 'cA7Z9': 'aA7Z9'},
}
# 2026-11-22 — 페어몬트 앰배서더 서울(dB200)은 아코르 공식 SNU 참여 호텔이다. 예전엔 확인한 7개 창에
#   SNU 요금이 안 떠서 snu=False 로 적었는데, 그건 「요금 미노출」이지 「미참여」가 아니다. 그래서 True 로 바로잡았다.
EXPECT_DOMESTIC_PROGRAM = {'dB220': (True, True), 'dB200': (True, True),
                           'dA3N6': (True, False), 'dC2G2': (True, False)}
# 출처 문구에 사이트 이름을 쓰지 않는다
FORBIDDEN = ('accorcards', 'ittaeda', 'roame', '트립닷컴', '호텔럭스', 'hotelux',
             '아고다', '부킹닷컴', '카약', '스카이스캐너', '호텔스컴바인', '마이리얼트립',
             '네이버', '야놀자', '여기어때',
             # ⑥ 땡처리 탭 — 예약 사이트 이름은 화면 글자에 남기지 않는다(href 주소는 제외)
             '모두투어', '땡처리닷컴', 'ttang.com', 'modetour.com')

# 예외 — 2026-11-20 한진님 지시로 ① 탭 버튼 이름을 '호텔럭스'로 적는다.
# 이 문구 하나만 검사에서 빼고, 본문·출처 문구의 사이트 이름 금지는 그대로 둔다.
# 2026-11-20 추가 — 이중 예약 링크 버튼 이름 「💎 호텔럭스」(① 메리어트 계열 호텔 카드의 예약 버튼)도 같은 지시에 따른 표기라 함께 뺀다.
# 2026-11-21 추가 — ⑤ 항공 「예약처 선택 창」(한진님 요청: 항공사 공홈 vs 써드파티를 골라 새 탭에서 열기)의
#   버튼 이름·안내 문구에만 트립닷컴·스카이스캐너를 적는다. 아래 문구 하나하나만 검사에서 빼고,
#   다른 곳(출처·요금 근거 문구)의 사이트 이름 금지는 그대로 둔다.
ALLOWED_LABELS = ('① 호텔럭스', '💎 호텔럭스',
                  '트립닷컴·스카이스캐너·구글 플라이트 중 골라 새 탭에서 엽니다',
                  '트립닷컴·스카이스캐너·구글 플라이트',
                  '트립닷컴·스카이스캐너에서',
                  '트립닷컴 ↗', '스카이스캐너 ↗')


def check_mileage(mg):
    """⑥ 마일리지(부산) — 원천이 준 값만 있는지(비트 0~31), 날짜 창, 집계 일치 검사.

    좌석 수량·수수료·기재는 원천에 없으므로 자료에도 없어야 한다(있으면 실패).
    """
    problems = []
    if not isinstance(mg, dict):
        return ['⑦ 마일리지 데이터가 객체가 아님']
    if mg.get('schema') != 'mileage/1':
        problems.append('⑦ schema 가 mileage/1 이 아님')
    for need in ('observedAt', 'observedLabel', 'months', 'routes', 'cells', 'counts'):
        if need not in mg:
            problems.append('⑦ %s 키가 없음' % need)
    if problems:
        return problems
    codes = {r.get('code') for r in mg['routes'] if isinstance(r, dict)}
    months = set(mg['months'] or [])
    cells = mg['cells'] or []
    seen = set()
    for row in cells:
        if not isinstance(row, list) or len(row) != 4:
            problems.append('⑦ cells 행 형식이 [노선, 방향, 날짜, 값] 이 아님: %r' % (row,))
            break
        code, direction, date, bit = row
        if code not in codes:
            problems.append('⑦ 모르는 노선 %r' % (code,))
        if direction not in (0, 1):
            problems.append('⑦ 방향 %r 가 0/1 이 아님' % (direction,))
        if len(str(date)) != 10 or str(date)[:7] not in months:
            problems.append('⑦ 날짜 %r 가 탑승월 목록 밖' % (date,))
        if not isinstance(bit, int) or bit < 0 or bit & ~31:
            problems.append('⑦ %s %s 값 %r 가 비트(0~31) 밖' % (code, date, bit))
        key = (code, direction, date)
        if key in seen:
            problems.append('⑦ %s %s %s 중복' % key)
        seen.add(key)
    cnt = mg.get('counts') or {}
    if cnt.get('cells') not in (None, len(cells)):
        problems.append('⑦ counts.cells %r ≠ 실제 %d' % (cnt.get('cells'), len(cells)))
    open_cells = sum(1 for r in cells if isinstance(r, list) and len(r) == 4 and r[3] and not (r[3] & 16))
    if cnt.get('open') not in (None, open_cells):
        problems.append('⑦ counts.open %r ≠ 실제 %d' % (cnt.get('open'), open_cells))
    if not (mg.get('sourceUrl') or '').startswith('https://www.koreanair.com/'):
        problems.append('⑦ 출처 주소가 항공사 공식 주소가 아님')
    # 원천에 없는 값이 섞이지 않았는지(수량·수수료·기재)
    blob = json.dumps(mg, ensure_ascii=False).lower()
    for bad in ('"seats"', 'quantity', 'surcharge', 'aircraft', '"fee"'):
        if bad in blob:
            problems.append('⑦ 원천에 없는 항목이 들어 있음: %s' % bad)
    return problems


def check_ttang(tt):
    """⑥ 땡처리 · 부산 출발 상품 검사 — id 중복·기간 일치·가격·예약 호스트·출발일 창."""
    problems = []
    if not isinstance(tt, dict):
        return ['⑥ 땡처리 데이터가 객체가 아님']
    deals = tt.get('deals')
    if not isinstance(deals, list):
        return ['⑥ ttang.deals 가 배열이 아님']
    win = tt.get('window') or {}
    w_start = win.get('start') or TTANG_WINDOW[0]
    w_end = win.get('end') or TTANG_WINDOW[1]
    if not win:
        problems.append('⑥ ttang.window 없음')
    seen = set()
    for d in deals:
        tag = d.get('id') or d.get('city') or '?'
        for k in ('id', 'src', 'region', 'city', 'code', 'out', 'back', 'airline', 'url'):
            if not d.get(k):
                problems.append('⑥ %s 에 %s 없음' % (tag, k))
        if d.get('id') in seen:
            problems.append('⑥ 상품 id 중복: %s' % tag)
        seen.add(d.get('id'))
        if d.get('src') not in TTANG_SRC:
            problems.append('⑥ %s src 이상: %r (g/t)' % (tag, d.get('src')))
        try:
            o = datetime.date.fromisoformat(str(d.get('out')))
            b = datetime.date.fromisoformat(str(d.get('back')))
        except Exception:
            problems.append('⑥ %s 출발/귀국일 형식 이상' % tag)
            continue
        if not (w_start <= str(d.get('out')) <= w_end):
            problems.append('⑥ %s 출발일이 창(%s~%s) 밖' % (tag, w_start, w_end))
        if b < o:
            problems.append('⑥ %s 귀국일이 출발일보다 이전' % tag)
        u = d.get('outUntil')
        if u:
            try:
                until = datetime.date.fromisoformat(str(u))
            except Exception:
                problems.append('⑥ %s outUntil 형식 이상: %r' % (tag, u))
                until = None
            if until is not None and until < o:
                problems.append('⑥ %s outUntil 이 출발일보다 이전' % tag)
        pt = d.get('priceTo')
        if pt is not None:
            if not isinstance(pt, int) or (isinstance(d.get('price'), int) and pt < d['price']):
                problems.append('⑥ %s priceTo 값 이상: %r' % (tag, pt))
        if d.get('days') != (b - o).days + 1:
            problems.append('⑥ %s 유효기간 %s일(출발~귀국은 %d일)' % (tag, d.get('days'), (b - o).days + 1))
        nights = d.get('nights')
        if nights is not None and nights != (b - o).days:
            problems.append('⑥ %s 박수 %s(%d박)' % (tag, nights, (b - o).days))
        if d.get('airline') == '미확인':
            pass
        if not isinstance(d.get('price'), int) or d['price'] <= 0:
            problems.append('⑥ %s 가격이 양의 정수가 아님(추정·0원 금지): %r' % (tag, d.get('price')))
        elif d['price'] > 5_000_000:
            problems.append('⑥ %s 가격 이상 고가: %r' % (tag, d['price']))
        for k in ('seats', 'minPax'):
            v = d.get(k)
            if v is not None and (not isinstance(v, int) or v < 0):
                problems.append('⑥ %s %s 값 이상: %r' % (tag, k, v))
        m = _TT_URL_RE.match(str(d.get('url') or ''))
        host = (m.group(1).lower() if m else '')
        if not any(host == h or host.endswith('.' + h) for h in TTANG_HOSTS):
            problems.append('⑥ %s 예약 주소 호스트가 화이트리스트 밖: %s' % (tag, host or '-'))
    return problems


def check_apc(db):
    """② 아코르 가운데 중올플 APC 카드 289곳 · 권역(tier) · APC 상태 검사."""
    problems = []
    china = [h for h in db['hotels'] if h.get('group') == 'accor' and h.get('accor')]
    if len(china) != EXPECT_APC['hotels']:
        problems.append('② APC 카드 %d곳 (기대 %d곳)' % (len(china), EXPECT_APC['hotels']))
    part = [h for h in china if (h.get('accor') or {}).get('participation') == 'participating']
    if len(part) != EXPECT_APC['participating']:
        problems.append('② 참여 %d곳 (기대 %d곳)' % (len(part), EXPECT_APC['participating']))
    pids = [(h.get('accor') or {}).get('public_id') for h in china]
    if len(set(pids)) != len(pids) or None in pids:
        problems.append('② public_id 중복/누락')
    tiers = {}
    cells = dec_av = 0
    legacy_cash = 0
    fresh_none = 0
    for h in china:
        a = h.get('accor') or {}
        t = a.get('tier')
        tiers[t] = tiers.get(t, 0) + 1
        if t not in (1, 2, 3):
            problems.append('② %s 권역(tier) 없음/이상: %s' % (h['id'], t))
        if not a.get('tier_label') or not a.get('city_key'):
            problems.append('② %s 권역명/도시키 없음' % h['id'])
        if a.get('participation') == 'participating':
            obs = (a.get('dec') or {}).get('observed', 0)
            if not h.get('accor_apc') and obs:
                problems.append('② %s APC 날짜 상태 없음 (관측 %d일)' % (h['id'], obs))
            for d, v in (h.get('accor_apc') or {}).items():
                if v not in ('a', 'n') or not (WINDOW_START <= d <= WINDOW_END):
                    problems.append('② %s APC 값 이상 %s=%s' % (h['id'], d, v))
                    break
                if d not in (h.get('accor_apc_t') or {}):
                    problems.append('② %s APC 관측시각 누락 %s' % (h['id'], d))
                    break
                cells += 1
                if v == 'a' and d <= '2026-12-18':
                    dec_av += 1
            for k in ('dec', 'nov'):
                v = a.get(k)
                if not isinstance(v, dict) or 'available' not in v or 'observed' not in v:
                    problems.append('② %s %s 관측 요약 없음' % (h['id'], k))
        priced = sum(1 for v in (h.get('rates') or {}).values() if v is not None)
        if priced:
            legacy_cash += 1
            if priced < 100:
                # 우한(2027-04 이후 요금 이상 241일 제외)만 124일이다 — 더 줄면 요금이 유실된 것
                if h['name'] != '페어몬트 우한':
                    problems.append('② %s 현금 요금 %d일 (100일 미만)' % (h['id'], priced))
        else:
            fresh_none += 1
        for v in (h.get('rates') or {}).values():
            if v is not None and (not isinstance(v, int) or v <= 0):
                problems.append('② %s 요금이 양의 정수가 아님: %r' % (h['id'], v))
                break
            if isinstance(v, int) and v > 3_000_000:
                problems.append('② %s 에 비정상 고가(%s) — 이상값은 null 이어야 함' % (h['id'], v))
                break
        if len(h.get('rates') or {}) != 365:
            problems.append('② %s 날짜 칸 %d개' % (h['id'], len(h.get('rates') or {})))
    if tiers != EXPECT_APC['tiers']:
        problems.append('② 권역 분포 %s (기대 %s)' % (tiers, EXPECT_APC['tiers']))
    if cells != EXPECT_APC['cells']:
        problems.append('② APC 칸 %d (기대 %d)' % (cells, EXPECT_APC['cells']))
    dec_hotels = len({h['id'] for h in china
                      if any(v == 'a' and d <= '2026-12-18'
                             for d, v in (h.get('accor_apc') or {}).items())})
    if dec_hotels != EXPECT_APC['dec_available']:
        problems.append('② 12월 APC 가능 호텔 %d곳 (기대 %d곳)' % (dec_hotels, EXPECT_APC['dec_available']))
    if legacy_cash != EXPECT_APC['cash_filled']:
        problems.append('② 현금 요금 보유 호텔 %d곳 (기대 %d곳)' % (legacy_cash, EXPECT_APC['cash_filled']))
    if fresh_none != EXPECT_APC['cash_empty']:
        problems.append('② 현금 미수집 호텔 %d곳 (기대 %d곳)' % (fresh_none, EXPECT_APC['cash_empty']))
    # 통합으로 사라진 중국 카드가 다시 생기지 않았는지
    for gone, keep in EXPECT_ACCOR['merged'].items():
        if any(h.get('id') == gone for h in db['hotels']):
            problems.append('② 통합으로 합친 카드 %s 가 다시 있습니다(남은 카드 %s)' % (gone, keep))
    return problems


def check_accor(db):
    """② 아코르(통합) · Stay Plus & SNU — 536곳 · 지역 4가지 · alsoIn 양방향 · SNU 표 · 레드핫."""
    problems = []
    dom = [h for h in db['hotels'] if h.get('group') == 'accor']
    if len(dom) != EXPECT_ACCOR['hotels']:
        problems.append('② 아코르 %d곳 (기대 %d곳)' % (len(dom), EXPECT_ACCOR['hotels']))
    ids = {h['id']: h for h in db['hotels']}
    zones = {}
    for h in dom:
        z = h.get('zone')
        zones[z] = zones.get(z, 0) + 1
        if z not in EXPECT_ACCOR['zones']:
            problems.append('② %s 지역(zone) 없음/이상: %r' % (h['id'], z))
        if not h.get('city') or not h.get('name'):
            problems.append('② %s 도시/이름 없음' % h['id'])
        # 중국(APC) 카드는 APC 블록이 있어야 하고, APC 블록이 있으면 지역이 cn 이어야 한다
        if h.get('accor') and z != 'cn':
            problems.append('② %s APC 카드인데 지역이 %r' % (h['id'], z))
    if zones != EXPECT_ACCOR['zones']:
        problems.append('② 지역 분포 %s (기대 %s)' % (zones, EXPECT_ACCOR['zones']))
    # 사라진 중국 카드 id 가 남아 있지 않고, 남은 카드가 별칭 파일과 같은지
    alias_path = os.path.join(ROOT, 'data', 'id_alias_accor.json')
    if os.path.exists(alias_path):
        try:
            alias = json.loads(_read(alias_path)).get('map') or {}
        except Exception:                        # noqa: BLE001
            alias = {}
        if alias != EXPECT_ACCOR['merged']:
            problems.append('② id_alias_accor.json 매핑이 기대와 다름 (%d개)' % len(alias))
        for gone, keep in EXPECT_ACCOR['merged'].items():
            if gone in ids:
                problems.append('② 통합으로 합친 카드 %s 가 아직 있음' % gone)
            if keep not in ids:
                problems.append('② 통합 카드 %s 없음' % keep)
    rh_hotels = [h for h in dom if h.get('redhot')]
    for h in dom:
        rates = h.get('rates') or {}
        # 2026-11-22 — 레드핫으로 새로 넣은 18곳은 365일 요금 없이 레드핫 시작가만 있다.
        #   그 밖의 호텔은 지금까지처럼 365칸을 요구한다.
        only_redhot = bool(h.get('redhot')) and not rates
        if not only_redhot and len(rates) != 365:
            problems.append('③ %s 날짜 칸 %d개' % (h['id'], len(rates)))
        for v in rates.values():
            if v is not None and (not isinstance(v, int) or v <= 0):
                problems.append('③ %s 요금이 양의 정수가 아님: %r' % (h['id'], v))
                break
            # 2026-11-22 — 동남아 196곳을 더하며 상한을 1천만 원으로 올렸다. 앱의 이상치 기준
            #   (차트·콤보에서 1박 1천만 원 이상 제외)과 같은 값이고, 동남아 실측 최고가는
            #   반얀트리 크라비 7,482,333원(2026-12-31 빌라)이라 정상값을 자르지 않는다.
            if isinstance(v, int) and v > 10_000_000:
                problems.append('③ %s 에 비정상 고가(%s) — 이상값은 null 이어야 함' % (h['id'], v))
                break
        if h.get('alsoIn'):
            other = ids.get(h['alsoIn'])
            if other is None:
                problems.append('③ %s alsoIn %s 대상 없음' % (h['id'], h['alsoIn']))
            elif other.get('alsoIn') != h['id']:
                problems.append('③ %s ↔ %s alsoIn 이 한쪽만 있음' % (h['id'], h['alsoIn']))
    for code, n in EXPECT_ACCOR['priced'].items():
        h = ids.get('a' + code)
        if not h:
            problems.append('③ %s 없음' % code)
            continue
        got = sum(1 for v in (h.get('rates') or {}).values() if v is not None)
        if got != n:
            problems.append('③ %s 요금 표시 %d일 (기대 %d일)' % (h['name'], got, n))
    for hid, (sp, snu) in EXPECT_DOMESTIC_PROGRAM.items():
        p = (ids.get(hid) or {}).get('program') or {}
        if p.get('stayplus') is not sp or p.get('snu') is not snu:
            problems.append('③ %s program %s (기대 stayplus=%s snu=%s)' % (hid, p, sp, snu))
    # ── SNU 참여 상태 — 아코르 공식 「참여 호텔」 목록(2026-11-22)과 전수 대조한 결과 ──
    #    네 상태(참여·개별 미참여·브랜드 미참여·확인 불가)가 536곳 모두에 있고,
    #    program 이 있는 카드는 program.snu 와 결론이 같아야 한다.
    snu_cnt = {'participating': 0, 'hotel_excluded': 0, 'brand_excluded': 0, 'unverified': 0}
    for h in dom:
        s = h.get('snu')
        if not isinstance(s, dict) or s.get('status') not in snu_cnt:
            problems.append('② %s snu 상태 없음/이상: %r' % (h['id'], s))
            continue
        snu_cnt[s['status']] += 1
        if not isinstance(s.get('brand'), bool) or not s.get('note'):
            problems.append('② %s snu brand/note 빠짐' % h['id'])
        if not str(s.get('checked') or '').startswith('2026-'):
            problems.append('② %s snu 확인일 이상: %r' % (h['id'], s.get('checked')))
        if 'program' in h:
            p = h.get('program') or {}
            if bool(p.get('snu')) != (s['status'] == 'participating'):
                problems.append('② %s program.snu %r ≠ snu.status %s' % (h['id'], p.get('snu'), s['status']))
    want = EXPECT_ACCOR['snu_counts']
    if snu_cnt['participating'] != want['participating']:
        problems.append('② SNU 참여 %d곳 (기대 %d곳)' % (snu_cnt['participating'], want['participating']))
    for k, key in (('hotel_excluded', 'hotelExcluded'), ('brand_excluded', 'brandExcluded'),
                   ('unverified', 'unverified')):
        if snu_cnt[k] != want[key]:
            problems.append('② SNU %s %d곳 (기대 %d곳)' % (k, snu_cnt[k], want[key]))
    _prog = (db.get('accor') or {}).get('program') or {}
    if (_prog.get('snuCounts') or {}) != {'hotels': len(dom), 'participating': want['participating'],
                                          'hotelExcluded': want['hotelExcluded'],
                                          'brandExcluded': want['brandExcluded'],
                                          'unverified': want['unverified']}:
        problems.append('② SNU 집계 문구가 자료와 다름: %r' % (_prog.get('snuCounts'),))
    if 'SNU' not in str(_prog.get('snuBrands') or ''):
        problems.append('② SNU 브랜드 기준 문구 없음')
    # ── Red Hot Rooms — 원천(오퍼 목록)에 적힌 값만 있는지 ──────────────────
    if len(rh_hotels) != EXPECT_ACCOR['redhot']['hotels']:
        problems.append('③ 레드핫 참여 호텔 %d곳 (기대 %d곳)' % (len(rh_hotels), EXPECT_ACCOR['redhot']['hotels']))
    offer_ids, rh_codes, rh_cells = set(), set(), 0
    for h in rh_hotels:
        r = h['redhot']
        for k in ('offerId', 'title', 'code', 'currency', 'priceText', 'krw', 'stayText',
                  'bookUntil', 'offerUrl', 'status'):
            if r.get(k) in (None, ''):
                problems.append('③ %s 레드핫 %s 없음' % (h['id'], k))
        # 객실 타입은 오퍼 원문이 비어 있는 경우가 있다(페어몬트 싱가포르) — 키가 있는지만 본다
        if 'rooms' not in r:
            problems.append('③ %s 레드핫 rooms 없음' % h['id'])
        if r.get('code') != h.get('code'):
            problems.append('③ %s 레드핫 코드 %r ≠ 호텔 코드 %r' % (h['id'], r.get('code'), h.get('code')))
        if not isinstance(r.get('krw'), int) or r['krw'] <= 0:
            problems.append('③ %s 레드핫 원화 시작가 이상: %r' % (h['id'], r.get('krw')))
        if r.get('currency') not in ('VND', 'IDR', 'USD', 'PHP', 'SGD', 'AUD', 'JPY', 'THB', 'MYR'):
            problems.append('③ %s 레드핫 통화 이상: %r' % (h['id'], r.get('currency')))
        if r['offerId'] in offer_ids:
            problems.append('③ 레드핫 오퍼 id 중복: %s' % r['offerId'])
        offer_ids.add(r['offerId'])
        rh_codes.add(h.get('code'))
        m = r.get('redhotRates') or h.get('redhotRates') or {}
        rates = h.get('redhotRates') or {}
        if r.get('status') == 'ended':
            if rates:
                problems.append('③ %s 레드핫 종료 오퍼인데 날짜 %d칸' % (h['id'], len(rates)))
        elif not rates:
            problems.append('③ %s 레드핫 진행 오퍼인데 날짜 없음' % h['id'])
        for d, v in rates.items():
            rh_cells += 1
            if not (WINDOW_START <= d <= WINDOW_END):
                problems.append('③ %s 레드핫 날짜 %s 창 밖' % (h['id'], d))
                break
            if not isinstance(v, int) or v <= 0:
                problems.append('③ %s 레드핫 %s 값 이상: %r' % (h['id'], d, v))
                break
            if v != r.get('krw'):
                problems.append('③ %s 레드핫 %s 값 %r ≠ 시작가 %r' % (h['id'], d, v, r.get('krw')))
                break
        if len(rates) != r.get('dates'):
            problems.append('③ %s 레드핫 dates %r ≠ 실제 %d칸' % (h['id'], r.get('dates'), len(rates)))
        if r.get('exceptDates'):
            bad = [d for d in r['exceptDates'] if d in rates]
            if bad:
                problems.append('③ %s 레드핫 제외일이 날짜에 남아 있음: %s' % (h['id'], bad[:3]))
        if not str(r.get('offerUrl') or '').startswith('https://www.accorplus.com/offers/'):
            problems.append('③ %s 레드핫 오퍼 주소 이상: %s' % (h['id'], r.get('offerUrl')))
        if h.get('rates'):
            # 기존 호텔 — 레드핫을 더해도 365일 요금·Stay Plus 는 그대로여야 한다
            if len(h['rates']) != 365:
                problems.append('③ %s 레드핫 추가 후 요금 칸 %d개' % (h['id'], len(h['rates'])))
    if len(offer_ids) != EXPECT_ACCOR['redhot']['offers']:
        problems.append('③ 레드핫 오퍼 %d건 (기대 %d건)' % (len(offer_ids), EXPECT_ACCOR['redhot']['offers']))
    if rh_cells != EXPECT_ACCOR['redhot']['cells']:
        problems.append('③ 레드핫 칸 %d개 (기대 %d개)' % (rh_cells, EXPECT_ACCOR['redhot']['cells']))
    for h in dom:
        if not (h.get('rates') or {}) and not h.get('redhot'):
            problems.append('③ %s 요금도 레드핫도 없음' % h['id'])

    accor = db.get('accor') or {}
    program = accor.get('program') or {}
    if program.get('stayplusExpiry') != '2027-09-30' or program.get('snuExpiry') != '2027-12-31':
        problems.append('③ SNU/Stay Plus 만료일 %s' % program)
    rows = accor.get('rows') or []
    if len(rows) != EXPECT_ACCOR['snu_rows']:
        problems.append('③ SNU 후보 %d줄 (기대 %d줄)' % (len(rows), EXPECT_ACCOR['snu_rows']))
    cities = {r.get('city') for r in rows}
    if len(cities) != EXPECT_ACCOR['snu_cities']:
        problems.append('③ SNU 도시 %d개 (기대 %d개: %s)' % (len(cities), EXPECT_ACCOR['snu_cities'],
                                                        sorted(cities)))
    for r in rows:
        if not r.get('hotel') or not r.get('checkin'):
            problems.append('③ SNU 줄에 호텔/체크인 없음: %s' % r)
            continue
        if not (WINDOW_START <= r['checkin'] <= WINDOW_END):
            problems.append('③ SNU 체크인 창 밖: %s' % r)
        for k in ('snu', 'list', 'save'):
            if not isinstance(r.get(k), int) or r[k] <= 0:
                problems.append('③ SNU %s 값 이상: %s' % (k, r))
        if isinstance(r.get('snu'), int) and isinstance(r.get('list'), int) and r['list'] < r['snu']:
            problems.append('③ SNU 정가가 SNU 요금보다 쌈: %s' % r)
    return problems


# 예약 링크(href) 호스트 — 화면에 보이는 글자가 아니라 날짜 칸이 여는 주소이므로
# 출처 문구 검사에서 제외한다. 그 밖의 출처 표기는 그대로 검사한다.
LINK_HOSTS = ('marriott.com', 'ritzcarlton.com', 'all.accor.com', 'accor.com', 'accorplus.com',
              'hotelux.com', 'trip.com', 'weixin.qq.com', 'americanexpress.com',
              'ttang.com', 'modetour.com', 'ybtour.co.kr', 'hanatour.com', 'tikitikit.kr')

# ── ⑥ 땡처리 · 부산 출발 ────────────────────────────────────────────────
# 부산(PUS) 출발 땡처리 상품 — `const TTANG`(master 의 ttang). 화면의 날짜 칸·노선 행·상품 행은
# 모두 이 상품들의 예약 주소(url)로 새 탭을 연다. 추정 금액은 넣지 않는다.
TTANG_SCHEMA = 'team-busan/pus-deals/1'
TTANG_WINDOW = ('2026-11-19', '2027-11-30')
TTANG_HOSTS = ('ttang.com', 'modetour.com', 'ybtour.co.kr', 'hanatour.com', 'trip.com', 'tikitikit.kr')
TTANG_SRC = ('g', 't')
_TT_URL_RE = re.compile(r'^https://(?:www\.)?([^/]+)/', re.I)
_LINK_RE = re.compile(r'https?://([^\s"\'<>()\\]+)', re.I)


# ⑥⑦⑧ 앱 딥링크 표(FL_APP_PKG · FL_APP_DEEP)의 키는 화면 글자가 아니라 링크 주소를 찾는 코드값이다.
# (예: 'modetour.com' → 패키지) — href 와 같은 이유로 출처 문구 검사에서 뺀다.
_APP_MAP_RE = re.compile(r"var FL_APP_(?:PKG|DEEP)=\{.*?\n\};", re.S)


def strip_booking_links(text_blob):
    """예약 링크 주소만 지운다(출처 검사 대상 = 화면에 보이는 글자)."""
    text_blob = _APP_MAP_RE.sub(' ', text_blob)

    def repl(m):
        host = m.group(1).split('/')[0].split(':')[0].lower()
        for h in LINK_HOSTS:
            if host == h or host.endswith('.' + h):
                return ' '
        return m.group(0)
    return _LINK_RE.sub(repl, text_blob)


def check_sources(text_blob):
    """출처 문구에 제3자 사이트 이름이 남아 있지 않은지 검사."""
    low = strip_booking_links(text_blob).lower()
    for label in ALLOWED_LABELS:
        low = low.replace(label.lower(), ' ')
    hits = [w for w in FORBIDDEN if w in low]
    return ['출처 문구에 금지된 사이트 이름: %s' % ', '.join(hits)] if hits else []


#   일본 3·4차 59곳에서 시티 익스프레스 2곳(오사카 신이마미야·난바 사우스)과 르네상스 1곳(오키나와)이 처음 들어왔다.
#   대만 4곳(2026-11-24)에서 럭셔리 컬렉션(AMNIS) · 디자인 호텔스(Gloria Manor) · 메리어트 ·
#   포 포인츠가 각 1곳씩 늘었고, 대만 2차 4곳(2026-11-24)에서 쉐라톤 2곳(신주·타오위안) ·
#   웨스틴 1곳(이란) · 포 포인츠 1곳(자오시)이 늘었으며, 오세아니아 10곳에서 리츠칼튼(퍼스) · 오토그래프(캔버라) · 알로프트 ·
#   웨스틴(퍼스) · 코트야드(퍼스 Murdoch) · 쉐라톤(포트더글라스) · 럭셔리 컬렉션(호바트) ·
#   메리어트(애들레이드) · 포 포인츠 2곳이 늘었다. 대만 4차 4곳(2026-11-24)에서 디자인 호텔스
#   (Proverbs) · 알로프트(Zhongshan) 각 1곳, 코트야드(Downtown · 타이베이) 2곳이 늘었다.
#   대만 5차 4곳(2026-11-24)에서 르메르디앙 2곳(타이베이 · Banqiao) · 메리어트 1곳(타이베이) ·
#   르네상스 1곳(Shihlin)이 늘었고, 대만 6차 4곳(2026-11-24)에서 쉐라톤 2곳(타이베이 · New Xinzhuang) ·
#   알로프트 1곳(Beitou) · 트리뷰트 포트폴리오 1곳(Madison)이 늘었다.
#   대만 7차 4곳(2026-11-24)에서 트리뷰트 포트폴리오 1곳(Suz Catorze) · 포 포인츠 1곳(타이베이 Bali —
#   원자료 브랜드가 `포인트`로 잘려 와 기존 표기로 통일) · 르메르디앙 1곳(타이중) · 목시 1곳(타이중)이 늘었다.
#   대만 8차 1곳(2026-11-24)에서 알로프트 1곳(타이중)이 늘었다(8→9).
#   베트남 1차 4곳(2026-11-25)에서 JW 메리어트 1곳(깜라인 · 8→9) · 웨스틴 1곳(깜라인 · 17→18) ·
#   쉐라톤 1곳(껀터 · 24→25) · 오토그래프 컬렉션 1곳(껀터 · 13→14)이 늘었다.
#   베트남 2차 4곳(2026-11-25)에서 메리어트 2곳(나트랑 Hon Tre · 다낭 · 24→26) · 쉐라톤 1곳(나트랑 ·
#   25→26) · 포 포인츠 바이 쉐라톤 1곳(나트랑 — 원자료 브랜드가 `포인트`로 잘려 와 기존 표기로 통일 · 15→16)이 늘었다.
#   베트남 3차 4곳(2026-11-25)에서 메리어트 1곳(다낭 Non Nuoc Beach Villas · 26→27) ·
#   메리어트 이그제큐티브 아파트먼트 1곳(다낭 한 리버 · 2→3) · 쉐라톤 1곳(다낭 그랜드 · 26→27) ·
#   코트야드 바이 메리어트 1곳(다낭 한 리버 · 27→28)이 늘었다.
#   베트남 4차 4곳(2026-11-25)에서 포 포인츠 바이 쉐라톤 1곳(다낭 · 16→17) · JW 메리어트 1곳(푸꾸옥 · 9→10) ·
#   쉐라톤 1곳(빈 · 27→28) · 목시 1곳(푸꾸옥 혼톰 · 9→10)이 늘었다.
#   베트남 5차 4곳(2026-11-25)에서 쉐라톤 1곳(푸꾸옥 롱 비치 · 28→29) · JW 메리어트 1곳(하노이 · 10→11) ·
#   페어필드 바이 메리어트 1곳(푸꾸옥 혼톰 · 34→35) · 메리어트 1곳(박닌 · 27→28)이 늘었다.
#   베트남 6차 4곳(2026-11-25)에서 쉐라톤 2곳(하노이 · 하노이 웨스트 · 29→31) · 포 포인츠 바이 쉐라톤
#   2곳(하장 · 랑선 · 17→19)이 늘었다.
#   베트남 7차 4곳(2026-11-26)에서 쉐라톤 1곳(하이퐁 · 31→32) · 르네상스 1곳(다낭 호이안 · 2→3) ·
#   메리어트 1곳(호이안 · 28→29) · JW 메리어트 1곳(사이공 · 11→12)이 늘었다.
#   베트남 8차 4곳(2026-11-26)에서 JW 메리어트 1곳(사이공 더 아파트먼트 · 12→13) ·
#   디자인 호텔스 1곳(호찌민 바흐 스위트 · 13→14) · 르네상스 1곳(호찌민 리버사이드 · 3→4) ·
#   르메르디앙 1곳(사이공 · 5→6)이 늘었다.
#   베트남 9차 3곳(2026-11-26)에서 쉐라톤 1곳(사이공 그랜드 오페라 · 32→33) ·
#   오토그래프 컬렉션 1곳(랜드마크 81 · 14→15) · 페어필드 바이 메리어트 1곳(사우스 빈즈엉성 · 35→36)이 늘었다.
EXPECT_BRANDS = {'리츠칼튼': 28, '세인트레지스': 16, 'W': 15, '코트야드 바이 메리어트': 28,
                 '포 포인츠 바이 쉐라톤': 19, 'JW 메리어트': 13, '럭셔리 컬렉션': 12, '웨스틴': 18,
                 '오토그래프 컬렉션': 15, '페어필드 바이 메리어트': 36, '메리어트': 29, 'AC 호텔': 5,
                 '알로프트': 9, '목시': 10, '쉐라톤': 33, '에디션': 3,
                 '메리어트 이그제큐티브 아파트먼트': 3, '르메르디앙': 6, '트리뷰트 포트폴리오': 7,
                 '디자인 호텔스': 14, '포인트 플렉스 바이 쉐라톤': 16, '엘리먼트': 1,
                 '메리어트 베케이션 클럽': 1, '시티 익스프레스': 2, '르네상스': 4}
# 한·일 원본 CSV 기대치(2026-11-17 수집) — 유실·중복 방지용 고정값. 2026-11-23에 한국 30곳을
#   더하면서 k11~k40 이 이 목록에 섞이지 않도록 원본 22곳 id 만 골라 검사한다. 신규 30곳은 아래
#   EXPECT_KR30 으로 따로 고정한다.
#   2026-11-26 조 3 순환 갱신 — k01~k07 7곳을 365일 재실측(2026-11-26 05:13 조회)해 현금 6,800→7,127칸 ·
#   아워드 포인트 6,629→6,502칸이 됐다(k08~k10 · j01~j12 15곳은 그대로 · 22×365=8,030칸).
#   2026-11-27 조 4 순환 갱신 — k08~k10 3곳 · j01~j12 12곳을 365일 재실측(2026-11-27 04:30~05:01 조회)해
#   현금 7,127→7,509칸 · 아워드 포인트 6,502→6,612칸이 됐다(22×365=8,030칸 · k09 SELER 은 아워드 미판매 0칸).
EXPECT_KJ = {'hotels': 22, 'cash': 7509, 'points': 6612}
KJ_IDS = {'k%02d' % i for i in range(1, 11)} | {'j%02d' % i for i in range(1, 13)}
# 2026-11-22 실측 한국 신규 30곳(k11~k40) — 현금 9,862칸 · 아워드 포인트 9,704칸 / 30×365=10,950칸
EXPECT_KR30 = {'hotels': 30, 'cash': 9862, 'points': 9704}
# 2026-11-23 싱가포르 8곳(m41~m48) — 현금 2,676칸 · 아워드 포인트 2,261칸 / 8×365=2,920칸
#   SINRZ(리츠칼튼 밀레니아)는 포인트 캘린더 미게시(0칸) — 보간하지 않는다.
EXPECT_SG8 = {'hotels': 8, 'cash': 2676, 'points': 2261}
SG8_IDS = {'m%02d' % i for i in range(41, 49)}
# 2026-11-23 싱가포르 중반 7곳(m49~m55) — 현금 2,398칸 · 아워드 포인트 2,041칸 / 7×365=2,555칸
#   SINHS(스트라이프스 차이나타운)는 아워드 재고 미게시(4회 독립 조회)로 포인트 0칸 — 보간하지 않는다.
EXPECT_SG7 = {'hotels': 7, 'cash': 2398, 'points': 2041}
SG7_IDS = {'m%02d' % i for i in range(49, 56)}
# 2026-11-23 싱가포르 마지막 7곳(m56~m62) — 현금 2,393칸 · 아워드 포인트 2,363칸 / 7×365=2,555칸
#   포인트 미게시 호텔은 없다(7곳 모두 아워드 포인트 캘린더 값이 있다). null 은 보간하지 않는다.
EXPECT_SG7L = {'hotels': 7, 'cash': 2393, 'points': 2363}
SG7L_IDS = {'m%02d' % i for i in range(56, 63)}
# 2026-11-23 오세아니아 1차 23곳(m63~m85) — 현금 7,250칸 · 아워드 포인트 6,263칸 / 23×365=8,395칸
#   제외 2곳: NANWI(웨스틴 피지 골프 · 호텔 페이지 404 미취급) · NANTI(쉐라톤 나디 토코리키 · 판매 중단).
#   포인트 0칸 3곳(NANSI 12월 31일만 판매 후 중단 · OOLAC 12/18 개관 · POMEA)은 보간하지 않는다.
EXPECT_OC23 = {'hotels': 23, 'cash': 7250, 'points': 6263}
OC23_IDS = {'m%02d' % i for i in range(63, 86)}
# 2026-11-23 일본 1차 30곳(m86~m115) — 현금 10,026칸 · 아워드 포인트 9,534칸 / 30×365=10,950칸
#   30곳 모두 포인트 캘린더 값이 있다(0칸 호텔 없음). null 은 보간하지 않는다.
#   UKBCY(코트야드 고베)는 2027-07-04 이후 150일 결번, UKYAK(오토그래프 교토)는 2027-10-01~11-30
#   61일 전면 결번 — 5번이 직접 로드·도시검색·다음 달 뷰로 확인한 실제 미개방이라 결번 그대로 둔다.
EXPECT_JP30 = {'hotels': 30, 'cash': 10026, 'points': 9534}
JP30_IDS = {'m%02d' % i for i in range(86, 116)}
# 2026-11-23 일본 2차 30곳(m168~m197) — 현금 9,904칸 · 아워드 포인트 9,233칸 / 30×365=10,950칸
#   CTSRZ(리츠칼튼 니세코) 2027-01-01~03-31 90일 · TYOCY(코트야드 도쿄 긴자)·MMJFJ(메리어트 후지 레이크야마나카)
#   2027-10-01~11-30 61일 · TYOAR(AC 호텔 도쿄 긴자) 2027-10-09~11-30 53일은 5번이 직접 로드·도시검색으로
#   확인한 실제 판매중단이라 결번 그대로 둔다(null 보간 없음).
EXPECT_JP30B = {'hotels': 30, 'cash': 9904, 'points': 9233}
JP30B_IDS = {'m%02d' % i for i in range(168, 198)}
# 2026-11-23 오세아니아 2차 14곳(m198~m211) — 현금 4,507칸 · 아워드 포인트 4,252칸 / 14×365=5,110칸
#   호주 14곳(멜버른 3 · 브리즈번 5 · 골드코스트 1 · 시드니 5) 모두 포인트 값이 있다(0칸 없음).
#   시드니 4곳(SYDWH·SYDMC·SYDXP·SYDAK)은 2027-10-01~11-30 61일, SYDSI 는 2027-10-28~11-30 34일,
#   멜버른 2곳(MELEL·MELCY)은 2027-10-01~10-24 24일이 결번 — 판매 중단과 예약창 상한을 구분하지 않고
#   보간하지 않는다.
EXPECT_OC2 = {'hotels': 14, 'cash': 4507, 'points': 4252}
OC2_IDS = {'m%02d' % i for i in range(198, 212)}
# 2026-11-23 일본 3차 30곳(m212~m241) — 현금 9,284칸 · 아워드 포인트 8,942칸 / 30×365=10,950칸
#   CTSKO(디자인 호텔스 삿포로)는 현금 365일 전면 판매중단(0칸)이고 포인트도 2027-10-26 하루 46,000P만
#   개방(1칸), OSAKO(디자인 호텔스 오쓰)는 아워드 365일 미게시(0칸)다 — 값이 없다는 사실 자체가 실측 결과라
#   보간하지 않는다. UBJSN(디자인 호텔스 야마구치)은 2027-04-01~11-30 244일 미게시, OSAMC(메리어트 오사카
#   Miyako)·OSACY(코트야드 오사카 신역)는 2027년 10월 이후 전면 결번이다.
EXPECT_JP34 = {'hotels': 30, 'cash': 9284, 'points': 8942}
JP34_IDS = {'m%d' % i for i in range(212, 242)}
# 2026-11-23 일본 4차 29곳(m242~m270) — 현금 9,546칸 · 아워드 포인트 8,184칸 / 29×365=10,585칸
#   TYOYY(코트야드 요코하마 신역 · 2026-12-18 개관) · TYOMH(럭셔리 컬렉션 하코네 MITSUI) ·
#   HKDXF(포 포인츠 플렉스 하코다테)는 아워드 재고 미개방(0칸), OKACR(코트야드 오키나와)은
#   2027-09-01~11-30 91일, OKARN(르네상스 오키나와)·OKJYD(디자인 호텔스 오카야마)는 2027년 10월 이후,
#   IKIKM(디자인 호텔스 이키)은 2027-07-01~11-30 153일 미게시다 — 보간하지 않는다.
EXPECT_JP34B = {'hotels': 29, 'cash': 9546, 'points': 8184}
JP34B_IDS = {'m%d' % i for i in range(242, 271)}
# 2026-11-24 오세아니아 2차 잔여 10곳(m271~m280) — 현금 3,367칸 · 아워드 포인트 3,219칸 / 10×365=3,650칸
#   호주 10곳(시드니 1 · 애들레이드 1 · 캔버라 1 · 퍼스 5 · 포트더글라스 1 · 호바트 1) 모두 포인트 값이
#   있다(0칸 없음). SYDCF 는 2027-10-01~11-30 61일, ADLMC 는 현금만 2027-09-30~10-17 18일 결번,
#   CNSSI 는 2027-07~08월 포인트가 격일로 비는 등 호텔별 예약창 상한과 성수기 재고 폐쇄를 구분하지 않고
#   보간하지 않는다.
EXPECT_OC10 = {'hotels': 10, 'cash': 3367, 'points': 3219}
OC10_IDS = {'m%d' % i for i in range(271, 281)}
# 2026-11-24 대만 1차 4곳(m281~m284) — 현금 1,215칸 · 아워드 포인트 1,149칸 / 4×365=1,460칸
#   KHHGM 은 2027-06-26~11-30 158일 현금·포인트 함께 미판매(1박·2박 체크인 불가 확인),
#   TPELF 는 포인트가 연중 26,000P 단일가, KHHLC 는 2026-12-04 현금 13,964,706원(1천만 원 이상
#   실측값 — 6번 교차 확인)이다. null 은 보간하지 않는다.
EXPECT_TW4 = {'hotels': 4, 'cash': 1215, 'points': 1149}
TW4_IDS = {'m%d' % i for i in range(281, 285)}
# 2026-11-24 대만 2차 4곳(m285~m288) — 현금 1,227칸 · 아워드 포인트 1,156칸 / 4×365=1,460칸
#   TPEHS(쉐라톤 신주) 336+326 · TPEYR(웨스틴 이란) 342+323 · TPEPJ(포 포인츠 자오시) 211+180 ·
#   TPESY(쉐라톤 타오위안) 338+327. TPEPJ 는 2027-07-01~11-30 153일 현금·포인트 함께 판매 중단(3박
#   조회 포함 불가 — 6번 확인), TPEYR 은 연말·설연휴(2026-12-28 · 12-31 · 2027-02-06~08)가
#   174만~194만원대 고가일, 네 곳 모두 2027-11-13~30 18일이 예약 창 끝(Rate Unavailable)이다.
#   TPEHS·TPESY 는 아워드 포인트가 2027-11-07 부터 현금보다 6일 먼저 끊긴다. null 은 보간하지 않는다.
EXPECT_TW8 = {'hotels': 8, 'cash': 2442, 'points': 2305}
TW8_IDS = {'m%d' % i for i in range(281, 289)}
# 2026-11-24 대만 3차 3곳(m289~m291) — 현금 891칸 · 아워드 포인트 632칸 / 3×365=1,095칸
#   TPETW(웨스틴 타오위안 Tashee) 341+327 · TTTSI(쉐라톤 타이둥) 209+0 · TPEWH(W 타이베이) 341+305.
#   TTTSI 는 아워드 포인트 캘린더가 365일 전부 미게시(0칸)이고, 현금은 2027-04-01~07-31 122일이
#   끊겼다가 2027-08-01 부터 다시 열린다(6번이 전면 판매 중단 후 재개로 확인) — null 은 보간하지 않는다.
#   TPEWH 는 2026-12-31 20,416,237원이 창 안 최고가이고 2027-05-26~06-03 컴퓨텍스 기간이
#   795,212~1,512,843원, TPETW 는 2027-11-07 부터 아워드 포인트가 끊긴다. 세 곳 모두
#   2027-11-13~30 18일이 예약 창 끝(Rate Unavailable)이다.
EXPECT_TW11 = {'hotels': 3, 'cash': 891, 'points': 632}
TW11_IDS = {'m%d' % i for i in range(289, 292)}
# 2026-11-24 대만 4차 4곳(m292~m295) — 현금 1,239칸 · 아워드 포인트 1,131칸 / 4×365=1,460칸
#   TPEDS(디자인 호텔스 타이베이 Proverbs) 210+149 · TPEAL(알로프트 타이베이 Zhongshan) 344+317 ·
#   TPECD(코트야드 바이 메리어트 타이베이 Downtown) 347+331 · TPECY(코트야드 바이 메리어트 타이베이)
#   338+334. TPEDS 는 2027-07-01~11-30 153일 현금·포인트가 함께 미게시(6번은 2027-07-01 이후
#   미게시로 전달)이고 2026-12-29 824,815원이 창 안 최고가다. TPEAL 은 2026-12-25~26·12-31 이
#   결번이고 포인트가 2027-11-06 에 끊기며, TPECD 는 2026-12-31 2,125,738원 · 2026-12-05
#   2,086,947원이 창 안 최고가·차고가다. TPECY 는 2026-12-26 717,630원 · 2026-12-31 705,993원이
#   고가 구간이고 현금·포인트가 모두 2027-11-06 까지만 게시된다. null 은 보간하지 않는다.
EXPECT_TW15 = {'hotels': 4, 'cash': 1239, 'points': 1131}
TW15_IDS = {'m%d' % i for i in range(292, 296)}
# 2026-11-24 대만 5차 4곳(m296~m299) — 현금 1,362칸 · 아워드 포인트 1,288칸 / 4×365=1,460칸
#   TPESH(르네상스 타이베이 Shihlin) 343+322 · TPEDM(르메르디앙 타이베이) 347+321 ·
#   TPEMB(르메르디앙 타이베이 Banqiao) 341+335 · TPETM(메리어트 타이베이) 331+310.
#   TPESH 는 2026-12-19 1,041,881원이 창 안 최고가(12-31 652,462원), TPEDM 은 2026-12-04·2027-01-01 이
#   6,206,536원으로 같고 12-31 2,572,445원 · 2027-05-26~06-04 컴퓨텍스 기간 969,771~1,062,869원,
#   TPEMB 는 2026-12-31 775,817원이 최고가이고 현금이 2027-11-06 에 끊겨 2027-11-07~11-30 24일이
#   1박 체크인 불가(6번은 11-07~12 로 전달 — 실측 결번이 11-30 까지 이어진다), TPETM 은
#   2027-02-15·2027-05-18 791,333원이 최고가이고 아워드 포인트만 2027-11-07 부터 끊긴다.
#   네 곳 모두 2027-11-13~30 18일이 예약 창 끝(Rate Unavailable)이다. null 은 보간하지 않는다.
EXPECT_TW19 = {'hotels': 4, 'cash': 1362, 'points': 1288}
TW19_IDS = {'m%d' % i for i in range(296, 300)}
# 2026-11-24 대만 6차 4곳(m300~m303) — 현금 1,022칸 · 아워드 포인트 992칸 / 4×365=1,460칸
#   TPEST(쉐라톤 타이베이) 343+326 · TPESX(쉐라톤 타이베이 New Xinzhuang) 0+0 ·
#   TPEBE(알로프트 타이베이 Beitou) 339+335 · TPEMT(트리뷰트 포트폴리오 타이베이 Madison) 340+331.
#   TPESX 는 2027년 1월 개관 예정(Opening Soon Jan 2027)으로 현금·포인트 365일이 모두 미게시다 —
#   0칸을 결측이 아니라 실측 결과로 싣고 보간하지 않는다(오픈 후 재실측 대상).
#   TPEST 는 2026-12-19·12-25·12-26·2027-01-09 543,071원이 창 안 최고가(12-30 519,797원),
#   TPEBE 는 2026-12-12 384,029원이 최고가이고 2027-03-02 이후 현금은 값이 있는 날이 모두 155,163원,
#   포인트는 2027-04-01 이후 17,500P 기본에 04-03·04-17·04-24 18,000P · 2027-10-24~11-12 27,000P 예외다
#   (6번은 17,500P 평탄으로 전달 — 실측에 예외가 있다). TPEMT 는 2026-12-30·2027-01-01 601,258원이
#   최고가이고 현금·포인트가 함께 2027-11-06 에 끊겨 2027-11-07~11-30 24일이 1박 불가다(6번은 11-07~12 로
#   전달 — 실측 결번이 11-30 까지 이어진다). TPEST·TPEBE 는 2027-11-12 가 마지막이고 11-13~30 18일이 예약
#   창 끝(Rate Unavailable)이다. null 은 보간하지 않는다.
EXPECT_TW23 = {'hotels': 4, 'cash': 1022, 'points': 992}
TW23_IDS = {'m%d' % i for i in range(300, 304)}
# 2026-11-24 대만 7차 4곳(m304~m307) — 현금 1,133칸 · 아워드 포인트 700칸 / 4×365=1,460칸
#   TPESC(트리뷰트 포트폴리오 타이베이 Suz Catorze) 340+0 · TPEFT(포 포인츠 바이 쉐라톤 타이베이
#   Bali) 335+245 · RMQMD(르메르디앙 타이중) 119+117 · RMQOX(목시 타이중) 339+338.
#   TPESC 는 아워드 포인트 캘린더가 365일 전부 미게시(0칸 — 어워드 재고 없음, null 보간 없음)이고
#   현금은 2027-05-01~2027-11-06 190일이 667,202원 한 값으로 평탄하다(실측 그대로).
#   TPEFT 는 아워드 포인트가 2026-12-31~2027-02-28 60일 비고 2027-03-06 이후 토요일 중심으로 결번이
#   반복되며, RMQMD 는 현금·포인트가 2027-04-01~11-30 244일 통째로 미게시다(6번 "2027-04~11 재고 없음"과
#   실측 일치). TPESC·TPEFT·RMQOX 는 현금·포인트가 2027-11-06 에 끊겨 11-07~30 24일이 빈다.
EXPECT_TW27 = {'hotels': 4, 'cash': 1133, 'points': 700}
TW27_IDS = {'m%d' % i for i in range(304, 308)}
# 2026-11-24 대만 8차 1곳(m308) — 현금 345칸 · 아워드 포인트 344칸 / 1×365=365칸
#   RMQTL(알로프트 타이중) 세전 현금 144,424~268,677원 · 결번 20일(2026-12-12 · 2026-12-31 ·
#   2027-11-13~30), 아워드 포인트 19,000~27,000P · 결번 21일(2026-12-05 · 12-12 · 12-31 ·
#   2027-11-13~30). 현금은 144,424원이 286일 · 토요일 40일만 174,640원 · 연휴 15일 208,245원 ·
#   2027-02-06~02-09 268,677원, 포인트는 22,000P 기본 254일 · 토요일 33일 24,500P · 27,000P 39일이다.
#   현금·포인트가 함께 2027-11-12 에 끊겨 11-13~30 18일이 예약 창 끝(Rate Unavailable)이다.
#   null 은 보간하지 않는다(6번 대화의 「현금 365/365일」과 달리 실측은 345/344일).
EXPECT_TW28 = {'hotels': 1, 'cash': 345, 'points': 344}
TW28_IDS = {'m308'}
# 2026-11-25 베트남 1차 4곳(m309~m312) — 현금 1,363칸 · 아워드 포인트 1,354칸 / 4×365=1,460칸
#   CXRJW 341/340(포인트 2027-02-07 미게시) · CXRWI 347/341 · VCASI 347/347 · VCALM 328/326.
#   네 곳 모두 포인트 값이 있어 NO_POINT_CODES 등록 대상은 없다. null 은 보간하지 않는다.
EXPECT_VN1 = {'hotels': 4, 'cash': 1363, 'points': 1354}
VN1_IDS = {'m%02d' % i for i in range(309, 313)}
# 2026-11-25 베트남 2차 4곳(m313~m316) — 현금 1,373칸 · 아워드 포인트 1,355칸 / 4×365=1,460칸
#   CXRHT 344/342(현금 2026-12-10~12-12 · 포인트 2026-12-09~12-12 · 2026-12-26 미게시) ·
#   NHASI 347/337(포인트 2027-11-07~11-30 24일 미게시) · CXRNP 341/341 · DADMR 341/335.
#   네 곳 모두 포인트 값이 있어 NO_POINT_CODES 등록 대상은 없다. null 은 보간하지 않는다.
#   ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳이라 alsoIn·MAR_CROSS 추가 0쌍.
EXPECT_VN2 = {'hotels': 4, 'cash': 1373, 'points': 1355}
VN2_IDS = {'m%02d' % i for i in range(313, 317)}
# 2026-11-25 베트남 3차 4곳(m317~m320) — 현금 1,007칸 · 아워드 포인트 973칸 / 4×365=1,460칸
#   DADNN(메리어트 다낭 Non Nuoc Beach Villas) 336/333 · DADER(메리어트 이그제큐티브 아파트먼트 다낭
#   한 리버) 0/0 · DADSI(쉐라톤 그랜드 다낭 비치 리조트) 339/328 · DADCY(코트야드 바이 메리어트 다낭
#   한 리버) 332/312. DADER 는 2027년 1분기 개관 예정(Opening Q1 2027)으로 현금·포인트 365일이 모두
#   미게시다 — 0칸을 결측이 아니라 실측 결과로 싣고 NO_POINT_CODES 에 등록한다(오픈 후 재실측 대상).
#   나머지 세 곳은 포인트 값이 있다. null 은 보간하지 않는다.
#   ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳이라 alsoIn·MAR_CROSS 추가 0쌍.
EXPECT_VN3 = {'hotels': 4, 'cash': 1007, 'points': 973}
VN3_IDS = {'m%d' % i for i in range(317, 321)}
# 2026-11-25 베트남 4차 4곳(m321~m324) — 현금 1,012칸 · 아워드 포인트 994칸 / 4×365=1,460칸
#   DADFP(포 포인츠 바이 쉐라톤 다낭) 344/338 · VIISI(쉐라톤 빈) 341/341 ·
#   PQCJW(JW 메리어트 푸꾸옥 에메랄드 베이 리조트 앤 스파) 327/315 · PQCOX(목시 푸꾸옥 혼톰) 0/0.
#   PQCOX 는 2027년 1분기 개관 예정(Opening Q1 2027)으로 현금·포인트 365일이 모두 미게시다 —
#   0칸을 결측이 아니라 실측 결과로 싣고 NO_POINT_CODES 에 등록한다(오픈 후 재실측 대상).
#   DADFP 는 현금이 2027-11-12 까지 · 포인트가 2027-11-06 에 먼저 끊기고, VIISI 는 둘 다 2027-11-06,
#   PQCJW 는 둘 다 2027-11-12 까지다. null 은 보간하지 않는다.
#   ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳(① 탭에 푸꾸옥·빈 호텔이 없다)이라 alsoIn·MAR_CROSS 추가 0쌍.
EXPECT_VN4 = {'hotels': 4, 'cash': 1012, 'points': 994}
VN4_IDS = {'m%d' % i for i in range(321, 325)}
# 2026-11-25 베트남 5차 4곳(m325~m328) — 현금 665칸 · 아워드 포인트 665칸 / 4×365=1,460칸
#   PQCSR(쉐라톤 푸꾸옥 롱 비치 리조트) 325/336 · HANJW(JW 메리어트 호텔 하노이) 340/329 ·
#   PQCFI(페어필드 바이 메리어트 푸꾸옥 혼톰) 0/0 · HANBN(박닌 메리어트 호텔) 0/0.
#   PQCFI 는 2027년 1분기 개관 예정(Opening Q1 2027), HANBN 은 원자료에서 marriott.com 숙소 페이지가
#   404(미등록)·미판매로 확인돼 둘 다 현금·포인트 365일이 미게시다 — 0칸을 결측이 아니라 실측 결과로
#   싣고 NO_POINT_CODES 에 등록한다(등록·개관 후 재실측 대상).
#   PQCSR 은 현금·포인트가 함께 2027-11-12 까지, HANJW 는 포인트가 2027-11-06 에 먼저 끊긴다
#   (현금 2027-11-12까지). null 은 보간하지 않는다.
#   ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳(① 탭에 푸꾸옥·하노이 호텔이 없다)이라 alsoIn·MAR_CROSS 추가 0쌍.
EXPECT_VN5 = {'hotels': 4, 'cash': 665, 'points': 665}
VN5_IDS = {'m%d' % i for i in range(325, 329)}
# 2026-11-25 베트남 6차 4곳(m329~m332) — 현금 1,383칸 · 아워드 포인트 1,336칸 / 4×365=1,460칸
#   HANHS(쉐라톤 하노이 호텔) 344/299 · HANSW(쉐라톤 하노이 웨스트) 345/343 ·
#   HANHP(포 포인츠 바이 쉐라톤 하장) 347/347 · HANLP(포 포인츠 바이 쉐라톤 랑선) 347/347.
#   HANSW 는 2026-12-01 · 2026-12-17 두 날만 스위트가 남아 1박 284만·265만 원의 고가가 실측됐다
#   (나머지 날은 15~27만 원대 — 보간·제외하지 않고 실측값 그대로). 네 곳 모두 포인트 값이 있어
#   NO_POINT_CODES 등록 대상은 없다. HANHS 는 포인트가 2027-11-06 에 먼저 끊기고(현금 11-12까지)
#   네 곳 모두 2027-11-13~30 18일이 예약 창 끝이다. null 은 보간하지 않는다.
#   원자료 국문명 `포인트 하노이 Ha Giang`·`포인트 하노이 Lang Son` 은 잘려 와 marriott.com/ko 공식
#   표기(`포 포인츠 바이 쉐라톤 하장`·`포 포인츠 바이 쉐라톤 랑선`)로 바로잡고, 원자료 도시 칸(하노이)도
#   실제 소재지인 하장 · 랑선으로 고쳤다(하장은 하노이에서 약 300km · 랑선은 약 150km).
#   ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳(① 탭에 하노이·하장·랑선 호텔이 없다)이라 alsoIn·MAR_CROSS 추가 0쌍.
EXPECT_VN6 = {'hotels': 4, 'cash': 1383, 'points': 1336}
VN6_IDS = {'m%d' % i for i in range(329, 333)}
# 2026-11-26 베트남 7차 4곳(m333~m336) — 현금 1,287칸 · 아워드 포인트 1,064칸 / 4×365=1,460칸
#   HPHSI(쉐라톤 하이퐁) 341/338(포인트 2026-12-06 · 12-08 · 2027-07-12 · 2027-11-07~30 미게시) ·
#   DADHA(르네상스 다낭 호이안 리조트 앤 스파) 278/62 — 현금이 2027-09-04 까지(2027-09-05~11-30 87일
#   미게시)이고, 포인트는 2026-12~2027-01 두 달만 표출된 뒤 2027-02-01~11-30 303일이 미게시다. ·
#   DADMC(호이안 메리어트 리조트 앤 스파) 327/326 — 2026-12-15 개관 예정(공식 Special Opening Offer
#   「Stay from December 15, 2026」)이라 2026-12-01~12-14 14일이 개관 전 미게시이고, 포인트는
#   2027-03-22 하루도 미게시다. · SGNJS(JW 메리어트 호텔 앤 스위트 사이공) 341/338
#   (포인트 2026-12-26 · 2027-02-27 · 2027-03-16 · 2027-11-07~30 미게시).
#   네 곳 모두 포인트 값이 있어 NO_POINT_CODES 등록 대상은 없다. 현금·포인트가 함께 끝나는
#   2027-11-07~11-30 24일은 예약 창 끝이다. null 은 보간하지 않는다.
#   원자료 국문명(`르네상스 호이안 Danang`·`메리어트 호이안`·`JW 메리어트 호찌민 Saigon`)은 잘려 와
#   marriott.com/ko 공식 표기로 바로잡았다(르네상스 페이지 「르네상스 다낭 호이안 리조트 & 스파」 ·
#   ko 신규 오픈 호텔 `호이안 메리어트 리조트 & 스파` · 「JW 메리어트 호텔 & 스위트 사이공」).
#   ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳(① 탭에 하이퐁·호이안·호찌민 호텔이 없다)이라
#   alsoIn·MAR_CROSS 추가 0쌍.
EXPECT_VN7 = {'hotels': 4, 'cash': 1287, 'points': 1064}
VN7_IDS = {'m%d' % i for i in range(333, 337)}
# 2026-11-26 베트남 8차 4곳(m337~m340) — 현금 1,366칸 · 아워드 포인트 629칸 / 4×365=1,460칸
#   SGNJT(JW 메리어트 호텔 앤 스위트 사이공, 더 아파트먼트) 347/0 · SGNBS(디자인 호텔스 호찌민 바흐 스위트)
#   328/290 · SGNBR(르네상스 리버사이드 호텔 사이공) 344/339 · SGNMD(르메르디앙 사이공) 347/0.
#   SGNJT·SGNMD 는 아워드 포인트 캘린더가 365일 전부 미게시(0칸)다 — 0칸을 결측이 아니라 실측 결과로
#   싣고 NO_POINT_CODES 에 등록한다(재실측 대상). SGNBS 는 현금·포인트가 2027-11-02 에, 나머지 세 곳은
#   2027-11-12 에 끊긴다. null 은 보간하지 않는다.
#   SGNJT 는 7차 SGNJS(JW 메리어트 호텔 앤 스위트 사이공)와 같은 복합 시설의 아파트먼트를 marriott.com 이
#   별도 숙소 코드로 파는 것이라 같은 호텔 중복이 아니다(공식 SGNJS ko 페이지 「305개의 객실과 스위트,
#   그리고 260개의 아파트먼트」) — 별도 카드로 싣는다.
#   원자료 국문명(`JW 메리어트 호찌민 Saigon`·`디자인 호텔스 호찌민 Bach Saigon`·`르네상스 호찌민
#   Riverside Saigon`·`르메르디앙 호찌민 Saigon`)은 marriott.com/ko 공식 표기로 바로잡았다
#   (SGNBS 는 ko 한국어 페이지가 없어 기존 디자인 호텔스 카드 관례 `디자인 호텔스 + 도시 + 고유명`).
#   ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳(① 탭에 호찌민 호텔이 없다)이라 alsoIn·MAR_CROSS 추가 0쌍.
EXPECT_VN8 = {'hotels': 4, 'cash': 1366, 'points': 629}
VN8_IDS = {'m%d' % i for i in range(337, 341)}
# 2026-11-26 베트남 9차(마지막) 3곳(m341~m343) — 현금 1,040칸 · 아워드 포인트 1,031칸 / 3×365=1,095칸
#   SGNSI(쉐라톤 사이공 그랜드 오페라 호텔) 346/343 · SGNAK(빈펄 랜드마크 81, 오토그래프 컬렉션)
#   347/341 · SGNFI(페어필드 바이 메리어트 사우스 빈즈엉성) 347/347.
#   SGNSI 는 2027-03-11 하루만 3,398,187원(다른 날의 10배 이상 · DOM .price-section 재확인, 같은 날 포인트
#   미게시)이고 2026-12-31 740,883원이다. SGNAK 은 2026-12-31 하루만 740,883원(창 안 최고가),
#   SGNFI 는 2027-03-09 하루만 110,742원이 최고가다. 세 곳 모두 현금·포인트가 2027-11-12 에 끊겨
#   2027-11-13~30 18일이 예약 창 끝이다. null 은 보간하지 않는다.
#   원자료 국문명(`쉐라톤 호찌민 Saigon Grand Opera`·`오토그래프 컬렉션 호찌민 Vinpearl Landmark 81`·
#   `페어필드 바이 메리어트 호찌민 South Binh Duong`)은 marriott.com/ko 공식 표기(`빈펄 랜드마크 81,
#   오토그래프 컬렉션`·`페어필드 바이 메리어트 사우스 빈즈엉성`)로 바로잡았고, SGNSI 는 ko 한국어 페이지가
#   없어 8차 SGNBS 와 같은 카드 관례(브랜드 + 사이공 + 고유명)로 `쉐라톤 사이공 그랜드 오페라 호텔`,
#   SGNFI 는 공식 ko 페이지가 「빈즈엉성 투언안시」로 적는 실제 소재지에 맞춰 도시를 `빈즈엉` 으로 적었다.
#   세 곳 모두 포인트 값이 있어 NO_POINT_CODES 등록 대상은 없다.
#   ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳(① 탭에 호찌민·빈즈엉 호텔이 없다)이라 alsoIn·MAR_CROSS 추가 0쌍.
EXPECT_VN9 = {'hotels': 3, 'cash': 1040, 'points': 1031}
VN9_IDS = {'m%d' % i for i in range(341, 344)}
# 아워드 포인트 캘린더가 전 기간 미게시인 호텔(코드) — 「포인트 칸 없음」 검사에서 뺀다.
#   k09 여의도 파크 센터 MEA · NANSI 12월 31일만 판매 · OOLAC 12/18 개관 · POMEA
NO_POINT_CODES = {'NANSI', 'OOLAC', 'POMEA',
                  # 일본 3·4차 — 아워드 포인트 캘린더 전 기간 미게시
                  'OSAKO', 'TYOYY', 'TYOMH', 'HKDXF',
                  # 대만 3차 — 쉐라톤 타이둥 아워드 포인트 캘린더 전 기간 미게시
                  'TTTSI',
                  # 대만 6차 — 쉐라톤 타이베이 New Xinzhuang 은 2027-01 개관 예정이라 현금·포인트 모두 미게시
                  'TPESX',
                  # 대만 7차 — 트리뷰트 포트폴리오 타이베이 Suz Catorze 는 아워드 포인트 캘린더 전 기간 미게시
                  #   (어워드 재고 없음 · 현금 340일은 실측됨)
                  'TPESC',
                  # 베트남 3차 — 메리어트 이그제큐티브 아파트먼트 다낭 한 리버 는 2027년 1분기 개관 예정이라
                  #   현금·포인트 365일 모두 미게시(0칸)
                  'DADER',
                  # 베트남 4차 — 목시 푸꾸옥 혼톰 은 2027년 1분기 개관 예정이라 현금·포인트 365일 모두 미게시(0칸)
                  'PQCOX',
                  # 베트남 5차 — 페어필드 바이 메리어트 푸꾸옥 혼톰 은 2027년 1분기 개관 예정,
                  #   박닌 메리어트 호텔 은 marriott.com 페이지 404(미등록·미판매)라 둘 다 365일 미게시(0칸)
                  'PQCFI', 'HANBN',
                  # 베트남 8차 — JW 메리어트 호텔 앤 스위트 사이공, 더 아파트먼트 와 르메르디앙 사이공 은
                  #   아워드 포인트 캘린더가 365일 전부 미게시(현금은 실측됨) — 재실측 대상
                  'SGNJT', 'SGNMD'}
# ① HoteLux 탭과 호텔이 겹치는 ⑤ 항목(요금 출처가 달라 둘 다 수록) — alsoIn 으로 교차 표시
EXPECT_OVERLAP = ({'k01', 'k02', 'k04', 'k05', 'k20', 'k26', 'j01', 'j04', 'j10', 'j11', 'j12'}
                  | SG8_IDS
                  # 싱가포르 중반 7곳 가운데 ① 탭과 겹치는 4곳(나머지 3곳은 ① 탭에 같은 호텔이 없다)
                  | {'m49', 'm52', 'm53', 'm54'}
                  # 싱가포르 마지막 7곳 가운데 ① 탭과 겹치는 2곳(웨스틴 = h97 · 세랑군 하우스 = h89,
                  #   나머지 5곳은 ① 탭에 같은 호텔이 없다)
                  | {'m56', 'm58'}
                  # 일본 2차 30곳 가운데 ① 호텔럭스와 같은 호텔 4곳(TYOJW↔h41 · TYOAK↔h46 ·
                  #   TYOAM↔h53 · TYOWI↔h60)
                  | {'m181', 'm187', 'm188', 'm189'}
                  # 오세아니아 2차 14곳 가운데 ① 호텔럭스와 같은 호텔 1곳(SYDWH W 시드니 ↔ h110)
                  | {'m207'}
                  # 베트남 1차 4곳 가운데 ① 호텔럭스와 같은 호텔 1곳(CXRJW JW 메리어트 깜라인 Bay ↔ h22)
                  | {'m309'})
# 원래부터 두 탭에 있던 중복(③ Stay Plus ↔ ① HoteLux) — 새 중복과 구분하기 위한 허용 목록
KNOWN_DUP = {('dB200', 'h39')}

# ④ 항공 — 47개 노선(기존 24 + 중국 신규 8 + 필리핀 신규 4 + 일본 신규 7 + 동남아 신규 4)
# · 2026년 12월 ~ 2027년 11월(12개월) · 당일치기(0박) 패턴
EXPECT_FLIGHTS = 47
# 중국 신규 8노선 — 노선 코드 → (도시 이름, 딜 건수). 12~1월 완본(9주 × 5패턴 180칸) +
# 연길·장가계·구이린·황산의 2027년 2~6월 금~일(2박) 71칸 + 연길 6/5 토~월 1칸(2026-11-18 반영)
# + 선양·다롄·광저우·샤먼의 2027년 2~6월 2박 168칸 완주본(금~일 84 + 토~월 84, 2026-11-18 반영)
# + 연길·장가계·구이린 2027년 2~6월 토~월 28칸(2026-11-18 반영, 황산 토~월은 값 0칸·0건 6칸)
# + 2026-11-18 완주본 2건 — 선양·다롄·광저우·샤먼 목~일 84칸 + 선양 금~월 1칸,
#   연길·장가계·구이린·황산 토~월 48칸(황산 3/20 토~월은 판매편 0건으로 정정)
# + 2026-11-18 3박 완주본 2건 — 선양·다롄·광저우·샤먼 2027년 2~6월 금~월 84칸(선양 2/5는 기존이라
#   신규 83칸), 연길·장가계·구이린·황산 2027년 2~6월 목~일 84칸(황산 포함 0건 없음)
# + 2026-11-18 G1 갱신본 — 선양·다롄·광저우·샤먼 2027년 2~6월 목~월(4박) 48칸(2/4~4/22 12주, 4/29 이후 미조회)
# + 2026-11-18 중국 8개 노선 2027년 7~11월 15주말 × 7패턴(측정 465 · 요금 465칸) —
#   SHE +75 · DLC +105 · CAN +90 · XMN +75 · YNJ +105 · DYG +15 · KWL +0 · TXN +0
# + 2026-11-18 G1 완결본 — 선양·다롄·광저우·샤먼 2027년 2~6월 목~월(4박) 4/29~6/24 9주 36칸을 더해 420/420칸(100%)
#   SHE +9 · DLC +9 · CAN +9 · XMN +9
# + 2026-11-18 일본 7노선 2027년 1월 완결본 140칸(값 138 · 항공편 없음 2) + 당일치기 21칸
#   KMJ +26 · TAK +23 · MYJ +20 · FSZ +28 · MMY +20 · CTS +22 · KOJ +20
EXPECT_NEW_ROUTES = {'SHE': ('선양', 226), 'DLC': ('다롄', 256), 'CAN': ('광저우', 241), 'XMN': ('샤먼', 226),
                     'YNJ': ('연길', 256), 'DYG': ('장가계', 166), 'KWL': ('구이린', 150), 'TXN': ('황산', 87)}
# 2026-11-18 신규 15노선 — 노선 코드 → (도시 이름, 딜 건수).
# 필리핀 4노선(4번)은 2026.12~2027.01 9주 × 5패턴 45칸씩 180칸 완본(판매편 0건 없음),
# 동남아 4노선(4번)은 같은 기간 178칸(비엔티안 12/3 목~일·목~월 2칸은 가격 미제공),
# 일본 7노선(5번)은 2026년 12월 완결본 171칸(175칸 중 — 삿포로 25칸 완결 + 시즈오카 21 · 나머지 25씩)
#   + 당일치기 실측 4칸(삿포로·구마모토·시즈오카·다카마쓰) = 175칸. 미실측은 시즈오카 4칸(표시 운임 없음).
# 동남아 4노선(4번)은 2026.12~2027.01 178칸 + 2027년 2~6월 21주 × 5패턴 420칸(푸꾸옥·코타키나발루·
#   쿠알라룸푸르 150칸씩 · 비엔티안 148칸 — 12/3 목~일·목~월 2칸 가격 미제공).
# 필리핀 4노선은 2026-11-18 2027년 2~6월 21주 × 5패턴 105칸을 더해 150칸이 됐고,
# 같은 날 저녁 2027년 7~11월 1차 실측(실측 126칸)을 더해 세부 162 · 마닐라 207 · 보홀 152 · 클락 205칸이다.
# 일본 7노선은 2026-11-19 2027년 7월 완결본(6개 노선 25칸 값 + 시즈오카 25칸 미오픈)을 더한 값이다.
# 2026-11-19 2027년 9~10월 병합분을 더했다 — KMJ +23 · KOJ +30 · MYJ +30 · TAK +30 · MMY +45 · CTS +32
# (시즈오카는 9~10월이 전부 판매편 0건·미오픈이라 값 0칸으로 85칸 그대로).
# 같은 날 2027년 8월 병합분을 더했다 — CTS +20 · KOJ +20 · KMJ +20 · MYJ +20 · TAK +20 · MMY +20
# (시즈오카 8월은 20칸이 전부 항공편 0건(미오픈)이라 값 0칸, 85칸 그대로).
# 필리핀 4노선은 2026-11-19 2027년 7~10월 미조회 174칸을 모두 채운 값을 더했다(네 노선 모두 75칸).
EXPECT_NEW_ROUTES2 = {'CEB': ('세부', 225), 'MNL': ('마닐라', 225), 'TAG': ('보홀(팡라오)', 225),
                      'CRK': ('클락', 225), 'PQC': ('푸꾸옥', 205), 'BKI': ('코타키나발루', 205),
                      'KUL': ('쿠알라룸푸르', 205), 'VTE': ('비엔티안', 203),
                      'KMJ': ('구마모토', 186), 'KOJ': ('가고시마', 252),
                      'FSZ': ('시즈오카', 85), 'MYJ': ('마쓰야마', 216), 'TAK': ('다카마쓰', 255),
                      'MMY': ('미야코지마', 171), 'CTS': ('삿포로', 275)}
# 일본 7노선 당일치기 실측 4칸(0박) — 노선 → (출발일, 금액). 나머지 노선은 당일치기 칸이 없다.
EXPECT_JP_DAYTRIP = {'CTS': ('2026-12-12', 574900), 'KMJ': ('2026-12-16', 370300),
                     'FSZ': ('2026-12-09', 305800), 'TAK': ('2026-12-24', 795000)}
# 일본 7노선의 1월 칸 — 2026-11-18 1월 완결본(4주 × 5패턴 140칸) + 당일치기 실측
#   = 기존 12/31 주 3칸 + 주말형 값/항공편 없음 + 당일치기(KMJ 6 · TAK 4 · FSZ 9 · CTS 2)
EXPECT_JP_JAN = {'CTS': 25, 'FSZ': 31, 'KOJ': 33, 'KMJ': 38, 'MYJ': 32, 'TAK': 36, 'MMY': 23}
# 2026-11-26 5번 재실측으로 KOJ +10 · KMJ +9 · MYJ +9 · TAK +10 = 38칸이 더해졌습니다(평일 2박·주말 1월).
# 일본 7노선 1월 주말형 5패턴 — 값 138칸 + 항공편 없음 2칸(다카마쓰 1/30 토~월 · 시즈오카 1/15 금~월)
EXPECT_JP_JAN_NOFLIGHT = {('TAK', '2027-01-30', '토~월'), ('FSZ', '2027-01-15', '금~월')}
EXPECT_JP_JAN_DAYTRIP = {'CTS': 2, 'FSZ': 9, 'KMJ': 6, 'TAK': 4}
# 2026-11-18 — 일본 7개 노선 2027년 2~6월 21주 × 7패턴 1,029칸 (실측 523 · 0건 303 · 요금 미공개 98 · 미조회 105)
# + 같은 날 5번 계정의 2027년 2월 보완본 — 2월 주말형 140칸을 다시 조회해 빈칸 7 + 판매편 0건 7 = 14칸을
#   값으로 채우고, 더 싼 최신 실측 73칸을 갱신 → 실측 523→537 · 0건 303→296 · 미조회 105→98
# 노선 → (실측 칸, 최저, 최고, 직항이 최저가인 칸). 2027-02-01~06-30 구간만 센다.
JP26 = ('KMJ', 'KOJ', 'FSZ', 'MYJ', 'TAK', 'MMY', 'CTS')
JP26_WEEKS = tuple((datetime.date(2027, 2, 4) + datetime.timedelta(days=7 * i)).isoformat()
                   for i in range(21))
JP26_WK = ('금~일', '토~월', '목~일', '금~월', '목~월')
JP26_DAY = ('토~토', '일~일')
JP26_PATS = JP26_WK + JP26_DAY
EXPECT_JP26 = {'KMJ': (52, 226000, 1028300, 7), 'KOJ': (117, 455800, 1600600, 2),
               'FSZ': (35, 274400, 1421100, 11), 'MYJ': (82, 240100, 3074400, 31),
               'TAK': (115, 226400, 2322200, 12), 'MMY': (31, 385500, 2888100, 0),
               'CTS': (143, 374303, 1144600, 38)}
# 노선 → {'주말형': (실측, 0건, 요금 미공개, 미조회), '당일치기': (...)} — 원문 노선별 특징·당일치기 표
EXPECT_JP26_STATUS = {
    'KMJ': {'주말형': (40, 0, 61, 4), '당일치기': (3, 0, 0, 39)},
    'KOJ': {'주말형': (105, 0, 0, 0), '당일치기': (2, 31, 0, 9)},
    'FSZ': {'주말형': (35, 68, 0, 2), '당일치기': (0, 24, 0, 18)},
    'MYJ': {'주말형': (73, 7, 25, 0), '당일치기': (0, 20, 11, 11)},
    'TAK': {'주말형': (105, 0, 0, 0), '당일치기': (0, 33, 0, 9)},
    'MMY': {'주말형': (31, 74, 0, 0), '당일치기': (0, 39, 0, 3)},
    'CTS': {'주말형': (105, 0, 0, 0), '당일치기': (38, 0, 1, 3)},
}
EXPECT_JP26_CELLS = len(JP26) * len(JP26_WEEKS) * len(JP26_PATS)      # 1,029칸
EXPECT_JP26_DEALS = 575      # 2026-11-27 5번 1조 순환(2027-02 가격표 ±7일) +38칸

EXPECT_JP26_NOSALE = 296
EXPECT_JP26_NOFARE = 98
EXPECT_JP26_BLANK = 98
# 이 달 실측 칸 수(출발일 기준) — 요약 md 와 같은 값
EXPECT_JP26_BY_MONTH = {'2027-02': 182, '2027-03': 135, '2027-04': 84,
                        '2027-05': 91, '2027-06': 83}
# 중국 G1(선양·다롄·광저우·샤먼) 2027년 2~6월 21주 × 5패턴 420칸(100%) — 노선별 최저·최고(원)
EXPECT_PUS4_FULL = {'SHE': (417700, 759800), 'DLC': (317400, 663000),
                    'CAN': (500700, 821600), 'XMN': (462400, 884000)}
# 중국 G2(연길·장가계·구이린·황산) 2027년 2~6월 21주 × 5패턴 420칸 완결 —
# 노선 → (값 칸, 최저, 최고). 황산은 판매편 0건 36칸을 떼고 값 69칸이다.
EXPECT_G2_FULL = {'YNJ': (105, 455700, 932000), 'DYG': (105, 686700, 904100),
                  'KWL': (105, 525900, 879900), 'TXN': (69, 783500, 2588000)}
EXPECT_PH4 = ('CEB', 'MNL', 'TAG', 'CRK')
EXPECT_SEA4 = ('PQC', 'BKI', 'KUL', 'VTE')
# 비엔티안 12/3 목~일·목~월은 항공편은 표시되나 이코노미 판매 가격이 없어 빈칸(0건 아님)
EXPECT_SEA4_MISSING = {('VTE', '2026-12-03', '목~일'), ('VTE', '2026-12-03', '목~월')}
# 2027년 3월 1주차(3/4~8) 기존 24개 노선 × 5패턴 120칸 완본(2026-11-18 5번 보고서)
EXPECT_MAR_W1_START = '2027-03-04'
# 2027년 3월 2주차(3/11~15) 기존 24개 노선 × 5패턴 120칸 완본(2026-11-18 5번 보고서)
EXPECT_MAR_W2_START = '2027-03-11'
# 3·4주차(3/18~22 · 3/25~29) 120칸씩 — 2026-11-18 추가 도착분. 1~4주차로 3월 480칸 완결.
EXPECT_MAR_W3_START = '2027-03-18'
EXPECT_MAR_W4_START = '2027-03-25'
EXPECT_MAR_W3_OVERALL = (245600, 553000)   # 최저 후쿠오카 3/20 토~월 · 최고 도쿄 3/18 목~일
EXPECT_MAR_W4_OVERALL = (278400, 701200)   # 최저 상하이 3/26 금~월 · 최고 치앙마이 3/26 금~월
EXPECT_MAR_W3_AVG = {'금~일': 396646, '토~월': 372962, '목~일': 394392,
                     '금~월': 380479, '목~월': 372646}
EXPECT_MAR_W4_AVG = {'금~일': 462850, '토~월': 474225, '목~일': 456408,
                     '금~월': 473550, '목~월': 468962}
EXPECT_MAR_W2_OVERALL = (238100, 519900)   # 최저 후쿠오카 3/11~15 목~월 · 최고 싱가포르 3/13~15 토~월
# (원문 '가장 비싼 노선'은 노선별 최저 기준으로 발리 496,600원이고, 칸 하나의 최고가는 싱가포르 519,900원)
# 2027년 3월 2주차 패턴 평균(원문 '한눈에') — 값이 통째로 밀리면 여기서 걸린다
EXPECT_MAR_W2_AVG = {'금~일': 388200, '토~월': 376275, '목~일': 392467, '금~월': 372612, '목~월': 374129}
EXPECT_MAR_W1_ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR',
                        'NKG', 'SGN', 'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX',
                        'DPS', 'KHH', 'RMQ', 'BJS')      # = EXPECT_JAN_ALL 과 같은 24개 노선
# 2027년 4월 1~4주차(4/1~5 · 4/8~12 · 4/15~19 · 4/22~26) 기존 24개 노선 × 5패턴 120칸씩
# (2026-11-18 5번 보고서 3건 + 2026-11-18~19 4주차 완본). 4주차로 4월 480칸(100%) 완결.
APR_WEEKS = (
    ('1주차', '2027-04-01', '2027-04-05', (299100, 2133000), 47,
     {'금~월': 524404, '목~일': 531117, '금~일': 534188, '토~월': 538488, '목~월': 578008}),
    ('2주차', '2027-04-08', '2027-04-12', (299100, 864500), 49,
     {'금~월': 486233, '토~월': 490192, '금~일': 491042, '목~월': 499771, '목~일': 500958}),
    ('3주차', '2027-04-15', '2027-04-19', (299000, 923000), 45,
     {'토~월': 490858, '금~월': 492833, '목~월': 493988, '목~일': 497004, '금~일': 506588}),
    ('4주차', '2027-04-22', '2027-04-26', (256200, 737300), 62,
     {'금~월': 460012, '토~월': 460329, '금~일': 465354, '목~일': 470496, '목~월': 474450}),
)
EXPECT_APR_TOTAL = 480
EXPECT_APR_LOW = {('PVG', '2027-04-03', '토~월'): 299100,
                  ('PVG', '2027-04-10', '토~월'): 299100,
                  ('PVG', '2027-04-17', '토~월'): 299000,
                  ('TPE', '2027-04-23', '금~월'): 256200,
                  ('MFM', '2027-04-23', '금~일'): 737300}
# 완본이 도착한 8노선 — 9주(목요일 기준) × 5패턴 45칸씩, 값 333 + 판매편 0건 27 = 360칸
EXPECT_FULL_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN', 'YNJ', 'DYG', 'KWL', 'TXN')
EXPECT_FULL_WEEKS = ('2026-12-03', '2026-12-10', '2026-12-17', '2026-12-24', '2026-12-31',
                     '2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
# 2026-11-18 추가 — 연길·장가계·구이린·황산 2027년 2~6월 금~일(2박) 21주 실측 주(금요일)
EXPECT_26M_WEEKS = ('2027-02-05', '2027-02-12', '2027-02-19', '2027-02-26',
                    '2027-03-05', '2027-03-12', '2027-03-19', '2027-03-26',
                    '2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23', '2027-04-30',
                    '2027-05-07', '2027-05-14', '2027-05-21', '2027-05-28',
                    '2027-06-04', '2027-06-11', '2027-06-18', '2027-06-25')
# 노선별로 채워진 금~일 칸 수(값) — 21주 전수, 황산은 4/2~6/25 13주가 판매편 0건
EXPECT_26M = {'YNJ': 21, 'DYG': 21, 'KWL': 21, 'TXN': 8}
# 노선별 금~일 실측 출발일(값) — 날짜가 밀리거나 바뀌면 여기서 걸린다
_W26M = EXPECT_26M_WEEKS
EXPECT_26M_DATES = {'YNJ': set(_W26M), 'DYG': set(_W26M), 'KWL': set(_W26M),
                    'TXN': set(_W26M) - {'2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23',
                                          '2027-04-30', '2027-05-07', '2027-05-14', '2027-05-21',
                                          '2027-05-28', '2027-06-04', '2027-06-11', '2027-06-18',
                                          '2027-06-25'}}
# 2026-11-18 추가 — 연길·장가계·구이린·황산 2027년 2~6월 토~월(2박) 실측 출발일(값)
_W26M_SAT = ('2027-02-06', '2027-02-13', '2027-02-20', '2027-02-27',
             '2027-03-06', '2027-03-13', '2027-03-20', '2027-03-27',
             '2027-04-03', '2027-04-10', '2027-04-17', '2027-04-24',
             '2027-05-01', '2027-05-08', '2027-05-15', '2027-05-22', '2027-05-29',
             '2027-06-05', '2027-06-12', '2027-06-19', '2027-06-26')
# 토~월 21주 84칸 완성(2026-11-18 완주본) — 연길·장가계·구이린은 21주 전부 값,
# 황산은 3/27~6/26 14주만 값이고 2/6~3/20 7주는 판매편 0건
EXPECT_26M_SAT = {
    'YNJ': set(_W26M_SAT),
    'DYG': set(_W26M_SAT),
    'KWL': set(_W26M_SAT),
    'TXN': set(_W26M_SAT) - set(_W26M_SAT[:7]),
}
ROUTE_ORDER_26M = ('YNJ', 'DYG', 'KWL', 'TXN')
# 2026-11-18 추가 — 선양·다롄·광저우·샤먼 2027년 2~5월 2박(금~일·토~월) 실측 출발일
_PUS4_FRI = ('2027-02-05', '2027-02-12', '2027-02-19', '2027-02-26',
             '2027-03-05', '2027-03-12', '2027-03-19', '2027-03-26',
             '2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23', '2027-04-30',
             '2027-05-07', '2027-05-14', '2027-05-21', '2027-05-28',
             '2027-06-04', '2027-06-11', '2027-06-18', '2027-06-25')
_PUS4_SAT = ('2027-02-06', '2027-02-13', '2027-02-20', '2027-02-27',
             '2027-03-06', '2027-03-13', '2027-03-20', '2027-03-27',
             '2027-04-03', '2027-04-10', '2027-04-17', '2027-04-24',
             '2027-05-01', '2027-05-08', '2027-05-15', '2027-05-22', '2027-05-29',
             '2027-06-05', '2027-06-12', '2027-06-19', '2027-06-26')
_PUS4_THU = ('2027-02-04', '2027-02-11', '2027-02-18', '2027-02-25',
             '2027-03-04', '2027-03-11', '2027-03-18', '2027-03-25',
             '2027-04-01', '2027-04-08', '2027-04-15', '2027-04-22', '2027-04-29',
             '2027-05-06', '2027-05-13', '2027-05-20', '2027-05-27',
             '2027-06-03', '2027-06-10', '2027-06-17', '2027-06-24')
# 2026-11-18 완주본 — 4노선 × 21주 2박 168칸(금~일·토~월, 100%) + 목~일(3박) 84칸 + 금~월(3박) 84칸 100%.
# 목~월(4박)은 G1 갱신본에서 2/4~4/22 12주 48칸(4/29 이후 9주는 미조회).
_PUS4_4N = _PUS4_THU      # 2026-11-18 G1 완결본으로 목~월 4박도 21주 전부 실측(420/420칸)
EXPECT_PUS4_2N = {
    'SHE': {'목~일': set(_PUS4_THU), '금~일': set(_PUS4_FRI), '토~월': set(_PUS4_SAT),
            '금~월': set(_PUS4_FRI), '목~월': set(_PUS4_4N)},
    'DLC': {'목~일': set(_PUS4_THU), '금~일': set(_PUS4_FRI), '토~월': set(_PUS4_SAT),
            '금~월': set(_PUS4_FRI), '목~월': set(_PUS4_4N)},
    'CAN': {'목~일': set(_PUS4_THU), '금~일': set(_PUS4_FRI), '토~월': set(_PUS4_SAT),
            '금~월': set(_PUS4_FRI), '목~월': set(_PUS4_4N)},
    'XMN': {'목~일': set(_PUS4_THU), '금~일': set(_PUS4_FRI), '토~월': set(_PUS4_SAT),
            '금~월': set(_PUS4_FRI), '목~월': set(_PUS4_4N)},
}
# 2026-11-18 동남아 4노선 2027년 2~6월 21주 × 5패턴 420칸 완본 — 월별 칸 수
EXPECT_SEA_26M_BY_MONTH = {'2027-02': 80, '2027-03': 80, '2027-04': 96,
                           '2027-05': 84, '2027-06': 80}
# 2026-11-18 연길·장가계·구이린·황산 2027년 2~6월 목~일(3박) 21주 84칸 완주 — 4노선 모두 값
EXPECT_26M_THU = {code: set(_PUS4_THU) for code in ('YNJ', 'DYG', 'KWL', 'TXN')}
EXPECT_MONTHS = ('2026-12', '2027-01', '2027-02', '2027-03', '2027-04', '2027-05',
                 '2027-06', '2027-07', '2027-08', '2027-09', '2027-10', '2027-11')
EXPECT_FIRST_WEEK, EXPECT_LAST_WEEK = '2026-12-03', '2027-11-25'
# 2026.12~2027.02 고정 기준(1,638건 + 중국 신규 8노선 177건 + 중국 4노선 완본 162칸 + 2027년 2~6월 2박 287칸)
# 2027-02~05는 2026-11-18 선양·다롄·광저우·샤먼 2박 131칸 + 연길·장가계·구이린·황산 토~월 28칸을 더한 값
# 2027-02는 2026-11-18 2월 1주차(설 연휴 2/4~8) 5패턴 86칸을 더한 값(457 + 86 = 543)
# 2027-02~05는 2026-11-18 2박·목~일·금~월 완주본까지 더한 값(2월 591 · 3월 229 · 4월 127 · 5월 116)
# 2026-12·2027-01·2027-03은 2026-11-18 필리핀 4노선 180칸 + 일본 7노선 90칸 + 3월 1주차 120칸
# + 동남아 4노선 178칸을 더한 값(12월 783+88+81+86=1,038 · 1월 797+92+9+92=990 · 3월 77+120=197)
# 2026-11-18 마지막 4건 반영 — 일본 12월 완결 +18(삿포로)·+3(1월), 3월 2주차 +120,
# 동남아 2~6월 420칸(2월 80·3월 80·4월 96·5월 84·6월 80), 중국 G1 목~월 48칸(2~4월 16씩)
# 2026-11-18 마지막 3건 — 필리핀 4노선 2~6월 420칸(2월 80·3월 80·4월 96·5월 84·6월 80)과
# 중국 G2 금~월 84칸(2월 16·3월 16·4월 20·5월 16·6월 16)을 더한 값
# 2026-11-18 마지막 2건 — 중국 G2 목~월 84칸(값 77: 2월 12·3월 13·4월 20·5월 16·6월 16)과
# 3월 3·4주차 240칸을 더한 값(2월 779→791 · 3월 538→791 · 4월 357→377 · 5월 316→332)
# 2026-11-18 일본 7노선 2027년 2월 보완본 — 빈칸 7 + 판매편 0건 7 = 14칸을 값으로 채워 2월 921→935
EXPECT_OLD_BY_MONTH = {'2026-12': 1225, '2027-01': 1229, '2027-02': 1003,
                       '2027-03': 926, '2027-04': 1037, '2027-05': 927}
# 2026-12·2027-02는 2026-11-27 5번 재실측(임박 주말·평일 2박·1조 순환 2027-02 159칸 가운데 창 안 새 칸 81개)을 더한 값
#   (2026-12 1212→1225 새 칸 13[다낭 당일치기 12/01~07] · 2027-02 935→1003 새 칸 68, 기존 54칸은 값만 바뀌어 건수 그대로)
# 2026-12·2027-01은 2026-11-26 5번 재실측(평일 2박·임박 주말 169칸 가운데 창 안 새 칸 58개)을 더한 값
#   (2026-12 1192→1212 새 칸 20 · 2027-01 1191→1229 새 칸 38, 기존 87칸은 값만 바뀌어 건수 그대로)
# 2026-12·2027-01은 2026-11-25 5번 재실측(임박 주말·평일 2박·당일치기 84칸 가운데 창 안 새 칸 32개)을 더한 값
#   (2026-12 1180→1192 새 칸 12 · 2027-01 1171→1191 새 칸 20, 기존 26칸은 값만 바뀌어 건수 그대로)
# 2026-12·2027-01은 2026-11-24 5번 재실측(임박 주말·당일치기·평일 2박 119칸 가운데 새 칸 74개)을 더한 값
#   (2026-12 1116→1180 새 칸 64 · 2027-01 1161→1171 새 칸 10, 기존 45칸은 값만 바뀌어 건수 그대로)
# 2026-12는 2026-11-23 5번 임박 주말·평일 재실측을 더한 값(1111→1116 — 새 칸 5개,
#   기존 13칸은 같은 (노선·출발일·패턴) 칸의 값만 바뀌어 건수는 그대로)
# 2027-05는 2026-11-19 기존 24개 노선 5월 3~4주차(5/13~17 · 5/20~24) 5패턴 240칸을 더한 값(423→663)
# 2027-04·05는 같은 날 기존 24개 노선 5월 1주차(4/29~5/3) 120칸을 더한 값(4월 941→1037 · 5월 663→687 —
#   출발일 4/29 48칸 · 4/30 48칸이 4월, 5/1 24칸이 5월)
# 2027-05는 이어 기존 24개 노선 5월 5주차(5/27~31) 120칸을 더한 값(687→807 — 출발일이 모두 5월)
# 2027-05는 다시 기존 24개 노선 5월 2주차(5/6~10) 120칸을 더한 값(807→927 — 출발일이 모두 5월)
# 2026-12·2027-01은 2026-11-18 일본 보완본(12월 +51칸·당일치기 4칸 · 1월 +9칸)과 중국 3박 완주본을 더한 값
# 2027.06~11 반영분(3개 원본: 260 + 73 + 53 = 386건)
# 2027-06은 2026-11-18 동남아 4노선 2~6월 420칸 가운데 6월 80칸을 더한 값(239+80)
# 2027-06은 필리핀 6월 80칸 + G2 금~월 6월 16칸을 더한 값(319 + 96)
# 2027-06은 다시 기존 24개 노선 6월 3주차(6/17~21) 120칸 중 새 칸 92를 더한 값(530→622)
# 2027-06은 다시 기존 24개 노선 6월 4주차(6/24~28) 120칸 중 새 칸 101을 더한 값(622→723)
# 2027-07은 2026-11-19 기존 24개 노선 7월 1주차(7/1~5) 120칸 중 새 칸 92를 더한 값(631→723 —
#   같은 날짜에 남아 있던 '가격표' 자리표시 28칸은 실측으로 교체했으므로 건수는 그대로)
# 2027-07~10은 2026-11-18 중국 8개 노선 2027년 7~11월 측정 465칸(7월 152 · 8월 127 · 9월 135 · 10월 51)
# 2027-07~09는 2026-11-18 필리핀 4개 노선 7~11월 실측(7월 64 · 8월 40 · 9월 22)을 더한 값
EXPECT_H2_BY_MONTH = {'2027-06': 886, '2027-07': 1106, '2027-08': 887,
                      '2027-09': 918, '2027-10': 700, '2027-11': 263}
# 2027-11 은 2026-11-21 B조 12개 노선 2027년 11월 2주(11/4~8 · 11/11~15) 빈칸 120칸을 더한
# 263 이다(143→263 — B조 12노선의 2027-11 보유분이 0칸이라 교체 없이 120칸이 모두 새 칸).
# 2027-10 은 2026-11-21 B조 12개 노선 10월 4주(10/7~11 · 10/14~18 · 10/21~25 ·
# 10/28~11/1) 빈칸 240칸을 더한 700 이다(460→700 — 이 격자에 앱이 이미 갖고 있던 칸이
# 0칸이라 교체 없이 240칸이 모두 새 칸이다. B조 10월 보유분은 9월 보고서에서 온 10/1·10/2
# 출발 36칸뿐이고 모두 이 네 주 밖이다).
# 2027-09·10 은 2026-11-20 B조 12개 노선 9월 5주(9/2~10/4) 빈칸 288칸을 출발일 기준으로
# 나눠 더한 값이다 — 9/30주 가운데 9/30 출발 24칸이 9월(654→918), 10/1·10/2 출발 24칸이
# 10월(436→460)이다(10/1 금~일 12칸은 앞선 조회분을 교체했으므로 건수는 그대로).
# 2027-08 은 2026-11-20 B조 12개 노선 8월 4주(8/5~30) 빈칸 228칸을 더한 887 이다(659→887 —
#   격자에 앞선 실시간 조회로만 있던 12칸(8/6 금~일)은 실측값으로 교체했으므로 건수는 그대로).
# 2027-07 은 2026-11-19 일본 7노선 7월 완결본(값 150칸)을 더한 595 에,
# 같은 날 필리핀 4노선 미조회 36칸을 더한 631 이고, A조 12노선 7월 3~5주차 134칸을 더한 857 이다.
#   삽8·9·10월에도 필리핀 40·66·32칸을 더했다.
# 2027-09·10 은 2026-11-19 일본 7노선 2027년 9~10월 병합분(출발일 기준 9월 127칸 · 10월 63칸)을 더했고,
# 2027-08 은 같은 날 일본 7노선 2027년 8월 병합분(120칸 — 시즈오카 20칸은 항공편 0건)을 더했다.
# 2027-11 은 같은 날 일본 7노선 2027년 11월 병합분(값 33칸 — 미오픈 87 · 시즈오카 판매편 0건 20)을
# 더한 34 다(기존 1칸은 후쿠오카 11/5~7).
# 2027-07은 2026-11-19 A조 12개 노선 7월 3~5주차(7/15~8/2) 실측분 134칸을 더한 857 이다(723→857 —
#   기존 가격표 자리표시 1칸은 재실측으로 교체했으므로 건수는 그대로).
# 2027-07은 같은 날 기존 24개 노선 7월 2주차(7/8~12) 120칸 중 새 칸 102를 더한 959 다(857→959 —
#   같은 주차에 남아 있던 '가격표' 자리표시 18칸은 실측으로 교체했으므로 건수는 그대로).
# 2027-08은 2026-11-19 A조 12개 노선 8월 4주 5패턴분 중 빈칸 205칸을 더한 659 다(454→659 —
#   이미 있던 3칸(마카오·상하이·타이베이 8/6 금~일)은 재실측으로 교체했으므로 건수는 그대로).
# 2027-09는 2026-11-20 A조 12개 노선 9월 5주(9/2~10/4) 빈칸 245칸 가운데 출발일이 9월인 229칸을
#   더한 654 이고(425→654), 2027-10은 같은 원본의 10/1·10/2 출발 16칸을 더한 205 였다(189→205 —
#   방콕 10/1 금~일 1칸은 재실측으로 교체했으므로 건수는 그대로).
# 2027-10은 2026-11-20 A조 12개 노선 10월 4주(10/7~11/1) 빈칸 231칸을 더한 436 이다(205→436 —
#   이번 원본은 교체 0칸이고, 격자에 이미 있던 9칸(금~일 10/8·10/15 8칸 + 후쿠오카 10/29)은 그대로).
EXPECT_H2 = {'weekend': 4665, 'day': 95, 'total': 4760}   # 주말형 2,587+205+245+102+231+109+163+147+228+288+240+120 · 당일치기 95
# 2027-11 은 2026-11-21 B조 12개 노선 11월 2주(11/4~8 · 11/11~15) 빈칸 120칸을 더한 값이다
# (주말형 4,545→4,665 · 총 4,640→4,760 — 교체 0칸).
# 2027-10 은 2026-11-21 B조 12개 노선 10월 4주(10/7~11/1) 빈칸 240칸을 더한 값이다
# (주말형 4,305→4,545 · 총 4,400→4,640 — 교체 0칸).
# 2027-07 은 2026-11-20 B조 12개 노선 7월 3주(7/15~8/2) 빈칸 147칸을 더한 1,106 이다(959→1,106 —
#   같은 격자의 가격표 자리표시 33칸은 실측값으로 교체했으므로 건수는 그대로).
# 2027-06 은 2026-11-19 기존 24개 노선 6월 3주차(6/17~21) 120칸 가운데 새 칸 92를 더하고(530→622),
# 같은 날 4주차(6/24~28) 120칸 가운데 새 칸 101을 더한 723 이었다
# (각 주차의 '가격표' 자리표시 28칸·19칸은 실측으로 교체 — 건수는 그대로).
# 2027-06 은 2026-11-19 기존 24개 노선 6월 1~2주차(6/3~7 · 6/10~14) 240칸 가운데 새 칸 163을
# 더한 886 이다(723→886 — 자리표시 77칸은 교체라 건수는 그대로).
EXPECT_NOSALE = {('FUK', '2027-11-12'), ('TYO', '2027-11-12'),
                 ('TYO', '2027-11-16'), ('FUK', '2027-11-20'),
                 ('MFM', '2027-11-13'), ('MFM', '2027-11-12'), ('MFM', '2027-11-11'),
                 ('CXR', '2027-11-12'), ('CXR', '2027-11-13'), ('CXR', '2027-11-11'),
                 ('KWL', '2026-12-05'), ('TXN', '2026-12-05'),   # 중국 2건: 같은 날 복편 0편
                 ('TAK', '2027-01-30'), ('FSZ', '2027-01-15')}   # 일본 1월: 가격표에도 항공편 없음
# 2026-11-18 황산 완본 — 토~월·금~월·목~월 9주 27칸은 조회 결과 판매편 0건(가격 아님)
EXPECT_NOSALE_TXN = {('TXN', d) for d in (
    '2026-12-05', '2026-12-04', '2026-12-03', '2026-12-12', '2026-12-11', '2026-12-10',
    '2026-12-19', '2026-12-18', '2026-12-17', '2026-12-26', '2026-12-25', '2026-12-24',
    '2027-01-02', '2027-01-01', '2026-12-31', '2027-01-09', '2027-01-08', '2027-01-07',
    '2027-01-16', '2027-01-15', '2027-01-14', '2027-01-23', '2027-01-22', '2027-01-21',
    '2027-01-30', '2027-01-29', '2027-01-28')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN
# 2026-11-18 황산 2027년 4/2~6/25 금~일 13주 연속 판매편 0건(값 아님)
EXPECT_NOSALE_TXN_26M = {('TXN', d) for d in (
    '2027-04-02', '2027-04-09', '2027-04-16', '2027-04-23',
    '2027-04-30', '2027-05-07', '2027-05-14', '2027-05-21', '2027-05-28',
    '2027-06-04', '2027-06-11', '2027-06-18', '2027-06-25')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M
# 2026-11-18 황산 2027년 2/6~3/20 토~월 7주 판매편 0건(값 아님, 3/27~6/26 14주는 정상 판매)
EXPECT_NOSALE_TXN_26M_SAT = {('TXN', d) for d in (
    '2027-02-06', '2027-02-13', '2027-02-20', '2027-02-27', '2027-03-06', '2027-03-13',
    '2027-03-20')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M_SAT
# 2026-11-18 중국 G2 4노선 2027년 2~6월 금~월(3박) — 황산은 2/5·2/12·2/19·2/26·3/5·3/12·3/19·4/2·4/30
# 9칸이 판매편 0건(2회 재조회 확인)이고 나머지 12칸은 값이다. 연길·장가계·구이린은 21칸 모두 값.
EXPECT_NOSALE_TXN_26M_FRIMON = {('TXN', d) for d in (
    '2027-02-05', '2027-02-12', '2027-02-19', '2027-02-26',
    '2027-03-05', '2027-03-12', '2027-03-19', '2027-04-02', '2027-04-30')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M_FRIMON
# 2026-11-18 G2 완결본 — 황산 목~월(4박) 2/4~3/18 7주가 판매편 0건(3/25부터 값).
EXPECT_NOSALE_TXN_26M_THUMON = {('TXN', d) for d in (
    '2027-02-04', '2027-02-11', '2027-02-18', '2027-02-25',
    '2027-03-04', '2027-03-11', '2027-03-18')}
EXPECT_NOSALE |= EXPECT_NOSALE_TXN_26M_THUMON
EXPECT_BOOKING_END = '2027-11-14'
EXPECT_BOOKING_SEA4 = '2027-09-14'      # 동남아 4노선(푸꾸옥·코타키나발루·쿠알라룸푸르·비엔티안) 판매창
EXPECT_BOOKING_PH4 = '2027-10-14'       # 필리핀 4노선(세부·마닐라·보홀·클락) 판매창
EXPECT_JAN_WEEKS = ('2027-01-07', '2027-01-14', '2027-01-21', '2027-01-28')
# 1월 4주 × 5패턴 전수 노선 — 기존 24개 노선(중국 신규 8노선은 연길만 전수, 나머지는 부분 조사)
EXPECT_JAN_ALL = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
                  'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
# 2026-11-18 2월 1주차(설 연휴 2/4~8) — 기존 24개 노선 × 5패턴 120칸 완결(목 2/4 · 금 2/5 · 토 2/6 출발)
EXPECT_FEB_W1_START = '2027-02-04'
EXPECT_FEB_W1_ROUTES = EXPECT_JAN_ALL
EXPECT_WEEKEND = ('목~일', '금~일', '토~월', '목~월', '금~월')
EXPECT_DAY = ('목~목', '금~금', '토~토', '일~일', '월~월')
EXPECT_DAYTRIP_MIN = 310
FL_WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
# ⑤ 항공 note 의 환승 대기 시간 — 앱(flDur)이 읽는 표기와 같은 식으로 뽑는다
FL_LAY = re.compile(r'환승\s*(\d+)시간\s*(?:(\d+)분)?')


def _rnd(x):
    """보고서·병합 도구와 같은 반올림(0.5 올림) — Python round() 는 짝수 반올림이라 다르다."""
    return int(decimal.Decimal(str(x)).quantize(0, rounding=decimal.ROUND_HALF_UP))

# 2027년 5월 3~4주차(5/13~17 · 5/20~24) 기존 24개 노선 × 5패턴 240칸 — 2026-11-19 6번 보고서 4건
# (일본·괌 60 · 중국 50 · 대만·홍콩·마카오 50 · 동남아 80). 240칸 모두 값이고 미오픈·0건·요금
# 미공개가 0칸이다. 주차 → (출발일 범위, (최저, 최고), 직항이 최저가인 칸, 패턴 평균)
MAY34_WEEKS = (
    ('3주차', '2027-05-13', '2027-05-17', (276160, 1033500), 40,
     {'토~월': 500981, '금~월': 510430, '금~일': 550387, '목~월': 590767, '목~일': 625078}),
    ('4주차', '2027-05-20', '2027-05-24', (266570, 783000), 43,
     {'토~월': 456831, '금~월': 462037, '목~일': 473249, '금~일': 481741, '목~월': 494095}),
)
EXPECT_MAY34_TOTAL = 240
EXPECT_MAY34_START, EXPECT_MAY34_END = '2027-05-13', '2027-05-24'
# 노선 → (그 두 주 안에서의 최저, 최고) — 원본 노선별 요약 표와 같은 값
EXPECT_MAY34_ROUTE = {
    'FUK': (363085, 670600), 'KIX': (426400, 673400), 'TYO': (542800, 795900),
    'NGO': (657700, 865203), 'OKA': (455900, 1033500), 'GUM': (658100, 888100),
    'PVG': (305942, 532342), 'BJS': (450400, 822300), 'NKG': (491718, 569500),
    'HGH': (472800, 699100), 'TAO': (499118, 686100),
    'TPE': (273396, 397830), 'HKG': (332370, 583546), 'KHH': (399700, 613400),
    'RMQ': (399700, 654600), 'MFM': (537900, 1002900),
    'BKK': (354411, 375172), 'CNX': (328401, 711300), 'DAD': (331573, 659700),
    'CXR': (352374, 581183), 'HAN': (266570, 377547), 'SGN': (295172, 352373),
    'SIN': (507376, 617191), 'DPS': (430222, 588184),
}
# 원본이 콕 집어 적은 칸(주차별 최저·최고, 노선 최저)
EXPECT_MAY34_LOW = {('TPE', '2027-05-14', '금~월'): 276160,
                    ('HAN', '2027-05-20', '목~월'): 266570,
                    ('OKA', '2027-05-13', '목~월'): 1033500,
                    ('OKA', '2027-05-21', '금~일'): 783000,
                    ('FUK', '2027-05-20', '목~월'): 363085}
# 최저가가 경유일 때 함께 적은 직항 최저가
EXPECT_MAY34_ALT = {('SIN', '2027-05-20', '목~일'): 642000,
                    ('TYO', '2027-05-14', '금~일'): 782900,
                    ('BJS', '2027-05-13', '목~일'): 617688}
# 상하이 5/13~17 1칸은 최저가만 표시되고 편성(직항/경유)이 확인되지 않아 via=null
EXPECT_MAY34_UNKNOWN = 1

# 2027년 5월 1주차(4/29~5/3) 기존 24개 노선 × 5패턴 120칸 — 2026-11-19 5번 보고서(부산출발-항공특가-2027년5월-1주차)
# 앱의 주차 선택은 목요일 기준이라 이 주는 '4월 5주(4/29~5/5)' 로 표시된다. 120칸 모두 값이고
# (미오픈·판매편 0건·요금 미공개 0칸), 원문이 패턴 평균·최저/최고·직항 칸 수·직항 최저 병기 수를 적었다.
MAY1_START, MAY1_END = '2027-04-29', '2027-05-03'
EXPECT_MAY1_TOTAL = 120
EXPECT_MAY1_OVERALL = (325800, 1067400)   # 최저 호찌민 4/29~5/2 · 최고 오키나와 4/30~5/3
EXPECT_MAY1_DIRECT = 44                   # 직항이 최저가인 칸
EXPECT_MAY1_ALT = 21                      # 최저가가 경유일 때 직항 최저가를 함께 적은 칸
EXPECT_MAY1_AVG = {'목~일': 556558, '목~월': 582871, '금~일': 627483,
                   '금~월': 661925, '토~월': 676333}
EXPECT_MAY1_ROUTE = {
    'FUK': (412100, 655200), 'KIX': (611500, 813200), 'TYO': (637900, 809800),
    'NGO': (745700, 982300), 'OKA': (534500, 1067400), 'GUM': (682600, 867400),
    'PVG': (403400, 610200), 'BJS': (450600, 527600), 'NKG': (600900, 685700),
    'HGH': (670400, 771200), 'TAO': (501900, 543500),
    'TPE': (401200, 446800), 'HKG': (520600, 597900), 'KHH': (709700, 841500),
    'RMQ': (745100, 978700), 'MFM': (685700, 797200),
    'BKK': (514600, 619300), 'CNX': (699000, 957500), 'DAD': (327300, 529200),
    'CXR': (375500, 566100), 'HAN': (385900, 561500), 'SGN': (325800, 385100),
    'SIN': (548800, 655200), 'DPS': (505300, 799300),
}
EXPECT_MAY1_LOW = {('SGN', '2027-04-29', '목~일'): 325800,
                   ('DAD', '2027-04-30', '금~일'): 327300,
                   ('OKA', '2027-04-30', '금~월'): 1067400,
                   ('PVG', '2027-05-01', '토~월'): 403400,
                   ('TAO', '2027-04-29', '목~월'): 501900}
EXPECT_MAY1_ALT_CELLS = {('PVG', '2027-04-30', '금~일'): 637000,
                         ('SIN', '2027-04-29', '목~일'): 744600,
                         ('TAO', '2027-04-29', '목~월'): 853600,
                         ('BJS', '2027-04-29', '목~일'): 511100,
                         ('CXR', '2027-04-29', '목~일'): None}

# 2027년 5월 5주차(5/27~5/31) 기존 24개 노선 × 5패턴 120칸 — 2026-11-19 6번 보고서 4장
# (일본·괌 30 · 중국 25 · 대만·홍콩·마카오 25 · 동남아 40). 120칸 모두 값이고(미오픈·판매편 0건·
# 요금 미공개 0칸), 앱의 주차 선택은 목요일 기준이라 '5월 4주(5/27~6/2)' 로 표시된다.
MAY5_START, MAY5_END = '2027-05-27', '2027-05-31'
EXPECT_MAY5_OVERALL = (282171, 849300)    # 최저 하노이 5/27~5/30 · 최고 마카오 5/27~5/30
EXPECT_MAY5_DIRECT = 45                   # 직항이 최저가인 칸
EXPECT_MAY5_AVG = {'금~월': 457678, '금~일': 465632, '토~월': 466150,
                   '목~일': 481303, '목~월': 491480}
EXPECT_MAY5_ROUTE = {
    'FUK': (333438, 429700), 'KIX': (411844, 453400), 'TYO': (542800, 587800),
    'NGO': (657700, 702700), 'OKA': (482400, 713000), 'GUM': (683100, 733100),
    'PVG': (286047, 404447), 'BJS': (412300, 499900), 'NKG': (481502, 569500),
    'HGH': (473637, 513100), 'TAO': (473400, 518700),
    'TPE': (288183, 302983), 'HKG': (315415, 383495), 'KHH': (399700, 633400),
    'RMQ': (399700, 460000), 'MFM': (749300, 849300),
    'BKK': (354361, 364871), 'CNX': (328401, 553300), 'DAD': (331573, 469900),
    'CXR': (352374, 378375), 'HAN': (282171, 323772), 'SGN': (295172, 295172),
    'SIN': (507209, 605230), 'DPS': (570134, 586523),
}
EXPECT_MAY5_LOW = {('HAN', '2027-05-27', '목~일'): 282171,
                   ('PVG', '2027-05-29', '토~월'): 286047,
                   ('TPE', '2027-05-27', '목~일'): 288183,
                   ('MFM', '2027-05-27', '목~일'): 849300,
                   ('FUK', '2027-05-27', '목~월'): 333438}
# 항저우 3칸 · 칭다오 4칸은 '최저가 탭 값(편성 미확인)' 이라 via=null
EXPECT_MAY5_UNKNOWN = 7

# 2027년 6월 3주차(6/17~6/21) 기존 24개 노선 × 5패턴 120칸 — 2026-11-19 5번 보고서
# (부산출발-항공특가-2027년6월-3주차, 2026-11-19 10:29~12:44 KST 실측). 120칸 모두 값이고
# (미오픈·판매편 0건·요금 미공개 0칸), 이 주차에 남아 있던 '가격표' 자리표시 28칸은
# 이번 실측값으로 교체했다(0박 당일치기 2칸은 이 조사 범위 밖이라 그대로).
JUN3_START, JUN3_END = '2027-06-17', '2027-06-21'
EXPECT_JUN3_TOTAL = 120
EXPECT_JUN3_OVERALL = (296600, 844300)    # 최저 홍콩 6/18~20 금~일 · 최고 괌 6/18~20·6/19~21
EXPECT_JUN3_DIRECT = 37                   # 직항이 최저가인 칸
EXPECT_JUN3_ALT = 33                      # 최저가가 경유일 때 직항 금액을 함께 적은 칸
EXPECT_JUN3_AVG = {'토~월': 478088, '목~월': 478829, '금~월': 483692,
                   '목~일': 485375, '금~일': 490150}
EXPECT_JUN3_ROUTE = {
    'FUK': (341500, 420400), 'KIX': (353800, 373400), 'TYO': (474600, 528400),
    'NGO': (620500, 683000), 'OKA': (493100, 639400), 'GUM': (658900, 844300),
    'PVG': (299000, 488900), 'BJS': (448500, 489100), 'NKG': (484200, 558500),
    'HGH': (483300, 488700), 'TAO': (471600, 516200),
    'TPE': (387500, 398300), 'HKG': (296600, 335900), 'KHH': (479300, 499000),
    'RMQ': (436100, 497300), 'MFM': (484200, 726200),
    'BKK': (411300, 411400), 'CNX': (538300, 622400), 'DAD': (487600, 488500),
    'CXR': (429000, 435800), 'HAN': (443600, 447000), 'SGN': (454000, 457600),
    'SIN': (424500, 430500), 'DPS': (421900, 428900),
}
EXPECT_JUN3_LOW = {('HKG', '2027-06-18', '금~일'): 296600,
                   ('PVG', '2027-06-19', '토~월'): 299000,
                   ('FUK', '2027-06-17', '목~월'): 341500,
                   ('GUM', '2027-06-18', '금~일'): 844300,
                   ('GUM', '2027-06-19', '토~월'): 844300}
EXPECT_JUN3_ALT_CELLS = {('PVG', '2027-06-18', '금~일'): 521600,
                         ('SIN', '2027-06-18', '금~일'): 917800,
                         ('TAO', '2027-06-19', '토~월'): 853600,
                         ('BJS', '2027-06-17', '목~월'): 552500}
# 이 주차 5패턴 전부 최저가가 직항인 노선(원문 '한눈에') — 후쿠오카·오사카·도쿄·나트랑·타이베이·홍콩
EXPECT_JUN3_ALLDIRECT = ('FUK', 'KIX', 'TYO', 'CXR', 'TPE', 'HKG')

# 2027년 6월 4주차(6/24~6/28) 기존 24개 노선 × 5패턴 120칸 — 2026-11-19 5번 보고서
# (부산출발-항공특가-2027년6월-4주차, 2026-11-19 12:45~14:05 KST 실측). 120칸 모두 값이고
# (미오픈·판매편 0건·요금 미공개 0칸), 이 주차에 남아 있던 '가격표' 자리표시 19칸은
# 이번 실측값으로 교체했다(0박 당일치기 2칸은 이 조사 범위 밖이라 그대로).
JUN4_START, JUN4_END = '2027-06-24', '2027-06-28'
EXPECT_JUN4_TOTAL = 120
EXPECT_JUN4_OVERALL = (299100, 820600)    # 최저 상하이 6/26~28 토~월 · 최고 괌 6/25~27 금~일
EXPECT_JUN4_DIRECT = 36                   # 직항이 최저가인 칸
EXPECT_JUN4_ALT = 34                      # 최저가가 경유일 때 직항 금액을 함께 적은 칸
EXPECT_JUN4_THIN = 35                     # '9석 미만' 표시가 붙은 칸
EXPECT_JUN4_AVG = {'목~일': 482688, '목~월': 488338, '금~일': 488950,
                   '토~월': 489612, '금~월': 490254}
EXPECT_JUN4_ROUTE = {
    'FUK': (309400, 352400), 'KIX': (353600, 380900), 'TYO': (481700, 527100),
    'NGO': (621300, 683800), 'OKA': (488100, 640500), 'GUM': (613300, 820600),
    'PVG': (299100, 489100), 'BJS': (448500, 489100), 'NKG': (492300, 497800),
    'HGH': (483700, 483700), 'TAO': (471400, 542700),
    'TPE': (382800, 387400), 'HKG': (300000, 333100), 'KHH': (481400, 532700),
    'RMQ': (435700, 677300), 'MFM': (559600, 723600),
    'BKK': (409300, 411300), 'CNX': (614500, 714000), 'DAD': (478600, 488600),
    'CXR': (431900, 432000), 'HAN': (444900, 448400), 'SGN': (453200, 453500),
    'SIN': (424500, 430200), 'DPS': (421900, 428900),
}
EXPECT_JUN4_LOW = {('PVG', '2027-06-26', '토~월'): 299100,
                   ('HKG', '2027-06-25', '금~일'): 300000,
                   ('HKG', '2027-06-26', '토~월'): 300000,
                   ('FUK', '2027-06-24', '목~일'): 309400,
                   ('FUK', '2027-06-24', '목~월'): 309400,
                   ('GUM', '2027-06-25', '금~일'): 820600,
                   ('GUM', '2027-06-26', '토~월'): 819500}
EXPECT_JUN4_ALT_CELLS = {('PVG', '2027-06-25', '금~일'): 507400,
                         ('SIN', '2027-06-25', '금~일'): 895900,
                         ('TAO', '2027-06-24', '목~일'): 853600,
                         ('BJS', '2027-06-24', '목~월'): 552500,
                         ('KHH', '2027-06-26', '토~월'): 864400}
# 이 주차 5패턴 전부 최저가가 직항인 노선 — 후쿠오카·오사카·도쿄·나트랑·타이베이·홍콩
EXPECT_JUN4_ALLDIRECT = ('FUK', 'KIX', 'TYO', 'CXR', 'TPE', 'HKG')
# 원문 '한눈에'는 직항 운임이 5패턴 모두 없는 노선을 15개로 적었지만, 칸별 원문에는 싱가포르·칭다오·
# 가오슝·베이징·호찌민·하노이·치앙마이가 '직항편우선 탭' 금액을 달고 있다. 칸별 값을 채택하면
# 5패턴 전부 직항 운임이 없는 노선은 아래 8개다(마카오는 부산 직항편 자체가 없음).
EXPECT_JUN4_NODIRECT = ('MFM', 'BKK', 'DAD', 'NKG', 'GUM', 'NGO', 'HGH', 'DPS')

# 2027년 7월 1주차(7/1~7/5) 기존 24개 노선 × 5패턴 120칸 — 2026-11-19 5번 보고서
# (부산출발-항공특가-2027년7월-1주차, 2026-11-19 13:52~14:57 KST 실측). 120칸 모두 값이고
# (미오픈·판매편 0건·요금 미공개 0칸), 이 주차에 남아 있던 '가격표' 자리표시 28칸은
# 이번 실측값으로 교체했다(0박 당일치기 칸 — 도쿄 7/4 일~일 1칸 — 은 이 조사 범위 밖이라 그대로).
# 7/1이 목요일이라 5패턴의 출발일이 7/1(목)과 7/2(금)에만 걸린다.
JUL1_START, JUL1_END = '2027-07-01', '2027-07-05'
EXPECT_JUL1_TOTAL = 120
EXPECT_JUL1_OVERALL = (299700, 819200)    # 최저 후쿠오카 7/1~4·7/1~5 · 최고 괌 7/2~4
EXPECT_JUL1_DIRECT = 38                   # 직항이 최저가인 칸
EXPECT_JUL1_ALT = 27                      # '직항편우선 탭' 금액을 함께 적은 칸
EXPECT_JUL1_THIN = 14                     # '9석 미만' 표시가 붙은 칸
EXPECT_JUL1_AVG = {'목~월': 506754, '목~일': 515125, '금~월': 524117,
                   '토~월': 524142, '금~일': 526275}
EXPECT_JUL1_ROUTE = {
    'PVG': (341000, 487200), 'FUK': (299700, 325000), 'KIX': (353800, 380300),
    'TYO': (482200, 535000), 'BKK': (428900, 431100), 'DAD': (495100, 501700),
    'CXR': (484900, 488500), 'TPE': (404300, 407300), 'HKG': (363100, 608100),
    'MFM': (633700, 766900), 'NKG': (507900, 553800), 'SGN': (472200, 472200),
    'SIN': (443900, 450000), 'GUM': (634400, 819200), 'NGO': (621200, 683700),
    'OKA': (500500, 640400), 'HGH': (508800, 641700), 'TAO': (501200, 506900),
    'HAN': (459900, 463500), 'CNX': (662700, 780000), 'DPS': (443300, 450700),
    'KHH': (558200, 712700), 'RMQ': (434400, 703600), 'BJS': (448600, 486500),
}
EXPECT_JUL1_LOW = {('FUK', '2027-07-01', '목~일'): 299700,
                   ('FUK', '2027-07-01', '목~월'): 299700,
                   ('PVG', '2027-07-03', '토~월'): 341000,
                   ('HKG', '2027-07-01', '목~월'): 363100,
                   # 홍콩 금~일은 두 번 재조회해 카드·날짜표 모두 608,100원으로 같았다(직항 우선 탭 647,600원)
                   ('HKG', '2027-07-02', '금~일'): 608100,
                   ('GUM', '2027-07-02', '금~일'): 819200,
                   ('GUM', '2027-07-03', '토~월'): 819000}
EXPECT_JUL1_ALT_CELLS = {('HKG', '2027-07-02', '금~일'): 647600,
                         ('SIN', '2027-07-02', '금~일'): 796800,
                         ('KHH', '2027-07-02', '금~일'): 863300,
                         ('BJS', '2027-07-01', '목~월'): 516300,
                         ('NGO', '2027-07-01', '목~일'): None}
# 이 주차 5패턴 전부 최저가가 직항인 노선 — 후쿠오카·오사카·도쿄·나트랑·타이베이
EXPECT_JUL1_ALLDIRECT = ('FUK', 'KIX', 'TYO', 'CXR', 'TPE')
# 5패턴 전부 직항 운임이 표시되지 않은 노선(원문 '한눈에'와 칸별 값이 같다 — 칭다오 포함 9개)
EXPECT_JUL1_NODIRECT = ('MFM', 'BKK', 'DAD', 'NKG', 'GUM', 'NGO', 'HGH', 'TAO', 'DPS')

# 2027년 7월 2주차(7/8~7/12) 기존 24개 노선 × 5패턴 120칸 — 2026-11-19 5번 보고서
# (부산출발-항공특가-2027년7월-2주차, 2026-11-19 15:00~15:47 KST 실측). 120칸 모두 값이고
# (미오픈·판매편 0건·요금 미공개 0칸), 이 주차에 남아 있던 '가격표' 자리표시 18칸은
# 이번 실측값으로 교체했다(0박 당일치기 칸 — 상하이 7/8 목~목 1칸 — 은 이 조사 범위 밖이라 그대로).
# 7/8이 목요일이라 5패턴의 출발일이 7/8(목)·7/9(금)·7/10(토)에 걸린다.
JUL2_START, JUL2_END = '2027-07-08', '2027-07-12'
EXPECT_JUL2_TOTAL = 120
EXPECT_JUL2_OVERALL = (272300, 840000)    # 최저 후쿠오카 7/8~12 목~월 · 최고 괌 7/9~11 금~일
EXPECT_JUL2_DIRECT = 39                   # 직항이 최저가인 칸
EXPECT_JUL2_ALT = 25                      # '직항편 우선' 금액을 함께 적은 칸
EXPECT_JUL2_THIN = 3                      # '9석 미만' 표시가 붙은 칸(괌 ③④⑤)
EXPECT_JUL2_NODIRECT = 55                 # '직항 운임 미표시' 칸(경유 최저 81칸 중 55칸)
EXPECT_JUL2_AVG = {'토~월': 495429, '금~월': 503775, '목~월': 508446,
                   '금~일': 509725, '목~일': 511825}
EXPECT_JUL2_ROUTE = {
    'PVG': (318500, 505800), 'FUK': (272300, 318900), 'KIX': (382900, 402600),
    'TYO': (480200, 541000), 'BKK': (429000, 431300), 'DAD': (499500, 501100),
    'CXR': (484400, 513300), 'TPE': (436400, 440000), 'HKG': (296500, 335500),
    'MFM': (613500, 735100), 'NKG': (503100, 553400), 'SGN': (470700, 471000),
    'SIN': (444000, 450000), 'GUM': (635600, 840000), 'NGO': (621200, 680900),
    'OKA': (494400, 643800), 'HGH': (503100, 620600), 'TAO': (494800, 504300),
    'HAN': (462000, 463900), 'CNX': (549600, 759100), 'DPS': (450600, 450600),
    'KHH': (552500, 593800), 'RMQ': (435400, 587600), 'BJS': (452500, 519900),
}
EXPECT_JUL2_LOW = {('FUK', '2027-07-08', '목~월'): 272300,
                   ('HKG', '2027-07-10', '토~월'): 296500,
                   ('PVG', '2027-07-10', '토~월'): 318500,
                   ('KIX', '2027-07-10', '토~월'): 382900,
                   ('BKK', '2027-07-09', '금~일'): 429000,
                   ('GUM', '2027-07-09', '금~일'): 840000,
                   ('GUM', '2027-07-10', '토~월'): 804500,
                   ('CNX', '2027-07-09', '금~일'): 759100}
EXPECT_JUL2_ALT_CELLS = {('PVG', '2027-07-09', '금~일'): 527400,
                         ('SIN', '2027-07-08', '목~월'): 787300,
                         ('SIN', '2027-07-10', '토~월'): 872200,
                         ('HAN', '2027-07-09', '금~일'): 480600,
                         ('KHH', '2027-07-09', '금~월'): 764600,
                         ('KHH', '2027-07-08', '목~월'): None,
                         ('RMQ', '2027-07-09', '금~월'): 646100,
                         ('BJS', '2027-07-08', '목~월'): 513900}
# 이 주차 5패턴 전부 최저가가 직항인 노선 — 후쿠오카·오사카·도쿄·나트랑·타이베이·홍콩
EXPECT_JUL2_ALLDIRECT = ('FUK', 'KIX', 'TYO', 'CXR', 'TPE', 'HKG')
# 5패턴 전부 직항 운임이 표시되지 않은 노선(원문 '한눈에'와 칸별 값이 같다 — 9개)
EXPECT_JUL2_NODIRECT_ROUTES = ('MFM', 'BKK', 'DAD', 'NKG', 'GUM', 'NGO', 'HGH', 'TAO', 'DPS')

# 부산 출발 A조 12개 노선 2027년 7월 3~5주차(7/15~19 · 7/22~26 · 7/29~8/2) — 2026-11-19 5번 보고서
# (잔여 3주 실측, 2026-11-19 21:07~2026-11-20 00:40 KST). 12노선 × 5패턴 × 3주 = 180칸 가운데
# 빈칸 134칸을 실측하고 1칸(후쿠오카 7/30~8/1 금~일 447,100→325,800원)을 다시 재 본 값으로
# 교체해 180칸이 모두 값이 됐다. 나머지 45칸은 앞선 가격표 조사분(편성 미확인, `via: null`).
# 0박 당일치기 2칸(후쿠오카 7/30 금~금 · 오사카 7/16 금~금)은 이 조사 범위 밖이라 그대로다.
GRP_A_JUL = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR',
             'NKG', 'SGN')
GRP_A_JUL_WEEKS = ('2027-07-15', '2027-07-22', '2027-07-29')
GRP_A_JUL_START, GRP_A_JUL_END = '2027-07-15', '2027-07-31'
GRP_A_JUL_TOTAL = 180          # 12노선 × 5패턴 × 3주가 모두 값
GRP_A_JUL_MEASURED = 135       # 이번 실측분(+ 재확인 1칸)
GRP_A_JUL_OVERALL = (300500, 913300)   # 후쿠오카 7/22~26 목~월 · 마카오 7/23~25 금~일
GRP_A_JUL_DIRECT = 60          # 실측분 가운데 직항이 최저가인 칸
GRP_A_JUL_ALT = 6              # 직항이 있어도 최저가가 경유라 직항 금액을 병기한 칸
GRP_A_JUL_THIN = 5             # '잔여 9석 미만' 표시가 붙은 칸
GRP_A_JUL_ROUTE_MEASURED = {'FUK': 11, 'KIX': 11, 'TYO': 10, 'TPE': 7, 'HKG': 9,
                            'MFM': 13, 'PVG': 14, 'BKK': 14, 'DAD': 14, 'CXR': 9,
                            'NKG': 13, 'SGN': 10}

# 부산 출발 B조 12개 노선 2027년 7월 3주(7/15~19 · 7/22~26 · 7/29~8/2) — 2026-11-20 5번 보고서
# (2026-11-20 05:29~07:11 KST 실측). 12노선 × 5패턴 × 3주 = 180칸을 전수 실측해 값 180칸
# (판매편 0건 0 · 편성 미확인 0)으로 채웠다. 앱이 '가격표 실측 · 직항/경유 미확인' 자리표시로
# 갖고 있던 33칸은 같은 노선·출발일·패턴의 실측값(항공사·경유지·소요·시각 포함)으로 교체했고
# (교체 칸 평균 667,282 → 652,297원), 빈칸 147칸을 새로 넣었다. 0박 당일치기는 이 조사
# 범위 밖이라 그대로다(이 격자 안에 0박 칸은 없다).
GRP_B_JUL = ('SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH',
             'RMQ', 'BJS')
GRP_B_JUL_WEEKS = ('2027-07-15', '2027-07-22', '2027-07-29')
GRP_B_JUL_START, GRP_B_JUL_END = '2027-07-15', '2027-07-31'
GRP_B_JUL_TOTAL = 180          # 12노선 × 5패턴 × 3주가 모두 금액
GRP_B_JUL_REPLACED = 33        # 가격표 자리표시 → 실측값 교체 칸
GRP_B_JUL_OVERALL = (433700, 995100)   # 타이중 7/15~19 금~일 · 괌 7/22~26 금~일
GRP_B_JUL_AVG = 654466         # 180칸 평균(반올림)
GRP_B_JUL_MEDIAN = 644200      # 180칸 중앙값
GRP_B_JUL_DIRECT = 22          # 최저가가 직항인 칸
# 노선: (칸수, 최저, 최고, 평균(반올림), 최저가가 직항인 칸)
GRP_B_JUL_ROUTE = {
    'SIN': (15, 448800, 803600, 651687, 3), 'GUM': (15, 637600, 995100, 789433, 0),
    'NGO': (15, 549600, 701700, 644200, 0), 'OKA': (15, 512500, 864400, 627340, 8),
    'HGH': (15, 501700, 683700, 600547, 0), 'TAO': (15, 500600, 584800, 553420, 0),
    'HAN': (15, 483000, 714200, 603500, 0), 'CNX': (15, 581100, 907400, 785367, 2),
    'DPS': (15, 442300, 833000, 634427, 0), 'KHH': (15, 632900, 759200, 691747, 0),
    'RMQ': (15, 433700, 968600, 734653, 5), 'BJS': (15, 447100, 652500, 537273, 4)}
GRP_B_JUL_GRID_ROUTE = {c: (v[1], v[2]) for c, v in GRP_B_JUL_ROUTE.items()}
GRP_B_JUL_MONTH = {'2027-07': 180}   # 출발일 기준 월별 칸수
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
GRP_B_JUL_WEEK = {'2027-07-15': (60, 36056400, 600940, 433700, 992700),
                  '2027-07-22': (60, 40173400, 669557, 452100, 995100),
                  '2027-07-29': (60, 41574100, 692902, 453200, 994700)}
GRP_B_JUL_PAT_AVG = {'금~일': 633850, '토~월': 702831, '목~일': 615272,
                     '금~월': 663789, '목~월': 656589}
# 10만원 단위 구간 — 원본 보고서의 8구간 표와 같다
GRP_B_JUL_BUCKET = {'30만원 미만': 0, '30만~40만원': 0, '40만~50만원': 18,
                    '50만~60만원': 49, '60만~70만원': 61, '70만~80만원': 23,
                    '80만~90만원': 19, '90만~100만원': 10, '100만원 이상': 0}
# 실측분의 장시간 경유 — 환승 12시간 이상 20시간 미만 15칸 · 20시간 이상 24칸
GRP_B_JUL_LONG = (15, 24)
# 총 소요 20시간 초과 칸(보고서 '최저가 기준 총 소요가 20시간을 넘는 칸 38칸')
GRP_B_JUL_OVER20 = 38
# 2회 환승 5칸 — 환승 시간 표기가 없어 note 에 경유지 2곳만 적었다
GRP_B_JUL_TWOHOP = {('HGH', '2027-07-15', '목~일'), ('HGH', '2027-07-22', '목~일'),
                    ('HGH', '2027-07-29', '목~일'), ('CNX', '2027-07-16', '금~월'),
                    ('CNX', '2027-07-17', '토~월')}
# 가격표 자리표시 33칸 — 이번 실측값으로 교체됐는지 본다(교체 뒤 금액)
GRP_B_JUL_REPLACE = {
    ('CNX', '2027-07-15', '목~월'): (638500, 684000),
    ('CNX', '2027-07-15', '목~일'): (664100, 695400),
    ('DPS', '2027-07-15', '목~월'): (428200, 442300),
    ('DPS', '2027-07-16', '금~월'): (454100, 740900),
    ('DPS', '2027-07-17', '토~월'): (989800, 568500),
    ('DPS', '2027-07-22', '목~일'): (536300, 588400),
    ('DPS', '2027-07-29', '목~월'): (566100, 782900),
    ('GUM', '2027-07-15', '목~일'): (652400, 684500),
    ('GUM', '2027-07-17', '토~월'): (987600, 985500),
    ('GUM', '2027-07-22', '목~일'): (832500, 638800),
    ('GUM', '2027-07-29', '목~일'): (596700, 638800),
    ('HAN', '2027-07-16', '금~월'): (486600, 483000),
    ('HGH', '2027-07-17', '토~월'): (593500, 648400),
    ('KHH', '2027-07-30', '금~월'): (742000, 711100),
    ('NGO', '2027-07-17', '토~월'): (709800, 665500),
    ('OKA', '2027-07-15', '목~월'): (689400, 611800),
    ('OKA', '2027-07-15', '목~일'): (628900, 616400),
    ('OKA', '2027-07-16', '금~월'): (759300, 864400),
    ('OKA', '2027-07-16', '금~일'): (810200, 667900),
    ('OKA', '2027-07-17', '토~월'): (816200, 727200),
    ('OKA', '2027-07-22', '목~일'): (506300, 512500),
    ('OKA', '2027-07-23', '금~월'): (654900, 645200),
    ('OKA', '2027-07-29', '목~월'): (596300, 587700),
    ('OKA', '2027-07-29', '목~일'): (542600, 532200),
    ('OKA', '2027-07-30', '금~월'): (635700, 648900),
    ('OKA', '2027-07-30', '금~일'): (641900, 595800),
    ('SIN', '2027-07-16', '금~월'): (459300, 448800),
    ('SIN', '2027-07-22', '목~일'): (544100, 653800),
    ('SIN', '2027-07-23', '금~월'): (1195100, 751000),
    ('SIN', '2027-07-29', '목~월'): (809800, 803600),
    ('SIN', '2027-07-30', '금~월'): (652200, 800900),
    ('TAO', '2027-07-23', '금~일'): (600000, 550600),
    ('TAO', '2027-07-30', '금~일'): (599900, 549100)}
GRP_B_JUL_REPLACE_AVG = (667282, 652297)   # 교체 33칸 평균(기존 → 신규)
# 이 원본이 쓴 note 꼴 — 출발-도착 시각이 괄호 앞 공백 뒤에 붙는다
GRP_B_JUL_NOTE = re.compile(r' \(\d\d:\d\d-\d\d:\d\d[^)]*\)$')

# 부산 출발 B조 12개 노선 2027년 8월 4주(8/5~9 · 8/12~16 · 8/19~23 · 8/26~30) — 2026-11-20 5번 보고서
# (2026-11-20 07:15~10:45 KST 실측). 12노선 × 5패턴 × 4주 = 240칸을 전수 실측해 값 240칸
# (판매편 0건 0 · 편성 미확인 0)으로 채웠다. 앱이 앞선 실시간 조회로만 갖고 있던 12칸(12노선
# 8/6 금~일)은 같은 노선·출발일·패턴의 실측값(항공사·경유지·소요·시각 포함)으로 교체했고
# (교체 칸 평균 670,858 → 662,067원), 빈칸 228칸을 새로 넣었다. 0박 당일치기는 이 조사
# 범위 밖이라 그대로다(이 격자 안에 0박 칸은 없다).
# 원본이 함께 적은 직항 요금 16칸은 `alt`(직항 최저 금액)로, `최단 …` 대안 22칸은 note 끝에 살렸다.
GRP_B_AUG = ('SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH',
             'RMQ', 'BJS')
GRP_B_AUG_WEEKS = ('2027-08-05', '2027-08-12', '2027-08-19', '2027-08-26')
GRP_B_AUG_START, GRP_B_AUG_END = '2027-08-05', '2027-08-31'
GRP_B_AUG_TOTAL = 240          # 12노선 × 5패턴 × 4주가 모두 금액
GRP_B_AUG_REPLACED = 12        # 앞선 실시간 조회분 → 실측값 교체 칸
GRP_B_AUG_OVERALL = (435200, 1087400)   # 타이중 8/26~30 금~일 · 괌 8/12~16 토~월
GRP_B_AUG_AVG = 645093         # 240칸 평균(반올림)
GRP_B_AUG_MEDIAN = 627000      # 240칸 중앙값 — 120·121번째(625,200 · 628,800)의 평균
GRP_B_AUG_DIRECT = 38          # 최저가가 직항인 칸
# 노선: (칸수, 최저, 최고, 평균(반올림), 최저가가 직항인 칸)
GRP_B_AUG_ROUTE = {
    'SIN': (20, 510300, 818400, 643800, 2), 'GUM': (20, 592000, 1087400, 759170, 0),
    'NGO': (20, 556400, 819400, 637765, 0), 'OKA': (20, 518000, 778600, 604805, 12),
    'HGH': (20, 501600, 703400, 615905, 0), 'TAO': (20, 484700, 624900, 531550, 0),
    'HAN': (20, 509200, 618300, 570080, 9), 'CNX': (20, 696400, 857600, 779600, 1),
    'DPS': (20, 495100, 832900, 624390, 0), 'KHH': (20, 590800, 782000, 714305, 2),
    'RMQ': (20, 435200, 1002800, 747475, 8), 'BJS': (20, 447100, 548100, 512275, 4)}
GRP_B_AUG_GRID_ROUTE = {c: (v[1], v[2]) for c, v in GRP_B_AUG_ROUTE.items()}
GRP_B_AUG_MONTH = {'2027-08': 240}   # 출발일 기준 월별 칸수
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
GRP_B_AUG_WEEK = {'2027-08-05': (60, 39919600, 665327, 447100, 995000),
                  '2027-08-12': (60, 41714400, 695240, 447100, 1087400),
                  '2027-08-19': (60, 36527300, 608788, 435700, 1002800),
                  '2027-08-26': (60, 36661100, 611018, 435200, 892100)}
GRP_B_AUG_PAT_AVG = {'목~일': 628248, '금~일': 627277, '토~월': 669829,
                     '금~월': 644113, '목~월': 656000}
# 10만원 단위 구간 — 원본 보고서의 8구간과 같다(칸 0인 구간 포함)
GRP_B_AUG_BUCKET = {'30만원 미만': 0, '30만~40만원': 0, '40만~50만원': 11,
                    '50만~60만원': 85, '60만~70만원': 75, '70만~80만원': 40,
                    '80만~90만원': 21, '90만~100만원': 6, '100만원 이상': 2}
# 장시간 경유 — 환승 12시간 이상 20시간 미만 19칸 · 20시간 이상 34칸
GRP_B_AUG_LONG = (19, 34)
GRP_B_AUG_MAX_LAY = 1420       # 가장 긴 환승 23시간 40분(칭다오 8/13 금~월 홍콩)
GRP_B_AUG_OVER20 = 49          # 총 소요가 20시간을 넘는 칸
# 원본이 함께 적은 직항 최저 금액(alt) 16칸 — 이번에 새로 붙인 칸
GRP_B_AUG_ALT = {
    ('SIN', '2027-08-26', '목~일'): 653800, ('SIN', '2027-08-27', '금~일'): 653800,
    ('SIN', '2027-08-26', '목~월'): 723700, ('HAN', '2027-08-26', '목~일'): 535000,
    ('HAN', '2027-08-28', '토~월'): 625200, ('CNX', '2027-08-19', '목~일'): 856300,
    ('CNX', '2027-08-19', '목~월'): 863500, ('CNX', '2027-08-26', '목~일'): 841700,
    ('CNX', '2027-08-26', '목~월'): 866400, ('KHH', '2027-08-20', '금~월'): 734400,
    ('BJS', '2027-08-19', '목~일'): 544800, ('BJS', '2027-08-20', '금~일'): 526600,
    ('BJS', '2027-08-20', '금~월'): 526600, ('BJS', '2027-08-19', '목~월'): 526600,
    ('BJS', '2027-08-26', '목~일'): 547200, ('BJS', '2027-08-26', '목~월'): 551600}
GRP_B_AUG_SHORTEST = 22        # `최단 …` 대안 일정을 note 에 덧붙인 칸
# 앞선 실시간 조회분 12칸 — 이번 실측값으로 교체됐는지 본다(기존 → 교체 뒤 금액)
GRP_B_AUG_REPLACE = {
    ('SIN', '2027-08-06', '금~일'): (707800, 693300),
    ('GUM', '2027-08-06', '금~일'): (1005000, 995000),
    ('NGO', '2027-08-06', '금~일'): (727300, 686900),
    ('OKA', '2027-08-06', '금~일'): (688700, 686600),
    ('HGH', '2027-08-06', '금~일'): (502800, 507300),
    ('TAO', '2027-08-06', '금~일'): (531900, 521800),
    ('HAN', '2027-08-06', '금~일'): (619400, 614100),
    ('CNX', '2027-08-06', '금~일'): (818600, 832400),
    ('DPS', '2027-08-06', '금~일'): (714200, 703000),
    ('KHH', '2027-08-06', '금~일'): (676700, 729600),
    ('RMQ', '2027-08-06', '금~일'): (530600, 527700),
    ('BJS', '2027-08-06', '금~일'): (527300, 447100)}
GRP_B_AUG_REPLACE_AVG = (670858, 662067)   # 교체 12칸 평균(기존 → 신규)
# 원본 note 꼴 — 출발-도착 시각(괄호 안)이 있고, 그 뒤에 직항 금액·최단 대안이 붙을 수 있다
GRP_B_AUG_NOTE = re.compile(r' \(\d\d:\d\d-\d\d:\d\d[^)]*\)')

# 부산 출발 B조 12개 노선 2027년 9월 5주(9/2~6 · 9/9~13 · 9/16~20 · 9/23~27 · 9/30~10/4) —
# 2026-11-20 5번 보고서(2026-11-20 10:46~13:57 KST 실측). 12노선 × 5패턴 × 5주 = 300칸을
# 전수 실측해 값 300칸(판매편 0건 0 · 편성 미확인 0)으로 채웠다. 앱이 앞선 조회로만 갖고 있던
# 12칸(12노선 2027-10-01 금~일 — 항공사·소요·시각 없이 '경유 · 직항 없음' 꼴)은 같은 노선·
# 출발일·패턴의 실측값(항공사·경유지·소요·시각 포함)으로 교체했고(교체 칸 평균
# 702,333 → 632,717원), 빈칸 288칸을 새로 넣었다. 0박 당일치기는 이 조사 범위 밖이다.
# 이 원본에는 '직항(항공사) N원' 꼴의 직항 최저 금액 표기가 없어 `alt` 를 만들지 않았고,
# 최저가 일정보다 짧은 대안 일정이 조회된 113칸은 note 끝에 `최단 …` 으로 살렸다.
GRP_B_SEP = ('SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH',
             'RMQ', 'BJS')
GRP_B_SEP_WEEKS = ('2027-09-02', '2027-09-09', '2027-09-16', '2027-09-23', '2027-09-30')
GRP_B_SEP_START, GRP_B_SEP_END = '2027-09-02', '2027-10-04'
GRP_B_SEP_TOTAL = 300          # 12노선 × 5패턴 × 5주가 모두 금액
GRP_B_SEP_REPLACED = 12        # 앞선 조회분 → 실측값 교체 칸(10/1 금~일)
GRP_B_SEP_OVERALL = (420800, 1101700)   # 발리 9/9~13 목~일 · 오키나와 9/30~10/4 금~월
GRP_B_SEP_AVG = 620993         # 300칸 평균(반올림)
GRP_B_SEP_MEDIAN = 602350      # 300칸 중앙값 — 150·151번째(598,500 · 606,200)의 평균
GRP_B_SEP_DIRECT = 34          # 최저가가 직항인 칸
# 노선: (칸수, 최저, 최고, 평균(반올림), 최저가가 직항인 칸)
GRP_B_SEP_ROUTE = {
    'SIN': (25, 423300, 842300, 551436, 2), 'GUM': (25, 593400, 1090700, 758132, 0),
    'NGO': (25, 491700, 874400, 665488, 0), 'OKA': (25, 519200, 1101700, 693360, 12),
    'HGH': (25, 486200, 873200, 630572, 0), 'TAO': (25, 464700, 689200, 553284, 0),
    'HAN': (25, 453000, 755200, 521648, 4), 'CNX': (25, 606200, 925800, 745900, 2),
    'DPS': (25, 420800, 941800, 561932, 0), 'KHH': (25, 476700, 899700, 637872, 0),
    'RMQ': (25, 436400, 897100, 627016, 9), 'BJS': (25, 447000, 630300, 505280, 5)}
GRP_B_SEP_GRID_ROUTE = {c: (v[1], v[2]) for c, v in GRP_B_SEP_ROUTE.items()}
# 출발일 기준 월별 칸수 — 9/30주는 9/30 출발 24칸이 9월, 10/1·10/2 출발 36칸이 10월이다
GRP_B_SEP_MONTH = {'2027-09': 264, '2027-10': 36}
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
GRP_B_SEP_WEEK = {'2027-09-02': (60, 32872700, 547878, 420900, 845000),
                  '2027-09-09': (60, 42089200, 701487, 420800, 1074600),
                  '2027-09-16': (60, 39387300, 656455, 429100, 1090700),
                  '2027-09-23': (60, 33533300, 558888, 428000, 832500),
                  '2027-09-30': (60, 38415500, 640258, 423300, 1101700)}
GRP_B_SEP_PAT_AVG = {'목~일': 608408, '금~일': 618908, '토~월': 637118,
                     '금~월': 629272, '목~월': 611260}
# 10만원 단위 구간
GRP_B_SEP_BUCKET = {'30만원 미만': 0, '30만~40만원': 0, '40만~50만원': 77,
                    '50만~60만원': 73, '60만~70만원': 76, '70만~80만원': 33,
                    '80만~90만원': 29, '90만~100만원': 8, '100만원 이상': 4}
# 장시간 경유 — 환승 12시간 이상 20시간 미만 43칸 · 20시간 이상 56칸(15시간 이상 85칸)
GRP_B_SEP_LONG = (43, 56)
GRP_B_SEP_LONG15 = 85
GRP_B_SEP_MAX_LAY = 1420       # 가장 긴 환승 23시간 40분(칭다오 9/3~6 · 9/4~6 금~월·토~월 홍콩)
GRP_B_SEP_OVER20 = 92          # 총 소요가 20시간을 넘는 칸
# 이 원본에는 직항 최저 금액 표기가 없어 alt 를 만들지 않았다(0칸)
GRP_B_SEP_ALT = {}
GRP_B_SEP_SHORTEST = 113       # `최단 …` 대안 일정을 note 에 덧붙인 칸
# 앞선 조회분 12칸 — 이번 실측값으로 교체됐는지 본다(기존 → 교체 뒤 금액)
GRP_B_SEP_REPLACE = {
    ('SIN', '2027-10-01', '금~일'): (438700, 423300),
    ('GUM', '2027-10-01', '금~일'): (953900, 833500),
    ('NGO', '2027-10-01', '금~일'): (936200, 797400),
    ('OKA', '2027-10-01', '금~일'): (764500, 955200),
    ('HGH', '2027-10-01', '금~일'): (851100, 522700),
    ('TAO', '2027-10-01', '금~일'): (636700, 582600),
    ('HAN', '2027-10-01', '금~일'): (465200, 453000),
    ('CNX', '2027-10-01', '금~일'): (947000, 920100),
    ('DPS', '2027-10-01', '금~일'): (436400, 427900),
    ('KHH', '2027-10-01', '금~일'): (923600, 647600),
    ('RMQ', '2027-10-01', '금~일'): (441100, 437300),
    ('BJS', '2027-10-01', '금~일'): (633600, 592000)}
GRP_B_SEP_REPLACE_AVG = (702333, 632717)   # 교체 12칸 평균(기존 → 신규)
# 원본 note 꼴 — 출발-도착 시각(괄호 안)이 있고, 그 뒤에 최단 대안이 붙을 수 있다
GRP_B_SEP_NOTE = re.compile(r' \(\d\d:\d\d-\d\d:\d\d[^)]*\)')

# 부산 출발 B조 12개 노선 2027년 10월 4주(10/7~11 · 10/14~18 · 10/21~25 · 10/28~11/1) —
# 2026-11-21 5번 보고서(2026-11-20 13:59 ~ 2026-11-21 08:55 KST 실측). 12노선 × 5패턴 × 4주 =
# 240칸을 전수 실측해 값 240칸(판매편 0건 0 · 편성 미확인 0)으로 채웠다. 이 격자(10/7~11/1 출발)에
# 앱이 이미 갖고 있던 칸은 0칸이다 — B조 12노선의 2027-10 보유분은 9월 보고서에서 온 10/1·10/2
# 출발 36칸뿐이고 모두 이 네 주 밖이라, 교체 0칸 · 새 칸 240칸이다. 0박 당일치기는 이 조사 범위 밖이다.
# 이 원본에는 '직항(항공사) N원' 꼴의 직항 최저 금액 표기가 없어 `alt` 를 만들지 않았고,
# 최저가 일정보다 짧은 대안 일정이 조회된 75칸은 note 끝에 `최단 …` 으로 살렸다.
GRP_B_OCT = ('SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH',
             'RMQ', 'BJS')
GRP_B_OCT_WEEKS = ('2027-10-07', '2027-10-14', '2027-10-21', '2027-10-28')
GRP_B_OCT_START, GRP_B_OCT_END = '2027-10-07', '2027-11-01'
GRP_B_OCT_TOTAL = 240          # 12노선 × 5패턴 × 4주가 모두 금액
GRP_B_OCT_REPLACED = 0         # 앞선 조회분 → 실측값 교체 칸(이 격자에 기존 칸 0칸)
GRP_B_OCT_OVERALL = (379100, 1086100)   # 오키나와 10/21~24 목~일 · 오키나와 10/8~11 금~월
GRP_B_OCT_AVG = 611788         # 240칸 평균(반올림)
GRP_B_OCT_MEDIAN = 615600      # 240칸 중앙값 — 120·121번째(615,600 · 615,600)의 평균
GRP_B_OCT_DIRECT = 26          # 최저가가 직항인 칸
# 노선: (칸수, 최저, 최고, 평균(반올림), 최저가가 직항인 칸)
GRP_B_OCT_ROUTE = {
    'SIN': (20, 422500, 626900, 479660, 0), 'GUM': (20, 630900, 941500, 770210, 0),
    'NGO': (20, 623100, 758700, 696880, 0), 'OKA': (20, 379100, 1086100, 680520, 11),
    'HGH': (20, 500500, 794600, 637590, 0), 'TAO': (20, 485900, 681000, 539290, 0),
    'HAN': (20, 453100, 655900, 501195, 1), 'CNX': (20, 579400, 941300, 684270, 3),
    'DPS': (20, 420100, 714200, 478475, 0), 'KHH': (20, 564200, 901700, 693755, 2),
    'RMQ': (20, 435400, 889500, 670690, 7), 'BJS': (20, 480100, 622600, 508920, 2)}
GRP_B_OCT_GRID_ROUTE = {c: (v[1], v[2]) for c, v in GRP_B_OCT_ROUTE.items()}
# 출발일 기준 월별 칸수 — 10/28주 금~월·목~월만 귀국일이 11/1이고 출발일은 모두 10월이다
GRP_B_OCT_MONTH = {'2027-10': 240}
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
GRP_B_OCT_WEEK = {'2027-10-07': (60, 40898600, 681643, 420900, 1086100),
                  '2027-10-14': (60, 33573700, 559562, 420100, 831800),
                  '2027-10-21': (60, 34247600, 570793, 379100, 864400),
                  '2027-10-28': (60, 38109200, 635153, 444200, 864400)}
GRP_B_OCT_PAT_AVG = {'목~일': 607160, '금~일': 596871, '토~월': 621681,
                     '금~월': 613190, '목~월': 620038}
# 10만원 단위 구간
GRP_B_OCT_BUCKET = {'30만원 미만': 0, '30만~40만원': 1, '40만~50만원': 69,
                    '50만~60만원': 44, '60만~70만원': 62, '70만~80만원': 40,
                    '80만~90만원': 15, '90만~100만원': 8, '100만원 이상': 1}
# 장시간 경유 — 환승 12시간 이상 20시간 미만 10칸 · 20시간 이상 41칸(15시간 이상 51칸)
GRP_B_OCT_LONG = (10, 41)
GRP_B_OCT_LONG15 = 51
GRP_B_OCT_MAX_LAY = 1420       # 가장 긴 환승 23시간 40분(칭다오 10/15 금~월 · 10/16 토~월 홍콩)
GRP_B_OCT_OVER20 = 51          # 총 소요가 20시간을 넘는 칸
# 이 원본에는 직항 최저 금액 표기가 없어 alt 를 만들지 않았다(0칸)
GRP_B_OCT_ALT = {}
GRP_B_OCT_SHORTEST = 75        # `최단 …` 대안 일정을 note 에 덧붙인 칸
GRP_B_OCT_TWOHOP = 6           # 두 번 환승이라 환승 시간 대신 경유지만 적은 칸
# 원본 note 꼴 — 출발-도착 시각(괄호 안)이 있고, 그 뒤에 최단 대안이 붙을 수 있다
GRP_B_OCT_NOTE = re.compile(r' \(\d\d:\d\d-\d\d:\d\d[^)]*\)')

# ── 2026-11-21 B조 12개 노선 2027년 11월 2주(11/4~8 · 11/11~15) 5패턴 120칸 ─────────────
# 원본: 5번 보고서(`0-2027-11-groupB-rest.csv` 120줄 + `1-2027-11-groupB-rest.md`),
# 2026-11-21 08:59~10:13 KST 실측(성인 1인 왕복 총액 · 유류·세금 포함). B조의 마지막 달이다.
# 12노선 × 5패턴 × 2주 = 120칸이 모두 금액이고 판매편 0건·편성 미확인·미실측 0칸이다.
# 이 격자(11/4~11/13 출발)에 앱이 앞서 갖고 있던 칸은 0칸(B조 12노선의 2027-11 보유분 0칸)이라
# 교체 없이 120칸을 새로 넣었다. 같은 두 주의 A조 12개 노선(값 109칸 + 판매편 0건 8칸)은 별개다.
# 이 원본에는 '직항(항공사) N원' 꼴의 직항 최저 금액 표기가 없어 `alt` 를 만들지 않았고,
# 최저가 일정보다 짧은 대안 일정이 조회된 41칸은 note 끝에 `최단 …` 으로 살렸다.
GRP_B_NOV = GRP_B_OCT
GRP_B_NOV_WEEKS = ('2027-11-04', '2027-11-11')
GRP_B_NOV_START, GRP_B_NOV_END = '2027-11-04', '2027-11-13'  # 11/4(목) ~ 11/11주 토~월(11/15)
GRP_B_NOV_TOTAL = 120          # 12노선 × 5패턴 × 2주가 모두 금액
GRP_B_NOV_REPLACED = 0         # 이 격자에 기존 칸 0칸
GRP_B_NOV_OVERALL = (442700, 992800)   # 타이중 11/4~7 목~일 · 가오슝 11/11~15 목~월
GRP_B_NOV_AVG = 688498         # 120칸 평균(반올림)
GRP_B_NOV_MEDIAN = 731000      # 120칸 중앙값 — 60·61번째(731,000 · 731,000)의 평균
GRP_B_NOV_DIRECT = 14          # 최저가가 직항인 칸(타이중 10 · 싱가포르 4)
# 노선: (칸수, 최저, 최고, 평균(반올림), 최저가가 직항인 칸)
GRP_B_NOV_ROUTE = {
    'SIN': (10, 685400, 926500, 809890, 4), 'GUM': (10, 662100, 865000, 759070, 0),
    'NGO': (10, 713400, 780700, 758480, 0), 'OKA': (10, 780900, 910900, 831180, 0),
    'HGH': (10, 731000, 743000, 735220, 0), 'TAO': (10, 475400, 545400, 517410, 0),
    'HAN': (10, 615100, 837900, 683040, 0), 'CNX': (10, 646400, 953100, 814890, 0),
    'DPS': (10, 595900, 860200, 700990, 0), 'KHH': (10, 567700, 992800, 722920, 0),
    'RMQ': (10, 442700, 445500, 444100, 10), 'BJS': (10, 482400, 488000, 484790, 0)}
GRP_B_NOV_GRID_ROUTE = {c: (v[1], v[2]) for c, v in GRP_B_NOV_ROUTE.items()}
# 출발일 기준 월별 칸수 — 두 주 모두 출발일이 11월이다
GRP_B_NOV_MONTH = {'2027-11': 120}
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
GRP_B_NOV_WEEK = {'2027-11-04': (60, 39472200, 657870, 442700, 897000),
                  '2027-11-11': (60, 43147600, 719127, 445500, 992800)}
GRP_B_NOV_PAT_AVG = {'목~일': 694846, '금~일': 698933, '토~월': 685771,
                     '금~월': 669638, '목~월': 693304}
# 10만원 단위 구간
GRP_B_NOV_BUCKET = {'30만원 미만': 0, '30만~40만원': 0, '40만~50만원': 21,
                    '50만~60만원': 15, '60만~70만원': 19, '70만~80만원': 36,
                    '80만~90만원': 23, '90만~100만원': 6, '100만원 이상': 0}
# 장시간 경유 — 환승 12시간 이상 20시간 미만 18칸 · 20시간 이상 12칸
# (6시간 이상 51칸 · 15시간 이상 27칸 · 12시간 이상 30칸)
GRP_B_NOV_LONG = (18, 12)
GRP_B_NOV_LONG6 = 51
GRP_B_NOV_LONG15 = 27
GRP_B_NOV_MAX_LAY = 1395       # 가장 긴 환승 23시간 15분(베이징 11/6 토~월 서울)
GRP_B_NOV_OVER20 = 29          # 총 소요가 20시간을 넘는 칸
# 이 원본에는 직항 최저 금액 표기가 없어 alt 를 만들지 않았다(0칸)
GRP_B_NOV_ALT = {}
GRP_B_NOV_SHORTEST = 41        # `최단 …` 대안 일정을 note 에 덧붙인 칸
GRP_B_NOV_TWOHOP = 2           # 두 번 환승이라 환승 시간 대신 경유지만 적은 칸(가오슝·치앙마이)
GRP_B_NOV_TWOHOP_CELLS = {('KHH', '2027-11-11', '목~월'), ('CNX', '2027-11-12', '금~일')}
# 원본 note 꼴 — 출발-도착 시각(괄호 안)이 있고, 그 뒤에 최단 대안이 붙을 수 있다
GRP_B_NOV_NOTE = GRP_B_OCT_NOTE

# 부산 출발 A조 12개 노선 2027년 8월 4주(8/5~9 · 8/12~16 · 8/19~23 · 8/26~30) — 2026-11-19 5번 보고서
# (2026-11-19 22:00~23:12 KST 실측). 12노선 × 5패턴 × 4주 = 240칸 가운데 빈칸 205칸을 실측하고,
# 앱에 이미 있던 3칸(마카오·상하이·타이베이 8/6 금~일)을 같은 조건으로 다시 조회한 값으로 교체해
# 240칸이 모두 값이다. 남은 32칸은 앞선 조사분 값이라 이번 조사 대상이 아니었다(추정·보간 없음).
# 원본 CSV 208줄 = 실측 205칸 + 대상 외 재확인 3칸.
GRP_A_AUG = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR',
             'NKG', 'SGN')
GRP_A_AUG_WEEKS = ('2027-08-05', '2027-08-12', '2027-08-19', '2027-08-26')
GRP_A_AUG_START, GRP_A_AUG_END = '2027-08-05', '2027-08-31'
GRP_A_AUG_TOTAL = 240          # 12노선 × 5패턴 × 4주가 모두 값
GRP_A_AUG_MEASURED = 208       # 이번 원본의 실측 208칸(재확인 3칸 포함)
GRP_A_AUG_OVERALL = (283700, 773400)   # 후쿠오카 8/19~23 금~월 · 마카오 8/12~16 금~일
GRP_A_AUG_AVG = 542357         # 실측 208칸 평균(반올림)
GRP_A_AUG_DIRECT = 97          # 실측분 가운데 직항이 최저가인 칸
GRP_A_AUG_MEASURED_BY_ROUTE = {'FUK': 6, 'KIX': 15, 'TYO': 16, 'TPE': 18, 'HKG': 18,
                               'MFM': 20, 'PVG': 20, 'BKK': 19, 'DAD': 19, 'CXR': 19,
                               'NKG': 19, 'SGN': 19}
# 병합 뒤 격자 20칸 기준 노선별 (최저, 최고) — 실측분 + 앞선 조사분 32칸
GRP_A_AUG_ROUTE = {'FUK': (283700, 528000), 'KIX': (399800, 623900),
                   'TYO': (472300, 736700), 'TPE': (445000, 465700),
                   'HKG': (357400, 544100), 'MFM': (594200, 773400),
                   'PVG': (297900, 541900), 'BKK': (492500, 737000),
                   'DAD': (520300, 771700), 'CXR': (519800, 680400),
                   'NKG': (502800, 657100), 'SGN': (506600, 665800)}
# 8/6(금) 재확인 3칸 — 앱 기입력 → 재실측
GRP_A_AUG_RECHECK = {('MFM', '2027-08-06', '금~일'): (767700, 763200),
                     ('PVG', '2027-08-06', '금~일'): (417500, 422400),
                     ('TPE', '2027-08-06', '금~일'): (468400, 464200)}

# 부산 출발 A조 12개 노선 2027년 9월 5주(9/2~6 · 9/9~13 · 9/16~20 · 9/23~27 · 9/30~10/4) — 2026-11-20 5번 보고서
# (2026-11-19 23:14~2026-11-20 00:40 KST 실측). 12노선 × 5패턴 × 5주 = 300칸 가운데 빈칸 245칸을 실측하고,
# 앱에 이미 있던 1칸(방콕 10/1 금~일)을 같은 조건으로 다시 조회한 값으로 교체해 300칸이 모두 금액을 가진다.
# 남은 54칸은 앞선 조사분 값이라 이번 조사 대상이 아니었다 — 그중 나트랑·호찌민 10/1 금~일 2칸은
# 금액만 있고 편성이 확인되지 않은 `via: null` 칸이라 그대로 둔다. 원본 CSV 246줄 = 실측 245칸 +
# 대상 외 재확인 1칸. 0박 당일치기 2칸(후쿠오카·타이베이 10/2 토~토)은 5패턴 격자 밖이라 그대로다.
GRP_A_SEP = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR',
             'NKG', 'SGN')
GRP_A_SEP_WEEKS = ('2027-09-02', '2027-09-09', '2027-09-16', '2027-09-23', '2027-09-30')
GRP_A_SEP_START, GRP_A_SEP_END = '2027-09-02', '2027-10-02'   # 9/2(목) ~ 9/30주 토~월(10/2)
GRP_A_SEP_TOTAL = 300          # 12노선 × 5패턴 × 5주가 모두 금액을 가짐
GRP_A_SEP_MEASURED = 246       # 이번 원본의 실측 246칸(재확인 1칸 포함)
GRP_A_SEP_OVERALL = (276600, 874200)   # 상하이 9/4 토~월 · 마카오 9/11 토~월 (실측 246칸)
GRP_A_SEP_AVG = 506318         # 실측 246칸 평균(반올림)
GRP_A_SEP_DIRECT = 110         # 실측분 가운데 직항이 최저가인 칸
GRP_A_SEP_MEASURED_BY_ROUTE = {'FUK': 12, 'KIX': 16, 'TYO': 16, 'TPE': 17, 'HKG': 22,
                               'MFM': 23, 'PVG': 23, 'BKK': 23, 'DAD': 23, 'CXR': 23,
                               'NKG': 24, 'SGN': 24}
# 실측분의 출발일 기준 월별 칸수(재확인 1칸 제외)
GRP_A_SEP_MONTH = {'2027-09': 229, '2027-10': 16}
# 병합 뒤 격자 25칸 기준 노선별 (최저, 최고) — 실측분 + 앞선 조사분 54칸
GRP_A_SEP_GRID_ROUTE = {'FUK': (323700, 532500), 'KIX': (359200, 654100),
                        'TYO': (471800, 812500), 'TPE': (312400, 450800),
                        'HKG': (283300, 651800), 'MFM': (555700, 896000),
                        'PVG': (276600, 619000), 'BKK': (408000, 779400),
                        'DAD': (462100, 708200), 'CXR': (458500, 771900),
                        'NKG': (486500, 657500), 'SGN': (449900, 694700)}
GRP_A_SEP_GRID_OVERALL = (276600, 896000)
# 10/1(금) 재확인 1칸 — 앱 기입력 → 재실측
GRP_A_SEP_RECHECK = {('BKK', '2027-10-01', '금~일'): (416600, 408000)}
# 이번 조사 대상이 아니었던 편성 미확인 2칸(금액만 있음)
GRP_A_SEP_UNKNOWN = (('CXR', '2027-10-01', '금~일'), ('SGN', '2027-10-01', '금~일'))
# 부산역(XMB) 출발 철도+항공 연계 상품 — 원본 비고를 note 에 남긴 2칸
GRP_A_SEP_XMB = (('SGN', '2027-09-16', '목~일'), ('SGN', '2027-09-16', '목~월'))
# 실측분의 장시간 경유 — 환승 12시간 이상 20시간 미만 8칸 · 20시간 이상 2칸(합 10칸이 12h+)
GRP_A_SEP_LONG = (10, 2)
# 실측분의 주차 평균(반올림) — 246칸 기준
GRP_A_SEP_WEEK_AVG = {'2027-09-02': 481581, '2027-09-09': 536347,
                      '2027-09-16': 526751, '2027-09-23': 479175,
                      '2027-09-30': 512663}
# 이번 원본이 쓴 note 꼴 — 출발-도착 시각이 괄호 앞 공백 뒤에 붙는다(앞선 조사분 54칸은
# '직항 1시간(14:50-16:00)' · '경유(서울)' 처럼 공백이 없어 걸러진다). XMB 연계 2칸은 시각 뒤에
# 문장이 더 붙으므로 따로 인정한다.
GRP_A_SEP_NOTE = re.compile(r' \(\d\d:\d\d-\d\d:\d\d[^)]*\)$')
GRP_A_SEP_XMB_NOTE = 'XMB(부산역) 출발 철도+항공 연계'

# 부산 출발 A조 12개 노선 2027년 10월 4주(10/7~11 · 10/14~18 · 10/21~25 · 10/28~11/1) — 2026-11-20 5번 보고서
# (2026-11-20 00:39~04:44 KST 실측). 12노선 × 5패턴 × 4주 = 240칸 가운데 빈칸 231칸을 실측해 넣고,
# 이미 값이 있던 9칸(후쿠오카·오사카·도쿄·타이베이의 10/8·10/15 금~일 8칸 + 후쿠오카 10/29 금~일)은
# 이번 조사 대상이 아니라 그대로 둔다 — 교체(재확인) 0칸. 원본 CSV 232줄 = 머리글 1 + 실측 231칸.
# 이 달 격자 안에 편성 미확인(`via: null`) 칸은 0칸이다. 10/1 출발 나트랑·호찌민 2칸이 `via: null`
# 인데 이번 격자(10/7~11/1) 밖(9월 달 9/30주)이라 GRP_A_SEP_UNKNOWN 이 그대로 본다.
GRP_A_OCT = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR',
             'NKG', 'SGN')
GRP_A_OCT_WEEKS = ('2027-10-07', '2027-10-14', '2027-10-21', '2027-10-28')
GRP_A_OCT_START, GRP_A_OCT_END = '2027-10-07', '2027-11-01'  # 10/7(목) ~ 10/28주 토~월(11/1)
GRP_A_OCT_TOTAL = 240          # 12노선 × 5패턴 × 4주가 모두 금액을 가짐
GRP_A_OCT_MEASURED = 231       # 이번 원본의 실측 231칸(교체 0칸)
GRP_A_OCT_OVERALL = (255600, 893100)   # 타이베이 10/29 금~일 · 마카오 10/8 금~일 (실측 231칸)
GRP_A_OCT_AVG = 495101         # 실측 231칸 평균(반올림)
GRP_A_OCT_DIRECT = 98          # 실측분 가운데 직항이 최저가인 칸
GRP_A_OCT_MEASURED_BY_ROUTE = {'FUK': 17, 'KIX': 18, 'TYO': 18, 'TPE': 18, 'HKG': 20,
                               'MFM': 20, 'PVG': 20, 'BKK': 20, 'DAD': 20, 'CXR': 20,
                               'NKG': 20, 'SGN': 20}
GRP_A_OCT_MONTH = {'2027-10': 231}   # 실측분의 출발일 기준 월별 칸수
# 병합 뒤 격자 20칸 기준 노선별 (최저, 최고) — 실측분 + 앞선 조사분 9칸
GRP_A_OCT_GRID_ROUTE = {'FUK': (257300, 601700), 'KIX': (339400, 655100),
                        'TYO': (528200, 812500), 'TPE': (230600, 562700),
                        'HKG': (283100, 491900), 'MFM': (561500, 893100),
                        'PVG': (297100, 638700), 'BKK': (407800, 598800),
                        'DAD': (464200, 568600), 'CXR': (485900, 739300),
                        'NKG': (506200, 686400), 'SGN': (450800, 574700)}
GRP_A_OCT_GRID_OVERALL = (230600, 893100)
# 이번 조사 대상이 아니어서 그대로 둔 9칸 — 금액이 바뀌지 않았는지 본다
GRP_A_OCT_KEEP = {('FUK', '2027-10-08', '금~일'): 524500,
                  ('FUK', '2027-10-15', '금~일'): 442400,
                  ('FUK', '2027-10-29', '금~일'): 601700,
                  ('KIX', '2027-10-08', '금~일'): 655100,
                  ('KIX', '2027-10-15', '금~일'): 510800,
                  ('TYO', '2027-10-08', '금~일'): 812500,
                  ('TYO', '2027-10-15', '금~일'): 597700,
                  ('TPE', '2027-10-08', '금~일'): 327600,
                  ('TPE', '2027-10-15', '금~일'): 230600}
# 실측분의 주차 평균(반올림) — 231칸 기준
GRP_A_OCT_WEEK_AVG = {'2027-10-07': 540041, '2027-10-14': 463111,
                      '2027-10-21': 455282, '2027-10-28': 523305}
# 실측분의 장시간 경유 — 12시간 이상이 4칸(그중 20시간 미만 3칸), 20시간 이상이 1칸
# (앱의 경유 12h+ / 20h+ 배지와 같은 식 — FL_LAY 로 환승 시간을 읽는다)
GRP_A_OCT_LONG = (4, 1)
# 이번 원본이 쓴 note 꼴 — 출발-도착 시각이 괄호 앞 공백 뒤에 붙는다(앞선 조사분 9칸은
# '직항(14:50-16:00)' · '경유(서울 1회) · 직항 없음' 처럼 공백이 없어 걸러진다).
GRP_A_OCT_NOTE = re.compile(r' \(\d\d:\d\d-\d\d:\d\d[^)]*\)$')

# ── 2026-11-20 A조 12개 노선 2027년 11월 2주(11/4~8 · 11/11~15) 5패턴 120칸 ─────────────
# 빈칸 117칸을 실측해 값 109칸을 넣고, 조회 결과 판매편이 없던 8칸(마카오 3 · 나트랑 5,
# 모두 11/11주)은 금액 대신 noSale(status: nosale)로 적었다. 앱에 이미 있던 3칸
# (후쿠오카 11/5~7 금~일 664,700원 + 후쿠오카·도쿄 11/12~14 금~일 판매편 0건)은 그대로 둔다.
# 격자는 값 110칸 + 판매편 0건 10칸 = 120칸이 모두 채워져 미조회 0칸이다.
GRP_A_NOV = GRP_A_OCT
GRP_A_NOV_WEEKS = ('2027-11-04', '2027-11-11')
GRP_A_NOV_START, GRP_A_NOV_END = '2027-11-04', '2027-11-15'  # 11/4(목) ~ 11/11주 토~월(11/15)
GRP_A_NOV_TOTAL = 120          # 12노선 × 5패턴 × 2주가 모두 값 또는 판매편 0건
GRP_A_NOV_MEASURED = 109       # 이번 원본의 금액 칸(교체 0칸)
GRP_A_NOV_NOSALE = 8           # 이번 원본의 판매편 0건(NA) 칸
GRP_A_NOV_OVERALL = (363000, 1659500)   # 홍콩 11/13 토~월 · 후쿠오카 11/13 토~월
GRP_A_NOV_AVG = 649015         # 실측 109칸 평균(반올림)
GRP_A_NOV_MEDIAN = 578900      # 실측 109칸 중앙값
GRP_A_NOV_DIRECT = 35          # 실측분 가운데 직항이 최저가인 칸
GRP_A_NOV_MEASURED_BY_ROUTE = {'FUK': 8, 'KIX': 10, 'TYO': 9, 'TPE': 10, 'HKG': 10,
                               'MFM': 7, 'PVG': 10, 'BKK': 10, 'DAD': 10, 'CXR': 5,
                               'NKG': 10, 'SGN': 10}
# 노선: (값 칸수, 판매편 0건 칸수, 최저, 최고, 평균) — 실측분 기준
GRP_A_NOV_ROUTE = {
    'FUK': (8, 0, 553000, 1659500, 996938), 'KIX': (10, 0, 628700, 1101200, 776240),
    'TYO': (9, 0, 507700, 837400, 661878), 'TPE': (10, 0, 425000, 487900, 443000),
    'HKG': (10, 0, 363000, 402800, 376840), 'MFM': (7, 3, 751700, 1039100, 876886),
    'PVG': (10, 0, 507500, 581600, 540470), 'BKK': (10, 0, 562900, 604200, 589760),
    'DAD': (10, 0, 526500, 571400, 549500), 'CXR': (5, 5, 1025300, 1031100, 1026640),
    'NKG': (10, 0, 545100, 850400, 580160), 'SGN': (10, 0, 604500, 908000, 697910)}
GRP_A_NOV_MONTH = {'2027-11': 109}   # 실측분의 출발일 기준 월별 칸수
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
GRP_A_NOV_WEEK = {'2027-11-04': (59, 35909900, 608642, 363200, 1031100),
                  '2027-11-11': (50, 34832700, 696654, 363000, 1659500)}
GRP_A_NOV_BUCKET = {'30만원 미만': 0, '30만~40만원': 9, '40만~50만원': 11,
                    '50만~60만원': 40, '60만~70만원': 22, '70만원 이상': 27}
GRP_A_NOV_PAT_AVG = {'금~일': 616640, '토~월': 682850, '목~일': 609513,
                     '금~월': 671091, '목~월': 663832}
# 이번 원본이 판매편 0건으로 적은 8칸 — 금액이 없고 상태가 nosale 이어야 한다
GRP_A_NOV_NA = {('MFM', '2027-11-13', '토~월'), ('MFM', '2027-11-12', '금~월'),
                ('MFM', '2027-11-11', '목~월'), ('CXR', '2027-11-12', '금~일'),
                ('CXR', '2027-11-13', '토~월'), ('CXR', '2027-11-11', '목~일'),
                ('CXR', '2027-11-12', '금~월'), ('CXR', '2027-11-11', '목~월')}
# 앞선 조사분 3칸 — 금액은 값, 판매편 0건 2칸은 상태만 그대로
GRP_A_NOV_KEEP = {('FUK', '2027-11-05', '금~일'): 664700}
GRP_A_NOV_KEEP_NOSALE = {('FUK', '2027-11-12', '금~일'), ('TYO', '2027-11-12', '금~일')}
# 병합 뒤 120칸 격자의 노선별 (최저, 최고) — 값 칸만 센다
GRP_A_NOV_GRID_ROUTE = {c: (v[2], v[3]) for c, v in GRP_A_NOV_ROUTE.items()}
GRP_A_NOV_GRID_OVERALL = (363000, 1659500)
# 실측분의 장시간 경유 — 12시간 이상이 15칸(그중 20시간 미만 13칸), 20시간 이상이 2칸
GRP_A_NOV_LONG = (15, 2)
# 이 원본이 쓴 note 꼴 — 출발-도착 시각이 괄호 앞 공백 뒤에 붙는다(앞선 조사분 1칸은
# '경유(서울 1시간 35분) · 직항 없음' 이라 걸러진다).
GRP_A_NOV_NOTE = GRP_A_OCT_NOTE

# ── 2026-11-19 기존 24개 노선 2027년 6월 1~2주차(6/3~7 · 6/10~14) 5패턴 240칸 ─────────────
# 원본 4건(일본·괌 60 · 중국 본토 50 · 대만·홍콩·마카오 50 · 동남아 80)이 240칸을 전수 실측했다
# (`NA`·미오픈 0칸). 앱에 '가격표' 자리표시(직항/경유 미확인)로 남아 있던 77칸은 같은 노선·
# 출발일·패턴의 실측값으로 바꾸고, 빈칸 163칸을 새로 넣었다 — 이 두 주 5패턴은 240/240칸이다.
# 이 격자 안의 0박 당일치기 4칸(후쿠오카·오사카 6/6 일~일 · 도쿄 6/4 금~금 · 오키나와
# 6/5 토~토)은 이번 5패턴 조사 범위 밖이라 그대로다.
GRP_A_JUN12 = ('FUK', 'KIX', 'TYO', 'NGO', 'OKA', 'GUM', 'PVG', 'BJS', 'NKG', 'HGH',
               'TAO', 'TPE', 'HKG', 'KHH', 'RMQ', 'MFM', 'BKK', 'CNX', 'DAD', 'CXR',
               'HAN', 'SGN', 'SIN', 'DPS')
GRP_A_JUN12_WEEKS = ('2027-06-03', '2027-06-10')
GRP_A_JUN12_START, GRP_A_JUN12_END = '2027-06-03', '2027-06-14'   # 6/3주 목~월(6/7) ~ 6/10주 목~월(6/14)
GRP_A_JUN12_TOTAL = 240         # 24노선 × 5패턴 × 2주가 모두 금액을 가짐
GRP_A_JUN12_REPLACED = 77       # 앱의 '가격표' 자리표시를 실측값으로 교체한 칸
GRP_A_JUN12_OVERALL = (262460, 849300)   # 타이베이 6/10~13 목~일 · 마카오 6/3~6·6/4~6 목~일
GRP_A_JUN12_AVG = 461518        # 240칸 평균(반올림)
GRP_A_JUN12_DIRECT = 91         # 최저가가 직항인 칸
GRP_A_JUN12_ALT = 36            # 직항 금액을 함께 적은 칸(최저가는 경유)
GRP_A_JUN12_UNKNOWN = (('TAO', '2027-06-04', '금~일'),)   # 최저가 탭 OTA 금액만 있어 편성 미확인
# 노선: (칸수, 최저, 최고, 평균(반올림)) — 실측 240칸 기준
GRP_A_JUN12_ROUTE = {
    'FUK': (10, 333438, 415000, 370844), 'KIX': (10, 351679, 381550, 366488),
    'TYO': (10, 482300, 564691, 513356), 'NGO': (10, 477275, 554381, 508785),
    'OKA': (10, 462000, 713000, 594660), 'GUM': (10, 645400, 733100, 685090),
    'PVG': (10, 285919, 444335, 386928), 'BJS': (10, 465865, 479900, 467893),
    'NKG': (10, 480736, 569500, 500361), 'HGH': (10, 480730, 689500, 545575),
    'TAO': (10, 473400, 548700, 505341), 'TPE': (10, 262460, 310760, 287266),
    'HKG': (10, 347070, 431200, 385830), 'KHH': (10, 399700, 506000, 439740),
    'RMQ': (10, 403100, 544100, 454300), 'MFM': (10, 538700, 849300, 747170),
    'BKK': (10, 354623, 365112, 357816), 'CNX': (10, 328401, 662100, 481064),
    'DAD': (10, 331573, 500995, 416204), 'CXR': (10, 351213, 378375, 357370),
    'HAN': (10, 281016, 299331, 285257), 'SGN': (10, 279571, 279571, 279571),
    'SIN': (10, 464200, 715439, 603370), 'DPS': (10, 434500, 586037, 536154)}
GRP_A_JUN12_GRID_ROUTE = {c: (v[1], v[2]) for c, v in GRP_A_JUN12_ROUTE.items()}
GRP_A_JUN12_MONTH = {'2027-06': 240}   # 출발일 기준 월별 칸수
# 주차: (칸수, 합, 평균(반올림), 최저, 최고)
GRP_A_JUN12_WEEK = {'2027-06-03': (120, 55604859, 463374, 279571, 849300),
                    '2027-06-10': (120, 55159460, 459662, 262460, 766700)}
GRP_A_JUN12_PAT_AVG = {'금~일': 462616, '토~월': 451693, '목~일': 476612,
                       '금~월': 443997, '목~월': 472672}
GRP_A_JUN12_BUCKET = {'30만원 미만': 29, '30만~40만원': 59, '40만~50만원': 70,
                      '50만~60만원': 43, '60만~70만원': 23, '70만원 이상': 16}
# 실측분의 장시간 경유 — 환승 12시간 이상 20시간 미만 6칸 · 20시간 이상 2칸
GRP_A_JUN12_LONG = (6, 2)

# ── 2026-11-18 중국 8개 노선 2027년 7~11월 (15주말 × 7패턴) ────────────────────────
# `noSale` 은 세 가지를 `status` 로 구분한다 — nosale(조회 결과 판매편 없음) ·
# nofare(운항편은 표시되나 요금 미게시) · unopened(예약창 밖, 항공사 스케줄 미개시).
H2_WEEKENDS = ('2027-07-02', '2027-07-09', '2027-07-16', '2027-07-23', '2027-07-30',
               '2027-08-06', '2027-08-13', '2027-08-20', '2027-08-27',
               '2027-09-03', '2027-09-10', '2027-09-17', '2027-09-24',
               '2027-10-01', '2027-10-08')
H2_ROUTES = ('SHE', 'DLC', 'CAN', 'XMN', 'YNJ', 'DYG', 'KWL', 'TXN')
# 원문 '노선별 특징' 의 요금 미공개·0건 칸 수(패턴)
H2_NOFARE_PATS = {'SHE': ('토~토', '일~일'), 'CAN': ('토~토',), 'XMN': ('토~토', '일~일'),
                  'DYG': ('금~일', '토~월', '금~월', '목~월'), 'KWL': tuple(EXPECT_WEEKEND),
                  'TXN': ('목~일', '토~월', '목~월')}
H2_NOSALE_PATS = {'DYG': ('토~토', '일~일'), 'KWL': ('토~토', '일~일'),
                  'TXN': ('토~토', '일~일', '금~일', '금~월')}
H2_PROBE_DATES = ('2027-10-15', '2027-11-12')     # 예약창(2027-10-13) 밖 확인용 금~일 조회
EXPECT_NOFARE_TOTAL = sum(len(v) * len(H2_WEEKENDS) for v in H2_NOFARE_PATS.values())
EXPECT_UNOPENED_CHINA = len(H2_ROUTES) * len(H2_PROBE_DATES)

# ── 2026-11-18 동남아 4개 노선 2027년 7~11월 (22주 × 5패턴 = 440칸) ─────────────
# 4노선 모두 마지막 판매일이 2027-09-14라 07-01~09-09 주 11주 220칸만 실측값이고,
# 09-16~11-25 주 11주 220칸은 미오픈(unopened)이다.
SEA4 = ('PQC', 'BKI', 'KUL', 'VTE')
SEA_H2_WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
                     for i in range(22))
SEA_H2_MEASURED = SEA_H2_WEEKS[:11]
SEA_H2_UNOPENED = SEA_H2_WEEKS[11:]
# 노선 → (실측 칸, 최저, 최고, 평균) — 원문 표와 절 머리 요약
EXPECT_SEA_H2 = {'PQC': (55, 423616, 780500, 624246), 'BKI': (55, 425000, 851200, 712273),
                 'KUL': (55, 411136, 436617, 421792), 'VTE': (55, 417896, 1365374, 608394)}
EXPECT_UNOPENED_SEA = len(SEA4) * len(SEA_H2_UNOPENED) * len(EXPECT_WEEKEND)

# ── 2026-11-18 필리핀 4개 노선 2027년 7~11월 (22주 × 5패턴 = 440칸) ──────────────
# 예약창 상한이 2027-10-14라 16주차(10/14 목 시작)~22주차 7주 140칸은 미오픈이고,
# 실측은 126칸(마닐라 57 · 클락 55 · 세부 12 · 보홀 2), 나머지 174칸은 미조회(—)다.
PH4_LAST_SALE = '2027-10-14'
PH4_H2_WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
                     for i in range(22))
# 노선 → (실측 칸, 최저, 최고, 최저가가 직항인 칸 수)
EXPECT_PH4_H2 = {'CEB': (75, 453652, 909700, 0), 'MNL': (75, 399291, 766600, 9),
                 'TAG': (75, 553300, 1004900, 0), 'CRK': (75, 409800, 894600, 0)}
EXPECT_PH4_H2_MISSING = {'CEB': 0, 'MNL': 0, 'TAG': 0, 'CRK': 0}   # 2026-11-19 174칸 전부 실측
EXPECT_PH4_H2_LOW = {('MNL', '2027-08-06', '금~일'): 406456,
                     ('CEB', '2027-07-01', '목~월'): 453652,
                     ('TAG', '2027-07-02', '금~일'): 553300,
                     ('CRK', '2027-09-03', '금~월'): 409800,
                     # 2026-11-19 미조회 174칸 보완본의 노선별 최저 칸
                     ('MNL', '2027-10-07', '목~일'): 399291,
                     ('CEB', '2027-07-08', '목~월'): 455543,
                     ('TAG', '2027-08-28', '토~월'): 558400,
                     ('CRK', '2027-09-23', '목~일'): 528800}
EXPECT_UNOPENED_PH4 = len(EXPECT_PH4) * len([w for w in PH4_H2_WEEKS if w >= PH4_LAST_SALE]) \
    * len(EXPECT_WEEKEND)
# 2026-11-19 일본 7노선 2027년 7월 — 시즈오카 25칸은 네 구간 조회 모두 "이용 가능한 항공편 없음"
# (원문이 예약창 미오픈으로 판단). 값 대신 `unopened` 로 적었고, 이 25칸을 미오픈 합계에 더한다.
JP_JUL_WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
                     for i in range(5))
EXPECT_UNOPENED_FSZ_JUL = len(JP_JUL_WEEKS) * len(EXPECT_WEEKEND)      # 25칸
EXPECT_UNOPENED_TOTAL = (EXPECT_UNOPENED_CHINA + EXPECT_UNOPENED_SEA + EXPECT_UNOPENED_PH4
                         + EXPECT_UNOPENED_FSZ_JUL)

# ── 2026-11-19 일본 7개 노선 2027년 9~10월 (9주 × 5패턴 = 315칸) ──────────────────
# 노선별 파일 구조가 달라(표·카드·불릿) 파서를 따로 두고, 원본이 스스로 적은
# 칸 수·최저·최고·직항 칸 수와 전수 대조했다. 값이 없는 칸은 세 갈래로 나뉜다 —
#   nosale(판매편 0건 34칸) · nofare(요금 미확인 4칸) · unopened(예약창 밖 87칸).
# 시즈오카는 9~10월 30칸이 전부 판매편 0건(2027년 하계 시즌 스케줄 미게시)이고 값이 0칸이다.
JP910 = ('KMJ', 'KOJ', 'FSZ', 'MYJ', 'TAK', 'MMY', 'CTS')
JP910_WEEKS = tuple((datetime.date(2027, 9, 2) + datetime.timedelta(days=7 * i)).isoformat()
                    for i in range(9))
# 노선 → (값, 판매편 0건, 요금 미확인, 예약창 밖, 최저, 최고, 직항이 최저가인 칸)
EXPECT_JP910 = {'KMJ': (23, 3, 4, 15, 393000, 1085031, 12),
                'KOJ': (30, 0, 0, 15, 599847, 995447, 0),
                'FSZ': (0, 30, 0, 15, None, None, 0),
                'MYJ': (30, 0, 0, 15, 635917, 816517, 0),
                'TAK': (30, 0, 0, 15, 770828, 1083174, 0),
                'MMY': (45, 0, 0, 0, 795900, 5743900, 0),
                'CTS': (32, 1, 0, 12, 374540, 1062100, 21)}
EXPECT_JP910_CELLS = len(JP910) * len(JP910_WEEKS) * len(EXPECT_WEEKEND)     # 315칸
EXPECT_JP910_PRICED = sum(v[0] for v in EXPECT_JP910.values())               # 190
EXPECT_JP910_NOSALE = sum(v[1] for v in EXPECT_JP910.values())               # 34
EXPECT_JP910_NOFARE = sum(v[2] for v in EXPECT_JP910.values())               # 4
EXPECT_JP910_UNOPENED = sum(v[3] for v in EXPECT_JP910.values())             # 87
# 원본이 적은 칸별 값 — 날짜·금액이 밀리면 여기서 걸린다(직항 최저가 병기 칸 포함)
EXPECT_JP910_LOW = {
    ('KMJ', '2027-09-09', '목~일'): 393000, ('KMJ', '2027-10-08', '금~월'): 1085031,
    ('KOJ', '2027-09-23', '목~월'): 599847, ('KOJ', '2027-10-01', '금~일'): 995447,
    ('MYJ', '2027-09-23', '목~월'): 635917, ('MYJ', '2027-10-08', '금~일'): 816517,
    ('TAK', '2027-09-04', '토~월'): 770828, ('TAK', '2027-10-08', '금~월'): 1083174,
    ('MMY', '2027-10-23', '토~월'): 795900, ('MMY', '2027-09-16', '목~일'): 5743900,
    ('CTS', '2027-09-23', '목~월'): 374540, ('CTS', '2027-10-16', '토~월'): 433900,
}
# ── 2026-11-19 일본 7개 노선 2027년 8월 (4주 × 5패턴 = 140칸) ──────────────────────
# 6개 노선 20칸 전부 값이고 시즈오카 20칸은 조회 결과 항공편 0건(2027년 하계 시즌 스케줄 미게시)이라
# `unopened` 로 적었다. 노선 → (값, 판매편 0건, 예약창 밖, 최저, 최고, 직항이 최저가인 칸)
JP8 = ('KMJ', 'KOJ', 'FSZ', 'MYJ', 'TAK', 'MMY', 'CTS')
JP8_WEEKS = tuple((datetime.date(2027, 8, 5) + datetime.timedelta(days=7 * i)).isoformat()
                  for i in range(4))
EXPECT_JP8 = {'CTS': (20, 0, 0, 573300, 928700, 16),
              'KOJ': (20, 0, 0, 589100, 2358600, 0),
              'FSZ': (0, 0, 20, None, None, 0),
              'MYJ': (20, 0, 0, 627800, 868100, 0),
              'TAK': (20, 0, 0, 712900, 1304000, 0),
              'MMY': (20, 0, 0, 603800, 2605000, 0),
              'KMJ': (20, 0, 0, 738100, 2110300, 11)}
EXPECT_JP8_CELLS = len(JP8) * len(JP8_WEEKS) * len(EXPECT_WEEKEND)        # 140칸
EXPECT_JP8_PRICED = sum(v[0] for v in EXPECT_JP8.values())                # 120
EXPECT_JP8_UNOPENED = sum(v[2] for v in EXPECT_JP8.values())              # 20
# 원본이 콕 집어 적은 칸(오봉 봉우리·노선별 최저)
EXPECT_JP8_LOW = {
    ('CTS', '2027-08-26', '목~월'): 573300, ('CTS', '2027-08-21', '토~월'): 573900,
    ('KOJ', '2027-08-21', '토~월'): 589100, ('KOJ', '2027-08-14', '토~월'): 2358600,
    ('KMJ', '2027-08-27', '금~월'): 738100, ('KMJ', '2027-08-13', '금~월'): 2110300,
    ('MYJ', '2027-08-19', '목~월'): 627800, ('TAK', '2027-08-20', '금~월'): 712900,
    ('MMY', '2027-08-21', '토~월'): 603800, ('MMY', '2027-08-13', '금~일'): 2605000,
}

# ── 2026-11-19 일본 7개 노선 2027년 11월 (4주 × 5패턴 = 140칸) ────────────────
# 값 33칸(구마모토·가고시마·마쓰야마·미야코지마 5씩 · 다카마쓰 6 · 삿포로 7) · 예약창 밖 87칸 ·
# 시즈오카 20칸은 판매편 0건(2027-28 겨울 시즌 스케줄 미게시)이다. 직항이 최저가인 칸은 0칸이다.
#       노선 → (값, 판매편 0건, 예약창 밖, 최저, 최고, 직항이 최저가인 칸)
JP11 = ('KMJ', 'KOJ', 'FSZ', 'MYJ', 'TAK', 'MMY', 'CTS')
JP11_WEEKS = tuple('2027-11-%02d' % d for d in (4, 11, 18, 25))
EXPECT_JP11 = {'KMJ': (5, 0, 15, 558700, 644100, 0),
               'KOJ': (5, 0, 15, 567700, 703400, 0),
               'FSZ': (0, 20, 0, None, None, 0),
               'MYJ': (5, 0, 15, 759000, 800700, 0),
               'TAK': (6, 0, 14, 757200, 1284100, 0),
               'MMY': (5, 0, 15, 1151900, 1304000, 0),
               'CTS': (7, 0, 13, 746600, 1313000, 0)}
EXPECT_JP11_CELLS = len(JP11) * len(JP11_WEEKS) * len(EXPECT_WEEKEND)     # 140칸
EXPECT_JP11_PRICED = sum(v[0] for v in EXPECT_JP11.values())              # 33
EXPECT_JP11_NOSALE = sum(v[1] for v in EXPECT_JP11.values())              # 20
EXPECT_JP11_UNOPENED = sum(v[2] for v in EXPECT_JP11.values())            # 87
# 원본이 콕 집어 적은 칸(노선별 최저·최고)
EXPECT_JP11_LOW = {
    ('KMJ', '2027-11-04', '목~월'): 558700, ('KMJ', '2027-11-05', '금~일'): 644100,
    ('KOJ', '2027-11-04', '목~월'): 567700, ('KOJ', '2027-11-05', '금~일'): 703400,
    ('MYJ', '2027-11-04', '목~일'): 759000, ('MYJ', '2027-11-04', '목~월'): 800700,
    ('TAK', '2027-11-04', '목~월'): 757200, ('TAK', '2027-11-11', '목~일'): 1284100,
    ('MMY', '2027-11-05', '금~일'): 1151900, ('MMY', '2027-11-04', '목~월'): 1304000,
    ('CTS', '2027-11-05', '금~월'): 746600, ('CTS', '2027-11-11', '목~일'): 1313000,
}

# 삿포로 2027-09-09 목~일은 최저가가 경유(자가환승) 578,222원이고 직항은 734,463원이다(alt)
EXPECT_JP910_ALT = {('CTS', '2027-09-09', '목~일'): 734463,
                    ('CTS', '2027-10-01', '금~일'): 924306}


def _h2_keys(pats_by_route):
    out = set()
    for code, pats in pats_by_route.items():
        for pat in pats:
            for fri in H2_WEEKENDS:
                thu = datetime.date.fromisoformat(fri) - datetime.timedelta(days=1)
                d = thu + datetime.timedelta(days=(FL_WD[pat[0]] - FL_WD['목']) % 7)
                out.add((code, d.isoformat(), pat))
    return out


EXPECT_NOSALE_H2 = _h2_keys(H2_NOSALE_PATS)
EXPECT_NOSALE_ALL = {(c, d) for (c, d) in EXPECT_NOSALE} | {
    (c, d) for (c, d, _p) in EXPECT_NOSALE_H2}
# 2026-11-18 중국 G2 4노선 2027년 2~6월 금~월(3박) 21주 — 21 금요일
_G2_FRIMON = tuple((datetime.date(2027, 2, 5) + datetime.timedelta(days=7 * i)).isoformat()
                   for i in range(21))


def _fl_nights(label):
    m = re.match(r'^([월화수목금토일])~([월화수목금토일])$', str(label))
    if not m:
        return None
    return (FL_WD[m.group(2)] - FL_WD[m.group(1)]) % 7


def check_flights(flights):
    """④ 항공 데이터 검사 — 노선 수·패턴·12개월 창·주차 연속성·1월 전수·당일치기·가격 유효성."""
    import datetime
    problems = []
    routes = flights.get('routes') or []
    if len(routes) != EXPECT_FLIGHTS:
        problems.append('항공 노선 %d개 (기대 %d개)' % (len(routes), EXPECT_FLIGHTS))
    pats = {p['label']: p for p in flights.get('patterns') or []}
    for label in EXPECT_WEEKEND:
        p = pats.get(label)
        if not p or not p.get('nights'):
            problems.append('주말형 패턴 %s 없음/박수 0' % label)
    for label in EXPECT_DAY:
        p = pats.get(label)
        if not p:
            problems.append('당일치기 패턴 %s 없음' % label)
        elif p.get('nights') != 0:
            problems.append('당일치기 패턴 %s 박수 %s (0이어야 함)' % (label, p.get('nights')))

    # 월·월 이동이 2026-12 ~ 2027-11 1년을 덮는지
    months = flights.get('months') or []
    if tuple(months) != EXPECT_MONTHS:
        problems.append('months %s (기대 2026-12~2027-11 12개)' % (months,))
    weeks = flights.get('weeks') or []
    if not weeks:
        problems.append('weeks 없음')
    else:
        if weeks[0].get('thu') != EXPECT_FIRST_WEEK or weeks[-1].get('thu') != EXPECT_LAST_WEEK:
            problems.append('weeks 범위 %s ~ %s (기대 %s ~ %s)' % (
                weeks[0].get('thu'), weeks[-1].get('thu'), EXPECT_FIRST_WEEK, EXPECT_LAST_WEEK))
        prev = None
        for w in weeks:
            if w.get('month') not in EXPECT_MONTHS:
                problems.append('week %s 의 month %s 이상' % (w.get('thu'), w.get('month')))
            if w.get('end') != (datetime.date.fromisoformat(w['thu']) +
                                datetime.timedelta(days=6)).isoformat():
                problems.append('week %s span 끝 %s 이상' % (w.get('thu'), w.get('end')))
            if prev is not None and (datetime.date.fromisoformat(w['thu']) -
                                     datetime.date.fromisoformat(prev)).days != 7:
                problems.append('week %s 가 이전 주 %s 와 7일 간격이 아님' % (w['thu'], prev))
            prev = w['thu']

    by_month = {}
    day_total = 0
    h2 = {'weekend': 0, 'day': 0}
    deal_keys = set()
    for r in routes:
        keys = {(d['date'], d['pattern']) for d in r['deals']}
        if len(keys) != len(r['deals']):
            problems.append('%s (노선·출발일·패턴) 중복' % r['code'])
        for thu in EXPECT_JAN_WEEKS:
            if r['code'] not in EXPECT_JAN_ALL:
                continue
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt, label) not in keys:
                    problems.append('1월 미실측 %s %s %s' % (r['code'], dt, label))
        if r['code'] in EXPECT_FEB_W1_ROUTES:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(EXPECT_FEB_W1_START) +
                      datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt, label) not in keys:
                    problems.append('2월 1주차 미실측 %s %s %s' % (r['code'], dt, label))
        if r['code'] in EXPECT_MAR_W1_ROUTES:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(EXPECT_MAR_W1_START) +
                      datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt, label) not in keys:
                    problems.append('3월 1주차 미실측 %s %s %s' % (r['code'], dt, label))
                dt2 = (datetime.date.fromisoformat(EXPECT_MAR_W2_START) +
                       datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt2, label) not in keys:
                    problems.append('3월 2주차 미실측 %s %s %s' % (r['code'], dt2, label))
                dt3 = (datetime.date.fromisoformat(EXPECT_MAR_W3_START) +
                       datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt3, label) not in keys:
                    problems.append('3월 3주차 미실측 %s %s %s' % (r['code'], dt3, label))
                dt4 = (datetime.date.fromisoformat(EXPECT_MAR_W4_START) +
                       datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt4, label) not in keys:
                    problems.append('3월 4주차 미실측 %s %s %s' % (r['code'], dt4, label))
        for d in r['deals']:
            tag = '%s %s %s' % (r['code'], d.get('date'), d.get('pattern'))
            if not (WINDOW_START <= d['date'] <= WINDOW_END):
                problems.append('%s 날짜 창 밖' % tag)
                break
            n = _fl_nights(d['pattern'])
            if n is None:
                problems.append('%s 패턴 형식 이상' % tag)
                break
            if not isinstance(d.get('price'), int) or d['price'] <= 0:
                problems.append('%s 가격이 양의 정수가 아님(추정·0원 금지): %r' % (tag, d.get('price')))
                break
            if d.get('back') != (datetime.date.fromisoformat(d['date']) +
                                 datetime.timedelta(days=n)).isoformat():
                problems.append('%s 귀국일 %s 가 %d박과 맞지 않음' % (tag, d.get('back'), n))
                break
            by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
            deal_keys.add((r['code'], d['date'], d['pattern']))
            if d['date'] >= '2027-06-01':
                h2['day' if n == 0 else 'weekend'] += 1
            if n == 0:
                day_total += 1
        meta = r.get('daytrip')
        if not meta or meta.get('status') not in ('ok', 'short', 'no', 'unk'):
            problems.append('%s daytrip 메타 없음/이상' % r['code'])
    if day_total < EXPECT_DAYTRIP_MIN:
        problems.append('당일치기 %d건 (기대 %d건 이상)' % (day_total, EXPECT_DAYTRIP_MIN))

    # 중국 신규 8노선: 노선 이름·건수가 원본 보고서와 같은지(조용한 누락·중복 방지)
    new_routes = {c: (city, n) for c, (city, n) in EXPECT_NEW_ROUTES.items()}
    by_code = {r['code']: r for r in routes}
    for code, (city, n) in new_routes.items():
        r = by_code.get(code)
        if not r:
            problems.append('중국 신규 노선 %s 없음' % code)
            continue
        if r.get('city') != city:
            problems.append('노선 %s 도시 이름 %r (기대 %s)' % (code, r.get('city'), city))
        if len(r['deals']) != n:
            problems.append('노선 %s 딜 %d건 (기대 %d건)' % (code, len(r['deals']), n))

    # 2026-11-18 신규 11노선(필리핀 4 · 일본 7) — 도시 이름·건수가 원본 보고서와 같은지
    for code, (city, n) in EXPECT_NEW_ROUTES2.items():
        r = by_code.get(code)
        if not r:
            problems.append('신규 노선 %s 없음' % code)
            continue
        if r.get('city') != city:
            problems.append('신규 노선 %s 도시 이름 %r (기대 %s)' % (code, r.get('city'), city))
        if len(r['deals']) != n:
            problems.append('신규 노선 %s 딜 %d건 (기대 %d건)' % (code, len(r['deals']), n))

    # 필리핀 4노선 완본 — 9주 × 5패턴 45칸이 값으로 채워졌는지(180/180, 0건 없음)
    for code in EXPECT_PH4:
        r = by_code.get(code)
        if not r:
            continue
        keys = {(d['date'], d['pattern']) for d in r['deals']}
        for thu in EXPECT_FULL_WEEKS:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                if (dt, label) not in keys:
                    problems.append('필리핀 완본 미채움 %s %s %s' % (code, dt, label))

    # 동남아 4노선 — 9주 × 5패턴 가운데 비엔티안 2칸만 빈칸(나머지는 값)
    for code in EXPECT_SEA4:
        r = by_code.get(code)
        if not r:
            continue
        keys = {(d['date'], d['pattern']) for d in r['deals']}
        for thu in EXPECT_FULL_WEEKS:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                if (code, dt, label) in EXPECT_SEA4_MISSING:
                    if (dt, label) in keys:
                        problems.append('동남아 빈칸이어야 할 칸에 값이 있음 %s %s %s'
                                        % (code, dt, label))
                    continue
                if (dt, label) not in keys:
                    problems.append('동남아 완본 미채움 %s %s %s' % (code, dt, label))

    # 중국 4노선 완본 — 9주 × 5패턴 45칸이 모두 '값' 또는 '판매편 0건'으로 채워졌는지(180/180)
    no_sale_keys = {(n.get('code'), n.get('date'), n.get('pattern')) for n in (flights.get('noSale') or [])}
    for code in EXPECT_FULL_ROUTES:
        r = by_code.get(code)
        if not r:
            continue
        keys = {(d['date'], d['pattern']) for d in r['deals']}
        for thu in EXPECT_FULL_WEEKS:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                if (dt, label) not in keys and (code, dt, label) not in no_sale_keys:
                    problems.append('중국 완본 미채움 %s %s %s' % (code, dt, label))
        cells = sum(1 for thu in EXPECT_FULL_WEEKS for label in EXPECT_WEEKEND
                    if (code, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat(), label)
                    in no_sale_keys)
        if code == 'TXN' and cells != 27:
            problems.append('황산 판매편 0건 %d칸 (기대 27칸)' % cells)
        if code != 'TXN' and cells:
            problems.append('%s 판매편 0건 %d칸 (기대 0칸)' % (code, cells))
    # 2027년 3월 2주차 — 24노선 × 5패턴 120칸의 최저·최고와 패턴 평균
    mar2 = [d for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES for d in r['deals']
            if '2027-03-11' <= d['date'] <= '2027-03-13']
    if len(mar2) != 120:
        problems.append('3월 2주차 %d칸 (기대 120칸)' % len(mar2))
    else:
        prices = [d['price'] for d in mar2]
        if (min(prices), max(prices)) != EXPECT_MAR_W2_OVERALL:
            problems.append('3월 2주차 최저·최고 %s (기대 %s)'
                            % ((min(prices), max(prices)), EXPECT_MAR_W2_OVERALL))
        for label, want in EXPECT_MAR_W2_AVG.items():
            ps = [d['price'] for d in mar2 if d['pattern'] == label]
            if round(sum(ps) / len(ps)) != want:
                problems.append('3월 2주차 %s 평균 %d (기대 %d)'
                                % (label, round(sum(ps) / len(ps)), want))
    # 2027년 3월 3·4주차 — 120칸씩, 최저·최고와 패턴 평균
    for label_w, start, end, overall, avg in (
            ('3주차', EXPECT_MAR_W3_START, '2027-03-22', EXPECT_MAR_W3_OVERALL, EXPECT_MAR_W3_AVG),
            ('4주차', EXPECT_MAR_W4_START, '2027-03-29', EXPECT_MAR_W4_OVERALL, EXPECT_MAR_W4_AVG)):
        rows = [d for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES for d in r['deals']
                if start <= d['date'] <= end]
        if len(rows) != 120:
            problems.append('3월 %s %d칸 (기대 120칸)' % (label_w, len(rows)))
            continue
        prices = [d['price'] for d in rows]
        if (min(prices), max(prices)) != overall:
            problems.append('3월 %s 최저·최고 %s (기대 %s)'
                            % (label_w, (min(prices), max(prices)), overall))
        for pat, want in avg.items():
            ps = [d['price'] for d in rows if d['pattern'] == pat]
            if round(sum(ps) / len(ps)) != want:
                problems.append('3월 %s %s 평균 %d (기대 %d)'
                                % (label_w, pat, round(sum(ps) / len(ps)), want))
    # 동남아 4노선 2027년 2~6월 420칸 — 월별 칸 수
    for m, want in EXPECT_SEA_26M_BY_MONTH.items():
        got = sum(1 for r in routes if r['code'] in EXPECT_SEA4 for d in r['deals']
                  if d['date'][:7] == m and '2027-02-01' <= d['date'] <= '2027-06-30')
        if got != want:
            problems.append('동남아 %s 2027년 2~6월 %d칸 (기대 %d칸)' % (m, got, want))
    # 2027년 4월 1~3주차 — 120칸씩(노선 24 × 5패턴). 최저·최고·직항 칸 수·패턴 평균이 원문과 같은지
    apr_cells = 0
    for label_w, start, end, overall, direct_want, avg in APR_WEEKS:
        rows = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
                for d in r['deals'] if start <= d['date'] <= end and d['pattern'] in EXPECT_WEEKEND]
        if len(rows) != 120:
            problems.append('4월 %s %d칸 (기대 120칸)' % (label_w, len(rows)))
            continue
        apr_cells += len(rows)
        prices = [d['price'] for d in rows]
        if (min(prices), max(prices)) != overall:
            problems.append('4월 %s 최저·최고 %s (기대 %s)'
                            % (label_w, (min(prices), max(prices)), overall))
        direct = sum(1 for d in rows if d.get('via') is False)
        if direct != direct_want:
            problems.append('4월 %s 직항 %d칸 (기대 %d칸)' % (label_w, direct, direct_want))
        for pat, want in avg.items():
            ps = [d['price'] for d in rows if d['pattern'] == pat]
            if len(ps) != 24:
                problems.append('4월 %s %s %d칸 (기대 24칸)' % (label_w, pat, len(ps)))
            elif round(sum(ps) / len(ps)) != want:
                problems.append('4월 %s %s 평균 %d (기대 %d)'
                                % (label_w, pat, round(sum(ps) / len(ps)), want))
    if apr_cells != EXPECT_APR_TOTAL:
        problems.append('4월 1~4주차 %d칸 (기대 %d칸)' % (apr_cells, EXPECT_APR_TOTAL))
    for (code, date, pat), price in EXPECT_APR_LOW.items():
        r = by_code.get(code)
        got = next((d['price'] for d in (r['deals'] if r else [])
                    if d['date'] == date and d['pattern'] == pat), None)
        if got != price:
            problems.append('4월 주차 최저 %s %s %s %s (기대 %d)'
                            % (code, date, pat, got, price))
    # 2027년 5월 3~4주차 — 기존 24개 노선 × 5패턴 240칸(100%)이 두 주 격자에 다 찼는지
    may34 = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
             for d in r['deals'] if EXPECT_MAY34_START <= d['date'] <= EXPECT_MAY34_END
             and d['pattern'] in EXPECT_WEEKEND]
    if len(may34) != EXPECT_MAY34_TOTAL:
        problems.append('5월 3~4주차 %d칸 (기대 %d칸)' % (len(may34), EXPECT_MAY34_TOTAL))
    else:
        for code, (lo, hi) in EXPECT_MAY34_ROUTE.items():
            ps = [d['price'] for d in may34 if d['code'] == code]
            if len(ps) != 10:
                problems.append('5월 %s %d칸 (기대 10칸)' % (code, len(ps)))
            elif (min(ps), max(ps)) != (lo, hi):
                problems.append('5월 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(ps), max(ps)), (lo, hi)))
        for label_w, start, end, overall, direct, avg in MAY34_WEEKS:
            rows = [d for d in may34 if start <= d['date'] <= end]
            if len(rows) != 120:
                problems.append('5월 %s %d칸 (기대 120칸)' % (label_w, len(rows)))
                continue
            ps = [d['price'] for d in rows]
            if (min(ps), max(ps)) != overall:
                problems.append('5월 %s 최저·최고 %s (기대 %s)'
                                % (label_w, (min(ps), max(ps)), overall))
            got_direct = sum(1 for d in rows if d.get('via') is False)
            if got_direct != direct:
                problems.append('5월 %s 직항이 최저가인 칸 %d (기대 %d)'
                                % (label_w, got_direct, direct))
            for pat, want in avg.items():
                v = [d['price'] for d in rows if d['pattern'] == pat]
                if len(v) != 24:
                    problems.append('5월 %s %s %d칸 (기대 24칸)' % (label_w, pat, len(v)))
                elif round(sum(v) / len(v)) != want:
                    problems.append('5월 %s %s 평균 %d (기대 %d)'
                                    % (label_w, pat, round(sum(v) / len(v)), want))
        unknown = [d for d in may34 if d.get('via') is None]
        if len(unknown) != EXPECT_MAY34_UNKNOWN:
            problems.append('5월 편성 미확인 칸 %d (기대 %d)'
                            % (len(unknown), EXPECT_MAY34_UNKNOWN))
        for (code, date, pat), price in EXPECT_MAY34_LOW.items():
            r = by_code.get(code)
            got = next((d['price'] for d in (r['deals'] if r else [])
                        if d['date'] == date and d['pattern'] == pat), None)
            if got != price:
                problems.append('5월 최저 칸 %s %s %s %s (기대 %d)'
                                % (code, date, pat, got, price))
        for (code, date, pat), alt in EXPECT_MAY34_ALT.items():
            r = by_code.get(code)
            got = next((d.get('alt') for d in (r['deals'] if r else [])
                        if d['date'] == date and d['pattern'] == pat), None)
            if got != alt:
                problems.append('5월 직항 최저 %s %s %s %s (기대 %s)'
                                % (code, date, pat, got, alt))
    # 2027년 5월 1주차(4/29~5/3 · 앱 주차 선택은 4월 5주 4/29~5/5) — 기존 24개 노선 × 5패턴 120칸
    may1 = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
            for d in r['deals'] if MAY1_START <= d['date'] <= MAY1_END
            and d['pattern'] in EXPECT_WEEKEND]
    if len(may1) != EXPECT_MAY1_TOTAL:
        problems.append('5월 1주차 %d칸 (기대 %d칸)' % (len(may1), EXPECT_MAY1_TOTAL))
    else:
        ps = [d['price'] for d in may1]
        if (min(ps), max(ps)) != EXPECT_MAY1_OVERALL:
            problems.append('5월 1주차 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), EXPECT_MAY1_OVERALL))
        got_direct = sum(1 for d in may1 if d.get('via') is False)
        if got_direct != EXPECT_MAY1_DIRECT:
            problems.append('5월 1주차 직항이 최저가인 칸 %d (기대 %d)'
                            % (got_direct, EXPECT_MAY1_DIRECT))
        got_alt = sum(1 for d in may1 if d.get('alt'))
        if got_alt != EXPECT_MAY1_ALT:
            problems.append('5월 1주차 직항 최저 병기 %d칸 (기대 %d칸)'
                            % (got_alt, EXPECT_MAY1_ALT))
        for code, (lo, hi) in EXPECT_MAY1_ROUTE.items():
            v = [d['price'] for d in may1 if d['code'] == code]
            if len(v) != 5:
                problems.append('5월 1주차 %s %d칸 (기대 5칸)' % (code, len(v)))
            elif (min(v), max(v)) != (lo, hi):
                problems.append('5월 1주차 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (lo, hi)))
        for pat, want in EXPECT_MAY1_AVG.items():
            v = [d['price'] for d in may1 if d['pattern'] == pat]
            if len(v) != 24:
                problems.append('5월 1주차 %s %d칸 (기대 24칸)' % (pat, len(v)))
            elif round(sum(v) / len(v)) != want:
                problems.append('5월 1주차 %s 평균 %d (기대 %d)'
                                % (pat, round(sum(v) / len(v)), want))
        for (code, date, pat), price in EXPECT_MAY1_LOW.items():
            got = next((d['price'] for d in may1 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != price:
                problems.append('5월 1주차 최저 칸 %s %s %s %s (기대 %d)'
                                % (code, date, pat, got, price))
        for (code, date, pat), alt in EXPECT_MAY1_ALT_CELLS.items():
            got = next((d.get('alt') for d in may1 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != alt:
                problems.append('5월 1주차 직항 최저 %s %s %s %s (기대 %s)'
                                % (code, date, pat, got, alt))
    # 2027년 5월 5주차(5/27~31 · 앱 주차 선택은 5월 4주 5/27~6/2) — 기존 24개 노선 × 5패턴 120칸
    may5 = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
            for d in r['deals'] if MAY5_START <= d['date'] <= MAY5_END
            and d['pattern'] in EXPECT_WEEKEND]
    if len(may5) != 120:
        problems.append('5월 5주차 %d칸 (기대 120칸)' % len(may5))
    else:
        ps = [d['price'] for d in may5]
        if (min(ps), max(ps)) != EXPECT_MAY5_OVERALL:
            problems.append('5월 5주차 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), EXPECT_MAY5_OVERALL))
        got_direct = sum(1 for d in may5 if d.get('via') is False)
        if got_direct != EXPECT_MAY5_DIRECT:
            problems.append('5월 5주차 직항이 최저가인 칸 %d (기대 %d)'
                            % (got_direct, EXPECT_MAY5_DIRECT))
        got_unknown = sum(1 for d in may5 if d.get('via') is None)
        if got_unknown != EXPECT_MAY5_UNKNOWN:
            problems.append('5월 5주차 편성 미확인 %d칸 (기대 %d칸)'
                            % (got_unknown, EXPECT_MAY5_UNKNOWN))
        for code, (lo, hi) in EXPECT_MAY5_ROUTE.items():
            v = [d['price'] for d in may5 if d['code'] == code]
            if len(v) != 5:
                problems.append('5월 5주차 %s %d칸 (기대 5칸)' % (code, len(v)))
            elif (min(v), max(v)) != (lo, hi):
                problems.append('5월 5주차 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (lo, hi)))
        for pat, want in EXPECT_MAY5_AVG.items():
            v = [d['price'] for d in may5 if d['pattern'] == pat]
            if len(v) != 24:
                problems.append('5월 5주차 %s %d칸 (기대 24칸)' % (pat, len(v)))
            elif round(sum(v) / len(v)) != want:
                problems.append('5월 5주차 %s 평균 %d (기대 %d)'
                                % (pat, round(sum(v) / len(v)), want))
        for (code, date, pat), price in EXPECT_MAY5_LOW.items():
            got = next((d['price'] for d in may5 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != price:
                problems.append('5월 5주차 최저 칸 %s %s %s %s (기대 %d)'
                                % (code, date, pat, got, price))
    # 2027년 6월 3주차(6/17~21) — 기존 24개 노선 × 5패턴 120칸(100%). 자리표시 칸이 남지 않았는지,
    # 최저·최고·직항 칸 수·패턴 평균·노선별 최저/최고가 원문과 같은지.
    jun3 = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
            for d in r['deals'] if JUN3_START <= d['date'] <= JUN3_END
            and d['pattern'] in EXPECT_WEEKEND]
    if len(jun3) != EXPECT_JUN3_TOTAL:
        problems.append('6월 3주차 %d칸 (기대 %d칸)' % (len(jun3), EXPECT_JUN3_TOTAL))
    else:
        if any(d.get('src') for d in jun3):
            problems.append('6월 3주차에 가격표 자리표시 칸이 남아 있습니다: %s'
                            % [(d['code'], d['date']) for d in jun3 if d.get('src')][:4])
        ps = [d['price'] for d in jun3]
        if (min(ps), max(ps)) != EXPECT_JUN3_OVERALL:
            problems.append('6월 3주차 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), EXPECT_JUN3_OVERALL))
        got_direct = sum(1 for d in jun3 if d.get('via') is False)
        if got_direct != EXPECT_JUN3_DIRECT:
            problems.append('6월 3주차 직항이 최저가인 칸 %d (기대 %d)'
                            % (got_direct, EXPECT_JUN3_DIRECT))
        got_alt = sum(1 for d in jun3 if d.get('alt'))
        if got_alt != EXPECT_JUN3_ALT:
            problems.append('6월 3주차 직항 금액 병기 %d칸 (기대 %d칸)'
                            % (got_alt, EXPECT_JUN3_ALT))
        unknown = [d for d in jun3 if d.get('via') is None]
        if unknown:
            problems.append('6월 3주차 편성 미확인 %d칸 (기대 0칸)' % len(unknown))
        for pat, want in EXPECT_JUN3_AVG.items():
            v = [d['price'] for d in jun3 if d['pattern'] == pat]
            if len(v) != 24:
                problems.append('6월 3주차 %s %d칸 (기대 24칸)' % (pat, len(v)))
            elif round(sum(v) / len(v)) != want:
                problems.append('6월 3주차 %s 평균 %d (기대 %d)'
                                % (pat, round(sum(v) / len(v)), want))
        for code, (lo, hi) in EXPECT_JUN3_ROUTE.items():
            v = [d['price'] for d in jun3 if d['code'] == code]
            if len(v) != 5:
                problems.append('6월 3주차 %s %d칸 (기대 5칸)' % (code, len(v)))
            elif (min(v), max(v)) != (lo, hi):
                problems.append('6월 3주차 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (lo, hi)))
        for code in EXPECT_JUN3_ALLDIRECT:
            v = [d for d in jun3 if d['code'] == code]
            if any(d.get('via') is not False for d in v):
                problems.append('6월 3주차 %s 5패턴이 모두 직항이어야 합니다' % code)
        for (code, date, pat), price in EXPECT_JUN3_LOW.items():
            got = next((d['price'] for d in jun3 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != price:
                problems.append('6월 3주차 최저 칸 %s %s %s %s (기대 %d)'
                                % (code, date, pat, got, price))
        for (code, date, pat), alt in EXPECT_JUN3_ALT_CELLS.items():
            got = next((d.get('alt') for d in jun3 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != alt:
                problems.append('6월 3주차 직항 금액 %s %s %s %s (기대 %s)'
                                % (code, date, pat, got, alt))
    # 2027년 6월 4주차(6/24~28) — 기존 24개 노선 × 5패턴 120칸(100%). 자리표시 칸이 남지 않았는지,
    # 최저·최고·직항 칸 수·직항 금액 병기·9석 미만·패턴 평균·노선별 최저/최고가 원문과 같은지.
    jun4 = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
            for d in r['deals'] if JUN4_START <= d['date'] <= JUN4_END
            and d['pattern'] in EXPECT_WEEKEND]
    if len(jun4) != EXPECT_JUN4_TOTAL:
        problems.append('6월 4주차 %d칸 (기대 %d칸)' % (len(jun4), EXPECT_JUN4_TOTAL))
    else:
        if any(d.get('src') for d in jun4):
            problems.append('6월 4주차에 가격표 자리표시 칸이 남아 있습니다: %s'
                            % [(d['code'], d['date']) for d in jun4 if d.get('src')][:4])
        ps = [d['price'] for d in jun4]
        if (min(ps), max(ps)) != EXPECT_JUN4_OVERALL:
            problems.append('6월 4주차 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), EXPECT_JUN4_OVERALL))
        got_direct = sum(1 for d in jun4 if d.get('via') is False)
        if got_direct != EXPECT_JUN4_DIRECT:
            problems.append('6월 4주차 직항이 최저가인 칸 %d (기대 %d)'
                            % (got_direct, EXPECT_JUN4_DIRECT))
        got_alt = sum(1 for d in jun4 if d.get('alt'))
        if got_alt != EXPECT_JUN4_ALT:
            problems.append('6월 4주차 직항 금액 병기 %d칸 (기대 %d칸)'
                            % (got_alt, EXPECT_JUN4_ALT))
        got_thin = sum(1 for d in jun4 if '잔여 9석 미만' in (d.get('note') or ''))
        if got_thin != EXPECT_JUN4_THIN:
            problems.append('6월 4주차 9석 미만 표시 %d칸 (기대 %d칸)'
                            % (got_thin, EXPECT_JUN4_THIN))
        unknown = [d for d in jun4 if d.get('via') is None]
        if unknown:
            problems.append('6월 4주차 편성 미확인 %d칸 (기대 0칸)' % len(unknown))
        for pat, want in EXPECT_JUN4_AVG.items():
            v = [d['price'] for d in jun4 if d['pattern'] == pat]
            if len(v) != 24:
                problems.append('6월 4주차 %s %d칸 (기대 24칸)' % (pat, len(v)))
            elif round(sum(v) / len(v)) != want:
                problems.append('6월 4주차 %s 평균 %d (기대 %d)'
                                % (pat, round(sum(v) / len(v)), want))
        for code, (lo, hi) in EXPECT_JUN4_ROUTE.items():
            v = [d['price'] for d in jun4 if d['code'] == code]
            if len(v) != 5:
                problems.append('6월 4주차 %s %d칸 (기대 5칸)' % (code, len(v)))
            elif (min(v), max(v)) != (lo, hi):
                problems.append('6월 4주차 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (lo, hi)))
        for code in EXPECT_JUN4_ALLDIRECT:
            v = [d for d in jun4 if d['code'] == code]
            if any(d.get('via') is not False for d in v):
                problems.append('6월 4주차 %s 5패턴이 모두 직항이어야 합니다' % code)
        for code in EXPECT_JUN4_NODIRECT:
            v = [d for d in jun4 if d['code'] == code]
            if any('직항편 없음' not in (d.get('note') or '') or d.get('alt') for d in v):
                problems.append('6월 4주차 %s 5패턴 전부 직항 운임 없음이어야 합니다' % code)
        for (code, date, pat), price in EXPECT_JUN4_LOW.items():
            got = next((d['price'] for d in jun4 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != price:
                problems.append('6월 4주차 최저 칸 %s %s %s %s (기대 %d)'
                                % (code, date, pat, got, price))
        for (code, date, pat), alt in EXPECT_JUN4_ALT_CELLS.items():
            got = next((d.get('alt') for d in jun4 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != alt:
                problems.append('6월 4주차 직항 금액 %s %s %s %s (기대 %s)'
                                % (code, date, pat, got, alt))
        for d in jun4:
            if d.get('via') is True and '총' not in (d.get('note') or ''):
                problems.append('6월 4주차 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in (d.get('note') or ''):
                problems.append('6월 4주차 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
    # 2027년 7월 1주차(7/1~5) — 기존 24개 노선 × 5패턴 120칸(100%). 자리표시 칸이 남지 않았는지,
    # 최저·최고·직항 칸 수·직항 금액 병기·9석 미만·패턴 평균·노선별 최저/최고가 원문과 같은지.
    jul1 = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
            for d in r['deals'] if JUL1_START <= d['date'] <= JUL1_END
            and d['pattern'] in EXPECT_WEEKEND]
    if len(jul1) != EXPECT_JUL1_TOTAL:
        problems.append('7월 1주차 %d칸 (기대 %d칸)' % (len(jul1), EXPECT_JUL1_TOTAL))
    else:
        if any(d.get('src') for d in jul1):
            problems.append('7월 1주차에 가격표 자리표시 칸이 남아 있습니다: %s'
                            % [(d['code'], d['date']) for d in jul1 if d.get('src')][:4])
        ps = [d['price'] for d in jul1]
        if (min(ps), max(ps)) != EXPECT_JUL1_OVERALL:
            problems.append('7월 1주차 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), EXPECT_JUL1_OVERALL))
        got_direct = sum(1 for d in jul1 if d.get('via') is False)
        if got_direct != EXPECT_JUL1_DIRECT:
            problems.append('7월 1주차 직항이 최저가인 칸 %d (기대 %d)'
                            % (got_direct, EXPECT_JUL1_DIRECT))
        got_alt = sum(1 for d in jul1 if d.get('alt'))
        if got_alt != EXPECT_JUL1_ALT:
            problems.append('7월 1주차 직항 금액 병기 %d칸 (기대 %d칸)'
                            % (got_alt, EXPECT_JUL1_ALT))
        got_thin = sum(1 for d in jul1 if '잔여 9석 미만' in (d.get('note') or ''))
        if got_thin != EXPECT_JUL1_THIN:
            problems.append('7월 1주차 9석 미만 표시 %d칸 (기대 %d칸)'
                            % (got_thin, EXPECT_JUL1_THIN))
        unknown = [d for d in jul1 if d.get('via') is None]
        if unknown:
            problems.append('7월 1주차 편성 미확인 %d칸 (기대 0칸)' % len(unknown))
        for pat, want in EXPECT_JUL1_AVG.items():
            v = [d['price'] for d in jul1 if d['pattern'] == pat]
            if len(v) != 24:
                problems.append('7월 1주차 %s %d칸 (기대 24칸)' % (pat, len(v)))
            elif round(sum(v) / len(v)) != want:
                problems.append('7월 1주차 %s 평균 %d (기대 %d)'
                                % (pat, round(sum(v) / len(v)), want))
        for code, (lo, hi) in EXPECT_JUL1_ROUTE.items():
            v = [d['price'] for d in jul1 if d['code'] == code]
            if len(v) != 5:
                problems.append('7월 1주차 %s %d칸 (기대 5칸)' % (code, len(v)))
            elif (min(v), max(v)) != (lo, hi):
                problems.append('7월 1주차 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (lo, hi)))
        for code in EXPECT_JUL1_ALLDIRECT:
            v = [d for d in jul1 if d['code'] == code]
            if any(d.get('via') is not False for d in v):
                problems.append('7월 1주차 %s 5패턴이 모두 직항이어야 합니다' % code)
        for code in EXPECT_JUL1_NODIRECT:
            v = [d for d in jul1 if d['code'] == code]
            if any('직항편 없음' not in (d.get('note') or '') or d.get('alt') for d in v):
                problems.append('7월 1주차 %s 5패턴 전부 직항 운임 없음이어야 합니다' % code)
        for (code, date, pat), price in EXPECT_JUL1_LOW.items():
            got = next((d['price'] for d in jul1 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != price:
                problems.append('7월 1주차 최저 칸 %s %s %s %s (기대 %d)'
                                % (code, date, pat, got, price))
        for (code, date, pat), alt in EXPECT_JUL1_ALT_CELLS.items():
            got = next((d.get('alt') for d in jul1 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), 'MISSING')
            if got != alt:
                problems.append('7월 1주차 직항 금액 %s %s %s %s (기대 %s)'
                                % (code, date, pat, got, alt))
        for d in jul1:
            if d.get('via') is True and '총' not in (d.get('note') or ''):
                problems.append('7월 1주차 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in (d.get('note') or ''):
                problems.append('7월 1주차 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
    # 2027년 7월 2주차(7/8~12) — 기존 24개 노선 × 5패턴 120칸(100%). 자리표시 칸이 남지 않았는지,
    # 최저·최고·직항 칸 수·직항 금액 병기·직항 운임 미표시·9석 미만·패턴 평균·노선별 최저/최고가
    # 원문과 같은지, 0박 당일치기 칸이 그대로인지는 위쪽 노선별 검사에서 본다.
    jul2 = [dict(d, code=r['code']) for r in routes if r['code'] in EXPECT_MAR_W1_ROUTES
            for d in r['deals'] if JUL2_START <= d['date'] <= JUL2_END
            and d['pattern'] in EXPECT_WEEKEND]
    if len(jul2) != EXPECT_JUL2_TOTAL:
        problems.append('7월 2주차 %d칸 (기대 %d칸)' % (len(jul2), EXPECT_JUL2_TOTAL))
    else:
        if any(d.get('src') for d in jul2):
            problems.append('7월 2주차에 가격표 자리표시 칸이 남아 있습니다: %s'
                            % [(d['code'], d['date']) for d in jul2 if d.get('src')][:4])
        ps = [d['price'] for d in jul2]
        if (min(ps), max(ps)) != EXPECT_JUL2_OVERALL:
            problems.append('7월 2주차 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), EXPECT_JUL2_OVERALL))
        got_direct = sum(1 for d in jul2 if d.get('via') is False)
        if got_direct != EXPECT_JUL2_DIRECT:
            problems.append('7월 2주차 직항이 최저가인 칸 %d (기대 %d)'
                            % (got_direct, EXPECT_JUL2_DIRECT))
        got_alt = sum(1 for d in jul2 if d.get('alt'))
        if got_alt != EXPECT_JUL2_ALT:
            problems.append('7월 2주차 직항 금액 병기 %d칸 (기대 %d칸)'
                            % (got_alt, EXPECT_JUL2_ALT))
        got_thin = sum(1 for d in jul2 if '잔여 9석 미만' in (d.get('note') or ''))
        if got_thin != EXPECT_JUL2_THIN:
            problems.append('7월 2주차 9석 미만 표시 %d칸 (기대 %d칸)'
                            % (got_thin, EXPECT_JUL2_THIN))
        got_nod = sum(1 for d in jul2 if '직항편 없음' in (d.get('note') or ''))
        if got_nod != EXPECT_JUL2_NODIRECT:
            problems.append('7월 2주차 직항 운임 미표시 %d칸 (기대 %d칸)'
                            % (got_nod, EXPECT_JUL2_NODIRECT))
        unknown = [d for d in jul2 if d.get('via') is None]
        if unknown:
            problems.append('7월 2주차 편성 미확인 %d칸 (기대 0칸)' % len(unknown))
        for pat, want in EXPECT_JUL2_AVG.items():
            v = [d['price'] for d in jul2 if d['pattern'] == pat]
            if len(v) != 24:
                problems.append('7월 2주차 %s %d칸 (기대 24칸)' % (pat, len(v)))
            elif round(sum(v) / len(v)) != want:
                problems.append('7월 2주차 %s 평균 %d (기대 %d)'
                                % (pat, round(sum(v) / len(v)), want))
        for code, (lo, hi) in EXPECT_JUL2_ROUTE.items():
            v = [d['price'] for d in jul2 if d['code'] == code]
            if len(v) != 5:
                problems.append('7월 2주차 %s %d칸 (기대 5칸)' % (code, len(v)))
            elif (min(v), max(v)) != (lo, hi):
                problems.append('7월 2주차 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (lo, hi)))
        for code in EXPECT_JUL2_ALLDIRECT:
            v = [d for d in jul2 if d['code'] == code]
            if any(d.get('via') is not False for d in v):
                problems.append('7월 2주차 %s 5패턴이 모두 직항이어야 합니다' % code)
        for code in EXPECT_JUL2_NODIRECT_ROUTES:
            v = [d for d in jul2 if d['code'] == code]
            if any('직항편 없음' not in (d.get('note') or '') or d.get('alt') for d in v):
                problems.append('7월 2주차 %s 5패턴 전부 직항 운임 없음이어야 합니다' % code)
        for (code, date, pat), price in EXPECT_JUL2_LOW.items():
            got = next((d['price'] for d in jul2 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), None)
            if got != price:
                problems.append('7월 2주차 최저/최고 칸 %s %s %s %s (기대 %d)'
                                % (code, date, pat, got, price))
        for (code, date, pat), alt in EXPECT_JUL2_ALT_CELLS.items():
            got = next((d.get('alt') for d in jul2 if d['code'] == code
                        and d['date'] == date and d['pattern'] == pat), 'MISSING')
            if got != alt:
                problems.append('7월 2주차 직항 금액 %s %s %s %s (기대 %s)'
                                % (code, date, pat, got, alt))
        for d in jul2:
            if d.get('via') is True and '총' not in (d.get('note') or ''):
                problems.append('7월 2주차 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in (d.get('note') or ''):
                problems.append('7월 2주차 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
    # A조 12개 노선 2027년 7월 3~5주차(7/15~19 · 7/22~26 · 7/29~8/2) — 180칸이 모두 값인지,
    # 실측분·자리표시·최저/최고·직항 칸·직항 금액 병기·9석 미만·노선별 칸 수가 보고서와 같은지.
    grp = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_A_JUL
           for d in r['deals'] if GRP_A_JUL_START <= d['date'] <= GRP_A_JUL_END
           and d['pattern'] in EXPECT_WEEKEND]
    if len(grp) != GRP_A_JUL_TOTAL:
        problems.append('A조 7월 3~5주 %d칸 (기대 %d칸)' % (len(grp), GRP_A_JUL_TOTAL))
    else:
        want = set()
        for code in GRP_A_JUL:
            for thu in GRP_A_JUL_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want.add((code, dt, label))
        got = {(d['code'], d['date'], d['pattern']) for d in grp}
        if got != want:
            problems.append('A조 7월 3~5주 격자 차이: %s' % sorted(got ^ want)[:6])
        measured = [d for d in grp if d.get('via') is not None]
        if len(measured) != GRP_A_JUL_MEASURED:
            problems.append('A조 7월 3~5주 실측 %d칸 (기대 %d칸)'
                            % (len(measured), GRP_A_JUL_MEASURED))
        else:
            ps = [d['price'] for d in measured]
            if (min(ps), max(ps)) != GRP_A_JUL_OVERALL:
                problems.append('A조 7월 3~5주 최저·최고 %s (기대 %s)'
                                % ((min(ps), max(ps)), GRP_A_JUL_OVERALL))
            direct = sum(1 for d in measured if d.get('via') is False)
            if direct != GRP_A_JUL_DIRECT:
                problems.append('A조 7월 3~5주 직항이 최저가인 칸 %d (기대 %d)'
                                % (direct, GRP_A_JUL_DIRECT))
            alt = sum(1 for d in measured if d.get('alt'))
            if alt != GRP_A_JUL_ALT:
                problems.append('A조 7월 3~5주 직항 금액 병기 %d칸 (기대 %d칸)'
                                % (alt, GRP_A_JUL_ALT))
            thin = sum(1 for d in measured if '잔여 9석 미만' in (d.get('note') or ''))
            if thin != GRP_A_JUL_THIN:
                problems.append('A조 7월 3~5주 9석 미만 표시 %d칸 (기대 %d칸)'
                                % (thin, GRP_A_JUL_THIN))
            for code, n in GRP_A_JUL_ROUTE_MEASURED.items():
                c = sum(1 for d in measured if d['code'] == code)
                if c != n:
                    problems.append('A조 7월 3~5주 %s 실측 %d칸 (기대 %d칸)' % (code, c, n))
            for d in measured:
                if d.get('via') is True and '총' not in (d.get('note') or ''):
                    problems.append('A조 경유 칸에 총 소요시간이 없습니다: %s %s'
                                    % (d['code'], d['date']))
                    break
                if d.get('via') is False and '직항' not in (d.get('note') or ''):
                    problems.append('A조 직항 칸 note 이상: %s %s' % (d['code'], d['date']))
                    break
    # 부산 출발 B조 12개 노선 2027년 7월 3주(7/15~19 · 7/22~26 · 7/29~8/2) — 격자 180칸이 모두
    # 금액을 가지는지, 가격표 자리표시가 남지 않았는지, 노선별 15칸(최저/최고/평균/직항 칸)과
    # 격자 최저·최고·평균·중앙값, 주차·패턴·10만원 구간, 장시간 경유, 2회 환승 칸, 교체 33칸의
    # 금액이 원본 보고서와 같은지.
    gb = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_B_JUL
          for d in r['deals'] if GRP_B_JUL_START <= d['date'] <= GRP_B_JUL_END
          and d['pattern'] in EXPECT_WEEKEND]
    if len(gb) != GRP_B_JUL_TOTAL:
        problems.append('B조 7월 3주 %d칸 (기대 %d칸)' % (len(gb), GRP_B_JUL_TOTAL))
    else:
        want = set()
        for code in GRP_B_JUL:
            for thu in GRP_B_JUL_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want.add((code, dt, label))
        got = {(d['code'], d['date'], d['pattern']) for d in gb}
        if got != want:
            problems.append('B조 7월 3주 격자 차이: %s' % sorted(got ^ want)[:6])
        if [d for d in gb if d.get('src')]:
            problems.append('B조 7월 3주에 가격표 자리표시가 남아 있습니다')
        left = [d for d in gb if not d.get('price') or d.get('via') is None]
        if left:
            problems.append('B조 7월 3주 금액·편성 없는 칸 %d칸 (기대 0칸): %s'
                            % (len(left), [(d['code'], d['date']) for d in left][:4]))
        ps = [d['price'] for d in gb]
        if (min(ps), max(ps)) != GRP_B_JUL_OVERALL:
            problems.append('B조 7월 3주 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), GRP_B_JUL_OVERALL))
        if _rnd(sum(ps) / len(ps)) != GRP_B_JUL_AVG:
            problems.append('B조 7월 3주 평균 %d (기대 %d)'
                            % (_rnd(sum(ps) / len(ps)), GRP_B_JUL_AVG))
        sp = sorted(ps)
        mid = sp[len(sp) // 2] if len(sp) % 2 else (sp[len(sp) // 2 - 1] + sp[len(sp) // 2]) / 2
        if mid != GRP_B_JUL_MEDIAN:
            problems.append('B조 7월 3주 중앙값 %s (기대 %s)' % (mid, GRP_B_JUL_MEDIAN))
        for code, (n, low, high, avg, ndirect) in GRP_B_JUL_ROUTE.items():
            cells_ = [d for d in gb if d['code'] == code]
            v = [d['price'] for d in cells_]
            if len(v) != n:
                problems.append('B조 7월 3주 %s %d칸 (기대 %d칸)' % (code, len(v), n))
                continue
            if (min(v), max(v), _rnd(sum(v) / len(v))) != (low, high, avg):
                problems.append('B조 7월 3주 %s 집계 %s (기대 %s)'
                                % (code, (min(v), max(v), _rnd(sum(v) / len(v))),
                                   (low, high, avg)))
            if sum(1 for d in cells_ if d.get('via') is False) != ndirect:
                problems.append('B조 7월 3주 %s 직항이 최저가인 칸 %d (기대 %d)'
                                % (code, sum(1 for d in cells_ if d.get('via') is False),
                                   ndirect))
        for key, (old, new) in GRP_B_JUL_REPLACE.items():
            hit = [d for d in gb if (d['code'], d['date'], d['pattern']) == key]
            if not hit:
                problems.append('B조 7월 3주 교체 칸이 없습니다: %s' % (key,))
            elif hit[0]['price'] != new:
                problems.append('B조 7월 3주 교체 칸 %s 금액 %s (기대 %d · 기존 %d)'
                                % (key, hit[0]['price'], new, old))
        direct = sum(1 for d in gb if d.get('via') is False)
        if direct != GRP_B_JUL_DIRECT:
            problems.append('B조 7월 3주 직항이 최저가인 칸 %d (기대 %d)'
                            % (direct, GRP_B_JUL_DIRECT))
        for m, n in GRP_B_JUL_MONTH.items():
            c = sum(1 for d in gb if d['date'][:7] == m)
            if c != n:
                problems.append('B조 7월 3주 %s 출발 %d칸 (기대 %d칸)' % (m, c, n))
        for thu, (cells_n, total, avg, low, high) in GRP_B_JUL_WEEK.items():
            v = [d['price'] for d in gb
                 if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                     days=(datetime.date.fromisoformat(d['date']).weekday()
                           - 3) % 7)).isoformat() == thu]   # 3 = datetime 목요일
            if not v:
                problems.append('B조 7월 3주 %s 칸이 없습니다' % thu)
                continue
            got_w = (len(v), sum(v), _rnd(sum(v) / len(v)), min(v), max(v))
            if got_w != (cells_n, total, avg, low, high):
                problems.append('B조 7월 3주 %s 주차 집계 %s (기대 %s)'
                                % (thu, got_w, (cells_n, total, avg, low, high)))
        for pat, want_avg in GRP_B_JUL_PAT_AVG.items():
            v = [d['price'] for d in gb if d['pattern'] == pat]
            if not v or _rnd(sum(v) / len(v)) != want_avg:
                problems.append('B조 7월 3주 %s 평균 %s (기대 %d)'
                                % (pat, v and _rnd(sum(v) / len(v)), want_avg))
        bucket = {k: 0 for k in GRP_B_JUL_BUCKET}
        edges = ((300000, '30만원 미만'), (400000, '30만~40만원'),
                 (500000, '40만~50만원'), (600000, '50만~60만원'),
                 (700000, '60만~70만원'), (800000, '70만~80만원'),
                 (900000, '80만~90만원'), (1000000, '90만~100만원'))
        for p in ps:
            name = '100만원 이상'
            for edge, label in edges:
                if p < edge:
                    name = label
                    break
            bucket[name] += 1
        if bucket != GRP_B_JUL_BUCKET:
            problems.append('B조 7월 3주 10만원 구간 %s (기대 %s)'
                            % (bucket, GRP_B_JUL_BUCKET))
        lay_cells = []
        for d in gb:
            lay = FL_LAY.search(d.get('note') or '')
            if lay:
                lay_cells.append(int(lay.group(1)) * 60 + int(lay.group(2) or 0))
        if (sum(1 for x in lay_cells if 720 <= x < 1200),
                sum(1 for x in lay_cells if x >= 1200)) != GRP_B_JUL_LONG:
            problems.append('B조 7월 3주 장시간 경유 %d/%d칸 (기대 %s)'
                            % (sum(1 for x in lay_cells if 720 <= x < 1200),
                               sum(1 for x in lay_cells if x >= 1200), GRP_B_JUL_LONG))
        two = sorted((d['code'], d['date'], d['pattern']) for d in gb
                     if d.get('via') is True and '환승' not in (d.get('note') or ''))
        if set(two) != GRP_B_JUL_TWOHOP:
            problems.append('B조 7월 3주 2회 환승 칸이 다릅니다: %s'
                            % sorted(set(two) ^ GRP_B_JUL_TWOHOP))
        over20 = 0
        for d in gb:
            note = d.get('note') or ''
            m = re.search(r'총\s*(\d+)시간\s*(?:(\d+)분)?', note) or \
                re.search(r'직항\s*(\d+)시간\s*(?:(\d+)분)?', note)
            if m and int(m.group(1)) * 60 + int(m.group(2) or 0) > 1200:
                over20 += 1
        if over20 != GRP_B_JUL_OVER20:
            problems.append('B조 7월 3주 총 소요 20시간 초과 %d칸 (기대 %d칸)'
                            % (over20, GRP_B_JUL_OVER20))
        for d in gb:
            note = d.get('note') or ''
            if not GRP_B_JUL_NOTE.search(note):
                problems.append('B조 7월 3주 note 에 출발-도착 시각이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is True and '총' not in note:
                problems.append('B조 7월 3주 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in note:
                problems.append('B조 7월 3주 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
            if '가격표' in note or d.get('alt'):
                problems.append('B조 7월 3주 칸에 자리표시·직항 금액이 붙었습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if '2026-11-2' in note:
                problems.append('B조 7월 3주 note 에 조사 시각이 들어갔습니다: %s %s'
                                % (d['code'], d['date']))
                break

    # 부산 출발 B조 12개 노선 2027년 8월 4주(8/5~9 · 8/12~16 · 8/19~23 · 8/26~30) — 격자 240칸이
    # 모두 금액을 가지는지, 앞선 실시간 조회 표시가 남지 않았는지, 노선별 20칸(최저/최고/평균/직항 칸)과
    # 격자 최저·최고·평균·중앙값, 주차·패턴·10만원 구간, 장시간 경유, 직항 최저 금액(alt)·최단 대안,
    # 교체 12칸의 금액이 원본 보고서와 같은지.
    gb8 = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_B_AUG
           for d in r['deals'] if GRP_B_AUG_START <= d['date'] <= GRP_B_AUG_END
           and d['pattern'] in EXPECT_WEEKEND]
    if len(gb8) != GRP_B_AUG_TOTAL:
        problems.append('B조 8월 4주 %d칸 (기대 %d칸)' % (len(gb8), GRP_B_AUG_TOTAL))
    else:
        want8 = set()
        for code in GRP_B_AUG:
            for thu in GRP_B_AUG_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt8 = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want8.add((code, dt8, label))
        got8 = {(d['code'], d['date'], d['pattern']) for d in gb8}
        if got8 != want8:
            problems.append('B조 8월 4주 격자 차이: %s' % sorted(got8 ^ want8)[:6])
        if [d for d in gb8 if d.get('src')]:
            problems.append('B조 8월 4주에 앞선 조회 표시(src)가 남아 있습니다')
        left8 = [d for d in gb8 if not d.get('price') or d.get('via') is None]
        if left8:
            problems.append('B조 8월 4주 금액·편성 없는 칸 %d칸 (기대 0칸): %s'
                            % (len(left8), [(d['code'], d['date']) for d in left8][:4]))
        ps8 = [d['price'] for d in gb8]
        if (min(ps8), max(ps8)) != GRP_B_AUG_OVERALL:
            problems.append('B조 8월 4주 최저·최고 %s (기대 %s)'
                            % ((min(ps8), max(ps8)), GRP_B_AUG_OVERALL))
        if _rnd(sum(ps8) / len(ps8)) != GRP_B_AUG_AVG:
            problems.append('B조 8월 4주 평균 %d (기대 %d)'
                            % (_rnd(sum(ps8) / len(ps8)), GRP_B_AUG_AVG))
        sp8 = sorted(ps8)
        mid8 = sp8[len(sp8) // 2] if len(sp8) % 2 \
            else (sp8[len(sp8) // 2 - 1] + sp8[len(sp8) // 2]) / 2
        if mid8 != GRP_B_AUG_MEDIAN:
            problems.append('B조 8월 4주 중앙값 %s (기대 %s)' % (mid8, GRP_B_AUG_MEDIAN))
        for code, (n8, low8, high8, avg8, ndirect8) in GRP_B_AUG_ROUTE.items():
            cells8 = [d for d in gb8 if d['code'] == code]
            v8 = [d['price'] for d in cells8]
            if len(v8) != n8:
                problems.append('B조 8월 4주 %s %d칸 (기대 %d칸)' % (code, len(v8), n8))
                continue
            if (min(v8), max(v8), _rnd(sum(v8) / len(v8))) != (low8, high8, avg8):
                problems.append('B조 8월 4주 %s 집계 %s (기대 %s)'
                                % (code, (min(v8), max(v8), _rnd(sum(v8) / len(v8))),
                                   (low8, high8, avg8)))
            if sum(1 for d in cells8 if d.get('via') is False) != ndirect8:
                problems.append('B조 8월 4주 %s 직항이 최저가인 칸 %d (기대 %d)'
                                % (code, sum(1 for d in cells8 if d.get('via') is False),
                                   ndirect8))
        for key8, (old8, new8) in GRP_B_AUG_REPLACE.items():
            hit8 = [d for d in gb8 if (d['code'], d['date'], d['pattern']) == key8]
            if not hit8:
                problems.append('B조 8월 4주 교체 칸이 없습니다: %s' % (key8,))
            elif hit8[0]['price'] != new8:
                problems.append('B조 8월 4주 교체 칸 %s 금액 %s (기대 %d · 기존 %d)'
                                % (key8, hit8[0]['price'], new8, old8))
        direct8 = sum(1 for d in gb8 if d.get('via') is False)
        if direct8 != GRP_B_AUG_DIRECT:
            problems.append('B조 8월 4주 직항이 최저가인 칸 %d (기대 %d)'
                            % (direct8, GRP_B_AUG_DIRECT))
        for m8, n8 in GRP_B_AUG_MONTH.items():
            c8 = sum(1 for d in gb8 if d['date'][:7] == m8)
            if c8 != n8:
                problems.append('B조 8월 4주 %s 출발 %d칸 (기대 %d칸)' % (m8, c8, n8))
        for thu8, (cells_n8, total8, avg8, low8, high8) in GRP_B_AUG_WEEK.items():
            v8 = [d['price'] for d in gb8
                  if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                      days=(datetime.date.fromisoformat(d['date']).weekday()
                            - 3) % 7)).isoformat() == thu8]   # 3 = datetime 목요일
            if not v8:
                problems.append('B조 8월 4주 %s 칸이 없습니다' % thu8)
                continue
            got_w8 = (len(v8), sum(v8), _rnd(sum(v8) / len(v8)), min(v8), max(v8))
            if got_w8 != (cells_n8, total8, avg8, low8, high8):
                problems.append('B조 8월 4주 %s 주차 집계 %s (기대 %s)'
                                % (thu8, got_w8, (cells_n8, total8, avg8, low8, high8)))
        for pat8, want8_avg in GRP_B_AUG_PAT_AVG.items():
            v8 = [d['price'] for d in gb8 if d['pattern'] == pat8]
            if not v8 or _rnd(sum(v8) / len(v8)) != want8_avg:
                problems.append('B조 8월 4주 %s 평균 %s (기대 %d)'
                                % (pat8, v8 and _rnd(sum(v8) / len(v8)), want8_avg))
        bucket8 = {k: 0 for k in GRP_B_AUG_BUCKET}
        edges8 = ((300000, '30만원 미만'), (400000, '30만~40만원'),
                  (500000, '40만~50만원'), (600000, '50만~60만원'),
                  (700000, '60만~70만원'), (800000, '70만~80만원'),
                  (900000, '80만~90만원'), (1000000, '90만~100만원'))
        for p8 in ps8:
            name8 = '100만원 이상'
            for edge8, label8 in edges8:
                if p8 < edge8:
                    name8 = label8
                    break
            bucket8[name8] += 1
        if bucket8 != GRP_B_AUG_BUCKET:
            problems.append('B조 8월 4주 10만원 구간 %s (기대 %s)'
                            % (bucket8, GRP_B_AUG_BUCKET))
        lay8 = []
        for d in gb8:
            hit = FL_LAY.search(d.get('note') or '') if d.get('via') is True else None
            if hit:
                lay8.append(int(hit.group(1)) * 60 + int(hit.group(2) or 0))
        if (sum(1 for x in lay8 if 720 <= x < 1200),
                sum(1 for x in lay8 if x >= 1200)) != GRP_B_AUG_LONG:
            problems.append('B조 8월 4주 장시간 경유 %d/%d칸 (기대 %s)'
                            % (sum(1 for x in lay8 if 720 <= x < 1200),
                               sum(1 for x in lay8 if x >= 1200), GRP_B_AUG_LONG))
        if not lay8 or max(lay8) != GRP_B_AUG_MAX_LAY:
            problems.append('B조 8월 4주 가장 긴 환승 %s분 (기대 %d분)'
                            % (lay8 and max(lay8), GRP_B_AUG_MAX_LAY))
        over8 = 0
        for d in gb8:
            note8 = d.get('note') or ''
            m8 = re.search(r'총\s*(\d+)시간\s*(?:(\d+)분)?', note8) or \
                re.search(r'직항\s*(\d+)시간\s*(?:(\d+)분)?', note8)
            if m8 and int(m8.group(1)) * 60 + int(m8.group(2) or 0) > 1200:
                over8 += 1
        if over8 != GRP_B_AUG_OVER20:
            problems.append('B조 8월 4주 총 소요 20시간 초과 %d칸 (기대 %d칸)'
                            % (over8, GRP_B_AUG_OVER20))
        alt8 = {(d['code'], d['date'], d['pattern']): d['alt'] for d in gb8 if d.get('alt')}
        if alt8 != GRP_B_AUG_ALT:
            problems.append('B조 8월 4주 직항 최저 금액 칸이 다릅니다: %s'
                            % sorted(set(alt8.items()) ^ set(GRP_B_AUG_ALT.items()))[:4])
        for key8, val8 in alt8.items():
            hit8 = [d for d in gb8 if (d['code'], d['date'], d['pattern']) == key8][0]
            if hit8.get('via') is not True or not hit8['price'] < val8:
                problems.append('B조 8월 4주 직항 금액이 최저가보다 싸지 않습니다: %s' % (key8,))
            if '직항 최저 %s원' % format(val8, ',') not in (hit8.get('note') or ''):
                problems.append('B조 8월 4주 note 에 직항 최저 금액이 없습니다: %s' % (key8,))
        short8 = sum(1 for d in gb8 if '최단' in (d.get('note') or ''))
        if short8 != GRP_B_AUG_SHORTEST:
            problems.append('B조 8월 4주 최단 대안 칸 %d (기대 %d칸)'
                            % (short8, GRP_B_AUG_SHORTEST))
        for d in gb8:
            note8 = d.get('note') or ''
            if not GRP_B_AUG_NOTE.search(note8):
                problems.append('B조 8월 4주 note 에 출발-도착 시각이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is True and '총' not in note8:
                problems.append('B조 8월 4주 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in note8:
                problems.append('B조 8월 4주 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
            if '가격표' in note8 or '2026-11-2' in note8:
                problems.append('B조 8월 4주 note 에 자리표시·조사 시각이 남았습니다: %s %s'
                                % (d['code'], d['date']))
                break

    # 부산 출발 B조 12개 노선 2027년 9월 5주(9/2~6 · 9/9~13 · 9/16~20 · 9/23~27 · 9/30~10/4) —
    # 격자 300칸이 모두 금액을 가지는지, 앞선 조회 표시가 남지 않았는지, 노선별 25칸(최저/최고/평균/
    # 직항 칸)과 격자 최저·최고·평균·중앙값, 주차·패턴·10만원 구간, 장시간 경유, 교체 12칸의 금액이
    # 원본 보고서와 같은지.
    gb9 = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_B_SEP
           for d in r['deals'] if GRP_B_SEP_START <= d['date'] <= GRP_B_SEP_END
           and d['pattern'] in EXPECT_WEEKEND]
    if len(gb9) != GRP_B_SEP_TOTAL:
        problems.append('B조 9월 5주 %d칸 (기대 %d칸)' % (len(gb9), GRP_B_SEP_TOTAL))
    else:
        want9 = set()
        for code in GRP_B_SEP:
            for thu in GRP_B_SEP_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt9 = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want9.add((code, dt9, label))
        got9 = {(d['code'], d['date'], d['pattern']) for d in gb9}
        if got9 != want9:
            problems.append('B조 9월 5주 격자 차이: %s' % sorted(got9 ^ want9)[:6])
        if [d for d in gb9 if d.get('src')]:
            problems.append('B조 9월 5주에 앞선 조회 표시(src)가 남아 있습니다')
        left9 = [d for d in gb9 if not d.get('price') or d.get('via') is None]
        if left9:
            problems.append('B조 9월 5주 금액·편성 없는 칸 %d칸 (기대 0칸): %s'
                            % (len(left9), [(d['code'], d['date']) for d in left9][:4]))
        ps9 = [d['price'] for d in gb9]
        if (min(ps9), max(ps9)) != GRP_B_SEP_OVERALL:
            problems.append('B조 9월 5주 최저·최고 %s (기대 %s)'
                            % ((min(ps9), max(ps9)), GRP_B_SEP_OVERALL))
        if _rnd(sum(ps9) / len(ps9)) != GRP_B_SEP_AVG:
            problems.append('B조 9월 5주 평균 %d (기대 %d)'
                            % (_rnd(sum(ps9) / len(ps9)), GRP_B_SEP_AVG))
        sp9 = sorted(ps9)
        mid9 = sp9[len(sp9) // 2] if len(sp9) % 2 \
            else (sp9[len(sp9) // 2 - 1] + sp9[len(sp9) // 2]) / 2
        if mid9 != GRP_B_SEP_MEDIAN:
            problems.append('B조 9월 5주 중앙값 %s (기대 %s)' % (mid9, GRP_B_SEP_MEDIAN))
        for code, (n9, low9, high9, avg9, ndirect9) in GRP_B_SEP_ROUTE.items():
            cells9 = [d for d in gb9 if d['code'] == code]
            v9 = [d['price'] for d in cells9]
            if len(v9) != n9:
                problems.append('B조 9월 5주 %s %d칸 (기대 %d칸)' % (code, len(v9), n9))
                continue
            if (min(v9), max(v9), _rnd(sum(v9) / len(v9))) != (low9, high9, avg9):
                problems.append('B조 9월 5주 %s 집계 %s (기대 %s)'
                                % (code, (min(v9), max(v9), _rnd(sum(v9) / len(v9))),
                                   (low9, high9, avg9)))
            if sum(1 for d in cells9 if d.get('via') is False) != ndirect9:
                problems.append('B조 9월 5주 %s 직항이 최저가인 칸 %d (기대 %d)'
                                % (code, sum(1 for d in cells9 if d.get('via') is False),
                                   ndirect9))
        for key9, (old9, new9) in GRP_B_SEP_REPLACE.items():
            hit9 = [d for d in gb9 if (d['code'], d['date'], d['pattern']) == key9]
            if not hit9:
                problems.append('B조 9월 5주 교체 칸이 없습니다: %s' % (key9,))
            elif hit9[0]['price'] != new9:
                problems.append('B조 9월 5주 교체 칸 %s 금액 %s (기대 %d · 기존 %d)'
                                % (key9, hit9[0]['price'], new9, old9))
        direct9 = sum(1 for d in gb9 if d.get('via') is False)
        if direct9 != GRP_B_SEP_DIRECT:
            problems.append('B조 9월 5주 직항이 최저가인 칸 %d (기대 %d)'
                            % (direct9, GRP_B_SEP_DIRECT))
        for m9, n9 in GRP_B_SEP_MONTH.items():
            c9 = sum(1 for d in gb9 if d['date'][:7] == m9)
            if c9 != n9:
                problems.append('B조 9월 5주 %s 출발 %d칸 (기대 %d칸)' % (m9, c9, n9))
        for thu9, (cells_n9, total9, avg9, low9, high9) in GRP_B_SEP_WEEK.items():
            v9 = [d['price'] for d in gb9
                  if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                      days=(datetime.date.fromisoformat(d['date']).weekday()
                            - 3) % 7)).isoformat() == thu9]   # 3 = datetime 목요일
            if not v9:
                problems.append('B조 9월 5주 %s 칸이 없습니다' % thu9)
                continue
            got_w9 = (len(v9), sum(v9), _rnd(sum(v9) / len(v9)), min(v9), max(v9))
            if got_w9 != (cells_n9, total9, avg9, low9, high9):
                problems.append('B조 9월 5주 %s 주차 집계 %s (기대 %s)'
                                % (thu9, got_w9, (cells_n9, total9, avg9, low9, high9)))
        for pat9, want9_avg in GRP_B_SEP_PAT_AVG.items():
            v9 = [d['price'] for d in gb9 if d['pattern'] == pat9]
            if not v9 or _rnd(sum(v9) / len(v9)) != want9_avg:
                problems.append('B조 9월 5주 %s 평균 %s (기대 %d)'
                                % (pat9, v9 and _rnd(sum(v9) / len(v9)), want9_avg))
        bucket9 = {k: 0 for k in GRP_B_SEP_BUCKET}
        edges9 = ((300000, '30만원 미만'), (400000, '30만~40만원'),
                  (500000, '40만~50만원'), (600000, '50만~60만원'),
                  (700000, '60만~70만원'), (800000, '70만~80만원'),
                  (900000, '80만~90만원'), (1000000, '90만~100만원'))
        for p9 in ps9:
            name9 = '100만원 이상'
            for edge9, label9 in edges9:
                if p9 < edge9:
                    name9 = label9
                    break
            bucket9[name9] += 1
        if bucket9 != GRP_B_SEP_BUCKET:
            problems.append('B조 9월 5주 10만원 구간 %s (기대 %s)'
                            % (bucket9, GRP_B_SEP_BUCKET))
        lay9 = []
        for d in gb9:
            hit = FL_LAY.search(d.get('note') or '') if d.get('via') is True else None
            if hit:
                lay9.append(int(hit.group(1)) * 60 + int(hit.group(2) or 0))
        if (sum(1 for x in lay9 if 720 <= x < 1200),
                sum(1 for x in lay9 if x >= 1200)) != GRP_B_SEP_LONG:
            problems.append('B조 9월 5주 장시간 경유 %d/%d칸 (기대 %s)'
                            % (sum(1 for x in lay9 if 720 <= x < 1200),
                               sum(1 for x in lay9 if x >= 1200), GRP_B_SEP_LONG))
        if sum(1 for x in lay9 if x >= 900) != GRP_B_SEP_LONG15:
            problems.append('B조 9월 5주 환승 15시간 이상 %d칸 (기대 %d칸)'
                            % (sum(1 for x in lay9 if x >= 900), GRP_B_SEP_LONG15))
        if not lay9 or max(lay9) != GRP_B_SEP_MAX_LAY:
            problems.append('B조 9월 5주 가장 긴 환승 %s분 (기대 %d분)'
                            % (lay9 and max(lay9), GRP_B_SEP_MAX_LAY))
        over9 = 0
        for d in gb9:
            note9 = d.get('note') or ''
            m9 = re.search(r'총\s*(\d+)시간\s*(?:(\d+)분)?', note9) or \
                re.search(r'직항\s*(\d+)시간\s*(?:(\d+)분)?', note9)
            if m9 and int(m9.group(1)) * 60 + int(m9.group(2) or 0) > 1200:
                over9 += 1
        if over9 != GRP_B_SEP_OVER20:
            problems.append('B조 9월 5주 총 소요 20시간 초과 %d칸 (기대 %d칸)'
                            % (over9, GRP_B_SEP_OVER20))
        alt9 = {(d['code'], d['date'], d['pattern']): d['alt'] for d in gb9 if d.get('alt')}
        if alt9 != GRP_B_SEP_ALT:
            problems.append('B조 9월 5주 직항 최저 금액 칸이 다릅니다: %s' % sorted(alt9)[:4])
        short9 = sum(1 for d in gb9 if '최단 ' in (d.get('note') or ''))
        if short9 != GRP_B_SEP_SHORTEST:
            problems.append('B조 9월 5주 최단 대안 칸 %d (기대 %d칸)'
                            % (short9, GRP_B_SEP_SHORTEST))
        for d in gb9:
            note9 = d.get('note') or ''
            if not GRP_B_SEP_NOTE.search(note9):
                problems.append('B조 9월 5주 note 에 출발-도착 시각이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is True and '총' not in note9:
                problems.append('B조 9월 5주 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in note9:
                problems.append('B조 9월 5주 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
            if ('2026-11' in note9 or '액세스레일' in note9 or '구성 미확인' in note9
                    or '가격표' in note9):
                problems.append('B조 9월 5주 note 에 자리표시·조사 시각·상품 이름이 남았습니다: '
                                '%s %s' % (d['code'], d['date']))
                break

    # 부산 출발 B조 12개 노선 2027년 10월 4주(10/7~11 · 10/14~18 · 10/21~25 · 10/28~11/1) —
    # 격자 240칸이 모두 금액을 가지는지, 앞선 조회 표시가 남지 않았는지, 노선별 20칸(최저/최고/평균/
    # 직항 칸)과 격자 최저·최고·평균·중앙값, 주차·패턴·10만원 구간, 장시간 경유·두 번 환승 칸수가
    # 원본 보고서와 같은지.
    gb10 = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_B_OCT
            for d in r['deals'] if GRP_B_OCT_START <= d['date'] <= GRP_B_OCT_END
            and d['pattern'] in EXPECT_WEEKEND]
    if len(gb10) != GRP_B_OCT_TOTAL:
        problems.append('B조 10월 4주 %d칸 (기대 %d칸)' % (len(gb10), GRP_B_OCT_TOTAL))
    else:
        want10 = set()
        for code10 in GRP_B_OCT:
            for thu10 in GRP_B_OCT_WEEKS:
                for label10 in EXPECT_WEEKEND:
                    dt10 = (datetime.date.fromisoformat(thu10) + datetime.timedelta(
                        days=(FL_WD[label10[0]] - FL_WD['목']) % 7)).isoformat()
                    want10.add((code10, dt10, label10))
        got10 = {(d['code'], d['date'], d['pattern']) for d in gb10}
        if got10 != want10:
            problems.append('B조 10월 4주 격자 차이: %s' % sorted(got10 ^ want10)[:6])
        if [d for d in gb10 if d.get('src')]:
            problems.append('B조 10월 4주에 앞선 조회 표시(src)가 남아 있습니다')
        left10 = [d for d in gb10 if not d.get('price') or d.get('via') is None]
        if left10:
            problems.append('B조 10월 4주 금액·편성 없는 칸 %d칸 (기대 0칸): %s'
                            % (len(left10), [(d['code'], d['date']) for d in left10][:4]))
        ps10 = [d['price'] for d in gb10]
        if (min(ps10), max(ps10)) != GRP_B_OCT_OVERALL:
            problems.append('B조 10월 4주 최저·최고 %s (기대 %s)'
                            % ((min(ps10), max(ps10)), GRP_B_OCT_OVERALL))
        if _rnd(sum(ps10) / len(ps10)) != GRP_B_OCT_AVG:
            problems.append('B조 10월 4주 평균 %d (기대 %d)'
                            % (_rnd(sum(ps10) / len(ps10)), GRP_B_OCT_AVG))
        sp10 = sorted(ps10)
        mid10 = sp10[len(sp10) // 2] if len(sp10) % 2 \
            else (sp10[len(sp10) // 2 - 1] + sp10[len(sp10) // 2]) / 2
        if mid10 != GRP_B_OCT_MEDIAN:
            problems.append('B조 10월 4주 중앙값 %s (기대 %s)' % (mid10, GRP_B_OCT_MEDIAN))
        for code10, (n10, low10, high10, avg10, ndirect10) in GRP_B_OCT_ROUTE.items():
            cells10 = [d for d in gb10 if d['code'] == code10]
            v10 = [d['price'] for d in cells10]
            if len(v10) != n10:
                problems.append('B조 10월 4주 %s %d칸 (기대 %d칸)' % (code10, len(v10), n10))
                continue
            if (min(v10), max(v10), _rnd(sum(v10) / len(v10))) != (low10, high10, avg10):
                problems.append('B조 10월 4주 %s 집계 %s (기대 %s)'
                                % (code10, (min(v10), max(v10), _rnd(sum(v10) / len(v10))),
                                   (low10, high10, avg10)))
            if sum(1 for d in cells10 if d.get('via') is False) != ndirect10:
                problems.append('B조 10월 4주 %s 직항이 최저가인 칸 %d (기대 %d)'
                                % (code10,
                                   sum(1 for d in cells10 if d.get('via') is False),
                                   ndirect10))
        direct10 = sum(1 for d in gb10 if d.get('via') is False)
        if direct10 != GRP_B_OCT_DIRECT:
            problems.append('B조 10월 4주 직항이 최저가인 칸 %d (기대 %d)'
                            % (direct10, GRP_B_OCT_DIRECT))
        for m10, n10 in GRP_B_OCT_MONTH.items():
            c10 = sum(1 for d in gb10 if d['date'][:7] == m10)
            if c10 != n10:
                problems.append('B조 10월 4주 %s 출발 %d칸 (기대 %d칸)' % (m10, c10, n10))
        for thu10, (cells_n10, total10, avg10, low10, high10) in GRP_B_OCT_WEEK.items():
            v10 = [d['price'] for d in gb10
                   if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                       days=(datetime.date.fromisoformat(d['date']).weekday()
                             - 3) % 7)).isoformat() == thu10]   # 3 = datetime 목요일
            if not v10:
                problems.append('B조 10월 4주 %s 칸이 없습니다' % thu10)
                continue
            got_w10 = (len(v10), sum(v10), _rnd(sum(v10) / len(v10)), min(v10), max(v10))
            if got_w10 != (cells_n10, total10, avg10, low10, high10):
                problems.append('B조 10월 4주 %s 주차 집계 %s (기대 %s)'
                                % (thu10, got_w10, (cells_n10, total10, avg10, low10, high10)))
        for pat10, want10_avg in GRP_B_OCT_PAT_AVG.items():
            v10 = [d['price'] for d in gb10 if d['pattern'] == pat10]
            if not v10 or _rnd(sum(v10) / len(v10)) != want10_avg:
                problems.append('B조 10월 4주 %s 평균 %s (기대 %d)'
                                % (pat10, v10 and _rnd(sum(v10) / len(v10)), want10_avg))
        bucket10 = {k: 0 for k in GRP_B_OCT_BUCKET}
        edges10 = ((300000, '30만원 미만'), (400000, '30만~40만원'),
                   (500000, '40만~50만원'), (600000, '50만~60만원'),
                   (700000, '60만~70만원'), (800000, '70만~80만원'),
                   (900000, '80만~90만원'), (1000000, '90만~100만원'))
        for p10 in ps10:
            name10 = '100만원 이상'
            for edge10, label10 in edges10:
                if p10 < edge10:
                    name10 = label10
                    break
            bucket10[name10] += 1
        if bucket10 != GRP_B_OCT_BUCKET:
            problems.append('B조 10월 4주 10만원 구간 %s (기대 %s)'
                            % (bucket10, GRP_B_OCT_BUCKET))
        lay10 = []
        for d in gb10:
            hit10 = FL_LAY.search(d.get('note') or '') if d.get('via') is True else None
            if hit10:
                lay10.append(int(hit10.group(1)) * 60 + int(hit10.group(2) or 0))
        if (sum(1 for x in lay10 if 720 <= x < 1200),
                sum(1 for x in lay10 if x >= 1200)) != GRP_B_OCT_LONG:
            problems.append('B조 10월 4주 장시간 경유 %d/%d칸 (기대 %s)'
                            % (sum(1 for x in lay10 if 720 <= x < 1200),
                               sum(1 for x in lay10 if x >= 1200), GRP_B_OCT_LONG))
        if sum(1 for x in lay10 if x >= 900) != GRP_B_OCT_LONG15:
            problems.append('B조 10월 4주 환승 15시간 이상 %d칸 (기대 %d칸)'
                            % (sum(1 for x in lay10 if x >= 900), GRP_B_OCT_LONG15))
        if not lay10 or max(lay10) != GRP_B_OCT_MAX_LAY:
            problems.append('B조 10월 4주 가장 긴 환승 %s분 (기대 %d분)'
                            % (lay10 and max(lay10), GRP_B_OCT_MAX_LAY))
        over10 = 0
        for d in gb10:
            note10 = d.get('note') or ''
            m10 = re.search(r'총\s*(\d+)시간\s*(?:(\d+)분)?', note10) or \
                re.search(r'직항\s*(\d+)시간\s*(?:(\d+)분)?', note10)
            if m10 and int(m10.group(1)) * 60 + int(m10.group(2) or 0) > 1200:
                over10 += 1
        if over10 != GRP_B_OCT_OVER20:
            problems.append('B조 10월 4주 총 소요 20시간 초과 %d칸 (기대 %d칸)'
                            % (over10, GRP_B_OCT_OVER20))
        alt10 = {(d['code'], d['date'], d['pattern']): d['alt'] for d in gb10 if d.get('alt')}
        if alt10 != GRP_B_OCT_ALT:
            problems.append('B조 10월 4주 직항 최저 금액 칸이 다릅니다: %s' % sorted(alt10)[:4])
        short10 = sum(1 for d in gb10 if '최단 ' in (d.get('note') or ''))
        if short10 != GRP_B_OCT_SHORTEST:
            problems.append('B조 10월 4주 최단 대안 칸 %d (기대 %d칸)'
                            % (short10, GRP_B_OCT_SHORTEST))
        twohop10 = sum(1 for d in gb10 if '경유 2회(' in (d.get('note') or ''))
        if twohop10 != GRP_B_OCT_TWOHOP:
            problems.append('B조 10월 4주 두 번 환승 칸 %d (기대 %d칸)'
                            % (twohop10, GRP_B_OCT_TWOHOP))
        for d in gb10:
            note10 = d.get('note') or ''
            if not GRP_B_OCT_NOTE.search(note10):
                problems.append('B조 10월 4주 note 에 출발-도착 시각이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is True and '총' not in note10:
                problems.append('B조 10월 4주 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in note10:
                problems.append('B조 10월 4주 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
            if ('2026-11' in note10 or '액세스레일' in note10 or '구성 미확인' in note10
                    or '가격표' in note10):
                problems.append('B조 10월 4주 note 에 자리표시·조사 시각·상품 이름이 남았습니다: '
                                '%s %s' % (d['code'], d['date']))
                break
        month10 = [d for d in gb10 if '최단 ' in (d.get('note') or '')]
        if any('원(' not in (d.get('note') or '') for d in month10):
            problems.append('B조 10월 4주 최단 대안에 금액·항공사 표기가 빠졌습니다')

    # 부산 출발 B조 12개 노선 2027년 11월 2주(11/4~8 · 11/11~15) — 120칸이 모두 금액을 가지는지,
    # 노선별 10칸(최저/최고/평균/직항 칸)과 격자 최저·최고·평균·중앙값, 주차·패턴·10만원 구간,
    # 6·12·15시간 이상 환승과 총 소요 20시간 초과, 최단 대안·두 번 환승 칸이 원본 보고서와 같은지.
    gb11 = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_B_NOV
            for d in r['deals'] if GRP_B_NOV_START <= d['date'] <= GRP_B_NOV_END
            and d['pattern'] in EXPECT_WEEKEND]
    if len(gb11) != GRP_B_NOV_TOTAL:
        problems.append('B조 11월 2주 %d칸 (기대 %d칸)' % (len(gb11), GRP_B_NOV_TOTAL))
    else:
        want11 = set()
        for code11 in GRP_B_NOV:
            for thu11 in GRP_B_NOV_WEEKS:
                for label11 in EXPECT_WEEKEND:
                    dt11 = (datetime.date.fromisoformat(thu11) + datetime.timedelta(
                        days=(FL_WD[label11[0]] - FL_WD['목']) % 7)).isoformat()
                    want11.add((code11, dt11, label11))
        got11 = {(d['code'], d['date'], d['pattern']) for d in gb11}
        if got11 != want11:
            problems.append('B조 11월 2주 격자 차이: %s' % sorted(got11 ^ want11)[:6])
        if [d for d in gb11 if d.get('src')]:
            problems.append('B조 11월 2주에 앞선 조회 표시(src)가 남아 있습니다')
        left11 = [d for d in gb11 if not d.get('price') or d.get('via') is None]
        if left11:
            problems.append('B조 11월 2주 금액·편성 없는 칸 %d칸 (기대 0칸): %s'
                            % (len(left11), [(d['code'], d['date']) for d in left11][:4]))
        ps11 = [d['price'] for d in gb11]
        if (min(ps11), max(ps11)) != GRP_B_NOV_OVERALL:
            problems.append('B조 11월 2주 최저·최고 %s (기대 %s)'
                            % ((min(ps11), max(ps11)), GRP_B_NOV_OVERALL))
        if _rnd(sum(ps11) / len(ps11)) != GRP_B_NOV_AVG:
            problems.append('B조 11월 2주 평균 %d (기대 %d)'
                            % (_rnd(sum(ps11) / len(ps11)), GRP_B_NOV_AVG))
        sp11 = sorted(ps11)
        mid11 = sp11[len(sp11) // 2] if len(sp11) % 2 \
            else (sp11[len(sp11) // 2 - 1] + sp11[len(sp11) // 2]) / 2
        if mid11 != GRP_B_NOV_MEDIAN:
            problems.append('B조 11월 2주 중앙값 %s (기대 %s)' % (mid11, GRP_B_NOV_MEDIAN))
        for code11, (n11, low11, high11, avg11, ndirect11) in GRP_B_NOV_ROUTE.items():
            cells11 = [d for d in gb11 if d['code'] == code11]
            v11 = [d['price'] for d in cells11]
            if len(v11) != n11:
                problems.append('B조 11월 2주 %s %d칸 (기대 %d칸)' % (code11, len(v11), n11))
                continue
            if (min(v11), max(v11), _rnd(sum(v11) / len(v11))) != (low11, high11, avg11):
                problems.append('B조 11월 2주 %s 집계 %s (기대 %s)'
                                % (code11, (min(v11), max(v11), _rnd(sum(v11) / len(v11))),
                                   (low11, high11, avg11)))
            if sum(1 for d in cells11 if d.get('via') is False) != ndirect11:
                problems.append('B조 11월 2주 %s 직항이 최저가인 칸 %d (기대 %d)'
                                % (code11,
                                   sum(1 for d in cells11 if d.get('via') is False),
                                   ndirect11))
        direct11 = sum(1 for d in gb11 if d.get('via') is False)
        if direct11 != GRP_B_NOV_DIRECT:
            problems.append('B조 11월 2주 직항이 최저가인 칸 %d (기대 %d)'
                            % (direct11, GRP_B_NOV_DIRECT))
        for m11, n11 in GRP_B_NOV_MONTH.items():
            c11 = sum(1 for d in gb11 if d['date'][:7] == m11)
            if c11 != n11:
                problems.append('B조 11월 2주 %s 출발 %d칸 (기대 %d칸)' % (m11, c11, n11))
        for thu11, (cells_n11, total11, avg11, low11, high11) in GRP_B_NOV_WEEK.items():
            v11 = [d['price'] for d in gb11
                   if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                       days=(datetime.date.fromisoformat(d['date']).weekday()
                             - 3) % 7)).isoformat() == thu11]   # 3 = datetime 목요일
            if not v11:
                problems.append('B조 11월 2주 %s 칸이 없습니다' % thu11)
                continue
            got_w11 = (len(v11), sum(v11), _rnd(sum(v11) / len(v11)), min(v11), max(v11))
            if got_w11 != (cells_n11, total11, avg11, low11, high11):
                problems.append('B조 11월 2주 %s 주차 집계 %s (기대 %s)'
                                % (thu11, got_w11, (cells_n11, total11, avg11, low11, high11)))
        for pat11, want11_avg in GRP_B_NOV_PAT_AVG.items():
            v11 = [d['price'] for d in gb11 if d['pattern'] == pat11]
            if not v11 or _rnd(sum(v11) / len(v11)) != want11_avg:
                problems.append('B조 11월 2주 %s 평균 %s (기대 %d)'
                                % (pat11, v11 and _rnd(sum(v11) / len(v11)), want11_avg))
        bucket11 = {k: 0 for k in GRP_B_NOV_BUCKET}
        edges11 = ((300000, '30만원 미만'), (400000, '30만~40만원'),
                   (500000, '40만~50만원'), (600000, '50만~60만원'),
                   (700000, '60만~70만원'), (800000, '70만~80만원'),
                   (900000, '80만~90만원'), (1000000, '90만~100만원'))
        for p11 in ps11:
            name11 = '100만원 이상'
            for edge11, label11 in edges11:
                if p11 < edge11:
                    name11 = label11
                    break
            bucket11[name11] += 1
        if bucket11 != GRP_B_NOV_BUCKET:
            problems.append('B조 11월 2주 10만원 구간 %s (기대 %s)'
                            % (bucket11, GRP_B_NOV_BUCKET))
        lay11 = []
        for d in gb11:
            hit11 = FL_LAY.search(d.get('note') or '') if d.get('via') is True else None
            if hit11:
                lay11.append(int(hit11.group(1)) * 60 + int(hit11.group(2) or 0))
        if (sum(1 for x in lay11 if 720 <= x < 1200),
                sum(1 for x in lay11 if x >= 1200)) != GRP_B_NOV_LONG:
            problems.append('B조 11월 2주 장시간 경유 %d/%d칸 (기대 %s)'
                            % (sum(1 for x in lay11 if 720 <= x < 1200),
                               sum(1 for x in lay11 if x >= 1200), GRP_B_NOV_LONG))
        if sum(1 for x in lay11 if x >= 360) != GRP_B_NOV_LONG6:
            problems.append('B조 11월 2주 환승 6시간 이상 %d칸 (기대 %d칸)'
                            % (sum(1 for x in lay11 if x >= 360), GRP_B_NOV_LONG6))
        if sum(1 for x in lay11 if x >= 900) != GRP_B_NOV_LONG15:
            problems.append('B조 11월 2주 환승 15시간 이상 %d칸 (기대 %d칸)'
                            % (sum(1 for x in lay11 if x >= 900), GRP_B_NOV_LONG15))
        if not lay11 or max(lay11) != GRP_B_NOV_MAX_LAY:
            problems.append('B조 11월 2주 가장 긴 환승 %s분 (기대 %d분)'
                            % (lay11 and max(lay11), GRP_B_NOV_MAX_LAY))
        over11 = 0
        for d in gb11:
            note11 = d.get('note') or ''
            m11 = re.search(r'총\s*(\d+)시간\s*(?:(\d+)분)?', note11) or \
                re.search(r'직항\s*(\d+)시간\s*(?:(\d+)분)?', note11)
            if m11 and int(m11.group(1)) * 60 + int(m11.group(2) or 0) > 1200:
                over11 += 1
        if over11 != GRP_B_NOV_OVER20:
            problems.append('B조 11월 2주 총 소요 20시간 초과 %d칸 (기대 %d칸)'
                            % (over11, GRP_B_NOV_OVER20))
        alt11 = {(d['code'], d['date'], d['pattern']): d['alt'] for d in gb11 if d.get('alt')}
        if alt11 != GRP_B_NOV_ALT:
            problems.append('B조 11월 2주 직항 최저 금액 칸이 다릅니다: %s' % sorted(alt11)[:4])
        short11 = sum(1 for d in gb11 if '최단 ' in (d.get('note') or ''))
        if short11 != GRP_B_NOV_SHORTEST:
            problems.append('B조 11월 2주 최단 대안 칸 %d (기대 %d칸)'
                            % (short11, GRP_B_NOV_SHORTEST))
        twohop11 = {(d['code'], d['date'], d['pattern']) for d in gb11
                    if '경유 2회(' in (d.get('note') or '')}
        if twohop11 != GRP_B_NOV_TWOHOP_CELLS:
            problems.append('B조 11월 2주 두 번 환승 칸 %d (기대 %d칸): %s'
                            % (len(twohop11), GRP_B_NOV_TWOHOP,
                               sorted(twohop11 ^ GRP_B_NOV_TWOHOP_CELLS)[:4]))
        for d in gb11:
            note11 = d.get('note') or ''
            if not GRP_B_NOV_NOTE.search(note11):
                problems.append('B조 11월 2주 note 에 출발-도착 시각이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is True and '총' not in note11:
                problems.append('B조 11월 2주 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in note11:
                problems.append('B조 11월 2주 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
            if ('2026-11' in note11 or '액세스레일' in note11 or '구성 미확인' in note11
                    or '가격표' in note11):
                problems.append('B조 11월 2주 note 에 자리표시·조사 시각·상품 이름이 남았습니다: '
                                '%s %s' % (d['code'], d['date']))
                break
        month11 = [d for d in gb11 if '최단 ' in (d.get('note') or '')]
        if any('원(' not in (d.get('note') or '') for d in month11):
            problems.append('B조 11월 2주 최단 대안에 금액·항공사 표기가 빠졌습니다')

    # A조 12개 노선 2027년 8월 4주(8/5~9 · 8/12~16 · 8/19~23 · 8/26~30) — 240칸이 모두 값인지,
    # 재확인 3칸의 금액, 노선별 20칸(최저/최고/직항 칸), 격자 최저·최고, note 표기(경유 총 소요).
    ga = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_A_AUG
          for d in r['deals'] if GRP_A_AUG_START <= d['date'] <= GRP_A_AUG_END
          and d['pattern'] in EXPECT_WEEKEND]
    if len(ga) != GRP_A_AUG_TOTAL:
        problems.append('A조 8월 4주 %d칸 (기대 %d칸)' % (len(ga), GRP_A_AUG_TOTAL))
    else:
        want = set()
        for code in GRP_A_AUG:
            for thu in GRP_A_AUG_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want.add((code, dt, label))
        got = {(d['code'], d['date'], d['pattern']) for d in ga}
        if got != want:
            problems.append('A조 8월 4주 격자 차이: %s' % sorted(got ^ want)[:6])
        left = [d for d in ga if d.get('via') is None]
        if left:
            problems.append('A조 8월 4주 편성 미확인 %d칸 (기대 0칸)' % len(left))
        ps = [d['price'] for d in ga]
        if (min(ps), max(ps)) != GRP_A_AUG_OVERALL:
            problems.append('A조 8월 4주 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), GRP_A_AUG_OVERALL))
        for code, (low, high) in GRP_A_AUG_ROUTE.items():
            v = [d['price'] for d in ga if d['code'] == code]
            if len(v) != 20:
                problems.append('A조 8월 4주 %s %d칸 (기대 20칸)' % (code, len(v)))
            elif (min(v), max(v)) != (low, high):
                problems.append('A조 8월 4주 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (low, high)))
        for (code, date, pat), (_old, new) in GRP_A_AUG_RECHECK.items():
            hit = next((d for d in ga if d['code'] == code and d['date'] == date
                        and d['pattern'] == pat), None)
            if not hit or hit['price'] != new:
                problems.append('A조 8월 4주 재확인 칸 %s %s %s %s (기대 %s원)'
                                % (code, date, pat, hit and hit['price'], format(new, ',')))
        for d in ga:
            note = d.get('note') or ''
            if ':' not in note:
                continue      # 앞선 조사분 32칸 — 이번 원본 이전 표기('직항' · '경유(서울)')라 그대로 둔다
            if d.get('via') is True and '총' not in note:
                problems.append('A조 8월 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in note:
                problems.append('A조 8월 직항 칸 note 이상: %s %s' % (d['code'], d['date']))
                break
            if '가격표' in note or d.get('alt'):
                problems.append('A조 8월 칸에 자리표시·직항 금액이 붙었습니다: %s %s'
                                % (d['code'], d['date']))
                break
        rich = [d for d in ga if ':' in (d.get('note') or '')]
        if len(rich) != GRP_A_AUG_MEASURED:
            problems.append('A조 8월 이번 실측분 note %d칸 (기대 %d칸)'
                            % (len(rich), GRP_A_AUG_MEASURED))
        for code, n in GRP_A_AUG_MEASURED_BY_ROUTE.items():
            c = sum(1 for d in rich if d['code'] == code)
            if c != n:
                problems.append('A조 8월 %s 실측 %d칸 (기대 %d칸)' % (code, c, n))

    # A조 12개 노선 2027년 9월 5주(9/2~6 · 9/9~13 · 9/16~20 · 9/23~27 · 9/30~10/4) — 300칸이 모두 금액을
    # 가지는지, 재확인 1칸·편성 미확인 2칸·XMB 연계 2칸의 표기, 노선별 25칸(최저/최고), 격자 최저·최고,
    # 실측 246칸의 최저·최고·평균·직항 칸·노선별·월별·주차 평균, note 표기(경유 총 소요 · 직항).
    gs = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_A_SEP
          for d in r['deals'] if GRP_A_SEP_START <= d['date'] <= GRP_A_SEP_END
          and d['pattern'] in EXPECT_WEEKEND]
    if len(gs) != GRP_A_SEP_TOTAL:
        problems.append('A조 9월 5주 %d칸 (기대 %d칸)' % (len(gs), GRP_A_SEP_TOTAL))
    else:
        want = set()
        for code in GRP_A_SEP:
            for thu in GRP_A_SEP_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want.add((code, dt, label))
        got = {(d['code'], d['date'], d['pattern']) for d in gs}
        if got != want:
            problems.append('A조 9월 5주 격자 차이: %s' % sorted(got ^ want)[:6])
        nofare = [d for d in gs if not d.get('price')]
        if nofare:
            problems.append('A조 9월 5주 금액 없는 칸 %d칸 (기대 0칸)' % len(nofare))
        ps = [d['price'] for d in gs]
        if (min(ps), max(ps)) != GRP_A_SEP_GRID_OVERALL:
            problems.append('A조 9월 5주 격자 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), GRP_A_SEP_GRID_OVERALL))
        for code, (low, high) in GRP_A_SEP_GRID_ROUTE.items():
            v = [d['price'] for d in gs if d['code'] == code]
            if len(v) != 25:
                problems.append('A조 9월 5주 %s %d칸 (기대 25칸)' % (code, len(v)))
            elif (min(v), max(v)) != (low, high):
                problems.append('A조 9월 5주 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (low, high)))
        unk = sorted((d['code'], d['date'], d['pattern']) for d in gs if d.get('via') is None)
        if unk != sorted(GRP_A_SEP_UNKNOWN):
            problems.append('A조 9월 5주 편성 미확인 칸이 다릅니다: %s' % unk)
        for (code, date, pat), (_old, new) in GRP_A_SEP_RECHECK.items():
            hit = next((d for d in gs if d['code'] == code and d['date'] == date
                        and d['pattern'] == pat), None)
            if not hit or hit['price'] != new:
                problems.append('A조 9월 5주 재확인 칸 %s %s %s %s (기대 %s원)'
                                % (code, date, pat, hit and hit['price'], format(new, ',')))
        rich = [d for d in gs if GRP_A_SEP_NOTE.search(d.get('note') or '')
                or GRP_A_SEP_XMB_NOTE in (d.get('note') or '')]
        if len(rich) != GRP_A_SEP_MEASURED:
            problems.append('A조 9월 5주 이번 실측분 note %d칸 (기대 %d칸)'
                            % (len(rich), GRP_A_SEP_MEASURED))
        else:
            rp = [d['price'] for d in rich]
            if (min(rp), max(rp)) != GRP_A_SEP_OVERALL:
                problems.append('A조 9월 5주 실측 최저·최고 %s (기대 %s)'
                                % ((min(rp), max(rp)), GRP_A_SEP_OVERALL))
            if _rnd(sum(rp) / len(rp)) != GRP_A_SEP_AVG:
                problems.append('A조 9월 5주 실측 평균 %d (기대 %d)'
                                % (_rnd(sum(rp) / len(rp)), GRP_A_SEP_AVG))
            got_direct = sum(1 for d in rich if d.get('via') is False)
            if got_direct != GRP_A_SEP_DIRECT:
                problems.append('A조 9월 5주 직항이 최저가인 칸 %d (기대 %d)'
                                % (got_direct, GRP_A_SEP_DIRECT))
            for code, n in GRP_A_SEP_MEASURED_BY_ROUTE.items():
                c = sum(1 for d in rich if d['code'] == code)
                if c != n:
                    problems.append('A조 9월 %s 실측 %d칸 (기대 %d칸)' % (code, c, n))
            for m, n in GRP_A_SEP_MONTH.items():
                c = sum(1 for d in rich if d['date'][:7] == m
                        and (d['code'], d['date'], d['pattern']) not in GRP_A_SEP_RECHECK)
                if c != n:
                    problems.append('A조 9월 실측 %s 출발 %d칸 (기대 %d칸)' % (m, c, n))
            for thu, want_avg in GRP_A_SEP_WEEK_AVG.items():
                v = [d['price'] for d in rich
                     if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                         days=(datetime.date.fromisoformat(d['date']).weekday()
                               - 3) % 7)).isoformat() == thu]   # 3 = datetime 목요일
                if not v:
                    problems.append('A조 9월 %s 실측 칸이 없습니다' % thu)
                elif _rnd(sum(v) / len(v)) != want_avg:
                    problems.append('A조 9월 %s 평균 %d (기대 %d)'
                                    % (thu, _rnd(sum(v) / len(v)), want_avg))
            for code, date, pat in GRP_A_SEP_XMB:
                hit = next((d for d in rich if d['code'] == code and d['date'] == date
                            and d['pattern'] == pat), None)
                if not hit or GRP_A_SEP_XMB_NOTE not in (hit.get('note') or ''):
                    problems.append('A조 9월 XMB 연계 표기가 없습니다: %s %s %s'
                                    % (code, date, pat))
            long_cells = []
            for d in rich:
                lay = FL_LAY.search(d.get('note') or '')
                if lay:
                    long_cells.append(int(lay.group(1)) * 60 + int(lay.group(2) or 0))
            if (sum(1 for x in long_cells if x >= 720),
                    sum(1 for x in long_cells if x >= 1200)) != GRP_A_SEP_LONG:
                problems.append('A조 9월 장시간 경유 %d/%d칸 (기대 %s)'
                                % (sum(1 for x in long_cells if x >= 720),
                                   sum(1 for x in long_cells if x >= 1200), GRP_A_SEP_LONG))
            for d in rich:
                note = d.get('note') or ''
                if d.get('via') is True and '총' not in note:
                    problems.append('A조 9월 경유 칸에 총 소요시간이 없습니다: %s %s'
                                    % (d['code'], d['date']))
                    break
                if d.get('via') is False and '직항' not in note:
                    problems.append('A조 9월 직항 칸 note 이상: %s %s' % (d['code'], d['date']))
                    break
                if '가격표' in note or d.get('alt'):
                    problems.append('A조 9월 칸에 자리표시·직항 금액이 붙었습니다: %s %s'
                                    % (d['code'], d['date']))
                    break
                if '2026-11-2' in note:
                    problems.append('A조 9월 note 에 조사 시각이 들어갔습니다: %s %s'
                                    % (d['code'], d['date']))
                    break

    # A조 12개 노선 2027년 10월 4주(10/7~11 · 10/14~18 · 10/21~25 · 10/28~11/1) — 240칸이 모두
    # 금액을 가지는지, 앞선 조사분 9칸이 그대로인지, 노선별 20칸(최저/최고), 격자 최저·최고,
    # 실측 231칸의 최저·최고·평균·직항 칸·노선별·월별·주차 평균, note 표기(경유 총 소요 · 직항).
    go = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_A_OCT
          for d in r['deals'] if GRP_A_OCT_START <= d['date'] <= GRP_A_OCT_END
          and d['pattern'] in EXPECT_WEEKEND]
    if len(go) != GRP_A_OCT_TOTAL:
        problems.append('A조 10월 4주 %d칸 (기대 %d칸)' % (len(go), GRP_A_OCT_TOTAL))
    else:
        want = set()
        for code in GRP_A_OCT:
            for thu in GRP_A_OCT_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want.add((code, dt, label))
        got = {(d['code'], d['date'], d['pattern']) for d in go}
        if got != want:
            problems.append('A조 10월 4주 격자 차이: %s' % sorted(got ^ want)[:6])
        nofare = [d for d in go if not d.get('price')]
        if nofare:
            problems.append('A조 10월 4주 금액 없는 칸 %d칸 (기대 0칸)' % len(nofare))
        ps = [d['price'] for d in go]
        if (min(ps), max(ps)) != GRP_A_OCT_GRID_OVERALL:
            problems.append('A조 10월 4주 격자 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), GRP_A_OCT_GRID_OVERALL))
        for code, (low, high) in GRP_A_OCT_GRID_ROUTE.items():
            v = [d['price'] for d in go if d['code'] == code]
            if len(v) != 20:
                problems.append('A조 10월 4주 %s %d칸 (기대 20칸)' % (code, len(v)))
            elif (min(v), max(v)) != (low, high):
                problems.append('A조 10월 4주 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (low, high)))
        for (code, date, pat), want_price in GRP_A_OCT_KEEP.items():
            hit = next((d for d in go if d['code'] == code and d['date'] == date
                        and d['pattern'] == pat), None)
            if not hit or hit['price'] != want_price:
                problems.append('A조 10월 그대로 두어야 할 칸 %s %s %s %s (기대 %s원)'
                                % (code, date, pat, hit and hit['price'],
                                   format(want_price, ',')))
        rich = [d for d in go if GRP_A_OCT_NOTE.search(d.get('note') or '')]
        if len(rich) != GRP_A_OCT_MEASURED:
            problems.append('A조 10월 이번 실측분 note %d칸 (기대 %d칸)'
                            % (len(rich), GRP_A_OCT_MEASURED))
        else:
            rp = [d['price'] for d in rich]
            if (min(rp), max(rp)) != GRP_A_OCT_OVERALL:
                problems.append('A조 10월 실측 최저·최고 %s (기대 %s)'
                                % ((min(rp), max(rp)), GRP_A_OCT_OVERALL))
            if _rnd(sum(rp) / len(rp)) != GRP_A_OCT_AVG:
                problems.append('A조 10월 실측 평균 %d (기대 %d)'
                                % (_rnd(sum(rp) / len(rp)), GRP_A_OCT_AVG))
            got_direct = sum(1 for d in rich if d.get('via') is False)
            if got_direct != GRP_A_OCT_DIRECT:
                problems.append('A조 10월 직항이 최저가인 칸 %d (기대 %d)'
                                % (got_direct, GRP_A_OCT_DIRECT))
            for code, n in GRP_A_OCT_MEASURED_BY_ROUTE.items():
                c = sum(1 for d in rich if d['code'] == code)
                if c != n:
                    problems.append('A조 10월 %s 실측 %d칸 (기대 %d칸)' % (code, c, n))
            for m, n in GRP_A_OCT_MONTH.items():
                c = sum(1 for d in rich if d['date'][:7] == m)
                if c != n:
                    problems.append('A조 10월 실측 %s 출발 %d칸 (기대 %d칸)' % (m, c, n))
            for thu, want_avg in GRP_A_OCT_WEEK_AVG.items():
                v = [d['price'] for d in rich
                     if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                         days=(datetime.date.fromisoformat(d['date']).weekday()
                               - 3) % 7)).isoformat() == thu]   # 3 = datetime 목요일
                if not v:
                    problems.append('A조 10월 %s 실측 칸이 없습니다' % thu)
                elif _rnd(sum(v) / len(v)) != want_avg:
                    problems.append('A조 10월 %s 평균 %d (기대 %d)'
                                    % (thu, _rnd(sum(v) / len(v)), want_avg))
            long_cells = []
            for d in rich:
                lay = FL_LAY.search(d.get('note') or '')
                if lay:
                    long_cells.append(int(lay.group(1)) * 60 + int(lay.group(2) or 0))
            if (sum(1 for x in long_cells if x >= 720),
                    sum(1 for x in long_cells if x >= 1200)) != GRP_A_OCT_LONG:
                problems.append('A조 10월 장시간 경유 %d/%d칸 (기대 %s)'
                                % (sum(1 for x in long_cells if x >= 720),
                                   sum(1 for x in long_cells if x >= 1200), GRP_A_OCT_LONG))
            for d in rich:
                note = d.get('note') or ''
                if d.get('via') is True and '총' not in note:
                    problems.append('A조 10월 경유 칸에 총 소요시간이 없습니다: %s %s'
                                    % (d['code'], d['date']))
                    break
                if d.get('via') is False and '직항' not in note:
                    problems.append('A조 10월 직항 칸 note 이상: %s %s' % (d['code'], d['date']))
                    break
                if '가격표' in note or d.get('alt'):
                    problems.append('A조 10월 칸에 자리표시·직항 금액이 붙었습니다: %s %s'
                                    % (d['code'], d['date']))
                    break
                if '2026-11-2' in note:
                    problems.append('A조 10월 note 에 조사 시각이 들어갔습니다: %s %s'
                                    % (d['code'], d['date']))
                    break

    # A조 12개 노선 2027년 11월 2주(11/4~8 · 11/11~15) — 격자 120칸이 값(110) 또는 판매편 0건(10)으로
    # 채워졌는지, 앞선 조사분 3칸이 그대로인지, 실측 109칸의 최저·최고·평균·중앙값·직항 칸·노선별·
    # 주차별·10만원 구간·장시간 경유가 보고서와 같은지, 판매편 0건 8칸에 금액이 없는지.
    nv = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_A_NOV
          for d in r['deals'] if GRP_A_NOV_START <= d['date'] <= GRP_A_NOV_END
          and d['pattern'] in EXPECT_WEEKEND]
    nv_marks = [n for n in (flights.get('noSale') or []) if n.get('code') in GRP_A_NOV
                and GRP_A_NOV_START <= n.get('date', '') <= GRP_A_NOV_END
                and n.get('pattern') in EXPECT_WEEKEND]
    if len(nv) + len(nv_marks) != GRP_A_NOV_TOTAL:
        problems.append('A조 11월 2주 %d칸 + 판매편 0건 %d칸 (기대 %d칸)'
                        % (len(nv), len(nv_marks), GRP_A_NOV_TOTAL))
    else:
        want = set()
        for code in GRP_A_NOV:
            for thu in GRP_A_NOV_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want.add((code, dt, label))
        got = {(d['code'], d['date'], d['pattern']) for d in nv} | \
              {(n['code'], n['date'], n['pattern']) for n in nv_marks}
        if got != want:
            problems.append('A조 11월 2주 격자 차이: %s' % sorted(got ^ want)[:6])
        na_got = {(n['code'], n['date'], n['pattern']) for n in nv_marks
                  if (n.get('status') or 'nosale') == 'nosale'}
        if na_got - GRP_A_NOV_KEEP_NOSALE != GRP_A_NOV_NA:
            problems.append('A조 11월 판매편 0건 칸이 다릅니다: %s'
                            % sorted((na_got - GRP_A_NOV_KEEP_NOSALE) ^ GRP_A_NOV_NA)[:6])
        for n in nv_marks:
            if 'price' in n:
                problems.append('A조 11월 판매편 0건 칸에 금액이 있습니다: %s %s'
                                % (n['code'], n['date']))
                break
        nofare = [d for d in nv if not d.get('price')]
        if nofare:
            problems.append('A조 11월 금액 없는 칸 %d칸 (기대 0칸)' % len(nofare))
        ps = [d['price'] for d in nv]
        for (code, date, pat), want_price in GRP_A_NOV_KEEP.items():
            hit = next((d for d in nv if d['code'] == code and d['date'] == date
                        and d['pattern'] == pat), None)
            if not hit or hit['price'] != want_price:
                problems.append('A조 11월 그대로 두어야 할 칸 %s %s %s %s (기대 %s원)'
                                % (code, date, pat, hit and hit['price'],
                                   format(want_price, ',')))
        keep_ns = {(n['code'], n['date'], n['pattern']) for n in nv_marks} & GRP_A_NOV_KEEP_NOSALE
        if keep_ns != GRP_A_NOV_KEEP_NOSALE:
            problems.append('A조 11월 그대로 두어야 할 판매편 0건 칸: %s'
                            % sorted(GRP_A_NOV_KEEP_NOSALE - keep_ns))
        if ps and (min(ps), max(ps)) != GRP_A_NOV_GRID_OVERALL:
            problems.append('A조 11월 격자 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), GRP_A_NOV_GRID_OVERALL))
        for code, (low, high) in GRP_A_NOV_GRID_ROUTE.items():
            v = [d['price'] for d in nv if d['code'] == code]
            if len(v) != GRP_A_NOV_ROUTE[code][0] + (1 if code == 'FUK' else 0):
                problems.append('A조 11월 격자 %s %d칸 (기대 %d칸)'
                                % (code, len(v), GRP_A_NOV_ROUTE[code][0]
                                   + (1 if code == 'FUK' else 0)))
            elif (min(v), max(v)) != (low, high):
                problems.append('A조 11월 격자 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (low, high)))
        unk = sorted((d['code'], d['date'], d['pattern']) for d in nv if d.get('via') is None)
        if unk:
            problems.append('A조 11월 편성 미확인 칸이 생겼습니다: %s' % unk[:4])
        rich = [d for d in nv if GRP_A_NOV_NOTE.search(d.get('note') or '')]
        if len(rich) != GRP_A_NOV_MEASURED:
            problems.append('A조 11월 이번 실측분 note %d칸 (기대 %d칸)'
                            % (len(rich), GRP_A_NOV_MEASURED))
        else:
            rp = [d['price'] for d in rich]
            if (min(rp), max(rp)) != GRP_A_NOV_OVERALL:
                problems.append('A조 11월 실측 최저·최고 %s (기대 %s)'
                                % ((min(rp), max(rp)), GRP_A_NOV_OVERALL))
            if _rnd(sum(rp) / len(rp)) != GRP_A_NOV_AVG:
                problems.append('A조 11월 실측 평균 %d (기대 %d)'
                                % (_rnd(sum(rp) / len(rp)), GRP_A_NOV_AVG))
            sp = sorted(rp)
            med = sp[len(sp) // 2]
            if med != GRP_A_NOV_MEDIAN:
                problems.append('A조 11월 실측 중앙값 %d (기대 %d)' % (med, GRP_A_NOV_MEDIAN))
            got_direct = sum(1 for d in rich if d.get('via') is False)
            if got_direct != GRP_A_NOV_DIRECT:
                problems.append('A조 11월 직항이 최저가인 칸 %d (기대 %d)'
                                % (got_direct, GRP_A_NOV_DIRECT))
            for code, n in GRP_A_NOV_MEASURED_BY_ROUTE.items():
                c = sum(1 for d in rich if d['code'] == code)
                if c != n:
                    problems.append('A조 11월 %s 실측 %d칸 (기대 %d칸)' % (code, c, n))
            for m, n in GRP_A_NOV_MONTH.items():
                c = sum(1 for d in rich if d['date'][:7] == m)
                if c != n:
                    problems.append('A조 11월 실측 %s 출발 %d칸 (기대 %d칸)' % (m, c, n))
            for code, (_n, na, low, high, avg) in GRP_A_NOV_ROUTE.items():
                v = [d['price'] for d in rich if d['code'] == code]
                got_na = sum(1 for k in GRP_A_NOV_NA if k[0] == code)
                if not v:
                    if _n or got_na != na:
                        problems.append('A조 11월 %s 실측 칸이 없습니다 (기대 %d칸 · 0건 %d칸)'
                                        % (code, _n, na))
                    continue
                if (len(v), min(v), max(v), _rnd(sum(v) / len(v))) != (_n, low, high, avg):
                    problems.append('A조 11월 %s 집계 %s (기대 %s)'
                                    % (code, (len(v), min(v), max(v),
                                              _rnd(sum(v) / len(v))),
                                       (_n, low, high, avg)))
                if got_na != na:
                    problems.append('A조 11월 %s 판매편 0건 %d칸 (기대 %d칸)'
                                    % (code, got_na, na))
            for thu, (cells_n, total, avg, low, high) in GRP_A_NOV_WEEK.items():
                v = [d['price'] for d in rich
                     if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                         days=(datetime.date.fromisoformat(d['date']).weekday()
                               - 3) % 7)).isoformat() == thu]   # 3 = datetime 목요일
                if not v:
                    problems.append('A조 11월 %s 실측 칸이 없습니다' % thu)
                    continue
                if (len(v), sum(v), _rnd(sum(v) / len(v)), min(v), max(v)) != \
                        (cells_n, total, avg, low, high):
                    problems.append('A조 11월 %s 주차 집계 %s (기대 %s)'
                                    % (thu, (len(v), sum(v), _rnd(sum(v) / len(v)),
                                             min(v), max(v)),
                                       (cells_n, total, avg, low, high)))
            bucket = {'30만원 미만': 0, '30만~40만원': 0, '40만~50만원': 0,
                      '50만~60만원': 0, '60만~70만원': 0, '70만원 이상': 0}
            for p in rp:
                if p < 300000:
                    bucket['30만원 미만'] += 1
                elif p < 400000:
                    bucket['30만~40만원'] += 1
                elif p < 500000:
                    bucket['40만~50만원'] += 1
                elif p < 600000:
                    bucket['50만~60만원'] += 1
                elif p < 700000:
                    bucket['60만~70만원'] += 1
                else:
                    bucket['70만원 이상'] += 1
            if bucket != GRP_A_NOV_BUCKET:
                problems.append('A조 11월 10만원 구간 %s (기대 %s)'
                                % (bucket, GRP_A_NOV_BUCKET))
            for pat, want_avg in GRP_A_NOV_PAT_AVG.items():
                v = [d['price'] for d in rich if d['pattern'] == pat]
                if not v or _rnd(sum(v) / len(v)) != want_avg:
                    problems.append('A조 11월 %s 평균 %s (기대 %d)'
                                    % (pat, v and _rnd(sum(v) / len(v)), want_avg))
            long_cells = []
            for d in rich:
                lay = FL_LAY.search(d.get('note') or '')
                if lay:
                    long_cells.append(int(lay.group(1)) * 60 + int(lay.group(2) or 0))
            if (sum(1 for x in long_cells if x >= 720),
                    sum(1 for x in long_cells if x >= 1200)) != GRP_A_NOV_LONG:
                problems.append('A조 11월 장시간 경유 %d/%d칸 (기대 %s)'
                                % (sum(1 for x in long_cells if x >= 720),
                                   sum(1 for x in long_cells if x >= 1200), GRP_A_NOV_LONG))
            for d in rich:
                note = d.get('note') or ''
                if d.get('via') is True and '총' not in note:
                    problems.append('A조 11월 경유 칸에 총 소요시간이 없습니다: %s %s'
                                    % (d['code'], d['date']))
                    break
                if d.get('via') is False and '직항' not in note:
                    problems.append('A조 11월 직항 칸 note 이상: %s %s' % (d['code'], d['date']))
                    break
                if '가격표' in note or d.get('alt'):
                    problems.append('A조 11월 칸에 자리표시·직항 금액이 붙었습니다: %s %s'
                                    % (d['code'], d['date']))
                    break
                if '2026-11-2' in note:
                    problems.append('A조 11월 note 에 조사 시각이 들어갔습니다: %s %s'
                                    % (d['code'], d['date']))
                    break

    # 기존 24개 노선 2027년 6월 1~2주차(6/3~7 · 6/10~14) — 격자 240칸이 모두 금액을 가지는지,
    # '가격표' 자리표시가 남지 않았는지, 노선별 10칸(최저/최고/평균), 격자 최저·최고·평균,
    # 직항이 최저가인 칸·직항 금액 병기·편성 미확인 칸, 주차·패턴·10만원 구간, 장시간 경유,
    # note 표기(경유 총 소요 · 직항)가 원본 보고서와 같은지.
    ju = [dict(d, code=r['code']) for r in routes if r['code'] in GRP_A_JUN12
          for d in r['deals'] if GRP_A_JUN12_START <= d['date'] <= GRP_A_JUN12_END
          and d['pattern'] in EXPECT_WEEKEND]
    if len(ju) != GRP_A_JUN12_TOTAL:
        problems.append('6월 1~2주차 %d칸 (기대 %d칸)' % (len(ju), GRP_A_JUN12_TOTAL))
    else:
        want = set()
        for code in GRP_A_JUN12:
            for thu in GRP_A_JUN12_WEEKS:
                for label in EXPECT_WEEKEND:
                    dt = (datetime.date.fromisoformat(thu) + datetime.timedelta(
                        days=(FL_WD[label[0]] - FL_WD['목']) % 7)).isoformat()
                    want.add((code, dt, label))
        got = {(d['code'], d['date'], d['pattern']) for d in ju}
        if got != want:
            problems.append('6월 1~2주차 격자 차이: %s' % sorted(got ^ want)[:6])
        nofare = [d for d in ju if not d.get('price')]
        if nofare:
            problems.append('6월 1~2주차 금액 없는 칸 %d칸 (기대 0칸)' % len(nofare))
        if [d for d in ju if d.get('src')]:
            problems.append('6월 1~2주차에 가격표 자리표시가 남아 있습니다')
        ps = [d['price'] for d in ju]
        if (min(ps), max(ps)) != GRP_A_JUN12_OVERALL:
            problems.append('6월 1~2주차 격자 최저·최고 %s (기대 %s)'
                            % ((min(ps), max(ps)), GRP_A_JUN12_OVERALL))
        if _rnd(sum(ps) / len(ps)) != GRP_A_JUN12_AVG:
            problems.append('6월 1~2주차 평균 %d (기대 %d)'
                            % (_rnd(sum(ps) / len(ps)), GRP_A_JUN12_AVG))
        for code, (n, low, high, avg) in GRP_A_JUN12_ROUTE.items():
            v = [d['price'] for d in ju if d['code'] == code]
            if not v:
                problems.append('6월 1~2주차 %s 칸이 없습니다 (기대 %d칸)' % (code, n))
            elif (len(v), min(v), max(v), _rnd(sum(v) / len(v))) != (n, low, high, avg):
                problems.append('6월 1~2주차 %s 집계 %s (기대 %s)'
                                % (code, (len(v), min(v), max(v), _rnd(sum(v) / len(v))),
                                   (n, low, high, avg)))
        for code, (low, high) in GRP_A_JUN12_GRID_ROUTE.items():
            v = [d['price'] for d in ju if d['code'] == code]
            if v and (min(v), max(v)) != (low, high):
                problems.append('6월 1~2주차 %s 최저·최고 %s (기대 %s)'
                                % (code, (min(v), max(v)), (low, high)))
        unk = sorted((d['code'], d['date'], d['pattern']) for d in ju if d.get('via') is None)
        if unk != sorted(GRP_A_JUN12_UNKNOWN):
            problems.append('6월 1~2주차 편성 미확인 칸 %s (기대 %s)'
                            % (unk, sorted(GRP_A_JUN12_UNKNOWN)))
        n_alt = sum(1 for d in ju if d.get('alt'))
        if n_alt != GRP_A_JUN12_ALT:
            problems.append('6월 1~2주차 직항 금액 병기 %d칸 (기대 %d칸)'
                            % (n_alt, GRP_A_JUN12_ALT))
        for d in ju:
            if d.get('alt') and d.get('via') is not False and d['alt'] <= d['price']:
                problems.append('6월 1~2주차 직항 금액이 최저가 이하: %s %s'
                                % (d['code'], d['date']))
                break
        got_direct = sum(1 for d in ju if d.get('via') is False)
        if got_direct != GRP_A_JUN12_DIRECT:
            problems.append('6월 1~2주차 직항이 최저가인 칸 %d (기대 %d)'
                            % (got_direct, GRP_A_JUN12_DIRECT))
        for m, n in GRP_A_JUN12_MONTH.items():
            c = sum(1 for d in ju if d['date'][:7] == m)
            if c != n:
                problems.append('6월 1~2주차 %s 출발 %d칸 (기대 %d칸)' % (m, c, n))
        for thu, (cells_n, total, avg, low, high) in GRP_A_JUN12_WEEK.items():
            v = [d['price'] for d in ju
                 if (datetime.date.fromisoformat(d['date']) - datetime.timedelta(
                     days=(datetime.date.fromisoformat(d['date']).weekday()
                           - 3) % 7)).isoformat() == thu]   # 3 = datetime 목요일
            if not v:
                problems.append('6월 1~2주차 %s 칸이 없습니다' % thu)
            elif (len(v), sum(v), _rnd(sum(v) / len(v)), min(v), max(v)) != \
                    (cells_n, total, avg, low, high):
                problems.append('6월 1~2주차 %s 주차 집계 %s (기대 %s)'
                                % (thu, (len(v), sum(v), _rnd(sum(v) / len(v)),
                                         min(v), max(v)),
                                   (cells_n, total, avg, low, high)))
        for pat, want_avg in GRP_A_JUN12_PAT_AVG.items():
            v = [d['price'] for d in ju if d['pattern'] == pat]
            if len(v) != 48 or _rnd(sum(v) / len(v)) != want_avg:
                problems.append('6월 1~2주차 %s %d칸 평균 %s (기대 48칸 %d)'
                                % (pat, len(v), v and _rnd(sum(v) / len(v)), want_avg))
        bucket = {'30만원 미만': 0, '30만~40만원': 0, '40만~50만원': 0,
                  '50만~60만원': 0, '60만~70만원': 0, '70만원 이상': 0}
        for p in ps:
            if p < 300000:
                bucket['30만원 미만'] += 1
            elif p < 400000:
                bucket['30만~40만원'] += 1
            elif p < 500000:
                bucket['40만~50만원'] += 1
            elif p < 600000:
                bucket['50만~60만원'] += 1
            elif p < 700000:
                bucket['60만~70만원'] += 1
            else:
                bucket['70만원 이상'] += 1
        if bucket != GRP_A_JUN12_BUCKET:
            problems.append('6월 1~2주차 10만원 구간 %s (기대 %s)'
                            % (bucket, GRP_A_JUN12_BUCKET))
        lay_all = []
        for d in ju:
            lay = FL_LAY.search(d.get('note') or '')
            if lay:
                lay_all.append(int(lay.group(1)) * 60 + int(lay.group(2) or 0))
        if (sum(1 for x in lay_all if 720 <= x < 1200),
                sum(1 for x in lay_all if x >= 1200)) != GRP_A_JUN12_LONG:
            problems.append('6월 1~2주차 장시간 경유 %d/%d칸 (기대 %s)'
                            % (sum(1 for x in lay_all if 720 <= x < 1200),
                               sum(1 for x in lay_all if x >= 1200), GRP_A_JUN12_LONG))
        for d in ju:
            note = d.get('note') or ''
            if not note:
                problems.append('6월 1~2주차 note 없는 칸: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is True and not any(w in note for w in ('총', '미운항', '편성 미표시')):
                problems.append('6월 1~2주차 경유 칸에 총 소요시간이 없습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if d.get('via') is False and '직항' not in note:
                problems.append('6월 1~2주차 직항 칸 note 이상: %s %s'
                                % (d['code'], d['date']))
                break
            if '가격표' in note:
                problems.append('6월 1~2주차 칸에 자리표시 문구가 남았습니다: %s %s'
                                % (d['code'], d['date']))
                break
            if '2026-11-' in note or '직항/경유 미확인' in note and d.get('via') is not None:
                problems.append('6월 1~2주차 note 에 조사 시각·미확인 문구가 들어갔습니다: %s %s'
                                % (d['code'], d['date']))
                break

    for m, n in EXPECT_OLD_BY_MONTH.items():
        if by_month.get(m) != n:
            problems.append('%s 기존 건 %s (기대 %d — 손실/변형)' % (m, by_month.get(m), n))

    # 2027년 2~6월 금~일 실측 — 노선별 출발일 집합과 0건 칸이 원본과 같은지
    for code, dates in EXPECT_26M_DATES.items():
        r = by_code.get(code)
        if not r:
            continue
        got = {d['date'] for d in r['deals']
               if d['pattern'] == '금~일' and '2027-02-01' <= d['date'] <= '2027-06-30'}
        if got != dates:
            problems.append('%s 2027년 2~6월 금~일 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(dates), sorted(got ^ dates)[:6]))
        if EXPECT_26M.get(code) is not None and len(got) != EXPECT_26M[code]:
            problems.append('%s 2027년 2~6월 금~일 %d칸 (기대 %d칸)' % (code, len(got), EXPECT_26M[code]))
    ns_dates = {x['date'] for x in (flights.get('noSale') or []) if x.get('code') == 'TXN'
                and '2027-04-01' <= x.get('date', '') <= '2027-06-30'}
    if ns_dates != {d for (_, d) in EXPECT_NOSALE_TXN_26M}:
        problems.append('황산 2027년 4~6월 금~일 판매편 0건 %d칸 (기대 13칸): %s'
                        % (len(ns_dates), sorted(ns_dates)))
    got_sat = {(r['code'], d['date'], d['pattern']) for r in routes
               if r['code'] in ROUTE_ORDER_26M for d in r['deals']
               if '2027-02-01' <= d['date'] <= '2027-06-30'
               and d['pattern'] not in EXPECT_WEEKEND}
    if got_sat:
        problems.append('4노선 2027년 2~6월에 주말형 5패턴 밖 패턴이 있습니다: %s'
                        % sorted(got_sat)[:6])
    # 2026-11-18 G2 완결본 — 4노선 × 21주 × 5패턴 420칸(값 384 + 판매편 0건 36)이 다 찼는지.
    # 목~월(4박)은 이번에 채운 축으로, 황산 7주만 0건이다.
    for code in ROUTE_ORDER_26M:
        r = by_code.get(code)
        if not r:
            continue
        filled = {(d['date'], d['pattern']) for d in r['deals']}
        filled |= {(n.get('date'), n.get('pattern')) for n in (flights.get('noSale') or [])
                   if n.get('code') == code and '2027-02-01' <= n.get('date', '') <= '2027-06-30'}
        missing = []
        for thu in _PUS4_THU:
            for pat in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[pat[0]] - FL_WD['목']) % 7)).isoformat()
                if (dt, pat) not in filled:
                    missing.append('%s %s' % (dt, pat))
        if missing:
            problems.append('G2 %s 2027년 2~6월 빈칸 %d개: %s'
                            % (code, len(missing), missing[:4]))
        ps = [d['price'] for d in r['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30']
        want = EXPECT_G2_FULL[code]
        if len(ps) != want[0]:
            problems.append('G2 %s 2027년 2~6월 값 %d칸 (기대 %d칸)' % (code, len(ps), want[0]))
        elif (min(ps), max(ps)) != want[1:]:
            problems.append('G2 %s 2027년 2~6월 최저·최고 %s (기대 %s)'
                            % (code, (min(ps), max(ps)), want[1:]))
    # 2026-11-18 G2 — 2027년 2~6월 금~월(3박) 21주. 연길·장가계·구이린은 21칸 값,
    # 황산은 9칸이 판매편 0건이고 나머지 12칸이 값이다.
    for code in ROUTE_ORDER_26M:
        r = by_code.get(code)
        if not r:
            continue
        got = {d['date'] for d in r['deals']
               if d['pattern'] == '금~월' and '2027-02-01' <= d['date'] <= '2027-06-30'}
        want = set(_G2_FRIMON)
        if code == 'TXN':
            want -= {d for (c, d) in EXPECT_NOSALE_TXN_26M_FRIMON}
        if got != want:
            problems.append('%s 2027년 2~6월 금~월 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(want), sorted(got ^ want)[:6]))
    # 2027년 2~6월 목~일(3박) 84칸 완주 — 4노선 × 21주 전부 값(0건 없음)
    for code, dates in EXPECT_26M_THU.items():
        r = by_code.get(code)
        if not r:
            continue
        got = {d['date'] for d in r['deals']
               if d['pattern'] == '목~일' and '2027-02-01' <= d['date'] <= '2027-06-30'}
        if got != dates:
            problems.append('%s 2027년 2~6월 목~일 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(dates), sorted(got ^ dates)[:6]))
    # 2027년 2~6월 토~월(2박) — 노선별 실측 출발일 집합과 황산 0건 6주가 원본과 같은지
    for code in ROUTE_ORDER_26M:
        r = by_code.get(code)
        if not r:
            continue
        got = {d['date'] for d in r['deals']
               if d['pattern'] == '토~월' and '2027-02-01' <= d['date'] <= '2027-06-30'}
        want = EXPECT_26M_SAT[code]
        if got != want:
            problems.append('%s 2027년 2~6월 토~월 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(want), sorted(got ^ want)[:6]))
    ns_sat = {(n.get('code'), n.get('date')) for n in (flights.get('noSale') or [])
              if n.get('pattern') == '토~월' and '2027-02-01' <= n.get('date', '') <= '2027-06-30'
              and n.get('code') in ROUTE_ORDER_26M}
    if ns_sat != EXPECT_NOSALE_TXN_26M_SAT:
        problems.append('4노선 2027년 2~6월 토~월 판매편 0건 %d칸 (기대 6칸): %s'
                        % (len(ns_sat), sorted(ns_sat)))
    # 선양·다롄·광저우·샤먼 2027년 2~5월 2박 — 노선·패턴별 출발일 집합
    for code, pats in EXPECT_PUS4_2N.items():
        r = by_code.get(code)
        if not r:
            continue
        for pat, dates in pats.items():
            got = {d['date'] for d in r['deals']
                   if d['pattern'] == pat and '2027-02-01' <= d['date'] <= '2027-06-30'}
            if got != dates:
                problems.append('%s 2027년 2~6월 %s %d칸 (기대 %d칸) 차이: %s'
                                % (code, pat, len(got), len(dates), sorted(got ^ dates)[:6]))
    # 일본 7노선 — 2026년 12월 보완본(150칸)과 당일치기, 2026-11-18 1월 완결본 140칸(값 138 + 항공편 없음 2)까지
    for code in ('CTS', 'FSZ', 'KOJ', 'KMJ', 'MYJ', 'TAK', 'MMY'):
        r = by_code.get(code)
        if not r:
            continue
        dec = [d for d in r['deals'] if d['date'].startswith('2026-12')]
        jan = [d for d in r['deals'] if d['date'].startswith('2027-01')]
        day = [d for d in dec if _fl_nights(d['pattern']) == 0]
        want = EXPECT_JP_DAYTRIP.get(code)
        if want:
            if len(day) != 1 or (day[0]['date'], day[0]['price']) != want:
                problems.append('일본 %s 당일치기 %s (기대 %s)'
                                % (code, [(d['date'], d['price']) for d in day], want))
        elif day:
            problems.append('일본 %s 당일치기 칸이 있음(불가 노선): %s' % (code, day[:2]))
        if len(jan) != EXPECT_JP_JAN[code]:
            problems.append('일본 %s 1월 %d칸 (기대 %d칸 — 12/31 주 3칸 + 1월 완결본)'
                            % (code, len(jan), EXPECT_JP_JAN[code]))
        jan_day = [d for d in jan if _fl_nights(d['pattern']) == 0]
        if len(jan_day) != EXPECT_JP_JAN_DAYTRIP.get(code, 0):
            problems.append('일본 %s 1월 당일치기 %d칸 (기대 %d칸)'
                            % (code, len(jan_day), EXPECT_JP_JAN_DAYTRIP.get(code, 0)))
        # 1월 4주 × 5패턴은 값 또는 '항공편 없음'으로 다 차 있어야 한다(140칸 완결)
        got_keys = {(d['date'], d['pattern']) for d in jan if _fl_nights(d['pattern']) > 0}
        for thu in EXPECT_JAN_WEEKS:
            for label in EXPECT_WEEKEND:
                dt = (datetime.date.fromisoformat(thu) +
                      datetime.timedelta(days=(FL_WD[label[0]] - 4) % 7)).isoformat()
                if (dt, label) not in got_keys and (code, dt, label) not in set(EXPECT_JP_JAN_NOFLIGHT):
                    problems.append('일본 1월 미실측 %s %s %s' % (code, dt, label))
    # 중국 G1(선양·다롄·광저우·샤먼) 2027년 2~6월 21주 × 5패턴 420칸(100%) — 노선별 최저·최고
    for code, (lo, hi) in EXPECT_PUS4_FULL.items():
        r = by_code.get(code)
        if not r:
            continue
        ps = [d['price'] for d in r['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30']
        if len(ps) != 105:
            problems.append('G1 %s 2027년 2~6월 %d칸 (기대 105칸)' % (code, len(ps)))
        elif (min(ps), max(ps)) != (lo, hi):
            problems.append('G1 %s 2027년 2~6월 최저·최고 %s (기대 %s)'
                            % (code, (min(ps), max(ps)), (lo, hi)))
    for m, n in EXPECT_H2_BY_MONTH.items():
        if by_month.get(m) != n:
            problems.append('%s 6~11월 건 %s (기대 %d)' % (m, by_month.get(m), n))
    if h2 != {'weekend': EXPECT_H2['weekend'], 'day': EXPECT_H2['day']}:
        problems.append('6~11월 주말/당일 %s (기대 %s)' % (h2, EXPECT_H2))

    c = flights.get('counts') or {}
    if c.get('daytrip') != day_total:
        problems.append('counts.daytrip %s (실제 %d)' % (c.get('daytrip'), day_total))
    if c.get('total') != sum(len(r['deals']) for r in routes):
        problems.append('counts.total %s (실제 %d)' % (c.get('total'), sum(len(r['deals']) for r in routes)))
    if c.get('byMonth') != {k: by_month[k] for k in sorted(by_month)}:
        problems.append('counts.byMonth 불일치: %s vs %s' % (c.get('byMonth'), by_month))

    # 조회했으나 값이 없는 칸(가격 아님) — deals 와 분리 보관.
    # status: nosale(판매편 없음, 기존 기록은 status 없음) · nofare(요금 미게시) · unopened(예약창 밖)
    codes = {r['code'] for r in routes}
    marks = flights.get('noSale') or []
    nosale = [n for n in marks if (n.get('status') or 'nosale') == 'nosale']
    nofare = [n for n in marks if n.get('status') == 'nofare']
    unopened = [n for n in marks if n.get('status') == 'unopened']
    other = [n for n in marks if n.get('status') not in (None, 'nosale', 'nofare', 'unopened')]
    if other:
        problems.append('noSale 의 status 가 이상합니다: %s' % (other[:3],))
    def _jp26_mark(n):
        """일본 7개 노선 2027년 2~6월 칸인가 — 이 구간은 아래 일본 전수 검사에서 따로 본다."""
        return (n.get('code') in JP26 and n.get('pattern') in JP26_PATS
                and '2027-02-01' <= n.get('date', '') <= '2027-06-30')

    def _jp910_mark(n):
        """일본 7개 노선 2027년 9~10월 칸인가 — 이 구간은 아래 315칸 전수 검사에서 따로 본다."""
        return (n.get('code') in JP910 and n.get('pattern') in EXPECT_WEEKEND
                and '2027-09-01' <= n.get('date', '') <= '2027-10-31')

    def _jp8_mark(n):
        """일본 7개 노선 2027년 8월 칸인가 — 아래 140칸 전수 검사에서 따로 본다."""
        return (n.get('code') in JP8 and n.get('pattern') in EXPECT_WEEKEND
                and n.get('date', '')[:7] == '2027-08')

    def _jp11_mark(n):
        """일본 7개 노선 2027년 11월 칸인가 — 아래 140칸 전수 검사에서 따로 본다."""
        return (n.get('code') in JP11 and n.get('pattern') in EXPECT_WEEKEND
                and n.get('date', '')[:7] == '2027-11')

    def _plain(n):
        return (not _jp26_mark(n) and not _jp910_mark(n) and not _jp8_mark(n)
                and not _jp11_mark(n))
    got_ns = {(n.get('code'), n.get('date')) for n in nosale if _plain(n)}
    if got_ns != EXPECT_NOSALE_ALL:
        problems.append('noSale %d칸 (기대 %d칸) 차이: %s'
                        % (len(got_ns), len(EXPECT_NOSALE_ALL),
                           sorted(got_ns ^ EXPECT_NOSALE_ALL)[:8]))
    got_h2 = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale
              if n.get('date', '') >= '2027-07-01' and n.get('code') in H2_ROUTES}
    if got_h2 != EXPECT_NOSALE_H2:
        problems.append('2027년 7~11월 판매편 0건 %d칸 (기대 %d칸) 차이: %s'
                        % (len(got_h2), len(EXPECT_NOSALE_H2), sorted(got_h2 ^ EXPECT_NOSALE_H2)[:6]))
    got_fr = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale
              if n.get('pattern') == '금~월' and '2027-02-01' <= n.get('date', '') <= '2027-06-30'
              and n.get('code') in ROUTE_ORDER_26M}
    if got_fr != {(c, d, '금~월') for (c, d) in EXPECT_NOSALE_TXN_26M_FRIMON}:
        problems.append('2027년 2~6월 금~월 판매편 0건 %d칸 (기대 %d칸): %s'
                        % (len(got_fr), len(EXPECT_NOSALE_TXN_26M_FRIMON), sorted(got_fr)[:6]))
    for n in marks:
        if n.get('code') not in codes or not (WINDOW_START <= n.get('date', '') <= WINDOW_END):
            problems.append('noSale 이상: %s' % (n,))
        if 'price' in n:
            problems.append('noSale 에 가격이 들어 있음(추정 금지): %s' % (n,))
        key = (n.get('code'), n.get('date'), n.get('pattern'))
        if key in deal_keys:
            problems.append('noSale 가 실측 딜과 겹침: %s' % (key,))
    # 요금 미공개(운항편은 표시되나 요금 미게시) — 2027년 7~11월 255칸 (일본 7노선 2~6월은 아래에서 따로)
    nofare_h2 = [n for n in nofare if _plain(n)]
    if len(nofare_h2) != EXPECT_NOFARE_TOTAL:
        problems.append('요금 미공개 %d칸 (기대 %d칸)' % (len(nofare_h2), EXPECT_NOFARE_TOTAL))
    got_nf = {(n.get('code'), n.get('pattern')) for n in nofare_h2}
    want_nf = {(c, p) for c, pats in H2_NOFARE_PATS.items() for p in pats}
    if got_nf != want_nf:
        problems.append('요금 미공개 (노선·패턴) 이상: %s' % sorted(got_nf ^ want_nf))
    if {(n.get('code'), n.get('date'), n.get('pattern')) for n in nofare_h2} != _h2_keys(H2_NOFARE_PATS):
        problems.append('요금 미공개 칸(출발일)이 원문과 다릅니다.')
    # 미오픈(예약창 밖) — 중국 8노선 × 10/15·11/12 금~일 16칸 + 동남아 4노선 09-16 주 이후 11주 220칸
    unopened_plain = [n for n in unopened if _plain(n)]
    if len(unopened_plain) != EXPECT_UNOPENED_TOTAL:
        problems.append('미오픈 %d칸 (기대 %d칸)' % (len(unopened_plain), EXPECT_UNOPENED_TOTAL))
    want_up = {(c, d, '금~일') for c in H2_ROUTES for d in H2_PROBE_DATES}
    want_up |= {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for c in SEA4 for thu in SEA_H2_UNOPENED for p in EXPECT_WEEKEND}
    want_up |= {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for c in EXPECT_PH4 for thu in PH4_H2_WEEKS if thu >= PH4_LAST_SALE
                for p in EXPECT_WEEKEND}
    want_up |= {('FSZ', (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for thu in JP_JUL_WEEKS for p in EXPECT_WEEKEND}
    if {(n.get('code'), n.get('date'), n.get('pattern')) for n in unopened_plain} != want_up:
        problems.append('미오픈 칸이 원문(중국 16칸 + 동남아 220칸 + 필리핀 140칸 + 일본 시즈오카 7월 25칸)과 다릅니다.')

    # 일본 7개 노선 2027년 9~10월 — 9주 × 5패턴 315칸 전수(값 190 + 0건 34 + 미확인 4 + 미오픈 87)
    jp10_grid = {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                 for c in JP910 for thu in JP910_WEEKS for p in EXPECT_WEEKEND}
    jp10_deals = {(r['code'], d['date'], d['pattern']) for r in routes if r['code'] in JP910
                  for d in r['deals'] if '2027-09-01' <= d['date'] <= '2027-10-31'}
    jp10_ns = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale if _jp910_mark(n)}
    jp10_nf = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nofare if _jp910_mark(n)}
    jp10_up = {(n.get('code'), n.get('date'), n.get('pattern')) for n in unopened if _jp910_mark(n)}
    if len(jp10_grid) != EXPECT_JP910_CELLS:
        problems.append('일본 7노선 2027년 9~10월 격자 %d칸 (기대 %d칸)'
                        % (len(jp10_grid), EXPECT_JP910_CELLS))
    for label, got in (('실측', jp10_deals), ('판매편 0건', jp10_ns),
                       ('요금 미확인', jp10_nf), ('미오픈', jp10_up)):
        if len(got) != {'실측': EXPECT_JP910_PRICED, '판매편 0건': EXPECT_JP910_NOSALE,
                        '요금 미확인': EXPECT_JP910_NOFARE, '미오픈': EXPECT_JP910_UNOPENED}[label]:
            problems.append('일본 7노선 2027년 9~10월 %s %d칸 (기대 %d칸)'
                            % (label, len(got), {'실측': EXPECT_JP910_PRICED,
                                                 '판매편 0건': EXPECT_JP910_NOSALE,
                                                 '요금 미확인': EXPECT_JP910_NOFARE,
                                                 '미오픈': EXPECT_JP910_UNOPENED}[label]))
    if (jp10_deals | jp10_ns | jp10_nf | jp10_up) != jp10_grid:
        problems.append('일본 7노선 2027년 9~10월 315칸이 값·0건·미확인·미오픈으로 다 차지 않았습니다: %s'
                        % sorted(jp10_grid - (jp10_deals | jp10_ns | jp10_nf | jp10_up))[:6])
    for code in JP910:
        r = by_code.get(code)
        if not r:
            problems.append('일본 9~10월 노선 %s 없음' % code)
            continue
        got = [d for d in r['deals'] if '2027-09-01' <= d['date'] <= '2027-10-31']
        n, _ns, _nf, _up, low, high, direct = EXPECT_JP910[code]
        if len(got) != n:
            problems.append('일본 %s 2027년 9~10월 값 %d칸 (기대 %d칸)' % (code, len(got), n))
            continue
        if not got:
            continue
        vals = [d['price'] for d in got]
        if (min(vals), max(vals)) != (low, high):
            problems.append('일본 %s 2027년 9~10월 최저·최고 %s (기대 %s)'
                            % (code, (min(vals), max(vals)), (low, high)))
        if sum(1 for d in got if d.get('via') is False) != direct:
            problems.append('일본 %s 2027년 9~10월 직항이 최저가인 칸 %d (기대 %d)'
                            % (code, sum(1 for d in got if d.get('via') is False), direct))
        mine_ns = sum(1 for (c, _d, _p) in jp10_ns if c == code)
        mine_nf = sum(1 for (c, _d, _p) in jp10_nf if c == code)
        mine_up = sum(1 for (c, _d, _p) in jp10_up if c == code)
        if (mine_ns, mine_nf, mine_up) != (_ns, _nf, _up):
            problems.append('일본 %s 2027년 9~10월 상태(0건·미확인·미오픈) %s (기대 %s)'
                            % (code, (mine_ns, mine_nf, mine_up), (_ns, _nf, _up)))
    for key, price in EXPECT_JP910_LOW.items():
        r = by_code.get(key[0])
        hit = next((d for d in (r['deals'] if r else [])
                    if d['date'] == key[1] and d['pattern'] == key[2]), None)
        if not hit or hit['price'] != price:
            problems.append('일본 9~10월 칸 %s (%s원)이 없습니다' % (key, price))
    # 일본 7개 노선 2027년 8월 — 4주 × 5패턴 140칸 전수(값 120 + 미오픈 20)
    jp8_grid = {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for c in JP8 for thu in JP8_WEEKS for p in EXPECT_WEEKEND}
    jp8_deals = {(r['code'], d['date'], d['pattern']) for r in routes if r['code'] in JP8
                 for d in r['deals'] if d['date'][:7] == '2027-08'}
    jp8_up = {(n.get('code'), n.get('date'), n.get('pattern')) for n in unopened if _jp8_mark(n)}
    jp8_ns = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale if _jp8_mark(n)}
    if len(jp8_grid) != EXPECT_JP8_CELLS:
        problems.append('일본 7노선 2027년 8월 격자 %d칸 (기대 %d칸)'
                        % (len(jp8_grid), EXPECT_JP8_CELLS))
    if len(jp8_deals) != EXPECT_JP8_PRICED:
        problems.append('일본 7노선 2027년 8월 실측 %d칸 (기대 %d칸)'
                        % (len(jp8_deals), EXPECT_JP8_PRICED))
    if len(jp8_up) != EXPECT_JP8_UNOPENED or jp8_ns:
        problems.append('일본 7노선 2027년 8월 미오픈 %d칸 · 판매편 0건 %d칸 (기대 %d · 0칸)'
                        % (len(jp8_up), len(jp8_ns), EXPECT_JP8_UNOPENED))
    if (jp8_deals | jp8_up) != jp8_grid:
        problems.append('일본 7노선 2027년 8월 140칸이 값·미오픈으로 다 차지 않았습니다: %s'
                        % sorted(jp8_grid - (jp8_deals | jp8_up))[:6])
    for code in JP8:
        r = by_code.get(code)
        got = [d for d in (r['deals'] if r else []) if d['date'][:7] == '2027-08']
        n, _ns, _up, low, high, direct = EXPECT_JP8[code]
        if len(got) != n:
            problems.append('일본 %s 2027년 8월 값 %d칸 (기대 %d칸)' % (code, len(got), n))
            continue
        if not got:
            continue
        vals = [d['price'] for d in got]
        if (min(vals), max(vals)) != (low, high):
            problems.append('일본 %s 2027년 8월 최저·최고 %s (기대 %s)'
                            % (code, (min(vals), max(vals)), (low, high)))
        if sum(1 for d in got if d.get('via') is False) != direct:
            problems.append('일본 %s 2027년 8월 직항이 최저가인 칸 %d (기대 %d)'
                            % (code, sum(1 for d in got if d.get('via') is False), direct))
    for key, price in EXPECT_JP8_LOW.items():
        r = by_code.get(key[0])
        hit = next((d for d in (r['deals'] if r else [])
                    if d['date'] == key[1] and d['pattern'] == key[2]), None)
        if not hit or hit['price'] != price:
            problems.append('일본 8월 칸 %s (%s원)이 없습니다' % (key, price))

    # 일본 7개 노선 2027년 11월 — 4주 × 5패턴 140칸 전수(값 33 + 미오픈 87 + 시즈오카 판매편 0건 20)
    jp11_grid = {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                 for c in JP11 for thu in JP11_WEEKS for p in EXPECT_WEEKEND}
    jp11_deals = {(r['code'], d['date'], d['pattern']) for r in routes if r['code'] in JP11
                  for d in r['deals'] if d['date'][:7] == '2027-11'}
    jp11_up = {(n.get('code'), n.get('date'), n.get('pattern')) for n in unopened
               if _jp11_mark(n)}
    jp11_ns = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale
               if _jp11_mark(n)}
    if len(jp11_grid) != EXPECT_JP11_CELLS:
        problems.append('일본 7노선 2027년 11월 격자 %d칸 (기대 %d칸)'
                        % (len(jp11_grid), EXPECT_JP11_CELLS))
    if len(jp11_deals) != EXPECT_JP11_PRICED:
        problems.append('일본 7노선 2027년 11월 실측 %d칸 (기대 %d칸)'
                        % (len(jp11_deals), EXPECT_JP11_PRICED))
    if (len(jp11_up), len(jp11_ns)) != (EXPECT_JP11_UNOPENED, EXPECT_JP11_NOSALE):
        problems.append('일본 7노선 2027년 11월 미오픈 %d칸 · 판매편 0건 %d칸 (기대 %d · %d칸)'
                        % (len(jp11_up), len(jp11_ns), EXPECT_JP11_UNOPENED,
                           EXPECT_JP11_NOSALE))
    if (jp11_deals | jp11_up | jp11_ns) != jp11_grid:
        problems.append('일본 7노선 2027년 11월 140칸이 값·미오픈·0건으로 다 차지 않았습니다: %s'
                        % sorted(jp11_grid - (jp11_deals | jp11_up | jp11_ns))[:6])
    for code in JP11:
        r = by_code.get(code)
        got = [d for d in (r['deals'] if r else []) if d['date'][:7] == '2027-11']
        n, ns, up, low, high, direct = EXPECT_JP11[code]
        if len(got) != n:
            problems.append('일본 %s 2027년 11월 값 %d칸 (기대 %d칸)' % (code, len(got), n))
            continue
        mine_ns = sum(1 for (c, _d, _p) in jp11_ns if c == code)
        mine_up = sum(1 for (c, _d, _p) in jp11_up if c == code)
        if (mine_ns, mine_up) != (ns, up):
            problems.append('일본 %s 2027년 11월 상태(0건·미오픈) %s (기대 %s)'
                            % (code, (mine_ns, mine_up), (ns, up)))
        if not got:
            continue
        vals = [d['price'] for d in got]
        if (min(vals), max(vals)) != (low, high):
            problems.append('일본 %s 2027년 11월 최저·최고 %s (기대 %s)'
                            % (code, (min(vals), max(vals)), (low, high)))
        if sum(1 for d in got if d.get('via') is False) != direct:
            problems.append('일본 %s 2027년 11월 직항이 최저가인 칸 %d (기대 %d)'
                            % (code, sum(1 for d in got if d.get('via') is False), direct))
    for key, price in EXPECT_JP11_LOW.items():
        r = by_code.get(key[0])
        hit = next((d for d in (r['deals'] if r else [])
                    if d['date'] == key[1] and d['pattern'] == key[2]), None)
        if not hit or hit['price'] != price:
            problems.append('일본 11월 칸 %s (%s원)이 없습니다' % (key, price))

    for key, alt in EXPECT_JP910_ALT.items():
        r = by_code.get(key[0])
        hit = next((d for d in (r['deals'] if r else [])
                    if d['date'] == key[1] and d['pattern'] == key[2]), None)
        if not hit or hit.get('alt') != alt:
            problems.append('일본 9~10월 직항 병기 %s (%s원)이 없습니다' % (key, alt))

    # 일본 7개 노선 2027년 2~6월 — 21주 × 7패턴 1,029칸 전수(값 523 + 0건 303 + 미공개 98 + 빈칸 105)
    jp_grid = {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
               for c in JP26 for thu in JP26_WEEKS for p in JP26_PATS}
    jp_deals = {(r['code'], d['date'], d['pattern'])
                for r in routes if r['code'] in JP26 for d in r['deals']
                if '2027-02-01' <= d['date'] <= '2027-06-30'}
    jp_ns = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nosale if _jp26_mark(n)}
    jp_nf = {(n.get('code'), n.get('date'), n.get('pattern')) for n in nofare if _jp26_mark(n)}
    jp_blank = jp_grid - jp_deals - jp_ns - jp_nf
    if len(jp_grid) != EXPECT_JP26_CELLS:
        problems.append('일본 7노선 2027년 2~6월 격자 %d칸 (기대 %d칸)'
                        % (len(jp_grid), EXPECT_JP26_CELLS))
    if len(jp_deals) != EXPECT_JP26_DEALS:
        problems.append('일본 7노선 2027년 2~6월 실측 %d칸 (기대 %d칸)'
                        % (len(jp_deals), EXPECT_JP26_DEALS))
    if len(jp_ns) != EXPECT_JP26_NOSALE:
        problems.append('일본 7노선 2027년 2~6월 판매편 0건 %d칸 (기대 %d칸)'
                        % (len(jp_ns), EXPECT_JP26_NOSALE))
    if len(jp_nf) != EXPECT_JP26_NOFARE:
        problems.append('일본 7노선 2027년 2~6월 요금 미공개 %d칸 (기대 %d칸)'
                        % (len(jp_nf), EXPECT_JP26_NOFARE))
    if len(jp_blank) != EXPECT_JP26_BLANK:
        problems.append('일본 7노선 2027년 2~6월 미조회 %d칸 (기대 %d칸)'
                        % (len(jp_blank), EXPECT_JP26_BLANK))
    if jp_deals & (jp_ns | jp_nf) or jp_ns & jp_nf:
        problems.append('일본 7노선 2027년 2~6월 상태가 겹칩니다: %s'
                        % sorted((jp_deals & (jp_ns | jp_nf)) | (jp_ns & jp_nf))[:4])
    for code in JP26:
        for part, pats in (('주말형', JP26_WK), ('당일치기', JP26_DAY)):
            mine = [k for k in jp_grid if k[0] == code and k[2] in pats]
            got = (len([k for k in mine if k in jp_deals]),
                   len([k for k in mine if k in jp_ns]),
                   len([k for k in mine if k in jp_nf]),
                   len([k for k in mine if k in jp_blank]))
            want = EXPECT_JP26_STATUS[code][part]
            if got != want:
                problems.append('일본 %s %s (실측·0건·미공개·미조회) %s (기대 %s)'
                                % (code, part, got, want))
        r = by_code.get(code)
        got_p = [d for d in r['deals'] if '2027-02-01' <= d['date'] <= '2027-06-30']
        n, low, high, direct = EXPECT_JP26[code]
        if len(got_p) != n:
            problems.append('일본 %s 2027년 2~6월 값 %d칸 (기대 %d칸)' % (code, len(got_p), n))
            continue
        vals = [d['price'] for d in got_p]
        if (min(vals), max(vals)) != (low, high):
            problems.append('일본 %s 2027년 2~6월 최저·최고 %s (기대 %s)'
                            % (code, (min(vals), max(vals)), (low, high)))
        if sum(1 for d in got_p if d.get('via') is False) != direct:
            problems.append('일본 %s 2027년 2~6월 직항이 최저가인 칸 %d (기대 %d)'
                            % (code, sum(1 for d in got_p if d.get('via') is False), direct))
    for m, want in EXPECT_JP26_BY_MONTH.items():
        got = sum(1 for c, d, p in jp_deals if d[:7] == m)
        if got != want:
            problems.append('일본 7노선 %s 실측 %d칸 (기대 %d칸)' % (m, got, want))
    if '일본 7개 노선' not in (flights.get('notes', {}).get('2027-02') or ''):
        problems.append('2027-02 notes 에 일본 7개 노선 커버리지가 없습니다.')

    # 필리핀 4노선 2027년 7~11월 — 실측 126칸 + 미오픈 140칸 + 미조회 174칸(빈칸)
    ph4_grid = {(c, (datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for c in EXPECT_PH4 for thu in PH4_H2_WEEKS for p in EXPECT_WEEKEND}
    ph4_deals = {(r['code'], d['date'], d['pattern']) for r in routes
                 if r['code'] in EXPECT_PH4 for d in r['deals']
                 if '2027-07-01' <= d['date'] <= '2027-11-29'}
    ph4_up = {(c, d, p) for (c, d, p) in want_up if c in EXPECT_PH4}
    if len(ph4_grid) != len(EXPECT_PH4) * len(PH4_H2_WEEKS) * len(EXPECT_WEEKEND):
        problems.append('필리핀 7~11월 격자 %d칸 (440칸이어야 함)' % len(ph4_grid))
    if ph4_deals & ph4_up:
        problems.append('필리핀 7~11월 실측 칸이 미오픈 칸과 겹칩니다: %s'
                        % sorted(ph4_deals & ph4_up)[:4])
    for code, (n, low, high, direct) in EXPECT_PH4_H2.items():
        r = by_code.get(code)
        if not r:
            problems.append('필리핀 노선 %s 없음' % code)
            continue
        got = [d for d in r['deals'] if '2027-07-01' <= d['date'] <= '2027-11-29']
        if len(got) != n:
            problems.append('필리핀 %s 2027년 7~11월 실측 %d칸 (기대 %d칸)'
                            % (code, len(got), n))
            continue
        vals = [d['price'] for d in got]
        if (min(vals), max(vals)) != (low, high):
            problems.append('필리핀 %s 2027년 7~11월 최저·최고 %s (기대 %s)'
                            % (code, (min(vals), max(vals)), (low, high)))
        if sum(1 for d in got if d.get('via') is False) != direct:
            problems.append('필리핀 %s 2027년 7~11월 직항이 최저가인 칸 %d (기대 %d)'
                            % (code, sum(1 for d in got if d.get('via') is False), direct))
        missing = {k for k in ph4_grid if k[0] == code} - ph4_deals - ph4_up
        if len(missing) != EXPECT_PH4_H2_MISSING[code]:
            problems.append('필리핀 %s 2027년 7~11월 미조회 %d칸 (기대 %d칸)'
                            % (code, len(missing), EXPECT_PH4_H2_MISSING[code]))
    for key, price in EXPECT_PH4_H2_LOW.items():
        r = by_code.get(key[0])
        hit = next((d for d in (r['deals'] if r else [])
                    if d['date'] == key[1] and d['pattern'] == key[2]), None)
        if not hit or hit['price'] != price:
            problems.append('필리핀 7~11월 최저 칸 %s (%s원)이 없습니다' % (key, price))

    # 동남아 4노선 2027년 7~11월 — 11주 × 5패턴 220칸 실측(최저/최고/평균), 09-16 주 이후는 미오픈
    for code, (n, low, high, avg) in EXPECT_SEA_H2.items():
        r = by_code.get(code)
        if not r:
            problems.append('동남아 노선 %s 없음' % code)
            continue
        got = {(d['date'], d['pattern']): d for d in r['deals']
               if '2027-07-01' <= d['date'] <= '2027-11-29'}
        want = {((datetime.date.fromisoformat(thu) + datetime.timedelta(
                    days=(FL_WD[p[0]] - FL_WD['목']) % 7)).isoformat(), p)
                for thu in SEA_H2_MEASURED for p in EXPECT_WEEKEND}
        if set(got) != want:
            problems.append('%s 2027년 7~11월 실측 %d칸 (기대 %d칸) 차이: %s'
                            % (code, len(got), len(want), sorted(set(got) ^ want)[:6]))
        vals = [d['price'] for d in got.values()]
        if len(vals) == n and (min(vals), max(vals), round(sum(vals) / len(vals))) != (low, high, avg):
            problems.append('%s 2027년 7~11월 최저/최고/평균 %s (기대 %s)'
                            % (code, (min(vals), max(vals), round(sum(vals) / len(vals))),
                               (low, high, avg)))
    # 동남아 4노선 실측 칸의 월별 분포(7월 100 · 8월 80 · 9월 40)
    for m, want_n in (('2027-07', 100), ('2027-08', 80), ('2027-09', 40)):
        got_n = sum(1 for r in routes if r['code'] in SEA4 for d in r['deals']
                    if d['date'][:7] == m)
        if got_n != want_n:
            problems.append('동남아 %s 실측 %d칸 (기대 %d칸)' % (m, got_n, want_n))

    notes = flights.get('notes') or {}
    for m in notes:
        if m not in EXPECT_MONTHS:
            problems.append('notes 의 월 %s 이상' % m)
    bw = flights.get('bookingWindow') or {}
    if bw.get('end') != EXPECT_BOOKING_END:
        problems.append('bookingWindow.end %r (기대 %s)' % (bw.get('end'), EXPECT_BOOKING_END))
    if bw.get('sea4End') != EXPECT_BOOKING_SEA4:
        problems.append('bookingWindow.sea4End %r (기대 %s)' % (bw.get('sea4End'),
                                                              EXPECT_BOOKING_SEA4))
    if bw.get('ph4End') != EXPECT_BOOKING_PH4:
        problems.append('bookingWindow.ph4End %r (기대 %s)' % (bw.get('ph4End'),
                                                              EXPECT_BOOKING_PH4))
    return problems


# ---------------------------------------------------------------- 추출 / 주입

def _read(path):
    with open(path, encoding='utf-8') as fp:
        return fp.read()


def find_literal(src, name):
    """`const NAME = <json>` 의 (시작, 끝) 오프셋을 중괄호 짝으로 찾는다."""
    m = re.search(r'\bconst\s+' + re.escape(name) + r'\s*=\s*', src)
    if not m:
        raise SystemExit('index.html 에서 const %s 를 찾지 못했습니다.' % name)
    i = m.end()
    while i < len(src) and src[i] not in '{[':
        i += 1
    opener = src[i]
    closer = '}' if opener == '{' else ']'
    depth, in_str, esc, j = 0, False, False, i
    while j < len(src):
        c = src[j]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return i, j + 1
        j += 1
    raise SystemExit('const %s 의 JSON 이 닫히지 않았습니다.' % name)


def read_db_literal(path=INDEX):
    """index.html 의 `const DB` — 호텔을 뺀 집계·출처 블록과 그 위치."""
    src = _read(path)
    a, b = find_literal(src, 'DB')
    return src, json.loads(src[a:b]), (a, b)


def part_path(name):
    return os.path.join(APP_DIR, name)


def write_part(name, obj):
    """탭별 JSON 한 파일 — 들여쓰기 없이 + 전송용 압축 인코딩으로 써서 전송량을 줄인다."""
    path = part_path(name)
    os.makedirs(APP_DIR, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        fp.write(compact(encode_part(obj)))
        fp.write('\n')
    os.replace(tmp, path)


def read_parts():
    """data/app/*.json — (탭별 호텔 묶음, 호텔 전체, 항공, 땡처리)."""
    parts, hotels = {}, []
    for tab, name in PART_TABS:
        part = decode_part(json.loads(_read(part_path(name))))
        if part.get('tab') != tab:
            raise SystemExit('%s: tab 이 %r (기대 %r)' % (name, part.get('tab'), tab))
        if part.get('count') != len(part.get('hotels') or []):
            raise SystemExit('%s: count 와 hotels 수가 다릅니다 (%r vs %d)'
                             % (name, part.get('count'), len(part.get('hotels') or [])))
        parts[tab] = part
        hotels.extend(part['hotels'])
    flights = decode_part(json.loads(_read(part_path(PART_FLIGHTS))))
    tt = decode_part(json.loads(_read(part_path(PART_TTANG))))
    return parts, hotels, flights, tt


def split_hotels(hotels):
    """호텔을 탭(group)별 묶음으로 나눈다 — 각 탭 안의 순서는 원본 그대로 보존."""
    out = {tab: [] for tab in PART_ORDER}
    for h in hotels:
        g = h.get('group')
        if g not in out:
            raise SystemExit('알 수 없는 group %r (호텔 %s)' % (g, h.get('id')))
        out[g].append(h)
    return out


def write_parts(master):
    """master_db.json -> data/app/*.json (탭별 지연 로딩 배포본)."""
    groups = split_hotels(master['hotels'])
    for tab, name in PART_TABS:
        part = {'tab': tab, 'count': len(groups[tab]), 'hotels': groups[tab]}
        if tab == 'accor':
            part['accor'] = master.get('accor')
        write_part(name, part)
    write_part(PART_FLIGHTS, master['flights'])
    write_part(PART_TTANG, master.get('ttang') or {'deals': []})
    return groups


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


# ------------------------------------------------- 전송용 압축 인코딩(5단계)
# data/app/*.json 은 앱이 fetch 해서 그대로 쓰는 배포본이라 **앱이 보는 구조는 그대로**여야
# 한다. 그래서 파일에만 아래 두 가지를 적용하고, 읽을 때(read_parts)와 앱(loadPart)이
# 같은 규칙으로 되돌린다. master_db.json(정본)과 index.html 의 구조는 건드리지 않는다.
#
#   · 날짜 맵  {"2026-12-01":240000,"2026-12-02":236000,…}  (연속·오름차순 365일)
#        ->  {"$d":"2026-12-01","$v":[240000,236000,…]}
#        날짜 키 196,370개(약 2.5MB)를 시작일 + 값 배열로 바꾼다.
#   · 객체 배열 [{…},{…},…] (3개 이상)
#        ->  {"$t":[키…],"$r":[[값…],…]}   없는 키는 "$~"(ABSENT)
#        같은 키 이름을 행마다 반복하지 않는다.
# 되돌린 결과는 원본과 **구조적으로 같다**(키 순서는 표 순서로 정규화).

ABSENT = '$~'
_DATE_KEY = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _is_date_key(k):
    return isinstance(k, str) and bool(_DATE_KEY.match(k))


def _as_date(k):
    try:
        return datetime.date.fromisoformat(k)
    except ValueError:
        return None


def _date_map(o):
    """연속·오름차순 날짜 키 맵이면 압축 표현을, 아니면 None."""
    if not isinstance(o, dict) or not o:
        return None
    keys = list(o.keys())
    if not all(_is_date_key(k) for k in keys):
        return None
    if keys != sorted(keys):
        return None
    ds = [_as_date(k) for k in keys]
    if any(a is None for a in ds):
        return None
    for a, b in zip(ds, ds[1:]):
        if (b - a).days != 1:
            return None
    return {'$d': keys[0], '$v': [encode_part(v) for v in o.values()]}


def encode_part(o):
    """앱 배포 JSON -> 전송용 압축 표현(되돌리면 원본과 구조적으로 같다)."""
    if isinstance(o, dict):
        dm = _date_map(o)
        if dm is not None:
            return dm
        return {k: encode_part(v) for k, v in o.items()}
    if isinstance(o, list):
        if len(o) >= 3 and all(isinstance(x, dict) for x in o):
            cols = []
            for x in o:
                for k in x:
                    if k not in cols:
                        cols.append(k)
            rows = []
            for x in o:
                row = []
                for k in cols:
                    if k in x:
                        row.append(encode_part(x[k]))
                    else:
                        row.append(ABSENT)
                rows.append(row)
            return {'$t': cols, '$r': rows}
        return [encode_part(x) for x in o]
    if o == ABSENT:
        raise SystemExit('전송용 압축: 값 %r 이 예약어와 겹칩니다' % ABSENT)
    return o


def decode_part(o):
    """전송용 압축 표현 -> 앱이 쓰는 원래 구조."""
    if isinstance(o, dict):
        if '$d' in o and '$v' in o and isinstance(o.get('$v'), list):
            start = _as_date(o['$d'])
            if start is None:
                raise SystemExit('전송용 압축: 날짜 맵 시작일이 잘못됐습니다 %r' % o.get('$d'))
            out = {}
            for i, v in enumerate(o['$v']):
                out[(start + datetime.timedelta(days=i)).isoformat()] = decode_part(v)
            return out
        if '$t' in o and '$r' in o and isinstance(o.get('$t'), list):
            cols = o['$t']
            out = []
            for row in o['$r']:
                if not isinstance(row, list) or len(row) != len(cols):
                    raise SystemExit('전송용 압축: 표 행 길이가 열 수와 다릅니다')
                item = {}
                for k, v in zip(cols, row):
                    if v == ABSENT:
                        continue
                    item[k] = decode_part(v)
                out.append(item)
            return out
        return {k: decode_part(v) for k, v in o.items()}
    if isinstance(o, list):
        return [decode_part(x) for x in o]
    return o


def plain_size(obj):
    return len(compact(obj).encode('utf-8'))


def encoded_size(obj):
    return len(compact(encode_part(obj)).encode('utf-8'))


# ---------------------------------------------------------------- 통계

def stats_of(db, flights, tt=None):
    hotels = db['hotels']
    cells = sum(len(h.get('rates') or {}) for h in hotels)
    priced = sum(1 for h in hotels for v in (h.get('rates') or {}).values() if v is not None)
    stayplus = sum(len(h.get('stayplus2') or {}) + len(h.get('stayplus3') or {}) for h in hotels)
    tabs = {}
    for h in hotels:
        tabs[h.get('group')] = tabs.get(h.get('group'), 0) + 1
    routes = flights.get('routes') or []
    deals = sum(len(r.get('deals') or []) for r in routes)
    redhot_cells = sum(len(h.get('redhotRates') or {}) for h in hotels)
    redhot_hotels = sum(1 for h in hotels if h.get('redhot'))
    dates = set()
    for h in hotels:
        dates.update((h.get('rates') or {}).keys())
    return {
        'hotels': len(hotels),
        'tabs': tabs,
        'snu': len(((db.get('accor') or {}).get('rows')) or []),
        'cells': cells,
        'priced': priced,
        'na': cells - priced,
        'stayplus': stayplus,
        'routes': len(routes),
        'deals': deals,
        'pus_deals': len(((tt or {}).get('deals')) or []),
        'pus_routes': len({d.get('code') for d in ((tt or {}).get('deals') or [])}),
        'redhot_hotels': redhot_hotels,
        'redhot_cells': redhot_cells,
        'priced_per_hotel': {h['id']: sum(1 for v in (h.get('rates') or {}).values() if v is not None)
                             for h in hotels},
        'cells_per_hotel': {h['id']: len(h.get('rates') or {}) for h in hotels},
        'dates': len(dates),
        'date_min': min(dates) if dates else None,
        'date_max': max(dates) if dates else None,
    }


# ---------------------------------------------------------------- extract

def cmd_extract(args):
    _, dbmeta, _ = read_db_literal()
    parts, hotels, flights, tt = read_parts()
    accor = parts['accor'].get('accor')
    commit = os.environ.get('MASTER_DB_COMMIT', '')
    if not commit:
        try:
            import subprocess
            commit = subprocess.check_output(['git', '-C', ROOT, 'rev-parse', '--short', 'HEAD'],
                                             text=True).strip()
        except Exception:
            commit = 'unknown'
    st = stats_of({'hotels': hotels, 'accor': accor}, flights, tt)
    master = {
        'schema': 'hotel-calendar-app/master-db',
        'version': 1,
        'generated_at': args.now,
        'source': {'file': 'data/app/*.json', 'commit': commit, 'tool': 'tools/master_db.py extract'},
        'window': {'start': WINDOW_START, 'end': WINDOW_END, 'days': 365},
        'built': dbmeta.get('built'),
        'voucherExpiry': dbmeta.get('voucherExpiry'),
        'extended': dbmeta.get('extended'),
        'counts': {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na', 'stayplus',
                                      'routes', 'deals', 'snu', 'pus_deals', 'pus_routes',
                                      'redhot_hotels', 'redhot_cells')},
        'sources': dbmeta.get('sources') or [],
        'hotels': hotels,
        'flights': flights,
        'ttang': tt,
        'accor': accor,
    }
    os.makedirs(os.path.dirname(MASTER), exist_ok=True)
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('wrote %s' % os.path.relpath(MASTER, ROOT))
    print('  hotels %(hotels)d  cells %(cells)d  priced %(priced)d  na %(na)d' % st)
    print('  stayplus %(stayplus)d  routes %(routes)d  deals %(deals)d' % st)
    print('  ⑥ 땡처리 %(pus_deals)d건 · %(pus_routes)d개 노선' % st)
    print('  date window %s ~ %s (%d days)' % (st['date_min'], st['date_max'], st['dates']))
    return 0


# ---------------------------------------------------------------- verify

def project(master):
    """master_db.json -> 검사·통계용 전체 DB(호텔 포함)."""
    db = {
        'hotels': master['hotels'],
        'sources': master['sources'],
        'built': master['built'],
        'voucherExpiry': master['voucherExpiry'],
        'extended': master['extended'],
        'accor': master.get('accor'),
    }
    return db, master['flights'], master.get('ttang') or {'deals': []}


def project_meta(master):
    """master_db.json -> index.html 의 `const DB` (호텔은 탭별 JSON 으로 빠지고 집계값만 남는다)."""
    return {
        'hotels': [],
        'sources': master['sources'],
        'built': master['built'],
        'voucherExpiry': master['voucherExpiry'],
        'extended': master['extended'],
        'accor': None,
        'counts': master.get('counts') or {},
    }


def check_tabs(db):
    """탭별 호텔 수와 ⑤ 메리어트 40곳의 브랜드 구성을 검사한다."""
    problems = []
    tabs = {}
    for h in db['hotels']:
        tabs[h.get('group')] = tabs.get(h.get('group'), 0) + 1
    for tab, n in EXPECT_TABS.items():
        if tabs.get(tab) != n:
            problems.append('tabs.%s %s곳 (기대 %d곳)' % (tab, tabs.get(tab), n))
    extra = {k: v for k, v in tabs.items() if k not in EXPECT_TABS}
    if extra:
        problems.append('알 수 없는 탭: %s' % extra)
    if len(db['hotels']) != EXPECT_HOTELS:
        problems.append('호텔 합계 %d곳 (기대 %d곳 = %s)' % (
            len(db['hotels']), EXPECT_HOTELS,
            ' + '.join(str(EXPECT_TABS[t]) for t in ('lux', 'accor', 'marriott'))))
    brands = {}
    ids = set()
    for h in db['hotels']:
        if h['id'] in ids:
            problems.append('호텔 id 중복: %s' % h['id'])
        ids.add(h['id'])
        if h.get('group') == 'marriott':
            brands[h.get('brand')] = brands.get(h.get('brand'), 0) + 1
            for k in ('brand', 'city', 'name', 'source'):
                if not h.get(k):
                    problems.append('메리어트 호텔 %s 에 %s 없음' % (h['id'], k))
    if brands != EXPECT_BRANDS:
        problems.append('메리어트 브랜드 구성 %s (기대 %s)' % (brands, EXPECT_BRANDS))

    # ⑤ 한·일 22곳: 현금·포인트 칸 수와 교차 참조
    kj = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in KJ_IDS]
    cash = sum(1 for h in kj for v in (h.get('rates') or {}).values() if v is not None)
    pts = sum(1 for h in kj for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(kj) != EXPECT_KJ['hotels'] or cash != EXPECT_KJ['cash'] or pts != EXPECT_KJ['points']:
        problems.append('한·일 22곳 수치 %s (기대 %s)' % (
            {'hotels': len(kj), 'cash': cash, 'points': pts}, EXPECT_KJ))
    # 2026-11-23 — 한국 신규 30곳(k11~k40)도 칸 수를 고정해 둔다(유실·보간 방지)
    kr30 = [h for h in db['hotels'] if h.get('group') == 'marriott'
            and h['id'][0] == 'k' and h['id'] not in KJ_IDS]
    c30 = sum(1 for h in kr30 for v in (h.get('rates') or {}).values() if v is not None)
    p30 = sum(1 for h in kr30 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(kr30) != EXPECT_KR30['hotels'] or c30 != EXPECT_KR30['cash'] or p30 != EXPECT_KR30['points']:
        problems.append('한국 신규 30곳 수치 %s (기대 %s)' % (
            {'hotels': len(kr30), 'cash': c30, 'points': p30}, EXPECT_KR30))
    # 2026-11-23 — 싱가포르 8곳(m41~m48)도 칸 수를 고정해 둔다(유실·보간 방지)
    sg8 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in SG8_IDS]
    sgc = sum(1 for h in sg8 for v in (h.get('rates') or {}).values() if v is not None)
    sgp = sum(1 for h in sg8 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(sg8) != EXPECT_SG8['hotels'] or sgc != EXPECT_SG8['cash'] or sgp != EXPECT_SG8['points']:
        problems.append('싱가포르 8곳 수치 %s (기대 %s)' % (
            {'hotels': len(sg8), 'cash': sgc, 'points': sgp}, EXPECT_SG8))
    # 2026-11-23 — 싱가포르 중반 7곳(m49~m55)도 칸 수를 고정해 둔다(유실·보간 방지)
    sg7 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in SG7_IDS]
    sg7c = sum(1 for h in sg7 for v in (h.get('rates') or {}).values() if v is not None)
    sg7p = sum(1 for h in sg7 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(sg7) != EXPECT_SG7['hotels'] or sg7c != EXPECT_SG7['cash'] or sg7p != EXPECT_SG7['points']:
        problems.append('싱가포르 중반 7곳 수치 %s (기대 %s)' % (
            {'hotels': len(sg7), 'cash': sg7c, 'points': sg7p}, EXPECT_SG7))
    # 2026-11-23 — 싱가포르 마지막 7곳(m56~m62)도 칸 수를 고정해 둔다(유실·보간 방지)
    sg7l = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in SG7L_IDS]
    sg7lc = sum(1 for h in sg7l for v in (h.get('rates') or {}).values() if v is not None)
    sg7lp = sum(1 for h in sg7l for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(sg7l) != EXPECT_SG7L['hotels'] or sg7lc != EXPECT_SG7L['cash'] \
            or sg7lp != EXPECT_SG7L['points']:
        problems.append('싱가포르 마지막 7곳 수치 %s (기대 %s)' % (
            {'hotels': len(sg7l), 'cash': sg7lc, 'points': sg7lp}, EXPECT_SG7L))
    # 2026-11-23 — 오세아니아 1차 23곳(m63~m85)도 칸 수를 고정해 둔다(유실·보간 방지)
    oc = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in OC23_IDS]
    occ = sum(1 for h in oc for v in (h.get('rates') or {}).values() if isinstance(v, (int, float)))
    ocp = sum(1 for h in oc for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(oc) != EXPECT_OC23['hotels'] or occ != EXPECT_OC23['cash'] \
            or ocp != EXPECT_OC23['points']:
        problems.append('오세아니아 23곳 수치 %s (기대 %s)' % (
            {'hotels': len(oc), 'cash': occ, 'points': ocp}, EXPECT_OC23))
    # 2026-11-23 — 일본 1차 30곳(m86~m115)도 칸 수를 고정해 둔다(유실·보간 방지)
    jp30 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in JP30_IDS]
    jp30c = sum(1 for h in jp30 for v in (h.get('rates') or {}).values()
                if isinstance(v, (int, float)))
    jp30p = sum(1 for h in jp30 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(jp30) != EXPECT_JP30['hotels'] or jp30c != EXPECT_JP30['cash'] \
            or jp30p != EXPECT_JP30['points']:
        problems.append('일본 30곳 수치 %s (기대 %s)' % (
            {'hotels': len(jp30), 'cash': jp30c, 'points': jp30p}, EXPECT_JP30))
    # 2026-11-23 — 일본 2차 30곳(m168~m197)도 칸 수를 고정해 둔다(유실·보간 방지)
    jp30b = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in JP30B_IDS]
    jp30bc = sum(1 for h in jp30b for v in (h.get('rates') or {}).values()
                 if isinstance(v, (int, float)))
    jp30bp = sum(1 for h in jp30b for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(jp30b) != EXPECT_JP30B['hotels'] or jp30bc != EXPECT_JP30B['cash'] \
            or jp30bp != EXPECT_JP30B['points']:
        problems.append('일본 2차 30곳 수치 %s (기대 %s)' % (
            {'hotels': len(jp30b), 'cash': jp30bc, 'points': jp30bp}, EXPECT_JP30B))
    # 2026-11-23 — 오세아니아 2차 14곳(m198~m211)도 칸 수를 고정해 둔다(유실·보간 방지)
    oc2 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in OC2_IDS]
    oc2c = sum(1 for h in oc2 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    oc2p = sum(1 for h in oc2 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(oc2) != EXPECT_OC2['hotels'] or oc2c != EXPECT_OC2['cash'] \
            or oc2p != EXPECT_OC2['points']:
        problems.append('오세아니아 2차 14곳 수치 %s (기대 %s)' % (
            {'hotels': len(oc2), 'cash': oc2c, 'points': oc2p}, EXPECT_OC2))
    # 2026-11-23 — 일본 3차 30곳(m212~m241)도 칸 수를 고정해 둔다(유실·보간 방지)
    jp34 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in JP34_IDS]
    jp34c = sum(1 for h in jp34 for v in (h.get('rates') or {}).values()
                if isinstance(v, (int, float)))
    jp34p = sum(1 for h in jp34 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(jp34) != EXPECT_JP34['hotels'] or jp34c != EXPECT_JP34['cash'] \
            or jp34p != EXPECT_JP34['points']:
        problems.append('일본 3차 30곳 수치 %s (기대 %s)' % (
            {'hotels': len(jp34), 'cash': jp34c, 'points': jp34p}, EXPECT_JP34))
    # 2026-11-23 — 일본 4차 29곳(m242~m270)도 칸 수를 고정해 둔다(유실·보간 방지)
    jp34b = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in JP34B_IDS]
    jp34bc = sum(1 for h in jp34b for v in (h.get('rates') or {}).values()
                 if isinstance(v, (int, float)))
    jp34bp = sum(1 for h in jp34b for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(jp34b) != EXPECT_JP34B['hotels'] or jp34bc != EXPECT_JP34B['cash'] \
            or jp34bp != EXPECT_JP34B['points']:
        problems.append('일본 4차 29곳 수치 %s (기대 %s)' % (
            {'hotels': len(jp34b), 'cash': jp34bc, 'points': jp34bp}, EXPECT_JP34B))
    # 2026-11-24 — 오세아니아 2차 잔여 10곳(m271~m280)도 칸 수를 고정해 둔다(유실·보간 방지)
    oc10 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in OC10_IDS]
    oc10c = sum(1 for h in oc10 for v in (h.get('rates') or {}).values()
                if isinstance(v, (int, float)))
    oc10p = sum(1 for h in oc10 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(oc10) != EXPECT_OC10['hotels'] or oc10c != EXPECT_OC10['cash'] \
            or oc10p != EXPECT_OC10['points']:
        problems.append('오세아니아 2차 잔여 10곳 수치 %s (기대 %s)' % (
            {'hotels': len(oc10), 'cash': oc10c, 'points': oc10p}, EXPECT_OC10))
    # 2026-11-24 — 대만 1차 4곳(m281~m284)도 칸 수를 고정해 둔다(유실·보간 방지)
    tw4 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in TW4_IDS]
    tw4c = sum(1 for h in tw4 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    tw4p = sum(1 for h in tw4 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(tw4) != EXPECT_TW4['hotels'] or tw4c != EXPECT_TW4['cash'] \
            or tw4p != EXPECT_TW4['points']:
        problems.append('대만 1차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(tw4), 'cash': tw4c, 'points': tw4p}, EXPECT_TW4))
    # 2026-11-24 — 대만 2차 4곳(m285~m288)도 칸 수를 고정해 둔다(유실·보간 방지)
    tw2 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in TW8_IDS]
    tw2c = sum(1 for h in tw2 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    tw2p = sum(1 for h in tw2 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(tw2) != EXPECT_TW8['hotels'] or tw2c != EXPECT_TW8['cash'] \
            or tw2p != EXPECT_TW8['points']:
        problems.append('대만 8곳 수치 %s (기대 %s)' % (
            {'hotels': len(tw2), 'cash': tw2c, 'points': tw2p}, EXPECT_TW8))
    # 2026-11-24 — 대만 3차 3곳(m289~m291)도 칸 수를 고정해 둔다(유실·보간 방지)
    tw3 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in TW11_IDS]
    tw3c = sum(1 for h in tw3 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    tw3p = sum(1 for h in tw3 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(tw3) != EXPECT_TW11['hotels'] or tw3c != EXPECT_TW11['cash'] \
            or tw3p != EXPECT_TW11['points']:
        problems.append('대만 3차 3곳 수치 %s (기대 %s)' % (
            {'hotels': len(tw3), 'cash': tw3c, 'points': tw3p}, EXPECT_TW11))
    # 2026-11-24 — 대만 4차 4곳(m292~m295)도 칸 수를 고정해 둔다(유실·보간 방지)
    tw4c4 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in TW15_IDS]
    twc4 = sum(1 for h in tw4c4 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    twp4 = sum(1 for h in tw4c4 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(tw4c4) != EXPECT_TW15['hotels'] or twc4 != EXPECT_TW15['cash'] \
            or twp4 != EXPECT_TW15['points']:
        problems.append('대만 4차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(tw4c4), 'cash': twc4, 'points': twp4}, EXPECT_TW15))
    # 2026-11-24 — 대만 5차 4곳(m296~m299)도 칸 수를 고정해 둔다(유실·보간 방지)
    tw5 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in TW19_IDS]
    tw5c = sum(1 for h in tw5 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    tw5p = sum(1 for h in tw5 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(tw5) != EXPECT_TW19['hotels'] or tw5c != EXPECT_TW19['cash'] \
            or tw5p != EXPECT_TW19['points']:
        problems.append('대만 5차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(tw5), 'cash': tw5c, 'points': tw5p}, EXPECT_TW19))
    # 2026-11-24 — 대만 6차 4곳(m300~m303)도 칸 수를 고정해 둔다(유실·보간 방지)
    tw6 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in TW23_IDS]
    tw6c = sum(1 for h in tw6 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    tw6p = sum(1 for h in tw6 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(tw6) != EXPECT_TW23['hotels'] or tw6c != EXPECT_TW23['cash'] \
            or tw6p != EXPECT_TW23['points']:
        problems.append('대만 6차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(tw6), 'cash': tw6c, 'points': tw6p}, EXPECT_TW23))
    # 2026-11-24 — 대만 7차 4곳(m304~m307)도 칸 수를 고정해 둔다(유실·보간 방지)
    tw7 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in TW27_IDS]
    tw7c = sum(1 for h in tw7 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    tw7p = sum(1 for h in tw7 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(tw7) != EXPECT_TW27['hotels'] or tw7c != EXPECT_TW27['cash'] \
            or tw7p != EXPECT_TW27['points']:
        problems.append('대만 7차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(tw7), 'cash': tw7c, 'points': tw7p}, EXPECT_TW27))
    # 2026-11-24 — 대만 8차 1곳(m308)도 칸 수를 고정해 둔다(유실·보간 방지)
    tw8 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in TW28_IDS]
    tw8c = sum(1 for h in tw8 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    tw8p = sum(1 for h in tw8 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(tw8) != EXPECT_TW28['hotels'] or tw8c != EXPECT_TW28['cash'] \
            or tw8p != EXPECT_TW28['points']:
        problems.append('대만 8차 1곳 수치 %s (기대 %s)' % (
            {'hotels': len(tw8), 'cash': tw8c, 'points': tw8p}, EXPECT_TW28))
    # 2026-11-25 — 베트남 1차 4곳(m309~m312)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn1 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN1_IDS]
    vn1c = sum(1 for h in vn1 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn1p = sum(1 for h in vn1 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn1) != EXPECT_VN1['hotels'] or vn1c != EXPECT_VN1['cash'] \
            or vn1p != EXPECT_VN1['points']:
        problems.append('베트남 1차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn1), 'cash': vn1c, 'points': vn1p}, EXPECT_VN1))
    # 2026-11-25 — 베트남 2차 4곳(m313~m316)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn2 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN2_IDS]
    vn2c = sum(1 for h in vn2 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn2p = sum(1 for h in vn2 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn2) != EXPECT_VN2['hotels'] or vn2c != EXPECT_VN2['cash'] \
            or vn2p != EXPECT_VN2['points']:
        problems.append('베트남 2차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn2), 'cash': vn2c, 'points': vn2p}, EXPECT_VN2))
    # 2026-11-25 — 베트남 3차 4곳(m317~m320)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn3 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN3_IDS]
    vn3c = sum(1 for h in vn3 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn3p = sum(1 for h in vn3 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn3) != EXPECT_VN3['hotels'] or vn3c != EXPECT_VN3['cash'] \
            or vn3p != EXPECT_VN3['points']:
        problems.append('베트남 3차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn3), 'cash': vn3c, 'points': vn3p}, EXPECT_VN3))
    # 2026-11-25 — 베트남 4차 4곳(m321~m324)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn4 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN4_IDS]
    vn4c = sum(1 for h in vn4 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn4p = sum(1 for h in vn4 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn4) != EXPECT_VN4['hotels'] or vn4c != EXPECT_VN4['cash'] \
            or vn4p != EXPECT_VN4['points']:
        problems.append('베트남 4차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn4), 'cash': vn4c, 'points': vn4p}, EXPECT_VN4))
    # 2026-11-25 — 베트남 5차 4곳(m325~m328)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn5 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN5_IDS]
    vn5c = sum(1 for h in vn5 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn5p = sum(1 for h in vn5 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn5) != EXPECT_VN5['hotels'] or vn5c != EXPECT_VN5['cash'] \
            or vn5p != EXPECT_VN5['points']:
        problems.append('베트남 5차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn5), 'cash': vn5c, 'points': vn5p}, EXPECT_VN5))
    # 2026-11-25 — 베트남 6차 4곳(m329~m332)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn6 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN6_IDS]
    vn6c = sum(1 for h in vn6 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn6p = sum(1 for h in vn6 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn6) != EXPECT_VN6['hotels'] or vn6c != EXPECT_VN6['cash'] \
            or vn6p != EXPECT_VN6['points']:
        problems.append('베트남 6차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn6), 'cash': vn6c, 'points': vn6p}, EXPECT_VN6))
    # 2026-11-26 — 베트남 7차 4곳(m333~m336)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn7 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN7_IDS]
    vn7c = sum(1 for h in vn7 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn7p = sum(1 for h in vn7 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn7) != EXPECT_VN7['hotels'] or vn7c != EXPECT_VN7['cash'] \
            or vn7p != EXPECT_VN7['points']:
        problems.append('베트남 7차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn7), 'cash': vn7c, 'points': vn7p}, EXPECT_VN7))
    # 2026-11-26 — 베트남 8차 4곳(m337~m340)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn8 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN8_IDS]
    vn8c = sum(1 for h in vn8 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn8p = sum(1 for h in vn8 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn8) != EXPECT_VN8['hotels'] or vn8c != EXPECT_VN8['cash'] \
            or vn8p != EXPECT_VN8['points']:
        problems.append('베트남 8차 4곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn8), 'cash': vn8c, 'points': vn8p}, EXPECT_VN8))
    # 2026-11-26 — 베트남 9차(마지막) 3곳(m341~m343)도 칸 수를 고정해 둔다(유실·보간 방지)
    vn9 = [h for h in db['hotels'] if h.get('group') == 'marriott' and h['id'] in VN9_IDS]
    vn9c = sum(1 for h in vn9 for v in (h.get('rates') or {}).values()
               if isinstance(v, (int, float)))
    vn9p = sum(1 for h in vn9 for v in (h.get('points') or {}).values() if isinstance(v, int))
    if len(vn9) != EXPECT_VN9['hotels'] or vn9c != EXPECT_VN9['cash'] \
            or vn9p != EXPECT_VN9['points']:
        problems.append('베트남 9차 3곳 수치 %s (기대 %s)' % (
            {'hotels': len(vn9), 'cash': vn9c, 'points': vn9p}, EXPECT_VN9))
    for h in kj + kr30 + sg8 + sg7 + sg7l + oc + jp30 + jp30b + oc2 + jp34 + jp34b + oc10 + tw4 + tw2 \
            + tw3 + tw4c4 + tw5 + tw6 + tw7 + tw8 + vn1 + vn2 + vn3 + vn4 + vn5 + vn6 + vn7 + vn8 + vn9:
        if h['id'] == 'k09' or h.get('code') in NO_POINT_CODES:
            continue
        if not h.get('points'):
            problems.append('%s 포인트 칸 없음' % h['id'])
        if h['id'] in EXPECT_OVERLAP and not h.get('alsoIn'):
            problems.append('%s 는 ① 탭과 겹치므로 alsoIn 필요' % h['id'])
    # 같은 호텔이 두 탭에 조용히 중복되지 않았는지(교차 참조 없는 이름 중복 금지)
    seen = {}
    for h in db['hotels']:
        key = (h.get('english') or h['name']).strip().lower()
        prev = seen.get(key)
        if prev and prev != h['id'] and not (h.get('alsoIn') or
                                             ('%s' % prev, h['id']) in KNOWN_DUP or
                                             (h['id'], prev) in KNOWN_DUP):
            problems.append('호텔 중복: %s ↔ %s (%s)' % (prev, h['id'], key))
        seen.setdefault(key, h['id'])
    # 예약 링크를 프로그램 페이지(h.fhr)로 보내는 호텔은 그 주소가 공식 프로그램 페이지인지 확인
    for h in db['hotels']:
        u = h.get('fhr')
        if u and not u.startswith('https://www.americanexpress.com/'):
            problems.append('%s fhr 주소가 아멕스 공식 페이지가 아님: %s' % (h['id'], u))
    problems.extend(check_apc(db))
    problems.extend(check_accor(db))
    return problems


def check_hyatt():
    """④ 하얏트 정본(tab10_hyatt.json) — 곳수·칸수·id/code 중복만 본다(내용 검사는 이 파일 범위 밖)."""
    path = os.path.join(APP_DIR, 'tab10_hyatt.json')
    if not os.path.exists(path):
        return ['④ tab10_hyatt.json 가 없습니다']
    try:
        tab = json.loads(_read(path))
    except Exception as exc:                      # noqa: BLE001
        return ['④ tab10_hyatt.json 를 읽지 못했습니다: %r' % (exc,)]
    hs = tab.get('hotels') or []
    problems = []
    if len(hs) != EXPECT_HYATT['hotels']:
        problems.append('④ 하얏트 %d곳 (기대 %d곳)' % (len(hs), EXPECT_HYATT['hotels']))
    cells = sum(len((h.get('points') or {}).get('$v') or []) for h in hs)
    priced = sum(1 for h in hs for v in ((h.get('points') or {}).get('$v') or []) if v is not None)
    if cells != EXPECT_HYATT['cells'] or priced != EXPECT_HYATT['priced']:
        problems.append('④ 하얏트 칸 %d · 값 %d (기대 %d · %d)' % (
            cells, priced, EXPECT_HYATT['cells'], EXPECT_HYATT['priced']))
    if len({h.get('id') for h in hs}) != len(hs):
        problems.append('④ 하얏트 id 중복')
    if len({h.get('code') for h in hs}) != len(hs):
        problems.append('④ 하얏트 code 중복')
    return problems


def check_ihg():
    """⑤ IHG 정본(tab11_ihg.json) — 곳수·칸수·값 있는 칸·id/code 중복만 본다(내용 검사는 이 파일 범위 밖)."""
    path = os.path.join(APP_DIR, 'tab11_ihg.json')
    if not os.path.exists(path):
        return ['⑤ tab11_ihg.json 가 없습니다']
    try:
        tab = json.loads(_read(path))
    except Exception as exc:                      # noqa: BLE001
        return ['⑤ tab11_ihg.json 를 읽지 못했습니다: %r' % (exc,)]
    hs = tab.get('hotels') or []
    problems = []
    if len(hs) != EXPECT_IHG['hotels']:
        problems.append('⑤ IHG %d곳 (기대 %d곳)' % (len(hs), EXPECT_IHG['hotels']))
    cells = sum(len((h.get('rates') or {}).get('$v') or []) for h in hs)
    cash = sum(1 for h in hs for v in ((h.get('rates') or {}).get('$v') or []) if v is not None)
    pts = sum(1 for h in hs for v in ((h.get('points') or {}).get('$v') or []) if v is not None)
    if cells != EXPECT_IHG['cells']:
        problems.append('⑤ IHG 칸 %d (기대 %d)' % (cells, EXPECT_IHG['cells']))
    if cash != EXPECT_IHG['cash'] or pts != EXPECT_IHG['points']:
        problems.append('⑤ IHG 값 있는 칸 현금 %d · 포인트 %d (기대 %d · %d)'
                        % (cash, pts, EXPECT_IHG['cash'], EXPECT_IHG['points']))
    cnt = tab.get('counts') or {}
    if (cnt.get('hotels'), cnt.get('cells'), cnt.get('cash'), cnt.get('points')) != \
            (len(hs), cells, cash, pts):
        problems.append('⑤ IHG counts 블록이 실제와 다름: %r' % (cnt,))
    if len({h.get('id') for h in hs}) != len(hs):
        problems.append('⑤ IHG id 중복')
    if len({h.get('code') for h in hs}) != len(hs):
        problems.append('⑤ IHG code 중복')
    for h in hs:
        for kind in ('rates', 'points'):
            if len((h.get(kind) or {}).get('$v') or []) != 365:
                problems.append('⑤ IHG %s %s 칸이 365가 아님' % (h.get('id'), kind))
                break
    return problems


def cmd_verify(args, quiet=False):
    master = json.loads(_read(MASTER))
    src, dbmeta, _ = read_db_literal()
    parts, hotels, flights, tt = read_parts()
    problems = []

    mdb, mfl, mtt = project(master)

    # 1) index.html 의 `const DB` — 호텔을 뺀 집계·출처 블록이 master 와 같은지
    meta = project_meta(master)
    if meta != dbmeta:
        if list(meta.keys()) != list(dbmeta.keys()):
            problems.append('DB key 구성 다름: %s vs %s' % (list(meta.keys()), list(dbmeta.keys())))
        for k in meta:
            if meta[k] != dbmeta.get(k):
                problems.append('DB.%s 다름' % k)
    if dbmeta.get('hotels'):
        problems.append('index.html 에 호텔 %d곳이 아직 인라인으로 남아 있습니다' % len(dbmeta['hotels']))

    # 2) 탭별 호텔 JSON — 건수·id 순서(탭 안 순서)·항목 내용이 master 와 같은지
    by_group = split_hotels(master['hotels'])
    for tab in PART_ORDER:
        name = PART_ADDRESS[tab]
        got = parts[tab]['hotels']
        want = by_group[tab]
        if len(got) != len(want):
            problems.append('%s 호텔 %d곳 (master %d곳)' % (name, len(got), len(want)))
        gid = [h.get('id') for h in got]
        wid = [h.get('id') for h in want]
        if gid != wid:
            missing = [i for i in wid if i not in set(gid)]
            extra = [i for i in gid if i not in set(wid)]
            problems.append('%s 호텔 id 순서/구성 다름 (빠짐 %s · 더있음 %s)' % (name, missing[:5], extra[:5]))
        for a, b in zip(got, want):
            if a != b:
                problems.append('%s 호텔 %s 내용 다름' % (name, a.get('id')))
                break
    if parts['accor'].get('accor') != master.get('accor'):
        problems.append('tab2_accor.json 의 accor(SNU) 블록이 master 와 다름')
    if flights != mfl:
        problems.append('%s 내용 다름' % PART_FLIGHTS)
    if tt != mtt:
        problems.append('%s(⑥ 땡처리) 내용 다름' % PART_TTANG)

    # 3) 탭별 JSON 을 합친 실제 배포 데이터로 통계
    st = stats_of({'hotels': hotels, 'accor': parts['accor'].get('accor')}, flights, tt)
    expect = master.get('counts') or {}
    for k in ('hotels', 'tabs', 'cells', 'priced', 'na', 'stayplus', 'routes', 'deals', 'snu',
              'pus_deals', 'pus_routes', 'redhot_hotels', 'redhot_cells'):
        if k in expect and expect[k] != st[k]:
            problems.append('counts.%s 불일치: master=%s index=%s' % (k, expect[k], st[k]))
    if st['date_min'] != WINDOW_START or st['date_max'] != WINDOW_END or st['dates'] != 365:
        problems.append('날짜 창 이상: %s ~ %s (%d일)' % (st['date_min'], st['date_max'], st['dates']))
    # 날짜 칸 — ① 은 실측분만 싣으므로 호텔마다 칸 수가 다르다(2026-11-20 검색 요금 제거).
    # ①은 0~365칸(창 안의 날짜만), ②~④는 365칸을 그대로 요구한다.
    by_id = {h.get('id'): h for h in hotels}
    for hid, n in st['cells_per_hotel'].items():
        grp = (by_id.get(hid) or {}).get('group')
        if n > 365:
            problems.append('%s 날짜 칸 %d개 (창 365일 초과)' % (hid, n))
        elif grp != 'lux' and n != 365 and not ((by_id.get(hid) or {}).get('redhot') and n == 0):
            problems.append('%s 날짜 칸 %d개 (365 이어야 함)' % (hid, n))
        for d in ((by_id.get(hid) or {}).get('rates') or {}):
            if not (WINDOW_START <= d <= WINDOW_END):
                problems.append('%s 날짜 %s 가 창(%s~%s) 밖' % (hid, d, WINDOW_START, WINDOW_END))
                break

    # 탭 구성 검사 (①~④ 기존 데이터가 손상되지 않았는지 포함)
    problems.extend(check_tabs(mdb))
    problems.extend(check_sources(src))
    problems.extend(check_sources(_read(MASTER)))
    for _tab, _name in PART_TABS:
        problems.extend(check_sources(_read(part_path(_name))))
    problems.extend(check_sources(_read(part_path(PART_FLIGHTS))))
    problems.extend(check_sources(_read(part_path(PART_TTANG))))
    problems.extend(check_hyatt())
    problems.extend(check_ihg())
    problems.extend(check_flights(flights))
    problems.extend(check_ttang(tt))
    if os.path.exists(os.path.join(APP_DIR, PART_MILEAGE)):
        try:
            problems.extend(check_mileage(json.loads(_read(os.path.join(APP_DIR, PART_MILEAGE)))))
        except Exception as exc:                  # noqa: BLE001
            problems.append('⑦ %s 를 읽지 못했습니다: %r' % (PART_MILEAGE, exc))
    else:
        problems.append('⑦ %s 가 없습니다' % PART_MILEAGE)
    check_history(problems)
    # ⑥ 탭·탭별 JSON 골격이 빠지지 않았는지(마크업·탭 버튼·데이터 블록)
    for needle in ('id="ttPanel"', 'data-tab="tt"', 'const TTANG', 'const FLIGHTS',
                   'DATA_ROOT', 'tab6_ttang.json', 'id="alertBar"', 'data/history/',
                   'function histOpen', 'id="chartModal"', 'cbNextDay'):
        if needle not in src:
            problems.append('⑥ 땡처리 탭·지연 로딩 골격 누락: %s' % needle)

    if problems:
        print('VERIFY FAIL')
        for p in problems:
            print('  - ' + p)
        return 1
    if not quiet:
        print('VERIFY OK — master_db.json == data/app/*.json + index.html 집계값')
        print('  hotels %(hotels)d  tabs %(tabs)s' % st)
        print('  cells %(cells)d  priced %(priced)d  na %(na)d  stayplus %(stayplus)d' % st)
        print('  routes {routes}  deals {deals}  window {date_min}~{date_max}'.format(**st))
        print('  ⑥ 땡처리 {pus_deals}건 · {pus_routes}개 노선'.format(**st))
        try:
            mgv = json.loads(_read(os.path.join(APP_DIR, PART_MILEAGE)))
            mc = mgv.get('counts') or {}
            print('  ⑦ 마일리지 %d개 노선 · 수집칸 %d · 좌석 있는 칸 %d · 미수집 %d'
                  % (mc.get('routes', 0), mc.get('cells', 0), mc.get('open', 0), mc.get('miss', 0)))
        except Exception:                          # noqa: BLE001
            pass
        print('  flights 당일치기 %d건 · 패턴 %d종' % (flights['counts'].get('daytrip', 0),
                                                   len(flights['patterns'])))
        print('  index.html const DB 호텔 %d곳 (비어 있어야 함)' % len(dbmeta.get('hotels') or []))
        if os.path.exists(HIST_ALERTS):
            al = json.loads(_read(HIST_ALERTS))
            print('  이력 스냅샷 %s · 에러가 의심 %s건 (data/history/)'
                  % (al.get('generated'), (al.get('counts') or {}).get('total')))
    return 0


# ---------------------------------------------------------------- inject

def _part_files():
    return [PART_ADDRESS[tab] for tab in PART_ORDER] + [PART_FLIGHTS, PART_TTANG]


def cmd_inject(args):
    if cmd_verify(args, quiet=True) != 0:
        print('배포 파일(data/app/*.json + index.html 집계값)이 이미 master_db.json 과 다릅니다')
        print('— verify 로 차이를 먼저 확인하세요.')
        print('(다른 데이터를 넣으려면 수정한 뒤 inject 하는 것이 맞습니다. 계속 진행합니다.)')
    master = json.loads(_read(MASTER))
    meta = project_meta(master)
    src, dbmeta, span_db = read_db_literal()

    if compact(meta) == compact(dbmeta):
        try:
            same = all(_read(part_path(n)) == _part_text(master, n) for n in _part_files())
        except OSError:
            same = False
        if same:
            print('배포 파일이 이미 master_db.json 과 같습니다 — 배포본은 그대로 두고 이력만 쌓습니다.')
            snapshot_run(master, args)
            return 0

    backup = tempfile.mkdtemp(prefix='hca-inject-')
    saved = [('index.html', INDEX)] + [(n, part_path(n)) for n in _part_files()]
    for name, path in saved:
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(backup, name))

    new = src[:span_db[0]] + compact(meta) + src[span_db[1]:]
    with open(INDEX, 'w', encoding='utf-8') as fp:
        fp.write(new)
    write_parts(master)

    if cmd_verify(args, quiet=True) != 0:
        for name, path in saved:
            srcp = os.path.join(backup, name)
            if os.path.exists(srcp):
                shutil.copy2(srcp, path)
        print('검증 실패 — index.html 과 data/app 을 백업으로 되돌렸습니다.')
        return 1
    shutil.rmtree(backup, ignore_errors=True)
    snapshot_run(master, args)
    counts = master.get('counts') or {}
    print('data/app 갱신 + index.html 집계값 갱신 완료 (호텔 %s곳, 항공 %s노선, ⑥ 땡처리 %s건, SNU %s줄)' % (
        counts.get('hotels'), counts.get('routes'), counts.get('pus_deals'), counts.get('snu')))
    _print_part_sizes(master)
    return 0


def _part_text(master, name):
    """write_parts 가 쓸 내용(비교용) — 파일을 건드리지 않는다."""
    groups = split_hotels(master['hotels'])
    for tab, fname in PART_TABS:
        if fname == name:
            part = {'tab': tab, 'count': len(groups[tab]), 'hotels': groups[tab]}
            if tab == 'accor':
                part['accor'] = master.get('accor')
            return compact(encode_part(part)) + '\n'
    if name == PART_FLIGHTS:
        return compact(encode_part(master['flights'])) + '\n'
    return compact(encode_part(master.get('ttang') or {'deals': []})) + '\n'


def cmd_parts(args):
    """master_db.json -> data/app/*.json 만 다시 쓴다(index.html 은 그대로)."""
    master = json.loads(_read(MASTER))
    groups = write_parts(master)
    print('wrote data/app/ — ' + ', '.join('%s %d곳' % (PART_ADDRESS[t], len(groups[t]))
                                          for t in PART_ORDER))
    print('  %s · %s' % (PART_FLIGHTS, PART_TTANG))
    _print_part_sizes()
    return 0


def _plain_parts(master):
    """압축 전(원래 구조) 기준 크기 — 절감 수치 보고용."""
    groups = split_hotels(master['hotels'])
    out = []
    for tab in PART_ORDER:
        part = {'tab': tab, 'count': len(groups[tab]), 'hotels': groups[tab]}
        if tab == 'accor':
            part['accor'] = master.get('accor')
        out.append((PART_ADDRESS[tab], part))
    out.append((PART_FLIGHTS, master['flights']))
    out.append((PART_TTANG, master.get('ttang') or {'deals': []}))
    return out


def _print_part_sizes(master=None):
    if master is None:
        master = json.loads(_read(MASTER))
    plain = dict(_plain_parts(master))
    p_sum = e_sum = 0
    for name in _part_files():
        p = plain_size(plain[name])
        e = os.path.getsize(part_path(name))
        p_sum += p
        e_sum += e
        print('  %-20s %8.1f KB -> %7.1f KB  (%4.1f%%↓)' % (name, p / 1024.0, e / 1024.0,
                                                         100.0 * (1 - e / float(p)) if p else 0))
    print('  %-20s %8.1f KB -> %7.1f KB  (%4.1f%%↓)' % ('합계', p_sum / 1024.0, e_sum / 1024.0,
                                                     100.0 * (1 - e_sum / float(p_sum)) if p_sum else 0))


# ---------------------------------------------------------------- stats

def cmd_refresh(args):
    """호텔·항공을 병합한 뒤 master_db.json 의 counts 만 다시 센다(데이터는 건드리지 않음)."""
    master = json.loads(_read(MASTER))
    st = stats_of(master, master['flights'], master.get('ttang'))
    master['counts'] = {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na',
                                           'stayplus', 'routes', 'deals', 'snu',
                                           'pus_deals', 'pus_routes')}
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('counts refreshed: %s' % json.dumps(master['counts'], ensure_ascii=False))
    return 0


def cmd_stats(args):
    parts, hotels, flights, tt = read_parts()
    st = stats_of({'hotels': hotels, 'accor': parts['accor'].get('accor')}, flights, tt)
    print('data/app 기준 (탭별 지연 로딩 배포본)')
    print('  hotels  %d  %s' % (st['hotels'], st['tabs']))
    print('  cells   %d  (priced %d / NA %d)' % (st['cells'], st['priced'], st['na']))
    print('  stayplus %d건 · SNU 후보 %d줄' % (st['stayplus'], st['snu']))
    print('  flights %d노선 %d건' % (st['routes'], st['deals']))
    print('  ⑥ 땡처리 %d건 · %d개 노선' % (st['pus_deals'], st['pus_routes']))
    print('  window  %s ~ %s (%d일)' % (st['date_min'], st['date_max'], st['dates']))
    print()
    print('파일 크기 (KB) — 압축 전(원래 구조) -> 배포 파일')
    print('  %-18s %8.1f' % ('index.html', os.path.getsize(INDEX) / 1024.0))
    plain = dict(_plain_parts(json.loads(_read(MASTER))))
    for name in _part_files():
        print('  %-18s %8.1f -> %7.1f' % (name, plain_size(plain[name]) / 1024.0,
                                          os.path.getsize(part_path(name)) / 1024.0))
    print()
    print('호텔별 요금 표기 칸수')
    for h in hotels:
        print('  %-7s %-34s %3d/365' % (h['id'], h['name'], st['priced_per_hotel'][h['id']]))
    return 0


# ---------------------------------------------------------------- 이력 저장 · 에러가 알람
# `inject`(또는 단독 `snapshot`)가 돌 때마다 오늘(KST) 스냅샷을 data/history/ 에 누적한다.
#   · history/hotels/{hotel_id}.json    체크인 날짜별  [스냅샷일, 현금가, 포인트, 상태]
#   · history/flights/{route_code}.json 출발일|패턴별  [스냅샷일, 출발일, 패턴, 가격, 직항(1/0), 상태]
#   · history/ttang/{airport_code}.json 출발_귀국_코드_항공사_시각별 [스냅샷일, 가격, 잔여석]
#   · history/alerts.json               에러가 의심 후보
# 직전 스냅샷과 값이 같은 칸은 다시 쓰지 않는다(바뀐 날·최초 기록만 남긴다).
# 상태 코드: O 판매·요금 있음 · N 요금 미표시 · E 이상 고가(1천만 원↑) ·
#            D 판매편 없음 · U 예약창 미오픈 · X 이번 스냅샷에서 사라짐
HIST_DIR = os.path.join(ROOT, 'data', 'history')
HIST_HOTELS = os.path.join(HIST_DIR, 'hotels')
HIST_FLIGHTS = os.path.join(HIST_DIR, 'flights')
HIST_TTANG = os.path.join(HIST_DIR, 'ttang')
HIST_ALERTS = os.path.join(HIST_DIR, 'alerts.json')
SCHEMA_HOTEL_HIST = 'hotel-calendar-app/history/hotel/1'
SCHEMA_FLIGHT_HIST = 'hotel-calendar-app/history/flight/1'
SCHEMA_TTANG_HIST = 'hotel-calendar-app/history/ttang/1'
SCHEMA_ALERTS = 'hotel-calendar-app/history/alerts/1'
HIST_STATUS = ('O', 'N', 'E', 'D', 'U', 'X')
ERROR_MIN = 10000000          # 1박 1천만 원 이상 — 시스템 폭등 오류로 본다(차트 Y축 제외)
ALERT_DROP = 0.5              # 유효 중앙값 대비 50% 이상 급락
ALERT_HOTEL_LOW = 50000       # 절대 초저가 — 호텔 1박
ALERT_FLIGHT_LOW = 70000      # 절대 초저가 — 왕복 항공
ALERT_TIER_REPEAT = 3         # 같은 값이 3일 이상 반복되면 정상 요금표로 보고 뺀다
ALERT_MIN_HOTEL = 30          # 중앙값을 낼 최소 표본(호텔)
ALERT_MIN_FLIGHT = 8          # 중앙값을 낼 최소 표본(노선·패턴·직항 여부)
ALERT_MIN_TTANG = 5           # 중앙값을 낼 최소 표본(⑥ 공항·항공사·시각)
ALERT_CAP = 160               # alerts.json 에 담는 최대 건수(넘으면 급락 폭 큰 순서로 자른다)
ALERT_WHY = ('직전 대비 50%↓', '기준 대비 50%↓', '초저가')
# ── 2026-11-20 오탐 차단(에러가) ─────────────────────────────────────────────
# 실제 요금이 50% 떨어져 보여도 (a) 출처·산식이 바뀐 날 (b) 앞뒤 날짜와 비교하면
# 정상인 계절 차이 (c) 요금이 없다가 열린 예약창 은 에러가 아니다. 아래 값으로 그 셋을 가른다.
ALERT_LOCAL_SPAN_H = 35        # 호텔 — 같은 호텔의 앞뒤 35일(같은 요일 5주) 값을 기준으로 비교
ALERT_LOCAL_SPAN_F = 42        # 항공 — 같은 노선·패턴·직항 여부의 앞뒤 42일
ALERT_LOCAL_MIN_H = 4          # 호텔 — 가까운 날짜 표본이 이만큼은 있어야 그 기준을 쓴다
ALERT_LOCAL_MIN_F = 3          # 항공
ALERT_LOCAL_K = 8              # 가까운 날짜 몇 개까지 볼지
ALERT_STABLE_RATIO = 1.5       # 한 해 값의 p75/p25 가 이보다 좁을 때만 1년 중앙값을 보조 기준으로
ALERT_LEVEL_RUN = 5            # 같은 스냅샷에 연속 N일이 함께 크게 움직이면 출처·산식 전환으로 본다
ALERT_LEVEL_RATIO = 0.30       # 그 '크게'의 폭(중앙값 기준 ±30%)
ALERT_PREV_SPIKE = 3.0         # 직전 값이 주변의 3배를 넘으면 스파이크로 보고 '직전 대비' 기준에서 뺀다
ALERT_PER_ID = 6               # 같은 호텔·노선에서 한 번에 올리는 최대 건수(홍수 방지)
ALERT_LOCAL_STABLE = 2.0       # 가까운 날짜 묶음의 p75/p25 가 이보다 크면 '평소'로 쓰지 않는다
# ── 2026-11-21 오탐 차단 보완 ───────────────────────────────────────────────
# (a) 같은 요일 중앙값만 보면 '1주~2주짜리 비수기 구간'을 급락으로 잘못 잡는다
#     (h42 2/3 51만 < 1월 수요일 132만, h52 4/29 117만 < 4월 목요일 239만).
#     → 날짜 바로 앞뒤 며칠(요일 무관)도 같이 싸면 그 구간의 계절 요금으로 보고 뺀다.
# (b) 출처·산식이 통째로 바뀐 스냅샷(11-19 검색가 → 11-20 예약 사이트 직접 조회)은
#     srcs 표지가 남지 않은 경우도 있어, 이력에서 '여러 날짜가 같은 날 같은 방향으로 크게 움직인 날'을
#     직접 찾아 그 전 관측을 기준선에서 뺀다(h24 아마노이 365일이 한꺼번에 내려간 경우).
ALERT_NEAR_SPAN = 3            # 호텔 — 날짜 앞뒤 며칠을 '그 구간의 값'으로 볼지
ALERT_NEAR_MIN = 2             # 그 표본이 이만큼은 있어야 본다
ALERT_PATCH_MARGIN = 0.70      # 이웃 중앙값의 70% 아래로 내려간 값만 급락으로 본다(구간 비수기 제외)
ALERT_SWITCH_MIN = 5           # 한 스냅샷에서 이만큼의 날짜가 함께 움직이면 전환 후보
ALERT_SWITCH_RATIO = 0.30      # 그 '함께 움직임'의 폭(±30%)
ALERT_SWITCH_SHARE = 0.20      # 호텔 날짜 칸의 이 비율 이상이 움직여야 전환으로 본다
KST = datetime.timezone(datetime.timedelta(hours=9))


def today_kst(override=None):
    """오늘 날짜(YYYY-MM-DD, KST). 테스트·소급 실행은 --date 로 바꾼다."""
    if override:
        return override
    return datetime.datetime.now(KST).strftime('%Y-%m-%d')


def add_days(day, n):
    return (datetime.date.fromisoformat(day) + datetime.timedelta(days=n)).isoformat()


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
        fp.write('\n')
    os.replace(tmp, path)


def _load_hist(path, schema, seed):
    if not os.path.exists(path):
        obj = dict(seed)
        obj['schema'] = schema
        return obj
    try:
        obj = json.loads(_read(path))
    except ValueError:
        raise SystemExit('%s 가 올바른 JSON 이 아닙니다 — 지우지 말고 먼저 확인하세요.' % path)
    if obj.get('schema') != schema:
        raise SystemExit('%s 의 schema 가 %r 입니다(기대 %r)' % (path, obj.get('schema'), schema))
    if not isinstance(obj.get('series', obj.get('keys')), dict):
        raise SystemExit('%s 에 series/keys 가 없습니다' % path)
    return obj


def merge_series(store, current, snap, blank):
    """store(키 -> [스냅샷일, 값...]) 에 오늘 값이 직전과 다를 때만 덧붙인다.

    blank(key) 는 이번 스냅샷에서 사라진 키에 남길 값 튜플.
    같은 날 다시 돌면 마지막 줄을 고쳐 쓴다(하루에 여러 번 돌아도 한 줄).
    """
    added = changed = 0
    for key, vals in current.items():
        arr = store.get(key)
        if not arr:
            store[key] = [[snap] + list(vals)]
            added += 1
            continue
        if list(arr[-1][1:]) == list(vals):
            continue
        if arr[-1][0] == snap:
            arr[-1] = [snap] + list(vals)
        else:
            arr.append([snap] + list(vals))
        changed += 1
    for key in [k for k in store if k not in current]:
        arr = store[key]
        vals = blank(key)
        if arr[-1][0] == snap:
            if list(arr[-1][1:]) != list(vals):
                arr[-1] = [snap] + list(vals)
                changed += 1
        elif arr[-1][-1] != 'X':
            arr.append([snap] + list(vals))
            changed += 1
    return added, changed


def hotel_status(v):
    if isinstance(v, int):
        return 'E' if v >= ERROR_MIN else 'O'
    return 'N'


def hotel_current(master):
    """hotel_id -> {체크인 날짜: (현금가, 포인트, 상태)}."""
    out = {}
    for h in master['hotels']:
        pts = h.get('points') or {}
        cur = {}
        for d, v in (h.get('rates') or {}).items():
            p = pts.get(d)
            cur[d] = (v if isinstance(v, int) else None,
                      p if isinstance(p, int) else None,
                      hotel_status(v))
        out[h['id']] = cur
    return out


def flight_current(flights):
    """route_code -> {'출발일|패턴': (출발일, 패턴, 가격, 직항(1/0/None), 상태)}."""
    out = {}
    nosale = flights.get('noSale') or []
    for r in flights.get('routes') or []:
        cur = {}
        for d in r.get('deals') or []:
            v = d.get('via')
            direct = 1 if v is False else (0 if v is True else None)
            price = d.get('price')
            st = 'E' if isinstance(price, int) and price >= ERROR_MIN else 'O'
            cur['%s|%s' % (d.get('date'), d.get('pattern'))] = (
                d.get('date'), d.get('pattern'), price if isinstance(price, int) else None,
                direct, st)
        for n in nosale:
            if n.get('code') != r.get('code'):
                continue
            key = '%s|%s' % (n.get('date'), n.get('pattern'))
            if key in cur:
                continue
            st = {'unopened': 'U', 'nofare': 'N', 'nosale': 'D'}.get(n.get('status'), 'D')
            cur[key] = (n.get('date'), n.get('pattern'), None, None, st)
        out[r['code']] = cur
    return out


def ttang_key(d):
    return '%s_%s_%s_%s_%s' % (d.get('out'), d.get('back'), d.get('code'),
                               d.get('airline') or '', d.get('times') or '')


def ttang_current(tt):
    """airport_code -> {고정 키: (가격, 잔여석)}."""
    out = {}
    for d in (tt or {}).get('deals') or []:
        code = d.get('code')
        if not code:
            continue
        price = d.get('price')
        out.setdefault(code, {})[ttang_key(d)] = (
            price if isinstance(price, int) else None, d.get('seats'))
    return out


def _median(vals):
    v = sorted(vals)
    n = len(v)
    if not n:
        return None
    m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) / 2.0


def _drop_pct(base, price):
    if not base or price is None:
        return 0.0
    return round(100.0 * (1.0 - float(price) / float(base)), 1)


def _mdy(day):
    return '%s/%s/%s' % (day[5:7], day[8:10], day[0:4])


def hotel_url(h, ci, nights=1):
    """앱의 예약 링크 규칙(index.html bookUrlOf)과 같은 주소."""
    co = add_days(ci, nights)
    if h.get('fhr'):
        return h['fhr']
    g = h.get('group')
    if g == 'lux':
        rid = str(h.get('ref_id') or '').strip()
        if rid:
            return ('https://hotel.hotelux.com/#/hotel/detail?hotelId=%s&checkIn=%s&checkOut=%s'
                    '&numberOfAdults=2&numberOfChildren=0&numberOfRooms=1' % (rid, ci, co))
        return 'https://hotel.hotelux.com/'
    if g == 'accor' and h.get('code'):
        return ('https://all.accor.com/booking/ko/accor/hotel/%s?dateIn=%s&nights=%d'
                '&compositions=2&stayplus=false' % (h['code'], ci, nights))
    if g == 'marriott' and h.get('code'):
        return ('https://www.marriott.com/reservation/availabilitySearch.mi?propertyCode=%s'
                '&isSearch=true&fromDate=%s&toDate=%s&numberOfAdults=2&numberOfRooms=1'
                '&useRewards=false&searchType=QuickSearch' % (h['code'], _mdy(ci), _mdy(co)))
    return ''


def flight_url(code, date, back):
    return ('https://kr.trip.com/flights/showfarefirst?dcity=pus&acity=' + code.lower()
            + '&ddate=' + date + '&rdate=' + (back or date) + '&triptype=rt&class=y'
            '&quantity=1&locale=ko-KR&curr=KRW')


def _alert(kind, ident, name, city, date, price, base, why, **extra):
    a = {'k': kind, 'id': ident, 'name': name, 'city': city, 'date': date,
         'price': int(round(price)) if isinstance(price, (int, float)) else price,
         'base': int(round(base)) if base else None,
         'drop': _drop_pct(base, price), 'why': why}
    a.update({k: v for k, v in extra.items() if v not in (None, '', [])})
    return a


def _pctile(vals, q):
    v = sorted(vals)
    if not v:
        return None
    return v[int(round((len(v) - 1) * q))]


def _trim(vals, factor=4.0):
    """1일 스파이크(주변의 4배 초과)를 빼고 다시 중앙값을 낸다 — 기준선이 부풀지 않게."""
    if len(vals) < 5:
        return vals
    m = _median(vals)
    if not m:
        return vals
    return [v for v in vals if v <= m * factor]


def _local_base(pairs, date, span, kmin, k=ALERT_LOCAL_K, same_dow=False):
    """같은 호텔·노선 안에서 date 앞뒤 span일의 가까운 k개 값 중앙값(스파이크 제거).

    same_dow=True 면 요일이 같은 날짜(7·14·21일 전후)를 먼저 쓴다 — 주말만 비싼 호텔에서
    화요일 요금이 '평소의 절반'으로 보이는 오탐을 막는다. 그런 표본이 모자라면 전체 창으로 간다.
    """
    try:
        d0 = datetime.date.fromisoformat(date)
    except ValueError:
        return None
    near, same = [], []
    for d, v in pairs:
        try:
            gap = abs((datetime.date.fromisoformat(d) - d0).days)
        except ValueError:
            continue
        if not gap or gap > span:
            continue
        near.append((gap, v))
        if same_dow and gap % 7 == 0:
            same.append((gap, v))
    pool = same if len(same) >= kmin else near
    if len(pool) < kmin:
        return None
    pool.sort()
    vals = [v for _g, v in pool[:k]]
    if not _stable(vals, ALERT_LOCAL_STABLE):
        return None      # 그 주변 자체가 들쭉날쭉하면 '평소'라고 부를 수 없다
    return _median(_trim(vals))


def _stable(vals, limit=None):
    """값 묶음이 계절·객실 타입으로 크게 흔들리지 않는지(p75/p25)."""
    p25, p75 = _pctile(vals, 0.25), _pctile(vals, 0.75)
    if not p25 or not p75:
        return False
    return p75 / float(p25) <= (limit or ALERT_STABLE_RATIO)


def _near_base(pairs, date, span=ALERT_NEAR_SPAN, kmin=ALERT_NEAR_MIN):
    """date 바로 앞뒤 span일(요일 무관) 값의 중앙값 — '그 구간이 통째로 싼지'를 본다.

    같은 요일 중앙값만 보면 1~2주짜리 비수기 구간을 급락으로 잘못 잡는다.
    앞뒤 날짜까지 함께 싸면 그건 계절 요금표이고, 하루만 뚫린 값이라면 이 값보다 훨씬 높다.
    """
    try:
        d0 = datetime.date.fromisoformat(date)
    except ValueError:
        return None
    near = []
    for d, v in pairs:
        try:
            gap = abs((datetime.date.fromisoformat(d) - d0).days)
        except ValueError:
            continue
        if not gap or gap > span:
            continue
        near.append((gap, v))
    if len(near) < kmin:
        return None
    near.sort()
    return _median([v for _g, v in near[:6]])


def _switch_snaps(series, min_ratio=ALERT_SWITCH_RATIO, min_keys=ALERT_SWITCH_MIN,
                  share=ALERT_SWITCH_SHARE):
    """요금 출처·산식이 바뀐 스냅샷 — 같은 날 여러 날짜가 같은 방향으로 크게 움직인 날.

    2026-11-20 에 h24 아마노이 등이 11-19 검색값 → 11-20 예약 사이트 직접 조회값으로 통째로 바뀌었는데,
    srcs 표지가 그 전날 것까지 남아 있지 않아 '출처 전환'으로 걸리지 않고 365일이 급락으로 남았다.
    이력만 보고 그런 날을 찾아, 그 전 관측은 기준선에서 뺀다.
    """
    moved = {}
    for arr in series.values():
        for i in range(1, len(arr)):
            a, b = arr[i - 1][1], arr[i][1]
            if not (isinstance(a, int) and isinstance(b, int)) or a <= 0 or b <= 0:
                continue
            if a >= ERROR_MIN or b >= ERROR_MIN:
                continue
            r = b / float(a)
            if abs(r - 1) < min_ratio:
                continue
            moved.setdefault(arr[i][0], []).append(1 if r < 1 else -1)
    pool = sum(1 for arr in series.values() if len(arr) >= 2)
    out = []
    for sn, dirs in moved.items():
        if len(dirs) < min_keys or (pool and len(dirs) < pool * share):
            continue
        down, up = dirs.count(1), dirs.count(-1)
        if max(down, up) >= len(dirs) * 0.8:      # 한 방향으로 몰려 움직였을 때만
            out.append(sn)
    return sorted(out)


def _level_run_dates(changed, minrun=ALERT_LEVEL_RUN, minratio=ALERT_LEVEL_RATIO):
    """같은 스냅샷에 연속 날짜들이 함께 ±30% 넘게 움직였으면 '출처·산식 전환'으로 본다.

    changed: {날짜: (직전값, 이번값)}. 한 날짜만 튄 스파이크는 여기에 걸리지 않는다.
    """
    ratio = {}
    for d, (a, b) in changed.items():
        if isinstance(a, int) and isinstance(b, int) and 0 < a < ERROR_MIN and b < ERROR_MIN:
            ratio[d] = b / float(a)
    keys = sorted(ratio)
    out = set()
    i = 0
    while i < len(keys):
        run = [keys[i]]
        j = i + 1
        while j < len(keys) and keys[j] == add_days(keys[j - 1], 1):
            run.append(keys[j])
            j += 1
        if len(run) >= minrun:
            r = _median([ratio[d] for d in run])
            if r and abs(r - 1) >= minratio:
                out |= set(run)
        i = j
    return out


def _method_sig(h):
    """요금 출처·산식 표지 — 'VIP 요금 조사' / '예약 사이트 직접 조회' / '검색 호텔' 처럼
    source 문장 앞머리만 남긴다(날짜·회차·숫자는 버린다). 이게 바뀐 스냅샷은 급락이 아니다."""
    s = str(h.get('source') or '')
    for sep in (' · ', ' — ', ' / ', ' (', ',', '·'):
        if sep in s:
            s = s.split(sep)[0]
    s = ''.join(ch for ch in s if not ch.isdigit()).strip()
    return s[:28] or 'unknown'


def build_alerts(master, hist_hotels, hist_flights, hist_ttang, snap):
    """에러가 의심 후보 — ① 직전 스냅샷 대비 50%↓ ② 가까운 날짜 기준 50%↓ ③ 절대 초저가.

    오탐 차단(2026-11-20):
      (a) 출처·산식 전환 — source 표지가 바뀐 스냅샷, 또는 같은 스냅샷에 연속 5일 이상이
          함께 ±30% 넘게 움직인 묶음은 '급락'이 아니라 측정 방식이 바뀐 것으로 보고 뺀다.
      (b) 기준선 — 1년 전체 중앙값 대신 같은 호텔·노선의 앞뒤 35·42일 값을 먼저 쓰고,
          1일 스파이크(주변의 4배 초과)는 기준선에서 뺀다. 계절 편차가 큰 묶음(p75/p25>1.5)은
          1년 중앙값을 아예 쓰지 않는다.
      (c) 예약창 — 직전 스냅샷에 요금이 없던(null·판매편 없음·예약창 미오픈) 칸이 이번에
          요금을 얻은 것은 '급락'이 아니므로 뺀다. 처음 관측된 칸은 이력이 없으므로 남긴다.

    오탐 차단(2026-11-21 보완 — 교차 검수에서 15건 중 12건이 오탐으로 지적됨):
      (d) 구간 비수기 — 같은 요일 중앙값은 1~2주짜리 계절 구간을 놓친다. 날짜 앞뒤 3일(요일 무관)
          값의 중앙값보다 30% 이상 싼 경우에만 급락으로 본다(h42 2/3·h52 4/29 등이 여기서 빠졌다).
      (e) 이력으로 찾은 산식 전환 — 한 스냅샷에서 여러 날짜가 같은 방향으로 ±30% 넘게 움직였으면
          그 스냅샷을 전환으로 보고 그 전 관측을 기준선에서 뺀다(srcs 표지가 없어도 걸린다 — h24).
      (f) '직전 대비'는 그 스냅샷에 실제로 관측된 값에만 적용한다 — 값이 안 바뀐 날 이전 관측의
          차이를 매일 다시 세어 보고하지 않는다(11-21 에 15건이 불어난 직접 원인).

    오탐 차단(2026-11-22 — ③ 동남아 196곳 첫 관측):
      (g) '절대 초저가'도 그 호텔의 1년 중앙값 절반 이하이고 같은 값이 3일 이상 반복되지 않을 때만
          남긴다. 동남아 이비스·머큐어는 비수기 1박이 2.6만~4.9만 원이 정상이라, 5만 원 기준만 쓰면
          72건이 '에러 의심'으로 올라왔다.
      (h) 이 스냅샷이 그 호텔의 **첫 관측**이면 '기준 대비 50%↓'는 1년 중앙값 절반 이하일 때만 남긴다.
          주변이 매진(null)이라 비싼 날만 남은 호텔(앙사나 라구나 푸켓 12/15)이 '급락'으로 잡히던 것을 막는다.
    """
    out = []
    suppressed = {'level': 0, 'method': 0, 'window': 0, 'spike': 0, 'patch': 0, 'cap': 0, 'first': 0}

    # ① 호텔
    for h in master['hotels']:
        obj = hist_hotels.get(h['id']) or {}
        series = obj.get('series') or {}
        if not series:
            continue
        latest = {k: v[-1] for k, v in series.items()}
        prev = {k: (v[-2] if len(v) >= 2 else None) for k, v in series.items()}
        sigs = obj.get('srcs') or {}
        sig_now = _method_sig(h)
        snaps = sorted(sigs)
        method_switch = bool(snaps and snaps[-1] == snap and len(snaps) >= 2
                             and sigs[snaps[-2]] != sigs[snaps[-1]])
        changed = {}
        for k, arr in series.items():
            if len(arr) >= 2 and arr[-1][0] == snap and arr[-2][0] != snap:
                changed[k] = (arr[-2][1], arr[-1][1])
        level = _level_run_dates(changed)
        switches = _switch_snaps(series)
        sw = switches[-1] if switches else None
        # 전환 스냅샷이 있으면 그 전 관측(다른 산식으로 잰 값)은 기준선에서 뺀다
        fresh = {k: a for k, a in latest.items() if not sw or a[0] >= sw}
        vals = [a[1] for a in fresh.values() if isinstance(a[1], int) and a[1] < ERROR_MIN]
        year_any = _median(_trim(vals)) if len(vals) >= ALERT_MIN_HOTEL else None
        year = year_any
        if year and not _stable(vals):
            year = None
        # 이 호텔의 첫 관측인가 — 직전 스냅샷에 이 호텔 값이 하나도 없으면 그렇다
        first_obs = not any(p for p in prev.values())
        rep = {}
        for v in vals:
            rep[v] = rep.get(v, 0) + 1
        pairs = [(k, a[1]) for k, a in fresh.items() if isinstance(a[1], int) and a[1] < ERROR_MIN]
        prevpairs = [(k, p[1]) for k, p in prev.items() if p and isinstance(p[1], int) and p[1] < ERROR_MIN]
        for key, last in latest.items():
            v = last[1]
            if not isinstance(v, int) or v >= ERROR_MIN:
                continue
            pv = prev.get(key)
            prevprice = pv[1] if pv and isinstance(pv[1], int) and pv[1] < ERROR_MIN else None
            first_seen = len(series[key]) == 1
            today = (last[0] == snap)          # 이번 스냅샷에서 실제로 관측된 값인가
            if method_switch:
                suppressed['method'] += 1
                continue
            if sw and last[0] < sw:
                suppressed['method'] += 1     # 전환 전 산식으로 잰 값 — 지금 기준선과 비교하지 않는다
                continue
            if key in level:
                suppressed['level'] += 1
                continue
            if pv and prevprice is None and not first_seen:
                suppressed['window'] += 1
                continue
            base_loc = _local_base(pairs, key, ALERT_LOCAL_SPAN_H, ALERT_LOCAL_MIN_H, same_dow=True)
            near = _near_base(pairs, key)
            prev_ok = True
            if prevprice:
                ref = _local_base(prevpairs, key, ALERT_LOCAL_SPAN_H, ALERT_LOCAL_MIN_H, same_dow=True) or year
                if ref and prevprice > ref * ALERT_PREV_SPIKE:
                    prev_ok = False
                    suppressed['spike'] += 1
            why = base = None
            if today and prevprice and prev_ok and v <= prevprice * ALERT_DROP:
                why, base = '직전 대비 50%↓', prevprice
            elif v <= ALERT_HOTEL_LOW and (year_any is None or v <= year_any * ALERT_DROP) \
                    and rep.get(v, 0) < ALERT_TIER_REPEAT:
                why, base = '초저가', ALERT_HOTEL_LOW
            else:
                base = base_loc or year
                if base and v <= base * ALERT_DROP and rep.get(v, 0) < ALERT_TIER_REPEAT \
                        and (prevprice is not None or first_seen):
                    if first_obs and year_any and v > year_any * ALERT_DROP:
                        suppressed['first'] += 1
                        continue
                    why = '기준 대비 50%↓'
                    # 앞뒤 날짜도 함께 싸면 1~2주짜리 비수기 구간 — 하루만 뚫린 급락이 아니다
                    if near is not None and v > near * ALERT_PATCH_MARGIN:
                        suppressed['patch'] += 1
                        why = None
            if not why:
                continue
            out.append(_alert('hotel', h['id'], h['name'], h.get('city'), key, v, base, why,
                              tab=h.get('group'), url=hotel_url(h, key)))

    # ② ⑤ 항공 — 노선·패턴·직항 여부가 같은 칸끼리, 앞뒤 42일을 기준으로 비교
    for r in master['flights'].get('routes') or []:
        obj = hist_flights.get(r['code']) or {}
        series = obj.get('series') or {}
        if not series:
            continue
        changed = {}
        for key, arr in series.items():
            if len(arr) >= 2 and arr[-1][0] == snap and arr[-2][0] != snap:
                changed[arr[-1][1]] = (arr[-2][3], arr[-1][3])
        level = _level_run_dates(changed)
        groups = {}
        for key, arr in series.items():
            last = arr[-1]
            groups.setdefault((last[2], last[4]), []).append((key, arr))
        backs = {}
        for d in r.get('deals') or []:
            backs[(d.get('date'), d.get('pattern'))] = d.get('back')
        for (_pat, _direct), items in groups.items():
            pairs = [(a[-1][1], a[-1][3]) for _k, a in items
                     if isinstance(a[-1][3], int) and a[-1][3] < ERROR_MIN]
            if len(pairs) < ALERT_MIN_FLIGHT:
                continue
            vals = [v for _d, v in pairs]
            year = _median(_trim(vals))
            if not _stable(vals):
                year = None
            rep = {}
            for v in vals:
                rep[v] = rep.get(v, 0) + 1
            for _key, arr in items:
                last = arr[-1]
                date, pattern, price, direct = last[1], last[2], last[3], last[4]
                if not isinstance(price, int) or price >= ERROR_MIN:
                    continue
                if date in level:
                    suppressed['level'] += 1
                    continue
                pv = arr[-2] if len(arr) >= 2 and arr[-2][0] != snap else None
                prevprice = pv[3] if pv and isinstance(pv[3], int) and pv[3] < ERROR_MIN else None
                if pv and (prevprice is None or pv[4] != direct):
                    suppressed['window'] += 1
                    continue
                first_seen = len(arr) == 1
                base = _local_base(pairs, date, ALERT_LOCAL_SPAN_F, ALERT_LOCAL_MIN_F) or year
                why = None
                if prevprice and price <= prevprice * ALERT_DROP:
                    why, base = '직전 대비 50%↓', prevprice
                elif price <= ALERT_FLIGHT_LOW:
                    why, base = '초저가', ALERT_FLIGHT_LOW
                elif base and price <= base * ALERT_DROP and rep.get(price, 0) < ALERT_TIER_REPEAT \
                        and (prevprice is not None or first_seen):
                    why = '기준 대비 50%↓'
                if not why:
                    continue
                back = backs.get((date, pattern))
                out.append(_alert('flight', r['code'], r.get('city'), r.get('city'), date,
                                  price, base, why, back=back, pattern=pattern,
                                  via=(1 if direct == 1 else (0 if direct == 0 else None)),
                                  tab='flight', url=flight_url(r['code'], date, back)))

    # ③ ⑥ 땡처리 — 공항·항공사·시각이 같은 상품끼리 비교
    by_air = {}
    for d in (master.get('ttang') or {}).get('deals') or []:
        by_air.setdefault(d.get('code'), []).append(d)
    for code, deals in by_air.items():
        series = (hist_ttang.get(code) or {}).get('keys') or {}
        groups = {}
        for d in deals:
            groups.setdefault((d.get('airline') or '', d.get('times') or ''), []).append(d)
        # 항공사·시각까지 같은 상품이 5건 미만이면 공항 전체(같은 노선)를 기준으로 쓴다
        if any(len(v) >= ALERT_MIN_TTANG for v in groups.values()):
            buckets = [v for v in groups.values() if len(v) >= ALERT_MIN_TTANG]
        else:
            buckets = [deals]
        for items in buckets:
            vals = [d['price'] for d in items if isinstance(d.get('price'), int)
                    and d['price'] < ERROR_MIN]
            if len(vals) < ALERT_MIN_TTANG:
                continue
            med = _median(_trim(vals))
            if not _stable(vals):
                med = med if len(vals) >= ALERT_MIN_TTANG * 3 else None
            rep = {}
            for d in items:
                if isinstance(d.get('price'), int):
                    rep[d['price']] = rep.get(d['price'], 0) + 1
            for d in items:
                price = d.get('price')
                if not isinstance(price, int) or price >= ERROR_MIN:
                    continue
                key = ttang_key(d)
                arr = series.get(key) or []
                pv = arr[-2] if len(arr) >= 2 and arr[-2][0] != snap else None
                prevprice = pv[1] if pv and isinstance(pv[1], int) else None
                if pv and prevprice is None:
                    suppressed['window'] += 1
                    continue
                first_seen = len(arr) == 1
                why = base = None
                if prevprice and price <= prevprice * ALERT_DROP:
                    why, base = '직전 대비 50%↓', prevprice
                elif price <= ALERT_FLIGHT_LOW:
                    why, base = '초저가', ALERT_FLIGHT_LOW
                elif med and price <= med * ALERT_DROP and rep.get(price, 0) < ALERT_TIER_REPEAT \
                        and (prevprice is not None or first_seen):
                    why, base = '기준 대비 50%↓', med
                if not why:
                    continue
                out.append(_alert('ttang', code, d.get('city'), d.get('city'), d.get('out'),
                                  price, base, why, back=d.get('back'),
                                  airline=d.get('airline'), seats=d.get('seats'), key=key,
                                  tab='tt', url=d.get('url')))

    # 같은 호텔이 두 탭에 있을 때 같은 날짜가 두 번 뜨지 않게 묶는다
    seen = {}
    for a in out:
        k = (a['k'], a['name'], a['date'], a.get('pattern'), a.get('airline'), a.get('back'))
        if k in seen:
            seen[k]['also'] = (seen[k].get('also') or 0) + 1
            continue
        seen[k] = a
    alerts = list(seen.values())
    alerts.sort(key=lambda a: (-a['drop'], a['price'] or 0, a['date']))
    # 한 호텔·노선이 목록을 독차지하지 않게 급락 폭이 큰 것부터 ALERT_PER_ID 건만 남긴다
    capped, per = [], {}
    for a in alerts:
        k = (a['k'], a['id'])
        if per.get(k, 0) >= ALERT_PER_ID:
            suppressed['cap'] += 1
            continue
        per[k] = per.get(k, 0) + 1
        capped.append(a)
    return capped, suppressed


def snapshot_run(master, args, verbose=True):
    """data/history/ 에 오늘 스냅샷을 누적하고 alerts.json 을 다시 쓴다."""
    snap = today_kst(getattr(args, 'date', None))
    cur_h = hotel_current(master)
    cur_f = flight_current(master['flights'])
    cur_t = ttang_current(master.get('ttang'))

    hist_hotels, hist_flights, hist_ttang = {}, {}, {}
    added = changed = files = 0

    for h in master['hotels']:
        path = os.path.join(HIST_HOTELS, h['id'] + '.json')
        obj = _load_hist(path, SCHEMA_HOTEL_HIST,
                         {'id': h['id'], 'name': h['name'], 'group': h.get('group'),
                          'city': h.get('city'), 'unit': 'KRW', 'series': {}})
        series = obj['series']
        a, c = merge_series(series, cur_h.get(h['id']) or {}, snap,
                            lambda key: (None, None, 'X'))
        # 요금 출처·산식 표지 — 다음 스냅샷에서 '출처가 바뀐 급락'을 가려내는 데 쓴다(최근 6회만)
        sig = _method_sig(h)
        srcs = obj.get('srcs') if isinstance(obj.get('srcs'), dict) else {}
        sig_changed = srcs.get(snap) != sig
        srcs[snap] = sig
        for old_snap in sorted(srcs)[:-6]:
            srcs.pop(old_snap, None)
        obj['srcs'] = srcs
        obj.update({'name': h['name'], 'group': h.get('group'), 'city': h.get('city'),
                    'updated': snap})
        if a or c or sig_changed or not os.path.exists(path):
            _write_json(path, obj)
            files += 1
        added += a
        changed += c
        hist_hotels[h['id']] = obj

    for r in master['flights'].get('routes') or []:
        code = r['code']
        path = os.path.join(HIST_FLIGHTS, code + '.json')
        obj = _load_hist(path, SCHEMA_FLIGHT_HIST,
                         {'code': code, 'city': r.get('city'), 'unit': 'KRW', 'series': {}})
        series = obj['series']
        a, c = merge_series(series, cur_f.get(code) or {}, snap,
                            lambda key: (key.split('|')[0], key.split('|')[1], None, None, 'X'))
        obj.update({'city': r.get('city'), 'updated': snap})
        if a or c or not os.path.exists(path):
            _write_json(path, obj)
            files += 1
        added += a
        changed += c
        hist_flights[code] = obj

    for code, cur in cur_t.items():
        city = ''
        for d in (master.get('ttang') or {}).get('deals') or []:
            if d.get('code') == code:
                city = d.get('city') or ''
                break
        path = os.path.join(HIST_TTANG, code + '.json')
        obj = _load_hist(path, SCHEMA_TTANG_HIST,
                         {'code': code, 'city': city, 'unit': 'KRW', 'keys': {}})
        store = obj['keys']
        a, c = merge_series(store, cur, snap, lambda key: (None, None))
        obj.update({'city': city, 'updated': snap})
        if a or c or not os.path.exists(path):
            _write_json(path, obj)
            files += 1
        added += a
        changed += c
        hist_ttang[code] = obj

    alerts, suppressed = build_alerts(master, hist_hotels, hist_flights, hist_ttang, snap)
    total = len(alerts)
    kept = alerts[:ALERT_CAP]
    counts = {'total': total, 'hotel': 0, 'flight': 0, 'ttang': 0}
    for a in alerts:
        counts[a['k']] = counts.get(a['k'], 0) + 1
    counts['suppressed'] = dict(suppressed)
    _write_json(HIST_ALERTS, {
        'schema': SCHEMA_ALERTS,
        'generated': snap,
        'rules': {'dropPct': int(ALERT_DROP * 100), 'hotelLow': ALERT_HOTEL_LOW,
                  'flightLow': ALERT_FLIGHT_LOW, 'excludeAt': ERROR_MIN,
                  'tierRepeat': ALERT_TIER_REPEAT,
                  'localSpan': {'hotel': ALERT_LOCAL_SPAN_H, 'flight': ALERT_LOCAL_SPAN_F},
                  'levelRun': ALERT_LEVEL_RUN, 'levelRatio': int(ALERT_LEVEL_RATIO * 100),
                  'prevSpike': ALERT_PREV_SPIKE, 'perId': ALERT_PER_ID,
                  'patch': {'span': ALERT_NEAR_SPAN, 'margin': int(ALERT_PATCH_MARGIN * 100)},
                  'switch': {'min': ALERT_SWITCH_MIN, 'ratio': int(ALERT_SWITCH_RATIO * 100),
                             'share': int(ALERT_SWITCH_SHARE * 100)},
                  'basis': '같은 호텔(노선·패턴·직항 여부) 안에서 앞뒤 35·42일(같은 요일) 기준 50%↓ 또는 '
                           '이번 스냅샷에서 실제로 바뀐 값의 직전 대비 50%↓ 또는 절대 초저가. '
                           '출처·산식 전환, 연속 5일 이상 동시 이동, 요금 없던 칸이 열린 경우, '
                           '날짜 앞뒤 3일도 함께 싼 구간 비수기는 뺀다'},
        'counts': counts,
        'shown': len(kept),
        'alerts': kept,
    })
    files += 1

    hist = {'snap': snap, 'files': files, 'added': added, 'changed': changed,
            'alerts': total, 'alert_counts': counts, 'shown': len(kept)}
    if verbose:
        print('이력 스냅샷 %s — 파일 %d개 갱신(신규 %d줄 · 변경 %d줄)' % (snap, files, added, changed))
        print('  호텔 %d곳 · 항공 %d노선 · ⑥ 땡처리 %d개 공항'
              % (len(hist_hotels), len(hist_flights), len(hist_ttang)))
        print('  🚨 에러가 의심 %d건 (호텔 %d · 항공 %d · ⑥ %d)'
              % (total, counts.get('hotel', 0), counts.get('flight', 0), counts.get('ttang', 0)))
        if suppressed:
            print('  오탐 차단 — 출처·산식 전환 %d · 연속 동시 이동 %d · 예약창 열림 %d · 직전 스파이크 %d · 구간 비수기 %d · 건수 상한 %d'
                  % (suppressed.get('method', 0), suppressed.get('level', 0),
                     suppressed.get('window', 0), suppressed.get('spike', 0),
                     suppressed.get('patch', 0), suppressed.get('cap', 0)))
    return hist


def cmd_snapshot(args):
    """data/history/ — 오늘 스냅샷만 따로 쌓는다(master_db.json 은 그대로)."""
    master = json.loads(_read(MASTER))
    snapshot_run(master, args)
    size = cnt = 0
    for base, _dirs, names in os.walk(HIST_DIR):
        for n in names:
            size += os.path.getsize(os.path.join(base, n))
            cnt += 1
    print('  data/history/ %d개 파일 · %.1f KB' % (cnt, size / 1024.0))
    return 0


def _check_hist_file(problems, path, schema, size, known, keyname):
    try:
        obj = json.loads(_read(path))
    except ValueError:
        problems.append('history JSON 손상: %s' % os.path.relpath(path, ROOT))
        return
    if obj.get('schema') != schema:
        problems.append('history schema 다름: %s' % os.path.relpath(path, ROOT))
    series = obj.get('series', obj.get('keys'))
    if not isinstance(series, dict):
        problems.append('history series 없음: %s' % os.path.relpath(path, ROOT))
        return
    if obj.get(keyname) not in known:
        problems.append('history %s 가 master 에 없음: %s'
                        % (keyname, os.path.relpath(path, ROOT)))
    for key, arr in series.items():
        if not isinstance(arr, list) or not arr:
            problems.append('history %s 키 %r 비어 있음' % (os.path.relpath(path, ROOT), key))
            continue
        for row in arr:
            if not isinstance(row, list) or len(row) != size:
                problems.append('history %s 키 %r 줄 길이 %s (기대 %d)'
                                % (os.path.relpath(path, ROOT), key,
                                   len(row) if isinstance(row, list) else row, size))
                break
            if not isinstance(row[0], str) or len(row[0]) != 10:
                problems.append('history %s 키 %r 스냅샷일 이상: %r'
                                % (os.path.relpath(path, ROOT), key, row[0]))
                break
            if size > 3 and row[-1] not in HIST_STATUS:
                problems.append('history %s 키 %r 상태 코드 이상: %r'
                                % (os.path.relpath(path, ROOT), key, row[-1]))
                break
        dates = [r[0] for r in arr if isinstance(r, list) and r]
        if dates != sorted(dates):
            problems.append('history %s 키 %r 스냅샷일 순서 이상'
                            % (os.path.relpath(path, ROOT), key))


def check_history(problems):
    """data/history/ 가 master_db.json 과 어긋나지 않는지 — 아직 없으면 건너뛴다."""
    if not os.path.isdir(HIST_DIR):
        return
    master = json.loads(_read(MASTER))
    ids = {h['id'] for h in master['hotels']}
    codes = {r['code'] for r in master['flights'].get('routes') or []}
    ttcodes = {d.get('code') for d in (master.get('ttang') or {}).get('deals') or []}

    for folder, schema, size, known, keyname in (
            (HIST_HOTELS, SCHEMA_HOTEL_HIST, 4, ids, 'id'),
            (HIST_FLIGHTS, SCHEMA_FLIGHT_HIST, 6, codes, 'code'),
            (HIST_TTANG, SCHEMA_TTANG_HIST, 3, ttcodes, 'code')):
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith('.json'):
                _check_hist_file(problems, os.path.join(folder, name),
                                 schema, size, known, keyname)

    if not os.path.exists(HIST_ALERTS):
        return
    try:
        al = json.loads(_read(HIST_ALERTS))
    except ValueError:
        problems.append('history alerts.json 손상')
        return
    if al.get('schema') != SCHEMA_ALERTS:
        problems.append('alerts.json schema 다름')
    rows = al.get('alerts')
    if not isinstance(rows, list):
        problems.append('alerts.json alerts 목록 없음')
        return
    counts = al.get('counts') or {}
    if len(rows) < ALERT_CAP and counts.get('total') != len(rows):
        problems.append('alerts.json counts.total %s vs 목록 %d'
                        % (counts.get('total'), len(rows)))
    if len(rows) > ALERT_CAP:
        problems.append('alerts.json %d건 (상한 %d)' % (len(rows), ALERT_CAP))
    for a in rows:
        if a.get('k') not in ('hotel', 'flight', 'ttang'):
            problems.append('alerts.json 종류 이상: %r' % a.get('k'))
            break
        if a.get('why') not in ALERT_WHY:
            problems.append('alerts.json 사유 이상: %r' % a.get('why'))
            break
        if not isinstance(a.get('price'), int) or not a.get('date'):
            problems.append('alerts.json 값 이상: %r' % a.get('id'))
            break

def main(argv):
    import argparse
    import datetime
    p = argparse.ArgumentParser(description='hotel-calendar-app 통합 마스터 DB 도구')
    p.add_argument('command', choices=['extract', 'verify', 'inject', 'parts', 'refresh',
                                    'stats', 'snapshot'])
    p.add_argument('--now', default=datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z'),
                   help='extract 시 기록할 생성 시각')
    p.add_argument('--date', default=None,
                   help='snapshot/inject 시 기록할 스냅샷 날짜(YYYY-MM-DD, 기본 오늘 KST)')
    args = p.parse_args(argv)
    return {'extract': cmd_extract, 'verify': cmd_verify, 'inject': cmd_inject,
            'parts': cmd_parts, 'refresh': cmd_refresh, 'stats': cmd_stats,
            'snapshot': cmd_snapshot}[args.command](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
