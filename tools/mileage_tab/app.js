/* ── ⑧ 마일리지발권 탭 ─────────────────────────────────────────────
   한 탭에서 두 자료를 함께 본다.
   · 대한항공(스카이패스) — 항공사가 공개하는 보너스 좌석 현황(하루 1회 갱신 · 앞으로 360일)을
     매일 04:00 옮긴 data/app/tab8_mileage.json. 부산/김해(PUS)를 드나드는 14개 노선의
     일반석 E · 프레스티지 P · 프레스티지 승급 U. 필요 마일은 항공사 공제표(편도) 값으로 계산한다.
   · 외항사 9개 프로그램 — data/app/tab9_partner_mileage.json(부산 PUS) · tab9_partner_mileage_icn.json(인천 ICN).
   같은 12개월 달력·같은 날짜 상세 시트에 나란히 놓아 같은 날 같은 노선의 마일을 바로 견준다.
   원천이 알려 주지 않는 값(좌석 수량·세금·수수료, 대한항공 직항 여부)은 만들어 내지 않는다. */
var MGD={meta:null,routes:[],cells:[],chart:[],monthNotes:[],months:[],ready:false,__ready:false};   /* 대한항공 */
var PMD={meta:null,programs:[],dests:[],rows:[],ready:false,__ready:false};                            /* 외항사 — 지금 보는 출발지 */
var PDS={};                                                                                            /* 출발지별 외항사 자료 */
var mlBusy=false,mlErr='';
var KE_SEARCH='https://www.koreanair.com/booking/book-and-manage/award-seat-availability';
var KE_CHART='https://www.koreanair.com/contents/skypass/use-miles';
var KE_PROG={key:'ke',short:'대한항공',name:'대한항공(스카이패스)',alliance:'skyteam',allianceName:'스카이팀',
             url:KE_SEARCH,urlLabel:'대한항공 공식'};
var PT_SHORT=['이코','프이','비즈','퍼스트'];
var PT_NAME=['이코노미','프리미엄 이코노미','비즈니스','퍼스트'];

var MLS={origin:'PUS',dir:0,view:'cal',list:'cal',alliance:'all',prog:'all',dest:'all',cabin:'all',
         direct:false,sort:'miles',keRoute:'',keMonth:'',keNights:2,keWeekend:false,keNewKind:'all'};

function mlMeta(){return (PDS[MLS.origin]&&PDS[MLS.origin].observedAt)?PDS[MLS.origin]:(PMD||{})}
function mlOriginName(){return MLS.origin==='ICN'?'인천':'부산'}
function mlOriginCode(){return MLS.origin}
function mlDirText(dir){var n=mlOriginName(),c=mlOriginCode();return dir?(n+' 도착(→ '+c+')'):(n+' 출발('+c+' →)')}
function mlWon(n){return n==null?'—':KR(n)+'마일'}
function mlP2(n){return (n<10?'0':'')+n}

/* ── 자료 준비 ──────────────────────────────────────────────── */
function mlKEPrep(){
  if(MGD.__ready)return;
  MGD.__route={};MGD.__cell={};MGD.__chart={};MGD.__note={};MGD.__days={};
  (MGD.routes||[]).forEach(function(r){MGD.__route[r.code]=r});
  (MGD.cells||[]).forEach(function(c){
    MGD.__cell[c[0]+'|'+c[1]+'|'+c[2]]=c[3];
    if(c[3]&&!(c[3]&16)){var k=c[0]+'|'+c[1];(MGD.__days[k]=MGD.__days[k]||[]).push(c[2])}
  });
  (MGD.chart||[]).forEach(function(r){MGD.__chart[r[0]]=r});
  (MGD.monthNotes||[]).forEach(function(n){MGD.__note[n[0]+'|'+n[1]+'|'+n[2]]=n[3]});
  MGD.__ready=true;
  ML_CACHE={key:'',rows:null,map:null};        /* 늦게 온 자료로 지난 계산을 쓰지 않게 */
}

function ptPrep(){
  if(PMD.__ready)return;
  PMD.__prog={};PMD.__dest={};
  (PMD.programs||[]).forEach(function(p){PMD.__prog[p.key]=p});
  (PMD.dests||[]).forEach(function(d){PMD.__dest[d.code]=d});
  PMD.__ready=true;
  ML_CACHE={key:'',rows:null,map:null};
}
function keRoute(code){return MGD.__route[code]||null}
function keBit(code,dir,date){var v=MGD.__cell[code+'|'+dir+'|'+date];return typeof v==='number'?v:null}
function keChart(region){return MGD.__chart[region]||null}
function keNote(code,dir,month){return MGD.__note[code+'|'+dir+'|'+month]||''}
function keDates(code,dir){return (MGD.__days[code+'|'+dir]||[]).slice().sort()}
function keHasData(code){return keDates(code,0).length>0||keDates(code,1).length>0}
function ptProg(k){return PMD.__prog[k]||null}
function ptDest(code){return PMD.__dest[code]||null}

/* 한 행 = [프로그램, 날짜, 최근확인, 도시, 이코, 프이, 비즈, 퍼스트, 방향]
   등급 값은 "" 또는 "직항편수:마일" (예: "0:9000" = 직항 9,000마일, "1:33000" = 1회 경유) */
function ptCabins(r){
  var out=[];
  for(var i=0;i<4;i++){
    var v=r[4+i];
    if(!v)continue;
    var sp=String(v).split(':');
    out.push({k:'epbf'.charAt(i),short:PT_SHORT[i],name:PT_NAME[i],stops:+sp[0],miles:+sp[1]});
  }
  return out;
}
/* 대한항공 등급 — 일반석 E 는 이코노미, 프레스티지 P 는 비즈니스로 놓아 외항사와 같은 줄에서 견준다.
   프레스티지 승급 U 는 마일 차감이 없어 '승급'으로 따로 표시하고 최저 마일 계산에서 뺀다. */
function keCabins(route,v){
  var ch=keChart(route?route.region:'');
  var out=[];
  if(!ch)return out;
  if(v&1)out.push({k:'e',short:'일반석',name:'일반석 보너스',miles:ch[2],peak:ch[3],stops:null,ke:true});
  if(v&2)out.push({k:'b',short:'프레스티지',name:'프레스티지 보너스',miles:ch[4],peak:ch[5],stops:null,ke:true});
  if(v&4)out.push({k:'b',short:'승급',name:'프레스티지 승급',miles:null,peak:null,stops:null,ke:true,upg:true});
  return out;
}
function mlMin(cs){
  var best=null;
  (cs||[]).forEach(function(c){if(c.upg||c.miles==null)return;if(!best||c.miles<best.miles)best=c});
  return best;
}
function mlCabinOK(c){
  if(MLS.cabin!=='all'&&c.k!==MLS.cabin)return false;
  /* 직항만 — 대한항공은 원천이 직항·경유 편수를 알려 주지 않아(stops=null) 함께 빠진다 */
  if(MLS.direct&&c.stops!==0)return false;
  return true;
}
function mlCabinLabel(c){return c.k==='e'?'이코노미':c.k==='p'?'프리미엄 이코노미':c.k==='b'?'비즈니스':'퍼스트'}
function mlCabinShort(c){return c.ke?c.short:(c.k==='e'?'이코':c.k==='p'?'프이':c.k==='b'?'비즈':'퍼스트')}
function mlStopsText(n){return n==null?'':(n===0?'직항':n+'회 경유')}
function mlProgShort(x){
  if(x.src==='ke')return '대한항공';
  return (x.p&&(x.p.short||x.p.name))||'';
}
function mlDestName(code){
  var d=ptDest(code);
  if(d)return d.city+' '+code;
  var r=keRoute(code);
  if(r)return r.city+' '+code;
  return code;
}
function mlDateKo(ds){
  var d=new Date(ds+'T12:00:00Z');
  var wd=['일','월','화','수','목','금','토'][d.getUTCDay()];
  return (d.getUTCMonth()+1)+'/'+d.getUTCDate()+'('+wd+')';
}
function mlDateLong(ds){
  var d=new Date(ds+'T12:00:00Z');
  var wd=['일','월','화','수','목','금','토'][d.getUTCDay()];
  return d.getUTCFullYear()+'년 '+(d.getUTCMonth()+1)+'월 '+d.getUTCDate()+'일('+wd+')';
}
function mlToday(){var d=new Date();return d.getFullYear()+'-'+mlP2(d.getMonth()+1)+'-'+mlP2(d.getDate())}

/* ── 공식 링크 — 휴대폰에서는 앱으로, 없으면 공식 웹으로 ──────────────────
   에어프랑스·KLM 플라이 블루만 공식 앱 딥링크를 쓴다.
   · 안드로이드: intent://…package=<구글 플레이의 공식 앱 패키지> + S.browser_fallback_url=<공식 웹>
   · 아이폰·데스크톱: 공식 웹 주소 그대로(새 탭). */
