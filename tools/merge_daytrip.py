#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **당일치기(0박 1일)** 조사 md → `data/master_db.json` 의 `flights` 병합.

사용법 (저장소 루트에서):
    python3 tools/merge_daytrip.py ../data-sources/flights-2026-12/...당일치기.md \
                                    ../data-sources/flights-2027-01/...당일치기.md --dry-run
    python3 tools/merge_daytrip.py ... --note "…KST ④ 항공 당일치기 반영"

읽는 줄 형식(두 보고서가 조금 다르다):
    - 2027-01-07(목) · 당일치기 · PUS–FUK · 337,700원 · 항공사·시각 미확인(가격표 실측)   (1월)
    - 2026-12-10(목) · 부산–후쿠오카 · 328,300원 · 실시간(최저 13:10 제주항공 …)          (12월)

규칙:
  · 출발일(요일)에서 패턴을 만든다 — 목~목·금~금·토~토·일~일·월~월(+화~화·수~수).
    `back` 은 출발일과 같다(0박).
  · 섹션 제목에 '불가'·'참고'가 있는 구간(오키나와 12월 참고가격 등)은 읽지 않는다.
    '가격 미표시'·'미확인' 줄은 gaps 로만 보고한다(추정 금지).
  · 같은 (노선, 출발일, 패턴)이 이미 있으면 최신 실측 가격으로 바꾸고,
    항공사·직항/경유·메모는 더 자세한 쪽을 남긴다.
  · `flights.patterns` 에 당일치기 패턴(kind='day')을 채우고, 주말형에는 kind='weekend' 를 붙인다.
  · 주차(`weeks`)의 표시 구간을 목~수(7일)로 다시 계산한다 — 당일치기 화·수 출발까지 한 주에 담기게.
  · 노선별 `daytrip` 메타(status/stay/note)를 보고서 내용대로 채운다. 호텔 데이터는 건드리지 않는다.
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
DAY_PATS = ['목~목', '금~금', '토~토', '일~일', '월~월', '화~화', '수~수']
CITY_CODE = {'후쿠오카': 'FUK', '도쿄': 'TYO', '나리타': 'TYO', '타이베이': 'TPE', '오사카': 'KIX',
             '나고야': 'NGO', '상하이': 'PVG', '푸둥': 'PVG', '칭다오': 'TAO', '가오슝': 'KHH',
             '타이중': 'RMQ', '베이징': 'BJS'}
CODE_ALIAS = {'NRT': 'TYO', 'HND': 'TYO', 'PEK': 'BJS', 'PKX': 'BJS'}
AIRLINES = ['제주항공', '에어부산', '진에어', '이스타항공', '트리니티항공', '대한항공', '아시아나항공',
            '중국동방항공', '춘추항공', '홍콩 익스프레스항공', '비엣젯항공', '타이거항공',
            '스타룩스', '캐세이퍼시픽', '중국국제항공', '상해항공', '룽에어', '피치항공',
            '일본 트랜스오션', '젯스타 재팬', '필리핀항공']

# 노선별 당일치기 가능 여부 — 2027-01-01·12월 당일치기 보고서(2026-11-17 실측·스케줄) 기준.
DAYTRIP_META = {
    'FUK': ('ok', '약 10시간', '오전 출발·저녁 귀국 조합 기준(1/27 실측 10시간 05분)', ''),
    'KIX': ('ok', '약 8시간', '간사이→부산 막편 20:40 도착', ''),
    'TYO': ('ok', '약 10시간', '나리타 기준 · 귀국 막편 22:00 부산 도착', ''),
    'NGO': ('ok', '약 9시간', '나고야→부산 막편 21:35 도착 · 직항편이 적어 경유가 최저인 날이 있음', ''),
    'PVG': ('ok', '약 5~6시간', '푸둥→부산 막편 20:55 도착', ''),
    'TPE': ('ok', '약 6시간 30분', '타이베이→부산 막편 21:00 도착', ''),
    'OKA': ('short', '약 2시간', '귀국편이 부산 13:05·13:30 도착뿐이라 체류가 짧음', '귀국편 오전뿐'),
    'TAO': ('short', '약 2~3시간', '오전 출발이 10:30, 귀국편이 오후 2시대뿐', '귀국편 오후 2시대'),
    'BJS': ('short', '2~4시간', '오전 편이 하루 2편뿐', '오전 편 2편뿐'),
    'KHH': ('short', '3~4시간', '부산 출발 12:00·14:05', '출발 낮 12~14시'),
    'RMQ': ('short', '3~4시간', '부산 출발 12:15·14:00 (하루 1~2편)', '하루 1~2편'),
    'MFM': ('no', '', '부산 직항 없음 · 경유 총 13시간 이상이라 같은 날 왕복 불가', '직항 없음·경유 13시간↑'),
    'HKG': ('no', '', '부산 출발 13:55·21:30·21:50 / 홍콩→부산 06:20·13:10 도착', '저녁 귀국편 없음'),
    'NKG': ('no', '', '부산 출발 18:50 한 편뿐(도착 21:40)', '출국편 저녁 1편'),
    'HGH': ('no', '', '부산 출발 14:00 한 편 / 귀국편은 13:00 부산 도착', '출국 오후 1편'),
    'BKK': ('no', '', '방콕 18:00 출발 / 방콕→부산 06:20 도착', '귀국편 심야·새벽'),
    'DAD': ('no', '', '다낭 20:50·21:05 출발 / 다낭→부산 06:50~08:30 도착', '귀국편 새벽 도착'),
    'CXR': ('no', '', '편도 5시간 이상 · 부산 출발 저녁, 귀국편 심야·이른 아침', '편도 5시간·귀국 심야'),
    'SGN': ('no', '', '편도 4시간 30분~5시간 40분 · 부산 출발 오후, 귀국편 심야', '편도 4시간 반 이상'),
    'SIN': ('no', '', '편도 6시간 40분 · 부산 출발 밤, 귀국편 이른 아침', '편도 6시간 40분'),
    'GUM': ('no', '', '괌 20:40·21:05 출발 / 괌→부산 06:40 도착', '귀국편 06:40 도착'),
    'HAN': ('no', '', '편도 4시간 50분 · 부산 출발 저녁, 귀국편 심야', '편도 4시간 50분'),
    'CNX': ('no', '', '편도 5시간 45분 · 부산 출발 저녁, 귀국편 이른 아침', '편도 5시간 45분'),
    'DPS': ('no', '', '편도 7시간 · 귀국편 심야 출발', '편도 7시간'),
}

