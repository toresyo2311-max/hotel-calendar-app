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


# 공항 코드 → 권역. 소스에 권역 칸이 없을 때(하나투어 JSON 등) 쓰는 기본값.
REGION_OF_CODE = {
    'CTS': '일본', 'FSZ': '일본', 'FUK': '일본', 'KIX': '일본', 'KMI': '일본', 'KMJ': '일본',
    'KOJ': '일본', 'MYJ': '일본', 'NGO': '일본', 'NGS': '일본', 'NRT': '일본', 'HND': '일본',
    'OKA': '일본', 'SHI': '일본', 'TAK': '일본',
    'GUM': '남태평양', 'SPN': '남태평양', 'ROR': '남태평양',
    'CAN': '중국', 'HGH': '중국', 'PEK': '중국', 'PVG': '중국', 'SHA': '중국', 'TAO': '중국',
    'TXN': '중국', 'DYG': '중국', 'RMQ': '중국', 'XMN': '중국', 'HKG': '중국', 'MFM': '중국',
    'BKI': '동남아', 'BKK': '동남아', 'CEB': '동남아', 'CNX': '동남아', 'CRK': '동남아',
    'CXR': '동남아', 'DAD': '동남아', 'HAN': '동남아', 'MNL': '동남아', 'PQC': '동남아',
    'SAI': '동남아', 'SGN': '동남아', 'SIN': '동남아', 'TAG': '동남아', 'VTE': '동남아',
    'TPE': '동남아', 'KHH': '동남아',
}

CITY_CANON = {'REP': '씨엠립', 'YNJ': '연길', 'TPE': '타이베이', 'NRT': '도쿄', 'HND': '도쿄', 'KIX': '오사카', 'PVG': '상하이',
              'SHA': '상하이', 'TAO': '칭다오', 'SHI': '미야코지마', 'CTS': '삿포로', 'HGH': '항주',
              'TXN': '황산', 'DYG': '장가계', 'PEK': '베이징', 'KHH': '카오슝', 'CXR': '나트랑',
              'BKK': '방콕', 'SIN': '싱가포르', 'SGN': '호치민', 'SAI': '씨엠립', 'VTE': '비엔티엔',
              'TAK': '다카마쓰', 'KMJ': '구마모토', 'KOJ': '가고시마', 'MYJ': '마쓰야마', 'FSZ': '시즈오카',
              'FUK': '후쿠오카', 'OKA': '오키나와', 'NGO': '나고야', 'KMI': '미야자키', 'GUM': '괌',
              'CEB': '세부', 'MNL': '마닐라', 'TAG': '보홀', 'CRK': '클락', 'BKI': '코타키나발루',
              'PQC': '푸꾸옥', 'CNX': '치앙마이', 'DAD': '다낭', 'HAN': '하노이', 'HKG': '홍콩',
              'RMQ': '타이중', 'XMN': '샤먼', 'CAN': '광저우', 'NGS': '나가사키'}


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


def note_parts(note):
    """비고 문구를 항목별로 나누고 같은 항목 반복을 지운다."""
    out = []
    for p in str(note or '').split(' · '):
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def fix_note(note, url):
    """예약 주소와 맞지 않는 링크 설명을 빼고(검색 링크 ↔ 상품 직링크) 반복 항목을 정리한다."""
    parts = note_parts(note)
    search = 'modetour.com/flights/discount-flight?' in str(url or '')
    drop = '상품 직링크' if search else '검색 링크(권역·도시·날짜)'
    lost = [p for p in parts if p != drop]
    return clean(' · '.join(lost))


# 공항 코드 별칭 — 같은 공항을 소스마다 다른 코드로 적는 경우 한 코드로 모은다(같은 항공편이 두 줄로 남지 않게).
CODE_ALIAS = {'REP': 'SAI'}          # 씨엠립 — 한 수집본은 REP, 다른 수집본은 SAI 로 적는다


def key_of(d):
    return (d['code'], d['out'], d.get('outUntil') or '', d['back'], d['airline'])


def add(bucket, deal, stats):
    deal['code'] = CODE_ALIAS.get(deal['code'], deal['code'])
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


