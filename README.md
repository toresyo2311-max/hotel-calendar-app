# 🏨 호텔 요금 달력 웹앱 (hotel-calendar-app)

> **바로 열기: https://hotel-calendar-app.netlify.app**
> Netlify가 이 저장소 `main` 브랜치를 보고 있어서, push하면 몇 초 안에 사이트가 자동으로 갱신됩니다.

38개 호텔의 **2026-12-01 ~ 2027-11-30 (365일)** 최저가와 부산 출발 항공 특가 50건을
한 화면에서 보는 달력 웹앱입니다. 서버·로그인·DB가 필요 없는 **정적 HTML 한 장**이라
GitHub에 올린 뒤 Netlify로 자동 배포하면 링크 하나로 계속 열어볼 수 있습니다.

## 탭 구성 (4개)

| 탭 | 이름 | 내용 | 건수 |
| --- | --- | --- | --- |
| ① | HoteLux · FHR | 부산·상하이·일본·방콕·다낭·나트랑 럭셔리 24곳 | 24곳 |
| ② | 중올플 · ALL PLUS China | 중국·마카오·홍콩 소피텔·풀만·뫼벤픽·AKI | 10곳 |
| ③ | 국내 아코르 · Stay Plus | 머큐어 울산, 이비스 전주, 소피텔·페어몬트 서울 | 4곳 |
| ④ | 항공 특가 · 부산 출발 | 부산(PUS) 출발 10개 노선 × 5개 출발 패턴 | 10노선 50건 |

## 수록 범위

| 탭 | 호텔 | 날짜 칸 | 요금 표기 | `NA` |
| --- | --- | --- | --- | --- |
| ① HoteLux · FHR | 24곳 (파라다이스·파크 하얏트·시그니엘 부산, 페어몬트 피스·푸동 샹그릴라·콘래드·세인트 레지스 상하이, 후쿠오카 2·오사카 2·도쿄 2, 방콕 5, 다낭·나트랑 6) | 8,760 | 6,909 | 1,851 |
| ② 중올플 | 10곳 (소피텔 8·뫼벤픽 1·AKI 홍콩 1) | 3,650 | 3,650 | 0 |
| ③ 국내 아코르 | 4곳 | 1,460 | 515 | 945 |
| **합계** | **38곳 × 365일** | **13,870칸** | **11,074칸** | **2,796칸** |

③ 국내 아코르에는 Stay Plus 무료숙박권 사용 가능일(`stayplus2` = 2박, `stayplus3` = 3박)이
호텔별로 함께 들어 있습니다: **총 142건** (소피텔 서울 12건, 페어몬트 서울 130건).

## ④ 부산 출발 항공 특가 탭

호텔 달력과 별개로, 부산(PUS) 출발 **10개 노선 × 주말 5패턴 = 50건** 항공권 최저가를 담습니다.
성인 1인 왕복 총액(유류·세금 포함), 2026-11-17 12:17~12:50 KST 트립닷컴 실측 스냅샷이며
출발일은 2026-12-17(목)·12-18(금)·12-19(토)입니다. 달력 뷰(12월)와 10×5 도표 뷰,
노선·패턴 필터, 상세(그 출발일 최저가 행 강조)를 제공합니다.

노선: 후쿠오카(FUK) · 오사카(KIX) · 도쿄(TYO) · 타이베이(TPE) · 홍콩(HKG) ·
마카오(MFM, 직항 없음·전부 경유) · 상하이(PVG) · 방콕(BKK) · 다낭(DAD) · 나트랑(CXR)

## 파일 구성

```
index.html              앱 본체. 화면 + 데이터(const DB, const FLIGHTS)가 한 파일에 들어 있습니다.
data/master_db.json     통합 마스터 DB. 호텔 38곳 × 365일 + 항공 특가 50건의 단일 원본.
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
  "counts": { "hotels": 38, "tabs": { "lux": 24, "china": 10, "domestic": 4 },
              "cells": 13870, "priced": 11074, "na": 2796,
              "stayplus": 142, "routes": 10, "deals": 50 },
  "sources":  ["…조사 원문 파일명…"],
  "hotels":   [ // index.html 의 const DB.hotels 와 같은 순서·같은 구조
    {
      "id": "h01", "group": "lux", "city": "부산", "region": "부산",
      "name": "파라다이스 호텔 부산", "english": "Paradise Hotel Busan",
      "promotion": "…", "source": "…",
      "rates": { "2026-12-01": 240000, "2026-12-02": 236000, "…": null },
      "stayplus2": { "…": 0 },   // ③ 국내 아코르 일부만
      "stayplus3": { "…": 0 }    // ③ 국내 아코르 일부만
    }
  ],
  "flights": { "patterns": [ …5개… ], "routes": [ { "code": "FUK", "city": "후쿠오카", "deals": [ …5건… ] } ] }
}
```

- `rates`는 365일 전부 키가 있고, 값이 `null`이면 `NA`(조사 시점에 요금 미공개·예약 미오픈)입니다.
- `blackouts`(중올플 블랙아웃 날짜), `code`(아코르 호텔 코드)는 해당 호텔에만 있습니다.
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
  hotels 38  tabs {'lux': 24, 'china': 10, 'domestic': 4}
  cells 13870  priced 11074  na 2796  stayplus 142
  routes 10  deals 50  window 2026-12-01~2027-11-30
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

- HoteLux·FHR 24곳은 Google 달력 상한(2027-10-13) 이후 대부분 `NA`입니다.
- 소피텔·페어몬트 서울은 Stay Plus 만료(2027-09-30)로 10~11월은 일반 회원가만 표시됩니다.
- 이비스 스타일 앰배서더 전주는 2027년 요금이 아직 열리지 않아 대부분 `NA`입니다.
- 항공 특가는 2026-11-17 12:17~12:50 KST 스냅샷이라 좌석·가격이 이후 바뀔 수 있습니다.
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
