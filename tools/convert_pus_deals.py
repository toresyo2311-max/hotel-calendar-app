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


REGION_BY_CONTINENT = {'JPN': '일본', 'CHI': '중국', 'ASIA': '동남아', 'SOPA': '남태평양'}
CITY_ALIAS = {'상해-푸둥': '상하이', '상해-푸동': '상하이', '상해-홍차오': '상하이', '상해': '상하이',
              '북경': '베이징', '광주': '광저우', '황산(통치)': '황산', '계림(구이린)': '구이린',
              '장가계(다융)': '장가계'}


def norm_city(name):
    n = str(name or '').strip()
    return CITY_ALIAS.get(n, n)


def modetour_url(code, out, back, continent):
    """예약 상세 직링크는 차단되므로 권역·도시·날짜 필터 조회 URL을 쓴다(실측 확인된 형태)."""
    q = {'departureCity': 'PUS', 'arrivalCity': code, 'continentCode': continent,
         'departureDate': out, 'arrivalDate': back}
    return ('https://www.modetour.com/flights/discount-flight?query='
            + urllib.parse.quote(json.dumps(q, ensure_ascii=False, separators=(',', ':')), safe=''))


def continent_from_url(url):
    m = re.search(r'continentCode%22%3A%22([A-Z]+)', str(url or ''))
    return m.group(1) if m else ''


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
    return (d['code'], d['out'], d.get('outUntil') or '', d['back'], d['airline'])


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


def iso(datestr):
    """'2026.12.01' 또는 '2026-12-01' → '2026-12-01'."""
    s = str(datestr or '').strip().replace('.', '-')
    return s[:10] if re.match(r'^\d{4}-\d{2}-\d{2}', s) else ''


def parse_validity(v):
    """'3박5일' / '5일' / '5' → (박수, 일수). 박수가 없으면 일수-1."""
    s = str(v or '')
    m = re.search(r'(\d+)\s*박', s)
    nights = int(m.group(1)) if m else None
    m2 = re.search(r'(\d+)\s*일', s)
    days = int(m2.group(1)) if m2 else (int(s) if s.strip().isdigit() else None)
    if nights is None and days is not None:
        nights = max(0, days - 1)
    if days is None and nights is not None:
        days = nights + 1
    return nights, days


def parse_seats(v):
    """'4-12석' → (4, 12) · '4석' → (4, 4) · '미표시(…) ' → (None, None)."""
    s = str(v or '')
    m = re.search(r'(\d+)\s*-\s*(\d+)\s*석', s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'(\d+)\s*석', s)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def from_ttang(path, items, stats):
    """땡처리 목록 — 상품별 판매기간과 fare_detail 직링크. 기간형은 outUntil 로 표시한다."""
    data = json.load(open(path, encoding='utf-8'))
    for it in data.get('items') or []:
        price = it.get('왕복총액_원')
        url = it.get('예약직링크') or ''
        out = iso(it.get('출발가능일_시작'))
        until = iso(it.get('출발가능일_종료'))
        nights, days = parse_validity(it.get('유효기간'))
        if not (price and url and out and nights is not None):
            stats['skipped'] += 1
            continue
        first_back = ''
        m = re.match(r'^(\d{4}[.-]\d{2}[.-]\d{2})\s*[-~]\s*(\d{4}[.-]\d{2}[.-]\d{2})',
                     str(it.get('상세_첫출발_귀국') or ''))
        if m:
            first_back = iso(m.group(2))
        back = first_back
        if not back:
            import datetime
            back = (datetime.date.fromisoformat(out) + datetime.timedelta(days=nights)).isoformat()
        price_to = None
        m = re.match(r'^(\d+)\s*-\s*(\d+)', str(it.get('상세_가격범위_원') or ''))
        if m and int(m.group(2)) > price:
            price_to = int(m.group(2))
        seats, seats_to = parse_seats(it.get('잔여좌석'))
        notes = []
        if until and until != out:
            notes.append('기간형')
        if it.get('유효기간_출처') == '상품코드':
            notes.append('유효기간 코드 기준')
        if it.get('직항_경유') and it['직항_경유'] != '직항':
            notes.append(it['직항_경유'])
        deal = {
            'id': 'T%03d' % (len(items) + 1),
            'src': 't',
            'region': it.get('지역') or '기타',
            'city': it.get('도착지') or '',
            'code': it.get('도착공항코드') or '',
            'out': out,
            'back': back,
            'days': days or (nights + 1),
            'airline': it.get('항공사') or '미확인',
            'price': int(price),
            'seats': seats,
            'minPax': int(it.get('최소인원_명') or 1),
            'times': '',
            'url': url,
            'seen': '지역별 목록 2026-11-19 12:07~12:25',
            'note': clean(' · '.join(notes)),
        }
        if until and until != out:
            deal['outUntil'] = until
        if price_to:
            deal['priceTo'] = price_to
        if seats_to and seats_to != seats:
            deal['seatsTo'] = seats_to
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


