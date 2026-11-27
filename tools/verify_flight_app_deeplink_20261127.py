"""⑥⑦⑧ 항공사·예약처 앱 딥링크 검증 (2026-11-27).

index.html 의 실제 코드 구간을 그대로 떼어 quickjs 로 돌린다.

검증 항목
 1) 표(FL_APP_PKG) — 값이 비지 않고, 패키지 형식이며, 앱 링크 표(FL_APP_DEEP)의 키가 모두 표 안의 도메인
 2) 도메인 찾기 — www./kr./mfly. 같은 하위 도메인에서 표의 도메인을 찾고, 표에 없는 곳은 비운다
 3) intent 문자열 — 앱이 주소를 받는 곳은 scheme=https·action=VIEW·category=BROWSABLE·package·주소·fallback
    앱 링크가 확인되지 않은 곳은 주소 없이 action=MAIN·category=LAUNCHER·package·fallback
 4) 안드로이드 클릭 — ⑥⑦⑧ 링크를 가로채 preventDefault + intent, 1,200ms 뒤 누른 주소(웹)로 fallback
 5) 앱이 열려 화면을 떠난 경우(blur/hidden)에는 fallback 하지 않음
 6) 아이폰·데스크톱·표에 없는 도메인(구글 플라이트 등)·비 https 링크는 가로채지 않음
 7) 기존 ⑧ data-ml-app 경로(플라이 블루·골 스마일즈)는 예전 그대로
"""
import json
import os
import re
import sys

import quickjs

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'index.html')
html = open(SRC, encoding='utf-8').read()

