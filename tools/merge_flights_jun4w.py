#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선의 2027년 6월 4주차(6/24~6/28) 5패턴 120칸** 실측을
`data/master_db.json` 의 `flights` 에 병합한다.

원본 1개(`data-sources/flights-2027-06/부산출발-항공특가-2027년6월-4주차.md`,
2026-11-19 12:45~14:05 KST 실측) — 24개 노선 5패턴 120칸 전수.
  · 노선 절: `### 부산–상하이 (PVG)`
  · 칸 1줄:
    `- 6/25(금) → 6/27(일) · ① 금~일 2박 · **420,000원** · 중국남방항공 · 경유(선양 2시간30분, 총7시간20분), 11:20-17:40 · 직항편우선 탭 507,400 / 30개 [출처: …]`
    (3주차 원본과 달리 직항 칸에도 소요시간·출도착 시각이 있고, 경유 칸의 시각은 괄호 밖에 있다)

규칙:
  · 120칸 모두 `routes[].deals` 로 넣는다(`price` = 원문 금액 그대로, 반올림 없음).
  · `via` 는 그 칸 **최저가 편성**이 직항(`false`)·경유(`true`)인지로 적는다.
  · `note` 는 `직항 1시간 55분 (21:50-22:45)` / `경유(선양 2시간 30분) · 총 7시간 20분 (11:20-17:40)`
    꼴로 적고, 2회 경유는 `경유(서울, 난징 2회 경유) · 총 37시간 55분 (…)` 처럼 경유지를 모두 남긴다.
  · `alt` 는 원문의 '직항편우선 탭' 금액이 최저가보다 비쌀 때만 넣는다.
  · 이 주차에 **이미 있던 '가격표' 자리표시 칸**(직항/경유 미확인) 19칸은 같은 노선·출발일·
    패턴이므로 이번 실측값으로 **교체**한다(같은 칸을 두 값으로 두지 않는다).
    교체 대상이 아닌 칸은 건드리지 않는다.
  · 호텔 538곳 · 아코르 · ⑥ 땡처리 · 출처 목록 · 패턴 정의 · 다른 노선/기존 딜·`noSale` 은
    값 대조로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-06 `notes` 끝에
    이번 120칸 문장을 덧붙인다(plain text — `**` 금지).
  · `extended`(데이터 갱신 이력) 끝에 이번 병합 한 줄을 덧붙인다(`--note`).
  · 제3자 사이트 이름은 값·note 어디에도 넣지 않는다.

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jun4w.py --dry-run
    python3 tools/merge_flights_jun4w.py
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-2027-06'))
FILE = '부산출발-항공특가-2027년6월-4주차.md'

WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
ROUTES = ('FUK', 'KIX', 'TYO', 'TPE', 'HKG', 'MFM', 'PVG', 'BKK', 'DAD', 'CXR', 'NKG', 'SGN',
          'SIN', 'GUM', 'NGO', 'OKA', 'HGH', 'TAO', 'HAN', 'CNX', 'DPS', 'KHH', 'RMQ', 'BJS')
CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'NGO': '나고야',
        'OKA': '오키나와', 'GUM': '괌', 'PVG': '상하이', 'BJS': '베이징', 'NKG': '난징',
        'HGH': '항저우', 'TAO': '칭다오', 'TPE': '타이베이', 'HKG': '홍콩', 'KHH': '가오슝',
        'RMQ': '타이중', 'MFM': '마카오', 'BKK': '방콕', 'CNX': '치앙마이', 'DAD': '다낭',
        'CXR': '나트랑', 'HAN': '하노이', 'SGN': '호찌민', 'SIN': '싱가포르', 'DPS': '발리'}
MONTH = '2027-06'
WEEK_START, WEEK_END = '2027-06-24', '2027-06-28'
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver')
_DUR_RE = re.compile(r'(\d+)\s*시간(?:\s*(\d+)\s*분)?|(\d+)\s*분')

EXPECT_CELLS = 120
EXPECT_OVERALL = (299100, 820600)
EXPECT_AVG = {'목~일': 482688, '목~월': 488338, '금~일': 488950,
              '토~월': 489612, '금~월': 490254}
EXPECT_DIRECT = 36          # 직항이 최저가인 칸
EXPECT_THIN = 35            # '9석 미만' 표시가 붙은 칸
EXPECT_PLACEHOLDER = 19     # 이 주차에 남아 있던 '가격표' 자리표시 칸(교체 대상)

