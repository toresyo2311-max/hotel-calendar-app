/* ── ⑧ 외항사 마일리지(부산) 탭 ───────────────────────────────────
   부산/김해(PUS)를 떠나거나 도착하는 노선의 '보너스(마일) 좌석'을 항공사
   마일리지 프로그램별로 모아 둔 스냅샷입니다. 원천은 날짜·노선마다 등급별로
   '예약 가능/불가'와 필요 마일, 직항·경유 편수까지만 알려 줍니다. 좌석 수량·
   세금·수수료는 원천에 없어 표시하지 않습니다(항공사 예약 화면에서 확인).
   예약은 언제나 각 프로그램의 공식 사이트로 보냅니다. */
var PMD={meta:null,programs:[],dests:[],rows:[],ready:false,progMap:{},destMap:{},byProg:{}};
var pms={dir:0,alliance:'all',prog:'all',dest:'all',cabin:'all',direct:false,sort:'miles'};

function pmMeta(){return PMD||{}}
function pmKey(o){return o?o.key:''}
function pmWon(n){return n==null?'—':KR(n)+'마일'}
function pmProg(key){return PMD.progMap[key]||null}
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
  pmRenderDir();
  pmRenderAlliance();
  pmRenderProgs();
  pmRenderDests();
  pmRenderBest();
  pmRenderList();
  pmRenderNote();
}

function pmRenderBanner(){
  var b=document.getElementById('pmBanner');
  if(!b)return;
  var m=pmMeta();
  var dirTxt=pms.dir?'부산 도착(→ PUS)':'부산 출발(PUS →)';
  var cnt=(PMD.rows||[]).length;
  b.innerHTML='<b>'+esc(m.sourceLabel||'항공사 마일리지 프로그램별 보너스 좌석')+'</b> · 기준 <b>'+esc(m.observedLabel||'—')+'</b>'
    +' · 앞으로 '+KR(m.windowDays||60)+'일('+esc(m.dateFrom||'')+'~'+esc(m.dateTo||'')+') · '+esc(dirTxt)+' · '+KR(cnt)+'건'
    +'<span class="pm-b2">보너스 좌석은 실시간으로 변동됩니다. 예약 전 <b>각 항공사 공식 사이트에서 재확인</b>해 주세요. '
    +'원천은 노선·날짜마다 등급별 <b>예약 가능 여부와 필요 마일</b>만 알려 주며, 좌석 수량·세금·수수료는 알려 주지 않아 표시하지 않습니다. '
    +'표시된 마일은 원천이 그 등급에 보여 준 <b>최저값</b>이고, 경유편은 편수로 구분합니다.</span>';
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
    +'<div><span>수집 프로그램</span><b>'+KR(withData)+'</b><i>9개 중 · 나머지는 원천에 부산 자료 없음</i></div>'
    +'<div><span>보너스 좌석 행</span><b>'+KR(dirRows.length)+'</b><i>'+(pms.dir?'부산 도착':'부산 출발')+' 방향</i></div>'
    +'<div><span>도시</span><b>'+KR(Object.keys(dests).length)+'</b><i>필터로 좁힐 수 있습니다</i></div>'
    +'<div class="new"><span>가장 적은 마일</span><b>'+(cheapest?KR(cheapest.c.miles):'—')+'</b><i>'
    +(cheapest?esc(pmDestName(cheapest.r[3]))+' · '+esc((cheapest.p&&(cheapest.p.short||cheapest.p.name))||'')+' '+esc(pmCabinShort(cheapest.c)):'—')+'</i></div>';
}

function pmRenderDir(){
  var el=document.getElementById('pmDir');
  if(!el)return;
  var n0=0,n1=0;
  (PMD.rows||[]).forEach(function(r){if(+r[8]===0)n0++;else n1++});
  el.innerHTML='<button type="button" data-pm-dir="0" class="'+(pms.dir===0?'on':'')+'" aria-pressed="'+(pms.dir===0?'true':'false')+'">부산 출발 PUS→ <b>'+KR(n0)+'</b></button>'
    +'<button type="button" data-pm-dir="1" class="'+(pms.dir===1?'on':'')+'" aria-pressed="'+(pms.dir===1?'true':'false')+'">부산 도착 →PUS <b>'+KR(n1)+'</b></button>';
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
      +(pms.dir?'부산 도착(→PUS) 방향은 아직 수집하지 못했습니다 — 다음 수집에서 채웁니다.':'프로그램·등급·직항 조건을 바꿔 보세요.')+'</div>';
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
      return '<article class="pm-card">'
        +'<div class="top"><b>'+esc(pmDestName(r[3]))+'</b><span class="dt">'+esc(pmDateKo(r[1]))+'</span></div>'
        +'<div class="pg">'+esc(p.name)+'<span>'+esc(p.allianceName||'')+'</span></div>'
        +'<div class="cab">'+cs.map(function(c){
          return '<span class="cb '+c.k+'">'+esc(pmCabinShort(c))+' <b>'+KR(c.miles)+'</b> <i>'+esc(pmStopsText(c.stops))+'</i></span>';
        }).join('')+'</div>'
        +'<div class="foot"><span class="seen">최근 확인 '+esc(r[2])+'</span>'
        +'<a class="go" href="'+esc(p.url)+'" target="_blank" rel="noopener">'+esc(p.urlLabel||'공식 예약')+'</a></div>'
        +'</article>';
    }).join('')+'</div>';
}

function pmRenderNote(){
  var el=document.getElementById('pmNote');
  if(!el)return;
  var m=pmMeta();
  var cov=(m.coverage||[]).map(function(c){return esc(c.name)+' '+KR(c.rows)+(c.note?' ('+esc(c.note)+')':'')});
  el.innerHTML='<b>수집 범위</b> — '+(cov.length?cov.join(' · '):'—')
    +'<br>원천은 프로그램마다 부산 노선을 얼마나 추적하는지가 다릅니다. 자료가 0건인 프로그램은 <b>보너스 좌석이 없다는 뜻이 아니라, 그 원천이 부산 노선을 추적하지 않는다는 뜻</b>입니다 — 해당 항공사 공식 사이트에서 직접 조회해 주세요.'
    +'<br>국내선(김포·제주)은 국제선 여행과 성격이 달라 이 화면에서 뺐습니다. 필요 마일은 원천 표시값이며, 같은 노선이라도 날짜·경유 편수·판매 조건에 따라 달라집니다. 세금·수수료는 마일과 별도입니다.';
}

/* ── 이벤트 ───────────────────────────────────────────────── */
document.addEventListener('click',function(e){
  var t=e.target;
  if(!t||!t.closest)return;
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
    var list=document.getElementById('pmList');
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
