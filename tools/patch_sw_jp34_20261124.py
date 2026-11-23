#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sw.js — VERSION 을 한 칸 올리고(zNNN) 맨 위 이력에 ③ 메리어트 일본 3·4차 병합 한 줄을 넣는다.

여러 작업이 같은 파일을 만지므로 지금 파일의 VERSION 을 읽어 +1 한다(이미 이 작업 줄이 있으면 건너뜀).
"""
import io
import re

PATH = 'sw.js'
MARK = '③ 메리어트 일본 3·4차 59곳 병합'
BODY = ('**③ 메리어트에 일본 3차 30곳 · 4차 29곳을 병합**(m212~m270 · 211→270곳 · 일본 72→131) — '
        '5번(@jin_5)이 잰 일본 미수록 119곳 가운데 마지막 59곳(3차 — 오사카 17 · 삿포로 6 · '
        '마쓰모토 2 · 시즈오카 2 · 모리오카 1 · 센다이 1 · 야마구치 1 / 4차 — 오사카 7 · 오키나와 5 · '
        '요코하마 4 · 오카야마 3 · 이바라키 3 · 후쿠오카 2 · 히로시마 2 · 이키 1 · 하코네 1 · '
        '하코다테 1)의 2026-12-01~2027-11-30 365일 **현금 18,830칸 + 아워드 포인트 17,126칸**'
        '(값 없는 칸은 보간 없이 —)입니다. CTSKO 디자인 호텔스 삿포로는 현금 365일 전면 판매중단'
        '(포인트는 2027-10-26 하루만), OSAKO 디자인 호텔스 오쓰는 아워드 365일 미게시, UBJSN 야마구치는 '
        '2027-04-01~11-30 244일 · IKIKM 이키는 2027-07-01~11-30 153일 · OSAMC·OKARN·OSACY·OKJYD 는 '
        '2027년 10월 이후 · OKACR 오키나와는 2027-09-01~11-30 91일이 값 없이 이어지고, TYOYY 코트야드 '
        '요코하마 신역은 2026-12-18 개관이라 그전 17일과 아워드 전 기간이 비어 있습니다. TYOMH 하코네 '
        'MITSUI · HKDXF 하코다테는 아워드 재고 미개방입니다. **① 호텔럭스 161곳과 전수 대조 — 겹침 0곳**'
        '(alsoIn 추가 없음). 이로써 5번이 실측한 일본 119곳이 모두 반영됐습니다. 탭 배지·제목·요약줄·'
        '안내문·머리말을 **270 / 일본 131 / 통합 967곳(346,385칸)** 으로 맞췄습니다.')


def main():
    with io.open(PATH, encoding='utf-8') as fp:
        text = fp.read()
    if MARK in text:
        print('sw.js — 이미 반영됨')
        return
    m = re.search(r"const VERSION = 'teambusan-v5-(\d{4}-\d{2}-\d{2})z(\d+)';", text)
    if not m:
        raise SystemExit('VERSION 줄을 찾지 못했습니다')
    day, num = m.group(1), int(m.group(2))
    newnum = num + 1
    newver = "const VERSION = 'teambusan-v5-%sz%d';" % (day, newnum)
    text = text.replace(m.group(0), newver, 1)
    anchor = re.search(r'^   · z\d+ \(\d{4}-\d{2}-\d{2}\) — ', text, re.M)
    if not anchor:
        raise SystemExit('이력 첫 줄을 찾지 못했습니다')
    line = '   · z%d (2026-11-24) — %s\n' % (newnum, BODY)
    text = text[:anchor.start()] + line + text[anchor.start():]
    with io.open(PATH, 'w', encoding='utf-8') as fp:
        fp.write(text)
    print('sw.js — VERSION z%d · 이력 한 줄 추가' % newnum)


if __name__ == '__main__':
    main()
