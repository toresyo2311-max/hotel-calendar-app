#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 유럽 이탈리아 1차 로마 3곳 병합에 맞춰 index.html·README.md·sw.js·master_db.py 문구·수를 갱신."""

import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def patch(path, pairs):
    src = io.open(os.path.join(ROOT, path), encoding='utf-8').read()
    for old, new, n in pairs:
        got = src.count(old)
        assert got == n, (path, got, n, old[:90])
        src = src.replace(old, new)
    io.open(os.path.join(ROOT, path), 'w', encoding='utf-8').write(src)
    print('patched', path, len(pairs))


SUB_ADD = (' 2026-11-26에는 유럽 3차(이탈리아 1차)로 <strong>로마 3곳</strong>(하얏트 리젠시 로마 센트럴 · '
           '더 트리뷴 · 톰슨 로마)을 스탠다드 아워드 포인트로 실측해 더했습니다(3 × 365 = 1,095칸 가운데 990칸 · '
           '값 없는 105칸은 보간 없이 —). 하얏트 리젠시 로마 센트럴은 <strong>2026년 12월 31일 전체가 '
           '개관 전 예약 미오픈</strong>이라 2027-01-01부터 재고가 있습니다.')

BASIS_IT = ('2026-11-26에 더한 <strong>유럽 3차(이탈리아 1차) 로마 3곳</strong>은 3 × 365 = '
            '<strong>1,095칸 가운데 990칸</strong>에 스탠다드 아워드 포인트가 있고(값 없는 105칸은 보간 없음), '
            '① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조했으나 겹치는 호텔이 없습니다'
            '(① 탭에 이탈리아 지점이 없습니다). 하얏트 리젠시 로마 센트럴 <code>romrt</code>'
            '(Cat 4 · 12,000~22,500P · 포인트 293일)이 가장 낮은 구간인데, <strong>2026년 12월 31일 전체가 '
            '매진이 아니라 개관 전 예약 미오픈</strong>이라 하얏트 공지 「Now accepting reservations for stays '
            'from January 1, 2027 and beyond」대로 <strong>2027-01-01부터 재고가 시작</strong>됩니다. '
            '더 트리뷴 <code>romjd</code>(JdV by Hyatt · Cat 6 · 20,000~35,000P · 339일), '
            '톰슨 로마 <code>romth</code>(Cat 8 · 35,000~65,000P · 358일) 순입니다. 3곳 모두 포인트만 실측했고 '
            '공홈 현금가·호럭 요금은 없습니다. No.7(@no_7)이 전달한 본입니다. ')

CAUTION_IT = ('<li>2026-11-26에 더한 <strong>유럽 3차(이탈리아 1차) 로마 3곳</strong>(이탈리아 라치오주 로마)도 '
              '<strong>아워드 포인트만</strong> 실측했습니다 — 공홈 현금가·호럭 요금은 미수집이라 「—」이고, '
              '3 × 365 = 1,095칸 가운데 990칸에 값이 있습니다(하얏트 리젠시 로마 센트럴 <code>romrt</code> Cat 4 ~ '
              '톰슨 로마 <code>romth</code> Cat 8 — 이탈리아 3곳은 원본에 카테고리가 있어 Cat 이 표시됩니다). '
              '<strong>하얏트 리젠시 로마 센트럴 <code>romrt</code>는 2026년 12월 31일 전체가 매진이 아니라 '
              '개관 전 예약 미오픈</strong>입니다 — 하얏트 공지 「Now accepting reservations for stays from '
              'January 1, 2027 and beyond」대로 <strong>2027-01-01부터 재고가 시작</strong>되어 12월은 투숙할 수 없고, '
              '그 31일은 값을 채우지 않고 「—」로 두었습니다. 개관이 여러 차례 연기된 신규 호텔이라 실제 투숙 전에 '
              '공홈에서 개관 여부를 다시 확인하시는 편이 안전합니다.</li>')

