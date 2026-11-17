#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""한국·일본 메리어트 22곳 → data/master_db.json `tab:"marriott"` 병합.

원본(2026-11-17 조사):
  /workspace/data-sources/marriott-korea/korea_marriott_2026_12_2027_11.csv (3,650행)
  /workspace/data-sources/marriott-japan/japan_marriott_2026_12_2027_11.csv (4,380행)
  각 행: hotel_id, hotel_name, date, cash_krw_tax_incl, points

사용법 (저장소 루트에서):
    python3 tools/import_marriott_kj.py --dry     # 파싱 결과·검증만 출력
    python3 tools/import_marriott_kj.py           # master_db.json 반영
    python3 tools/import_marriott_kj.py --json out.json

필드 규칙
  rates  : {date: 현금 KRW}            — Google 호텔 세금 포함 1박 최저
  points : {date: 아워드 포인트}        — roame.travel 아워드 캘린더(원 단위 정확값)
  code   : roame 지점 코드
  alsoIn : ① HoteLux 탭에 같은 호텔이 이미 있는 경우 그 id (중복 표시 방지용 교차 참조)
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC_KR = '/workspace/data-sources/marriott-korea/korea_marriott_2026_12_2027_11.csv'
SRC_JP = '/workspace/data-sources/marriott-japan/japan_marriott_2026_12_2027_11.csv'

CASH_SRC = 'Google 호텔(세금 포함 1박 최저) · 2026-11-17 조회'
POINT_SRC = 'roame.travel 아워드 캘린더(2026-11-17 기준)'

# (id, 브랜드, 도시, region, 한국어 이름, 영문명, csv hotel_id, roame 코드, 원본 파일, ①탭 같은 호텔 id)
SPEC = [
    # ── 한국 10곳 ─────────────────────────────────────────────────
    ('k01', 'JW 메리어트', '서울', '한국', 'JW 메리어트 호텔 서울', 'JW Marriott Hotel Seoul',
     'jw_seoul', 'SELJW', 'korea', 'h26'),
    ('k02', 'JW 메리어트', '서울', '한국', 'JW 메리어트 동대문 스퀘어 서울',
     'JW Marriott Dongdaemun Square Seoul', 'jw_dongdaemun', 'SELDP', 'korea', 'h25'),
    ('k03', 'JW 메리어트', '제주', '한국', 'JW 메리어트 제주 리조트 & 스파',
     'JW Marriott Jeju Resort & Spa', 'jw_jeju', 'CJUJU', 'korea', None),
    ('k04', '럭셔리 컬렉션', '서울', '한국', '조선 팰리스 서울 강남, 럭셔리 컬렉션 호텔',
     'Josun Palace, a Luxury Collection Hotel, Seoul Gangnam', 'josun_palace', 'SELLC', 'korea', 'h36'),
    ('k05', '웨스틴', '서울', '한국', '웨스틴 조선 서울', 'The Westin Josun Seoul',
     'westin_josun_seoul', 'SELWI', 'korea', 'h35'),
    ('k06', '웨스틴', '부산', '한국', '웨스틴 조선 부산', 'The Westin Josun Busan',
     'westin_josun_busan', 'PUSWI', 'korea', None),
    ('k07', '메리어트', '대구', '한국', '대구 메리어트 호텔', 'Daegu Marriott Hotel',
     'daegu_marriott', 'TAEMC', 'korea', None),
    ('k08', '오토그래프 컬렉션', '서울', '한국', '라이즈 오토그래프 컬렉션 서울',
     'RYSE, Autograph Collection', 'ryse_autograph', 'SELSA', 'korea', None),
    ('k09', '메리어트 이그제큐티브 아파트먼트', '서울', '한국',
     '여의도 파크 센터, 서울 - 메리어트 이그제큐티브 아파트먼트',
     'Yeouido Park Centre, Seoul - Marriott Executive Apartments', 'yeouido_mea', 'SELER',
     'korea', None),
    ('k10', '르메르디앙', '서울', '한국', '르메르디앙 서울 명동', 'Le Méridien Seoul Myeongdong',
     'le_meridien_myeongdong', 'SELMM', 'korea', None),
    # ── 일본 12곳 ─────────────────────────────────────────────────
    ('j01', '리츠칼튼', '도쿄', '일본', '더 리츠칼튼 도쿄', 'The Ritz-Carlton, Tokyo',
     'ritz_tokyo', 'TYORZ', 'japan', 'h51'),
    ('j02', '리츠칼튼', '교토', '일본', '더 리츠칼튼 교토', 'The Ritz-Carlton, Kyoto',
     'ritz_kyoto', 'UKYRZ', 'japan', None),
    ('j03', '리츠칼튼', '오사카', '일본', '더 리츠칼튼 오사카', 'The Ritz-Carlton, Osaka',
     'ritz_osaka', 'OSARZ', 'japan', None),
    ('j04', '리츠칼튼', '후쿠오카', '일본', '더 리츠칼튼 후쿠오카', 'The Ritz-Carlton, Fukuoka',
     'ritz_fukuoka', 'FUKRZ', 'japan', 'h09'),
    ('j05', '리츠칼튼', '오키나와', '일본', '더 리츠칼튼 오키나와', 'The Ritz-Carlton, Okinawa',
     'ritz_okinawa', 'OKARZ', 'japan', None),
    ('j06', '리츠칼튼', '닛코', '일본', '더 리츠칼튼 닛코', 'The Ritz-Carlton, Nikko',
     'ritz_nikko', 'TYONZ', 'japan', None),
    ('j07', '세인트레지스', '오사카', '일본', '세인트 레지스 오사카', 'The St. Regis Osaka',
     'st_regis_osaka', 'OSAXR', 'japan', None),
    ('j08', 'W', '오사카', '일본', 'W 오사카', 'W Osaka', 'w_osaka', 'OSAOW', 'japan', None),
    ('j09', 'JW 메리어트', '나라', '일본', 'JW 메리어트 호텔 나라', 'JW Marriott Hotel Nara',
     'jw_nara', 'OSAJW', 'japan', None),
    ('j10', '에디션', '도쿄', '일본', '더 도쿄 에디션 도라노몬', 'The Tokyo EDITION, Toranomon',
     'edition_toranomon', 'TYOET', 'japan', 'h49'),
    ('j11', '에디션', '도쿄', '일본', '더 도쿄 에디션 긴자', 'The Tokyo EDITION, Ginza',
     'edition_ginza', 'TYOEB', 'japan', 'h48'),
    ('j12', '럭셔리 컬렉션', '도쿄', '일본', '더 프린스 갤러리 도쿄 기오이초',
     'The Prince Gallery Tokyo Kioicho, a Luxury Collection Hotel',
     'prince_gallery_kioicho', 'TYOLC', 'japan', 'h45'),
]

