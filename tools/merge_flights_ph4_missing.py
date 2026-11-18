#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 필리핀 4개 노선(세부·마닐라·보홀(팡라오)·클락)의 **2027년 7~10월 미조회 174칸**을
`data/master_db.json` 의 `flights` 에 병합한다.

원본: `data-sources/flights-sea-new8/부산출발-{세부,보홀,마닐라,클락}-7_10월-6번보완.md`
  · 세부 63칸 — `## 📅 주차별 상세` 의 표 `| 07-08~07-12 (목~월) | ₩455,543 | 대표 편성 | 차선 | [Sxx] |`
      최저가 열이 그 칸의 값이고, 대표 편성의 금액이 최저가와 같을 때만 그 편성(항공사·경유)을 값에 붙인다.
  · 보홀 73칸 — `## 🗂️ 73칸 전체 내역 (표)` 의 줄 `| 21 | 07/29주 | 07-31~08-02 | **₩639,400** | … | 날짜표 | … |`
      조회가 `개별` 이면 항공사·경유를 적고, `날짜표` 면 값만 있고 개별 편이 미조회라 항공사를 비운다.
  · 마닐라 18칸 — `## 1. 18칸 전체` 의 줄 `- 🟡 **9/16(목) → 9/20(월) · 목~월** — **₩469,200** · 필리핀항공 **직항** · 3시간 55분`
  · 클락 20칸 — `## 📋 20칸 전체 내역 (한 표)` 의 표 `| **A1** | 09-16(목)~09-19(일) (3박) | **₩658,100** | 항공사 | 경유 | 총 소요 | 출발→도착 |`

규칙:
  · 네 파일의 칸이 지금 `master_db.json` 에서 **미조회(값도 상태도 없음)** 인 칸과 정확히 같은지 대조한다.
    하나라도 다르거나 겹치면 멈춘다(기존 값을 덮어쓰지 않는다).
  · 파일이 스스로 적은 칸 수·최저/최고·패턴별 칸 수·월별 칸 수와 파싱 결과를 대조한다.
  · 값은 원문 그대로(반올림 없음). 항공사 이름·직항/경유·소요시간만 앱 표기로 옮긴다.
  · 제3자 사이트 이름(구글·스카이스캐너·네이버·카약·트립닷컴)은 값·note 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · 출처 목록 · 다른 43개 노선 · 다른 달 `notes` · `noSale` 은 바이트 동일성으로 보존을 확인한다.
  · `counts`(flights.total · byMonth · holiday · daytrip, 최상위 deals)와 2027-07~10 `notes` 를 다시 쓴다.
  · `extended` 끝에 이번 병합 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_ph4_missing.py --dry-run
    python3 tools/merge_flights_ph4_missing.py
