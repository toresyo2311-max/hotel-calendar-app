#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 중국 4노선(선양·다롄·광저우·샤먼) **2027년 2~6월 2박(금~일·토~월) 168칸(100%)**
완주본 md → `data/master_db.json` 의 `flights` 병합.

앞선 `merge_flights_china_pus4_26m.py`(131칸)가 넣은 칸은 그대로 두고, 이번 완주본에서
새로 찬 **37칸**(6월 금~일·토~월 32칸 + 2/13·5/29 토~월 5칸)만 더한다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_china_pus4_26m.py \
        ../data-sources/flights-china-new8/부산출발-중국4노선-선양다롄광저우샤먼-2_6월-2박.md --dry-run

읽는 곳(부록 A '병합용 줄(실측분)' + 2-1·2-2 실측표 + 1·5절 요약):
  · 값 — `- 2027-02-05 · 금~일 · PUS–SHE · 713,600원 · 중국동방항공(상하이항공 운항) · 경유(상하이 2h35, 총7h00)`
  · 미조회 — 2-1·2-2 표에서 `—` 인 칸은 넣지 않고 gaps 로만 센다.
  · 이번 원본에는 `판매편 없음(0건)` 칸이 없다(1절 '판매편 없음(0건) **0칸**').

규칙:
  · 값(가격·날짜·소요시간)은 원문 그대로. 소요시간 표기만 앱 표기(h/m → 시간/분)로 옮긴다.
  · 부록 줄과 2-1·2-2 표를 **(노선·출발일·패턴) 단위로 전수 대조**한다 — 한 칸이라도 다르면 멈춘다.
    3-1·3-2·3-3(3·4박) 표는 전부 `—` 인지 확인한다(420칸 = 2박 168 + 3·4박 252).
    노선별 최저·최고·평균과 전체 최저·최고를 1·5절 요약과 대조한다.
  · 이미 있는 칸은 **중복으로 넣지 않는다**(기존 건 보존). 기존 딜이 하나라도 달라지면 멈춘다.
  · 호텔 538곳 · 아코르 · 다른 28개 노선은 **바이트 동일성**으로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)와 2027년 5~6월 `notes`(커버리지 문구)를 다시 쓴다.
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
ROUTE_ORDER = ('SHE', 'DLC', 'CAN', 'XMN')
ROUTE_CITY = {'SHE': '선양', 'DLC': '다롄', 'CAN': '광저우', 'XMN': '샤먼'}
PATTERNS = ('금~일', '토~월')
# 원문이 말하는 칸 수 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT = {
    'cells': 168,
    'gaps': 0,           # 2박 168칸 전부 실측(완주본)
    'thu_cells': 252,    # 3·4박 4노선 × 21주 × 3패턴, 전부 미조회
    'per': {             # 노선·패턴별 값이 있는 칸 수
        'SHE': {'금~일': 21, '토~월': 21},
        'DLC': {'금~일': 21, '토~월': 21},
        'CAN': {'금~일': 21, '토~월': 21},
        'XMN': {'금~일': 21, '토~월': 21},
    },
    # 5절 성수기 특징 — 금~일 평균·최고·최저(원)
    '금~일': {'SHE': (538167, 713600, 463500), 'DLC': (466567, 607100, 373300),
              'CAN': (545043, 775200, 501100), 'XMN': (555929, 758400, 464500)},
    'overall': (373300, 884000),   # 전체 최저(다롄 3/12~3/14 금~일) · 최고(샤먼 2/6~2/8 토~월)
}
# 앞선 131칸 병합분(중복)과 이번에 새로 차는 37칸 — 이번 원본은 2박 168칸 완주본
PREV_CELLS, NEW_CELLS = 131, 37
# 6월에 새로 찬 4주 × 4노선 × 2패턴 = 32칸 + 2/13·5/29 토~월 5칸
NEW_MONTHS = {'2027-02': 3, '2027-05': 2, '2027-06': 32}

