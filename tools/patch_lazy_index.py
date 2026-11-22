#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""index.html 을 **탭별 JSON 지연 로딩** 구조로 한 번 바꾸는 패치 도구.

이 도구는 2026-11-19 의 4단계(HTML 경량화) 1회용 패치다. 이미 패치된 파일에는
아무 것도 하지 않는다(멱등). 데이터 값은 건드리지 않는다 — `const DB` 의 호텔 배열을
비우고 집계값(counts)을 넣으며, `const FLIGHTS` / `const TTANG` 은 빈 골격으로 둔다.
실제 값은 `python3 tools/master_db.py inject` 가 `data/app/*.json` 에 쓴다.

사용법 (저장소 루트에서):
    python3 tools/patch_lazy_index.py --dry-run
    python3 tools/patch_lazy_index.py
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

MARK = 'DATA_ROOT='  # 패치 여부 표식


def literal_span(src, name):
    m = re.search(r'\bconst\s+' + re.escape(name) + r'\s*=\s*', src)
    if not m:
        raise SystemExit('const %s 를 찾지 못했습니다.' % name)
    i = m.end()
    while src[i] not in '{[':
        i += 1
    opener = src[i]
    closer = '}' if opener == '{' else ']'
    depth, in_str, esc, j = 0, False, False, i
    while j < len(src):
        c = src[j]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return i, j + 1
        j += 1
    raise SystemExit('const %s 의 JSON 이 닫히지 않았습니다.' % name)


FLIGHTS_SKELETON = ('{"patterns":[],"months":[],"weeks":[],"counts":{"total":0},"routes":[],'
                    '"noSale":[],"notes":{},"bookingWindow":{}}')
TTANG_SKELETON = ('{"schema":"team-busan/pus-deals/1","observedAt":"","window":{},"channels":[],'
                  '"deals":[],"coverage":"","coverageOk":false}')

CSS = """/* ── 탭별 JSON 지연 로딩 표시 ───────────────────────────────── */
.dataloading{position:fixed;inset:0;z-index:9000;display:flex;align-items:center;justify-content:center;background:rgba(24,20,38,.42);backdrop-filter:blur(2px)}
.dataloading[hidden]{display:none}
.dl-box{min-width:248px;max-width:min(440px,88vw);background:#fff;border-radius:14px;padding:18px 20px 20px;box-shadow:0 18px 48px rgba(20,16,40,.28);text-align:center;font-size:11.5px;color:#4a4463;line-height:1.55}
.dl-box b{display:block;font-size:13px;margin-bottom:5px;color:#241d3a}
.dl-box span{color:#77718f}
.dl-spin{display:block;width:18px;height:18px;margin:0 auto 9px;border:2.5px solid #ded8f2;border-top-color:#7c3aed;border-radius:50%;animation:dlspin .8s linear infinite}
.dl-spin[hidden]{display:none}
@keyframes dlspin{to{transform:rotate(360deg)}}
.dl-box.err{border:1px solid #f0c8c8;background:#fff8f8}
.dl-box.err b{color:#b3261e}
.dl-retry{margin-top:11px;padding:6px 14px;border:1px solid #7c3aed;border-radius:8px;background:#7c3aed;color:#fff;font:inherit;font-weight:600;cursor:pointer}
.dl-retry:hover{background:#6d28d9}
@media(prefers-reduced-motion:reduce){.dl-spin{animation:none}}
"""

MARKUP = """<div id="dataLoading" class="dataloading" hidden role="status" aria-live="polite">
  <div class="dl-box" id="dlBox"><span class="dl-spin" id="dlSpin" aria-hidden="true"></span><b id="dlTitle">데이터 불러오는 중…</b><span id="dlSub"></span></div>
</div>
"""

