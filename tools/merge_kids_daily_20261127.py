#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧒 체험·예약 — 2026-11-27 일일 재수집 병합기

tools/fetch_kids_programs.py 를 세 번에 나눠 돌린 결과를 14개 출처 순서대로 합쳐
data/app/tab13_kids.json 을 만든다.

  ① 부산 3호스트(reserve.busan.go.kr · 119.busan.go.kr · www.busan.go.kr/bschild/dnpa)와
     들락날락 행사·강좌        → kids_batchA.json   (2026-11-27 셸에서 정상 수집)
  ② 교육청 · 도서관 · 과학관 등 → kids_batch1.json
  ③ 서울 · 연제 · 잡월드 · 대구 · 인천 → kids_batch2.json

2026-11-24~26 에는 부산 3호스트가 셸에서 TCP 타임아웃(또는 401 차단)이라
브라우저로 읽은 TSV 를 tools/fetch_kids_busan_browser.py 로 병합했지만,
2026-11-27 04:0x KST 에는 브라우저 UA 로 셸에서 세 호스트 모두 HTTP 200 이 열려
기존 수집기 그대로 전량 수집했다(부분 수집·이월 없음).

사용
  python3 tools/merge_kids_daily_20261127.py \
      --in /workspace/tmp/kids_batchA.json --in /workspace/tmp/kids_batch1.json \
      --in /workspace/tmp/kids_batch2.json --prev <직전 tab13_kids.json>
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_kids_programs as F                                     # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='ins', action='append', required=True)
    ap.add_argument('--prev', help='직전 배포본(변동 계산용)')
    ap.add_argument('--out', default=os.path.join(F.ROOT, 'data', 'app', 'tab13_kids.json'))
    a = ap.parse_args()

    items, meta = [], {}
    for path in a.ins:
        doc = json.load(open(path, encoding='utf-8'))
        items.extend(doc.get('items') or [])
        for m in doc.get('sources') or []:
            meta[m['key']] = m
        print('%-46s %5d건' % (os.path.basename(path), len(doc.get('items') or [])))

    order = [k for k, _n, _f in F.SOURCES]
    sources = [meta[k] for k in order if k in meta]
    missing = [k for k in order if k not in meta]
    if missing:
        print('!! 수집되지 않은 출처:', missing)

    # fetch_kids_programs.py 와 같은 규칙으로 중복 제거 · id 유일성
    seen, uniq = set(), []
    for it in items:
        k = (re.sub(r'\s+', '', it['title']), it.get('start') or '', it.get('org') or '')
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    used = set()
    for it in uniq:
        base_id, n = it['id'], 1
        while it['id'] in used:
            n += 1
            it['id'] = '%s-%d' % (base_id, n)
        used.add(it['id'])
    uniq.sort(key=lambda x: (x.get('applyEnd') or x.get('start') or '9999', x['title']))

    doc = {
        'tab': 13,
        'name': '어린이 체험·예약',
        'generatedAt': dt.datetime.now(F.KST).isoformat(timespec='seconds'),
        'today': F.TODAY.isoformat(),
        'sources': sources,
        'count': len(uniq),
        'items': uniq,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    st = {}
    for it in uniq:
        st[it.get('status') or '(빈값)'] = st.get(it.get('status') or '(빈값)', 0) + 1
    print('\n합계 %d건 → %s' % (len(uniq), a.out))
    print('출처별:', json.dumps({m['key']: m['count'] for m in sources}, ensure_ascii=False))
    print('상태 분포:', json.dumps(st, ensure_ascii=False))

    if a.prev and os.path.exists(a.prev):
        prev = json.load(open(a.prev, encoding='utf-8'))
        pv = {it['id']: it for it in prev['items']}
        nv = {it['id']: it for it in uniq}
        added = [nv[k] for k in nv if k not in pv]
        gone = [pv[k] for k in pv if k not in nv]
        chg = [k for k in nv if k in pv and nv[k].get('status') != pv[k].get('status')]
        print('\n전일 대비: %d → %d건 (신규 %d · 빠짐 %d · 상태 변경 %d)'
              % (len(pv), len(nv), len(added), len(gone), len(chg)))
        for it in added[:40]:
            print('  + [%s] %s (%s ~ %s)' % (it['src'], it['title'], it.get('start'), it.get('end')))
        for it in gone[:40]:
            print('  - [%s] %s (%s ~ %s)' % (it['src'], it['title'], it.get('start'), it.get('end')))
        per = {}
        for it in prev['items']:
            per.setdefault(it['src'], [0, 0])[0] += 1
        for it in uniq:
            per.setdefault(it['src'], [0, 0])[1] += 1
        print('\n출처별 전일→오늘:')
        for k in order:
            if k in per:
                print('  %-22s %5d → %5d (%+d)' % (k, per[k][0], per[k][1], per[k][1] - per[k][0]))


if __name__ == '__main__':
    main()
