#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 아코르 탭 — 동남아(태국·베트남·싱가포르) 196곳 × 365일 실측 병합 (2026-11-22).

입력 (2·3·4·5·6번 담당, 총 196곳 = 태국 102 · 베트남 55 · 싱가포르 39)
  · 2번 40곳  downloads/sea_accor_measured_no2_2026-11-21.json
  · 3번 39곳  memory/clones/2e8f9e24-hanjinlee4/pickle/2026-11-22-0026/received/
              1-sea_accor_no3_full_2026-12_2027-11.json
  · 4번 39곳  memory/clones/06130525-jin489/pickle/2026-11-21-2120/received/
              0-2026-11-21_sea-accor-no4-merged.json (회원가)
              1-2026-11-21_sea-accor-no4-merged-nonmember.json (비회원가 — 교차 확인용)
  · 5번 39곳  memory/clones/f0ee2d96-jin_5/pickle/2026-11-21-2144/received/
              0-2026-11-21-accor-sea-39.merge.json
  · 6번 39곳  memory/clones/146dd4d1-jin_6/pickle/2026-11-21-2056/received/
              0-accor-sea-39hotels-2026-12-2027-11.json
  · 메타 정본 downloads/sea_accor_directory_2026-11-20.json (196곳 이름·브랜드·등급·도시·국가)
  · 배분 정본 downloads/sea_accor_split_no{2..6}_2026-11-21.json (담당 호텔 ID 대조)

요금 기준 통일
  다섯 조의 계열을 맞춰 **세금 포함 KRW · 성인 2인 1실 1박 최저 표시가**로 통일했다.
    · 2번 = 세금 포함(rates) · 비로그인 공개 최저가(회원가 포함) — 파일 tax/limitations 문구
    · 3번 = rates(표시가, hideMemberRate=false = 회원 요금 포함) · rates_public·rates_all_card 도 있으나
             기존 ③·다른 조와 같은 '표시 최저가' 계열인 rates 를 쓴다
    · 4번 = member_lowest(달력 기본 요금) 계열. nonmember 계열도 같은 호텔·날짜에 있어
             회원가 = 비회원가 × 0.9505(5% 할인)임을 확인했다(교차 확인용, 값은 member 계열)
    · 5번 = 비로그인 표시 최저가(세금 포함 KRW)
    · 6번 = 비회원 공개 최저가(hideMemberRate=true). 이 조만 회원 요금이 빠져 있어
             같은 날짜의 회원가보다 약 5% 높다 — 호텔 note·promotion 에 그대로 적는다
  즉 196곳 모두 '세금 포함'으로 맞았고, 157곳은 ALL 회원 요금이 포함된 표시 최저가,
  39곳(6번)만 비회원 공개 최저가다. 회원가를 곱해 지어내지 않았다.

id
  기존 ③ 은 `id = 'a' + 아코르 코드`(해외 21곳) · `'d' + 코드`(국내 30곳)다.
  신규 196곳은 코드가 겹칠 위험을 없애려고 **a52~a247** 연번을 준다(기존 id 와 충돌 0).
  코드는 `code` 칸에 그대로 두고, 예약 링크·호텔럭스 연결은 code 로 찾는다.

배치
  국내 30곳 → 동남아 196곳(태국 → 베트남 → 싱가포르, 디렉토리 순서) → 한·중·일 21곳.

이중 연결(상시 지침)
  ① 호텔럭스 161곳에 같은 호텔이 있는 7곳은 alsoIn 을 양방향으로 채운다
  (① 쪽 alsoIn = ③ id, ③ 쪽 alsoIn = ① id). ① 쪽 호텔럭스 ID(ref_id)는 이미 ① 자료에 있는 값이다.

값은 새 카드만 더한다 — 기존 ③ 51곳·②·①·④ 는 한 칸도 건드리지 않고, 다르면 중단한다.
이어서 `python3 tools/master_db.py refresh && python3 tools/master_db.py inject`.
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
WS = '/workspace'

DIRECTORY = WS + '/downloads/sea_accor_directory_2026-11-20.json'
SPLIT = WS + '/downloads/sea_accor_split_no%d_2026-11-21.json'
SRC = {
    'no2': WS + '/downloads/sea_accor_measured_no2_2026-11-21.json',
    'no3': WS + '/memory/clones/2e8f9e24-hanjinlee4/pickle/2026-11-22-0026/received/'
                '1-sea_accor_no3_full_2026-12_2027-11.json',
    'no4': WS + '/memory/clones/06130525-jin489/pickle/2026-11-21-2120/received/'
                '0-2026-11-21_sea-accor-no4-merged.json',
    'no4n': WS + '/memory/clones/06130525-jin489/pickle/2026-11-21-2120/received/'
                 '1-2026-11-21_sea-accor-no4-merged-nonmember.json',
    'no5': WS + '/memory/clones/f0ee2d96-jin_5/pickle/2026-11-21-2144/received/'
                '0-2026-11-21-accor-sea-39.merge.json',
    'no6': WS + '/memory/clones/146dd4d1-jin_6/pickle/2026-11-21-2056/received/'
                '0-accor-sea-39hotels-2026-12-2027-11.json',
}
WIN_START = '2026-12-01'
WIN_END = '2027-11-30'

