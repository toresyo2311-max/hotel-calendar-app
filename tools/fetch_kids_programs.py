#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧒 어린이 체험·예약 수집기 — '육' 폴더 41개 사이트 중 비로그인으로 수집되는 곳을 모아
data/app/tab13_kids.json 을 만든다.

수집 원칙
  · 실제 응답에서 확인된 항목만 담는다. 값이 없으면 빈칸(null)으로 두고 만들지 않는다.
  · 각 항목에는 출처(src)·원문 제목·원문 상태 문구·상세 URL을 함께 남긴다.
  · 날짜에 연도가 없는 출처(예: 들락날락 참여 목록)는 연도를 추정해 채우되
    dateEstimated=true 로 표시한다.
  · 사이트가 개편·차단으로 수집이 안 되면 그 사실을 sources[].error 에 남기고
    나머지 출처 수집은 계속한다.

사용
  python3 tools/fetch_kids_programs.py                 # 전체 수집 → data/app/tab13_kids.json
  python3 tools/fetch_kids_programs.py --only busan_119
  python3 tools/fetch_kids_programs.py --out /tmp/kids.json --quiet
  python3 tools/fetch_kids_programs.py --list          # 수집기 목록만
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
import zlib
from html import unescape

from lxml import html as LH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
OUT_DEFAULT = os.path.join(ROOT, 'data', 'app', 'tab13_kids.json')
KST = dt.timezone(dt.timedelta(hours=9))
TODAY = dt.datetime.now(KST).date()

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


# ── 통신 ──────────────────────────────────────────────────────────────
class Fetcher:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=CTX))
        self.calls = 0

    def _open(self, url, data=None, headers=None, timeout=45):
        h = {'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9',
             'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
             'Accept-Encoding': 'gzip, deflate'}
        if data is not None:
            h['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            h['X-Requested-With'] = 'XMLHttpRequest'
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, headers=h)
        with self.op.open(req, timeout=timeout) as r:
            raw = r.read()
            enc = (r.headers.get('Content-Encoding') or '').lower()
            if 'gzip' in enc:
                raw = gzip.decompress(raw)
            elif 'deflate' in enc:
                try:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                except Exception:                        # noqa: BLE001
                    pass
            ctype = r.headers.get('Content-Type') or ''
            m = re.search(r'charset=([\w-]+)', ctype, re.I)
            cs = m.group(1) if m else ''
            for c in filter(None, [cs, 'utf-8', 'euc-kr']):
                try:
                    return raw.decode(c)
                except Exception:                        # noqa: BLE001
                    continue
            return raw.decode('utf-8', 'replace')

    def get(self, url, headers=None, tries=3):
        last = None
        for n in range(tries):
            try:
                self.calls += 1
                return self._open(url, None, headers)
            except Exception as e:                       # noqa: BLE001
                last = e
                time.sleep(0.7 * (n + 1))
        raise RuntimeError('GET 실패 %s → %s' % (url, last))

    def post(self, url, data, headers=None, tries=3):
        body = urllib.parse.urlencode(data).encode()
        last = None
        for n in range(tries):
            try:
                self.calls += 1
                return self._open(url, body, headers)
            except Exception as e:                       # noqa: BLE001
                last = e
                time.sleep(0.7 * (n + 1))
        raise RuntimeError('POST 실패 %s → %s' % (url, last))


FETCH = Fetcher()


