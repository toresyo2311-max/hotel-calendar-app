#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README.md — ③ 메리어트 베트남 1차 4곳 병합(308→312 · 통합 1,009곳) 반영."""
PATH = 'README.md'
src = open(PATH, encoding='utf-8').read()
orig = src


def sub(old, new, count=1, label=''):
    global src
    n = src.count(old)
    if n != count:
        raise SystemExit('[%s] 기대 %d회 · 실제 %d회: %r' % (label, count, n, old[:90]))
    src = src.replace(old, new)


# 1) 탭 구성 요약 — 카드 수
sub('(① 호텔럭스 161 · ② 아코르 536 · ③ 메리어트 308 · ④ 하얏트 275 · ⑤ IHG 218 = **카드 1,498장**)',
    '(① 호텔럭스 161 · ② 아코르 536 · ③ 메리어트 312 · ④ 하얏트 275 · ⑤ IHG 218 = **카드 1,502장**)',
    label='카드 수')

# 2) 상단 지표 표
sub('| 통합 호텔 | **1,005** | ① 호텔럭스 161 + ② 아코르 536 + ③ 메리어트 308 (`counts.tabs`) |',
    '| 통합 호텔 | **1,009** | ① 호텔럭스 161 + ② 아코르 536 + ③ 메리어트 312 (`counts.tabs`) |',
    label='통합 호텔')
sub('| 달력 요금·상태 | **360,255** | 그 1,005곳의 날짜 칸 합계 — 값 있음 229,757 · `—`(미공개/미조회) 130,498 |',
    '| 달력 요금·상태 | **361,715** | 그 1,009곳의 날짜 칸 합계 — 값 있음 232,658 · `—`(미공개/미조회) 129,057 |',
    label='칸 합계')
sub('위 1,005·360,255에 들어 있지 않습니다.', '위 1,009·361,715에 들어 있지 않습니다.', label='주석')
sub('`verify` 의 호텔 검사 대상은 **①~③ 1,005곳**입니다', '`verify` 의 호텔 검사 대상은 **①~③ 1,009곳**입니다',
    label='검사 대상')

# 3) 탭 구성 표의 ③ 행
sub('| ③ | 메리어트 | 한국 40 · 중국 본토·홍콩·마카오 40 · 일본 131 · 싱가포르 22 · 오세아니아 47 · 대만 28.',
    '| ③ | 메리어트 | 한국 40 · 중국 본토·홍콩·마카오 40 · 일본 131 · 싱가포르 22 · 오세아니아 47 · 대만 28 · 베트남 4.',
    label='표 ③ 지역')
sub('| 308곳 / 112,420칸(현금 98,230 · 포인트 91,816) | 2026.12~2027.11 |',
    '| 312곳 / 113,880칸(현금 100,888 · 포인트 93,204) | 2026.12~2027.11 |', label='표 ③ 칸')

# 4) 탭별 JSON 표 — ③ 크기
sub('| `data/app/tab4_marriott.json` | ③ 메리어트 | 308곳(현금·아워드 포인트) | 1.68 MB |',
    '| `data/app/tab4_marriott.json` | ③ 메리어트 | 312곳(현금·아워드 포인트) | 1.70 MB |',
    label='탭별 JSON')

# 5) verify 출력 예시 — 지금 값으로
sub('정상일 때 `verify` 출력(2026-11-24 실행):', '정상일 때 `verify` 출력(2026-11-25 실행):', label='verify 날짜')
sub('  hotels 1005  tabs {\'lux\': 161, \'accor\': 536, \'marriott\': 308}\n'
    '  cells 360255  priced 229757  na 130498  stayplus 142',
    '  hotels 1009  tabs {\'lux\': 161, \'accor\': 536, \'marriott\': 312}\n'
    '  cells 361715  priced 232658  na 129057  stayplus 142', label='verify 수치')
sub('  ⑦ 마일리지 9개 노선 · 수집칸 3558 · 좌석 있는 칸 3119 · 미수집 12\n'
    '  flights 당일치기 320건 · 패턴 12종\n'
    '  index.html const DB 호텔 0곳 (비어 있어야 함)\n'
    '  이력 스냅샷 2026-11-24 · 에러가 의심 3건 (data/history/)',
    '  ⑦ 마일리지 9개 노선 · 수집칸 3558 · 좌석 있는 칸 3118 · 미수집 18\n'
    '  flights 당일치기 326건 · 패턴 12종\n'
    '  index.html const DB 호텔 0곳 (비어 있어야 함)\n'
    '  이력 스냅샷 2026-11-25 · 에러가 의심 6건 (data/history/)', label='verify 나머지')

assert src != orig
open(PATH, 'w', encoding='utf-8').write(src)
print('README.md 갱신 완료')
