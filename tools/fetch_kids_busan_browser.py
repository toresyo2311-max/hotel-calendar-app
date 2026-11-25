#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧒 체험·예약 — 부산 3호스트(브라우저 경유) 수집분 병합기

배경
  셸(파이썬·curl·Playwright)에서는 reserve.busan.go.kr / 119.busan.go.kr / www.busan.go.kr
  이 모두 210.103.81.224 로 풀리지만 TCP 443·80 이 8~20초 타임아웃이다(2026-11-24~26).
  반면 Pickle 원격 브라우저(exit KR)는 세 호스트 모두 정상 열린다.
  그래서 이 세 출처만 "브라우저로 읽어 TSV 로 남긴 원자료"를 입력으로 받아,
  파싱·상태 판정·중복 제거는 기존 tools/fetch_kids_programs.py 의 규칙을 그대로 재사용한다.

원자료(탭 구분 TSV, 첫 줄 없음)
  reserve_exprn.tsv / reserve_lctre.tsv
      g, p, title, status, org, target, place, applyRaw, eventRaw, method, phone
  dnpa.tsv
      href, title, org, applyRaw, target, fullText
  busan119.tsv
      date, name, hhmm, cap, left

사용
  python3 tools/fetch_kids_busan_browser.py \
      --raw-dir /workspace/work/kids-browser-raw \
      --base /tmp/kids_10.json \
      --out data/app/tab13_kids.json
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_kids_programs as F                                     # noqa: E402

TODAY = F.TODAY


def rows(path, expand=False):
    """TSV 원자료를 읽는다. expand=True 면 '~' 로 시작하는 축약행(앞 행과 같은 상태·기관·대상·신청·행사·문의)을
    앞 행 값으로 펼친다. 축약행 형식: ~, g, p, title, place"""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            r = line.split('\t')
            if expand and r and r[0] == '~':
                prev = out[-1] if out else [''] * 10
                r = [r[1] if len(r) > 1 else '', r[2] if len(r) > 2 else '', r[3] if len(r) > 3 else '',
                     prev[3], prev[4], prev[5], r[4] if len(r) > 4 else '', prev[7], prev[8],
                     r[5] if len(r) > 5 else prev[9]]
            out.append(r)
    return out


def build_reserve(path, kind):
    label = {'exprn': '견학/체험', 'lctre': '강좌/교육'}[kind]
    src = 'busan_reserve_' + kind
    base = 'https://reserve.busan.go.kr'
    items = []
    for r in rows(path, expand=True):
        r = (r + [''] * 11)[:11]
        g, p, title, status, org, target, place, apply_raw, event_raw, method, phone = r
        if not title:
            continue
        e_s, e_e = F.split_range(event_raw)
        it = F.mk(src, '부산광역시 통합예약 · ' + label, title,
                  '%s/%s/view?resveGroupSn=%s&progrmSn=%s' % (base, kind, g, p),
                  kid='%s-%s' % (g, p), cat=label,
                  org=org, target=target, place=place,
                  status=status, region='부산', note=phone)
        if it:
            # 기존 수집기와 같은 규칙: 신청기간은 필드로 넣지 않고 note 에만 원문을 남긴다
            if apply_raw:
                it['note'] = (it.get('note') or '') + (' · ' if it.get('note') else '') + '신청 ' + apply_raw
            it['start'], it['end'] = e_s, e_e
            items.append(it)
    return src, label, items


def build_dnpa(path):
    src = 'dream_dnpa'
    name = '부산 들락날락 · 참여 프로그램'
    items = []
    for r in rows(path):
        r = (r + [''] * 6)[:6]
        href, title, org, apply_raw, target, full = r
        if not title:
            continue
        status = ''
        for cand in ('접수마감', '접수중', '접수예정', '마감'):
            if cand in full:
                status = cand
                break
        a_s = a_e = None
        if '~' in apply_raw:
            p1, p2 = [x.strip() for x in apply_raw.split('~')][:2]
            a_s, a_e = F.md_pair(p1, p2)
            if not a_s:
                a_s, a_e = F.iso_any(p1), F.iso_any(p2)
        it = F.mk(src, name, title, href or 'https://www.busan.go.kr/bschild/dnpa/list.nm?menuCd=9&lang=ko&url=dnpa',
                  cat='들락날락', org=org, target=target,
                  applyStart=a_s, applyEnd=a_e, status=status,
                  region='부산', note='접수기간 원문: ' + apply_raw,
                  dateEstimated=True)
        if it:
            items.append(it)
    return src, name, items


