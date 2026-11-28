#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧒 체험·예약 — 부산 들락날락 참여(dream_dnpa) 1~60쪽 병합기 (2026-11-29)

배경
  2026-11-24~29 셸에서 www.busan.go.kr 이 TCP 타임아웃이라 들락날락 참여 목록은
  브라우저로 1쪽(12건)씩 읽어 왔다. 2026-11-29 04:5x KST 에 5번·6번·7번이 1~60쪽을
  나눠 읽은 TSV 3개(717행)를 받아, 이 계정에서 `build_dnpa` 규칙으로 파싱·병합한다.

입력 (탭 구분 TSV, 머리줄 없음 · 6열)
  href, title, org, applyRaw, target, fullText

  · 717행 가운데 완전히 같은 행 1건(59~60쪽 경계 중복)을 빼고 716행을 쓴다.
  · 같은 href·같은 제목이라도 기관·이용대상·요일·시간이 다른 회차가 있어
    href 만으로는 지우지 않는다(그러면 다른 프로그램이 사라진다).

사용
  python3 tools/merge_dnpa_20261129.py \\
      --tsv <1~20쪽.tsv> --tsv <21~40쪽.tsv> --tsv <41~60쪽.tsv> \\
      --prev data/app/tab13_kids.json --out data/app/tab13_kids.json
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_kids_programs as F                                     # noqa: E402
import fetch_kids_busan_browser as B                                # noqa: E402

SRC = 'dream_dnpa'
SRC_NAME = '부산 들락날락 · 참여 프로그램'