LOADER = r"""/* ══ 데이터 지연 로딩 — 탭별 JSON ════════════════════════════════
   화면 코드와 집계값(DB.counts)만 index.html 에 두고, 호텔·항공·땡처리 데이터는
   탭에 처음 들어갈 때 data/app/*.json 을 fetch 해서 메모리에 캐시한다.
   ✈️+🏨 콤보는 ①~④ 호텔과 ⑤ 항공이 모두 필요하므로 없는 것만 병렬로 받는다. */
const DATA_ROOT='data/app/';
const PART_FILE={lux:'tab1_vip.json',accor:'tab2_accor.json',marriott:'tab4_marriott.json',flight:'tab5_flights.json',tt:'tab6_ttang.json'};
const HOTEL_TABS=['lux','accor','marriott'];
const DATA_READY={lux:false,accor:false,marriott:false,flight:false,tt:false};
const DATA_LOADING={};
function tabNeeds(tab){return tab==='combo'?HOTEL_TABS.concat(['flight']):[tab]}
function loadPart(tab){
  if(DATA_READY[tab])return Promise.resolve();
  if(DATA_LOADING[tab])return DATA_LOADING[tab];
  const url=DATA_ROOT+PART_FILE[tab];
  const p=fetch(url).then(function(r){
    if(!r.ok)throw new Error(url+' → HTTP '+r.status);
    return r.json();
  }).then(function(data){
    if(HOTEL_TABS.indexOf(tab)>=0){
      (data.hotels||[]).forEach(function(h){DB.hotels.push(h)});
      if(tab==='domestic'&&data.accor)DB.accor=data.accor;
    }else if(tab==='flight'){
      Object.assign(FLIGHTS,data);
    }else if(tab==='tt'){
      Object.assign(TTANG,data);ttBuildCh();ttBadge();
    }
    DATA_READY[tab]=true;
  });
  DATA_LOADING[tab]=p;
  p.catch(function(){}).then(function(){delete DATA_LOADING[tab]});
  return p;
}
let dlToken=0;
function dlShow(title,sub){
  const el=$('dataLoading');if(!el)return ++dlToken;
  const r=$('dlRetry');if(r)r.remove();
  $('dlBox').classList.remove('err');
  $('dlSpin').hidden=false;
  $('dlTitle').textContent=title||'데이터 불러오는 중…';
  $('dlSub').textContent=sub||'';
  el.hidden=false;
  return ++dlToken;
}
function dlHide(tok){
  if(tok!=null&&tok!==dlToken)return;
  const el=$('dataLoading');if(el)el.hidden=true;
}
function dlFail(err,tok){
  if(tok!=null&&tok!==dlToken)return;
  const el=$('dataLoading');if(!el)return;
  const hint=location.protocol==='file:'
    ?'file:// 로 열면 브라우저가 JSON fetch 를 막습니다. 로컬 서버(python3 -m http.server)나 라이브 주소로 열어 주세요.'
    :'잠시 뒤 다시 시도해 주세요. 계속 실패하면 data/app/*.json 배포 여부를 확인해 주세요.';
  $('dlBox').classList.add('err');
  $('dlSpin').hidden=true;
  $('dlTitle').textContent='데이터를 불러오지 못했습니다';
  $('dlSub').textContent=(err&&err.message?err.message+' · ':'')+hint;
  el.hidden=false;
  if(!$('dlRetry')){
    const b=document.createElement('button');
    b.type='button';b.className='dl-retry';b.id='dlRetry';b.textContent='다시 시도';
    b.addEventListener('click',function(){activate(st.tab)});
    $('dlBox').appendChild(b);
  }
}
function activate(tab){
  renderTabs();
  const missing=tabNeeds(tab).filter(function(t){return !DATA_READY[t]});
  if(!missing.length){dlHide();render();return}
  const tok=dlShow((tabs[tab]&&tabs[tab].title)||'',
    missing.length>1
      ? '이 탭은 '+missing.length+'개 데이터(①~④ 호텔 · ⑤ 항공)가 함께 필요합니다 — 병렬로 불러오는 중입니다'
      : missing.map(function(t){return PART_FILE[t]}).join(', ')+' 만 불러옵니다');
  Promise.all(missing.map(loadPart)).then(function(){
    if(st.tab!==tab)return;
    dlHide(tok);render();
  }).catch(function(err){
    if(st.tab!==tab)return;
    dlFail(err,tok);
  });
}
"""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(argv)

    src = open(INDEX, encoding='utf-8').read()
    if MARK in src:
        print('이미 지연 로딩 패치가 적용되어 있습니다 — 바꾸지 않았습니다.')
        return 0

    master = json.load(open(MASTER, encoding='utf-8'))
    counts = master.get('counts') or {}
    da, db_ = literal_span(src, 'DB')
    olddb = json.loads(src[da:db_])
    meta = {
        'hotels': [],
        'sources': olddb.get('sources') or [],
        'built': olddb.get('built'),
        'voucherExpiry': olddb.get('voucherExpiry'),
        'extended': olddb.get('extended'),
        'accor': None,
        'counts': counts,
    }
    for k in ('hotels', 'sources', 'built', 'voucherExpiry', 'extended', 'accor'):
        if k in ('hotels', 'accor'):
            continue
        if meta[k] != olddb.get(k):
            raise SystemExit('DB.%s 가 master_db.json 과 다릅니다 — 먼저 verify 로 확인하세요.' % k)
    if len(olddb['hotels']) != counts.get('hotels'):
        raise SystemExit('호텔 수가 master counts 와 다릅니다 (%d vs %s)'
                         % (len(olddb['hotels']), counts.get('hotels')))

    # 1) 큰 데이터 리터럴 → 집계/골격
    out = src
    fa, fb = literal_span(out, 'FLIGHTS')
    ta, tb = literal_span(out, 'TTANG')
    da, db_ = literal_span(out, 'DB')
    meta_txt = json.dumps(meta, ensure_ascii=False, separators=(',', ':'))
    # 뒤쪽부터 바꿔 오프셋을 유지한다
    out = out[:ta] + TTANG_SKELETON + out[tb:]
    out = out[:fa] + FLIGHTS_SKELETON + out[fb:]
    out = out[:da] + meta_txt + out[db_:]

    # 2) 코드 수정
    #   ⑤ 항공 전체 건수는 데이터를 받은 뒤에 채워지므로 상수 대신 함수로 읽는다
    if out.count('const flTotal=FLIGHTS.counts.total;') != 1:
        raise SystemExit('flTotal 정의를 찾지 못했습니다.')
    out = out.replace('const flTotal=FLIGHTS.counts.total;',
                      'const flTotal=()=>FLIGHTS.counts.total;   /* 데이터를 fetch 한 뒤 채워지므로 함수로 읽는다 */')
    out = out.replace('KR(flTotal)', 'KR(flTotal())').replace('||flTotal;', '||flTotal();')
    edits = [
        # ⑥ 채널 이름 — 로딩 뒤에 다시 만든다
        ("(function(){const cs=(typeof TTANG!=='undefined'&&TTANG.channels)||[];cs.forEach(function(c){ttCh[c.key]=c.label})})();",
         "function ttBuildCh(){for(const k in ttCh)delete ttCh[k];((TTANG&&TTANG.channels)||[]).forEach(function(c){ttCh[c.key]=c.label})}"),
        # ⑥ 탭 머리 주석 — 데이터 위치가 바뀌었다
        ("   상품 데이터는 `const TTANG`(아래 별도 블록)에 있고 tools/master_db.py inject 가 채운다.",
         "   상품 데이터는 `data/app/tab6_ttang.json` 에 있고(⑥ 탭에 들어갈 때 fetch), tools/master_db.py inject 가 채운다."),
        # ⑥ 탭 배지 — 로딩 뒤에 실제 건수로 다시 채우고, 그 전에는 HTML 에 적힌 건수를 보여 준다
        ('<button class="tab" data-tab="tt" type="button">⑥ 땡처리 · 부산 출발 <b>0</b></button>',
         '<button class="tab" data-tab="tt" type="button">⑥ 땡처리 · 부산 출발 <b>3,857</b></button>'),
        # ⑥ 탭 배지 — 로딩 뒤에 채운다
        ("/* 첫 렌더 전에도 탭 배지 숫자가 실제 건수로 보이게 */\n(function(){const tb=document.querySelector('[data-tab=\"tt\"] b');if(tb)tb.textContent=KR(ttAll().length)})();",
         "/* ⑥ 탭 배지 숫자를 실제 건수로 (데이터를 받은 뒤 부른다) */\nfunction ttBadge(){const tb=document.querySelector('[data-tab=\"tt\"] b');if(tb)tb.textContent=KR(ttAll().length)}"),
        # 상단 지표 — 현재 탭에 받아 둔 호텔이 아니라 전체 집계값을 보여 준다
        (" $('statHotels').textContent=KR(allHotels.length);\n $('statDates').textContent=KR(allHotels.reduce((n,h)=>n+Object.keys(h.rates||{}).length,0));\n $('statVoucher').textContent=KR(allHotels.reduce((n,h)=>n+Object.keys(h.stayplus2||{}).length+Object.keys(h.stayplus3||{}).length,0));",
         " const DC=DB.counts||{};\n $('statHotels').textContent=KR(DC.hotels!=null?DC.hotels:allHotels.length);\n $('statDates').textContent=KR(DC.cells!=null?DC.cells:allHotels.reduce((n,h)=>n+Object.keys(h.rates||{}).length,0));\n $('statVoucher').textContent=KR(DC.stayplus!=null?DC.stayplus:allHotels.reduce((n,h)=>n+Object.keys(h.stayplus2||{}).length+Object.keys(h.stayplus3||{}).length,0));"),
        # 탭 전환 — 필요한 JSON 이 없으면 받은 뒤 그린다
        ("if(tab==='combo'&&cb.month!==st.month)cb.month=st.month;render()}",
         "if(tab==='combo'&&cb.month!==st.month)cb.month=st.month;activate(tab)}"),
        # 첫 화면 — ① 탭만 먼저 받는다
        ("\nrender();\n</script>", "\n" + LOADER + "/* 첫 화면 — ① VIP 탭 JSON 만 받아 그리고, 나머지는 탭에 들어갈 때 받는다 */\nactivate('lux');\n</script>"),
        # 상단 표기
        ('<span class="offline">● 100% 오프라인 · 데이터 내장</span>',
         '<span class="offline">● 정적 파일 · 탭별 JSON 지연 로딩</span>'),
        # 로딩 표시 CSS·마크업
        ("</style>\n</head>", CSS + "</style>\n</head>"),
        ("<body>\n", "<body>\n" + MARKUP),
    ]
    for old, new in edits:
        if out.count(old) != 1:
            raise SystemExit('치환 대상이 %d개입니다(1개여야 함): %r' % (out.count(old), old[:80]))
        out = out.replace(old, new)

    print('index.html  %d bytes → %d bytes (-%.1f MB, -%.0f%%)' % (
        len(src.encode()), len(out.encode()),
        (len(src) - len(out)) / 1048576.0,
        100.0 * (len(src) - len(out)) / len(src)))
    if args.dry_run:
        return 0
    tmp = INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        fp.write(out)
    os.replace(tmp, INDEX)
    print('index.html 패치 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
