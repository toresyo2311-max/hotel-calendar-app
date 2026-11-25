#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P2 2차 4곳 병합 — README 숫자·문구를 240곳 / 유럽 63 로 맞춘다."""
import io
import sys

PATH = 'README.md'
src = io.open(PATH, encoding='utf-8').read()
reps = []

reps.append(('⑤ IHG 236 = **카드 1,623장**', '⑤ IHG 240 = **카드 1,627장**'))
reps.append((
    '+ 유럽 59(영국 9 · 프랑스 8 · 이탈리아 12 · 스페인 6 · 포르투갈 5 · 아일랜드 1 · 네덜란드 3 · '
    '독일 5 · 벨기에 2 · 오스트리아 1 · 헝가리 2 · 스위스 1 · 핀란드 1 · 그리스 1 · 튀르키예 2)',
    '+ 유럽 63(영국 9 · 프랑스 8 · 이탈리아 12 · 스페인 6 · 포르투갈 5 · 아일랜드 1 · 네덜란드 3 · '
    '독일 6 · 벨기에 2 · 오스트리아 2 · 헝가리 3 · 체코 1 · 스위스 1 · 핀란드 1 · 그리스 1 · 튀르키예 2)',
))
reps.append(('| 236곳 / 86,140칸(현금 75,624 · 포인트 73,148) |',
             '| 240곳 / 87,600칸(현금 76,966 · 포인트 74,424) |'))
reps.append(('| `data/app/tab11_ihg.json` | ⑤ IHG | 236곳(현금·포인트) | 1.29 MB |',
             '| `data/app/tab11_ihg.json` | ⑤ IHG | 240곳(현금·포인트) | 1.30 MB |'))

# 본문 두 곳(지표 설명 · verify 주의)의 ⑤ IHG 곳수
src = src.replace('④ 하얏트(347곳)와 ⑤ IHG(236곳)는', '④ 하얏트(347곳)와 ⑤ IHG(240곳)는')

for old, new in reps:
    n = src.count(old)
    if n != 1:
        print('!! 매치 %d회: %s' % (n, old[:100]))
        sys.exit(1)
    src = src.replace(old, new)

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('README 갱신 완료 — 치환 %d건' % len(reps))
print('남은 236:', src.count('236'), '· 남은 유럽 59:', src.count('유럽 59'))