LINE = re.compile(r'^- (\d{4}-\d{2}-\d{2}) · ([월화수목금토일]~[월화수목금토일]) · PUS–([A-Z]{3}) · (.+)$')
ROW = re.compile(r'^\| ([^|]+?) \(([A-Z]{3})\) \| (.+?) \|$')
HEAD = re.compile(r'^\| 노선 \| (.+) \|$')
COL = re.compile(r'^(\d{1,2})/(\d{1,2})~(\d{1,2})/(\d{1,2})$')


# ---------------------------------------------------------------- 표기 변환
def timespan(text):
    """'상하이 2h35, 총7h00' → '상하이 2시간 35분, 총 7시간' (값은 그대로)."""
    def one(m):
        h, mi = int(m.group(1)), m.group(2)
        out = '%d시간' % h
        if mi and int(mi):
            out += ' %d분' % int(mi)
        return out
    text = re.sub(r'(\d{1,2})h\s*(\d{1,2})?', one, text)
    return re.sub(r'총\s*(?=\d)', '총 ', text).replace('  ', ' ').strip()


def norm_desc(desc):
    """원문 편구성 → {via, note}."""
    d = (desc or '').strip()
    if d.startswith('경유'):
        body = timespan(d[2:].strip())
        return {'via': True, 'note': '경유' + (body if body.startswith('(') else ' ' + body if body else '')}
    if d.startswith('직항'):
        return {'via': False, 'note': timespan(d)}
    raise SystemExit('경유/직항 표기가 아닙니다(원문 확인 필요): %r' % d)


def back_date(date, pattern):
    a, _, b = pattern.partition('~')
    start = datetime.date.fromisoformat(date)
    if start.isoweekday() % 7 != WD[a]:
        raise SystemExit('%s 는 %s요일이 아닙니다(패턴 %s)' % (date, a, pattern))
    nights = (WD[b] - WD[a]) % 7 or 7
    return (start + datetime.timedelta(days=nights)).isoformat()


# ---------------------------------------------------------------- 파싱
def parse_appendix(text):
    values, nosale, gaps = {}, {}, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('- 20'):
            continue
        m = LINE.match(line)
        if not m:
            raise SystemExit('부록 줄 형식이 예상과 다릅니다: %s' % line)
        date, pattern, code, body = m.groups()
        if body.startswith('미측정'):
            gaps.append((code, date, pattern))
            continue
        if body.startswith('판매편 없음'):
            nosale[(code, date, pattern)] = {
                'code': code, 'date': date, 'back': back_date(date, pattern),
                'pattern': pattern, 'note': '검색 결과 0건(판매편 없음)'}
            continue
        fields = [f.strip() for f in body.split(' · ')]
        pm = re.fullmatch(r'([\d,]+)원', fields[0])
        if not pm:
            raise SystemExit('부록 금액을 읽지 못했습니다: %s' % line)
        deal = {'date': date, 'back': back_date(date, pattern), 'pattern': pattern,
                'price': int(pm.group(1).replace(',', ''))}
        if len(fields) > 1 and fields[1]:
            deal['airline'] = fields[1]
        if len(fields) > 2:
            info = norm_desc(' · '.join(fields[2:]))
            deal['via'] = info['via']
            deal['note'] = info['note']
        values[(code, date, pattern)] = deal
    return values, nosale, gaps