ROUTE_MINMAX = {
    'FUK': (309400, 352400), 'KIX': (353600, 380900), 'TYO': (481700, 527100),
    'NGO': (621300, 683800), 'OKA': (488100, 640500), 'GUM': (613300, 820600),
    'PVG': (299100, 489100), 'BJS': (448500, 489100), 'NKG': (492300, 497800),
    'HGH': (483700, 483700), 'TAO': (471400, 542700),
    'TPE': (382800, 387400), 'HKG': (300000, 333100), 'KHH': (481400, 532700),
    'RMQ': (435700, 677300), 'MFM': (559600, 723600),
    'BKK': (409300, 411300), 'CNX': (614500, 714000), 'DAD': (478600, 488600),
    'CXR': (431900, 432000), 'HAN': (444900, 448400), 'SGN': (453200, 453500),
    'SIN': (424500, 430200), 'DPS': (421900, 428900),
}


def read():
    path = os.path.join(SRC, FILE)
    if not os.path.isfile(path):
        raise SystemExit('원본이 없습니다: %s' % path)
    return open(path, encoding='utf-8').read()


def won(text):
    m = re.search(r'([\d,]+)', text)
    return int(m.group(1).replace(',', '')) if m else None


def norm_dur(text):
    """'1시간10분' → '1시간 10분', '30시간' → '30시간 00분', '55분' 그대로."""
    def rep(m):
        if m.group(1):
            return '%s시간 %s분' % (m.group(1), (m.group(2) or '00').rjust(2, '0'))
        return '%s분' % m.group(3)
    return _DUR_RE.sub(rep, text).strip()


def build_note(leg):
    """`직항 1시간 55분 (21:50-22:45)` / `경유(선양 2시간 30분) · 총 7시간 20분 (11:20-17:40)`."""
    kind = '직항' if leg.startswith('직항') else ('경유' if leg.startswith('경유') else None)
    if kind is None:
        raise SystemExit('편성 문장을 읽지 못했습니다: %r' % leg)
    rest = leg[len(kind):].strip()
    inner = ''
    m = re.match(r'^\(([^)]*)\)\s*(.*)$', rest)
    if m:
        inner, rest = m.group(1).strip(), m.group(2).strip()
    rest = rest.lstrip(',').strip()
    dur = times = ''
    for chunk in [c.strip() for c in rest.split(',') if c.strip()]:
        if re.search(r'\d\d:\d\d', chunk):
            times = re.sub(r'\s*-\s*', '-', chunk)      # '09:20-11:35 NRT' — 공항코드 앞 공백은 남긴다
        elif '시간' in chunk or '분' in chunk:
            dur = chunk
        else:
            raise SystemExit('편성 시각을 읽지 못했습니다: %r' % leg)
    if kind == '직항':
        note = '직항'
        if inner:
            note += ' ' + norm_dur(inner)
        if dur:
            note += ' ' + norm_dur(dur)
        if times:
            note += ' (%s)' % times
        return note, False
    pieces = [p.strip() for p in inner.split(',') if p.strip()]
    hops, total = [], None
    for p in pieces:
        tm = re.match(r'^총\s*(.+)$', p)
        if tm:
            total = norm_dur(tm.group(1))
            continue
        hops.append(norm_dur(p))
    if not hops:
        raise SystemExit('경유지가 없습니다: %r' % leg)
    note = '경유(' + ', '.join(hops) + ')'
    if total:
        note += ' · 총 ' + total
    if times:
        note += ' (%s)' % times
    return note, True


