#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2027년 6~11월 부산 출발 항공 특가 3개 원본 → `data/master_db.json` flights 병합.

입력(고정 경로, /workspace 기준 상대):
  ../data-sources/flights-2027-06-11/부산출발-항공특가-2027년6-7월.csv   (주말 249 + 당일치기 11 = 260행)
  ../data-sources/flights-2027-06-11/부산출발-항공특가-2027년8-9월.md    (부록 기계판독 73줄)
  ../data-sources/flights-2027-06-11/부산출발-항공특가-2027년10-11월.md  (표에서 53칸 + 판매편 없음 4건)

규칙:
  · 원본에 적힌 실측값만 넣는다. 추정·보간 금지. `—`(미조회)·`미표시`·`0원`은 가격으로 넣지 않는다.
  · 판매편이 없던 칸(0건)은 deals 가 아니라 `flights.noSale` 에 따로 적는다(가격 아님).
  · 기존 2026-12~2027-02 건은 1건도 건드리지 않고, 새 건은 각 노선 deals 끝(날짜 오름차순)에 붙인다.
  · 노선·주차·패턴 목록과 counts 를 다시 세고, 월 이동이 2026-12~2027-11 1년을 덮도록 months/weeks 를 채운다.
  · 호텔 데이터는 읽기만 한다.

사용법:
    python3 tools/merge_flights_2027_h2.py --dry-run
    python3 tools/merge_flights_2027_h2.py --note "…KST ④ 항공 2027년 6~11월 반영"
