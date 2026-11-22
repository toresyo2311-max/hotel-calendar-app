#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 유럽(서유럽·남유럽) P1 26곳 → data/app/tab11_ihg.json 병합

원자료: 3번(@jin_3) 실측 `0-ihg_eu_p1_no3_26.json`
        (2026-11-23 05:16 KST · 2026-12-01~2027-11-30 365일 · 현금 8,151칸 · 포인트 7,619칸)

기존 tab11_ihg.json(아시아·오세아니아 72곳, i01~i72)은 값·순서를 그대로 두고
뒤에 26곳을 i73~i98로 붙인다. 스키마는 기존과 똑같이 맞춘다:
  · brand      — 화면 태그·필터용 한글 브랜드명(자료는 코드라 build_ihg_tab.py 의 BRAND_KO 로 옮긴다)
  · rates/points — {$d, $v} 압축 열, 값 없는 칸은 null(보간 금지)
  · cells      — {"rates": n, "points": n} (기존 72곳과 같은 키 이름)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))  # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', '2e8f9e24-hanjinlee4', 'pickle',
                   '2026-11-23-0516', 'received', '0-ihg_eu_p1_no3_26.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')

BRAND_KO = {
    'IC': '인터컨티넨탈', 'VOCO': '보코', 'HIX': '홀리데이 인 익스프레스',
    'HI': '홀리데이 인', 'CP': '크라운 플라자', 'KIMPTON': '킴프턴',
    'INDIGO': '호텔 인디고', 'REGENT': '리젠트', 'VIGNETTE': '비네트 컬렉션',
}


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 72, len(old)

    n = len(old)
    added = []
    for h in src['hotels']:
        n += 1
        code = h['brand']
        note = h.get('note')
        if not note:
            c = numeric(h['rates']['$v'])
            p = numeric(h['points']['$v'])
            note = ('현금 %d일 / 포인트 %d일 실측(2026-12-01~2027-11-30). '
                    '값 없는 날 = 해당 날짜 판매 재고·리워드 재고 없음. '
                    '2027-11-07~11-30은 예약창 미오픈(전부 null).' % (c, p))
        added.append({
            'id': 'i%02d' % n,
            'group': 'ihg',
            'code': h['code'],
            'brand': BRAND_KO.get(code, code),
            'brand_code': h['brand_code'],
            'brand_key': h['brand_key'],
            'brand_path': h['brand_path'],
            'region': h['region'],
            'city': h['city'],
            'country': h['country'],
            'name': h['name'],
            'english': h['english'],
            'rates': h['rates'],
            'points': h['points'],
            'note': note,
            'source': h['source'],
            'cells': {'rates': numeric(h['rates']['$v']), 'points': numeric(h['points']['$v'])},
        })

    hotels = old + added
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    base['hotels'] = hotels
    base['generated_at'] = '2026-11-23'
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    json.dump(base, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    print('hotels %d (신규 %d) · cells %d · cash %d · points %d'
          % (len(hotels), len(added), base['counts']['cells'], cash, pts))
    print('신규 ids %s ~ %s' % (added[0]['id'], added[-1]['id']))
    assert len(added) == 26
    assert cash - 23807 == 8151, cash - 23807
    assert pts - 22587 == 7619, pts - 22587


if __name__ == '__main__':
    main()