def parse():
    cells, code = {}, None
    for raw in read().splitlines():
        line = raw.strip()
        m = re.match(r'^###\s*부산[–-].*?\(([A-Z]{3})\)', line)
        if m:
            code = m.group(1)
            if code not in ROUTES:
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        if not line.startswith('- 6/'):
            continue
        if code is None:
            raise SystemExit('노선 없이 칸: %s' % line[:60])
        line = re.sub(r'\s*\[출처:[^\]]*\]', '', line).strip()
        parts = [p.strip() for p in line[2:].split(' · ')]
        if len(parts) < 5:
            raise SystemExit('%s 칸 형식을 읽지 못했습니다: %r' % (code, line[:80]))
        dm = re.match(r'^6/(\d+)\(.\)\s*→\s*6/(\d+)\(.\)$', parts[0])
        if not dm:
            raise SystemExit('%s 날짜를 읽지 못했습니다: %r' % (code, parts[0]))
        pm = re.match(r'^[①②③④⑤]\s*([월화수목금토일]~[월화수목금토일])\s*(\d)박$', parts[1])
        if not pm:
            raise SystemExit('%s 패턴을 읽지 못했습니다: %r' % (code, parts[1]))
        pat = pm.group(1)
        if PAT_NIGHTS[pat] != int(pm.group(2)):
            raise SystemExit('%s 박수 불일치: %s' % (code, parts[1]))
        date = datetime.date(2027, 6, int(dm.group(1)))
        back = datetime.date(2027, 6, int(dm.group(2)))
        if (back - date).days != PAT_NIGHTS[pat]:
            raise SystemExit('%s 출발·귀국 간격이 박수와 다릅니다: %s' % (code, parts[0]))
        if (WD[pat[0]] - (date.weekday() + 1) % 7) % 7 != 0:
            raise SystemExit('%s 요일 불일치: %s %s' % (code, date.isoformat(), pat))
        price = won(parts[2])
        if not price:
            raise SystemExit('%s 금액을 읽지 못했습니다: %r' % (code, parts[2]))
        airline = parts[3].strip()
        leg = parts[4].strip()
        note, via = build_note(leg)
        alt, thin, no_direct = None, False, False
        for more in parts[5:]:
            for piece in [x.strip() for x in more.split(' / ')]:
                if piece.startswith('직항편우선 탭'):
                    got = re.search(r'([\d,]{6,})', piece)
                    if got:
                        alt = int(got.group(1).replace(',', ''))
                        if alt <= price:
                            raise SystemExit('%s 직항 금액이 최저가보다 싸거나 같습니다: %s'
                                             % (code, piece))
                        note += ' · 직항 금액 ' + format(alt, ',') + '원'
                    else:
                        if '직항편 없음' in piece:
                            no_direct = True
                        note += ' · 직항 운임 미표시'
                elif piece.startswith('직항 없음'):
                    no_direct = True
                    note += ' · 직항편 없음'
                elif piece.startswith('최저가(직항)'):
                    pass                      # 편성이 이미 직항 — 덧붙일 것이 없다
                elif re.match(r'^캘린더', piece):
                    pass                      # 가격 캘린더 교차 확인 메모 — 값이 아니다
                elif re.match(r'^\d+석 미만', piece):
                    thin = True
                    note += ' · 잔여 9석 미만'
                elif re.match(r'^\d+개', piece):
                    pass                      # 그날 표시된 항공편 수(괄호 메모 포함) — 값이 아니다
                else:
                    raise SystemExit('%s 처리하지 못한 비고: %r' % (code, piece))
        if no_direct and alt:
            raise SystemExit('%s 직항 없음인데 직항 금액이 있습니다' % code)
        if (code, date.isoformat(), pat) in cells:
            raise SystemExit('중복 칸 %s %s %s' % (code, date.isoformat(), pat))
        cells[(code, date.isoformat(), pat)] = dict(
            code=code, date=date.isoformat(), back=back.isoformat(), pattern=pat,
            price=price, airline=airline or None, via=via, alt=alt, thin=thin, note=note)
    return cells


def matrix_expect():
    """원문의 '가격 매트릭스' 표 → 노선별 (최저, 최고) · 패턴 평균."""
    text = read()
    sect = text.split('## 가격 매트릭스')[1].split('## 날짜·패턴별')[0]
    out, avg = {}, {}
    for line in sect.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 7:
            continue
        m = re.match(r'^[^|]*?\(([A-Z]{3})\)$', cells[0])
        if m:
            vals = []
            for c in cells[1:6]:
                c = c.replace('**', '').replace('원', '').replace(',', '').strip()
                if not c.isdigit():
                    raise SystemExit('%s 표 값 이상: %r' % (m.group(1), c))
                vals.append(int(c))
            out[m.group(1)] = (min(vals), max(vals))
            continue
        if '패턴 평균' in cells[0]:
            for pat, c in zip(('금~일', '토~월', '목~일', '금~월', '목~월'), cells[1:6]):
                c = c.replace('**', '').replace('원', '').replace(',', '').strip()
                if not c.isdigit():
                    raise SystemExit('패턴 평균 값 이상: %r' % c)
                avg[pat] = int(c)
    return out, avg


