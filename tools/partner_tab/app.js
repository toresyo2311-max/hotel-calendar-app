/* ── ⑨ 외항사 마일 탭 ─────────────────────────────────────
   부산/김해(PUS)와 인천(ICN)을 떠나는 노선의 '보너스(마일) 좌석'을 항공사
   마일리지 프로그램별로 모아 둔 스냅샷입니다. 조회 사이트는 날짜·노선마다 등급별로 '예약 가능/불가'와 필요 마일,
   직항·경유 편수까지만 알려 줍니다. 좌석 수량·세금·수수료는 조회 사이트에 없어
   표시하지 않습니다(항공사 예약 화면에서 확인).
   예약은 언제나 각 프로그램의 공식 사이트로 보냅니다. */
var PMD={meta:null,programs:[],dests:[],rows:[],ready:false,progMap:{},destMap:{},byProg:{}};
var PDS={};                    /* 출발지별 자료 보관 — 부산·인천을 오갈 때 다시 받지 않는다 */
var pmBusy=false,pmErr='';
var pms={origin:'PUS',dir:0,alliance:'all',prog:'all',dest:'all',cabin:'all',direct:false,sort:'miles',view:'cal'};

function pmMeta(){return PMD||{}}
function pmOrigin(){return (pmMeta().origin)||{code:'PUS',name:'부산',full:'부산/김해(PUS)'}}
function pmOName(){return pmOrigin().name||'부산'}
function pmOCode(){return pmOrigin().code||'PUS'}
function pmDirText(dir){var n=pmOName(),c=pmOCode();return dir?(n+' 도착(→ '+c+')'):(n+' 출발('+c+' →)')}
function pmKey(o){return o?o.key:''}
function pmWon(n){return n==null?'—':KR(n)+'마일'}
function pmProg(key){return PMD.progMap[key]||null}

/* ── 공식 링크 — 휴대폰에서는 앱으로, 없으면 공식 웹으로 ────────────────────
   에어프랑스·KLM 플라이 블루만 공식 앱 딥링크를 쓴다.
   · 안드로이드: intent://…package=<구글 플레이의 공식 앱 패키지> + S.browser_fallback_url=<공식 웹>
     → 앱이 있으면 앱이 열리고, 없으면 크롬이 공식 웹으로 이어 준다.
   · 아이폰·데스크톱: 공식 웹 주소 그대로(새 탭). 아이폰은 유니버설 링크가 있으면 사파리가 앱으로 넘긴다.
   패키지 이름은 구글 플레이 'Air France - Book a flight'(AIRFRANCE S.A.) 페이지에서 확인한 값이다. */