m = re.search(r'^function esc\(str\)\{.*$', html, re.M)
assert m, 'esc() 를 찾지 못함'
esc_fn = m.group(0)

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
function __tick(){ __timers.slice().forEach(function(t){t.fn()}); __timers.length=0 }
function __click(href,extra){
  var attrs={href:href};
  if(extra)for(var k in extra)attrs[k]=extra[k];
  var el={getAttribute:function(k){return k in attrs?attrs[k]:null}};
  var ev={target:{closest:function(sel){
      if(sel==='a[data-ml-app]')return attrs['data-ml-app']?el:null;
      if(sel==='a[href]')return el;
      return null;}},
    preventDefault:function(){__prevented++},stopPropagation:function(){__stopped++}};
  __prevented=0;__stopped=0;
  (__docListeners['click']||[]).slice().forEach(function(f){f(ev)});
  return {prevented:__prevented,stopped:__stopped};
}
"""

ctx = quickjs.Context()
ctx.set_memory_limit(256 * 1024 * 1024)
for chunk in (HARNESS, esc_fn, block):
    ctx.eval(chunk)

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


def click(href, extra=None):
    js = '__click(%s%s)' % (json.dumps(href), (',' + json.dumps(extra)) if extra else '')
    return json.loads(run('JSON.stringify(%s)' % js))


print('[1] 표 — 패키지 형식 · 앱 링크 표 정합')
n = run('Object.keys(FL_APP_PKG).length')
print('       도메인 %d곳' % n)
eq('도메인 55곳 이상', n >= 55, True)
eq('빈 값 없음', run('Object.keys(FL_APP_PKG).filter(function(k){return !/^[a-z][a-z0-9_]*(\\.[a-z0-9_]+)+$/i.test(FL_APP_PKG[k])}).length'), 0)
eq('앱 링크 표 키가 모두 표 안의 도메인', run("""
(function(){
  var bad=[],ok=['koreanair.com','flyasiana.com','airbusan.com','jinair.com','jejuair.net','eastarjet.com','trinityairways.com',
    'flyairseoul.com','airpremia.com','jal.co.kr','jal.co.jp','ana.co.kr','ana.co.jp','flypeach.com','jetstar.com',
    'starflyer.jp','cathaypacific.com','hkexpress.com','ceair.com','airchina.kr','airchina.com','china-airlines.com',
    'evaair.com','starlux-airlines.com','tigerairtw.com','juneyaoair.com','airmacau.com.mo','greaterbay-airlines.com',
    'vietjetair.com','vietnamairlines.com','singaporeair.com','flyscoot.com','philippineairlines.com',
    'cebupacificair.com','malaysiaairlines.com','thaiairways.com','bangkokair.com','airasia.com','trip.com',
    'skyscanner.co.kr','modetour.com','ttang.com','ybtour.co.kr','hanatour.com','flyingblue.com','smiles.com.br',
    'virginatlantic.com','delta.com','lifemiles.com','aircanada.com','miles-and-more.com','united.com',
    'turkishairlines.com','aa.com','alaskaair.com','qantas.com','jetblue.com','etihad.com','emirates.com'];
  for(var d in ok){if(!FL_APP_PKG[ok[d]])bad.push('missing:'+ok[d])}
  for(var h in FL_APP_DEEP){var hit=false;for(var d in FL_APP_PKG){if(h===d||h.slice(-(d.length+1))==='.'+d)hit=true}if(!hit)bad.push('deep:'+h)}
  return bad.join(',');
})()
"""), '')

print('[2] 도메인 찾기')
for href, want in (
    ('https://www.koreanair.com/', 'koreanair.com'),
    ('https://www.jinair.com/', 'jinair.com'),
    ('https://kr.trip.com/flights/showfarefirst?dcity=pus&acity=fuk&ddate=2026-12-01', 'trip.com'),
    ('https://www.skyscanner.co.kr/transport/flights/pus/fuk/261201/261203/', 'skyscanner.co.kr'),
    ('https://www.modetour.com/flights/discount-flight', 'modetour.com'),
    ('https://mfly.ybtour.co.kr/mobile/fr/booking/findPaxInfoSummaryRtM', 'ybtour.co.kr'),
    ('https://www.ttang.com/ttangair/search/ttang/fare_detail.do', 'ttang.com'),
    ('https://www.tikitikit.kr/flight/tripcom-10cc1e552c0e44481824', ''),
    ('https://www.google.com/travel/flights?q=Flights+to+FUK', ''),
    ('https://www.agoda.com/', ''),
):
    eq('base %s' % href, run('flAppBase(%s)' % json.dumps(href)), want)

print('[3] intent 문자열')
DEEP_TRIP = ('intent://kr.trip.com/flights/showfarefirst?dcity=pus&acity=fuk&ddate=2026-12-01#Intent;scheme=https;'
             'action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=ctrip.english;'
             'S.browser_fallback_url=https%3A%2F%2Fkr.trip.com%2Fflights%2Fshowfarefirst%3Fdcity%3Dpus%26acity%3Dfuk%26ddate%3D2026-12-01;end')
eq('trip.com 깊은 링크(VIEW)', run('flAppIntentFor("trip.com",%s)' % json.dumps('https://kr.trip.com/flights/showfarefirst?dcity=pus&acity=fuk&ddate=2026-12-01')), DEEP_TRIP)
eq('진에어 앱 첫 화면(LAUNCHER)', run('flAppIntentFor("jinair.com","https://www.jinair.com/")'),
   'intent://#Intent;package=com.jinair.android;action=android.intent.action.MAIN;'
   'category=android.intent.category.LAUNCHER;S.browser_fallback_url=https%3A%2F%2Fwww.jinair.com%2F;end')
eq('플라이 블루 → 에어프랑스 앱 주소', run('flAppIntentFor("flyingblue.com","https://www.flyingblue.com/")'),
   'intent://www.airfrance.com/home#Intent;scheme=https;action=android.intent.action.VIEW;'
   'category=android.intent.category.BROWSABLE;package=com.airfrance.android.dinamoprd;'
   'S.browser_fallback_url=https%3A%2F%2Fwww.flyingblue.com%2F;end')
eq('스카이스캐너 주소 유지', run('flAppIntentFor("skyscanner.co.kr","https://www.skyscanner.co.kr/transport/flights/pus/fuk/261201/261203/")'),
   'intent://www.skyscanner.co.kr/transport/flights/pus/fuk/261201/261203/#Intent;scheme=https;'
   'action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=net.skyscanner.android.main;'
   'S.browser_fallback_url=https%3A%2F%2Fwww.skyscanner.co.kr%2Ftransport%2Fflights%2Fpus%2Ffuk%2F261201%2F261203%2F;end')
eq('모두투어 앱 첫 화면', run('flAppIntentFor("modetour.com","https://www.modetour.com/flights/discount-flight")'),
   'intent://#Intent;package=com.modetour.m;action=android.intent.action.MAIN;'
   'category=android.intent.category.LAUNCHER;S.browser_fallback_url=https%3A%2F%2Fwww.modetour.com%2Fflights%2Fdiscount-flight;end')

print('[4] 안드로이드 클릭 → intent + 1,200ms 웹 fallback')
run('navigator={userAgent:%s}' % json.dumps(ANDROID))
run('__nav.length=0;__timers.length=0;document.hidden=false')
r = click("https://www.ttang.com/ttangair/search/ttang/fare_detail.do")
eq('preventDefault', r['prevented'], 1)
eq('stopPropagation(카드 시트 방지)', r['stopped'], 1)
eq('첫 이동 = intent', run('__nav[0]||""'),
   'intent://#Intent;package=com.com072.app072dotcom;action=android.intent.action.MAIN;'
   'category=android.intent.category.LAUNCHER;S.browser_fallback_url=https%3A%2F%2Fwww.ttang.com%2Fttangair%2Fsearch%2Fttang%2Ffare_detail.do;end')
eq('타이머 1개 · 1200ms', run('__timers.length+" / "+(__timers[0]&&__timers[0].ms)'), '1 / 1200')
run('__tick()')
eq('1,200ms 뒤 누른 주소로 fallback', run('__nav[1]||""'), 'https://www.ttang.com/ttangair/search/ttang/fare_detail.do')

print('[5] 앱이 열려 화면을 떠난 경우 → fallback 없음')
run('__nav.length=0;__timers.length=0;document.hidden=false')
run('__click("https://www.koreanair.com/")')
eq('대한항공 intent', run('__nav[0]||""'),
   'intent://#Intent;package=com.koreanair.passenger;action=android.intent.action.MAIN;'
   'category=android.intent.category.LAUNCHER;S.browser_fallback_url=https%3A%2F%2Fwww.koreanair.com%2F;end')
run('__fireWin("blur");__tick()')
eq('blur 뒤에는 웹으로 보내지 않음', run('__nav.length'), 1)

print('[6] 아이폰·데스크톱·표 밖 도메인·비 https 는 가로채지 않음')
for ua, label in ((IPHONE, 'iphone'), (DESKTOP, 'desktop')):
    run('__nav.length=0;__timers.length=0;navigator={userAgent:%s}' % json.dumps(ua))
    r = click("https://www.koreanair.com/")
    eq('%s preventDefault 없음' % label, r['prevented'], 0)
    eq('%s 이동 없음' % label, run('__nav.length'), 0)
run('navigator={userAgent:%s}' % json.dumps(ANDROID))
for href, label in (('https://www.google.com/travel/flights?q=x', '구글 플라이트'),
                    ('https://www.tikitikit.kr/flight/ybtour-43buzn', '티키티킷'),
                    ('#', '해시 링크')):
    run('__nav.length=0;__timers.length=0')
    r = click(href)
    eq('%s 가로채지 않음' % label, (r['prevented'], run('__nav.length')), (0, 0))

print('[7] 기존 ⑧ data-ml-app 경로 그대로')
SMILES = '{"key":"smiles","name":"GOL 스마일즈","short":"골 스마일즈","url":"https://www.smiles.com.br/","urlLabel":"Smiles 공식"}'
eq('smiles href', run('mlAppHref(%s)' % SMILES), 'https://www.smiles.com.br/')
run('__nav.length=0;__timers.length=0;document.hidden=false')
r = click("https://www.smiles.com.br/",{"data-ml-app":"smiles","data-app-pkg":"com.br.smiles","data-app-web":"https://www.smiles.com.br/"})
eq('smiles preventDefault', r['prevented'], 1)
eq('smiles intent', run('__nav[0]||""'),
   'intent://www.smiles.com.br/#Intent;scheme=https;action=android.intent.action.VIEW;'
   'category=android.intent.category.BROWSABLE;package=com.br.smiles;'
   'S.browser_fallback_url=https%3A%2F%2Fwww.smiles.com.br%2F;end')
run('__tick()')
eq('smiles 1,200ms fallback', run('__nav[1]||""'), 'https://www.smiles.com.br/')

print()
if fails:
    print('FAILED %d: %s' % (len(fails), fails))
    sys.exit(1)
print('ALL PASS')
