"""⑧ 앱 딥링크 함수 단위 검증 — index.html 의 실제 코드 구간을 그대로 떼어 quickjs 로 돌린다.

검증 항목
 1) href 는 안드로이드·아이폰·데스크톱 구분 없이 언제나 공식 웹(https)
 2) data 속성(data-ml-app · data-app-pkg · data-app-web)
 3) 클릭 시 만들어지는 intent:// 문자열 (action=VIEW · category=BROWSABLE · package · browser_fallback_url)
 4) 안드로이드 클릭 처리: preventDefault + intent 시도, 1,200ms 뒤 !document.hidden 이면 공식 웹으로 fallback
 5) 앱이 열려 화면을 떠난 경우(blur/hidden)에는 fallback 하지 않음
 6) 아이폰·데스크톱 클릭은 가로채지 않음(기본 링크 그대로)
"""
import json
import re
import sys

import quickjs

import os
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'index.html')
html = open(SRC, encoding='utf-8').read()

# esc() 원본
m = re.search(r'^function esc\(str\)\{.*$', html, re.M)
assert m, 'esc() 를 찾지 못함'
esc_fn = m.group(0)

# 이번에 고친 앱 링크 구간
a = html.index('var ML_AF_APP=')
b = html.index('function mlAppsNote()')
block = html[a:b]

HARNESS = """
var __nav=[], __timers=[], __docListeners={}, __winListeners={};
var location={set href(v){__nav.push(v)},get href(){return __nav.length?__nav[__nav.length-1]:'https://toresyo2311-max.github.io/hotel-calendar-app/'}};
var document={
  hidden:false,
  addEventListener:function(t,f){(__docListeners[t]=__docListeners[t]||[]).push(f)},
  removeEventListener:function(t,f){var l=__docListeners[t]||[];var i=l.indexOf(f);if(i>=0)l.splice(i,1)}
};
var window={location:location,
  addEventListener:function(t,f){(__winListeners[t]=__winListeners[t]||[]).push(f)},
  removeEventListener:function(t,f){var l=__winListeners[t]||[];var i=l.indexOf(f);if(i>=0)l.splice(i,1)}
};
function setTimeout(fn,ms){__timers.push({fn:fn,ms:ms});return __timers.length}
function __fireWin(t){ (__winListeners[t]||[]).slice().forEach(function(f){f()}) }
function __fireDoc(t){ (__docListeners[t]||[]).slice().forEach(function(f){f()}) }
function __tick(){ __timers.slice().forEach(function(t){t.fn()}); __timers.length=0 }
"""

ctx = quickjs.Context()
ctx.set_memory_limit(256 * 1024 * 1024)
ctx.eval(HARNESS)
ctx.eval(esc_fn)
ctx.eval(block)

SMILES = '{"key":"smiles","name":"GOL 스마일즈","short":"골 스마일즈","url":"https://www.smiles.com.br/","urlLabel":"Smiles 공식"}'
FB = '{"key":"flyingblue","name":"에어프랑스·KLM 플라이 블루","short":"에어프랑스","url":"https://www.flyingblue.com/","urlLabel":"플라이 블루 공식"}'

EXP_SMILES = ('intent://www.smiles.com.br/#Intent;scheme=https;action=android.intent.action.VIEW;'
              'category=android.intent.category.BROWSABLE;package=com.br.smiles;'
              'S.browser_fallback_url=https%3A%2F%2Fwww.smiles.com.br%2F;end')
EXP_FB = ('intent://www.airfrance.com/home#Intent;scheme=https;action=android.intent.action.VIEW;'
          'category=android.intent.category.BROWSABLE;package=com.airfrance.android.dinamoprd;'
          'S.browser_fallback_url=https%3A%2F%2Fwwws.airfrance.co.kr%2F;end')

ANDROID = 'Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36'
IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1'
DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'

fails = []


def eq(name, got, want):
    ok = got == want
    print(('  OK   ' if ok else '  FAIL ') + name + ('' if ok else '\n        got  ' + repr(got) + '\n        want ' + repr(want)))
    if not ok:
        fails.append(name)


def run(js):
    return ctx.eval(js)


print('[1] href — 언제나 공식 웹(https)')
for ua, label in ((ANDROID, 'android'), (IPHONE, 'iphone'), (DESKTOP, 'desktop')):
    run('navigator={userAgent:%s}' % json.dumps(ua))
    eq('smiles href (%s)' % label, run('mlAppHref(%s)' % SMILES), 'https://www.smiles.com.br/')
    eq('flyingblue href (%s)' % label, run('mlAppHref(%s)' % FB), 'https://www.flyingblue.com/')
    eq('target (%s)' % label, run('mlAppTarget(%s)' % SMILES), '_blank')