LINE = re.compile(r'^- (\d{4}-\d{2}-\d{2})\(([월화수목금토일])\) · (.+)$')
HEAD = re.compile(r'^(#{2,3}) (.+)$')


def code_from(text):
    m = re.search(r'\(([A-Z]{3})', text)
    if m:
        return CODE_ALIAS.get(m.group(1), m.group(1))
    for city, code in CITY_CODE.items():
        if city in text:
            return code
    return None


def parse_tail(tail):
    """'가격표' / '실시간(…)' / '항공사·시각 미확인(가격표 실측)' / '제주항공 07:00→07:55 …' → 필드."""
    out = {'via': None}
    t = (tail or '').strip()
    if not t:
        out['src'] = '가격표'
        return out
    if t.startswith('실시간'):
        out['src'] = '실시간'
        t = t[len('실시간'):].strip()
        m = re.match(r'^\(([^)]*)\)\s*(.*)$', t)
        if m:
            t = (m.group(1) + ' ' + m.group(2)).strip()
    else:
        out['src'] = '가격표'
        if t.startswith('항공사·시각 미확인') or t.startswith('항공사 미확인'):
            return out
    names = [a for a in AIRLINES if a in t]
    if len(set(names)) == 1:
        out['airline'] = names[0]
        if t.startswith(names[0]):                      # 메모 앞의 항공사 이름은 중복이라 뺄다
            t = t[len(names[0]):].lstrip(' ·')
    if '직항 없음' in t or '경유만' in t:
        out['via'] = True
    elif '경유' in t:
        out['via'] = True
    elif '직항' in t:
        out['via'] = False
    t = re.sub(r'\s*—\s*', ' ※', t)
    out['note'] = t.strip()
    return out