REGION_BY_BLOCK = {'일본': '일본', '중화권': '중국', '중국': '중국', '동남아': '동남아',
                   '남태평양': '남태평양', '미주': '미주', '유럽': '유럽', '중동': '중동'}


def from_tt_json(path, items, stats, yb_meta, seen_day=''):
    """땡처리·집계 목록 통합본(`_출처키` 스키마, 2026-11-21 형식).

    두 목록이 한 파일에 담겨 온다.
      · `ttang`      — 상품별 판매기간(`출발가능일_시작`~`종료`)과 fare_detail 직링크. 기간형은 outUntil 로 남긴다.
      · `tikitikit`  — 출발일·귀국일이 고정된 상품. 날짜가 박힌 상세 직링크.
    """
    data = json.load(open(path, encoding='utf-8'))
    for it in data.get('items') or []:
        code = it.get('도착공항코드') or ''
        price = it.get('왕복총액_원')
        url = it.get('예약링크') or ''
        region = REGION_BY_BLOCK.get(it.get('권역') or '', it.get('권역') or '기타')
        if not (code and price and url):
            stats['skipped'] += 1
            continue
        out = iso(it.get('출발일') or it.get('출발가능일_시작'))
        until = iso(it.get('출발가능일_종료'))
        nights, days = parse_validity(it.get('숙박일수'))
        if nights is None:
            # 숙박일수 칸이 비어 있는 줄은 여행일수(계산값 포함)로 박수를 잡는다.
            for v in (it.get('여행일수'), it.get('여행일수_계산')):
                if isinstance(v, int) and v > 0:
                    days, nights = v, v - 1
                    break
        if not out:
            stats['skipped'] += 1
            continue
        first_back = ''
        m = re.match(r'^(\d{4}[.-]\d{2}[.-]\d{2})\s*[-~]\s*(\d{4}[.-]\d{2}[.-]\d{2})',
                     str(it.get('상세_첫출발_귀국') or ''))
        # 상세의 첫출발이 이 상품의 출발일과 같을 때만 그 귀국일을 쓴다(기간형 오차 방지).
        if m and iso(m.group(1)) == out:
            first_back = iso(m.group(2))
        back = iso(it.get('귀국일')) or first_back
        if not back and nights is not None:
            import datetime
            back = (datetime.date.fromisoformat(out) + datetime.timedelta(days=nights)).isoformat()
        if not back:
            stats['skipped'] += 1
            continue
        seats, seats_to = parse_seats(it.get('잔여좌석'))
        pmin = it.get('최소인원_명')
        meta = yb_meta.get((code, out, back, it.get('항공사') or ''))
        notes = []
        if until and until != out:
            notes.append('기간형')
        if it.get('숙박일수_출처') == '상품코드':
            notes.append('유효기간 코드 기준')
        if '미검증' in str(it.get('요금_포함범위') or ''):
            notes.append('가격 포함 범위 미확인(예약 화면 확인)')
        if it.get('직항_경유') and it['직항_경유'] != '직항':
            notes.append(it['직항_경유'])
        if it.get('배지') and '미표시' not in str(it['배지']):
            notes.append(str(it['배지']))
        if it.get('잔여좌석_비고') and '미표시' not in str(it.get('잔여좌석_비고')):
            notes.append(str(it['잔여좌석_비고']))
        if meta and meta.get('note'):
            notes.append(meta['note'])
        times = ((it.get('출발시각') or '') + ('–' + it['귀국시각'] if it.get('귀국시각') else '')).strip('–')
        deal = {
            'id': 'X%03d' % (len(items) + 1),
            'src': 't',
            'region': region,
            'city': norm_city(it.get('도착지')),
            'code': code,
            'out': out,
            'back': back,
            'days': days,
            'airline': it.get('항공사') or '미확인',
            'price': int(price),
            'seats': seats,
            'minPax': max(int(pmin or 1), (meta or {}).get('minPax') or 1),
            'times': times,
            'url': url,
            'seen': '통합 목록 %s 기준' % seen_day,
            'note': clean(' · '.join(p for p in notes if p)),
        }
        pr = it.get('상세_가격범위_원')
        if isinstance(pr, list) and len(pr) >= 2 and isinstance(pr[1], int) and pr[1] > deal['price']:
            deal['priceTo'] = pr[1]
        if until and until != out:
            deal['outUntil'] = until
        if seats_to and seats_to != seats:
            deal['seatsTo'] = seats_to
        add(items, deal, stats)


