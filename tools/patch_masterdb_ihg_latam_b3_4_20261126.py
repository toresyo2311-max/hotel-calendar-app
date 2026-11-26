#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 3차 4곳 병합 — tools/master_db.py 의 EXPECT_IHG 기대치를 263곳으로 올린다."""
import io
import sys

PATH = 'tools/master_db.py'
src = io.open(PATH, encoding='utf-8').read()

old_line = "EXPECT_IHG = {'hotels': 259, 'cells': 94535, 'cash': 82966, 'points': 79855}"
new_line = "EXPECT_IHG = {'hotels': 263, 'cells': 95995, 'cash': 84328, 'points': 81186}"
assert src.count(old_line) == 1, src.count(old_line)
src = src.replace(old_line, new_line)

old_c = ('#   Fee 별도다. ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조해 겹침 0곳(alsoIn 9쌍 그대로).\n')
new_c = old_c + (
    '#   2026-11-26 중남미 3차 4곳(SCLHA · LIMHA · LIMMP · LIMMD = 산티아고 1 · 리마 3)을 더해 263곳 ·\n'
    '#   북미·중남미 69 — 1,460칸(현금 1,362 · 포인트 1,331)을 더한 수 · 263 × 365 = 95,995칸.\n'
    '#   칠레 · 페루는 ⑤ IHG 의 첫 지점(미국 52 · 캐나다 5 · 멕시코 6 · 브라질 1 · 아르헨티나 1 · 칠레 1 · 페루 3).\n'
    '#   SCLHA 는 칠레 IVA 19% 포함 세후가이고 2027-04-04~06 · 04-11~15 · 04-19~22 12일이 현금·포인트 동시\n'
    '#   매진(부활절 주간) · 2026-12-02 등 6일은 리워드만 없음, LIMHA 는 10% 서비스차지 + 18% IGV 포함이고\n'
    '#   현금·포인트 null 집합이 같다. LIMMP 는 날짜별 최저가에 Early Saver Member Exclusive(환불불가 ·\n'
    '#   29일 전 예약 · 회원 전용)가 들어 있고, LIMMD 는 2026년 12월 현금 31일 전부 판매에 리워드는 19일만\n'
    '#   열려 포인트 319일(포인트만 비는 날 25일)이다 — check_ihg 는 0칸을 결측으로 보지 않는다.\n'
    '#   네 곳 모두 마지막 값 있는 날이 2027-11-09(2027-11-10~30 예약창 밖)이다. ① 호텔럭스 161곳과\n'
    '#   코드·영문명·국문명·도시를 전수 대조해 겹침 0곳(alsoIn 9쌍 그대로 · ①·⑤ 모두 좌표 필드 없음).\n'
)
if src.count(old_c) == 1:
    src = src.replace(old_c, new_c)
else:
    print('!! 주석 앵커 매치 %d회 — 주석은 건너뜀' % src.count(old_c))
    sys.exit(1)

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('master_db.py EXPECT_IHG 갱신 — 263곳 / 95,995칸 / 현금 84,328 · 포인트 81,186')
