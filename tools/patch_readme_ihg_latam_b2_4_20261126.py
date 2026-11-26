#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 2차 4곳 병합에 맞춰 README 숫자를 259곳 / 북미·중남미 65 로 맞춘다."""
import io
import sys

PATH = 'README.md'
src = io.open(PATH, encoding='utf-8').read()
reps = [
    ('④ 하얏트(347곳)와 ⑤ IHG(255곳)는',
     '④ 하얏트(347곳)와 ⑤ IHG(259곳)는'),
    ('+ 북미·중남미 61(멕시코시티 4) + 중동 36 + 아프리카 12. 공홈 비로그인 세후 현금과 IHG One Rewards '
     '포인트를 같은 달력에 | 255곳 / 93,075칸(현금 81,720 · 포인트 78,878) |',
     '+ 북미·중남미 65(멕시코시티 4 · 칸쿤 2 · 상파울루 · 부에노스아이레스) + 중동 36 + 아프리카 12. '
     '공홈 비로그인 세후 현금과 IHG One Rewards 포인트를 같은 달력에 | 259곳 / 94,535칸'
     '(현금 82,966 · 포인트 79,855) |'),
    ('| `data/app/tab11_ihg.json` | ⑤ IHG | 255곳(현금·포인트) | 1.45 MB |',
     '| `data/app/tab11_ihg.json` | ⑤ IHG | 259곳(현금·포인트) | 1.49 MB |'),
    ('지역 칩 6개(아시아·오세아니아 72 · 유럽 74 · 북미·중남미 61 · 중동 36 · 아프리카 12 + 전체)',
     '지역 칩 6개(아시아·오세아니아 72 · 유럽 74 · 북미·중남미 65 · 중동 36 · 아프리카 12 + 전체)'),
]
for old, new in reps:
    n = src.count(old)
    if n == 0:
        print('!! 매치 0회: %s' % old[:120])
        sys.exit(1)
    src = src.replace(old, new)
io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('README.md 갱신 완료 · 남은 255: %d · 남은 북미·중남미 61: %d'
      % (src.count('IHG(255곳)'), src.count('북미·중남미 61')))
