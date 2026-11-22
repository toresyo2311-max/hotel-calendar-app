/* TEAM-부산 호텔·항공 요금 달력 — 서비스 워커 (2026-11-22 z52 · ② 중올플 + ③ 아코르 → ② 아코르 536곳 통합) · z51 ③ 아코르 레드핫 32건 · 호텔 265곳 · z50 ⑧ 외항사 마일 부산·인천 출발·귀국 양방향 1년치(365일) 실측 175,128건 · z40 디자인 시스템 v2 — 색·타입·깊이·모서리·모션을 토큰 하나로 정리 / z34 · ⑧ 외항사 마일리지(부산) 신설 — 9개 프로그램 부산 보너스 좌석 625건 / ⑥ 땡처리 3,847건 · 44개 노선 / ③ 아코르 동남아 196곳 × 365일 실측)
   · z52 (2026-11-22) — **② 중올플 + ③ 아코르 → ② 아코르 536곳** 통합. ② 중올플 289곳과 ③ 아코르 265곳 가운데 같은 호텔 18곳을 한 카드로 합쳤습니다(중국(APC) 291 · 국내 30 · 동남아 196 · 기타 해외 19, 데이터 `data/app/tab2_accor.json` 하나). 탭은 ② 아코르 하나로 정리하고 뒤 탭 번호를 ③ 메리어트 · ④ 항공 · ⑤ 땡처리 · ⑥ 마일리지 · ⑦ 외항사 마일로 맞췄습니다. 화면 위에는 **지역 칩(전체·국내·동남아·중국(APC)·기타 해외)** 과 **요금 유형(1박 최저가 · Stay Plus 2박 · Stay Plus 토 3박 · Red Hot Rooms · APC 무료숙박)** 을 두고, 중올플 전용 필터(권역 · 12월 APC 가능 호텔 · 약관 제외일 · 무료숙박 가능일)는 **중국(APC) 지역/APC 무료숙박 모드에서만** 보이게 했습니다. 중국·홍콩·마카오 호텔은 위챗 예약 시트와 아코르 공홈 링크를 함께 열고, 호텔럭스 이중 연결(11곳)·레드핫 상세 카드도 그대로 동작합니다. 옛 주소(#tab=china · #tab=domestic · 사라진 호텔 id)는 통합 탭·남은 카드로 이어집니다. 함께 고침 — APC 무료숙박 상태가 최신 확인 +72시간을 기준으로 계산돼 최신 확인 호텔 한 곳만 남고 나머지가 전부 '미확인'으로 보이던 문제(12월 가능일 1곳 → 203곳). 검증: `master_db.py inject`·`verify` 통과(호텔 759 · 통합 536 · 칸 270,465)
   · z51 (2026-11-22) — ③ 아코르에 **Red Hot Rooms(레드핫 요금제)**를 넣었습니다. ALL Accor+ Explorer 회원 전용 오퍼 목록(accorplus.com)에서 2026-11-22에 받은 오퍼 32건을 그대로 옮겨, 기존 ③ 아코르 247곳 가운데 14곳에는 레드핫을 더하고 나머지 18곳(인도네시아 7 · 필리핀 4 · 캄보디아 2 · 말레이시아 1 · 몰디브 1 · 호주 1 · 일본 삿포로 1)은 새 호텔로 넣었습니다 — ③ 아코르가 247곳에서 **265곳**이 됩니다. 요금 유형에 **「Red Hot Rooms」** 버튼을 두고, 조건 필터에 **「레드핫」**을 넣었습니다. 달력 칸은 오퍼의 투숙 기간에만 원화 참고 환산 시작가가 뜨고(2026-11-22 환율 · 100원 단위), 기간 밖은 —입니다. 날짜 상세에는 **레드핫 시작가(원화 + 현지 통화 원문) · 정상가 대비 할인 · 투숙 기간 · 예약 마감일(D-n) · 객실 타입 · ALL Accor+ Explorer 회원 전용 안내 · 오퍼 페이지 / 아코르 공홈 예약 링크**가 함께 나옵니다. 세금 표기(++, +++, net)는 원문 그대로입니다. 오퍼 4곳(소피텔 크라비 · 노보텔 푸켓 시티 · 이비스 스타일 푸켓 · 프리미어 빌리지 푸꾸옥)은 투숙 기간이 2026-11-30에 끝나 달력 창(12-01~) 안에 날짜가 없어 「오퍼 종료」로 적었습니다. 기존 365일 최저가·Stay Plus 값은 건드리지 않았습니다.
   · z50 (2026-11-22) — ⑧ 플라잉블루 링크 수정: 안드로이드에서 눌러도 아무 반응이 없던 문제(앱 딥링크를 href 에 그대로 넣어 인앱 브라우저·홈 화면 앱이 intent:// 를 무시하던 것)를 고쳤습니다. 링크 주소는 언제나 공식 웹(https://wwws.airfrance.co.kr/)으로 두고, 안드로이드에서만 클릭 순간 앱 인텐트(호스트 www.airfrance.com/home · action VIEW · category BROWSABLE · package com.airfrance.android.dinamoprd · browser_fallback_url)를 시도해 1.2초 안에 화면이 넘어가지 않으면 공식 웹으로 스스로 이동합니다. 아이폰·데스크톱은 공식 웹 새 탭 그대로.
   · z49 (2026-11-22) — ⑧ 외항사 마일 공식 링크: 에어프랑스·KLM 플라이 블루만 안드로이드에서 공식 앱 딥링크(intent:// … package=com.airfrance.android.dinamoprd · 구글 플레이 'Air France - Book a flight' 확인값, S.browser_fallback_url=https://wwws.airfrance.co.kr/)로 열리게 했습니다. 앱이 없으면 같은 주소의 공식 웹으로 이어지고, 아이폰·데스크톱은 기존처럼 공식 웹을 새 탭으로 엽니다. 날짜 상세에 한 줄 안내를 넣었습니다.
   · z48 (2026-11-22) — ⑧ 외항사 마일: 귀국편(→부산 PUS · →인천 ICN) 1년치(2026-11-22~2027-11-21)를 실측해 출발편과 합쳤습니다. 부산 8,462건(출발 4,663 · 도착 3,799 — 플라잉블루 870 · 스마일즈 1,146 · 버진 2,718 · 델타 2,715 · 유나이티드 157 · 에어로플랜 856 · 옌타이 공홈 실측 42행 보존) · 인천 166,666건(출발 82,906 · 도착 83,760 — 플라잉블루 29,913 · 스마일즈 23,109 · 버진 24,516 · 델타 31,031 · 유나이티드 23,803 · 에어로플랜 33,855 · 아시아마일즈 439). 영국항공·JAL은 조회 사이트에 부산·인천 자료가 없음을 실측 확인(0건으로 정직 표기). 상단 방향 버튼(부산 출발/도착 · 인천 출발/도착)으로 달력·목록·도시 칩·월별 최저 띠·KPI·날짜 상세가 함께 바뀌고, 날짜 상세 시트 맨 위에 「↔ 왕복 짝 — 같은 날 반대 방향」 최저 마일과 방향을 바꾸는 버튼을 넣었습니다. 국내선(김포·제주 ↔ 부산)은 뺐고 값 보간은 없습니다. 함께 고침: 직항/경유 표시를 'Direct Carriers'(직항 편이 있는가) 기준으로 바로잡아, 좌석 수를 0으로 주는 프로그램(아시아마일즈 439건 · 유나이티드 인천 651건)의 직항 편이 '1회 경유'로 잘못 적히던 것을 바로잡았습니다.
   · z47 (2026-11-22) — ⑧ 안내문의 프로그램별 수집 범위 문구에 남아 있던 '원천' 표기를 '조회 사이트'로 정리(자료 문구 포함).
   · z46 (2026-11-22) — 하단 안내 정리: ⑧ 외항사 마일 '수집 범위' 안내문과 각 탭·푸터의 조회 기준·자료 기준·갱신 이력을 접기(기본 접힘)로 내리고, 푸터 자료 기준을 탭별 조회일 한 줄로 요약, 발치 문구를 'OFFLINE FILE / 2026-11-19 통합판'에서 'TEAM-부산 · 2026-11-22'로 정비. '원천' 같은 수집기 용어를 '조회 사이트'로 다듬고, ⑤ 프로모션 카드의 '최대 20%부산–후쿠오카'처럼 붙어 나오던 문자열 결합을 고침. 기능·자료 수치는 변경 없음.
   · z45 (2026-11-22) — ⑧ 외항사 마일: 로그인 실측(PRO 전체 연도)으로 부산·인천 출발을 모두 1년(2026-11-22~2027-11-21, 365일)로 확장.
     부산 6개 프로그램 4,663건(플라잉블루 519 · 스마일즈 622 · 버진 1,441 · 델타 1,575 · 유나이티드 68 · 에어로플랜 438 · 옌타이 공홈 실측 42행 보존),
     인천 7개 프로그램 82,906건(플라잉블루 14,360 · 스마일즈 11,196 · 버진 11,789 · 델타 16,588 · 유나이티드 11,959 · 에어로플랜 16,801 · 아시아마일즈 213).
     영국항공·JAL은 원천에 부산·인천 자료가 없음(실측 확인). 2027-02~11 달력이 채워지고 미수집 안내는 사라짐.
   · z43 (2026-11-22) — ⑧ 외항사 마일: 출발지 전환(부산 PUS / 인천 ICN)과 인천(ICN) 출발 9개 프로그램 실측 9,159건 추가. 인천 자료는 2026-11-22~2027-01-21(61일) 원천 비로그인 창까지 7개 프로그램(플라잉블루·스마일즈·버진·델타·유나이티드·에어로플랜·아시아마일즈 40건) 125개 도시, 영국항공·JAL은 원천에 인천 자료 없음. 달력·목록·도시별 최저·날짜 상세 시트·직항/경유·공식 발권 링크가 출발지에 따라 함께 바뀌고, 자료는 data/app/tab9_partner_mileage_icn.json(약 600KB)로 지연 로딩.
   · z42 (2026-11-22) — ⑧ 플라잉블루 부산→옌타이(YNT) 실측 42일로 확장(2026-11-22~2027-01-03 · 12-25·01-04는 공홈이 결과를 주지 않아 미수집). 12-27 이후는 같은 플라잉블루 엔진의 에어프랑스 프랑스 사이트에서 실측(12-26 값 대조 일치). 수집 구간 표기 2027-01-03까지.
  · z41 (2026-11-22) — ⑧ 에어프랑스 플라잉블루 부산(PUS)→옌타이(YNT) 보너스 좌석 34일 실측 추가(2026-11-22~12-26, 이코노미 10,000~20,000마일·비즈니스 30,000~33,500마일, 프리미엄·퍼스트는 전 편성 미노출). 옌타이 도시명 등록. 수집 구간은 2026-12-26까지로 정직하게 표기(그 뒤는 미수집).
  · z40 (2026-11-22) — 디자인 시스템 v2: 딥 플럼·바이올렛 정체성은 그대로 두고 ① 토큰(표면·글자·의미색·가격대 5단계·깊이 3단계·모서리 스케일)을 한 블록으로 모아 정리 ② 숫자는 전부 tabular(가격·날짜·마일·퍼센트 자리수 고정) ③ muted2 8b86a3 → 6b6484(작은 글자 4.5:1 확보) ④ 헤더 지표·탭·필터 칩·TOP5 목록·달력 칸·KPI·예약처 시트의 여백과 테두리·그림자 깊이를 같은 규칙으로 ⑤ hover/active 마이크로 인터랙션(가리킬 수 있는 기기에서만) + prefers-reduced-motion 이면 전부 정지 ⑥ 데스크톱(1180px~) 여백 정돈, 430px 이하 글자 크기 미세 조정. 기능·레이아웃·자료 수치는 변경 없음.
   · z39 (2026-11-22) — 탭 상단 정리: 제목 밑에 줄줄이 붙던 수집 이력·칸 수·주차별 완료 내역을 한 줄 안내로 바꾸고 긴 내역은 접기(⑧ 조회 범위·읽는 법 등)로 옮김. 원천·스냅샷·실측·전수·블록 같은 작업 용어를 사이트·자료·조회·전체·구간으로 정리.
   · z38 (2026-11-22) — ⑧ 달력 칸 글자 잘림 방지(숫자·직항/경유 줄바꿈 없음) + 탭 설명의 수집 구간 표기 정정.
   · z37 (2026-11-22) — ⑧ 외항사 마일리지(부산) 달력·1년 창: 2026-11~2027-11 13개월 격자(날짜 칸에 최저 마일·직항/경유, 월별 최저 마일 띠) + 날짜 칸을 누르면 프로그램별·노선별·등급별 필요 마일·최근 확인·공식 발권 링크가 뜨는 상세 시트. 창은 1년(2026-11-22~2027-11-21)으로 선언하고, 원천 비로그인 화면이 열어 준 2026-11-22~2027-01-21(61일) 밖은 미수집(빗금)으로 표시 — 값 보간 없음.
   · z33 (2026-11-22) — ⑧ 외항사 마일리지(부산) 탭 신설: 에어프랑스 플라잉블루 · GOL 스마일즈 · 버진 애틀랜틱 · 델타 스카이마일즈 · 유나이티드 마일리지플러스 · 에어캐나다 에어로플랜 · 캐세이 아시아 마일즈 · 영국항공 아비오스 · JAL 마일지뱅크 9곳을 부산/김해(PUS) 출발·도착, 앞으로 60일, 이코노미/프리미엄/비즈니스/퍼스트로 나눠 보여 줍니다. 프로그램·동맹·도시·직항 필터, 도시별 최저 마일 요약, 날짜별 목록(마일 낮은순·날짜순), 각 행의 예약 버튼은 프로그램 공식 사이트로 연결. 실측 625건(플라잉블루 66 · 스마일즈 54 · 버진 225 · 델타 252 · 유나이티드 4 · 에어로플랜 24, 아시아마일즈·영국항공·JAL은 원천에 부산 자료 없음) · 자료는 data/app/tab9_partner_mileage.json 지연 로딩, 수집 원본은 tools/partner_tab/raw
   · z32 (2026-11-22) — 🌲 휴양림 전수 재수집(2026-11-22 07:13 KST · 185곳 · 7,460객실·사이트 · 71일 · 예약가능 102,647칸 · 직전 01:43 대비 새로 빈 자리 81칸)과 예약 버튼 수정: 예약 링크를 눌러도 안 열리던 문제를 고쳐 새 탭(window.open)이 막히는 인앱 브라우저·웹뷰에서는 같은 탭으로 이동합니다(데스크톱은 그대로 새 탭).
   · z31 (2026-11-22) — 모바일 탭을 4칸 폴더 그리드로: 390px에서 한 줄 가로 스크롤 대신 ①~④ / ⑤·콤보·⑥ / ⑦·발렛 세 줄에 열 개 탭이 모두 보입니다(좁은 화면 전용 짧은 탭 이름 — ④ 메리어트 · ⑤ 항공 · ⑥ 땡처리 · ⑦ 마일리지 · 🅿️ 발렛). 🔒 잠금 버튼은 통계 줄 아래에서 제목 줄 오른쪽 끝으로 옮겼습니다. 데스크톱 탭 줄과 긴 이름은 그대로.
   · z30 (2026-11-22) — ⑦ 마일리지(부산) 14개 노선 336블록(3·4·5번 수집분 병합) 완결: 부산발 미운항 5개 노선(FUK·HKG·SIN·HAN·SGN)과 하계 미개시 6개 노선(KIX·TAO·NGO·CTS·BKK·DAD 2027-04~11)을 노선 칩·달력·요약에 배지로 표시해 '미수집'과 구분. 왕복 후보는 귀국편(dir 1) 실제 좌석과 날짜로 맞춰 확인/좌석 없음/운항 없음/조회 불가/미수집을 나눠 적고, 귀국편 확인 후보를 앞에 놓음(가는 편의 '운항편 없음'·'좌석 없음'은 후보에서 제외) · 자료 data/mileage/captures/2026-11-22.json 336행, 병합은 tools/merge_mileage.py
   · z29 (2026-11-22) — ⑦ 마일리지(부산) 탭 신설: 부산/김해(PUS) 출발 노선의 날짜별 보너스 좌석(일반석 E · 프레스티지 P · 프레스티지 승급 U)을 노선별 12개월 달력으로 보여 줍니다. 자료는 항공사가 공개하는 보너스 좌석 현황(하루 1회 갱신·앞으로 360일)을 옮긴 스냅샷이고, 좌석 수량·수수료·기재는 원천에 없어 표시하지 않습니다. 왕복 후보·새로 열린 좌석(전일 대비)·마일 계산기(공제표) 포함. 자료는 data/app/tab8_mileage.json 지연 로딩, 수집은 tools/collect_mileage.py
   · z28 (2026-11-22) — 🌲 휴양림 탭 신설: 전국 185곳 자연휴양림의 숙소·야영장 빈자리를 숲나들e 월별 예약현황 스냅샷(2026-11-22 01:43 KST 수집 · 71일 · 7,460객실·사이트 · 예약가능 102,728칸)으로 목록·체크인 달력·월간 그리드에 표시. 권역·객실유형·인원·1~3박·금·토 체크인·새로 빈 자리 필터, 예약 버튼은 모두 숲나들e 공식 화면(휴양림별 페이지·월별현황조회)으로 연결 · 자료는 data/app/tab7_forest.json 지연 로딩(1.3MB)
   · z27 (2026-11-22) — ⑥ 땡처리 3,847건 · 44개 노선 전면 갱신(수집 2026-11-22 04:31~05:40 KST)
   · z26 (2026-11-22) — z25 병합의 문구·표시 후속 수정: ③ 스냅샷 기준(국내·한·중·일 11-16~20 / 동남아 196곳 11-21 20:50~21:25 KST) 현행화, ③ 카드 요금 근거를 「세금 포함 KRW 최저 표시가(ALL 회원 요금 포함 / 6번 39곳은 비회원 공개 최저가)」로 통일, 이중 연결 7곳의 ① 호텔럭스 채널에 그 날짜 VIP 요금 비교 표시, ③ 탭 안내문에 「1박 최저가 ↔ Stay Plus 결제액」 비교 문구
   · z25 (2026-11-22) — ③ 아코르에 동남아 196곳(태국 102·베트남 55·싱가포르 39, a52~a247) 365일 실측 병합. 요금 기준은 세금 포함 KRW 1박 최저 표시가(157곳 ALL 회원 요금 포함 · 6번 담당 39곳은 비회원 공개 최저가). ③ 은 247곳이 되고, ① 호텔럭스에 있는 7곳(페어몬트 방콕 수쿰윗·페어몬트 싱가포르·래플스 싱가포르·래플스 센토사·소피텔 싱가포르 2곳·만다이 by 반얀트리)은 양방향 「💎 호텔럭스 ↔ 🏨 아코르 공홈」 선택 창. ④ 아워드 포인트 모드의 「2.7만P원」 중복 표기 수정. 알림 오탐 차단 보강(첫 관측 호텔·초저가 기준)
   · z24 (2026-11-21) — ④ 메리어트 중국·홍콩·마카오 40곳(m01~m40) 아워드 포인트 12,175칸 병합(2026-11-21 marriott.com 아워드 캘린더 365일 실측, 3곳은 Standard 아워드 연중 전무·전 호텔 2027-11-06~30은 예약창 밖 null) · 「아워드 포인트」 표시 모드·🎟️ 35k/50k 필터·상세 배지가 중국 호텔까지 판단 · 콤보(청두·시안·톈진·광저우 등) 🎫 35k / 🎫 35k(+○k) 배지 · ④ 안내문의 '한·일 22곳·6,629칸' 표기를 실측 기준으로 현행화
   · z23 (2026-11-21) — 예약처 두 곳 창에서 채널별 그 날짜 요금을 버튼마다 나란히(④ 공홈 검색가 ↔ ① VIP 요금 · ① 탭 자료는 필요할 때 한 번 받아 채움, 미조사는 「미실측」) · 이중 예약처 칸으로도 「선택일 호텔 비교」 활성 · 390px 활성 탭 자동 스크롤 · ④ 라벨 메리어트 통일 · USD 표시 '$156 · 환산 전 ₩…', 목록 도시명 중복 제거
   · 앱 셸(index.html·manifest·아이콘)은 미리 저장
   · data/app/*.json · data/history/*.json 은 네트워크 우선(항상 새 값 시도) → 실패하면 저장본
   · 오프라인에서도 마지막으로 본 탭·달력이 열리고, 저장본이 없으면 안내 문구를 보여 준다 */
