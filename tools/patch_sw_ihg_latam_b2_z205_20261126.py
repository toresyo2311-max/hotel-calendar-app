#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 2차 4곳 병합 — sw.js 캐시 버전 z205(직전 z204 다음) + 버전 이력 추가."""
import io

SW = 'sw.js'
sw = io.open(SW, encoding='utf-8').read()

ENTRY = (
    '   · z205 (2026-11-26) — **⑤ IHG에 중남미 2차 4곳을 병합**(i256~i259 · 255→259곳 · 북미·중남미 65) — '
    'No.7(@no_7)이 공홈에서 직접 실측해 보낸 2026-12-01~2027-11-30 365일본(2026-11-26 조회)을 더했습니다. '
    '4 × 365 = **1,460칸 가운데 현금 1,246칸 · 포인트 977칸**에 값이 있고, 값 없는 칸은 보간 없이 — 입니다. '
    '**인터컨티넨탈 프레시덴테 칸쿤 리조트**(CUNHC · 336/336) · **보코 칸쿤 소나 호텔레라**(CUNCN · 268/0) · '
    '**인터컨티넨탈 상파울루**(SAOHA · 344/343) · **인터컨티넨탈 부에노스아이레스**(BUEHA · 298/298)이며, '
    '**브라질 · 아르헨티나는 이 탭의 첫 지점**입니다. CUNHC는 요금카드에 「Excludes 12 USD Amenity Fee per '
    'night」가 병기돼 **1박 12 USD 어메니티 피가 세후가에 미포함**이고(2026-12-23~24 · 12-28~2027-01-02 '
    '여드레는 연말연시 재고 없음 · 12-26·12-27 1.2M·1.3M), CUNCN은 옛 Real Inn 칸쿤(160실)을 voco로 '
    '리브랜딩한 개관 초기 호텔이라 **2027-02-15부터 현금만 268일 단일가 259,600원**으로 열리고 '
    '**리워드 포인트는 365일 전부 없음(미출시)**이며, SAOHA는 **전면 리노베이션**(lobby · restaurants · '
    'pool 임시 휴업) 공지가 상세 페이지에 있고, BUEHA는 「Excludes 1.5 USD Amenity Fee per guest per '
    'night」로 **1인 1박 1.5 USD가 별도**입니다. 네 곳 모두 마지막 값 있는 날이 2027-11-09이고 '
    '2027-11-10~11-30은 예약창 밖입니다. ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조해 '
    '**겹침 0곳**(alsoIn 9쌍 그대로 · IHG 공홈 단일 링크). 탭 배지·지역 칩·제목·요약·TAB_SHORT·순위 힌트·'
    '조회 시각·주의문·자료 기준·README 를 **259 / 북미·중남미 65 / 94,535칸(현금 82,966 · 포인트 79,855)** '
    '로 맞췄고, `tools/master_db.py` 의 EXPECT_IHG 기대치도 함께 올렸습니다.\n'
)

old_head = '서비스 워커 (2026-11-26 z204 · ⑤ IHG 중남미 1차 4곳 병합('
new_head = ('서비스 워커 (2026-11-26 z205 · ⑤ IHG 중남미 2차 4곳 병합(255→259곳 · 북미·중남미 65 · '
            '현금 1,246 + 포인트 977칸 · ① 호텔럭스 겹침 0곳 · 칸쿤 2 · 브라질·아르헨티나 첫 지점 · '
            'CUNHC 12 USD 어메니티 피 별도 · CUNCN 리워드 미출시) · z204 · ⑤ IHG 중남미 1차 4곳 병합(')
assert sw.count(old_head) == 1, sw.count(old_head)
sw = sw.replace(old_head, new_head)

anchor = '\n   · z204 (2026-11-26) — **⑤ IHG에 중남미 1차 4곳을 병합**'
assert sw.count(anchor) == 1, sw.count(anchor)
sw = sw.replace(anchor, '\n' + ENTRY + '   · z204 (2026-11-26) — **⑤ IHG에 중남미 1차 4곳을 병합**')

old_ver = "const VERSION = 'teambusan-v5-2026-11-26z204';"
assert sw.count(old_ver) == 1, sw.count(old_ver)
sw = sw.replace(old_ver, "const VERSION = 'teambusan-v5-2026-11-26z205';")

io.open(SW, 'w', encoding='utf-8', newline='').write(sw)
print('sw.js 갱신 — z205')