# ── 값 정리 ───────────────────────────────────────────────────────────
def clean(v):
    if v is None:
        return ''
    s = str(v).replace('\xa0', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def txt(el):
    return clean(el.text_content()) if el is not None else ''


def iso(s, year=None):
    """'2026-12-05', '2026.12.05', '2026.12.05 14:00' → 'YYYY-MM-DD'"""
    if not s:
        return None
    m = re.search(r'(20\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})', str(s))
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def iso_any(s):
    """'04월 01일' 처럼 연도가 없는 표기는 오늘 기준으로 연도를 정한다(추정 표시용)."""
    if not s:
        return None
    m = re.fullmatch(r'\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*', str(s))
    if not m:
        return iso(s)
    mo, d = int(m.group(1)), int(m.group(2))
    for y in (TODAY.year, TODAY.year + 1):
        try:
            cand = dt.date(y, mo, d)
        except ValueError:
            continue
        if (cand - TODAY).days > -200:
            return cand.isoformat()
    return None


def split_range(s):
    """'2026-11-22 ~ 2026-12-03' → (start, end). ISO 날짜의 '-'는 구분자로 쓰지 않는다."""
    if not s:
        return None, None
    s = str(s)
    parts = re.split(r'\s*(?:~|～|부터|까지)\s*', s)
    if len(parts) < 2:
        parts = re.split(r'\s+-\s+', s)
    if len(parts) == 2 and iso(parts[0]) and iso(parts[1]):
        return iso(parts[0]), iso(parts[1])
    one = iso(s)
    return (one, one) if one else (None, None)


def md_pair(p1, p2):
    """'04월 01일', '11월 30일' → 연도를 맞춰 (start, end). 연도는 오늘과 가장 가까운 해로 맞춘다."""
    def md(s):
        m = re.search(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', str(s))
        return (int(m.group(1)), int(m.group(2))) if m else None
    a, b = md(p1), md(p2)
    if not a or not b:
        return None, None
    best = None
    for y in (TODAY.year - 1, TODAY.year, TODAY.year + 1):
        try:
            s = dt.date(y, a[0], a[1])
            e = dt.date(y, b[0], b[1])
        except ValueError:
            continue
        if e < s:
            try:
                e = dt.date(y + 1, b[0], b[1])
            except ValueError:
                continue
        dist = abs((e - TODAY).days)
        if best is None or dist < best[0]:
            best = (dist, s, e)
    if not best:
        return None, None
    return best[1].isoformat(), best[2].isoformat()


def num(v):
    m = re.search(r'-?\d+', str(v or ''))
    return int(m.group(0)) if m else None


def mk(src, srcname, title, url, **kw):
    title = clean(unescape(title))     # 원문 title 속성에 &lt; &middot; 처럼 남은 실체 참조를 글자로 되돌린다
    if not title:
        return None
    it = {
        'id': '%s:%s' % (src, kw.pop('kid', re.sub(r'\W+', '', title)[:40] + str(kw.get('start') or ''))),
        'src': src, 'srcName': srcname, 'title': title, 'url': url,
        'cat': kw.pop('cat', ''), 'org': kw.pop('org', srcname),
        'target': kw.pop('target', ''), 'place': kw.pop('place', ''),
        'applyStart': kw.pop('applyStart', None), 'applyEnd': kw.pop('applyEnd', None),
        'start': kw.pop('start', None), 'end': kw.pop('end', None),
        'time': kw.pop('time', ''), 'status': kw.pop('status', ''),
        'cap': kw.pop('cap', None), 'applied': kw.pop('applied', None),
        'left': kw.pop('left', None), 'fee': kw.pop('fee', ''),
        'region': kw.pop('region', ''), 'note': kw.pop('note', ''),
        'dateEstimated': kw.pop('dateEstimated', False),
    }
    it.update(kw)
    return it


# ── 1. 부산광역시 통합예약 (견학/체험 · 강좌/교육) ─────────────────────
def busan_reserve(kind):
    """kind='exprn'(견학/체험) | 'lctre'(강좌/교육). 서버가 목록 HTML을 그대로 그려 준다."""
    base = 'https://reserve.busan.go.kr'
    label = {'exprn': '견학/체험', 'lctre': '강좌/교육'}[kind]
    src = 'busan_reserve_' + kind
    out = []
    last = 1
    past_streak = 0
    for page in range(1, 121):
        url = '%s/%s/list?curPage=%d' % (base, kind, page)
        h = FETCH.get(url)
        if page == 1:
            nums = [int(n) for n in re.findall(r'curPage=(\d+)', h)]
            last = max(nums) if nums else 1
        doc = LH.fromstring(h)
        nodes = doc.xpath('//a[contains(@class,"reserveItem")]')
        if not nodes:
            break
        for a in nodes:
            oc = a.get('onclick') or ''
            m = re.search(r"fn_viewProgrm\('(\d+)','(\d+)'\)", oc)
            g, p = (m.group(1), m.group(2)) if m else ('', '')
            title = ''
            t = a.xpath('.//p[contains(@class,"tit")]')
            if t:
                title = t[0].get('title') or txt(t[0])
            status = txt(a.xpath('.//span[contains(@class,"statusMark")]')[0]) \
                if a.xpath('.//span[contains(@class,"statusMark")]') else ''
            dts = [txt(x) for x in a.xpath('.//dt')]
            dds = [txt(x) for x in a.xpath('.//dd')]
            d = dict(zip(dts, dds))
            dates = [txt(x) for x in a.xpath('.//dd[@class="date"]//span')]
            a_s = a_e = e_s = e_e = None
            for s in dates:
                if '[행사]' in s:
                    e_s, e_e = split_range(s.replace('[행사]', '').strip())
            detail = '%s/%s/view?resveGroupSn=%s&progrmSn=%s' % (base, kind, g, p)
            it = mk(src, '부산광역시 통합예약 · ' + label, title, detail,
                    kid='%s-%s' % (g, p), cat=label,
                    org=d.get('기관', ''), target=d.get('대상', ''), place=d.get('장소', ''),
                    applyStart=a_s, applyEnd=a_e, start=e_s, end=e_e,
                    status=status, region='부산', note=d.get('문의', ''))
            if it:
                out.append(it)
                # 이미 끝난 과정이 두 페이지 연속이면 그 뒤는 지난 목록으로 보고 멈춘다
                if (it.get('end') or it.get('start') or '9999') < (TODAY - dt.timedelta(days=30)).isoformat():
                    past_streak += 1
        if nodes and past_streak >= len(nodes) * 2:
            break
        if page >= last:
            break
        time.sleep(0.2)
    return out


def src_busan_reserve_exprn():
    return busan_reserve('exprn')


def src_busan_reserve_lctre():
    return busan_reserve('lctre')


# ── 2. 부산 119 안전체험관 (JSON: 날짜별 과정·잔여석) ──────────────────
def src_busan_119():
    base = 'https://119.busan.go.kr'
    days = json.loads(FETCH.post(base + '/fnct/new_safe119/dayList', {},
                                 headers={'Referer': base + '/firesafe/sub0402'}))
    out = []
    seen = set()
    for d in days.get('result', {}).get('data', []):
        date = d.get('_date')
        if not date or d.get('block_yn') == 'Y':
            continue
        if not (TODAY.isoformat() <= date <= (TODAY + dt.timedelta(days=30)).isoformat()):
            continue
        r = json.loads(FETCH.post(base + '/fnct/new_safe119/reserveCourseList',
                                  {'reserv_date': date},
                                  headers={'Referer': base + '/firesafe/sub0402'}))
        for c in r.get('result', {}).get('data', []):
            name = clean(c.get('course_name'))
            hhmm = clean(c.get('course_reserv_time'))
            if not name or not hhmm or len(hhmm) < 4:
                continue
            key = (date, name, hhmm)
            if key in seen:
                continue
            seen.add(key)
            cap = num(c.get('course_reserv_people'))
            left = num(c.get('reserv_people'))
            if left is not None and left < 0:
                left = 0
            out.append(mk('busan_119', '부산광역시 119 안전체험관',
                          '%s %s' % (name, hhmm[:2] + ':' + hhmm[2:4]),
                          base + '/firesafe/sub0402',
                          kid='%s-%s-%s' % (date, name, hhmm), cat='안전체험',
                          org='부산광역시 119 안전체험관', place='부산119안전체험관',
                          target='새싹안전마을 20~22년생 / 그 외 초등학생 이상',
                          start=date, end=date, time='%s:%s' % (hhmm[:2], hhmm[2:4]),
                          status='예약가능' if (left or 0) > 0 else '마감',
                          cap=cap, left=left, region='부산',
                          note='예약은 본인인증 후 홈페이지에서'))
        time.sleep(0.15)
    return out


# ── 3. 들락날락 '참여' 프로그램 (부산시) ──────────────────────────────
def src_dream_dnpa():
    base = 'https://www.busan.go.kr/bschild/dnpa/list.nm?menuCd=9&lang=ko&url=dnpa'
    out, last = [], 1
    for page in range(1, 81):
        h = FETCH.get('%s&pageIndex=%d' % (base, page))
        doc = LH.fromstring(h)
        if page == 1:
            nums = [int(n) for n in re.findall(r'fn_page\((\d+)\)', h)]
            last = max(nums) if nums else 1
        lis = doc.xpath('//div[contains(@class,"photo_info_type")]//li')
        if not lis:
            break
        for li in lis:
            a = li.xpath('.//a')
            if not a:
                continue
            href = a[0].get('href') or base
            title = txt(li.xpath('.//div[contains(@class,"title_txt")][1]')[0]) \
                if li.xpath('.//div[contains(@class,"title_txt")]') else ''
            org = txt(li.xpath('.//div[contains(@class,"cate_txt")][1]')[0]) \
                if li.xpath('.//div[contains(@class,"cate_txt")]') else ''
            spans = [clean(' '.join(x.itertext())) for x in li.xpath('.//span')]
            apply_raw = target = ''
            for i, s in enumerate(spans):
                if s.startswith('접수기간'):
                    apply_raw = spans[i + 1] if i + 1 < len(spans) else ''
                elif s.startswith('이용대상'):
                    target = spans[i + 1] if i + 1 < len(spans) else ''
            status = ''
            for cand in ('접수마감', '접수중', '접수예정', '마감'):
                if cand in clean(li.text_content()):
                    status = cand
                    break
            a_s = a_e = None
            if '~' in apply_raw:
                p1, p2 = [x.strip() for x in apply_raw.split('~')][:2]
                a_s, a_e = md_pair(p1, p2) or (iso_any(p1), iso_any(p2))
            it = mk('dream_dnpa', '부산 들락날락 · 참여 프로그램', title, href,
                    cat='들락날락', org=org, target=target,
                    applyStart=a_s, applyEnd=a_e, status=status,
                    region='부산', note='접수기간 원문: ' + apply_raw,
                    dateEstimated=True)
            if it:
                out.append(it)
        if page >= last:
            break
        time.sleep(0.15)
    return out


# ── 4. 부산시청 열린도서관(들락날락) 행사·강좌 ────────────────────────
def src_dream_teach():
    url = ('https://library.busan.go.kr/openlib/module/teach/index.do'
           '?menu_idx=80&searchCate1=17')
    h = FETCH.get(url)
    doc = LH.fromstring(h)
    out = []
    for tr in doc.xpath('//tbody[@id="teach_list"]/tr'):
        a = tr.xpath('.//a[contains(@class,"detail-btn")]')
        if not a:
            continue
        title = txt(a[0])
        kv = [a[0].get('data-keyvalue%d' % i) for i in range(1, 6)]
        detail = ('https://library.busan.go.kr/openlib/module/teach/detail.do'
                  '?editMode=ADD&homepage_id=%s&group_idx=%s&category_idx=%s'
                  '&teach_idx=%s&large_category_idx=%s&menu_idx=80' % tuple(kv))
        cat = txt(tr.xpath('.//td[contains(@class,"list_cate_group")]')[0]) \
            if tr.xpath('.//td[contains(@class,"list_cate_group")]') else ''
        dds = [txt(x) for x in tr.xpath('.//dd[contains(@class,"con")]')]
        place = target = ''
        for d in dds:
            if d.startswith('장소'):
                place = clean(d.split(':', 1)[-1])
            elif d.startswith('대상'):
                target = clean(d.split(':', 1)[-1])
        app = tr.xpath('.//span[contains(@class,"app_p")]')
        applied = num(txt(app[0])) if app else None
        cap = None
        span_txt = txt(tr.xpath('.//td[contains(@class,"visit")]')[0]) \
            if tr.xpath('.//td[contains(@class,"visit")]') else ''
        m = re.search(r'/\s*(\d+)', span_txt)
        if m:
            cap = int(m.group(1))
        tds = tr.xpath('./td')
        ev = ap = ''
        for td in tds:
            t = txt(td)
            if re.search(r'20\d{2}-\d{2}-\d{2}', t):
                if not ev:
                    ev = t
                elif not ap:
                    ap = t
        e_s, e_e = split_range(re.sub(r'\([^)]*\)', ' ', ev))
        a_s, a_e = split_range(re.sub(r'\([^)]*\)', ' ', ap))
        st = ''
        for cand in ('정원마감', '접수마감', '신청완료', '신청대기', '접수중', '수강종료'):
            if cand in clean(tr.text_content()):
                st = cand
                break
        it = mk('dream_teach', '부산 들락날락 · 행사·강좌', title, detail,
                kid='-'.join(kv), cat=cat, org='부산시청 열린도서관(들락날락)',
                target=target, place=place, applyStart=a_s, applyEnd=a_e,
                start=e_s, end=e_e, status=st, cap=cap, applied=applied,
                left=(cap - applied) if (cap is not None and applied is not None) else None,
                region='부산')
        if it:
            out.append(it)
    return out


# ── 5. 서울특별시 공공서비스예약 · 문화체험(T200) 7갈래 ──────────────
# 문화체험(T200) 아래 갈래 가운데 어린이 체험과 겹치는 7갈래를 모두 모은다.
# (T202 단체봉사는 어린이 체험과 성격이 달라 뺀다. 갈래 이름은 사이트 표기 그대로다.)
SEOUL_YEYAK_DCODES = (
    ('T203', '전시/관람'),
    ('T204', '문화행사'),
    ('T205', '교육체험'),
    ('T206', '농장체험'),
    ('T207', '공원탐방'),
    ('T208', '서울형키즈카페'),
    ('T209', '산림여가'),
)


def seoul_yeyak_dcode(code, sub):
    """dCode 한 갈래를 끝 페이지까지 넘기며 카드를 읽는다.
    외부사이트로 넘기는 항목은 fnDetailPage 없이 fnNewPop(외부 주소)로만 열리므로
    제목은 h4.tit1, 상세는 그 외부 주소를 그대로 쓴다."""
    base = ('https://yeyak.seoul.go.kr/web/search/selectPageListDetailSearchImg.do'
            '?code=T200&dCode=' + code)
    name = '서울특별시 공공서비스예약 · ' + sub
    out, last = [], 1
    for page in range(1, 81):          # 교육체험(T205)이 50쪽까지 있다
        h = FETCH.get('%s&currentPage=%d' % (base, page))
        doc = LH.fromstring(h)
        if page == 1:
            nums = [int(n) for n in re.findall(r"fnGoPage\('(\d+)'\)", h)]
            last = max(nums) if nums else 1
        lis = doc.xpath('//ul[contains(@class,"img_board")]/li')
        if not lis:
            break
        for li in lis:
            a = li.xpath('.//a[contains(@onclick,"fnDetailPage")]')
            if a:
                title = a[0].get('title') or txt(a[0])
                m = re.search(r"fnDetailPage\('([^']+)'", a[0].get('onclick') or '')
                sid = m.group(1) if m else ''
                detail = ('https://yeyak.seoul.go.kr/web/reservation/selectReservView.do'
                          '?rsv_svc_id=' + sid)
                kid = sid
            else:
                pops = (li.xpath('.//a/@onclick[contains(.,"fnNewPop")]')
                        or li.xpath('.//*[contains(@class,"txt_more")]/@onclick'))
                m = re.search(r"(?:fnNewPop\('|location\.href=')([^']+)",
                              pops[0] if pops else '')
                if not m:
                    continue                       # 상세로 갈 길이 없는 카드
                detail = m.group(1).strip()
                h4 = li.xpath('.//h4[contains(@class,"tit1")]')
                title = txt(h4[0]) if h4 else ''
                kid = 'ext-' + hashlib.md5(detail.encode('utf-8')).hexdigest()[:12]
            labels = [txt(x) for x in li.xpath('.//span[contains(@class,"bd_label")]')]
            status = labels[0] if labels else ''
            fee = labels[1] if len(labels) > 1 else ''
            cats = [txt(x) for x in li.xpath('.//ul[contains(@class,"ib_type")]/li')]
            body = txt(li)
            def after(label):
                m2 = re.search(label + r'\s*([^\n]{0,60}?)(?=\s*(?:장소명|이용대상|접수기간|이용기간|상세보기|$))', body)
                return clean(m2.group(1)) if m2 else ''
            place = after('장소명')
            target = after('이용대상')
            def rng(label):
                m2 = re.search(label + r'\s*(\d{4}\.\d{2}\.\d{2})\s*~\s*(\d{4}\.\d{2}\.\d{2})', body)
                return (iso(m2.group(1)), iso(m2.group(2))) if m2 else (None, None)
            a_s, a_e = rng('접수기간')
            e_s, e_e = rng('이용기간')
            it = mk('seoul_yeyak', name, title, detail,
                    kid=kid, cat=' / '.join(cats), org='서울특별시',
                    target=target, place=place, applyStart=a_s, applyEnd=a_e,
                    start=e_s, end=e_e, status=status, fee=fee, region='서울')
            if it:
                out.append(it)
        if page >= last:
            break
        time.sleep(0.2)
    return out


def src_seoul_yeyak():
    """7갈래를 합치되 같은 예약 항목(상세 주소 기준)은 한 번만 담는다."""
    out, seen = [], set()
    for code, sub in SEOUL_YEYAK_DCODES:
        for it in seoul_yeyak_dcode(code, sub):
            if it['url'] in seen:
                continue
            seen.add(it['url'])
            out.append(it)
    return out


# ── 6. 부산광역시 강서도서관 강좌·행사 ────────────────────────────────
def src_gangseo_lib():
    url = ('https://library.bsgangseo.go.kr/gslib/index.php'
           '?g_page=culture&m_page=culture02')
    out, last = [], 1
    for page in range(1, 11):
        h = FETCH.get('%s&page=%d' % (url, page))
        doc = LH.fromstring(h)
        if page == 1:
            nums = [int(n) for n in re.findall(r'[?&]page=(\d+)', h)]
            last = max(nums) if nums else 1
        rows = doc.xpath('//table//tr[td]')
        if not rows:
            break
        for tr in rows:
            tds = tr.xpath('./td')
            if len(tds) < 5:
                continue
            a = tr.xpath('.//a[contains(@href,"leCode")]')
            title = txt(a[0]) if a else ''
            if not title:
                continue
            href = a[0].get('href') if a else ''
            if href.startswith('./'):
                detail = 'https://library.bsgangseo.go.kr/gslib/' + href[2:]
            elif href.startswith('/'):
                detail = 'https://library.bsgangseo.go.kr' + href
            elif href.startswith('index.php'):
                detail = 'https://library.bsgangseo.go.kr/gslib/' + href
            else:
                detail = url
            body = txt(tr)
            target = ''
            m = re.search(r'대상\s*:\s*([^\t]{1,60})', txt(tr.xpath('./td')[1]) if len(tds) > 1 else '')
            if m:
                target = clean(m.group(1))
            capm = re.search(r'(\d+)\s*/\s*(\d+)\s*명', body)
            applied = int(capm.group(1)) if capm else None
            cap = int(capm.group(2)) if capm else None
            ev = txt(tds[3]) if len(tds) > 3 else ''
            ap = txt(tds[5]) if len(tds) > 5 else ''
            fee = txt(tds[4]) if len(tds) > 4 else ''
            e_s, e_e = split_range(re.sub(r'\([^)]*\)', ' ', ev))
            a_s, a_e = split_range(ap.replace('/', ' '))
            if not a_s:
                m2 = re.search(r'(\d{4}\.\d{2}\.\d{2})', ap)
                a_s = iso(m2.group(1)) if m2 else None
            st = txt(tds[6]) if len(tds) > 6 else ''
            st = re.sub(r'\s*접수확인\s*', ' ', st).strip()
            it = mk('gangseo_lib', '부산광역시 강서도서관', title, detail,
                    cat='도서관 강좌·행사', org='강서도서관', target=target,
                    applyStart=a_s, applyEnd=a_e, start=e_s, end=e_e,
                    status=st, cap=cap, applied=applied, fee=fee, region='부산')
            if it:
                out.append(it)
        if page >= last:
            break
        time.sleep(0.2)
    return out


# ── 7. 국립부산과학관 개인교육프로그램 (JSON) ─────────────────────────
def src_sciport():
    base = 'https://www.sciport.or.kr/kor/CMS/IndivCurriMgr/list/default/std_A/MG/%d.json'
    out, total = [], None
    for page in range(1, 31):
        h = FETCH.post(base % page, {'mCode': 'MN038'},
                       headers={'Referer': 'https://www.sciport.or.kr/kor/CMS/IndivCurriMgr/curriList.do?mCode=MN038'})
        d = json.loads(h)
        r = d.get('result', {})
        if total is None:
            total = r.get('Max_cnt') or 0
        items = r.get('event_info_list') or []
        if not items:
            break
        for it in items:
            title = clean(it.get('curri_title'))
            start = iso(it.get('curri_s_date'))
            end = iso(it.get('curri_e_date'))
            apply_yn = it.get('apply_yn')
            it2 = mk('sciport', '국립부산과학관 · 개인교육프로그램', title,
                     'https://www.sciport.or.kr/kor/CMS/IndivCurriMgr/curriList.do?mCode=MN038',
                     kid=str(it.get('curri_seq')), cat='과학관 교육',
                     org='국립부산과학관', start=start, end=end,
                     status='신청가능' if apply_yn == 'Y' else '안내',
                     region='부산', note='연간일정 안내글 포함')
            if it2:
                out.append(it2)
        if total and page * 6 >= total:
            break
        time.sleep(0.15)
    return out


# ── 8. 연제구 희망교육지원센터 · 연제 프로그램 ────────────────────────
def src_yeonje_happy():
    url = 'https://www.yeonje.go.kr/happyedu/yeonjeprogram/list.do?mId=0304000000'
    out, last = [], 1
    for page in range(1, 21):
        h = FETCH.get('%s&page=%d' % (url, page))
        doc = LH.fromstring(h)
        if page == 1:
            nums = [int(n) for n in re.findall(r"goPage\((\d+)\)", h)]
            last = max(nums) if nums else 1
        blocks = doc.xpath('//div[contains(@class,"edu_items")]')
        if not blocks:
            break
        page_old = 0
        for b in blocks:
            a = b.xpath('.//p[contains(@class,"lecture_tit")]//a')
            if not a:
                continue
            title = txt(a[0])
            lec = re.search(r"'lecIdx'\s*:\s*(\d+)", a[0].get('data-keyset') or '')
            detail = url + ('&lecIdx=%s' % lec.group(1) if lec else '')
            body = txt(b)
            d = {}
            for dl in b.xpath('.//dl'):
                dt_ = txt(dl.xpath('./dt')[0]) if dl.xpath('./dt') else ''
                dd_ = txt(dl.xpath('./dd')[0]) if dl.xpath('./dd') else ''
                if dt_:
                    d[re.sub(r'\s+', '', dt_)] = dd_
            ap = d.get('접수기간', '')
            capm = re.search(r'(\d+)\s*/\s*(\d+)\s*명', body)
            ev = d.get('학습기간', '')
            st = ''
            for cand in ('접수중', '접수준비', '접수마감', '교육중', '교육마감'):
                if cand in body:
                    st = cand
                    break
            a_s, a_e = split_range(ap)
            e_s, e_e = split_range(ev)
            it = mk('yeonje_happy', '연제구 희망교육지원센터 · 연제 프로그램', title,
                    detail, kid=lec.group(1) if lec else title,
                    cat='희망교육', org='연제구 희망교육지원센터',
                    applyStart=a_s, applyEnd=a_e, start=e_s, end=e_e, status=st,
                    cap=int(capm.group(2)) if capm else None,
                    applied=int(capm.group(1)) if capm else None,
                    region='부산')
            if it:
                out.append(it)
                if (it.get('end') or it.get('start') or '9999') < (TODAY - dt.timedelta(days=30)).isoformat():
                    page_old += 1
        if blocks and page_old == len(blocks):
            break
        if page >= last:
            break
        time.sleep(0.2)
    return out


# ── 9. 부산광역시교육청 통합예약포털 (NetFunnel 대기열 통과 후 목록) ──────
PEN = 'https://home.pen.go.kr'
PEN_NF = 'https://homenet.pen.go.kr:443/ts.wseq'
PEN_PASSED = {'ok': False}


def pen_netfunnel_pass():
    """NetFunnel 대기열(5101→5002→netFunnelSs)을 통과해 세션에 통과 표시를 남긴다.
    대기 인원이 없을 때는 세 번의 요청으로 끝난다(2026-11-23 확인)."""
    if PEN_PASSED['ok']:
        return
    FETCH.get(PEN + '/yeyak/index.jsp')
    nfid = '0.%d' % int(time.time() * 1000)

    def call(q):
        return FETCH.get('%s?%s&js=yes&%d' % (PEN_NF, q, int(time.time() * 1000)))

    a = call('opcode=5101&nfid=%s&prefix=NetFunnel.gRtype=5101;&ttl=30'
             '&sid=service_1&aid=orghome' % nfid)
    m = re.search(r'key=([0-9A-F]+)&', a)
    if not m:
        raise RuntimeError('NetFunnel 5101 응답에 key 없음: %s' % a[:120])
    key = m.group(1)
    FETCH.post(PEN + '/yeyak/netFunnelSs.do', {'netfunnelKeyString': key},
               headers={'Referer': PEN + '/yeyak/index.jsp'})
    PEN_PASSED['ok'] = True


def pen_rows(h):
    """통합예약포털 목록 표를 항목 dict 목록으로 바꾼다(견학·체험 / 강좌·교육 공통)."""
    doc = LH.fromstring(h)
    out = []
    for tr in doc.xpath('//div[contains(@class,"rvelst")]//tbody/tr'):
        tds = tr.xpath('./td')
        if len(tds) < 6:
            continue
        a = tr.xpath('.//a[contains(@class,"viewExprnInfo") or contains(@class,"viewEduInfo")]')
        organ = txt(tds[1])
        tcell = tds[2]
        title = ''
        period_note = ''
        ps = tcell.xpath('.//p')
        if ps:
            title = txt(ps[0])
            if len(ps) > 1:
                period_note = txt(ps[1])
        if not title:
            continue
        ev = ' '.join(txt(x) for x in tds[3].xpath('.//p')) if len(tds) > 3 else ''
        ap = ' '.join(txt(x) for x in tds[4].xpath('.//p')) if len(tds) > 4 else ''
        target = txt(tds[5]) if len(tds) > 5 else ''
        who = txt(tds[6]) if len(tds) > 6 else ''
        status = ''
        for td in tds[6:]:
            st = txt(td)
            if st in ('접수중', '예정', '마감', '마감임박', '접수종료'):
                status = st
                break
        if not status and len(tds) > 6:
            status = txt(tds[-1])
        did = a[0].get('data-id') if a else ''
        rsid = a[0].get('data-rssysid') if a else ''
        pid = a[0].get('data-period-id') if a else ''
        e_s, e_e = (iso(x) for x in re.findall(r'20\d{2}/\d{2}/\d{2}', ev)[:2]) if len(re.findall(r'20\d{2}/\d{2}/\d{2}', ev)) >= 2 else (None, None)
        a_s, a_e = (iso(x) for x in re.findall(r'20\d{2}/\d{2}/\d{2}', ap)[:2]) if len(re.findall(r'20\d{2}/\d{2}/\d{2}', ap)) >= 2 else (None, None)
        out.append(dict(title=title, organ=organ, note=period_note, target=target,
                        who=who, status=status, ev=(e_s, e_e), ap=(a_s, a_e),
                        did=did, rsid=rsid, pid=pid))
    return out


def pen_portal_pairs(kind):
    """포털 첫 화면에서 기관별 (목록종류, srchRsSysId, mi) 짝을 모은다."""
    h = FETCH.get('%s/yeyak/exprn/selectExprnList.do?srchRsSysId=gaonplay&mi=15871' % PEN)
    pat = r'(selectExprnList|selectEduList)\.do\?([^"\']*srchRsSysId=[a-z0-9]+[^"\']*)'
    pairs = []
    for m in re.finditer(pat, h):
        path, q = m.group(1), m.group(2).replace('&amp;', '&')
        sid = re.search(r'srchRsSysId=([a-z0-9]+)', q)
        mi = re.search(r'mi=(\d+)', q)
        if not sid or not mi:
            continue
        item = (path, sid.group(1), mi.group(1))
        if item not in pairs:
            pairs.append(item)
    if kind == 'exprn':
        return [p for p in pairs if p[0] == 'selectExprnList']
    return [p for p in pairs if p[0] == 'selectEduList']


def pen_collect(kind, only_sys=None, max_sys=60):
    pen_netfunnel_pass()
    out = []
    seen_sys = []
    for path, sid, mi in pen_portal_pairs(kind)[:max_sys]:
        if only_sys and sid not in only_sys:
            continue
        if sid in seen_sys:
            continue
        seen_sys.append(sid)
        url = '%s/yeyak/%s/%s.do?srchRsSysId=%s&mi=%s' % (
            PEN, 'exprn' if kind == 'exprn' else 'edu/lib', path, sid, mi)
        if kind == 'edu':
            url = '%s/yeyak/edu/lib/%s.do?srchRsSysId=%s&mi=%s' % (PEN, path, sid, mi)
        else:
            url = '%s/yeyak/exprn/%s.do?srchRsSysId=%s&mi=%s' % (PEN, path, sid, mi)
        try:
            h = FETCH.get(url)
        except Exception:                                # noqa: BLE001
            continue
        for r in pen_rows(h):
            detail = '%s/yeyak/%s/view.do?exprnSeq=%s&exprnPeriodSeq=%s&srchRsSysId=%s' % (
                PEN, 'exprn' if kind == 'exprn' else 'edu/lib', r['did'], r['pid'], r['rsid'] or sid)
            cat = '견학·체험' if kind == 'exprn' else '강좌·교육'
            it = mk('pen_yeyak' if kind == 'exprn' else 'pen_bellib_edu',
                    '부산광역시교육청 통합예약포털 · ' + cat,
                    r['title'], detail, kid='%s-%s' % (r['rsid'], r['pid']),
                    cat=cat, org=r['organ'], target=r['target'],
                    applyStart=r['ap'][0], applyEnd=r['ap'][1],
                    start=r['ev'][0], end=r['ev'][1], status=r['status'],
                    region='부산', note='신청대상: ' + r['who'] + (' / ' + r['note'] if r['note'] else ''))
            if it:
                out.append(it)
        time.sleep(0.2)
    return out


def src_pen_yeyak():
    return pen_collect('exprn')


def src_pen_bellib_edu():
    return pen_collect('edu', only_sys={'bellib'})


# ── 10. 한국잡월드 (공개 JSON: 달력 + 상품 회차/잔여) ───────────────────
JOBWORLD = 'https://www.koreajobworld.or.kr'
JW_PRODUCTS = [100541]          # 확인된 상품: 잡월드 슈퍼위크 (어린이체험관 2부)


def src_jobworld():
    out = []
    # 달력: 날짜별 예약가능 여부(rvAvl 1/0)
    open_days = []
    months = [(TODAY.year, TODAY.month)]
    nxt = TODAY.replace(day=28) + dt.timedelta(days=5)
    if (nxt.year, nxt.month) != months[0]:
        months.append((nxt.year, nxt.month))
    for y, m in months:
        d = json.loads(FETCH.get('%s/api/reserve/calendar/%04d-%02d-01' % (JOBWORLD, y, m),
                                 headers={'Accept': 'application/json'}))
        for r in d.get('response') or []:
            if r.get('rvAvl') == 1 and (r.get('dt') or '') >= TODAY.isoformat():
                open_days.append(r['dt'])
    for pno in JW_PRODUCTS:
        d = json.loads(FETCH.get('%s/api/product/%s?pgDiv=P' % (JOBWORLD, pno),
                                 headers={'Accept': 'application/json'}))
        if not d.get('success'):
            continue
        resp = d.get('response') or {}
        prod = resp.get('product') or {}
        sched = resp.get('schedule') or []
        title = clean(prod.get('mrktnPdNm'))
        sal_s, sal_e = iso(prod.get('rvpossStartDt')), iso(prod.get('rvpossEndDt'))
        fee = prod.get('price')
        for s in sched:
            tm = clean(s.get('tm'))
            cap = num(s.get('capaPcnt'))
            left = num(s.get('rvResiduePcnt'))
            for day in open_days:
                it = mk('jobworld', '한국잡월드', '%s · %s' % (title, clean(s.get('mrktnScheSeqNm'))),
                        '%s/reserve/ind/child/%s' % (JOBWORLD, pno),
                        kid='%s-%s-%s' % (pno, s.get('mrktnScheSeqNo'), day), cat='직업체험',
                        org='한국잡월드', target='만 4세 이상(상품 기준)',
                        place='한국잡월드(경기 성남)', applyStart=sal_s, applyEnd=sal_e,
                        start=day, end=day, time=tm,
                        status='예약가능' if (left or 0) > 0 else '마감',
                        cap=cap, left=left, fee=('%s원' % fee) if fee else '', region='경기',
                        note='회차 잔여는 상품 API 기준(날짜별 잔여는 미제공)')
                if it:
                    out.append(it)
    return out


# ── 11. 대구광역시 통합예약 (공개 JSON) ────────────────────────────────
DAEGU_INST = [('DSS_INST_00000112', '대구시민안전테마파크')]


def src_daegu_yeyak():
    out = []
    for inst, instname in DAEGU_INST:
        body = json.dumps({'ftrPrgrmDcd': 'DSS_0078_02', 'instId': inst,
                           'pageNo': 1, 'rowsPerPage': 50}).encode()
        raw = FETCH._open('https://yeyak.daegu.go.kr/api/v1/res/expr/user/expr-prod-list',
                          body, {'Content-Type': 'application/json',
                                 'Accept': 'application/json',
                                 'Referer': 'https://yeyak.daegu.go.kr/'})
        d = json.loads(raw)
        for p in (d.get('data') or {}).get('items') or []:
            fee = ''
            if p.get('chrgYn') == 'Y' and p.get('ntslAmt'):
                fee = '%s원' % p['ntslAmt']
            elif p.get('chrgYn') == 'N':
                fee = '무료'
            st = {'ING': '접수중', 'END': '접수마감', 'PREV': '접수예정'}.get(p.get('rcptStatus'), p.get('rcptStatus') or '')
            it = mk('daegu_yeyak', '대구광역시 통합예약', p.get('ftrPrgrmNm'),
                    'https://yeyak.daegu.go.kr/expr/list/%s' % inst,
                    kid=p.get('ftrPrgrmId'), cat=clean(p.get('ftrPrgrmDcdNm')),
                    org=clean(p.get('instNm')) or instname, target=clean(p.get('ftrTrgtSe')),
                    place=clean(p.get('plcNm')),
                    applyStart=iso(p.get('rcptBgngYmd')), applyEnd=iso(p.get('rcptEndYmd')),
                    start=iso(p.get('prgrmBgngYmd')), end=iso(p.get('prgrmEndYmd')),
                    status=st, fee=fee, region='대구',
                    note=('문의 ' + p['inqryTelNo']) if p.get('inqryTelNo') else '')
            if it:
                out.append(it)
    return out


# ── 12. 인천어린이과학관 (월 달력 HTML: 회차별 잔여) ─────────────────────
def src_incheon_child():
    base = 'https://reserve.insiseol.or.kr/childsee/childSeeScheduleMonth.do?see_seq=1'
    out = []
    months = [(TODAY.year, TODAY.month)]
    nxt = (TODAY.replace(day=28) + dt.timedelta(days=5))
    months.append((nxt.year, nxt.month))
    for y, m in months:
        ym = '%04d-%02d' % (y, m)
        h = FETCH.get('%s&sch_ym=%s' % (base, ym))
        doc = LH.fromstring(h)
        for tr in doc.xpath('//table//tr[td]'):
            for td in tr.xpath('./td'):
                dp = td.xpath('.//p[contains(@class,"date")]')
                if not dp:
                    continue
                mday = num(txt(dp[0]))
                if not mday:
                    continue
                date = '%04d-%02d-%02d' % (y, m, mday)
                if date < TODAY.isoformat():
                    continue
                for li in td.xpath('.//ul[contains(@class,"book")]/li'):
                    t = txt(li)
                    tm = ''
                    sp = li.xpath('.//span[contains(@class,"part")]')
                    if sp:
                        tm = txt(sp[0])
                    if not tm:
                        continue
                    left = None
                    mm2 = re.search(r'잔여\s*[:：]?\s*(\d+)\s*명', t)
                    if mm2:
                        left = int(mm2.group(1))
                        status = '예약가능' if left > 0 else '마감'
                    elif '매진' in t:
                        status = '매진'
                    elif '예약불가' in t:
                        status = '예약불가'
                    else:
                        continue
                    if status == '예약불가':
                        continue
                    it = mk('incheon_child', '인천어린이과학관',
                            '상설전시관 %s' % tm, base,
                            kid='%s-%s' % (date, tm), cat='상설전시',
                            org='인천어린이과학관', place='인천어린이과학관(계양구)',
                            target='영유아~초등(보호자 동반)',
                            start=date, end=date, time=tm, status=status,
                            cap=400, left=left,
                            fee='어린이 2,000원 / 성인 4,000원',
                            region='인천', note='잔여는 월 달력 표기 기준')
                    if it:
                        out.append(it)
        time.sleep(0.2)
    return out


SOURCES = [
    ('busan_reserve_exprn', '부산광역시 통합예약 · 견학/체험', src_busan_reserve_exprn),    ('pen_yeyak', '부산광역시교육청 통합예약포털 · 견학/체험', src_pen_yeyak),
    ('pen_bellib_edu', '부산광역시교육청 통합예약포털 · 영어도서관 강좌', src_pen_bellib_edu),
    ('busan_reserve_lctre', '부산광역시 통합예약 · 강좌/교육', src_busan_reserve_lctre),
    ('busan_119', '부산광역시 119 안전체험관', src_busan_119),
    ('dream_teach', '부산 들락날락 · 행사·강좌', src_dream_teach),
    ('dream_dnpa', '부산 들락날락 · 참여 프로그램', src_dream_dnpa),
    ('seoul_yeyak', '서울특별시 공공서비스예약 · 문화체험 7갈래', src_seoul_yeyak),
    ('gangseo_lib', '부산광역시 강서도서관', src_gangseo_lib),
    ('sciport', '국립부산과학관 · 개인교육프로그램', src_sciport),
    ('yeonje_happy', '연제구 희망교육지원센터', src_yeonje_happy),
    ('jobworld', '한국잡월드', src_jobworld),
    ('daegu_yeyak', '대구광역시 통합예약', src_daegu_yeyak),
    ('incheon_child', '인천어린이과학관', src_incheon_child),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append', help='수집기 key (여러 번 가능)')
    ap.add_argument('--out', default=OUT_DEFAULT)
    ap.add_argument('--merge-in', action='append', default=[],
                    help='이미 수집한 JSON을 합쳐서 저장(무거운 출처를 나눠 돌릴 때)')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if a.list:
        for k, n, _ in SOURCES:
            print('%-24s %s' % (k, n))
        return
    picked = [s for s in SOURCES if not a.only or s[0] in a.only]
    items, meta = [], []
    for key, name, fn in picked:
        t0 = time.time()
        try:
            got = fn() or []
            err = None
        except Exception as e:                           # noqa: BLE001
            got, err = [], '%s: %s' % (type(e).__name__, e)
        stale = 0
        fresh = []
        for it in got:
            ref = max([x for x in (it.get('end'), it.get('start'), it.get('applyEnd')) if x] or [''])
            if ref and ref < (TODAY - dt.timedelta(days=30)).isoformat():
                stale += 1
                continue
            fresh.append(it)
        items.extend(fresh)
        meta.append({'key': key, 'name': name, 'count': len(fresh),
                     'pastSkipped': stale, 'ok': err is None, 'error': err,
                     'sec': round(time.time() - t0, 1)})
        if not a.quiet:
            print('%-24s %5d건 (지난 과정 %d건 제외) %5.1fs  %s' % (
                key, len(fresh), stale, time.time() - t0, err or 'OK'))
    # 같은 (제목·시작일·장소) 중복 제거
    seen, uniq = set(), []
    extra_meta = []
    for path in getattr(a, 'merge_in', []) or []:
        try:
            prev = json.load(open(path, encoding='utf-8'))
        except Exception as e:                           # noqa: BLE001
            print('합칠 파일을 읽지 못했습니다: %s (%s)' % (path, e))
            continue
        items = (prev.get('items') or []) + items
        extra_meta.extend(prev.get('sources') or [])
    meta = extra_meta + meta
    dedup_meta, seen_keys = [], set()
    for m in meta:
        if m.get('key') in seen_keys:
            continue
        seen_keys.add(m.get('key'))
        dedup_meta.append(m)
    meta = dedup_meta
    for it in items:
        k = (re.sub(r'\s+', '', it['title']), it.get('start') or '', it.get('org') or '')
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    # id 유일성 보장(같은 제목·날짜가 여러 기관에 있는 경우)
    used = set()
    for it in uniq:
        base_id = it['id']
        n = 1
        while it['id'] in used:
            n += 1
            it['id'] = '%s-%d' % (base_id, n)
        used.add(it['id'])
    uniq.sort(key=lambda x: (x.get('applyEnd') or x.get('start') or '9999', x['title']))
    doc = {
        'tab': 13,
        'name': '어린이 체험·예약',
        'generatedAt': dt.datetime.now(KST).isoformat(timespec='seconds'),
        'today': TODAY.isoformat(),
        'sources': meta,
        'count': len(uniq),
        'items': uniq,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    if not a.quiet:
        print('\n합계 %d건 (중복 제거 후) → %s' % (len(uniq), a.out))


if __name__ == '__main__':
    main()
