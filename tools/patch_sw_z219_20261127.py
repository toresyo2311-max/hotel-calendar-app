#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① 호텔럭스 일일 순환 수집 5일차(h18~h20) — sw.js 캐시 버전 z218 → z219 + 버전 이력 추가(원격 최신 위 재적용)."""
import io

SW = 'sw.js'
sw = io.open(SW, encoding='utf-8').read()

ENTRY = (
    '   · z219 (2026-11-27) — **① 호텔럭스 23곳 일일 순환 수집 5일차** — 카펠라 방콕(h18) · '
    '하얏트 리젠시 다낭(h19) · 인터컨티넨탈 다낭(h20) 세 곳의 2026-12-01~12-14 14일 요금을 '
    '예약 사이트 상세 페이지에서 다시 재어(42칸 · 빈칸 0) 갱신하고, 미오픈 경계를 다시 확인해 '
    '세 곳 모두 예약 창이 **2027-10-23까지**로 밀린 것을 반영했습니다(새로 열린 10-19~10-23 15칸 채움 · '
    '10-24은 세 곳 모두 판매 객실 없음 · h20은 10-25도 확인). h18 USD 1,068~1,344(142만~179만원) · '
    'h19 USD 155(206,400원) 균일 · h20 USD 463~867(61만6,500~115만4,500원). ① 호텔럭스 23곳 '
    '`hotel.hotelux.com` ID 매핑도 이번에 **23/23 완결**됐습니다.\n'
)

old_head = '서비스 워커 (2026-11-27 z218 · ② 아코르·③ 국내 아코르 새벽 정기 갱신'
new_head = ('서비스 워커 (2026-11-27 z219 · ① 호텔럭스 5일차 — 카펠라 방콕·하얏트 리젠시 다낭·'
            '인터컨티넨탈 다낭 12/1~12/14 실측 갱신 + 예약창 2027-10-19~10-23 확장(3곳 모두 10-24 판매 없음) · '
            '매핑 23/23 완결 · z218 · ② 아코르·③ 국내 아코르 새벽 정기 갱신')
assert sw.count(old_head) == 1, sw.count(old_head)
sw = sw.replace(old_head, new_head, 1)

anchor = '\n   · z218 (2026-11-27) — '
if sw.count(anchor) != 1:
    # 2차 폴백: 이력 목록 첫 항목 앞
    import re
    m = re.search(r'\n   · z2\d\d \(2026-11-27\) — ', sw)
    assert m, 'changelog anchor not found'
    anchor = m.group(0)
sw = sw.replace(anchor, '\n' + ENTRY + anchor.lstrip('\n'), 1)

old_ver = "const VERSION = 'teambusan-v5-2026-11-27z218';"
assert sw.count(old_ver) == 1
sw = sw.replace(old_ver, "const VERSION = 'teambusan-v5-2026-11-27z219';")

io.open(SW, 'w', encoding='utf-8', newline='').write(sw)
print('sw.js 갱신 — z219')
