#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 항공 특가 md(5패턴 실측 보고서)를 `data/master_db.json` 의 `flights` 에 병합한다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_batch.py ../보고서1.md ../보고서2.md --dry-run
    python3 tools/merge_flights_batch.py ../보고서1.md ../보고서2.md --note "…KST ④ 항공 보완 반영"

읽는 줄 형식(보고서마다 조금씩 다르다):
    - 2026-12-03 · 목~일 · PUS–MFM · 308,200원 · 중국동방항공 경유(난징 13h, 총18h) 직항없음   (보완2차)
    - 2026-12-04 · ①금~일 · PUS–OKA · 465,500원 · 항공사 미확인(가격표)                        (보완3차)
    - 2026-12-03(목) · 목~일(3박) · PUS–RMQ · 435,300원 · 항공사 미확인(가격표 실측) · 직항/경유 미확인
    - 12/03 · 목~일 · 385,600원 · 가격표 실측                                                  (보완1차, 노선은 ## 헤딩)
    - 12/04 · 금~월 · 미측정                                                                   (미측정 → gaps)

주차별 완본(2027년 2월 2~4주차) 형식 — 도시 이름/코드가 줄에 있거나 ## 헤딩에 있다:
    - 2027-02-11 · 목~월 · 부산–후쿠오카(FUK) · 263,900원 · 에어부산 · 직항 1시간 (4박)          (2주차)
    - 2/19 · ① · 부산–상하이 · 379,600원 · 춘추항공 · 직항 1시간55분(22:10-23:05)              (3주차, 노선은 ### 헤딩)
    - 2027-02-26 · 금~일·2박 · PUS–PVG · 417,500원 · 중국남방항공 · 경유(선양, 총7시간25분) (직항 최저 420,400원)

  · ①~⑤ 만 적힌 줄은 ①금~일 ②토~월 ③목~일 ④금~월 ⑤목~월 로 읽고, 출발일의 요일과 맞는지 검사한다.
  · '(직항 최저 …원)' 은 alt 로 살리고, '(N박)'·'←이 노선 최저' 같은 표시는 메모에서 뺀다.

규칙:
  · 보고서의 줄만 읽는다. 추정값은 만들지 않는다. '미측정'·'가격 미표시' 줄은 gaps 로만 보고한다.
  · 같은 (노선, 출발일, 패턴) 이 이미 있으면 **기존 건을 그대로 둔다**(완본의 항공사·직항 정보 보존).
    기존 건에 항공사가 비어 있고 새 보고서에 있으면 그 항목만 채운다.
  · 병기된 '(가격표 …원)' 캐시값은 넣지 않고, '직항 최저 …원' 은 alt 로 살린다.
  · 노선·주차·패턴 목록(`routes`/`weeks`/`patterns`)은 그대로 두고 `counts` 만 다시 센다.
    counts.holiday 는 기존 정의(2026-12-25 · 2027-02-04 출발 건수)를 그대로 따른다.
  · 호텔 데이터(`hotels`)는 읽기만 하고 절대 건드리지 않는다.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

CIRCLED_PAT = {'①': '금~일', '②': '토~월', '③': '목~일', '④': '금~월', '⑤': '목~월'}
PAT_ORDER = ['목~일', '금~일', '토~월', '목~월', '금~월',
             '목~목', '금~금', '토~토', '일~일', '월~월', '화~화', '수~수',
             '일~수', '일~목', '월~수']  # 주말형 5패턴 → 당일치기 → 보조 창구
WD = {'월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6, '일': 0}
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
CIRCLED = '①②③④⑤'

ROUTE = re.compile(r'^#{2,3} 부산\s*–\s*(.+?)\s*\(([A-Z]{3})')
LINE_FULL = re.compile(r'^- (\d{4}-\d{2}-\d{2})(?:\([월화수목금토일]\))? · '
                       r'([①②③④⑤]?[월화수목금토일]~[월화수목금토일])(?:\(\d박\))? · '
                       r'PUS–([A-Z]{3}) · (.+)$')
LINE_SHORT = re.compile(r'^- (\d{2})/(\d{2}) · '
                        r'([①②③④⑤]?[월화수목금토일]~[월화수목금토일]) · (.+)$')
LINE_SHORT_CODE = re.compile(r'^- (\d{2})/(\d{2}) · '
                             r'([①②③④⑤]?[월화수목금토일]~[월화수목금토일]) · '
                             r'PUS–([A-Z]{3}) · (.+)$')
LINE_CITY = re.compile(r'^- (\d{2})/(\d{2}) · '
                       r'([①②③④⑤]?[월화수목금토일]~[월화수목금토일]) · '
                       r'[^·]+\(([A-Z]{3})\) · (.+)$')
UNKNOWN = re.compile(r'^항공사 미확인\(([^)]*)\)\s*(.*)$')
DIRECT = re.compile(r'직항\s*(?:최저\s*)?(?:(\S+)\s+)?([\d,]{4,})\s*원?')


# ---------------------------------------------------------------- 파싱

def parse_md(path, codes_by_city=None):
    """보고서 md → (deals, gaps). deals 는 (code, deal dict) 목록."""
    with open(path, encoding='utf-8') as fp:
        text = fp.read()
    codes_by_city = codes_by_city or {}
    deals, gaps, code, city = [], [], None, None
    for raw in text.splitlines():
        line = raw.strip()
        m = ROUTE.match(line)
        if m:
            city = m.group(1).strip()
            code = codes_by_city.get(city) or m.group(2)
            continue
        v2 = parse_week_line(line, code, city, codes_by_city)
        if v2 is not None:
            if v2[0] == 'gap':
                gaps.append(v2[1])
            else:
                deals.append((v2[0], v2[1]))
            continue
        m = LINE_FULL.match(line)
        if m:
            date, pattern, rcode, rest = m.groups()
        else:
            m = LINE_CITY.match(line)
            if m:
                mm, dd, pattern, rcode, rest = m.groups()
                date = '%s-%s-%s' % ('2026' if mm == '12' else '2027', mm, dd)
            else:
                m = LINE_SHORT_CODE.match(line)
                if m:
                    mm, dd, pattern, rcode, rest = m.groups()
                else:
                    m = LINE_SHORT.match(line)
                    if not m or not code:
                        continue
                    mm, dd, pattern, rest = m.groups()
                    rcode = code
                year = '2026' if mm == '12' else '2027'   # 12월 = 2026, 01월 = 2027
                date = '%s-%s-%s' % (year, mm, dd)
        pattern = pattern.lstrip(CIRCLED)
        if '미측정' in rest or '가격 미표시' in rest:
            gaps.append((rcode, date, pattern, rest))
            continue
        fields = [f.strip() for f in rest.split(' · ')]
        pm = re.match(r'([\d,]+)원', fields[0])
        if not pm:
            gaps.append((rcode, date, pattern, rest))
            continue
        price = int(pm.group(1).replace(',', ''))

        airline, desc = None, ''
        if len(fields) >= 3:
            if not is_unknown(fields[1]):
                airline = fields[1]
            desc = ' · '.join(fields[2:])
        elif len(fields) == 2:
            desc = fields[1]

        deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern, 'price': price}
        deal.update(parse_info(airline, desc))
        deals.append((rcode, deal))
    return deals, gaps


def parse_week_line(line, heading_code, heading_city, codes_by_city):
    """주차별 완본(2주차·3주차·4주차) 줄 → (code, deal) | ('gap', (...)) | None.

    세 보고서의 줄 모양을 필드 순서로 읽는다: 출발일 · 패턴 · 노선 · 금액 · 항공사 · 직항/경유.
    모양이 맞지 않으면 None 을 돌려주고, 기존 파서가 이어서 읽는다.
    """
    if not line.startswith('- ') or line.startswith('- 참고'):
        return None
    body = line[2:].strip()
    body = re.sub(r'\s*←.*$', '', body)          # '←이 노선 최저' 표시는 메모가 아니다
    parts = [p.strip() for p in body.split(' · ')]
    if len(parts) < 4:
        return None
    # 이 세 보고서의 모양만 받는다(다른 보고서의 줄은 기존 파서가 읽는다)
    if not (parts[2].startswith('부산–')                    # 도시 이름으로 적은 노선 (2주차)
            or parts[1] in CIRCLED_PAT                       # ①~⑤ 만 적은 패턴 (3주차)
            or re.search(r'·\d박', parts[1])):               # '금~일·2박' 패턴 (4주차)
        return None

    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', parts[0])
    if m:
        date = '%s-%s-%s' % m.groups()
    else:
        m = re.fullmatch(r'(\d{1,2})/(\d{1,2})', parts[0])
        if not m:
            return None
        mm, dd = int(m.group(1)), int(m.group(2))
        date = '%s-%02d-%02d' % ('2026' if mm == 12 else '2027', mm, dd)

    token = parts[1]
    if token in CIRCLED_PAT:
        pattern = CIRCLED_PAT[token]
    else:
        m = re.match(r'([월화수목금토일]~[월화수목금토일])', re.sub(r'[·(]\d박\)?', '', token))
        if not m:
            return None
        pattern = m.group(1)

    rp = parts[2]
    m = re.search(r'\(([A-Z]{3})\)', rp)
    if m:
        code = m.group(1)
    elif rp.startswith('PUS–'):
        code = rp[4:].strip()
    else:
        name = re.sub(r'^부산\s*–\s*', '', rp).strip()
        code = codes_by_city.get(name) or heading_code
    if not code:
        return None

    pm = re.fullmatch(r'([\d,]+)원', parts[3])
    if not pm:
        return ('gap', (code, date, pattern, parts[3]))
    price = int(pm.group(1).replace(',', ''))

    airline = parts[4] if len(parts) >= 5 else None
    desc = ' · '.join(parts[5:]) if len(parts) > 5 else ''
    back = back_date(date, pattern)
    deal = {'date': date, 'back': back, 'pattern': pattern, 'price': price}
    deal.update(parse_info_v2(airline, desc))
    return (code, deal)


def parse_info_v2(airline, desc):
    """주차별 완본의 항공사 + 설명 → {airline, via, note, alt, src}."""
    out = {}
    d = (desc or '').strip()
    m = re.search(r'\s*\(직항\s*최저\s*([\d,]+)\s*원?([^)]*)\)', d)
    if m:
        out['alt'] = int(m.group(1).replace(',', ''))
        extra = m.group(2).strip()
        d = (d[:m.start()] + (' ※직항 최저 %s %s' % (m.group(1), extra) if extra else '')).strip()
    d = re.sub(r'\s*\(\d박\)\s*$', '', d)       # '(4박)' 은 패턴이 이미 말한다
    m = re.fullmatch(r'직항\s*\((.+)\)', d)
    if m:                                        # '직항 (1시간)' → '직항 1시간'
        d = '직항 %s' % m.group(1).strip()
    if '(부산 직항 없음)' in d:
        d = d.replace('(부산 직항 없음)', '').strip() + ' · 부산 직항 없음'

    if airline and airline not in ('미확인', '항공사 미확인'):
        out['airline'] = airline
    elif airline:
        out['src'] = '가격표'
        if '캘린더' in d or '가격표' in d:
            d = '항공사·직항여부 미확인(운임 캘린더 값)'

    if d.startswith('경유'):
        out['via'] = True
    elif d.startswith('직항'):
        out['via'] = False
    else:
        out['via'] = None
    if d:
        out['note'] = d
    elif 'src' not in out:
        out['src'] = '가격표'
        out['note'] = '직항/경유 미확인'
    return out


def is_unknown(text):
    return text.startswith('항공사 미확인') or text.startswith('가격표')


def parse_info(airline, desc):
    """항공사 + 설명 → {airline, via, note, alt, src}."""
    out = {}
    d = (desc or '').strip()

    if d.startswith('직항/경유'):                 # '… · 직항/경유 미확인' 줄
        out['src'], out['via'], out['note'] = '가격표', None, d
        return out

    m = UNKNOWN.match(d)
    if m:
        out['src'], out['via'] = '가격표', None
        d = m.group(2).strip()                    # '항공사 미확인(가격표) ※직항 …' 의 뒷부분
    elif is_unknown(d):
        out['src'], out['via'], d = '가격표', None, ''
    elif airline is None and d and not d.startswith(('직항', '경유')):
        airline, _, d = d.partition(' ')          # 보완2차형: 항공사가 설명 앞에 붙어 있다
    elif d.startswith(('직항', '경유')):
        d = d                                     # '경유(부산 직항 없음)' 는 항공사가 아니라 직항/경유 설명
        d = d.strip()
    if airline:
        out['airline'] = airline

    if not d:
        out.setdefault('src', '가격표')
        out.setdefault('via', None)
        out.setdefault('note', '직항/경유 미확인')
        return out

    d = re.sub(r'\((?:직항\s*최저)[^)]*?([\d,]{4,})원\)', r' ※직항 최저 \1원', d)
    d = re.sub(r'\s*\(가격표[^)]*\)', '', d)      # 병기된 가격표 캐시값은 넣지 않는다
    d = re.sub(r'\s*—\s*', ' ※', d)               # 부연은 ※ 뒤로 (카드 메모는 앞부분만 보인다)
    d = d.replace(' · ', ' ※')
    d = re.sub(r'\s*직항\s*없음$', '', d).strip()

    if d.startswith('※'):                         # 항공사 미확인 + 부연만 있는 줄
        note = d.lstrip('※').strip()
        alt = DIRECT.search(note)
        if alt:
            out['alt'] = int(alt.group(2).replace(',', ''))
        out['note'] = note
        return out

    head, _, tail = d.partition('※')
    head, tail = head.strip(), tail.strip()
    m = re.search(r'\s+/\s+(직항.*)$', head)      # '경유 … / 직항 제주항공 462,500'
    if m:
        head = head[:m.start()].strip()
        tail = (m.group(1).strip() + (' ' + tail if tail else '')).strip()

    if head.startswith('경유'):
        out['via'] = True
    elif head.startswith('직항'):
        out['via'] = False
    else:
        out.setdefault('via', None)
    out['note'] = (head + (' ※' + tail if tail else '')).strip()

    alt = DIRECT.search(tail) if tail else None
    if alt:
        out['alt'] = int(alt.group(2).replace(',', ''))
    return out


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다 (패턴 %s)' % (date, a, pattern))
    nights = (WD[b] - WD[a]) % 7 or 7
    return (start + datetime.timedelta(days=nights)).isoformat()


def rank(pattern):
    return PAT_ORDER.index(pattern) if pattern in PAT_ORDER else len(PAT_ORDER)


def insert_by_date(deals):
    """출발일 순서만 맞춘다(파이썬 정렬은 안정 정렬이라 같은 날짜의 기존 순서는 그대로 남는다)."""
    deals.sort(key=lambda d: d['date'])


# ---------------------------------------------------------------- 병합

def merge(master, deals, gaps, replace_price=False):
    """deals → 마스터. replace_price=True 면 같은 (날짜·패턴)의 **더 새로운 실측 가격**으로 바꾼다.

    replace_price 로 실측(항공사 확인) 건이 기존 가격표 캐시값을 대신하면, 그 캐시 표시(src)는 지운다.
    """
    routes = {r['code']: r for r in master['flights']['routes']}
    added, filled, skipped, updated = [], [], [], []
    for code, deal in deals:
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)
        r = routes[code]
        same = [d for d in r['deals'] if d['date'] == deal['date'] and d['pattern'] == deal['pattern']]
        if same:
            old = same[0]
            changed = False
            measured = bool(deal.get('airline'))
            if replace_price and old['price'] != deal['price']:
                updated.append((code, deal['date'], deal['pattern'], old['price'], deal['price']))
                old['price'] = deal['price']
                changed = True
            if replace_price and measured and old.get('src') in ('가격표', '캘린더') and not old.get('airline'):
                old.pop('src', None)          # 실측가로 바뀌었으니 '가격표/캘린더 값' 표시는 더 이상 사실이 아니다
                changed = True
            if replace_price and measured and deal.get('note'):
                if old.get('note') != deal['note']:
                    old['note'] = deal['note']
                    changed = True
            if not old.get('airline') and deal.get('airline'):
                old['airline'] = deal['airline']
                changed = True
            if old.get('via') is None and deal.get('via') is not None:
                old['via'] = deal['via']
                changed = True
            if old.get('note') in (None, '', '직항/경유 미확인') and deal.get('note') and deal['note'] != '직항/경유 미확인':
                old['note'] = deal['note']
                changed = True
            if deal.get('alt') and not old.get('alt'):
                old['alt'] = deal['alt']
                changed = True
            if changed and not (replace_price and (code, deal['date'], deal['pattern']) in
                                [u[:3] for u in updated]):
                filled.append((code, deal['date'], deal['pattern']))
            elif not changed:
                skipped.append((code, deal['date'], deal['pattern'], old['price'], deal['price']))
            continue
        r['deals'].append(deal)
        added.append((code, deal['date'], deal['pattern'], deal['price']))

    for r in master['flights']['routes']:
        insert_by_date(r['deals'])
        for d in r['deals']:                      # 보고서의 '← 1주차 최저' 같은 표시는 메모에서 뺀다
            if d.get('note'):
                d['note'] = re.sub(r'\s*←.*$', '', d['note']).strip()

    all_deals = [d for r in master['flights']['routes'] for d in r['deals']]
    by_month = {}
    for d in all_deals:
        by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    master['flights']['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month[k] for k in sorted(by_month)},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals if d['pattern'].split('~')[0] == d['pattern'].split('~')[1]),
    }
    return added, filled, skipped, updated, gaps


def main(argv):
    ap = argparse.ArgumentParser(description='항공 특가 md → master_db.json flights 병합')
    ap.add_argument('md', nargs='+')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--replace-price', action='store_true',
                    help='같은 (날짜·패턴)이 이미 있으면 더 새로운 실측 가격으로 바꾼다')
    ap.add_argument('--note', default='', help='DB.extended 에 덧붙일 한 줄')
    args = ap.parse_args(argv)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    before = master['flights']['counts']['total']
    all_added, all_filled, all_skipped, all_updated, all_gaps = [], [], [], [], []
    codes_by_city = {r['city']: r['code'] for r in master['flights']['routes']}
    for path in args.md:
        deals, gaps = parse_md(path, codes_by_city)
        added, filled, skipped, updated, gaps = merge(master, deals, gaps, args.replace_price)
        print('%s → 파싱 %d건 (미측정/미표시 %d건)' % (os.path.basename(path), len(deals), len(gaps)))
        print('  신규 %d · 가격 갱신 %d · 기존 유지 %d · 항목 보강 %d'
              % (len(added), len(updated), len(skipped), len(filled)))
        all_added += added
        all_filled += filled
        all_skipped += skipped
        all_updated += updated
        all_gaps += gaps

    print('총 건수 %d → %d' % (before, master['flights']['counts']['total']))
    if os.environ.get('MERGE_VERBOSE'):
        for a in all_added:
            print('  + %s %s %s %s원' % a)
    for f in all_filled:
        print('  ~ %s %s %s (항공사/직항 보강)' % f)
    for u in all_updated:
        print('  ↑ %s %s %s %s원 → %s원 (최신 실측)' % u)
    for s in all_skipped:
        print('  = %s %s %s 기존 %s원 / 보고서 %s원' % s)
    for g in all_gaps:
        print('  - %s %s %s 미측정/미표시: %s' % g)

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