def build_119(path):
    src = 'busan_119'
    name = '부산광역시 119 안전체험관'
    base = 'https://119.busan.go.kr'
    items, seen = [], set()
    cur_date = None
    recs = []
    for r in rows(path):
        if r and r[0].startswith('@'):                 # @YYYY-MM-DD 뒤에는 name·hhmm[·left] 만 써도 된다(정원 20 기본)
            cur_date = r[0][1:].strip()
            continue
        if len(r) >= 5:
            recs.append((r[0], r[1], r[2], r[3], r[4]))
        elif len(r) == 4:
            recs.append((r[0], r[1], r[2], '20', r[3]))
        elif len(r) == 3 and cur_date:
            recs.append((cur_date, r[0], r[1], '20', r[2]))
        elif len(r) == 2 and cur_date:
            recs.append((cur_date, r[0], r[1], '20', '20'))
    for date, course, hhmm, cap, left in recs:
        course = F.clean(course)
        hhmm = F.clean(hhmm)
        if not course or len(hhmm) < 4:
            continue
        key = (date, course, hhmm)
        if key in seen:
            continue
        seen.add(key)
        cap_n = F.num(cap)
        left_n = F.num(left)
        if left_n is not None and left_n < 0:
            left_n = 0
        it = F.mk(src, name, '%s %s' % (course, hhmm[:2] + ':' + hhmm[2:4]),
                  base + '/firesafe/sub0402',
                  kid='%s-%s-%s' % (date, course, hhmm), cat='안전체험',
                  org=name, place='부산119안전체험관',
                  target='새싹안전마을 20~22년생 / 그 외 초등학생 이상',
                  start=date, end=date, time='%s:%s' % (hhmm[:2], hhmm[2:4]),
                  status='예약가능' if (left_n or 0) > 0 else '마감',
                  cap=cap_n, left=left_n, region='부산',
                  note='예약은 본인인증 후 홈페이지에서')
        if it:
            items.append(it)
    return src, name, items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw-dir', required=True)
    ap.add_argument('--base', help='tools/fetch_kids_programs.py --only 로 받은 10개 출처 JSON')
    ap.add_argument('--out', default=os.path.join(F.ROOT, 'data', 'app', 'tab13_kids.json'))
    a = ap.parse_args()

    built = [build_reserve(os.path.join(a.raw_dir, 'reserve_exprn.tsv'), 'exprn'),
             build_reserve(os.path.join(a.raw_dir, 'reserve_lctre.tsv'), 'lctre'),
             build_119(os.path.join(a.raw_dir, 'busan119.tsv')),
             build_dnpa(os.path.join(a.raw_dir, 'dnpa.tsv'))]

    items, meta = [], []
    for key, name, got in built:
        stale, fresh = 0, []
        for it in got:
            ref = max([x for x in (it.get('end'), it.get('start'), it.get('applyEnd')) if x] or [''])
            if ref and ref < (TODAY - dt.timedelta(days=30)).isoformat():
                stale += 1
                continue
            fresh.append(it)
        items.extend(fresh)
        meta.append({'key': key, 'name': name, 'count': len(fresh), 'pastSkipped': stale,
                     'ok': None, 'error': None, 'sec': 0, 'via': 'browser'})
        print('%-24s %5d건 (지난 과정 %d건 제외)  via=browser' % (key, len(fresh), stale))

    base_items = []
    if a.base:
        prev = json.load(open(a.base, encoding='utf-8'))
        base_items = prev.get('items') or []
        for m in prev.get('sources') or []:
            m = dict(m)
            m.pop('via', None)
            meta.append(m)
        print('기준 10개 출처 %d건 합침' % len(base_items))
    items = base_items + items

    # 출처 순서는 fetch_kids_programs.SOURCES 순서를 따른다
    order = {k: i for i, (k, _n, _f) in enumerate(F.SOURCES)}
    meta_order, seen_keys = [], set()
    for m in sorted(meta, key=lambda x: order.get(x.get('key'), 99)):
        if m.get('key') in seen_keys:
            continue
        seen_keys.add(m.get('key'))
        meta_order.append(m)
    meta = meta_order

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
        'today': TODAY.isoformat(),
        'sources': meta,
        'count': len(uniq),
        'items': uniq,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print('\n합계 %d건 (중복 제거 후) → %s' % (len(uniq), a.out))
    st = {}
    for it in uniq:
        st[it.get('status') or '(빈값)'] = st.get(it.get('status') or '(빈값)', 0) + 1
    print('상태 분포:', json.dumps(st, ensure_ascii=False))


if __name__ == '__main__':
    main()
