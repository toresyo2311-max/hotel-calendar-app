#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 4차 2곳 병합에 맞춰 README 숫자를 265곳 / 북미·중남미 71 로 맞춘다."""
import io
import sys

PATH = 'README.md'
src = io.open(PATH, encoding='utf-8').read()
reps = [
    ('⑤ IHG 263 = **카드 1,650장**', '⑤ IHG 265 = **카드 1,652장**'),
    ('④ 하얏트(347곳)와 ⑤ IHG(263곳)는', '④ 하얏트(347곳)와 ⑤ IHG(265곳)는'),
    ('+ 북미·중남미 69(멕시코시티 4 · 칸쿤 2 · 상파울루 · 부에노스아이레스 · 산티아고 · 리마 3) '
     '+ 중동 36 + 아프리카 12. 공홈 비로그인 세후 현금과 IHG One Rewards 포인트를 같은 달력에 | '
     '263곳 / 95,995칸(현금 84,328 · 포인트 81,186) |',
     '+ 북미·중남미 71(멕시코시티 4 · 칸쿤 2 · 상파울루 · 부에노스아이레스 · 산티아고 · 리마 4 · '
     '파나마시티) + 중동 36 + 아프리카 12. 공홈 비로그인 세후 현금과 IHG One Rewards 포인트를 같은 '
     '달력에 | 265곳 / 96,725칸(현금 85,015 · 포인트 81,841) |'),
    ('| `data/app/tab11_ihg.json` | ⑤ IHG | 263곳(현금·포인트) | 1.52 MB |',
     '| `data/app/tab11_ihg.json` | ⑤ IHG | 265곳(현금·포인트) | 1.53 MB |'),
    ('지역 칩 6개(아시아·오세아니아 72 · 유럽 74 · 북미·중남미 69 · 중동 36 · 아프리카 12 + 전체)',
     '지역 칩 6개(아시아·오세아니아 72 · 유럽 74 · 북미·중남미 71 · 중동 36 · 아프리카 12 + 전체)'),
]
for old, new in reps:
    n = src.count(old)
    if n == 0:
        print('!! 매치 0회: %s' % old[:120])
        sys.exit(1)
    src = src.replace(old, new)
io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('README.md 갱신 완료 · 남은 IHG(263곳: %d · IHG 263: %d · 북미·중남미 69: %d · 95,995: %d'
      % (src.count('IHG(263곳'), src.count('IHG 263'), src.count('북미·중남미 69'), src.count('95,995')))