# 담당 조 — (파일 키, 요금 계열 이름, 남길 별칭)
TEAM = {'no2': ('no2', 'rates', '2번'), 'no3': ('no3', 'rates', '3번'),
        'no4': ('no4', 'prices', '4번'), 'no5': ('no5', 'rates', '5번'),
        'no6': ('no6', 'prices', '6번')}
TEAM_BASIS = {
    'no2': '세금 포함 KRW · 비로그인 공개 최저가(ALL 회원 요금 포함)',
    'no3': '세금 포함 KRW · 표시 최저가(ALL 회원 요금 포함)',
    'no4': '세금 포함 KRW · 달력 기본 회원 최저가',
    'no5': '세금 포함 KRW · 비로그인 공개 최저가(ALL 회원 요금 포함)',
    'no6': '세금 포함 KRW · 비회원 공개 최저가(회원 요금 미포함)',
}
COUNTRY = {'TH': '태국', 'VN': '베트남', 'SG': '싱가포르'}

# 도시가 이름에 없어 디렉토리에서 빈칸이던 8곳 — 호텔 공식 주소(아코르 호텔 페이지)로 확인한 도시
CITY_FIX = {
    'C2B8': ('푸켓', '라구나 푸켓 단지 안(공식 주소: Laguna, Phuket)'),
    'B9E6': ('푸켓', '파통 비치(공식 주소: Patong, Phuket)'),
    'C561': ('나트랑', '공식 주소 62-65 Pham Van Dong, Nha Trang'),
    'C1H4': ('호짬', '호짬(Ho Tram) 해변'),
    'B1Y7': ('옌투', '옌투 사찰 경내(우옹비 · 꽝닌)'),
    'C376': ('뚜이호아', '뚜이호아(Tuy Hoa) · 푸옌성'),
    'C678': ('푸꾸옥', '푸꾸옥 톰 섬(2027년 1분기 개관 예정)'),
    'C3Q7': ('싱가포르', '만다이 야생동물공원 단지(싱가포르)'),
}

# ① 호텔럭스에 같은 호텔이 있는 7곳 — ③ 코드 → (① id, ① 에 적힌 한글 이름)
LUX_TWIN = {
    'C1G0': ('h14', '페어몬트 방콕 수쿰윗'),
    'A5G8': ('h105', '페어몬트 싱가포르'),
    'A5E1': ('h81', '래플스 싱가포르'),
    'B5Q2': ('h80', '래플스 센토사 싱가포르'),
    'A152': ('h92', '소피텔 싱가포르 시티 센터'),
    '9474': ('h91', '소피텔 싱가포르 센토사 리조트 & 스파'),
    'C3Q7': ('h85', '만다이 레인포레스트 리조트 바이 반얀트리'),
}

EXT_ADD = (' / 2026-11-22 KST ③ 아코르 동남아 196곳(태국 102 · 베트남 55 · 싱가포르 39) '
           '× 365일 실측 병합 — 세금 포함 KRW 1박 최저 표시가로 기준 통일(157곳 ALL 회원 요금 포함 · '
           '6번 담당 39곳은 비회원 공개 최저가), ③ 51→247곳, ① 호텔럭스와 겹치는 7곳 alsoIn 양방향 연결')
SRC_FILES = [
    '동남아 아코르 40곳 365일 최저요금 실측 — 2번 담당 (2026-11-21)',
    '동남아 아코르 39곳 365일 실측 — 3번 담당 (2026-11-21~22)',
    '동남아 아코르 39곳 365일 실측(회원가·비회원가 2계열) — 4번 담당 (2026-11-21)',
    '동남아 아코르 39곳 365일 실측 — 5번 담당 (2026-11-21)',
    '동남아 아코르 39곳 365일 실측(비회원 공개 최저가) — 6번 담당 (2026-11-21)',
]