def parse_tables(text):
    """2-1·2-2(2박) 표 → (code,date,pattern)→가격|'—', 3-1·3-2·3-3 칸 수."""
    out, thu_cells, section, heads = {}, 0, None, None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('## '):
            if line.startswith('## 2-'):
                section = '2'
            elif line.startswith('## 3'):
                section = '3'
            elif line.startswith('## 4') or line.startswith('## 5') or line.startswith('## 부록'):
                section = None
            heads = None
            continue
        if section is None:
            continue
        if section == '3':
            if line.startswith('| ') and '—' in line \
                    and any(c in line for c in ('(SHE)', '(DLC)', '(CAN)', '(XMN)')):
                cells = [c.strip() for c in line.strip('|').split('|')]
                if any(c != '—' for c in cells[1:]):
                    raise SystemExit('3·4박 표에 값이 있습니다(원문 확인): %s' % line)
                thu_cells += len(cells) - 1
            continue
        m = HEAD.match(line)
        if m:
            heads = [c.strip() for c in m.group(1).split('|')]
            for h in heads:
                if not COL.match(h):
                    raise SystemExit('2박 표 머리가 날짜 범위가 아닙니다: %r' % h)
            continue
        m = ROW.match(line)
        if m:
            if heads is None:
                raise SystemExit('2박 표 머리 없이 노선 줄이 나왔습니다: %s' % line)
            city, code, cells = m.groups()
            if city.strip() != ROUTE_CITY.get(code, city.strip()):
                raise SystemExit('노선 이름이 다릅니다: %s / %s' % (city, code))
            vals = [c.strip() for c in cells.split('|')]
            if len(vals) != len(heads):
                raise SystemExit('표 열 수가 머리와 다릅니다: %s' % line)
            for h, v in zip(heads, vals):
                sm, sd, em, ed = COL.match(h).groups()
                date = datetime.date(2027, int(sm), int(sd))
                end = datetime.date(2027, int(em), int(ed))
                pat = '%s~%s' % ('금토일월화수목'[date.isoweekday() % 7], '일월화수목금토'[end.isoweekday() % 7])
                # 두 표의 머리는 금~일·토~월뿐이다
                pat = '금~일' if date.isoweekday() == 5 else '토~월' if date.isoweekday() == 6 else pat
                if v == '—':
                    out[(code, date.isoformat(), pat)] = '—'
                elif v == '0건':
                    out[(code, date.isoformat(), pat)] = 'NOSALE'
                elif re.fullmatch(r'[\d,]+', v):
                    out[(code, date.isoformat(), pat)] = int(v.replace(',', ''))
                else:
                    raise SystemExit('표 칸 값을 읽지 못했습니다: %s' % line)
    return out, thu_cells


def summary_checks(text, values):
    """1·5절 요약(칸 수·최저·최고·평균)을 계산값과 대조한다."""
    bad = []
    def num(pattern, name):
        m = re.search(pattern, text)
        if not m:
            raise SystemExit('요약 문장을 찾지 못했습니다: %s' % name)
        return int(m.group(1).replace(',', ''))
    grid = num(r'\| 전체 격자 \| \*\*([\d,]+)칸\*\*', '전체 격자')
    done = num(r'\| 실측 완료 \| \*\*([\d,]+)칸\*\*', '실측 완료')
    zero = num(r'\| 판매편 없음\(0건\) \| \*\*([\d,]+)칸\*\*', '판매편 없음')
    rest = num(r'\| 미조회 \| \*\*([\d,]+)칸\*\*', '미조회')
    got = len(values)
    if grid != 4 * 21 * 5 or done != got or zero != 0 or rest != grid - done:
        bad.append('요약 칸 수(격자 %d·실측 %d·0건 %d·미조회 %d)와 파싱(%d칸)이 다릅니다'
                   % (grid, done, zero, rest, got))
    lo = num(r'- 전체 최저 \*\*([\d,]+)원\*\*', '전체 최저')
    hi = num(r'- 전체 최고 \*\*([\d,]+)원\*\*', '전체 최고')
    prices = [d['price'] for d in values.values()]
    if (min(prices), max(prices)) != (lo, hi):
        bad.append('전체 최저·최고 %s (요약 %s)' % ((min(prices), max(prices)), (lo, hi)))
    if (min(prices), max(prices)) != EXPECT['overall']:
        bad.append('전체 최저·최고 %s (기대 %s)' % ((min(prices), max(prices)), EXPECT['overall']))
    for code, city in ROUTE_CITY.items():
        m = re.search(r'- \*\*%s 금~일\*\* 평균 ([\d,]+)원 · 최고 ([\d,]+)원[^·]*· 최저 ([\d,]+)원' % city, text)
        if not m:
            raise SystemExit('5절 금~일 요약을 찾지 못했습니다: %s' % city)
        avg, top, bottom = (int(x.replace(',', '')) for x in m.groups())
        ps = [d['price'] for (c, _, p), d in values.items() if c == code and p == '금~일']
        calc = round(sum(ps) / len(ps))
        if (calc, max(ps), min(ps)) != (avg, top, bottom):
            bad.append('%s 금~일 평균·최고·최저 계산 %s (요약 %s)' % (city, (calc, max(ps), min(ps)), (avg, top, bottom)))
        if (avg, top, bottom) != EXPECT['금~일'][code]:
            bad.append('%s 금~일 요약 %s (기대 %s)' % (city, (avg, top, bottom), EXPECT['금~일'][code]))
    return bad


