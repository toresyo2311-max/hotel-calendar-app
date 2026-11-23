#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧒 '육' 폴더 41개 사이트 1단계 전수 프로빙.

각 사이트에 대해
  · HTTP 상태 / 최종 URL(리다이렉트) / 바이트 / Content-Type
  · 비로그인 공개 JSON·AJAX 후보(스크립트 안의 fetch/ajax/API 경로)
  · JS 렌더링 의존 여부(본문 텍스트가 거의 없고 SPA 흔적만 있는 경우)
  · 로그인 필수 여부(로그인 페이지로 튕김·로그인 안내 문구)
  · 봇 차단(WAF) 여부(403/차단 문구/캡차)
를 기록하고 원본 HTML을 남긴다.

사용
  python3 tools/probe_kids_sites.py                 # 41개 전수
  python3 tools/probe_kids_sites.py --only busan_119
  python3 tools/probe_kids_sites.py --out downloads/kids_probe_2026-11-23
"""
import argparse
import gzip
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))          # /workspace
DEFAULT_MANIFEST = os.path.join(WS, 'downloads', 'kids_probe_2026-11-23', 'sites.json')
OUTDIR = os.path.join(WS, 'downloads', 'kids_probe_2026-11-23')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'close',
    'Upgrade-Insecure-Requests': '1',
}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def decode(raw, headers):
    enc = (headers.get('Content-Encoding') or '').lower()
    if 'gzip' in enc:
        try:
            raw = gzip.decompress(raw)
        except Exception:                                # noqa: BLE001
            pass
    elif 'deflate' in enc:
        try:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except Exception:                                # noqa: BLE001
            pass
    ctype = headers.get('Content-Type') or ''
    m = re.search(r'charset=([\w-]+)', ctype, re.I)
    charset = m.group(1) if m else None
    for cs in filter(None, [charset, 'utf-8', 'euc-kr', 'cp949']):
        try:
            return raw.decode(cs), cs
        except Exception:                                # noqa: BLE001
            continue
    return raw.decode('utf-8', 'replace'), 'utf-8(replace)'


def fetch(url, timeout=25):
    t0 = time.time()
    res = {'url': url, 'ok': False, 'status': None, 'final_url': None,
           'bytes': 0, 'ctype': '', 'charset': '', 'ms': 0, 'error': None, 'text': None}
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            raw = r.read()
            text, cs = decode(raw, r.headers)
            res.update(ok=True, status=r.status, final_url=r.geturl(), bytes=len(raw),
                       ctype=r.headers.get('Content-Type') or '', charset=cs, text=text)
    except urllib.error.HTTPError as e:
        raw = b''
        try:
            raw = e.read()
        except Exception:                                # noqa: BLE001
            pass
        text, cs = decode(raw, e.headers or {})
        res.update(status=e.code, final_url=url, bytes=len(raw), charset=cs,
                   ctype=(e.headers or {}).get('Content-Type') or '',
                   text=text, error='HTTP %s' % e.code)
    except socket.timeout:
        res['error'] = 'timeout'
    except urllib.error.URLError as e:
        res['error'] = 'URLError: %s' % e.reason
    except Exception as e:                               # noqa: BLE001
        res['error'] = '%s: %s' % (type(e).__name__, e)
    res['ms'] = int((time.time() - t0) * 1000)
    return res


# ── 판별 ──────────────────────────────────────────────────────────────
LOGIN_RE = re.compile(r'(로그인\s*(후|이\s*필요)|login\s*required|sign\s*in\s*to\s*continue)', re.I)
BLOCK_RE = re.compile(r'(비정상적인\s*(접근|요청)|접근이\s*차단|차단되었습니다|Access\s*Denied|'
                      r'자동\s*(입력|접속)|captcha|reCAPTCHA|Cloudflare|Just a moment|'
                      r'잘못된\s*접근|보안\s*프로그램)', re.I)
JS_RE = re.compile(r'(react|vue(?:\.js)?["\']|angular|__NEXT_DATA__|createApp\(|'
                   r'지원하지\s*않는\s*브라우저|JavaScript\s*활성화|script\s*src=)', re.I)
API_RE = re.compile(r'''["']((?:https?://[^"']+|/[A-Za-z0-9_\-./]+)\.(?:json|do|jsp|asp|php|action|ajax)(?:\?[^"']*)?)["']''')
API_HINT_RE = re.compile(r'''(fetch\(|ajax|XMLHttpRequest|\.getJSON|apiUrl|url\s*:\s*['"])''')


def visible_text(html):
    t = re.sub(r'(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>', ' ', html or '')
    t = re.sub(r'(?s)<[^>]+>', ' ', t)
    t = re.sub(r'&nbsp;?', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def api_candidates(html):
    out = []
    for m in API_RE.finditer(html or ''):
        u = m.group(1)
        if re.search(r'\.(css|png|jpg|gif|ico|woff2?|svg)$', u, re.I):
            continue
        if u not in out:
            out.append(u)
    return out[:40]


def probe(site):
    url = site['url']
    r = fetch(url)
    html = r.pop('text') or ''
    vt = visible_text(html)
    info = dict(site)
    info.update(
        status=r['status'], final_url=r['final_url'], bytes=r['bytes'], ctype=r['ctype'],
        charset=r['charset'], ms=r['ms'], error=r['error'],
        text_len=len(vt), links=len(re.findall(r'(?i)<a\s', html)),
        scripts=len(re.findall(r'(?i)<script', html)),
        json_like=(html.lstrip()[:1] in ('{', '[')),
        login_hint=bool(LOGIN_RE.search(html)),
        login_redirect=bool(re.search(r'(login|signin|sign_in|member/login)', r['final_url'] or '', re.I)),
        block_hint=bool(BLOCK_RE.search(html)),
        js_hint=bool(JS_RE.search(html)),
        api=api_candidates(html),
        api_hint=bool(API_HINT_RE.search(html)),
    )
    if html:
        fn = os.path.join(OUTDIR, 'raw', '%s.html' % site['key'])
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(fn, 'w', encoding='utf-8') as f:
            f.write('<!-- probed %s status=%s -->\n' % (url, r['status']))
            f.write(html)
        info['raw'] = os.path.relpath(fn, WS)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', default=DEFAULT_MANIFEST)
    ap.add_argument('--only', action='append')
    ap.add_argument('--sleep', type=float, default=0.4)
    a = ap.parse_args()
    sites = json.load(open(a.manifest, encoding='utf-8'))
    if a.only:
        sites = [s for s in sites if s['key'] in a.only]
    os.makedirs(os.path.join(OUTDIR, 'raw'), exist_ok=True)
    results = []
    for n, s in enumerate(sites, 1):
        info = probe(s)
        results.append(info)
        print('%2d/%d %-26s %-4s %7db %5dms txt=%-6d links=%-4d api=%-2d %s' % (
            n, len(sites), s['key'], info['status'] or '-', info['bytes'], info['ms'],
            info['text_len'], info['links'], len(info['api']),
            ' '.join(x for x, v in (('LOGIN', info['login_hint'] or info['login_redirect']),
                                    ('BLOCK', info['block_hint']), ('JS', info['js_hint'])) if v)),
        )
        if info['error'] and not info['status']:
            print('        ! %s' % info['error'])
        time.sleep(a.sleep)
    out = os.path.join(OUTDIR, 'probe_results.json')
    json.dump(results, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n저장:', out)


if __name__ == '__main__':
    main()