def from_modetour_csv(path, items, stats):
    """모두투어 할인항공 CSV 두 벌을 한 번에 받는다(컬럼이 다르므로 행 단위로 구분)."""
    with open(path, encoding='utf-8-sig') as fp:
        for r in csv.DictReader(fp):
            if r.get('route_code'):                      # 중국분(route_code/city/…/listing_url)
                code = r['route_code']
                city = norm_city(r.get('city'))
                airline = r.get('airline') or '미확인'
                out, back = iso(r.get('dep_date')), iso(r.get('ret_date'))
                times = ((r.get('dep_time') or '') + ('–' + r['ret_time'] if r.get('ret_time') else '')).strip('–')
                days = r.get('validity_days') or ''
                days = int(days) if str(days).isdigit() else None
                seats = r.get('seats') or ''
                price = r.get('price_krw') or ''
                minpax = int(r.get('min_pax') or 1)
                continent = continent_from_url(r.get('listing_url')) or 'CHI'
            else:                                        # 일본·남태평양분(한글 헤더)
                code = r.get('공항코드')
                city = norm_city(r.get('도착지'))
                airline = r.get('항공사') or '미확인'
                out, back = iso((r.get('출발일시') or '')[:10]), iso((r.get('귀국일시') or '')[:10])
                ot, rt = (r.get('출발일시') or '')[11:16], (r.get('귀국일시') or '')[11:16]
                times = (ot + ('–' + rt if rt else '')).strip('–')
                d = re.search(r'(\d+)\s*일', r.get('소요/유효기간') or '')
                days = int(d.group(1)) if d else None
                seats = r.get('잔여좌석') or ''
                price = r.get('왕복가격') or ''
                minpax = 1
                continent = 'SOPA' if (r.get('권역') == '남태평양') else 'JPN'
            if not (code and out and back and str(price).replace(',', '').isdigit()):
                stats['skipped'] += 1
                continue
            s = re.search(r'(\d+)', str(seats))
            deal = {
                'id': 'M%04d' % (len(items) + 1),
                'src': 'g',
                'region': REGION_BY_CONTINENT.get(continent, '기타'),
                'city': city or code,
                'code': code,
                'out': out,
                'back': back,
                'days': days,
                'airline': airline,
                'price': int(str(price).replace(',', '')),
                'seats': int(s.group(1)) if s else None,
                'minPax': minpax,
                'times': times,
                'url': modetour_url(code, out, back, continent),
                'seen': '공동구매 목록 2026-11-19',
                'note': '검색 링크(권역·도시·날짜)' + (' · 최소 %d명' % minpax if minpax > 1 else ''),
            }
            add(items, deal, stats)