print('[2] data 속성')
run('navigator={userAgent:%s}' % json.dumps(ANDROID))
eq('smiles attr', run('mlAppAttr(%s)' % SMILES),
   ' data-ml-app="smiles" data-app-pkg="com.br.smiles" data-app-web="https://www.smiles.com.br/"')
eq('flyingblue attr', run('mlAppAttr(%s)' % FB),
   ' data-ml-app="flyingblue" data-app-pkg="com.airfrance.android.dinamoprd" data-app-web="https://wwws.airfrance.co.kr/"')
eq('ke(대한항공) 은 앱 없음', run('mlAppAttr({key:"ke",url:"https://www.koreanair.com/"})'), '')

print('[3] intent 문자열')
eq('smiles intent', run('mlAppIntent(%s)' % SMILES), EXP_SMILES)
eq('flyingblue intent', run('mlAppIntent(%s)' % FB), EXP_FB)

print('[4] 안드로이드 클릭 → intent 시도 + 1,200ms 웹 fallback')
run('__nav.length=0;__timers.length=0;navigator={userAgent:%s}' % json.dumps(ANDROID))
run("""
var __a={getAttribute:function(k){return {href:'https://www.smiles.com.br/','data-ml-app':'smiles',
  'data-app-pkg':'com.br.smiles','data-app-web':'https://www.smiles.com.br/'}[k]||null}};
var __prevented=0,__stopped=0;
var __ev={target:{closest:function(sel){return sel==='a[data-ml-app]'?__a:null}},
  preventDefault:function(){__prevented=1},stopPropagation:function(){__stopped=1}};
(__docListeners['click']||[]).slice().forEach(function(f){f(__ev)});
""")
eq('preventDefault', run('__prevented'), 1)
eq('stopPropagation(카드 시트 방지)', run('__stopped'), 1)
eq('첫 이동 = intent', run('__nav[0]||""'), EXP_SMILES)
eq('타이머 1개 · 1200ms', run('__timers.length+" / "+(__timers[0]&&__timers[0].ms)'), '1 / 1200')
run('document.hidden=false;__tick()')
eq('1,200ms 뒤 fallback 웹', run('__nav[1]||""'), 'https://www.smiles.com.br/')

print('[5] 앱이 열려 화면을 떠난 경우 → fallback 없음')
run('__nav.length=0;__timers.length=0;document.hidden=false')
run("""
var __a={getAttribute:function(k){return {href:'https://www.flyingblue.com/','data-ml-app':'flyingblue',
  'data-app-pkg':'com.airfrance.android.dinamoprd','data-app-web':'https://wwws.airfrance.co.kr/'}[k]||null}};
var __ev={target:{closest:function(sel){return sel==='a[data-ml-app]'?__a:null}},
  preventDefault:function(){},stopPropagation:function(){}};
(__docListeners['click']||[]).slice().forEach(function(f){f(__ev)});
""")
eq('플라이블루 intent', run('__nav[0]||""'), EXP_FB)
run('__fireWin("blur");__tick()')
eq('blur 뒤에는 웹으로 보내지 않음', run('__nav.length'), 1)

print('[6] 아이폰·데스크톱은 가로채지 않음')
for ua, label in ((IPHONE, 'iphone'), (DESKTOP, 'desktop')):
    run('__nav.length=0;__timers.length=0;navigator={userAgent:%s}' % json.dumps(ua))
    run("""
var __a={getAttribute:function(k){return {href:'https://www.smiles.com.br/','data-ml-app':'smiles',
  'data-app-pkg':'com.br.smiles','data-app-web':'https://www.smiles.com.br/'}[k]||null}};
var __prevented=0;
var __ev={target:{closest:function(sel){return sel==='a[data-ml-app]'?__a:null}},
  preventDefault:function(){__prevented=1},stopPropagation:function(){}};
(__docListeners['click']||[]).slice().forEach(function(f){f(__ev)});
""")
    eq('%s preventDefault 없음' % label, run('__prevented'), 0)
    eq('%s 이동 없음' % label, run('__nav.length'), 0)

print()
if fails:
    print('FAILED %d: %s' % (len(fails), fails))
    sys.exit(1)
print('ALL PASS')
