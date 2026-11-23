#!/usr/bin/env python3
"""🧒 체험·예약 — 아이 나이 필터 규칙 프로토타입 (JS 로 옮기기 전 검증용).

DK 2018-05-10 → 2026-11-23 기준 만 8세 · 초등 2학년
JH 2020-07-05 → 2026-11-23 기준 만 6세 · 미취학
학년 눈금: 유아·미취학 0 / 초1~6 = 1~6 / 중1~3 = 7~9 / 고1~3 = 10~12
"""
import json, re, collections, random

TODAY_Y = 2026
DK_AGE, DK_GRADE = 8, 2
JH_AGE, JH_GRADE = 6, 0

def norm(s):
    s = (s or '').lower()
    s = s.replace('～', '~').replace('–', '-').replace('—', '-')
    return re.sub(r'\s+', '', s)

def by(y):
    y = int(y)
    if y >= 1900: return y
    return 1900 + y if y > 26 else 2000 + y

def ages(t):
    out = []
    for m in re.finditer(r'(\d{1,3})[~-](\d{1,3})개월', t):
        out.append((int(m.group(1)) / 12.0, int(m.group(2)) / 12.0))
    for m in re.finditer(r'(\d{1,3})개월', t):
        v = int(m.group(1)) / 12.0; out.append((v, v))
    for m in re.finditer(r'(\d{1,2})세?[~-](\d{1,2})세', t):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= 20 and b <= 20: out.append((min(a, b), max(a, b)))
    for m in re.finditer(r'(\d{1,2})세(이상|이후|부터|이하|까지|미만|초과)', t):
        v, k = int(m.group(1)), m.group(2)
        if v > 20: continue
        if k in ('이상', '이후', '부터'): out.append((v, 99))
        elif k in ('이하', '까지'): out.append((0, v))
        elif k == '미만': out.append((0, max(0, v - 1)))
        else: out.append((v + 1, 99))
    # 낱개 N세 (범위·이상/이하 표현에 안 잡힌 것)
    for m in re.finditer(r'(\d{1,2})세', t):
        v = int(m.group(1))
        if v > 20: continue
        pre = t[max(0, m.start() - 1):m.start()]
        post = t[m.end():m.end() + 1]
        if pre in ('~', '-'): continue
        if post in ('~', '-'): continue
        if re.match(r'(이상|이하|미만|초과|부터|까지)', t[m.end():m.end() + 2]): continue
        out.append((v, v))
    # 5,6,7세 처럼 쉼표로 나열
    for m in re.finditer(r'(\d{1,2})[,、](\d{1,2})[,、](\d{1,2})세', t):
        for g in m.groups(): out.append((int(g), int(g)))
    for m in re.finditer(r'(\d{1,2})[,、](\d{1,2})세', t):
        for g in m.groups(): out.append((int(g), int(g)))
    # 생년
    for m in re.finditer(r"'?((?:19|20)?\d{2})년?[~-]'?((?:19|20)?\d{2})년", t):
        a, b = by(m.group(1)), by(m.group(2))
        if a > b: a, b = b, a
        out.append((TODAY_Y - b, TODAY_Y - a))
    for m in re.finditer(r"'?((?:19|20)?\d{2})[~-]'?((?:19|20)?\d{2})년생", t):
        a, b = by(m.group(1)), by(m.group(2))
        if a > b: a, b = b, a
        out.append((TODAY_Y - b, TODAY_Y - a))
    for m in re.finditer(r'((?:19|20)\d{2})년생', t):
        y = int(m.group(1)); out.append((TODAY_Y - y, TODAY_Y - y))
    for m in re.finditer(r"'?((?:19|20)?\d{2})[,、]'?((?:19|20)?\d{2})년생", t):
        a, b = by(m.group(1)), by(m.group(2))
        out.append((TODAY_Y - max(a, b), TODAY_Y - min(a, b)))
    return out

def grades(t):
    out = []
    P = r'초(?:등)?(?:학교|학생)?'
    for m in re.finditer(P + r'\s*([1-6])\s*(?:학년)?\s*[~-]\s*(?:' + P + r'\s*)?([1-6])\s*(?:학년)?', t):
        a, b = int(m.group(1)), int(m.group(2))
        out.append((min(a, b), max(a, b)))
    for m in re.finditer(P + r'\s*([1-6])\s*학년\s*(이상|이후|부터)', t):
        out.append((int(m.group(1)), 12))
    for m in re.finditer(P + r'\s*([1-6])\s*학년\s*[~-]\s*누구나', t):
        out.append((int(m.group(1)), 12))
    for m in re.finditer(P + r'\s*([1-6])\s*학년', t):
        out.append((int(m.group(1)), int(m.group(1))))
    for m in re.finditer(r'중([1-3])[~-]([1-3])', t):
        out.append((6 + int(m.group(1)), 6 + int(m.group(2))))
    for m in re.finditer(P + r'\s*([1-6])\s*(?:학년)?\s*[~-]\s*중(?:등)?(?:학교|학생)?\s*([1-3])', t):
        out.append((int(m.group(1)), 6 + int(m.group(2))))
    for m in re.finditer(P + r'\s*([1-6])\s*(?:학년)?\s*[~-]\s*고(?:등)?(?:학교|학생)?\s*([1-3])', t):
        out.append((int(m.group(1)), 9 + int(m.group(2))))
    for m in re.finditer(r'중(?:등)?(?:학교|학생)?\s*([1-3])\s*(?:학년)?\s*[~-]\s*고(?:등)?(?:학교|학생)?\s*([1-3])', t):
        out.append((6 + int(m.group(1)), 9 + int(m.group(2))))
    return out

