/* TEAM-부산 호텔·항공 요금 달력 — 서비스 워커 (2026-11-20 · 🅿️ 발렛 · 🛫 공항 라운지(58장 전수 조사) 탭 · 6단계 PWA 셸 · ⑥ 땡처리 3,857건 · ⑤ 10,209건)
   · 앱 셸(index.html·manifest·아이콘)은 미리 저장
   · data/app/*.json · data/history/*.json 은 네트워크 우선(항상 새 값 시도) → 실패하면 저장본
   · 오프라인에서도 마지막으로 본 탭·달력이 열리고, 저장본이 없으면 안내 문구를 보여 준다 */
const VERSION = 'teambusan-v5-2026-11-20z25';
const SHELL = ['./', './index.html', './manifest.json',
  './icons/icon-180.png', './icons/icon-192.png', './icons/icon-512.png', './icons/icon-maskable-512.png'];
/* 오프라인 폴백은 캐시에 마지막으로 저장된 응답을 그대로 쓴다 */

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(VERSION).then(function (cache) {
      return Promise.all(SHELL.map(function (url) {
        return cache.add(new Request(url, { cache: 'reload' })).catch(function () { /* 파일 하나가 없어도 설치를 막지 않는다 */ });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

function isData(url) {
  return url.pathname.indexOf('/data/app/') >= 0 || url.pathname.indexOf('/data/history/') >= 0;
}

function offlineDoc() {
  const html = '<!doctype html><html lang="ko"><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<title>TEAM-부산 — 오프라인</title>'
    + '<body style="margin:0;background:#1b122b;color:#fff;font-family:-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',sans-serif;display:grid;place-items:center;min-height:100vh;padding:24px">'
    + '<div style="max-width:420px;text-align:center">'
    + '<div style="font-size:30px">◈</div><h1 style="font-size:17px;letter-spacing:-.03em">오프라인입니다</h1>'
    + '<p style="font-size:12.5px;line-height:1.7;color:#c4b5fd">한 번 이상 연 탭의 자료는 저장돼 있어 오프라인에서도 열립니다. '
    + '이 화면이 보이면 아직 저장본이 없는 상태입니다 — 연결된 뒤 새로고침하면 탭 자료를 받아 둡니다.</p>'
    + '<p style="font-size:11px;color:#8b86a3">자료는 조회 시점 스냅샷이며 실시간 가격 연결은 없습니다.</p>'
    + '<button onclick="location.reload()" style="margin-top:14px;border:0;border-radius:9px;padding:11px 18px;font-weight:800;background:#ddd6fe;color:#3b1a78">다시 시도</button>'
    + '</div></body></html>';
  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}

function networkFirst(req, event, kind) {
  return fetch(req).then(function (res) {
    if (res && res.ok) {
      const copy = res.clone();
      caches.open(VERSION).then(function (cache) { cache.put(req, copy); });
    }
    return res;
  }).catch(function () {
    return caches.match(req).then(function (hit) {
      if (hit) return hit;
      if (kind === 'doc') return offlineDoc();
      return new Response(JSON.stringify({ offline: true, error: 'offline' }),
        { status: 503, headers: { 'Content-Type': 'application/json; charset=utf-8' } });
    });
  });
}

function cacheFirst(req) {
  return caches.match(req).then(function (hit) {
    if (hit) {
      fetch(req).then(function (res) {
        if (res && res.ok) caches.open(VERSION).then(function (c) { c.put(req, res); });
      }).catch(function () {});
      return hit;
    }
    return fetch(req).then(function (res) {
      if (res && res.ok) {
        const copy = res.clone();
        caches.open(VERSION).then(function (c) { c.put(req, copy); });
      }
      return res;
    });
  });
}

self.addEventListener('fetch', function (event) {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (isData(url)) { event.respondWith(networkFirst(req, event, 'json')); return; }
  if (req.mode === 'navigate') { event.respondWith(networkFirst(req, event, 'doc')); return; }
  if (/\.(json|js|css|svg|png|webp|jpg|ico)(\?|$)/.test(url.pathname) || url.pathname.endsWith('/')) {
    event.respondWith(cacheFirst(req)); return;
  }
  event.respondWith(fetch(req).catch(function () { return caches.match(req); }));
});
