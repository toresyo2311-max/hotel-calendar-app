"""⑥⑦⑧ 항공사·예약처 전체 안드로이드 앱 딥링크 세팅 (2026-11-27).

바꾸는 것
 1) index.html — 공식 링크 구간에 도메인→공식 앱 패키지 표(FL_APP_PKG)와
    앱이 그 주소를 직접 받는 곳 표(FL_APP_DEEP), 링크 해석 함수(flAppHost/flAppBase/flAppIntentFor)를 넣는다.
 2) index.html — 문서 클릭 위임을 넓혀, ⑥⑦⑧ 의 모든 <a href="https://…"> 가 표에 있는 도메인이면
    안드로이드에서만 intent:// 로 앱을 먼저 열고 1.2초 뒤 공식 웹으로 넘어가게 한다.
 3) index.html — ⑥ 예약 창 안내문에 안드로이드 앱 안내 한 줄, ⑧ 앱 안내문 문구 확장.
 4) sw.js VERSION z234 → z235, README 안내 갱신.

패키지 값은 전부 play.google.com/store/apps/details?id=… 에서 앱 이름·개발자를 확인한 것만 넣는다.
"""
import re
import sys
import io

INDEX = 'index.html'
SW = 'sw.js'
README = 'README.md'

html = io.open(INDEX, encoding='utf-8').read()
sw = io.open(SW, encoding='utf-8').read()
readme = io.open(README, encoding='utf-8').read()

changed = []


def once(name, hay, old, new):
    n = hay.count(old)
    if n != 1:
        raise SystemExit('FAIL %s — 패턴 %d회 발견' % (name, n))
    changed.append(name)
    return hay.replace(old, new, 1)


# ── 1) 머리 주석 ───────────────────────────────────────────────
OLD_HEAD = u"""/* ── 공식 링크 — 휴대폰에서는 앱으로, 없으면 공식 웹으로 ─────────────────
   플라이 블루(에어프랑스·KLM)와 골 스마일즈(GOL)는 공식 앱을 먼저 열어 본다.
   · <a href> 는 언제나 공식 웹(https) 주소다. 홈 화면 앱(standalone)·인앱 WebView 는
     <a href="intent://…"> 를 조용히 무시해 '눌러도 아무 반응 없음'이 되므로, 링크 자체는 늘 웹으로 살려 둔다.
   · 안드로이드에서 누른 순간에만 아래 클릭 처리(mlAppOpen)가 intent:// 를 한 번 시도하고,
     1,200ms 안에 화면이 넘어가지 않으면(앱이 없거나 intent 를 무시한 경우) 공식 웹으로 넘어간다.
   · 아이폰·데스크톱: 공식 웹 주소 그대로(새 탭). 아이폰은 유니버설 링크가 있으면 사파리가 앱으로 넘긴다. */"""
NEW_HEAD = u"""/* ── 공식 링크 — 휴대폰에서는 앱으로, 없으면 공식 웹으로 ─────────────────
   ⑥ 항공특가 · ⑦ 땡처리 · ⑧ 마일리지발권 에 나오는 항공사·예약처 링크는 그 공식 앱을 먼저 열어 본다.
   · <a href> 는 언제나 공식 웹(https) 주소다. 홈 화면 앱(standalone)·인앱 WebView 는
     <a href="intent://…"> 를 조용히 무시해 '눌러도 아무 반응 없음'이 되므로, 링크 자체는 늘 웹으로 살려 둔다.
   · 안드로이드에서 누른 순간에만 아래 클릭 처리(mlAppOpen)가 intent:// 를 한 번 시도하고,
     1,200ms 안에 화면이 넘어가지 않으면(앱이 없거나 intent 를 무시한 경우) 공식 웹으로 넘어간다.
   · 아이폰·데스크톱: 공식 웹 주소 그대로(새 탭). 아이폰은 유니버설 링크가 있으면 사파리가 앱으로 넘긴다. */"""
html = once('head-comment', html, OLD_HEAD, NEW_HEAD)

# ── 2) 패키지 표 + 해석 함수 ────────────────────────────────────
ANCHOR = u"""var ML_APP_LINK={flyingblue:'www.airfrance.com/home',smiles:'www.smiles.com.br/'};"""