def check(cells):
    if len(cells) != EXPECT_CELLS:
        raise SystemExit('%d칸 (기대 %d칸)' % (len(cells), EXPECT_CELLS))
    codes = {k[0] for k in cells}
    if codes != set(ROUTES):
        raise SystemExit('노선이 24개가 아닙니다: %s' % sorted(codes))
    want = set()
    for code in ROUTES:
        for pat in PAT_NIGHTS:
            d = (datetime.date.fromisoformat(WEEK_START) +
                 datetime.timedelta(days=(WD[pat[0]] - WD['목']) % 7)).isoformat()
            want.add((code, d, pat))
    if set(cells) != want:
        raise SystemExit('칸 집합이 24노선 × 5패턴과 다릅니다: %s'
                         % sorted(set(cells) ^ want)[:6])
    ps = [c['price'] for c in cells.values()]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('최저·최고 %s (원문 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    for pat, want_avg in EXPECT_AVG.items():
        v = [c['price'] for c in cells.values() if c['pattern'] == pat]
        if len(v) != 24:
            raise SystemExit('%s %d칸 (기대 24칸)' % (pat, len(v)))
        if abs(sum(v) / len(v) - want_avg) > 1:
            raise SystemExit('%s 평균 %.1f (원문 %d)' % (pat, sum(v) / len(v), want_avg))
    direct = sum(1 for c in cells.values() if c['via'] is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (원문 %d)' % (direct, EXPECT_DIRECT))
    if any(c['via'] is None for c in cells.values()):
        raise SystemExit('via 미확인 칸이 있습니다')
    thin = sum(1 for c in cells.values() if c['thin'])
    if thin != EXPECT_THIN:
        raise SystemExit('9석 미만 표시 칸 %d (원문 %d)' % (thin, EXPECT_THIN))
    exp, exp_avg = matrix_expect()
    if set(exp) != set(ROUTES):
        raise SystemExit('매트릭스 표 노선이 24개가 아닙니다: %s' % sorted(exp))
    if exp_avg != EXPECT_AVG:
        raise SystemExit('매트릭스 표 패턴 평균 %s (스크립트 상수 %s)' % (exp_avg, EXPECT_AVG))
    for code in ROUTES:
        v = [c['price'] for k, c in cells.items() if k[0] == code]
        if len(v) != 5:
            raise SystemExit('%s %d칸 (기대 5칸)' % (code, len(v)))
        if (min(v), max(v)) != exp[code]:
            raise SystemExit('%s 최저·최고 %s (매트릭스 표 %s)'
                             % (code, (min(v), max(v)), exp[code]))
        if exp[code] != ROUTE_MINMAX[code]:
            raise SystemExit('%s 매트릭스 표 %s (스크립트 상수 %s)'
                             % (code, exp[code], ROUTE_MINMAX[code]))
    for k, c in cells.items():
        if c['alt'] is not None and c['alt'] <= c['price']:
            raise SystemExit('%s 직항 금액이 최저가 이하입니다' % (k,))
        if c['price'] <= 0:
            raise SystemExit('%s 가격이 양의 정수가 아닙니다' % (k,))
        if not c['note']:
            raise SystemExit('%s note 비어 있음' % (k,))
        if '**' in c['note'] or '[' in c['note'] or '출처' in c['note']:
            raise SystemExit('%s note 에 마크업이 있습니다: %r' % (k, c['note']))
        if '총' in c['note'] and c['via'] is False:
            raise SystemExit('%s 직항인데 총 소요시간이 붙었습니다: %r' % (k, c['note']))
        for word in BANNED:
            if word in c['note'] or word in (c['airline'] or ''):
                raise SystemExit('%s 값에 제3자 사이트 이름(%s)이 있습니다' % (k, word))
    return cells


def recount(fl):
    all_deals = [d for r in fl['routes'] for d in r['deals']]
    by_month = collections.Counter(d['date'][:7] for d in all_deals)
    fl['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month.get(k, 0) for k in fl['months']},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals
                       if d['pattern'].split('~')[0] == d['pattern'].split('~')[-1]),
    }
    return fl['counts']


def _viaword(d):
    return '직항' if d.get('via') is False else ('경유' if d.get('via') else '편성 미확인')


def span(d):
    return '%d/%d~%d/%d' % (int(d['date'][5:7]), int(d['date'][8:10]),
                            int(d['back'][5:7]), int(d['back'][8:10]))


def week_note(rows, label):
    lo = min(rows, key=lambda d: d['price'])
    hi = max(rows, key=lambda d: d['price'])
    agg = collections.defaultdict(list)
    for d in rows:
        agg[d['pattern']].append(d['price'])
    avg = ' < '.join('{} {}원'.format(p, format(round(sum(v) / len(v)), ','))
                     for p, v in sorted(agg.items(), key=lambda kv: sum(kv[1]) / len(kv[1])))
    direct = sum(1 for d in rows if d.get('via') is False)
    ties_lo = sum(1 for d in rows if d['price'] == lo['price'])
    ties_hi = sum(1 for d in rows if d['price'] == hi['price'])
    return (label + ' 최저는 ' + CITY[lo['code']] + ' ' + span(lo) + ' ' + lo['pattern'] + ' '
            + format(lo['price'], ',') + '원(' + (lo['airline'] or '항공사 미확인') + ' '
            + _viaword(lo) + (' · 같은 금액 %d칸' % ties_lo if ties_lo > 1 else '')
            + ')이고, 최고는 ' + CITY[hi['code']] + ' ' + span(hi) + ' ' + hi['pattern'] + ' '
            + format(hi['price'], ',') + '원(' + (hi['airline'] or '항공사 미확인') + ' '
            + _viaword(hi) + (' · 같은 금액 %d칸' % ties_hi if ties_hi > 1 else '')
            + ')입니다. 직항이 최저가인 칸 ' + str(direct) + ' · 경유 '
            + str(len(rows) - direct) + '칸이고, 패턴 평균은 ' + avg + ' 순입니다.')


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 6월 4주(6/24~28) 120칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ⑤ 항공 기존 24개 노선 2027년 6월 4주차(6/24~28) '
        '5패턴 120칸 완결 — 최저 상하이 6/26~28 토~월 299,100원(춘추항공 직항), '
        '직항이 최저가인 칸 36, 가격표 자리표시 19칸 교체, 총 8,452→8,553건'))
    args = ap.parse_args(argv)

    cells = check(parse())
    print('파싱 %d칸 — 최저 %s · 최고 %s · 직항이 최저인 칸 %d · 경유 %d · 잔여 9석 미만 %d'
          % (len(cells), format(min(c['price'] for c in cells.values()), ','),
             format(max(c['price'] for c in cells.values()), ','),
             sum(1 for c in cells.values() if c['via'] is False),
             sum(1 for c in cells.values() if c['via'] is True),
             sum(1 for c in cells.values() if c['thin'])))
    for k in sorted(cells)[:2]:
        print('  예:', k, cells[k])

    master = json.load(open(MASTER, encoding='utf-8'))
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다' % code)

    before = {k: json.dumps(master.get(k), ensure_ascii=False, sort_keys=True)
              for k in ('hotels', 'accor', 'sources', 'window', 'built', 'voucherExpiry',
                        'schema', 'version', 'ttang')}
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    before_deals = {c: json.dumps(routes[c]['deals'], ensure_ascii=False) for c in ROUTES}
    before_daytrip = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    before_other = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_jun = fl['counts']['byMonth'][MONTH]
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])

    # 이 주차에 남아 있던 자리표시 칸 — 같은 (노선·출발일·패턴)이므로 이번 실측으로 교체한다.
    placeholders = {}
    for code in ROUTES:
        for d in routes[code]['deals']:
            if WEEK_START <= d['date'] <= WEEK_END and d['pattern'] in PAT_NIGHTS:
                if d.get('src') != '가격표' or d.get('note') != '가격표 실측 · 직항/경유 미확인':
                    raise SystemExit('이 주차에 예상 밖의 기존 칸: %s %s'
                                     % (code, json.dumps(d, ensure_ascii=False)))
                placeholders[(code, d['date'], d['pattern'])] = d
    if len(placeholders) != EXPECT_PLACEHOLDER:
        raise SystemExit('자리표시 칸 %d개 (기대 %d개): %s'
                         % (len(placeholders), EXPECT_PLACEHOLDER, sorted(placeholders)))
    extra_keys = set(cells) - set(placeholders)
    print('자리표시 %d칸 교체 · 새 칸 %d칸 추가' % (len(placeholders), len(extra_keys)))

    replaced = []
    for key, old in placeholders.items():
        v = cells[key]
        deal = collections.OrderedDict()
        deal['date'] = v['date']
        deal['back'] = v['back']
        deal['pattern'] = key[2]
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt']:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        deal = json.loads(json.dumps(deal))
        deals = routes[key[0]]['deals']
        idx = next(i for i, d in enumerate(deals) if (d['date'], d['pattern']) == key[1:])
        deals[idx] = deal
        replaced.append((key[0], key[1], key[2], old['price'], v['price']))

    added = []
    for key in sorted(extra_keys):
        v = cells[key]
        deal = collections.OrderedDict()
        deal['date'] = v['date']
        deal['back'] = v['back']
        deal['pattern'] = key[2]
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt']:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        routes[key[0]]['deals'].append(json.loads(json.dumps(deal)))
        added.append(key)
    for code in ROUTES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))
        for d in routes[code]['deals']:
            for word in BANNED:
                if word in json.dumps(d, ensure_ascii=False):
                    raise SystemExit('%s %s 값에 제3자 사이트 이름(%s)이 있습니다'
                                     % (code, d['date'], word))

    counts = recount(fl)
    if counts['total'] != before_total + len(added):
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], before_total + len(added)))
    if counts['byMonth'][MONTH] != before_jun + len(added):
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                 before_jun + len(added)))

    rows = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if WEEK_START <= d['date'] <= WEEK_END
            and d['pattern'] in PAT_NIGHTS]
    if len(rows) != EXPECT_CELLS:
        raise SystemExit('이 주 칸 %d칸 (기대 %d칸)' % (len(rows), EXPECT_CELLS))
    ps = [d['price'] for d in rows]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('이 주 최저·최고 %s (기대 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    if any(d.get('src') for d in rows):
        raise SystemExit('이 주에 가격표 자리표시 칸이 남아 있습니다')

    week_sent = ('2027년 6월 4주차(6/24~28) 24개 노선 5패턴 120칸도 전부 실측했습니다 — '
                 '이 주도 한국 공휴일이 없어 주말 수요만 반영된 기준선 주차이고, '
                 + week_note(rows, '이 주(6/24~28)')
                 + ' 목요일 출발·일요일 귀국(③)이 가장 싸고 금요일 출발·월요일 귀국(④)이 '
                   '가장 비싸며, 두 패턴 차이는 7,566원입니다. 3주차(6/17~21) 120칸 평균 '
                   '483,227원보다 4,741원(+1.0%) 높습니다.')
    if '**' in week_sent:
        raise SystemExit('notes 문장에 마크다운 별표가 있습니다')
    for word in BANNED:
        if word in week_sent:
            raise SystemExit('notes 문장에 제3자 사이트 이름(%s)이 있습니다' % word)
    fl['notes'][MONTH] = fl['notes'][MONTH].rstrip() + ' ' + week_sent

    for key, old in before.items():
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != old:
            raise SystemExit('%s 가 바뀌었습니다' % key)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('noSale 이 바뀌었습니다')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != before_other:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다')
    for code in ROUTES:
        old = json.loads(before_deals[code])
        cur = routes[code]['deals']
        if len(cur) != len(old) + 5 - sum(1 for k in placeholders if k[0] == code):
            raise SystemExit('%s 딜 %d건 (기존 %d + 이번 %d)'
                             % (code, len(cur), len(old),
                                5 - sum(1 for k in placeholders if k[0] == code)))
        have = {(d['date'], d['pattern']): d for d in cur}
        if len(have) != len(cur):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for o in old:
            key = (o['date'], o['pattern'])
            got = have.get(key)
            if got is None:
                raise SystemExit('%s 기존 딜이 사라졌습니다: %s %s' % (code, o['date'], o['pattern']))
            if (code, o['date'], o['pattern']) in placeholders:
                continue          # 이번 실측으로 교체된 칸
            if json.dumps(got, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(o, ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 기존 딜이 바뀌었습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
        keys = [(d['date'], WD[d['pattern'][0]]) for d in cur]
        if keys != sorted(keys):
            raise SystemExit('%s 딜 정렬이 깨졌습니다' % code)
        if json.dumps(routes[code]['daytrip'], ensure_ascii=False) != before_daytrip[code]:
            raise SystemExit('%s 당일치기 요약이 바뀌었습니다' % code)
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')
    for word in BANNED:
        if word in json.dumps(fl['notes'], ensure_ascii=False):
            raise SystemExit('notes 에 제3자 사이트 이름이 들어갔습니다: %s' % word)

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    master['extended'] = (before_extended + ' / ' + args.note).strip(' /')

    print('교체 %d칸(평균 %s원 → %s원) · 신규 %d칸'
          % (len(replaced),
             format(round(sum(r[3] for r in replaced) / len(replaced)), ','),
             format(round(sum(r[4] for r in replaced) / len(replaced)), ','),
             len(added)))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'],
             counts['total'] - counts['daytrip'], counts['daytrip']))
    print('2027-06 %d → %d건' % (before_jun, counts['byMonth'][MONTH]))
    print('notes[2027-06] 새 문장:', week_sent)

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        return 0
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('저장: %s' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
