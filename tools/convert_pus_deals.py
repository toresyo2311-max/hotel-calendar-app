#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑥ 땡처리 · 부산 출발 — 외부 수집본(집계 JSON·CSV)을 앱 스키마(team-busan/pus-deals/1)로 변환한다.

    python3 tools/convert_pus_deals.py --out ../../data-sources/flights-ttang/normalized-2026-11-19.json \\
        --aggregate ../../data-sources/flights-ttang/pus_tikitikit_2026-11-19.json \\
        --ybtour    ../../data-sources/flights-ttang/ybtour_pus_discount_flights.csv

변환 규칙
  · 같은 항공편(도착공항+출발일+귀국일+항공사)은 **한 줄**로 합치고 가장 싼 값을 남긴다(같으면 예약 직링크 우선순위).
  · 공급사 이름은 결과에 넣지 않는다. 비고에 섞여 있으면 지운다(화면 노출 금지).
  · 예약 링크가 확인되지 않은 행(예약 불가)은 목록에서 빼고 몇 건인지만 보고한다.
"""
import argparse
import csv
import json
import os
import re
import sys
import urllib.parse

REGION_FIX = {'기타': '중국'}            # 항주(HGH) 등 지역 표기가 '기타'인 중국 도시
SUPPLIER_BAN = ('노랑풍선', '모두투어', '하나투어', '땡처리닷컴', '트립닷컴', '티키티켓',
                'tikitikit', 'ybtour', 'modetour', 'ttang', 'hanatour', 'trip.com')
# 같은 값이면 공식 예약 페이지를 먼저 쓴다(집계 사이트 링크보다 정확)
HOST_RANK = ('fly.ybtour.co.kr', 'www.modetour.com', 'www.hanatour.com', 'mm.ttang.com', 'kr.trip.com')
# 공급사 → 채널 라벨(공동구매 = 여행사 공동구매·할인항공, 특가 = 땡처리·집계 목록)
SRC_OF = {'modetour': 'g', 'hanatour': 'g', 'ybtour': 'g', 'ttang': 't', 'tripcom': 't'}


def clean(text):
    if not text:
        return ''
    t = str(text).strip()
    for w in SUPPLIER_BAN:
        t = re.sub(re.escape(w), '', t, flags=re.I)
    return re.sub(r'\s{2,}', ' ', t).strip(' ,·')


def seats_of(v):
    if v is None:
        return None
    m = re.search(r'(\d+)\s*석', str(v))
    return int(m.group(1)) if m else None


def host_rank(url):
    for i, h in enumerate(HOST_RANK):
        if h in url:
            return i
    return len(HOST_RANK)


def fix_link(url, out, back):
    """모두투어 검색 링크의 날짜를 상품 날짜로 맞춘다(원본은 귀국일이 출발+1일로 고정돼 있었다).

    상품 상세 직링크가 아니라 권역·도시·출발~귀국 날짜가 박힌 검색 링크이므로, 주소의 다른 값은
    그대로 두고 `query` 안의 departureDate / arrivalDate 만 바로잡는다.
    """
    if 'modetour.com' not in url:
        return url
    m = re.search(r'([?&]query=)([^&]+)', url)
    if not m:
        return url
    try:
        q = json.loads(urllib.parse.unquote(m.group(2)))
    except Exception:                                   # noqa: BLE001 - 형식이 다르면 손대지 않는다
        return url
    if not isinstance(q, dict):
        return url
    q['departureDate'] = out
    q['arrivalDate'] = back
    enc = urllib.parse.quote(json.dumps(q, ensure_ascii=False, separators=(',', ':')), safe='')
    return url[:m.start(2)] + enc + url[m.end(2):]


def link_note(url):
    if 'modetour.com' in url:
        return '검색 링크(권역·도시·날짜)'
    if 'ttang.com' in url:
        return '목록 링크(출발일 기준)'
    return ''


def key_of(d):
    return (d['code'], d['out'], d['back'], d['airline'])


def add(bucket, deal, stats):
    k = key_of(deal)
    old = bucket.get(k)
    if old is None:
        bucket[k] = deal
        stats['added'] += 1
        return
    if deal['price'] < old['price']:
        bucket[k] = deal
        stats['cheaper'] += 1
    elif deal['price'] == old['price'] and host_rank(deal['url']) < host_rank(old['url']):
        bucket[k] = deal
        stats['relinked'] += 1
    else:
        stats['dupe'] += 1
    # 최소 인원·비고는 더 자세한 쪽을 남긴다
    cur = bucket[k]
    if not cur.get('minPax') or cur['minPax'] <= 1:
        cur['minPax'] = max(cur.get('minPax') or 1, deal.get('minPax') or 1)
    if deal.get('note') and deal['note'] not in (cur.get('note') or ''):
        cur['note'] = clean((cur.get('note') or '') + ' · ' + deal['note']).strip(' ·')


def from_aggregate(path, items, stats, yb_meta):
    data = json.load(open(path, encoding='utf-8'))
    for it in data.get('items') or data:
        code = it['도착지_공항코드']
        price = it.get('왕복총액_원')
        url = it.get('예약직링크') or ''
        if not price or not url:
            stats['skipped'] += 1
            continue
        region = it.get('지역') or ''
        if region == '기타' or region not in ('일본', '중국', '동남아', '남태평양', '미주', '유럽', '중동'):
            region = REGION_FIX.get(region, region or '기타')
        note = ''
        basis = it.get('가격기준') or ''
        if '미검증' in basis:
            note = '가격 포함 범위 미확인(예약 화면 확인)'
        ln = link_note(url)
        if ln:
            note = (note + ' · ' + ln).strip(' ·')
        meta = yb_meta.get((it['도착지_공항코드'], it['출발일'], it['귀국일'], it['항공사']))
        deal = {
            'id': 'P%03d' % it['no'],
            'src': SRC_OF.get(it.get('공급사_키'), 't'),
            'region': region,
            'city': it['도착지'],
            'code': code,
            'out': it['출발일'],
            'back': it['귀국일'],
            'days': it['여행일수'],
            'airline': it['항공사'],
            'price': int(price),
            'seats': seats_of(it.get('잔여좌석')),
            'minPax': (meta or {}).get('minPax') or 1,
            'times': (it.get('출발시각') or '') + ('–' + it['귀국시각'] if it.get('귀국시각') else ''),
            'url': fix_link(url, it['출발일'], it['귀국일']),
            'seen': '통합 목록 2026-11-19 11:21 기준',
            'note': clean(note),
        }
        if meta and meta.get('note'):
            deal['note'] = clean((deal['note'] + ' · ' + meta['note']).strip(' ·'))
        add(items, deal, stats)


def read_ybtour(path):
    """노랑풍선 CSV → (공항+날짜+항공사) 메타 사전 (최소인원·비고·예약불가)."""
    meta, bad = {}, []
    with open(path, encoding='utf-8-sig') as fp:
        for r in csv.DictReader(fp):
            k = (r['공항코드'], r['출발일시'][:10], r['귀국일시'][:10], r['항공사'])
            if r.get('예약링크검증') == '불가':
                bad.append((k, r.get('비고') or ''))
                continue
            note = r.get('비고') or ''
            minpax = int(r['최소예약인원']) if r.get('최소예약인원') else 1
            if minpax > 1 and '최소' not in note:
                note = (note + ' 최소 %d명' % minpax).strip()
            meta[k] = {'minPax': minpax, 'note': clean(note)}
    return meta, bad


def main(argv):
    ap = argparse.ArgumentParser(description='⑥ 땡처리 수집본 변환')
    ap.add_argument('--out', required=True)
    ap.add_argument('--aggregate', action='append', default=[])
    ap.add_argument('--ybtour', action='append', default=[])
    ap.add_argument('--observed', default='2026-11-19 12:25 KST')
    args = ap.parse_args(argv)

    yb_meta, bad = {}, []
    for p in args.ybtour:
        m, b = read_ybtour(p)
        yb_meta.update(m)
        bad.extend(b)

    stats = {'added': 0, 'cheaper': 0, 'relinked': 0, 'dupe': 0, 'skipped': 0}
    items = {}
    for p in args.aggregate:
        from_aggregate(p, items, stats, yb_meta)

    deals = sorted(items.values(), key=lambda d: (d['out'], d['price']))
    for i, d in enumerate(deals, 1):
        d['id'] = 'P%03d' % i

    out = {
        'schema': 'team-busan/pus-deals/1',
        'observedAt': args.observed,
        'window': {'start': min(d['out'] for d in deals), 'end': max(d['back'] for d in deals), 'basis': '출발일'},
        'channels': [{'key': 'g', 'label': '공동구매', 'note': '여행사 공동구매·할인항공'},
                     {'key': 't', 'label': '특가', 'note': '땡처리·집계 목록'}],
        'coverage': '',
        'coverageOk': False,
        'deals': deals,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    print('항공편 %d건 → %s' % (len(deals), args.out))
    print('  새 항공편 %(added)d · 더 싼 값 %(cheaper)d · 직링크 교체 %(relinked)d · 중복 %(dupe)d · 링크없음 %(skipped)d' % stats)
    for k, why in bad:
        print('  ! 예약 불가로 제외: %s %s %s (%s)' % (k[0], k[1], k[3], clean(why)[:60]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
