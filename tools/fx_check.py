#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""①~④ 호텔 538곳 현지 통화 매핑 검증 (2026-11-19).

index.html 의 @@FX-BLOCK@@ 안에 있는 **실제 매핑·환율 코드**를 그대로 읽어서
data/app/tab1~4 의 호텔 538곳에 적용해 본다. (환율 숫자·도시 목록을 여기 복사하지 않는다)

    python3 tools/fx_check.py

검사 항목
  1) 538곳 모두 통화 코드가 정해지는가 — 한국 외 해외 호텔 '통화 미지정' 0건
  2) 국내 호텔은 KRW, 일본 호텔은 JPY (권역과 어긋난 매핑 0건)
  3) KRW 로 잡힌 도시가 실제 국내 도시인가 (해외 도시가 원화로 새는지)
  4) FX_TABLE 통화가 9종 모두 쓰이고, 표본 금액 환산이 역산해도 맞는가
  5) 그랜드 하얏트 후쿠오카 290,000원 → 약 ¥34,69x
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
TABS = [('lux', 'tab1_vip.json'), ('accor', 'tab2_accor.json'),
        ('marriott', 'tab4_marriott.json')]


def fx_source():
    src = open(INDEX, encoding='utf-8').read()
    a = src.index('/* @@FX-BLOCK-START@@')
    b = src.index('/* @@FX-BLOCK-END@@ */')
    return src[a:b]


def read_fx(src):
    """index.html 의 JS 에서 FX_TABLE 과 CCY_CITY 를 그대로 읽는다."""
    table_src = src[src.index('const FX_TABLE={'):src.index('};', src.index('const FX_TABLE={'))]
    table = {}
    for code, body in re.findall(r"(\w{3}):\{([^}]*)\}", table_src):
        krw = float(re.search(r'krw:([\d.]+)', body).group(1))
        sym = re.search(r"sym:'([^']*)'", body).group(1)
        label = re.search(r"label:'([^']*)'", body).group(1)
        unit = re.search(r"unit:'([^']*)'", body).group(1)
        step = int(re.search(r'step:(\d+)', body).group(1))
        table[code] = dict(krw=krw, sym=sym, label=label, unit=unit, step=step)
    city = {}
    for lst, code in re.findall(r"^'([^']+)'\.split\(' '\)\.forEach\(c=>CCY_CITY\[c\]='(\w{3})'\);", src, re.M):
        for c in lst.split(' '):
            city[c] = code
    assign = src[src.index('Object.assign(CCY_CITY,{'):]
    assign = assign[:assign.index('});')]
    for k, v in re.findall(r"([^,{]+):'(\w{3})'", assign):
        city[k.strip()] = v
    return table, city


def currency_of(h, city_map):
    """index.html 의 currencyOf() 와 같은 규칙."""
    city = str(h.get('city') or '').strip()
    region = str(h.get('region') or '').strip()
    if city in city_map:
        return city_map[city]
    if '일본' in region:
        return 'JPY'
    if '한국' in region:
        return 'KRW'
    if '중국' in region:
        return 'CNY'
    if region in city_map:
        return city_map[region]
    if h.get('group') == 'china':
        return 'CNY'
    return None


def decode(o):
    """index.html hcDecode() 와 같은 압축 해제 ($t/$r 표, $d/$v 달력)."""
    if isinstance(o, list):
        return [decode(v) for v in o]
    if isinstance(o, dict):
        if isinstance(o.get('$d'), str) and isinstance(o.get('$v'), list):
            import datetime
            start = datetime.date.fromisoformat(o['$d'])
            return {(start + datetime.timedelta(days=i)).isoformat(): decode(v)
                    for i, v in enumerate(o['$v'])}
        if isinstance(o.get('$t'), list) and isinstance(o.get('$r'), list):
            cols, rows = o['$t'], o['$r']
            out = []
            for row in rows:
                item = {}
                for i, col in enumerate(cols):
                    v = row[i] if i < len(row) else None
                    if v == '$~':
                        continue
                    item[col] = decode(v)
                out.append(item)
            return out
        return {k: decode(v) for k, v in o.items()}
    return o


