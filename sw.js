/* TEAM-부산 호텔·항공 요금 달력 — 서비스 워커 (2026-11-22 z25 · ③ 아코르 동남아 196곳 × 365일 실측 병합 — ③ 51→247곳, ① 호텔럭스와 겹치는 7곳 이중 연결)
   · z25 (2026-11-22) — ③ 아코르에 동남아 196곳(태국 102·베트남 55·싱가포르 39, a52~a247) 365일 실측 병합. 요금 기준은 세금 포함 KRW 1박 최저 표시가(157곳 ALL 회원 요금 포함 · 6번 담당 39곳은 비회원 공개 최저가). ③ 은 247곳이 되고, ① 호텔럭스에 있는 7곳(페어몬트 방콕 수쿰윗·페어몬트 싱가포르·래플스 싱가포르·래플스 센토사·소피텔 싱가포르 2곳·만다이 by 반얀트리)은 양방향 「💎 호텔럭스 ↔ 🏨 아코르 공홈」 선택 창. ④ 아워드 포인트 모드의 「2.7만P원」 중복 표기 수정. 알림 오탐 차단 보강(첫 관측 호텔·초저가 기준)
   · z24 (2026-11-21) — ④ 메리어트 중국·홍콩·마카오 40곳(m01~m40) 아워드 포인트 12,175칸 병합(2026-11-21 marriott.com 아워드 캘린더 365일 실측, 3곳은 Standard 아워드 연중 전무·전 호텔 2027-11-06~30은 예약창 밖 null) · 「아워드 포인트」 표시 모드·🎟️ 35k/50k 필터·상세 배지가 중국 호텔까지 판단 · 콤보(청두·시안·톈진·광저우 등) 🎫 35k / 🎫 35k(+○k) 배지 · ④ 안내문의 '한·일 22곳·6,629칸' 표기를 실측 기준으로 현행화
   · z23 (2026-11-21) — 예약처 두 곳 창에서 채널별 그 날짜 요금을 버튼마다 나란히(④ 공홈 검색가 ↔ ① VIP 요금 · ① 탭 자료는 필요할 때 한 번 받아 채움, 미조사는 「미실측」) · 이중 예약처 칸으로도 「선택일 호텔 비교」 활성 · 390px 활성 탭 자동 스크롤 · ④ 라벨 메리어트 통일 · USD 표시 '$156 · 환산 전 ₩…', 목록 도시명 중복 제거
   · 앱 셸(index.html·manifest·아이콘)은 미리 저장
   · data/app/*.json · data/history/*.json 은 네트워크 우선(항상 새 값 시도) → 실패하면 저장본
   · 오프라인에서도 마지막으로 본 탭·달력이 열리고, 저장본이 없으면 안내 문구를 보여 준다 */
const VERSION = 'teambusan-v5-2026-11-22z25';
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
  /* cache:'no-cache' — GitHub Pages 의 HTTP 캐시(max-age=600)를 우회해 새로고침 즉시 최신본을 받는다 */
  return fetch(req, { cache: 'no-cache' }).then(function (res) {
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
