#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 2차 4곳 병합 — tools/master_db.py 의 EXPECT_IHG 기대치를 259곳으로 올린다."""
import io
import sys

PATH = 'tools/master_db.py'
src = io.open(PATH, encoding='utf-8').read()

old_line = "EXPECT_IHG = {'hotels': 255, 'cells': 93075, 'cash': 81720, 'points': 78878}"
new_line = "EXPECT_IHG = {'hotels': 259, 'cells': 94535, 'cash': 82966, 'points': 79855}"
assert src.count(old_line) == 1, src.count(old_line)
src = src.replace(old_line, new_line)

old_c = ('#   MEXVC 는 2026년 12월 리워드 재고가 5일(12-06 · 12-13 · 12-16 · 12-23 · 12-30)뿐이다.\n')
new_c = old_c + (
    '#   2026-11-26 중남미 2차 4곳(CUNHC · CUNCN · SAOHA · BUEHA = 칸쿤 2 · 상파울루 · 부에노스아이레스)을\n'
    '#   더해 259곳 · 북미·중남미 65 — 1,460칸(현금 1,246 · 포인트 977)을 더한 수 · 259 × 365 = 94,535칸.\n'
    '#   브라질 · 아르헨티나는 ⑤ IHG 의 첫 지점(미국 52 · 캐나다 5 · 멕시코 6 · 브라질 1 · 아르헨티나 1).\n'
    '#   CUNHC 는 1박 12 USD Amenity Fee 별도(세후가 미포함)이고, CUNCN 은 옛 Real Inn 칸쿤을 voco 로\n'
    '#   리브랜딩한 개관 초기 호텔이라 현금이 2027-02-15부터 268일 단일가(259,600원)만 열리고 리워드\n'
    '#   포인트는 365일 전부 null(0칸)이다 — check_ihg 는 0칸을 결측으로 보지 않는다.\n'
    '#   SAOHA 는 전면 리노베이션(로비·레스토랑·풀 임시 휴업) 공지, BUEHA 는 1인 1박 1.5 USD Amenity\n'
    '#   Fee 별도다. ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조해 겹침 0곳(alsoIn 9쌍 그대로).\n'
)
if src.count(old_c) == 1:
    src = src.replace(old_c, new_c)
else:
    print('!! 주석 앵커 매치 %d회 — 주석은 건너뜀' % src.count(old_c))

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('master_db.py EXPECT_IHG 갱신 — 259곳 / 94,535칸 / 현금 82,966 · 포인트 79,855')