var ML_AF_APP='com.airfrance.android.dinamoprd';
var ML_AF_WEB='https://wwws.airfrance.co.kr/';
function mlUA(ua){return String(ua==null?navigator.userAgent:ua)}
function mlAppHref(p,ua){
  var web=(p&&p.url)||'';
  if(!p||p.key!=='flyingblue')return web;
  if(!/Android/i.test(mlUA(ua)))return web;
  return 'intent://'+ML_AF_WEB.replace(/^https?:\/\//,'')
    +'#Intent;scheme=https;package='+ML_AF_APP
    +';S.browser_fallback_url='+encodeURIComponent(ML_AF_WEB)+';end';
}
function mlAppTarget(p){return (p&&p.key==='flyingblue'&&/Android/i.test(mlUA()))?'_self':'_blank'}
function mlAppsNote(){
  return /Android/i.test(mlUA())
    ? '<p class="pm-ds-apphint">안드로이드에서는 <b>플라이 블루</b>를 누르면 에어프랑스 공식 앱이 설치된 경우 앱으로, 없으면 공식 웹으로 열립니다.</p>'
    : '';
}

/* ── 출발지(부산 PUS / 인천 ICN) 전환 ──────────────────────────
   부산 자료는 탭을 열 때 함께 받고(loadPart), 인천 자료는 처음 인천을 누를 때 한 번 받아
   PDS 에 보관한다. 대한항공은 부산(PUS) 출발 전용이라 인천에서는 외항사만 보인다. */
function mlRoot(){return (typeof DATA_ROOT!=='undefined'&&DATA_ROOT)?DATA_ROOT:'data/app/'}
function mlBust(){return (typeof DATA_BUST!=='undefined'&&DATA_BUST['mileage-pt'])||''}
function mlSwap(d){
  PMD=d;PMD.__ready=false;ptPrep();
  MLS.dest='all';MLS.prog='all';ML_CACHE.key='';
  renderMileage();
  var el=document.getElementById('mlCal');
  if(el&&el.scrollIntoView)el.scrollIntoView({block:'start',behavior:'smooth'});
}
function mlPickOrigin(code){
  if(mlBusy||code===MLS.origin)return;
  PDS[MLS.origin]=PMD;
  if(PDS[code]){MLS.origin=code;mlErr='';mlSwap(PDS[code]);return}
  mlBusy=true;mlErr='';mlRenderOrigin();
  var url=mlRoot()+'tab9_partner_mileage_icn.json'+(mlBust()?'?g='+mlBust():'');
  fetch(url).then(function(r){
    if(!r.ok)throw new Error(url+' → HTTP '+r.status);
    return r.json();
  }).then(function(d){
    if(typeof hcDecode==='function')d=hcDecode(d);
    PDS[code]=d;MLS.origin=code;mlBusy=false;
    mlSwap(d);
  }).catch(function(){
    mlBusy=false;
    mlErr='인천 자료를 불러오지 못했습니다 — 잠시 뒤 다시 눌러 주세요.';
    mlRenderOrigin();
  });
}

/* ── 조건에 맞는 행 모으기 (대한항공 + 외항사) ───────────────────── */
var ML_CACHE={key:'',rows:null,map:null};
function mlSig(){return [MLS.origin,MLS.dir,MLS.alliance,MLS.prog,MLS.dest,MLS.cabin,MLS.direct?1:0].join('~')}
function mlCollect(dir,onlyDate){
  var out=[];
  /* 외항사 */
  if(MLS.prog!=='ke'){
    (PMD.rows||[]).forEach(function(r){
      if(+r[8]!==dir)return;
      if(onlyDate&&r[1]!==onlyDate)return;
      var p=ptProg(r[0]);if(!p)return;
      if(MLS.prog!=='all'&&r[0]!==MLS.prog)return;
      if(MLS.alliance!=='all'&&p.alliance!==MLS.alliance)return;
      if(MLS.dest!=='all'&&r[3]!==MLS.dest)return;
      var cs=[];
      ptCabins(r).forEach(function(c){if(mlCabinOK(c))cs.push(c)});
      if(!cs.length)return;
      out.push({src:'pt',prog:r[0],p:p,date:r[1],seen:r[2],dest:r[3],cabins:cs,best:mlMin(cs)});
    });
  }
  /* 대한항공 — 부산 자료일 때만 */
  if(MLS.origin==='PUS'&&(MLS.prog==='all'||MLS.prog==='ke')&&(MLS.alliance==='all'||MLS.alliance==='skyteam')){
    (MGD.cells||[]).forEach(function(c){
      if(c[1]!==dir)return;
      if(onlyDate&&c[2]!==onlyDate)return;
      var v=c[3];
      if(!v||(v&16))return;                       /* 좌석 없음·운항 없음은 여기서 빼고 시트에서 따로 적는다 */
      if(MLS.dest!=='all'&&c[0]!==MLS.dest)return;
      var route=keRoute(c[0]);if(!route)return;
      var cs=[];
      keCabins(route,v).forEach(function(x){if(mlCabinOK(x))cs.push(x)});
      if(!cs.length)return;
      out.push({src:'ke',prog:'ke',p:KE_PROG,date:c[2],seen:'',dest:c[0],cabins:cs,best:mlMin(cs),route:route});
    });
  }
  return out;
}
function mlSortRows(a,b){
  if(MLS.sort==='date')return a.date<b.date?-1:a.date>b.date?1:((a.best?a.best.miles:1e12)-(b.best?b.best.miles:1e12));
  var am=a.best?a.best.miles:1e12,bm=b.best?b.best.miles:1e12;
  return (am-bm)||(a.date<b.date?-1:a.date>b.date?1:0);
}
function mlRows(){
  var sig=mlSig();
  if(ML_CACHE.key===sig&&ML_CACHE.rows)return ML_CACHE.rows;
  var out=mlCollect(MLS.dir,null);
  out.sort(mlSortRows);
  ML_CACHE={key:sig,rows:out,map:null};
  return out;
}
function mlDayMap(){
  if(ML_CACHE.map)return ML_CACHE.map;
  var map={};
  mlRows().forEach(function(x){(map[x.date]=map[x.date]||[]).push(x)});
  ML_CACHE.map=map;
  return map;
}
function mlRowsForDateDir(ds,dir){
  var out=mlCollect(dir,ds);
  out.sort(mlSortRows);
  return out;
}
function mlDayStat(list){
  var min=null,best=null,row=null,upg=0;
  list.forEach(function(x){
    if(x.best&&(min==null||x.best.miles<min)){min=x.best.miles;best=x.best;row=x}
    if(!x.best)upg++;
  });
  return {min:min,best:best,row:row,upg:upg};
}
function mlCondText(){
  var p=MLS.prog==='all'?'전체 프로그램':(MLS.prog==='ke'?'대한항공':((ptProg(MLS.prog)||{}).short||MLS.prog));
  var d=MLS.dest==='all'?'전체 도시':mlDestName(MLS.dest);
  var c=MLS.cabin==='all'?'모든 등급':mlCabinLabel({k:MLS.cabin});
  return [p,d,c].join(' · ')+(MLS.direct?' · 직항만':'');
}

/* ── 기간·달력 기준 ───────────────────────────────────────────── */
function mlWin(){
  var m=mlMeta()||{};
  var from=m.dateFrom||'',to=m.dateTo||'';
  if(!from||!to){
    var ms=MGD.months||[];
    from=ms.length?ms[0]+'-01':'';
    to=ms.length?ms[ms.length-1]+'-28':'';
  }
  return {from:from,to:to,cFrom:m.collectedFrom||from,cTo:m.collectedTo||to};
}
function mlDaysBetween(a,b){
  if(!a||!b)return 0;
  return Math.round((new Date(b+'T00:00:00Z')-new Date(a+'T00:00:00Z'))/86400000)+1;
}
function mlInRange(ds,a,b){return !!a&&!!b&&ds>=a&&ds<=b}
function mlMonthList(){
  var w=mlWin();
  if(!w.from||!w.to)return [];
  var y=+w.from.slice(0,4),m=+w.from.slice(5,7);
  var ey=+w.to.slice(0,4),em=+w.to.slice(5,7);
  var out=[],guard=0;
  while(guard++<40){
    out.push(y+'-'+mlP2(m));
    if(y===ey&&m===em)break;
    m++;if(m>12){m=1;y++}
  }
  return out;
}
function mlMonthCovered(mo){
  var w=mlWin();
  return !((mo+'-31')<w.cFrom||(mo+'-01')>w.cTo);
}

/* ── 화면 ───────────────────────────────────────────────────── */
function renderMileage(){
  mlKEPrep();ptPrep();
  setDealPanels('mileage');
  var p=document.getElementById('mgPanel');
  if(!p)return;
  mlRenderBanner();
  mlRenderKpi();
  mlRenderViews();
  mlRenderCalcInit();
  mlRenderOrigin();
  mlRenderDir();
  mlRenderAlliance();
  mlRenderProgs();
  mlRenderDests();
  mlRenderBest();
  mlRenderCal();
  mlRenderList();
  mlRenderKeRoutes();
  mlRenderRound();
  mlRenderNew();
  mlRenderChart();
  mlRenderNote();
  mlTabBadge();
}

function mlRenderBanner(){
  var b=document.getElementById('mlBanner');
  if(!b)return;
  var m=mlMeta()||{},w=mlWin();
  var rowsOut=0,rowsIn=0;
  (PMD.rows||[]).forEach(function(r){if(+r[8]===0)rowsOut++;else rowsIn++});
  var keRoutes=(MGD.counts&&MGD.counts.routes)||0;
  var keTxt=MLS.origin==='PUS'
    ? '<b>🇰🇷 대한항공(스카이패스)</b> 기준 <b>'+esc(MGD.observedLabel||'—')+'</b> · 부산(PUS) 14개 노선 중 '+KR(keRoutes)+'개 노선 수집(나머지는 부산발 직항 미운항·하계 미개시)'
    : '대한항공은 <b>부산(PUS) 출발·도착 전용</b>이라 인천 자료에는 없습니다 — 인천은 외항사 9개 프로그램만 봅니다';
  b.innerHTML='<b>대한항공(스카이패스) + 항공사 마일리지 프로그램 9곳 — 한 달력에서 견주기</b>'
    +' · '+esc(mlDirText(MLS.dir))
    +' · 목표 <b>1년 '+KR(mlDaysBetween(w.from,w.to))+'일</b>('+esc(w.from)+'~'+esc(w.to)+')'
    +'<span class="pm-b2">'+keTxt+'</span>'
    +'<span class="pm-b2">외항사 기준 <b>'+esc(m.observedLabel||'—')+'</b> · '+KR((PMD.rows||[]).length)+'건(출발 '+KR(rowsOut)+' · 도착 '+KR(rowsIn)+') · '
    +'대한항공 마일은 공제표 <b>평수기 편도</b> 값입니다(성수기 탑승일은 더 큽니다).</span>'
    +'<span class="pm-b2">보너스 좌석은 실시간으로 변동됩니다. 예약 전 <b>각 항공사 공식 사이트에서 재확인</b>해 주세요. '
    +'조회 사이트는 노선·날짜마다 등급별 예약 가능 여부와 필요 마일만 알려 주며, 좌석 수량·세금·수수료와 대한항공 직항·경유 편수는 알려 주지 않아 표시하지 않습니다.</span>';
}

function mlBaseStat(){
  var pr={},cities={},ptRows=0,keRows=0;
  (PMD.rows||[]).forEach(function(r){
    if(+r[8]!==MLS.dir)return;
    pr[r[0]]=(pr[r[0]]||0)+1;cities[r[3]]=1;ptRows++;
  });
  if(MLS.origin==='PUS'){
    (MGD.cells||[]).forEach(function(c){
      if(c[1]!==MLS.dir||!c[3]||(c[3]&16))return;
      keRows++;cities[c[0]]=1;
    });
  }
  return {progs:Object.keys(pr).length+(keRows?1:0),ptRows:ptRows,keRows:keRows,
          rows:ptRows+keRows,cities:Object.keys(cities).length,total:9+(MLS.origin==='PUS'?1:0)};
}

function mlRenderKpi(){
  var el=document.getElementById('mlKpi');
  if(!el)return;
  var st=mlBaseStat();
  var rows=mlRows(),cheap=null;
  rows.forEach(function(x){if(x.best&&(!cheap||x.best.miles<cheap.best.miles))cheap=x});
  el.innerHTML=''
    +'<div><span>수집 프로그램</span><b>'+KR(st.progs)+'</b><i>'+KR(st.total)+'개 중 · 나머지는 이 출발지 자료 없음</i></div>'
    +'<div><span>보너스 좌석 행</span><b>'+KR(st.rows)+'</b><i>대한항공 '+KR(st.keRows)+' · 외항사 '+KR(st.ptRows)+' · '+(MLS.dir?'도착':'출발')+' 방향</i></div>'
    +'<div><span>도시</span><b>'+KR(st.cities)+'</b><i>대한항공 노선 · 외항사 도시 합계</i></div>'
    +'<div class="new"><span>가장 적은 마일</span><b>'+(cheap?KR(cheap.best.miles):'—')+'</b><i>'
    +(cheap?esc(mlDestName(cheap.dest))+' · '+esc(mlProgShort(cheap))+' '+esc(mlCabinShort(cheap.best)):'—')+'</i></div>';
}

function mlRenderViews(){
  var el=document.getElementById('mlViews');
  if(el){
    [].forEach.call(el.querySelectorAll('[data-ml-view]'),function(b){
      var on=b.getAttribute('data-ml-view')===MLS.view;
      b.classList.toggle('on',on);b.setAttribute('aria-selected',on?'true':'false');
    });
  }
  var map={cal:'mlViewCal',round:'mlViewRound',new:'mlViewNew',chart:'mlViewChart'};
  Object.keys(map).forEach(function(k){
    var n=document.getElementById(map[k]);
    if(n)n.hidden=(MLS.view!==k);
  });
}

function mlRenderOrigin(){
  var el=document.getElementById('mlOrigin');
  if(!el)return;
  PDS[MLS.origin]=PMD;
  var opts=[['PUS','부산'],['ICN','인천']];
  el.innerHTML=opts.map(function(o){
    var on=MLS.origin===o[0];
    var d=PDS[o[0]];
    var n=d?(d.rows||[]).length:null;
    return '<button type="button" data-ml-origin="'+o[0]+'" class="'+(on?'on':'')+'" aria-pressed="'+(on?'true':'false')+'"'
      +' title="'+esc(o[1]+'('+o[0]+') 출발'+(n!=null?' · '+KR(n)+'건':''))+'">'
      +esc(o[1])+'('+o[0]+')'+(n!=null?' <b>'+KR(n)+'</b>':'')+'</button>';
  }).join('');
  var h=document.getElementById('mlOriginHint');
  if(h)h.textContent=mlBusy?'자료 불러오는 중…':(mlErr||(MLS.origin==='PUS'?'대한항공 + 외항사 9개':'외항사 9개 — 대한항공은 부산 출발 전용'));
}

function mlRenderDir(){
  var el=document.getElementById('mlDir');
  if(!el)return;
  var n0=0,n1=0;
  (PMD.rows||[]).forEach(function(r){if(+r[8]===0)n0++;else n1++});
  if(MLS.origin==='PUS'){
    (MGD.cells||[]).forEach(function(c){
      if(!c[3]||(c[3]&16))return;
      if(c[1]===0)n0++;else n1++;
    });
  }
  el.innerHTML='<button type="button" data-ml-dir="0" class="'+(MLS.dir===0?'on':'')+'" aria-pressed="'+(MLS.dir===0?'true':'false')+'">'+esc(mlOriginName())+' 출발 '+esc(mlOriginCode())+'→ <b>'+KR(n0)+'</b></button>'
    +'<button type="button" data-ml-dir="1" class="'+(MLS.dir===1?'on':'')+'" aria-pressed="'+(MLS.dir===1?'true':'false')+'">'+esc(mlOriginName())+' 도착 →'+esc(mlOriginCode())+' <b>'+KR(n1)+'</b></button>';
  var dc=document.getElementById('mlDirect');
  if(dc)dc.setAttribute('aria-pressed',MLS.direct?'true':'false');
  var cs=document.getElementById('mlCabin');
  if(cs)cs.value=MLS.cabin;
  var so=document.getElementById('mlSort');
  if(so)so.value=MLS.sort;
}

function mlRenderAlliance(){
  var el=document.getElementById('mlAlliance');
  if(!el)return;
  var order=[['all','전체'],['skyteam','스카이팀'],['star','스타얼라이언스'],['oneworld','원월드'],['none','얼라이언스 없음']];
  el.innerHTML='<span class="pm-lab">동맹</span>'+order.map(function(o){
    var on=MLS.alliance===o[0];
    return '<button type="button" class="chip'+(on?' on':'')+'" data-ml-alliance="'+o[0]+'" aria-pressed="'+(on?'true':'false')+'">'+esc(o[1])+'</button>';
  }).join('');
}

function mlRenderProgs(){
  var el=document.getElementById('mlProgs');
  if(!el)return;
  var counts={},dir=MLS.dir,total=0;
  (PMD.rows||[]).forEach(function(r){if(+r[8]===dir)counts[r[0]]=(counts[r[0]]||0)+1});
  if(MLS.origin==='PUS'){
    var k=0;
    (MGD.cells||[]).forEach(function(c){if(c[1]!==dir||!c[3]||(c[3]&16))return;k++});
    counts.ke=k;
  }
  var html='<span class="pm-lab">프로그램</span>';
  (PMD.programs||[]).forEach(function(p){
    if(MLS.alliance!=='all'&&p.alliance!==MLS.alliance)return;
    total+=counts[p.key]||0;
  });
  if(MLS.origin==='PUS'&&(MLS.alliance==='all'||MLS.alliance==='skyteam'))total+=counts.ke||0;
  html+='<button type="button" class="chip'+(MLS.prog==='all'?' on':'')+'" data-ml-prog="all" aria-pressed="'+(MLS.prog==='all'?'true':'false')+'">전체 <b>'+KR(total)+'</b></button>';
  if(MLS.origin==='PUS'&&(MLS.alliance==='all'||MLS.alliance==='skyteam')){
    var nk=counts.ke||0,onk=MLS.prog==='ke';
    html+='<button type="button" class="chip'+(onk?' on':'')+(nk?'':' off')+'" data-ml-prog="ke" aria-pressed="'+(onk?'true':'false')+'"'
      +' title="'+esc('대한항공(스카이패스) · 스카이팀 · '+(nk?nk+'건':'이 방향 자료 없음'))+'">'
      +'🇰🇷 대한항공 <b>'+KR(nk)+'</b></button>';
  }
  (PMD.programs||[]).forEach(function(p){
    var n=counts[p.key]||0;
    if(MLS.alliance!=='all'&&p.alliance!==MLS.alliance)return;
    var on=MLS.prog===p.key;
    html+='<button type="button" class="chip'+(on?' on':'')+(n?'':' off')+'" data-ml-prog="'+esc(p.key)+'" aria-pressed="'+(on?'true':'false')+'"'
      +' title="'+esc(p.name+' · '+(p.allianceName||'')+' · '+(n?n+'건':'이 방향 자료 없음'))+'">'
      +esc(p.short||p.name)+' <b>'+KR(n)+'</b></button>';
  });
  el.innerHTML=html;
}

function mlRenderDests(){
  var el=document.getElementById('mlDests');
  if(!el)return;
  var best={};
  mlRows().forEach(function(x){
    if(!x.best)return;
    if(!best[x.dest]||x.best.miles<best[x.dest])best[x.dest]=x.best.miles;
  });
  var codes=Object.keys(best).sort(function(a,b){return best[a]-best[b]});
  var html='<span class="pm-lab">도시</span>';
  html+='<button type="button" class="chip'+(MLS.dest==='all'?' on':'')+'" data-ml-dest="all" aria-pressed="'+(MLS.dest==='all'?'true':'false')+'">전체</button>';
  html+=codes.map(function(c){
    var on=MLS.dest===c;
    return '<button type="button" class="chip'+(on?' on':'')+'" data-ml-dest="'+esc(c)+'" aria-pressed="'+(on?'true':'false')+'">'
      +esc(mlDestName(c))+' <b>'+KR(best[c])+'</b></button>';
  }).join('');
  el.innerHTML=html;
}

/* 도시별 최저 마일 — 지금 조건에서 도시마다 가장 싼 한 건(대한항공·외항사 통틀어) */
function mlRenderBest(){
  var el=document.getElementById('mlBest');
  if(!el)return;
  var rows=mlRows();
  if(!rows.length){
    el.innerHTML='<div class="pm-empty">이 조건에 맞는 보너스 좌석이 없습니다.<br>'
      +'프로그램·등급·직항 조건을 바꾸거나, 방향 버튼으로 반대 방향('+(MLS.dir?'출발':'도착')+')을 눌러 보세요.</div>';
    return;
  }
  var best={};
  rows.forEach(function(x){
    if(!x.best)return;
    if(!best[x.dest]||x.best.miles<best[x.dest].miles)best[x.dest]={miles:x.best.miles,cabin:x.best,prog:x.p,row:x};
  });
  var list=Object.keys(best).map(function(c){return {code:c,b:best[c]}})
    .sort(function(a,b){return a.b.miles-b.b.miles}).slice(0,12);
  el.innerHTML='<div class="pm-bhead">도시별 최저 마일 <span>'+KR(Object.keys(best).length)+'개 도시 중 싼 순서 12곳</span></div>'
    +'<div class="pm-bcards">'+list.map(function(o){
      var b=o.b,c=b.cabin,r=b.row;
      return '<button type="button" class="pm-bcard" data-ml-dest="'+esc(o.code)+'">'
        +'<span class="d">'+esc(mlDestName(o.code))+'</span>'
        +'<span class="m">'+KR(b.miles)+'</span>'
        +'<span class="s">'+esc(mlProgShort(r))+' · '+esc(mlCabinShort(c))+' · '+esc(r.src==='ke'?'KE':mlStopsText(c.stops))+'</span>'
        +'<span class="t">'+esc(mlDateKo(r.date))+' 기준</span></button>';
    }).join('')+'</div>';
}

function mlRenderList(){
  var el=document.getElementById('mlList');
  if(!el)return;
  if(MLS.view!=='cal'||MLS.list!=='list'){el.innerHTML='';return}
  var rows=mlRows();
  if(!rows.length){
    el.innerHTML='<div class="pm-empty">이 조건에 맞는 보너스 좌석이 없습니다.</div>';
    return;
  }
  var limit=300,shown=rows.slice(0,limit);
  el.innerHTML='<div class="pm-lhead">날짜별 보너스 좌석 <span>'+KR(rows.length)+'건'+(rows.length>limit?' 중 '+KR(limit)+'건 표시':'')+' · 대한항공 + 외항사</span></div>'
    +'<div class="pm-cards">'+shown.map(mlCardHtml).join('')+'</div>';
}

function mlCardHtml(x){
  var cs=x.cabins.slice();
  if(!cs.length)return '';
  var ke=x.src==='ke';
  var cab=cs.map(function(c){
    return '<span class="cb '+c.k+(c.upg?' u':'')+'">'+esc(mlCabinShort(c))+' <b>'+(c.miles==null?'승급':KR(c.miles))+'</b>'
      +' <i>'+esc(c.upg?'마일차감 없음':(ke?'평수기':mlStopsText(c.stops)))+'</i></span>';
  }).join('');
  var seen=ke?('원천 '+(MGD.observedLabel||'—')):('최근 확인 '+x.seen);
  var go=ke
    ? '<a class="go" href="'+KE_SEARCH+'" target="_blank" rel="noopener">대한항공 예약</a>'
    : '<a class="go" href="'+esc(mlAppHref(x.p))+'" target="'+mlAppTarget(x.p)+'" rel="noopener">'+esc(x.p.urlLabel||'공식 예약')+'</a>';
  return '<article class="pm-card'+(ke?' ml-ke':'')+'" data-ml-day="'+esc(x.date)+'" title="눌러서 이 날짜 상세 보기">'
    +'<div class="top"><b>'+esc(mlDestName(x.dest))+'</b><span class="dt">'+esc(mlDateKo(x.date))+'</span></div>'
    +'<div class="pg">'+(ke?'🇰🇷 대한항공':'')+esc(ke?'대한항공(스카이패스)':x.p.name)+'<span>'+(ke?'스카이패스 · 공제표 평수기 편도':esc(x.p.allianceName||''))+'</span></div>'
    +'<div class="cab">'+cab+'</div>'
    +'<div class="foot"><span class="seen">'+esc(seen)+'</span>'
    +'<span class="pm-footbtns"><button type="button" class="pm-open" data-ml-day="'+esc(x.date)+'">날짜 상세</button>'+go+'</span></div>'
    +'</article>';
}

/* ══ 통합 12개월 달력 ══════════════════════════════════════════════════════
   목표 창 = meta.dateFrom~dateTo(365일), 실제 수집 구간 = collectedFrom~collectedTo.
   수집 구간 밖의 날은 값이 아니라 '미수집'으로 그린다 — 보간하지 않는다.
   · 한 칸 = 그 날 (대한항공 + 지금 고른 외항사) 가운데 가장 적은 마일. 등급 색으로 구분한다.
   · 대한항공이 가장 싼 날은 칸 아래에 KE 로 적어 어느 쪽인지 바로 보이게 한다. */
function mlRenderCal(){
  var el=document.getElementById('mlCal');
  if(!el)return;
  if(MLS.view!=='cal'||MLS.list!=='cal'){el.innerHTML='';return}
  var w=mlWin(),months=mlMonthList();
  if(!months.length){el.innerHTML='<div class="pm-empty">자료 기간 기준을 읽지 못했습니다.</div>';return}
  var map=mlDayMap();
  var monMin={};
  months.forEach(function(mo){monMin[mo]=null});
  Object.keys(map).forEach(function(ds){
    var mo=ds.slice(0,7);
    if(!(mo in monMin))return;
    var st=mlDayStat(map[ds]);
    if(st.min!=null&&(monMin[mo]==null||st.min<monMin[mo]))monMin[mo]=st.min;
  });
  var today=mlToday();
  var strip='<div class="pm-year" role="group" aria-label="월 바로가기 — 달마다 최저 마일">'
    + months.map(function(mo){
        var v=monMin[mo],cov=mlMonthCovered(mo);
        return '<button type="button" class="pm-ym'+(v!=null?' has':'')+(cov?'':' unc')+'" data-ml-jump="'+mo+'"'
          +' title="'+(cov?(v!=null?mo+' 최저 '+KR(v)+'마일':mo+' 표시 없음'):mo+' 미수집')+'">'
          +'<b>'+mo.slice(2,4)+'.'+(+mo.slice(5,7))+'</b>'
          +'<span>'+(cov?(v!=null?KR(v):'—'):'미수집')+'</span></button>';
      }).join('')+'</div>';
  var grids=months.map(function(mo){return mlMonthGrid(mo,map,w,today)}).join('');
  el.innerHTML=strip+grids
    +'<div class="pm-legend">'
    +'<span class="lg"><i class="pm-cell has e">7,000</i>그 날 최저 마일(등급 색: <b class="e">이코</b> <b class="p">프이</b> <b class="b">비즈</b> <b class="f">퍼스트</b>)</span>'
    +'<span class="lg"><i class="pm-cell has ke">KE</i>대한항공이 가장 싼 날</span>'
    +'<span class="lg"><i class="pm-cell none">—</i>보너스 좌석 표시 없음</span>'
    +'<span class="lg"><i class="pm-cell miss">미수집</i>수집 구간 밖</span>'
    +'</div>'
    +'<p class="ml-calnote">'+esc(mlCondText())+' · 대한항공은 공제표 평수기 편도 값 · 프레스티지 승급(U)은 마일 차감이 없어 최저 마일에 넣지 않습니다.</p>';
}

function mlMonthGrid(mo,map,w,today){
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
      var ds=mo+'-'+mlP2(d);
      var cls=['pm-cell'],inner='<span class="d">'+d+'</span>';
      if(wd===0)cls.push('sun');else if(wd===6)cls.push('sat');
      var inWin=mlInRange(ds,w.from,w.to),col=inWin&&mlInRange(ds,w.cFrom,w.cTo);
      var aria=mlDateLong(ds);
      if(ds===today)cls.push('today');
      if(!inWin){
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
          aria+=' · 보너스 좌석 표시 없음';
        }else{
          rows++;
          var st=mlDayStat(list);
          if(st.min!=null){
            if(minV==null||st.min<minV)minV=st.min;
            var isKE=st.row&&st.row.src==='ke';
            cls.push('has','cb-'+st.best.k);
            if(isKE)cls.push('ke');
            inner+='<span class="m">'+KR(st.min)+'</span>'
              +'<span class="s">'+(isKE?'KE':mlStopsText(st.best.stops))+'</span>';
            aria+=' · 최저 '+KR(st.min)+'마일 · '+list.length+'건'+(isKE?' · 대한항공':'');
          }else{
            cls.push('has','cb-b','ke');
            inner+='<span class="m">승급</span><span class="s">마일차감 없음</span>';
            aria+=' · 대한항공 프레스티지 승급만';
          }
        }
      }
      cur+='<td><button type="button" class="'+cls.join(' ')+'" data-ml-day="'+ds+'" aria-label="'+esc(aria)+'"'+(inWin?'':' tabindex="-1"')+'>'+inner+'</button></td>';
    }
    if(idx%7===6){cur+='</tr>';body+=cur;cur=''}
  });
  if(cur){cur+='</tr>';body+=cur}
  var sub=!mlMonthCovered(mo)?'미수집'
    :(minV!=null?'최저 '+KR(minV)+'마일 · '+KR(rows)+'일 표시'
    :(collected?'표시 없음':'미수집'));
  return '<div class="pm-mblock" id="mlM-'+mo+'">'
    +'<div class="pm-mhead"><b>'+y+'년 '+m+'월</b><span>'+esc(sub)+'</span></div>'
    +'<table class="pm-cal"><thead><tr>'
    +'<th class="sun">일</th><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th class="sat">토</th>'
    +'</tr></thead><tbody>'+body+'</tbody></table></div>';
}

