#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽 P1 1차 3곳 병합 — sw.js 캐시 버전 z193(직전 z192 다음) + 버전 이력 추가."""
import io

SW = 'sw.js'
sw = io.open(SW, encoding='utf-8').read()

ENTRY = (
    '   · z193 (2026-11-26) — **⑤ IHG에 유럽 P1 1차 3곳(헝가리 부다페스트 · 스위스 제네바 · 핀란드 '
    '헬싱키)을 병합**(i227~i229 · 226→229곳 · 유럽 49→52) — No.7(@no_7)이 공홈에서 직접 실측해 보낸 '
    '2026-12-01~2027-11-30 365일본(2026-11-26 조회)을 더했습니다. 3 × 365 = **1,095칸 가운데 현금 '
    '1,007칸 · 포인트 985칸**에 값이 있고, 값 없는 칸은 보간 없이 — 입니다. **킴프턴 BEM 부다페스트**'
    '(BUDKM · 344/335) · **인터컨티넨탈 제네바**(GVAHA · 322/322 — 현금·포인트가 같은 43일 비어 있고 '
    '달력 셀이 취소선으로 표시된 실제 판매불가 날짜) · **호텔 인디고 헬싱키 - Boulevard**(HELIN · '
    '341/328)이고, 세 곳 모두 값이 있는 마지막 날이 **2027-11-09**입니다(2027-11-10~11-30은 예약창 '
    '미오픈). ① 호텔럭스 161곳과 코드·영문명·국문명·도시를 전수 대조해 **겹침 0곳**(① 탭은 뉴욕 · '
    '싱가포르 · 도쿄 · 서울 · 시드니 · 방콕 · 상하이 · 다낭 · 나트랑 · 부산 · 후쿠오카 · 오사카 12개 '
    '도시에만 있어 부다페스트 · 제네바 · 헬싱키에 지점이 없음 — alsoIn 추가 0쌍 · IHG 공홈 단일 링크). '
    '탭 배지·지역 칩·제목·요약·자료 기준·안내문·주의문·순위 힌트·머리말·README 를 **229 / 유럽 52 / '
    '83,585칸(현금 73,262 · 포인트 70,817)** 로 맞췄고, `tools/master_db.py` 에 ⑤ IHG 검사'
    '(EXPECT_IHG — 곳수·칸수·값 있는 칸·id/code 중복)를 더했습니다.\n'
)

old_head = '서비스 워커 (2026-11-26 z192 · '
new_head = ('서비스 워커 (2026-11-26 z193 · ⑤ IHG 유럽 P1 1차 3곳 병합(226→229곳 · 유럽 52 · 현금 '
            '1,007 + 포인트 985칸 · ① 호텔럭스 겹침 0곳) · z192 · ')
assert sw.count(old_head) == 1, sw.count(old_head)
sw = sw.replace(old_head, new_head)

anchor = '\n   · z192 (2026-11-26) — **🔄 근거리 90일 주간 재수집'
assert sw.count(anchor) == 1, sw.count(anchor)
sw = sw.replace(anchor, '\n' + ENTRY + '   · z192 (2026-11-26) — **🔄 근거리 90일 주간 재수집')

old_ver = "const VERSION = 'teambusan-v5-2026-11-26z192';"
assert sw.count(old_ver) == 1
sw = sw.replace(old_ver, "const VERSION = 'teambusan-v5-2026-11-26z193';")

io.open(SW, 'w', encoding='utf-8', newline='').write(sw)
print('sw.js 갱신 — z193')