patch('index.html', [
    # 탭 버튼 배지·aria-label
    ('+ 미국 209곳 + 유럽 61곳"><span class="t-full">④ 하얏트</span>'
     '<span class="t-short">④ 하얏트</span> <b>321</b>',
     '+ 미국 209곳 + 유럽 64곳"><span class="t-full">④ 하얏트</span>'
     '<span class="t-short">④ 하얏트</span> <b>324</b>', 1),
    # tabs.hyatt 제목
    ("'하얏트 321곳 (공홈 세후 · 호럭 · 포인트)'", "'하얏트 324곳 (공홈 세후 · 호럭 · 포인트)'", 1),
    # tabs.hyatt 요약 — 유럽 61 → 64 (요약·자료 기준 두 곳)
    ('+ 유럽 61(영국 22 — 런던 12', '+ 유럽 64(영국 22 — 런던 12', 2),
    ('마인츠 3 · 울름) = 321곳 /', '마인츠 3 · 울름 / 이탈리아 3 — 로마 3) = 324곳 /', 1),
    ('마인츠 3 · 울름). 2026-11-23에', '마인츠 3 · 울름 / 이탈리아 3 — 로마 3). 2026-11-23에', 1),
    # 탭 짧은 설명 맵
    ('하얏트 321곳(아·태 51 + 미국 209 + 유럽 61)',
     '하얏트 324곳(아·태 51 + 미국 209 + 유럽 64)', 1),
    # 주석
    ('④ 하얏트 미국 209곳 · 유럽 61곳 등', '④ 하얏트 미국 209곳 · 유럽 64곳 등', 1),
    # 순위 힌트
    ('+ 유럽 61(영국 22 · 프랑스 14 · 독일 25) = <strong>321곳</strong>',
     '+ 유럽 64(영국 22 · 프랑스 14 · 독일 25 · 이탈리아 3) = <strong>324곳</strong>', 1),
    ('미국 209곳과 유럽 61곳은', '미국 209곳과 유럽 64곳은', 1),
    ('샌안토니오 2차 4곳) 공홈 현금가는', '샌안토니오 2차 4 · 이탈리아 1차 로마 3곳) 공홈 현금가는', 1),
    ('(미국 호럭 미입점 176곳과 유럽 61곳은 —)', '(미국 호럭 미입점 176곳과 유럽 64곳은 —)', 1),
    # 자료 기준(basis)
    ('<strong>④ 하얏트 321곳</strong> = 아시아·오세아니아 51',
     '<strong>④ 하얏트 324곳</strong> = 아시아·오세아니아 51', 1),
    ('4차-B 샌안토니오 2차 4곳까지 237곳(미국 176 · 영국 22 · 프랑스·독일 39)이 됩니다',
     '이탈리아 1차 로마 3곳까지 240곳(미국 176 · 영국 22 · 프랑스·독일 39 · 이탈리아 3)이 됩니다', 1),
    # 주의 문구(caution) — 유럽 1·2차 한정 문구로 정정
    ('유럽 61곳은 원본 실측에 지점 카테고리 값이 없어',
     '유럽 1·2차 61곳은 원본 실측에 지점 카테고리 값이 없어', 1),
])

src = io.open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()

# tabs.hyatt 요약 끝에 이탈리아 1차 문단 추가
anchor_sub = '이로써 <strong>샌안토니오 8곳</strong>이 완결됐습니다.\',checked:'
assert src.count(anchor_sub) == 1, src.count(anchor_sub)
src = src.replace(anchor_sub, '이로써 <strong>샌안토니오 8곳</strong>이 완결됐습니다.' + SUB_ADD + '\',checked:')

# 자료 기준(basis) 유럽 2차 문단 뒤에 이탈리아 1차 문단 추가
anchor_basis = '(alsoIn 연결 0쌍 — 유럽 2차 39곳도 공홈 단일 링크). '
assert src.count(anchor_basis) == 1, src.count(anchor_basis)
src = src.replace(anchor_basis, anchor_basis + BASIS_IT)

# 주의 문구에 이탈리아 1차 li 추가
anchor_caution = ('유럽 1·2차 61곳은 원본 실측에 지점 카테고리 값이 없어 모두 <strong>Cat 표시 없이</strong> '
                  '이름만 나옵니다.</li>')
assert src.count(anchor_caution) == 1, src.count(anchor_caution)
src = src.replace(anchor_caution, anchor_caution + CAUTION_IT)
io.open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(src)
print('inserted 이탈리아 1차 문단 3곳')

