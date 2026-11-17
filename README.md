# 🏨 호텔 요금 달력 웹앱 (hotel-calendar-app)

> **바로 열기: https://hotel-calendar-app.netlify.app**
> Netlify가 이 저장소 `main` 브랜치를 보고 있어서, push하면 몇 초 안에 사이트가 자동으로 갱신됩니다.

**176개 호텔**의 **2026-12-01 ~ 2027-11-30 (365일)** 최저가와 부산 출발 항공 특가 288건을
한 화면에서 보는 달력 웹앱입니다. ① HoteLux VIP 탭은 **이때다 ITTAEDA(ittaeda.com)** 가
날짜별로 수집한 HoteLux VIP 요금 138곳을 새로 담았습니다(2026-11-17 수집).
서버·로그인·DB가 필요 없는 **정적 HTML 한 장**이라 GitHub에 올린 뒤 Netlify로 자동 배포하면
링크 하나로 계속 열어볼 수 있습니다.

## 탭 구성 (4개)

| 탭 | 이름 | 내용 | 건수 |
| --- | --- | --- | --- |
| ① | HoteLux VIP · FHR | 이때다 HoteLux VIP 138곳 신규 + 기존 24곳 (서울·부산·도쿄·싱가포르·시드니·뉴욕·상하이·후쿠오카·오사카·방콕·다낭·나트랑) | 162곳 |
| ② | 중올플 · ALL PLUS China | 중국·마카오·홍콩 소피텔·풀만·뫼벤픽·AKI | 10곳 |
| ③ | 국내 아코르 · Stay Plus | 머큐어 울산, 이비스 전주, 소피텔·페어몬트 서울 | 4곳 |
| ④ | 항공 특가 · 부산 출발 | 부산(PUS) 출발 24개 노선 × 5개 출발 패턴, 2026.12~2027.02 (설 연휴 2/4~8 포함) | 24노선 288건 |

## 수록 범위

| 탭 | 호텔 | 날짜 칸 | 요금 표기 | `NA` |
| --- | --- | --- | --- | --- |
| ① HoteLux VIP · FHR | 162곳 (이때다 HoteLux VIP 142곳 중 기존과 겹친 4곳 제외 138곳 + 기존 24곳: 부산 3·상하이 4·후쿠오카 2·오사카 2·도쿄 2·방콕 5·다낭 3·나트랑 3) | 59,130 | 40,458 | 18,672 |
| ② 중올플 | 10곳 (소피텔 8·뫼벤픽 1·AKI 홍콩 1) | 3,650 | 3,650 | 0 |
| ③ 국내 아코르 | 4곳 | 1,460 | 515 | 945 |
| **합계** | **176곳 × 365일** | **64,240칸** | **44,623칸** | **19,617칸** |

### ① 이때다 ITTAEDA HoteLux VIP 반영 내역 (2026-11-17)

- 원본: `https://ittaeda.com/` 의 `/api/meta`(호텔 191곳 메타) + `/api/table`(날짜 범위·페이지네이션)
  + `/api/fx`(환율). 수집 스냅샷은 워크스페이스 `ittaeda-hotelux-vip.json`(4.3MB)에 그대로 보관.
- 요금이 공개된 **142곳**을 ① 탭에 넣고, 기존 24곳과 이름이 겹치는 **파크 하얏트 부산·시그니엘 부산·
  콘래드 도쿄·페어몬트 도쿄 4곳은 실제 HoteLux VIP 요금으로 교체**했습니다. 그 4곳 중 이때다에
  없는 날짜(2027-10-08~11-30)만 기존 Google 값을 유지하고 출처에 그렇게 적었습니다.
- 이때다에 없는 나머지 20곳(상하이·후쿠오카·오사카·방콕·다낭·나트랑)은 **기존 Google 조사값을 그대로**
  두고 `source`를 `Google 호텔(이때다 미수록)`으로 구분 표기했습니다.
- 금액: 체크인 1박 · 성인 2인 1실 · **세금 포함 표시가**. 해외 호텔은 사이트의 USD 표시가를
  **USD 1 = ₩1,336.02**(2026-11-17 이때다 고시 환율)로 환산해 100원 단위 반올림했습니다.
- 요금 공개 구간: **2026-12-01 ~ 2027-10-07** (2027-08부터 공개 호텔 감소 → 9월 778건, 10월 7건).
  그 이후는 `null`(`NA`)입니다.
- 호텔별 `promotion`에는 이때다가 표기한 프로모션(예: `15% OFF(예약~2026-12-08 · 숙박~2027-04-30)`),
  대표 요율명, 조식·환불 여부(라이브 조회분만)를 요약해 넣었습니다.
- 등록 191곳 중 요금 미공개 49곳은 앱에 넣지 않았습니다(원본 JSON의 `not_priced_hotels` 참고).

③ 국내 아코르에는 Stay Plus 무료숙박권 사용 가능일(`stayplus2` = 2박, `stayplus3` = 3박)이
호텔별로 함께 들어 있습니다: **총 142건** (소피텔 서울 12건, 페어몬트 서울 130건).

