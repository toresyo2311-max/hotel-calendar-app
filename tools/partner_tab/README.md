# 외항사 마일리지 9개 프로그램 — 자료 수집·재생성 안내

항공사 마일리지 프로그램 9곳의 **보너스(마일) 좌석**을 부산/김해(PUS)·인천(ICN) **출발편과 귀국편**으로
모아 **⑧ 마일리지발권 탭**(`#tab=mileage`)에 달력·목록·날짜 상세로 보여 줍니다.

> 2026-11-22 통합: ⑨ 외항사 마일 탭은 없어졌습니다. 대한항공(스카이패스)과 **같은 달력·같은 날짜 시트**에서
> 보도록 ⑧ 마일리지발권 하나로 합쳤습니다. 화면 원본은 `tools/mileage_tab/`(section.html · tab.css · app.js)에 있고,
> 이 폴더에는 **자료 수집·변환**만 남아 있습니다.

- 자료: `data/app/tab9_partner_mileage.json` (부산) · `data/app/tab9_partner_mileage_icn.json` (인천)
- 원자료(파이프 텍스트): `tools/partner_tab/raw/`
- 화면 블록: `python3 tools/build_partner_tab.py` 가 JSON 을 만든 뒤 `tools/build_mileage_tab.py` 를 불러 다시 채웁니다.

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

1. `git pull --rebase origin main` — 다른 작업과 충돌을 먼저 막습니다.
2. 브라우저 프로필의 **조회 사이트 PRO 로그인 세션**을 확인합니다(계정 메뉴에 `PRO` 표시).
3. 프로그램 9곳 × 출발지 2곳 × **방향 2가지 = 36개** 내보내기를 받습니다.
   - 출발편: `/flyingblue/departing/PUS` 처럼 `departing/{PUS|ICN}` 화면에서 「전체 연도」 → CSV 내보내기
   - 귀국편: `/flyingblue/arriving/PUS` 처럼 `arriving/{PUS|ICN}` 화면에서 같은 방식
   - 저장 파일 이름이 프로그램 이름으로 겹치므로, 받은 CSV를 곧바로 `downloads/arr_{슬러그}_{PUS|ICN}.csv`
     (출발편은 `dep_...`)로 바꿔 두면 섞이지 않습니다.
4. CSV → 원자료 변환
   - 출발편: `python3 work/pus_partner_mileage/s2/convert_pro365.py` (기존 값과 합집합 병합 · YNT 보존)
   - 귀국편: `python3 tools/partner_tab/convert_arr.py` (CSV 폴더는 `PARTNER_CSV_DIR`, 기본 `downloads/`)
5. CSV 값 읽는 규칙(화면 10여 건 대조로 확인): `X Miles` = 그 등급 최저 마일,
   `X Direct Seats` 가 채워져 있으면 그 최저가 **직항(0)**, 비어 있으면 **경유(1)**.
6. 빌드·검증·배포
   ```
   python3 tools/build_partner_tab.py      # JSON 2개 + ⑧ 마일리지발권 탭 블록 재생성
   python3 tools/master_db.py verify       # VERIFY OK 확인
   ```
   `sw.js` 의 `VERSION`(z숫자)을 올린 뒤 `git pull --rebase origin main` → `git push` → GitHub Pages `built` 확인.

## 2-1. 매일 04:00 자동 갱신이 실제로 쓰는 길 (2026-11-23 추가)

```
# 36개 화면(9프로그램 × 출발·도착 × PUS·ICN)에서 「. CSV」를 눌러 내려받은 뒤
python3 tools/partner_tab/grab_csv.py {dep|arr} {슬러그} {PUS|ICN}   # 방금 받은 CSV → downloads/collect/
python3 tools/partner_tab/refresh_from_csv.py                        # collect/ → raw/*.txt
python3 tools/build_partner_tab.py --json-only                       # raw/ → JSON 2개 (화면 블록은 그대로)
```

- `grab_csv.py` 는 파일 이름이 프로그램마다 같아 겹치므로 CSV 안의 `Mileage Program`·출발/도착 공항 값으로
  확인한 뒤에만 옮긴다. 내려받기가 늦게 끝나면 몇 초 뒤 다시 부르면 된다.
- `refresh_from_csv.py` 는 그날 CSV 에 없는 (날짜,도시) 를 버려서 팔린 좌석이 남지 않게 하고,
  공항 홈페이지 실측분(`flyingblue` 부산 YNT·NKG, `delta` 부산 NKG)만 보존한다(스크립트 안 `PRESERVE`).
- **`--json-only` 없이 빌더를 돌리면** ⑧ 탭의 💎 마일리지 가치·구매가 비교표(`mlv`)가 지워진다 —
  그 블록은 아직 `tools/mileage_tab/section.html` 에 없고 index.html 에만 있다.
- 조회 사이트에서 0건인 화면(asiamiles·british·jal 의 부산 등)은 CSV 를 받지 않고 원자료를 빈 파일로 둔다.

## 3. 화면 연결 요약

- ⑧ 마일리지발권 탭의 **출발지**(부산 PUS / 인천 ICN) × **방향**(`부산 출발 PUS→` / `부산 도착 →PUS`, `인천 출발 ICN→` / `인천 도착 →ICN`)
  버튼 하나로 달력·목록·도시 칩·월별 최저 띠·KPI·날짜 상세 시트가 함께 바뀝니다(자료는 출발지별로 한 번만 받아 보관).
- 대한항공은 **부산(PUS) 전용**입니다. 인천을 고르면 외항사만 보이고 그 사실을 화면에 적습니다.
- 자료 행의 9번째 칸(인덱스 8)이 방향입니다 — `0` = 출발, `1` = 귀국.
- 날짜 상세 시트에서 같은 도시의 **대한항공 행과 외항사 행이 한 상자에** 나옵니다. 시트 맨 위의
  **「↔ 왕복 짝 — 같은 날 반대 방향」** 은 반대 방향 최저 마일을 보여 주고 방향을 바꿔 같은 날짜를 다시 엽니다.
- 미수집 구간은 값이 아니라 `미수집`으로 그립니다(보간·추정 없음).

## 4. 하지 말 것

- 조회 사이트·수집기 이름을 `index.html`·`sw.js`·`data/app/*.json`·`tools/*` 화면 문구에 노출하지 않습니다(화면 문구는 「조회 사이트」).
- 원자료에 없는 값을 추정해 채우지 않습니다. 0건은 0건으로 적습니다.
- **⑨ 외항사 마일 탭을 다시 만들지 않습니다** — 화면은 `tools/mileage_tab/` 하나입니다.
