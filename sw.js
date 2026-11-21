/* TEAM-부산 호텔·항공 요금 달력 — 서비스 워커 (2026-11-22 z32 · ⑦ 마일리지 14개 노선 × 양방향 × 12개월 = 336블록 완결 / ⑥ 땡처리 3,847건 · 44개 노선 / ③ 아코르 동남아 196곳 × 365일 실측)
   · z32 (2026-11-22) — 🌲 휴양림 전수 재수집(2026-11-22 07:13 KST · 185곳 · 7,460객실·사이트 · 71일 · 예약가능 102,647칸 · 직전 01:43 대비 새로 빈 자리 81칸)과 예약 버튼 수정: 예약 링크를 눌러도 안 열리던 문제를 고쳐 새 탭(window.open)이 막히는 인앱 브라우저·웹뷰에서는 같은 탭으로 이동합니다(데스크톱은 그대로 새 탭).
   · z31 (2026-11-22) — 모바일 탭을 4칸 폴더 그리드로: 390px에서 한 줄 가로 스크롤 대신 ①~④ / ⑤·콤보·⑥ / ⑦·발렛 세 줄에 열 개 탭이 모두 보입니다(좁은 화면 전용 짧은 탭 이름 — ④ 메리어트 · ⑤ 항공 · ⑥ 땡처리 · ⑦ 마일리지 · 🅿️ 발렛). 🔒 잠금 버튼은 통계 줄 아래에서 제목 줄 오른쪽 끝으로 옮겼습니다. 데스크톱 탭 줄과 긴 이름은 그대로.
   · z30 (2026-11-22) — ⑦ 마일리지(부산) 14개 노선 336블록(3·4·5번 수집분 병합) 완결: 부산발 미운항 5개 노선(FUK·HKG·SIN·HAN·SGN)과 하계 미개시 6개 노선(KIX·TAO·NGO·CTS·BKK·DAD 2027-04~11)을 노선 칩·달력·요약에 배지로 표시해 '미수집'과 구분. 왕복 후보는 귀국편(dir 1) 실제 좌석과 날짜로 맞춰 확인/좌석 없음/운항 없음/조회 불가/미수집을 나눠 적고, 귀국편 확인 후보를 앞에 놓음(가는 편의 '운항편 없음'·'좌석 없음'은 후보에서 제외) · 자료 data/mileage/captures/2026-11-22.json 336행, 병합은 tools/merge_mileage.py
   · z29 (2026-11-22) — ⑦ 마일리지(부산) 탭 신설: 부산/김해(PUS) 출발 노선의 날짜별 보너스 좌석(일반석 E · 프레스티지 P · 프레스티지 승급 U)을 노선별 12개월 달력으로 보여 줍니다. 자료는 항공사가 공개하는 보너스 좌석 현황(하루 1회 갱신·앞으로 360일)을 옮긴 스냅샷이고, 좌석 수량·수수료·기재는 원천에 없어 표시하지 않습니다. 왕복 후보·새로 열린 좌석(전일 대비)·마일 계산기(공제표) 포함. 자료는 data/app/tab8_mileage.json 지연 로딩, 수집은 tools/collect_mileage.py
   · z28 (2026-11-22) — 🌲 휴양림 탭 신설: 전국 185곳 자연휴양림의 숙소·야영장 빈자리를 숲나들e 월별 예약현황 스냅샷(2026-11-22 01:43 KST 수집 · 71일 · 7,460객실·사이트 · 예약가능 102,728칸)으로 목록·체크인 달력·월간 그리드에 표시. 권역·객실유형·인원·1~3박·금·토 체크인·새로 빈 자리 필터, 예약 버튼은 모두 숲나들e 공식 화면(휴양림별 페이지·월별현황조회)으로 연결 · 자료는 data/app/tab7_forest.json 지연 로딩(1.3MB)
   · z27 (2026-11-22) — ⑥ 땡처리 3,847건 · 44개 노선 전면 갱신(수집 2026-11-22 04:31~05:40 KST)
   · z26 (2026-11-22) — z25 병합의 문구·표시 후속 수정: ③ 스냅샷 기준(국내·한·중·일 11-16~20 / 동남아 196곳 11-21 20:50~21:25 KST) 현행화, ③ 카드 요금 근거를 「세금 포함 KRW 최저 표시가(ALL 회원 요금 포함 / 6번 39곳은 비회원 공개 최저가)」로 통일, 이중 연결 7곳의 ① 호텔럭스 채널에 그 날짜 VIP 요금 비교 표시, ③ 탭 안내문에 「1박 최저가 ↔ Stay Plus 결제액」 비교 문구
   · z25 (2026-11-22) — ③ 아코르에 동남아 196곳(태국 102·베트남 55·싱가포르 39, a52~a247) 365일 실측 병합. 요금 기준은 세금 포함 KRW 1박 최저 표시가(157곳 ALL 회원 요금 포함 · 6번 담당 39곳은 비회원 공개 최저가). ③ 은 247곳이 되고, ① 호텔럭스에 있는 7곳(페어몬트 방콕 수쿰윗·페어몬트 싱가포르·래플스 싱가포르·래플스 센토사·소피텔 싱가포르 2곳·만다이 by 반얀트리)은 양방향 「💎 호텔럭스 ↔ 🏨 아코르 공홈」 선택 창. ④ 아워드 포인트 모드의 「2.7만P원」 중복 표기 수정. 알림 오탐 차단 보강(첫 관측 호텔·초저가 기준)
   · z24 (2026-11-21) — ④ 메리어트 중국·홍콩·마카오 40곳(m01~m40) 아워드 포인트 12,175칸 병합(2026-11-21 marriott.com 아워드 캘린더 365일 실측, 3곳은 Standard 아워드 연중 전무·전 호텔 2027-11-06~30은 예약창 밖 null) · 「아워드 포인트」 표시 모드·🎟️ 35k/50k 필터·상세 배지가 중국 호텔까지 판단 · 콤보(청두·시안·톈진·광저우 등) 🎫 35k / 🎫 35k(+○k) 배지 · ④ 안내문의 '한·일 22곳·6,629칸' 표기를 실측 기준으로 현행화
   · z23 (2026-11-21) — 예약처 두 곳 창에서 채널별 그 날짜 요금을 버튼마다 나란히(④ 공홈 검색가 ↔ ① VIP 요금 · ① 탭 자료는 필요할 때 한 번 받아 채움, 미조사는 「미실측」) · 이중 예약처 칸으로도 「선택일 호텔 비교」 활성 · 390px 활성 탭 자동 스크롤 · ④ 라벨 메리어트 통일 · USD 표시 '$156 · 환산 전 ₩…', 목록 도시명 중복 제거
   · 앱 셸(index.html·manifest·아이콘)은 미리 저장
   · data/app/*.json · data/history/*.json 은 네트워크 우선(항상 새 값 시도) → 실패하면 저장본
   · 오프라인에서도 마지막으로 본 탭·달력이 열리고, 저장본이 없으면 안내 문구를 보여 준다 */
const VERSION = 'teambusan-v5-2026-11-22z32';
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