## ④ 부산 출발 항공 특가 탭

호텔 달력과 별개로, 부산(PUS) 출발 **24개 노선 × 주말 5패턴 = 288건** 항공권 최저가를 담습니다.
성인 1인 왕복 총액(유류·세금 포함), 2026-11-17 12:17~17:00 KST 트립닷컴 실측 스냅샷이며
출발일은 **2026년 12월 ~ 2027년 2월**(설 연휴 2/4~8 포함)입니다. 달력 뷰(월 이동 ‹ 2026년 12월 › 
2027년 1월 › 2027년 2월), 24×5 도표 뷰(주차 선택), 노선·패턴 필터, 상세(그 출발일 최저가·항공사·직항/경유)를
제공합니다.

노선: 후쿠오카(FUK) · 오사카(KIX) · 도쿄(TYO) · 타이베이(TPE) · 홍콩(HKG) ·
마카오(MFM, 직항 없음·전부 경유) · 상하이(PVG) · 방콕(BKK) · 다낭(DAD) · 나트랑(CXR) ·
난징(NKG) · 호찌민(SGN) · 싱가포르(SIN) · 괌(GUM) · 나고야(NGO) · 오키나와(OKA) ·
항저우(HGH) · 칭다오(TAO) · 하노이(HAN) · 치앙마이(CNX) · 발리(DPS) · 가오슝(KHH) ·
타이중(RMQ) · 베이징(BJS)

24개 노선 × 13주 × 5패턴 = 1,560칸 중 실측 288칸입니다. 빈칸(—)은 값이 없는 것이 아니라
**조회하지 않은 것**입니다(1월 12개 노선, 2월 2~4주차는 후쿠오카 제외 미조사).

## 파일 구성

```
index.html              앱 본체. 화면 + 데이터(const DB, const FLIGHTS)가 한 파일에 들어 있습니다.
data/master_db.json     통합 마스터 DB. 호텔 176곳 × 365일 + 항공 특가 288건의 단일 원본.
tools/master_db.py      마스터 DB 추출·검증·주입 도구 (표준 라이브러리만 사용).
netlify.toml            Netlify 배포 설정 (빌드 없음, 루트를 그대로 게시).
```

### data/master_db.json 구조

```json
{
  "schema": "hotel-calendar-app/master-db",
  "version": 1,
  "generated_at": "…KST",
  "source": { "file": "index.html", "commit": "…", "tool": "tools/master_db.py extract" },
  "window": { "start": "2026-12-01", "end": "2027-11-30", "days": 365 },
  "built": "2026-11-17",
  "voucherExpiry": "2027-09-30",
  "extended": "2026-11-17 11:25~12:05 KST (2·3·4번 계정 연장 조사)",
  "counts": { "hotels": 176, "tabs": { "lux": 162, "china": 10, "domestic": 4 },
              "cells": 64240, "priced": 44623, "na": 19617,
              "stayplus": 142, "routes": 24, "deals": 288 },
  "sources":  ["…조사 원문 파일명…"],
  "hotels":   [ // index.html 의 const DB.hotels 와 같은 순서·같은 구조
    {
      "id": "h01", "group": "lux", "city": "부산", "region": "부산",
      "name": "파라다이스 호텔 부산", "english": "Paradise Hotel Busan",
      "promotion": "…", "source": "…", "vip": 1, "ittaeda_id": "…",
      "rates": { "2026-12-01": 240000, "2026-12-02": 236000, "…": null },
      "stayplus2": { "…": 0 },   // ③ 국내 아코르 일부만
      "stayplus3": { "…": 0 }    // ③ 국내 아코르 일부만
    }
  ],
  "flights": {
    "patterns": [ { "label": "금~일", "nights": 2 }, …5개… ],
    "months": [ "2026-12", "2027-01", "2027-02" ],
    "weeks": [ { "thu": "2026-12-17", "month": "2026-12", "label": "12월 3주", "span": "12/17~12/21" }, …13개… ],
    "counts": { "total": 288, "byMonth": { "2026-12": 186, "2027-01": 53, "2027-02": 49 }, "holiday": 34 },
    "routes": [ { "code": "FUK", "city": "후쿠오카", "extra": "",
                  "deals": [ { "date": "2026-12-18", "back": "2026-12-20", "pattern": "금~일",
                               "price": 325400, "airline": "이스타항공", "via": false }, … ] } ]
  }
}
```

- `rates`는 365일 전부 키가 있고, 값이 `null`이면 `NA`(조사 시점에 요금 미공개·예약 미오픈)입니다.
- `flights.routes[].deals[]`의 `via`는 `false`=직항, `true`=경유, `null`=직항/경유 미확인입니다.
  `airline`이 없으면 항공사 미확인(트립닷컴 가격표 값)이고 `src`에 `가격표`/`캘린더`가 붙습니다.
  `alt`는 그 줄에 적힌 직항 대안 금액, `note`는 경유지·소요시간 메모입니다.