def read_tsvs(paths):
    """여러 TSV 를 이어 붙이며 완전히 같은 행은 한 번만 남긴다."""
    rows, seen, dup = [], set(), []
    for path in paths:
        n = 0
        for line in open(path, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            n += 1
            r = (line.split('\t') + [''] * 6)[:6]
            key = tuple(r)
            if key in seen:
                dup.append((os.path.basename(path), r[1], r[3]))
                continue
            seen.add(key)
            rows.append(r)
        print('  %-34s %4d행' % (os.path.basename(path), n))
    return rows, dup


def dnpa_key(it):
    """같은 제목이라도 기관·이용대상·접수기간이 다르면 다른 회차로 남긴다."""
    return (re.sub(r'\s+', '', it['title']), it.get('org') or '', it.get('target') or '',
            it.get('applyStart') or '', it.get('applyEnd') or '', it.get('time') or '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tsv', dest='tsvs', action='append', required=True)
    ap.add_argument('--prev', default=os.path.join(F.ROOT, 'data', 'app', 'tab13_kids.json'))
    ap.add_argument('--raw-out', default='/workspace/work/kids-dnpa-20261129/dnpa_combined.tsv')
    ap.add_argument('--out', default=os.path.join(F.ROOT, 'data', 'app', 'tab13_kids.json'))
    a = ap.parse_args()

    rows, dup = read_tsvs(a.tsvs)
    print('  합계 %d행 → 완전 중복 %d행 제외 · 고유 %d행' % (len(rows) + len(dup), len(dup), len(rows)))
    for d in dup:
        print('    중복: [%s] %s (%s)' % (d[0], d[1], d[2]))
    os.makedirs(os.path.dirname(a.raw_out), exist_ok=True)
    with open(a.raw_out, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write('\t'.join(r) + '\n')

    _src, _name, built = B.build_dnpa(a.raw_out)
    cut = (F.TODAY - dt.timedelta(days=30)).isoformat()
    fresh, stale = [], []
    for it in built:
        ref = max([x for x in (it.get('end'), it.get('start'), it.get('applyEnd')) if x] or [''])
        (stale if (ref and ref < cut) else fresh).append(it)
    print('\n  파싱 %d건 → 30일 지난 과정 %d건 제외 · 반영 %d건' % (len(built), len(stale), len(fresh)))

    # 회차 기준 중복 제거(완전히 같은 회차가 두 쪽에 걸친 경우)
    seen, uniq = set(), []
    for it in fresh:
        k = dnpa_key(it)
        if k in seen:
            print('    회차 중복 제외: %s (%s ~ %s)' % (it['title'], it['applyStart'], it['applyEnd']))
            continue
        seen.add(k)
        uniq.append(it)

    prev = json.load(open(a.prev, encoding='utf-8'))
    others = [it for it in prev['items'] if it.get('src') != SRC]
    prev_dn = [it for it in prev['items'] if it.get('src') == SRC]

    items = others + uniq
    # id 유일성(같은 제목 회차가 여럿이면 -2, -3 …)
    used, fixed = set(), 0
    for it in items:
        base_id, n = it['id'], 1
        while it['id'] in used:
            n += 1
            it['id'] = '%s-%d' % (base_id, n)
            fixed += 1
        used.add(it['id'])
    items.sort(key=lambda x: (x.get('applyEnd') or x.get('start') or '9999', x['title']))

    meta = dict((m['key'], m) for m in prev['sources'] if m['key'] != SRC)
    meta[SRC] = {
        'key': SRC, 'name': SRC_NAME, 'count': len(uniq), 'pastSkipped': len(stale),
        'ok': True, 'error': None, 'sec': 0, 'via': 'browser',
        'measured': ('1~60쪽 717행(5·6·7번 분담 수집 · %s KST) 중복 1행 제거 후 파싱'
                     % dt.datetime.now(F.KST).strftime('%Y-%m-%d %H:%M')),
        'note': '59~60쪽 경계 중복 1행 제거 · 30일 지난 과정 %d건 제외' % len(stale),
    }
    sources = [meta[k] for k, _n, _f in F.SOURCES if k in meta]

    doc = {
        'tab': 13,
        'name': '어린이 체험·예약',
        'generatedAt': dt.datetime.now(F.KST).isoformat(timespec='seconds'),
        'today': F.TODAY.isoformat(),
        'sources': sources,
        'count': len(items),
        'items': items,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    # ── 검증 ────────────────────────────────────────────────────────────
    chk = json.load(open(a.out, encoding='utf-8'))
    assert chk['count'] == len(chk['items']), 'count 와 items 길이가 다릅니다'
    assert len({it['id'] for it in chk['items']}) == len(chk['items']), 'id 가 겹칩니다'
    fields = set(prev['items'][0].keys())
    bad = [it['id'] for it in chk['items'] if set(it.keys()) != fields]
    assert not bad, '필드 집합이 다른 항목: %s' % bad[:5]
    full = collections.Counter((it['title'], it.get('start'), it.get('end'), it.get('org'),
                                it.get('applyStart'), it.get('applyEnd'), it.get('target'),
                                it.get('time'), it.get('status')) for it in chk['items'])
    assert not [k for k, v in full.items() if v > 1], '같은 내용의 항목이 남아 있습니다'
    dn = [it for it in chk['items'] if it['src'] == SRC]
    assert len({dnpa_key(it) for it in dn}) == len(dn), '들락날락 회차 중복'
    raw = open(a.out, 'rb').read()
    raw.decode('utf-8')
    assert b'\\u' not in raw, 'JSON 에 \\u 이스케이프가 남아 있습니다'

    # ── 보고 ────────────────────────────────────────────────────────────
    pk = {dnpa_key(it) for it in prev_dn}
    nk = {dnpa_key(it) for it in uniq}
    added = [it for it in uniq if dnpa_key(it) not in pk]
    gone = [it for it in prev_dn if dnpa_key(it) not in nk]
    pm = {dnpa_key(it): it for it in prev_dn}
    chg = [(pm[dnpa_key(it)], it) for it in uniq
           if dnpa_key(it) in pm and (pm[dnpa_key(it)].get('status') or '') != (it.get('status') or '')]
    print('\n  들락날락 참여: %d → %d건 (그대로 %d · 새 회차 %d · 빠짐 %d · 상태 변경 %d)'
          % (len(prev_dn), len(uniq), len(prev_dn) - len(gone), len(added), len(gone), len(chg)))
    for it in added:
        print('    + %s | %s | %s ~ %s | %s'
              % (it['title'], it['org'], it['applyStart'], it['applyEnd'], it['status']))
    for it in gone:
        print('    - %s | %s | %s ~ %s | %s'
              % (it['title'], it['org'], it['applyStart'], it['applyEnd'], it['status']))
    for old, new in chg:
        print('    ~ %s : 「%s」 → 「%s」' % (new['title'], old.get('status') or '(빈값)', new.get('status')))
    print('    id 에 -2·-3 을 붙인 항목 %d건(같은 제목 다른 회차)' % fixed)

    per = collections.Counter(it['src'] for it in chk['items'])
    print('\n  전체 %d건 (직전 %d건 %+d)' % (len(chk['items']), len(prev['items']),
                                          len(chk['items']) - len(prev['items'])))
    for k, _n, _f in F.SOURCES:
        print('    %-22s %5d → %5d' % (k, sum(1 for i in prev['items'] if i['src'] == k), per.get(k, 0)))
    print('  상태 분포:', json.dumps(dict(collections.Counter(it.get('status') or '(빈값)' for it in dn)),
                                 ensure_ascii=False))
    print('  검증 OK — count %d · id 유일 · 필드 일치 · 중복 0 · UTF-8' % chk['count'])


if __name__ == '__main__':
    main()