/* ══ 날짜 상세 시트 ══════════════════════════════════════════════════════════
   도시마다 대한항공 행과 외항사 행을 같은 상자에 놓는다 — 같은 날·같은 노선 비교.
   대한항공은 좌석이 없는 날·운항이 없는 날도 그 도시에 노선이 있으면 행을 남겨
   '외항사는 있는데 대한항공은 없다'를 숨기지 않는다. */
function mlSheetEl(){return document.getElementById('mlSheet')}

function mlKERowHtml(route,ds){
  var v=keBit(route.code,MLS.dir,ds);
  var note=keNote(route.code,MLS.dir,ds.slice(0,7));
  var cab='',put='',pick=null,state='';
  if(note){
    state='<span class="ml-ke-state">'+esc((MGD.noService||[]).indexOf(route.code)>=0?'미운항 — 대한항공 부산발 직항 없음':'하계 스케줄 미개시 — 이 달은 조회 불가')+'</span>';
  }else if(v==null){
    state='<span class="ml-ke-state">이 날 미수집</span>';
  }else if(v&16){
    state='<span class="ml-ke-state">운항 없음</span>';
  }else if(!(v&7)){
    state='<span class="ml-ke-state">이 날 보너스 좌석 없음</span>';
  }else{
    var cs=keCabins(route,v).filter(mlCabinOK);
    if(!cs.length)state='<span class="ml-ke-state">고른 등급의 보너스 좌석 없음</span>';
    cs.forEach(function(c){if(!c.upg&&c.miles!=null&&(!pick||c.miles<pick.miles))pick=c});
    cab=cs.map(function(c){
      return '<span class="cb '+c.k+(c.upg?' u':'')+'">'+esc(c.short)+' <b>'+(c.upg?'승급':KR(c.miles))+'</b>'
        +' <i>'+esc(c.upg?'마일차감 없음':'평수기')+'</i></span>';
    }).join('');
    if(pick){
      var side=MLS.dir?'back':'go',sideKo=MLS.dir?'오는 편':'가는 편';
      put='<button type="button" class="pm-ds-put" data-ml-calc-put="'+side+'" data-ml-calc-prog="ke"'
        +' data-ml-calc-miles="'+pick.miles+'"'
        +' data-ml-calc-name="'+esc(mlDestName(route.code)+' 대한항공 '+pick.short)+'"'
        +' title="'+esc('대한항공 '+pick.short+' '+KR(pick.miles)+'마일을 '+sideKo+'에 넣습니다')+'">🧮 '+sideKo+'에</button>';
    }
  }
  return '<div class="pm-ds-row ml-ke-row">'
    +'<div class="pm-ds-pg"><b>🇰🇷 대한항공</b><span>스카이패스 · 공제표 편도</span></div>'
    +'<div class="pm-ds-cab">'+(cab+put+state)+'</div>'
    +'<div class="pm-ds-meta"><span class="seen">원천 '+esc(MGD.observedLabel||'—')+'</span>'
    +'<a class="pm-ds-go" href="'+KE_SEARCH+'" target="_blank" rel="noopener">대한항공 ↗</a></div>'
    +'</div>';
}

