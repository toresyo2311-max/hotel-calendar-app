#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 중남미 1차 4곳 병합에 맞춰 README 숫자를 255곳 / 북미·중남미 61 으로 맞춘다."""
import io
import sys

PATH = 'README.md'
src = io.open(PATH, encoding='utf-8').read()
reps = [
    ('④ 하얏트 347 · ⑤ IHG 251 = **카드 1,638장**',
     '④ 하얏트 347 · ⑤ IHG 255 = **카드 1,642장**'),
    ('> ④ 하얏트(347곳)와 ⑤ IHG(251곳)는',
     '> ④ 하얏트(347곳)와 ⑤ IHG(255곳)는'),
    ('+ 북미·중남미 57 + 중동 36 + 아프리카 12. 공홈 비로그인 세후 현금과 IHG One Rewards 포인트를 같은 달력에 | '
     '251곳 / 91,615칸(현금 80,363 · 포인트 77,653) |',
     '+ 북미·중남미 61(멕시코시티 4) + 중동 36 + 아프리카 12. 공홈 비로그인 세후 현금과 IHG One Rewards 포인트를 같은 달력에 | '
     '255곳 / 93,075칸(현금 81,720 · 포인트 78,878) |'),
    ('| `data/app/tab11_ihg.json` | ⑤ IHG | 251곳(현금·포인트) | 1.41 MB |',
     '| `data/app/tab11_ihg.json` | ⑤ IHG | 255곳(현금·포인트) | 1.45 MB |'),
    ('지역 칩 6개(아시아·오세아니아 72 · 유럽 41 · 북미·중남미 57 · 중동 36 · 아프리카 12 + 전체)',
     '지역 칩 6개(아시아·오세아니아 72 · 유럽 74 · 북미·중남미 61 · 중동 36 · 아프리카 12 + 전체)'),
    ('④ 하얏트(347곳)와 ⑤ IHG(251곳)는\n',
     '④ 하얏트(347곳)와 ⑤ IHG(255곳)는\n'),
]
for old, new in reps:
    n = src.count(old)
    if n != 1:
        print('!! 매치 %d회: %s' % (n, old[:120]))
        sys.exit(1)
    src = src.replace(old, new)
io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('README.md 갱신 완료 — 치환 %d건 · 남은 251: %d · 남은 IHG 57: %d'
      % (len(reps), src.count('IHG 251'), src.count('북미·중남미 57')))
