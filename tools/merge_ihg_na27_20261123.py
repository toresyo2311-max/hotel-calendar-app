#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ IHG 북미·중남미 P1 27곳 → data/app/tab11_ihg.json 병합 (+ ① 호텔럭스 alsoIn 양방향)

원자료: 6번(@jin_6) 실측 `0-ihg-global-no6-p1-27.json`
        (2026-11-23 05:2x KST · 2026-12-01~2027-11-30 365일 · 현금 8,708칸 · 포인트 8,671칸)

기존 tab11_ihg.json(아시아·오세아니아 72 + 유럽 26 = 98곳, i01~i98)은 값·순서를 그대로 두고
뒤에 27곳을 i99~i125로 붙인다(미국 26 · 캐나다 1 — 뉴욕 5 · 로스앤젤레스 4 · 샌프란시스코 3 ·
워싱턴DC 3 · 시카고 2 · 마이애미 2 · 보스턴 2 · 시애틀 2 · 샌디에이고 1 · 호놀룰루 1 · 토론토 1 ·
뉴올리언스 1).

스키마는 기존과 똑같이 맞춘다:
  · brand      — 화면 태그·필터용 한글 브랜드명(자료의 '인디고'는 기존 표기 '호텔 인디고'로 정규화)
  · rates/points — {$d, $v} 압축 열, 값 없는 칸은 null(보간 금지)
  · cells      — {"rates": n, "points": n}

① 호텔럭스(tab1_vip.json 161곳) 전수 대조 — 코드·영문명·국문명·도시를 정규화해 맞춘 9쌍은
tab11 쪽 alsoIn 과 tab1 쪽 alsoIn 을 양방향으로 적고, data/master_db.json 의 lux 사본에도 같은 값을 적는다.
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # work/ 아래 저장소 → 워크스페이스 뿌리
SRC = os.path.join(WS, 'memory', 'clones', 'b61af69f-leehanjin7', 'pickle',
                   '2026-11-23-0525', 'received', '0-ihg-global-no6-p1-27.json')
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')
VIP = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

# ① 호텔럭스 ↔ ⑤ IHG 짝 — 2026-11-23 전수 대조(코드·영문명·국문명·도시)
#   뉴욕 2쌍(신규) + 기존 98곳 가운데 7쌍
PAIRS = [
    ('h122', 'i99',  'Intercontinental Times Square ↔ 인터컨티넨탈 뉴욕 타임스 스퀘어'),
    ('h152', 'i100', 'InterContinental New York Barclay ↔ 인터컨티넨탈 뉴욕 바클레이'),
    ('h27',  'i01',  'Grand InterContinental Seoul Parnas ↔ 인터컨티넨탈 그랜드 서울 파르나스'),
    ('h61',  'i12',  'Intercontinental The Strings ↔ 인터컨티넨탈 더 스트링스 도쿄'),
    ('h64',  'i13',  'Kimpton Shinjuku Tokyo ↔ 킴프턴 신주쿠 도쿄'),
    ('h15',  'i48',  'Kimpton Maa-Lai Bangkok ↔ 킴프턴 마라이 방콕'),
    ('h20',  'i54',  'InterContinental Danang Sun Peninsula ↔ 인터컨티넨탈 다낭 선 페닌슐라 리조트'),
    ('h115', 'i63',  'InterContinental Sydney ↔ 인터컨티넨탈 시드니'),
    ('h118', 'i65',  'Kimpton Margot Sydney ↔ 킴프턴 마고 시드니'),
]

BRAND_KO = {
    'IC': '인터컨티넨탈', 'VOCO': '보코', 'HIX': '홀리데이 인 익스프레스',
    'HI': '홀리데이 인', 'CP': '크라운 플라자', 'KIMPTON': '킴프턴',
    'INDIGO': '호텔 인디고', 'REGENT': '리젠트', 'VIGNETTE': '비네트 컬렉션',
    # 자료가 한글 브랜드명을 주는 경우의 정규화(기존 98곳 표기와 맞춘다)
    '인터컨티넨탈': '인터컨티넨탈', '킴프턴': '킴프턴', '킴튼': '킴프턴', '보코': '보코',
    '리젠트': '리젠트', '인디고': '호텔 인디고', '호텔 인디고': '호텔 인디고',
    '홀리데이 인 익스프레스': '홀리데이 인 익스프레스', '홀리데이 인': '홀리데이 인',
    '크라운 플라자': '크라운 플라자', '비네트 컬렉션': '비네트 컬렉션',
}


def numeric(v):
    return sum(1 for x in v if isinstance(x, (int, float)) and not isinstance(x, bool))


