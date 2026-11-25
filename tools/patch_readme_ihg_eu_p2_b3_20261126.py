#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P2 3차 4곳 병합 — README 숫자·문구를 244곳 / 유럽 67 로 맞춘다."""
import io
import os
import sys

PATH = 'README.md'
src = io.open(PATH, encoding='utf-8').read()
reps = []

size_mb = os.path.getsize('data/app/tab11_ihg.json') / (1024.0 * 1024.0)
print('tab11_ihg.json %.2f MB' % size_mb)

reps.append(('⑤ IHG 240 = **카드 1,627장**', '⑤ IHG 244 = **카드 1,631장**'))
reps.append(('④ 하얏트(347곳)와 ⑤ IHG(240곳)는 자기 탭 안에서 따로 셉니다',
             '④ 하얏트(347곳)와 ⑤ IHG(244곳)는 자기 탭 안에서 따로 셉니다'))
reps.append((
    '+ 유럽 63(영국 9 · 프랑스 8 · 이탈리아 12 · 스페인 6 · 포르투갈 5 · 아일랜드 1 · 네덜란드 3 · '
    '독일 6 · 벨기에 2 · 오스트리아 2 · 헝가리 3 · 체코 1 · 스위스 1 · 핀란드 1 · 그리스 1 · 튀르키예 2)',
    '+ 유럽 67(영국 9 · 프랑스 8 · 이탈리아 12 · 스페인 6 · 포르투갈 5 · 아일랜드 1 · 네덜란드 3 · '
    '독일 6 · 벨기에 2 · 오스트리아 2 · 헝가리 3 · 체코 1 · 스위스 3 · 덴마크 1 · 스웨덴 1 · 핀란드 1 · '
    '그리스 1 · 튀르키예 2)',
))
reps.append(('| 240곳 / 87,600칸(현금 76,966 · 포인트 74,424) |',
             '| 244곳 / 89,060칸(현금 78,315 · 포인트 75,783) |'))
reps.append(('| `data/app/tab11_ihg.json` | ⑤ IHG | 240곳(현금·포인트) | 1.32 MB |',
             '| `data/app/tab11_ihg.json` | ⑤ IHG | 244곳(현금·포인트) | %.2f MB |' % size_mb))

# 본문 두 곳(지표 설명 · verify 주의)의 ⑤ IHG 곳수
src = src.replace('④ 하얏트(347곳)와 ⑤ IHG(240곳)는\n', '④ 하얏트(347곳)와 ⑤ IHG(244곳)는\n')

for old, new in reps:
    n = src.count(old)
    if n != 1:
        print('!! 매치 %d회: %s' % (n, old[:120]))
        sys.exit(1)
    src = src.replace(old, new)

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('README 갱신 완료 — 치환 %d건' % len(reps))
print('남은 IHG 240:', src.count('IHG(240'), src.count('⑤ IHG 240'), '· 남은 유럽 63:', src.count('유럽 63'))