def from_modetour_json(path, items, stats):
    """동남아 JSON — flights 목록(pkg/code/depdate/price/booking_url)."""
    data = json.load(open(path, encoding='utf-8'))
    continent = 'ASIA'
    for name in ('continent', 'continent_name'):
        v = str(data.get(name) or '')
        if v in REGION_BY_CONTINENT:
            continent = v
    for f in data.get('flights') or []:
        out, back = iso(f.get('depdate')), iso(f.get('retdate'))
        price = f.get('price')
        if not (f.get('code') and out and back and price):
            stats['skipped'] += 1
            continue
        times = ((f.get('deptime') or '') + ('–' + f['rettime'] if f.get('rettime') else '')).strip('–')
        deal = {
            'id': 'M%04d' % (len(items) + 1),
            'src': 'g',
            'region': REGION_BY_CONTINENT.get(continent, '동남아'),
            'city': norm_city(f.get('city')),
            'code': f['code'],
            'out': out,
            'back': back,
            'days': f.get('day'),
            'airline': f.get('air') or '미확인',
            'price': int(price),
            'seats': f.get('seat') if isinstance(f.get('seat'), int) else None,
            'minPax': 1,
            'times': times,
            'url': modetour_url(f['code'], out, back, continent),
            'seen': '동남아 목록 2026-11-19 12:41',
            'note': '검색 링크(권역·도시·날짜)' + ((' · ' + f['waypoint']) if f.get('waypoint') else ''),
        }
        add(items, deal, stats)


def from_hanatour_json(path, items, stats, region_of):
    """하나투어 JSON — fareId 딥링크가 그대로 열리는 상품 직링크."""
    data = json.load(open(path, encoding='utf-8'))
    for f in data.get('flights') or []:
        out, back = iso(f.get('dep_date')), iso(f.get('ret_date'))
        price = f.get('price_krw')
        url = f.get('booking_url') or ''
        if not (f.get('airport') and out and back and price and url):
            stats['skipped'] += 1
            continue
        times = ((f.get('dep_time') or '') + ('–' + f['ret_time'] if f.get('ret_time') else '')).strip('–')
        deal = {
            'id': 'H%04d' % (len(items) + 1),
            'src': 'g',
            'region': region_of.get(f['airport'], '기타'),
            'city': norm_city(f.get('city')),
            'code': f['airport'],
            'out': out,
            'back': back,
            'days': f.get('days'),
            'airline': f.get('airline') or '미확인',
            'price': int(price),
            'seats': f.get('seats_left') if isinstance(f.get('seats_left'), int) else None,
            'minPax': 1,
            'times': times,
            'url': url,
            'seen': '통합 목록 2026-11-19 12:12',
            'note': '상품 직링크',
        }
        add(items, deal, stats)


def main(argv):
    ap = argparse.ArgumentParser(description='⑥ 땡처리 수집본 변환')
    ap.add_argument('--out', required=True)
    ap.add_argument('--aggregate', action='append', default=[])
    ap.add_argument('--ybtour', action='append', default=[])
    ap.add_argument('--ttang', action='append', default=[])
    ap.add_argument('--modetour-csv', action='append', default=[])
    ap.add_argument('--modetour-json', action='append', default=[])
    ap.add_argument('--hana-json', action='append', default=[])
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
    for p in args.ttang:
        from_ttang(p, items, stats)
    for p in args.modetour_csv:
        from_modetour_csv(p, items, stats)
    for p in args.modetour_json:
        from_modetour_json(p, items, stats)
    region_of = {}
    for d in items.values():
        if d.get('code') and d.get('region') and d['code'] not in region_of:
            region_of[d['code']] = d['region']
    for p in args.hana_json:
        from_hanatour_json(p, items, stats, region_of)

    deals = sorted(items.values(), key=lambda d: (d['price'], d['out']))
    import datetime
    keep = []
    for d in deals:
        try:
            o = datetime.date.fromisoformat(d['out'])
            b = datetime.date.fromisoformat(d['back'])
        except Exception:
            stats['skipped'] += 1
            continue
        if b < o:
            stats['skipped'] += 1
            continue
        real = (b - o).days + 1
        if d.get('days') and d['days'] != real:
            d['note'] = clean((d.get('note') or '') + ' · 표기 유효기간 %d일' % d['days']).strip(' ·')
        d['days'] = real
        keep.append(d)
    deals = keep
    for i, d in enumerate(deals, 1):
        d['id'] = 'P%04d' % i

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
