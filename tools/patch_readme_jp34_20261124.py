#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README.md — ③ 메리어트 일본 3·4차 병합에 맞춰 호텔 수·칸 수·탭 설명을 현행화한다.

집계값은 `data/master_db.json` 의 counts 에서 읽으므로 다른 작업이 먼저 들어와도 숫자가 어긋나지 않는다.
이미 바뀐 파일에 다시 돌려도 안전하다.
"""
import io
import json
import re

MASTER = 'data/master_db.json'
README = 'README.md'


def main():
    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    c = master['counts']
    tabs = c['tabs']
    hotels, cells = c['hotels'], c['cells']
    priced, na = c['priced'], c['na']
    mar = [h for h in master['hotels'] if h.get('group') == 'marriott']
    mcash = sum(1 for h in mar for v in (h.get('rates') or {}).values()
                if isinstance(v, (int, float)))
    mpts = sum(1 for h in mar for v in (h.get('points') or {}).values() if isinstance(v, int))
    mjp = sum(1 for h in mar if h.get('region') == '일본')
    moce = sum(1 for h in mar if h.get('region') == '오세아니아')
    cards = tabs['lux'] + tabs['accor'] + tabs['marriott'] + 275 + 218

    with io.open(README, encoding='utf-8') as fp:
        text = fp.read()
    pairs = [
        # 머리말 카드 수
        (r'③ 메리어트 \d+ · ④ 하얏트 275 · ⑤ IHG 218 = \*\*카드 [\d,]+장\*\*',
         '③ 메리어트 %d · ④ 하얏트 275 · ⑤ IHG 218 = **카드 %s장**' % (tabs['marriott'], format(cards, ','))),
        # 통합 지표표
        (r'\| 통합 호텔 \| \*\*\d+\*\* \| ① 호텔럭스 161 \+ ② 아코르 536 \+ ③ 메리어트 \d+ \(`counts\.tabs`\) \|',
         '| 통합 호텔 | **%d** | ① 호텔럭스 161 + ② 아코르 536 + ③ 메리어트 %d (`counts.tabs`) |'
         % (hotels, tabs['marriott'])),
        (r'\| 달력 요금·상태 \| \*\*[\d,]+\*\* \| 그 \d+곳의 날짜 칸 합계 — 값 있음 [\d,]+ · `—`\(미공개/미조회\) [\d,]+ \|',
         '| 달력 요금·상태 | **%s** | 그 %d곳의 날짜 칸 합계 — 값 있음 %s · `—`(미공개/미조회) %s |'
         % (format(cells, ','), hotels, format(priced, ','), format(na, ','))),
        (r'> ④ 하얏트\(275곳\)와 ⑤ IHG\(218곳\)는 자기 탭 안에서 따로 셉니다 — 위 [\d,]+·[\d,]+에 들어 있지 않습니다\.',
         '> ④ 하얏트(275곳)와 ⑤ IHG(218곳)는 자기 탭 안에서 따로 셉니다 — 위 %s·%s에 들어 있지 않습니다.'
         % (format(hotels, ','), format(cells, ','))),
        # ③ 탭 줄
        (r'\| ③ \| 메리어트 \|[^\n]*\|[^\n]*\| 2026\.12~2027\.11 \|',
         '| ③ | 메리어트 | 한국 40 · 중국 본토·홍콩·마카오 40 · 일본 %d · 싱가포르 22 · 오세아니아 %d. '
         '현금(공홈 요금 캘린더, 기존 62곳은 세금 포함·신규는 세전, 호주 26곳은 세금 포함 총액) + '
         '아워드 포인트 365일, 35k 숙박권 필터 | %d곳 / %s칸(현금 %s · 포인트 %s) | 2026.12~2027.11 |'
         % (mjp, moce, tabs['marriott'], format(tabs['marriott'] * 365, ','),
            format(mcash, ','), format(mpts, ','))),
        # 지연 로딩 표
        (r'\| `data/app/tab4_marriott\.json` \| ③ 메리어트 \| \d+곳\(현금·아워드 포인트\) \| [\d.]+ MB \|',
         '| `data/app/tab4_marriott.json` | ③ 메리어트 | %d곳(현금·아워드 포인트) | 1.46 MB |'
         % tabs['marriott']),
    ]
    changed = 0
    for pat, new in pairs:
        text, n = re.subn(pat, new.replace('\\', '\\\\'), text, count=1)
        if n:
            changed += 1
    with io.open(README, 'w', encoding='utf-8') as fp:
        fp.write(text)
    print('README 갱신 — %d곳 바꿈 (통합 %d곳 · %s칸 · 메리어트 %d곳)' % (
        changed, hotels, format(cells, ','), tabs['marriott']))


if __name__ == '__main__':
    main()
