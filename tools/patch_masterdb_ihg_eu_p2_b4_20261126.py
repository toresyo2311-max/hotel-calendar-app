#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P2 4차 4곳 병합 — tools/master_db.py 의 EXPECT_IHG 기대치를 248곳으로 올린다."""
import io
import sys

PATH = 'tools/master_db.py'
src = io.open(PATH, encoding='utf-8').read()
reps = []

reps.append((
    "#   2026-11-26 유럽 P2 3차 4곳(ZRHHA · GVACP · RKECP · STOKT = 스위스 2 · 덴마크 1 · 스웨덴 1)을\n"
    "#   더해 244곳 · 유럽 67 — 1,460칸(현금 1,349 · 포인트 1,359)을 더한 수 · 244 × 365 = 89,060칸.\n"
    "#   덴마크 · 스웨덴은 ⑤ IHG 유럽의 첫 지점이라 유럽이 18개국이 됐다(제네바 2 · 취리히 1).\n"
    "EXPECT_IHG = {'hotels': 244, 'cells': 89060, 'cash': 78315, 'points': 75783}",
    "#   2026-11-26 유럽 P2 3차 4곳(ZRHHA · GVACP · RKECP · STOKT = 스위스 2 · 덴마크 1 · 스웨덴 1)을\n"
    "#   더해 244곳 · 유럽 67 — 1,460칸(현금 1,349 · 포인트 1,359)을 더한 수 · 244 × 365 = 89,060칸.\n"
    "#   덴마크 · 스웨덴은 ⑤ IHG 유럽의 첫 지점이라 유럽이 18개국이 됐다(제네바 2 · 취리히 1).\n"
    "#   2026-11-26 유럽 P2 4차 4곳(HELMH · ATHGR · ISTBM · ISTOR = 핀란드 1 · 그리스 1 · 튀르키예 2)을\n"
    "#   더해 248곳 · 유럽 71 — 1,460칸(현금 1,367 · 포인트 1,368)을 더한 수 · 248 × 365 = 90,520칸.\n"
    "#   핀란드 · 그리스 · 튀르키예는 이미 지점이 있어 유럽은 18개국 그대로다(헬싱키 2 · 아테네 2 ·\n"
    "#   이스탄불 4). HELMH 는 크라운 플라자 헬싱키 - 헤스페리아이고 호텔 인디고 헬싱키(HELIN)와 다른 호텔.\n"
    "EXPECT_IHG = {'hotels': 248, 'cells': 90520, 'cash': 79682, 'points': 77151}",
))

for old, new in reps:
    n = src.count(old)
    if n != 1:
        print('!! 매치 %d회: %s' % (n, old[:120]))
        sys.exit(1)
    src = src.replace(old, new)

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('master_db.py EXPECT_IHG 갱신 완료 — 248곳 / 90,520칸 / 현금 79,682 · 포인트 77,151')