def kw(t):
    """말로 된 대상 → (구간, 종류)"""
    out = []
    if re.search(r'초등', t) and not re.search(r'초등[^0-9]{0,2}\d', t):
        out.append(('elem', (1, 6)))
    if re.search(r'유아|미취학|영유아|어린이집|유치원|취학전', t) and not re.search(r'(?:유아|영유아)[^0-9]{0,2}\d', t):
        out.append(('pre', (0, 0)))
    if re.search(r'어린이(?!집)|아동', t):
        out.append(('child', (0, 6)))
    if '가족' in t:
        out.append(('fam', (0, 12)))
    if re.search(r'제한없|전연령|상관없|무관|모든연령', t) or (re.search(r'누구나', t) and '~누구나' not in t and '-누구나' not in t):
        out.append(('any', (0, 12)))
    if '청소년' in t:
        out.append(('teen', (4, 12)))
    if re.search(r'중학생|중등|중학교', t):
        out.append(('mid', (7, 9)))
    if re.search(r'고등학생|고등학교', t):
        out.append(('high', (10, 12)))
    return out

EXCL = ['사전답사', '답사', '인솔교사', '교직원용', '교원', '교사연수', '학부모교육', '기관(']

def decide(t, title=''):
    for w in EXCL:
        if w in t: return 0, 0, '제외:' + w
    if '단체' in t and '가족' not in t: return 0, 0, '제외:단체'
    if '단체' in title and '가족' not in t and '동반' not in t: return 0, 0, '제외:단체(제목)'
    if re.search(r'(?:최소|최대)\d+인|\d+인(?:이상|부터|~)', t) and '가족' not in t: return 0, 0, '제외:인원'
    A, G, K = ages(t), grades(t), kw(t)
    fromTitle = False
    if not A and not G:
        At, Gt = ages(title), grades(title)
        if At or Gt:
            A, G, fromTitle = At, Gt, True
    if not A and not G and not K: return None, None, '없음'
    dk = jh = False
    for lo, hi in A:
        if lo <= DK_AGE <= hi: dk = True
        if lo <= JH_AGE <= hi: jh = True
    for lo, hi in G:
        if lo <= DK_GRADE <= hi: dk = True
        if lo <= JH_GRADE <= hi: jh = True
    for kind, (lo, hi) in K:
        if kind == 'elem' and G: continue
        if kind == 'child' and (A or G): continue
        if fromTitle and kind in ('elem', 'child', 'fam', 'any'): continue
        if lo <= DK_GRADE <= hi: dk = True
        if lo <= JH_GRADE <= hi: jh = True
    if ('가족' in t or '동반' in t) and (dk or jh):
        dk = jh = True
    return (1 if dk else 0), (1 if jh else 0), ''

def classify(it):
    t = norm(it.get('target'))
    title = norm(it.get('title'))
    dk = jh = None
    if t:
        dk, jh, why = decide(t, title)
    if dk is not None:
        return dk, jh, why
    if t:
        return 0, 0, '대상없음'
    tt = title + ' ' + norm(it.get('cat'))
    dk, jh, why = decide(tt, '')
    if dk is not None:
        return dk, jh, '제목'
    if re.search(r'엄마|아빠|부모|가족|함께|키즈|놀이|어린이|유아|아이', tt):
        return 1, 1, '제목키워드'
    return 1, 1, '기관(어린이)'

def mask(it):
    dk, jh, _ = classify(it)
    return (('DK' if dk else '') + ('JH' if jh else '')) or 'none'

def main():
    d = json.load(open('data/app/tab13_kids.json'))
    items = d['items']
    c = collections.Counter(); per = collections.defaultdict(collections.Counter)
    for it in items:
        m = mask(it); c[m] += 1; per[it['target']][m] += 1
    print(dict(c))
    print('--- per target (top 100) ---')
    for t, cc in sorted(per.items(), key=lambda kv: -sum(kv[1].values()))[:100]:
        print(sum(cc.values()), dict(cc), '|', t)
    print('--- none sample (60) ---')
    for it in random.Random(5).sample([i for i in items if mask(i) == 'none'], 60):
        print('|', (it['target'] or '(빈)')[:45], '||', it['title'][:40])
    print('--- DK sample ---')
    dks = [i for i in items if mask(i) == 'DK']
    for it in random.Random(1).sample(dks, min(20, len(dks))):
        print('|', it['target'][:45], '||', it['title'][:45])
    print('--- JH sample ---')
    jhs = [i for i in items if mask(i) == 'JH']
    for it in random.Random(2).sample(jhs, min(20, len(jhs))):
        print('|', it['target'][:45], '||', it['title'][:45])

if __name__ == '__main__':
    main()
