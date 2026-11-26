#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 4차 2곳 병합 — tools/master_db.py 의 EXPECT_IHG 기대치를 265곳으로 올린다."""
import io
import sys

PATH = 'tools/master_db.py'
src = io.open(PATH, encoding='utf-8').read()

old_line = "EXPECT_IHG = {'hotels': 263, 'cells': 95995, 'cash': 84328, 'points': 81186}"
new_line = "EXPECT_IHG = {'hotels': 265, 'cells': 96725, 'cash': 85015, 'points': 81841}"
assert src.count(old_line) == 1, src.count(old_line)
src = src.replace(old_line, new_line)

old_c = ('#   네 곳 모두 마지막 값 있는 날이 2027-11-09(2027-11-10~30 예약창 밖)이다. ① 호텔럭스 161곳과\n'
         '#   코드·영문명·국문명·도시를 전수 대조해 겹침 0곳(alsoIn 9쌍 그대로 · ①·⑤ 모두 좌표 필드 없음).\n')
new_c = old_c + (
    '#   2026-11-26 중남미 4차(마지막) 2곳(LMAMI · PCYHA = 리마 1 · 파나마시티 1)을 더해 265곳 ·\n'
    '#   북미·중남미 71 — 730칸(현금 687 · 포인트 655)을 더한 수 · 265 × 365 = 96,725칸. 이로써\n'
    '#   중남미 14곳(멕시코시티 4 · 칸쿤 2 · 상파울루 1 · 부에노스아이레스 1 · 산티아고 1 · 리마 4 ·\n'
    '#   파나마시티 1)이 전량 완결됐다. 파나마는 ⑤ IHG 의 첫 지점(미국 52 · 캐나다 5 · 멕시코 6 ·\n'
    '#   브라질 1 · 아르헨티나 1 · 칠레 1 · 페루 4 · 파나마 1)이고 리마는 4곳이 됐다.\n'
    '#   LMAMI(크라운 플라자)는 현금 344일 · 포인트 342일 — 2026-12-01 · 12-27 두 날은 리워드만 없고\n'
    '#   현금 표시가는 세금·수수료 포함이나 포인트 모드 요금카드에 「Excludes 10% Service Charge.」가\n'
    '#   병기돼 포인트 숙박에는 10% 서비스차지가 따로 붙는다. PCYHA(인터컨티넨탈)는 현금 343일 ·\n'
    '#   포인트 313일 — 2026-12-11 이 현금·포인트 함께 빈 하루, 포인트만 비는 날 30일이고,\n'
    '#   2026-12-26 은 달력 견적가 356,431원과 요금카드 최저 383,994원이 2만7,400원 다른 날이다\n'
    '#   (달력 = 날짜별 최저 견적 · 요금카드 = Best Available 목록, 값은 달력 표시값 그대로).\n'
    '#   두 곳 모두 마지막 값 있는 날이 2027-11-09(2027-11-10~30 예약창 밖)이다. ① 호텔럭스 161곳과\n'
    '#   코드·영문명·국문명·도시를 전수 대조해 겹침 0곳(alsoIn 9쌍 그대로 · ①·⑤ 모두 좌표 필드 없음).\n'
)
if src.count(old_c) == 1:
    src = src.replace(old_c, new_c)
else:
    print('!! 주석 앵커 매치 %d회 — 주석은 건너뜀' % src.count(old_c))
    sys.exit(1)

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('master_db.py EXPECT_IHG 갱신 — 265곳 / 96,725칸 / 현금 85,015 · 포인트 81,841')