def main():
    src = fx_source()
    table, city_map = read_fx(src)
    hotels = []
    for tab, file in TABS:
        data = decode(json.load(open(os.path.join(ROOT, 'data', 'app', file), encoding='utf-8')))
        for h in data.get('hotels') or []:
            h.setdefault('group', tab)
            h['group'] = h.get('group') or tab
            hotels.append(h)

    problems, by_ccy, cities_by_ccy, krw_cities = [], {}, {}, set()
    for h in hotels:
        code = currency_of(h, city_map)
        if not code:
            problems.append('통화 미지정 — %s/%s/%s' % (h.get('group'), h.get('city'), h.get('name')))
            continue
        if code not in table and code != 'KRW':
            problems.append('FX_TABLE 에 없는 통화 %s — %s' % (code, h.get('name')))
            continue
        by_ccy.setdefault(code, []).append(h)
        cities_by_ccy.setdefault(code, set()).add(h.get('city'))
        if code == 'KRW':
            krw_cities.add(h.get('city'))
        r = str(h.get('region') or '')
        if '한국' in r and code != 'KRW':
            problems.append('한국 호텔인데 %s — %s' % (code, h.get('name')))
        if '일본' in r and code != 'JPY':
            problems.append('일본 호텔인데 %s — %s' % (code, h.get('name')))

    KR_OK = set('서울 부산 제주 대구 울산 전주 인천 대전 광주 수원 경주'.split(' '))
    for c in sorted(krw_cities):
        if c not in KR_OK:
            problems.append('국내가 아닌 도시가 KRW — %s' % c)

    print('호텔 %d곳 / 통화 %d종' % (len(hotels), len(by_ccy)))
    for code in table:
        lst = by_ccy.get(code, [])
        cs = sorted(cities_by_ccy.get(code, []), key=lambda x: (-sum(1 for h in lst if h.get('city') == x), x))
        print('  %-4s %3d곳  %s%s  (%s)' % (
            code, len(lst), '·'.join(cs[:6]),
            (' 외 %d개 도시' % (len(cs) - 6)) if len(cs) > 6 else '', table[code]['unit']))
    unused = [c for c in table if c not in by_ccy]
    if unused:
        problems.append('쓰이지 않은 통화: %s' % ', '.join(unused))

    def find(city, name):
        return next((h for h in hotels if h.get('city') == city and name in (h.get('name') or '')), None)

    samples = [
        (find('후쿠오카', '그랜드 하얏트'), 290000),
        (find('도쿄', '콘래드'), 420000),
        (find('상하이', '페어몬트'), 240000),
        (find('홍콩', '리츠칼튼'), 250000),
        (find('마카오', '리츠칼튼'), 250000),
        (find('방콕', ''), 300000),
        (find('다낭', ''), 250000),
        (find('싱가포르', '리츠칼튼'), 240000),
        (find('뉴욕', '리츠칼튼'), 290000),
        (find('시드니', ''), 290000),
        (find('서울', '페어몬트'), 290000),
    ]
    print('표본 환산 (KRW → 현지 통화)')

    def fmt(n):
        return format(int(n), ',')

    def convert(krw, code):
        fx = table[code]
        return int(round(krw / fx['krw'] / fx['step']) * fx['step'])

    ok_n = 0
    for h, krw in samples:
        if not h:
            problems.append('표본 호텔을 찾지 못함')
            print('  ✗ 표본 호텔 없음')
            continue
        code = currency_of(h, city_map)
        if code == 'KRW':
            txt, backable = '(국내 · 환산 없음)', True
        else:
            v = convert(krw, code)
            txt = '약 %s%s' % (table[code]['sym'], fmt(v))
            back = v * table[code]['krw']
            backable = abs(back - krw) / krw < 0.002
        ok = backable
        ok_n += ok
        if not ok:
            problems.append('환산값 어긋남 — %s %s → %s' % (h.get('name'), krw, txt))
        print('  %s %s %s: ₩%s → %s' % ('✓' if ok else '✗', h.get('city'), h.get('name'), fmt(krw), txt))

    fk = find('후쿠오카', '그랜드 하얏트')
    if fk:
        y = convert(290000, 'JPY')
        if not (34690 <= y <= 34699):
            problems.append('그랜드 하얏트 후쿠오카 290,000원 엔화 표기가 약 ¥34,69x 가 아님 (%s)' % y)
        print('히어로 줄: 엔화 환산·약 ¥%s · %s · 2026-11-19 기준' % (fmt(y), table['JPY']['unit']))

    print()
    if problems:
        print('✗ 문제 %d건' % len(problems))
        for p in problems:
            print('  -', p)
        return 1
    print('✓ 통화 매핑 누락·오매핑 0건 (%d곳 전수) · 표본 환산 %d/%d 정상' % (len(hotels), ok_n, len(samples)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