"""
import argparse
import collections
import copy
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-sea-new8'))
FILES = {'CEB': '부산출발-세부-7_10월-6번보완.md',
         'TAG': '부산출발-보홀-7_10월-6번보완.md',
         'MNL': '부산출발-마닐라-7_10월-6번보완.md',
         'CRK': '부산출발-클락-7_10월-6번보완.md'}
CITY = {'CEB': '세부', 'MNL': '마닐라', 'TAG': '보홀(팡라오)', 'CRK': '클락'}
WD = {'일': 0, '월': 1, '화': 2, '수': 3, '목': 4, '금': 5, '토': 6}
WK = ('목~일', '금~일', '토~월', '목~월', '금~월')
PAT_ORDER = ('목~월', '목~일', '금~월', '금~일', '토~월')
WEEKS = tuple((datetime.date(2027, 7, 1) + datetime.timedelta(days=7 * i)).isoformat()
              for i in range(22))

# 파일이 스스로 적은 값 — 파싱이 조용히 빠뜨리지 않았는지 대조한다
EXPECT = {
    'CEB': {'cells': 63, 'low': 455543, 'high': 909700,
            'patterns': {'목~일': 12, '금~일': 12, '토~월': 12, '금~월': 13, '목~월': 14}},
    'TAG': {'cells': 73, 'low': 558400, 'high': 1004900,
            'months': {'2027-07': 23, '2027-08': 20, '2027-09': 22, '2027-10': 8},
            'src': {'개별': 31, '날짜표': 42}},
    'MNL': {'cells': 18, 'low': 399291, 'high': 738200},
    'CRK': {'cells': 20, 'low': 528800, 'high': 894600,
            'patterns': {'목~일': 4, '금~일': 4, '토~월': 4, '금~월': 4, '목~월': 4}},
}
EXPECT_TOTAL = sum(v['cells'] for v in EXPECT.values())          # 174
BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '네이버', '구글',
          'google', 'Google')


def pat_back(start, back):
    a = datetime.date.fromisoformat(start)
    b = datetime.date.fromisoformat(back)
    label = '%s~%s' % ('월화수목금토일'[a.weekday()], '월화수목금토일'[b.weekday()])
    return label, (b - a).days


def norm_time(s):
    s = re.sub(r'(\d+)시간\s*(\d+)분', r'\1시간 \2분', s)
    s = re.sub(r'(\d+)시간(?=\s|·|$|,)', r'\1시간', s)
    return s


def clean(s):
    s = s.replace('**', '').replace('(PAL Express)', '').strip()
    s = s.replace('필리핀항공 ', '필리핀항공 ')       # 이름은 그대로 둔다
    s = re.sub(r'\s*\(18칸 중 최저\)', '', s)
    s = re.sub(r'\s*\(절대최저\)', '', s)
    s = re.sub(r'\s*⚠️.*$', '', s)
    s = re.sub(r'\s*·\s*', ' · ', s)
    s = re.sub(r'\s+', ' ', s).strip(' ·')
    return norm_time(s)


def parse_ceb(text):
    i = text.index('## 📅 주차별 상세')
    j = text.index('## 🏆 최저가 TOP 10')
    rows = re.findall(r'^\| (\d{2}-\d{2})~(\d{2}-\d{2}) \(([^)]+)\) \| ₩([\d,]+) \| (.+?) \| (.+?) \|',
                      text[i:j], re.M)
    out = {}
    for a, b, pat, price, rep, alt in rows:
        start, back = '2027-' + a, '2027-' + b
        label, _ = pat_back(start, back)
        if label != pat:
            raise SystemExit('세부 %s 패턴 표기 %s (계산 %s)' % (start, pat, label))
        if (start, pat) in out:
            raise SystemExit('세부 %s %s 중복' % (start, pat))
        price = int(price.replace(',', ''))
        last = re.findall(r'₩([\d,]+)', rep)
        rep_price = int(last[-1].replace(',', '')) if last else None
        rec = {'price': price, 'via': True, 'airline': None, 'note': None, 'back': back}
        if rep_price == price:
            code = re.search(r'\b(MNL|HKG|SIN|TPE|ICN|SGN|HAN)\b', rep)
            if not code:
                if '날짜표' in rep:
                    # 날짜 표에서만 읽은 칸 — 편성 상세가 없으므로 금액만 적는다
                    rec['note'] = '경유 · 날짜표 값 (개별 편 미조회)'
                    out[(start, pat)] = rec
                    continue
                raise SystemExit('세부 %s 대표 편성에서 경유지를 읽지 못했습니다: %s' % (start, rep))
            airline = clean(rep[:code.start()])
            airline = re.sub(r'^(1회경유|경유\s*\d회)\s*', '', airline)
            airline = re.sub(r'\s*(1회경유|경유\s*\d회)$', '', airline).strip()
            if not airline:
                raise SystemExit('세부 %s 대표 편성 항공사 없음: %s' % (start, rep))
            tail = rep[code.end():]
            tail = re.sub(r'₩[\d,]+', '', tail)
            tail = re.sub(r'\s*\(=[^)]*\)', '', tail)
            tail = re.sub(r'\s*\(재조회\)', '', tail)
            tail = tail.strip(' ·')
            tail = re.sub(r'\s*/\s*', ' · 총 ' if '총' not in tail else ' · ', tail)
            rec['airline'] = airline
            rec['note'] = clean('경유 1회 %s %s' % (code.group(1), tail))
        else:
            rec['note'] = '경유 · 최저가 탭 값 (표시 편성 항공사 미기재)'
        out[(start, pat)] = rec
    return out


def parse_tag(text):
    rows = re.findall(r'^\| (\d+) \| (\d{2}/\d{2})주 \| (\d{2}-\d{2})~(\d{2}-\d{2}) \| '
                      r'\*\*₩([\d,]+)\*\* \| (.+?) \| (\S+) \| (.*?) \|$', text, re.M)
    out = {}
    src_count = collections.Counter()
    for _n, _wk, a, b, price, it, src, _note in rows:
        start, back = '2027-' + a, '2027-' + b
        label, _ = pat_back(start, back)
        if (start, label) in out:
            raise SystemExit('보홀 %s %s 중복' % (start, label))
        price = int(price.replace(',', ''))
        rec = {'price': price, 'via': True, 'airline': None, 'note': None, 'back': back}
        src_count[src] += 1
        if src == '개별':
            parts = [p.strip() for p in it.split('·')]
            if '경유' not in parts[1]:
                raise SystemExit('보홀 %s 경유 표기가 없습니다: %s' % (start, it))
            rec['airline'] = clean(parts[0])
            rec['note'] = clean(' · '.join(parts[1:]))
        else:
            rec['note'] = '경유 · 날짜표 값 (개별 편 미조회)'
        out[(start, label)] = rec
    out['__src__'] = dict(src_count)
    return out


def parse_mnl(text):
    i = text.index('## 1. 18칸 전체')
    j = text.index('## 2. 주차별 도형')
    rows = re.findall(r'^- \S+ \*\*(\d{1,2})/(\d{1,2})\(([월화수목금토일])\) → '
                      r'(\d{1,2})/(\d{1,2})\(([월화수목금토일])\) · '
                      r'([월화수목금토일]~[월화수목금토일])\*\* — \*\*₩([\d,]+)\*\* · (.+)$',
                      text[i:j], re.M)
    out = {}
    for mo, d, _w, mo2, d2, _w2, pat, price, rest in rows:
        start = '2027-%02d-%02d' % (int(mo), int(d))
        back = '2027-%02d-%02d' % (int(mo2), int(d2))
        label, _ = pat_back(start, back)
        if label != pat:
            raise SystemExit('마닐라 %s 패턴 표기 %s (계산 %s)' % (start, pat, label))
        if (start, pat) in out:
            raise SystemExit('마닐라 %s %s 중복' % (start, pat))
        rest = clean(rest)
        via = '직항' not in rest
        airline = re.split(r'\s+경유|\s+직항', rest)[0].strip()
        if not airline:
            raise SystemExit('마닐라 %s 항공사를 읽지 못했습니다: %s' % (start, rest))
        note = rest[len(airline):].strip(' ·')
        if not note.startswith(('경유', '직항')):
            raise SystemExit('마닐라 %s 편성 표기가 이상합니다: %s' % (start, rest))
        out[(start, pat)] = {'price': int(price.replace(',', '')), 'via': via,
                             'airline': airline, 'note': clean(note), 'back': back}
    return out


def parse_crk(text):
    rows = re.findall(r'^\| \*\*([A-D]\d)\*\* \| (\d{2}-\d{2})\(([월화수목금토일])\)~'
                      r'(\d{2}-\d{2})\(([월화수목금토일])\) \((\d)박\) \| \*\*₩([\d,]+)\*\* \| '
                      r'(.+?) \| (.+?) \| (.+?) \| (.+?) \|$', text, re.M)
    out = {}
    for _cid, a, _wa, b, _wb, nights, price, air, via, dur, arr in rows:
        start, back = '2027-' + a, '2027-' + b
        label, n = pat_back(start, back)
        if n != int(nights):
            raise SystemExit('클락 %s 박수 %s (표기 %s박)' % (start, n, nights))
        if (start, label) in out:
            raise SystemExit('클락 %s %s 중복' % (start, label))
        if '경유' not in via:
            raise SystemExit('클락 %s 경유 표기가 없습니다: %s' % (start, via))
        self_transfer = '자가 환승' in air
        airline = clean(re.sub(r'\s*\(자가 환승\)', '', air))
        note = clean('%s · 총 %s · %s' % (via, dur, arr))
        if self_transfer:
            note += ' · 자가 환승'
        out[(start, label)] = {'price': int(price.replace(',', '')), 'via': True,
                               'airline': airline, 'note': note, 'back': back}
    return out


def load_cells():
    cells = {}
    for code, fname in FILES.items():
        text = open(os.path.join(SRC, fname), encoding='utf-8').read()
        if code == 'CEB':
            got = parse_ceb(text)
        elif code == 'TAG':
            got = parse_tag(text)
            src_count = got.pop('__src__')
        elif code == 'MNL':
            got = parse_mnl(text)
        else:
            got = parse_crk(text)
        want = EXPECT[code]
        if len(got) != want['cells']:
            raise SystemExit('%s %d칸 (원문 %d칸)' % (code, len(got), want['cells']))
        vals = [v['price'] for v in got.values()]
        if (min(vals), max(vals)) != (want['low'], want['high']):
            raise SystemExit('%s 최저·최고 %s (원문 %s~%s)'
                             % (code, (min(vals), max(vals)), want['low'], want['high']))
        if 'patterns' in want:
            got_pat = dict(collections.Counter(k[1] for k in got))
            if got_pat != want['patterns']:
                raise SystemExit('%s 패턴 분포 %s (원문 %s)' % (code, got_pat, want['patterns']))
        if 'months' in want:
            got_mon = dict(collections.Counter(k[0][:7] for k in got))
            if got_mon != want['months']:
                raise SystemExit('%s 월 분포 %s (원문 %s)' % (code, got_mon, want['months']))
        if 'src' in want and src_count != want['src']:
            raise SystemExit('%s 조회 방식 %s (원문 %s)' % (code, src_count, want['src']))
        for (start, pat), rec in got.items():
            if rec['back'] != (datetime.date.fromisoformat(start) +
                               datetime.timedelta(days=(WD[pat[-1]] - WD[pat[0]]) % 7)).isoformat():
                raise SystemExit('%s %s 귀국일이 맞지 않습니다' % (code, start))
            if '2027-07-01' > start or start > '2027-10-14':
                raise SystemExit('%s %s 가 2027년 7~10/14 밖입니다' % (code, start))
            for word in BANNED:
                if word in json.dumps(rec, ensure_ascii=False):
                    raise SystemExit('%s %s 값에 금지된 이름(%s)' % (code, start, word))
        cells[code] = got
    return cells


def missing_of(master, code):
    routes = {r['code']: r for r in master['flights']['routes']}
    grid = {((datetime.date.fromisoformat(w) + datetime.timedelta(days=(WD[p[0]] - 4) % 7)).isoformat(), p)
            for w in WEEKS for p in WK}
    deals = {(d['date'], d['pattern']) for d in routes[code]['deals']
             if '2027-07-01' <= d['date'] <= '2027-11-29'}
    marks = {(n['date'], n['pattern']) for n in master['flights']['noSale'] if n.get('code') == code}
    return grid - deals - marks


def sort_key(deal):
    return (deal['date'], PAT_ORDER.index(deal['pattern']) if deal['pattern'] in PAT_ORDER else 9)


def month_sentence(master, added_by_month):
    parts = []
    for m in ('2027-07', '2027-08', '2027-09', '2027-10'):
        n = added_by_month.get(m, 0)
        if n:
            parts.append('%s %d칸' % (m[5:7] + '월', n))
    return (' 필리핀 4개 노선(세부·마닐라·보홀·클락)은 2027년 7~10월 미조회 칸 %d칸을 전부 실측해 '
            '네 노선 모두 75/75칸(100%%)이 됐습니다 — 이번에 %s을 채웠고, 판매편 0건·요금 미공개 없이 '
            '전 칸에 값이 있습니다.' % (EXPECT_TOTAL, ' · '.join(parts)))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default=(
        '2026-11-19 KST ④ 항공 필리핀 4노선 2027년 7~10월 미조회 174칸 전부 실측(세부 63 · 보홀 73 · '
        '마닐라 18 · 클락 20) — 네 노선 75/75칸 완결, 최저 마닐라 10/7~10 399,291원, 총 7,243→7,417건'))
    args = ap.parse_args(argv)

    cells = load_cells()
    master = json.load(open(MASTER, encoding='utf-8'))
    merged = copy.deepcopy(master)
    routes = {r['code']: r for r in merged['flights']['routes']}
    old_routes = {r['code']: r for r in master['flights']['routes']}

    added_month = collections.Counter()
    added = {}
    for code in FILES:
        missing = missing_of(master, code)
        got = set(cells[code])
        if got != missing:
            raise SystemExit('%s 칸이 지금 미조회 칸과 다릅니다 — 파일에만 %d칸, DB에만 %d칸: %s'
                             % (code, len(got - missing), len(missing - got),
                                sorted(got ^ missing)[:6]))
        lst = routes[code]['deals']
        for (start, pat), rec in sorted(cells[code].items()):
            deal = {'date': start, 'back': rec['back'], 'pattern': pat, 'price': rec['price']}
            if rec['airline']:
                deal['airline'] = rec['airline']
                deal['via'] = rec['via']
            else:
                deal['via'] = rec['via']
                deal['src'] = '가격표'
            deal['note'] = rec['note']
            pos = sum(1 for d in lst if d['date'] < start)
            lst.insert(pos, deal)
        added[code] = len(cells[code])
        added_month.update(k[0][:7] for k in cells[code])
    if sum(added.values()) != EXPECT_TOTAL:
        raise SystemExit('추가 칸 %d (기대 %d)' % (sum(added.values()), EXPECT_TOTAL))

    # ── 보존 확인 ──────────────────────────────────────────────
    for key in ('schema', 'version', 'window', 'built', 'voucherExpiry', 'sources', 'accor', 'hotels'):
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != \
                json.dumps(merged.get(key), ensure_ascii=False, sort_keys=True):
            raise SystemExit('%s 가 달라졌습니다' % key)
    new_routes = {r['code']: r for r in merged['flights']['routes']}
    if list(old_routes) != list(new_routes):
        raise SystemExit('노선 목록이 달라졌습니다')
    for code, old in old_routes.items():
        if code not in FILES:
            if json.dumps(old, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(new_routes[code], ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 노선이 달라졌습니다' % code)
            continue
        if {k: v for k, v in old.items() if k != 'deals'} != \
                {k: v for k, v in new_routes[code].items() if k != 'deals'}:
            raise SystemExit('%s 노선 메타가 달라졌습니다' % code)
        before = {(d['date'], d['pattern']): d for d in old['deals']}
        after = {(d['date'], d['pattern']): d for d in new_routes[code]['deals']}
        if not set(before) <= set(after):
            raise SystemExit('%s 기존 칸이 사라졌습니다' % code)
        for k, deal in before.items():
            if after[k] != deal:
                raise SystemExit('%s %s 칸이 예고 없이 달라졌습니다' % (code, k))
        if len(after) != len(before) + added[code]:
            raise SystemExit('%s 칸 수 %d → %d' % (code, len(before), len(after)))
        h2 = [d for d in new_routes[code]['deals'] if '2027-07-01' <= d['date'] <= '2027-11-29']
        if len(h2) != 75:
            raise SystemExit('%s 2027년 7~11월이 75칸이 아닙니다 (%d칸)' % (code, len(h2)))
        if [d['date'] for d in new_routes[code]['deals']] != \
                sorted(d['date'] for d in new_routes[code]['deals']):
            raise SystemExit('%s 날짜 정렬이 깨졌습니다' % code)
        if missing_of(merged, code):
            raise SystemExit('%s 에 아직 미조회 칸이 %d칸 있습니다'
                             % (code, len(missing_of(merged, code))))
    if json.dumps(master['flights']['noSale'], ensure_ascii=False) != \
            json.dumps(merged['flights']['noSale'], ensure_ascii=False):
        raise SystemExit('noSale 이 달라졌습니다')
    for code in FILES:
        for word in BANNED:
            if word in json.dumps([d for d in new_routes[code]['deals']
                                   if '2027-07-01' <= d['date'] <= '2027-10-14'], ensure_ascii=False):
                raise SystemExit('%s 새 값에 금지된 이름(%s)' % (code, word))

    # ── counts ────────────────────────────────────────────────
    deals = [d for r in merged['flights']['routes'] for d in r['deals']]
    by_month = collections.Counter(d['date'][:7] for d in deals)
    old_counts = master['flights']['counts']
    counts = {
        'total': len(deals),
        'byMonth': {m: by_month.get(m, 0) for m in merged['flights']['months']},
        'holiday': sum(1 for d in deals if d['date'] in ('2026-12-25', '2027-02-04')),
        'daytrip': sum(1 for d in deals if d['pattern'].split('~')[0] == d['pattern'].split('~')[-1]),
    }
    for m, n in old_counts['byMonth'].items():
        want = n + added_month.get(m, 0)
        if counts['byMonth'][m] != want:
            raise SystemExit('%s 건수 %s (기대 %s)' % (m, counts['byMonth'][m], want))
    if counts['holiday'] != old_counts['holiday'] or counts['daytrip'] != old_counts['daytrip']:
        raise SystemExit('연휴/당일치기 수가 달라졌습니다: %s' % counts)
    merged['flights']['counts'] = counts
    merged['counts'] = dict(master['counts'])
    merged['counts']['deals'] = counts['total']

    # ── notes · extended ──────────────────────────────────────
    sentence = month_sentence(merged, added_month)
    notes = dict(master['flights']['notes'])
    for m in ('2027-07', '2027-08', '2027-09', '2027-10'):
        if m not in notes:
            raise SystemExit('%s notes 가 없습니다' % m)
        notes[m] = notes[m].rstrip() + sentence
        for word in BANNED:
            if word in notes[m]:
                raise SystemExit('%s notes 에 금지된 이름(%s)' % (m, word))
    merged['flights']['notes'] = notes
    merged['extended'] = (master.get('extended', '') + ' / ' + args.note).strip(' /')
    for word in BANNED:
        if word in args.note:
            raise SystemExit('extended 에 금지된 이름(%s)' % word)

    print('노선별 추가:', added, '합계', sum(added.values()))
    print('월별 추가:', dict(added_month))
    print('counts:', json.dumps(counts, ensure_ascii=False))
    print('무항공사(가격표) 칸:', {c: sum(1 for d in new_routes[c]['deals']
                                        if '2027-07-01' <= d['date'] <= '2027-10-14'
                                        and 'airline' not in d) for c in FILES})
    print('최저 칸:', {c: min((d['price'], d['date'], d['pattern'])
                              for d in new_routes[c]['deals']
                              if '2027-07-01' <= d['date'] <= '2027-10-14') for c in FILES})

    if args.dry_run:
        print('\n[dry-run] 파일은 쓰지 않았습니다.')
        return 0
    with open(MASTER, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('\n%s 를 다시 썼습니다.' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