"""
import argparse
import collections
import csv
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.join(os.path.dirname(os.path.dirname(ROOT)), 'data-sources', 'flights-2027-06-11')
CSV_67 = os.path.join(SRC, '부산출발-항공특가-2027년6-7월.csv')
MD_89 = os.path.join(SRC, '부산출발-항공특가-2027년8-9월.md')
MD_1011 = os.path.join(SRC, '부산출발-항공특가-2027년10-11월.md')

PAT_ORDER = ['목~일', '금~일', '토~월', '목~월', '금~월',
             '목~목', '금~금', '토~토', '일~일', '월~월', '화~화', '수~수', '화~목', '토~화']
WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
WINDOW_START, WINDOW_END = '2026-12-01', '2027-11-30'
LAST_MONTH = '2027-11'
BOOKING_END = '2027-11-14'

# 10월 1~3 주말 노선별 최저가 편 구성(보고서 3장 '노선별 항공사·직항 실측 비고')
OCT1_ROUTE = {
    'FUK': ('이스타항공', False, '직항 1시간(14:50-16:00)'),
    'KIX': ('이스타항공', False, '직항 1시간 30분(13:30-15:00)'),
    'TYO': ('대한항공', False, '직항 2시간 15분(NRT 09:20-11:35)'),
    'TPE': ('타이거에어타이완', False, '직항 2시간 20분'),
    'HKG': (None, False, '직항 3시간 35분(14:20-16:55)'),
    'MFM': ('중국동방항공', True, '경유(상하이) · 직항 없음'),
    'PVG': ('중국동방항공', False, '직항 1시간 50분(12:35-13:25)'),
    'BKK': ('베트남항공', True, '경유(하노이) · 직항 없음'),
    'DAD': ('베트남항공', True, '경유(나트랑) · 직항 없음'),
    'CXR': (None, None, '직항 최저 511,400원 · 최저가 편 구성 미확인'),
    'NKG': (None, True, '경유 · 직항 없음'),
    'SGN': (None, None, '직항 최저 530,700원 · 최저가 편 구성 미확인'),
    'SIN': (None, True, '경유 · 직항 없음(직항 최저 931,600원)'),
    'GUM': (None, True, '경유 · 직항 없음'),
    'NGO': (None, True, '경유 · 직항 없음'),
    'OKA': (None, True, '경유(후쿠오카) · 직항 없음'),
    'HGH': (None, True, '경유 · 직항 없음'),
    'TAO': (None, True, '경유(서울) · 직항 없음'),
    'HAN': (None, None, '직항 최저 483,400원 · 최저가 편 구성 미확인'),
    'CNX': (None, True, '경유 · 직항 없음'),
    'DPS': (None, True, '경유 · 직항 없음'),
    'KHH': (None, True, '경유(홍콩) · 직항 없음'),
    'RMQ': (None, False, '직항'),
    'BJS': (None, False, '직항'),
}
# 10월 1~3 주말 표의 열 → (패턴, 출발일)
OCT1_COLS = [('목~일', '2027-09-30'), ('금~일', '2027-10-01'),
             ('토~월', '2027-10-02'), ('목~월', '2027-09-30'), ('금~월', '2027-10-01')]

PROBLEMS = []


def warn(msg):
    PROBLEMS.append(msg)


def add_days(iso, n):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=n)).isoformat()


def nights_of(label):
    a, b = label.split('~')
    return (WD[b] - WD[a]) % 7


def wd_of(iso):
    return datetime.date.fromisoformat(iso).isoweekday() % 7  # 월=1 … 일=0


def deal(code, date, pattern, price, **kw):
    """deal dict 생성 + 공통 검증."""
    if not isinstance(price, int) or price <= 0:
        raise ValueError('%s %s %s 가격 이상: %r' % (code, date, pattern, price))
    if not (WINDOW_START <= date <= WINDOW_END):
        raise ValueError('%s %s 날짜 창 밖' % (code, date))
    n = nights_of(pattern)
    if wd_of(date) != WD[pattern[0]]:
        raise ValueError('%s %s 출발 요일이 패턴 %s 와 다름' % (code, date, pattern))
    d = {'date': date, 'back': add_days(date, n), 'pattern': pattern, 'price': price}
    d.update({k: v for k, v in kw.items() if v is not None})
    return d


# ---------------------------------------------------------------- 6~7월 CSV

def parse_csv_67():
    out = []
    with open(CSV_67, encoding='utf-8-sig') as fp:
        for r in csv.DictReader(fp):
            price = int(r['price_krw'])
            src = '가격표' if r['source'] == 'calendar' else '실시간'
            kw = {'src': src, 'via': None, 'note': '가격표 실측 · 직항/경유 미확인'}
            if r['source'] != 'calendar':
                # 개별 날짜 실시간 검색 2건(보고서 「실측된 당일치기 칸」 비고)
                if r['code'] == 'FUK':
                    kw = {'src': '실시간', 'airline': '이스타항공', 'via': False,
                          'note': '직항 09:55 도착→16:55 출발 · 체류 7시간 0분'}
                else:
                    kw = {'src': '실시간', 'airline': '이스타항공+대한항공', 'via': None,
                          'note': '가는편 이스타항공 직항·오는편 대한항공 서울 경유 · 체류 4시간 35분~5시간 30분 · 다음 날 08:05 부산 도착'}
            out.append((r['code'], deal(r['code'], r['ddate'], r['pattern'], price, **kw),
                        r['rdate']))
            if r['rdate'] != add_days(r['ddate'], nights_of(r['pattern'])):
                warn('CSV 귀국일 불일치 %s %s %s' % (r['code'], r['ddate'], r['pattern']))
    return out


# ---------------------------------------------------------------- 8~9월 부록

LINE_89 = re.compile(r'^- (2027-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · '
                     r'PUS–([A-Z]{3}) · ([\d,]+)원 · (.*)$')


def parse_89():
    text = open(MD_89, encoding='utf-8').read()
    if '## 8. 앱 병합용 부록' not in text:
        raise SystemExit('8~9월 보고서에서 부록 절을 찾지 못했습니다')
    sec = text.split('## 8. 앱 병합용 부록', 1)[1]
    out = []
    for line in sec.splitlines():
        m = LINE_89.match(line.strip())
        if not m:
            continue
        date, pattern, code, price, rest = m.groups()
        fields = [f.strip() for f in rest.split('·')]
        airline_txt, src_txt = fields[0], fields[-1]
        src = '실시간' if 'search' in src_txt else '캘린더' if 'strip' in src_txt else '실시간'
        kw = {'src': src}
        mm = re.match(r'^(.*?)\s*경유\(([^)]*)\)\s*(.*)$', airline_txt)
        if mm:
            kw['airline'] = mm.group(1).strip() or None
            kw['via'] = True
            kw['note'] = '경유(%s)' % mm.group(2)
        elif airline_txt in ('NRT', 'HND'):
            kw['airline'] = '대한항공'
            kw['via'] = False
            kw['note'] = '직항(%s)' % airline_txt
        else:
            kw['airline'] = airline_txt
            kw['via'] = False
            kw['note'] = '직항'
        out.append((code, deal(code, date, pattern, int(price.replace(',', '')), **kw), None))
    return out


# ---------------------------------------------------------------- 10~11월 표

def cell_num(s):
    s = s.strip().replace('*', '').replace(',', '')
    if not re.fullmatch(r'\d+', s):
        return None
    v = int(s)
    return v if v > 0 else None


def md_table_rows(text):
    rows = []
    for line in text.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
    return rows


def parse_1011():
    text = open(MD_1011, encoding='utf-8').read()
    out, nosale = [], []

    # 3장 — 2027년 10월 1~3 주말 (24개 노선 × 5패턴)
    sec3 = text.split('## 3. 2027년 10월 1~3 주말 실측', 1)[1].split('### 노선별', 1)[0]
    for cells in md_table_rows(sec3):
        m = re.match(r'^(.+?) \(([A-Z]{3})(?:[^)]*)\)$', cells[0]) if cells else None
        if not m:
            continue
        code = m.group(2)
        if code not in OCT1_ROUTE:
            warn('10월 표 노선 코드 미확인 %s' % code)
            continue
        airline, via, note = OCT1_ROUTE[code]
        for (pattern, date), raw in zip(OCT1_COLS, cells[1:1 + len(OCT1_COLS)]):
            v = cell_num(raw)
            if v is None:
                continue
            out.append((code, deal(code, date, pattern, v, airline=airline, via=via, note=note), None))

    # 3-2장 — 10/8·10/15 금~일 4개 노선
    sec32 = text.split('## 3-2.', 1)[1].split('## 4.', 1)[0]
    for cells in md_table_rows(sec32):
        m = re.match(r'^(.+?) \(([A-Z]{3})(?:[^)]*)\)$', cells[0]) if cells else None
        if not m:
            continue
        code = m.group(2)
        for date, raw in zip(('2027-10-08', '2027-10-15'), cells[2:4]):
            v = cell_num(raw)
            if v is None:
                continue
            kw = {'via': False, 'note': '직항'}
            if code == 'FUK':
                kw['airline'] = '이스타항공'
                kw['note'] = '직항(14:50-16:00)'
            out.append((code, deal(code, date, '금~일', v, **kw), None))

    # 4장 — 당일치기 2칸
    sec4 = text.split('## 4. 당일치기(0박 1일) 실측', 1)[1].split('## 5.', 1)[0]
    day_air = {'FUK': ('이스타항공', '직항(08:55-09:55) · 체류 미확인'),
               'TPE': ('대한항공', '직항(09:00-10:30) · 체류 미확인')}
    for cells in md_table_rows(sec4):
        m = re.match(r'^(.+?) \(([A-Z]{3})(?:[^)]*)\)$', cells[0]) if cells else None
        if not m:
            continue
        code, pattern, date = m.group(2), cells[1].strip(), cells[2].strip()
        v = cell_num(cells[3])
        if v is None or code not in day_air:
            continue
        airline, note = day_air[code]
        out.append((code, deal(code, date, pattern, v, airline=airline, via=False, note=note), None))

    # 3-2장 머리말 + 5장 — 10/29~31·11/5~7 후쿠오카(경유만)
    out.append(('FUK', deal('FUK', '2027-10-29', '금~일', 601700, airline='대한항공', via=True,
                            note='경유(서울 1회) · 직항 없음'), None))
    out.append(('FUK', deal('FUK', '2027-11-05', '금~일', 664700, airline='대한항공', via=True,
                            note='경유(서울 1시간 35분) · 직항 없음'), None))

    # 6장 — 조회했으나 판매편이 없던 4건 (가격 아님)
    nosale = [
        {'code': 'FUK', 'date': '2027-11-12', 'back': '2027-11-14', 'pattern': '금~일',
         'note': '검색 결과 0건(판매편 없음)'},
        {'code': 'TYO', 'date': '2027-11-12', 'back': '2027-11-14', 'pattern': '금~일',
         'note': '검색 결과 0건(판매편 없음)'},
        {'code': 'TYO', 'date': '2027-11-16', 'back': '2027-11-18', 'pattern': '화~목',
         'note': '검색 결과 0건(판매편 없음)'},
        {'code': 'FUK', 'date': '2027-11-20', 'back': '2027-11-23', 'pattern': '토~화',
         'note': '검색 결과 0건(판매편 없음)'},
    ]
    return out, nosale


# ---------------------------------------------------------------- 주차·월

def build_weeks(existing):
    by_thu = {w['thu']: w for w in existing}
    thu = datetime.date(2026, 12, 3)
    last = datetime.date(2027, 11, 25)
    out = []
    while thu <= last:
        iso = thu.isoformat()
        if iso in by_thu:
            out.append(by_thu[iso])
        else:
            month = iso[:7]
            nth = (thu.day - 1) // 7 + 1
            mon, mday = int(iso[5:7]), int(iso[8:10])
            end = add_days(iso, 6)
            out.append({'thu': iso, 'month': month, 'label': '%d월 %d주' % (mon, nth),
                        'span': '%d/%d~%d/%d' % (mon, mday, int(end[5:7]), int(end[8:10])),
                        'end': end})
        thu += datetime.timedelta(days=7)
    return out


def month_notes():
    pending = ('이 달은 아직 조사 전입니다(미수신). 빈칸(—)은 추정하지 않은 칸입니다.')
    return {
        '2027-03': pending, '2027-04': pending, '2027-05': pending,
        '2027-10': '예약창은 2027-11-14까지입니다. 10월은 첫 주말(10/1~3)과 10/8~10·10/15~17·10/29~31 일부만 실측했습니다.',
        '2027-11': '예약창은 2027-11-14까지이고 그 뒤 출발일은 달력에서 선택되지 않습니다. 실측은 11/5~7 후쿠오카 1칸이며 11/11~14·11/16~18·11/20~23은 판매편이 없었습니다.',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args()

    master = json.load(open(MASTER, encoding='utf-8'))
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    before = {r['code']: [dict(d) for d in r['deals']] for r in fl['routes']}
    before_total = sum(len(r['deals']) for r in fl['routes'])
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False, sort_keys=True)

    items = [(c, d) for c, d, _ in parse_csv_67()]
    items += [(c, d) for c, d, _ in parse_89()]
    sep_out, nosale = parse_1011()
    items += [(c, d) for c, d, _ in sep_out]

    seen = set()
    for code, d in items:
        if code not in routes:
            raise SystemExit('알 수 없는 노선 %s' % code)
        key = (code, d['date'], d['pattern'])
        if key in seen:
            raise SystemExit('새 데이터 안 중복: %s' % (key,))
        seen.add(key)

    # 기존 건과 겹치면 실패(기존 보존 원칙) — 겹치는 게 있으면 사람이 판단해야 한다
    for code, d in items:
        for old in routes[code]['deals']:
            if (old['date'], old['pattern']) == (d['date'], d['pattern']):
                raise SystemExit('기존 건과 겹침: %s %s %s' % (code, d['date'], d['pattern']))

    if not args.dry_run:
        # 기존 건은 순서까지 그대로 두고, 새 건만 각 노선 끝에 날짜·패턴 순으로 붙인다
        per = collections.defaultdict(list)
        for code, d in items:
            per[code].append(d)
        for code, new in per.items():
            new.sort(key=lambda x: (x['date'], PAT_ORDER.index(x['pattern'])
                                    if x['pattern'] in PAT_ORDER else 99))
            routes[code]['deals'] = routes[code]['deals'] + new

    # months / weeks
    months = []
    m = datetime.date(2026, 12, 1)
    while m.strftime('%Y-%m') <= LAST_MONTH:
        months.append(m.strftime('%Y-%m'))
        m = (m.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)

    if args.dry_run:
        new_total = before_total + len(items)
        print('[dry-run] new deals %d → total %d' % (len(items), new_total))
        print('  csv6-7 %d · md8-9 %d · md10-11 %d · noSale %d' % (
            len(parse_csv_67()), len(parse_89()), len(sep_out), len(nosale)))
        c = collections.Counter(d['date'][:7] for _, d in items)
        print('  byMonth', dict(sorted(c.items())))
        print('  weeks would be %d, months %d' % (len(build_weeks(fl['weeks'])), len(months)))
        for p in PROBLEMS:
            print('  ! ' + p)
        return 0

    fl['months'] = months
    fl['weeks'] = build_weeks(fl['weeks'])
    fl['noSale'] = nosale
    fl['notes'] = month_notes()
    fl['bookingWindow'] = {'end': BOOKING_END,
                           'note': '2027-11-14 이후 출발일은 날짜 선택이 되지 않습니다(조회 시점 기준).'}

    total = sum(len(r['deals']) for r in fl['routes'])
    by_month = collections.Counter(d['date'][:7] for r in fl['routes'] for d in r['deals'])
    daytrip = sum(1 for r in fl['routes'] for d in r['deals']
                  if d['pattern'][0] == d['pattern'][2])
    holiday = sum(1 for r in fl['routes'] for d in r['deals']
                  if d['date'] in ('2026-12-25', '2027-02-04'))
    fl['counts'] = {'total': total,
                    'byMonth': {k: by_month[k] for k in sorted(by_month)},
                    'holiday': holiday, 'daytrip': daytrip}

    # master_db.json 최상위 counts(호텔 지표는 그대로, 항공만 다시 센다)
    top = master.setdefault('counts', {})
    top['routes'] = len(fl['routes'])
    top['deals'] = total

    if args.note:
        master['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')
    master['generated_at'] = datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')

    # 기존 건 보존 확인
    for r in fl['routes']:
        after = r['deals']
        olds = before[r['code']]
        kept = [d for d in after if any(d == o for o in olds)]
        missing = [o for o in olds if not any(d == o for d in after)]
        if missing:
            raise SystemExit('기존 건 소실: %s %s' % (r['code'], missing[:2]))
        if len(kept) != len(olds):
            raise SystemExit('기존 건 순서/내용 변형: %s' % r['code'])
        if [o for o in after if o in olds] != olds:
            raise SystemExit('기존 건 순서 변형: %s' % r['code'])
    if json.dumps(master['hotels'], ensure_ascii=False, sort_keys=True) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다')

    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('merged %d건: %d → %d' % (len(items), before_total, total))
    print('  byMonth', fl['counts']['byMonth'])
    print('  daytrip %d · weeks %d · months %d · noSale %d' % (
        daytrip, len(fl['weeks']), len(months), len(nosale)))
    for p in PROBLEMS:
        print('  ! ' + p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
