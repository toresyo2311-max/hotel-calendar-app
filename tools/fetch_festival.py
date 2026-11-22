#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎉 축제 탭 자료 수집 — 전국 축제 일정을 모아 data/app/tab12_festival.json 을 만든다.

수집 방식(2026-11-22 확인)
  · chukjemoa.co.kr 은 정적 사이트다. 축제 원본은 /search/data.json (882건) 이고
    각 건에 이름·기간·주소·시도/시군구·좌표·전화·사진·소개·공식 홈페이지가 들어 있다.
  · 월별 페이지(/2026-12/ 처럼 /YYYY-MM/)는 카드마다 data-* 속성으로 다음 회차 일정을
    담고 있다. 일정이 확정된 건은 data-conf=1, 예년 시기만 적은 건은 data-conf=0 이다.
  · 상세 페이지(/festival/<slug>/)에는 이용요금·운영시간·주최·행사장·문의가 있다.
    앞으로 열리는 축제만 골라 이 값을 덧붙인다(지난 회차 기준임을 화면에서 밝힌다).
  · 오일장(5일장) 자료(/market-fav.json)는 쓰지 않는다 — 이 탭은 축제만 다룬다(한진님 11-22 지시).

화면 원칙
  · 수집 사이트 이름은 화면에 쓰지 않는다. 링크는 각 축제의 공식 홈페이지와 지도만 연다.
  · 자료에 없는 값은 만들지 않는다. 예년 시기로 적은 일정은 est=1 로 표시한다.

사용
  python3 tools/fetch_festival.py            # 수집 → data/app/tab12_festival.json
  python3 tools/fetch_festival.py --no-detail  # 상세 페이지 보강 생략(빠름)
  python3 tools/fetch_festival.py --quiet    # 요약만 출력
"""
import argparse
import datetime as dt
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

BASE = 'https://chukjemoa.co.kr'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'app', 'tab12_festival.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'

KST = dt.timezone(dt.timedelta(hours=9))
# 자료 범위 — 2026년 축제 전체와 2027년까지 확인된 일정
WIN_START = dt.date(2026, 1, 1)
WIN_END = dt.date(2027, 12, 31)

SIDO_ORDER = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
              '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주']
CAT_ORDER = ['문화', '전통', '음악', '음식', '꽃', '물놀이', '불꽃', '빛', '눈', '기타']


# ── 통신 ──────────────────────────────────────────────────────────────
def http_get(url, tries=3, timeout=40):
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA, 'Accept-Encoding': 'gzip',
                'Accept-Language': 'ko-KR,ko;q=0.9'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
                return raw.decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 403, 404):
                break
        except Exception as e:            # noqa: BLE001 - 네트워크 오류는 재시도
            last = e
        time.sleep(0.6 * (n + 1))
    raise RuntimeError('요청 실패 %s → %s' % (url, last))


def get_json(path):
    txt = http_get(BASE + path)
    return json.loads(txt)


# ── 값 정리 ───────────────────────────────────────────────────────────
def norm_name(s):
    return re.sub(r'\s+', '', s or '')


def base_name(s):
    """같은 축제를 다르게 적은 이름을 맞춰 보기 위한 열쇠 — 연도·회차 표기를 뺀다."""
    t = norm_name(s)
    t = re.sub(r'(?<!\d)(19|20)\d{2}(?!\d)', '', t)
    t = re.sub(r'제?\d+회', '', t)
    t = re.sub(r'[\[\](){}<>·\-_/]+', '', t)
    return t


def ymd(s):
    m = re.fullmatch(r'(\d{4})-?(\d{2})-?(\d{2})', str(s or '').strip())
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def clean(v, limit=None):
    if v is None:
        return ''
    s = re.sub(r'\s+', ' ', str(v)).strip()
    if limit and len(s) > limit:
        s = s[:limit].rstrip() + '…'
    return s


def is_http(u):
    return isinstance(u, str) and re.match(r'^https?://', u.strip())


# ── 월별 페이지 카드 ──────────────────────────────────────────────────
class CardParser(HTMLParser):
    """<div class="card" data-name=...> 하나를 dict 로 뽑는다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self.cur = None
        self.depth = 0
        self.in_h3 = False
        self.buf = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'div' and 'card' in (a.get('class') or '').split() and a.get('data-name'):
            self.cur = dict(a)
            self.depth = 1
            self.text = []
            self.cards.append(self.cur)
            return
        if self.cur is None:
            return
        if tag == 'h3':
            self.in_h3 = True
            self.buf = []
        elif tag == 'div':
            self.depth += 1

    def handle_endtag(self, tag):
        if self.cur is None:
            return
        if tag == 'h3' and self.in_h3:
            self.cur['title'] = ''.join(self.buf).strip()
            self.in_h3 = False
        elif tag == 'div':
            self.depth -= 1
            if self.depth <= 0:
                self.cur['text'] = re.sub(r'\s+', ' ', ''.join(self.text)).strip()
                self.cur = None

    def handle_data(self, data):
        if self.cur is None:
            return
        self.text.append(data)
        if self.in_h3:
            self.buf.append(data)