patch('README.md', [
    ('(① 호텔럭스 161 · ② 아코르 536 · ③ 메리어트 343 · ④ 하얏트 321 · ⑤ IHG 218 = **카드 1,579장**)',
     '(① 호텔럭스 161 · ② 아코르 536 · ③ 메리어트 343 · ④ 하얏트 324 · ⑤ IHG 218 = **카드 1,582장**)', 1),
    ('> ④ 하얏트(321곳)와 ⑤ IHG(218곳)는', '> ④ 하얏트(324곳)와 ⑤ IHG(218곳)는', 1),
    ('+ 유럽 61(영국 22·프랑스 14·독일 25). 공홈 세후 현금 33곳 · 호럭 52곳 · 스탠다드 아워드 포인트 321곳 365일',
     '+ 유럽 64(영국 22·프랑스 14·독일 25·이탈리아 3). 공홈 세후 현금 33곳 · 호럭 52곳 · '
     '스탠다드 아워드 포인트 324곳 365일', 1),
    ('| 321곳 / 포인트 117,165칸(값 104,770) |', '| 324곳 / 포인트 118,260칸(값 105,760) |', 1),
    ('| `data/app/tab10_hyatt.json` | ④ 하얏트 | 321곳(공홈 세후·호럭·포인트) | 1.09 MB |',
     '| `data/app/tab10_hyatt.json` | ④ 하얏트 | 324곳(공홈 세후·호럭·포인트) | 1.10 MB |', 1),
    ('④ 하얏트(321곳)만은 `EXPECT_HYATT`', '④ 하얏트(324곳)만은 `EXPECT_HYATT`', 1),
])

# ── sw.js ────────────────────────────────────────────────
Z178 = ('   · z178 (2026-11-26) — **④ 하얏트에 유럽 이탈리아 1차 로마 3곳을 병합**(hy322~hy324 · '
        '321→324곳 · 유럽 61→64 · **이탈리아 로마 3**) — No.7(@no_7)이 전달한 hyatt.com 스탠다드 아워드 '
        '실측본(2026-11-26 02:33 KST · 2026-12-01~2027-11-30 365일)을 더했습니다. 3 × 365 = **1,095칸 가운데 '
        '990칸**에 값이 있고, 값 없는 105칸은 보간 없이 — 입니다. **하얏트 리젠시 로마 센트럴**(romrt · Cat 4 · '
        '12,000~22,500P · 293일 — **2026년 12월 31일 전체가 개관 전 예약 미오픈**, 하얏트 공지 「Now accepting '
        'reservations for stays from January 1, 2027 and beyond」대로 2027-01-01부터 재고) · **더 트리뷴**(romjd · '
        'JdV by Hyatt · Cat 6 · 20,000~35,000P · 339일) · **톰슨 로마**(romth · Cat 8 · 35,000~65,000P · 358일)이고, '
        '① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조해 **겹침 0곳**입니다(① 탭에 이탈리아 지점이 없습니다).\n')
patch('sw.js', [
    ('서비스 워커 (2026-11-26 z177 · ',
     '서비스 워커 (2026-11-26 z178 · ④ 하얏트 유럽 이탈리아 1차 로마 3곳 병합(321→324곳 · 유럽 64 · '
     '1,095칸 중 990칸 · ① 호텔럭스 겹침 0곳 · romrt 2026-12 개관 전 예약 미오픈) · z177 · ', 1),
    ("const VERSION = 'teambusan-v5-2026-11-26z177';",
     "const VERSION = 'teambusan-v5-2026-11-26z178';", 1),
    ('   · z177 (2026-11-26) — ', Z178 + '   · z177 (2026-11-26) — ', 1),
])

# ── master_db.py ─────────────────────────────────────────
patch('tools/master_db.py', [
    ('#   4차-B 샌안토니오 1차 4곳 → 317곳, 4차-B 샌안토니오 2차(마지막) 4곳 → 321곳 ·\n'
     '#   117,165칸 · 값 104,770칸 — 샌안토니오 8곳 완결).\n'
     "EXPECT_HYATT = {'hotels': 321, 'cells': 117165, 'priced': 104770}",
     '#   4차-B 샌안토니오 1차 4곳 → 317곳, 4차-B 샌안토니오 2차(마지막) 4곳 → 321곳,\n'
     '#   4차-B 유럽 3차(이탈리아 1차) 로마 3곳 → 324곳 · 118,260칸 · 값 105,760칸 — 117,165칸 · 값 104,770칸에서\n'
     '#   이탈리아 1차 3곳(1,095칸 · 값 990칸)을 더한 수).\n'
     "EXPECT_HYATT = {'hotels': 324, 'cells': 118260, 'priced': 105760}", 1),
])