function mlPtRowHtml(x){
  var cs=x.cabins.slice();
  var pick=x.best;
  var side=MLS.dir?'back':'go',sideKo=MLS.dir?'오는 편':'가는 편';
  var put=pick?'<button type="button" class="pm-ds-put" data-ml-calc-put="'+side+'"'
      +' data-ml-calc-prog="'+esc(x.prog)+'"'
      +' data-ml-calc-miles="'+pick.miles+'"'
      +' data-ml-calc-name="'+esc(mlDestName(x.dest)+' '+(x.p.short||x.p.name)+' '+mlCabinLabel(pick))+'"'
      +' title="'+esc(mlCabinLabel(pick)+' '+KR(pick.miles)+'마일을 '+sideKo+'에 넣습니다')+'">🧮 '+sideKo+'에</button>':'';
  return '<div class="pm-ds-row">'
    +'<div class="pm-ds-pg"><b>'+esc(x.p.short||x.p.name)+'</b><span>'+esc(x.p.allianceName||'')+'</span></div>'
    +'<div class="pm-ds-cab">'+cs.map(function(c){
        return '<span class="cb '+c.k+'">'+esc(mlCabinShort(c))+' <b>'+KR(c.miles)+'</b> <i>'+esc(mlStopsText(c.stops))+'</i></span>';
      }).join('')+put+'</div>'
    +'<div class="pm-ds-meta"><span class="seen">최근 확인 '+esc(x.seen)+'</span>'
    +'<a class="pm-ds-go" href="'+esc(mlAppHref(x.p))+'" target="'+mlAppTarget(x.p)+'" rel="noopener">'+esc(x.p.urlLabel||'공식 사이트')+' ↗</a></div>'
    +'</div>';
}