MAP = ANCHOR + u"""
/* ── ⑥⑦⑧ 항공사·예약처 공식 안드로이드 앱 (2026-11-27 Google Play 실측) ──────────
   링크 도메인 → 공식 앱 패키지. 값은 전부 play.google.com/store/apps/details?id=… 에서
   앱 이름·개발자를 확인하고, 대한민국 스토어에서 설치되는 것만 넣었다(추측 없음).
   공식 앱이 없거나 스토어에서 확인되지 않은 곳(티키티킷 · 일본 트랜스오션 · 스카이마크 · 후지드림 ·
   AIRDO · 솔라시드 · 중국남방 · 춘추 · 산동 · 칭다오 · 샤먼 · 룽에어 · 길상 · Avios)은 넣지 않았다 —
   넣어 봐야 누를 때마다 1.2초를 버리고 결국 공식 웹으로 간다. */
var FL_APP_PKG={
  /* 국내 항공사 */
  'koreanair.com':'com.koreanair.passenger',
  'flyasiana.com':'com.ssm.asiana',
  'airbusan.com':'com.airbusan.gcm',
  'jinair.com':'com.jinair.android',
  'jejuair.net':'com.parksmt.jejuair.android16',
  'eastarjet.com':'com.eastarjet.eastarjet',
  'trinityairways.com':'com.twayair.m.app',
  'flyairseoul.com':'com.asianaidt.airseoul',
  'airpremia.com':'com.airpremia.lua',
  /* 일본 항공사 */
  'jal.co.kr':'jp.co.jal.dom',
  'jal.co.jp':'jp.co.jal.dom',
  'ana.co.kr':'jp.co.ana.android.tabidachi',
  'ana.co.jp':'jp.co.ana.android.tabidachi',
  'flypeach.com':'com.flypeach.flypeach',
  'jetstar.com':'com.ink.jetstar.mobile.app',
  'starflyer.jp':'jp.starflyer.bookingapp',
  /* 중화권 항공사 */
  'cathaypacific.com':'com.xs2theworld.cxmobile',
  'hkexpress.com':'com.hkexpress.android',
  'ceair.com':'com.ceair.global',
  'airchina.kr':'com.rytong.airchina',
  'airchina.com':'com.rytong.airchina',
  'china-airlines.com':'com.chinaairlines.mobile30',
  'evaair.com':'com.evaair.android',
  'starlux-airlines.com':'com.starlux.cale',
  'tigerairtw.com':'com.tigerair',
  'juneyaoair.com':'org.zywx.wbpalmstar.widgetone.uex11296876',
  'airmacau.com.mo':'com.neusoft.airmacau',
  'greaterbay-airlines.com':'com.greaterbay.aom',
  /* 동남아 항공사 */
  'vietjetair.com':'com.vietjetair.vjmobileapp',
  'vietnamairlines.com':'com.vietnamairlines.android.app',
  'singaporeair.com':'com.amadeus.merci.client.ui',
  'flyscoot.com':'com.flyscoot.android',
  'philippineairlines.com':'com.pal.dx',
  'cebupacificair.com':'com.inkglobal.cebu.android',
  'malaysiaairlines.com':'aero.sita.lab.resmobileweb.android.mh',
  'thaiairways.com':'com.thaiairways.mobile',
  'bangkokair.com':'com.bangkokairways.main',
  'airasia.com':'com.airasia.mobile',
  /* 예약처·비교 사이트 */
  'trip.com':'ctrip.english',
  'skyscanner.co.kr':'net.skyscanner.android.main',
  'modetour.com':'com.modetour.m',
  'ttang.com':'com.com072.app072dotcom',
  'ybtour.co.kr':'kr.co.ybtour.mobile.ybtourApp',
  'hanatour.com':'com.hanatour.dotcom',
  /* ⑧ 마일리지 프로그램 */
  'flyingblue.com':'com.airfrance.android.dinamoprd',
  'smiles.com.br':'com.br.smiles',
  'virginatlantic.com':'com.virginatlantic.app',
  'delta.com':'com.delta.mobile.android',
  'lifemiles.com':'com.mobile.lifemiles',
  'aircanada.com':'com.aircanada',
  'miles-and-more.com':'com.plannet.milesandmoreapp',
  'united.com':'com.united.mobile.android',
  'turkishairlines.com':'com.turkishairlines.mobile',
  'aa.com':'com.aa.android',
  'alaskaair.com':'com.alaskaairlines.android',
  'qantas.com':'au.com.qantas.qantas',
  'jetblue.com':'com.jetblue.JetBlueAndroid',
  'etihad.com':'com.mttnow.android.etihad',
  'emirates.com':'com.emirates.ek.android'
};
/* 앱이 그 주소를 직접 받는 곳 — https://{도메인}/.well-known/assetlinks.json 에 같은 패키지가
   등록돼 있는 도메인만 적었다(2026-11-27 확인). 크롬은 확인되지 않은 https 주소는 앱으로 넘기지 않고
   그대로 웹에서 열기 때문에, 여기 있는 곳만 주소까지 넘겨 앱의 그 화면으로 들어간다.
   값이 문자열이면 앱이 받는 주소가 따로 있다는 뜻이다(플라이 블루 → 에어프랑스 앱 www.airfrance.com/home). */
var FL_APP_DEEP={
  'www.jejuair.net':1,
  'ana.co.jp':1,'www.ana.co.jp':1,
  'cathaypacific.com':1,'www.cathaypacific.com':1,
  'hkexpress.com':1,'www.hkexpress.com':1,
  'www.starlux-airlines.com':1,
  'www.vietjetair.com':1,
  'singaporeair.com':1,'www.singaporeair.com':1,
  'cebupacificair.com':1,'www.cebupacificair.com':1,
  'malaysiaairlines.com':1,'www.malaysiaairlines.com':1,
  'airasia.com':1,'www.airasia.com':1,
  'kr.trip.com':1,'trip.com':1,'www.trip.com':1,
  'skyscanner.co.kr':1,'www.skyscanner.co.kr':1,
  'virginatlantic.com':1,'www.virginatlantic.com':1,
  'delta.com':1,'www.delta.com':1,
  'aircanada.com':1,'www.aircanada.com':1,
  'miles-and-more.com':1,'www.miles-and-more.com':1,
  'aa.com':1,'www.aa.com':1,
  'alaskaair.com':1,'www.alaskaair.com':1,
  'qantas.com':1,'www.qantas.com':1,
  'jetblue.com':1,'www.jetblue.com':1,
  'smiles.com.br':1,'www.smiles.com.br':1,
  'flyingblue.com':'www.airfrance.com/home'
};
function flAppHost(href){var m=/^https?:\\/\\/([^\\/?#]+)/i.exec(String(href||''));return m?m[1].toLowerCase():''}
/* 링크 주소에서 표에 있는 도메인을 찾는다 — mfly.ybtour.co.kr → ybtour.co.kr, kr.trip.com → kr.trip.com */
function flAppBase(href){
  var h=flAppHost(href);if(!h)return '';
  var p=h.split('.'),i,d;
  for(i=0;i<p.length-1;i++){d=p.slice(i).join('.');if(FL_APP_PKG[d])return d}
  return '';
}
/* 안드로이드 인텐트 — 앱이 주소를 받는 곳은 VIEW 로 그 화면까지, 나머지는 주소 없이 패키지만 지정해
   앱 첫 화면을 연다. 둘 다 앱이 없으면 크롬이 S.browser_fallback_url(공식 웹)로 넘어간다. */
function flAppIntentFor(base,href){
  var pkg=(base&&FL_APP_PKG[base])||'';if(!pkg)return '';
  var fb=';S.browser_fallback_url='+encodeURIComponent(href);
  var host=flAppHost(href),deep=FL_APP_DEEP[host]||FL_APP_DEEP[base];
  if(deep){
    var rest=(typeof deep==='string')?deep:String(href).replace(/^https?:\\/\\//,'').replace(/#.*$/,'');
    return 'intent://'+rest+'#Intent;scheme=https;action=android.intent.action.VIEW'
      +';category=android.intent.category.BROWSABLE;package='+pkg+fb+';end';
  }
  return 'intent://#Intent;package='+pkg+';action=android.intent.action.MAIN'
    +';category=android.intent.category.LAUNCHER'+fb+';end';
}"""
html = once('pkg-map', html, ANCHOR, MAP)

