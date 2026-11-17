#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **중국 신규 8개 노선**(선양·다롄·광저우·샤먼·연길·장가계·구이린·황산) 조사 md →
`data/master_db.json` 의 `flights` 병합 (노선 신설 + 주말형/당일치기).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_china_new8.py \
        ../data-sources/flights-china-new8/부산출발-중국4노선-선양다롄광저우샤먼-12_1월.md \
        ../data-sources/flights-china-new8/부산출발-중국4노선-연길장가계구이린황산-12_1월.md --dry-run

읽는 곳:
  · 부록 A (첫 파일) — `- 2026-12-03 · 목~일 · PUS–SHE · 335,100원 · Jin Air+Spring Airlines · 경유`
  · 5절 당일치기 표 + 부록 B (첫 파일) — `| 선양 (SHE) | 445,200원 | **성립(가능)** | … |
    `- 2026-12-05 · 토~토(당일) · PUS–CAN · 1,034,400원 · Korean Air+China Southern`
  · 부록 (둘째 파일) — `- 2026-12-03(목) · 목~일(3박) · PUS–YNJ · 304,800원 · Jeju Air · 경유(Seoul 7h40, 총11h15)`
  · 4절 당일치기 표 (둘째 파일) — `| DYG | 토~토 | 2026-12-05 | 성립 793,000원 | … |` / `불가(0건)`

규칙:
  · `—`·`미측정` 줄은 넣지 않는다(gaps 로만 보고). 추정·보간값을 만들지 않는다.
  · 조회했으나 **같은 날 복편이 없던** 칸(0건)은 가격이 아니라 `flights.noSale` 로 넣는다.
  · 노선 8개를 `flights.routes` 끝에 새로 만들고, 기존 24개 노선·기존 딜·호텔 배열은 건드리지 않는다.
  · 항공사·경유지 이름은 앱 표기(한국어)로 옮긴다 — 값 자체(가격·날짜·소요시간)는 원문 그대로.
  · `counts`(total · byMonth · holiday · daytrip)만 다시 센다. 호텔 지표는 그대로 둔다.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')

# 신설 노선 (브리프 지정 순서) — ①~④ 는 12월 1주~1월 5주, ⑤~⑧ 은 12~1월
NEW_ROUTES = [('SHE', '선양'), ('DLC', '다롄'), ('CAN', '광저우'), ('XMN', '샤먼'),
              ('YNJ', '연길'), ('DYG', '장가계'), ('KWL', '구이린'), ('TXN', '황산')]

# 원문 표기 → 앱 표기 (번역일 뿐, 값은 바꾸지 않는다)
AIRLINE_KO = {
    'Jin Air+Spring Airlines': '진에어+춘추항공',
    'Jin Air': '진에어',
    'Spring Airlines': '춘추항공',
    'China Eastern': '중국동방항공',
    'China Eastern(Shanghai Airlines 운항)': '중국동방항공(상하이항공 운항)',
    'Air China': '중국국제항공',
    'Korean Air': '대한항공',
    'Jeju Air': '제주항공',
    'Air Busan': '에어부산',
    'Shanghai Airlines': '상하이항공',
    'Eastar Jet+Jeju Air': '이스타항공+제주항공',
    'Korean Air+Asiana': '대한항공+아시아나항공',
    'Korean Air+China Eastern': '대한항공+중국동방항공',
    'Korean Air+China Southern': '대한항공+중국남방항공',
}
AIRPORT_KO = {'Seoul': '서울', 'Beijing': '베이징', 'Shanghai': '상하이',
              'Jeju': '제주', 'Nanjing': '난징', 'Guangzhou': '광저우'}

# 노선별 당일치기 메타 — 원문(첫 파일 5절 · 둘째 파일 4절)의 판정과 근거만 옮긴다
DAYTRIP_META = {
    'SHE': ('ok', '체류 미확인', '진에어+춘추항공 07:15 → 13:35(제주 4시간 5분 경유) · 같은 날 복편 선택 · 복편 시각·체류시간 미표시', ''),
    'DLC': ('ok', '체류 미확인', '같은 날 왕복 판매 확인(2박 363,600원과 사실상 같은 값) · 직항/경유·체류시간 미확인', ''),
    'CAN': ('ok', '체류 미확인', '성립하나 비현실적 — 대한항공+중국남방 12:00 → 18:05(서울 경유) · 1,034,400원 · 체류시간 미확인', ''),
    'XMN': ('ok', '체류 미확인', '성립하나 비현실적 — 12:35 → 16:55(상하이 1시간 30분 경유) · 621,800원 · 체류시간 미확인', ''),
    'YNJ': ('ok', '체류 미확인', '대한항공 07:00 → 10:50(서울 1시간 10분 경유) · 검색 7편 · 복편 시각 미표시', ''),
    'DYG': ('ok', '체류 미확인', '에어부산 직항 09:30 → 12:10(3시간 40분) · 검색 2편 · 복편 시각 미표시', ''),
    'KWL': ('no', '', '같은 날 복편 편성 없음 — 검색 결과 0편(상하이 경유만 있고 당일 복편 없음)', '같은 날 복편 없음'),
    'TXN': ('no', '', '같은 날 복편 편성 없음 — 검색 결과 0편(노선 자체가 매우 얇음)', '같은 날 복편 없음'),
}

LINE_F1 = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일])(?:\(당일\))? · '
                     r'PUS–([A-Z]{3}) · ([\d,]+)원(?: · (.+))?$')
LINE_F2 = re.compile(r'^- (\d{4}-\d{2}-\d{2})\([월화수목금토일]\) · ([월화수목금토일]~[월화수목금토일])'
                     r'(?:\(\d박\))? · PUS–([A-Z]{3}) · ([\d,]+)원(?: · (.+))?$')
LINE_F2_GAP = re.compile(r'^- (\d{4}-\d{2}-\d{2})\([월화수목금토일]\) · ([월화수목금토일]~[월화수목금토일])'
                         r'(?:\(\d박\))? · PUS–([A-Z]{3}) · (미측정|가격 미표시).*$')
TABLE_F1_DAY = re.compile(r'^\| (\S+) \(([A-Z]{3})\) \| ([\d,]+)원 \| (.+?) \| (.+?) \|$')
TABLE_F2_DAY = re.compile(r'^\| ([A-Z]{3}) \| ([월화수목금토일]~[월화수목금토일]) \| (\d{4}-\d{2}-\d{2}) \| '
                          r'(.+?) \| (.+?) \|$')


# ---------------------------------------------------------------- 값 표기 변환

def timespan(text):
    """'7h40' → '7시간 40분', '2h' → '2시간', '3시간40분' 은 그대로."""
    def one(m):
        h, mi = int(m.group(1)), m.group(2)
        return ('%d시간' % h) + (' %s분' % mi if mi and int(mi) else '')
    text = re.sub(r'(\d{1,2})h(\d{2})?\b', one, text)
    text = re.sub(r'총(\d)', r'총 \1', text)
    return text


def city_words(text):
    for en, ko in AIRPORT_KO.items():
        text = re.sub(r'\b%s\b' % en, ko, text)
    return text.replace('2 stops', '2회').replace('1 stop', '1회')


def norm_desc(desc):
    """원문 편구성 설명 → {airline, via, note, src}."""
    out = {}
    d = (desc or '').strip()
    if not d:
        return {'via': None, 'src': '가격표', 'note': '직항/경유 미확인'}
    if d == '직항/경유 미확인':
        return {'via': None, 'src': '가격표', 'note': d}
    m = re.fullmatch(r'경유\((.*)\)', d)
    if m:
        parts = [city_words(timespan(p.strip())) for p in m.group(1).split(',')]
        parts = [p for p in parts if p and p != '총']
        out['via'] = True
        out['note'] = '경유' + ('(%s)' % ', '.join(parts) if parts else '')
        return out
    m = re.fullmatch(r'직항\((.*)\)', d)
    if m:
        parts = [timespan(city_words(p.strip())) for p in m.group(1).split(',')
                 if p.strip() and p.strip() not in ('무경유', '총')]
        out['via'] = False
        out['note'] = '직항' + ('(%s)' % ', '.join(parts) if parts else '')
        return out
    if d.startswith('경유'):
        out['via'] = True
        out['note'] = '경유'
        return out
    if d.startswith('직항'):
        out['via'] = False
        out['note'] = d
        return out
    out['via'] = None
    out['note'] = d
    return out


def parse_info(airline_raw, desc):
    """항공사 + 설명 → deal 에 붙일 필드."""
    out = norm_desc(desc)
    a = (airline_raw or '').strip()
    if not a:
        return out
    m = re.fullmatch(r'항공사 미확인(?:\(([^)]*)\))?', a)
    if m:
        out['src'] = '가격표'
        return out
    ko = AIRLINE_KO.get(a, a)
    if ko == a and re.search(r'[A-Za-z]', a):
        raise SystemExit('모르는 항공사 표기입니다(번역표에 추가 필요): %s' % a)
    out['airline'] = ko
    return out


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    nights = (WD[b] - WD[a]) % 7 or 7
    return (start + datetime.timedelta(days=nights)).isoformat()


def deal_of(date, pattern, price, info):
    deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern, 'price': int(price)}
    for k in ('airline', 'via', 'note', 'src'):
        if info.get(k) is not None:
            deal[k] = info[k]
    return deal


# ---------------------------------------------------------------- 파싱

def day_note(text):
    """당일치기 표의 근거 문장 → 앱 메모(시간·도시 이름만 한국어 표기로)."""
    t = timespan(city_words(text.strip()))
    t = t.replace('·', ' · ').replace('. ', ' · ').strip(' .·')
    return re.sub(r'\s+', ' ', t)


def merge_day(daytrip, extra, answers):
    """당일치기 표의 근거를 반영하고, 0박(back=date)으로 고정한다."""
    for (code, date, pattern), deal in daytrip.items():
        info = answers.get(code)
        if info:
            price, verdict, why = info
            if deal['price'] != price:
                raise SystemExit('당일치기 금액 불일치 %s: 부록 %s원 / 표 %s원' % (code, deal['price'], price))
            body = why
            head, sep, tail = body.partition(',')
            if sep and ('항공' in head or 'Airlines' in head or 'Air' in head) and len(head) < 40:
                body = tail.strip()            # 근거 앞에 붙은 항공사 이름은 이미 airline 필드에 있다
            if '직항' in why and '경유' not in why:
                deal['via'] = False
            elif '경유' in why:
                deal['via'] = True
            note = day_note(body)
            if '비현실적' in verdict:
                note = '성립하나 비현실적 · ' + note
            deal['note'] = note
            deal.pop('src', None)
        deal['back'] = deal['date']            # 0박 1일 — 같은 날 귀국


def parse_first(text):
    """첫 파일 — 부록 A(주말형 84줄) + 5절 당일치기 표/부록 B(4줄)."""
    weekend, daytrip, gaps = {}, {}, []
    day_rows_f1 = {}
    for line in text.splitlines():
        m = TABLE_F1_DAY.match(line.strip())
        if m:
            city, code, price, verdict, why = m.groups()
            day_rows_f1[code] = (int(price.replace(',', '')), verdict, why)
            continue
        m = LINE_F1.match(line.strip())
        if not m:
            continue
        date, pattern, code, price, rest = m.groups()
        rest = (rest or '').strip()
        if '당일' in line and pattern.split('~')[0] == pattern.split('~')[1]:
            fields = [f.strip() for f in rest.split(' · ')]
            info = parse_info(fields[0] if fields else '', '')
            daytrip[(code, date, pattern)] = deal_of(date, pattern, price.replace(',', ''), info)
            continue
        fields = [f.strip() for f in rest.split(' · ')]
        airline = fields[0] if fields else ''
        desc = ' · '.join(fields[1:]) if len(fields) > 1 else ''
        if not airline and not desc:
            gaps.append((code, date, pattern, rest))
            continue
        weekend[(code, date, pattern)] = deal_of(date, pattern, price.replace(',', ''), parse_info(airline, desc))
    merge_day(daytrip, None, day_rows_f1)
    return weekend, daytrip, day_rows_f1, gaps


def parse_second(text):
    """둘째 파일 — 부록(87줄 실측 + 미측정 줄) + 4절 당일치기 표(성립 2 · 불가 2)."""
    weekend, daytrip, nosale, gaps = {}, {}, {}, []
    for line in text.splitlines():
        s = line.strip()
        m = TABLE_F2_DAY.match(s)
        if m:
            code, pattern, date, result, why = m.groups()
            why = why.strip()
            if result.startswith('성립'):
                price = re.search(r'([\d,]+)원', result)
                if not price:
                    raise SystemExit('당일치기 표에서 금액을 읽지 못했습니다: %s' % s)
                airline = None
                for en, ko in sorted(AIRLINE_KO.items(), key=lambda x: -len(x[0])):
                    if '+' in en:
                        continue
                    if why.startswith(en):
                        airline = ko
                        why = why[len(en):].strip()
                        break
                if airline is None:
                    mair = re.match(r'^((?:[가-힣]+항공|에어부산)(?:\+[가-힣]+항공)?)\s+', why)
                    if mair:
                        airline = mair.group(1)
                        why = why[mair.end():].strip()
                via = False if why.startswith('직항') else (True if '경유' in why.split('·')[0] else None)
                info = {'via': via, 'note': day_note(why)}
                if airline:
                    info['airline'] = airline
                daytrip[(code, date, pattern)] = deal_of(date, pattern, price.group(1).replace(',', ''), info)
            else:
                nosale[(code, date, pattern)] = {'code': code, 'date': date, 'back': date, 'pattern': pattern,
                                                 'note': '검색 결과 0건(판매편 없음)'}
            continue
        m = LINE_F2_GAP.match(s)
        if m:
            gaps.append(m.group(3, 1, 2))
            continue
        m = LINE_F2.match(s)
        if not m:
            continue
        date, pattern, code, price, rest = m.groups()
        fields = [f.strip() for f in (rest or '').split(' · ')]
        airline = fields[0] if fields else ''
        desc = ' · '.join(fields[1:]) if len(fields) > 1 else ''
        if not re.search(r'\d', desc) and desc.startswith('경유') and not airline:
            gaps.append((code, date, pattern, desc))
            continue
        weekend[(code, date, pattern)] = deal_of(date, pattern, price.replace(',', ''), parse_info(airline, desc))
    for deal in daytrip.values():
        deal['back'] = deal['date']            # 0박 1일
    return weekend, daytrip, nosale, gaps


# ---------------------------------------------------------------- 병합

def merge(master, weekend, daytrip, nosale, dry=False):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    added_routes, added, skipped = [], [], []

    for code, city in NEW_ROUTES:
        if code in routes:
            continue
        r = {'code': code, 'city': city, 'extra': '', 'deals': []}
        status, stay, note, short = DAYTRIP_META[code]
        r['daytrip'] = {'status': status, 'stay': stay, 'note': note, 'short': short}
        fl['routes'].append(r)
        routes[code] = r
        added_routes.append((code, city))

    for (code, date, pattern), deal in sorted(weekend.items()) + sorted(daytrip.items()):
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)
        r = routes[code]
        if any(d['date'] == date and d['pattern'] == pattern for d in r['deals']):
            skipped.append((code, date, pattern))
            continue
        r['deals'].append(deal)
        added.append((code, date, pattern, deal['price']))

    for r in fl['routes']:
        r['deals'].sort(key=lambda d: d['date'])

    known = {(n['code'], n['date'], n['pattern']) for n in fl['noSale']}
    new_nosale = []
    for key, entry in sorted(nosale.items()):
        if key in known:
            continue
        fl['noSale'].append(entry)
        new_nosale.append(key)
    fl['noSale'].sort(key=lambda n: (n['date'], n['code']))

    all_deals = [d for r in fl['routes'] for d in r['deals']]
    by_month = {}
    for d in all_deals:
        by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    fl['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month[k] for k in sorted(by_month)},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals if d['pattern'].split('~')[0] == d['pattern'].split('~')[1]),
    }
    master['counts']['routes'] = len(fl['routes'])
    master['counts']['deals'] = len(all_deals)
    return added_routes, added, skipped, new_nosale


def main(argv):
    ap = argparse.ArgumentParser(description='중국 신규 8노선 md → master_db.json flights 병합')
    ap.add_argument('md', nargs=2, help='첫 파일(선양·다롄·광저우·샤먼) 둘째 파일(연길·장가계·구이린·황산)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text1 = open(args.md[0], encoding='utf-8').read()
    text2 = open(args.md[1], encoding='utf-8').read()
    w1, d1, day_f1, g1 = parse_first(text1)
    w2, d2, ns2, g2 = parse_second(text2)

    # 원문이 말하는 건수와 파싱 결과가 정확히 맞는지 먼저 확인한다(조용한 누락 금지)
    checks = [('첫 파일 주말형 84줄', len(w1), 84), ('첫 파일 당일치기 4줄', len(d1), 4),
              ('둘째 파일 주말형 87줄', len(w2), 87), ('둘째 파일 당일치기 성립 2줄', len(d2), 2),
              ('둘째 파일 당일치기 불가 2줄', len(ns2), 2), ('첫 파일 5절 당일치기 표 4줄', len(day_f1), 4)]
    bad = [(n, got, want) for n, got, want in checks if got != want]
    for n, got, want in checks:
        print('  %-28s %3d / %3d' % (n, got, want))
    if bad:
        raise SystemExit('원문 건수와 파싱 결과가 다릅니다: %s' % bad)
    print('  미측정 줄 %d개(첫 %d · 둘째 %d) — 넣지 않고 gaps 로 보고' % (len(g1) + len(g2), len(g1), len(g2)))

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    before_total = master['flights']['counts']['total']
    before_routes = [(r['code'], len(r['deals'])) for r in master['flights']['routes']]
    before_deep = json.dumps([r['deals'] for r in master['flights']['routes']], ensure_ascii=False)

    added_routes, added, skipped, new_nosale = merge(master, w1 | w2 if False else {**w1, **w2},
                                                     {**d1, **d2}, {**ns2})

    # 기존 24개 노선·딜이 한 건도 바뀌지 않았는지 확인
    after_routes = [(r['code'], len(r['deals'])) for r in master['flights']['routes']
                    if r['code'] not in dict(NEW_ROUTES)]
    if after_routes != before_routes:
        raise SystemExit('기존 노선 구성이 달라졌습니다: %s → %s' % (before_routes, after_routes))
    after_deep = json.dumps([r['deals'] for r in master['flights']['routes']
                             if r['code'] not in dict(NEW_ROUTES)], ensure_ascii=False)
    before_deep_old = json.dumps([d for (code, _), d in zip(before_routes,
                                                            json.loads(before_deep)) if code not in dict(NEW_ROUTES)],
                                 ensure_ascii=False)
    if after_deep != before_deep_old:
        raise SystemExit('기존 노선의 딜 내용이 달라졌습니다(호텔·항공 보존 실패).')
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')

    print('노선 신설 %d개: %s' % (len(added_routes), ', '.join('%s %s' % x for x in added_routes)))
    print('신규 딜 %d건 (중복 %d건) · 총 %d건 → %d건' % (len(added), len(skipped), before_total,
                                                  master['flights']['counts']['total']))
    per = {}
    for code, date, pattern, price in added:
        per[code] = per.get(code, 0) + 1
    print('노선별 신규: %s' % ', '.join('%s %d' % (c, per.get(c, 0)) for c, _ in NEW_ROUTES))
    print('신규 noSale %d건: %s' % (len(new_nosale), new_nosale))
    print('월별: %s' % master['flights']['counts']['byMonth'])
    print('주말형 %d · 당일치기 %d · holiday %d' % (
        master['flights']['counts']['total'] - master['flights']['counts']['daytrip'],
        master['flights']['counts']['daytrip'], master['flights']['counts']['holiday']))
    if os.environ.get('MERGE_VERBOSE'):
        for a in added:
            print('  + %s %s %s %s원' % a)

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        return 0
    if args.note:
        master['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('wrote %s' % os.path.relpath(MASTER, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
