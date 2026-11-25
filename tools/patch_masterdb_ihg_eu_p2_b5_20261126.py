#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P2 5차(마지막) 3곳 병합 — tools/master_db.py 의 EXPECT_IHG 기대치를 251곳으로 올린다."""
import io
import sys

PATH = 'tools/master_db.py'
src = io.open(PATH, encoding='utf-8').read()
reps = []

reps.append((
    "#   이스탄불 4). HELMH 는 크라운 플라자 헬싱키 - 헤스페리아이고 호텔 인디고 헬싱키(HELIN)와 다른 호텔.\n"
    "EXPECT_IHG = {'hotels': 248, 'cells': 90520, 'cash': 79682, 'points': 77151}",
    "#   이스탄불 4). HELMH 는 크라운 플라자 헬싱키 - 헤스페리아이고 호텔 인디고 헬싱키(HELIN)와 다른 호텔.\n"
    "#   2026-11-26 유럽 P2 5차(마지막) 3곳(NAVNC · WAWFN · REKRR = 튀르키예 · 폴란드 · 아이슬란드)을\n"
    "#   더해 251곳 · 유럽 74 — 1,095칸(현금 681 · 포인트 502)을 더한 수 · 251 × 365 = 91,615칸.\n"
    "#   폴란드 · 아이슬란드는 ⑤ IHG 유럽의 첫 지점이라 유럽이 20개국이 됐다. 튀르키예는\n"
    "#   5곳(카파도키아 1 + 이스탄불 4)이 됐다. WAWFN 은 WorldHotels 운영 중 · IHG 채널 판매 미개시\n"
    "#   (2027년 통합 예정)로 현금·포인트 365일 전부 null(0칸) — 기존 미판매 호텔(ROMAA·ROMVB·LISPD ·\n"
    "#   ACCRA 등)과 같은 관례이고 check_ihg 는 0칸을 결측으로 보지 않는다(NO_POINT_CODES 는 ③ 메리어트\n"
    "#   전용 목록이라 ⑤ 에는 등록하지 않는다). REKRR 은 리워드 재고가 얇아 포인트가 163일뿐이다.\n"
    "EXPECT_IHG = {'hotels': 251, 'cells': 91615, 'cash': 80363, 'points': 77653}",
))

for old, new in reps:
    n = src.count(old)
    if n != 1:
        print('!! 매치 %d회: %s' % (n, old[:120]))
        sys.exit(1)
    src = src.replace(old, new)

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('master_db.py EXPECT_IHG 갱신 완료 — 251곳 / 91,615칸 / 현금 80,363 · 포인트 77,653')