# ── 3) 클릭 위임 확장 ───────────────────────────────────────────
OLD_CLICK = u"""document.addEventListener('click',function(e){
  var t=e.target;
  var a=(t&&t.closest)?t.closest('a[data-ml-app]'):null;
  if(!a)return;
  if(!/Android/i.test(mlUA()))return;              /* 아이폰·데스크톱은 기본 링크(새 탭) 그대로 */
  var p={key:a.getAttribute('data-ml-app'),url:a.getAttribute('href')||'',appWeb:a.getAttribute('data-app-web')||''};
  var intent=mlAppIntent(p);
  if(!intent)return;
  e.preventDefault();
  if(e.stopPropagation)e.stopPropagation();        /* 카드 '날짜 상세' 시트가 함께 열리지 않게 */
  mlAppOpen(mlAppWeb(p),intent);
},true);"""

NEW_CLICK = u"""document.addEventListener('click',function(e){
  var t=e.target;
  var a=(t&&t.closest)?t.closest('a[data-ml-app]'):null;
  if(a){
    if(!/Android/i.test(mlUA()))return;            /* 아이폰·데스크톱은 기본 링크(새 탭) 그대로 */
    var p={key:a.getAttribute('data-ml-app'),url:a.getAttribute('href')||'',appWeb:a.getAttribute('data-app-web')||''};
    var intent=mlAppIntent(p);
    if(!intent)return;
    e.preventDefault();
    if(e.stopPropagation)e.stopPropagation();      /* 카드 '날짜 상세' 시트가 함께 열리지 않게 */
    mlAppOpen(mlAppWeb(p),intent);
    return;
  }
  /* ⑥⑦⑧ 항공사·예약처 — 표(FL_APP_PKG)에 있는 도메인이면 안드로이드에서 그 앱을 먼저 열어 본다.
     href 는 늘 공식 웹(https) 그대로 두고(아이폰·데스크톱은 손대지 않는다), 앱이 없으면 1.2초 뒤
     누른 주소 그대로 넘어간다. 카드 행이 함께 열리지 않도록 전파도 막는다. */
  var b=(t&&t.closest)?t.closest('a[href]'):null;
  if(!b||!b.getAttribute)return;
  var href=b.getAttribute('href')||'';
  if(!/^https?:\\/\\//i.test(href))return;
  var base=flAppBase(href);
  if(!base)return;
  if(!/Android/i.test(mlUA()))return;
  var appIntent=flAppIntentFor(base,href);
  if(!appIntent)return;
  e.preventDefault();
  if(e.stopPropagation)e.stopPropagation();
  mlAppOpen(href,appIntent);
},true);"""
html = once('click-delegate', html, OLD_CLICK, NEW_CLICK)

