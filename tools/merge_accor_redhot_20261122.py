#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 아코르 — Red Hot Rooms(레드핫 요금제) 병합 (2026-11-22).

무엇을 하는가
  · accorplus.com 오퍼 목록 API(getOfferList)에서 categories=red-hot-rooms 인 32건만 쓴다.
    (tools/redhot/offers_redhot_20261122.json · 수집 2026-11-22 KST)
  · 32건 가운데 기존 ③ 아코르 247곳과 코드가 같은 14곳은 `redhot`·`redhotRates`만 더한다
    (rates·stayplus2·stayplus3 는 건드리지 않는다).
  · 나머지 18곳(인도네시아 7 · 필리핀 4 · 캄보디아 2 · 말레이시아 1 · 몰디브 1 · 호주 1 · 일본 1)은
    a248 부터 새 id 로 `group: domestic` 호텔을 만들어 넣는다(rates 는 빈 객체).
  · 달력 창(2026-12-01~2027-11-30)과 겹치는 투숙 날짜만 `redhotRates` 에 담고,
    원화는 2026-11-22 환율로 100원 단위 반올림한 정수다. 세금 표기(++ · +++ · net)는 원문 그대로.

    python3 tools/merge_accor_redhot_20261122.py            # 병합
    python3 tools/merge_accor_redhot_20261122.py --dry-run   # 계산만