def parse_md(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    section, deals, gaps = None, [], []
    for raw in lines:
        line = raw.strip()
        h = HEAD.match(line)
        if h:
            title = h.group(2)
            section = None if ('불가' in title or '참고' in title) else code_from(title)
            continue
        m = LINE.match(line)
        if not m or not section:
            continue
        date, wd, rest = m.groups()
        fields = [f.strip() for f in rest.split(' · ')]
        label = fields[0]
        i = 1
        code = section
        if i < len(fields) and fields[i].startswith('PUS–'):
            code = CODE_ALIAS.get(fields[i][4:], fields[i][4:])
            i += 1
        elif '–' in label:
            city = label.split('–')[-1].split('(')[0].strip()
            code = CITY_CODE.get(city, code)
        if i >= len(fields):
            gaps.append((code, date, label))
            continue
        pm = re.match(r'^([\d,]+)원$', fields[i])
        if not pm:
            gaps.append((code, date, label))
            continue
        price = int(pm.group(1).replace(',', ''))
        expected = WD[wd]
        if datetime.date.fromisoformat(date).isoweekday() % 7 != expected:
            raise SystemExit('%s 는 %s요일이 아닙니다 (%s)' % (date, wd, os.path.basename(path)))
        pattern = wd + '~' + wd
        deal = {'date': date, 'back': date, 'pattern': pattern, 'price': price}
        deal.update(parse_tail(' · '.join(fields[i + 1:])))
        deals.append((code, deal))
    return deals, gaps


def merge(master, deals, gaps, replace_price=True):
    routes = {r['code']: r for r in master['flights']['routes']}
    added, updated, filled, skipped = [], [], [], []
    for code, deal in deals:
        if code not in routes:
            raise SystemExit('마스터 DB 에 없는 노선입니다: %s' % code)
        r = routes[code]
        same = [d for d in r['deals'] if d['date'] == deal['date'] and d['pattern'] == deal['pattern']]
        if not same:
            r['deals'].append(deal)
            added.append((code, deal['date'], deal['pattern'], deal['price']))
            continue
        old = same[0]
        changed = False
        if replace_price and old['price'] != deal['price']:
            updated.append((code, deal['date'], deal['pattern'], old['price'], deal['price']))
            old['price'] = deal['price']
            changed = True
        for k in ('airline', 'src', 'note'):
            if deal.get(k) and (not old.get(k) or old.get('note') in ('직항/경유 미확인',)):
                if old.get(k) != deal[k]:
                    old[k] = deal[k]
                    changed = True
        if deal.get('via') is not None and old.get('via') is None:
            old['via'] = deal['via']
            changed = True
        if changed and not any(u[:3] == (code, deal['date'], deal['pattern']) for u in updated):
            filled.append((code, deal['date'], deal['pattern']))
        elif not changed:
            skipped.append((code, deal['date'], deal['pattern'], old['price'], deal['price']))
    for r in master['flights']['routes']:
        r['deals'].sort(key=lambda d: (d['date'], d['pattern']))
    return added, updated, filled, skipped


def sync_patterns(flights):
    """patterns 에 kind(주말형/당일치기)를 붙이고 당일치기 패턴을 채운다."""
    pats = []
    for p in flights['patterns']:
        q = dict(p)
        q.setdefault('kind', 'weekend')
        if q['label'].split('~')[0] == q['label'].split('~')[1]:
            q['nights'], q['kind'] = 0, 'day'
        pats.append(q)
    labels = {p['label'] for p in pats}
    for label in DAY_PATS:
        if label not in labels:
            pats.append({'label': label, 'nights': 0, 'kind': 'day'})
    flights['patterns'] = pats


def sync_weeks(flights):
    """주차 표시 구간을 목~수(7일)로 다시 계산 — 당일치기 화·수 출발까지 담는다."""
    for w in flights['weeks']:
        a = datetime.date.fromisoformat(w['thu'])
        b = a + datetime.timedelta(days=6)
        w['span'] = '%d/%d~%d/%d' % (a.month, a.day, b.month, b.day)
        w['end'] = b.isoformat()


def sync_meta(flights):
    """노선별 daytrip 메타 + counts 재계산."""
    for r in flights['routes']:
        meta = DAYTRIP_META.get(r['code'])
        if meta:
            r['daytrip'] = {'status': meta[0], 'stay': meta[1], 'note': meta[2], 'short': meta[3]}
    all_deals = [d for r in flights['routes'] for d in r['deals']]
    by_month = {}
    for d in all_deals:
        by_month[d['date'][:7]] = by_month.get(d['date'][:7], 0) + 1
    flights['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month[k] for k in sorted(by_month)},
        'holiday': sum(1 for d in all_deals if d['date'] in ('2026-12-25', '2027-02-04')),
        'daytrip': sum(1 for d in all_deals if d['pattern'].split('~')[0] == d['pattern'].split('~')[1]),
    }


def main(argv):
    ap = argparse.ArgumentParser(description='당일치기(0박) md → master_db.json flights 병합')
    ap.add_argument('md', nargs='+')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note', default='')
    args = ap.parse_args(argv)

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    before = master['flights']['counts']['total']
    total = {'added': 0, 'updated': 0, 'filled': 0, 'skipped': 0, 'gaps': 0}
    for path in args.md:
        deals, gaps = parse_md(path)
        added, updated, filled, skipped = merge(master, deals, gaps)
        print('%s → 파싱 %d건 (미확인 %d건)' % (os.path.basename(path), len(deals), len(gaps)))
        print('  신규 %d · 가격 갱신 %d · 기존 유지 %d · 항목 보강 %d'
              % (len(added), len(updated), len(skipped), len(filled)))
        for a in added:
            print('    + %s %s %s %s원' % a)
        for u in updated:
            print('    ↑ %s %s %s %s원 → %s원' % u)
        for g in gaps:
            print('    - %s %s %s 가격 미표시' % g)
        total['added'] += len(added)
        total['updated'] += len(updated)
        total['filled'] += len(filled)
        total['skipped'] += len(skipped)
        total['gaps'] += len(gaps)

    sync_patterns(master['flights'])
    sync_weeks(master['flights'])
    sync_meta(master['flights'])
    print('총 건수 %d → %d (당일치기 %d건)'
          % (before, master['flights']['counts']['total'], master['flights']['counts']['daytrip']))
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