# ── 4) ⑧ 안내문 ────────────────────────────────────────────────
OLD_NOTE = u"""function mlAppsNote(){
  return /Android/i.test(mlUA())
    ? '<p class="pm-ds-apphint">안드로이드에서는 <b>플라이 블루</b>·<b>골 스마일즈</b>를 누르면 해당 공식 앱이 설치된 경우 앱으로 열리고, 앱이 없거나 앱이 열리지 않는 화면(인앱 브라우저 등)에서는 공식 웹으로 자동 이동합니다.</p>'
    : '';
}"""
NEW_NOTE = u"""function mlAppsNote(){
  return /Android/i.test(mlUA())
    ? '<p class="pm-ds-apphint">안드로이드에서는 <b>항공사·마일리지 프로그램</b> 링크를 누르면 그 공식 앱이 설치된 경우 앱으로 열립니다(앱이 그 주소를 직접 받는 곳은 해당 화면, 나머지는 앱 첫 화면). ⑥⑦⑧ 의 모든 항공사·예약처 링크에 같은 방식이 걸려 있고, 앱이 없거나 앱을 열 수 없는 화면(인앱 브라우저 등)에서는 공식 웹으로 자동 이동합니다.</p>'
    : '';
}"""
html = once('apps-note', html, OLD_NOTE, NEW_NOTE)

# ── 5) ⑥ 예약 창 안내 한 줄 ─────────────────────────────────────
OLD_FBTEXT = u"""    :((!hasOff?'이 편의 항공사 공식 홈페이지 주소가 확인되지 않아 써드파티로만 연결합니다. ':'')+'공홈과 써드파티는 같은 좌석이라도 운임 조건·수수료가 다를 수 있습니다. 결제·취소 조건은 연 페이지에서 확인하세요.');"""
NEW_FBTEXT = u"""    :((!hasOff?'이 편의 항공사 공식 홈페이지 주소가 확인되지 않아 써드파티로만 연결합니다. ':'')+'공홈과 써드파티는 같은 좌석이라도 운임 조건·수수료가 다를 수 있습니다. 결제·취소 조건은 연 페이지에서 확인하세요.');
  if(/Android/i.test(mlUA()))$('flbkNote').textContent+=' 안드로이드에서 공식 앱이 설치돼 있으면 위 버튼이 그 앱으로 먼저 열립니다(항공사 공홈은 앱 첫 화면).';"""
html = once('flbk-note-text', html, OLD_FBTEXT, NEW_FBTEXT)

# ── 6) sw.js 버전 ──────────────────────────────────────────────
OLD_VER = u"const VERSION = 'teambusan-v5-2026-11-27z234';"
NEW_VER = u"const VERSION = 'teambusan-v5-2026-11-27z235';"
sw = once('sw-version', sw, OLD_VER, NEW_VER)