function mlRoundBlock(ds){
  var od=1-MLS.dir,label=mlDirText(od),list=mlRowsForDateDir(ds,od);
  var cities={},best=null;
  list.forEach(function(x){
    cities[x.dest]=1;
    if(x.best&&(!best||x.best.miles<best.best.miles))best=x;
  });
  var nc=Object.keys(cities).length;
  return '<div class="pm-ds-round">'
    +'<div class="pm-ds-rh"><b>↔ 왕복 짝 — 같은 날 '+esc(label)+'</b>'
    +'<span>'+(best?'최저 '+KR(best.best.miles)+'마일 · '+KR(list.length)+'건 · '+KR(nc)+'개 도시 (대한항공 포함)':'이 날은 반대 방향 자료 없음')+'</span></div>'
    +(best?'<div class="pm-ds-rb"><span class="cb '+best.best.k+'">'+esc(mlDestName(best.dest))+' · '
        +esc(mlProgShort(best))+' '+esc(mlCabinShort(best.best))+' <b>'+KR(best.best.miles)+'</b> <i>'+esc(best.src==='ke'?'KE':mlStopsText(best.best.stops))+'</i></span></div>':'')
    +'<div class="pm-ds-rb"><button type="button" class="pm-ds-swap" data-ml-flip="'+esc(ds)+'">'
    +esc(label)+' 보고 방향 바꾸기 →</button></div>'
    +'</div>';
}

function mlProgramsBlock(){
  var ws=[];
  if(MLS.origin==='PUS'&&(MLS.prog==='all'||MLS.prog==='ke')&&(MLS.alliance==='all'||MLS.alliance==='skyteam'))ws.push(KE_PROG);
  if(MLS.prog!=='ke'){
    (PMD.programs||[]).forEach(function(p){
      if(MLS.prog!=='all'&&p.key!==MLS.prog)return;
      if(MLS.alliance!=='all'&&p.alliance!==MLS.alliance)return;
      ws.push(p);
    });
  }
  if(!ws.length)return '';
  return '<div class="pm-ds-gh">공식 사이트에서 직접 조회</div>'+mlAppsNote()
    +'<div class="pm-ds-sites">'+ws.map(function(p){
        return '<a class="pm-ds-site" href="'+esc(mlAppHref(p))+'" target="'+mlAppTarget(p)+'" rel="noopener"'+(p.key==='flyingblue'?' title="'+esc(p.name+' 공식 앱 또는 공식 웹으로 엽니다')+'"':'')+'>'
          +'<b>'+esc(p.short||p.name)+'</b>'
          +'<span>'+esc(p.name)+' · '+esc(p.allianceName||'')+'</span>'
          +'<i>공식 발권 ↗</i></a>';
      }).join('')+'</div>';
}

function mlOpenSheet(ds){
  var el=mlSheetEl();
  if(!el||!ds)return;
  var w=mlWin();
  var col=mlInRange(ds,w.cFrom,w.cTo);
  document.getElementById('mlDsTitle').textContent=mlDateLong(ds);
  document.getElementById('mlDsSub').innerHTML=esc(mlDirText(MLS.dir)+' · '+mlCondText()
    +' · 기준 대한항공 '+((MGD.observedLabel)||'—')+' / 외항사 '+(((mlMeta()||{}).observedLabel)||'—'));
  var body='';
  if(!col){
    body='<div class="pm-ds-warn"><b>이 날짜는 아직 수집하지 않았습니다.</b><br>'
      +'조회 사이트가 비로그인 화면에 '+esc(w.cFrom)+'~'+esc(w.cTo)+' 만 열어 주어, '+esc(ds)+' 은 조회하지 못했습니다. '
      +'값을 추측해 채우지 않았습니다 — 아래 공식 사이트에서 직접 조회해 주세요.</div>'
      +mlProgramsBlock();
  }else{
    var dayRows=mlRowsForDateDir(ds,MLS.dir);
    var by={};
    dayRows.forEach(function(x){(by[x.dest]=by[x.dest]||[]).push(x)});
    /* 대한항공 — 좌석이 없는 날도 노선이 있으면 행을 남긴다 */
    var keRoutes=[];
    if(MLS.origin==='PUS'&&(MLS.prog==='all'||MLS.prog==='ke')&&(MLS.alliance==='all'||MLS.alliance==='skyteam')){
      (MGD.routes||[]).forEach(function(r){
        if(MLS.dest!=='all'&&r.code!==MLS.dest)return;
        var v=keBit(r.code,MLS.dir,ds);
        if(v==null&&!keNote(r.code,MLS.dir,ds.slice(0,7)))return;
        keRoutes.push(r);
        by[r.code]=by[r.code]||[];
      });
    }
    var groups=Object.keys(by).map(function(code){
      var items=by[code];
      var pt=items.filter(function(x){return x.src==='pt'}).sort(function(a,b){
        return (a.best?a.best.miles:1e12)-(b.best?b.best.miles:1e12);
      });
      var keR=keRoutes.filter(function(r){return r.code===code})[0]||null;
      var keRow=items.filter(function(x){return x.src==='ke'})[0]||null;
      var min=null;
      items.forEach(function(x){if(x.best&&(min==null||x.best.miles<min))min=x.best.miles});
      return {code:code,pt:pt,keRoute:keR,keRow:keRow,min:min,n:items.length};
    }).sort(function(a,b){
      var am=a.min==null?1e12:a.min,bm=b.min==null?1e12:b.min;
      return am-bm;
    });
    if(!groups.length){
      body='<div class="pm-ds-warn"><b>이 날짜에는 표시된 보너스 좌석이 없습니다.</b><br>'
        +'조회 사이트가 이 노선·날짜에 보너스 좌석을 보여 주지 않았습니다(좌석이 없다는 뜻과 조회되지 않았다는 뜻을 구분해 주지 않습니다). '
        +'아래 공식 사이트에서 직접 확인해 주세요.</div>'+mlProgramsBlock();
    }else{
      body=groups.map(function(g){
        var head='<div class="pm-ds-rt"><b>'+esc(mlDestName(g.code))+'</b><span>'
          +(g.min!=null?'최저 '+KR(g.min)+'마일 · '+KR(g.n)+'건':'이 날 표시 없음')+'</span></div>';
        var keHtml=g.keRoute?mlKERowHtml(g.keRoute,ds):'';
        var ptHtml=g.pt.map(mlPtRowHtml).join('');
        var none='';
        if(!ptHtml&&!keHtml)none='<div class="pm-ds-warn" style="margin:7px 10px">이 도시는 이 날 자료가 없습니다.</div>';
        return '<div class="pm-ds-route">'+head+keHtml+ptHtml+none+'</div>';
      }).join('')
        +mlProgramsBlock();
    }
  }
  document.getElementById('mlDsBody').innerHTML=mlRoundBlock(ds)+body;
  document.getElementById('mlDsNote').innerHTML='필요 마일은 조회 사이트가 그 등급에 표시한 값(대한항공은 공제표 값)이고, 같은 노선이라도 날짜·경유 편수·판매 조건에 따라 달라집니다. '
    +'대한항공 일반석·프레스티지는 <b>평수기 편도</b> 값이며 성수기 탑승일은 더 큽니다(공제표의 성수기 열 참고). '
    +'프레스티지 승급(U)은 마일 차감 없이 승급만 하는 좌석이라 현금 운임이 필요합니다. 세금·수수료는 마일과 별도이며 좌석 수량은 조회 사이트에 없어 표시하지 않습니다. '
    +'예약 전 <b>항공사 공식 사이트에서 재확인</b>해 주세요.';
  el.classList.add('show');
  el.setAttribute('aria-hidden','false');
  var close=document.getElementById('mlDsClose');
  if(close&&close.focus)close.focus({preventScroll:true});
}
function mlCloseSheet(){
  var el=mlSheetEl();
  if(!el)return;
  el.classList.remove('show');
  el.setAttribute('aria-hidden','true');
}

/* ══ 🧮 마일리지 계산기 ═════════════════════════════════════════
   프로그램(대한항공 + 외항사 9개 + 직접 입력)마다 보유 마일과 1마일 참고 가치를 따로 저장한다.
   가는 편·오는 편 마일과 인원으로 총 필요 마일을, 현금 항공권 가격으로 1마일당 원화 가치를 계산해
   그 프로그램의 참고 가치와 나란히 보여 준다. 날짜 상세 시트의 「🧮 가는 편에 / 오는 편에」를 누르면
   그 행의 프로그램이 자동으로 골라지고 마일이 그대로 들어온다. 값은 이 기기(localStorage)에만 저장. */
var ML_CALC_KEY='teambusan.mlcalc.v2';
var ML_CALC={trip:'rt',pax:1,go:0,back:0,tax:0,cash:0,open:true,prog:'ke',byProg:{}};
var ML_CALC_READY=false,ML_CALC_FLASH_T=null;
var ML_CALC_RATE_DEFAULT=15;