def from_ybtour_deals(path, items, stats, seen_day=''):
    """노랑풍선 CSV — 행마다 예약요약 직링크가 확인된 상품을 상품 줄로도 넣는다.

    같은 상품이 집계 목록에도 있으면 병합 단계에서 같은 값이면 직링크 쪽이 남는다.
    """
    with open(path, encoding='utf-8-sig') as fp:
        for r in csv.DictReader(fp):
            if r.get('예약링크검증') == '불가' or not r.get('예약URL'):
                stats['skipped'] += 1
                continue
            code = r.get('공항코드') or ''
            out, back = iso((r.get('출발일시') or '')[:10]), iso((r.get('귀국일시') or '')[:10])
            price = str(r.get('왕복가격') or '').replace(',', '')
            if not (code and out and back and price.isdigit()):
                stats['skipped'] += 1
                continue
            ot, rt = (r.get('출발일시') or '')[11:16], (r.get('귀국일시') or '')[11:16]
            seats, _ = parse_seats(r.get('잔여좌석'))
            minpax = int(r['최소예약인원']) if str(r.get('최소예약인원') or '').isdigit() else 1
            d = re.search(r'(\d+)\s*일', r.get('소요/유효기간') or '')
            notes = ['상품 직링크']
            if minpax > 1:
                notes.append('최소 %d명' % minpax)
            deal = {
                'id': 'Y%03d' % (len(items) + 1),
                'src': 'g',
                'region': REGION_BY_BLOCK.get(r.get('지역') or '', '기타'),
                'city': norm_city(r.get('도착지')),
                'code': code,
                'out': out,
                'back': back,
                'days': int(d.group(1)) if d else None,
                'airline': r.get('항공사') or '미확인',
                'price': int(price),
                'seats': seats,
                'minPax': minpax,
                'times': (ot + ('–' + rt if rt else '')).strip('–'),
                'url': r['예약URL'],
                'seen': '공동구매 목록 %s' % seen_day,
                'note': clean(' · '.join(notes)),
            }
            add(items, deal, stats)


def from_aggregate(path, items, stats, yb_meta, seen_day=''):
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
            'minPax': max((meta or {}).get('minPax') or 1, int(it.get('인원조건_최소') or 1)),
            'times': (it.get('출발시각') or '') + ('–' + it['귀국시각'] if it.get('귀국시각') else ''),
            'url': fix_link(url, it['출발일'], it['귀국일']),
            'seen': '통합 목록 %s 기준' % seen_day,
            'note': clean(note),
        }
        if meta and meta.get('note'):
            deal['note'] = clean((deal['note'] + ' · ' + meta['note']).strip(' ·'))
        # 노랑풍선 상품 링크는 수집본에서 행별 '예약링크검증=확인'을 통과한 주소만 meta 에 남는다.
        # 그 주소가 그대로 들어왔으면 상품 화면으로 열리는 직링크이므로 '미확인' 배지를 붙이지 않는다.
        if it.get('공급사_키') == 'ybtour' and meta and 'fly.ybtour.co.kr' in str(deal['url']):
            deal['note'] = clean((deal['note'] + ' · 상품 직링크').strip(' ·'))
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


def from_ttang(path, items, stats, seen_day=''):
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
        # 상세의 첫출발이 이 상품의 출발가능일 시작과 같을 때만 그 귀국일을 쓴다.
        # 기간형은 상세 기준일이 시작일과 다를 수 있어, 그러면 유효기간(박수)으로 계산한다(8일·26일 같은 오류 방지).
        if m and iso(m.group(1)) == out:
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
            'seen': '지역별 목록 %s' % seen_day,
            'note': clean(' · '.join(notes)),
        }
        if until and until != out:
            deal['outUntil'] = until
        if price_to:
            deal['priceTo'] = price_to
        if seats_to and seats_to != seats:
            deal['seatsTo'] = seats_to
        add(items, deal, stats)