# ── 7) README ─────────────────────────────────────────────────
OLD_R1 = u"""- **⑥** 직항만 보기, 장시간 경유(12h+·20h+) 경고, 병합 이력 접기, 날짜 칸·노선 행에서 항공 검색 링크.
- **⑦** 공동구매·특가 채널 표시, 기간형 상품 표시, `목록 → 상품 선택` · `성인 2명부터` · `미확인` 주의 배지."""
NEW_R1 = u"""- **⑥** 직항만 보기, 장시간 경유(12h·20h+) 경고, 병합 이력 접기, 날짜 칸·노선 행에서 항공 검색 링크.
  항공사 공홈·트립닷컴·스카이스캐너 링크는 안드로이드에서 그 공식 앱으로 먼저 열립니다.
- **⑦** 공동구매·특가 채널 표시, 기간형 상품 표시, `목록 → 상품 선택` · `성인 2명부터` · `미확인` 주의 배지.
  모두투어·땡처리닷컴·노랑풍선·하나투어 상품 링크도 안드로이드에서 각 사 공식 앱으로 먼저 열립니다."""
readme = once('readme-tabs', readme, OLD_R1, NEW_R1)

OLD_R2 = u"""  항공사 「공식」 링크(href)는 늘 공식 웹(https)이고, 안드로이드에서 누르면 그 앱(골 스마일즈 `com.br.smiles` ·
  플라이 블루 `com.airfrance.android.dinamoprd`)을 `intent://` 로 먼저 열어 본 뒤 1.2초 안에 앱이 뜨지 않으면
  공식 웹으로 넘어갑니다(홈 화면 앱·인앱 WebView 에서 `intent://` 가 무시돼도 먹통이 되지 않게)."""
NEW_R2 = u"""  항공사 「공식」 링크(href)는 늘 공식 웹(https)이고, 안드로이드에서 누르면 그 앱을 `intent://` 로 먼저 열어 본 뒤
  1.2초 안에 앱이 뜨지 않으면 공식 웹으로 넘어갑니다(홈 화면 앱·인앱 WebView 에서 `intent://` 가 무시돼도 먹통이 되지 않게).

### ⑥⑦⑧ 항공사·예약처 안드로이드 앱 딥링크 (2026-11-27)

- `index.html` 의 `FL_APP_PKG` 가 링크 도메인 → 공식 앱 패키지 표(56곳)이고, 문서 클릭 위임이 표에 있는
  도메인의 `<a href="https://…">` 를 안드로이드에서만 가로채 `intent://` 로 앱을 연다. href·`target="_blank"` 는
  그대로라 아이폰·데스크톱은 예전처럼 새 탭에서 공식 웹이 열린다.
- `FL_APP_DEEP` 은 앱이 그 주소를 직접 받는 곳(`/.well-known/assetlinks.json` 에 같은 패키지가 등록된 도메인)이다.
  이곳은 `intent://{host}{path}#Intent;scheme=https;action=VIEW;category=BROWSABLE;package=…;S.browser_fallback_url=…;end`
  로 앱의 그 화면까지 들어가고, 나머지 앱은 크롬이 확인되지 않은 https 주소를 앱으로 넘기지 않으므로
  주소 없이 `intent://#Intent;package=…;action=MAIN;category=LAUNCHER;…;end` 로 앱 첫 화면을 연다.
- 패키지는 전부 `play.google.com/store/apps/details?id=…` 에서 앱 이름·개발자를 확인하고 대한민국 스토어에서
  설치되는 것만 넣었다. 공식 앱이 없거나 스토어에서 확인되지 않은 곳(티키티킷 · 일본 트랜스오션 · 스카이마크 ·
  후지드림 · AIRDO · 솔라시드 · 중국남방 · 춘추 · 산동 · 칭다오 · 샤먼 · 룽에어 · 길상 · Avios)은 표에 없어
  예전처럼 공식 웹이 바로 열린다.
- 안드로이드에서 앱이 없으면 `S.browser_fallback_url`(누른 주소 그대로)로 공식 웹이 열리고, 인앱 WebView 처럼
  `intent://` 자체를 무시하는 화면에서는 1.2초 뒤 같은 주소로 넘어간다."""
readme = once('readme-⑧', readme, OLD_R2, NEW_R2)

io.open(INDEX, 'w', encoding='utf-8').write(html)
io.open(SW, 'w', encoding='utf-8').write(sw)
io.open(README, 'w', encoding='utf-8').write(readme)

print('패치 완료:', ', '.join(changed))
