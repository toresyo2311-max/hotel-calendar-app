#!/usr/bin/env python3
"""🧒 인기·추천 점수 + 프로그램 묶음 프로토타입 (JS 이식 전 검증)."""
import json, re, collections, random
import importlib.util, sys
spec = importlib.util.spec_from_file_location('p', 'tools/kids_age_proto.py')
P = importlib.util.module_from_spec(spec); sys.modules['p'] = P; spec.loader.exec_module(P)

TODAY = '2026-11-23'
SRC_POP = {
    'busan_119': 40, 'pen_yeyak': 34, 'sciport': 32, 'jobworld': 30, 'incheon_child': 26,
    'dream_teach': 26, 'dream_dnpa': 24, 'seoul_yeyak': 18, 'busan_reserve_exprn': 14,
    'yeonje_happy': 12, 'busan_reserve_lctre': 10, 'pen_bellib_edu': 8, 'gangseo_lib': 8,
    'daegu_yeyak': 8,
}
OPEN = {'예약가능', '접수중', '신청가능', '전화접수', '대기접수', '대기중'}
SOON = {'예정', '접수준비', '접수대기중', '신청대기', '안내중', '안내'}

def cls(it):
    s = it['status'] or ''
    if s in OPEN: return 'open'
    if s in SOON: return 'soon'
    if s: return 'closed'
    if it['applyEnd'] and it['applyEnd'] < TODAY: return 'closed'
    if it['applyStart'] and it['applyStart'] > TODAY: return 'soon'
    return 'open'

def days_until(d):
    from datetime import date
    y, m, dd = map(int, d.split('-'))
    return (date(y, m, dd) - date(2026, 11, 23)).days

BAD = ['사전답사', '교직원', '인솔교사', '학급단체', '유의사항', '연간일정', '안내문', '수강시']

def score(it):
    s = SRC_POP.get(it['src'], 5)
    c = cls(it)
    s += {'open': 30, 'soon': 6, 'closed': -40}[c]
    # 잔여석 경쟁
    L, C = it['left'], it['cap']
    if L is not None:
        if L == 0: s -= 20
        else:
            if C:
                r = L / C
                if r <= 0.10: s += 16
                elif r <= 0.25: s += 12
                elif r <= 0.50: s += 6
            if L <= 5: s += 10
    if it['fee'] == '무료': s += 5
    mask = P.mask(it)
    if mask == 'DKJH': s += 6
    t = it['target'] or ''
    if t and '제한없음' not in t: s += 4
    if it['start']:
        d = days_until(it['start'])
        if d <= 7: s += 10
        elif d <= 30: s += 6
        elif d <= 60: s += 3
    else:
        s += 2
    if it['region'] == '부산': s += 8
    if it['cat'] and '키즈카페' in it['cat']: s += 8
    tt = (it['title'] or '') + (it['target'] or '')
    for w in BAD:
        if w in tt: s -= 60
    return s

def gkey(it):
    return it['src'] + '|' + re.sub(r'\s*\d{1,2}:\d{2}.*$', '', it['title'] or '').strip()

def groups(items):
    g = collections.OrderedDict()
    for it in items:
        k = gkey(it)
        it['_pop'] = score(it)
        if k not in g: g[k] = []
        g[k].append(it)
    out = []
    for k, xs in g.items():
        xs.sort(key=lambda x: (-x['_pop'], x['start'] or '9999'))
        best = xs[0]
        sc = best['_pop'] + min(8, len(xs) * 0.5)
        out.append(dict(key=k, best=best, n=len(xs), score=sc))
    out.sort(key=lambda x: -x['score'])
    return out

def main():
    d = json.load(open('data/app/tab13_kids.json'))
    items = d['items']
    for m in ('DKJH', 'DK', 'JH'):
        xs = [i for i in items if P.mask(i) == m and cls(i) == 'open']
        gs = groups(xs)
        print('=== %s open %d건 · 프로그램 %d개' % (m, len(xs), len(gs)))
        for g in gs[:14]:
            b = g['best']
            print('%.1f | %s | %s | left %s/%s | fee %s | n=%d | %s' % (
                g['score'], b['src'], b['title'][:46], b['left'], b['cap'], b['fee'] or '-', g['n'], b['start']))
    # 분포
    allg = groups([i for i in items if cls(i) == 'open'])
    print('open programs:', len(allg))
    print('score>=60:', sum(1 for g in allg if g['score'] >= 60))

if __name__ == '__main__':
    main()