def tidy_yb_note(v):
    """노랑풍선 비고 → 화면에 남길 말만. 수집 메타(미확인·신규 포착 등)는 줄이고, 도시명 차이는 배지 판정에 필요한 짧은 문구로 바꾼다."""
    keep = []
    for p in str(v or '').replace(';', ' · ').split(' · '):
        p = p.strip()
        if not p:
            continue
        if p.startswith('최소예약인원 데이터 없음') or '미노출' in p or '예약페이지' in p or '별도 판매' in p:
            continue
        if p.startswith('오늘(') and '신규' in p:
            p = '신규'
        if p.startswith('도시명 표기차'):
            m = re.search(r'\(([A-Z]{3})\)', p)
            p = '카드 도시명과 실제 도착공항이 다름' + ('(%s)' % m.group(1) if m else '')
        p = clean(p)
        if p and p not in keep:
            keep.append(p)
    return ' · '.join(keep)


def read_ybtour(path):
    """노랑풍선 CSV → (공항+날짜+항공사) 메타 사전 (최소인원·비고·예약불가)."""
    meta, bad = {}, []
    with open(path, encoding='utf-8-sig') as fp:
        for r in csv.DictReader(fp):
            k = (r['공항코드'], r['출발일시'][:10], r['귀국일시'][:10], r['항공사'])
            if r.get('예약링크검증') == '불가':
                bad.append((k, r.get('비고') or ''))
                continue
            note = tidy_yb_note(r.get('비고'))
            minpax = int(r['최소예약인원']) if r.get('최소예약인원') else 1
            if minpax > 1 and '최소' not in note:
                note = (note + ' · 최소 %d명' % minpax).strip(' ·')
            meta[k] = {'minPax': minpax, 'note': note}
    return meta, bad


def bigo_note(v):
    """CSV 비고 열(15열 스키마) → 화면에 남길 메모. ';' 구분, '정가 미표시'처럼 쓸모없는 값은 버린다."""
    out = []
    for p in str(v or '').replace(';', ' · ').split(' · '):
        p = p.strip()
        if not p or p == '-' or p.startswith('정가 미표시'):
            continue
        p = clean(p)
        if p and p not in out:
            out.append(p)
    return ' · '.join(out)


def from_modetour_csv(path, items, stats, seen_day=''):
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
            bigo = bigo_note(r.get('비고')) if r.get('비고') else ''
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
                'seen': '공동구매 목록 %s' % seen_day,
                'note': clean(' · '.join(p for p in ['검색 링크(권역·도시·날짜)',
                                                    ('최소 %d명' % minpax) if minpax > 1 else '',
                                                    bigo] if p)),
            }
            add(items, deal, stats)


def from_modetour_json(path, items, stats, seen_day=''):
    """동남아 JSON — flights 목록(pkg/code/depdate/price/booking_url)."""
    data = json.load(open(path, encoding='utf-8'))
    continent = 'ASIA'
    for name in ('continent', 'continent_name'):
        v = str(data.get(name) or '')
        if v in REGION_BY_CONTINENT:
            continent = v
    for f in data.get('flights') or []:
        out, back = iso(f.get('depdate') or f.get('dep_date')), iso(f.get('retdate') or f.get('ret_date'))
        price = f.get('price') or f.get('price_krw')
        code = f.get('code') or f.get('route_code')
        if not (code and out and back and price):
            stats['skipped'] += 1
            continue
        times = ((f.get('deptime') or '') + ('–' + f['rettime'] if f.get('rettime') else '')).strip('–')
        deal = {
            'id': 'M%04d' % (len(items) + 1),
            'src': 'g',
            'region': REGION_BY_CONTINENT.get(continent, '동남아'),
            'city': norm_city(f.get('city') or f.get('route')),
            'code': code,
            'out': out,
            'back': back,
            'days': f.get('day') if f.get('day') is not None else f.get('validity_days'),
            'airline': f.get('air') or f.get('airline') or '미확인',
            'price': int(price),
            'seats': f.get('seat') if isinstance(f.get('seat'), int) else (
                f.get('seats') if isinstance(f.get('seats'), int) else None),
            'minPax': int(f.get('min_pax_today') or 1) if str(f.get('min_pax_today') or '').isdigit() else 1,
            'times': times,
            'url': modetour_url(code, out, back, continent),
            'seen': '동남아 목록 %s' % seen_day,
            'note': '검색 링크(권역·도시·날짜)' + ((' · ' + f['waypoint']) if f.get('waypoint') else '')
                    + ((' · 최소 %d명' % int(f['min_pax_today'])) if str(f.get('min_pax_today') or '').isdigit()
                       and int(f['min_pax_today']) > 1 else ''),
        }
        add(items, deal, stats)