MONTH_LINK = re.compile(r'^/(\d{4})-(\d{2})/$')


def month_pages(home_html):
    """사이트가 지금 내놓는 월별 페이지 목록(오래된 순)."""
    found = set()
    for m in re.finditer(r'href="(/(\d{4})-(\d{2})/)"', home_html):
        found.add(m.group(2) + '-' + m.group(3))
    return sorted(found)


def page_window(pm):
    """월별 페이지가 다루는 기간 — 12월 페이지는 다음 해 1월까지 함께 본다."""
    y, m = int(pm[:4]), int(pm[5:7])
    if m == 12:
        return dt.date(y, 12, 1), dt.date(y + 1, 1, 31)
    first = dt.date(y, m, 1)
    last_month = dt.date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    return first, last_month - dt.timedelta(days=1)


def cards_for(pm, html):
    p = CardParser()
    p.feed(html)
    out = []
    for c in p.cards:
        s, e = ymd(c.get('data-start')), ymd(c.get('data-end'))
        if not s or not e:
            continue
        out.append({
            'name': clean(c.get('data-name')),
            'start': s, 'end': e,
            'conf': c.get('data-conf') == '1',
            'sido': clean(c.get('data-region')),
            'sigungu': clean(c.get('data-city')),
            'addr': clean(c.get('data-place')),
            'cat': clean(c.get('data-cat')),
            'img': clean(c.get('data-img')),
            'hp': clean(c.get('data-hp')) if is_http(c.get('data-hp')) else '',
            'ov': clean(c.get('data-ov') or c.get('data-desc')),
            'lat': num(c.get('data-lat')), 'lng': num(c.get('data-lng')),
            'page': pm,
        })
    return out


def place_card(c, today):
    """카드 일정을 '앞으로 열리는 회차'로 옮긴다.

    미래 달 페이지는 다음 회차를 미리 적어 둔 것이다. 카드에 작년 날짜가 남아 있으면
    페이지가 다루는 기간과 겹칠 때까지 해를 더한다(예년 시기 → 올해 시기).
    옮길 수 없으면 None.
    """
    win_a, win_b = page_window(c['page'])
    for k in range(0, 4):
        try:
            s = c['start'].replace(year=c['start'].year + k)
            e = c['end'].replace(year=c['end'].year + k)
        except ValueError:               # 2월 29일 등
            continue
        if s <= win_b and e >= win_a and e >= today:
            d = dict(c)
            d['start'], d['end'], d['shift_years'] = s, e, k
            return d
    return None


# ── 상세 페이지 ───────────────────────────────────────────────────────
DL_FIELD = re.compile(r'<dt>\s*([^<]+?)\s*</dt>\s*<dd>(.*?)</dd>', re.S)
TAG = re.compile(r'<[^>]+>')


def fetch_detail(slug):
    html = http_get(BASE + '/festival/' + slug + '/')
    out = {}
    block = re.search(r'<dl class="f(?:info|meta)">(.*?)</dl>', html, re.S)
    if block:
        for k, v in DL_FIELD.findall(block.group(1)):
            k = k.strip()
            v = clean(re.sub(r'\s+', ' ', TAG.sub(' ', v)))
            if k == '이용요금':
                out['fee'] = v
            elif k == '운영시간':
                out['hr'] = v
            elif k == '주최':
                out['org'] = v
            elif k == '행사장':
                out['ven'] = v
            elif k == '문의' and not out.get('tel'):
                out['tel'] = v
    return out