function mlNum(v){
  var n=parseInt(String(v==null?'':v).replace(/[^0-9]/g,''),10);
  return isNaN(n)?0:n;
}
function mlRateNum(v){
  var n=parseFloat(String(v==null?'':v).replace(/[^0-9.]/g,''));
  return isNaN(n)?0:n;
}
function mcEl(id){return document.getElementById(id)}
function mlCalcProgList(){
  var out=[['ke','🇰🇷 대한항공(스카이패스)']];
  var progs=(PDS.PUS&&PDS.PUS.programs)||(PDS.ICN&&PDS.ICN.programs)||(PMD.programs||[]);
  (progs||[]).forEach(function(p){out.push([p.key,p.short||p.name])});
  out.push(['custom','직접 입력(프로그램 없음)']);
  return out;
}
function mlCalcProgName(k){
  var hit=mlCalcProgList().filter(function(o){return o[0]===k})[0];
  return hit?hit[1]:(k==='custom'?'직접 입력':k);
}
function mlCalcSlot(k){
  k=k||ML_CALC.prog||'ke';
  if(!ML_CALC.byProg[k]||typeof ML_CALC.byProg[k]!=='object')ML_CALC.byProg[k]={have:0,rate:ML_CALC_RATE_DEFAULT};
  var s=ML_CALC.byProg[k];
  if(s.rate==null)s.rate=ML_CALC_RATE_DEFAULT;
  return s;
}
function mlCalcLoad(){
  if(ML_CALC_READY)return ML_CALC;
  ML_CALC_READY=true;
  try{
    var raw=window.localStorage.getItem(ML_CALC_KEY);
    if(raw){
      var o=JSON.parse(raw)||{};
      if(o.trip==='ow'||o.trip==='rt')ML_CALC.trip=o.trip;
      var pax=mlNum(o.pax);if(pax>=1&&pax<=9)ML_CALC.pax=pax;
      ML_CALC.go=mlNum(o.go);ML_CALC.back=mlNum(o.back);
      ML_CALC.tax=mlNum(o.tax);ML_CALC.cash=mlNum(o.cash);
      if(o.open===false)ML_CALC.open=false;
      if(o.prog)ML_CALC.prog=String(o.prog);
      var bp=o.byProg||{};
      for(var k in bp){
        if(!Object.prototype.hasOwnProperty.call(bp,k))continue;
        var v=bp[k]||{};
        ML_CALC.byProg[k]={have:mlNum(v.have),rate:mlRateNum(v.rate)||ML_CALC_RATE_DEFAULT};
      }
    }
  }catch(e){}
  mlCalcSlot(ML_CALC.prog);
  return ML_CALC;
}
function mlCalcSave(){
  try{window.localStorage.setItem(ML_CALC_KEY,JSON.stringify(ML_CALC))}catch(e){}
}
function mlCalcFillProgs(){
  var sel=mcEl('mlCalcProg');
  if(!sel)return;
  var list=mlCalcProgList();
  var cur=ML_CALC.prog||'ke';
  var html=list.map(function(o){
    return '<option value="'+esc(o[0])+'">'+esc(o[1])+'</option>';
  }).join('');
  if(sel.__html!==html){sel.innerHTML=html;sel.__html=html}
  var has=list.filter(function(o){return o[0]===cur}).length>0;
  if(!has){cur='custom';ML_CALC.prog='custom'}
  sel.value=cur;
}
function mlCalcPaintNum(id,n,fmt){
  var el=mcEl(id);
  if(el&&document.activeElement!==el)el.value=n?(fmt?fmt(n):KR(n)):'';
}
function mlCalcPaint(){
  mlCalcLoad();
  mlCalcFillProgs();
  var trip=mcEl('mlCalcTrip');
  if(trip){
    [].forEach.call(trip.querySelectorAll('button'),function(b){
      var on=b.getAttribute('data-ml-trip')===ML_CALC.trip;
      b.classList.toggle('on',on);
      b.setAttribute('aria-pressed',on?'true':'false');
    });
  }
  var pax=mcEl('mlCalcPax');if(pax)pax.value=String(ML_CALC.pax);
  var slot=mlCalcSlot();
  mlCalcPaintNum('mlCalcGo',ML_CALC.go);
  mlCalcPaintNum('mlCalcBack',ML_CALC.back);
  mlCalcPaintNum('mlCalcHave',slot.have);
  mlCalcPaintNum('mlCalcRate',slot.rate,function(n){
    return (Math.round(n*100)/100)+'';    /* 15 · 12.5 — 쉼표 없이 */
  });
  mlCalcPaintNum('mlCalcTax',ML_CALC.tax);
  mlCalcPaintNum('mlCalcCash',ML_CALC.cash);
  var ow=ML_CALC.trip==='ow';
  var bf=mcEl('mlCalcBackF');if(bf)bf.classList.toggle('off',ow);
  var bi=mcEl('mlCalcBack');if(bi)bi.disabled=ow;
  mlCalcOut();
}
function mlCalcOut(){
  var out=mcEl('mlCalcOut'),sum=mcEl('mlCalcSum');
  if(!out)return;
  var tripKo=ML_CALC.trip==='ow'?'편도':'왕복';
  var per=ML_CALC.go+(ML_CALC.trip==='rt'?ML_CALC.back:0);
  var total=per*ML_CALC.pax;
  var slot=mlCalcSlot();
  var progName=mlCalcProgName(ML_CALC.prog);
  var eff=ML_CALC.cash-ML_CALC.tax;
  var value=(ML_CALC.cash>0&&eff>0&&total>0)?((eff*ML_CALC.pax)/total):null;
  var rate=slot.rate||0;
  if(sum)sum.textContent=progName+' · '+tripKo+' · '+ML_CALC.pax+'명'
    +(total?' · '+KR(total)+'마일':' · 마일을 넣어 주세요')
    +(value!=null?' · '+(Math.round(value*10)/10).toFixed(1)+'원/마일':'');
  if(!total){
    out.innerHTML='<div class="pm-calc-empty">가는 편 마일을 적으면 총 필요 마일을 계산합니다. '
      +'달력에서 날짜를 눌러 열린 상세에서 <b>「🧮 가는 편에」·「오는 편에」</b>를 누르면 그 행의 마일이 들어오고 '
      +'<b>프로그램도 그 행(대한항공 · 외항사)으로 바뀝니다</b>.</div>';
    return;
  }
  var sub='1인 '+KR(per)+'마일'+(ML_CALC.trip==='rt'
    ?'(가는 '+KR(ML_CALC.go)+' + 오는 '+KR(ML_CALC.back)+')'
    :'(가는 편만)')+' × '+ML_CALC.pax+'명';
  var html='<div class="pm-co-main"><div class="pm-co-big">'+KR(total)+'<small>마일</small></div>'
    +'<div class="pm-co-sub">'+esc(sub)+'</div></div><div class="pm-co-rows">';
  /* 보유 마일 — 프로그램별로 따로 저장한 값 */
  if(slot.have>0){
    var rest=slot.have-total;
    html+='<div class="pm-co-row"><span class="k">보유 마일 · '+esc(progName)+'</span>'
      +(rest>=0?'<b class="ok">'+KR(rest)+'마일 남음</b><span class="f">보유 '+KR(slot.have)+'마일로 가능</span>'
               :'<b class="lack">'+KR(-rest)+'마일 부족</b><span class="f">보유 '+KR(slot.have)+'마일</span>')
      +'</div>';
  }else{
    html+='<div class="pm-co-row"><span class="k">보유 마일 · '+esc(progName)+'</span><b class="dim">넣으면 부족·잔여를 계산합니다</b></div>';
  }
  /* 1마일 참고 가치 — 프로그램별 */
  if(rate>0){
    html+='<div class="pm-co-row"><span class="k">참고 가치 · '+esc(progName)+'</span><b>'+rate+'원/마일</b>'
      +'<span class="f">× '+KR(total)+'마일 = '+KR(Math.round(rate*total))+'원어치</span></div>';
  }
  /* 계산된 1마일당 원화 가치 — 현금가와 비교 */
  if(ML_CALC.cash>0){
    if(value==null){
      html+='<div class="pm-co-row"><span class="k">계산된 1마일당 가치</span><b class="dim">비교 가격이 세금보다 낮아 계산하지 않았습니다</b></div>';
    }else{
      var vTxt=(Math.round(value*10)/10).toFixed(1);
      var good=rate>0?value>=rate:value>=15;
      html+='<div class="pm-co-row"><span class="k">계산된 1마일당 가치</span><b>'+vTxt+'원/마일</b>'
        +'<i class="pm-co-badge'+(good?'':' low')+'">'+(good
          ?(rate>0?rate+'원 참고값 이상 · 마일 쪽이 유리한 편':'15원/마일 이상 · 마일 쪽이 유리한 편')
          :(rate>0?rate+'원 참고값 미만 · 현금 구매가 나을 수 있음':'15원/마일 미만 · 현금 구매가 나을 수 있음'))+'</i></div>'
        +'<div class="pm-co-row"><span class="f">현금 '+KR(ML_CALC.cash)+' − 유류·세금 '+KR(ML_CALC.tax)+' = '+KR(eff)+'원 ÷ 1인 '+KR(per)+'마일'
        +(ML_CALC.pax>1?' · 세금 뺀 현금 기준 총 '+KR(Math.round(eff*ML_CALC.pax))+'원어치':'')+'</span></div>';
    }
  }else{
    html+='<div class="pm-co-row"><span class="k">계산된 1마일당 가치</span><b class="dim">비교 현금 항공권 가격을 넣으면 계산합니다</b></div>';
  }
  html+='</div><div class="pm-co-foot"><button type="button" id="mlCalcClear">입력 지우기</button></div>';
  out.innerHTML=html;
}
function mlCalcInit(){
  mlCalcLoad();
  var el=mcEl('mlCalc');
  if(!el)return;
  if(el.tagName==='DETAILS'){
    el.open=ML_CALC.open!==false;
    if(!el.__mlTog){
      el.__mlTog=true;
      el.addEventListener('toggle',function(){
        ML_CALC.open=el.open;mlCalcSave();
        if(el.open)mlCalcPaint();
      });
    }
  }
  mlCalcPaint();
}
function mlRenderCalcInit(){mlCalcInit()}
/* 날짜 상세 시트의 버튼으로 그 행의 마일과 프로그램을 계산기에 넣는다 */
function mlCalcPut(side,miles,name,prog){
  if(!miles)return;
  mlCalcLoad();
  var wasOw=ML_CALC.trip==='ow';
  if(prog)ML_CALC.prog=prog;
  if(side==='back'){ML_CALC.trip='rt';ML_CALC.back=miles}else{ML_CALC.go=miles}
  ML_CALC.open=true;
  mlCalcSave();mlCalcPaint();
  var el=mcEl('mlCalc');
  if(el){
    if(el.tagName==='DETAILS')el.open=true;
    if(el.scrollIntoView)el.scrollIntoView({block:'center',behavior:'smooth'});
  }
  mlCloseSheet();
  var fl=mcEl('mlCalcFlash');
  if(fl){
    fl.textContent=(side==='back'?'오는 편':'가는 편')+'에 '+KR(miles)+'마일을 넣었습니다'
      +' · 프로그램 '+mlCalcProgName(ML_CALC.prog)
      +(name?' · '+name:'')+(side==='back'&&wasOw?' (왕복으로 바꿨습니다)':'');
    fl.classList.add('on');
    clearTimeout(ML_CALC_FLASH_T);
    ML_CALC_FLASH_T=setTimeout(function(){
      var cur=mcEl('mlCalcFlash');
      if(cur){cur.classList.remove('on');cur.textContent=''}
    },4200);
  }
}

/* ══ 🔁 대한항공 왕복 후보 · 🆕 좌석 변동 · 🧮 공제표 ═══════════ 여기까지 통합 탭은 대한항공
   자료(tab8_mileage.json)의 서브뷰를 그대로 살려 둔다. 이 세 보기는 대한항공만 다룬다
   (외항사는 위 통합 달력·날짜 상세에서 본다). */