def from_hanatour_json(path, items, stats, region_of, seen_day=''):
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
        notes = ['상품 직링크']
        for b in f.get('baggage') or []:
            if isinstance(b, dict) and b.get('limit'):
                notes.append('위탁 %s%s' % (b['limit'], 'kg' if str(b.get('baggUnit')).upper() == 'K' else '개'))
                break
        deal = {
            'id': 'H%04d' % (len(items) + 1),
            'src': 'g',
            'region': region_of.get(f['airport']) or REGION_OF_CODE.get(f['airport']) or '기타',
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
            'seen': '공동구매 상세 %s' % seen_day,
            'note': ' · '.join(notes),
        }
        add(items, deal, stats)


def main(argv):
    ap = argparse.ArgumentParser(description='⑥ 땡처리 수집본 변환')
    ap.add_argument('--out', required=True)
    ap.add_argument('--aggregate', action='append', default=[])
    ap.add_argument('--ybtour', action='append', default=[])
    ap.add_argument('--ttang', action='append', default=[])
    ap.add_argument('--tt-json', action='append', default=[], help='땡처리·집계 통합본(_출처키 스키마)')
    ap.add_argument('--ybtour-deals', action='append', default=[], help='노랑풍선 CSV를 상품 줄로도 넣기')
    ap.add_argument('--modetour-csv', action='append', default=[])
    ap.add_argument('--modetour-json', action='append', default=[])
    ap.add_argument('--hana-json', action='append', default=[])
    ap.add_argument('--observed', default='2026-11-19 12:25 KST')
    ap.add_argument('--day', default='', help="'seen' 기록에 쓰는 수집일(비우면 오늘)")
    args = ap.parse_args(argv)
    seen_day = args.day

    yb_meta, bad = {}, []
    for p in args.ybtour:
        m, b = read_ybtour(p)
        yb_meta.update(m)
        bad.extend(b)

    stats = {'added': 0, 'cheaper': 0, 'relinked': 0, 'dupe': 0, 'skipped': 0}
    items = {}
    for p in args.aggregate:
        from_aggregate(p, items, stats, yb_meta, seen_day)
    for p in args.ttang:
        from_ttang(p, items, stats, seen_day)
    for p in args.tt_json:
        from_tt_json(p, items, stats, yb_meta, seen_day)
    for p in args.modetour_csv:
        from_modetour_csv(p, items, stats, seen_day)
    for p in args.modetour_json:
        from_modetour_json(p, items, stats, seen_day)
    region_of = dict(REGION_OF_CODE)
    for d in items.values():
        if d.get('code') and d.get('region') and d['code'] not in region_of:
            region_of[d['code']] = d['region']
    for p in args.hana_json:
        from_hanatour_json(p, items, stats, region_of, seen_day)
    # 노랑풍선 상품 줄은 맨 뒤에 넣는다 — 같은 값이면 확인된 예약요약 직링크가 남도록.
    for p in args.ybtour_deals:
        from_ybtour_deals(p, items, stats, seen_day)

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
    # 같은 공항(코드)을 소스마다 다르게 적은 이름을 하나로 통일한다(가장 많이 쓰인 이름, 동률이면 짧은 것)
    names = {}
    for d in deals:
        names.setdefault(d['code'], {})
        names[d['code']][d['city']] = names[d['code']].get(d['city'], 0) + 1
    canon = {}
    for code, cnt in names.items():
        canon[code] = CITY_CANON.get(code) or sorted(cnt.items(), key=lambda kv: (-kv[1], len(kv[0])))[0][0]
    for d in deals:
        d['city'] = canon[d['code']]
        d['note'] = fix_note(d.get('note'), d.get('url'))
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