# ── 조립 ──────────────────────────────────────────────────────────────
def build(args):
    now = dt.datetime.now(KST)
    today = now.date()
    stats = {'base': 0, 'cards': 0, 'shifted': 0, 'skipped': 0, 'detail': 0, 'detail_miss': 0}

    home = http_get(BASE + '/')
    data = get_json('/search/data.json')
    if not isinstance(data, list) or len(data) < 100:
        raise RuntimeError('축제 목록을 받지 못했습니다(건수 %s)' % (len(data) if isinstance(data, list) else '?'))
    stats['base'] = len(data)

    items = {}          # (정규화 이름, 시작, 끝) → item

    def put(it):
        key = (norm_name(it['n']), it['s'], it['e'])
        if key not in items:
            items[key] = it

    for x in data:
        s, e = ymd(x.get('start')), ymd(x.get('end'))
        if not s or not e or e < WIN_START or s > WIN_END:
            continue
        put({
            'n': clean(x.get('title')),
            's': s.isoformat(), 'e': e.isoformat(),
            'si': clean(x.get('sido')), 'sg': clean(x.get('sigungu')),
            'ad': clean(x.get('addr')),
            'c': '', 'est': 0,
            'img': clean(x.get('img')) if is_http(x.get('img')) else '',
            'hp': clean(x.get('hp')) if is_http(x.get('hp')) else '',
            'tel': clean(x.get('tel')),
            'y': num(x.get('y')), 'x': num(x.get('x')),
            'ov': clean(x.get('ov'), 600),
            'src': 'db',
        })

    months = month_pages(home)
    if not months:
        months = ['%d-%02d' % (y, m) for y, m in
                  [(2026, m) for m in range(7, 13)] + [(2027, m) for m in range(2, 7)]]
    for pm in months:
        try:
            html = http_get('%s/%s/' % (BASE, pm))
        except RuntimeError:
            continue
        for c in cards_for(pm, html):
            stats['cards'] += 1
            # 과거 달 페이지는 그대로, 앞으로의 달 페이지는 다음 회차로 옮긴다
            if pm >= today.strftime('%Y-%m') and page_window(pm)[1] >= today:
                c2 = place_card(c, today)
                if not c2:
                    stats['skipped'] += 1
                    continue
                if c2['shift_years']:
                    stats['shifted'] += 1
                    # 해를 옮긴 일정은 작년 시기를 옮긴 것일 뿐이라 '확정'으로 적지 않는다
                    c2['conf'] = False
                c = c2
            if c['end'] < WIN_START or c['start'] > WIN_END:
                continue
            it = {
                'n': c['name'], 's': c['start'].isoformat(), 'e': c['end'].isoformat(),
                'si': c['sido'], 'sg': c['sigungu'], 'ad': c['addr'],
                'c': c['cat'], 'est': 0 if c['conf'] else 1,
                'img': c['img'] if is_http(c['img']) else '',
                'hp': c['hp'], 'tel': '',
                'y': c['lat'], 'x': c['lng'],
                'ov': clean(c['ov'], 600),
                'src': 'card',
            }
            if not c['conf']:
                it['note'] = '예년 시기 기준'
            put(it)

    # 같은 이름·겹치는 기간이면 하나로 — 원본(data.json) 쪽 값을 남기고 빈 칸만 채운다
    def same_festival(a, b):
        if not (a['s'] <= b['e'] and b['s'] <= a['e']):       # 기간이 겹쳐야 한다
            return False
        if a['si'] and b['si'] and a['si'] != b['si']:
            return False
        if a['sg'] and b['sg'] and a['sg'] != b['sg']:
            return False
        x, y = base_name(a['n']), base_name(b['n'])
        if not x or not y:
            return False
        if x == y:
            return True
        lo, hi = (x, y) if len(x) <= len(y) else (y, x)
        return len(lo) >= 5 and lo in hi

    merged = []
    for it in sorted(items.values(), key=lambda z: (0 if z['src'] == 'db' else 1, z['s'])):
        hit = None
        for cur in merged:
            if same_festival(cur, it):
                hit = cur
                break
        if hit is None:
            merged.append(it)
            continue
        keep, drop = (it, hit) if (it['src'] == 'db' and hit['src'] != 'db') else (hit, it)
        for k, v in drop.items():
            if v and not keep.get(k):
                keep[k] = v
        if keep is not hit:
            hit.clear()
            hit.update(keep)

    items = merged

    # 앞으로 열리는 축제만 상세 페이지로 보강(요금·시간·주최·행사장·문의)
    if not args.no_detail:
        index = {}
        for row in get_json('/hsearch.json'):
            if isinstance(row, list) and len(row) >= 2 and str(row[1]).startswith('/festival/'):
                index[norm_name(row[0])] = str(row[1]).strip('/').split('/')[-1]
        targets = [it for it in items if ymd(it['e']) >= today]
        targets.sort(key=lambda z: z['s'])
        for n, it in enumerate(targets):
            slug = index.get(norm_name(it['n']))
            if not slug:
                stats['detail_miss'] += 1
                continue
            try:
                det = fetch_detail(slug)
            except RuntimeError:
                stats['detail_miss'] += 1
                continue
            if det:
                stats['detail'] += 1
                for k, v in det.items():
                    if v and not it.get(k):
                        it[k] = v
            if not args.quiet and (n + 1) % 40 == 0:
                print('  상세 %d/%d …' % (n + 1, len(targets)), flush=True)
            time.sleep(0.25)

    # 정렬: 시작일 → 이름
    items.sort(key=lambda z: (z['s'], z['n']))

    # 소개는 지난 축제일수록 짧게 — 파일 크기를 줄이면서 앞으로의 축제 설명은 살린다
    for it in items:
        if it.get('ov') and ymd(it['e']) < today and len(it['ov']) > 180:
            it['ov'] = it['ov'][:180].rstrip() + '…'

    for it in items:
        if it.get('c') and it['c'] not in CAT_ORDER:
            it['c'] = '기타'
        if it.get('note') and it['est'] == 0:
            del it['note']

    by_sido = {}
    for it in items:
        by_sido[it['si']] = by_sido.get(it['si'], 0) + 1
    cats = sorted({it['c'] for it in items if it.get('c')}, key=lambda c: (CAT_ORDER.index(c) if c in CAT_ORDER else 99, c))
    regions = [s for s in SIDO_ORDER if by_sido.get(s)] + sorted(s for s in by_sido if s not in SIDO_ORDER)
    active = [it for it in items if ymd(it['e']) >= today]
    ongoing = [it for it in items if ymd(it['s']) <= today <= ymd(it['e'])]

    payload = {
        'schema': 'festival-tab-v1',
        'generated': now.isoformat(timespec='seconds'),
        'basis': '전국 축제 일정 — 한국관광공사 TourAPI 등록 축제와 주최 측 발표 일정을 모아 정리',
        'window': [WIN_START.isoformat(), WIN_END.isoformat()],
        'counts': {
            'total': len(items), 'live': len(active), 'ongoing': len(ongoing),
            'upcoming': len(active) - len(ongoing), 'past': len(items) - len(active),
            'est': len([it for it in items if it['est']]),
            'by_sido': by_sido,
        },
        'regions': regions,
        'cats': cats,
        'months': ['%04d-%02d' % (y, m) for y in (2026, 2027) for m in range(1, 13)
                   if WIN_START <= dt.date(y, m, 1) <= WIN_END],
        'items': items,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, OUT)

    size = os.path.getsize(OUT)
    print('저장 %s (%.0f KB)' % (os.path.relpath(OUT, ROOT), size / 1024))
    print('  원본 %d건 · 월별 카드 %d건(해 넘김 %d · 제외 %d) · 최종 %d건'
          % (stats['base'], stats['cards'], stats['shifted'], stats['skipped'], len(items)))
    print('  진행 중 %d · 예정 %d · 종료 %d · 예년 기준 %d'
          % (len(ongoing), len(active) - len(ongoing), len(items) - len(active),
             len([it for it in items if it['est']])))
    print('  상세 보강 %d건(못 찾음 %d)' % (stats['detail'], stats['detail_miss']))
    print('  지역 %s' % ', '.join('%s %d' % (s, by_sido[s]) for s in regions[:6]))
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-detail', action='store_true', help='상세 페이지 보강 생략')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    try:
        build(args)
    except Exception as e:               # noqa: BLE001 - 스케줄 실행이 원인을 남기도록
        print('실패: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