def norm(s):
    """코드·이름 대조용 정규화 — 소문자, 한글/영문/숫자만 남긴다."""
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def main():
    base = json.load(open(OUT, encoding='utf-8'))
    src = json.load(open(SRC, encoding='utf-8'))
    old = base['hotels']
    assert len(old) == 98, len(old)
    assert src['days'] == 365 and src['window'] == ['2026-12-01', '2027-11-30']
    assert src['counts'] == {'hotels': 27, 'cells': 19710, 'cash': 8708, 'points': 8671}, src['counts']

    old_cash = sum(h['cells']['rates'] for h in old)
    old_pts = sum(h['cells']['points'] for h in old)

    n = len(old)
    added = []
    for h in src['hotels']:
        n += 1
        brand = BRAND_KO.get(h['brand']) or BRAND_KO.get(h['brand_code']) or h['brand']
        rc = numeric(h['rates']['$v'])
        pc = numeric(h['points']['$v'])
        assert rc == h['cells']['rates'] and pc == h['cells']['points'], h['id']
        rec = {
            'id': 'i%02d' % n,
            'group': 'ihg',
            'code': h['code'],
            'brand': brand,
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
            'note': h.get('note') or '',
            'source': h.get('source') or '',
            'cells': {'rates': rc, 'points': pc},
        }
        added.append(rec)

    assert len(added) == 27
    assert added[0]['id'] == 'i99' and added[-1]['id'] == 'i125'
    assert added[0]['code'] == 'NYCHC' and added[1]['code'] == 'NYCHA'
    assert sum(h['cells']['rates'] for h in added) == 8708
    assert sum(h['cells']['points'] for h in added) == 8671

    hotels = old + added
    byid = {h['id']: h for h in hotels}

    # ⑤ IHG 쪽 alsoIn — 새로 붙인 키는 끝에 둔다(기존 값·순서는 그대로)
    for lux_id, ihg_id, label in PAIRS:
        h = byid[ihg_id]
        assert h.get('alsoIn') in (None, lux_id), (ihg_id, h.get('alsoIn'))
        h['alsoIn'] = lux_id

    base['hotels'] = hotels
    base['generated_at'] = '2026-11-23'
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    base['counts'] = {'hotels': len(hotels), 'cells': len(hotels) * 365,
                      'cash': cash, 'points': pts}
    assert cash == old_cash + 8708, (cash, old_cash)
    assert pts == old_pts + 8671, (pts, old_pts)
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(base, fp, ensure_ascii=False, separators=(',', ':'))

    print('tab11 hotels %d (신규 %d) · cells %d · cash %d · points %d'
          % (len(hotels), len(added), base['counts']['cells'], cash, pts))

    # ── ① 호텔럭스 쪽 alsoIn (배포본 + master 사본) ────────────────────────
    vip = json.load(open(VIP, encoding='utf-8'))
    cols = vip['hotels']['$t']
    ai = cols.index('alsoIn')
    rows = vip['hotels']['$r']
    lux_pos = {}
    for idx, row in enumerate(rows):
        lux_pos[row[cols.index('id')]] = idx
    changed = 0
    for lux_id, ihg_id, label in PAIRS:
        assert lux_id in lux_pos, lux_id
        row = rows[lux_pos[lux_id]]
        prev = row[ai]
        assert prev in ('$~', ihg_id), (lux_id, prev)
        if prev != ihg_id:
            row[ai] = ihg_id
            changed += 1
    with open(VIP, 'w', encoding='utf-8') as fp:
        json.dump(vip, fp, ensure_ascii=False, separators=(',', ':'))
        fp.write('\n')
    print('tab1_vip alsoIn %d행 갱신' % changed)

    master = json.load(open(MASTER, encoding='utf-8'))
    mchanged = 0
    for h in master['hotels']:
        if h.get('group') != 'lux':
            continue
        tgt = {lux: ihg for lux, ihg, _ in PAIRS}
        if h['id'] in tgt:
            assert h.get('alsoIn') in (None, tgt[h['id']]), (h['id'], h.get('alsoIn'))
            if h.get('alsoIn') != tgt[h['id']]:
                h['alsoIn'] = tgt[h['id']]
                mchanged += 1
    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    print('master_db lux alsoIn %d행 갱신' % mchanged)

    # ── 대조 확인 — 정규화한 영문명이 같은 짝이 위 9쌍 밖에 없는지 ─────────
    lux_en = {}
    for row in rows:
        d = dict(zip(cols, row))
        lux_en.setdefault(norm(d.get('english')), []).append(d['id'])
    pairs_lux = {l for l, _, _ in PAIRS}
    extra = []
    for h in hotels:
        key = norm(h['english'])
        for lux_id in lux_en.get(key, []):
            if lux_id not in pairs_lux and h.get('alsoIn') != lux_id:
                extra.append((h['id'], h['english'], lux_id))
    print('정규화 영문명이 같으나 연결하지 않은 짝:', extra if extra else '없음')


if __name__ == '__main__':
    main()