var PM_AF_APP='com.airfrance.android.dinamoprd';
var PM_AF_WEB='https://wwws.airfrance.co.kr/';
function pmUA(ua){return String(ua==null?navigator.userAgent:ua)}
function pmAppHref(p,ua){
  var web=(p&&p.url)||'';
  if(!p||p.key!=='flyingblue')return web;
  if(!/Android/i.test(pmUA(ua)))return web;
  return 'intent://'+PM_AF_WEB.replace(/^https?:\/\//,'')
    +'#Intent;scheme=https;package='+PM_AF_APP
    +';S.browser_fallback_url='+encodeURIComponent(PM_AF_WEB)+';end';
}
function pmAppTarget(p){return (p&&p.key==='flyingblue'&&/Android/i.test(pmUA()))?'_self':'_blank'}
function pmDest(code){return PMD.destMap[code]||null}
function pmDestName(code){
  var d=pmDest(code);
  return d?(d.city+' '+code):code;
}
/* 자료 준비 — 프로그램·도시 색인과 프로그램별 건수를 한 번만 만든다 */
function pmPrep(){
  if(PMD.ready||!PMD.rows||!PMD.rows.length)return;
  PMD.progMap={};PMD.destMap={};PMD.byProg={};
  (PMD.programs||[]).forEach(function(p){PMD.progMap[p.key]=p;PMD.byProg[p.key]=[]});
  (PMD.dests||[]).forEach(function(d){PMD.destMap[d.code]=d});
  PMD.rows.forEach(function(r){
    var p=r[0];
    if(!PMD.byProg[p])PMD.byProg[p]=[];
    PMD.byProg[p].push(r);
  });
  PMD.ready=true;
}

/* ── 출발지(부산 PUS / 인천 ICN) 전환 ──────────────────────────
   부산 자료는 탭을 열 때 함께 받고(loadPart), 인천 자료는 처음 인천을 누를 때 한 번 받아
   PDS 에 보관한다. 오갈 때는 다시 받지 않고 화면만 갈아 끼운다. */
function pmRoot(){return (typeof DATA_ROOT!=='undefined'&&DATA_ROOT)?DATA_ROOT:'data/app/'}
function pmBust(){
  if(typeof DATA_BUST==='undefined')return '';
  return DATA_BUST['partner-mileage']||'';
}
function pmSwap(d){
  PMD=Object.assign({meta:null,programs:[],dests:[],rows:[],ready:false,progMap:{},destMap:{},byProg:{}},d);
  PMD.ready=false;pmPrep();
  pms.dest='all';pms.prog='all';
  renderPartner();
  var el=document.getElementById('pmCal');
  if(el&&el.scrollIntoView)el.scrollIntoView({block:'start',behavior:'smooth'});
}
function pmPickOrigin(code){
  if(pmBusy||code===pms.origin)return;
  PDS[pms.origin]=PMD;                      /* 지금 보던 자료는 그대로 남긴다 */
  if(PDS[code]){pms.origin=code;pmErr='';pmSwap(PDS[code]);return}
  pmBusy=true;pmErr='';pmRenderOrigin();
  var url=pmRoot()+'tab9_partner_mileage_icn.json'+(pmBust()?'?g='+pmBust():'');
  fetch(url).then(function(r){
    if(!r.ok)throw new Error(url+' → HTTP '+r.status);
    return r.json();
  }).then(function(d){
    if(typeof hcDecode==='function')d=hcDecode(d);
    PDS[code]=d;pms.origin=code;pmBusy=false;
    pmSwap(d);
  }).catch(function(){
    pmBusy=false;
    pmErr='인천 자료를 불러오지 못했습니다 — 잠시 뒤 다시 눌러 주세요.';
    pmRenderOrigin();
  });
}

/* 한 행 = [프로그램, 날짜, 최근확인, 도착/출발 코드, 이코, 프이, 비즈, 퍼스트]
   등급 값은 "" 또는 "직항편수:마일" (예: "0:9000" = 직항 9,000마일, "1:33000" = 1회 경유) */
function pmCabins(r){
  var out=[];
  var map=[['e','이코노미'],['p','프리미엄'],['b','비즈니스'],['f','퍼스트']];
  for(var i=0;i<4;i++){
    var v=r[4+i];
    if(!v)continue;
    var sp=v.split(':');
    out.push({k:map[i][0],name:map[i][1],stops:+sp[0],miles:+sp[1]});
  }
  return out;
}
function pmMinMiles(r){
  var cs=pmCabins(r),m=null;
  cs.forEach(function(c){if(m==null||c.miles<m)m=c.miles});
  return m;
}
function pmBestCabin(r,cabin){
  var cs=pmCabins(r),best=null;
  cs.forEach(function(c){
    if(cabin!=='all'&&c.k!==cabin)return;
    if(!best||c.miles<best.miles)best=c;
  });
  return best;
}
function pmDateKo(ds){
  var d=new Date(ds+'T12:00:00Z');
  var wd=['일','월','화','수','목','금','토'][d.getUTCDay()];
  return (d.getUTCMonth()+1)+'/'+d.getUTCDate()+'('+wd+')';
}
function pmCabinLabel(c){return c.k==='e'?'이코노미':c.k==='p'?'프리미엄 이코노미':c.k==='b'?'비즈니스':'퍼스트'}
function pmCabinShort(c){return c.k==='e'?'이코':c.k==='p'?'프이':c.k==='b'?'비즈':'퍼스트'}
function pmStopsText(n){return n===0?'직항':n+'회 경유'}

/* ── 필터 ─────────────────────────────────────────────────── */
function pmRows(){
  var out=[];
  (PMD.rows||[]).forEach(function(r){
    if(+r[8]!==pms.dir)return;                 /* 9번째 칸(인덱스 8) = 방향(0 출발·1 도착) */
    var p=pmProg(r[0]);
    if(!p)return;
    if(pms.alliance!=='all'&&p.alliance!==pms.alliance)return;
    if(pms.prog!=='all'&&r[0]!==pms.prog)return;
    if(pms.dest!=='all'&&r[3]!==pms.dest)return;
    var cs=pmCabins(r),hit=null;
    for(var i=0;i<cs.length;i++){
      if(pms.cabin!=='all'&&cs[i].k!==pms.cabin)continue;
      if(pms.direct&&cs[i].stops!==0)continue;
      if(!hit||cs[i].miles<hit.miles)hit=cs[i];
    }
    if(!hit)return;
    if(pms.direct){
      /* 직항만 — 고른 등급에 직항이 하나도 없으면 이 행은 뺀다 */
      var anyDirect=false;
      cs.forEach(function(c){
        if(pms.cabin!=='all'&&c.k!==pms.cabin)return;
        if(c.stops===0)anyDirect=true;
      });
      if(!anyDirect)return;
    }
    out.push({r:r,p:p,best:hit,cs:cs});
  });
  out.sort(function(a,b){
    if(pms.sort==='date')return a.r[1]<b.r[1]?-1:a.r[1]>b.r[1]?1:(a.best.miles-b.best.miles);
    return (a.best.miles-b.best.miles)||(a.r[1]<b.r[1]?-1:a.r[1]>b.r[1]?1:0);
  });
  return out;
}

/* ── 화면 ─────────────────────────────────────────────────── */
function renderPartner(){
  pmPrep();
  setDealPanels('partner-mileage');
  var p=document.getElementById('pmPanel');
  if(!p)return;
  pmRenderBanner();
  pmRenderKpi();
  pmRenderOrigin();
  pmRenderDir();
  pmRenderAlliance();
  pmRenderProgs();
  pmRenderDests();
  pmRenderBest();
  pmCalcInit();
  pmRenderView();
  pmRenderCal();
  pmRenderList();
  pmRenderNote();
}

function pmRenderBanner(){
  var b=document.getElementById('pmBanner');
  if(!b)return;
  var m=pmMeta(),w=pmWin();
  var dirTxt=pmDirText(pms.dir);
  var cnt=(PMD.rows||[]).length;
  var cOut=0,cIn=0;
  (PMD.rows||[]).forEach(function(r){if(+r[8]===0)cOut++;else cIn++});
  var colDays=pmDaysBetween(w.cFrom,w.cTo),allDays=pmDaysBetween(w.from,w.to);
  b.innerHTML='<b>'+esc(m.sourceLabel||'항공사 마일리지 프로그램별 보너스 좌석')+'</b> · 기준 <b>'+esc(m.observedLabel||'—')+'</b>'
    +' · 목표 <b>1년 '+KR(allDays)+'일</b>('+esc(w.from)+'~'+esc(w.to)+')'
    +' · 실측 수집 <b>'+KR(colDays)+'일</b>('+esc(w.cFrom)+'~'+esc(w.cTo)+') · '+esc(dirTxt)+' · '+KR(cnt)+'건'
    +' (출발 '+KR(cOut)+' · 도착 '+KR(cIn)+')'
    +'<span class="pm-b2">보너스 좌석은 실시간으로 변동됩니다. 예약 전 <b>각 항공사 공식 사이트에서 재확인</b>해 주세요. '
    +'조회 사이트는 노선·날짜마다 등급별 <b>예약 가능 여부와 필요 마일</b>만 알려 주며, 좌석 수량·세금·수수료는 알려 주지 않아 표시하지 않습니다. '
    +'표시된 마일은 조회 사이트가 그 등급에 보여 준 <b>최저값</b>이고, 경유편은 편수로 구분합니다. '
    +(colDays<allDays?'<b>'+esc(w.cTo)+'</b> 이후 '+KR(allDays-colDays)+'일은 조회 사이트가 비로그인 화면에 열어 주지 않아 <b>미수집</b>입니다 — 달력에 빗금으로 표시하고 값을 채우지 않았습니다(추측·보간 없음). 각 항공사 공식 사이트에서 직접 조회해 주세요.':'')+'</span>';
}

function pmRenderKpi(){
  var el=document.getElementById('pmKpi');
  if(!el)return;
  var all=(PMD.rows||[]);
  var dirRows=all.filter(function(r){return +r[8]===pms.dir});
  var progs={},dests={};
  dirRows.forEach(function(r){progs[r[0]]=1;dests[r[3]]=1});
  var cheapest=null;
  dirRows.forEach(function(r){
    var b=pmBestCabin(r,pms.cabin);
    if(b&&(!cheapest||b.miles<cheapest.c.miles))cheapest={r:r,c:b,p:pmProg(r[0])};
  });
  var withData=Object.keys(progs).length;
  el.innerHTML=''
    +'<div><span>수집 프로그램</span><b>'+KR(withData)+'</b><i>9개 중 · 나머지는 조회 사이트에 '+esc(pmOName())+' 자료 없음</i></div>'
    +'<div><span>보너스 좌석 행</span><b>'+KR(dirRows.length)+'</b><i>'+esc(pmOName())+(pms.dir?' 도착':' 출발')+' 방향</i></div>'
    +'<div><span>도시</span><b>'+KR(Object.keys(dests).length)+'</b><i>필터로 좁힐 수 있습니다</i></div>'
    +'<div class="new"><span>가장 적은 마일</span><b>'+(cheapest?KR(cheapest.c.miles):'—')+'</b><i>'
    +(cheapest?esc(pmDestName(cheapest.r[3]))+' · '+esc((cheapest.p&&(cheapest.p.short||cheapest.p.name))||'')+' '+esc(pmCabinShort(cheapest.c)):'—')+'</i></div>';
}

function pmRenderOrigin(){
  var el=document.getElementById('pmOrigin');
  if(!el)return;
  PDS[pms.origin]=PMD;
  var opts=[['PUS','부산'],['ICN','인천']];
  el.innerHTML=opts.map(function(o){
    var on=pms.origin===o[0];
    var d=PDS[o[0]];
    var n=d?(d.rows||[]).length:null;
    return '<button type="button" data-pm-origin="'+o[0]+'" class="'+(on?'on':'')+'" aria-pressed="'+(on?'true':'false')+'"'
      +' title="'+esc(o[1]+'('+o[0]+') 출발'+(n!=null?' · '+KR(n)+'건':''))+' ">'
      +esc(o[1])+'('+o[0]+')'+(n!=null?' <b>'+KR(n)+'</b>':'')+'</button>';
  }).join('');
  var h=document.getElementById('pmOriginHint');
  if(h)h.textContent=pmBusy?'자료 불러오는 중…':(pmErr||'');
}

function pmRenderDir(){
  var el=document.getElementById('pmDir');
  if(!el)return;
  var n0=0,n1=0;
  (PMD.rows||[]).forEach(function(r){if(+r[8]===0)n0++;else n1++});
  el.innerHTML='<button type="button" data-pm-dir="0" class="'+(pms.dir===0?'on':'')+'" aria-pressed="'+(pms.dir===0?'true':'false')+'">'+esc(pmOName())+' 출발 '+esc(pmOCode())+'→ <b>'+KR(n0)+'</b></button>'
    +'<button type="button" data-pm-dir="1" class="'+(pms.dir===1?'on':'')+'" aria-pressed="'+(pms.dir===1?'true':'false')+'">'+esc(pmOName())+' 도착 →'+esc(pmOCode())+' <b>'+KR(n1)+'</b></button>';
  var dc=document.getElementById('pmDirect');
  if(dc)dc.setAttribute('aria-pressed',pms.direct?'true':'false');
  var cs=document.getElementById('pmCabin');
  if(cs)cs.value=pms.cabin;
  var so=document.getElementById('pmSort');
  if(so)so.value=pms.sort;
}

function pmRenderAlliance(){
  var el=document.getElementById('pmAlliance');
  if(!el)return;
  var order=[['all','전체'],['skyteam','스카이팀'],['star','스타얼라이언스'],['oneworld','원월드'],['none','얼라이언스 없음']];
  el.innerHTML='<span class="pm-lab">동맹</span>'+order.map(function(o){
    var on=pms.alliance===o[0];
    return '<button type="button" class="chip'+(on?' on':'')+'" data-pm-alliance="'+o[0]+'" aria-pressed="'+(on?'true':'false')+'">'+esc(o[1])+'</button>';
  }).join('');
}

function pmRenderProgs(){
  var el=document.getElementById('pmProgs');
  if(!el)return;
  var counts={};
  (PMD.rows||[]).forEach(function(r){if(+r[8]===pms.dir)counts[r[0]]=(counts[r[0]]||0)+1});
  var html='<span class="pm-lab">프로그램</span>';
  var total=0;
  (PMD.programs||[]).forEach(function(p){total+=counts[p.key]||0});
  html+='<button type="button" class="chip'+(pms.prog==='all'?' on':'')+'" data-pm-prog="all" aria-pressed="'+(pms.prog==='all'?'true':'false')+'">전체 <b>'+KR(total)+'</b></button>';
  (PMD.programs||[]).forEach(function(p){
    var n=counts[p.key]||0;
    if(pms.alliance!=='all'&&p.alliance!==pms.alliance)return;
    var on=pms.prog===p.key;
    html+='<button type="button" class="chip'+(on?' on':'')+(n?'':' off')+'" data-pm-prog="'+esc(p.key)+'" aria-pressed="'+(on?'true':'false')+'"'
      +' title="'+esc(p.name+' · '+(p.allianceName||'')+' · '+(n?n+'건':'이 방향 자료 없음'))+'">'
      +esc(p.short||p.name)+' <b>'+KR(n)+'</b></button>';
  });
  el.innerHTML=html;
}

function pmRenderDests(){
  var el=document.getElementById('pmDests');
  if(!el)return;
  var best={};
  pmRows().forEach(function(x){
    var c=x.r[3];
    if(!best[c]||x.best.miles<best[c])best[c]=x.best.miles;
  });
  var codes=Object.keys(best).sort(function(a,b){return best[a]-best[b]});
  var html='<span class="pm-lab">도시</span>';
  html+='<button type="button" class="chip'+(pms.dest==='all'?' on':'')+'" data-pm-dest="all" aria-pressed="'+(pms.dest==='all'?'true':'false')+'">전체</button>';
  html+=codes.map(function(c){
    var on=pms.dest===c;
    return '<button type="button" class="chip'+(on?' on':'')+'" data-pm-dest="'+esc(c)+'" aria-pressed="'+(on?'true':'false')+'">'
      +esc(pmDestName(c))+' <b>'+KR(best[c])+'</b></button>';
  }).join('');
  el.innerHTML=html;
}

/* 도시별 최저 마일 요약 — 지금 조건에서 도시마다 가장 싼 한 건 */
function pmRenderBest(){
  var el=document.getElementById('pmBest');
  if(!el)return;
  var rows=pmRows();
  if(!rows.length){
    el.innerHTML='<div class="pm-empty">이 조건에 맞는 보너스 좌석이 없습니다.<br>'
      +'프로그램·등급·직항 조건을 바꾸거나, 아래 방향 버튼으로 반대 방향('+(pms.dir?'출발':'도착')+')을 눌러 보세요.</div>';
    return;
  }
  var best={};
  rows.forEach(function(x){
    var c=x.r[3];
    if(!best[c]||x.best.miles<best[c].miles)best[c]={miles:x.best.miles,r:x.r,cabin:x.best,prog:x.p};
  });
  var list=Object.keys(best).map(function(c){return {code:c,b:best[c]}})
    .sort(function(a,b){return a.b.miles-b.b.miles}).slice(0,12);
  el.innerHTML='<div class="pm-bhead">도시별 최저 마일 <span>'+KR(Object.keys(best).length)+'개 도시 중 싼 순서 12곳</span></div>'
    +'<div class="pm-bcards">'+list.map(function(o){
      var b=o.b,p=b.prog,c=b.cabin;
      return '<button type="button" class="pm-bcard" data-pm-dest="'+esc(o.code)+'">'
        +'<span class="d">'+esc(pmDestName(o.code))+'</span>'
        +'<span class="m">'+KR(b.miles)+'</span>'
        +'<span class="s">'+esc(p.short||p.name)+' · '+esc(pmCabinShort(c))+' · '+esc(pmStopsText(c.stops))+'</span>'
        +'<span class="t">'+esc(pmDateKo(b.r[1]))+' 기준</span></button>';
    }).join('')+'</div>';
}

function pmRenderList(){
  var el=document.getElementById('pmList');
  if(!el)return;
  var rows=pmRows();
  if(!rows.length)return void(el.innerHTML='');
  var limit=300;
  var shown=rows.slice(0,limit);
  el.innerHTML='<div class="pm-lhead">날짜별 보너스 좌석 <span>'+KR(rows.length)+'건'+(rows.length>limit?' 중 '+KR(limit)+'건 표시':'')+'</span></div>'
    +'<div class="pm-cards">'+shown.map(function(x){
      var r=x.r,p=x.p;
      var cs=x.cs.filter(function(c){return pms.cabin==='all'||c.k===pms.cabin})
        .filter(function(c){return !pms.direct||c.stops===0});
      return '<article class="pm-card" data-pm-day="'+esc(r[1])+'" title="눌러서 이 날짜 상세 보기">'
        +'<div class="top"><b>'+esc(pmDestName(r[3]))+'</b><span class="dt">'+esc(pmDateKo(r[1]))+'</span></div>'
        +'<div class="pg">'+esc(p.name)+'<span>'+esc(p.allianceName||'')+'</span></div>'
        +'<div class="cab">'+cs.map(function(c){
          return '<span class="cb '+c.k+'">'+esc(pmCabinShort(c))+' <b>'+KR(c.miles)+'</b> <i>'+esc(pmStopsText(c.stops))+'</i></span>';
        }).join('')+'</div>'
        +'<div class="foot"><span class="seen">최근 확인 '+esc(r[2])+'</span>'
        +'<span class="pm-footbtns"><button type="button" class="pm-open" data-pm-day="'+esc(r[1])+'">날짜 상세</button>'
        +'<a class="go" href="'+esc(pmAppHref(p))+'" target="'+pmAppTarget(p)+'" rel="noopener"'+(p.key==='flyingblue'?' title="'+esc(p.name+' 공식 앱 또는 공식 웹으로 엽니다')+'"':'')+'>'+esc(p.urlLabel||'공식 예약')+'</a></span></div>'
        +'</article>';
    }).join('')+'</div>';
}

function pmWord(t){return String(t==null?'':t).replace(/원천/g,'조회 사이트')}
function pmRenderNote(){
  var el=document.getElementById('pmNote');
  if(!el)return;
  var m=pmMeta();
  var cov=(m.coverage||[]).map(function(c){
    var d=(c.rowsIn!=null&&c.rowsOut!=null)?' (출발 '+KR(c.rowsOut)+' · 도착 '+KR(c.rowsIn)+')':'';
    return esc(pmWord(c.name))+' '+KR(c.rows)+d+(c.note?' — '+esc(pmWord(c.note)):'');
  });
  var have=(m.coverage||[]).filter(function(c){return c.rows>0}).length;
  var all=(m.coverage||[]).length||9;
  el.innerHTML='<details class="notefold">'
    +'<summary>📑 안내 및 조회 범위 보기 <small>'+all+'개 프로그램 중 자료 있는 곳 '+have+'곳 · 읽는 법</small></summary>'
    +'<div class="pm-notebody">'
    +'<b>수집 범위</b> — '+(cov.length?cov.join(' · '):'—')
    +'<p>조회 사이트마다 '+esc(pmOName())+' 노선을 얼마나 추적하는지가 다릅니다. 자료가 0건인 프로그램은 <b>보너스 좌석이 없다는 뜻이 아니라, 그 조회 사이트가 '+esc(pmOName())+' 노선을 추적하지 않는다는 뜻</b>입니다 — 해당 항공사 공식 사이트에서 직접 조회해 주세요.</p>'
    +'<p>국내선(김포·제주)은 국제선 여행과 성격이 달라 이 화면에서 뺐습니다. 필요 마일은 조회 사이트에 표시된 값이며, 같은 노선이라도 날짜·경유 편수·판매 조건에 따라 달라집니다. 세금·수수료는 마일과 별도입니다.</p>'
    +'</div></details>';
}

/* ── 이벤트 ───────────────────────────────────────────────── */
document.addEventListener('click',function(e){
  var t=e.target;
  if(!t||!t.closest)return;
  var og=t.closest('[data-pm-origin]');
  if(og){pmPickOrigin(og.getAttribute('data-pm-origin'));return}
  var d=t.closest('#pmDir button');
  if(d){pms.dir=+d.getAttribute('data-pm-dir');pms.dest='all';renderPartner();return}
  var al=t.closest('[data-pm-alliance]');
  if(al){pms.alliance=al.getAttribute('data-pm-alliance');pms.prog='all';renderPartner();return}
  var pg=t.closest('[data-pm-prog]');
  if(pg){pms.prog=pg.getAttribute('data-pm-prog');renderPartner();return}
  var ds=t.closest('[data-pm-dest]');
  if(ds){
    var v=ds.getAttribute('data-pm-dest');
    pms.dest=(v==='all'||pms.dest===v)?'all':v;
    renderPartner();
    var list=document.getElementById(pms.view==='cal'?'pmCal':'pmList');
    if(list&&pms.dest!=='all'&&list.scrollIntoView)list.scrollIntoView({block:'start',behavior:'smooth'});
    return;
  }
  if(t.closest('#pmDirect')){pms.direct=!pms.direct;renderPartner();return}
});
document.addEventListener('change',function(e){
  var t=e.target;
  if(!t||!t.id)return;
  if(t.id==='pmCabin'){pms.cabin=t.value;renderPartner()}
  else if(t.id==='pmSort'){pms.sort=t.value;renderPartner()}
});

/* ══ 달력 보기 ══════════════════════════════════════════════════════════════
   2026-11-22 한진님 지시: "달력 형식으로 1년치 한눈에" + "달력 날짜를 누르면 각 항공사
   연결해 주고 정보 볼 수 있도록".
   · 목표 창 = meta.dateFrom~dateTo(365일), 실제 수집 구간 = meta.collectedFrom~collectedTo.
     수집 구간 밖의 날은 값이 아니라 '미수집(공홈 조회)'으로 그린다 — 보간하지 않는다.
   · 수집 구간 안에서 그 날 표시가 없는 칸은 '—'(조회 사이트에 표시 없음)이다. 둘을 섞지 않는다. */

function pmP2(n){return (n<10?'0':'')+n}
function pmWin(){
  var m=pmMeta()||{};
  var from=m.dateFrom||'',to=m.dateTo||from;
  return {from:from,to:to,cFrom:m.collectedFrom||from,cTo:m.collectedTo||to};
}
function pmDaysBetween(a,b){
  if(!a||!b)return 0;
  var x=new Date(a+'T00:00:00Z'),y=new Date(b+'T00:00:00Z');
  return Math.round((y-x)/86400000)+1;
}
function pmToday(){
  var d=new Date();
  return d.getFullYear()+'-'+pmP2(d.getMonth()+1)+'-'+pmP2(d.getDate());
}
function pmDateLong(ds){
  var d=new Date(ds+'T12:00:00Z');
  var wd=['일','월','화','수','목','금','토'][d.getUTCDay()];
  return d.getUTCFullYear()+'년 '+(d.getUTCMonth()+1)+'월 '+d.getUTCDate()+'일('+wd+')';
}
function pmInRange(ds,a,b){return !!a&&!!b&&ds>=a&&ds<=b}

/* 창의 달 목록 (2026-11 ~ 2027-11 — 앞뒤가 걸친 달 포함) */
function pmMonthList(){
  var w=pmWin();
  if(!w.from||!w.to)return [];
  var y=+w.from.slice(0,4),m=+w.from.slice(5,7);
  var ey=+w.to.slice(0,4),em=+w.to.slice(5,7);
  var out=[],guard=0;
  while(guard++<40){
    out.push(y+'-'+pmP2(m));
    if(y===ey&&m===em)break;
    m++;if(m>12){m=1;y++}
  }
  return out;
}
function pmMonthCovered(mo){
  var w=pmWin();
  return !((mo+'-31')<w.cFrom||(mo+'-01')>w.cTo);
}

/* 지금 필터에 맞는 행을 날짜별로 묶는다 */
function pmDayMap(){
  var map={};
  pmRows().forEach(function(x){(map[x.r[1]]=map[x.r[1]]||[]).push(x)});
  return map;
}
function pmDayStat(list){
  var min=null,best=null;
  list.forEach(function(x){
    if(min==null||x.best.miles<min){min=x.best.miles;best=x.best}
  });
  return {min:min,best:best};
}
function pmCondText(){
  var p=pms.prog==='all'?'전체 프로그램':((pmProg(pms.prog)||{}).short||pms.prog);
  var d=pms.dest==='all'?'전체 도시':pmDestName(pms.dest);
  var c=pms.cabin==='all'?'모든 등급':pmCabinLabel({k:pms.cabin});
  return [p,d,c].join(' · ')+(pms.direct?' · 직항만':'');
}

function pmRenderView(){
  var el=document.getElementById('pmView');
  if(el){
    Array.prototype.forEach.call(el.querySelectorAll('[data-pm-view]'),function(b){
      var on=b.getAttribute('data-pm-view')===pms.view;
      b.className=on?'on':'';
      b.setAttribute('aria-pressed',on?'true':'false');
    });
  }
  var cal=document.getElementById('pmCal'),list=document.getElementById('pmList');
  if(cal)cal.hidden=pms.view!=='cal';
  if(list)list.hidden=pms.view!=='list';
}

/* 12(13)개월 한눈에 — 위에 월별 최저 마일 띠, 아래에 달마다 격자 */
function pmRenderCal(){
  var el=document.getElementById('pmCal');
  if(!el)return;
  if(pms.view!=='cal'){el.innerHTML='';return}
  var w=pmWin(),months=pmMonthList();
  if(!months.length){el.innerHTML='<div class="pm-empty">자료 기간 기준을 읽지 못했습니다.</div>';return}
  var map=pmDayMap();
  var monMin={};
  months.forEach(function(mo){monMin[mo]=null});
  Object.keys(map).forEach(function(ds){
    var mo=ds.slice(0,7);
    if(!(mo in monMin))return;
    var st=pmDayStat(map[ds]);
    if(st.min!=null&&(monMin[mo]==null||st.min<monMin[mo]))monMin[mo]=st.min;
  });
  var today=pmToday();
  var strip='<div class="pm-year" role="group" aria-label="월 바로가기 — 달마다 최저 마일">'
    + months.map(function(mo){
        var v=monMin[mo],cov=pmMonthCovered(mo);
        return '<button type="button" class="pm-ym'+(v!=null?' has':'')+(cov?'':' unc')+'" data-pm-jump="'+mo+'"'
          +' title="'+(cov?(v!=null?mo+' 최저 '+KR(v)+'마일':mo+' 표시 없음'):mo+' 미수집')+'">'
          +'<b>'+mo.slice(2,4)+'.'+(+mo.slice(5,7))+'</b>'
          +'<span>'+(cov?(v!=null?KR(v):'—'):'미수집')+'</span></button>';
      }).join('')+'</div>';
  var grids=months.map(function(mo){return pmMonthGrid(mo,map,w,today)}).join('');
  el.innerHTML=strip+grids
    +'<div class="pm-legend">'
    +'<span class="lg"><i class="pm-cell has e">7,000</i>최저 마일(등급 색: <b class="e">이코</b> <b class="p">프이</b> <b class="b">비즈</b> <b class="f">퍼스트</b>)</span>'
    +'<span class="lg"><i class="pm-cell none">—</i>조회 사이트에 표시 없음</span>'
    +'<span class="lg"><i class="pm-cell miss">미수집</i>수집 구간 밖</span>'
    +'</div>';
}

function pmMonthGrid(mo,map,w,today){
  var y=+mo.slice(0,4),m=+mo.slice(5,7);
  var startWd=new Date(Date.UTC(y,m-1,1)).getUTCDay();
  var days=new Date(Date.UTC(y,m,0)).getUTCDate();
  var cells=[],k;
  for(k=0;k<startWd;k++)cells.push(null);
  for(k=1;k<=days;k++)cells.push(k);
  var minV=null,collected=0,rows=0;
  var body='',cur='';
  cells.forEach(function(d,idx){
    if(idx%7===0)cur+='<tr>';
    var wd=idx%7;
    if(d==null){cur+='<td class="pm-blank"></td>';}
    else{
      var ds=mo+'-'+pmP2(d);
      var cls=['pm-cell'],inner='<span class="d">'+d+'</span>';
      if(wd===0)cls.push('sun');else if(wd===6)cls.push('sat');
      var inWin=pmInRange(ds,w.from,w.to),col=inWin&&pmInRange(ds,w.cFrom,w.cTo);
      var aria=pmDateLong(ds);
      if(ds===today)cls.push('today');
      if(!inWin){
        /* 목표 1년 창 밖(앞뒤로 걸친 달의 남는 날) — 미수집과 구분해 빈칸으로 둔다 */
        cls.push('out');
        aria+=' · 1년 창 밖';
      }else if(!col){
        cls.push('miss');
        inner+='<span class="t">미수집</span>';
        aria+=' · 미수집';
      }else{
        collected++;
        var list=map[ds]||[];
        if(!list.length){
          cls.push('none');inner+='<span class="t">—</span>';
          aria+=' · 조회 사이트에 표시 없음';
        }else{
          rows++;
          var st=pmDayStat(list);
          if(minV==null||st.min<minV)minV=st.min;
          cls.push('has','cb-'+st.best.k);
          inner+='<span class="m">'+KR(st.min)+'</span>'
            +'<span class="s">'+(st.best.stops===0?'직항':st.best.stops+'경유')+'</span>';
          aria+=' · 최저 '+KR(st.min)+'마일 · '+list.length+'건';
        }
      }
      cur+='<td><button type="button" class="'+cls.join(' ')+'" data-pm-day="'+ds+'" aria-label="'+esc(aria)+'"'+(inWin?'':' tabindex="-1"')+'>'+inner+'</button></td>';
    }
    if(idx%7===6){cur+='</tr>';body+=cur;cur=''}
  });
  if(cur){cur+='</tr>';body+=cur}
  var sub=!pmMonthCovered(mo)?'미수집'
    :(minV!=null?'최저 '+KR(minV)+'마일 · '+KR(rows)+'일 표시'
    :(collected?'표시 없음':'미수집'));  return '<div class="pm-mblock" id="pmM-'+mo+'">'
    +'<div class="pm-mhead"><b>'+y+'년 '+m+'월</b><span>'+esc(sub)+'</span></div>'
    +'<table class="pm-cal"><thead><tr>'
    +'<th class="sun">일</th><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th class="sat">토</th>'
    +'</tr></thead><tbody>'+body+'</tbody></table></div>';
}

/* ══ 날짜 상세 시트 ══════════════════════════════════════════════════════════ */
function pmSheetEl(){return document.getElementById('pmSheet')}
function pmProgramsBlock(){
  var ws=(PMD.programs||[]).filter(function(p){
    if(pms.alliance!=='all'&&p.alliance!==pms.alliance)return false;
    if(pms.prog!=='all'&&p.key!==pms.prog)return false;
    return true;
  });
  if(!ws.length)return '';
  return '<div class="pm-ds-gh">공식 사이트에서 직접 조회</div>'+pmAppsNote()
    +'<div class="pm-ds-sites">'+ws.map(function(p){
        return '<a class="pm-ds-site" href="'+esc(pmAppHref(p))+'" target="'+pmAppTarget(p)+'" rel="noopener"'+(p.key==='flyingblue'?' title="'+esc(p.name+' 공식 앱 또는 공식 웹으로 엽니다')+'"':'')+'>'
          +'<b>'+esc(p.short||p.name)+'</b>'
          +'<span>'+esc(p.name)+' · '+esc(p.allianceName||'')+'</span>'
          +'<i>공식 발권 ↗</i></a>';
      }).join('')+'</div>';
}
/* ── 왕복 짝 — 같은 날 반대 방향 ────────────────────────────────
   날짜 상세 시트에서 그 날의 반대 방향(부산·인천에서 떠나는 편 ↔ 돌아오는 편) 최저를
   함께 보여 주고, 누르면 방향을 바꿔 같은 날짜를 다시 연다. 값이 없으면 없다고 적는다(보간 없음). */
function pmRoundRows(ds,dir){
  var out=[];
  (PMD.rows||[]).forEach(function(r){
    if(r[1]!==ds||+r[8]!==dir)return;
    var p=pmProg(r[0]);
    if(!p)return;
    if(pms.alliance!=='all'&&p.alliance!==pms.alliance)return;
    if(pms.prog!=='all'&&r[0]!==pms.prog)return;
    var b=pmBestCabin(r,pms.cabin);
    if(!b)return;
    if(pms.direct&&b.stops!==0)return;
    out.push({r:r,p:p,c:b});
  });
  out.sort(function(a,b){return a.c.miles-b.c.miles});
  return out;
}
function pmRoundBlock(ds){
  var od=1-pms.dir,label=pmDirText(od),list=pmRoundRows(ds,od);
  var cities={};
  list.forEach(function(x){cities[x.r[3]]=1});
  var nc=Object.keys(cities).length,best=list.length?list[0]:null;
  return '<div class="pm-ds-round">'
    +'<div class="pm-ds-rh"><b>↔ 왕복 짝 — 같은 날 '+esc(label)+'</b>'
    +'<span>'+(best?'최저 '+KR(best.c.miles)+'마일 · '+KR(list.length)+'건 · '+KR(nc)+'개 도시':'이 날은 반대 방향 자료 없음')+'</span></div>'
    +(best?'<div class="pm-ds-rb"><span class="cb '+best.c.k+'">'+esc(pmDestName(best.r[3]))+' · '
        +esc((best.p.short||best.p.name))+' '+esc(pmCabinShort(best.c))+' <b>'+KR(best.c.miles)+'</b> <i>'+esc(pmStopsText(best.c.stops))+'</i></span></div>':'')
    +'<div class="pm-ds-rb"><button type="button" class="pm-ds-swap" data-pm-flip="'+esc(ds)+'">'
    +esc(label)+' 보고 방향 바꾸기 →</button></div>'
    +'</div>';
}
function pmAppsNote(){
  return /Android/i.test(pmUA())
    ? '<p class="pm-ds-apphint">안드로이드에서는 <b>플라이 블루</b>를 누르면 에어프랑스 공식 앱이 설치된 경우 앱으로, 없으면 공식 웹으로 열립니다.</p>'
    : '';
}
function pmOpenSheet(ds){
  var el=pmSheetEl();
  if(!el||!ds)return;
  var w=pmWin(),list=(pmDayMap()[ds]||[]);
  var col=pmInRange(ds,w.cFrom,w.cTo);
  var dirTxt=pmDirText(pms.dir);
  document.getElementById('pmDsTitle').textContent=pmDateLong(ds);
  document.getElementById('pmDsSub').innerHTML=esc(dirTxt+' · '+pmCondText()+' · 조회 기준 '+((pmMeta()||{}).observedLabel||'—'));
  var body='';
  if(!col){
    body='<div class="pm-ds-warn"><b>이 날짜는 아직 수집하지 않았습니다.</b><br>'
      +'조회 사이트가 비로그인 화면에 앞으로 '+KR(pmDaysBetween(w.cFrom,w.cTo))+'일('+esc(w.cFrom)+'~'+esc(w.cTo)+')만 열어 주어, '
      +esc(ds)+' 은 조회하지 못했습니다. 값을 추측해 채우지 않았습니다 — 아래 공식 사이트에서 직접 조회해 주세요.</div>'
      +pmProgramsBlock();
  }else if(!list.length){
    body='<div class="pm-ds-warn"><b>이 날짜에는 조회 사이트에 표시된 보너스 좌석이 없습니다.</b><br>'
      +'조회 사이트가 이 노선·날짜에 보너스 좌석을 보여 주지 않았습니다(좌석이 없다는 뜻과 조회되지 않았다는 뜻을 조회 사이트가 구분해 주지 않습니다). '
      +'아래 공식 사이트에서 직접 확인해 주세요.</div>'
      +pmProgramsBlock();
  }else{
    var by={};
    list.forEach(function(x){(by[x.r[3]]=by[x.r[3]]||[]).push(x)});
    var groups=Object.keys(by).map(function(c){
      var items=by[c].sort(function(a,b){return a.best.miles-b.best.miles});
      return {code:c,items:items,min:items[0].best.miles};
    }).sort(function(a,b){return a.min-b.min});
    body=groups.map(function(g){
      return '<div class="pm-ds-route">'
        +'<div class="pm-ds-rt"><b>'+esc(pmDestName(g.code))+'</b><span>최저 '+KR(g.min)+'마일 · '+KR(g.items.length)+'건</span></div>'
        +g.items.map(function(x){
            var r=x.r,p=x.p;
            var cs=x.cs.filter(function(c){return pms.cabin==='all'||c.k===pms.cabin})
                       .filter(function(c){return !pms.direct||c.stops===0});
            if(!cs.length)cs=x.cs;
            /* 계산기에 넣을 값 — 지금 고른 등급·질항 필터 안의 최저 마일 */
            var pick=cs[0]||null;
            cs.forEach(function(c){if(pick&&c.miles<pick.miles)pick=c});
            var side=pms.dir?'back':'go',sideKo=pms.dir?'오는 편':'가는 편';
            var putBtn=(pick?'<button type="button" class="pm-ds-put" data-pm-calc-put="'+side+'"'
                +' data-pm-calc-miles="'+pick.miles+'"'
                +' data-pm-calc-name="'+esc(pmDestName(r[3])+' '+(p.short||p.name)+' '+pmCabinLabel(pick))+'"'
                +' title="'+esc(pmCabinLabel(pick)+' '+KR(pick.miles)+'마일을 '+sideKo+'에 넣습니다')+'">🧮 '+sideKo+'에</button>':'');
            return '<div class="pm-ds-row">'
              +'<div class="pm-ds-pg"><b>'+esc(p.short||p.name)+'</b><span>'+esc(p.allianceName||'')+'</span></div>'
              +'<div class="pm-ds-cab">'+cs.map(function(c){
                  return '<span class="cb '+c.k+'">'+esc(pmCabinShort(c))+' <b>'+KR(c.miles)+'</b> <i>'+esc(pmStopsText(c.stops))+'</i></span>';
                }).join('')+putBtn+'</div>'
              +'<div class="pm-ds-meta"><span class="seen">최근 확인 '+esc(r[2])+'</span>'
              +'<a class="pm-ds-go" href="'+esc(pmAppHref(p))+'" target="'+pmAppTarget(p)+'" rel="noopener">'+esc(p.urlLabel||'공식 사이트')+' ↗</a></div>'
              +'</div>';
          }).join('')
        +'</div>';
    }).join('');
  }
  document.getElementById('pmDsBody').innerHTML=pmRoundBlock(ds)+body;
  document.getElementById('pmDsNote').innerHTML='필요 마일은 조회 사이트가 그 등급에 표시한 값이고, 같은 노선이라도 날짜·경유 편수·판매 조건에 따라 달라집니다. '
    +'세금·수수료는 마일과 별도이며 좌석 수량은 조회 사이트에 없어 표시하지 않습니다. 예약 전 <b>항공사 공식 사이트에서 재확인</b>해 주세요.';
  el.classList.add('show');
  el.setAttribute('aria-hidden','false');
  var close=document.getElementById('pmDsClose');
  if(close&&close.focus)close.focus({preventScroll:true});
}
function pmCloseSheet(){
  var el=pmSheetEl();
  if(!el)return;
  el.classList.remove('show');
  el.setAttribute('aria-hidden','true');
}

/* ══ 🧮 마일리지 계산기 ═════════════════════════════════════════
   가는 편·오는 편 마일과 인원으로 총 필요 마일을, 현금 항공권 가격으로 1마일당
   원화 가치를 계산한다. 값은 이 기기(localStorage)에만 저장하고, 날짜 상세 시트의
   「🧮 가는 편에 / 오는 편에」 버튼으로 그 행의 최저 마일을 그대로 채운다. */
var PM_CALC_KEY='teambusan.pmcalc.v1';
var PM_CALC={trip:'rt',pax:1,go:0,back:0,have:0,tax:0,cash:0,open:true};
var PM_CALC_READY=false,PM_CALC_FLASH_T=null;

function pmNum(v){
  var n=parseInt(String(v==null?'':v).replace(/[^0-9]/g,''),10);
  return isNaN(n)?0:n;
}
function pmCalcEl(id){return document.getElementById(id)}
function pmCalcLoad(){
  if(PM_CALC_READY)return PM_CALC;
  PM_CALC_READY=true;
  try{
    var raw=window.localStorage.getItem(PM_CALC_KEY);
    if(raw){
      var o=JSON.parse(raw)||{};
      if(o.trip==='ow'||o.trip==='rt')PM_CALC.trip=o.trip;
      var pax=pmNum(o.pax);if(pax>=1&&pax<=9)PM_CALC.pax=pax;
      PM_CALC.go=pmNum(o.go);PM_CALC.back=pmNum(o.back);
      PM_CALC.have=pmNum(o.have);PM_CALC.tax=pmNum(o.tax);PM_CALC.cash=pmNum(o.cash);
      if(o.open===false)PM_CALC.open=false;
    }
  }catch(e){}
  return PM_CALC;
}
function pmCalcSave(){
  try{window.localStorage.setItem(PM_CALC_KEY,JSON.stringify(PM_CALC))}catch(e){}
}
/* 폼에 값을 되쓴다 — 지금 입력 중인 칸은 건드리지 않는다(커서가 튀지 않게) */
function pmCalcPaintNum(id,n){
  var el=pmCalcEl(id);
  if(el&&document.activeElement!==el)el.value=n?KR(n):'';
}
function pmCalcPaint(){
  pmCalcLoad();
  var trip=pmCalcEl('pmCalcTrip');
  if(trip){
    [].forEach.call(trip.querySelectorAll('button'),function(b){
      var on=b.getAttribute('data-pm-trip')===PM_CALC.trip;
      b.classList.toggle('on',on);
      b.setAttribute('aria-pressed',on?'true':'false');
    });
  }
  var pax=pmCalcEl('pmCalcPax');if(pax)pax.value=String(PM_CALC.pax);
  pmCalcPaintNum('pmCalcGo',PM_CALC.go);
  pmCalcPaintNum('pmCalcBack',PM_CALC.back);
  pmCalcPaintNum('pmCalcHave',PM_CALC.have);
  pmCalcPaintNum('pmCalcTax',PM_CALC.tax);
  pmCalcPaintNum('pmCalcCash',PM_CALC.cash);
  var ow=PM_CALC.trip==='ow';
  var bf=pmCalcEl('pmCalcBackF');if(bf)bf.classList.toggle('off',ow);
  var bi=pmCalcEl('pmCalcBack');if(bi)bi.disabled=ow;
  pmCalcOut();
}
function pmCalcOut(){
  var out=pmCalcEl('pmCalcOut'),sum=pmCalcEl('pmCalcSum');
  if(!out)return;
  var tripKo=PM_CALC.trip==='ow'?'편도':'왕복';
  var per=PM_CALC.go+(PM_CALC.trip==='rt'?PM_CALC.back:0);
  var total=per*PM_CALC.pax;
  var eff=PM_CALC.cash-PM_CALC.tax;
  var value=(PM_CALC.cash>0&&eff>0&&total>0)?((eff*PM_CALC.pax)/total):null;
  var html='';
  if(sum)sum.textContent=tripKo+' · '+PM_CALC.pax+'명'+(total?' · '+KR(total)+'마일':' · 마일을 넣어 주세요')+(value!=null?' · '+(Math.round(value*10)/10).toFixed(1)+'원/마일':'');
  if(!total){
    html='<div class="pm-calc-empty">가는 편 마일을 적으면 총 필요 마일을 계산합니다. '
      +'달력에서 날짜를 눌러 열린 상세에서 <b>「🧮 가는 편에」·「오는 편에」</b>를 누르면 그 행의 마일이 그대로 들어옵니다.</div>';
    out.innerHTML=html;
    return;
  }
  var sub='1인 '+KR(per)+'마일'+(PM_CALC.trip==='rt'
    ?'(가는 '+KR(PM_CALC.go)+' + 오는 '+KR(PM_CALC.back)+')'
    :'(가는 편만)')+' × '+PM_CALC.pax+'명';
  html='<div class="pm-co-main"><div class="pm-co-big">'+KR(total)+'<small>마일</small></div>'
    +'<div class="pm-co-sub">'+esc(sub)+'</div></div><div class="pm-co-rows">';
  /* 보유 마일 — 부족/잔여 */
  if(PM_CALC.have>0){
    var rest=PM_CALC.have-total;
    html+='<div class="pm-co-row"><span class="k">보유 마일</span>'
      +(rest>=0?'<b class="ok">'+KR(rest)+'마일 남음</b><span class="f">보유 '+KR(PM_CALC.have)+'마일로 가능</span>'
               :'<b class="lack">'+KR(-rest)+'마일 부족</b><span class="f">보유 '+KR(PM_CALC.have)+'마일</span>')
      +'</div>';
  }else{
    html+='<div class="pm-co-row"><span class="k">보유 마일</span><b class="dim">넣으면 부족·잔여를 계산합니다</b></div>';
  }
  /* 1마일당 원화 가치 */
  if(PM_CALC.cash>0){
    if(value==null){
      html+='<div class="pm-co-row"><span class="k">1마일당 원화 가치</span><b class="dim">비교 가격이 세금보다 낮아 계산하지 않았습니다</b></div>';
    }else{
      var vTxt=(Math.round(value*10)/10).toFixed(1);
      var good=value>=15;
      html+='<div class="pm-co-row"><span class="k">1마일당 원화 가치</span><b>'+vTxt+'원/마일</b>'
        +'<i class="pm-co-badge'+(good?'':' low')+'">'+(good?'15원/마일 이상 · 마일 쪽이 유리한 편':'15원/마일 미만 · 현금 구매가 나을 수 있음')+'</i></div>'
        +'<div class="pm-co-row"><span class="f">현금 '+KR(PM_CALC.cash)+' − 유류·세금 '+KR(PM_CALC.tax)+' = '+KR(eff)+'원 ÷ 1인 '+KR(per)+'마일'
        +(PM_CALC.pax>1?' · 세금 뺀 현금 기준 총 '+KR(Math.round(eff*PM_CALC.pax))+'원어치':'')
        +' · 15원/마일은 단순 참고값</span></div>';
    }
  }else{
    html+='<div class="pm-co-row"><span class="k">1마일당 원화 가치</span><b class="dim">비교 현금 항공권 가격을 넣으면 계산합니다</b></div>';
  }
  html+='</div><div class="pm-co-foot"><button type="button" id="pmCalcClear">입력 지우기</button></div>';
  out.innerHTML=html;
}
function pmCalcInit(){
  pmCalcLoad();
  var el=pmCalcEl('pmCalc');
  if(!el)return;
  if(el.tagName==='DETAILS'){
    el.open=PM_CALC.open!==false;
    if(!el.__pmTog){
      el.__pmTog=true;
      el.addEventListener('toggle',function(){
        PM_CALC.open=el.open;pmCalcSave();
        if(el.open)pmCalcPaint();
      });
    }
  }
  pmCalcPaint();
}
/* 날짜 상세 시트의 버튼으로 그 행의 마일을 가는 편 / 오는 편에 넣는다 */
function pmCalcPut(side,miles,name){
  if(!miles)return;
  pmCalcLoad();
  var wasOw=PM_CALC.trip==='ow';
  if(side==='back'){PM_CALC.trip='rt';PM_CALC.back=miles}else{PM_CALC.go=miles}
  PM_CALC.open=true;
  pmCalcSave();pmCalcPaint();
  var el=pmCalcEl('pmCalc');
  if(el){
    if(el.tagName==='DETAILS')el.open=true;
    if(el.scrollIntoView)el.scrollIntoView({block:'center',behavior:'smooth'});
  }
  pmCloseSheet();
  var fl=pmCalcEl('pmCalcFlash');
  if(fl){
    fl.textContent=(side==='back'?'오는 편':'가는 편')+'에 '+KR(miles)+'마일을 넣었습니다'
      +(name?' · '+name:'')+(side==='back'&&wasOw?' (왕복으로 바꿨습니다)':'');
    fl.classList.add('on');
    clearTimeout(PM_CALC_FLASH_T);
    PM_CALC_FLASH_T=setTimeout(function(){
      var cur=pmCalcEl('pmCalcFlash');
      if(cur){cur.classList.remove('on');cur.textContent=''}
    },3600);
  }
}
/* 계산기 입력 — 타이핑 중에는 칸을 다시 쓰지 않고 결과만 새로 그린다 */
document.addEventListener('input',function(e){
  var t=e.target;
  if(!t||!t.id||!t.closest||!t.closest('#pmCalc'))return;
  var map={pmCalcGo:'go',pmCalcBack:'back',pmCalcHave:'have',pmCalcTax:'tax',pmCalcCash:'cash'};
  var k=map[t.id];
  if(!k)return;
  pmCalcLoad();
  PM_CALC[k]=pmNum(t.value);
  pmCalcOut();
  pmCalcSave();
});
/* 칸을 벗어나면 1,000 단위 쉼표로 정리 */
document.addEventListener('focusout',function(e){
  var t=e.target;
  if(!t||!t.id||!t.closest||!t.closest('#pmCalc'))return;
  var map={pmCalcGo:1,pmCalcBack:1,pmCalcHave:1,pmCalcTax:1,pmCalcCash:1};
  if(map[t.id])t.value=pmNum(t.value)?KR(pmNum(t.value)):'';
});
document.addEventListener('change',function(e){
  var t=e.target;
  if(t&&t.id==='pmCalcPax'){
    pmCalcLoad();
    var n=pmNum(t.value);
    PM_CALC.pax=(n>=1&&n<=9)?n:1;
    pmCalcSave();pmCalcPaint();
  }
});
document.addEventListener('click',function(e){
  var t=e.target;
  if(!t||!t.closest)return;
  if(t.closest('#pmCalc')){
    var tb=t.closest('[data-pm-trip]');
    if(tb){
      pmCalcLoad();
      PM_CALC.trip=tb.getAttribute('data-pm-trip')==='ow'?'ow':'rt';
      pmCalcSave();pmCalcPaint();
      return;
    }
    if(t.closest('#pmCalcClear')){
      pmCalcLoad();
      PM_CALC.go=0;PM_CALC.back=0;PM_CALC.have=0;PM_CALC.tax=0;PM_CALC.cash=0;
      pmCalcSave();pmCalcPaint();
      var fl=pmCalcEl('pmCalcFlash');if(fl){fl.classList.remove('on');fl.textContent=''}
      return;
    }
  }
  var put=t.closest('[data-pm-calc-put]');
  if(put){
    e.preventDefault();
    pmCalcPut(put.getAttribute('data-pm-calc-put'),pmNum(put.getAttribute('data-pm-calc-miles')),put.getAttribute('data-pm-calc-name')||'');
  }
});

/* 보기 전환 · 월 바로가기 · 날짜 칸 · 시트 닫기 */
document.addEventListener('click',function(e){
  var t=e.target;
  if(!t||!t.closest)return;
  var sheet=pmSheetEl();
  if(sheet&&sheet.classList.contains('show')&&t.closest('#pmSheet')){
    var flb=t.closest('[data-pm-flip]');
    if(flb){
      var fd=flb.getAttribute('data-pm-flip');
      pms.dir=1-pms.dir;pms.dest='all';      /* 반대 방향으로 바꿔 같은 날짜를 다시 연다 */
      renderPartner();
      pmOpenSheet(fd);
      return;
    }
    if(t.id==='pmDsClose'||t===sheet)pmCloseSheet();
    /* 공식 사이트 링크는 새 탭 이동이 끝난 뒤에 닫는다(이동이 취소되지 않게) */
    if(t.closest('a.pm-ds-go')||t.closest('a.pm-ds-site')){
      setTimeout(function(){var cur=pmSheetEl();if(cur&&cur.classList.contains('show'))pmCloseSheet()},350);
    }
    return;
  }
  var vw=t.closest('[data-pm-view]');
  if(vw){pms.view=vw.getAttribute('data-pm-view');renderPartner();return}
  var fl=t.closest('[data-pm-flip]');
  if(fl){
    var fd=fl.getAttribute('data-pm-flip');
    pms.dir=1-pms.dir;pms.dest='all';
    renderPartner();
    pmOpenSheet(fd);
    return;
  }
  var jp=t.closest('[data-pm-jump]');
  if(jp){
    var mo=jp.getAttribute('data-pm-jump');
    var box=document.getElementById('pmM-'+mo);
    if(box&&box.scrollIntoView)box.scrollIntoView({block:'start',behavior:'smooth'});
    return;
  }
  if(t.closest('a'))return;                       /* 카드·칸 안의 링크는 그대로 새 탭 */
  var day=t.closest('[data-pm-day]');
  if(day){e.preventDefault();pmOpenSheet(day.getAttribute('data-pm-day'));return}
});
document.addEventListener('keydown',function(e){if(e.key==='Escape')pmCloseSheet()});
