# ⑧ 외항사 마일 — 자료 수집·재생성 안내

항공사 마일리지 프로그램 9곳의 **보너스(마일) 좌석**을 부산/김해(PUS)·인천(ICN) **출발편과 귀국편**으로
모아 ⑧ 탭(`#tab=partner-mileage`)에 달력·목록·날짜 상세로 보여 줍니다.

- 화면: `index.html` 의 `<!-- PARTNER:SECTION -->`·`/* PARTNER:CSS */`·`// PARTNER:JS` 블록
  (원본 = `tools/partner_tab/section.html` · `tab.css` · `app.js`)
- 자료: `data/app/tab9_partner_mileage.json` (부산) · `data/app/tab9_partner_mileage_icn.json` (인천)
- 원자료(파이프 텍스트): `tools/partner_tab/raw/`

## 1. 원자료 형식

한 줄 = `날짜|최근확인|상대도시|이코노미|프리미엄|비즈니스|퍼스트`, 레코드 구분은 `;`

| 파일 | 방향 | `상대도시`의 뜻 |
| --- | --- | --- |
| `{슬러그}_dep_PUS.txt` · `{슬러그}_dep_ICN.txt` | 출발(PUS→ · ICN→) | 도착 도시 |
| `{슬러그}_arr_PUS.txt` · `{슬러그}_arr_ICN.txt` | 귀국(→PUS · →ICN) | 출발 도시 |

- 날짜는 `YYYY-MM-DD` 전체 형식(2027년 11월을 2026년으로 잘못 읽지 않게).
- 등급 값은 `-`(표시 없음) 또는 `직항편수-마일` (`0-9000` = 직항 9,000마일, `1-33000` = 1회 경유).
- 슬러그: `flyingblue` `smiles` `virgin` `delta` `united` `aeroplan` `asiamiles` `british` `jal`.
- **국내선(김포 GMP·제주 CJU ↔ 부산 등)은 넣지 않습니다.** 빌더도 한 번 더 걸러 냅니다.
- **값이 없는 (날짜·도시·등급)은 적지 않습니다.** 0건 프로그램은 빈 파일로 남겨 "자료 없음"을 정직하게 표시합니다.
- `flyingblue_dep_PUS.txt` 의 **부산→옌타이(YNT) 42행**은 공홈에서 직접 확인한 값입니다. 자동 수집이 이 조합을
  덮어쓰지 않도록, 자동 갱신은 (날짜·도시) 단위로 **합집합**으로 합칩니다(아래 4번).

## 2. 수집 절차 (매일 04:00 자동 갱신도 같은 순서)

1. `git pull --rebase origin main` — 다른 작업(본계정 쪽 ⑧ 하단 안내 등)과 충돌을 먼저 막습니다.
2. 브라우저 프로필의 **조회 사이트 PRO 로그인 세션**을 확인합니다(계정 메뉴에 `PRO` 표시).
   60일 창에서 365일(전체 연도) 창으로 넓히려면 PRO 로그인이 필요합니다.
3. 프로그램 9곳 × 출발지 2곳 × **방향 2가지 = 36개** 내보내기를 받습니다.
   - 출발편: `/flyingblue/departing/PUS` 처럼 `departing/{PUS|ICN}` 화면에서 「전체 연도」 → CSV 내보내기
   - 귀국편: `/flyingblue/arriving/PUS` 처럼 `arriving/{PUS|ICN}` 화면에서 같은 방식
   - 내보내기 주소는 화면의 CSV 버튼과 같습니다(아래 두 갈래):
     - 출발편 `.../availability_table_modern_ss.csv?...&origin_airport=PUS&destination_airport=&source={슬러그}&giga=true&date_scope=full-year...`
     - 귀국편 `.../availability_table_modern_ss.csv?...&origin_airport=&destination_airport=PUS&source={슬러그}&giga=true&date_scope=full-year...`
   - 저장 파일 이름이 프로그램 이름으로 겹치므로, 받은 CSV를 곧바로 `downloads/arr_{슬러그}_{PUS|ICN}.csv`
     (출발편은 `dep_...`)로 바꿔 두면 섞이지 않습니다.
4. CSV → 원자료 변환
   - 출발편: `python3 work/pus_partner_mileage/s2/convert_pro365.py` (기존 값과 합집합 병합 · YNT 보존)
   - 귀국편: `python3 tools/partner_tab/convert_arr.py` (CSV 폴더는 `PARTNER_CSV_DIR`, 기본 `downloads/`)
     (CSV의 `Origin Airport` = 상대 도시, 국내선 제외, 2026-11-22~2027-11-21 창만)
5. CSV 값 읽는 규칙(화면 10여 건 대조로 확인): `X Miles` = 그 등급 최저 마일,
   `X Direct Seats` 가 채워져 있으면 그 최저가 **직항(0)**, 비어 있으면 **경유(1)**.
   같은 (날짜·도시)에 여러 줄이 있으면 등급별 최저 마일·직항 우선으로 하나로 정리합니다.
6. 빌드·검증·배포
   ```
   python3 tools/build_partner_tab.py      # JSON 2개 + index.html 블록 재생성
   python3 tools/master_db.py verify       # VERIFY OK 확인
   ```
   `sw.js` 의 `VERSION`(z숫자)과 `DATA_BUST['partner-mileage']` 값을 함께 올린 뒤
   `git pull --rebase origin main` → `git push` → GitHub Pages `built` 확인.

## 3. 화면 연결 요약

- 상단 **출발지**(부산 PUS / 인천 ICN) × **방향**(`부산 출발 PUS→` / `부산 도착 →PUS`, `인천 출발 ICN→` / `인천 도착 →ICN`)
  버튼 하나로 달력·목록·도시 칩·월별 최저 띠·KPI·날짜 상세 시트가 함께 바뀝니다(자료는 출발지별로 한 번만 받아 보관).
- 자료 행의 9번째 칸(인덱스 8)이 방향입니다 — `0` = 출발, `1` = 귀국. 기존 스키마와 같습니다.
- 날짜 상세 시트(`#pmSheet`) 맨 위의 **「↔ 왕복 짝 — 같은 날 반대 방향」** 은 같은 날짜의 반대 방향 최저 마일을
  보여 주고, 버튼을 누르면 방향을 바꿔 같은 날짜를 다시 엽니다(출발 → 귀국 왕복 확인).
- 미수집 구간은 값이 아니라 `미수집`으로 그립니다(보간·추정 없음).

## 4. 하지 말 것

- 조회 사이트·수집기 이름을 `index.html`·`sw.js`·`data/app/*.json`·`tools/partner_tab/*` 화면 문구에 노출하지 않습니다
  (화면 문구는 「조회 사이트」로 씁니다).
- 원자료에 없는 값을 추정해 채우지 않습니다. 0건은 0건으로 적습니다.
- `tools/partner_tab/*` 를 고칠 때는 `index.html` 의 해당 블록도 같은 내용으로 맞춥니다(빌드가 블록을 통째로 바꿔 끼우므로,
  원본만 고치면 다음 빌드에서 화면이 되돌아갑니다).