FILES = {
    'korea': ('marriott-korea/korea_marriott_2026_12_2027_11.csv', SRC_KR),
    'japan': ('marriott-japan/japan_marriott_2026_12_2027_11.csv', SRC_JP),
}


def read_csv(path):
    """/workspace CSV → {hotel_id: {'name':…, 'cash': {date: int|None}, 'points': {date: int|None}}}"""
    import csv
    import collections
    out = collections.OrderedDict()
    with open(path, encoding='utf-8-sig', newline='') as fp:
        for row in csv.DictReader(fp):
            hid = row['hotel_id'].strip()
            e = out.setdefault(hid, {'name': row['hotel_name'].strip(), 'cash': {}, 'points': {}})
            date = row['date'].strip()
            cash = row['cash_krw_tax_incl'].strip().replace(',', '')
            pts = row['points'].strip().replace(',', '')
            e['cash'][date] = int(cash) if cash else None
            e['points'][date] = int(pts) if pts else None
    return out


def build():
    data = {k: read_csv(p) for k, (_, p) in FILES.items()}
    hotels = []
    for hid, brand, city, region, name, eng, csv_id, code, src, also in SPEC:
        e = data[src].get(csv_id)
        if not e:
            raise SystemExit('CSV 에 %s 가 없습니다.' % csv_id)
        cash = {d: v for d, v in sorted(e['cash'].items()) if v is not None}
        pts = {d: v for d, v in sorted(e['points'].items()) if v is not None}
        # 다른 탭과 같은 규칙: 365일 키를 모두 두고 값이 없는 날은 None
        all_days = sorted(e['cash'])
        cash = {d: cash.get(d) for d in all_days}
        pts = {d: pts.get(d) for d in all_days}
        cash_last = max([d for d, v in cash.items() if v is not None], default=None)
        pts_last = max([d for d, v in pts.items() if v is not None], default=None)
        # 아워드 재고 없음(=포인트 캘린더 범위 안인데 값이 없는 날)
        gap = 0
        if pts_last:
            from datetime import date, timedelta
            d0, d1 = date(2026, 12, 1), date.fromisoformat(pts_last)
            gap = (d1 - d0).days + 1 - sum(1 for v in pts.values() if v is not None)
        notes = ['roame %s · 아워드 포인트 %d일/365' % (code, sum(1 for v in pts.values() if v is not None))]
        if pts_last:
            notes.append('포인트 캘린더 마지막 %s 이후 미공개' % pts_last)
            if gap:
                notes.append('범위 내 아워드 재고 없음 %d일' % gap)
        else:
            notes.append('roame 아워드 데이터 0건(포인트 미공개)')
        notes.append('현금 %d일/365' % sum(1 for v in cash.values() if v is not None))
        if cash_last and cash_last < '2027-10-20':
            notes.append('Google 예약창 밖(%s 이후 미공개)' % cash_last)
        hotel = {
            'id': hid,
            'group': 'marriott',
            'brand': brand,
            'city': city,
            'region': region,
            'name': name,
            'english': eng,
            'promotion': '%s · %s' % (POINT_SRC, '포인트 %d일 확보' % sum(1 for v in pts.values() if v is not None)
                                     if pts_last else '포인트 자료 없음'),
            'source': '%s / %s · %s' % (CASH_SRC, POINT_SRC, FILES[src][0]),
            'code': code,
            'rates': cash,
            'points': pts,
            'note': ' · '.join(notes),
        }
        if also:
            hotel['alsoIn'] = also
            hotel['alsoInLabel'] = '① HoteLux VIP 탭에도 수록'
        hotels.append((hotel, sum(1 for v in cash.values() if v is not None),
                       sum(1 for v in pts.values() if v is not None), gap))
    return hotels


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    built = build()
    print('%-4s %-6s %-8s %-28s %5s %5s %5s' % ('id', '지역', '브랜드', '호텔', '현금', '포인트', '재고X'))
    for h, nc, np_, gap in built:
        print('%-4s %-6s %-8s %-28s %5d %5d %5d' % (h['id'], h['region'], h['brand'], h['name'], nc, np_, gap))
    tc = sum(sum(1 for v in h['rates'].values() if v is not None) for h, *_ in built)
    tp = sum(sum(1 for v in h['points'].values() if v is not None) for h, *_ in built)
    print('\n합계 %d곳 · 현금 %d칸 · 포인트 %d칸' % (len(built), tc, tp))
    exp = (22, 6800, 6629)
    if (len(built), tc, tp) != exp:
        print('!! 기대치(22곳·6800·6629)와 다릅니다: %s' % ((len(built), tc, tp),))
        return 1
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as fp:
            json.dump([h for h, *_ in built], fp, ensure_ascii=False, indent=1)
        print('wrote', a.json)
    if a.dry:
        return 0

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import master_db  # noqa: E402

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    keep = [h for h in master['hotels']
            if not (h.get('group') == 'marriott' and h['id'][0] in 'kj')]
    ids = {h['id'] for h in keep}
    clash = [h['id'] for h, *_ in built if h['id'] in ids]
    if clash:
        raise SystemExit('id 충돌: %s' % clash)
    master['hotels'] = keep + [h for h, *_ in built]
    master['sources'] = [s for s in master.get('sources', [])
                         if not s.startswith('marriott-korea/') and not s.startswith('marriott-japan/')]
    master['sources'] += [FILES['korea'][0], FILES['japan'][0]]
    st = master_db.stats_of(master, master['flights'])
    master['counts'] = {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na',
                                           'stayplus', 'routes', 'deals')}
    master['built'] = '2026-11-17'
    tag = '2026-11-17 15:10 KST ⑤ 메리어트 한국 10 + 일본 12곳(현금·roame 포인트) 수집 반영'
    ext = master.get('extended') or ''
    if '한국 10 + 일본 12' not in ext:
        master['extended'] = (ext + ' / ' + tag).strip(' /')
    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    print('master_db.json 갱신 — 호텔 %d곳 %s' % (len(master['hotels']), master['counts']['tabs']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