function mlKeRoutesList(){
  return (MGD.routes||[]).map(function(r){return r});
}
function mlKeFirstRoute(){
  var cur=MLS.keRoute&&keRoute(MLS.keRoute);
  if(cur)return cur.code;
  var list=mlKeRoutesList().filter(function(r){return keHasData(r.code)});
  if(list.length)return list[0].code;
  var any=mlKeRoutesList()[0];
  return any?any.code:'';
}
function mlRenderKeRoutes(){
  var el=document.getElementById('mlKeRoutes');
  if(!el)return;
  var first=mlKeFirstRoute();
  if(MLS.keRoute!==first)MLS.keRoute=first;
  el.innerHTML=mlKeRoutesList().map(function(r){
    var on=r.code===MLS.keRoute;
    var has=keHasData(r.code);
    return '<button type="button" class="'+(on?'on':'')+'" data-ml-ke-route="'+esc(r.code)+'" aria-pressed="'+(on?'true':'false')+'"'
      +' title="'+(has?'수집 '+(keDates(r.code,0).length+keDates(r.code,1).length)+'칸':'아직 수집하지 않은 노선')+'">'
      +'<b>'+esc(r.code)+'</b>'+esc(r.city)+(has?'':' <span style="color:#b6bac1">·</span>')+'</button>';
  }).join('');
}
function mlSeatBadges(v,lim){
  var map=[['e','E',1],['b','P',2],['u','U',4]],out='';
  var n=0;
  map.forEach(function(x){
    if((v&x[2])===0)return;
    if(n++>=(lim||3)){return}
    out+='<span class="bd '+x[0]+'">'+x[1]+'</span>';
  });
  return out;
}
function mlAriaForKe(v,winEnd,ds){
  if(winEnd&&ds>winEnd)return '원천 미제공';
  if(v==null)return '미수집';
  if(v&16)return '운항편 없음';
  if(!v)return '보너스 좌석 없음';
  var s=[];
  if(v&1)s.push('일반석 보너스');
  if(v&2)s.push('프레스티지 보너스');
  if(v&4)s.push('프레스티지 승급');
  return s.join(' ');
}
function mlAddDays(ds,n){
  var d=new Date(ds+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);
  return d.toISOString().slice(0,10);
}
function mlRenderRound(){
  var listEl=document.getElementById('mlRoundList');
  if(!listEl)return;
  var code=MLS.keRoute||mlKeFirstRoute(),r=keRoute(code);
  var cnt=document.getElementById('mlRoundCount');
  if(!r){
    listEl.innerHTML='<div class="mg-empty">노선을 고르면 왕복 후보를 계산합니다.</div>';
    if(cnt)cnt.textContent='';
    return;
  }
  var outs=keDates(code,0).filter(function(d){
    var v=keBit(code,0,d);
    if(!v||(v&16)||!(v&7))return false;
    if(MLS.keWeekend){
      var w=new Date(d+'T12:00:00Z').getUTCDay();
      if(w!==5&&w!==6)return false;
    }
    return true;
  });
  var ins={};
  keDates(code,1).forEach(function(d){ins[d]=keBit(code,1,d)});
  var rows=outs.map(function(d){
    var back=mlAddDays(d,MLS.keNights);
    var rv=(back in ins)?ins[back]:null;
    if(rv!=null&&((rv&16)||!(rv&7)))rv=0;      /* 운항 없음·좌석 없음은 0 으로 — 미수집(null)과 구분 */
    return {out:d,back:back,ov:keBit(code,0,d),rv:rv};
  });
  if(cnt)cnt.textContent=rows.length?('후보 '+KR(rows.length)+'개'):'';
  if(!rows.length){
    listEl.innerHTML='<div class="mg-empty">이 조건에 맞는 후보가 없습니다.<br>노선·숙박 일수·주말 조건을 바꿔 보세요.</div>';
    mlRoundNote('');
    return;
  }
  var limit=24;
  listEl.innerHTML=rows.slice(0,limit).map(function(x){
    var cabin=(x.ov&2)?'pre':'eco';
    var m1=mlMilesFor(r.region,cabin,'off','ow');
    var total=m1==null?null:m1*2;
    var backTxt=(x.rv==null)?'귀국편 좌석 미수집':(x.rv?'귀국편 보너스 좌석 있음':'귀국편 보너스 좌석 없음');
    return '<div class="mg-card">'
      +'<div class="top"><b>'+esc(r.code)+' '+esc(r.city)+'</b><span>'+esc(mlDateKo(x.out))+' → '+esc(mlDateKo(x.back))+' · '+MLS.keNights+'박</span></div>'
      +'<div class="mg-leg"><span class="k">가는 편</span><span class="v">'+esc(mlDateKo(x.out))+' '+mlSeatBadges(x.ov,3)+'</span>'
      +'<span class="k">오는 편</span><span class="v">'+(x.rv==null?'<span style="color:#9aa0a6">미수집</span>':esc(mlDateKo(x.back))+' '+(x.rv?mlSeatBadges(x.rv,3):'<span style="color:#9aa0a6">좌석 없음</span>'))+'</span></div>'
      +'<div class="miles">필요 마일 1인 <b>'+(total==null?'—':KR(total)+'마일')+'</b> <span style="color:#6b7280">('+(cabin==='pre'?'프레스티지':'일반석')+' 왕복·평수기 · 편도 '+KR(m1)+'×2)</span></div>'
      +'<div class="miles" style="border-top:0;padding-top:0;font-size:10px;color:#6b7280">'+esc(backTxt)+' · 2인 좌석 수량은 항공사 화면 확인 · 수수료 별도</div>'
      +'<div class="acts"><button type="button" data-ml-day="'+esc(x.out)+'">가는 편 상세</button>'
      +'<a class="go" href="'+KE_SEARCH+'" target="_blank" rel="noopener">대한항공 예약</a></div>'
      +'</div>';
  }).join('');
  mlRoundNote(rows.length>limit?'후보가 많아 앞선 '+limit+'개만 보여 줍니다.':'');
}
function mlRoundNote(t){
  var el=document.getElementById('mlRoundNote');
  if(!el)return;
  el.innerHTML=(t?esc(t)+'<br>':'')
    +'가는 편에 보너스 좌석이 있는 날만 골라 '+MLS.keNights+'박 뒤 같은 노선 귀국편을 붙였습니다. '
    +'필요 마일은 <b>편도 공제표 × 2(평수기)</b>로 계산한 값이고, 성수기 탑승일은 더 큽니다. '
    +'귀국편 좌석은 원천의 반대 방향 조회분만 표시하며, 받지 않은 날은 <b>미수집</b>으로 둡니다. '
    +'2인 이상 동시 예약 가능 여부는 원천에 수량이 없어 단정하지 않습니다 — 항공사 화면에서 확인해 주세요.';
}
function mlMilesFor(region,cabin,season,trip){
  var row=keChart(region);
  if(!row)return null;
  var col=cabin==='eco'?2:cabin==='pre'?4:6;
  var v=row[col+(season==='peak'?1:0)];
  if(v==null)return null;
  return v*(trip==='ow'?1:2);
}
function mlRenderNew(){
  var el=document.getElementById('mlNewBody');
  if(!el)return;
  var cnt=document.getElementById('mlNewCount');
  var nb=document.getElementById('mlNewBadge');
  var nNew=(MGD.newSeats||[]).length,nGone=(MGD.goneSeats||[]).length;
  if(nb){nb.textContent=KR(nNew);nb.hidden=!nNew}
  if(!MGD.hasPrev){
    el.innerHTML='<div class="mg-empty"><b>첫 수집입니다.</b><br>오늘 스냅샷을 기준으로 저장해 두었고, 다음 수집부터 <b>새로 열린 좌석</b>과 <b>사라진 좌석</b>을 이 자리에서 보여 드립니다.<br>'
      +'지금은 통합 달력에서 날짜별 좌석을 먼저 확인해 보세요.</div>';
    if(cnt)cnt.textContent='';
  }else{
    var rows=[];
    var nw=(MGD.newSeats||[]).map(function(x){return {k:'new',x:x}});
    var gn=(MGD.goneSeats||[]).map(function(x){return {k:'gone',x:x}});
    if(MLS.keNewKind==='new')rows=nw;
    else if(MLS.keNewKind==='gone')rows=gn;
    else rows=nw.concat(gn);
    if(!rows.length)el.innerHTML='<div class="mg-empty">직전 수집과 비교해 바뀐 좌석이 없습니다.</div>';
    else el.innerHTML='<table class="mg-tbl"><thead><tr><th>노선</th><th>날짜</th><th>방향</th><th>등급</th><th>변화</th><th></th></tr></thead><tbody>'
      +rows.slice(0,120).map(function(o){
        var r=keRoute(o.x[0]);
        return '<tr><td class="b">'+esc(o.x[0])+' '+esc(r?r.city:'')+'</td><td>'+esc(o.x[2]?mlDateKo(o.x[2]):'')+'</td>'
          +'<td>'+(o.x[1]?'오는 편':'가는 편')+'</td><td>'+mlSeatBadges(o.x[3],3)+'</td>'
          +'<td>'+(o.k==='new'?'<b style="color:#c2410c">새로 열림</b>':'<b style="color:#6b7280">사라짐</b>')+'</td>'
          +'<td><button type="button" class="open" data-ml-day="'+esc(o.x[2])+'" data-ml-ke-route="'+esc(o.x[0])+'" data-ml-dir="'+o.x[1]+'">보기</button></td></tr>';
      }).join('')+'</tbody></table>';
    if(cnt)cnt.textContent='새로 열림 '+KR(nNew)+' · 사라짐 '+KR(nGone);
  }
  var note=document.getElementById('mlNewNote');
  if(note)note.innerHTML='직전 수집 스냅샷과 비교해 <b>없음 → 있음</b>으로 바뀐 칸을 새로 열린 좌석으로 셉니다(비교 기준 '+(MGD.prevLabel?esc(MGD.prevLabel):'—')+'). '
    +'원천이 하루 1회만 갱신되므로, 하루 안에 열렸다 닫힌 좌석은 잡히지 않을 수 있습니다.';
}
function mlRenderChart(){
  var out=document.getElementById('mlChartOut');
  if(!out)return;
  var haveEl=document.getElementById('mlChartHave');
  var have=parseInt(String(haveEl?haveEl.value:'').replace(/[^0-9]/g,''),10)||0;
  var cabin=(document.getElementById('mlChartCabin')||{}).value||'pre';
  var region=(document.getElementById('mlChartRegion')||{}).value||'jp_cn_ne';
  var trip=(document.getElementById('mlChartTrip')||{}).value||'rt';
  var season=(document.getElementById('mlChartSeason')||{}).value||'off';
  var need=mlMilesFor(region,cabin,season,trip);
  var row=keChart(region);
  var label=row?row[1]:region;
  var html='';
  if(need==null){
    html='<div class="big">—</div><div class="sub">이 등급은 공제표에 값이 없습니다(일등석은 국내선 미운영).</div>';
  }else{
    var rest=have-need;
    html='<div class="big">'+KR(need)+'마일</div>'
      +'<div class="sub">'+esc(label)+' · '+(cabin==='eco'?'일반석':cabin==='pre'?'프레스티지':'일등석')+' · '+(trip==='ow'?'편도':'왕복')+' · '+(season==='peak'?'성수기':'평수기')+'</div>'
      +'<div class="rest">'+(rest>=0
        ?'보유 마일로 <b>가능</b> — 남는 마일 <b>'+KR(rest)+'</b>'
        :'<b style="color:#c2410c">'+KR(-rest)+'마일 부족</b>')+'</div>';
  }
  var opts=[['jp_cn_ne','일본·중국·동북아'],['sea_guam','동남아·괌'],['sw_asia','서남아'],['us_eu_me_oc','미주·유럽·중동·대양주']];
  html+='<ul class="regions">'+opts.map(function(o){
    var n=mlMilesFor(o[0],cabin,season,trip);
    if(n==null)return '';
    var ok=have>=n;
    return '<li class="'+(ok?'':'nope')+'"><span>'+esc(o[1])+'</span><b>'+KR(n)+'마일'+(ok?' ✓':'')+'</b></li>';
  }).join('')+'</ul>';
  out.innerHTML=html;
  var note=document.getElementById('mlChartNote');
  if(note)note.innerHTML='공제표는 항공사가 공개한 <b>편도</b> 값이며, 왕복은 ×2(같은 지역 기준)로 계산했습니다. '
    +'실제 왕복은 <b>가는 편과 오는 편의 탑승일 시즌을 각각</b> 적용하므로 두 값의 합이 위 계산과 다를 수 있습니다. '
    +'성수기 지정일(명절·연휴·성수기 기간)은 항공사 공지 기준이며, <a href="'+KE_CHART+'" target="_blank" rel="noopener">공식 공제표</a>에서 확인해 주세요. '
    +'수수료(세금·유류할증료)는 마일과 별도입니다 — 실제 금액은 예약 화면 값입니다. '
    +'프로그램별 보유 마일·참고 가치로 계산하려면 위쪽 <b>🧮 마일리지 계산기</b>를 쓰세요.';
}