const VERSION = 'teambusan-v5-2026-11-22z52';
const SHELL = ['./', './index.html', './manifest.json',
  './icons/icon-180.png', './icons/icon-192.png', './icons/icon-512.png', './icons/icon-maskable-512.png'];
/* 오프라인 폴백은 캐시에 마지막으로 저장된 응답을 그대로 쓴다 */

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(VERSION).then(function (cache) {
      return Promise.all(SHELL.map(function (url) {
        return cache.add(new Request(url, { cache: 'reload' })).catch(function () { /* 파일 하나가 없어도 설치를 막지 않는다 */ });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

function isData(url) {
  return url.pathname.indexOf('/data/app/') >= 0 || url.pathname.indexOf('/data/history/') >= 0;
}

function offlineDoc() {
  const html = '<!doctype html><html lang="ko"><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<title>TEAM-부산 — 오프라인</title>'
    + '<body style="margin:0;background:#1b122b;color:#fff;font-family:-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',sans-serif;display:grid;place-items:center;min-height:100vh;padding:24px">'
    + '<div style="max-width:420px;text-align:center">'
    + '<div style="font-size:30px">◈</div><h1 style="font-size:17px;letter-spacing:-.03em">오프라인입니다</h1>'
    + '<p style="font-size:12.5px;line-height:1.7;color:#c4b5fd">한 번 이상 연 탭의 자료는 저장돼 있어 오프라인에서도 열립니다. '
    + '이 화면이 보이면 아직 저장본이 없는 상태입니다 — 연결된 뒤 새로고침하면 탭 자료를 받아 둡니다.</p>'
    + '<p style="font-size:11px;color:#8b86a3">자료는 조회 시점 스냅샷이며 실시간 가격 연결은 없습니다.</p>'
    + '<button onclick="location.reload()" style="margin-top:14px;border:0;border-radius:9px;padding:11px 18px;font-weight:800;background:#ddd6fe;color:#3b1a78">다시 시도</button>'
    + '</div></body></html>';
  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}

function networkFirst(req, event, kind) {
  /* cache:'no-cache' — GitHub Pages 의 HTTP 캐시(max-age=600)를 우회해 새로고침 즉시 최신본을 받는다 */
  return fetch(req, { cache: 'no-cache' }).then(function (res) {
    if (res && res.ok) {
      const copy = res.clone();
      caches.open(VERSION).then(function (cache) { cache.put(req, copy); });
    }
    return res;
  }).catch(function () {
    return caches.match(req).then(function (hit) {
      if (hit) return hit;
      if (kind === 'doc') return offlineDoc();
      return new Response(JSON.stringify({ offline: true, error: 'offline' }),
        { status: 503, headers: { 'Content-Type': 'application/json; charset=utf-8' } });
    });
  });
}

function cacheFirst(req) {
  return caches.match(req).then(function (hit) {
    if (hit) {
      fetch(req).then(function (res) {
        if (res && res.ok) caches.open(VERSION).then(function (c) { c.put(req, res); });
      }).catch(function () {});
      return hit;
    }
    return fetch(req).then(function (res) {
      if (res && res.ok) {
        const copy = res.clone();
        caches.open(VERSION).then(function (c) { c.put(req, copy); });
      }
      return res;
    });
  });
}

self.addEventListener('fetch', function (event) {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (isData(url)) { event.respondWith(networkFirst(req, event, 'json')); return; }
  if (req.mode === 'navigate') { event.respondWith(networkFirst(req, event, 'doc')); return; }
  if (/\.(json|js|css|svg|png|webp|jpg|ico)(\?|$)/.test(url.pathname) || url.pathname.endsWith('/')) {
    event.respondWith(cacheFirst(req)); return;
  }
  event.respondWith(fetch(req).catch(function () { return caches.match(req); }));
});