def load(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def days_of(a, b):
    d, out = dt.date.fromisoformat(a), []
    while d <= dt.date.fromisoformat(b):
        out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def main():
    master = load(MASTER)
    directory = load(DIRECTORY)['hotels']
    days = days_of(WIN_START, WIN_END)
    if len(days) != 365:
        sys.exit('날짜 창이 365일이 아닙니다')

    # ---- 다섯 조 파일 — 담당 목록·날짜 창·중복 확인
    series = {}
    for key, path in SRC.items():
        if key == 'no4n':
            continue
        hotels = load(path)['hotels']
        rows = {}
        for h in hotels:
            field = TEAM[key][1]
            rates = h.get(field) or {}
            if list(rates.keys()) != days:
                sys.exit('%s %s 날짜 창/순서가 다릅니다 (%d칸)' % (key, h['accor_id'], len(rates)))
            for d, v in rates.items():
                if v is not None and (not isinstance(v, int) or v <= 0):
                    sys.exit('%s %s %s 값 이상: %r' % (key, h['accor_id'], d, v))
            rows[h['accor_id']] = h
        series[key] = rows
        print('%s %d곳 · 365칸 확인' % (key, len(rows)))

    # 4번 비회원 계열 — 같은 날짜·같은 호텔에서 회원가 = 비회원가 × 0.95 임을 확인(값은 쓰지 않음)
    nonmem = {h['accor_id']: h['prices'] for h in load(SRC['no4n'])['hotels']}
    ratios = []
    for cid, h in series['no4'].items():
        for d, v in h['prices'].items():
            nv = nonmem.get(cid, {}).get(d)
            if isinstance(v, int) and isinstance(nv, int) and nv:
                ratios.append(v / float(nv))
    ratios.sort()
    med = ratios[len(ratios) // 2]
    print('4번 회원가/비회원가 중위 %.4f (%d쌍)' % (med, len(ratios)))
    if not 0.90 <= med <= 1.00:
        sys.exit('4번 두 계열 비율이 예상(≈0.95)과 다릅니다 — 기준 확인 필요')

    # ---- 디렉토리 196곳과 담당 조 대조
    if len(directory) != 196:
        sys.exit('디렉토리 호텔 수 %d (196 이어야 함)' % len(directory))
    owner = {}
    for key, rows in series.items():
        for cid in rows:
            if cid in owner:
                sys.exit('두 조에 같은 호텔 %s (%s·%s)' % (cid, owner[cid], key))
            owner[cid] = key
    for n in (2, 3, 4, 5, 6):
        want = {h['accor_id'] for h in load(SPLIT % n)['hotels']}
        have = {cid for cid, k in owner.items() if k == 'no%d' % n}
        if want != have:
            sys.exit('no%d 배분 목록과 실측 파일이 다릅니다 (빠짐 %s / 더있음 %s)'
                     % (n, sorted(want - have)[:5], sorted(have - want)[:5]))
    missing = [h['accor_id'] for h in directory if h['accor_id'] not in owner]
    if missing:
        sys.exit('실측이 없는 호텔 %d곳: %s' % (len(missing), missing[:5]))
    print('디렉토리 196곳 = 다섯 조 실측 196곳 (중복 0)')

    # ---- 기존 ③ 은 그대로 — 손상 확인용 스냅숏
    dom_old = [h for h in master['hotels'] if h.get('group') == 'domestic']
    before = json.dumps(dom_old, ensure_ascii=False, sort_keys=True)
    byid = {h['id']: h for h in master['hotels']}
    korean = [h for h in dom_old if h['id'].startswith('d')]
    overseas = [h for h in dom_old if h['id'].startswith('a')]
    if len(korean) != 30 or len(overseas) != 21:
        sys.exit('기존 ③ 구성이 다릅니다 (국내 %d · 해외 %d)' % (len(korean), len(overseas)))

    # ---- 196곳 행 만들기 (a52~a247)
    new_rows = []
    for i, meta in enumerate(directory):
        cid = meta['accor_id']
        key = owner[cid]
        src = series[key][cid]
        hid = 'a%d' % (52 + i)
        cc = meta['country_code']
        city = meta['city'] or CITY_FIX[cid][0]
        name = meta['name']
        english = (src.get('english') or '').strip()
        twin = LUX_TWIN.get(cid)
        if twin:
            name, english = twin[1], (english or meta['name'])
        basis = TEAM_BASIS[key]
        promo = ('세금 포함 KRW 1박 최저 표시가 · ALL 회원 요금 포함'
                 if key != 'no6' else '세금 포함 KRW 1박 최저 표시가 · 비회원 공개 요금')
        source = ('동남아 아코르 365일 실측 2026-11-21 KST · %s 담당(%s) · 아코르 공식 예약 사이트 요금 API · '
                  '%s · 성인 2인 1실 1박 · 요금 없는 날은 빈칸(매진·미판매·미오픈)' % (TEAM[key][2], key, basis))
        note_bits = []
        if key == 'no6':
            note_bits.append('6번 담당분은 비회원 공개 최저가라 ALL 회원 로그인 시 약 5%% 낮은 요금이 보일 수 있습니다')
        if meta['city'] == '':
            note_bits.append('도시 표기는 호텔 공식 주소로 확인: ' + CITY_FIX[cid][1])
        if twin:
            note_bits.append('① 호텔럭스에도 있는 호텔 — 두 예약처 비교 가능')
        row = {'id': hid, 'group': 'domestic', 'city': city, 'name': name,
               'english': english, 'brand': meta['brand'], 'region': COUNTRY[cc],
               'promotion': promo, 'code': cid, 'source': source,
               'rates': dict(src[TEAM[key][1]])}
        if note_bits:
            row['note'] = ' · '.join(note_bits)
        if twin:
            row['alsoIn'] = twin[0]
        new_rows.append(row)

    # ---- 이름 중복(alsoIn 없이 같은 이름) 점검
    seen = {}
    for h in master['hotels']:
        seen.setdefault((h.get('english') or h['name']).strip().lower(), h['id'])
    for r in new_rows:
        k = (r['english'] or r['name']).strip().lower()
        if k in seen and not r.get('alsoIn'):
            sys.exit('이름 중복(alsoIn 없음): %s ↔ %s (%s)' % (seen[k], r['id'], k))

    # ---- ① 쪽 alsoIn 채우기 (양방향)
    for r in new_rows:
        if not r.get('alsoIn'):
            continue
        lux = byid[r['alsoIn']]
        if lux.get('group') != 'lux':
            sys.exit('%s 는 ① 호텔럭스가 아닙니다' % r['alsoIn'])
        if lux.get('alsoIn') and lux['alsoIn'] != r['id']:
            sys.exit('① %s 에 이미 다른 alsoIn %s' % (lux['id'], lux['alsoIn']))
        lux['alsoIn'] = r['id']
        print('이중 연결 %s(%s) ↔ ① %s(%s)' % (r['id'], r['name'], lux['id'], lux['name']))

    # ---- 호텔 배열 재구성: 국내 30 → 동남아 196 → 한·중·일 21
    # 기존 순서에서 ③ 은 통째로 빼고, ③ 이 있던 자리에 새 순서를 끼워 넣는다
    out, inserted = [], False
    for h in master['hotels']:
        if h.get('group') == 'domestic':
            if not inserted:
                out.extend(korean)
                out.extend(new_rows)
                out.extend(overseas)
                inserted = True
            continue
        out.append(h)
    if not inserted:
        out.extend(korean)
        out.extend(new_rows)
        out.extend(overseas)
    master['hotels'] = out

    # 기존 ③ 51곳이 값 하나도 바뀌지 않았는지
    after = [h for h in master['hotels'] if h.get('group') == 'domestic' and h['id'] in byid]
    after = [h for h in after if h['id'] in {x['id'] for x in dom_old}]
    if json.dumps(sorted(after, key=lambda x: x['id']), ensure_ascii=False, sort_keys=True) != \
            json.dumps(sorted(dom_old, key=lambda x: x['id']), ensure_ascii=False, sort_keys=True):
        sys.exit('기존 ③ 51곳이 바뀌었습니다 — 중단')

    if EXT_ADD not in (master.get('extended') or ''):
        master['extended'] = (master.get('extended') or '') + EXT_ADD
    for s in SRC_FILES:
        if s not in master['sources']:
            master['sources'].append(s)

    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')

    # ---- 보고
    per = {}
    for r in new_rows:
        per.setdefault(r['region'], []).append(r)
    print('\n③ 아코르 %d곳 = 국내 %d + 동남아 %d + 한·중·일 %d'
          % (len(korean) + len(new_rows) + len(overseas), len(korean), len(new_rows), len(overseas)))
    for k, v in per.items():
        vals = [x for r in v for x in r['rates'].values() if isinstance(x, int)]
        print('  %s %d곳 · 요금 %d/%d칸 · 최저 %s원' % (k, len(v), len(vals), len(v) * 365,
                                                       format(min(vals), ',')))
    priced = sum(1 for r in new_rows for v in r['rates'].values() if isinstance(v, int))
    print('  동남아 196곳 요금 %d칸 / %d칸 (%.1f%%)' % (priced, 196 * 365, 100.0 * priced / (196 * 365)))
    print('  id %s ~ %s' % (new_rows[0]['id'], new_rows[-1]['id']))
    print('  이중 연결 7곳 · 이름 정렬 확인 완료')


if __name__ == '__main__':
    main()