"""
import datetime
import decimal
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
OFFERS = os.path.join(ROOT, 'tools', 'redhot', 'offers_redhot_20261122.json')

WINDOW_START = '2026-12-01'
WINDOW_END = '2027-11-30'

# 2026-11-22 환율(open.er-api.com/v6/latest/KRW · 2026-11-22 00:02 UTC 갱신분)
#   1 단위 = 아래 원화. 화면에는 'VND 1 = ₩0.0520' 처럼 4자리로 적는다.
FX = {'VND': 0.052015, 'IDR': 0.073465, 'USD': 1342.281879, 'PHP': 21.011052,
      'SGD': 1035.196687, 'AUD': 891.265597, 'JPY': 8.423535, 'THB': 39.41508,
      'MYR': 325.839036}
FX_ASOF = '2026-11-22'
FX_UNIT = {'VND': 1000, 'IDR': 1000, 'USD': 1, 'PHP': 1, 'SGD': 1, 'AUD': 1,
           'JPY': 1, 'THB': 1, 'MYR': 1}

# ── 오퍼별 투숙 기간 파싱 결과 ────────────────────────────────────────────
# 원문(offer_information_body_2)은 `redhot.stayText` 에 그대로 남기고, 여기서는 해석한 날짜만 적는다.
# None 은 '그 방향으로 열려 있음'(창 밖은 어차피 잘린다).
STAY = {
    '7965': ('2027-01-29', '2027-02-14'),
    'B066': ('2026-11-01', '2027-03-31'),
    'C0Q3': ('2027-01-01', '2027-04-15'),
    'B4P2': ('2026-11-15', '2027-03-07'),
    'A5E0': (None, '2027-09-30'),              # Until 30 September 2027
    'A5D9': (None, '2027-12-20'),              # Until 20 December 2027 (창은 11-30 까지)
    'C586': (None, '2026-12-22'),
    '9338': (None, '2027-03-31'),
    'A5E3': ('2026-12-01', '2026-12-31'),
    'A5G3': ('2026-12-01', '2026-12-31'),
    'B5L7': ('2026-11-01', '2027-01-25'),
    'B986': (None, '2026-12-20'),
    'B9H8': ('2026-01-03', '2027-02-28'),      # 원문 '3 January 2026 - 28 February 2027'
    '8778': ('2026-12-13', '2027-04-28'),
    'A5G8': ('2026-10-28', '2026-12-17'),
    'C082': ('2026-11-01', '2026-12-05'),
    'B4G8': ('2026-10-26', '2026-12-23'),
    '9799': (None, '2026-12-30'),
    '6033': (None, '2026-12-20'),
    '8455': ('2026-10-19', '2027-01-31'),
    '6184': (None, '2026-11-30'),
    '9932': (None, '2026-11-30'),
    '9929': (None, '2026-11-30'),
    'B764': (None, '2026-12-25'),
    '9103': (None, '2026-12-30'),
    '5704': (None, '2026-12-30'),
    'B2R4': (None, '2026-11-30'),
    'A123': ('2026-05-21', '2026-12-31'),
    'A152': ('2026-03-24', '2026-12-30'),
    '8488': (None, '2026-12-31'),
    'B1Y7': (None, '2026-12-31'),
    'C561': (None, '2026-12-31'),
}

# 투숙 제외일 — 원문 '(except 24 and 31 December 2026)' 처럼 날짜를 콕 집은 오퍼만.
EXCEPT = {
    'A5E3': ['2026-12-24', '2026-12-31'],
    'A5G3': ['2026-12-24', '2026-12-31'],
}
# 원문에 날짜 없이 '공휴일 제외'만 적힌 오퍼 — 날짜를 지어내지 않고 문구만 남긴다.
EXCEPT_TEXT = {'C561': '원문 「except public holidays」 — 공휴일 날짜는 오퍼에 적혀 있지 않습니다'}

# 예약 기간 마지막 날 — 원문(offer_information_body_1)을 해석한 값. 화면에 '예약 마감'으로 적는다.
BOOK_UNTIL = {
    '7965': '2027-02-11', 'B066': '2027-03-31', 'C0Q3': '2026-12-20', 'B4P2': '2027-01-31',
    'A5E0': '2027-03-31', 'A5D9': '2027-03-31', 'C586': '2026-12-22', '9338': '2027-03-31',
    'A5E3': '2026-12-30', 'A5G3': '2026-12-30', 'B5L7': '2026-11-30', 'B986': '2026-12-20',
    'B9H8': '2026-11-30', '8778': '2026-11-30', 'A5G8': '2026-11-22', 'C082': '2026-11-30',
    'B4G8': '2026-12-23', '9799': '2026-12-30', '6033': '2026-12-20', '8455': '2026-11-30',
    '6184': '2026-11-30', '9932': '2026-11-30', '9929': '2026-11-30', 'B764': '2026-12-25',
    '9103': '2026-12-30', '5704': '2026-12-30', 'B2R4': '2026-11-30', 'A123': '2026-12-31',
    'A152': '2026-12-30', '8488': '2026-12-31', 'B1Y7': '2026-12-31', 'C561': '2026-12-31',
}

# 새로 넣는 18곳 — (코드, region, city, 이름, 영문명, 브랜드)
NEW = [
    ('B066', '인도네시아', '수라바야', '호텔 마자파힛 수라바야 - 엠갤러리 컬렉션',
     'Hotel Majapahit Surabaya - MGallery Collection', 'MGallery'),
    ('C0Q3', '인도네시아', '자카르타', '뫼벤픽 호텔 자카르타 시티 센터',
     'Mövenpick Hotel Jakarta City Centre', 'Mövenpick'),
    ('B4P2', '인도네시아', '발리', '뫼벤픽 리조트 앤 스파 짐바란 발리',
     'Mövenpick Resort & Spa Jimbaran Bali', 'Mövenpick'),
    ('A5E0', '캄보디아', '프놈펜', '래플스 호텔 르 로열', 'Raffles Hotel Le Royal', 'Raffles'),
    ('A5D9', '캄보디아', '시엠립', '래플스 그랜드 호텔 당코르',
     "Raffles Grand Hotel d'Angkor", 'Raffles'),
    ('C586', '필리핀', '세부', '머큐어 막탄 세부', 'Mercure Mactan Cebu', 'Mercure'),
    ('9338', '필리핀', '마닐라', '아드미럴 호텔 마닐라 - 엠갤러리 컬렉션',
     'Admiral Hotel Manila - MGallery Collection', 'MGallery'),
    ('A5E3', '필리핀', '마카티', '래플스 마카티', 'Raffles Makati', 'Raffles'),
    ('A5G3', '필리핀', '마카티', '페어몬트 마카티', 'Fairmont Makati', 'Fairmont'),
    ('B986', '몰디브', '말레', 'SO/ 몰디브', 'SO/ Maldives', 'SO/'),
    ('8778', '호주', '브리즈번', '더 세벨 브리즈번', 'The Sebel Brisbane', 'The Sebel'),
    ('C082', '일본', '삿포로', '호텔 소세이 삿포로 - 엠갤러리 컬렉션',
     'Hotel Sosei Sapporo - MGallery Collection', 'MGallery'),
    ('9799', '인도네시아', '자카르타', '노보텔 자카르타 치키니', 'Novotel Jakarta Cikini', 'Novotel'),
    ('8455', '인도네시아', '탕에랑', '머큐어 세르퐁 알람 수테라',
     'Mercure Serpong Alam Sutera', 'Mercure'),
    ('B764', '인도네시아', '자카르타', '스위소텔 리빙 자카르타 메가 쿠닝안',
     'Swissôtel Living Jakarta Mega Kuningan', 'Swissôtel'),
    ('9103', '인도네시아', '자카르타', '이비스 스타일스 자카르타 망가 두아 스퀘어',
     'ibis Styles Jakarta Mangga Dua Square', 'ibis Styles'),
    ('5704', '인도네시아', '자카르타', '노보텔 자카르타 망가 두아 스퀘어',
     'Novotel Jakarta Mangga Dua Square', 'Novotel'),
    ('A123', '말레이시아', '쿠알라룸푸르', '소피텔 쿠알라룸푸르 다만사라',
     'Sofitel Kuala Lumpur Damansara', 'Sofitel'),
]

MONEY_RE = re.compile(r'([A-Z]{3})\s*([\d,]+(?:\.\d+)?)\s*(.*)$')


def _rnd(x):
    return int(decimal.Decimal(str(x)).quantize(0, rounding=decimal.ROUND_HALF_UP))


def parse_money(text):
    """'VND 1,510,000++' -> ('VND', 1510000.0, '++', 'VND 1,510,000++')"""
    if not text:
        return None
    s = str(text).strip()
    m = MONEY_RE.search(s.replace('\u00a0', ' '))
    if not m:
        return None
    code, num, tail = m.group(1), m.group(2).replace(',', ''), m.group(3).strip()
    return code, float(num), tail, s


def to_krw(code, amount):
    rate = FX[code]
    return _rnd(amount * rate / 100.0) * 100


def days_between(a, b):
    d = datetime.date.fromisoformat(a)
    e = datetime.date.fromisoformat(b)
    out = []
    while d <= e:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def build():
    off = json.load(open(OFFERS, encoding='utf-8'))
    offers = off['offers']
    if len(offers) != 32:
        raise SystemExit('오퍼 32건이 아닙니다: %d' % len(offers))
    rows = []
    for o in offers:
        f = o['fields']
        code = (f.get('location_id') or '').strip()
        if code not in STAY:
            raise SystemExit('투숙 기간 표에 없는 코드: %s (%s)' % (code, o['title']))
        price = parse_money(f.get('red_hot_room_discounted_price'))
        lst = parse_money(f.get('red_hot_room_discount'))
        if not price:
            raise SystemExit('레드핫 시작가를 읽지 못했습니다: %s' % o['title'])
        cur, amount, tax, price_text = price
        if lst and lst[0] == cur:
            list_amount, list_text = lst[1], lst[3]
        else:
            list_amount, list_text = None, ''
        stay_from, stay_to = STAY[code]
        start = max(stay_from or WINDOW_START, WINDOW_START)
        end = min(stay_to or WINDOW_END, WINDOW_END)
        excepts = set(EXCEPT.get(code) or [])
        dates = [d for d in (days_between(start, end) if start <= end else [])
                 if start <= d <= end and d not in excepts]
        krw = to_krw(cur, amount)
        disc = None
        if list_amount and list_amount > 0:
            disc = _rnd((1 - amount / list_amount) * 100)
        m = re.search(r'sav(?:e|ing)[^.]{0,40}?(\d+)\s*%', (f.get('main_content') or '').replace('\n', ' '), re.I)
        offer_save = int(m.group(1)) if m else None
        rows.append({
            'code': code,
            'title': o['title'],
            'offerId': o['id'],
            'offerUrl': o['url'],
            'country': f.get('country') or '',
            'city': f.get('city') or '',
            'currency': cur,
            'priceLocal': int(round(amount)),
            'priceText': price_text,
            'listLocal': int(round(list_amount)) if list_amount else None,
            'listText': list_text,
            'tax': tax,
            'krw': krw,
            'discountPct': disc,
            'offerSave': offer_save,
            'stayText': f.get('offer_information_body_2') or '',
            'stayFrom': stay_from,
            'stayTo': stay_to,
            'bookText': f.get('offer_information_body_1') or '',
            'bookUntil': BOOK_UNTIL[code],
            'rooms': (f.get('offer_information_body_3') or '').strip(),
            'exceptText': EXCEPT_TEXT.get(code) or '',
            'exceptDates': sorted(excepts),
            'terms': re.sub(r'<[^>]+>', ' ', f.get('terms_and_conditions') or '').replace('  ', ' ').strip(),
            'offerBookUrl': f.get('button_1_link') or '',
            'expiry': f.get('expiry') or '',
            'dates': dates,
        })
    return rows


def main():
    dry = '--dry-run' in sys.argv
    rows = build()
    master = json.loads(open(MASTER, encoding='utf-8').read())
    dom = [h for h in master['hotels'] if h.get('group') == 'domestic']
    by_code = {}
    for h in dom:
        by_code.setdefault(str(h.get('code') or '').strip(), h)
    # 새 id — 기존 aNNN 최대값 다음부터
    nums = [int(h['id'][1:]) for h in master['hotels']
            if re.fullmatch(r'a\d{3}', h['id'] or '')]
    next_num = (max(nums) + 1) if nums else 1

    added, updated, ended = [], [], []
    for r in rows:
        code = r['code']
        hotel = by_code.get(code)
        if hotel is None:
            if code not in [n[0] for n in NEW]:
                raise SystemExit('기존 247곳에도 없고 NEW 표에도 없는 호텔: %s' % r['title'])
            meta = [n for n in NEW if n[0] == code][0]
            hid = 'a%03d' % next_num
            next_num += 1
            hotel = {'id': hid, 'group': 'domestic', 'city': meta[2], 'name': meta[3],
                     'english': meta[4], 'brand': meta[5],
                     'promotion': 'Red Hot Rooms — ALL Accor+ Explorer 회원 전용',
                     'rates': {}, 'code': code, 'region': meta[1],
                     'source': ('레드핫 오퍼 조회 %s KST · 오퍼 목록 원문(accorplus.com) · '
                                'ALL Accor+ Explorer 회원 전용 요금 · 세금 표기(++, +++, net) 원문 그대로'
                                % FX_ASOF)}
            master['hotels'].append(hotel)
            added.append(hotel)
        else:
            updated.append(hotel)
        rh = {
            'offerId': r['offerId'],
            'title': r['title'],
            'code': code,
            'country': r['country'],
            'city': r['city'],
            'currency': r['currency'],
            'priceText': r['priceText'],
            'priceLocal': r['priceLocal'],
            'listText': r['listText'],
            'listLocal': r['listLocal'],
            'tax': r['tax'],
            'krw': r['krw'],
            'fx': '%s 1 = ₩%s' % (r['currency'], format(FX[r['currency']], '.4f')),
            'fxAsOf': FX_ASOF,
            'fxText': ('%s %s = ₩%s' % (r['currency'], format(FX_UNIT[r['currency']], ','),
                                        format(round(FX[r['currency']] * FX_UNIT[r['currency']], 2), ','))
                       if FX_UNIT[r['currency']] > 1 else
                       '%s 1 = ₩%s' % (r['currency'], format(FX[r['currency']], '.4f'))),
            'discountPct': r['discountPct'],
            'offerSavePct': r['offerSave'],
            'stayText': r['stayText'],
            'stayFrom': r['stayFrom'],
            'stayTo': r['stayTo'],
            'bookText': r['bookText'],
            'bookUntil': r['bookUntil'],
            'rooms': r['rooms'],
            'exceptText': r['exceptText'],
            'exceptDates': r['exceptDates'],
            'terms': r['terms'],
            'memberOnly': True,
            'offerUrl': r['offerUrl'],
            'offerBookUrl': r['offerBookUrl'],
            'expiry': r['expiry'],
            'dates': len(r['dates']),
            'status': 'open' if r['dates'] else 'ended',
            'fetched': '2026-11-22 KST',
        }
        hotel['redhot'] = rh
        hotel['redhotRates'] = {d: r['krw'] for d in r['dates']}
        if rh['status'] == 'ended':
            ended.append((hotel['id'], hotel['name'], r['stayText'], r['expiry']))

    print('기존 호텔에 레드핫 추가 %d곳 / 새 호텔 %d곳 / 달력 창 안 날짜 없음 %d곳'
          % (len(updated), len(added), len(ended)))
    print('  총 ③ 아코르 %d곳' % len([h for h in master['hotels'] if h.get('group') == 'domestic']))
    cells = sum(len(h.get('redhotRates') or {}) for h in master['hotels'])
    print('  레드핫 칸 %d개 (창 %s~%s)' % (cells, WINDOW_START, WINDOW_END))
    for a in added:
        print('  + %s %s · %s/%s · %s (레드핫 %d일)' % (a['id'], a['name'], a['region'], a['city'],
                                                   a['redhot']['priceText'], a['redhot']['dates']))
    for e in ended:
        print('  · 창 안 날짜 없음 %s %s (%s · 만료 %s)' % e)

    # 집계(counts)는 extract 와 같은 식으로 다시 센다 — inject 는 이 값을 그대로 배포한다
    hotels = master['hotels']
    cells = sum(len(h.get('rates') or {}) for h in hotels)
    priced = sum(1 for h in hotels for v in (h.get('rates') or {}).values() if v is not None)
    tabs = {}
    for h in hotels:
        tabs[h.get('group')] = tabs.get(h.get('group'), 0) + 1
    stayplus = sum(len(h.get('stayplus2') or {}) + len(h.get('stayplus3') or {}) for h in hotels)
    routes = master['flights'].get('routes') or []
    master['counts'] = {
        'hotels': len(hotels), 'tabs': tabs, 'cells': cells, 'priced': priced,
        'na': cells - priced, 'stayplus': stayplus,
        'routes': len(routes), 'deals': sum(len(r.get('deals') or []) for r in routes),
        'snu': len(((master.get('accor') or {}).get('rows')) or []),
        'pus_deals': len(((master.get('ttang') or {}).get('deals')) or []),
        'pus_routes': len({d.get('code') for d in ((master.get('ttang') or {}).get('deals') or [])}),
        'redhot_hotels': sum(1 for h in hotels if h.get('redhot')),
        'redhot_cells': sum(len(h.get('redhotRates') or {}) for h in hotels),
    }
    master['generated_at'] = '2026-11-22 20:35 KST (레드핫 병합)'
    print('counts — 호텔 %(hotels)d곳 · ③ %(domestic)d곳 · 레드핫 %(redhot_hotels)d곳/%(redhot_cells)d칸'
          % dict(master['counts'], domestic=tabs.get('domestic', 0)))
    if dry:
        print('--dry-run — 파일을 쓰지 않았습니다')
        return 0
    with open(MASTER + '.tmp', 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(MASTER + '.tmp', MASTER)
    print('wrote data/master_db.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
