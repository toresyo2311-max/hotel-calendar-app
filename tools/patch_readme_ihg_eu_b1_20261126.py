#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P1 1차 3곳 병합에 맞춰 README 숫자·문구를 229곳 / 유럽 52 로 맞춘다."""
import io
import sys

PATH = 'README.md'
src = io.open(PATH, encoding='utf-8').read()
reps = []

reps.append((
    '(① 호텔럭스 161 · ② 아코르 536 · ③ 메리어트 343 · ④ 하얏트 347 · ⑤ IHG 226 = **카드 1,613장**),',
    '(① 호텔럭스 161 · ② 아코르 536 · ③ 메리어트 343 · ④ 하얏트 347 · ⑤ IHG 229 = **카드 1,616장**),',
))
reps.append((
    '> ④ 하얏트(347곳)와 ⑤ IHG(226곳)는 자기 탭 안에서 따로 셉니다',
    '> ④ 하얏트(347곳)와 ⑤ IHG(229곳)는 자기 탭 안에서 따로 셉니다',
))
reps.append((
    '유럽 49(영국 9 · 프랑스 8 · 이탈리아 12 · 스페인 6 · 포르투갈 5 · 아일랜드 1 · 네덜란드 2 · '
    '독일 3 · 벨기에 1 · 오스트리아 1 · 헝가리 1) + 북미·중남미 57 + 중동 36 + 아프리카 12.',
    '유럽 52(영국 9 · 프랑스 8 · 이탈리아 12 · 스페인 6 · 포르투갈 5 · 아일랜드 1 · 네덜란드 2 · '
    '독일 3 · 벨기에 1 · 오스트리아 1 · 헝가리 2 · 스위스 1 · 핀란드 1) + 북미·중남미 57 + 중동 36 '
    '+ 아프리카 12.',
))
reps.append((
    '| 226곳 / 82,490칸(현금 72,255 · 포인트 69,832) | 2026.12~2027.11 |',
    '| 229곳 / 83,585칸(현금 73,262 · 포인트 70,817) | 2026.12~2027.11 |',
))
reps.append((
    '| `data/app/tab11_ihg.json` | ⑤ IHG | 226곳(현금·포인트) | 1.22 MB |',
    '| `data/app/tab11_ihg.json` | ⑤ IHG | 229곳(현금·포인트) | 1.24 MB |',
))
reps.append((
    '> **주의** — `verify` 의 호텔 검사 대상은 **①~③ 1,040곳**이고, ④ 하얏트(347곳)만은 `EXPECT_HYATT`\n'
    '> (곳수·칸수·값 있는 칸)로 따로 검사합니다. ⑤ IHG와 🌲·🎉·🅿️·🛫·⑧ 외항사는 각 `build_*` 도구가 만든\n'
    '> 별도 JSON이라 `verify` 가 내용을 대조하지 않습니다. 그 탭을 고쳤으면\n'
    '> GitHub Pages에서 그 탭을 직접 열어 확인하세요.',
    '> **주의** — `verify` 의 호텔 검사 대상은 **①~③ 1,040곳**이고, ④ 하얏트(347곳)와 ⑤ IHG(229곳)는\n'
    '> `EXPECT_HYATT`·`EXPECT_IHG`(곳수·칸수·값 있는 칸 · ⑤는 id/code 중복·`counts` 블록 포함)로 따로\n'
    '> 검사합니다. 🌲·🎉·🅿️·🛫·⑧ 외항사는 각 `build_*` 도구가 만든 별도 JSON이라 `verify` 가 내용을\n'
    '> 대조하지 않습니다. 그 탭을 고쳤으면 GitHub Pages에서 그 탭을 직접 열어 확인하세요.',
))

for old, new in reps:
    n = src.count(old)
    if n != 1:
        print('!! 매치 %d회: %s' % (n, old[:80]))
        sys.exit(1)
    src = src.replace(old, new)

io.open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('README.md 갱신 완료 — 치환 %d건' % len(reps))