- `flights.weeks`가 도표의 주차 단위입니다. `thu`(그 주 목요일)에서 5패턴 출발일을 계산합니다.
- `blackouts`(중올플 블랙아웃 날짜), `code`(아코르 호텔 코드)는 해당 호텔에만 있습니다.
- `vip: 1` + `ittaeda_id`(이때다 호텔 ObjectId) + `brand`는 이때다 반영 호텔에만 있습니다.
- `hotels` 순서는 화면 탭 순서(① 24곳 → ② 10곳 → ③ 4곳)와 같습니다.

## 검증과 갱신 절차

`tools/master_db.py` 하나로 마스터 DB와 라이브 앱의 일치 여부를 확인합니다.

```bash
python3 tools/master_db.py verify    # data/master_db.json == index.html 인지 검사
python3 tools/master_db.py stats     # 수록 범위·호텔별 요금 표기 칸수 출력
python3 tools/master_db.py extract   # index.html -> data/master_db.json 재생성
python3 tools/master_db.py inject    # data/master_db.json -> index.html (DB·FLIGHTS만 교체)
```

정상일 때 `verify` 출력:

```
VERIFY OK — master_db.json == index.html
  hotels 176  tabs {'lux': 162, 'china': 10, 'domestic': 4}
  cells 64240  priced 44623  na 19617  stayplus 142
  routes 24  deals 288  window 2026-12-01~2027-11-30
```

### 새 조사 결과를 넣는 순서

1. 조사 원문(md/pdf)에서 뽑은 요금을 **`data/master_db.json`의 해당 호텔 `rates`(과 필요하면
   `stayplus2`/`stayplus3`)에만** 반영합니다. 값이 없는 날은 `null`로 둡니다.
2. `counts`(요금 표기 칸수 등)와 `built`·`extended`·`sources`를 실제 값으로 고칩니다.
3. `python3 tools/master_db.py inject` — index.html의 `const DB`/`const FLIGHTS`만 다시 채웁니다.
   디자인·스크립트·탭 구조는 그대로이고, 자동 검증이 실패하면 원본으로 되돌립니다.
4. `python3 tools/master_db.py verify` 로 확인한 뒤 commit → push 합니다.

`index.html`을 직접 손으로 고치지 마세요. 손으로 고쳤다면 `extract`로 마스터 DB를 다시 뜬 뒤
`git diff data/master_db.json` 으로 무엇이 바뀐지 확인하는 편이 안전합니다.

### 이전 파일 정리

- `data/parsed_rates.json`(2027-03~11 9개월 부분본, 9,712칸)은 **`data/master_db.json`에 완전히
  포함되어 삭제**했습니다. 두 파일이 서로 다른 시점을 담아 혼동을 만들던 문제를 없앴습니다.
  필요하면 `git show 34c41da:data/parsed_rates.json` 으로 꺼낼 수 있습니다.
- 앱은 여전히 `data/*.json`을 읽지 않습니다. 서버 없이 `index.html` 한 장으로 동작하며,
  마스터 DB는 **유실 방지용 원본 + 재빌드 기준**입니다.

## 유의사항

- 이때다 HoteLux VIP 반영 142곳은 **2027-10-07 이후 전부 `NA`** 입니다(사이트 요금 공개 한계).
  기존 24곳 중 이때다 미수록 20곳은 Google 달력 상한(2027-10-13) 이후 대부분 `NA`입니다.
- 이때다 요금은 사이트가 매일 다시 수집하는 값이라, 다음 반영 때는 같은 절차로 새 스냅샷을 떠서
  `rates_krw`만 갈아끼우면 됩니다.
- 소피텔·페어몬트 서울은 Stay Plus 만료(2027-09-30)로 10~11월은 일반 회원가만 표시됩니다.
- 이비스 스타일 앰배서더 전주는 2027년 요금이 아직 열리지 않아 대부분 `NA`입니다.
- 항공 특가는 2026-11-17 12:17~17:00 KST 스냅샷이라 좌석·가격이 이후 바뀔 수 있습니다.
  항공 데이터의 빈칸(—)은 미조회이며, 항공사 미확인 줄은 트립닷컴 가격표(운임 캘린더) 값입니다.
- 요금은 조사 시점의 1박 최저가이며, 세금·봉사료 포함 여부는 각 조사 원문 기준입니다.
  실제 예약 전에는 해당 호텔 공식 채널에서 다시 확인하세요.

## 배포

Netlify 프로젝트 `hotel-calendar-app` (Team-Jin)이 이 저장소의 `main` 브랜치와 연결돼 있습니다.
`netlify.toml` 설정대로 **빌드 없이 루트 디렉터리**를 게시하며, `index.html`이 루트에 있어
사이트 최상위 주소(https://hotel-calendar-app.netlify.app)에서 바로 앱이 열립니다.

```
변경 → commit → git push origin main → Netlify 자동 빌드·배포 (약 10초)
```

비공개(private) 저장소로 운영할 경우 Netlify 쪽에서 이 저장소에 대한 GitHub 접근 권한을
한 번 허용해야 합니다.