function mlRenderNote(){
  var el=document.getElementById('mlNote');
  if(!el)return;
  var m=mlMeta()||{};
  var cov=(m.coverage||[]).map(function(c){
    var d=(c.rowsIn!=null&&c.rowsOut!=null)?' (출발 '+KR(c.rowsOut)+' · 도착 '+KR(c.rowsIn)+')':'';
    return esc(String(c.name||'').replace(/원천/g,'조회 사이트'))+' '+KR(c.rows)+d+(c.note?' — '+esc(String(c.note).replace(/원천/g,'조회 사이트')):'');
  });
  var have=(m.coverage||[]).filter(function(c){return c.rows>0}).length;
  var all=(m.coverage||[]).length||9;
  var keRoutes=mlKeRoutesList().filter(function(r){return keHasData(r.code)});
  var keTxt=keRoutes.map(function(r){return r.code+' '+r.city+' '+KR(keDates(r.code,0).length+keDates(r.code,1).length)+'칸'}).join(' · ');
  el.innerHTML='<details class="notefold">'
    +'<summary>📑 안내 및 조회 범위 보기 <small>대한항공 '+KR(keRoutes.length)+'/'+KR(mlKeRoutesList().length)+'노선 · 외항사 '+all+'개 중 '+have+'곳 · 읽는 법</small></summary>'
    +'<div class="ml-notebody">'
    +'<b>🇰🇷 대한항공(스카이패스)</b> — '+esc(keTxt||'수집한 노선 없음')
    +'<p>부산(PUS)을 드나드는 14개 노선을 하루 1회 갱신되는 공개 현황에서 옮깁니다. 대한항공 부산발 직항이 없는 5개 노선(후쿠오카·홍콩·싱가포르·하노이·호찌민)은 <b>미운항</b>, 2027년 4월 이후 하계 스케줄이 열리지 않은 6개 노선(오사카·나고야·삿포로·칭다오·방콕·다낭)은 <b>하계 미개시</b>로 적어 미수집과 구분합니다. 필요 마일은 공제표(편도) 값이고, 좌석 수량·수수료는 원천에 없어 표시하지 않습니다.</p>'
    +'<b>외항사 9개 프로그램</b> — '+(cov.length?cov.join(' · '):'—')
    +'<p>조회 사이트마다 '+esc(mlOriginName())+' 노선을 얼마나 추적하는지가 다릅니다. 자료가 0건인 프로그램은 <b>보너스 좌석이 없다는 뜻이 아니라, 그 조회 사이트가 '+esc(mlOriginName())+' 노선을 추적하지 않는다는 뜻</b>입니다 — 해당 항공사 공식 사이트에서 직접 조회해 주세요.</p>'
    +'<p>같은 날·같은 도시의 <b>대한항공과 외항사 마일을 한 시트에서</b> 견주도록 합쳤습니다. 대한항공 일반석은 외항사 이코노미, 프레스티지는 비즈니스와 같은 줄에 놓았습니다. 국내선(김포·제주)은 국제선 여행과 성격이 달라 이 화면에서 뺐습니다. 세금·수수료는 마일과 별도입니다.</p>'
    +'</div></details>';
}

function mlTabBadge(){
  var tb=document.querySelector('[data-tab="mileage"] b');
  if(!tb)return;
  var n=mlBaseStat();
  tb.textContent=KR(n.rows);
  tb.hidden=false;
}

/* ── 이벤트 ───────────────────────────────────────────────── */
document.addEventListener('click',function(e){
  var t=e.target;
  if(!t||!t.closest)return;
  var sheet=mlSheetEl();
  if(sheet&&sheet.classList.contains('show')&&t.closest('#mlSheet')){
    var flb=t.closest('[data-ml-flip]');
    if(flb){
      var fd=flb.getAttribute('data-ml-flip');
      MLS.dir=1-MLS.dir;MLS.dest='all';
      renderMileage();
      mlOpenSheet(fd);
      return;
    }
    if(t.id==='mlDsClose'||t===sheet)mlCloseSheet();
    if(t.closest('a.pm-ds-go')||t.closest('a.pm-ds-site')){
      setTimeout(function(){var cur=mlSheetEl();if(cur&&cur.classList.contains('show'))mlCloseSheet()},350);
    }
    return;
  }
  var og=t.closest('[data-ml-origin]');
  if(og){mlPickOrigin(og.getAttribute('data-ml-origin'));return}
  var dv=t.closest('#mlDir [data-ml-dir]');
  if(dv){MLS.dir=+dv.getAttribute('data-ml-dir');MLS.dest='all';renderMileage();return}
  var al=t.closest('[data-ml-alliance]');
  if(al){MLS.alliance=al.getAttribute('data-ml-alliance');MLS.prog='all';renderMileage();return}
  var pg=t.closest('[data-ml-prog]');
  if(pg){MLS.prog=pg.getAttribute('data-ml-prog');renderMileage();return}
  var ds=t.closest('[data-ml-dest]');
  if(ds){
    var v=ds.getAttribute('data-ml-dest');
    MLS.dest=(v==='all'||MLS.dest===v)?'all':v;
    renderMileage();
    var box=document.getElementById(MLS.list==='list'?'mlList':'mlCal');
    if(box&&MLS.dest!=='all'&&box.scrollIntoView)box.scrollIntoView({block:'start',behavior:'smooth'});
    return;
  }
  if(t.closest('#mlDirect')){MLS.direct=!MLS.direct;renderMileage();return}
  var vw=t.closest('[data-ml-view]');
  if(vw){MLS.view=vw.getAttribute('data-ml-view');renderMileage();return}
  var lw=t.closest('[data-ml-list]');
  if(lw){MLS.list=lw.getAttribute('data-ml-list');
    var seg=document.getElementById('mlListSwitch');
    if(seg)[].forEach.call(seg.querySelectorAll('[data-ml-list]'),function(b){
      var on=b.getAttribute('data-ml-list')===MLS.list;
      b.classList.toggle('on',on);b.setAttribute('aria-pressed',on?'true':'false');
    });
    mlRenderCal();mlRenderList();return;
  }
  var put=t.closest('[data-ml-calc-put]');
  if(put){
    e.preventDefault();
    mlCalcPut(put.getAttribute('data-ml-calc-put'),mlNum(put.getAttribute('data-ml-calc-miles')),
      put.getAttribute('data-ml-calc-name')||'',put.getAttribute('data-ml-calc-prog')||'');
    return;
  }
  if(t.closest('#mlCalc')){
    var tb=t.closest('[data-ml-trip]');
    if(tb){
      mlCalcLoad();
      ML_CALC.trip=tb.getAttribute('data-ml-trip')==='ow'?'ow':'rt';
      mlCalcSave();mlCalcPaint();
      return;
    }
    if(t.closest('#mlCalcClear')){
      mlCalcLoad();
      var slot=mlCalcSlot();
      ML_CALC.go=0;ML_CALC.back=0;ML_CALC.tax=0;ML_CALC.cash=0;slot.have=0;
      mlCalcSave();mlCalcPaint();
      var fl=mcEl('mlCalcFlash');if(fl){fl.classList.remove('on');fl.textContent=''}
      return;
    }
  }
  if(t.closest('#mlWeekend')){
    MLS.keWeekend=!MLS.keWeekend;
    t.closest('#mlWeekend').setAttribute('aria-pressed',MLS.keWeekend?'true':'false');
    mlRenderRound();return;
  }
  if(t.closest('a'))return;                       /* 카드·칸 안의 링크는 그대로 새 탭 */
  var kr=t.closest('[data-ml-ke-route]');
  if(kr&&!t.closest('[data-ml-day]')){
    MLS.keRoute=kr.getAttribute('data-ml-ke-route');
    mlRenderKeRoutes();mlRenderRound();return;
  }
  var jp=t.closest('[data-ml-jump]');
  if(jp){
    var mo=jp.getAttribute('data-ml-jump');
    var mb=document.getElementById('mlM-'+mo);
    if(mb&&mb.scrollIntoView)mb.scrollIntoView({block:'start',behavior:'smooth'});
    return;
  }
  var day=t.closest('[data-ml-day]');
  if(day){
    e.preventDefault();
    var dr=day.getAttribute('data-ml-dir'),rt=day.getAttribute('data-ml-ke-route');
    if(dr!=null)MLS.dir=+dr;
    if(rt)MLS.keRoute=rt;
    mlOpenSheet(day.getAttribute('data-ml-day'));
    return;
  }
});
document.addEventListener('change',function(e){
  var t=e.target;
  if(!t||!t.id)return;
  if(t.id==='mlCabin'){MLS.cabin=t.value;renderMileage();return}
  if(t.id==='mlSort'){MLS.sort=t.value;renderMileage();return}
  if(t.id==='mlNights'){MLS.keNights=+t.value;mlRenderRound();return}
  if(t.id==='mlNewKind'){MLS.keNewKind=t.value;mlRenderNew();return}
  if(t.id==='mlChartHave'||t.id==='mlChartCabin'||t.id==='mlChartRegion'||t.id==='mlChartTrip'||t.id==='mlChartSeason'){mlRenderChart();return}
  if(t.id==='mlCalcProg'){
    mlCalcLoad();
    ML_CALC.prog=t.value||'ke';
    mlCalcSlot(ML_CALC.prog);
    mlCalcSave();mlCalcPaint();
    return;
  }
  if(t.id==='mlCalcPax'){
    mlCalcLoad();
    var n=mlNum(t.value);
    ML_CALC.pax=(n>=1&&n<=9)?n:1;
    mlCalcSave();mlCalcPaint();
    return;
  }
});
document.addEventListener('input',function(e){
  var t=e.target;
  if(!t||!t.id||!t.closest||!t.closest('#mlCalc'))return;
  mlCalcLoad();
  var slot=mlCalcSlot();
  if(t.id==='mlCalcGo')ML_CALC.go=mlNum(t.value);
  else if(t.id==='mlCalcBack')ML_CALC.back=mlNum(t.value);
  else if(t.id==='mlCalcHave')slot.have=mlNum(t.value);
  else if(t.id==='mlCalcRate')slot.rate=mlRateNum(t.value);
  else if(t.id==='mlCalcTax')ML_CALC.tax=mlNum(t.value);
  else if(t.id==='mlCalcCash')ML_CALC.cash=mlNum(t.value);
  else return;
  mlCalcOut();
  mlCalcSave();
});
document.addEventListener('focusout',function(e){
  var t=e.target;
  if(!t||!t.id||!t.closest||!t.closest('#mlCalc'))return;
  if(t.id==='mlCalcRate'){
    var slot=mlCalcSlot();
    t.value=slot.rate?String(Math.round(slot.rate*100)/100):String(ML_CALC_RATE_DEFAULT);
    if(!slot.rate){slot.rate=ML_CALC_RATE_DEFAULT;mlCalcSave();mlCalcOut()}
    return;
  }
  if(t.id==='mlCalcHave'||t.id==='mlCalcGo'||t.id==='mlCalcBack'||t.id==='mlCalcTax'||t.id==='mlCalcCash'){
    t.value=mlNum(t.value)?KR(mlNum(t.value)):'';
  }
});
document.addEventListener('keydown',function(e){if(e.key==='Escape')mlCloseSheet()});