# ---------------------------------------------------------------- 병합
def merge(master, values, nosale):
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTE_ORDER:
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)

    added, dup, conflicts = [], [], []
    for (code, date, pattern), deal in sorted(values.items()):
        r = routes[code]
        have = next((d for d in r['deals'] if d['date'] == date and d['pattern'] == pattern), None)
        if have is not None:
            if have.get('price') != deal['price']:
                conflicts.append((code, date, pattern, have.get('price'), deal['price']))
            dup.append((code, date, pattern))
            continue
        r['deals'].append(deal)
        added.append((code, date, pattern, deal['price']))
    if conflicts:
        raise SystemExit('기존 금액과 다른 실측값이 왔습니다(확인 필요): %s' % conflicts)

    for r in fl['routes']:
        r['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))

    known = {(n['code'], n['date'], n['pattern']) for n in fl['noSale']}
    deal_keys = {(r['code'], d['date'], d['pattern']) for r in fl['routes'] for d in r['deals']}
    new_nosale = []
    for key, entry in sorted(nosale.items()):
        if key in known:
            continue
        if key in deal_keys:
            raise SystemExit('판매편 0건 칸이 실측 딜과 겹칩니다: %s' % (key,))
        fl['noSale'].append(entry)
        new_nosale.append(key)
    fl['noSale'].sort(key=lambda n: (n['code'], n['date']))

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
    return added, dup, new_nosale


def notes_update(fl):
    """화면 커버리지 문구(월별 notes)를 이번 조사 범위에 맞춘다."""
    fl['notes']['2027-02'] = ('선양·다롄·광저우·샤먼 4개 노선의 금~일·토~월(2박) 4주씩과 연길·장가계·구이린·황산의 '
                              '금~일(2박) 4주를 실측했습니다. 나머지 노선·패턴은 미조회(—)입니다.')
    fl['notes']['2027-03'] = ('선양·다롄·광저우·샤먼 4개 노선의 금~일·토~월(2박) 4주와 연길·장가계·구이린·황산의 '
                              '금~일(2박) 4주를 실측했습니다. 나머지 노선·패턴은 미조회(—)입니다.')
    fl['notes']['2027-04'] = ('선양·다롄·광저우·샤먼 4개 노선의 금~일 5주·토~월 4주를, 연길·장가계·구이린·황산은 '
                              '금~일(2박)을 실측했습니다(황산은 4/2~4/30 판매편이 없어 0건). '
                              '나머지 노선·패턴은 미조회(—)입니다.')
    fl['notes']['2027-05'] = ('중국 8개 노선의 2027년 5월 2박을 실측했습니다 — 선양·다롄·광저우·샤먼은 금~일 4주·'
                              '토~월 5주(5/29 포함), 연길·장가계·구이린·황산은 금~일 5주입니다(황산은 5/7~5/28 판매편이 없어 0건). '
                              '3·4박과 다른 노선은 미조회(—)입니다.')
    fl['notes']['2027-06'] = ('중국 8개 노선의 2027년 6월 2박을 실측했습니다 — 선양·다롄·광저우·샤먼은 금~일·토~월 4주씩(32칸), '
                              '연길·장가계·구이린·황산은 금~일 4주와 연길 6/5 토~월 1칸입니다(황산은 6월 네 주 모두 판매편이 없어 0건). '
                              '3·4박과 다른 노선은 미조회(—)입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='중국 4노선(선양·다롄·광저우·샤먼) 2027년 2~5월 2박 md → master_db.json flights 병합')
    ap.add_argument('md')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    text = open(args.md, encoding='utf-8').read()
    values, nosale, gaps = parse_appendix(text)
    table, thu_cells = parse_tables(text)

    # 1) 원문 칸 수와 파싱 결과
    bad = []
    per = {c: {p: 0 for p in PATTERNS} for c in ROUTE_ORDER}
    for code, _, pat in values:
        if code not in per or pat not in per[code]:
            raise SystemExit('예상 밖 (노선·패턴) 칸입니다: %s %s' % (code, pat))
        per[code][pat] += 1
    if len(values) != EXPECT['cells']:
        bad.append('값 %d칸 (기대 %d칸)' % (len(values), EXPECT['cells']))
    if nosale:
        bad.append('이번 원본에 0건 칸이 %d개 있습니다(1절은 0칸이라고 함): %s' % (len(nosale), sorted(nosale)[:3]))
    if len(values) + len(nosale) != EXPECT['cells']:
        bad.append('값+0건 %d칸 (기대 %d칸)' % (len(values) + len(nosale), EXPECT['cells']))
    for code in ROUTE_ORDER:
        if per[code] != EXPECT['per'][code]:
            bad.append('%s 노선·패턴별 칸 수 %s (기대 %s)' % (code, per[code], EXPECT['per'][code]))
    for code, _, pat in gaps:
        if pat not in PATTERNS:
            bad.append('미조회 줄에 2박 밖 패턴: %s %s' % (code, pat))
    # 미조회 = 표에서 — 인 2박 칸 (이번 부록에는 미측정 줄을 적지 않았다 — 표로만 센다)
    table_gaps = sum(1 for v in table.values() if v == '—')
    if table_gaps != EXPECT['gaps']:
        bad.append('미조회 칸 수 표 %d (기대 %d)' % (table_gaps, EXPECT['gaps']))
    for key in gaps:
        if table.get(key) != '—':
            bad.append('부록 미측정 칸이 표에서는 값이 있습니다: %s' % (key,))
    if len(table) != 4 * 21 * 2:
        bad.append('2박 표 칸 수 %d (기대 %d)' % (len(table), 4 * 21 * 2))
    if thu_cells != EXPECT['thu_cells']:
        bad.append('3·4박 표 칸 수 %d (기대 %d)' % (thu_cells, EXPECT['thu_cells']))

    # 2) 부록 ↔ 2-1·2-2 표 전수 대조 (2박 168칸)
    mismatch = []
    for key, got in table.items():
        if key in values:
            if got != values[key]['price']:
                mismatch.append('%s %s 부록 %s / 표 %s' % (key, values[key]['price'], got))
        elif got != '—':
            mismatch.append('%s 부록에 없는데 표는 %s' % (key, got))
    if mismatch:
        bad.append('부록·표 불일치 %d건: %s' % (len(mismatch), mismatch[:6]))

    # 3) 요약(칸 수·최저·최고·평균)
    bad.extend(summary_checks(text, values))
    print('  값 %d칸 (금~일 %d · 토~월 %d) · 미조회 %d칸 · 3·4박 %d칸 전부 미조회 · 표 대조 %d칸'
          % (len(values), sum(1 for k in values if k[2] == '금~일'),
             sum(1 for k in values if k[2] == '토~월'), len(gaps), thu_cells, len(table)))
    print('  노선별: %s' % ', '.join('%s 금~일 %d·토~월 %d' % (c, per[c]['금~일'], per[c]['토~월'])
                                     for c in ROUTE_ORDER))
    if bad:
        raise SystemExit('원문과 파싱 결과가 다릅니다: %s' % bad)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    fl = master['flights']
    hotels_before = json.dumps(master['hotels'], ensure_ascii=False)
    accor_before = json.dumps(master.get('accor'), ensure_ascii=False)
    before_total = fl['counts']['total']
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTE_ORDER],
                              ensure_ascii=False, sort_keys=True)
    before_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False, sort_keys=True)
                     for r in fl['routes'] if r['code'] in ROUTE_ORDER for d in r['deals']}
    before_nosale = json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True)

    before_by_month = dict(fl['counts']['byMonth'])
    added, dup, new_nosale = merge(master, values, nosale)
    notes_update(fl)

    # 이번 완주본이 정확히 37칸만 더했는지(중복 131칸 + 신규 37칸)
    if len(dup) != PREV_CELLS:
        raise SystemExit('기존 2박 %d칸과 겹쳤습니다 (기대 %d칸)' % (len(dup), PREV_CELLS))
    if len(added) != NEW_CELLS:
        raise SystemExit('신규 %d칸 (기대 %d칸): %s' % (len(added), NEW_CELLS, added))
    if new_nosale:
        raise SystemExit('이번 원본에 0건 칸이 있습니다: %s' % new_nosale)
    after_by_month = fl['counts']['byMonth']
    for m, n in NEW_MONTHS.items():
        if after_by_month.get(m, 0) - before_by_month.get(m, 0) != n:
            raise SystemExit('%s 증가 %d칸 (기대 %d칸)'
                             % (m, after_by_month.get(m, 0) - before_by_month.get(m, 0), n))

    # 4) 보존 검증 — 호텔·아코르·다른 노선·기존 딜은 한 바이트도 바뀌면 안 된다
    if json.dumps(master['hotels'], ensure_ascii=False) != hotels_before:
        raise SystemExit('호텔 데이터가 바뀌었습니다.')
    if json.dumps(master.get('accor'), ensure_ascii=False) != accor_before:
        raise SystemExit('아코르 데이터가 바뀌었습니다.')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTE_ORDER],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 항공 노선 데이터가 바뀌었습니다.')
    after_within = {(r['code'], d['date'], d['pattern']): json.dumps(d, ensure_ascii=False, sort_keys=True)
                    for r in fl['routes'] if r['code'] in ROUTE_ORDER for d in r['deals']}
    lost = [k for k in before_within if before_within[k] != after_within.get(k)]
    if lost:
        raise SystemExit('기존 딜이 사라지거나 바뀌었습니다: %s' % lost[:5])
    if json.dumps(fl['noSale'], ensure_ascii=False, sort_keys=True) != before_nosale:
        raise SystemExit('기존 판매편 0건 기록이 바뀌었습니다.')
    for r in fl['routes']:
        if r['code'] in ROUTE_ORDER:
            keys = [(d['date'], d['pattern']) for d in r['deals']]
            if len(keys) != len(set(keys)):
                raise SystemExit('%s (출발일·패턴) 중복' % r['code'])

    print('신규 딜 %d건(중복 %d건) · 신규 0건 %d건 → noSale %d건'
          % (len(added), len(dup), len(new_nosale), len(fl['noSale'])))
    print('총 %d건 → %d건 (주말형 %d · 당일치기 %d)' % (
        before_total, fl['counts']['total'],
        fl['counts']['total'] - fl['counts']['daytrip'], fl['counts']['daytrip']))
    print('월별: %s' % fl['counts']['byMonth'])
    print('4노선 건수: %s' % ', '.join(
        '%s %d' % (r['code'], len(r['deals'])) for r in fl['routes'] if r['code'] in ROUTE_ORDER))
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
