#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P2 4차 4곳 병합 — README 숫자·문구를 248곳 / 유럽 71 로 맞춘다."""
import io
import os
import sys

PATH = 'README.md'
src = io.open(PATH, encoding='utf-8').read()
reps = []

size_mb = os.path.getsize('data/app/tab11_ihg.json') / (1024.0 * 1024.0)
print('tab11_ihg.json %.2f MB' % size_mb)

reps.append(('⑤ IHG 244 = **카드 1,631장**', '⑤ IHG 248 = **카드 1,635장**'))
reps.append(('⑤ IHG(244곳)는 자기 탭 안에서', '⑤ IHG(248곳)는 자기 탭 안에서'))
reps.append(('⑤ IHG(244곳)는\n', '⑤ IHG(248곳)는\n'))
reps.append((
    '+ 유럽 67(영국 9 · 프랑스 8 · 이탈리아 12 · 스페인 6 · 포르투갈 5 · 아일랜드 1 · 네덜란드 3 · '
    '독일 6 · 벨기에 2 · 오스트리아 2 · 헝가리 3 · 체코 1 · 스위스 3 · 덴마크 1 · 스웨덴 1 · 핀란드 1 · '
    '그리스 1 · 튀르키예 2)',
    '+ 유럽 71(영국 9 · 프랑스 8 · 이탈리아 12 · 스페인 6 · 포르투갈 5 · 아일랜드 1 · 네덜란드 3 · '
    '독일 6 · 벨기에 2 · 오스트리아 2 · 헝가리 3 · 체코 1 · 스위스 3 · 덴마크 1 · 스웨덴 1 · 핀란드 2 · '
    '그리스 2 · 튀르키예 4)',
))
reps.append(('| 244곳 / 89,060칸(현금 78,315 · 포인트 75,783) |',
             '| 248곳 / 90,520칸(현금 79,682 · 포인트 77,151) |'))
reps.append(('| `data/app/tab11_ihg.json` | ⑤ IHG | 244곳(현금·포인트) | 1.35 MB |',
             '| `data/app/tab11_ihg.json` | ⑤ IHG | 248곳(현금·포인트) | %.2f MB |' % size_mb))

for old, new in reps:
    n = src.count(old)
    if n != 1:
        print('!! 매치 %d회: %s' % (n, old[:120]))
        sys.exit(1)
    src = src.replace(old, new)

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('README 갱신 완료 — 치환 %d건' % len(reps))
print('남은 IHG(244:', src.count('IHG(244'), '· 남은 ⑤ IHG 244:', src.count('⑤ IHG 244'),
      '· 남은 유럽 67:', src.count('유럽 67'))
